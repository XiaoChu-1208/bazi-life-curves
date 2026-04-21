# Phase Decision Protocol · v9（自适应贝叶斯问答）/ v8.1 兼容

> **v9（本文件当前版本）**：R1 的 disambiguation 信号收集从「一次性 26 题」
> 切到「自适应 EIG 单题流式」（[scripts/adaptive_elicit.py](../scripts/adaptive_elicit.py)），
> 平均 5–8 题落地（最多 12 题、prior 强先验时 0 题 fast-path）。后验更新公式
> 与 v8 完全一致（`decide_phase` / `weight_class × likelihood`），变化只在
> **何时问 / 问哪一题 / 何时停**这三个维度。
>
> 详见 [handshake_protocol.md §0](handshake_protocol.md) v9 段 +
> [elicitation_ethics.md](elicitation_ethics.md) §E1–§E6 双盲约束。
>
> 本协议替代 [phase_inversion_protocol.md](phase_inversion_protocol.md) 的「事后兜底」立场。
> 旧协议把"反演"做成"R0+R1+R2 命中率 ≤ 2/6 时才触发"的兜底机制；新协议把"相位决策"做成 `solve_bazi` 阶段就强制要做的一等公民，由 detector 算先验、用户校验答案算后验、贝叶斯落地。
>
> 历史背景：典型边界 case 中, 6 个 detector 满分（P5 三气成象 4/4 + P3 调候反向 3/3 + P4 假从触发），但默认 `bazi.json` 仍按 `day_master_dominant` 输出，全因"反演"在旧协议里是事后兜底。详见 [diagnosis_pitfalls.md](diagnosis_pitfalls.md) §13。

---

## §1 心智模型 · identification vs disambiguation

```
┌─────────────────────┬─────────────────────────────┬──────────────────────────┐
│ 责任方              │ 任务                        │ 输出                     │
├─────────────────────┼─────────────────────────────┼──────────────────────────┤
│ 算法（detector）    │ identification              │ 候选 phase 全集          │
│                     │ 穷尽结构性自洽的可能 phase  │ + 各 phase 的先验概率    │
├─────────────────────┼─────────────────────────────┼──────────────────────────┤
│ 用户（校验回路）    │ disambiguation              │ 在已穷尽的候选间投票     │
│                     │ 通过外部观察事实做最终选择  │ （AskQuestion 多选答案） │
├─────────────────────┼─────────────────────────────┼──────────────────────────┤
│ 算法（decide_phase）│ posterior decision          │ 后验分布 + top-1 phase   │
│                     │ 贝叶斯综合先验 + 用户答案    │ + 置信度                 │
└─────────────────────┴─────────────────────────────┴──────────────────────────┘
```

**关键边界**：算法负责"我能想到的可能"，用户负责"在我能想到的可能里哪一个像你"。算法不能因为"我自己倾向选 A"就只把 A 抛给用户校验——这是旧协议把 R0 题面只按默认相位生成的根本错误。

---

## §2 候选 phase 全集

由 6 个 detector（住在 [_bazi_core.py](../scripts/_bazi_core.py)）共同贡献，覆盖 14 个 phase_id：

