# 合盘协议（He Pan / Synastry Protocol · v2 · v9.3 化）

> 用户输入 ≥ 2 份八字，从 4 个关系维度（合作 / 婚配 / 友谊 / 家人）做兼容性分析。
> **整体动作逻辑与单盘对齐：每份八字单独走 v9 adaptive_elicit 完成 phase 落地，再做合盘评分，最后流式写 13 节 markdown（含每人「我想和你说的话」三段）。**
>
> v9.3 核心变化（对比 v1）：
>
> 1. **R1 校验路径整体迁到 v9 adaptive_elicit**：每份八字独立跑 `adaptive_elicit.py next` 单题流式（旧 v6/v7 R0/R1「健康三问 + 命中率」路径已退役，仅 `--ack-batch` / `BAZI_HEPAN_BYPASS_V8_GATE=1` 兜底可用）
> 2. **多人编排走 `he_pan_orchestrator.py --mode plan-v9 / next-person`**：plan-v9 输出每个人 phase 状态 → next-person 串行驱动 elicit state；旧 `collect-r1` / `apply-answers` 模式（v8 一次性 R1 batch）标 deprecated，需 `--ack-batch` 显式承认
> 3. **每个人 phase 必须 finalize**：`he_pan.py` 入口守卫拒绝 `phase.is_provisional=true` 或 `confidence < 0.60`（PR-2 · `BAZI_HEPAN_BYPASS_V8_GATE=1` 可强行过，需写明原因）
> 4. **每个人独立跑 `virtue_motifs.py`**：合盘解读末尾追加每个人的「我想和你说的话」三段（位置 ④ declaration · 位置 ⑤ love_letter · 位置 ⑥ free_speech）；合盘场景下 motif 取交集（双方都触发的母题）做"双人共振"提示，不取并集
> 5. **流式分节升级到 13 节**：旧 10 节（概览 / 总分定调 / 4 层 / 加分 / 减分 / tips / 总结）尾部新增 3 节 closing 三段 × N 人；R-STREAM-1/R-STREAM-2 物理铁律同样适用
> 6. **HTML 默认关闭**：合盘默认就走纯 markdown 流式，HTML 汇总表仅在用户**主动**说「要 HTML / 给我图」时才跑（v9.3 删除原 Step 2.7 询问输出格式）

---

## 1. 4 个关系维度（rel_type）

| key | 名称 | 主要看 | 加分项 | 减分项 |
|---|---|---|---|---|
| `cooperation` | 合作关系 | 财、官、印、比劫互动 + 大运同步度 | 财官印配（资源 + 上下级 + 认可） | 比劫夺财、双方都纯比劫无财 |
| `marriage` | 婚配 | 日柱合 / 夫妻宫（日支）/ 五行互补 / 配偶星 | 日干合、日支六合、桃花互见、贵人互见、男看正财 / 女看正官 | 日支冲（大忌）、忌神在对方旺、大运反向 |
| `friendship` | 友谊 | 比肩 / 食伤同道 + 用神互助 | 互为比劫（同道）、互为食伤（一起搞事） | 七杀过多 → 友谊里有较劲 |
| `family` | 家人（可选第 4 维）| 印 / 比为主 + 长辈宫 / 子女宫 | 互为印（庇护教养）、互为比劫（同辈扶持）、杀印相生（严父慈子） | 父母宫（年柱）冲、子女宫（时柱）冲 |

## 2. 评分 4 层（脚本机械算）

`scripts/he_pan.py` 对每对人组合（A↔B）计算 4 层分数，求和得到 `total_score`：

### Layer 1：五行互补（`score_wuxing_complement`）
- A 用神在 B 八字里占比 ≥ 18% → **+(ratio×30)** 分
- A 用神在 B 八字里占比 < 5% → **-3** 分
- A 忌神在 B 八字里占比 ≥ 25% → **-(ratio×24)** 分
- 双向计算

### Layer 2：干支互动（`score_ganzhi_interactions`）
- 天干合化（柱位加权：日 1.0、月 0.9、时 0.7、年 0.6）→ +6×w
- 天干相冲 → -4×w
- 地支六合 → +7×w；**日支六合婚配额外 +5**
- 地支六冲 → -6×w；**日支冲婚配额外 -4（大忌）**
- 地支相害（穿） → -3×w
- 三合 / 半合 → +4
- 桃花互见 → +4
- 天乙贵人互见 → +5

