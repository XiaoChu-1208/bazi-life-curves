# Phase Architecture v9 Design · 做功维度接入方案

> **状态**：Active · **版本**：v9.0 · **日期**：2026-04-20
>
> 触发案例：一例壬日干 + 午刃 + 子财 + 阳刃驾结构的命局，盲派视角应识别为"刃冲财做功"。在 v8.1 架构下系统性识别失败（候选池只有 14 个 power-视角 phase），诊断出 10 条跨层架构缺陷。本文固化解决方案。
>
> 注：原案例的具体公历生辰已脱敏，仅在内部回归基线保留；公开测试 fixture 用合成等价八字（详见 `tests/test_yangren_chong_cai.py`）。

---

## 一、问题一句话

**v8.1 只能用"力量视角"识别命局**（14 phase 全部围绕日主强弱 / 从格 / 调候 / 化气）。当命局主结构需要用**做功视角**（刃冲财 / 食制杀 / 伤官佩印…）描述时，识别层 / 决策层 / 打分层同时失效，且三层之间没有桥接，导致失败无法被单点修复。

---

## 二、设计原则（约束条件）

1. **不动 v8.1 R1/R2 主流程** —— 只加层，不 rewrite
2. **bit-for-bit deterministic** —— 现有 examples 两个 case sha256 必须完全不变
3. **候选池单调增** —— phase 只能加，不能删（保护老 confirmed_facts.json）
4. **古籍出处铁律** —— 每个新 phase / 新反转规则必须标引古籍出处（AGENTS.md §4.2）
5. **现代化语言** —— 新题 / 新解读遵守 fairness_protocol §10 红线
6. **可回溯降级** —— 任何新层可通过 feature flag 关闭，回到 v8.1 行为

---

## 三、架构层级

```
┌──────────────────────────────────────────────────────────────┐
│ L7 confirmed_facts phase_full_override  (用户固化)            │
├──────────────────────────────────────────────────────────────┤
│ L6 score_curves · zuogong_modifier       (打分底色)            │
├──────────────────────────────────────────────────────────────┤
│ L5 mangpai_reversal_rules.yaml           (事件反转 DSL)         │
├──────────────────────────────────────────────────────────────┤
│ L4 phase_posterior · Round 3 fallback    (reject 降级)          │
├──────────────────────────────────────────────────────────────┤
│ L3 _question_bank · D6 做功视角题        (判别层)              │
├──────────────────────────────────────────────────────────────┤
│ L2 rare_phase_detector · phase_likelihoods (识别接入后验)      │
├──────────────────────────────────────────────────────────────┤
│ L1 _phase_registry.py                    (知识表示根基)         │
└──────────────────────────────────────────────────────────────┘
```

---

## 四、核心接口契约

### §4.1 Phase Registry（L1）

所有 phase 走单一注册表。`ALL_PHASE_IDS` 变为动态派生。

```python
# scripts/_phase_registry.py

@dataclass(frozen=True)
class PhaseMeta:
    id: str                        # 稳定 id（不可改，保 confirmed_facts 兼容）
    name_cn: str
    school: str                    # 'ziping' | 'mangpai_zuogong' | 'tianyuan' | 'sanming' | ...
    dimension: str                 # 'power' | 'zuogong' | 'cong' | 'huaqi' | 'climate'
    parent: Optional[str]          # None 或家族 id
    siblings: Tuple[str, ...]      # 家族内兄弟
    source: str                    # 古籍出处（禁止 "自创"）
    requires: Dict[str, Any]       # 成立条件（strength / 印护 / 冲克关系）
    zuogong_trigger_branches: Tuple[str, ...]  # 做功应期流年支（仅 dimension=zuogong 使用）
    reversal_overrides: Dict[str, str]  # {event_key: "positive"/"neutral"/"negative"}

def ids(*, dimension: Optional[str] = None, school: Optional[str] = None) -> Tuple[str, ...]:
    """动态列出 phase_id（按 dimension / school 筛选）."""

def get(phase_id: str) -> PhaseMeta: ...

def ALL_PHASE_IDS() -> Tuple[str, ...]:
    """保留旧名作为"全部已注册 phase"快捷方式。"""
```

规模：**14 power/climate/cong/huaqi + 5 新增 zuogong + 30 rare（Tier1 zapgé + Tier2 盲派）= ~49 个注册条目**。

向后兼容：`_bazi_core.ALL_PHASE_IDS` 保留为 `_phase_registry.ALL_PHASE_IDS()` 的别名。

### §4.2 rare detector 升级（L2）

rare_phase_detector 每个 detector 返回值扩展：

```python
# 老格式（保留兼容）
{"id", "school", "evidence", "confidence"}

# v9 新增字段
{
    ...老字段,
    "triggered": True,
    "score": "3/3（满足 3 条硬性条件）",
    "suggested_phase": <同 id>,
    "phase_likelihoods": Dict[phase_id, float],  # 来自 _likelihoods_from_phasemeta()
}
```

`_bazi_core.detect_all_phase_candidates()` 除了运行 P1-P6，还追加：

