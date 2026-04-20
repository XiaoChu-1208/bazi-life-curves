# Changelog

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
