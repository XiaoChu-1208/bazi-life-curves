# Elicitation Ethics · v9 · 自适应问答的 6 条工程约束

> **核心命题**：用户对自己 Bazi "格 / 相位" 的预期会**强烈地**污染答题；
> 算法因此必须对用户**保持双盲**——既不告诉用户当前最像什么相位，也不
> 向用户暴露问题在测什么、还要问几道、问题之间的相互关系。
>
> 这不是 nice-to-have，是工程级约束。任何违反的代码改动 = bug。
>
> 配套：[scripts/adaptive_elicit.py](../scripts/adaptive_elicit.py)、
> [scripts/handshake.py](../scripts/handshake.py)、
> [scripts/audit_questions.py](../scripts/audit_questions.py)、
> [references/fairness_protocol.md](fairness_protocol.md)（互补：
> fairness 管 *题目本身的歧视性* / 本文管 *提问过程的诱导性*）

---

## §E1 · 后验信息严格隔离（双盲核心）

**约束**：`posterior` / `phase_candidates` / `prior_distribution` /
`decision_probability` / `decision_threshold` 等任何**反映"算法此刻最像什么"的字段**，
都不得：

- 进入 `askquestion_payload`（即用户在 AskQuestion UI 看到的题面 JSON）
- 通过 LLM 自然语言转述给用户（即"我目前倾向于认为你是 X 格"类话术）
- 写入用户可访问的明文文件（state 文件用 `.` 开头隐藏 + `agent_warning` 字段标记）

**实现位点**：
- `adaptive_elicit.py · _question_to_payload()` 只输出 prompt + options + neutral_instruction
- `handshake.py · _build_askquestion_payload()` 同上
- state 文件路径推荐 `output/.elicit.state.json`（点开头）
- state 文件第一个字段是 `agent_warning`，明文警告 LLM 不要回灌

**反例**：

```
× askquestion_payload[i].weighted_eig = 0.24       ← E1 违反（暴露选题分数）
× askquestion_payload[i].pairwise_target = {a, b}   ← E1 违反（暴露目标 phase）
× LLM: "你刚才答 B，看起来更接近从财格"             ← E1 违反（命名 phase）
```

---

## §E2 · 中间态不命名 phase

**约束**：在 R1 / R2 收敛前，**任何**输出文本中都不得出现具体 phase 标签
（"day_master_dominant" / "从财格" / "化气格"）。`bazi.phase` 在 finalize 之前
不存在；LLM 不得"先猜一个相位再让用户校验"。

**实现位点**：
- `adaptive_elicit.py · cmd_next()` 在 status=ASK 时不输出 phase 信息
- `handshake.py · build_round2()` 输出的 `round1_summary.decision` 仅给 LLM
  内部 reasoning 用，不得作为 user-facing 文本素材

**反例**：

```
× "我先假设你是身强格，问几个题来确认"
× "你的相位有 60% 概率是从势格，30% 概率是真化"
```

为什么硬约束：哪怕 LLM 加 caveat 说"这只是初步推断"，**用户的答题也会受锚定**。
心理学上叫 confirmation bias / anchoring；在 Bazi elicitation 上后验偏移可达 0.2+。

---

## §E3 · 进度不倒推

**约束**：不得告诉用户 "还差 N 题就能确定 / 已经收集了 X% 的信息 /
当前置信度 Y%"。这等价于实时暴露 posterior。

**允许**：模糊的范围（"通常 5–8 题"、"最多不超过 12 题"）。

**反例**：

```
× "还差 2 题就到 high confidence 了"
× "目前置信度 0.78，再答 3 题应该能突破 0.80"
× "已经问完一半了"  ← 暗含 "总长固定 = 算法已经决定了"
```

---

## §E4 · 不揭示题目意图

**约束**：不得告诉用户某道题"在测什么 / 主要区分哪两个相位 / 为什么问这题"。

**允许**：通用的 neutral_instruction（"按直觉选 / 不确定挑最接近的"）。

**反例**：

```
× "这题问的其实是日主强弱"
× "我问体感寒热是因为想区分调候用神方向"
× "这题对你回答的 D4_Q1 来说很关键"  ← 隐性揭示题目相互关系
```

---

## §E5 · 题面 / 选项不带命理词

