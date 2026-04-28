# Changelog

## v9.6 — 2026-04 · 事件 Ask-Loop 兜底（R2 之后第三轮收敛）

> **Triggering pattern**: web 端实测发现，R2 confirmation 跑完 top1_p 仍处于
> 0.65–0.85 中段的 ambiguous 命盘占比 ~25%，原 v9.2 路径只能给"weakly_confirmed +
> caveat"或"escalate 核对时辰"——但用户的时辰其实是对的，只是性格自述对多个 phase
> 都讲得通。本次新增**事件 ask-loop**：在性格自述（elicit）通道之外开第二条
> 独立贝叶斯通道——抛若干历史年份"是否发生明显事件"清单题，用真实经历做证据
> 把后验向"与用户经历最一致"的 phase 拉。事件比性格自述更"硬"（用户更难撒谎），
> 但避免事件主导滑向宿命，加权融合刻意定 1:1.2（事件 55% / 性格 45%）。
>
> 本版本合并跨度 v9.4–v9.6：v9.4 disjoint 年清单题 + Stage A Bayesian 引擎、
> v9.5 Stage B 重叠年事件类型查表（v2 零 LLM）+ verification 题、v9.6 把后验
> 真正写回 bazi.json + 重跑 score_curves / virtue_motifs（修真 bug：之前后验
> 只更新 in-memory state，deliver pipeline 拿到旧判定，事件题白答了）。
>
> 引擎层先行落地，本次只做 B 引擎库的回流——web 适配层（A 项目 SSE 串流 / TS
> 包装层）不进本仓。普通用户经 Claude 调本 skill 时，由 Claude 当编排者用 Bash
> 串脚本 + 把结构化问题翻译成自然语言问用户。

### 新增脚本（共 7 个，~2228 行，零新第三方依赖）

- `scripts/event_elicit.py`：Stage A 后验初始化 + Bayesian 更新引擎
  - 4 选项答案 yes/partial/no/dunno，似然表硬编码 + assert 强制归一性
  - **「记不清」中性铁律**：`P(dunno|predicted) == P(dunno|not_predicted)` 由 assert
    保证，违反「不替用户记忆」铁律即代码 fail
  - `fuse_posteriors(elicit, event, w_e=1.0, w_v=1.2)` 加权对数融合
  - 三档收敛阈值 high 0.80 / soft 0.70 / weak 0.60（2026-04 从原 0.85/0.79/0.69
    放宽，77.9% 不该落到"重警示"档）
- `scripts/event_year_predictor.py`：Phase × 流年/大运 预测命中矩阵
  - 复用 `_phase_registry.zuogong_trigger_branches` + 十神标签命中
  - `select_disjoint_year_batch` 找独占预测年（Stage A 数据基础）
- `scripts/event_elicit_stage_b.py`：重叠年事件类型判别（v2 零 LLM）
  - Jaccard 加权后验分歧分公式：`Σ_{i<j} (1-jaccard) × π_i × π_j`
  - `update_with_category_answer` categorical 似然查表
- `scripts/phase_event_categories.py`：Phase → 事件类别静态映射（12 大类纯数据）
  - 替代早期"每对 (年×phase) 调 LLM 估事件类型"的高成本路线
  - 类别用大白话不用命理术语（"升学/学术贵人" 而非 "印星岁运"）
- `scripts/event_verification.py`：融合后验透明复核题
  - likelihood 不对称：hit ×5 / miss ×0.2 / partial / dunno 中性
  - 题面铁律：透明告知"这是验证题 + 当前判定 + 命中/落空后果"，与
    methodology.md「命理师之道」§II 对齐
- `scripts/event_elicit_cli.py`：9 个子命令（init / pick-disjoint / update-stage-a /
  find-overlap / pick-stage-b / update-stage-b / find-verification /
  update-verification / evaluate）
  - 每命令 stdin 不读、命令行参数读 state JSON、stdout 输出单行 JSON
  - 错误走 stderr + exit 1
- `scripts/apply_event_finalize.py`：最终后验写回 + 重算 derived 字段
  - **复用** `adaptive_elicit._finalize_phase`（同一套 phase / phase_decision /
    strength_after_phase / yongshen_after_phase / xishen / jishen / climate 写入逻辑）
  - 加 `phase_decision.event_loop_finalized: true` + `elicitation_path: "event_loop_v9.6"`
    标记，下游可识别但不强依赖

