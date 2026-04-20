# 下马威 / 校准握手协议（Handshake Protocol · v6）

> 用户输入八字之后、出图 / 合盘之前，**必须**先输出：
> - **Round 0**（v6 新增）：反询问·感情画像 2 题（**取向校准**）
> - **Round 1**：健康/体感 3 题（**命局校准**）
> - **Round 2**（仅 R1 命中 < 3 时触发）：本性 + 历史锚点 3 题（**交叉验证**）
>
> 用「双层命中率」（R0 取向准确度 + R1 命局准确度）共同决定 `accuracy_grade`，再决定是否继续。

---

## 0. v6 重大变化（2026-04 更新）

| 维度 | v3 | v6 |
|---|---|---|
| 校验轮次 | R1（3 健康）+ R2（3 交叉） | **R0（2 反询问·感情）+ R1（3 健康）+ R2（3 交叉）** |
| 反询问 | 无 | ★ **R0 由系统主动抛 2 题**（偏好类型 + 对方态度） |
| 准确度判定 | 单层（R1 命中率） | **双层**：取向准确度（R0）+ 命局准确度（R1） → 综合 |
| 红线 | 寒热 ✗ + 脏腑 ✗ 双红线 | + **★ 感情①·偏好类型 ✗ + R1 ≤ 1/3** = 第三红线 |
| 取向决策 | 隐式（按 LLM 经验） | ★ **显式 hint**：R0 命中模式直接告诉 LLM 走格局 / 扶抑 / 调候 |
| 适用场景 | 单盘 + 合盘 | 单盘 + 合盘（**合盘 R0 只对提问者本人跑**，对方那盘从结构里读，不再问） |

---

## 1. 为什么 v6 要加 R0 反询问·感情画像

**核心理由：感情画像是八字里"指针最硬"的一类信息**，几乎可以一对一翻译成"你历史上喜欢过的人 + 对方对你的态度"，
而用户对这两件事的记忆（尤其前 2-3 段关系）几乎是终生稳定的。

具体机理：
- **偏好类型 ← 妻/夫星五行 + 夫宫主气十神**
  - 男命财星五行 / 女命官杀五行 → 直接翻译成"你被吸引的人外形 / 体感 / 性格类型"
  - 日支（夫宫）藏干主气十神 → 你"想找的另一半在你心里的角色"
- **对方态度 ← 妻/夫星强弱 + 比劫 + 食伤 + 印 + 桃花**
  - 妻/夫星旺 → 对方主动 / 强势；妻/夫星弱 → 对方被动 / 依赖
  - 比劫强 → 对方有顾虑 / 有竞争；食伤强 → 对方欣赏你才华
  - 印旺 → 对方愿意照顾你；桃花透 → 互动里有"被吸引"的明显气场

这两件事错八字的人**几乎不可能蒙混**——和健康三问形成"取向 + 体感"双向交叉。

更重要的：**R0 的命中模式同时告诉 LLM 应该用哪派方法读这盘**——
- R0 = 2/2 + R1 = 3/3 → 命局结构清晰 → **格局派优先**（高置信展开）
- R0 = 1/2 → 取向有歧义 → **扶抑 / 调候**主调，感情段双解
- R0 = 0/2 + R1 = 3/3 → 时辰大概率对，但取向跑偏 → **改用扶抑 / 调候**，感情段必须双解
- R0 = 0/2 + R1 ≤ 1/3 → 红线，几乎可断定时辰偏 ≥ 1 小时

## 2. 为什么继续保留 R1 健康三问

理由不变（v3 已述）：

- **健康/体感是终生稳定的证据**
- **错八字会让健康三维同时跳档**
- **三个不同侧面 = 三次独立投票**
- **公平**：不需要回忆任何具体事件 / 关系 / 职业

R0 + R1 共 5 条独立指针，覆盖"取向 + 体感 + 脏腑"，是目前能做到的最强校验组合。

## 3. R0 两问的来源（v6 · 脚本机械导出，LLM 不能改）

