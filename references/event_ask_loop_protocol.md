# 事件 Ask-Loop 协议（Event Ask-Loop · v9.6）

> **v9.6（本文件）**：在 [adaptive_elicit](handshake_protocol.md) 自适应贝叶斯问答收敛后，
> 当 top1 仍未达到高置信（典型 < 0.85）时，启动**事件 ask-loop**——抛若干历史
> 年份的「是否发生明显事件」清单题，根据用户答案做独立 Bayesian 收敛，
> 把候选 phase 的后验向「与用户真实经历最一致」的方向拉。
>
> 设计立场：性格自述（elicit）和事件经历（event）是**两条独立的贝叶斯通道**，
> 各自更新后验后再做加权对数融合（默认 1:1.2，事件略高于性格）。最终融合
> 后验由 [scripts/apply_event_finalize.py](../scripts/apply_event_finalize.py)
> 写回 `bazi.json.phase_decision`，下游 [score_curves](../scripts/score_curves.py)
> 和 [virtue_motifs](../scripts/virtue_motifs.py) **必须重跑**才能看到效果——
> 这是 2026-04 修复的真 bug：之前后验只在内存，deliver 拿到旧判定。

---

## §0 何时启用

**入口条件**（由编排者判定，本协议不强制）：

- `adaptive_elicit next` 已收敛或截停（`finalized: true`）
- 但 `phase_decision.top1_p < 0.85` 且 `elicitation_path != "fast_path"`
- 且候选 top-k（默认 k=4）里至少 2 个 phase 后验仍 ≥ 0.05（否则没有可区分对象）

**不启用**的情况：

- 0 题 fast-path（初始 prior top1 ≥ 0.85）—— 已经高置信
- elicit 末态 top1 ≥ 0.85 —— 已经收敛
- 用户显式拒答历史事件类问题 —— 直接走 elicit 后验出图（带 `warning_level: weak/refuse`）
- candidate_phases 全部缺乏可预测年份（如纯 day_master_dominant 主导且无大运冲合）—— 转验证题或定档

---

## §1 Stage A：disjoint 年清单题（独占预测年）

**目标**：找出**只有一个候选 phase** 预测会触发事件的年份，问用户那年是否真发生明显事件。
答 yes 强烈支持该 phase；答 no 强烈否定该 phase。

### §1.1 出题（[scripts/event_year_predictor.py](../scripts/event_year_predictor.py)）

对每个候选 phase，按以下规则计算它在用户生平里**应当**发生明显事件的年份（公历）：

1. **registry 的 `zuogong_trigger_branches`**：大运 / 流年地支命中即触发
2. **phase 相关「十神标签」**：流年 `gan_shishen` / `zhi_shishen` 命中即触发
3. （`reversal_overrides` 暂不参与—— [mangpai_events.py](../scripts/mangpai_events.py)
   独立产出年份级 events，可后续融合）

`select_disjoint_year_batch` 返回若干 `DisjointPick(year, sole_phase, all_predictions)`：
该年只有 `sole_phase` 预测有事件，其余候选都预测无事件。

**EIG 截断**：`sole_phase` 当前后验 ≤ 0.05 视为「已死」，不再问那年（避免空答浪费用户体力）。

### §1.2 题面（人话）

- 主语：「你 YYYY 年（你 NN 岁那年）」
- 问句：「是不是发生过比较明显的事？比如健康、感情、工作、家庭里的大动静」
- 选项：`yes` / `partial`（有波动谈不上大事）/ `no` / `dunno`（记不清）
- **铁律**：题面**不**告诉用户那年对应哪个 phase 预测什么事件——会污染答案

### §1.3 似然表（[event_elicit.py](../scripts/event_elicit.py) §似然表）

```
P(answer | phase 预测此年触发):     yes 0.55  partial 0.25  no 0.10  dunno 0.10
P(answer | phase 不预测此年触发):   yes 0.20  partial 0.20  no 0.50  dunno 0.10
```

**「记不清」必须中性**（两条似然 P(dunno|·) 相等）。代码用 assert 强制——
否则等于隐式逼用户回忆，违反「不替用户记忆」铁律。

### §1.4 Bayesian 更新

每抛一批 batch，对每个候选 phase 乘以对应似然，再归一化：

```
P_event(phase | answers) ∝ P_event(phase) × Π_year P(a_year | phase 是否预测 year)
```

事件通道 posterior **独立于 elicit 通道**——初始为 candidates 上的 uniform，每轮
更新只用事件答案，不掺 elicit 数据。

### §1.5 Stage A 退出条件

- batch 抛空（所有 disjoint 候选已用尽 / 全被 EIG 截断）→ 转 Stage B
- 任一 candidate 的 event posterior ≥ 0.85 → 进收敛 / 验证题
- 已问年数累计 ≥ 5 → 强制转 Stage B 或验证题（避免疲劳）

---

## §2 Stage B：重叠年事件类型判别（v2 · 零 LLM）