### 新增文档

- `references/event_ask_loop_protocol.md`：完整学理协议
  - §0 何时启用 / §1 Stage A disjoint 年清单 / §2 Stage B 重叠年类别 /
    §3 验证题 / §4 收敛阈值 / §5 后验融合 / §6 写回 + 重跑契约 /
    §7 编排者契约（Claude / 调用方）/ §8 退化与 fallback /
    §9 工程不变量（assert 强制）/ §10 与其它协议关系
  - 风格对齐 `handshake_protocol.md` + `elicitation_ethics.md`

### 修改：SKILL.md v9.6 编排手册

- 新增 §2.6b 「v9.6 · 事件 Ask-Loop 兜底（R2 仍 < 0.85 时启用）」
  - 触发条件 + 完整执行序列（每步给具体 Bash 命令）
  - 自然语言 → discrete 映射规范表（防诱导铁律）
  - Round 3 红线 HS-R8/R9/R10/R11（漏重跑 / 诱导 / dunno 误判 / 多次落空仍 deliver）

### 修改：AGENTS.md

- §2 标准 pipeline 流程图加可选节点：
  `adaptive_elicit next → R2 confirmation → [若 top1<0.85] event ask-loop → score_curves 重跑`
- §4 协议映射表新增 `event_ask_loop_protocol.md` ↔ `event_*.py` 行

### 不变量保护

- `bazi.json` schema 兼容：`phase_decision` 新增 2 个**可选**标记字段
  （`event_loop_finalized` / `elicitation_path`），下游读取必须容错（v9.3.1 之前的
  bazi.json 不会有这俩字段）
- `decide_phase` / `phase_posterior.py` / `_finalize_phase` 后验公式未动
- `score_curves.py` / `virtue_motifs.py` / `render_artifact.py` 逻辑零改动——
  本次只在 phase decision 层兜底，下游照常吃 bazi.phase 重新跑
- 不引入新第三方依赖（`requirements.txt` 不变）
- 高确信命盘（top1 ≥ 0.85）行为完全不变，事件 ask-loop 不启用

### 事件 Ask-Loop 与现有通道的关系

- **与 elicit（性格自述）独立**：两条贝叶斯通道分别更新后验后融合
- **与盲派（mangpai_events）独立**：本协议是 phase decision 层兜底，盲派是事件
  烈度修正层。两者目前不交叉，未来可考虑把盲派 events 作为 `reversal_overrides`
  触发源融入本通道
- **与 virtue_motifs 独立**：母题独立通道，写回 bazi.json 后必须重跑 motif
  选择（不同 phase 触发不同母题）

---

## v9.2 — 2026-04 · 自适应贝叶斯问答 + 双盲 6 约束 + 题库静态审计

> **Triggering pattern**: 用户反馈 v8 一次性 28 题流程"问得太多 / 模棱两可 / 像在被试卷"，
> 且现有 LLM 转述 + 进度暴露存在多处 sycophancy / anchoring 风险。本次把 R1 默认路径
> 重写为自适应贝叶斯单题流式（EIG 选题 + 4 条早停 + 0 题 fast-path），并立 6 条工程
> 级双盲约束，把"算法此刻最像什么 phase"对用户和 LLM 同步隔离。

### 新增脚本（核心算法）
- `scripts/_eig_selector.py`：EIG 算法纯函数（`weighted_eig` / `bayes_update` /
  `should_stop` 4 条早停 / `pick_top_question`），带自检单测
  - 选题权重 hard×2.0 / soft×0.7（仅排序），后验更新权重 hard×2.0 / soft×1.0（与
    `decide_phase` 同源）
  - 4 条早停：S1 强落地（top1≥0.95 + margin≥0.05）/ S2 边际收益消失（top1≥0.75 +
    max_eig<0.05）/ S3 硬封顶（≥12 题）/ S4 收敛（最近 4 题摆动<0.03）
- `scripts/adaptive_elicit.py`：v9 主入口，三个 CLI 子命令
  - `next` 单题流式（默认）：state 持久化 + 0 题 fast-path（prior top1≥0.85）
  - `dump-question-set --tier core14|full28` 一次性导出 batch 题集 markdown
  - `submit-batch` 一次性提交答案 → finalize（confidence 默认上限 mid，top1≥0.97 解锁 high）