| # | 侧面 | 来源字段 | 文案表 |
|---|---|---|---|
| ① | 偏好类型（preference） | 妻/夫星五行（男命=最旺财星；女命=最旺官杀）+ 日支主气十神 | `WUXING_TYPE_DESC` × `SHISHEN_DAYAN_TRAIT` |
| ② | 对方态度（attitude） | 妻/夫星强弱 + 比劫 + 食伤 + 印 + 桃花 | `_attitude_descriptor()` 综合产出 |

每条候选含：`category="emotion"` / `claim` / `evidence`（命理依据）/ `falsifiability`（可证伪点 = 你历史上喜欢的人具体是不是这个画像）/ `weight`（仅用于 LLM 提示）。

**重要**：感情①和②**只用于校准 + 加 caveat**，**不进入打分**（emotion 维度的分数走独立通道，由 `score_curves.py emotion_baseline / dayun_delta / liunian_delta` 算出）。

## 4. R1 三问的来源（与 v3 一致 · 脚本机械导出）

| # | 侧面 | 来源字段 | 文案表 |
|---|---|---|---|
| ① | 寒热出汗（temperature） | `bazi.yongshen.climate.label` | `HEALTH_TEMPERATURE` |
| ② | 睡眠 / 精力 / 神经（sleep_energy） | `climate.label` × `strength.label` | `SLEEP_BY_CLIMATE` + `ENERGY_BY_STRENGTH` + `NERVE_BY_CLIMATE` |
| ③ | 易病脏腑 / 体质短板（organ） | `bazi.weakest_wuxing` + `wuxing_distribution[wx].missing` | `ORGAN_BY_WUXING` |

## 5. R2 候选（仅 R1 命中 < 3 时触发；与 v3 一致 · v7.5 加民俗志锚点）

来自旧的「本性画像 + 历史锚点 + 民俗志锚点」池：
- 1 条本性画像（基底 / 反应模式 / 主导动力）
- 2 条历史锚点（按 `deviation·conf·dispute·interaction·recency·life_stage·mp_bonus` 综合分排序）
- **【v7.5 新增】≤ 1 条民俗志锚点**（按 §5.4 规则）—— 仅在脚本能给出 high-confidence folkways_anchor_seed 时使用；否则该名额让位给本性 / 历史锚点

数据不足时实事求是输出 N < 3 条，不强行凑。

### 5.4 【v7.5 新增】民俗志锚点（folkways_anchor）的特殊规则

**脚本侧**：`handshake.py` 在生成 `handshake.json` 时，新增字段 `folkways_anchor_seeds`（list of dict），每个 seed 含：

```json
{
  "year_range": [1996, 2000],
  "user_age_range": [11, 15],
  "era_window_id": "cn_reform_late_90s",
  "associated_bazi_event": "印星受冲 + 流年财库被引动",
  "yongshen_match": ["金"],
  "class_prior_top1": "urban_state_or_educated",
  "anchor_type": "single_event_in_window",
  "suggested_directions": [
    "家庭单位变动（撤并/内退/转岗）",
    "家庭迁居或学区变动",
    "家中重大支出（购置/医疗）"
  ]
}
```

**LLM 侧**：根据 seed **现场**写完整的 R2 民俗志锚点 claim，必须满足：

1. **必须有时间窗**：精确到 ±1-2 年，禁止"小时候 / 那段时期"
2. **必须有可证伪点**：明确写"如果 X 没发生 / 如果你完全没接触过 Y → 这条错"
3. **必须给 ≥ 2 个 suggested_directions**：让用户选，不要问"是不是 X"
4. **confidence 必须 high 或 mid**：禁止 low
5. **援引 era_window 的简短背景**：1 句话铺垫
6. **过 folkways_protocol §4 五项自检**：5 项都答得出
7. **遵守 class_inference_ethics**：禁止身份命名

**示例**：