| phase_id | 短描述 | detector |
|---|---|---|
| `day_master_dominant` | 默认 · 日主主导（扶抑 + 调候 + 格局正向） | （baseline，无 detector） |
| `floating_dms_to_cong_cai` | 弃命从财（日主虚浮 → 财星主事） | P1 |
| `floating_dms_to_cong_sha` | 弃命从杀（日主虚浮 → 官杀主事） | P1 |
| `floating_dms_to_cong_er` | 弃命从儿（日主虚浮 → 食伤主事） | P1 |
| `floating_dms_to_cong_yin` | 弃命从印（日主虚浮 → 印星主事） | P1 |
| `dominating_god_cai_zuo_zhu` | 旺神得令 · 财星主事 · 日主借力 | P2 |
| `dominating_god_guan_zuo_zhu` | 旺神得令 · 官杀主事 · 日主受制 | P2 |
| `dominating_god_shishang_zuo_zhu` | 旺神得令 · 食伤主事 · 日主泄秀 | P2 |
| `dominating_god_yin_zuo_zhu` | 旺神得令 · 印主事 · 日主被庇护 | P2 |
| `climate_inversion_dry_top` | 调候反向 · 上燥下寒（用神锁水） | P3 |
| `climate_inversion_wet_top` | 调候反向 · 上湿下燥（用神锁火） | P3 |
| `pseudo_following` | 假从格 · 仍按弱身扶身但加 caveat | P4 |
| `true_following` | 真从格 · 按从神方向走 | P4 |
| `huaqi_to_<wuxing>` | 化气格（土/金/水/木/火） | P6 |

P5（三气成象）不另立 phase，而是输出 `floating_dms_to_cong_<最强非日主十神>` 之一。

---

## §3 先验分布算法

每个 detector 输出 `phase_likelihoods: Dict[phase_id, float]`（本 detector 对各 phase 的支持度，∑ = 1.0），由 `_phase_likelihoods_from_detector()` 计算。融合规则：

```python
# 1. 起始 prior 取均匀分布（14 phase 各 1/14）
prior = {pid: 1.0 / N for pid in ALL_PHASE_IDS}

# 2. 对每个 detector 输出的 phase_likelihoods，按贝叶斯独立证据相乘
for det in triggered_detectors:
    for pid in prior:
        prior[pid] *= det["phase_likelihoods"].get(pid, 1e-6)
    prior = _normalize(prior)  # 防数值下溢

# 3. 注入 day_master_dominant baseline（避免极端 case 把默认相位概率压到 0）
prior["day_master_dominant"] = max(prior["day_master_dominant"], 0.05)
prior = _normalize(prior)
```

**关键设计**：先验 + 多 detector 同时触发用乘性融合（独立证据假设），不用加性。这意味着两个 detector 都强烈支持同一 phase 时，先验会显著高于单 detector 触发。

---

## §4 后验更新公式

用户答完 N 道题后：

```
P(phase_i | answers) ∝ prior(phase_i) × ∏_{j} likelihood(answer_j | phase_i)^{w_j}

其中：
  w_j = 2.0 if question_j.weight_class == "hard_evidence" else 1.0
  likelihood(answer_j | phase_i) = question_j.likelihood_table[phase_i][answer_option_j]
```

硬体征（D1 家庭客观事实 / D3 流年方向 / D4 中医体征）权重 2× 软自述（D2 关系自述 / D5 本性画像）。

实现住在 [_bazi_core.decide_phase()](../scripts/_bazi_core.py)。

---

## §5 R1 落地阈值（首轮 disambiguation 后）

| R1 后验 top-1 概率 | 行动 | confidence |
|---|---|---|
| ≥ 0.95 且 runner-up < 0.02 | 可直接出图（仍**强烈推荐**走 R2） | high |
| 0.60 – 0.95 | 必须走 **Round 2 confirmation** | mid / high |
| 0.40 – 0.60 | 必须走 **Round 2**（confirmation_threshold 决定是否出图） | low |
| < 0.40 | 报告"算法无法落地，请核对时辰 / 性别"，不出图 | reject |

实现住在 [phase_posterior.py](../scripts/phase_posterior.py)（`--round 1`）。

---

## §6 phase / 调候 / 用神 / 喜神 / 忌神 耦合落地表

`decide_phase()` 落地时一并写入 5 元组（不能各自决策）。表中省略号项由 [`_strength_to_dom_wuxing()`](../scripts/score_curves.py) 按命局动态推导。

