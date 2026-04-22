"""Question bank · v8 · phase-discriminative validation

与 references/discriminative_question_bank.md 1:1 对应。

5 维度 ≥ 28 题题库（D1×6 + D2×6 + D3 动态模板 + D4×6 + D5×4 = 22 静态 + N 动态）。
每题 likelihood_table[phase_id][option_id] 行和必须 = 1.0；模块加载时 assert。
fairness_protocol.md §10 黑名单词不得出现在 prompt + options 中；模块加载时 assert。

不要 import _bazi_core（避免循环依赖）——decide_phase 需要时反过来 import 本模块。
"""
from __future__ import annotations

import re
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
    # v9 · 大白话铁律：可选的"用户侧 1 句话引导"（≤40 字，**禁止**泄露 phase 名 / 内部模型）。
    # 用法：在 askquestion_payload 里和 prompt 一起渲染，帮助用户理解题目意图。
    # 例：「想了解你早年家里的物质条件，请按当时整体感觉选；不太确定就选 X」。
    intro: str = ""


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


# v9 · 算命专业词典（phase / 十神 / 五行强弱）
# 出现这些词意味着题面在向用户**泄露算法内部模型**，违反 elicitation_ethics §E1 / §E4。
# 当前阶段（v9 PR1）只 warn，不 hard-fail —— 题库 v10 全量改写后改为 assert。
_PHASE_LEAK_TERMS = (
    "格局", "从财", "从官", "从杀", "从儿", "从印", "从势",
    "化气", "真化", "假化", "真从", "假从",
    "三奇", "成象", "日主", "用神", "喜神", "忌神", "调候",
    "下马威", "盲派", "盲师", "纳音", "胎元", "命宫",
    "正官", "七杀", "偏官", "偏财", "正财", "食神", "伤官",
    "偏印", "枭神", "正印", "比肩", "劫财", "羊刃",
    "食伤", "官杀", "印星", "财星", "比劫",
    "身强", "身弱", "太过", "不及", "失令", "得令", "通根",
    "透干", "扶抑",
)


def _check_no_phase_leak(q: Question, *, strict: bool = True) -> List[str]:
    """v9 · 静态扫题面 / option label 中是否泄露算法内部命理词。

    v9 默认 strict=True。当前题库 25 题已全部清洗为 0 leak。
    若新加题偷懒带回了命理术语，模块加载即 AssertionError，CI fail-fast。

    详见 references/elicitation_ethics.md §E1 + scripts/audit_questions.py B1/B2/B3。
    """
    text = q.prompt + " || " + " | ".join(o.label for o in q.options)
    hits = [w for w in _PHASE_LEAK_TERMS if w in text]
    if hits and strict:
        raise AssertionError(
            f"{q.id} 题面泄露命理词: {hits} —— 违反 elicitation_ethics §E1。\n"
            f"  违规题面：{q.prompt!r}\n"
            f"  违规选项：{[o.label for o in q.options]!r}\n"
            f"  修法：用大白话改写，把命理术语替换为生活化体感描述。\n"
            f"  详见 references/discriminative_question_bank.md「行话→大白话」对照表。"
        )
    return hits


# v9 · 大白话铁律：option label 不允许是 1-3 字"对/不对/部分/其它"占位空选项。
# 题面 + 选项 token 总长度 / 命理术语数 → 简易 readability 估计；触发 warn（agent
# 重写题时容易 regress 到术语化）。
#
# v9.3 加强：用户在 18e281d2 case 多次反馈"描述都跟我沾边但都不完全像"
# （D6_Q2 节奏感、D6_Q3 得失来源、D4_Q2 睡眠都被吐槽），原因是 label 5-8 字
# 的"核心描述"太短，无法承载消歧场景。把阈值拉到 12 → 强迫每个选项写出
# "核心描述 + 场景边界"，并通过 _check_option_disambiguation 强制每题至少
# 一个选项带括号备注（"XX 也算 / 偏 YY / 含 ZZ"）。
_MIN_OPTION_LABEL_CHARS = 12  # v9.3 ↑ from 5 → 12，强迫场景化
_OPTIONS_BANNED_LITERAL = {"对", "不对", "是", "不是", "对/错", "对 / 错", "部分", "其它", "其他"}