- `scripts/audit_questions.py`：8 维 ambiguity detector + 命理词典扫描
  - B1/B2/B3 critical（phase / 十神 / 五行强弱泄露）
  - A1–A8 ambiguity（vague_quantifier / subjective_judgment / multi_concept /
    temporal / counterfactual / double_neg / option_overlap / leading）

### 新增文档（双盲 6 约束 + 题库审计）
- `references/elicitation_ethics.md`：6 条工程约束论述（E1 后验隔离 / E2 不命名 phase /
  E3 不倒推进度 / E4 不揭示意图 / E5 题面无命理词 / E6 batch 缓解）+ 与
  fairness_protocol 的分工矩阵
- `references/batch_elicitation_prompt.md`：LLM 给用户的固定开场白模板 + 关键词分流
  + Anti-pattern 黑名单
- `references/question_bank_audit.md`：现题库 25 题审计报告（critical=0 / high=1 /
  medium=4 / low=4 / ok=16）
- `references/question_bank_rewrite_examples.md`：D4_Q1 / D4_Q2 / D5_Q1 / D2_Q1 /
  D1_Q1 五道改写示范

### 修改：handshake.py v9 hard cutover
- R1 默认入口标 `deprecated_v9: true`（保留 he_pan_orchestrator / mcp_server / 旧
  examples 兜底；新加 `--strict-v9` 标志硬切到 adaptive_elicit）
- R2 confirmation 选题函数从 v8 pairwise L1 升级为 weighted EIG（限定 2-phase 后验，
  对称 0.5/0.5 算 EIG 排序，避免 R1 已极度确定时选不出题）
- `askquestion_payload` 严格剥离所有后验字段（`weighted_eig` / `pairwise_target` /
  `discrimination_power` / `likelihood_table` 全部不进 payload）
- `_build_askquestion_payload` 白名单只输出 prompt + options + neutral_instruction

### 修改：_question_bank.py 加 `_check_no_phase_leak`
- 新增 `_PHASE_LEAK_TERMS` 词典（phase / 十神 / 五行强弱共 ~50 词）
- 模块加载时 warn-only 扫描所有 STATIC_QUESTIONS（v10 全量改写后改 strict assert）
- 当前 25 题全部清洁，无 warn

### 修改：协议文档 + AGENTS.md Pipeline
- `handshake_protocol.md` 加 §0 v9 自适应路径段（CLI / state schema / ASK 单轮输出 /
  finalize 输出 / EIG 选题 + 4 条早停说明）+ 更新 §7 接口契约（v9 默认 + v8
  deprecated 双链路）
- `phase_decision_protocol.md` 文头加 v9 段（指向 adaptive_elicit + ethics）
- `AGENTS.md` Pipeline 段、目录结构、§4.1 协议映射、§4.5 防御铁律、§5.1 一键示例、
  §8 LLM 回答指南全部刷到 v9

### 测试
- `tests/L0_static/test_no_nondeterministic_calls.py` 把 `_eig_selector` /
  `audit_questions` / `adaptive_elicit` 显式归类（前两者 DETERMINISTIC_CORE，
  adaptive_elicit ALLOWLIST 因用 `dt.date.today()` + `random.Random(bazi_fp)` 做
  确定性洗牌）
- 全套 pytest **194 passed, 7 skipped, 0 failed**
- examples 两份 adaptive_elicit fast-path 命中（prior 0.90 ≥ 0.85）
- 合成 jobs_steve case 流式问答 6 题 finalize（S2 边际收益消失）
- batch dump-question-set core14 输出 14 题（D1×6 + D4×6 + D3×2）
- handshake R2 EIG 选题输出 6 题 confirmation
- `calibrate.py` 与改动前 byte-equal（同样 fail，原因相同，非新引入）

### 不变量保护
- `decide_phase` / `phase_posterior.py` 后验更新公式未动 → bazi.json schema 保持兼容
- `score_curves.py` 输出未动 → examples 曲线 sha256 未受影响
- AskQuestion 抛题契约保持向后兼容（payload 是去字段而非新增字段）

---