```
R2 ④【民俗志锚点 · 国企改制末段】
你 11-15 岁那段（1996-2000）—— 1998 ± 1 年是国企整顿 + 朱镕基改革的高峰期。
按你命局的「印星受冲 + 财库被引动」+ 父母 prior「体制气重」推，那段时间你家
最可能经历过以下三种之一：
（a）父母中至少一方的工作单位发生了肉眼可见的变动（部门撤并 / 内退 / 转岗 / 减薪）
（b）家里因为这种变动有过一段集体焦虑期（甚至搬家 / 转学 / 学区变动）
（c）父母没动但身边亲戚邻居有动，你目睹了那种"稳定也会塌"的氛围

请回 (a) / (b) / (c) / 都没有 / 部分（具体哪个）

可证伪点：如果你家在 1996-2000 整段**完全没有**任何上述三种迹象，
甚至父母工作环境/收入完全平稳 → 这条就是错的（说明命局的 class_prior 偏差）
```

**不允许的写法**：

```
✗ "你 11-15 岁是不是经历过家里变动？"   ← 没时代背景，不可证伪
✗ "你那时候是不是看 VCD？"              ← 太普及，没区分度
✗ "你家是不是工人阶级？"                ← 身份命名 → 红线
```

## 5.5 【v7.4 #3 新增】Round 0 反迎合·反向探针（counter-claim probes）

### 为什么要加

R0 两题命中很高的常见**伪命中**：用户被命局画像"带跑"——
看到「你被吸引的是干练果决型」就下意识答「对」，
看到「你被吸引的是温和成长型」也下意识答「对」（因为人都有多面）。
两个**逻辑上互斥**的描述都说"对"是不可能的，必然有一条是迎合性回答。

### 实现位置

`scripts/handshake.py`：
- `_WUXING_OPPOSITE`：相生 / 相克 五行的"对立"映射（金↔木、火↔水、土→木）
- `_SPOUSE_SHISHEN_OPPOSITE`：十神对立（食伤型 ↔ 印星型，财官型 ↔ 比劫型）
- `_build_emotion_preference_counter(bazi, original)`：基于 R0① 推出对立类型 → 反向 claim
- `_build_emotion_attitude_counter(bazi, original)`：基于 R0② 推出对立态度 → 反向 claim
- `build_emotion_counter_probes(bazi, original_pair)`：返回 ≤ 2 条反向 probe
- `build()` 输出新增字段 `round0_counter_probes: List[dict]`，每条带 `paired_with`（指向原 R0 题的 category）

### LLM 抛题位置

R0 ② 答完后、R1 之前**统一抛 2 条反向 probe**（一次性抛，不要拆开）：

```
为了避免你"迎合性"答题（命局推啥就说啥），我再抛 2 条**故意构造的反向陈述**让你校验。
你只需对每条回 「对 / 不对 / 部分」，按你真实记忆答即可——
如果你两条都答「对」，意味着相反的两种描述你都觉得像，逻辑上不可能 → 我会自动给 R0 命中率打折。

⓪'-① 【关系①·反向探针（防迎合）】{counter_probes[0].claim}
   依据：{counter_probes[0].evidence}
   可证伪点：{counter_probes[0].falsifiability}

⓪'-② 【关系②·反向探针（防迎合）】{counter_probes[1].claim}
   依据：{counter_probes[1].evidence}
   可证伪点：{counter_probes[1].falsifiability}
```

### 三态判定（机械化在 `evaluate_responses` 里跑）

| 模式 | 触发条件 | consistency_grade | 后续动作 |
|---|---|---|---|
| **consistent** | n_contradictions = 0 且 n_mirror_signals = 0 | `consistent` | 正常按 R0 命中走 |
| **sycophantic** | n_contradictions ≥ 1（原 = 对 且 反向 = 对） | `sycophantic` | **R0 命中率 × 0.5 打折**；`advisory_caveats` 提醒用户重新校准 |
| **mirror** | n_contradictions = 0 且 n_mirror_signals ≥ 1（原 = 不对 + 反向 = 对） | `mirror` | 命局推反了，建议触发 `--dump-phase-candidates` 跑相位反演 |
| **mixed** | 同时有矛盾 + 镜像 | `mixed` | 走 sycophantic 处理 + 提醒可能时辰错 |
| n/a | 用户没回答任何 counter probe | `n/a` | R0 命中率不打折 |

`evaluation` 字段下新增：