def _check_plain_language(q: Question, *, strict: bool = True) -> List[str]:
    """v9 · 大白话铁律 · option label 必须有最低描述性。

    检查项：
      P1. 任何 option label 不得 ∈ _OPTIONS_BANNED_LITERAL（"对/不对/是/不是/部分/其它"）
      P2. 任何 option label 长度 ≥ _MIN_OPTION_LABEL_CHARS（v9.3 默认 12）
      P3. 题面 + 选项总文本不得高密度命理术语（_PHASE_LEAK_TERMS 命中 ≥1 已被 P1 捕获）

    P1/P2 违反 = 用户答题缺乏锚点，likelihood_table 失去判别度。
    详见 references/elicitation_ethics.md §E5 + plan §2.2。
    """
    issues: List[str] = []
    for o in q.options:
        label = (o.label or "").strip()
        if label in _OPTIONS_BANNED_LITERAL:
            issues.append(f"option {o.id}: 命中 banned literal {label!r}（违反 P1）")
        if len(label) < _MIN_OPTION_LABEL_CHARS:
            issues.append(
                f"option {o.id}: label 仅 {len(label)} 字 (<{_MIN_OPTION_LABEL_CHARS})，"
                f"违反 P2 → {label!r}"
            )
    if issues and strict:
        raise AssertionError(
            f"{q.id} 违反大白话铁律：\n  " + "\n  ".join(issues) +
            f"\n  题面：{q.prompt!r}"
            f"\n  详见 references/elicitation_ethics.md §E5 大白话铁律。"
        )
    return issues


# v9.3 · 选项消歧铁律：每题至少 1 个选项 label 带括号备注（"XX 也算 / 偏 YY / 含 ZZ"），
# 帮助命主在"核心描述跟我沾边但不完全像"时仍有锚点选。
_DISAMB_BRACKET_RE = re.compile(r"[（(]([^）)]{4,})[）)]")
_DISAMB_HINT_TOKENS = (
    "也算", "也属于", "也行", "也可", "也包含", "也包括",
    "含", "偏", "主要", "大致", "大体", "大概", "差不多", "倾向", "更像",
    "≈", "≤", "≥", "约", "左右",
)


