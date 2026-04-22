# Open Phase Anchor Collection Protocol（v9.3.1 新增）

> 当 `multi_school_vote.decision == "open_phase"` 时，agent 必须向用户收集事件锚点。
> 本协议定义**收集这些锚点时不得做什么**，专门治"agent 自创硬约束 + 假反馈循环"这类 UX bug。

---

## §1 触发场景

`scripts/multi_school_vote.py::vote()` 输出 `decision="open_phase"` 时（top1 < 0.55 OR top1_top2_gap < 0.10），agent 必须：

1. 把 `alternative_readings` 全部读法陈列给用户（v9 PR-6 既有要求）
2. 请用户补 ≥ 2 条具体事件年份 + 事件描述
3. 把用户提供的 anchor 灌回 `multi_school_vote.vote(bazi, fallback_phase_candidates=[anchors...])` 重算后验
4. 重算后再决定 adopt phase / 仍 open_phase / 升级到 LLM fallback

本协议管的是**第 2 步和第 3 步**的实现细节。

---

## §2 Agent 不得做的事（硬红线）

### §2.1 不得自创"年龄段"硬约束

**禁止**在 UI / prompt 里加任何形如：

- "请补 ≥ 2 个你 **25 岁前** 真实经历过的事件年份"
- "只收 **本命大运前** 的事件"
- "**成年前** 的锚点更可信"
- "请提供 **童年期** 的标志事件"

**为什么禁**：协议（`scripts/multi_school_vote.py::_generate_must_be_true`）只要求"具体年份 + 事件类型 + 强度"，**没有任何年龄段限制**。年龄段限制是 agent 自己拍脑袋编的（典型 case：把"25 岁前"当成"印星 / 食伤期"的隐喻投射出去），结果用户输近年事件全部被判无效，陷入死循环。

**唯一例外**：算法层（multi_school_vote / phase_posterior）出于贝叶斯计算需要主动在 `evidence_required` 字段里写明某 phase 的 likelihood 在某年龄段更可分辨——这是算法字段，不是 UI 文案。**agent 不得把算法字段直接渲染成对用户的硬约束**。

### §2.2 不得自创"事件类型"硬约束

**禁止**：

- "只收事业类事件，不收感情 / 健康 / 家庭"
- "请提供 ≥ 2 个**学业**事件"
- "请补**正向**事件（不收挫败）"

**为什么禁**：anchor 的判别力来自年份 × 强度的命局共振，事件**类型**只是辅助信息（用于 LLM 后期 narrative）。任何类型的真实事件都能用作 phase 后验更新的证据。

### §2.3 不得自创"强度阈值"硬约束

**禁止**：

- "只收**大事件**，中事 / 小事不算"
- "请补**改变人生轨迹**的标志性年份"

**为什么禁**：强度是 agent 询问的元数据（用于贝叶斯权重），不是 filter。用户主观觉得"小事"的年份在命局上可能正好踩在大运冲合点，反而是高判别力 anchor。

### §2.4 不得自创"地理 / 身份 / 关系状态"硬约束

**禁止**：

- "只收国内事件 / 只收发生在出生地的事件"
- "只收已婚 / 已工作以后的事件"

**为什么禁**：违反 `references/fairness_protocol.md` §4 的盲化原则，且与 anchor 收集本身的目的（phase disambiguation）无关。

---

## §3 Agent 必须做的事（实施铁律）

### §3.1 实时显式校验反馈

**用户每次提交 anchor，agent 必须立刻在同一条响应里告知：**

| 用户输入状态 | Agent 必须显示 |
|---|---|
| 全部 anchor 有效（≥ 2 条） | "✓ 已收 N 条有效 anchor，正在调 multi_school_vote 重算……" |
| 部分有效（< 2 条） | "已收 X 条有效，还差 Y 条；下面这些被判无效：[列表 + 每条原因]" |
| 全部无效（0 条有效） | "本次提交 0 条有效。原因：[每条具体原因，不能笼统]" |
| 解析失败（格式错） | "无法解析年份：[原始输入]。请用 YYYY 格式（例：2003, 2010）" |

**绝对禁止**：