```json
"anti_sycophancy": {
  "n_probes_responded": 2,
  "n_contradictions": 1,
  "n_mirror_signals": 0,
  "consistency_grade": "sycophantic",
  "warning": "检测到 1 组矛盾 ... R0 命中率已自动打 5 折（2.0 → 1.0）。",
  "round0_adjusted_hits": 1.0
}
```

后续所有判定（accuracy_grade / should_proceed / 红线）都用 `round0_adjusted_hits`，不再用原始 `round0_hits`。

### CLI 用法

```bash
# 1. 生成 handshake（包含 R0 + R0_counter + R1 + R2）
python3 scripts/handshake.py \
  --bazi out.bazi.json --curves out.curves.json --out out.handshake.json

# 2. 用户答题后写到 responses.json，机械化评估
python3 scripts/handshake.py \
  --bazi out.bazi.json --curves out.curves.json --out out.handshake.json \
  --user-responses responses.json
# → out.handshake.json 内多一个 "evaluation" 字段
```

`responses.json` 格式：

```json
[
  {"side": "R0", "trait_or_anchor": "关系①·偏好类型", "user_response": "对"},
  {"side": "R0", "trait_or_anchor": "关系②·对方反应模式", "user_response": "对"},
  {"side": "R0_counter", "trait_or_anchor": "关系①·反向探针（防迎合）", "user_response": "不对"},
  {"side": "R0_counter", "trait_or_anchor": "关系②·反向探针（防迎合）", "user_response": "不对"},
  {"side": "R1", "trait_or_anchor": "本性基底", "user_response": "对"}
]
```

### 不允许的写法

- ❌ 不抛 counter probes 直接进 R1（v7.4 强制）
- ❌ 改写 counter probes 的 claim（必须原样使用脚本输出，否则破坏对立性）
- ❌ 把 counter probes 算进 R0 命中率分子（counter 不加分，只检查矛盾 / 镜像）
- ❌ sycophantic 状态下绕过 5 折直接按 raw R0 走
- ❌ mirror 状态下不提醒用户跑相位反演

---

## 6. 命中率 → 准确度（v6 强制双层等级表 + v7.4 反迎合修订）

> **v7.4 修订**：所有 R0 相关判定都改用 `round0_adjusted_hits`（被 anti-sycophancy 折扣后的值）。
> sycophantic 模式下原 R0 = 2/2 会被打成 1/2，按下面 6.3 的 1/2 行处理。

### 6.1 取向准确度（R0 命中）

| R0 命中 | orientation_grade | 含义 |
|---|---|---|
| **2/2** | high | 妻/夫星 + 夫宫读对了 → 命格主调可放心走格局 |
| **1/2** | mid | 一对一错 → 命格主调需双解（格局 + 扶抑） |
| **0/2** | low | 妻/夫星 + 夫宫双偏 → 改走扶抑 / 调候，感情段必须双解 |

### 6.2 命局准确度（R1 命中）

| R1 命中 | chart_grade | 后续动作 |
|---|---|---|
| **3/3** | high | 直接进入 Step 2.7（询问输出格式） |
| **2/3** | mid | 触发 Round 2；R1+R2 ≥ 4/6 → 继续 + 加 caveat |
| **1/3** | low | 触发 Round 2；R1+R2 ≥ 4/6 → 谨慎继续 + 强 caveat |
| **0/3** | reject | 不再追问，强烈建议核对八字（时辰多半错） |

### 6.3 综合 accuracy_grade（v6 = R0 + R1 联合判定）

| R0 | R1 | accuracy_grade | 行动 |
|---|---|---|---|
| 2/2 | 3/3 | **high** | 全速放行；格局派优先 |
| 2/2 | 2/3 | **mid-high** | 进入 + R1 标 caveat；感情段重点写 |
| 1/2 | 3/3 | **mid** | 进入；感情段双解 |
| 1/2 | 2/3 | **mid** | 追 R2，≥ 4/6 才进；感情段双解 |
| 0/2 | 3/3 | **mid-low** | 进入；感情段必须双解，主调改"扶抑/调候" |
| 任意 | 1/3 | **low** | 追 R2，≥ 4/6 才谨慎进入；强 caveat |
| 任意 | 0/3 | **reject** | 拒绝，建议核对八字 |
| **0/2** | **≤ 1/3** | **★ 红线 reject** | 妻/夫星 + 健康同时崩 → 时辰偏 ≥ 1 小时高度可疑 |