**目标**：当 disjoint 年用尽，剩下若干「多个候选 phase 都预测有事件」的重叠年，
问用户**那年发生的事件属于哪一类**，根据类别命中区分候选。

### §2.1 出题（[event_elicit_stage_b.py](../scripts/event_elicit_stage_b.py)）

候选年枚举：`find_overlap_year_candidates(state, bazi, max_candidates=8)` —— 每年至少 2 个候选 phase 都预测有事件。

挑分歧最大年（`select_best_overlap_year`）——按 Jaccard 加权后验：

```
score(year) = Σ_{i<j} (1 - jaccard(cats_i, cats_j)) × π_i × π_j
            (i,j ∈ 该年命中的候选 phase, π = 当前 event posterior)
```

`cats_i` 来自 [phase_event_categories.py](../scripts/phase_event_categories.py) 的
`PHASE_EVENT_CATEGORIES` 静态映射（12 大类，纯数据，零 LLM）。

### §2.2 题面（人话）

- 主语：「你 YYYY 年那次比较明显的事，主要是哪一类？（多选）」
- 选项：从 `EVENT_CATEGORIES`（12 类）里挑该年候选 phases 全集中提到的几条
- 始终包含 `__none_of_above__`（"以上都不是"）作为 sentinel
- 允许自由输入（free_text），由编排者调 LLM 做 categorical 映射后传回 `chosen_categories`

### §2.3 categorical 似然（v3 · 查表 + Jaccard）

`update_with_category_answer(state, pick, discrete, chosen, free_text, summary)`：

```
likelihood(phase_i | chosen) = jaccard(chosen, cats_i)  ∈ [0, 1]
```

Jaccard 全为 0（"以上都不是"或全部无交集）→ 全部候选乘以一个低均匀值，
等价于该年信息无效，不污染后验。

`discrete` 兼容 yes/partial/no/dunno（向上兼容 Stage A 字段），但 Stage B 主信号
来自 `chosen_categories`。

### §2.4 LLM 在 Stage B 的唯一介入

用户除了勾选还填了自述时，编排者调 `classifyFreeText` 把自述映射成
`(discrete, chosen_categories, summary)` 后再传回 `update-stage-b`。

LLM 失败 / 超时 / 解析失败 → 用户的勾选已经是主信号，free_text 部分降级
为 summary 留档，不影响 Bayesian 更新。

---

## §3 验证题（[event_verification.py](../scripts/event_verification.py)）

**目标**：Stage A + Stage B 后融合后验 top1 ≥ 0.85（或人为指定）时，抛 1 道
**透明的复核题**——让用户最终拍板。

### §3.1 透明告知契约

题面**显式**告知三件事：
1. 这是验证题（不是猜测题）
2. 当前判定的 phase 中文名
3. 命中 / 落空的后果（命中 → 把握度上拉 ≥ 0.92；落空 → 触发回退重判）

与 [methodology.md](methodology.md)「命理师之道」§II「判错时要诚实」对齐。

### §3.2 选年策略

`find_verification_year`：选 top1 phase 预测最强、其它候选完全沉默的年份
（强独占，区别于 Stage A 的 disjoint）。

### §3.3 likelihood 不对称

```
hit (yes):     top1 后验 × 5     (大幅放大)
partial:        × 1               (中性)
miss (no):     top1 后验 × 0.2   (大幅缩小)
dunno:         × 1               (中性)
```

落空触发回退：`top1 -> top2`，从 top2 起重新跑短一轮 Stage A 或直接走 elicit 后验。

### §3.4 退化策略

- 找不到强独占年 → 不抛验证题，按融合后验直接 deliver（带原警示档）
- LLM 题面生成失败 → 用 fallback 模板（`fallback_question_text`）

---

## §4 收敛阈值（[event_elicit.py](../scripts/event_elicit.py) §CONFIDENCE_TIERS）

```
high:  ≥ 0.80    干净 deliver（无警示）
soft:  ≥ 0.70    deliver + 轻警示（"未到充分置信，请保留怀疑权"）
weak:  ≥ 0.60    deliver + 重警示（"明显偏低，请优先信你的直觉"）
       < 0.60   refuse / low_confidence_offer（再答一轮 / 自由输入年份 / 退款）
```

**2026-04 调整记录**：原阈值 0.85 / 0.79 / 0.69 太严苛（77.9% 落到"重警示"档不合理）。
新档位 80/70/60 是基于真实数据回看的妥协。

---

## §5 后验融合（事件通道 ⊗ elicit 通道）

`fuse_posteriors(elicit_posterior, event_state, elicit_weight=1.0, event_weight=1.2)`：

```
log P_fused(p) = w_e × log P_elicit(p) + w_v × log P_event(p)   再归一化
```

**为什么 1:1.2 而不是 1:1**：
- 事件比性格自述更"硬"（用户更难撒谎）→ 事件略高
- 但避开 1:1.5+（事件主导 → 滑向宿命）和 1.2:1（性格主导 → 易被巧言蒙过）
- 1:1.2 ≈ 事件 55% / 性格 45%
- 命主对性格的选择能反向改变命运 → elicit 通道不能被压扁