## v9.1.1 — 2026-04 · zuogong phase 配置矩阵全量补齐

> **Triggering pattern**: v9.1.0 已建好"做功视角"7 层骨架，但配置层仅刃做功族 3 个 phase
> 三件齐全；伤官 / 杀印 / 食制 / 通明白清 8 个 phase 还停留在 metadata only 或部分配
> 的状态，矩阵右侧大片 ❌。本次按"古籍出处 + e2e fixture"流程把 8 个 phase 一次补齐。

### L1 · _phase_registry 三件套补齐
- 伤官族 3 phase
  - `shang_guan_sheng_cai`：trigger=寅申巳亥（《子平真诠·伤官生财》"财根为应期"+《穷通宝鉴·四时论》"四生为发用之地"）
  - `shang_guan_sheng_cai_geju`：trigger=寅申巳亥 + reversal 加 `bi_jie_duo_cai: neutral`（盲派师承传"伤官生财，比劫透露同行竞合"）
  - `shang_guan_pei_yin_geju`：trigger=辰戌丑未（《子平真诠·伤官佩印》"佩印者，藏神固本"+《滴天髓·伤官》"印藏库中，逢库为应"）
- 杀印族 2 phase
  - `sha_yin_xiang_sheng_geju`：trigger=寅申巳亥 + reversal 加 `qi_sha_feng_yin: positive`（《滴天髓·七杀》"逢印化杀，反凶为吉"）
  - `qi_yin_xiang_sheng`：补齐 trigger + 同 reversal
- 食制杀 1 phase
  - `shi_shen_zhi_sha_geju`：trigger=寅申巳亥 + reversal `shi_shen_zhi_sha: positive` / `qi_sha_feng_yin: neutral`（《滴天髓·七杀》"食制者贵，最忌印夺"）
- 通明 / 白清 2 phase
  - `mu_huo_tong_ming`：trigger=巳午（《滴天髓·五行论》"木火通明者，逢火地大显"）
  - `jin_bai_shui_qing`：trigger=亥子（《滴天髓·五行论》"金水相涵，逢水地清贵"）
  - reversal_overrides by-design 留空（流通秀气类无明确事件反转规则；不强凑古籍依据）

### L3 · _question_bank D6 likelihood 全量化
- D6_Q1/Q2/Q3 三题各加 7 个 phase 显式 likelihood row（共 21 row），覆盖 5 大族族群化判别
- 族内梯度对比：
  - 伤官生财（`P_SGSC_G`）A/B 双高，伤官佩印（`P_SGPY`）B 主导（耐心经营）
  - 杀印族 B/C 偏高（借印化煞 + 耐心借势）
  - 食制杀 A 偏高（主动制衡，弱于纯刃做功）
  - 通明 / 白清 C 主导（顺势而为）
- `_check_discrimination` 模块加载断言保持 pass

### L5 · mangpai_reversal_rules.yaml 新增事件反转
- 新增 `qi_sha_feng_yin` 两条规则（positive：印化七杀凶转吉；neutral：食制格印夺破格）
- 新增 `shi_shen_zhi_sha` 一条规则（positive：食神制杀格成事，主动制衡获利）
- 总规则数 5 → 10，event_keys 5 → 7

### 验收 · 新增 4 个 e2e fixture（共 16 个验收点）
- `tests/test_shang_guan_sheng_cai.py`：伤官族 4 点（L1 注册三件 / L3 D6 偏 B 佩印 / L5 反转 ≥ 3 / L6 trigger 年 geju 抬升 ≥ 2.0）
- `tests/test_sha_yin_xiang_sheng.py`：杀印族 4 点（含 qi_sha_feng_yin polarity=positive 反转断言）
- `tests/test_shi_shen_zhi_sha.py`：食制杀 4 点（含 shi_shen_zhi_sha polarity=positive 反转断言）
- `tests/test_tongming_baiqing.py`：通明 + 白清 4 点（合并测试，共享结构；不测 L5 反转 by-design）
- `tests/test_yangren_chong_cai.py::test_l1_zuogong_dimension_phases_registered` 的 must_have 集合扩展为 8 个代表 phase（覆盖五大族），防止后续族群覆盖被回退

