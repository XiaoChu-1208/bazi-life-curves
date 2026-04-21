#!/usr/bin/env python3
"""_phase_registry.py — v9 Phase Registry (做功维度接入)

统一两套 phase 体系：
  - v8 core phase（14 个，来自 _bazi_core._DETECTOR_PHASE_FAMILY，P1-P6 detector 贡献）
  - rare phase（来自 rare_phase_detector.py + rare_phases_catalog.md）

设计目标：
  - 单一事实来源（single source of truth）—— 所有 phase 的 metadata 走这里
  - 向后兼容 —— 旧 ALL_PHASE_IDS 导入路径继续可用（作为动态派生的别名）
  - 稳定 id —— phase_id 一旦注册不可改（保护 confirmed_facts.json 历史数据）
  - 古籍出处强制 —— 每个 phase 的 source 字段必填（AGENTS.md §4.2）

详见 references/phase_architecture_v9_design.md §4.1
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List


# ============================================================================
# 数据模型
# ============================================================================

@dataclass(frozen=True)
class PhaseMeta:
    """Phase 的不可变元数据。"""

    id: str
    """稳定 phase_id（如 'day_master_dominant' / 'yangren_chong_cai'）。不可改。"""

    name_cn: str
    """中文名，仅用于展示。"""

    school: str
    """流派：'ziping' | 'mangpai_zuogong' | 'sanming' | 'tianyuan' |
       'ditian_sui' | 'yuanhai_ziping' | 'mangpai' | 'mangpai_geju' | baseline"""

    dimension: str
    """识别维度：
       - 'power'     力量视角（身强身弱 + 扶抑）
       - 'zuogong'   做功视角（冲合刑害做功）
       - 'cong'      从格视角
       - 'huaqi'     化气视角
       - 'climate'   调候反向视角
       - 'special'   纯结构特征（天元一气等）
    """

    parent: Optional[str] = None
    """家族父节点 id（None 表示顶级）"""

    siblings: Tuple[str, ...] = ()
    """同家族兄弟 phase（给先验共振用）"""

    source: str = ""
    """古籍出处 / 师承（AGENTS.md §4.2 铁律：禁止 '自创'）"""

    requires: Dict[str, str] = field(default_factory=dict)
    """成立条件（供 detector 自检 + R3 targeted 题反演）:
       e.g. {"strength": ">= 中和", "print_protection": "required",
             "chong_with_cai": "required"}
    """

    zuogong_trigger_branches: Tuple[str, ...] = ()
    """做功应期流年支。仅 dimension=='zuogong' 使用。
       e.g. yangren_chong_cai → ('子', '午')"""

    reversal_overrides: Dict[str, str] = field(default_factory=dict)
    """mangpai 事件反向覆盖：{event_key: polarity}
       polarity ∈ {'positive', 'neutral', 'negative'}
       e.g. yangren_chong_cai = {"yangren_chong": "positive",
                                  "bi_jie_duo_cai": "neutral"}"""


# ============================================================================
# v8 兼容：14 个 core phase（保持 id / family 不变）
# ============================================================================

# 家族定义（复用 _bazi_core._DETECTOR_PHASE_FAMILY）
_P1_FAMILY = ("floating_dms_to_cong_cai", "floating_dms_to_cong_sha",
              "floating_dms_to_cong_er", "floating_dms_to_cong_yin")
_P2_FAMILY = ("dominating_god_cai_zuo_zhu", "dominating_god_guan_zuo_zhu",
              "dominating_god_shishang_zuo_zhu", "dominating_god_yin_zuo_zhu")
_P3_FAMILY = ("climate_inversion_dry_top", "climate_inversion_wet_top")
_P4_FAMILY = ("pseudo_following", "true_following")
_P6_FAMILY = tuple(f"huaqi_to_{wx}" for wx in ("土", "金", "水", "木", "火"))


# ============================================================================
# 注册表构造
# ============================================================================

_REGISTRY: Dict[str, PhaseMeta] = {}


def _register(meta: PhaseMeta) -> None:
    """注册一个 phase。id 冲突会抛 ValueError（保护稳定 id）。"""
    if meta.id in _REGISTRY:
        raise ValueError(f"Phase id 冲突: {meta.id}")
    if not meta.source:
        raise ValueError(f"Phase {meta.id} 缺古籍出处（AGENTS.md §4.2 铁律）")
    _REGISTRY[meta.id] = meta


# ---- v8 baseline ----
_register(PhaseMeta(
    id="day_master_dominant",
    name_cn="日主主导",
    school="ziping",
    dimension="power",
    source="子平真诠·用神篇（扶抑法本义）",
    requires={"default": "baseline"},
))

# ---- P1 从格（真从） ----
for pid, role in [("floating_dms_to_cong_cai", "财"),
                  ("floating_dms_to_cong_sha", "官杀"),
                  ("floating_dms_to_cong_er", "食伤"),
                  ("floating_dms_to_cong_yin", "印")]:
    _register(PhaseMeta(
        id=pid,
        name_cn=f"弃命从{role}",
        school="ditian_sui",
        dimension="cong",
        siblings=_P1_FAMILY,
        source="滴天髓·从象论",
        requires={"strength.total_root": "< 0.30", f"{role}_dominant": "required"},
    ))

# ---- P2 旺神得令 ----
for pid, role in [("dominating_god_cai_zuo_zhu", "财"),
                  ("dominating_god_guan_zuo_zhu", "官杀"),
                  ("dominating_god_shishang_zuo_zhu", "食伤"),
                  ("dominating_god_yin_zuo_zhu", "印")]:
    _register(PhaseMeta(
        id=pid,
        name_cn=f"旺神得令·{role}作主",
        school="ziping",
        dimension="power",
        siblings=_P2_FAMILY,
        source="子平真诠·论用神成败救应",
        requires={"strength.label": "weak", f"{role}_dominant": "required"},
    ))

# ---- P3 调候反向 ----
_register(PhaseMeta(
    id="climate_inversion_dry_top", name_cn="调候反向·上燥下寒",
    school="ziping", dimension="climate", siblings=_P3_FAMILY,
    source="穷通宝鉴·春夏秋冬总论",
))
_register(PhaseMeta(
    id="climate_inversion_wet_top", name_cn="调候反向·上湿下燥",
    school="ziping", dimension="climate", siblings=_P3_FAMILY,
    source="穷通宝鉴·春夏秋冬总论",
))

# ---- P4 真从 / 假从 ----
_register(PhaseMeta(
    id="pseudo_following", name_cn="假从格",
    school="ditian_sui", dimension="cong", siblings=_P4_FAMILY,
    source="滴天髓·从象论（假从）",
))
_register(PhaseMeta(
    id="true_following", name_cn="真从格",
    school="ditian_sui", dimension="cong", siblings=_P4_FAMILY,
    source="滴天髓·从象论（真从）",
))

# ---- P6 化气 ----
for wx in ("土", "金", "水", "木", "火"):
    _register(PhaseMeta(
        id=f"huaqi_to_{wx}", name_cn=f"化气归{wx}",
        school="ditian_sui", dimension="huaqi", siblings=_P6_FAMILY,
        source="滴天髓·化气论",
    ))


# ============================================================================
# v9 新增：做功视角 phase（zuogong）
# ============================================================================

_ZUOGONG_FAMILY_YANGREN = ("yangren_chong_cai", "sha_ren_shuang_ting_cai")

_register(PhaseMeta(
    id="yangren_chong_cai",
    name_cn="刃冲财做功格",
    school="mangpai_zuogong",
    dimension="zuogong",
    siblings=_ZUOGONG_FAMILY_YANGREN,
    source="盲派象法·刃冲做功（师承传·与『阳刃驾杀』并称二大刃做功模式）",
    requires={
        "day_gan.polarity": "阳干",
        "strength.total_root": ">= 1.0",
        "yangren_in_pillars": "required",
        "chong_between_yangren_and_cai": "required",
    },
    zuogong_trigger_branches=("子", "午", "卯", "酉"),  # 刃支 + 其冲支
    reversal_overrides={
        "yangren_chong": "positive",       # 刃冲在做功格中是兑现
        "bi_jie_duo_cai": "neutral",       # 竞合推动而非损财
        "fuyin_yingqi": "neutral",         # 做功格的伏吟 = 结构再现
        "fanyin_yingqi": "neutral",
    },
))


# 以下几个 rare phase 升格为注册 phase（dimension 明确化）
# 保留 rare_phase_detector.py 的 detector 函数
# 但通过 registry 使其可参与 posterior 候选池

_register(PhaseMeta(
    id="shang_guan_sheng_cai_geju",
    name_cn="伤官生财格",
    school="mangpai_geju",
    dimension="zuogong",
    source="子平真诠·伤官格 + 盲派象法·伤官生财",
    requires={"shang_guan_present": "required", "cai_present": "required"},
    # 寅申巳亥 = 四生支：财根发用 + 食伤生发地
    # 出处《子平真诠·伤官生财》"伤官见财，财根为应期"
    #     《穷通宝鉴·四时论》"四生为发用之地"
    zuogong_trigger_branches=("寅", "申", "巳", "亥"),
    reversal_overrides={
        "shang_guan_jian_guan": "neutral",  # 有财转化，不再纯负
        # 财通关后比劫同行，转为竞合推进而非夺财
        # 出处：盲派师承传"伤官生财，比劫透露同行竞合"
        "bi_jie_duo_cai": "neutral",
    },
))

_register(PhaseMeta(
    id="sha_yin_xiang_sheng_geju",
    name_cn="杀印相生格",
    school="mangpai_geju",
    dimension="zuogong",
    source="子平真诠·七杀格·杀印相生 + 滴天髓·七杀（逢印化杀，反凶为吉）+ 盲派象法",
    requires={"qisha_present": "required", "yin_present": "required"},
    # 寅申巳亥 = 四生支：印旺地 + 杀根透发地
    # 出处《子平真诠·七杀格·杀印相生》"杀印相生者，逢印生杀根之地为应"
    #     《滴天髓·七杀》
    zuogong_trigger_branches=("寅", "申", "巳", "亥"),
    reversal_overrides={
        "yangren_chong": "neutral",
        # 杀逢印化为贵格成事
        # 出处《滴天髓·七杀》"逢印化杀，反凶为吉"
        "qi_sha_feng_yin": "positive",
    },
))

_register(PhaseMeta(
    id="shi_shen_zhi_sha_geju",
    name_cn="食神制杀格",
    school="mangpai_geju",
    dimension="zuogong",
    source="子平真诠·七杀格·食神制杀 + 滴天髓·七杀（食制者贵，最忌印夺）",
    requires={"shishen_present": "required", "qisha_present": "required"},
    # 寅申巳亥 = 四生支：食神禄旺地 + 杀冲化地
    # 出处《子平真诠·七杀格·食神制杀》"食制者，逢食地或杀冲化为应"
    zuogong_trigger_branches=("寅", "申", "巳", "亥"),
    reversal_overrides={
        # 食神制杀格成事，主动制衡获利
        # 出处《子平真诠·七杀格·食神制杀》
        "shi_shen_zhi_sha": "positive",
        # 食制不需印化，印夺反破格
        # 出处《滴天髓·七杀》"食制者贵，最忌印夺"
        "qi_sha_feng_yin": "neutral",
    },
))

_register(PhaseMeta(
    id="shang_guan_pei_yin_geju",
    name_cn="伤官配印格",
    school="mangpai_geju",
    dimension="zuogong",
    source="子平真诠·伤官格·伤官佩印 + 滴天髓·伤官（印藏库中，逢库为应）",
    requires={"shang_guan_present": "required", "yin_present": "required"},
    # 辰戌丑未 = 四库支：印星归库为兑现
    # 出处《子平真诠·伤官佩印》"佩印者，藏神固本"
    #     《滴天髓·伤官》"印藏库中，逢库为应"
    zuogong_trigger_branches=("辰", "戌", "丑", "未"),
    reversal_overrides={
        "shang_guan_jian_guan": "positive",  # 佩印化伤，反吉
    },
))


# ============================================================================
# v9 新增：其他 rare phase（保留 detector 能力，走 registry 后入候选池）
# 这些 phase 已经在 rare_phase_detector.py 有 detector，这里只登记 metadata
# ============================================================================

# 子平八正格（严格月令透干）
for pid, role, src in [
    ("zhengguan_ge", "正官", "子平真诠·正官格"),
    ("qisha_ge", "七杀", "子平真诠·七杀格"),
    ("zhengyin_ge", "正印", "子平真诠·正印格"),
    ("pianyin_ge", "偏印", "子平真诠·偏印格"),
    ("shishen_ge", "食神", "子平真诠·食神格"),
    ("shangguan_ge", "伤官", "子平真诠·伤官格"),
    ("zhengcai_ge", "正财", "子平真诠·正财格"),
    ("piancai_ge", "偏财", "子平真诠·偏财格"),
]:
    _register(PhaseMeta(
        id=pid, name_cn=f"{role}格", school="ziping_zhenquan",
        dimension="power", source=src,
        requires={"month_qi_transparent": role},
    ))

_register(PhaseMeta(
    id="jianlu_ge", name_cn="建禄格", school="ziping_zhenquan",
    dimension="power", source="子平真诠·建禄格",
    requires={"day_gan_at_month_lu": "required"},
))
_register(PhaseMeta(
    id="yangren_ge", name_cn="阳刃格（月刃）", school="ziping_zhenquan",
    dimension="power", source="子平真诠·阳刃格",
    requires={"yangren_in_month": "required"},
    zuogong_trigger_branches=(),
))

# 三命通会 / 渊海子平杂格（结构特征类）
_register(PhaseMeta(id="kuigang_ge", name_cn="魁罡格", school="yuanhai_ziping",
                    dimension="special", source="渊海子平·魁罡格"))
_register(PhaseMeta(id="jinshen_ge", name_cn="金神格", school="yuanhai_ziping",
                    dimension="special", source="渊海子平·金神格"))
_register(PhaseMeta(id="ride_ge", name_cn="日德格", school="sanming_tonghui",
                    dimension="special", source="三命通会·日德格"))
_register(PhaseMeta(id="rigui_ge", name_cn="日贵格", school="sanming_tonghui",
                    dimension="special", source="三命通会·日贵格"))
_register(PhaseMeta(id="riren_ge", name_cn="日刃格", school="sanming_tonghui",
                    dimension="zuogong", source="三命通会·日刃格",
                    zuogong_trigger_branches=("子", "午", "卯", "酉"),
                    reversal_overrides={"yangren_chong": "positive"}))
_register(PhaseMeta(id="tianyuanyiqi", name_cn="天元一气", school="sanming_tonghui",
                    dimension="special", source="三命通会·天元一气"))
_register(PhaseMeta(id="lianggan_buza", name_cn="两干不杂", school="sanming_tonghui",
                    dimension="special", source="三命通会·两干不杂"))
_register(PhaseMeta(id="wuqi_chaoyuan", name_cn="五气朝元", school="sanming_tonghui",
                    dimension="special", source="三命通会·五气朝元"))
_register(PhaseMeta(id="jinglanchaa_ge", name_cn="井栏叉格", school="yuanhai_ziping",
                    dimension="special", source="渊海子平·井栏叉格"))

# 从格（真从）
_register(PhaseMeta(id="cong_cai_zhen", name_cn="真从财（detector）",
                    school="ditian_sui", dimension="cong",
                    source="滴天髓·真从财",
                    siblings=("floating_dms_to_cong_cai",)))
_register(PhaseMeta(id="cong_sha_zhen", name_cn="真从杀（detector）",
                    school="ditian_sui", dimension="cong",
                    source="滴天髓·真从杀",
                    siblings=("floating_dms_to_cong_sha",)))

# 盲派象法（已有 detector）
_register(PhaseMeta(id="yang_ren_jia_sha", name_cn="阳刃驾杀",
                    school="mangpai", dimension="zuogong",
                    source="盲派象法·阳刃驾杀",
                    zuogong_trigger_branches=("子", "午", "卯", "酉"),
                    reversal_overrides={"yangren_chong": "positive"}))
_register(PhaseMeta(id="shang_guan_jian_guan", name_cn="伤官见官",
                    school="mangpai", dimension="special",
                    source="盲派象法·伤官见官"))
_register(PhaseMeta(id="qi_yin_xiang_sheng", name_cn="杀印相生",
                    school="mangpai_geju", dimension="zuogong",
                    source="盲派象法·杀印相生 + 滴天髓·七杀（逢印化杀，反凶为吉）",
                    # 与 sha_yin_xiang_sheng_geju 同源，trigger 一致
                    zuogong_trigger_branches=("寅", "申", "巳", "亥"),
                    reversal_overrides={
                        "yangren_chong": "neutral",
                        "qi_sha_feng_yin": "positive",
                    }))
_register(PhaseMeta(id="shang_guan_sheng_cai", name_cn="伤官生财",
                    school="mangpai_geju", dimension="zuogong",
                    source="盲派象法·伤官生财 + 子平真诠·伤官生财（财根为应期）",
                    # 寅申巳亥 = 四生支：与 shang_guan_sheng_cai_geju 同源
                    # 出处《子平真诠·伤官生财》《穷通宝鉴·四时论》
                    zuogong_trigger_branches=("寅", "申", "巳", "亥"),
                    reversal_overrides={"shang_guan_jian_guan": "neutral"}))
_register(PhaseMeta(id="si_sheng_si_bai", name_cn="四生/四败/四库齐",
                    school="mangpai", dimension="special",
                    source="盲派象法·四生四败四库"))
_register(PhaseMeta(id="si_ku_ju", name_cn="四库聚",
                    school="mangpai", dimension="special",
                    source="盲派象法·四库聚"))
_register(PhaseMeta(id="ma_xing_yi_dong", name_cn="驿马星动",
                    school="mangpai", dimension="special",
                    source="盲派象法·驿马动"))
_register(PhaseMeta(id="hua_gai_ru_ming", name_cn="华盖入命",
                    school="mangpai", dimension="special",
                    source="盲派象法·华盖"))
_register(PhaseMeta(id="jin_bai_shui_qing", name_cn="金白水清",
                    school="mangpai", dimension="zuogong",
                    source="盲派象法·金白水清 + 滴天髓·五行论（金水相涵，逢水地清贵）",
                    # 亥子 = 水支：金白水清应在水地
                    # 出处《滴天髓·五行论》"金水相涵，逢水地清贵"
                    zuogong_trigger_branches=("亥", "子"),
                    # reversal_overrides 留空 by-design：
                    # 通明 / 白清 属于流通秀气类，无明确事件反转规则
                    # AGENTS.md 不要求强加 reversal；不强凑古籍依据
                    reversal_overrides={}))
_register(PhaseMeta(id="mu_huo_tong_ming", name_cn="木火通明",
                    school="mangpai", dimension="zuogong",
                    source="盲派象法·木火通明 + 滴天髓·五行论（木火通明者，逢火地大显）",
                    # 巳午 = 火支：木火通明应在火地
                    # 出处《滴天髓·五行论》"木火通明者，逢火地大显"
                    zuogong_trigger_branches=("巳", "午"),
                    # reversal_overrides 留空 by-design（同 jin_bai_shui_qing）
                    reversal_overrides={}))


# ============================================================================
# 公共 API
# ============================================================================

def get(phase_id: str) -> PhaseMeta:
    """获取 phase metadata。未注册 id 抛 KeyError。"""
    if phase_id not in _REGISTRY:
        raise KeyError(f"Phase id 未注册: {phase_id}")
    return _REGISTRY[phase_id]


def exists(phase_id: str) -> bool:
    return phase_id in _REGISTRY


def all_ids() -> Tuple[str, ...]:
    """全部已注册 phase id（稳定顺序）。"""
    return tuple(sorted(_REGISTRY.keys()))


def ids(*, dimension: Optional[str] = None,
        school: Optional[str] = None) -> Tuple[str, ...]:
    """按 dimension / school 筛选 id。"""
    out = []
    for pid, meta in _REGISTRY.items():
        if dimension is not None and meta.dimension != dimension:
            continue
        if school is not None and meta.school != school:
            continue
        out.append(pid)
    return tuple(sorted(out))


# v8 兼容白名单 —— 严格等于 v8.1 时期 _bazi_core.ALL_PHASE_IDS 的 14 个 id
# 这保证 _compute_prior_distribution 的 N=14 不变 → examples sha256 不变
# rare phase / zuogong phase 不进入这个白名单，通过 L2 P7 聚合器独立通道进入候选池
V8_CORE_PHASE_IDS: Tuple[str, ...] = tuple(sorted({
    "day_master_dominant",
    # P1
    "floating_dms_to_cong_cai", "floating_dms_to_cong_sha",
    "floating_dms_to_cong_er", "floating_dms_to_cong_yin",
    # P2
    "dominating_god_cai_zuo_zhu", "dominating_god_guan_zuo_zhu",
    "dominating_god_shishang_zuo_zhu", "dominating_god_yin_zuo_zhu",
    # P3
    "climate_inversion_dry_top", "climate_inversion_wet_top",
    # P4
    "pseudo_following", "true_following",
    # P6 化气
    *(f"huaqi_to_{wx}" for wx in ("土", "金", "水", "木", "火")),
}))


def core_phase_ids() -> Tuple[str, ...]:
    """v8 兼容的 14 phase（bit-for-bit 保护）。不随 registry 扩展而变。"""
    return V8_CORE_PHASE_IDS


def ids_by_dimensions(dims: frozenset) -> Tuple[str, ...]:
    return tuple(sorted(pid for pid, m in _REGISTRY.items() if m.dimension in dims))


def zuogong_phase_ids() -> Tuple[str, ...]:
    return ids(dimension="zuogong")


def dump_registry() -> Dict[str, Dict]:
    """序列化 registry（给测试 / 调试用）。"""
    out = {}
    for pid, m in sorted(_REGISTRY.items()):
        out[pid] = {
            "name_cn": m.name_cn,
            "school": m.school,
            "dimension": m.dimension,
            "parent": m.parent,
            "siblings": list(m.siblings),
            "source": m.source,
            "requires": dict(m.requires),
            "zuogong_trigger_branches": list(m.zuogong_trigger_branches),
            "reversal_overrides": dict(m.reversal_overrides),
        }
    return out


if __name__ == "__main__":
    import json
    print(f"Registered {len(_REGISTRY)} phases:")
    print(f"  by dimension:")
    for d in ("power", "zuogong", "cong", "huaqi", "climate", "special"):
        pids = ids(dimension=d)
        print(f"    {d:10s} × {len(pids):2d}  {list(pids)[:3]}...")
    print()
    print(f"  core (v8 compat) × {len(core_phase_ids())}")
    print(f"  zuogong × {len(zuogong_phase_ids())}")