### Layer 3：十神互配（按 rel_type focus）（`score_shishen_match`）
分 4 个 rel_type 子规则：
- **婚配**：男看正财 +12 / 偏财 +8 / 官杀 -6；女看正官 +12 / 七杀 +8 / 财星 -6（双向）
- **合作**：互为财 +6 / 一方官杀+另一方印 +8 / 互为比劫 +4（中性偏正，提示比肩夺财）
- **友谊**：互为比劫 +10 / 食伤 +5 / 出现七杀 -4
- **家人**：互为印 +8 / 互为比劫 +6 / 杀印相生 +6

### Layer 4：大运同步（`score_dayun_sync`）
- 在 `focus_years` 区间，看双方所走大运的天干 vs 各自用神是否同步
- 大运干属用神 / 生用神 → polarity = +1
- 大运干属忌神 / 克用神 → polarity = -1
- 同号年数 / 总年数 = `sync_ratio`
- 得分 = (sync_ratio - 0.5) × 20，范围 [-10, +10]

## 3. 总分等级（仅供 LLM 内部定调，不直接报给用户）

| total_score | grade | label |
|---|---|---|
| ≥ 50 | A | 结构性高度匹配 |
| 25 ~ 49 | B | 总体匹配，有亮点也有要注意的点 |
| 5 ~ 24 | C | 中性 / 平淡，看双方主观经营 |
| -15 ~ 4 | D | 偏摩擦 / 需双方刻意磨合 |
| < -15 | E | 结构性高摩擦，长期相处会很累 |

⚠️ **不要把 grade 直接报给用户**——尤其 D / E 等级，会让人不舒服。LLM 必须把它转化为人话，描述具体的"摩擦点"和"如何缓冲"，而不是甩等级。

## 4. 与 v9 校验回路的关系（v9.3 强制）

合盘前必须保证每份八字本身的 phase 都已 finalize 落地，否则一切结构性配伍都是空中楼阁。

### 4.1 每份八字独立走 v9 adaptive_elicit（旧 R1 健康三问已退役）

```bash
# 多人合盘的 v9.3 推荐路径：用 he_pan_orchestrator 串行驱动
python scripts/he_pan_orchestrator.py \
    --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json \
    --names Alice Bob \
    --mode plan-v9 \
    --out /tmp/he_pan.plan.json
# 输出每个人的 phase status：is_provisional / confidence
# 若任一人 is_provisional=true → 走 next-person 串行 elicit

# 串行驱动（每次 advance 一人 / 一题）：
python scripts/he_pan_orchestrator.py \
    --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json \
    --names Alice Bob \
    --mode next-person \
    --state /tmp/he_pan.elicit.state.json
# 内部对 needs_r1 队首调 adaptive_elicit.py next，
# elicit state 文件按 _prefix(name) 隔离命名空间存到
# /tmp/he_pan.elicit.state.json 的 per_person[<name>] 子树
```

LLM 把每个人的 ASK payload 用宿主结构化 `AskQuestion` 抛单题，回答后写回 state，循环至该人 finalize（触发 S1/S2/S3/S4 早停或 0 题 fast-path）。

> **多人 elicit state 命名约定（v9.3）**：
>
> - 单人：`output/<name>.elicit.state.json`（与单盘一致）
> - 多人合盘：`output/he_pan.elicit.state.json`，内含 `per_person: {<name>: {...单人 state...}}` 子树；`he_pan_orchestrator next-person` 自动按 `_prefix(name)` 路由
> - 题目 ID 在合盘 ASK payload 里加前缀 `<prefix>_<qid>`（例如 `alice_D1_Q3_father_presence`），收回答时由 `split_answers()` 拆回各自命名空间

### 4.2 合盘 confidence 由短板决定（v9.3 改用 phase.confidence 而非旧 R1 命中率）

| 双方 phase 状态 | 合盘 confidence | LLM 解读权限 |
|---|---|---|
| 双方都 finalize 且 `confidence ≥ 0.85` | high | 可以重一些，给具体年份 / 具体场景建议 |
| 任一方 `0.60 ≤ confidence < 0.85` | mid | 必须加 caveat："另一方 phase 置信度仅 mid，结论作为方向参考" |
| 任一方 `confidence < 0.60` | reject | `he_pan.py` PR-2 守卫直接 exit 3；建议改用 `BAZI_HEPAN_BYPASS_V8_GATE=1` 强行过并写明原因，或先核对该方时辰 / 性别再回到 §4.1 |
| 任一方 `is_provisional == true` | reject | 同上，必须先跑 `adaptive_elicit` 完成 disambiguation |