### 配置矩阵 · 100% 对齐
| 族 | trigger | reversal | D6 likelihood | e2e fixture |
|---|---|---|---|---|
| 刃做功族 | ✅ | ✅ | ✅ | ✅ yangren_chong_cai |
| 伤官族 | ✅ | ✅ | ✅ | ✅ shang_guan_sheng_cai |
| 杀印族 | ✅ | ✅ | ✅ | ✅ sha_yin_xiang_sheng |
| 食制杀 | ✅ | ✅ | ✅ | ✅ shi_shen_zhi_sha |
| 通明 / 白清 | ✅ | by-design 留空 | ✅ | ✅ tongming_baiqing |

### 不变量保护
- 14 个 v8 core phase 的 likelihood 未动 → examples sha256 byte-equal（`shang_guan_sheng_cai.curves.json` = `cf1f6c88...`，`guan_yin_xiang_sheng.curves.json` = `7346cfc5...`）
- 默认 phase=`day_master_dominant` 下 `mangpai_events.detect_all` 反转事件数仍为 0
- 全套 192 tests pass（v9.1.0 的 176 + 本轮新增 16）

---

## v9.1.0 — 2026-04 · 盲派做功视角接入 · 7 层架构改造

> **Triggering pattern**: 一类壬日干 + 午刃 + 子财 + 阳刃驾结构的命局，盲派视角应识别为"刃冲财做功"。
> v8.1 的 `phase_posterior` 候选池只有 14 个 power 视角的 core phase，导致 `yangren_chong_cai`
> 即便被 `rare_phase_detector` 命中（confidence 0.85）也无法进入决策层 → R1 直接 reject。
>
> 这暴露了**整条流水线对"做功视角"零认知**的架构缺陷。本版本用 7 层独立改造接入做功体系，
> 而不是给某个 phase 加特判。详见 `references/phase_architecture_v9_design.md`。

### L1 · Phase Registry（统一抽象层）
- 新增 `scripts/_phase_registry.py`：54 个 phase 的 metadata 中心
  - `dimension`: power / bridge / **zuogong**
  - `zuogong_trigger_branches`: 应期地支元组（如刃族四仲 子/午/卯/酉）
  - `reversal_overrides`: phase 下事件 polarity 反转规则
  - `source`: 古籍出处（铁律：缺出处不予注册）
- 改造 `ALL_PHASE_IDS` 为动态拉取 `_phase_registry.all_ids()`

### L2 · Rare-phase 接入贝叶斯先验
- `scripts/rare_phase_detector.py`：scan/enrich 解耦，保 v8 raw hits 字段 bit-for-bit
- `scripts/_bazi_core.py`：新增 `_p7_zuogong_aggregator` 把 zuogong-dim rare hits 聚合成
  P7 evidence detector，进入 `_compute_prior_distribution_v9` 的先验分布
- 候选池单调增：从 14 → 54，且 `decide_phase(use_rare_phase=False)` 可降级回 v8 行为

### L3 · D6 做功视角判别题
- `scripts/_question_bank.py` 新增 3 道题（`D6_Q1_agency_style` / `D6_Q2_life_rhythm` / `D6_Q3_gains_source`）
- 每题 likelihood_table 对刃族 / 伤官族 / 力量族 / 从格族都有非均匀分布
- 配套 `_fill_uniform_for_missing_v9` 自动补全 54 个 phase 的均匀先验

### L4 · R3 降级路径
- `scripts/phase_posterior.py`：R1 后验 < 0.55 + rare-phase 强命中（P ≥ 0.20）时
  触发 `_suggest_round3`，专问 D6 三题
- 新增 `update_posterior_round3` 合并 R1 + R3 答案重算后验

### L5 · Mangpai 反转 DSL
- 新增 `references/mangpai_reversal_rules.yaml`：YAML 化的反转规则（5 条规则覆盖 4 类事件）
- 新增 `scripts/_mangpai_reversal.py`：纯静态 DSL 引擎（含无 pyyaml 时的最小 fallback parser）
- `scripts/mangpai_events.py::_evt`：仅在 `phase.dimension == "zuogong"` 时
  注入 `phase_context` 走反转路径（保证默认 phase bit-for-bit）

