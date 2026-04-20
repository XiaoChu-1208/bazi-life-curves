# Changelog

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