**候选集只取 `event_state.candidate_phases`**（其它 phase 在事件通道里没参与，
强制它们继承 elicit 后验既不公平也无必要）。

---

## §6 后验回写 + 重跑下游

[scripts/apply_event_finalize.py](../scripts/apply_event_finalize.py) 是**唯一的**写回入口：

```bash
python scripts/apply_event_finalize.py \
    --bazi out/bazi.json \
    --posterior '{"phase_id": 0.82, ...}' \
    --stop-reason event_loop_converged
```

内部行为：
1. 读 `bazi.json`
2. 调 [adaptive_elicit._finalize_phase](../scripts/adaptive_elicit.py)（**复用同一套
   字段写入逻辑**：phase / phase_decision / strength_after_phase / yongshen_after_phase /
   xishen / jishen / climate）
3. 加两个标记字段：
   - `phase_decision.event_loop_finalized: true`
   - `phase_decision.elicitation_path: "event_loop_v9.6"`
4. 写回 `bazi.json`

**写回后必须重跑**（编排者职责）：
1. `python scripts/score_curves.py` —— 曲线按新 phase 喜忌算
2. `python scripts/virtue_motifs.py` —— 德性母题独立通道
3. `python scripts/render_artifact.py` —— 出 HTML

否则 deliver 拿到的还是旧 phase 的曲线和母题——这是 v9.6 修的真 bug。

---

## §7 编排者契约（Claude / 调用方）

本套 7 个脚本是**纯逻辑工具**，不含交互循环。完整的"问→答→收敛"循环由
编排者负责（参考 [SKILL.md](../SKILL.md) §"事件 Ask-Loop 编排"）：

1. 调 [event_elicit_cli.py init](../scripts/event_elicit_cli.py) 拿初始 state
2. 循环：
   - `pick-disjoint` / `find-overlap` + `pick-stage-b` → 拿 batch
   - 把每个 `DisjointPick.year` / `OverlapYearCandidate.year` 翻译成自然语言问用户
   - 用户自然语言回答 → 编排者调 LLM 分类成 `discrete + chosen_categories + summary`
   - `update-stage-a` / `update-stage-b` → 拿新 state
   - 调 `evaluate` 看是否收敛
3. 收敛后或用尽 / 截停后 → `apply_event_finalize.py` 写回
4. 重跑 `score_curves.py` + `virtue_motifs.py`

**自然语言 → discrete 映射规范**（编排者必须遵守）：
- 用户「那年我父亲去世了 / 我考上大学 / 离婚了」→ `yes`
- 用户「没什么特别的 / 平淡」→ `no`
- 用户「想不起来 / 不确定 / 算了吧」→ `dunno`
- 用户「有点变化但不算大事」→ `partial`
- **不要诱导**：题面不说"这年你应该会有……"，等用户自述再分类

---

## §8 退化与 fallback

| 情况 | 处理 |
|---|---|
| Stage A 抛空 + Stage B 无候选 | 直接走融合后验 deliver，警示档由 §4 决定 |
| 5 题后仍未收敛 | `--stop-reason exhausted`，按当前最高后验定档，向用户说明"信心略低，请把曲线当趋势参考" |
| 用户拒答（多次 dunno） | 视同 fast-path 退化，用 elicit 后验直接 deliver |
| 验证题落空 | 触发 top1 → top2 回退，从 top2 起重跑短一轮 Stage A |
| LLM 自述分类失败 | 降级为 `dunno`（中性，不污染后验），summary 写"(自述解析失败)" |

---

## §9 工程不变量（assert 强制）

- Stage A 似然表归一性：两表 sum == 1.0
- 「记不清」中性：`P(dunno | predicted) == P(dunno | not_predicted)`
- 候选集封闭：fuse_posteriors 输出的 keys ⊆ event_state.candidate_phases
- 后验归一性：每次更新后 Σ posterior == 1.0
- 已问年不重复：`asked_years` 严格累积，`pick-disjoint` / `pick-stage-b` 不会
  返回已在 `asked_years` 里的年份

违反任一条 → 代码 assert 直接 fail，不让脏数据进 deliver。

---

## §10 与其它协议的关系

- [handshake_protocol.md](handshake_protocol.md) §0 自适应路径 → **本协议是其下游兜底**
- [elicitation_ethics.md](elicitation_ethics.md) §E1–§E6 双盲约束 → 事件通道也遵守：
  题面不告知 phase id / 不告知预测内容 / 后验写在隐藏 state 文件
- [phase_decision_protocol.md](phase_decision_protocol.md) → `phase_decision.event_loop_finalized`
  是新增可选字段，下游读取必须容错（可能不存在）
- [mangpai_protocol.md](mangpai_protocol.md) → 盲派事件断与本协议是**独立通道**，
  不参与本协议的 Bayesian 通道，但可作为未来 `reversal_overrides` 触发源