- ❌ 只显示 "已识别 0 个有效年份"，不告诉用户**为什么 0**
- ❌ 显示 "已补事件年份: 2023, 2024 —— 等待重跑校准"，但实际**没真调** `vote()` 重算

### §3.2 提交 = 真重跑

`提交并重跑校准` 按钮 / `[补事件年份]` 命令被触发时，agent **必须实际执行**：

```python
import json
from scripts.multi_school_vote import vote

bazi = json.loads(open(bazi_json_path).read())
anchors = parse_user_anchors(user_input)  # 必须真解析
result = vote(bazi, fallback_phase_candidates=anchors)
# result.decision 可能从 "open_phase" 变成某个 phase_id
```

并把 `result` 的真实变化（top1_posterior 从 X 变到 Y / decision 从 open_phase 变到 phase_id / 仍 open_phase 但 alternative_readings 排序变了）**逐项告知用户**。

**禁止**只回安慰话术（"等待重跑校准 / 正在处理 / 已收到"）但实际没跑命令。

### §3.3 已收 anchor 必须可见 + 可撤销

UI 必须显示：

- 当前已收的所有有效 anchor（年份 + 描述 + 算法判定的强度档）
- 用户能删除某条 anchor 重新提交
- 未达 ≥ 2 条阈值时按钮显示 "还需补 N 条"，达到后才显示 "提交并重跑"

---

## §4 机械护栏（v9.3.1 新增）

| 守卫 | 触发条件 | 动作 |
|---|---|---|
| `_v9_guard.scan_fabricated_anchor_constraint` | agent 即将渲染的 prompt / askquestion_payload / UI label 包含 §2 任一红线模式 | exit 12 + stderr 报告"agent 自创了协议未规定的 anchor 收集约束" |
| `multi_school_vote._generate_must_be_true(decision='open_phase')` | 输出 `must_be_true[0].anchor_collection_rules` 强制 spell out `no_age_window=True` 等 flag | 让下游 agent 没法假装"协议要求 25 岁前" |

---

## §5 历史 Bug 复盘（驱动本协议产生的 incident）

**Date**: 2026-04-22
**Symptom**: 用户对话循环卡死。截图证据：

> 用户连续 3 次输入 `[补事件年份] 2023, 2024（搬家+升职加论文拿奖）`
> Agent 每次回 `已补事件年份: 2023, 2024 —— 等待重跑校准`
> UI 持续显示 `已识别 0 个有效年份`
> 实际从未触发 `multi_school_vote.vote()` 重算

**根因链**：

1. Agent 在抛 open_phase UI 时自加文案 "请补 ≥ 2 个你 25 岁前真实经历过的事件年份"——`25 岁前` 在协议里 **0 命中**（grep `references/` + `scripts/` 全表）
2. UI 用 "出生年 + 25" 作为 cutoff 静默 filter，2023 / 2024 被判无效
3. Agent 没有错误反馈机制，只回固定话术 "等待重跑校准"
4. Agent 实际从未调用 `vote()` 重算，"重跑" 是字面意义的谎言

**修复**：本协议 + `_v9_guard.scan_fabricated_anchor_constraint` + 测试覆盖。

---

## §6 与现有协议的关系

- 上游：`scripts/multi_school_vote.py::vote()` § 5.6 open_phase 逃逸阀
- 上游：`references/llm_fallback_protocol.md` §4 兜底结果回流（vote 重跑触发条件）
- 横向：`references/handshake_protocol.md` HS-R 红线表（本协议增加 HS-R6/R7/R8/R9 四条 fabricated UI constraint 子规则，详见 SKILL.md §2.5 红线表）
- 横向：`references/elicitation_ethics.md` §E1-§E4（agent 不得越权 / 不得静默 filter）
- 下游：`scripts/_v9_guard.py` §6 机械护栏

---

## §7 一句话版

> **Agent 收集 open_phase anchor 时，唯一能 filter 的是"年份是否能解析为合法公历年"和"事件描述是否非空"。其它任何 filter 都是 agent 越权，必须撤销。提交按钮必须真触发 `vote()` 重算，不许打白条。**