def _check_option_disambiguation(q: Question, *, strict: bool = True) -> List[str]:
    """v9.3 · 每题至少 1 个 option label 带「消歧括号备注」。

    备注格式：括号 ≥4 字内容，且括号内出现 _DISAMB_HINT_TOKENS 任一 token，例如：
        - 「内向（偏安静、独处也算）」
        - 「23-30 岁（前后 ±2 年也行）」
        - 「容易长肉（含浮肿、易瘦下来）」

    意图：当用户在 18e281d2 case 反复说"我跟好几个选项都有点像但都不完全像"时，
    给他/她一个"含 / 偏 / 也算"的扩展空间，而不是只能选最接近的"核心描述"。

    违反 = strict raise；非 strict = 返回 issues 列表。
    """
    issues: List[str] = []
    has_disamb = False
    for o in q.options:
        label = (o.label or "")
        for m in _DISAMB_BRACKET_RE.finditer(label):
            note = m.group(1)
            if any(tok in note for tok in _DISAMB_HINT_TOKENS):
                has_disamb = True
                break
        if has_disamb:
            break
    if not has_disamb:
        issues.append(
            f"题 {q.id}：4 个选项无任何带「消歧括号备注」的 label。"
            f" v9.3 铁律：至少 1 个选项必须形如「核心描述（XX 也算 / 偏 YY / 含 ZZ）」。"
        )
    if issues and strict:
        raise AssertionError(
            f"{q.id} 违反 v9.3 选项消歧铁律：\n  " + "\n  ".join(issues) +
            f"\n  题面：{q.prompt!r}"
            f"\n  options：" +
            "\n    ".join(f"{o.id}: {o.label!r}" for o in q.options) +
            f"\n  详见 plan v9.3 改动 1 + references/elicitation_ethics.md §E5。"
        )
    return issues


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
            QuestionOption("A", "富裕宽绰，物质从未匮乏（含家底厚实、衣食无忧也算）"),
            QuestionOption("B", "中等到中等偏上，日子紧但不缺（偶有手紧但没真缺过也算）"),
            QuestionOption("C", "紧巴巴，常为钱发愁（含父母为钱吵架、买东西要算计也算）"),
            QuestionOption("D", "困窘，缺过基本物资（含吃穿、医疗、上学钱真不够也算）"),
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
        intro='想了解你出生那两年家里物质条件大致怎样；按整体感觉选最贴的一档。',
    ),
    Question(
        id="D1_Q2_father_presence",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时（前后 2 年内）家里父亲在体感上的存在度是？",
        options=[
            QuestionOption("A", "长期在场且是家里主心骨（含话语权大、拍板者也算）"),
            QuestionOption("B", "人在场但权威感弱（含长期生病、经商常出差、性格软等也算）"),
            QuestionOption("C", "缺位（含早逝、父母分居、长年外地、被关押 / 隐姓等也算）"),
            QuestionOption("D", "在场但关系紧张（含高压管教、严厉打骂、冲突频繁也算）"),
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
        intro='问的是父亲在你婴幼期家里的"分量感"，不是好坏评价。',
    ),
    Question(
        id="D1_Q3_mother_presence",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时（前后 2 年内）家里母亲的角色更偏向？",
        options=[
            QuestionOption("A", "强势主事、家里实际掌权者（含强势但对你温柔溺爱也算）"),
            QuestionOption("B", "温和持家、与父亲分工互补（含传统贤内助、不强势也不弱也算）"),
            QuestionOption("C", "弱势 / 长期生病 / 早逝 / 缺位（含产后抑郁、长期不在身边也算）"),
            QuestionOption("D", "与你关系紧张 / 冲突多 / 距离远（含对你忽冷忽热、控制欲强也算）"),
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
        intro='同样问的是母亲在你婴幼期的角色定位，不带"好母亲 / 坏母亲"评价。',
    ),
    Question(
        id="D1_Q4_siblings",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你的兄弟姐妹关系大致是？",
        options=[
            QuestionOption("A", "多个兄弟姐妹，关系紧密互助（含从小一起长大、能托付也算）"),
            QuestionOption("B", "1-2 个手足，关系一般（含联系不密、各自过自己生活也算）"),
            QuestionOption("C", "独生 / 没有同辈手足（含只有表 / 堂亲、没亲手足也算）"),
            QuestionOption("D", "有手足但常争执 / 远离 / 失和（含成年后断联、为家事翻脸也算）"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_DM:      {"A": 0.35, "B": 0.40, "C": 0.10, "D": 0.15},
            P_FCAI:    {"A": 0.20, "B": 0.20, "C": 0.15, "D": 0.45},
            P_DGCAI:   {"A": 0.20, "B": 0.20, "C": 0.15, "D": 0.45},
            P_FSHA:    {"A": 0.10, "B": 0.20, "C": 0.40, "D": 0.30},
            P_DGGUAN:  {"A": 0.10, "B": 0.20, "C": 0.40, "D": 0.30},
        }, _ABCD),
        evidence_note="比劫 = 兄弟；《三命通会·兄弟篇》",
        intro='问的是手足"数量 + 关系质感"两件事的合并印象。',
    ),
    Question(
        id="D1_Q5_birth_place_era",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你出生时家庭所处的环境是？（结合 era_windows_skeleton）",
        options=[
            QuestionOption("A", "大城市 + 中产以上家庭（含省会 / 直辖市 + 公务员 / 知识分子家庭也算）"),
            QuestionOption("B", "中小城镇 + 工人 / 普通职员家庭（含县城 + 双职工也算）"),
            QuestionOption("C", "农村 / 乡镇底层（含务农、外出打工家庭也算）"),
            QuestionOption("D", "跨地域 / 父母常迁移 / 无固定根（含军人 / 商人随迁、移民也算）"),
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
        intro='按你出生头几年的家庭真实生存环境选；不分"好坏"，只分"形态"。',
    ),
    Question(
        id="D1_Q6_grandparent_influence",
        dimension="ethnography_family",
        weight_class="hard_evidence",
        prompt="你童年（0-12 岁）受祖辈（爷奶 / 外公外婆）影响的程度？",
        options=[
            QuestionOption("A", "由祖辈带大、影响极深（含从小住爷奶 / 外公外婆家也算）"),
            QuestionOption("B", "经常见面、部分养育影响（含周末或寒暑假常去也算）"),
            QuestionOption("C", "偶尔见面、影响较小（含逢年过节才见、平时联系少也算）"),
            QuestionOption("D", "几乎没见过 / 早逝 / 失联（含出生前去世、家族断联也算）"),
        ],
        likelihood_table=_fill_uniform_for_missing({
            P_FYIN:   {"A": 0.50, "B": 0.30, "C": 0.15, "D": 0.05},
            P_DGYIN:  {"A": 0.45, "B": 0.30, "C": 0.15, "D": 0.10},
            P_FCAI:   {"A": 0.10, "B": 0.20, "C": 0.30, "D": 0.40},
            P_DGCAI:  {"A": 0.10, "B": 0.25, "C": 0.30, "D": 0.35},
        }, _ABCD),
        evidence_note="印星 = 长辈 / 祖荫；《滴天髓·六亲》",
        intro='问的是 0-12 岁里"被祖辈实际带 / 见 / 影响"的程度，不是有没有过。',
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
            QuestionOption("A", "强势主导型、你常跟随对方节奏（含被对方安排日程、决定方向也算）"),
            QuestionOption("B", "资源型 / 给予物质型、欣赏对方供给能力（含家境好、收入高也算）"),
            QuestionOption("C", "同辈对等型、势均力敌互不主导（含三观相近、平等沟通也算）"),
            QuestionOption("D", "欣赏才华、想推 ta '输出'的人（含愿意陪伴写作 / 表达 / 做作品也算）"),
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
        intro='把你历任 / 反复心动的人合在一起看一种"画像规律"，无关性别。',
    ),
    Question(
        id="D2_Q2_partner_proactive",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="在你过往的亲密关系建立时，多数时候是？",
        options=[
            QuestionOption("A", "你主动追求对方居多（含你先表白、你先暧昧也算）"),
            QuestionOption("B", "对方主动追求你居多（含对方追了很久、你被打动也算）"),
            QuestionOption("C", "双方差不多对等（含互有好感后顺势在一起也算）"),
            QuestionOption("D", "没有明确'建立'过程、关系自然滑入（含从朋友变情侣也算）"),
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
        intro='问的是关系"是怎么开始的"——大多数情况里谁更主动。',
    ),
    Question(
        id="D2_Q3_partner_economic_role",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="在你过往的亲密关系中，经济角色更常见是？",
        options=[
            QuestionOption("A", "你是主要经济输出方（含你出大头、对方少出或不出也算）"),
            QuestionOption("B", "对方是主要经济输出方（含被对方养、家用主要靠 ta 也算）"),
            QuestionOption("C", "平摊 / 各自独立财务（含 AA 制、共同账户但各管各也算）"),
            QuestionOption("D", "经济常是关系中的冲突源（含为钱吵架、消费观差大也算）"),
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
        intro='问的是经济上谁更承担更多——选你历任关系里更常见的那一种。',
    ),
    Question(
        id="D2_Q4_partner_emotional_dependence",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="在你过往的亲密关系中，情感依赖度更常见是？",
        options=[
            QuestionOption("A", "你更需要对方在场、对方相对独立（含分开就焦虑也算）"),
            QuestionOption("B", "对方更需要你在场、你相对独立（含 ta 黏你、你需要喘息也算）"),
            QuestionOption("C", "高度互相依赖（含两人粘在一起、生活高度交织也算）"),
            QuestionOption("D", "双方都偏独立 / 各自有空间的伴生（含分居 / 周末夫妻也算）"),
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
        intro='问的是情感能量"流向"——谁更需要谁、还是双方都很独立。',
    ),
    Question(
        id="D2_Q5_relationship_pattern",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="你过往关系的总体模式更接近哪个？",
        options=[
            QuestionOption("A", "长稳型、少而长（含一段持续多年、稳定不波动也算）"),
            QuestionOption("B", "流动型、多而短、常切换（含恋爱多次、每段不超 1-2 年也算）"),
            QuestionOption("C", "高强度爆发型、激烈短暂（含轰轰烈烈但很快烧完也算）"),
            QuestionOption("D", "低密度型、长期独处或淡如水（含长期单身、关系平淡也算）"),
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
        intro='问的是关系节奏：少而长 / 多而短 / 强而急 / 淡而稀，挑最贴近你的。',
    ),
    Question(
        id="D2_Q6_attraction_age_pattern",
        dimension="relationship",
        weight_class="soft_self_report",
        prompt="你反复被吸引的对象，年龄段更常见是？",
        options=[
            QuestionOption("A", "比你大较多（≥5 岁也算、含成熟稳重型）"),
            QuestionOption("B", "和你年纪相仿（差 ≤3 岁、含同龄同辈也算）"),
            QuestionOption("C", "比你小较多（≥5 岁也算、含偏弟弟妹妹型）"),
            QuestionOption("D", "没明显规律 / 年龄跨度很大（含从大很多到小很多都喜欢过也算）"),
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
        intro='问的是吸引规律里的"年龄轴"，不是有没有过更大或更小的对象。',
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
            QuestionOption("A", "怕冷、手脚常凉、爱穿厚（含冬天特别难熬、夏天也凉也算）"),
            QuestionOption("B", "怕热、爱出汗、爱冷饮（含夏天难熬、动一动就大汗也算）"),
            QuestionOption("C", "上热下寒（脸红脚冷、口干腿凉、含上半身热下半身凉也算）"),
            QuestionOption("D", "上寒下热 / 寒热不定（含咽痒脚心热、忽冷忽热也算）"),
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
        intro='按你长年身体感觉来选；偶发情况不算。',
    ),
    Question(
        id="D4_Q2_sleep",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你过去 3 年的整体睡眠状况是？",
        options=[
            QuestionOption("A", "入睡快、深睡足、醒后清爽（含基本不失眠、醒来有精神也算）"),
            QuestionOption("B", "多梦 / 浅眠 / 易醒、醒后疲乏（含半夜频繁醒、梦特别多也算）"),
            QuestionOption("C", "入睡难、但睡着后较深（含躺下半小时以上才能睡着、醒得早也算）"),
            QuestionOption("D", "睡眠时长足、但晨起仍困倦沉重（含睡 8h+ 还是没精神、起床困难也算）"),
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
        intro='按近 3 年的整体睡眠模式选，不是某次失眠。',
    ),
    Question(
        id="D4_Q3_organs",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你长期感觉的'薄弱'部位最接近？",
        options=[
            QuestionOption("A", "心 / 神系统（含心慌、易焦虑、口腔溃疡反复也算）"),
            QuestionOption("B", "脾胃系统（含消化弱、胃胀、易腹泻或便秘也算）"),
            QuestionOption("C", "肺 / 呼吸 / 皮肤系统（含鼻炎、过敏、皮肤干燥反复也算）"),
            QuestionOption("D", "肝肾 / 腰膝系统（含腰酸、膝软、精力不足、易累也算）"),
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
        intro='问的是哪个系统是你长期的"短板"——常出问题或恢复最慢的那一组。',
    ),
    Question(
        id="D4_Q4_body_type",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你成年后的体型最常见是？",
        options=[
            QuestionOption("A", "偏瘦、骨架小 / 不易长肉（含怎么吃都不胖、肌肉难长也算）"),
            QuestionOption("B", "中等匀称、体重稳定（含 BMI 正常、长年没大变化也算）"),
            QuestionOption("C", "偏壮 / 易长肉 / 易浮肿（含喝水都胖、容易水肿也算）"),
            QuestionOption("D", "起伏大 / 体重常波动（含一段瘦下来一段又胖回去也算）"),
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
        intro='按成年后大部分时间的身材状态选。',
    ),
    Question(
        id="D4_Q5_appetite",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你长期的食欲与口味偏好是？",
        options=[
            QuestionOption("A", "食量大、口重（含爱辣 / 咸 / 厚味、无辣不欢也算）"),
            QuestionOption("B", "食量小、清淡、吃多易胀（含一份小份就饱、爱清蒸白水也算）"),
            QuestionOption("C", "偏好甜食 / 碳水 / 温热饮食（含爱面食、爱热汤、爱奶茶也算）"),
            QuestionOption("D", "偏好生冷 / 凉饮 / 重水分（含爱冰饮、爱水果、爱凉拌也算）"),
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
        intro='问的是没人陪同时你自己默认会点的那种食物。',
    ),
    Question(
        id="D4_Q6_emotion_temperament",
        dimension="tcm_body",
        weight_class="hard_evidence",
        prompt="你的长期情志倾向最像哪一种？",
        options=[
            QuestionOption("A", "急躁 / 易上火 / 一点就炸（含脾气来得快去得也快也算）"),
            QuestionOption("B", "沉郁 / 易思虑 / 容易'想太多'（含反复琢磨、内耗也算）"),
            QuestionOption("C", "平和、起伏小（含情绪稳定、不易被外事带动也算）"),
            QuestionOption("D", "情绪起伏剧烈、时而高昂时而低落（含躁郁、情绪两极也算）"),
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
        intro='按"长期默认情绪基调"选，不是某段特殊时期。',
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
            QuestionOption("A", "主动迎击、靠自己硬扛（含死磕、不求人、自己扛下来也算）"),
            QuestionOption("B", "借外力 / 找资源 / 找支持系统（含求助朋友、找贵人也算）"),
            QuestionOption("C", "顺势而为 / 等局势变（含先观望、不急于动也算）"),
            QuestionOption("D", "切换轨道 / 换个赛道重来（含换工作、搬家、转行也算）"),
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
        intro='问的是"压力来了第一反应"——别想"应该怎样"，想"实际怎样"。',
    ),
    Question(
        id="D5_Q2_money_attitude",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="你对金钱的本能态度更接近？",
        options=[
            QuestionOption("A", "主动管理 / 重视积累 / 擅长保值（含记账、定投、稳健理财也算）"),
            QuestionOption("B", "善于撬动 / 借力生财 / 资源整合（含投资、生意、合伙也算）"),
            QuestionOption("C", "看淡 / 够用就好 / 不主动追求（含没欲望、月光也无所谓也算）"),
            QuestionOption("D", "起伏大 / 来去快 / 不擅积蓄（含赚得多花得也多、存不下也算）"),
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
        intro='问的是钱的"心理位置"——不是收入高低，是你跟钱的关系姿态。',
    ),
    Question(
        id="D5_Q3_authority_relation",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="你与权威 / 规则系统的关系更接近？",
        options=[
            QuestionOption("A", "自己定规则 / 不愿被管（含自由职业、独立工作、自己当老板也算）"),
            QuestionOption("B", "在规则内争上游 / 善用规则（含晋升、考证、卷绩效也算）"),
            QuestionOption("C", "服从规则 / 适应权威（含按部就班、不挑战上级也算）"),
            QuestionOption("D", "体制外 / 边缘化 / 与规则保持距离（含游离、不在主流轨道也算）"),
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
        intro='问的是面对"上级 / 公司 / 体制 / 规则"时你的本能位姿。',
    ),
    Question(
        id="D5_Q4_creative_outlet",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="你最自然的'创造性输出'方式是？",
        options=[
            QuestionOption("A", "表达 / 内容 / 表演型输出（含写作、视频、演讲、做作品也算）"),
            QuestionOption("B", "组织 / 系统建设 / 资源整合（含建团队、做平台、运营项目也算）"),
            QuestionOption("C", "学习 / 研究 / 知识沉淀（含读书、做研究、写笔记也算）"),
            QuestionOption("D", "没有明显输出冲动 / 不需要外显（含享受过程、不追产出也算）"),
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
        intro='问的是没有外部约束时，你最爱也最常做的"产出形态"。',
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
P_SGSC = "shang_guan_sheng_cai"        # 伤官生财（detector）
P_SGSC_G = "shang_guan_sheng_cai_geju" # 伤官生财格（geju metadata）
P_SGPY = "shang_guan_pei_yin_geju"     # 伤官佩印格
P_SYXS = "sha_yin_xiang_sheng_geju"    # 杀印相生（格局派）
P_QYXS = "qi_yin_xiang_sheng"          # 杀印相生（盲派 detector）
P_SSZS = "shi_shen_zhi_sha_geju"       # 食神制杀格
P_MHTM = "mu_huo_tong_ming"            # 木火通明
P_JBSQ = "jin_bai_shui_qing"           # 金白水清
P_RIREN = "riren_ge"                    # 日刃格

D6_QUESTIONS: List[Question] = [
    Question(
        id="D6_Q1_agency_style",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="在人生大方向上，你更接近哪一种推进模式？",
        options=[
            QuestionOption("A", "主动出击、找到目标就直接启动、靠强决断推进（含敢拍板、敢硬冲也算）"),
            QuestionOption("B", "有明确目标、但耐心经营按部就班攒资源（含长期主义、慢工出细活也算）"),
            QuestionOption("C", "随机应变、外部机会来了就跟、不太预设路径（含跟着风口走、灵活转向也算）"),
            QuestionOption("D", "被推着走、多数关键节点被环境关系决定（含被父母 / 公司 / 时代推动也算）"),
        ],
        likelihood_table=_fill_uniform_for_missing_v9({
            # 做功视角（刃/杀/伤官做功）→ A 高
            P_YRCC:    {"A": 0.55, "B": 0.15, "C": 0.20, "D": 0.10},
            P_YRJS:    {"A": 0.55, "B": 0.15, "C": 0.20, "D": 0.10},
            P_RIREN:   {"A": 0.50, "B": 0.20, "C": 0.20, "D": 0.10},
            P_SGSC:    {"A": 0.35, "B": 0.35, "C": 0.20, "D": 0.10},
            # 伤官族（geju 同质 + 佩印偏 B）
            P_SGSC_G:  {"A": 0.35, "B": 0.35, "C": 0.20, "D": 0.10},
            P_SGPY:    {"A": 0.25, "B": 0.45, "C": 0.20, "D": 0.10},
            # 杀印族（借外力 + 耐心 + 偶有外推）→ B/C 偏高
            P_SYXS:    {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            P_QYXS:    {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            # 食制杀（主动制衡，A 偏高弱于刃做功）
            P_SSZS:    {"A": 0.40, "B": 0.25, "C": 0.25, "D": 0.10},
            # 通明 / 白清（才华外显 + 顺势而为）→ C 主导
            P_MHTM:    {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
            P_JBSQ:    {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
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
        intro='问的是你做大事的"出力姿态"——不是结果好坏，是过程模式。',
    ),
    Question(
        id="D6_Q2_life_rhythm",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="回顾你人生到目前为止的整体节奏，更像哪一种？",
        options=[
            QuestionOption("A", "少数 1-3 次剧烈转折定调全局、其余时间在消化这些转折（含转学 / 跳槽 / 重大变故等也算）"),
            QuestionOption("B", "阶段性高光爆发 + 阶段性平稳期交替（含考过状元、出过作品、当过领导，但中间也有平淡期，主要算这种）"),
            QuestionOption("C", "循序渐进、缓慢稳步累积（含没有特别戏剧节点、长年线性上升也算）"),
            QuestionOption("D", "起伏不稳定、常被动应对外部变动（含被裁、被动调岗、家变也算）"),
        ],
        likelihood_table=_fill_uniform_for_missing_v9({
            # 做功视角 → A 高（剧烈转折 = 做功兑现）
            P_YRCC:    {"A": 0.55, "B": 0.25, "C": 0.10, "D": 0.10},
            P_YRJS:    {"A": 0.50, "B": 0.30, "C": 0.10, "D": 0.10},
            P_RIREN:   {"A": 0.45, "B": 0.30, "C": 0.15, "D": 0.10},
            P_SGSC:    {"A": 0.30, "B": 0.40, "C": 0.20, "D": 0.10},
            # 伤官族（geju 同质 + 佩印 B 主导）
            P_SGSC_G:  {"A": 0.30, "B": 0.40, "C": 0.20, "D": 0.10},
            P_SGPY:    {"A": 0.25, "B": 0.45, "C": 0.20, "D": 0.10},
            # 杀印族（B/C 偏高）
            P_SYXS:    {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            P_QYXS:    {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            # 食制杀
            P_SSZS:    {"A": 0.40, "B": 0.25, "C": 0.25, "D": 0.10},
            # 通明 / 白清 → C 主导
            P_MHTM:    {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
            P_JBSQ:    {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
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
        intro='回看至今，你的人生"波形"更像哪种——少数大转折？匀速？被动起伏？',
    ),
    Question(
        id="D6_Q3_gains_source",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="到目前为止，你最重要的几次「得失变化」更多来自？",
        options=[
            QuestionOption("A", "主要靠少数几个关键决策 / 一次定型的选择（含我拍了关键板、其余靠惯性也算）"),
            QuestionOption("B", "关键决策 + 平台与贵人机会并重、两者像握手一样发生（含我做了选择、平台 / 老板 / 时机也给了我机会，二者缺一不可，主要算这种）"),
            QuestionOption("C", "长期持续经营 + 复利积累、没有特别戏剧的节点（含十年磨一剑、慢慢攒出来也算）"),
            QuestionOption("D", "外部给定 / 周围人推动 / 时机到来就自然发生（含被父母安排、被朋友拉着走也算）"),
        ],
        likelihood_table=_fill_uniform_for_missing_v9({
            P_YRCC:    {"A": 0.60, "B": 0.20, "C": 0.10, "D": 0.10},
            P_YRJS:    {"A": 0.55, "B": 0.25, "C": 0.10, "D": 0.10},
            P_RIREN:   {"A": 0.50, "B": 0.30, "C": 0.10, "D": 0.10},
            P_SGSC:    {"A": 0.30, "B": 0.40, "C": 0.20, "D": 0.10},
            # 伤官族
            P_SGSC_G:  {"A": 0.30, "B": 0.40, "C": 0.20, "D": 0.10},
            P_SGPY:    {"A": 0.25, "B": 0.45, "C": 0.20, "D": 0.10},
            # 杀印族
            P_SYXS:    {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            P_QYXS:    {"A": 0.20, "B": 0.40, "C": 0.25, "D": 0.15},
            # 食制杀
            P_SSZS:    {"A": 0.40, "B": 0.25, "C": 0.25, "D": 0.10},
            # 通明 / 白清
            P_MHTM:    {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
            P_JBSQ:    {"A": 0.20, "B": 0.30, "C": 0.40, "D": 0.10},
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
        intro='想想到目前为止 2-3 次最重要的"得到 / 失去"，它们更多是决策来的还是日积月累来的？',
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
    # v9 · strict 默认开。新加题面只要带回命理术语 / 短选项 → 模块加载即 raise。
    _check_no_phase_leak(_q, strict=True)
    _check_plain_language(_q, strict=True)
    # v9.3 · 选项消歧铁律：每题至少 1 个 option label 带括号备注。
    # 模块加载时 strict=True，不让任何新题 regress 到"4 个干巴干巴的核心描述"。
    _check_option_disambiguation(_q, strict=True)


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