caveat 模板：
- 中等：「八字命局结构基本对，但具体年份事件强度需打折看；感情走势按 X 派解读为主、Y 派为辅。」
- 强：「双层校验只命中 N/5 条，曲线 / 合盘结论的可信度上限较低 —— 仅当方向参考，具体数值不要当真，感情段需要你自己再校准。」

## 7. 红线规则（v6 三红线）

★ 若【健康①·寒热出汗】被用户标 "✗"：
  → climate.label 多半判错，**立即停止**，告知用户：
    "寒热体感没对上 → climate 判读可能反了 → 我需要重新审视命局结构再给你跑一遍"

★ 若【健康③·脏腑短板】被用户标 "✗"：
  → 五行权重多半算偏（常见于时辰错导致月柱 / 时柱跳位），**立即停止**，建议：
    用 `--gregorian` 重新解析；或把时辰 ±1 小时各跑一次对比脏腑短板。

★ **v6 新增**：若【感情①·偏好类型】被标 "✗"，**且 R1 命中 ≤ 1/3**：
  → 妻/夫星 + 健康同时崩盘，时辰偏 ≥ 1 小时几乎可断定，**立即停止**，建议：
    用 `--gregorian` 重新解析；或把时辰 ±1 小时各跑一次对比 R0 + R1。

注：单独 R0 ✗ 但 R1 ≥ 2/3 → 不算红线，按 6.3 综合表走（mid-low），主调改扶抑 / 调候，感情段必须双解。

## 8. LLM 输出格式（v6 强制）

完整模板（脚本输出 `instruction_for_llm` 字段已包含）：

```
在画图 / 合盘之前，我先做两轮校验。

== Round 0：反询问·感情画像（v6 · 取向校准）==
这两题不是为了"算桃花"，而是用来校准我该用哪派方法读你这盘。
你只要回想一下你印象最深的 2-3 段关系（喜欢过 / 暗恋过 / 在一起过都算）
然后逐题选最贴近的一项就行。

① 【感情①·偏好类型】{claim}
   选项：
     A. {option_a 从你妻/夫星五行翻译}
     B. {option_b}
     C. {option_c}
     D. 都不太像
   依据：{evidence}
   可证伪点：{falsifiability}

② 【感情②·对方态度】{claim}
   选项：
     A. {option_a 从你妻/夫星强弱 + 比劫 + 食伤 + 印 + 桃花翻译}
     B. {option_b}
     C. {option_c}
     D. 都不太像
   依据：{evidence}
   可证伪点：{falsifiability}

== Round 1：健康三问（命局校准）==
请逐条回 「对 / 不对 / 部分」。这三条都是终生稳定的体感证据。

① 【健康①·寒热出汗】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}

② 【健康②·睡眠精力】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}

③ 【健康③·脏腑短板】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}

（双层命中率 → 综合准确度：
  R0 = 2/2 + R1 = 3/3 → 高，全速放行；
  R0 = 0/2 + R1 ≤ 1/3 → 红线，几乎可断定时辰偏 ≥ 1 小时；
  其余按双层等级表走，可能追 R2 三条交叉。）
```

## 9. 不允许的写法

- ❌ 跳过 R0 直接抛 R1（v6 必须 R0 先抛）
- ❌ 跳过 R1 直接出图 / 跑合盘
- ❌ 改写 R0 / R1 的 claim（必须原样转述脚本文案 + 选项）
- ❌ 在 R0 里加事件类问题（"你哪一年谈过恋爱"）—— 那是 R2 的范畴，且 R2 不能问感情
- ❌ 用模糊话术（"应该差不多"——必须给可证伪点 + 选项）
- ❌ 红线触发后绕过去继续
- ❌ 把感情维度的分数和 R0 命中数挂钩 —— **R0 仅做校准，emotion 走独立通道**
- ❌ 在合盘场景里给对方那盘也抛 R0（v6 只问提问者本人；对方的偏好/态度从你这盘读）