```python
from rare_phase_detector import scan_from_bazi
rare_hits = scan_from_bazi(bazi)
if rare_hits:
    detection_details.append(_aggregate_rare_as_P7(rare_hits))  # 单个聚合证据
```

**P7_zuogong_aggregator 规则**：按 dimension 分组，dimension=zuogong 组内 softmax 合并；dimension=power（如 jianlu_ge）累加到 day_master_dominant；dimension=cong 累加到对应 cong_* phase。避免 30 个小 hit 压垮 6 个 P1-P6。

### §4.3 D6 做功视角题（L3）

```python
# _question_bank.py 新增 3 题
D6_Q1: 主动出击 vs 顺势而为   (zuogong/power 判别)
D6_Q2: 人生节奏 剧烈节点 vs 循序累积 (zuogong/power)
D6_Q3: 得失来源 关键决策 vs 持续经营 (zuogong/power/cong)
```

likelihood_table 对所有 49 phase 打分（自动化：按 phase.dimension 生成 baseline，罕见格单独微调）。

### §4.4 Round 3 rare-phase confirmation（L4）

```
R1 后验 < 0.40:
    IF rare_phase_detector 有触发但 aggregator 被压制（prior < 0.10）:
        → 触发 Round 3: handshake.py --round 3 --targeted-rare <top_rare_phase>
        → 5 道 targeted 题（源自 phase.requires 反演）
        → phase_posterior.py --round 3 合并 R1 + R3
        IF 仍 < 0.40: 走 llm_fallback_protocol (render_with_caveat)
    ELSE: 老路径 reject 提示核对时辰
```

R3 非强制：仅当 rare hit 存在但未能主导 posterior 时触发。

### §4.5 mangpai reversal DSL（L5）

`references/mangpai_reversal_rules.yaml`：

```yaml
- event_key: yangren_chong
  default_polarity: negative
  reverse_when:
    - phase.id in [yangren_chong_cai, sha_ren_shuang_ting]
    - strength.label in [强, 强根]
  reversed_meaning: "刃冲财兑现：主动取财 / 激烈决断"
  source: 盲派口诀·刃格变通（师承传）

- event_key: bi_jie_duo_cai
  default_polarity: negative
  reverse_when:
    - phase.family == yangren_zuogong_family
    - has_印护身 == true
  reversed_meaning: "竞合推动财动（合作 / 同行 / 市场竞争出价）"
  source: 盲派口诀·印护比劫不夺
```

`mangpai_events.py` 新增 `apply_reversal_rules(event, phase_meta, strength_meta)` 读 yaml 决定 `intensity_adjustment` 和 `meaning_override`。

条件表达式最小 DSL（禁止 exec/eval，只支持：`==` / `!=` / `in` / `and` / `or` / 属性访问）。

### §4.6 zuogong_modifier（L6）

`score_curves.py` 的 geju 派打分：

```python
def geju_score_with_zuogong(base_geju: float, phase_meta: PhaseMeta, year_pillar: Pillar) -> float:
    if phase_meta.dimension != "zuogong":
        return base_geju
    if year_pillar.zhi in phase_meta.zuogong_trigger_branches:
        return base_geju + ZUOGONG_BONUS  # +10
    return base_geju
```

`ZUOGONG_BONUS = 10`（可调，写入 calibration/thresholds.yaml）。

#### trigger_branches 当前覆盖（v9.1.1）

5 大族 11 个 zuogong phase 的 trigger 集合（每条均带古籍出处，详见 `scripts/_phase_registry.py`）：

| 族 | phase id | trigger 支 | 出处 |
|---|---|---|---|
| 刃做功族 | `yangren_chong_cai` / `yang_ren_jia_sha` / `riren_ge` | 子/午/卯/酉（四仲，刃位与冲位） | 盲派象法·刃做功 |
| 伤官生财 | `shang_guan_sheng_cai` / `shang_guan_sheng_cai_geju` | 寅/申/巳/亥（四生，财根发用地） | 子平真诠·伤官生财 + 穷通宝鉴·四时论 |
| 伤官佩印 | `shang_guan_pei_yin_geju` | 辰/戌/丑/未（四库，印星归库） | 子平真诠·伤官佩印 + 滴天髓·伤官 |
| 杀印族 | `sha_yin_xiang_sheng_geju` / `qi_yin_xiang_sheng` | 寅/申/巳/亥（印旺 + 杀根透发地） | 子平真诠·杀印相生 + 滴天髓·七杀 |
| 食制杀 | `shi_shen_zhi_sha_geju` | 寅/申/巳/亥（食神禄旺地 + 杀冲化地） | 子平真诠·食神制杀 |
| 木火通明 | `mu_huo_tong_ming` | 巳/午（火地） | 滴天髓·五行论 |
| 金白水清 | `jin_bai_shui_qing` | 亥/子（水地） | 滴天髓·五行论 |

> 增加新做功格时：在 `_phase_registry.py` 的 `PhaseMeta.zuogong_trigger_branches` 字段声明，无须改 L6 代码。