| phase_id | strength.label | yongshen | xishen（生用神） | jishen（克用神） | climate 翻向 |
|---|---|---|---|---|---|
| `day_master_dominant` | 原值 | 原值 | 生用神之五行 | 克用神之五行 | 不变 |
| `floating_dms_to_cong_cai` | 强（从神为主）| 财（克日主） | 食伤（生财） | 比劫（夺财） | 不变 |
| `floating_dms_to_cong_sha` | 强（从神为主）| 官杀 | 财（生杀） | 印（化杀） | 不变 |
| `floating_dms_to_cong_er` | 强（从神为主）| 食伤 | 比劫（生食伤） | 印（克食伤） | 不变 |
| `floating_dms_to_cong_yin` | 强（从神为主）| 印 | 官杀（生印） | 财（破印） | 不变 |
| `dominating_god_cai_zuo_zhu` | 弱 | 财 | 食伤 | 比劫 | 不变 |
| `dominating_god_guan_zuo_zhu` | 弱 | 官杀 | 财 | 印 | 不变 |
| `dominating_god_shishang_zuo_zhu` | 弱 | 食伤 | 比劫 | 印 | 不变 |
| `dominating_god_yin_zuo_zhu` | 弱 | 印 | 官杀 | 财 | 不变 |
| `climate_inversion_dry_top` | 不变 | 水（润降） | 金（生水） | 土（克水） | 翻为"上燥下寒" |
| `climate_inversion_wet_top` | 不变 | 火（暖局） | 木（生火） | 水（克火） | 翻为"上湿下燥" |
| `pseudo_following` | 弱 | 原值 | 原 xishen | 原 jishen | 不变 + caveat |
| `true_following` | 强 | 旺神 | 生旺神 | 克旺神 | 不变 |
| `huaqi_to_<wx>` | 强 | 化神 | 生化神 | 克化神 | 不变 |

---

## §7 Round 2 confirmation（v8.1）

R1 用宽口径判别题选出 top phase 之后，R2 是**第二批独立证据**的 confirmation 步骤。设计原则：

1. **题目挑选目标变了**：从"对全部候选的 prior 加权平均判别力"换成"对 R1 决策 phase
   与 R1 runner-up phase 的 pairwise L1 区分度"（`pairwise_discrimination_power`）；
2. **题源排除 R1 已答题**：避免循环喂相同信号；
3. **D3 流年题重生**：仅在 decided vs runner-up 两个 phase 之间找预测分歧最大的年份生成；
4. **决策一致性 + 概率门槛**：

   | 条件 | confirmation_status | action |
   |---|---|---|
   | R2 决策 == R1 决策 AND R2 prob ≥ 0.85 | `confirmed` | render |
   | R2 决策 == R1 决策 AND 0.65 ≤ R2 prob < 0.85 | `weakly_confirmed` | render_with_caveat |
   | R2 决策 == R1 决策 AND R2 prob < 0.65 | `uncertain` | escalate |
   | R2 决策 != R1 决策 | `decision_changed` | escalate（必须报告） |

实现住在 [`_bazi_core.assess_confirmation()`](../scripts/_bazi_core.py)，CLI 入口
[`phase_posterior.py --round 2`](../scripts/phase_posterior.py)。详细流程图见
[handshake_protocol.md §4](handshake_protocol.md)。

> **R2 是默认推荐路径**：除非 R1 后验 ≥ 0.95 且 runner-up < 0.02，否则一律必须走 R2。
> Hard cutover 自 v8.0 起，旧"low → 追问 1 轮"的 ad-hoc 路径被 R2 confirmation 替换。

---

## §8 与旧 phase_inversion_protocol.md 的关系

旧协议被本协议**全面替代**，但 [phase_inversion_loop.py](../scripts/phase_inversion_loop.py) 脚本保留可运行（避免破坏旧 confirmed_facts）。新流程下不再调用该脚本——它只剩"调试用手工分步"价值。

旧协议中"4 类相位反演候选"的 P1-P4 标号在本协议里依然作为 detector_id 使用（P1_floating_day_master 等），但语义不再是"事后反演候选"，而是"事前 detector 给出的 phase_likelihoods 来源"。