## 10. 合盘场景的特殊要求（v6 修订）

详见 `he_pan_protocol.md`，要点：

- 用户输入多份八字 → **R0 只对提问者本人那盘抛**（对方的"偏好类型 + 对方态度"从你这盘的夫宫 + 财/官星直接读，不再问你回忆对方喜欢谁）
- **每份八字都要单独跑 R1 健康三问**
- 用户对自己的八字答得最准；对对方答不上来 → 标 caveat
- 主体（提问者本人）必须 R0 ≥ 1/2 **且** R1 ≥ 2/3 才放行合盘
- 合盘 confidence：
  - 双方 R1 都 ≥ 2/3 + 提问者 R0 ≥ 1/2 → high
  - 一方 R1 ≥ 2/3、另一方 < 2/3 → mid + 注明
  - 双方 R1 都 < 2/3 → low，劝退

## 11. 校验通过 → Step 2.7 询问输出格式（v5 不变）

R0 + R1（或 + R2）通过后**不要直接进 Step 3 渲染 HTML**。先按 `SKILL.md §2.7` 主动问用户：

```
校验通过 ✓（R0 N/2 · R1 M/3 · 综合 grade = high/mid/low）。
在我开始写分析之前，问一下你想要哪种输出：
(A) 纯 markdown 流式输出 —— 我每写完一节就立刻发给你，最快
(B) markdown 流式 + 最后渲染 HTML 交互图（v6 · 8 条曲线 含感情线）—— 多等 5-15 秒
回 A 或 B（默认 A）。
```

**默认值规则**：
- 单盘：默认 A
- 合盘：默认 A（合盘没有"曲线图"）
- 用户初次提问已说"画图 / 出 artifact / 给我图" → 直接走 B
- 用户初次提问已说"口头说说 / 不用图" → 直接走 A

**禁止**：
- ❌ 跳过 Step 2.7 默认渲染 HTML
- ❌ 用户回 A 之后还跑 render_artifact.py
- ❌ 把 Step 3a 内容憋成大段一次性吐出

## 12. 当 R1 命中 < 4/6（合并 R2 后仍不达标）时怎么办

⚠️ **v7 新增·重要**：在跳到"试不同时辰"之前，**必须先跑 §13 相位反演校验循环**。
"算法读反"比"时辰错"更常见，且不需要重新问用户。

只有在 §13 全部相位候选都 < 4/6 时，才进入下面的时辰扫描：

```bash
for h in 12 13 14 15 16; do
  python scripts/solve_bazi.py --gregorian "1990-05-12 $h:30" --gender M --out /tmp/bazi_$h.json
  python scripts/score_curves.py --bazi /tmp/bazi_$h.json --out /tmp/curves_$h.json --age-end 60
  python scripts/handshake.py --bazi /tmp/bazi_$h.json --curves /tmp/curves_$h.json --out /tmp/hs_$h.json
done
```

把 5 份 R0 + R1 并排呈现给用户，让用户挑哪个时辰的"偏好类型 + 健康问题"最对得上 → 反推真实时辰。

---

## 13. 【v7 新增】R0+R1 命中率 ≤ 2/6 → 相位反演校验循环（P1-7）

### 13.1 背景：为什么命中率低不一定是八字错

某用户 1996 年八字 `丙子 庚子 己卯 己巳`：

- **默认 Skill 推法**：壬水日主主导（实际是己土）+ 印星化杀 + 身弱用印 → R0/R1 命中率 ≈ 30%
- **LLM 反向推法**：丙火财星主事 + 日主借力 + 上燥下寒 → R0/R1 命中率 ≈ 90%

**幅度差** = 60 个百分点。这不是八字错，是**算法的相位选择反了**。本协议把这种"算法读反"的兜底纠错机械化、纳入闭环。

### 13.2 强制流程（不允许跳过 · v7.2 加二轮校验 + Auto-Loop）

