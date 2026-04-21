# Batch Elicitation Prompt · v9 · LLM 话术模板

> 配套 [scripts/adaptive_elicit.py](../scripts/adaptive_elicit.py) 的 batch 快速通道使用。
> Agent 在调起第一题 `AskQuestion` 之前，**必须以纯文本形式**把本文档的 §1
> 模板贴给用户（不进 askquestion_payload，避免污染答题语境）。

---

## 一、开场白模板（每个新会话第一次抛题前发出，仅一次）

下面这段是 LLM 给用户的固定话术，逐字使用即可（不要重写不要翻译不要改顺序）：

```
开始之前先说一下流程：
我会按贝叶斯信息增益算法，从题库里挑最能帮我落地相位的题给你，
通常 5–8 题就能定下来；最多不超过 12 题。

如果你想一次性快速搞定（少几次来回），也可以直接贴答案。两档可选：
- 核心 14 题（hard evidence 主战，体征 + 原生家庭 + 流年节奏）
- 完整 28 题（再补主观自述，准确度更高但要多答 14 道）

需要的话回复 "给我 14 题清单" 或 "给我 28 题清单"，我会一次性列出所有题。
否则直接答下面这第一题，我按你的节奏推进。
```

> 不要在话术里：
> - 提"目前最像 X 格 / 倾向于 X 相位"（违反 elicitation_ethics §E2）
> - 提"还差 N 题就到 high confidence"（违反 §E3 进度倒推）
> - 解释"为什么问这题"（违反 §E4 不揭示意图）

---

## 二、用户回复 → 路径分流（关键词识别）

| 用户回复包含关键词 | 触发动作 |
|---|---|
| "给我 14"、"核心 14"、"14 题清单"、"core14" | 跑 `dump-question-set --tier core14` → 把 markdown 贴回 |
| "给我 28"、"完整 28"、"28 题清单"、"full28" | 跑 `dump-question-set --tier full28` → 把 markdown 贴回 |
| 含 "一次"、"batch"、"全部"、"一起答" 但未明确档位 | 反问："要核心 14 题还是完整 28 题？" 一次（不要循环追问）|
| 直接给出选项（如 "B"、"D4_Q1=A"、"A、B、C..."）| 走单题流式：`adaptive_elicit.py next --answer 'qid:opt'` |
| 其他自然语言 | 视作没明确选 batch，继续抛单题 |

---

## 三、Batch 题集贴回 → submit-batch

用户贴回答案后，LLM 解析成 `{qid: opt}` 形式。支持以下格式（脚本端的
`_parse_batch_answers` 已经容错）：

**A · 行式**
```
D1_Q1_birth_economic_condition=B
D4_Q3_organs=A
D3_Q_age33_overall=C
...
```

**B · JSON**
```json
{"D1_Q1_birth_economic_condition": "B", "D4_Q3_organs": "A", ...}
```

**C · 简短行式（脚本不接受简写，LLM 必须补全 qid）**
```
1. B
2. A
3. C
...
```
LLM 看到这种短答时，要按题集导出顺序补全 `qid`，再交给 submit-batch。

LLM 把整理好的 dict 写到 `output/batch_answers.json`，然后调：

```bash
python scripts/adaptive_elicit.py submit-batch \
    --bazi output/bazi.json --curves output/curves.json \
    --answers output/batch_answers.json \
    --out output/bazi.json
```

返回的 stdout 是 `{"status": "DONE_BATCH", ...}` JSON；LLM 不要把
`decision_probability / confidence_cap_applied` 等字段直接念给用户看，
按 elicitation_ethics §E1 / §E2 翻译成中性叙事。

---

## 四、Confidence 上限规则（务必告知用户的部分）

| 路径 | confidence 上限 | 触发条件 |
|---|---|---|
| 单题流式 (`next`) | high | 满足 S1 强落地 + 用户耐心答完 |
| batch (`submit-batch`) | mid | 默认。即使 prob ≥ 0.95 也封顶在 mid |
| batch + 高确定 | high | top1 prob ≥ 0.97（极少数极清晰命局）|

**理由**（写进 elicitation_ethics §E6）：batch 模式让用户一次看到所有题，
更容易出现"我是 X 类型人"的元叙事而不自知地保持自洽答题，对算法等于注入
sycophancy；流式模式每题独立，元叙事难形成。

---

## 五、Anti-Pattern · 严禁出现的话术

```
× "我先看看你是哪个相位，再决定要问什么"          ← 违反 §E2 不暴露后验
× "再答 3 题就能确定了"                          ← 违反 §E3 进度倒推
× "这题问的其实是日主强弱 / 印星格"                ← 违反 §E4 不揭示意图
× "你刚才答 B，看起来更像 X 格"                    ← 违反 §E5 不命名相位
× "我建议你选 A，因为这样我就能更确定了"            ← 违反 §E6 不诱导回答
× "如果你不确定就跳过这题吧"                       ← 违反 §E1 用户应在选项内表达不确定
```

把这些场景全部转写成中性、就事论事的措辞，详见
[elicitation_ethics.md](elicitation_ethics.md)。

---

## 六、Batch 题集本身的 caveat（脚本已自动注入到 markdown 顶部）

`dump-question-set` 输出的 markdown 顶部固定带这段话，不需要 LLM 额外加：

```
> 答题提示：请按你最直觉的反应填，不要前后翻看试图保持一致——刻意追求自洽
> 反而会降低准确度。不要试图揣测题目想测什么；如不确定可挑最接近的一项。
```

LLM 把题集贴回时务必带这段 caveat（即"原样贴回 markdown 文件内容"，不要
裁剪）。