> **他人 confidence cap 规则**：用户对自己的八字最熟，但对方的八字（配偶 / 合伙人 / 朋友 / 家人）能答的题往往少 —— 即使全部答完，confidence 也建议人工 cap 到 mid（除非用户明确表示"对方配合度高，每题都能精确回答"）。`he_pan_orchestrator next-person` 会在 `per_person.<name>.context_hint == "other"` 时给出 cap 提示。

### 4.3 红线（v9.3 沿用 _v9_guard 机械护栏）

- `he_pan.py` 任一参与者 `phase.is_provisional == true` 或 `confidence < 0.60` → exit 3（PR-2 守卫）
- `he_pan_orchestrator collect-r1` / `apply-answers` 旧 v8 batch 模式 → 默认 stderr 打 deprecated 警告；需传 `--ack-batch` 显式承认才能跑
- 合盘解读流式写作过程中，用户看到的任何 `## ` heading 必须落在 §5 13 节序内；越界 / 节序回退 → `_v9_guard.check_message_heading_count` + render_artifact `--required-node-order` 双重拦截

## 5. LLM 解读规则（强制 · v9.3 13 节流式输出）

### 5.1 必做（v9.3 13 节序）

合盘 markdown 输出必须按下面 13 节顺序流式 emit（每写完一节立刻 send 一条 assistant message · R-STREAM-1）：

```
## 概览                      ← Node 1：N 人 / 关系类型 / confidence（基于 phase 短板）
## 总分定调                  ← Node 2：人话定调，不甩 grade
## 第 1 层 · 五行互补         ← Node 3：援引 ≥ 2 条 layers[0].notes
## 第 2 层 · 干支互动         ← Node 4：援引 ≥ 2 条 layers[1].notes，标出关键合 / 冲
## 第 3 层 · 十神互配         ← Node 5：按 rel_type 重点
## 第 4 层 · 大运同步         ← Node 6：focus_years 哪些年同向 / 反向
## 关键加分项 · 怎么用         ← Node 7：援引 top_pluses
## 关键减分项 · 怎么避         ← Node 8：援引 top_minuses
## 关系类型 tips             ← Node 9：按 rel_type 给特定建议
## 总结                      ← Node 10：「如果决定做 X，怎样能更顺」

# 以下是「我想和你说的话」收尾三段 × N 人（v9.3 新增 · 与单盘 §13 closing 三段同源）
## 我想和你说                 ← Node 11：每个人各写一段（按 names 顺序，二人合盘 = 2 段；标题用 `## 我想和你说 · <name>` 区分）
## 项目的编写者想和你说         ← Node 12：仅 motifs.love_letter_eligible == true 的人写
## 我（大模型）想和你说         ← Node 13：每个人各写一段
```

每节用 markdown 标题逐一标记，**禁止把多节挤进一条 message**（R-STREAM-2 物理审计 · `_v9_guard.check_message_heading_count(allow_closing_chain=False)`，仅 closing 三段允许在最后一条 turn 紧邻出现）。

#### 4 层逐层解读细则

1. **按层逐一解读**：每层至少援引 2 条 notes
2. **加分项 / 减分项要写"怎么用 / 怎么避"**：
   - 加分（top_pluses）：为什么这条结构有意义 + 实操中怎么用上（比如"日支六合 → 你们一起做决定时容易达成共识，重要决策建议同桌当面谈，不要异地分头决定"）
   - 减分（top_minuses）：摩擦点是什么 + 怎么缓冲（比如"日支冲 → 同住时小事易摩擦，建议各自有独立空间 + 重大节日错峰相处"）
3. **focus_years 大运同步度**要落到具体建议（"未来 5 年共有 4 年同向 → 适合一起搞大事 / 创业 / 买大件"或反过来"未来 5 年只有 1 年同向 → 各自做事，重大共同决策推迟到 2030 后"）
4. **关系类型敏感性**：
   - 婚配：日柱合 / 日支冲必须明确指出，是婚配关键
   - 合作：财官印配 + 警惕比劫夺财
   - 友谊：比劫食伤同道 = 长久；七杀过多 = 易争胜
   - 家人：代际庇护（印） + 同辈互助（比）

#### Closing 三段 × N 人 写作细则（v9.3 新增）

- 每位参与者的「我想和你说的话」三段（位置 ④/⑤/⑥）独立成节，**首行 markdown header 严格遵循 v9.3 白名单**：
  - `## 我想和你说 · <name>`（位置 ④ declaration）
  - `## 项目的编写者想和你说 · <name>`（位置 ⑤ love_letter，仅 motifs.love_letter_eligible=true 写）
  - `## 我（大模型）想和你说 · <name>`（位置 ⑥ free_speech）