**约束**：题目 prompt + option label 不得出现：
- phase 词（格局 / 从财 / 真化 / 化气 ...）
- 十神词（正官 / 七杀 / 食伤 / 印星 ...）
- 五行强弱词（身强 / 身弱 / 太过 / 失令 ...）

**实现位点**：
- `_question_bank.py · _check_no_phase_leak()` 模块加载时扫描，v9 阶段先 warn-only
- `audit_questions.py · B1/B2/B3` 静态 detector
- 题库 v10 全量改写后改成 strict assert（CI gate）

**反例**：见 [question_bank_rewrite_examples.md](question_bank_rewrite_examples.md)

---

## §E6 · Batch 通道的额外缓解

batch 模式（`dump-question-set` + `submit-batch`）让用户**一次看到所有题**，
天然增加 sycophancy 风险（用户更容易识别题目意图、更容易在 28 题里保持自洽
的"我是 X 类型人"叙事）。补 3 条缓解：

1. **题集打乱 dimension 顺序**
   `_shuffle_dimensions_deterministic(questions, seed=bazi_fingerprint)`
   防止 "D1 全是家境题、D4 全是体感题" 让用户猜出框架；用 fingerprint 作
   seed 保 bit-for-bit 可复算。

2. **题集顶部固定 caveat**
   `_BATCH_CAVEAT` 文本：

   > 答题提示：请按你最直觉的反应填，不要前后翻看试图保持一致——
   > 刻意追求自洽反而会降低准确度。

3. **Confidence 上限锁 mid**
   batch 提交后，无论 posterior 多高，`confidence` 默认上限是 mid；
   只有 top1 ≥ 0.97 时才解锁 high（极少数极清晰命局）。
   字段 `phase_decision.confidence_cap_applied` 标记是否触发。

**实现位点**：
- `adaptive_elicit.py · _shuffle_dimensions_deterministic()`
- `adaptive_elicit.py · _BATCH_CAVEAT`
- `adaptive_elicit.py · _finalize_phase(... confidence_cap="mid")`

---

## 6 条约束的 enforcement 矩阵

| 约束 | 静态检查 | 运行时检查 | 文档约束 |
|---|---|---|---|
| E1 后验隔离 | `audit_questions.py` payload schema scan | `_question_to_payload` 白名单 | `batch_elicitation_prompt.md` LLM 话术 |
| E2 不命名 phase | LLM prompt audit | `adaptive_elicit.py` agent_instructions | 本文 + `batch_elicitation_prompt.md` |
| E3 不倒推进度 | — | — | 本文 + LLM rule |
| E4 不揭示意图 | — | — | 本文 + LLM rule |
| E5 题面无命理词 | `_check_no_phase_leak` (warn-only v9) | 模块加载日志 | `question_bank_audit.md` |
| E6 batch 缓解 | — | `_shuffle_dimensions_deterministic` + `_BATCH_CAVEAT` + `confidence_cap` | 本文 |

---

## 与 fairness_protocol 的分工

| 文件 | 管什么 | 例子 |
|---|---|---|
| `fairness_protocol.md` | 题目 / 解读**对人群的歧视性**（性别 / 阶级 / 取向） | 不假设 "结婚生子=幸福"、不用"老婆/丈夫"默认顺序 |
| `elicitation_ethics.md` (本文) | 题目 **对算法的诱导性**（暗示用户答案 → 偏移 posterior） | 不命名 phase、不暴露 EIG、不揭示题目意图 |

两个文件**同时 enforce**；audit_questions.py 既扫 fairness 也扫 ethics 命理词。

---

## 历史背景

v8 之前的设计假设：用户答题是"独立、客观、机械化"的过程，因此可以一次抛
26 题、可以解释每题在测什么。

v9 修正这个假设：
- 用户**会预读**题集（尤其 batch 模式）
- 用户**会猜测**算法在测什么
- 用户**会调整**答案以保持"自我形象自洽"
- LLM 转述会**不可避免地**把内部状态泄漏给用户

→ 工程对策：让 LLM 和用户都看不到中间状态。
   `posterior` 全部留在 `.elicit.state.json` 里，用户层面只能看到题面与最终结论。

详见 plan §A6（双盲 6 约束讨论） + plan §A6'（batch 模式的 ethics 妥协）。