### L6 · Score curves zuogong_modifier
- `scripts/score_curves.py` 新增 `_apply_zuogong_modifier`：
  trigger 地支流年 geju 派 spirit/wealth/fame 上浮
  （内部 bonus = {spirit: 10, wealth: 8, fame: 8}，融合后实际抬升约 +3-4 分）
- 集成到 `l2_liunian_adjust`

### L7 · 用户拍板 phase_full_override
- `scripts/save_confirmed_facts.py` 新增 `--phase-full-override <PHASE_ID> --reason "..."` CLI
- `scripts/score_curves.py::apply_structural_corrections` 识别 `kind: phase_full_override`：
  调 `apply_phase_override` + 锁死 `phase_decision`（`decision_probability=1.0`,
  `confidence=user_locked`, `lock_source=confirmed_facts.phase_full_override`）

### 验收 · 11 个 e2e 测试
- 新增 `tests/test_yangren_chong_cai.py`（合成八字 + pillars 模式 + 早期 birth_year，无具体公历）
- 覆盖 L1–L7 全链路 + 防过拟合 guard：
  - L1: zuogong phase ≥ 5 + 必须包含 4 个经典做功格
  - L3: D6 三题对 4+ 经典做功格都有非均匀 likelihood（族群化判别）
  - 默认答案下不允许 yangren_chong_cai 强推（必须 R3 用户证据驱动）
  - 默认 phase 下 mangpai 反转 0 条（bit-for-bit 保护）
- 全套 176 tests pass + calibrate `--soft` 数字与改造前完全一致

### 当前覆盖度（诚实声明）
- **方法论层 100% 通用**：L1/L2/L5/L6/L7 骨架对所有 zuogong phase 生效
- **配置层渐进**：11 个 zuogong phase 中
  - 刃做功族 3 个完整配置（trigger + reversal + D6 likelihood）
  - 伤官族 / 杀印族 reversal 已配，trigger / D6 部分配
  - 通明 / 白清 / 食制杀仅 metadata
- 后续 PR 按"古籍出处 + e2e fixture"流程渐进补全，不破坏方法论先行原则

### 不变量（v9 宪法层延伸）
6. zuogong-dim phase 的 mangpai 反转**仅**在 phase 锁定后触发（`detect_all` 默认路径不读 reversal DSL）
7. D6 likelihood_table 对至少 4 个 zuogong phase 必须有非均匀分布（防过拟合 guard 自动测试）
8. 任何新 zuogong phase 注册必须带 `source` 古籍出处 + 至少一个 e2e fixture

---

## v9.0.0 — 2026-04 · Precision-Over-Recall · 多流派交叉投票 · open_phase 逃逸阀

> **Triggering pattern**: 一类"印根足够却被旧算法误判为弃命从财"的边界 case 反思。详见
> `references/diagnosis_pitfalls.md` §13-14 + `references/mind_model_protocol.md`.
>
> 这不是小修, 是结构性的范式转换:
> - **旧 (v8)**: 算法独断 → 让用户答题校验 → 80% 接受率出图
> - **新 (v9)**: 多流派加权投票 + open_phase 逃逸阀 + 必出多解备选 + LLM 兜底特殊格

### PR-1 · 通根度严判 (`本气/中气/余气` 1.0/0.5/0.2)
- 新增 `scripts/_bazi_core.py::compute_dayuan_root_strength`
- `scripts/score_curves.py::apply_phase_override` 守卫: `cong_*`/`huaqi_to_*` phase 强制
  要求 `total_root<0.30`, 否则写 `_root_strength_warnings`.
- 修复: 地支主气印星 (如 巳中本气丙=正印) 应贡献 `yin_root=1.0`, 不再被算法误标"无根 → 弃命从财".

### PR-2 · `--pillars` 弃用 + `he_pan` v8 入口守卫
- `scripts/solve_bazi.py`: `--pillars` 模式自 v9 起进入 DeprecationWarning 流程; 必须显式
  `--qiyun-age` (除非 `BAZI_ALLOW_PILLARS_DEFAULT_QIYUN=1`).
- `scripts/he_pan.py`: 入口守卫 — 任一 `bazi.json` 的 `phase.is_provisional=true` 或
  `phase.confidence<0.60` 直接拒绝合盘 (`BAZI_HEPAN_BYPASS_V8_GATE=1` 可临时绕过).