- 数据源：每人独立跑过的 `output/<name>.virtue_motifs.json`；`he_pan.py --require-virtue-motifs` 守卫确保所有人 motif 文件齐全（缺任一人 → exit 7；`BAZI_HEPAN_SKIP_VIRTUE=1` 兜底）
- **合盘场景 motif 取交集做"双人共振"提示**：在 Node 11 的 declaration 里若两人都激活了同一母题（按 motif id 取 ∩），写一句"双方都被同一种东西反复抓住"作为合盘特有暗线，不替代单人 declaration 内容；并集不写
- 调性铁律 + 反身性铁律 + 禁用词表 完全沿用 [`virtue_recurrence_protocol.md`](virtue_recurrence_protocol.md) §3.5 / §8 / `references/tone_blacklist.yaml`

### 5.2 禁止

- ❌ 直接给"配 / 不配"二元结论
- ❌ 把 grade 直接报给用户（"你们是 D 级"）
- ❌ 跳过任一人 v9 adaptive_elicit phase finalize 直接合盘（PR-2 守卫强制）
- ❌ 不援引脚本 notes 凭"感觉"打分
- ❌ 在合盘里夹带"前世今生 / 命中注定"等不可证伪话术
- ❌ 给"建议分手 / 建议结婚 / 建议合伙"这种代替用户做决定的话——只给"如果决定做 X，怎样能更顺"
- ❌ 把所有节点憋在末尾一次性吐（v5 流式 + R-STREAM-1/R-STREAM-2 物理铁律）
- ❌ 默认渲染 HTML / 主动询问"要 markdown 还是 HTML"（v9.3 默认 markdown-only · 旧 Step 2.7 已删除）
- ❌ closing 三段使用旧 v9 白名单（`## 走到这里` / `## 写到这里我想说` / `## 不在协议里的话`）或更早的 `## 灵魂宣言` / `## 情书` / `## 承认人性` 等模板词（命中即 exit 10）

## 6. 工作流（合盘版 · v9.3）

```
Step 0  收集 N 份八字（≥ 2）+ 关系类型 + 关注年份
Step 1  对每份八字跑 solve_bazi.py
Step 2  对每份八字跑 score_curves.py（生成各自 curves.json）
Step 2a 对每份八字跑 mangpai_events.py（可选 · score_curves 已内置基础调用）
Step 2.5 多人 R1 校验（v9 adaptive_elicit · 串行）：
        ↓
        python scripts/he_pan_orchestrator.py --mode plan-v9 …
        ↓ 输出每人 phase status + needs_r1 名单
        ↓
        for name in needs_r1:
            python scripts/he_pan_orchestrator.py --mode next-person --state …
            → 内部 dispatch 到 adaptive_elicit.py next（per-person state）
            → LLM 调宿主 AskQuestion 抛单题 → 写回 answer → 循环至 finalize
        ↓ 全部 finalize 后回到 plan-v9 验证 needs_r1_count == 0
        ↓
        若任一人最终 confidence < 0.60 → 让用户复核该方时辰 / 性别再重跑
        若对方八字 confidence cap 到 mid → 标 caveat 但允许继续，合盘结论降权
Step 2.6 对每份八字跑 virtue_motifs.py（v9.3 必跑 · 合盘 closing 三段数据源）：
        ↓
        for each bazi:
            python scripts/virtue_motifs.py --bazi <bazi.json> --curves <curves.json> --out <name>.virtue_motifs.json
        ↓
        计算合盘 motif 交集（用于 Node 11 的"双人共振"暗线提示）
Step 3  跑 he_pan.py（生成 he_pan.json）：
        python scripts/he_pan.py --bazi … --names … --type … \
            --require-virtue-motifs <name1>.virtue_motifs.json <name2>.virtue_motifs.json \
            --out he_pan.json
        ↓ 缺任一人 motif → exit 7（BAZI_HEPAN_SKIP_VIRTUE=1 兜底）
        ↓ 任一人 phase 未 finalize → exit 3（BAZI_HEPAN_BYPASS_V8_GATE=1 兜底）
Step 4  LLM 在对话里按 §5 规则**13 节流式分节写解读**（每写完一节立刻发出，禁止憋整段 · R-STREAM-1/R-STREAM-2 物理铁律）：
        ▸ Node 1-10  评分解读（与 v1 兼容）
        ▸ Node 11    每人「我想和你说」（位置 ④ declaration · 含双人共振一句）
        ▸ Node 12    每人「项目的编写者想和你说」（仅 love_letter_eligible=true）
        ▸ Node 13    每人「我（大模型）想和你说」（位置 ⑥ free_speech）
Step 5  保存反馈到 confirmed_facts.json（每方一条）
```