### §4.7 confirmed_facts phase_full_override（L7）

```json
{
  "kind": "phase_full_override",
  "before": "day_master_dominant",
  "after": "yangren_chong_cai",
  "reason": "用户自述 + 命理顾问确认",
  "cascade": {
    "rerun_prior": true,
    "rerun_mangpai_reversal": true,
    "lock_posterior_to": 0.95
  }
}
```

`save_confirmed_facts.py --phase-full-override <phase_id> --reason <str>` CLI 入口。

---

## 五、回归保障

### §5.1 两个 examples bit-for-bit 不变

原则：**所有新增 detector / phase 对现有 examples 均不触发**。

- guan_yin_xiang_sheng.bazi.json: 丙辛合、官印相生格 → 不触发任何 zuogong phase
- shang_guan_sheng_cai.bazi.json: 月干伤官透 → 旧 `shang_guan_sheng_cai`（rare）已触发，dimension 标为 zuogong 后通过 P7 聚合进入候选池。若 posterior top-1 仍为 day_master_dominant（子平视角），sha256 保持不变。

回归断言：

```bash
.regression_baseline/
├── guan_yin_xiang_sheng.sha256   # 4fe389d6aa08ceb1...
└── shang_guan_sheng_cai.sha256   # f3d40b3048f6787a...
```

每个 PR 必须：`python3 tests/check_baseline.py` 返回 0。

### §5.2 yangren_chong_cai e2e acceptance

固化在 `tests/test_yangren_chong_cai.py`（合成等价八字 + pillars 模式，无具体公历，不指向任何特定个人）：

```python
SYNTHETIC_PILLARS = "丙子 丙申 壬午 乙巳"   # 该干支组合每 60 年重现一次
SYNTHETIC_BIRTH_YEAR = 1936                 # 早期重现年份, 与近现代任何已知人物均无关联

# 14 个验收点覆盖 L1-L7, 任一退化都阻断合并
# 关键指标:
#   - L2 prior_distribution[yangren_chong_cai] >= 0.20
#   - L3 D6 三题对至少 4 个经典做功格 (yangren_chong_cai/yang_ren_jia_sha/
#                                       riren_ge/shang_guan_sheng_cai) 都有非均匀判别力
#   - L4 D6 全 A 后 posterior_distribution[yangren_chong_cai] >= 0.60
#   - L5 锁定后 mangpai 反转事件数 >= 10, 且 yangren_chong→positive / bi_jie_duo_cai→neutral 必触发
#   - L6 trigger zhi (子/午/卯/酉) 流年 spirit geju 平均 delta >= 3.0, 显著高于非 trigger 年
#   - L7 phase_full_override 后 phase_decision 锁死 (decision_probability=1.0, lock_source 标识)
```

注：原触发案例的真实公历已脱敏，仅在 `.regression_baseline/`（gitignore）保留。

---

## 六、变更清单

| 文件 | 性质 | 行数估计 |
|---|---|---|
| `scripts/_phase_registry.py` | 新建 | ~500 |
| `scripts/_bazi_core.py` | 修改（ALL_PHASE_IDS 动态化 + P7 聚合器） | ~80 |
| `scripts/rare_phase_detector.py` | 修改（返回格式升级） | ~60 |
| `scripts/_question_bank.py` | 修改（D6 三题 + likelihood 自动生成） | ~150 |
| `scripts/handshake.py` | 修改（R3 支持） | ~60 |
| `scripts/phase_posterior.py` | 修改（R3 降级路径） | ~80 |
| `scripts/mangpai_events.py` | 修改（yaml 反转规则加载） | ~100 |
| `scripts/score_curves.py` | 修改（zuogong_modifier） | ~50 |
| `scripts/save_confirmed_facts.py` | 修改（phase_full_override） | ~40 |
| `references/mangpai_reversal_rules.yaml` | 新建 | ~200 |
| `references/phase_decision_protocol.md` | 修改（§5 / §7 / 新增 §8 R3） | ~80 |
| `references/discriminative_question_bank.md` | 修改（D6 节） | ~100 |
| `references/mangpai_protocol.md` | 修改（指向 yaml） | ~30 |
| `references/rare_phases_catalog.md` | 修改（phase 等价 → registry） | ~20 |
| `examples/yangren_chong_cai_case.yaml` | 新建 | ~40 |
| `tests/test_yangren_chong_cai.py` | 新建 | ~80 |
| `tests/check_baseline.py` | 新建 | ~30 |

总计 **~1700 行**，分 7 层独立可测。

---

## 七、明确不做的事

1. ❌ 不合并 core / rare 两个 detector 文件（设计意图不同）
2. ❌ 不替换 phase_posterior 的 naive Bayes（可解释性核心资产）
3. ❌ 不为每个 rare phase 单独加 P 系列 detector（P7_zuogong_aggregator 聚合）
4. ❌ 不改 R1/R2 基础协议（R3 是可选降级）
5. ❌ 不引入 LLM SDK（AGENTS.md §6）