- 新增 `scripts/he_pan_orchestrator.py`: 多人 v8 编排器 (3 步: plan → collect-r1 → apply-answers).

### PR-3 · 盲派 dayun 层 fanyin/fuyin
- `scripts/mangpai_events.py` 增加 4 个 detector:
  - `detect_dayun_fuyin_natal` / `detect_dayun_fanyin_rizhu` (大运 vs 命局)
  - `detect_liunian_fuyin_dayun` / `detect_liunian_fanyin_dayun` (流年 vs 大运)
- `dayun_only` 事件仅在大运首年触发 (避免 10x 重复).

### PR-4 · 心智模型协议 + HS-R7 最高红线
- 新增 `references/mind_model_protocol.md` (五项操作戒律 + 五项认知戒律).
- `scripts/score_curves.py::hsr7_audit`: 检查 `narrative_caution` / `phase_composition` /
  `alternative_readings` / `must_be_true` 字段是否齐全; warning 模式或 `BAZI_STRICT_HSR7=1` raise.
- 同类边界 case 的 6 个独立拦截点都已落地.

### PR-5 · 罕见格全集 (~110 条) + LLM inline fallback
- 新增 `references/rare_phases_catalog.md`: 三层 catalog —
  Tier 1 (子平经典 ~60) / Tier 2 (盲派象法 ~30) / Tier 3 (紫微/铁板 ~20).
  字段: `id` / `流派` / `古书出处` / `触发条件` / `算法可判定` / `phase 等价名` / `典型应验`.
- 新增 `scripts/rare_phase_detector.py::scan_all`: 实现 ~30 个算法可判定 detector
  (八正格 + 建禄阳刃 + 魁罡日德金神日刃 + 天元一气两干不杂 + 五气朝元 + 井栏叉 +
   真从财杀 + 阳刃驾杀 + 伤官见官 + 杀印相生 + 伤官生财 + 四生四败 + 驿马 + 木火通明 +
   金白水清 + 华盖入命 等).
- 新增 `references/llm_fallback_protocol.md`: 协议化 inline prompt — 当多流派共识低
  (top1<0.55 OR gap<0.10) 时, AI 自查 catalog 输出 `fallback_phase_candidates` JSON.

### PR-6 · 多流派加权投票 + open_phase 逃逸阀
- 新增 `scripts/_school_registry.py`: 注册 6 大流派
  (子平真诠 / 滴天髓 / 穷通宝鉴 / 盲派 / 紫微 / 铁板) — 各 `weight` + `vote_type`
  (`phase_candidate` 或 `ratify_only`) + `judge` callable.
- 新增 `scripts/multi_school_vote.py`:
  - 加权投票 → 后验分布 → top3 with role + top5 with `if_this_is_right_then`.
  - **open_phase 逃逸阀**: top1<0.55 OR gap<0.10 → `decision="open_phase"`.
  - LLM fallback candidates 按 0.7x 权重回流投票.
- `scripts/score_curves.py::score()` 自动注入 `multi_school_vote` 字段到所有产物.
- 多格并存型边界 case 验证: top1=0.34 → open_phase, 杀印相生 / 伤官生财 / 调候反向干燥
  三足鼎立, 真正落到"多流派必出备解" — 不允许独断"弃命从财".

### 测试覆盖
- 新增 `tests/test_root_strength.py` (13 例)
- 新增 `tests/test_hepan_v8_gate.py` (7 例)
- 新增 `tests/test_mangpai_dayun.py` (9 例)
- 新增 `tests/test_hsr7_audit.py` (9 例)
- 新增 `tests/test_rare_phase_catalog.py` (14 例)
- 新增 `tests/test_multi_school_vote.py` (8 例)
- 总: **155 passed, 6 skipped, 2 xfailed** (基线全绿).

### 用户视角 · 落 open_phase 时 Agent 必须做什么

1. 不许独断输出"你是 X 相位".
2. 把 `multi_school_vote.alternative_readings` 全部列出, 每条带 `if_this_is_right_then`.
3. 请用户补充 ≥ 2 条具体事件年份 (学业 / 工作 / 婚配 / 大病 等), 重新跑投票.
4. 必带 HS-R7.3 disclaimer: "本工具是辅助, 不构成确定预测; 任何与你强烈直觉冲突的判定, 你保留最终裁定权".