**v5 流式硬要求 + v9.3 R-STREAM-1/R-STREAM-2 物理铁律**：上述 13 节必须按节流式输出，每节落盘走 `scripts/append_analysis_node.py --node <key> --markdown-file <md>`；单条 assistant message 的 user-facing markdown 不允许 ≥2 个顶级 `## ` heading（closing 三段允许在最后一条收尾 turn 紧邻出现）。
**v9.3 默认输出**：合盘默认就走纯 markdown 流式；HTML 汇总表仅当用户**主动**说「要 HTML / 给我图 / 出 artifact / 给我 chart」时才跑——绝对不主动询问「要 markdown 还是 HTML」、绝对不主动渲染 HTML。原 Step 2.7 询问输出格式已退役。

## 7. 命令行示例（v9.3）

```bash
# 1. 双人婚配 · 完整 pipeline

# 1.1 各自跑单盘 pipeline 直到 phase finalize + virtue_motifs
for who in p1 p2; do
  python scripts/solve_bazi.py --gregorian "1990-05-12 14:30" --gender M --orientation hetero --longitude 121.5 --out /tmp/${who}_bazi.json
  python scripts/score_curves.py --bazi /tmp/${who}_bazi.json --out /tmp/${who}_curves.json --age-end 80
  python scripts/virtue_motifs.py --bazi /tmp/${who}_bazi.json --curves /tmp/${who}_curves.json --out /tmp/${who}_virtue_motifs.json
done

# 1.2 多人 R1 校验 · 串行 next-person
python scripts/he_pan_orchestrator.py \
    --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json \
    --names 男方 女方 \
    --mode plan-v9 \
    --out /tmp/he_pan.plan.json
# … 按 plan 输出 needs_r1_for 名单，逐人 next-person 跑 adaptive_elicit …

# 1.3 合盘
python scripts/he_pan.py \
    --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json \
    --names 男方 女方 \
    --type marriage \
    --focus-years 2026 2027 2028 2029 2030 \
    --require-virtue-motifs /tmp/p1_virtue_motifs.json /tmp/p2_virtue_motifs.json \
    --out /tmp/he_pan_marriage.json

# 2. 三人合作（创业团队）
python scripts/he_pan.py \
    --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json /tmp/p3_bazi.json \
    --names CEO CTO COO \
    --type cooperation \
    --focus-years 2026 2027 2028 \
    --require-virtue-motifs /tmp/p1_virtue_motifs.json /tmp/p2_virtue_motifs.json /tmp/p3_virtue_motifs.json \
    --out /tmp/he_pan_team.json
# 输出含所有 C(3,2)=3 对配对的评分

# 3. 友谊 / 家人（同样需要 virtue_motifs；--require-virtue-motifs 顺序与 --bazi 一一对应）
python scripts/he_pan.py --bazi a.json b.json --names 我 朋友A --type friendship \
    --require-virtue-motifs a.vm.json b.vm.json --out hp.json

python scripts/he_pan.py --bazi a.json b.json --names 我 母亲 --type family \
    --require-virtue-motifs a.vm.json b.vm.json --out hp.json

# 4. 兜底：跳过 virtue_motifs 守卫（不推荐 · closing 三段会显示空话）
BAZI_HEPAN_SKIP_VIRTUE=1 python scripts/he_pan.py --bazi a.json b.json --names A B --type marriage --out hp.json
```

## 8. 输出 schema 简表（v2 · 与 v1 兼容）

