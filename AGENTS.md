# AGENTS.md · 给 AI 编码代理的项目导航

> 本文件遵循 [agents.md](https://agents.md/) 通行约定，被 Cursor / Claude Code / OpenAI Codex CLI / Aider / Continue / Devin 等 AI Coding Agent 自动读取。
> 如果你是人类开发者，请直接读 [README.md](README.md)；如果你是 AI 助手，从这里开始。

---

## 一、项目是什么

`bazi-life-curves` 是一个把中国传统八字命理（Four Pillars of Destiny / 子平命理）量化成**可证伪、可审计、可回测、bit-for-bit deterministic** 的人生曲线引擎。它不是 LLM 包装层 —— **打分由确定性 Python 脚本完成**，LLM 只负责把 JSON 翻译成大白话解读。

- 语言：Python 3.10+
- 入口：`scripts/` 下 12 个独立 CLI 脚本，按 pipeline 顺序运行
- 产物：`output/curves.json` + `output/chart.html` + 流式 markdown 解读
- Skill 接入：`SKILL.md` 是 Claude / Cursor Skill 主定义（YAML frontmatter）

---

## 二、Pipeline 标准流程（不要跳步）

```
solve_bazi.py                  # 解析八字（含起运岁精算 + --orientation 取向 + --longitude 真太阳时）
    ↓ output/bazi.json
score_curves.py                # 4 维曲线打分（spirit/wealth/fame/emotion · 80 年）
    ↓ output/curves.json
mangpai_events.py              # 盲派事件检测 + 反向规则 + 护身减压（可选 · score_curves 已内置基础调用）
    ↓ output/curves.json (events 字段)
virtue_motifs.py               # 【v9 必跑】第三条独立叙事通道：38 条人性母题检测（read-only of bazi/curves）
    ↓ output/virtue_motifs.json (life_review 6 个写作位置 + HTML 「我想和你说的话」卡片的输入数据)
    ↓ ⚠ 不跑 → render_artifact 的「我想和你说的话」卡片显示"未启用"，LLM 6 个写作位置全空
adaptive_elicit.py next        # v9 · 自适应贝叶斯单题流式问答（默认 R1 路径）
    ↓ 循环 ASK → AskQuestion 单题 → answer → ASK ...
    ↓ 触发 S1/S2/S3/S4 早停（通常 5-8 题，最多 12 题；prior top1 ≥ 0.85 直接 0 题 fast-path）
    ↓ output/.elicit.state.json   # 内含 posterior / asked_history（点开头隐藏 · LLM 不得回灌）
    ↓ output/bazi.json            # bazi.phase + bazi.phase_decision（is_provisional=false）
[可选 batch 通道]
adaptive_elicit.py dump-question-set --tier core14|full28
    → 用户贴题集 markdown 一次答完
adaptive_elicit.py submit-batch
    → output/bazi.json（confidence 默认上限 mid · top1≥0.97 才解锁 high）

[deprecated v9] handshake.py (round 1)  # v8 一次性 26 题路径，仅 he_pan_orchestrator/mcp_server 兜底
    ↓ output/handshake.r1.json [deprecated_v9: true · askquestion_payload 已剥离后验]
[Agent 调宿主 AskQuestion 抛点选 UI → 用户答案 → user_answers.r1.json]
phase_posterior.py (round 1)   # v8 · 贝叶斯后验更新（兼容路径）

handshake.py --round 2         # v9 · 基于 R1 决策的 EIG 选题 confirmation（限定 2-phase 后验）
    ↓ output/handshake.r2.json # 含 round1_summary + pairwise_target + 6-8 道 confirmation 题
[Agent 调宿主 AskQuestion 抛 R2 题 → user_answers.r2.json]
phase_posterior.py --round 2   # v8.1 · 合并 R1+R2 算最终后验 + confirmation_status
    ↓ output/bazi.json         # bazi.phase / phase_decision / phase_confirmation
[save_confirmed_facts.py --round r2 --r1-* --r2-* 写回 confirmed_facts.json（按 round 分桶）]
    ↓ output/confirmed_facts.json
render_artifact.py --virtue-motifs output/X.virtue_motifs.json
                               # 交互 HTML（Recharts + marked.js）· 4 维曲线 + 「我想和你说的话」独立卡片 ·
                               #   confirmation=weakly_confirmed 时解读自动加 caveat ·
                               #   不传 --virtue-motifs 时该卡片只能写空话
    ↓ output/chart.html

[deprecated] phase_inversion_loop.py  # v7 老路径，保留可运行但不再是主流程
```

**关键不可跳步（v9）**：

- **`virtue_motifs.py` 是必跑步骤**，不再是可选。它产出的 `virtue_motifs.json` 是 `analysis.virtue_narrative`（v9.3 改名「我想和你说的话」独立通道；schema/字段名不动）+ `life_review` 6 个位置的唯一数据源；不跑 → HTML「我想和你说的话」卡片显示"未启用"、LLM 6 个写作位置全空，等于把这条德性暗线铁律物理删除
- **R1 默认路径必须走 `adaptive_elicit.py next`**（CLI）或 MCP `adaptive_elicit(action="next")`，不要再用 `handshake.py` / MCP `handshake()` 默认入口（已 deprecated_v9，调用时 stderr 会打 v9 警告，仅 R2 confirmation 与 he_pan 兜底可用，需传 `--ack-batch` / `ack_legacy_r1=true` 关警告）；**禁止默认走 `dump-question-set --tier core14`**（一次抛 14 题），仅当用户**主动**要求 batch 时才允许，并需传 `--ack-batch` / `ack_batch=true`（否则 stderr 会打 v9 警告）
- 不能跳过 R1 elicit + 必要时的 R2 confirmation 直接渲染 HTML —— `bazi.phase_decision.is_provisional=true` 时 render_artifact 必须拒绝
- **Agent 必须用宿主结构化 `AskQuestion` 抛 `askquestion_payload`，禁止用自然语言转述题面让用户口头回答**（违反 = 破坏 phase 决策的 likelihood 计算前提）
- **第一次抛单题前必须给用户 [batch_elicitation_prompt.md](references/batch_elicitation_prompt.md) §1 开场白**（介绍 batch 通道）
- **不得把 `.elicit.state.json` / `posterior` / `phase_candidates` 等内部字段呈现或转述给用户**（[elicitation_ethics.md](references/elicitation_ethics.md) §E1）；不得在 elicit 中途命名 phase（§E2）；不得倒推进度（§E3）；不得揭示题目意图（§E4）
- **R1 后验 < 0.95 或 runner-up ≥ 0.02 时必须走 Round 2 confirmation**（详见 [handshake_protocol.md §4](references/handshake_protocol.md) HS-R7）
- **R2 confirmation_status=`decision_changed` 时必须 escalate 报告决策反转，不允许直接出图**（HS-R6）
- 不能让 LLM 自己改 `curves.json` 的数值 —— 那是 `score_curves.py` 的职责
- 不能在 `solve_bazi.py` 之外推导八字 —— 起运岁、真太阳时、orientation 全部依赖该脚本
- 后验 < 0.40 → **拒绝出图**，提示用户复核时辰 / 性别（详见 [phase_decision_protocol.md](references/phase_decision_protocol.md) §5）

### 流式 emit 红线（v9 重写 · 五阶段节序 · render_artifact 默认机械审计）

写 `analysis` 阶段必须**按五阶段流式 emit**，由 [`references/multi_dim_xiangshu_protocol.md`](references/multi_dim_xiangshu_protocol.md) §13.1 定义为权威；render_artifact 默认 `--required-node-order` + `--require-streamed-emit` 物理审计。

- **节序（v9 重排 · 以"当前所在大运"为锚 · 不再先写整图）**：
  0. **阶段 -1（v9.4 · 算法判断披露 · 不是 LLM 写）** · `bazi.{phase, phase_decision, phase_confirmation}` + `curves.multi_school_vote` 由引擎/web 在 elicit done → deliver 之前直接 emit。HTML 顶部"算法判断卡"`templates/chart_artifact.html.j2` 永远渲染；Web 侧 `web/src/app/api/chat/route.ts · afterElicitDone` 发 SSE `phase_decision` 事件 → `chat-room.tsx · PhaseDisclosureBlock`。**LLM 不得**在 opening 里复述命格名 / 置信度 / 后验概率（仍受 §E2 约束：禁止在 narrative 里出现 phase 字面 id）。详见 `references/elicitation_ethics.md §E2.1`
  1. **阶段 0** · `virtue_narrative.opening`（开篇暗线 · 位置① · 30-80 字）
  2. **阶段 1** · `dayun_reviews[<current_dayun_label>]`（命主"今天"所在大运段 · `bazi.current_dayun_label` 由 solve_bazi 自动写）
  3. **阶段 1.5（v9.4 新增）** · `motif_witness.after_current_dayun`（命理师第三人称回归 · 80-200 字 · 起点 anchor）
  4. **阶段 2** · `liunian.<year>` × N≈10（当前大运 10 个流年逐年写 · **平淡年也要落字**）
  5. **阶段 2.5（v9.4 新增）** · `motif_witness.after_current_liunian`（必须显式呼应 #1 + 改写铁律）
  6. **阶段 3** · `dayun_reviews[<其它 label>]` × M（按时间顺序顺写 · 旧 G 块嵌入式 deprecated · 新写法走阶段 3.5）
  7. **阶段 3.5（v9.4 · 可选累加）** · `motif_witness.after_dayun.<label>`（任一其它大运后触发母题就写一段）
  8. **阶段 4** · `key_years[i].body` × K（其它关键年 · convergence_year 嵌入位置③）
  9. **阶段 4.5（v9.4 新增）** · `motif_witness.after_key_years`（必须呼应 #1 #2 + 所有 after_dayun）
  10. **阶段 5** · `analysis.overall`（整图综合 · **现在才写**）
  11. **阶段 5.5** · `life_review.{spirit/wealth/fame/emotion}` × 4（四维一生评价）
  12. **阶段 6** · `virtue_narrative.convergence_notes`（仅 `motifs.convergence_years` 非空）
  13. **阶段 6.5（v9.4 新增）** · `motif_witness.before_closing`（closing 三段前的最终累加旁白）
  14. **阶段 7-9** · 收尾三段 closing（去模板化 · 见下）
- **每写完一节立刻 send 一条 assistant message**（哪怕半成品也要先发出 `## [阶段 N · 写作中…]` 占位），禁止积累 ≥2 节不发；60 秒帧内塞 ≥4 节即被 `--require-streamed-emit` 判伪流式（exit 4）
- **节序回退判定**：写阶段 N 后又写阶段 ≤N-2 → exit 4（dayun↔liunian 同阶段交错允许）
- 节内嵌套：每段大运评价节内**仅在母题激活时**嵌入德性母题位置②G 块（由 `audit_virtue_recurrence_continuity._check_position2` 强制）；convergence_year 命中的关键年节内**必须**嵌入位置③
- 流式可观测：用 `scripts/append_analysis_node.py --node <key> --markdown <md>` 增量落盘到 `output/X.analysis.partial.json`；脚本会自动追加 `_stream_log` 时间戳 + 调用 `_v9_guard.enforce_tone` + `enforce_no_phase_leak_in_message`；用户随时 `python scripts/render_artifact.py --analysis output/X.analysis.partial.json --virtue-motifs output/X.virtue_motifs.json --allow-partial` 即可看进度

#### v9.3 红线（R-STREAM-1 / R-STREAM-2 · 单节单 message 物理铁律）

18e281d2 case 复盘暴露：LLM 即使口头承认"分节流式"，仍会在一条 turn 里塞 7 段 `## ` 把整篇分析吐光。v9.3 起改为**机器可校验**的硬 lint，一条没过 → render fail：

- **R-STREAM-1**：每个 `append_analysis_node.py` 调用之间**必须**有一次 stop turn（assistant message 边界）。一次 turn 内连续 `append_analysis_node ≥ 2` 次 → 视为憋整段，违规。
  - 物理实现：`append_analysis_node.py` 读环境变量 `BAZI_AGENT_TURN_ID`（由宿主 / Cursor / MCP 在每个 LLM turn 注入），与上一次 `_stream_log[-1].agent_turn_id` 比对；相同 → stderr WARN + 写入 `state['_stream_violations']`。
  - 物理拦截：`render_artifact.py --audit-stream-batching`（默认开）扫 `_stream_violations`，命中 ≥1 → exit 11。
- **R-STREAM-2**：单条 assistant message 的 user-facing markdown **不允许** 包含 ≥2 个**顶级** `## ` heading。closing 三段（`## 我想和你说` / `## 项目的编写者想和你说` / `## 我（大模型）想和你说`）允许在最后一条收尾 turn 紧邻出现，是唯一例外。
  - 物理实现：`append_analysis_node.py` 写入前调用 `_v9_guard.check_message_heading_count(md, allow_closing_chain=<是否最末段>)`，违规 → SystemExit。
- **环境变量约定**：宿主侧需在每个 LLM turn 启动时设 `BAZI_AGENT_TURN_ID=<turn_id>`；缺失时 `append_analysis_node.py` 退化到时间戳作伪 turn_id（不报 R-STREAM-1，但仍可被 60s 伪流式审计兜底）。
- 详见 [`references/multi_dim_xiangshu_protocol.md`](references/multi_dim_xiangshu_protocol.md) §13.1-§13.6 + [`references/virtue_recurrence_protocol.md`](references/virtue_recurrence_protocol.md) 6 个写作位置 + §8 Closing 标题去模板化

#### v9.3 pipeline-streaming 默认路径（真正的「React 模式」）

旧路径（`score_curves.py --out curves.json` 一次性算完整生命 → LLM 一段段写）虽然能跑，但 LLM 必须等所有 4 维曲线 + 80 年逐年算完才能开始写第一节。v9.3 起默认推 **pipeline-streaming**：

- 入口：[`scripts/streaming_pipeline.py`](scripts/streaming_pipeline.py) `stream --bazi X.json --stage <name>` / `--stage all` / `--resume <state> --next`
- 6 个 stage，对应 §3a 节序图阶段 1-9：
  1. `current_dayun` → 当前大运段（≈1s 出第一行）
  2. `current_dayun_liunian` → 当前大运 10 流年逐年
  3. `other_dayuns` → 其它大运 segment
  4. `key_years` → 全图关键流年（peak / dip / shift / dispute）
  5. `overall_and_life_review` → 整图 + 4 维一生总评
  6. `closing` → 「我想和你说的话」三段数据钩子（virtue_motifs 直接透传）
- 输出协议：每行一条 NDJSON，`{stage, ts_iso, payload, ...}`；状态文件 `output/X.stream_state.json` 记录 cursor 与已完成 stage 的 payload，支持 `--next` 增量推进
- LLM 行为：每收到一个 NDJSON 行 → 立刻写一节 `## ` → `append_analysis_node` 落盘 → send → **stop turn**（恰好满足 R-STREAM-1）
- HTML 渲染：`render_artifact.py --from-stream-state output/X.stream_state.json` 可直接从 stream_state 还原 curves（不再依赖批量 `score_curves.py --out curves.json`）；旧 `--curves` 入口仍保留作合盘 / 兜底
- 兼容：`score_curves.py --out curves.json` 仍是合盘场景默认入口；分析阶段（单盘）则**默认走 pipeline-streaming**

### 工具入口铁律（v9 新增 · `_v9_guard.enforce_v9_only_path`）

| 入口 | 默认行为 | 解锁条件 |
|---|---|---|
| `handshake.py` round=1 | exit 2 | `--ack-legacy-r1` |
| `adaptive_elicit dump-question-set` | exit 2 | `--ack-batch --confirm-batch-defeats-v9` 双标 |
| `adaptive_elicit next --answer X` | 必填 `--answer-source` ∈ {`user`, `user_freetext`, `user_skipped`} | — |
| `adaptive_elicit next --answer-source agent_inferred` | exit 3 | **永久禁止**（LLM 不准替用户答题） |
| MCP `tool_handshake` round=1 | 返回 `_err` | `ack_legacy_r1=true` + `dump_phase_candidates` + `phase_id` |
| MCP `tool_adaptive_elicit action=dump_question_set` | 返回 `_err` | `ack_batch=true` + `confirm_batch_defeats_v9=true` |

### 调性铁律（v9 新增 · `references/tone_blacklist.yaml` + `_v9_guard.scan_tone`）

`append_analysis_node.py` 写入前调用 `_v9_guard.enforce_tone(markdown, node=...)`；命中字面短语 / 正则 → exit 5。

- **banned_phrases**（字面短语）：`"人生 A 面"` / `"你真的好棒"` / `"加油哦"` / `"你值得拥有"` / `"给你（本人）的一封信"` 等鸡汤化、撒娇腔、模板化措辞
- **banned_patterns**（正则 · `applies_to_whitelisted: true` 即对所有节生效）：`！{2,}` / `~{2,}` / emoji 全集（U+1F300-1FAFF / U+2600-27BF）
- **whitelisted_nodes**：`virtue_narrative.love_letter` / `virtue_narrative.free_speech` 仅豁免**字面短语**（情书可以情绪化）；emoji / 多感叹号 / 撒娇腔仍**全位置禁**
- **`motif_witness.*` 节点（v9.4）**：纳入与其它结构化叙事节点同样的 hard ban —— emoji / 多感叹号 / 撒娇腔禁；不在 whitelist 里

### 反系统化铁律（v9.4 新增 · `R-MOTIF-1` / `R-MOTIF-2` / `R-MOTIF-3`）

详见 [`references/virtue_recurrence_protocol.md §3.11`](references/virtue_recurrence_protocol.md) + [`references/multi_dim_xiangshu_protocol.md §12.7`](references/multi_dim_xiangshu_protocol.md)。三层物理护栏（`append_analysis_node.py` 写入前自动调用 + `render_artifact.py` 兜底）：

- **R-MOTIF-1（反 motif id 字面）**：`scripts/_v9_guard.py::enforce_no_motif_id_leak` —— narrative 全节点禁止出现 catalog 内 motif id 字面（`B1` / `K2_xxx` / `L3` 等正则匹配）；命中 → exit 5
- **R-MOTIF-2（反 canonical label 字面）**：`scripts/_v9_guard.py::enforce_no_canonical_label_leak` —— catalog 内 canonical name 字段（"亲密者的无能"/"创业者"/"远行者" 等）禁止字面落入 narrative；命中 → exit 5
- **R-MOTIF-3（同母题改写多样性）**：`scripts/_v9_guard.py::enforce_paraphrase_diversity` —— 同一母题在 ≥2 个位置（多个 motif_witness anchor / dayun_review G 块 / love_letter / free_speech）出现时，两次表述字符级相似度（Jaccard / Levenshtein 归一化）必须 < 0.6；命中 → exit 5

LLM 在写 narrative 时只允许引用 `virtue_motifs.json.triggered_motifs[i].paraphrase_seeds`（v2 schema 起每条 motif 携带 3-5 句面向「这个具体命主」的口语化改写起点）+ 必须再次个性化润色，**严禁**出现 motif id / canonical label 字面。命主面前**永远不能**显出系统的诊断结构感。

### Closing 三段「我想和你说的话」（v9.3 改名 · `_v9_guard.enforce_closing_header`）

v9.3 起，三段统称「我想和你说的话」（仅作为内部叙述，不出现在用户可见 H2 上）。

| 节（schema 名不动）| v9.3 必须用的 markdown header（首行）| 禁止（含 v9 旧白名单已退役）|
|---|---|---|
| `virtue_narrative.declaration` | `## 我想和你说` | `## 走到这里` / `## 承认维度·宣告` / `## 位置④灵魂宣言` / `## 宣告` / `## 承认人性` |
| `virtue_narrative.love_letter` | `## 项目的编写者想和你说` | `## 写到这里我想说` / `## 给你（本人）的一封信` / `## 位置⑤情书` / `## 情书` |
| `virtue_narrative.free_speech` | `## 我（大模型）想和你说` | `## 不在协议里的话` / `## 位置⑥ LLM 自由话` / `## 自由发言` / `## free_speech` |

意图：让三段 closing 在用户视角变成三个清晰的"我对你说话"，而不是带"宣告 / 情书 / 自由话"等模板感的填空题。命中旧白名单 / 模板词 → exit 10。

### v9.3 协议回潮防火墙（v9.3 新增 · `audit_reference_consistency.py`）

skill 加载时 LLM 会读到 `SKILL.md` + `AGENTS.md` + `references/*.md`。如果其中任一文件还在**正向引导** LLM 用旧 v9 closing header（`## 走到这里` / `## 写到这里我想说` / `## 不在协议里的话`）、Step 2.7 询问输出格式、或「陀氏 / 灵魂宣言 / 承认人性 / 那一刀」等 v9.3 已封禁的措辞，会形成「**按文档写 → 落盘 fail**」的协议自相矛盾陷阱（机械护栏在最后一刻 exit 5 / 10 / 11 拦下，但用户已经走错路）。

`scripts/audit_reference_consistency.py --strict` 是**第三道防线**：

- 扫所有协议文件，区分三档严重度：`exit5`（tone）/ `exit10`（closing header）/ `deprecated`（Step 2.7 等已删流程）
- tone 类宽容：协议章节标题 / blockquote 元说明 / 邻近 negation token / 文件顶部 `v9.3 命名约定` banner 都算合法引用
- closing_header / deprecated 严格：banner 不豁免；只接受**强 negation token**（`已退役` / `命中即` / `禁止` / `(旧 v9)` 等）
- exit 12 时 CI 阻断；本审计已加进 `tests/test_audit_reference_consistency.py::test_repo_snapshot_passes`，PR 必须保持 PASS

任何新加的 reference / 协议改动若引入旧措辞，本测试立刻 fail。

### 高置信度盲派事件强制 surface（v9 新增 · `audit_mangpai_surface.py`）

`scripts/mangpai_events.py` 现在每条事件 / 静态标记带 `confidence ∈ {high, mid, low}`；`render_artifact --audit-mangpai-surface`（默认开）扫 `analysis` 全文，**漏掉**任一 `confidence=high` 事件 → exit 6。详见 [`references/mangpai_protocol.md §H`](references/mangpai_protocol.md)。

### P0 派别中立的高置信度 rare phase 候选池（v9.2 · 取代 v9.1 月令格种子）

**v9.1 → v9.2 教训**：v9.1 曾经在 P0 引入"月令格 prior 种子"，把"月令为先"的子平派立场写进 prior 起点（给 ziping_zhenquan power-dim 月令格独占 0.66-0.70 prior，并在 P7 用 `protected_pids` 防止被盲派 zuogong 压死）。这条修法被实测打回 —— 它本质是**算法替用户做了学派仲裁**：在用户答任何题之前就把答案内定，剥夺了 R1 EIG 的判别空间。同一份八字在派别选择上可能有合理分歧（譬如 6d0abb46 case 可读作"子平阳刃格" / "盲派阳刃驾杀" / "魁罡格"），算法不应替用户选派。

**v9.2 修法**：`_bazi_core._p0_rare_phase_prior_seed` 把 P0 改成派别中立的"top-k 候选池"——所有 `confidence ≥ 0.80` 的 rare hits（**不分 school、不分 dimension**）按 confidence softmax (τ=0.4) 平等分配到 prior 候选池：

- 触发门槛：N ≥ 3 个 conf ≥ 0.80 hits（≤ 2 hit 时 P0 skip → 保护 examples bit-for-bit）
- 份额分配：`p_hits_total = 0.45`（softmax 后单 hit 上限 ~0.15），`p_dm = 0.20`，`p_other_total = 0.35`
- P7 同步撤销 `protected_pids` 参数 —— P0 派别中立后不再需要 P7 做族内保护

**算法职责重申**：算清楚结构性证据 → 给出最可能的几个候选。由 R1 adaptive_elicit (EIG) 用用户答题做 disambiguation，**不在 prior 起点写"月令为先 / 调候压格局 / 盲派优先 / 书房派优先"等任何派别立场**。

**bit-for-bit 安全**：`tests/test_phase_decision_determinism.py` 4 个金标准 case + 性别对称测试 10/10 passed。两个 examples（1 hit / 2 hits）都不触发 P0。**6d0abb46 case 验证**：5 个高置信度 hits 进 P0 候选池 → P7 把盲派 zuogong top 推上去 → 决策 `yang_ren_jia_sha`（阳刃驾杀）mid 0.634，`mangpai_conflict_alert` mid 提示 yangren_ge / kuigang_ge 等其它高置信度候选。详见 [`references/phase_decision_protocol.md §7.6`](references/phase_decision_protocol.md)。

### 盲派 / 子平正格与 phase decision 冲突警示（v9 新增 · 修 6d0abb46 case bug）

`_bazi_core.decide_phase` 输出新增 `mangpai_conflict_alert` 字段（severity ∈ {high, mid, low}）：当 `rare_phase_detector` 给出 ≥ 1 条 `school startswith "mangpai"` 且 conf ≥ 0.80（或任一 `ziping_zhenquan` conf ≥ 0.85）的 phase ≠ decision 时触发。`audit_mangpai_surface.py --bazi <bazi.json>`（render 默认透传）要求 alert.conflicting_hits 每条 `name_cn` 都在 analysis 中字面出现，severity=high 还要求叙事里出现「冲突 / 张力 / 承认 / 盲派 / 另一相位 / 另一种判读」之一；失败 exit 3。`phase_posterior.update_posterior` 在所有 confidence 档位都跑 alert 检查；severity=high 且 R1 confidence ∈ {mid, high} 时**强制建议 R3**（`rare_phase_fallback_suggestion.trigger_reason = "mangpai_conflict_alert_high"`）。HTML 顶部渲染「盲派强冲突 · 必读」/「盲派冲突」/「盲派提示」三档警示卡。详见 [`references/phase_decision_protocol.md §7.5`](references/phase_decision_protocol.md) + [`references/mangpai_protocol.md §H.4`](references/mangpai_protocol.md)。

### 大白话 + intro + X 兜底铁律（v9 新增 · `_question_bank.py`）

- `_check_no_phase_leak(strict=True)` + `_check_plain_language(strict=True)` 在模块加载时强制；命中 → AssertionError
- 每题 `Question.intro: str`（≤60 字 · 1 句）必填，`askquestion_payload.intro` 透传
- 每题 options 自动尾插 ID=`X` free-text 兜底；用户选 X 必须配 `--free-text "..."`，落进 `confirmed_facts.free_facts[]`，**不更新 likelihood**
- 详见 [`references/discriminative_question_bank.md §0.5`](references/discriminative_question_bank.md) + [`references/elicitation_ethics.md §E7-§E10`](references/elicitation_ethics.md)

---

## 三、目录结构

```
bazi-life-curves/
├── SKILL.md                       # Claude/Cursor Skill 主定义（看这个理解端到端工作流）
├── README.md                      # 用户视角总览
├── USAGE.md / INSTALL.md          # 速览与安装
├── AGENTS.md                      # 本文件
├── llms.txt                       # LLM 检索入口（简化版导航）
├── CITATION.cff                   # 学术引用元数据
├── PLAN_zeitgeist_folkways.md     # 时代风气 / 民俗修正设计文档
├── requirements.txt               # 依赖：lunar-python / matplotlib / PyYAML / Jinja2
├── scripts/                       # 12 个核心脚本
│   ├── _bazi_core.py              # 干支/五行/十神/互动/化气格/神煞底层（不要直接 CLI）
│   ├── solve_bazi.py              # 入口 1
│   ├── score_curves.py            # 入口 2
│   ├── mangpai_events.py          # 入口 3（可选）
│   ├── _virtue_registry.py        # v8 · 38 条人性母题 spec 注册表（不要直接 CLI）
│   ├── virtue_motifs.py           # 入口 3.5 · 德性暗线检测 · 输出 virtue_motifs.json
│   ├── audit_llm_invented.py      # 运维侧 · 聚合 LLM 自创母题候选，反哺 catalog 演化
│   ├── adaptive_elicit.py         # 入口 4（必跑）· v9 自适应贝叶斯单题流式 + batch 双通道
│   ├── _eig_selector.py           # v9 EIG 算法核心（pure function · 4 条早停）
│   ├── handshake.py               # 入口 4 兼容（deprecated R1 + EIG-based R2 confirmation）
│   ├── phase_posterior.py         # 入口 4.5 · v8 用户答案 → 贝叶斯后验 → 落地 phase
│   ├── _question_bank.py          # v8 5 维度 28 题 dataclass（与 references/discriminative_question_bank.md 1:1）
│   ├── audit_questions.py         # v9 题库可答性 / 中性度静态审计（8 维 ambiguity + 命理词典）
│   ├── phase_inversion_loop.py    # [deprecated v8] 老 R0/R1/R2 反演路径，保留可运行
│   ├── save_confirmed_facts.py    # 校验反馈固化（v8 加 --user-choices 参数 + schema migration）
│   ├── family_profile.py          # [legacy] 旧 R3 原生家庭，逻辑已迁入 D1 题库
│   ├── render_chart.py            # 静态 PNG
│   ├── render_artifact.py         # 交互 HTML
│   ├── he_pan.py                  # 合盘评分
│   └── calibrate.py               # 历史回测
├── references/                    # 13 个学理/协议文档（修改算法前必读对应协议）
├── examples/                      # 2 套完整产物（官印相生格 / 伤官生财格）
├── templates/chart_artifact.html.j2
├── calibration/                   # dataset.yaml + thresholds.yaml
└── output/                        # 用户运行产物（gitignore 屏蔽，含真实八字）
```

---

## 四、修改算法时的硬性约束

### 4.1 任何打分规则的改动 → 必须更新对应协议文档

| 修改文件 | 必须同步更新 |
|---|---|
| `score_curves.py` 的扶抑/调候/格局权重 | `references/methodology.md` + `references/scoring_rubric.md` |
| `mangpai_events.py` 的事件 / 反向 / 护身 | `references/mangpai_protocol.md` |
| `virtue_motifs.py` 的母题检测 / 调性 / blessing_path / convergence | `references/virtue_motifs_catalog.md` + `references/virtue_recurrence_protocol.md`（铁律 ★★★★★★ 不可绕过） |
| `_virtue_registry.py` 的 motif id / threshold / is_l_class / is_persistent | catalog 与 recurrence 协议同步；不得删除任何已发布 motif（向前兼容） |
| `adaptive_elicit.py` / `_eig_selector.py` 的选题 / 早停 / state schema | `references/handshake_protocol.md` §0 (v9) + `references/elicitation_ethics.md` |
| `handshake.py` 的 R2 confirmation 题（deprecated R1 也在此）| `references/handshake_protocol.md` (v8 / §4 v8.1 + v9 §0) |
| `_bazi_core.py` 的 detector / decide_phase / pairwise_discrimination_power / assess_confirmation | `references/phase_decision_protocol.md` (v8 / §7 v8.1) + `references/diagnosis_pitfalls.md` §14 |
| `_question_bank.py` / `references/discriminative_question_bank.md` 题目 / likelihood_table | 两边必须 1:1 同步；calibrate.py 做一致性检查 |
| `phase_posterior.py` 后验阈值 / R1 决策规则 / R2 confirmation_status | `references/phase_decision_protocol.md` §5 / §7 |
| `he_pan.py` 的 4 层评分 | `references/he_pan_protocol.md` |
| 任何涉及性别 / 取向 / 关系结构的改动 | **必须**先读 `references/fairness_protocol.md §9-§10`，违反会破坏现代化承诺 |

### 4.2 古籍出处铁律

新加任何"机制 / 规则 / 应事 / 反向"，**必须**在协议文档同步加古籍出处（《滴天髓阐微》《子平真诠》《穷通宝鉴》《三命通会》《子平粹言》或现代盲派师承）。**禁止**自创无源规则。

### 4.3 现代化解读铁律（fairness_protocol §10）

- ❌ "克夫" / "旺夫" / "妨夫" / "妨妻" 等措辞
- ❌ "配偶星弱 = 单身 = 差" / "女命印多 = 重事业 = 感情位次靠后" 等价值判断
- ❌ "男看财 / 女看官" 的语言（结构识别可保留，但解读层必须用 `--orientation` 决定的中性表述）
- ✅ 必须使用 `relationship_mode` 7 种中性描述：outward_attractive / competitive_pursuit / nurture_oriented / ambiguous_dynamic / low_density / balanced / self_centered
- ✅ 每次 emotion 解读首段必须强制声明：「命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育」

### 4.4 Bit-for-bit deterministic 铁律

任何 PR 必须通过：

```bash
diff <(python scripts/score_curves.py --bazi examples/guan_yin_xiang_sheng.bazi.json --strict | sha256sum) \
     <(python scripts/score_curves.py --bazi examples/guan_yin_xiang_sheng.bazi.json --strict | sha256sum)
# 必须输出空（同输入 100 次 100 个 byte-equal 结果）

# virtue_motifs 同样要求 bit-for-bit deterministic
diff <(python scripts/virtue_motifs.py --bazi examples/guan_yin_xiang_sheng.bazi.json --curves examples/guan_yin_xiang_sheng.curves.json --out /tmp/vm1.json --strict) \
     <(python scripts/virtue_motifs.py --bazi examples/guan_yin_xiang_sheng.bazi.json --curves examples/guan_yin_xiang_sheng.curves.json --out /tmp/vm2.json --strict)
diff /tmp/vm1.json /tmp/vm2.json
```

不允许引入：随机 seed / 时间戳 / 字典遍历顺序依赖 / set 序列化。

### 4.5 LLM 后视镜归因防御铁律

任何接受用户输入的脚本（`adaptive_elicit.py` / `handshake.py` / `save_confirmed_facts.py`）**必须**：

- 拒绝 "我 X 岁升职 / 我已婚 / 我离婚 / 我读了 X 大学" 这类**带具体身份标签**的事实
- 只接受 "我 X 岁那年财务有大波动（涨/跌）" 这类**结构性事实**
- 写回 `confirmed_facts.json` 时强制脱敏字段名

---

## 五、运行 / 测试

### 5.1 一键端到端跑两个示例（验证你没改坏）

```bash
mkdir -p output

python scripts/solve_bazi.py --pillars "甲子 丁卯 丙寅 戊戌" --gender M --birth-year 1984 --orientation hetero --qiyun-age 8 --out output/test1.bazi.json
python scripts/score_curves.py --bazi output/test1.bazi.json --out output/test1.curves.json --age-end 80
# v9 默认：自适应单题流式（循环到 finalize；非交互测试可改用 batch）
python scripts/adaptive_elicit.py next --bazi output/test1.bazi.json --curves output/test1.curves.json --state output/.test1.elicit.state.json
# 或 batch 模式：导出 → 填答 → 提交
python scripts/adaptive_elicit.py dump-question-set --bazi output/test1.bazi.json --curves output/test1.curves.json --tier core14 --out output/test1.questions.md
# [...用户填答 → 写到 output/test1.answers.json...]
# python scripts/adaptive_elicit.py submit-batch --bazi output/test1.bazi.json --answers output/test1.answers.json
# v9 必跑：第三条独立叙事通道（「我想和你说的话」独立通道 · life_review 6 写作位置 + HTML 卡片的唯一数据源）
python scripts/virtue_motifs.py --bazi output/test1.bazi.json --curves output/test1.curves.json --out output/test1.virtue_motifs.json
# 必须在 LLM 写 life_review / virtue_narrative 之前生成（multi_dim_xiangshu_protocol.md §12 + virtue_recurrence_protocol.md）

# 渲染（必须 --virtue-motifs，否则 HTML「我想和你说的话」卡片只能写空话）
python scripts/render_artifact.py \
  --curves output/test1.curves.json \
  --analysis output/test1.analysis.json \
  --virtue-motifs output/test1.virtue_motifs.json \
  --out output/test1.html

# 流式部分渲染（agent 边写 analysis 边刷 HTML 看进度时用）
python scripts/render_artifact.py \
  --curves output/test1.curves.json \
  --analysis output/test1.analysis.partial.json \
  --virtue-motifs output/test1.virtue_motifs.json \
  --allow-partial --out output/test1.partial.html
```

### 5.2 历史回测

```bash
python scripts/calibrate.py
# 期望输出：spirit_recall ≥ 0.70, wealth_recall ≥ 0.75, fame_recall ≥ 0.65, fp_rate ≤ 0.15
```

### 5.3 性别对称性自检（fairness_protocol 强制要求）

同八字翻转性别（M→F / F→M），spirit/wealth/fame 三维必须 byte-equal；只有 emotion 因配偶星识别可不同。

---

## 六、依赖管理

- 仅允许添加广泛使用、有积极维护的库
- 添加新依赖必须在 `requirements.txt` 用 `>=` 写最低版本
- **禁止**引入：torch / tensorflow / 任何大模型 SDK（保持工具轻量、可在 CPU 跑 < 5 秒完成）

---

## 七、PR / Issue 规范

- PR 标题格式：`[scripts/score_curves] 添加化气格 phase override`
- 任何打分逻辑改动必须附：
  - 古籍出处引文
  - 至少 1 个 `examples/` 下的回归对比
  - `calibration/` 跑分变化（recall / fp_rate）
- 不接受 "感觉这样准" 类无脚本可重现的 issue

---

## 八、我（AI agent）应该如何回答用户

### 当用户问"算个八字"

1. 先用 `solve_bazi.py` 解析（询问性别 + 公历生辰 + 取向）
2. 跑 `score_curves.py`
3. **R1（v9 默认）**：跑 `adaptive_elicit.py next` 进入自适应单题流式
   - 第一次抛题前必须按 [batch_elicitation_prompt.md](references/batch_elicitation_prompt.md) §1 给用户开场白（介绍 batch 通道）
   - 用户若选 batch：跑 `dump-question-set --tier core14|full28` 把题集贴回 → 用户填答 → `submit-batch`
   - 用户若选流式：每轮调宿主 AskQuestion 抛 `askquestion_payload` 单题，回答后 `--answer 'qid:opt'` 进下一轮
   - 全程**禁止**把 `posterior` / `phase_candidates` / `EIG` 转述给用户，**禁止**在 finalize 前命名 phase（[elicitation_ethics.md](references/elicitation_ethics.md) §E1–§E4）
4. R1 finalize 后 `bazi.json` 直接写入 `phase` + `phase_decision`，不需要单独跑 `phase_posterior.py --round 1`
5. **R2**（仅在 R1 confidence < high 或想再次确认时）：跑 `handshake.py --round 2`（EIG 选 confirmation 题）→ AskQuestion 抛 → `phase_posterior.py --round 2`
6. 看 `phase_confirmation.action`：`render` / `render_with_caveat` 直接出图；`escalate` 时**必须**报告决策反转或不确定，建议核对时辰 / 性别
7. **必须**先跑 `virtue_motifs.py` 产出 `virtue_motifs.json`（「我想和你说的话」独立通道的唯一数据源）
8. 按 [`references/multi_dim_xiangshu_protocol.md`](references/multi_dim_xiangshu_protocol.md) **流式**输出 markdown 解读：每写完一节立刻发出，禁止憋整段；同时用 `scripts/append_analysis_node.py` 增量落盘到 `output/X.analysis.partial.json`，让用户用 `render_artifact.py --allow-partial` 随时看进度
9. 全部节写完后用 `python scripts/render_artifact.py --curves ... --analysis ... --virtue-motifs ... --out ... [--strict-llm]` 出最终 HTML（**必须**带 `--virtue-motifs`，否则「我想和你说的话」卡片只显示"未启用"）

### 当用户问"我 X 年怎么样"

读 `output/curves.json` 的 `points[X]` 字段，按 `prediction_protocol.md` 强制输出"推论过程 + 可证伪点"格式。**禁止**直接说"X 年好/坏"。

### 当用户问"跟 Y 合不合"

v9.3 起合盘走 **多人 adaptive_elicit 编排** + `he_pan.py` 4 层评分 + 13 节流式：

```bash
# Step A · 多人编排 plan
python scripts/he_pan_orchestrator.py --mode plan-v9 \
  --bazi /tmp/p1.json /tmp/p2.json --names Alice Bob \
  --out-dir /tmp/hepan_state/

# Step B · 串行 next-person（每人独立跑 v9 单题流式 adaptive_elicit）
python scripts/he_pan_orchestrator.py --mode next-person \
  --bazi /tmp/p1.json /tmp/p2.json --names Alice Bob \
  --out-dir /tmp/hepan_state/

# Step C · 每人 finalize 后各跑一次 virtue_motifs.py
python scripts/virtue_motifs.py --bazi /tmp/hepan_state/p1.bazi.json \
  --curves /tmp/hepan_state/p1.curves.json --out /tmp/hepan_state/p1.virtue_motifs.json

# Step D · 4 层合盘（入口守门：每人 phase finalized + virtue_motifs 必须存在）
python scripts/he_pan.py --bazi /tmp/hepan_state/p*.bazi.json \
  --names Alice Bob --type marriage --require-virtue-motifs \
  --out /tmp/hepan_state/he_pan.json
```

按 `he_pan_protocol.md` v2 的 13 节流式输出（10 节常规 + Node 11/12 「## 我想和你说 · <name>」 + Node 13 「## 共振 motif」 ∩ 双方 motif_ids）。**禁止旧 R0/R1 健康三问 batch 路径（`--mode plan / collect-r1 / apply-answers` 默认 exit 2，需 `--ack-batch` 兜底）。**

### 当用户告诉你"我 31 岁升职了，命局对吗"

**红线**：不要立刻"哦命局应验了"。按 `accuracy_protocol.md` 走身份盲化路径，用 `save_confirmed_facts.py` 只把"31 岁财务/事业有正向波动"写入，**禁止**写入"升职"这种带身份的标签。

---

## 九、版本与演进

当前主版本：**v9.3.1（2026-04）**

- v7：现代化语言重构 + LGBTQ+ 包容
- v7.1：P5 三气成象 / 假从真从 detect
- v7.2：相位反演 Auto-Loop + 真太阳时 + confirmed_facts 持久化
- v7.3：R3 原生家庭反询问
- v7.4：化气格 + 神煞 + R0' 反迎合反向探针
- v8 / v8.1：phase decision + AskQuestion 结构化点选 + Round 2 confirmation
- v9：discriminative_question_bank 5 维度 + adaptive_elicit 单题流式贝叶斯（EIG + 4 条早停）
- v9.1：mangpai surface 强制 + tone_blacklist
- v9.2：rare phase P0 候选池 + 月令格中立化
- v9.3：R-STREAM-1/2 单节单 message 物理硬 lint + closing 三段「我想和你说的话」改名 + audit_reference_consistency 协议回潮防火墙 + Step 2.7 已删除（默认流式 markdown）
- **v9.3.1（当前）**：合盘 v9.3 化 — `he_pan_orchestrator.py` plan-v9 / next-person 多人 adaptive_elicit 编排；`he_pan.py` 13 节流式 + `--require-virtue-motifs` 入口守门（exit 7）；`he_pan_protocol.md` v2；旧 R0/R1 健康三问 batch 路径全部已退役（`--ack-batch` 兜底）

详见 `references/phase_inversion_protocol.md §9` + `references/he_pan_protocol.md` v2 + `CHANGELOG.md` 版本时间表。