```
R0 + R1 + R2 命中率
   ↓
  ≥ 4/6 → 进入 Step 3 出图（happy path）
  ≤ 2/6 → 【强制】进入相位反演校验循环 ↓
       ↓
       【v7.2 推荐 · 一条命令】
       python scripts/phase_inversion_loop.py --bazi <bazi.json> --out-dir out/ --default-hit-rate "X/6"
         自动 4 步：dump 候选 → pick top-1 → score_curves --override-phase → handshake --phase-id（二轮 6 题）
         输出 handshake_round2.json（按反演相位重生成的 R0/R1/R2 6 题）
       ↓
       (1) 读 handshake_round2.json，按 v7.2 话术抛 6 题给用户：
           「命中率 X/6 比较低，但这**不一定意味着**你八字错。
            另一种常见可能是『**算法读法方向反了**』。
            最有希望的反向假设是 [pick]：[pick_explain_for_user]。
            为了证伪/证实这个猜测，我按反演相位重新出了 6 题——
            这 6 题在反演相位下的答案应该跟之前**显著不同**，请你重新作答。」
       (2) 用户作答 → 算二轮命中率
       (3) 二轮命中率 ≥ 4/6 → 落地：
           python scripts/save_confirmed_facts.py --bazi <bazi.json> \
               --add-structural phase_override day_master_dominant <pick> \
               --reason '二轮校验 X/6 → 反演落地'
           之后所有 score_curves --confirmed-facts 自动应用反演 → 进 Step 3 出图（带「相位 = X」标记）
       (4) 二轮命中率 < 4/6 + 还有候选 → 重跑 phase_inversion_loop.py --pick <next_id>
       (5) 全部候选都 < 4/6 → §12 时辰扫描
```

### 13.3 LLM 必守 4 条话术铁律（v7.2 · 详见 phase_inversion_protocol.md §5）

1. **不允许第一句话就说"八字错"**：必须先说"另一种可能是算法读反"
2. **不允许反演后默认跑**：必须用户同意才跑
3. **二轮校验是强制的**：把 `handshake_round2.json` 的 6 题完整抛给用户重新作答，**禁止**根据反演候选直接出图
4. **重跑后必须明确告知"已反演"**：第一段输出必带「相位 = X，不是默认相位」

### 13.4 何时**跳过**相位反演

- 默认相位 R0+R1+R2 ≥ 4/6 → 跳过（happy path）
- `dump_phase_candidates` 返回 `n_triggered = 0` → 跳过（4 类 detect 都没触发，命中率低更可能是八字错）
- 用户明确说"我确定八字对，不需要试反向假设" → 跳过，按时辰扫描走

### 13.5 相位反演的成功证据

```json
// confirmed_facts.json 写入示例
{
  "kind": "phase_override",
  "value": "climate_inversion_dry_top",
  "evidence": {
    "default_phase_hit_rate": "2/6",
    "inverted_phase_hit_rate": "5/6",
    "swing": "+50%",
    "from_detector": "P3_climate_inversion",
    "detector_score": "3/3"
  },
  "reason": "上燥下寒：干头丙庚己己全燥（+8.5），地支双子湿（-5.5）→ 用神锁水"
}
```

下次跑同一个 `bazi_key` → Step 0 自动加载 `phase_override` → 跳过相位反演，直接用 override 跑。

## 14. 与其他保障的关系

- **accuracy_protocol.md**：R0 + R1 双层命中率是 accuracy 的"实时自检指标" —— 综合 grade ≤ low 即 accuracy 保障被破
- **fairness_protocol.md**：R0 + R1 都不接收身份信息（R0 只让用户在四选一里挑最贴近的画像）→ 满足盲化
- **prediction_protocol.md**：未来预测的 confidence 上限 ≈ R1 命中数 / 3；感情维度的 confidence 上限 ≈ R0 命中数 / 2
- **he_pan_protocol.md**：合盘的 confidence = min(双方 R1 命中率) × max(0.5, R0 命中率/2)（短板效应 + R0 加权）
- **multi_dim_xiangshu_protocol.md §10**：感情维度的 LLM 解读模板必须援引 R0 命中情况（标题强制带 `R0 = N/2`）