```jsonc
{
  "version": 2,                                // v9.3 起升到 2
  "rel_type": "marriage",
  "rel_name": "婚配",
  "n_persons": 2,
  "names": ["男方", "女方"],
  "pillars": ["庚午 辛巳 壬子 丁未", "甲子 丙寅 戊午 庚申"],
  "focus_years": [2026, 2027, /* ... */],
  "phase_summary": [                           // v2 新增 · 每人 phase + virtue_motifs 元数据
    {"name": "男方", "phase_id": "yang_ren_jia_sha", "confidence": 0.87, "is_provisional": false,
     "virtue_motifs_path": "/tmp/p1_virtue_motifs.json", "love_letter_eligible": true},
    {"name": "女方", "phase_id": "guan_yin_xiang_sheng", "confidence": 0.72, "is_provisional": false,
     "virtue_motifs_path": "/tmp/p2_virtue_motifs.json", "love_letter_eligible": false}
  ],
  "shared_motif_ids": ["L1_…", "K2_…"],        // v2 新增 · 双人共振母题（按 motif id 取交集）
  "pairs": [
    {
      "pair": "男方 ↔ 女方",
      "total_score": -9.1,
      "grade": {"grade": "D", "label": "...", "color": "orange"},
      "layers": [
        {"layer": "五行互补", "score": 1.3, "notes": [/* ... */]},
        {"layer": "干支互动", "score": 5.6, "notes": [/* ... */]},
        {"layer": "十神互配（婚配）", "score": -6.0, "notes": [/* ... */]},
        {"layer": "大运同步", "score": -10.0, "notes": [/* ... */], "sync_ratio": 0.0, "detail": [/* ... */]}
      ],
      "top_pluses": [/* 排序后取 top 6 */],
      "top_minuses": [/* 排序后取 top 5 */]
    }
  ]
}
```

## 9. 与 fairness / accuracy / prediction / virtue_recurrence 协议的关系

- **fairness_protocol.md**：合盘只看八字结构，不接受姓名 / 关系状态 / 历史 → 满足盲化；任何"配/不配"结论必须可证伪
- **accuracy_protocol.md**：合盘准确度受任一参与者 `phase.confidence` 限制（短板效应）→ 合盘 confidence 自动降级（§4.2）
- **prediction_protocol.md**：focus_years 的同步度建议必须给 (方向, confidence) 二元组
- **virtue_recurrence_protocol.md**：合盘 closing 三段 × N 人完全沿用单盘 6 个写作位置规范；motif 交集仅作为 Node 11 declaration 段内"双人共振"提示一句话，不替代单人 declaration 主体内容；love_letter_eligible 由每人独立 `virtue_motifs.json` 决定，不取交集

## 10. v9.3 R-STREAM 边界（与单盘共用 _v9_guard 机械护栏）

- **R-STREAM-1**：每个 `append_analysis_node.py` 调用之间必须有 stop turn（assistant message 边界）；BAZI_AGENT_TURN_ID 环境变量由宿主在每个 LLM turn 启动时注入
- **R-STREAM-2**：单条 assistant message 的 user-facing markdown 不允许 ≥2 个顶级 `## ` heading；合盘 13 节里 closing 三段（Node 11/12/13）允许在最后一条收尾 turn 紧邻出现，是唯一例外（与单盘一致）
- **closing header 白名单**：合盘 Node 11/12/13 的首行 markdown header 必须命中 `## 我想和你说` / `## 项目的编写者想和你说` / `## 我（大模型）想和你说`（允许带 `· <name>` 后缀）；命中旧 v9 白名单或更早模板词 → exit 10
- **tone**：[`tone_blacklist.yaml`](tone_blacklist.yaml) 全位置生效；love_letter / free_speech 仅豁免**字面短语**，emoji / 多感叹号 / 撒娇腔 / "陀氏 / 灵魂宣言 / 承认人性 / 那一刀" 等仍**全位置禁**
- **mangpai surface**：每人 `confidence == high` 的盲派事件必须 surface 到该人 closing 三段或合盘解读；漏写 → render_artifact `--audit-mangpai-surface` exit 6

完整 R-STREAM 物理铁律见 [`AGENTS.md` v9.3 红线](../AGENTS.md) + [`multi_dim_xiangshu_protocol.md` §13.1-§13.6](multi_dim_xiangshu_protocol.md) + [`virtue_recurrence_protocol.md` §8](virtue_recurrence_protocol.md)。
