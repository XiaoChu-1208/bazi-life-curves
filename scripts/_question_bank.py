"""Question bank · v8 · phase-discriminative validation

与 references/discriminative_question_bank.md 1:1 对应。

5 维度 ≥ 28 题题库（D1×6 + D2×6 + D3 动态模板 + D4×6 + D5×4 = 22 静态 + N 动态）。
每题 likelihood_table[phase_id][option_id] 行和必须 = 1.0；模块加载时 assert。
fairness_protocol.md §10 黑名单词不得出现在 prompt + options 中；模块加载时 assert。

不要 import _bazi_core（避免循环依赖）——decide_phase 需要时反过来 import 本模块。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# §1 phase_id 全集（与 phase_decision_protocol.md §2 对齐）
# ---------------------------------------------------------------------------

ALL_PHASE_IDS = [
    "day_master_dominant",
    "floating_dms_to_cong_cai",
    "floating_dms_to_cong_sha",
    "floating_dms_to_cong_er",
    "floating_dms_to_cong_yin",
    "dominating_god_cai_zuo_zhu",
    "dominating_god_guan_zuo_zhu",
    "dominating_god_shishang_zuo_zhu",
    "dominating_god_yin_zuo_zhu",
    "climate_inversion_dry_top",
    "climate_inversion_wet_top",
    "pseudo_following",
    "true_following",
]
HUAQI_PHASES = [f"huaqi_to_{wx}" for wx in ("土", "金", "水", "木", "火")]
ALL_PHASE_IDS_FULL = ALL_PHASE_IDS + HUAQI_PHASES


# 短别名（仅在本模块内部用，避免每行重复长字符串）
P_DM = "day_master_dominant"
P_FCAI = "floating_dms_to_cong_cai"
P_FSHA = "floating_dms_to_cong_sha"
P_FER = "floating_dms_to_cong_er"
P_FYIN = "floating_dms_to_cong_yin"
P_DGCAI = "dominating_god_cai_zuo_zhu"
P_DGGUAN = "dominating_god_guan_zuo_zhu"
P_DGSS = "dominating_god_shishang_zuo_zhu"
P_DGYIN = "dominating_god_yin_zuo_zhu"
P_CIDRY = "climate_inversion_dry_top"
P_CIWET = "climate_inversion_wet_top"
P_PSEUDO = "pseudo_following"
P_TRUE = "true_following"


# ---------------------------------------------------------------------------
# §2 fairness §10 黑名单（D3 动态题选项严禁出现）
# ---------------------------------------------------------------------------

FAIRNESS_BLACKLIST = {
    "升职", "结婚", "生孩子", "生育", "怀孕", "离职", "离婚", "分手",
    "确诊", "拿到 offer", "创业", "失业", "下岗", "破产", "暴富",
    "考上", "考研", "考公", "出国", "定居",
}


# ---------------------------------------------------------------------------
# §3 dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QuestionOption:
    id: str            # "A" / "B" / "C" / "D"
    label: str


@dataclass
class Question:
    id: str
    dimension: str     # "ethnography_family" | "relationship" | "yearly_event" | "tcm_body" | "self_perception"
    weight_class: str  # "hard_evidence" | "soft_self_report"
    prompt: str
    options: List[QuestionOption]
    likelihood_table: Dict[str, Dict[str, float]]  # {phase_id: {option_id: p}}; 行和必须 ≈ 1.0
    requires_dynamic_year: Optional[int] = None
    evidence_note: str = ""


# ---------------------------------------------------------------------------
# §4 一致性 / 公正性检查
# ---------------------------------------------------------------------------

def _check_likelihood_sums(q: Question, tol: float = 1e-3) -> None:
    for phase_id, row in q.likelihood_table.items():
        s = sum(row.values())
        assert abs(s - 1.0) < tol, (
            f"{q.id} likelihood row {phase_id} sums to {s}, must be 1.0"
        )


def _check_blacklist(q: Question) -> None:
    text = q.prompt + " " + " ".join(o.label for o in q.options)
    for word in FAIRNESS_BLACKLIST:
        assert word not in text, (
            f"{q.id} contains fairness blacklist word: {word}"
        )


def _check_discrimination(q: Question, threshold: float = 0.20) -> None:
    """每题至少存在 2 个 phase 间出现 ≥ threshold 的最大 option 概率差。"""
    phases = list(q.likelihood_table.keys())
    option_ids = [o.id for o in q.options]
    for i, pi in enumerate(phases):
        for pj in phases[i + 1:]:
            for oid in option_ids:
                diff = abs(
                    q.likelihood_table[pi].get(oid, 0.0)
                    - q.likelihood_table[pj].get(oid, 0.0)
                )
                if diff >= threshold:
                    return
    raise AssertionError(
        f"{q.id} has no phase pair with ≥ {threshold} option-prob diff"
    )


def _uniform(option_ids: List[str]) -> Dict[str, float]:
    n = len(option_ids)
    return {oid: 1.0 / n for oid in option_ids}


def _fill_uniform_for_missing(
    table: Dict[str, Dict[str, float]],
    option_ids: List[str],
) -> Dict[str, Dict[str, float]]:
    """对未在 table 中显式给出的 phase，填均匀分布。
    仅填 v8 18 phase（ALL_PHASE_IDS_FULL），D1-D5 用此函数保持 bit-for-bit。"""
    full = dict(table)
    for pid in ALL_PHASE_IDS_FULL:
        if pid not in full:
            full[pid] = _uniform(option_ids)
    return full


def _fill_uniform_for_missing_v9(
    table: Dict[str, Dict[str, float]],
    option_ids: List[str],
) -> Dict[str, Dict[str, float]]:
    """v9 · 对 _phase_registry.all_ids() 全量（54 phase）填 uniform。
    仅 D6 做功视角题使用（其它题走 v8 18 phase 以保 handshake.json 兼容）。
    """
    full = dict(table)
    try:
        from _phase_registry import all_ids
        pids = all_ids()
    except Exception:
        pids = ALL_PHASE_IDS_FULL
    for pid in pids:
        if pid not in full:
            full[pid] = _uniform(option_ids)
    return full


# 4 选项题的常用 option_ids
_ABCD = ["A", "B", "C", "D"]


# ---------------------------------------------------------------------------
# §5 D1 · 民族志 × 原生家庭（6 题，hard_evidence × 2.0）
# ---------------------------------------------------------------------------

D1_QUESTIONS: List[Question] = [
    Question(
        id="D1_Q1_birth_economic_condition",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时（前后 2 年内）家里的经济状况大致是？",
        options=[
            QuestionOption("A", "富裕、宽绰，物质从未匮乏"),
            QuestionOption("B", "中等偏上，紧但不缺"),
            QuestionOption("C", "紧巴巴，常为钱发愁"),
            QuestionOption("D", "困窘，缺过基本物资"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_FCAI:   {"A": 0.40, "B": 0.35, "C": 0.15, "D": 0.10},
            P_DGCAI:  {"A": 0.35, "B": 0.35, "C": 0.20, "D": 0.10},
            P_FYIN:   {"A": 0.35, "B": 0.35, "C": 0.20, "D": 0.10},
            P_DGYIN:  {"A": 0.35, "B": 0.35, "C": 0.20, "D": 0.10},
            P_FER:    {"A": 0.10, "B": 0.20, "C": 0.45, "D": 0.25},
            P_DGSS:   {"A": 0.10, "B": 0.25, "C": 0.40, "D": 0.25},
            P_DM:     {"A": 0.20, "B": 0.30, "C": 0.30, "D": 0.20},
        }, _ABCD),
        evidence_note="年柱财星 → 父母经济；《三命通会·父母篇》",
    ),
    Question(
        id="D1_Q2_father_presence",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时（前后 2 年内）家里父亲在体感上的存在度是？",
        options=[
            QuestionOption("A", "长期在场，是家里主心骨"),
            QuestionOption("B", "在场但权威感弱（长期生病 / 经商在外）"),
            QuestionOption("C", "缺位（早逝 / 父母分居 / 常年外地）"),
            QuestionOption("D", "在场且关系紧张（高压 / 严厉 / 冲突多）"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.40, "B": 0.25, "C": 0.15, "D": 0.20},
            P_FCAI:    {"A": 0.20, "B": 0.25, "C": 0.40, "D": 0.15},
            P_FSHA:    {"A": 0.15, "B": 0.20, "C": 0.25, "D": 0.40},
            P_DGGUAN:  {"A": 0.20, "B": 0.20, "C": 0.15, "D": 0.45},
            P_FYIN:    {"A": 0.45, "B": 0.30, "C": 0.10, "D": 0.15},
            P_DGYIN:   {"A": 0.40, "B": 0.30, "C": 0.15, "D": 0.15},
        }, _ABCD),
        evidence_note="父星 = 偏财；《滴天髓·父母》",
    ),
    Question(
        id="D1_Q3_mother_presence",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时（前后 2 年内）家里母亲的角色更偏向？",
        options=[
            QuestionOption("A", "强势主事、家里实际掌权者"),
            QuestionOption("B", "温和持家、与父亲分工互补"),
            QuestionOption("C", "弱势 / 长期生病 / 早逝 / 缺位"),
            QuestionOption("D", "与你关系紧张 / 冲突多 / 距离远"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:     {"A": 0.25, "B": 0.40, "C": 0.15, "D": 0.20},
            P_FYIN:   {"A": 0.40, "B": 0.35, "C": 0.10, "D": 0.15},
            P_DGYIN:  {"A": 0.45, "B": 0.30, "C": 0.10, "D": 0.15},
            P_FCAI:   {"A": 0.15, "B": 0.15, "C": 0.30, "D": 0.40},
            P_DGCAI:  {"A": 0.15, "B": 0.15, "C": 0.30, "D": 0.40},
            P_DGSS:   {"A": 0.45, "B": 0.20, "C": 0.15, "D": 0.20},
        }, _ABCD),
        evidence_note="母星 = 正印；《子平真诠·六亲》",
    ),
    Question(
        id="D1_Q4_siblings",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你的兄弟姐妹关系大致是？",
        options=[
            QuestionOption("A", "多个兄弟姐妹，关系紧密互助"),
            QuestionOption("B", "1-2 个，关系普通"),
            QuestionOption("C", "独生 / 没有同辈手足"),
            QuestionOption("D", "有手足但常争执 / 远离 / 失和"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.35, "B": 0.40, "C": 0.10, "D": 0.15},
            P_FCAI:    {"A": 0.20, "B": 0.20, "C": 0.15, "D": 0.45},
            P_DGCAI:   {"A": 0.20, "B": 0.20, "C": 0.15, "D": 0.45},
            P_FSHA:    {"A": 0.10, "B": 0.20, "C": 0.40, "D": 0.30},
            P_DGGUAN:  {"A": 0.10, "B": 0.20, "C": 0.40, "D": 0.30},
        }, _ABCD),
        evidence_note="比劫 = 兄弟；《三命通会·兄弟篇》",
    ),
    Question(
        id="D1_Q5_birth_place_era",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时家庭所处的环境是？（结合 era_windows_skeleton）",
        options=[
            QuestionOption("A", "大城市 / 中产以上家庭"),
            QuestionOption("B", "中小城镇 / 工人家庭"),
            QuestionOption("C", "农村 / 乡镇底层"),
            QuestionOption("D", "跨地域 / 父母常迁移 / 无固定根"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_FCAI:   {"A": 0.40, "B": 0.30, "C": 0.15, "D": 0.15},
            P_DGCAI:  {"A": 0.40, "B": 0.30, "C": 0.15, "D": 0.15},
            P_DGSS:   {"A": 0.20, "B": 0.25, "C": 0.15, "D": 0.40},
            P_FER:    {"A": 0.20, "B": 0.25, "C": 0.15, "D": 0.40},
            **{f"huaqi_to_{wx}": {"A": 0.15, "B": 0.25, "C": 0.15, "D": 0.45}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="年柱 = 大环境；era_windows_skeleton 提供分类先验",
    ),
    Question(
        id="D1_Q6_grandparent_influence",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你童年（0-12 岁）受祖辈（爷奶 / 外公外婆）影响的程度？",
        options=[
            QuestionOption("A", "由祖辈带大，影响极深"),
            QuestionOption("B", "经常见面，部分影响"),
            QuestionOption("C", "偶尔见面，影响小"),
            QuestionOption("D", "没怎么见过 / 早逝 / 失联"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_FYIN:   {"A": 0.50, "B": 0.30, "C": 0.15, "D": 0.05},
            P_DGYIN:  {"A": 0.45, "B": 0.30, "C": 0.15, "D": 0.10},
            P_FCAI:   {"A": 0.10, "B": 0.20, "C": 0.30, "D": 0.40},
            P_DGCAI:  {"A": 0.10, "B": 0.25, "C": 0.30, "D": 0.35},
        }, _ABCD),
        evidence_note="印星 = 长辈 / 祖荫；《滴天髓·六亲》",
    ),
]


# ---------------------------------------------------------------------------
# §6 D2 · 关系结构（6 题，soft_self_report × 1.0；不预设对方性别）
# ---------------------------------------------------------------------------

D2_QUESTIONS: List[Question] = [
    Question(
        id="D2_Q1_partner_attraction_type",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="你反复被吸引的对象，最常见的画像是？",
        options=[
            QuestionOption("A", "强势主导型，你常跟随对方节奏"),
            QuestionOption("B", "资源型 / 给予物质型，你欣赏对方供给能力"),
            QuestionOption("C", "同辈对等型，势均力敌互不主导"),
            QuestionOption("D", "你欣赏其才华、想推他 / 她'输出'的人"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_FSHA:    {"A": 0.50, "B": 0.20, "C": 0.15, "D": 0.15},
            P_DGGUAN:  {"A": 0.50, "B": 0.20, "C": 0.15, "D": 0.15},
            P_FCAI:    {"A": 0.20, "B": 0.50, "C": 0.15, "D": 0.15},
            P_DGCAI:   {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_DM:      {"A": 0.20, "B": 0.20, "C": 0.40, "D": 0.20},
            P_FER:     {"A": 0.15, "B": 0.15, "C": 0.25, "D": 0.45},
            P_DGSS:    {"A": 0.15, "B": 0.20, "C": 0.25, "D": 0.40},
            P_FYIN:    {"A": 0.40, "B": 0.20, "C": 0.20, "D": 0.20},
        }, _ABCD),
        evidence_note="财官印食 = 关系核心人物画像；《滴天髓·夫妻》《渊海子平·妻财》",
    ),
    Question(
        id="D2_Q2_partner_proactive",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="在你过往的亲密关系建立时，多数时候是？",
        options=[
            QuestionOption("A", "你主动追求对方居多"),
            QuestionOption("B", "对方主动追求你居多"),
            QuestionOption("C", "双方差不多对等"),
            QuestionOption("D", "没有明确'建立'过程，关系自然滑入"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_FCAI:    {"A": 0.50, "B": 0.15, "C": 0.20, "D": 0.15},
            P_DGCAI:   {"A": 0.40, "B": 0.20, "C": 0.25, "D": 0.15},
            P_FSHA:    {"A": 0.15, "B": 0.50, "C": 0.20, "D": 0.15},
            P_DGGUAN:  {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_DM:      {"A": 0.20, "B": 0.20, "C": 0.45, "D": 0.15},
            P_FER:     {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20},
            P_DGSS:    {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20},
            **{f"huaqi_to_{wx}": {"A": 0.20, "B": 0.20, "C": 0.15, "D": 0.45}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="从财 vs 从杀 vs 日主主导的根本差异；《滴天髓·从化》",
    ),
    Question(
        id="D2_Q3_partner_economic_role",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="在你过往的亲密关系中，经济角色更常见是？",
        options=[
            QuestionOption("A", "你是主要经济输出方"),
            QuestionOption("B", "对方是主要经济输出方"),
            QuestionOption("C", "平摊 / 各自独立财务"),
            QuestionOption("D", "经济常是关系中的冲突源"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.25, "B": 0.20, "C": 0.40, "D": 0.15},
            P_FCAI:    {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20},
            P_DGCAI:   {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            P_FSHA:    {"A": 0.15, "B": 0.40, "C": 0.25, "D": 0.20},
            P_DGGUAN:  {"A": 0.15, "B": 0.35, "C": 0.30, "D": 0.20},
            P_FER:     {"A": 0.45, "B": 0.15, "C": 0.25, "D": 0.15},
            P_DGSS:    {"A": 0.40, "B": 0.20, "C": 0.25, "D": 0.15},
            P_FYIN:    {"A": 0.20, "B": 0.35, "C": 0.30, "D": 0.15},
        }, _ABCD),
        evidence_note="财星位置 vs 食伤位置决定能量输出方向；《渊海子平·妻财》",
    ),
    Question(
        id="D2_Q4_partner_emotional_dependence",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="在你过往的亲密关系中，情感依赖度更常见是？",
        options=[
            QuestionOption("A", "你更需要对方在场，对方相对独立"),
            QuestionOption("B", "对方更需要你在场，你相对独立"),
            QuestionOption("C", "高度互相依赖"),
            QuestionOption("D", "双方都偏独立 / 各自有空间的伴生"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.20, "B": 0.25, "C": 0.15, "D": 0.40},
            P_FYIN:    {"A": 0.45, "B": 0.15, "C": 0.25, "D": 0.15},
            P_DGYIN:   {"A": 0.40, "B": 0.20, "C": 0.25, "D": 0.15},
            P_FCAI:    {"A": 0.40, "B": 0.20, "C": 0.25, "D": 0.15},
            P_FSHA:    {"A": 0.40, "B": 0.15, "C": 0.25, "D": 0.20},
            P_DGGUAN:  {"A": 0.35, "B": 0.20, "C": 0.30, "D": 0.15},
            P_FER:     {"A": 0.15, "B": 0.40, "C": 0.20, "D": 0.25},
            P_DGSS:    {"A": 0.15, "B": 0.40, "C": 0.20, "D": 0.25},
            P_TRUE:    {"A": 0.50, "B": 0.15, "C": 0.20, "D": 0.15},
            **{f"huaqi_to_{wx}": {"A": 0.20, "B": 0.20, "C": 0.45, "D": 0.15}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="印星依赖 vs 食伤外推；《滴天髓·性情》",
    ),
    Question(
        id="D2_Q5_relationship_pattern",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="你过往关系的总体模式更接近哪个？",
        options=[
            QuestionOption("A", "长稳型，少而长"),
            QuestionOption("B", "流动型，多而短，常切换"),
            QuestionOption("C", "高强度爆发型，激烈短暂"),
            QuestionOption("D", "低密度型，长期独处或淡如水"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.45, "B": 0.20, "C": 0.15, "D": 0.20},
            P_FER:     {"A": 0.15, "B": 0.45, "C": 0.25, "D": 0.15},
            P_DGSS:    {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20},
            P_FSHA:    {"A": 0.15, "B": 0.20, "C": 0.45, "D": 0.20},
            P_FCAI:    {"A": 0.20, "B": 0.20, "C": 0.40, "D": 0.20},
            P_FYIN:    {"A": 0.40, "B": 0.15, "C": 0.15, "D": 0.30},
            P_DGYIN:   {"A": 0.40, "B": 0.15, "C": 0.15, "D": 0.30},
            P_TRUE:    {"A": 0.15, "B": 0.25, "C": 0.40, "D": 0.20},
            P_CIDRY:   {"A": 0.30, "B": 0.20, "C": 0.15, "D": 0.35},
            P_CIWET:   {"A": 0.30, "B": 0.20, "C": 0.15, "D": 0.35},
            **{f"huaqi_to_{wx}": {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="关系密度 = 用神 + 食伤 + 桃花的合成体感；《滴天髓·夫妻》",
    ),
    Question(
        id="D2_Q6_attraction_age_pattern",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="你反复被吸引的对象，年龄段更常见是？",
        options=[
            QuestionOption("A", "比你大较多（5 岁以上）"),
            QuestionOption("B", "与你相仿"),
            QuestionOption("C", "比你小较多（5 岁以上）"),
            QuestionOption("D", "无明显规律 / 跨度很大"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.20, "B": 0.50, "C": 0.20, "D": 0.10},
            P_FYIN:    {"A": 0.50, "B": 0.25, "C": 0.10, "D": 0.15},
            P_DGYIN:   {"A": 0.45, "B": 0.30, "C": 0.10, "D": 0.15},
            P_FSHA:    {"A": 0.45, "B": 0.25, "C": 0.15, "D": 0.15},
            P_DGGUAN:  {"A": 0.40, "B": 0.30, "C": 0.15, "D": 0.15},
            P_FER:     {"A": 0.15, "B": 0.25, "C": 0.45, "D": 0.15},
            P_DGSS:    {"A": 0.15, "B": 0.30, "C": 0.40, "D": 0.15},
            P_FCAI:    {"A": 0.15, "B": 0.30, "C": 0.40, "D": 0.15},
            P_DGCAI:   {"A": 0.15, "B": 0.35, "C": 0.35, "D": 0.15},
            P_TRUE:    {"A": 0.40, "B": 0.20, "C": 0.15, "D": 0.25},
            **{f"huaqi_to_{wx}": {"A": 0.15, "B": 0.25, "C": 0.15, "D": 0.45}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="十神年龄象征；《三命通会·六亲篇》",
    ),
]


# ---------------------------------------------------------------------------
# §7 D4 · 中医体征（6 题，hard_evidence × 2.0）
# ---------------------------------------------------------------------------

D4_QUESTIONS: List[Question] = [
    Question(
        id="D4_Q1_cold_heat",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你的整体寒热倾向是？",
        options=[
            QuestionOption("A", "怕冷、手脚常凉、爱穿厚"),
            QuestionOption("B", "怕热、爱出汗、爱冷饮"),
            QuestionOption("C", "上热下寒（脸红脚冷 / 口干腿凉）"),
            QuestionOption("D", "上寒下热（咽痒脚心热）/ 寒热不定"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:     {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            P_CIDRY:  {"A": 0.10, "B": 0.30, "C": 0.50, "D": 0.10},
            P_CIWET:  {"A": 0.45, "B": 0.10, "C": 0.15, "D": 0.30},
            P_FYIN:   {"A": 0.40, "B": 0.20, "C": 0.20, "D": 0.20},
            P_FCAI:   {"A": 0.25, "B": 0.35, "C": 0.20, "D": 0.20},
            P_FER:    {"A": 0.20, "B": 0.35, "C": 0.20, "D": 0.25},
            P_DGSS:   {"A": 0.20, "B": 0.35, "C": 0.20, "D": 0.25},
        }, _ABCD),
        evidence_note="《黄帝内经·素问》寒热辨证；干头 vs 地支冷暖独立判",
    ),
    Question(
        id="D4_Q2_sleep",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你过去 3 年的整体睡眠状况是？",
        options=[
            QuestionOption("A", "入睡快、深睡足、醒后清爽"),
            QuestionOption("B", "多梦 / 浅眠 / 易醒，醒后疲乏"),
            QuestionOption("C", "入睡难，但睡着后较深"),
            QuestionOption("D", "睡眠时长足，但晨起仍困倦 / 沉重"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.45, "B": 0.25, "C": 0.15, "D": 0.15},
            P_CIDRY:   {"A": 0.15, "B": 0.25, "C": 0.45, "D": 0.15},
            P_CIWET:   {"A": 0.15, "B": 0.25, "C": 0.15, "D": 0.45},
            P_DGSS:    {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_FER:     {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20},
            P_DGGUAN:  {"A": 0.20, "B": 0.30, "C": 0.35, "D": 0.15},
            P_FSHA:    {"A": 0.15, "B": 0.30, "C": 0.40, "D": 0.15},
            P_FYIN:    {"A": 0.45, "B": 0.20, "C": 0.15, "D": 0.20},
        }, _ABCD),
        evidence_note="心神 / 脾湿 / 肾水睡眠三辨；《黄帝内经·素问》《伤寒论·辨阳明病》",
    ),
    Question(
        id="D4_Q3_organs",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你长期感觉的'薄弱'部位最接近？",
        options=[
            QuestionOption("A", "心 / 神（心慌、易焦虑、口腔溃疡反复）"),
            QuestionOption("B", "脾胃（消化弱、胃胀、易腹泻或便秘）"),
            QuestionOption("C", "肺呼吸 / 皮肤（鼻炎、过敏、皮肤干）"),
            QuestionOption("D", "肝肾 / 腰膝（腰酸、膝软、精力不足）"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            P_CIDRY:   {"A": 0.30, "B": 0.15, "C": 0.40, "D": 0.15},
            P_CIWET:   {"A": 0.15, "B": 0.45, "C": 0.15, "D": 0.25},
            P_FCAI:    {"A": 0.20, "B": 0.35, "C": 0.25, "D": 0.20},
            P_DGCAI:   {"A": 0.20, "B": 0.30, "C": 0.25, "D": 0.25},
            P_FYIN:    {"A": 0.20, "B": 0.25, "C": 0.20, "D": 0.35},
            P_DGYIN:   {"A": 0.20, "B": 0.25, "C": 0.20, "D": 0.35},
            P_DGGUAN:  {"A": 0.30, "B": 0.15, "C": 0.15, "D": 0.40},
            P_DGSS:    {"A": 0.35, "B": 0.20, "C": 0.25, "D": 0.20},
        }, _ABCD),
        evidence_note="五脏 → 五行对应；《黄帝内经·素问·阴阳应象大论》",
    ),
    Question(
        id="D4_Q4_body_type",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你成年后的体型最常见是？",
        options=[
            QuestionOption("A", "偏瘦、骨架小 / 不易长肉"),
            QuestionOption("B", "中等、匀称"),
            QuestionOption("C", "偏壮 / 易长肉 / 易浮肿"),
            QuestionOption("D", "起伏大 / 体重常波动"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:     {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_CIDRY:  {"A": 0.50, "B": 0.25, "C": 0.10, "D": 0.15},
            P_CIWET:  {"A": 0.10, "B": 0.20, "C": 0.50, "D": 0.20},
            P_DGSS:   {"A": 0.25, "B": 0.20, "C": 0.15, "D": 0.40},
            P_FER:    {"A": 0.25, "B": 0.20, "C": 0.15, "D": 0.40},
            P_FCAI:   {"A": 0.20, "B": 0.30, "C": 0.35, "D": 0.15},
            P_DGCAI:  {"A": 0.20, "B": 0.30, "C": 0.35, "D": 0.15},
        }, _ABCD),
        evidence_note="燥湿 → 体型；现代体质辨证 + 《伤寒论·辨痰饮病》",
    ),
    Question(
        id="D4_Q5_appetite",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你长期的食欲与口味偏好是？",
        options=[
            QuestionOption("A", "食量大、口重（爱辣 / 咸 / 厚味）"),
            QuestionOption("B", "食量小、清淡，吃多易胀"),
            QuestionOption("C", "偏好甜食 / 碳水 / 温热饮食"),
            QuestionOption("D", "偏好生冷 / 凉饮 / 重水分"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
            P_CIDRY:   {"A": 0.20, "B": 0.15, "C": 0.20, "D": 0.45},
            P_CIWET:   {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
            P_DGCAI:   {"A": 0.45, "B": 0.15, "C": 0.20, "D": 0.20},
            P_FCAI:    {"A": 0.40, "B": 0.20, "C": 0.20, "D": 0.20},
            P_FYIN:    {"A": 0.15, "B": 0.40, "C": 0.25, "D": 0.20},
            P_DGYIN:   {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            P_DGSS:    {"A": 0.30, "B": 0.20, "C": 0.20, "D": 0.30},
        }, _ABCD),
        evidence_note="寒热口味偏好；《黄帝内经·素问·五味篇》",
    ),
    Question(
        id="D4_Q6_emotion_temperament",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你的长期情志倾向最像哪一种？",
        options=[
            QuestionOption("A", "急躁 / 易上火 / 一点就炸"),
            QuestionOption("B", "沉郁 / 易思虑 / 容易'想太多'"),
            QuestionOption("C", "平和 / 起伏小"),
            QuestionOption("D", "情绪起伏剧烈，时而高昂时而低落"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.20, "B": 0.20, "C": 0.45, "D": 0.15},
            P_CIDRY:   {"A": 0.50, "B": 0.15, "C": 0.15, "D": 0.20},
            P_CIWET:   {"A": 0.15, "B": 0.45, "C": 0.20, "D": 0.20},
            P_DGSS:    {"A": 0.20, "B": 0.15, "C": 0.20, "D": 0.45},
            P_FER:     {"A": 0.20, "B": 0.20, "C": 0.20, "D": 0.40},
            P_DGGUAN:  {"A": 0.25, "B": 0.40, "C": 0.15, "D": 0.20},
            P_FSHA:    {"A": 0.25, "B": 0.35, "C": 0.15, "D": 0.25},
            P_TRUE:    {"A": 0.20, "B": 0.20, "C": 0.20, "D": 0.40},
            P_PSEUDO:  {"A": 0.25, "B": 0.25, "C": 0.15, "D": 0.35},
        }, _ABCD),
        evidence_note="五志七情；《黄帝内经·素问·阴阳应象大论》",
    ),
]


# ---------------------------------------------------------------------------
# §8 D5 · 自我体感（4 题，soft_self_report × 1.0）
# ---------------------------------------------------------------------------

D5_QUESTIONS: List[Question] = [
    Question(
        id="D5_Q1_default_strategy",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="遇到大压力时，你最本能的反应是？",
        options=[
            QuestionOption("A", "主动迎击，靠自己硬扛"),
            QuestionOption("B", "借外力 / 找资源 / 找支持系统"),
            QuestionOption("C", "顺势而为 / 等局势变"),
            QuestionOption("D", "切换轨道 / 换个赛道重来"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.50, "B": 0.20, "C": 0.15, "D": 0.15},
            P_TRUE:    {"A": 0.10, "B": 0.20, "C": 0.50, "D": 0.20},
            P_PSEUDO:  {"A": 0.25, "B": 0.20, "C": 0.40, "D": 0.15},
            P_FCAI:    {"A": 0.15, "B": 0.25, "C": 0.40, "D": 0.20},
            P_FSHA:    {"A": 0.15, "B": 0.25, "C": 0.45, "D": 0.15},
            P_FER:     {"A": 0.15, "B": 0.15, "C": 0.40, "D": 0.30},
            P_FYIN:    {"A": 0.15, "B": 0.45, "C": 0.25, "D": 0.15},
            P_DGCAI:   {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_DGGUAN:  {"A": 0.15, "B": 0.30, "C": 0.40, "D": 0.15},
            P_DGSS:    {"A": 0.20, "B": 0.25, "C": 0.20, "D": 0.35},
            P_DGYIN:   {"A": 0.20, "B": 0.50, "C": 0.20, "D": 0.10},
            **{f"huaqi_to_{wx}": {"A": 0.10, "B": 0.25, "C": 0.15, "D": 0.50}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="从化 vs 自主 vs 化轨 三类核心差异；《滴天髓·性情》《滴天髓·从化》",
    ),
    Question(
        id="D5_Q2_money_attitude",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="你对金钱的本能态度更接近？",
        options=[
            QuestionOption("A", "主动管理 / 重视积累 / 擅长保值"),
            QuestionOption("B", "善于撬动 / 借力生财 / 资源整合"),
            QuestionOption("C", "看淡 / 够用就好 / 不主动追求"),
            QuestionOption("D", "起伏大 / 来去快 / 不擅积蓄"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.45, "B": 0.20, "C": 0.20, "D": 0.15},
            P_FCAI:    {"A": 0.15, "B": 0.45, "C": 0.15, "D": 0.25},
            P_DGCAI:   {"A": 0.20, "B": 0.45, "C": 0.15, "D": 0.20},
            P_FYIN:    {"A": 0.25, "B": 0.15, "C": 0.45, "D": 0.15},
            P_DGYIN:   {"A": 0.30, "B": 0.15, "C": 0.40, "D": 0.15},
            P_FER:     {"A": 0.15, "B": 0.20, "C": 0.20, "D": 0.45},
            P_DGSS:    {"A": 0.15, "B": 0.25, "C": 0.20, "D": 0.40},
            P_TRUE:    {"A": 0.15, "B": 0.40, "C": 0.20, "D": 0.25},
            **{f"huaqi_to_{wx}": {"A": 0.15, "B": 0.30, "C": 0.15, "D": 0.40}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="财星 vs 印星 vs 食伤的金钱观差异；《渊海子平·财》",
    ),
    Question(
        id="D5_Q3_authority_relation",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="你与权威 / 规则系统的关系更接近？",
        options=[
            QuestionOption("A", "自己定规则 / 不愿被管"),
            QuestionOption("B", "在规则内争上游 / 善用规则"),
            QuestionOption("C", "服从规则 / 适应权威"),
            QuestionOption("D", "体制外 / 边缘化 / 与规则保持距离"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.45, "B": 0.25, "C": 0.20, "D": 0.10},
            P_FSHA:    {"A": 0.15, "B": 0.25, "C": 0.45, "D": 0.15},
            P_DGGUAN:  {"A": 0.15, "B": 0.20, "C": 0.50, "D": 0.15},
            P_FCAI:    {"A": 0.25, "B": 0.40, "C": 0.20, "D": 0.15},
            P_DGCAI:   {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_FER:     {"A": 0.25, "B": 0.15, "C": 0.15, "D": 0.45},
            P_DGSS:    {"A": 0.30, "B": 0.15, "C": 0.15, "D": 0.40},
            P_FYIN:    {"A": 0.20, "B": 0.25, "C": 0.40, "D": 0.15},
            P_DGYIN:   {"A": 0.15, "B": 0.25, "C": 0.45, "D": 0.15},
            **{f"huaqi_to_{wx}": {"A": 0.25, "B": 0.15, "C": 0.15, "D": 0.45}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="官杀 vs 食伤 = 规则态度的两极；《滴天髓·官杀》",
    ),
    Question(
        id="D5_Q4_creative_outlet",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="你最自然的'创造性输出'方式是？",
        options=[
            QuestionOption("A", "表达 / 内容 / 表演型输出"),
            QuestionOption("B", "组织 / 系统建设 / 资源整合"),
            QuestionOption("C", "学习 / 研究 / 知识沉淀"),
            QuestionOption("D", "没有明显输出冲动 / 不需要外显"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.30, "B": 0.30, "C": 0.20, "D": 0.20},
            P_FER:     {"A": 0.50, "B": 0.20, "C": 0.15, "D": 0.15},
            P_DGSS:    {"A": 0.45, "B": 0.20, "C": 0.20, "D": 0.15},
            P_FCAI:    {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_DGCAI:   {"A": 0.20, "B": 0.45, "C": 0.20, "D": 0.15},
            P_FYIN:    {"A": 0.20, "B": 0.20, "C": 0.50, "D": 0.10},
            P_DGYIN:   {"A": 0.20, "B": 0.20, "C": 0.45, "D": 0.15},
            P_FSHA:    {"A": 0.20, "B": 0.40, "C": 0.20, "D": 0.20},
            P_DGGUAN:  {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            P_TRUE:    {"A": 0.20, "B": 0.20, "C": 0.20, "D": 0.40},
            **{f"huaqi_to_{wx}": {"A": 0.25, "B": 0.25, "C": 0.15, "D": 0.35}
               for wx in ("土", "金", "水", "木", "火")},
        }, _ABCD),
        evidence_note="食伤 / 财 / 印 = 三种主要输出原型；《滴天髓·性情》",
    ),
]


# ---------------------------------------------------------------------------
# §9 D3 · 流年大事件（动态题模板，hard_evidence × 2.0）
# ---------------------------------------------------------------------------

D3_DIMENSIONS = ["overall", "emotion", "career", "health", "money", "relationship"]

_D3_DIMENSION_LABELS = {
    "overall":      "综合方向",
    "emotion":      "感情方向",
    "career":       "事业方向",
    "health":       "身体方向",
    "money":        "财务方向",
    "relationship": "重要关系方向",
}


def D3_dynamic_event_question(
    age: int,
    year: int,
    dimension: str,
    phase_curve_values: Dict[str, float],
) -> Question:
    """根据某一年各 phase 的曲线值，生成 4 档方向题。

    phase_curve_values: {phase_id: 该年该维度的曲线值（建议归一到 [-5, 5]）}
    没显式给出的 phase 走均匀分布。
    """
    options = [
        QuestionOption("A", "明显向上 / 顺风顺水"),
        QuestionOption("B", "明显向下 / 受挫连连"),
        QuestionOption("C", "大起大落 / 起伏剧烈"),
        QuestionOption("D", "平稳 / 没什么特别记忆"),
    ]
    table: Dict[str, Dict[str, float]] = {}
    for pid, v in phase_curve_values.items():
        if abs(v) >= 3.0:
            # 大幅波动 → C 档主导
            table[pid] = {"A": 0.20, "B": 0.20, "C": 0.50, "D": 0.10}
        elif v >= 2.0:
            table[pid] = {"A": 0.55, "B": 0.10, "C": 0.20, "D": 0.15}
        elif v <= -2.0:
            table[pid] = {"A": 0.10, "B": 0.55, "C": 0.20, "D": 0.15}
        else:
            table[pid] = {"A": 0.20, "B": 0.20, "C": 0.20, "D": 0.40}
    full_table = _fill_uniform_for_missing(table, _ABCD)
    dim_label = _D3_DIMENSION_LABELS.get(dimension, "综合方向")
    q = Question(
        id=f"D3_Q_age{age}_{dimension}",
        dimension="yearly_event",
        weight_class="hard_evidence",
        prompt=f"你 {age} 岁那一年（约 {year} 年），{dim_label}整体感觉是？",
        options=options,
        likelihood_table=full_table,
        requires_dynamic_year=year,
        evidence_note="流年节奏 phase 决策最强信号；《穷通宝鉴·流年篇》",
    )
    _check_blacklist(q)
    _check_likelihood_sums(q)
    return q


# ---------------------------------------------------------------------------
# §9.5 D6 · 做功视角（v9 · 3 题，soft_self_report × 1.0）
# ---------------------------------------------------------------------------
# 设计目标：把 power 视角（日主强弱 / 扶抑）和 zuogong 视角（冲合刑做功）在
#   自我体感层面区分开。所有题目必须避免事件化黑名单词汇（见 FAIRNESS_BLACKLIST）。
# 古籍出处：盲派象法·刃冲做功 / 子平真诠·用神成败救应（两者对"做功 vs 扶抑"的
#   原始区分）。
# ---------------------------------------------------------------------------

# D6 专用 phase 短别名（zuogong 维度代表）
P_YRCC = "yangren_chong_cai"           # 刃冲财做功
P_YRJS = "yang_ren_jia_sha"            # 阳刃驾杀
P_SGSC = "shang_guan_sheng_cai"        # 伤官生财
P_SYXS = "sha_yin_xiang_sheng_geju"    # 杀印相生（格局派）
P_RIREN = "riren_ge"                    # 日刃格

D6_QUESTIONS: List[Question] = [
    Question(
        id="D6_Q1_agency_style",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="在人生大方向上，你更接近哪一种推进模式？",
        options=[
            QuestionOption("A", "主动出击：找到目标就直接启动，靠强决断推进"),
            QuestionOption("B", "有明确目标，但耐心经营、按部就班地攒资源"),
            QuestionOption("C", "随机应变：外部机会来了就跟，不太预设路径"),
            QuestionOption("D", "被推着走：多数关键节点是被环境 / 关系决定的"),
        ],
        likelihood_table=_fill_uniform_for_missing_v9({
            # 做功视角（刃/杀/伤官做功）→ A 高
            P_YRCC:    {"A": 0.55, "B": 0.15, "C": 0.20, "D": 0.10},
            P_YRJS:    {"A": 0.55, "B": 0.15, "C": 0.20, "D": 0.10},
            P_RIREN:   {"A": 0.50, "B": 0.20, "C": 0.20, "D": 0.10},
            P_SGSC:    {"A": 0.35, "B": 0.35, "C": 0.20, "D": 0.10},
            # 力量视角（DM / 旺神作主）→ B 高
            P_DM:      {"A": 0.25, "B": 0.45, "C": 0.20, "D": 0.10},
            P_DGCAI:   {"A": 0.20, "B": 0.50, "C": 0.20, "D": 0.10},
            P_DGGUAN:  {"A": 0.20, "B": 0.45, "C": 0.25, "D": 0.10},
            P_DGSS:    {"A": 0.30, "B": 0.35, "C": 0.25, "D": 0.10},
            P_DGYIN:   {"A": 0.15, "B": 0.50, "C": 0.25, "D": 0.10},
            # 从格视角 → C / D 高
            P_FCAI:    {"A": 0.15, "B": 0.15, "C": 0.40, "D": 0.30},
            P_FSHA:    {"A": 0.15, "B": 0.15, "C": 0.35, "D": 0.35},
            P_FER:     {"A": 0.20, "B": 0.15, "C": 0.45, "D": 0.20},
            P_FYIN:    {"A": 0.10, "B": 0.25, "C": 0.30, "D": 0.35},
            P_TRUE:    {"A": 0.10, "B": 0.10, "C": 0.40, "D": 0.40},
            P_PSEUDO:  {"A": 0.15, "B": 0.20, "C": 0.35, "D": 0.30},
        }, _ABCD),
        evidence_note="主动决断 vs 耐心累积 vs 被动 的三分；盲派象法·刃冲做功 / 子平真诠·用神成败",
    ),
    Question(
        id="D6_Q2_life_rhythm",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="回顾你人生到目前为止的整体节奏，更像哪一种？",
        options=[
            QuestionOption("A", "几次剧烈转折决定全局，剩下是在消化这些转折"),
            QuestionOption("B", "阶段性爆发 + 阶段性平稳交替，起伏明显"),
            QuestionOption("C", "循序渐进累积，缓慢稳步上升"),
            QuestionOption("D", "起伏不稳定，常被动应对外部变动"),
        ],
        likelihood_table=_fill_uniform_for_missing_v9({
            # 做功视角 → A 高（剧烈转折 = 做功兑现）
            P_YRCC:    {"A": 0.55, "B": 0.25, "C": 0.10, "D": 0.10},
            P_YRJS:    {"A": 0.50, "B": 0.30, "C": 0.10, "D": 0.10},
            P_RIREN:   {"A": 0.45, "B": 0.30, "C": 0.15, "D": 0.10},
            P_SGSC:    {"A": 0.30, "B": 0.40, "C": 0.20, "D": 0.10},
            # 力量视角 → C 高（累积型）
            P_DM:      {"A": 0.15, "B": 0.25, "C": 0.50, "D": 0.10},
            P_DGCAI:   {"A": 0.15, "B": 0.25, "C": 0.50, "D": 0.10},
            P_DGGUAN:  {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
            P_DGSS:    {"A": 0.20, "B": 0.35, "C": 0.35, "D": 0.10},
            P_DGYIN:   {"A": 0.15, "B": 0.25, "C": 0.50, "D": 0.10},
            # 从格视角 → D 高（被动型）
            P_FCAI:    {"A": 0.15, "B": 0.20, "C": 0.20, "D": 0.45},
            P_FSHA:    {"A": 0.15, "B": 0.20, "C": 0.20, "D": 0.45},
            P_FER:     {"A": 0.15, "B": 0.25, "C": 0.20, "D": 0.40},
            P_FYIN:    {"A": 0.10, "B": 0.20, "C": 0.30, "D": 0.40},
            P_TRUE:    {"A": 0.10, "B": 0.15, "C": 0.20, "D": 0.55},
            P_PSEUDO:  {"A": 0.15, "B": 0.25, "C": 0.20, "D": 0.40},
        }, _ABCD),
        evidence_note="节奏形态：剧变（做功）vs 累积（扶抑）vs 被动（从格）；盲派象法·做功应期",
    ),
    Question(
        id="D6_Q3_gains_source",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="到目前为止，你最重要的几次「得失变化」更多来自？",
        options=[
            QuestionOption("A", "少数几个关键决策 / 一次定型的选择"),
            QuestionOption("B", "关键决策 + 日常经营并重，两者贡献相近"),
            QuestionOption("C", "长期持续经营 + 复利积累，没有特别戏剧的节点"),
            QuestionOption("D", "外部给定 / 周围人推动 / 时机到来就自然发生"),
        ],
        likelihood_table=_fill_uniform_for_missing_v9({
            P_YRCC:    {"A": 0.60, "B": 0.20, "C": 0.10, "D": 0.10},
            P_YRJS:    {"A": 0.55, "B": 0.25, "C": 0.10, "D": 0.10},
            P_RIREN:   {"A": 0.50, "B": 0.30, "C": 0.10, "D": 0.10},
            P_SGSC:    {"A": 0.30, "B": 0.40, "C": 0.20, "D": 0.10},
            P_DM:      {"A": 0.15, "B": 0.30, "C": 0.45, "D": 0.10},
            P_DGCAI:   {"A": 0.15, "B": 0.30, "C": 0.45, "D": 0.10},
            P_DGGUAN:  {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
            P_DGSS:    {"A": 0.25, "B": 0.30, "C": 0.35, "D": 0.10},
            P_DGYIN:   {"A": 0.15, "B": 0.30, "C": 0.45, "D": 0.10},
            P_FCAI:    {"A": 0.15, "B": 0.20, "C": 0.20, "D": 0.45},
            P_FSHA:    {"A": 0.15, "B": 0.20, "C": 0.20, "D": 0.45},
            P_FER:     {"A": 0.20, "B": 0.25, "C": 0.20, "D": 0.35},
            P_FYIN:    {"A": 0.10, "B": 0.25, "C": 0.25, "D": 0.40},
            P_TRUE:    {"A": 0.10, "B": 0.15, "C": 0.20, "D": 0.55},
            P_PSEUDO:  {"A": 0.15, "B": 0.20, "C": 0.25, "D": 0.40},
        }, _ABCD),
        evidence_note="得失来源：决策驱动（做功）vs 经营驱动（扶抑）vs 被给予（从格）",
    ),
]


# ---------------------------------------------------------------------------
# §10 全部静态题集合 + 模块加载时一致性检查
# ---------------------------------------------------------------------------

STATIC_QUESTIONS: List[Question] = (
    D1_QUESTIONS + D2_QUESTIONS + D4_QUESTIONS + D5_QUESTIONS + D6_QUESTIONS
)


for _q in STATIC_QUESTIONS:
    _check_likelihood_sums(_q)
    _check_blacklist(_q)
    _check_discrimination(_q)


def get_static_questions() -> List[Question]:
    return STATIC_QUESTIONS


def get_questions_by_dimension(dimension: str) -> List[Question]:
    return [q for q in STATIC_QUESTIONS if q.dimension == dimension]


# ---------------------------------------------------------------------------
# §11 discrimination_power 计算（与 markdown §8 一致）
# ---------------------------------------------------------------------------

def discrimination_power(q: Question, prior: Dict[str, float]) -> float:
    """KL-style 简化区分度：phase 对在选项分布上的 L1 距离按 prior 加权平均。"""
    phases = list(q.likelihood_table.keys())
    total = 0.0
    weight_sum = 0.0
    for i, pi in enumerate(phases):
        for pj in phases[i + 1:]:
            if pi not in q.likelihood_table or pj not in q.likelihood_table:
                continue
            l1 = sum(
                abs(q.likelihood_table[pi].get(o.id, 0.0)
                    - q.likelihood_table[pj].get(o.id, 0.0))
                for o in q.options
            )
            w = prior.get(pi, 0.05) * prior.get(pj, 0.05)
            total += l1 * w
            weight_sum += w
    return total / max(weight_sum, 1e-9)


__all__ = [
    "ALL_PHASE_IDS",
    "HUAQI_PHASES",
    "ALL_PHASE_IDS_FULL",
    "FAIRNESS_BLACKLIST",
    "QuestionOption",
    "Question",
    "D1_QUESTIONS",
    "D2_QUESTIONS",
    "D4_QUESTIONS",
    "D5_QUESTIONS",
    "STATIC_QUESTIONS",
    "D3_DIMENSIONS",
    "D3_dynamic_event_question",
    "get_static_questions",
    "get_questions_by_dimension",
    "discrimination_power",
]
