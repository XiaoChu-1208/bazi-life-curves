"""Core Bazi data model and helpers.

身份盲化：本模块及所有 scripts/ 下的脚本都不接受、不存储、不输出
任何身份信息（姓名 / 职业 / 关系 / 经历）。仅处理干支 / 性别 / 出生年。

Public API:
    parse_pillars(s) -> List[Pillar]
    pillars_from_gregorian(date_str, gender) -> Tuple[List[Pillar], int]
    GAN, ZHI, GAN_WUXING, ZHI_WUXING, ZHI_HIDDEN_GAN
    SHISHEN_TABLE, calc_shishen, day_master_strength
    climate_profile  -- 燥湿独立维度（lessons learned 2026-04 后新增）
    select_yongshen, day_year_to_pillar
    get_dayun_sequence
    compute_qiyun_age_from_gregorian
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
ZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

GAN_WUXING = {
    "甲": "木", "乙": "木",
    "丙": "火", "丁": "火",
    "戊": "土", "己": "土",
    "庚": "金", "辛": "金",
    "壬": "水", "癸": "水",
}
GAN_YIN_YANG = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(GAN)}

ZHI_WUXING = {
    "寅": "木", "卯": "木",
    "巳": "火", "午": "火",
    "辰": "土", "戌": "土", "丑": "土", "未": "土",
    "申": "金", "酉": "金",
    "子": "水", "亥": "水",
}
ZHI_YIN_YANG = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(ZHI)}

ZHI_HIDDEN_GAN = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "庚", "戊"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

WUXING_ORDER = ["木", "火", "土", "金", "水"]
WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}  # X 生 SHENG[X]
WUXING_KE = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}     # X 克 KE[X]
WUXING_BEI_SHENG = {v: k for k, v in WUXING_SHENG.items()}                  # X 被 BEI_SHENG[X] 所生

ZHI_CHONG = {
    "子": "午", "午": "子",
    "丑": "未", "未": "丑",
    "寅": "申", "申": "寅",
    "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰",
    "巳": "亥", "亥": "巳",
}
ZHI_CHUAN = {
    "子": "未", "未": "子",
    "丑": "午", "午": "丑",
    "寅": "巳", "巳": "寅",
    "卯": "辰", "辰": "卯",
    "申": "亥", "亥": "申",
    "酉": "戌", "戌": "酉",
}
ZHI_LIUHE = {
    "子": "丑", "丑": "子",
    "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯",
    "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳",
    "午": "未", "未": "午",
}
SANHE_GROUPS = [
    (["申", "子", "辰"], "水"),
    (["亥", "卯", "未"], "木"),
    (["寅", "午", "戌"], "火"),
    (["巳", "酉", "丑"], "金"),
]
SANHUI_GROUPS = [
    (["亥", "子", "丑"], "水"),
    (["寅", "卯", "辰"], "木"),
    (["巳", "午", "未"], "火"),
    (["申", "酉", "戌"], "金"),
]

# 库（四墓）本气藏
KU_BENQI = {"辰": "癸", "戌": "丁", "丑": "辛", "未": "乙"}


@dataclass
class Pillar:
    gan: str
    zhi: str

    def __str__(self):
        return f"{self.gan}{self.zhi}"

    @classmethod
    def parse(cls, s: str) -> "Pillar":
        s = s.strip()
        if len(s) != 2:
            raise ValueError(f"Invalid pillar: {s!r}, expect 2 chars like 庚午")
        if s[0] not in GAN or s[1] not in ZHI:
            raise ValueError(f"Invalid pillar: {s!r}")
        return cls(gan=s[0], zhi=s[1])


def parse_pillars(s: str) -> List[Pillar]:
    """Parse '庚午 辛巳 壬子 丁未' into [Pillar, Pillar, Pillar, Pillar] (year, month, day, hour)."""
    parts = s.replace(",", " ").split()
    if len(parts) != 4:
        raise ValueError(f"Need 4 pillars (year/month/day/hour), got {len(parts)}: {s!r}")
    return [Pillar.parse(p) for p in parts]


def pillars_from_gregorian(date_str: str, gender: str) -> Tuple[List[Pillar], int]:
    """Convert Gregorian date '1990-05-12 14:30' → 4 pillars + birth year.

    Falls back to a deterministic stub if lunar-python is not installed; the stub
    is good enough for downstream pipeline tests but should not be used for real
    chart calculation.
    """
    try:
        from lunar_python import Solar
    except ImportError as e:
        raise ImportError(
            "lunar-python is required for gregorian conversion. "
            "Install via: pip install lunar-python"
        ) from e

    # Parse date
    if " " in date_str:
        d, t = date_str.split(" ", 1)
    else:
        d, t = date_str, "12:00"
    y, mo, da = [int(x) for x in d.split("-")]
    hh, mm = [int(x) for x in t.split(":")]

    solar = Solar.fromYmdHms(y, mo, da, hh, mm, 0)
    lunar = solar.getLunar()
    eight = lunar.getEightChar()
    pillars = [
        Pillar(eight.getYearGan(), eight.getYearZhi()),
        Pillar(eight.getMonthGan(), eight.getMonthZhi()),
        Pillar(eight.getDayGan(), eight.getDayZhi()),
        Pillar(eight.getTimeGan(), eight.getTimeZhi()),
    ]
    return pillars, y


# --- 十神 ---

def calc_shishen(day_gan: str, other_gan: str) -> str:
    """Compute 十神 of `other_gan` relative to `day_gan`."""
    d_wx = GAN_WUXING[day_gan]
    o_wx = GAN_WUXING[other_gan]
    d_yy = GAN_YIN_YANG[day_gan]
    o_yy = GAN_YIN_YANG[other_gan]
    same_yy = d_yy == o_yy
    if d_wx == o_wx:
        return "比肩" if same_yy else "劫财"
    if WUXING_SHENG[d_wx] == o_wx:
        return "食神" if same_yy else "伤官"
    if WUXING_KE[d_wx] == o_wx:
        return "偏财" if same_yy else "正财"
    if WUXING_KE[o_wx] == d_wx:
        return "七杀" if same_yy else "正官"
    if WUXING_SHENG[o_wx] == d_wx:
        return "偏印" if same_yy else "正印"
    return "?"


def calc_zhi_shishen(day_gan: str, zhi: str) -> str:
    """十神 of the main hidden gan in zhi."""
    main_gan = ZHI_HIDDEN_GAN[zhi][0]
    return calc_shishen(day_gan, main_gan)


# --- 通根度（v9 新增 · 修"印根足够却被误判为弃命从财"边界 case） ---
#
# 设计动机（lessons learned 2026-04 后第二轮回顾）：
# 旧 day_master_strength 把"印根"和"比劫根"合并到 sheng/same 加权得分里，
# 导致 floating_dms 判定无法区分"完全无根"vs"有印无比劫"——后者其实是杀印
# 相生格的典型基础，强行按从格走会全盘错。
#
# v9 把通根度独立出来，作为一个公开的、细粒度的 day_master 子结构：
#   bijie_root = 同五行藏干贡献（比肩/劫财根）
#   yin_root   = 生我五行藏干贡献（正印/偏印根）
# 三档藏干权重：本气 1.0 / 中气 0.5 / 余气 0.2
#
# 五档 label 阈值经 12 case 校准（diagnosis_pitfalls.md §13、§14）：
#   < 0.30  → 无根    （真从格的硬门槛）
#   < 0.70  → 微根    （假从格 / 仍按弱身扶身）
#   < 1.50  → 弱根    （格局派优先 / 慎用从格）
#   < 2.50  → 中根    （扶抑派标准）
#   >= 2.50 → 强根    （日主夯实 / 抑为主）
ROOT_TIER_WEIGHT = {0: 1.0, 1: 0.5, 2: 0.2}  # 本气 / 中气 / 余气


def compute_dayuan_root_strength(stem: str, branches: List[str]) -> Dict:
    """Compute Day Master grounding via three-tier weighted scan over branches.

    Args:
        stem: 日主天干（如 "己"）
        branches: 4 个地支字符（年/月/日/时）

    Returns:
        {
            "stem": str, "stem_wx": str,
            "bijie_root": float, "yin_root": float, "total_root": float,
            "label": "无根"|"微根"|"弱根"|"中根"|"强根",
            "details": List[Dict],
        }

    See references/methodology.md §通根度 for theory.
    """
    if stem not in GAN_WUXING:
        raise ValueError(f"unknown stem: {stem}")

    d_wx = GAN_WUXING[stem]
    bijie = 0.0
    yin = 0.0
    details: List[Dict] = []

    for br in branches:
        if br not in ZHI_HIDDEN_GAN:
            continue
        hidden = ZHI_HIDDEN_GAN[br]
        for tier_idx, hg in enumerate(hidden):
            tier_w = ROOT_TIER_WEIGHT.get(tier_idx, 0.0)
            if tier_w == 0.0:
                continue
            hg_wx = GAN_WUXING[hg]
            kind = None
            if hg_wx == d_wx:
                bijie += tier_w
                kind = "比劫"
            elif WUXING_SHENG.get(hg_wx) == d_wx:
                yin += tier_w
                kind = "印"
            if kind:
                details.append({
                    "branch": br,
                    "hidden": hg,
                    "tier": ["本", "中", "余"][tier_idx],
                    "weight": tier_w,
                    "kind": kind,
                })

    total = bijie + yin
    if total < 0.30:
        label = "无根"
    elif total < 0.70:
        label = "微根"
    elif total < 1.50:
        label = "弱根"
    elif total < 2.50:
        label = "中根"
    else:
        label = "强根"

    return {
        "stem": stem,
        "stem_wx": d_wx,
        "bijie_root": round(bijie, 3),
        "yin_root": round(yin, 3),
        "total_root": round(total, 3),
        "label": label,
        "details": details,
    }


# --- 日主强弱 ---

def day_master_strength(pillars: List[Pillar]) -> Dict[str, float]:
    """Estimate day master strength by counting same-element / supporting-element
    presence among the 8 chars + main hidden gans of zhi.

    Returns dict with: score (-100..100, positive=strong), label (强/中和/弱)
    and same/sheng/ke/xie counts.
    """
    day_gan = pillars[2].gan
    d_wx = GAN_WUXING[day_gan]

    same = 0  # 比劫
    sheng = 0  # 印
    xie = 0  # 食伤
    ke = 0  # 财
    kewo = 0  # 官杀

    def _count(wx: str, weight: float):
        nonlocal same, sheng, xie, ke, kewo
        if wx == d_wx:
            same += weight
        elif WUXING_SHENG[wx] == d_wx:
            sheng += weight
        elif WUXING_SHENG[d_wx] == wx:
            xie += weight
        elif WUXING_KE[d_wx] == wx:
            ke += weight
        elif WUXING_KE[wx] == d_wx:
            kewo += weight

    # 4 天干（日干本身不算）
    for i, p in enumerate(pillars):
        if i == 2:
            continue
        _count(GAN_WUXING[p.gan], 1.0)

    # 4 地支藏干（月支位置加成 × 1.5；藏干内部本/中/余 = 1.0/0.5/0.2）
    for i, p in enumerate(pillars):
        pos_weight = 1.5 if i == 1 else 1.0
        hidden = ZHI_HIDDEN_GAN[p.zhi]
        for tier_idx, sub in enumerate(hidden):
            tier_w = ROOT_TIER_WEIGHT.get(tier_idx, 0.0) * 2.0  # 维持旧 *2 总盘量级
            if tier_w == 0.0:
                continue
            _count(GAN_WUXING[sub], pos_weight * tier_w)

    # 月令是否当令（最关键）
    month_zhi = pillars[1].zhi
    in_season = (GAN_WUXING[ZHI_HIDDEN_GAN[month_zhi][0]] == d_wx) or (
        WUXING_SHENG[GAN_WUXING[ZHI_HIDDEN_GAN[month_zhi][0]]] == d_wx
    )
    season_bonus = 15 if in_season else -10

    support = same + sheng
    consume = xie + ke + kewo
    score = (support - consume) * 5 + season_bonus
    score = max(-100, min(100, score))

    if score > 15:
        label = "强"
    elif score < -15:
        label = "弱"
    else:
        label = "中和"

    # v9: 通根度独立子结构
    branches = [p.zhi for p in pillars]
    root_strength = compute_dayuan_root_strength(day_gan, branches)

    return {
        "score": round(score, 2),
        "label": label,
        "in_season": in_season,
        "same": round(same, 2),
        "sheng": round(sheng, 2),
        "xie": round(xie, 2),
        "ke": round(ke, 2),
        "kewo": round(kewo, 2),
        "root_strength": root_strength,
    }


# --- 燥湿独立画像（lessons learned 2026-04 后新增） ---
#
# 关键洞察（来自一类"上燥下寒"边界 case 的失败经验）：
# 月令决定"季节寒暖"，但**天干能量场**才决定"体感和性格的明面表现"。
# 例如干头三土火金全燥 + 月支水 → 实际是燥实命；
# 旧 select_yongshen 只看月令水 + 身弱 → 错判用神为火土。
# 同样身弱：燥实命用神 = 水（润降）；寒湿命用神 = 火（暖局）—— 完全相反。
# 所以"燥湿"必须是独立于"身强弱"的维度。

DRY_GAN = {"丙", "丁", "戊", "己", "庚", "辛"}
WET_GAN = {"壬", "癸"}
DRY_ZHI_HEAVY = {"巳", "午", "未", "戌"}
WET_ZHI_HEAVY = {"亥", "子", "丑", "辰"}


def climate_profile(pillars: List[Pillar]) -> Dict:
    """命局燥湿独立画像（不依赖身强弱）。

    Returns:
      {
        "干头分": float,
        "地支分": float,
        "总分": float,
        "label": "燥实"|"偏燥"|"中和"|"偏湿"|"寒湿",
        "干头主导": bool,
        "details": {...}
      }
    """
    g_score = 0.0
    g_detail: List[str] = []
    for i, p in enumerate(pillars):
        w = 2.0 if i in (1, 2) else 1.5
        if p.gan in DRY_GAN:
            pt = 2 if p.gan in {"丙", "丁"} else 1
            g_score += pt * w
            g_detail.append(f"{p.gan}+{pt * w:.1f}")
        elif p.gan in WET_GAN:
            g_score -= 2 * w
            g_detail.append(f"{p.gan}-{2 * w:.1f}")

    z_score = 0.0
    z_detail: List[str] = []
    for i, p in enumerate(pillars):
        w = 2.0 if i == 1 else 1.5
        if p.zhi in DRY_ZHI_HEAVY:
            pt = 2 if p.zhi in {"午", "未"} else 1
            z_score += pt * w
            z_detail.append(f"{p.zhi}+{pt * w:.1f}")
        elif p.zhi in WET_ZHI_HEAVY:
            pt = 2 if p.zhi in {"子", "丑"} else 1
            z_score -= pt * w
            z_detail.append(f"{p.zhi}-{pt * w:.1f}")

    total = round(0.6 * g_score + 0.4 * z_score, 1)
    # 阈值参考：干头分单边强烈（≥6 或 ≤-6）也算极端，即使总分被对冲
    extreme_dry = g_score >= 6 and z_score < -2
    extreme_wet = g_score <= -6 and z_score > 2

    if extreme_dry:
        label = "外燥内湿"           # 干头极燥 + 地支湿
    elif extreme_wet:
        label = "外湿内燥"           # 干头极湿 + 地支燥
    elif total >= 4:
        label = "燥实"
    elif total >= 1.5:
        label = "偏燥"
    elif total > -1.5:
        label = "中和"
    elif total > -4:
        label = "偏湿"
    else:
        label = "寒湿"

    gan_dom = abs(g_score) > abs(z_score) * 1.3

    if label == "外燥内湿":
        interp = f"干头极燥（{g_score:+.1f}）+ 地支湿（{z_score:+.1f}）→ 「体感常热怕烫 + 财源 / 智识在水里」 → 用神水（让地支水透干，制干头燥）"
    elif label == "外湿内燥":
        interp = f"干头极湿（{g_score:+.1f}）+ 地支燥（{z_score:+.1f}）→ 「体感偏寒怕冷 + 内里有暗火 / 急躁」 → 用神火（暖干头，地支底火接应）"
    elif label in ("燥实", "偏燥") and z_score < -2:
        interp = f"干头{label}（{g_score:+.1f}）但地支湿（{z_score:+.1f}）→ 燥湿对冲，仍以干头主导"
    elif label in ("寒湿", "偏湿") and g_score > 2:
        interp = f"干头燥（{g_score:+.1f}）但地支寒湿（{z_score:+.1f}）→ 寒湿对冲"
    elif label == "中和":
        interp = "燥湿均衡，按身强弱选用神"
    elif gan_dom:
        interp = f"{label} · 干头主导 → 体感和性格按{label}走，是真{label}"
    else:
        interp = f"{label} · 地支主导 → 隐性{label}，体感不一定明显"

    return {
        "干头分": round(g_score, 1),
        "地支分": round(z_score, 1),
        "总分": total,
        "label": label,
        "干头主导": gan_dom,
        "details": {
            "干头": "+".join(g_detail) or "（无显著燥湿干）",
            "地支": "+".join(z_detail) or "（无显著燥湿支）",
            "解读": interp,
        },
    }


# --- 用神选取（v2：燥湿为先，强弱为次） ---

def select_yongshen(pillars: List[Pillar], strength: Dict) -> Dict[str, str]:
    """Pick yongshen / xishen / jishen — climate-first, strength-second.

    [改进 v2，2026-04，from 上燥下寒边界 case 失败教训]：
    - **燥实命**（climate.label = 燥实，总分 ≥ 4）→ 用神 = 水（润降），
      不论身强弱。同样身弱，燥实命用神是水；寒湿命才是火 —— 完全相反。
    - **寒湿命**（总分 ≤ -4）→ 用神 = 火（暖局），不论身强弱。
    - **偏燥 / 偏湿**：燥湿方向上微调（影响 jishen），主选用神仍按身强弱走。
    - **中和**：原 (强→克泄耗、弱→生扶、中和→调候) 规则。

    典型反例：日主己土 + 月令子水 + 干头多火多燥土
    旧规则 → 月令子水 + 身弱 → 用神 = 火土（错）
    新规则 → 干头全燥 → 燥实命 → 用神 = 水（对，且匹配"从小怕热"体感）
    """
    climate = climate_profile(pillars)

    day_gan = pillars[2].gan
    d_wx = GAN_WUXING[day_gan]
    label = strength["label"]
    month_zhi = pillars[1].zhi
    season = {
        "寅": "春", "卯": "春", "辰": "春",
        "巳": "夏", "午": "夏", "未": "夏",
        "申": "秋", "酉": "秋", "戌": "秋",
        "亥": "冬", "子": "冬", "丑": "冬",
    }[month_zhi]

    # ① 燥湿优先覆盖（极燥 / 极湿 / 外燥内湿 / 外湿内燥 → 不论身强弱，调候为先）
    climate_override = None
    if climate["label"] == "燥实":
        climate_override = ("水", "燥实命 → 用神水（润降），覆盖身强弱规则")
    elif climate["label"] == "寒湿":
        climate_override = ("火", "寒湿命 → 用神火（暖局），覆盖身强弱规则")
    elif climate["label"] == "外燥内湿":
        climate_override = ("水", "外燥内湿 → 用神水（让地支水透干，制干头燥），覆盖身强弱规则")
    elif climate["label"] == "外湿内燥":
        climate_override = ("火", "外湿内燥 → 用神火（让地支火透干，暖干头），覆盖身强弱规则")

    if climate_override:
        yongshen, override_reason = climate_override
        xishen = WUXING_BEI_SHENG[yongshen]  # 生用神者为喜神（如 yongshen=水 → xishen=金）
        jishen_map = {"水": "火", "火": "水"}
        jishen = jishen_map[yongshen]
        tongguan = _find_tongguan(pillars)
        return {
            "yongshen": yongshen,
            "xishen": xishen,
            "jishen": jishen,
            "tongguan": tongguan,
            "season": season,
            "day_master_wuxing": d_wx,
            "climate": climate,
            "_climate_override": override_reason,
        }

    # ② 偏燥 / 偏湿：影响 jishen 倾向（不影响 yongshen 主选）
    if label == "强":
        # 用神：克我（官杀） / 我克（财） / 我生（食伤）中较缺者
        candidates = []
        for wx in WUXING_ORDER:
            if WUXING_KE[wx] == d_wx:  # 官杀
                candidates.append((wx, "官杀"))
            elif WUXING_KE[d_wx] == wx:  # 财
                candidates.append((wx, "财"))
            elif WUXING_SHENG[d_wx] == wx:  # 食伤
                candidates.append((wx, "食伤"))
        # Heuristic: 选与原局现存五行最少的那个
        existing = _wuxing_count(pillars)
        candidates.sort(key=lambda x: existing.get(x[0], 0))
        yongshen, _ = candidates[0]
        xishen = WUXING_BEI_SHENG.get(yongshen, yongshen)  # 生用神者为喜神
        # 忌神 = 生扶日主者
        for wx in WUXING_ORDER:
            if wx == d_wx or WUXING_SHENG[wx] == d_wx:
                jishen = wx
                break
    elif label == "弱":
        # 用神：印（生我） / 比（同我）中较缺者
        candidates = []
        for wx in WUXING_ORDER:
            if WUXING_SHENG[wx] == d_wx:
                candidates.append((wx, "印"))
            elif wx == d_wx:
                candidates.append((wx, "比"))
        existing = _wuxing_count(pillars)
        candidates.sort(key=lambda x: existing.get(x[0], 0))
        yongshen, _ = candidates[0]
        xishen = d_wx  # 同我也喜
        # 忌神 = 克泄耗日主者
        for wx in WUXING_ORDER:
            if WUXING_KE[wx] == d_wx:
                jishen = wx
                break
    else:
        # 中和 → 调候
        climate_map = {"春": "金", "夏": "水", "秋": "木", "冬": "火"}
        yongshen = climate_map[season]
        xishen = WUXING_BEI_SHENG[yongshen]
        # 忌神 = 加剧失衡的
        anti_climate = {"春": "土", "夏": "火", "秋": "金", "冬": "水"}
        jishen = anti_climate[season]

    tongguan = _find_tongguan(pillars)

    # ③ 偏燥 / 偏湿微调 jishen
    if climate["label"] == "偏燥" and jishen in ("木", "土", "金"):
        jishen = "火"  # 偏燥命，火再多就过头
    elif climate["label"] == "偏湿" and jishen in ("木", "土", "金"):
        jishen = "水"  # 偏湿命，水再多就过头

    return {
        "yongshen": yongshen,
        "xishen": xishen,
        "jishen": jishen,
        "tongguan": tongguan,
        "season": season,
        "day_master_wuxing": d_wx,
        "climate": climate,
    }


# ============================================================================
# Phase Inversion Detection (P1-7, v7 新增)
# ----------------------------------------------------------------------------
# 当默认算法对一份命局的"相位"判定方向反了，R0/R1 命中率会很低。
# 当前 Skill 只会归因为"八字错"，漏掉"算法读反"这种可能。
# 这一组 detect 函数枚举 4 类常见相位反向假设：
#   P1 · 日主虚浮（弃命从势：从财 / 从杀 / 从儿 / 从印）
#   P2 · 旺神得令反主事
#   P3 · 调候反向（外燥内湿 / 上燥下寒）
#   P4 · 假从 / 真从边界
# 每个 detect 输出 {triggered, score, suggested_phase, evidence}。
# 详见 references/phase_inversion_protocol.md
# ============================================================================


def _shishen_to_phase(shishen: str) -> str:
    """十神 → 反演相位 ID（用于 from_god 类）。"""
    if shishen in ("正财", "偏财"):
        return "floating_dms_to_cong_cai"
    if shishen in ("正官", "七杀"):
        return "floating_dms_to_cong_sha"
    if shishen in ("食神", "伤官"):
        return "floating_dms_to_cong_er"
    if shishen in ("正印", "偏印"):
        return "floating_dms_to_cong_yin"
    return "day_master_dominant"


def _dominating_wuxing(pillars: List[Pillar], day_wx: str) -> Tuple[Optional[str], float]:
    """找全局最强的"非日主同党"五行 + 其总分。"""
    cnt = _wuxing_count(pillars)
    candidates = [(wx, score) for wx, score in cnt.items() if wx != day_wx]
    candidates.sort(key=lambda x: -x[1])
    if not candidates:
        return None, 0.0
    return candidates[0][0], candidates[0][1]


def _bijie_grounded(pillars: List[Pillar], day_wx: str) -> bool:
    """比劫是否通根（地支主气是否有同党）。
    通根 = 至少一个地支的主气与日主同五行。
    """
    return any(
        GAN_WUXING[ZHI_HIDDEN_GAN[p.zhi][0]] == day_wx
        for p in pillars
    )


def _yin_grounded(pillars: List[Pillar], day_wx: str) -> bool:
    """印星是否通根（天干有印 + 地支主气也有"生我"五行）。
    印通根 = 天干有印 AND 至少一个地支主气是"生我"五行。
    """
    has_yin_in_gan = any(
        WUXING_SHENG.get(GAN_WUXING[p.gan]) == day_wx
        for i, p in enumerate(pillars) if i != 2
    )
    if not has_yin_in_gan:
        return False
    yin_grounded_in_zhi = any(
        WUXING_SHENG.get(GAN_WUXING[ZHI_HIDDEN_GAN[p.zhi][0]]) == day_wx
        for p in pillars
    )
    return yin_grounded_in_zhi


def _shishen_class_from_wuxing(day_wx: str, target_wx: str) -> str:
    """target_wx 在日主的视角是什么十神类。"""
    if target_wx == day_wx:
        return "比肩"
    if WUXING_KE.get(day_wx) == target_wx:
        return "正财"
    if WUXING_KE.get(target_wx) == day_wx:
        return "七杀"
    if WUXING_SHENG.get(day_wx) == target_wx:
        return "食神"
    if WUXING_SHENG.get(target_wx) == day_wx:
        return "正印"
    return "比肩"


def detect_floating_day_master(pillars: List[Pillar], strength: Dict) -> Dict:
    """P1 · 日主虚浮反演检测（v7.1 重写：看「比劫 / 印 是否通根」而不是点数总和）。

    学理：日主"虚浮" ≠ 五行点数低，而是「比劫不通根」+「印星无地支根」。
    参考《滴天髓·从象》、《子平真诠·从化篇》。

    满足 4 / 5 → 触发，建议 phase = floating_dms_to_cong_<旺神所属十神>
    """
    day_gan = pillars[2].gan
    day_wx = GAN_WUXING[day_gan]
    same = strength.get("same", 0)
    sheng = strength.get("sheng", 0)
    support = same + sheng

    month_zhi = pillars[1].zhi
    month_main_wx = GAN_WUXING[ZHI_HIDDEN_GAN[month_zhi][0]]
    month_supports = (month_main_wx == day_wx) or (WUXING_SHENG[month_main_wx] == day_wx)

    day_zhi = pillars[2].zhi
    day_zhi_main_wx = GAN_WUXING[ZHI_HIDDEN_GAN[day_zhi][0]]
    day_zhi_supports = (day_zhi_main_wx == day_wx) or (WUXING_SHENG[day_zhi_main_wx] == day_wx)

    bijie_grounded = _bijie_grounded(pillars, day_wx)
    yin_grounded = _yin_grounded(pillars, day_wx)

    dominating_wx, dominating_score = _dominating_wuxing(pillars, day_wx)

    # v7.1 五条件改为：
    cond_1_bijie_floating = (not bijie_grounded) and same <= 3.0    # 比劫不通根（核心）
    cond_2_month_against = not month_supports                        # 月令克泄
    cond_3_day_zhi_against = not day_zhi_supports                    # 日支非同党
    cond_4_yin_not_grounded = not yin_grounded                       # 印不通根（弱化版"无印"）
    cond_5_dominating = dominating_score >= 8                        # 旺神成势（阈值由 12 → 8）

    score = sum([cond_1_bijie_floating, cond_2_month_against, cond_3_day_zhi_against,
                 cond_4_yin_not_grounded, cond_5_dominating])
    # 触发条件：满足 4/5 → 触发；或者 cond_1 + cond_2 + cond_5 三大核心都满足 → 触发（即使有印通根）
    core_three = cond_1_bijie_floating and cond_2_month_against and cond_5_dominating
    triggered = score >= 4 or core_three

    suggested_phase = "day_master_dominant"
    suggested_label = ""
    if triggered and dominating_wx:
        shishen_class = _shishen_class_from_wuxing(day_wx, dominating_wx)
        suggested_phase = _shishen_to_phase(shishen_class)
        suggested_label = {
            "floating_dms_to_cong_cai": "弃命从财（日主虚浮 → 财星主事）",
            "floating_dms_to_cong_sha": "弃命从杀（日主虚浮 → 官杀主事）",
            "floating_dms_to_cong_er": "弃命从儿（日主虚浮 → 食伤主事）",
            "floating_dms_to_cong_yin": "弃命从印（日主虚浮 → 印星主事）",
        }.get(suggested_phase, "弃命从势")

    return {
        "phase_id": "P1_floating_day_master",
        "triggered": triggered,
        "score": f"{score}/5" + ("（核心三条满足触发）" if core_three and score < 4 else ""),
        "suggested_phase": suggested_phase,
        "suggested_label": suggested_label,
        "evidence": {
            "day_master_support（same+sheng）": round(support, 2),
            "bijie_grounded": bijie_grounded,
            "yin_grounded": yin_grounded,
            "month_supports_dms": month_supports,
            "day_zhi_supports_dms": day_zhi_supports,
            "dominating_wuxing": dominating_wx,
            "dominating_score": round(dominating_score, 2),
            "conditions_met": {
                "1_比劫不通根 (核心)": cond_1_bijie_floating,
                "2_月令克泄": cond_2_month_against,
                "3_日支非同党": cond_3_day_zhi_against,
                "4_印不通根 (允许有透干印)": cond_4_yin_not_grounded,
                "5_旺神成势 (≥8)": cond_5_dominating,
            },
        },
    }


def detect_dominating_god(pillars: List[Pillar], strength: Dict) -> Dict:
    """P2 · 旺神得令反主事检测。

    旺神 ≠ 日主同党，月令权重 ≥ 65% + 透干 + 比日主同党 2 倍以上 → 触发
    """
    day_gan = pillars[2].gan
    day_wx = GAN_WUXING[day_gan]

    month_zhi = pillars[1].zhi
    month_hidden = ZHI_HIDDEN_GAN[month_zhi]
    month_total = sum(1.0 if i == 0 else 0.3 for i in range(len(month_hidden)))
    non_dms_in_month = sum(
        (1.0 if i == 0 else 0.3)
        for i, hg in enumerate(month_hidden)
        if GAN_WUXING[hg] != day_wx and WUXING_SHENG[GAN_WUXING[hg]] != day_wx
    )
    month_dominated_by_non_dms = (non_dms_in_month / month_total) >= 0.65 if month_total > 0 else False

    dominating_wx, dominating_score = _dominating_wuxing(pillars, day_wx)
    same_score = strength.get("same", 0) + strength.get("sheng", 0)

    transparent_in_gan = False
    if dominating_wx:
        transparent_in_gan = any(
            GAN_WUXING[p.gan] == dominating_wx
            for i, p in enumerate(pillars) if i != 2
        )

    ratio_ok = (dominating_score / max(same_score, 0.1)) >= 2.0

    cond_1_month = month_dominated_by_non_dms
    cond_2_transparent = transparent_in_gan
    cond_3_ratio = ratio_ok
    cond_4_strong = dominating_score >= 10

    score = sum([cond_1_month, cond_2_transparent, cond_3_ratio, cond_4_strong])
    triggered = score >= 3

    suggested_phase = "day_master_dominant"
    suggested_label = ""
    if triggered and dominating_wx:
        if WUXING_KE[day_wx] == dominating_wx:
            suggested_phase = "dominating_god_cai_zuo_zhu"
            suggested_label = f"旺神得令·财星({dominating_wx})主事 · 日主借力"
        elif WUXING_KE[dominating_wx] == day_wx:
            suggested_phase = "dominating_god_guan_zuo_zhu"
            suggested_label = f"旺神得令·官杀({dominating_wx})主事 · 日主受制"
        elif WUXING_SHENG[day_wx] == dominating_wx:
            suggested_phase = "dominating_god_shishang_zuo_zhu"
            suggested_label = f"旺神得令·食伤({dominating_wx})主事 · 日主泄秀"
        elif WUXING_SHENG[dominating_wx] == day_wx:
            suggested_phase = "dominating_god_yin_zuo_zhu"
            suggested_label = f"旺神得令·印({dominating_wx})主事 · 日主被庇护"

    return {
        "phase_id": "P2_dominating_god",
        "triggered": triggered,
        "score": f"{score}/4",
        "suggested_phase": suggested_phase,
        "suggested_label": suggested_label,
        "evidence": {
            "dominating_wuxing": dominating_wx,
            "dominating_score": round(dominating_score, 2),
            "day_master_support": round(same_score, 2),
            "ratio (dominating/dms)": round(dominating_score / max(same_score, 0.1), 2),
            "month_dominated_by_non_dms": month_dominated_by_non_dms,
            "transparent_in_gan": transparent_in_gan,
            "conditions_met": {
                "1_月令旺神主导 (≥65%)": cond_1_month,
                "2_天干透出": cond_2_transparent,
                "3_压日主比 ≥ 2": cond_3_ratio,
                "4_旺神 ≥ 10": cond_4_strong,
            },
        },
    }


def detect_climate_inversion(pillars: List[Pillar], climate: Dict) -> Dict:
    """P3 · 调候反向检测（外燥内湿 / 外湿内燥 / 上燥下寒等）。

    climate.label ∈ 极端对冲类 → 触发
    """
    label = climate.get("label", "")
    g_score = climate.get("干头分", 0)
    z_score = climate.get("地支分", 0)

    cond_1_inverted_label = label in ("外燥内湿", "外湿内燥")
    cond_2_signs_opposite = (g_score > 0 and z_score < 0) or (g_score < 0 and z_score > 0)
    cond_3_both_strong = abs(g_score) >= 4 and abs(z_score) >= 4

    score = sum([cond_1_inverted_label, cond_2_signs_opposite, cond_3_both_strong])
    triggered = score >= 2

    suggested_phase = "day_master_dominant"
    suggested_label = ""
    if triggered:
        if g_score > 0 and z_score < 0:
            suggested_phase = "climate_inversion_dry_top"
            suggested_label = "调候反向·上燥下寒（用神锁水：让地支水透干，制干头燥）"
        elif g_score < 0 and z_score > 0:
            suggested_phase = "climate_inversion_wet_top"
            suggested_label = "调候反向·上湿下燥（用神锁火：让地支火透干，暖干头）"

    return {
        "phase_id": "P3_climate_inversion",
        "triggered": triggered,
        "score": f"{score}/3",
        "suggested_phase": suggested_phase,
        "suggested_label": suggested_label,
        "evidence": {
            "climate_label": label,
            "干头分": g_score,
            "地支分": z_score,
            "conditions_met": {
                "1_label 是极端对冲": cond_1_inverted_label,
                "2_干支符号相反": cond_2_signs_opposite,
                "3_两边都≥4": cond_3_both_strong,
            },
        },
    }


def detect_pseudo_following(pillars: List[Pillar], strength: Dict) -> Dict:
    """P4 · 假从 / 真从边界检测（v7.1 重写：综合看比劫根 + 印根 + 全四柱）。

    学理：
      真从 = 日主完全无救（无印 / 无比劫通根）
      假从 = 有印护身 OR 时柱有比劫帮扶，仍顺财杀走但能保全自身

    判断方法：
      has_self_help = 比劫通根 OR 印通根 OR 时干印 OR 时支自坐印根
    """
    day_gan = pillars[2].gan
    day_wx = GAN_WUXING[day_gan]
    support = strength.get("same", 0) + strength.get("sheng", 0)

    bijie_grounded = _bijie_grounded(pillars, day_wx)
    yin_grounded = _yin_grounded(pillars, day_wx)

    # 时柱印根：时干是印（生我）且时支主气是"生我"五行 → 印有自坐根
    shi_pillar = pillars[3]
    shi_gan_wx = GAN_WUXING[shi_pillar.gan]
    shi_zhi_main_wx = GAN_WUXING[ZHI_HIDDEN_GAN[shi_pillar.zhi][0]]
    shi_zuo_yin = (WUXING_SHENG.get(shi_gan_wx) == day_wx and
                   WUXING_SHENG.get(shi_zhi_main_wx) == day_wx)
    # 时干是日主同党且时支也支撑 → 时柱比劫自坐
    shi_zuo_bijie = (shi_gan_wx == day_wx and
                     (shi_zhi_main_wx == day_wx or WUXING_SHENG.get(shi_zhi_main_wx) == day_wx))

    has_self_help = bijie_grounded or yin_grounded or shi_zuo_yin or shi_zuo_bijie

    # 触发：support 在边界 2~5 之间 OR 比劫不通根但 support ≤ 5（覆盖更多假从场景）
    in_boundary = 2.0 <= support <= 5.5
    weak_no_grounded_bijie = (not bijie_grounded) and support <= 5.5
    triggered = in_boundary or weak_no_grounded_bijie

    if not triggered:
        kind = None
        suggested_phase = "day_master_dominant"
        suggested_label = ""
    elif has_self_help:
        kind = "pseudo"
        suggested_phase = "pseudo_following"
        suggested_label = "假从格 · 日主有印 / 时柱帮扶，顺势从财杀但能保全自身（比真从温和）"
    else:
        kind = "true"
        suggested_phase = "true_following"
        suggested_label = "真从格 · 日主完全无救（无印 / 无比劫通根 / 时柱也无帮扶），完全顺旺神走"

    return {
        "phase_id": "P4_pseudo_following",
        "triggered": triggered,
        "kind": kind,
        "suggested_phase": suggested_phase,
        "suggested_label": suggested_label,
        "evidence": {
            "day_master_support": round(support, 2),
            "in_boundary (2.0~5.5)": in_boundary,
            "weak_no_grounded_bijie": weak_no_grounded_bijie,
            "bijie_grounded": bijie_grounded,
            "yin_grounded": yin_grounded,
            "shi_pillar_yin_self_seated": shi_zuo_yin,
            "shi_pillar_bijie_self_seated": shi_zuo_bijie,
            "has_self_help": has_self_help,
        },
    }


def detect_three_qi_cheng_xiang(pillars: List[Pillar], strength: Dict) -> Dict:
    """P5 · 三气成象 / 财官印连环检测（v7.1 新增）。

    学理：当日主弱 + 命局存在「财生官 + 官生印 + 印生身」或「食伤生财 + 财生官」
    这种"三气流通"结构，命局主旋律不是"日主主导"而是"流通方向 = 主事"。
    参考《滴天髓·体用篇》"流通生化，体用相宜"、《穷通宝鉴》气机论。

    判断方法：
      有 ≥ 3 个非日主五行存在（每个 ≥ 2 分）+ 日主弱 + 比劫不通根
      → 命局是"多神成势"而不是"单神得令"
      → suggested_phase = floating_dms_to_cong_<最强非日主五行>

    与 P1 的关系：P5 处理"非单一旺神主导"的边缘 case（P1 漏掉的部分）。
    """
    day_gan = pillars[2].gan
    day_wx = GAN_WUXING[day_gan]

    cnt = {wx: 0.0 for wx in WUXING_ORDER}
    for i, p in enumerate(pillars):
        cnt[GAN_WUXING[p.gan]] += 1.0
        weight = 3.0 if i == 1 else 2.0
        for j, hg in enumerate(ZHI_HIDDEN_GAN[p.zhi]):
            cnt[GAN_WUXING[hg]] += weight * (1.0 if j == 0 else 0.3)

    non_dms = sorted(
        [(wx, score) for wx, score in cnt.items() if wx != day_wx],
        key=lambda x: -x[1]
    )

    # 至少 2 个非日主五行 ≥ 3 分（说明气机流通成势；少于 2 通常是单旺神 → 走 P1）
    n_strong_non_dms = sum(1 for _, s in non_dms if s >= 3.0)
    cond_1_three_strong = n_strong_non_dms >= 2

    # 最强非日主 + 第二强非日主 ≥ 8（成势）
    if len(non_dms) >= 2:
        top_two_sum = non_dms[0][1] + non_dms[1][1]
    else:
        top_two_sum = 0
    cond_2_top_two_strong = top_two_sum >= 8

    # 日主**真的弱**：label = 弱 AND score ≤ -20 AND 比劫不通根（三个 AND，防中和命误报）
    bijie_grounded = _bijie_grounded(pillars, day_wx)
    cond_3_dms_truly_weak = (
        strength.get("label") == "弱"
        and strength.get("score", 0) <= -20
        and (not bijie_grounded)
    )

    # 检测连环结构：A 生 B 生 C 这种链条
    has_chain = False
    if len(non_dms) >= 3:
        top3_wx = [non_dms[i][0] for i in range(3)]
        for src in top3_wx:
            mid = WUXING_SHENG.get(src)
            tgt = WUXING_SHENG.get(mid) if mid else None
            if mid in top3_wx and tgt in top3_wx:
                has_chain = True
                break
            # 链条也可以走到日主：财 → 官 → 印 → 身
            if mid in top3_wx and WUXING_SHENG.get(mid) == day_wx:
                has_chain = True
                break

    # 触发：必须同时满足 1 + 2 + 3 + has_chain（has_chain 强制要求，确保是"流通"而非"杂乱多神"）
    triggered = (cond_1_three_strong and cond_2_top_two_strong
                 and cond_3_dms_truly_weak and has_chain)
    score = sum([cond_1_three_strong, cond_2_top_two_strong, cond_3_dms_truly_weak, has_chain])

    suggested_phase = "day_master_dominant"
    suggested_label = ""
    if triggered and non_dms:
        dominating_wx = non_dms[0][0]
        shishen_class = _shishen_class_from_wuxing(day_wx, dominating_wx)
        suggested_phase = _shishen_to_phase(shishen_class)
        ten_god_label = {
            "正财": "财", "正官": "官", "七杀": "杀",
            "食神": "食伤", "正印": "印",
        }.get(shishen_class, shishen_class)
        suggested_label = (
            f"三气成象·{ten_god_label}({dominating_wx})为主神 · "
            f"日主弱借力流通（{'/'.join([w for w,_ in non_dms[:3]])}成势）"
            f"{' · 含连环生化' if has_chain else ''}"
        )

    return {
        "phase_id": "P5_three_qi_cheng_xiang",
        "triggered": triggered,
        "score": f"{score}/4",
        "suggested_phase": suggested_phase,
        "suggested_label": suggested_label,
        "evidence": {
            "non_dms_distribution": [{wx: round(s, 2)} for wx, s in non_dms[:4]],
            "n_strong_non_dms (≥2)": n_strong_non_dms,
            "top_two_sum": round(top_two_sum, 2),
            "bijie_grounded": bijie_grounded,
            "has_chain (生化连环)": has_chain,
            "conditions_met": {
                "1_两个非日主五行 ≥ 3": cond_1_three_strong,
                "2_最强两个 ≥ 8": cond_2_top_two_strong,
                "3_日主真弱 (label=弱 AND score≤-20 AND 比劫不通根)": cond_3_dms_truly_weak,
                "4_存在连环生化链 (强制要求)": has_chain,
            },
        },
    }


# ============================================================================
# 【v7.4 #5 新增】化气格检测 (P6 · Hua Qi Ge / Transformation Pattern)
# ----------------------------------------------------------------------------
# 天干五合若得地支化神之根 + 月令有气 + 无破格之物 → 真化气格
# 此时日主"借合化"易主，命局主导五行 = 化神，扶抑判定全部翻转。
#
# 五合化气：
#   甲 + 己 → 化土（月令辰戌丑未 / 地支土多）
#   乙 + 庚 → 化金（月令申酉 / 巳丑 / 地支金多）
#   丙 + 辛 → 化水（月令子亥 / 申辰 / 地支水多）
#   丁 + 壬 → 化木（月令寅卯 / 亥未 / 地支木多）
#   戊 + 癸 → 化火（月令巳午 / 寅戌 / 地支火多）
#
# 条件（4 + 1 一票否决）：
#   1. 日干 ∈ 五合对，且合干必须紧贴（月干 OR 时干，年干较弱）
#   2. 月令属化神（或半合 / 三合化神局）
#   3. 化神在地支至少 2 根，或月令本气就是化神
#   4. 无强力克化神者（如化土遇月干/时干透甲乙木，且木有根 → 破格）
#   5. 一票否决：日干本身在地支有强根（≥ 3 处比劫得地） → 不能化（化不掉）
# ============================================================================

GAN_WUHE_PAIRS = {
    "甲": ("己", "土"), "己": ("甲", "土"),
    "乙": ("庚", "金"), "庚": ("乙", "金"),
    "丙": ("辛", "水"), "辛": ("丙", "水"),
    "丁": ("壬", "木"), "壬": ("丁", "木"),
    "戊": ("癸", "火"), "癸": ("戊", "火"),
}

# 化神 → 月令所属地支（化神有气的月）
HUASHEN_FAVOR_MONTH = {
    "土": {"辰", "戌", "丑", "未", "巳", "午"},
    "金": {"申", "酉", "巳", "丑"},
    "水": {"子", "亥", "申", "辰"},
    "木": {"寅", "卯", "亥", "未"},
    "火": {"巳", "午", "寅", "戌"},
}


def detect_huaqi_pattern(pillars: List[Pillar]) -> Dict:
    """化气格检测。返回：
        {
            "triggered": bool,
            "huashen": str | None,         # 化神五行
            "score": "N/4",
            "evidence": {...},
            "suggested_phase": "huaqi_to_<wuxing>" | "day_master_dominant",
            "suggested_label": "化XX格 · ..."
        }
    """
    day_gan = pillars[2].gan
    day_wx = GAN_WUXING[day_gan]
    if day_gan not in GAN_WUHE_PAIRS:
        return {"triggered": False, "huashen": None, "score": "0/4",
                "phase_id": "P6_huaqi", "evidence": {}, "suggested_phase": "day_master_dominant",
                "suggested_label": ""}

    partner_gan, huashen = GAN_WUHE_PAIRS[day_gan]

    # 条件 1：合干必须紧贴日干（月干或时干）
    month_gan = pillars[1].gan
    hour_gan = pillars[3].gan
    year_gan = pillars[0].gan
    cond_1_adjacent = (month_gan == partner_gan) or (hour_gan == partner_gan)
    cond_1_year_only = (year_gan == partner_gan) and not cond_1_adjacent  # 年干合稍弱

    # 条件 2：月令属化神
    month_zhi = pillars[1].zhi
    favor_zhi = HUASHEN_FAVOR_MONTH.get(huashen, set())
    cond_2_month_favor = month_zhi in favor_zhi
    # 月令本气直接就是化神 → 加分
    month_main_wx = GAN_WUXING[ZHI_HIDDEN_GAN[month_zhi][0]]
    cond_2_month_huashen_main = (month_main_wx == huashen)

    # 条件 3：地支化神有根（至少 2 处）
    huashen_zhi_count = 0
    for p in pillars:
        if ZHI_WUXING[p.zhi] == huashen:
            huashen_zhi_count += 1
        for hg in ZHI_HIDDEN_GAN[p.zhi]:
            if GAN_WUXING[hg] == huashen:
                huashen_zhi_count += 0.4
                break
    cond_3_root = huashen_zhi_count >= 2.0

    # 条件 4：无强力克化神者
    huashen_ke_by = {v: k for k, v in WUXING_KE.items()}.get(huashen)  # 谁克化神
    breakers = 0
    for i, p in enumerate(pillars):
        if i == 2:
            continue  # 日干本身不算
        if GAN_WUXING[p.gan] == huashen_ke_by:
            # 地支有根才算硬破
            for q in pillars:
                if ZHI_WUXING[q.zhi] == huashen_ke_by or huashen_ke_by in [GAN_WUXING[hg] for hg in ZHI_HIDDEN_GAN[q.zhi]]:
                    breakers += 1
                    break
    cond_4_no_break = breakers == 0

    # 条件 5（一票否决）：日干本身有强根（化不掉）
    dms_root_count = 0
    for p in pillars:
        if ZHI_WUXING[p.zhi] == day_wx:
            dms_root_count += 1
        elif GAN_WUXING[ZHI_HIDDEN_GAN[p.zhi][0]] == day_wx:
            dms_root_count += 0.5
    veto_dms_strong = dms_root_count >= 2.5

    # 评分
    score = 0
    if cond_1_adjacent:
        score += 1
    elif cond_1_year_only:
        score += 0.5
    if cond_2_month_favor:
        score += 1
        if cond_2_month_huashen_main:
            score += 0.5
    if cond_3_root:
        score += 1
    if cond_4_no_break:
        score += 1

    # 真化气：score ≥ 3.5 + 无 veto
    triggered = (score >= 3.5) and (not veto_dms_strong) and cond_1_adjacent

    if not triggered:
        return {
            "phase_id": "P6_huaqi",
            "triggered": False,
            "huashen": huashen,
            "score": f"{score}/4.5",
            "suggested_phase": "day_master_dominant",
            "suggested_label": "",
            "evidence": {
                "partner_gan": partner_gan,
                "cond_1_adjacent_he": cond_1_adjacent,
                "cond_1_year_only_he": cond_1_year_only,
                "cond_2_month_favor": cond_2_month_favor,
                "cond_2_month_main_is_huashen": cond_2_month_huashen_main,
                "cond_3_huashen_root_count": round(huashen_zhi_count, 2),
                "cond_4_no_strong_breaker": cond_4_no_break,
                "n_breakers": breakers,
                "veto_dms_strong": veto_dms_strong,
                "dms_root_count": round(dms_root_count, 2),
            },
        }

    return {
        "phase_id": "P6_huaqi",
        "triggered": True,
        "huashen": huashen,
        "score": f"{score}/4.5",
        "suggested_phase": f"huaqi_to_{huashen}",
        "suggested_label": f"化{huashen}格（{day_gan}{partner_gan}合化{huashen}） · 命局主导改为{huashen}",
        "evidence": {
            "partner_gan": partner_gan,
            "cond_1_adjacent_he": cond_1_adjacent,
            "cond_2_month_favor": cond_2_month_favor,
            "cond_2_month_main_is_huashen": cond_2_month_huashen_main,
            "cond_3_huashen_root_count": round(huashen_zhi_count, 2),
            "cond_4_no_strong_breaker": cond_4_no_break,
            "veto_dms_strong": veto_dms_strong,
            "dms_root_count": round(dms_root_count, 2),
        },
    }


# ============================================================================
# 【v7.4 #5 新增】神煞检测 (Shen Sha · 烈度修正用，不影响主格局)
# ----------------------------------------------------------------------------
# 神煞规则参考通行版本（《三命通会》《渊海子平》），仅做主流神煞，不做冷门。
# 用法：在 score_curves.py 烈度修正阶段，命中神煞的大运 / 流年微调强度，
# 不参与主格局判定（避免混入"封建迷信"权重）。
# 影响幅度都很小（±0.5 ~ ±1.0），只是局部调味。
# ============================================================================

# 天乙贵人：日干 → 贵人地支
TIANYI_GUIREN = {
    "甲": {"丑", "未"}, "戊": {"丑", "未"}, "庚": {"丑", "未"},
    "乙": {"子", "申"}, "己": {"子", "申"},
    "丙": {"亥", "酉"}, "丁": {"亥", "酉"},
    "辛": {"寅", "午"},
    "壬": {"卯", "巳"}, "癸": {"卯", "巳"},
}

# 文昌贵人：日干 → 文昌地支（食神临官）
WENCHANG = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}

# 驿马：年支 / 日支 三合局首字 → 驿马（冲首字者）
# 申子辰马在寅；寅午戌马在申；亥卯未马在巳；巳酉丑马在亥
YIMA = {
    "申": "寅", "子": "寅", "辰": "寅",
    "寅": "申", "午": "申", "戌": "申",
    "亥": "巳", "卯": "巳", "未": "巳",
    "巳": "亥", "酉": "亥", "丑": "亥",
}

# 桃花：年支 / 日支 → 桃花（已在他处使用，此处为完整性保留）
TAOHUA = {
    "申": "酉", "子": "酉", "辰": "酉",
    "寅": "卯", "午": "卯", "戌": "卯",
    "亥": "子", "卯": "子", "未": "子",
    "巳": "午", "酉": "午", "丑": "午",
}

# 华盖：年支 / 日支 三合局末字 → 华盖
HUAGAI = {
    "申": "辰", "子": "辰", "辰": "辰",
    "寅": "戌", "午": "戌", "戌": "戌",
    "亥": "未", "卯": "未", "未": "未",
    "巳": "丑", "酉": "丑", "丑": "丑",
}

# 孤辰寡宿：年支 → (孤辰, 寡宿)
GUCHEN_GUASU = {
    "亥": ("寅", "戌"), "子": ("寅", "戌"), "丑": ("寅", "戌"),
    "寅": ("巳", "丑"), "卯": ("巳", "丑"), "辰": ("巳", "丑"),
    "巳": ("申", "辰"), "午": ("申", "辰"), "未": ("申", "辰"),
    "申": ("亥", "未"), "酉": ("亥", "未"), "戌": ("亥", "未"),
}

# 旬空（空亡）：日柱所在六十甲子旬 → 空亡两字
# 简化：按日干日支组合查（标准方法是按 60 甲子旬）
def _xunkong(day_gan: str, day_zhi: str) -> Tuple[str, str]:
    """根据日柱所在旬返回空亡两支。"""
    gan_idx = GAN.index(day_gan)
    zhi_idx = ZHI.index(day_zhi)
    # 日柱在 60 甲子里的位置
    # 找到所在旬的起点
    # 60 甲子 = (gan_idx, zhi_idx) 对应序号
    # 简化算法：旬首干 = 甲，旬首干日序号 i 时，其对应的支序号是 (zhi_idx - gan_idx) mod 12
    diff = (zhi_idx - gan_idx) % 12
    # 旬空 = 旬首支 + 10 与 +11
    # 旬首支序号 = (60 - gan_idx) % 12 内（甲为旬首），实际旬首支 = (zhi_idx - gan_idx) mod 12 = diff
    # 旬空 = (diff + 10) % 12, (diff + 11) % 12
    return ZHI[(diff + 10) % 12], ZHI[(diff + 11) % 12]


def detect_shensha(pillars: List[Pillar]) -> Dict:
    """检测命局神煞分布。返回每个神煞触发位置 + 是否落在原局。

    Returns:
        {
            "tianyi_guiren": {"target_zhi": [...], "in_chart": [...], "found": bool},
            "wenchang": {"target_zhi": "X", "in_chart": [...], "found": bool},
            "yima": {"target_zhi": [...], "in_chart": [...], "found": bool},
            "taohua": {...},
            "huagai": {...},
            "guchen": {"target_zhi": "X", "in_chart": [...], "found": bool},
            "guasu": {"target_zhi": "X", "in_chart": [...], "found": bool},
            "kongwang": {"target_zhi": [X, Y], "in_chart": [...], "found": bool},
        }

    用途：
      - in_chart 为空但 target_zhi 存在 → 当大运/流年走到 target_zhi 时触发，
        在 score_curves.py 烈度修正阶段做小幅 ±0.5 调整。
      - in_chart 已命中 → 命主一生持续受该神煞影响（e.g., 天乙贵人在原局
        → 终生有贵人相助倾向，命名 / 关系维度小幅 +0.5）。
    """
    day_gan = pillars[2].gan
    day_zhi = pillars[2].zhi
    year_zhi = pillars[0].zhi

    chart_zhi = [p.zhi for p in pillars]

    def _check(target_zhi_set):
        if isinstance(target_zhi_set, str):
            target_zhi_set = {target_zhi_set}
        target = list(target_zhi_set) if isinstance(target_zhi_set, (set, list, tuple)) else [target_zhi_set]
        hits = [z for z in chart_zhi if z in target_zhi_set]
        return {"target_zhi": sorted(target), "in_chart": hits, "found": bool(hits)}

    # 天乙贵人：以日干为主
    tianyi_target = TIANYI_GUIREN.get(day_gan, set())
    # 文昌：以日干为主
    wenchang_target = {WENCHANG.get(day_gan)} if day_gan in WENCHANG else set()
    # 驿马 / 桃花 / 华盖：以年支 + 日支查（取并集）
    yima_target = {YIMA[year_zhi], YIMA[day_zhi]} if year_zhi in YIMA else set()
    taohua_target = {TAOHUA[year_zhi], TAOHUA[day_zhi]} if year_zhi in TAOHUA else set()
    huagai_target = {HUAGAI[year_zhi], HUAGAI[day_zhi]} if year_zhi in HUAGAI else set()
    # 孤辰 / 寡宿：以年支
    if year_zhi in GUCHEN_GUASU:
        gu, gua = GUCHEN_GUASU[year_zhi]
    else:
        gu, gua = "", ""
    # 旬空
    kw1, kw2 = _xunkong(day_gan, day_zhi)

    return {
        "tianyi_guiren": _check(tianyi_target),
        "wenchang": _check(wenchang_target),
        "yima": _check(yima_target),
        "taohua": _check(taohua_target),
        "huagai": _check(huagai_target),
        "guchen": _check({gu} if gu else set()),
        "guasu": _check({gua} if gua else set()),
        "kongwang": _check({kw1, kw2}),
    }


# 神煞 → 维度 / 烈度修正映射（用于 score_curves）
# 影响幅度刻意小（±0.5 ~ ±1.0），只是调味
SHENSHA_IMPACT = {
    "tianyi_guiren": {
        "in_chart_bonus": {"fortune": 0.3, "fame": 0.3, "emotion": 0.2},  # 终生贵人倾向
        "yearly_bonus": {"fortune": 0.5, "fame": 0.5},  # 大运/流年走到 → 当年贵人显
        "label": "天乙贵人",
    },
    "wenchang": {
        "in_chart_bonus": {"fame": 0.4},
        "yearly_bonus": {"fame": 0.5, "spirit": 0.3},  # 考试 / 学问 / 著述
        "label": "文昌贵人",
    },
    "yima": {
        "in_chart_bonus": {},  # 命带驿马 → 一生奔波，但不直接加减分
        "yearly_volatility": 0.3,  # 大运/流年逢 → 该年波动幅度 +30%（变动 / 出行 / 调岗）
        "label": "驿马",
    },
    "taohua": {
        "in_chart_bonus": {"emotion": 0.3},  # 命带桃花 → 关系能量略升
        "yearly_bonus": {"emotion": 0.5},
        "label": "桃花",
    },
    "huagai": {
        "in_chart_bonus": {"spirit": 0.2},  # 偏门艺术 / 宗教 / 内省 → 精神维度小升
        "yearly_bonus": {"spirit": 0.3},
        "label": "华盖",
    },
    "guchen": {
        "in_chart_penalty": {"emotion": -0.4},  # 孤辰 → 关系能量小减（仅基线，不绝对）
        "label": "孤辰",
    },
    "guasu": {
        "in_chart_penalty": {"emotion": -0.4},
        "label": "寡宿",
    },
    "kongwang": {
        "yearly_penalty": {"fortune": -0.5, "fame": -0.3},  # 大运/流年逢空亡 → 落空感
        "label": "空亡",
    },
}


# ============================================================================
# end of HuaQi + Shensha (v7.4 #5)
# ============================================================================


def detect_all_phase_candidates(bazi_dict: Dict) -> List[Dict]:
    """跑全部 4 类 detect，返回触发的候选 + 全部 detect 详情。

    v8 改动：每个 detector 输出 dict 在原有字段上 augment 两个 v8 字段：
        - confidence_for_decide: float ∈ [0, 1]，detector 对自己结论的信心
        - phase_likelihoods: Dict[phase_id, float]，14 个 phase 上的 likelihood 分布（∑=1.0）
                             用于 decide_phase 做贝叶斯先验融合（详见 phase_decision_protocol.md §3）

    输入是 bazi.json 解析后的 dict（含 pillars / strength / climate / pillar_info）。
    输出 list 按 confidence 降序排序，仅 triggered=True 的进入 triggered_candidates。
    """
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi_dict["pillars"]]
    strength = bazi_dict["strength"]
    climate = bazi_dict.get("yongshen", {}).get("climate") or climate_profile(pillars)

    raw_results = [
        detect_floating_day_master(pillars, strength),
        detect_dominating_god(pillars, strength),
        detect_climate_inversion(pillars, climate),
        detect_pseudo_following(pillars, strength),
        detect_three_qi_cheng_xiang(pillars, strength),
        detect_huaqi_pattern(pillars),
    ]
    # v8 · augment 每个 detector 输出
    results = [_augment_detector_output(r) for r in raw_results]

    triggered = [r for r in results if r["triggered"]]
    not_triggered = [r for r in results if not r["triggered"]]

    # v7.2 · 触发候选按置信度排序：先按 hit/total 比值降序，平手时按 hit 绝对值降序
    def _conf(det: Dict) -> Tuple[float, int]:
        s = det.get("score", "")
        if not s or "/" not in str(s):
            return (0.5, 0)
        try:
            hit, tot = str(s).split("(")[0].split("/")
            hit_f, tot_f = float(hit), float(tot)
            return (hit_f / tot_f if tot_f > 0 else 0.5, int(hit_f))
        except Exception:
            return (0.5, 0)

    triggered.sort(key=lambda r: (-_conf(r)[0], -_conf(r)[1], r["phase_id"]))
    return {
        "triggered_candidates": triggered,
        "all_detection_details": results,
        "not_triggered": not_triggered,
        "summary": {
            "n_triggered": len(triggered),
            "phases_suggested": [r["suggested_phase"] for r in triggered if r["suggested_phase"] != "day_master_dominant"],
        },
    }


# ============================================================================
# v8 · Phase Decision · detector → prior → posterior 融合
# ----------------------------------------------------------------------------
# 详见 references/phase_decision_protocol.md
# ============================================================================

# 每个 detector 能"投票"的 phase 家族（家族外 phase 给残余权重）
_DETECTOR_PHASE_FAMILY: Dict[str, Tuple[str, ...]] = {
    "P1_floating_day_master": (
        "floating_dms_to_cong_cai", "floating_dms_to_cong_sha",
        "floating_dms_to_cong_er", "floating_dms_to_cong_yin",
    ),
    "P2_dominating_god": (
        "dominating_god_cai_zuo_zhu", "dominating_god_guan_zuo_zhu",
        "dominating_god_shishang_zuo_zhu", "dominating_god_yin_zuo_zhu",
    ),
    "P3_climate_inversion": (
        "climate_inversion_dry_top", "climate_inversion_wet_top",
    ),
    "P4_pseudo_following": (
        "pseudo_following", "true_following",
    ),
    "P5_three_qi_cheng_xiang": (
        "floating_dms_to_cong_cai", "floating_dms_to_cong_sha",
        "floating_dms_to_cong_er", "floating_dms_to_cong_yin",
    ),
    "P6_huaqi": tuple(f"huaqi_to_{wx}" for wx in ("土", "金", "水", "木", "火")),
}

ALL_PHASE_IDS: Tuple[str, ...] = tuple(sorted({
    "day_master_dominant",
    *(p for fam in _DETECTOR_PHASE_FAMILY.values() for p in fam),
}))

# detector → 它语义上"邻近"但不在自己 family 里的 phase 集（语义相近 → 触发时给 moderate boost）
# 例：P3（调候反向）触发，往往伴随 cong_xxx；P4（假从）本身是 cong 的子集
_DETECTOR_NEIGHBOR_PHASES: Dict[str, Tuple[str, ...]] = {
    "P3_climate_inversion": (
        "floating_dms_to_cong_cai", "floating_dms_to_cong_sha",
        "floating_dms_to_cong_er", "floating_dms_to_cong_yin",
    ),
    "P4_pseudo_following": (
        "floating_dms_to_cong_cai", "floating_dms_to_cong_sha",
        "floating_dms_to_cong_er", "floating_dms_to_cong_yin",
    ),
    "P5_three_qi_cheng_xiang": (
        "pseudo_following", "true_following",
    ),
    "P1_floating_day_master": (
        "pseudo_following", "true_following",
    ),
}


def _parse_detector_score(score_str: str) -> Tuple[float, float]:
    """解析 detector score 字段（如 "4/5（核心三条满足触发）"）→ (hit, tot)。"""
    if not score_str or "/" not in str(score_str):
        return (0.0, 1.0)
    try:
        head = str(score_str).split("（")[0].split("(")[0]
        hit_s, tot_s = head.split("/")
        return (float(hit_s), float(tot_s))
    except Exception:
        return (0.0, 1.0)


def _phase_likelihoods_from_detector(det: Dict) -> Dict[str, float]:
    """把单个 detector 输出映射成 18 phase 上的 likelihood 分布（∑=1.0）。

    映射规则（启发式 · 详见 phase_decision_protocol.md §3）：
      - triggered:
          suggested_phase: 0.50 + 0.15 × score_ratio   → 0.50 ~ 0.65
          family 其他成员: 各 0.04
          neighbor 语义邻近 phase: 各 0.05
          day_master_dominant: 0.04
          其他 outside: 平分残余
      - 未 triggered:
          返回近似 uniform 分布（fusion 时会被跳过；保留是为了诊断 / 调试）
          day_master_dominant: 0.10（轻微 DM 偏好）
          其他: 均匀分摊剩余
    """
    detector_id = det.get("phase_id", "unknown")
    family = set(_DETECTOR_PHASE_FAMILY.get(detector_id, ()))
    neighbors = set(_DETECTOR_NEIGHBOR_PHASES.get(detector_id, ()))
    neighbors -= family  # neighbors 与 family 不重叠
    suggested = det.get("suggested_phase", "day_master_dominant")
    triggered = bool(det.get("triggered", False))
    hit, tot = _parse_detector_score(str(det.get("score", "0/1")))
    score_ratio = (hit / tot) if tot > 0 else 0.5

    out: Dict[str, float] = {}
    if triggered:
        w_suggested = 0.50 + 0.15 * score_ratio  # 0.50 ~ 0.65
        w_family = 0.04
        w_neighbor = 0.05
        w_dm = 0.04
        used_phases = {suggested, "day_master_dominant"} | family | neighbors
        outside = [p for p in ALL_PHASE_IDS if p not in used_phases]
        n_family_others = sum(1 for p in family if p != suggested)
        n_neighbors = len(neighbors)
        n_outside = len(outside)
        consumed = (
            w_suggested
            + w_family * n_family_others
            + w_neighbor * n_neighbors
            + (w_dm if "day_master_dominant" not in family and "day_master_dominant" not in neighbors and "day_master_dominant" != suggested else 0.0)
        )
        w_outside = max((1.0 - consumed) / max(n_outside, 1), 0.005)

        for pid in ALL_PHASE_IDS:
            if pid == suggested:
                out[pid] = w_suggested
            elif pid in family:
                out[pid] = w_family
            elif pid in neighbors:
                out[pid] = w_neighbor
            elif pid == "day_master_dominant":
                out[pid] = w_dm
            else:
                out[pid] = w_outside
    else:
        # 未触发：近似 uniform，DM 略偏好（fusion 时会被 _compute_prior 跳过）
        w_dm = 0.10
        w_other = (1.0 - w_dm) / (len(ALL_PHASE_IDS) - 1)
        for pid in ALL_PHASE_IDS:
            out[pid] = w_dm if pid == "day_master_dominant" else w_other

    total = sum(out.values())
    return {pid: round(out[pid] / total, 8) for pid in sorted(out.keys())}


def _augment_detector_output(det: Dict) -> Dict:
    """v8 · 在 detector 原 dict 上加 confidence_for_decide + phase_likelihoods。"""
    triggered = bool(det.get("triggered", False))
    hit, tot = _parse_detector_score(str(det.get("score", "0/1")))
    score_ratio = (hit / tot) if tot > 0 else 0.5
    if triggered:
        confidence_for_decide = round(0.50 + 0.50 * score_ratio, 4)
    else:
        confidence_for_decide = round(max(0.05, 0.30 - 0.20 * score_ratio), 4)
    out = dict(det)
    out["confidence_for_decide"] = confidence_for_decide
    out["phase_likelihoods"] = _phase_likelihoods_from_detector(det)
    return out


def _normalize_distribution(dist: Dict[str, float]) -> Dict[str, float]:
    total = sum(dist.values())
    if total <= 0:
        n = len(dist) or 1
        return {k: 1.0 / n for k in sorted(dist.keys())}
    return {k: dist[k] / total for k in sorted(dist.keys())}


def _compute_prior_distribution(detection_details: List[Dict]) -> Dict[str, float]:
    """对所有 *已触发* detector 输出做乘性贝叶斯融合，得到 18 phase 上的先验分布。

    设计要点（详见 phase_decision_protocol.md §3）：
      - 起始 prior：DM = 0.30（baseline 偏好默认相位但不绝对），其它 17 phase 平分剩余 0.70
      - 跳过未触发 detector：未触发 ≈ 无信息，不应把 DM 推到 99%
      - 末尾 floor：DM ≥ 0.03（防止极端 case 把 DM 压到 0；但允许显著降低）
    """
    n = len(ALL_PHASE_IDS)
    triggered = [d for d in detection_details if d.get("triggered", False)]

    # 0 triggered → fast-path：DM_dominant 高置信，其它平分残余
    # （detector 设计本身就是为了找"非默认"case；都没触发 = 默认相位的强证据）
    if not triggered:
        prior: Dict[str, float] = {pid: 0.10 / (n - 1) for pid in ALL_PHASE_IDS}
        prior["day_master_dominant"] = 0.90
        return _normalize_distribution(prior)

    # 有 triggered → 弱 DM 偏置 + 乘性融合
    prior = {pid: 0.70 / (n - 1) for pid in ALL_PHASE_IDS}
    prior["day_master_dominant"] = 0.30
    prior = _normalize_distribution(prior)

    for det in triggered:
        likelihoods = det.get("phase_likelihoods") or _phase_likelihoods_from_detector(det)
        for pid in prior:
            prior[pid] *= max(likelihoods.get(pid, 1e-6), 1e-6)
        prior = _normalize_distribution(prior)
    # day_master_dominant baseline floor，避免数值下溢
    prior["day_master_dominant"] = max(prior["day_master_dominant"], 0.03)
    return _normalize_distribution(prior)


# 五行映射常量（供 _phase_five_tuple 使用）
_WUXING_INV_KE: Dict[str, str] = {v: k for k, v in WUXING_KE.items()}  # 谁克我
_WUXING_INV_SHENG: Dict[str, str] = {v: k for k, v in WUXING_SHENG.items()}  # 谁生我


def _phase_five_tuple(phase_id: str, bazi_dict: Dict) -> Dict:
    """根据 phase_id 算 (strength_label, yongshen, xishen, jishen, climate_label) 五元组。
    详见 phase_decision_protocol.md §6。
    """
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi_dict["pillars"]]
    day_gan = pillars[2].gan
    day_wx = GAN_WUXING[day_gan]
    cai_wx = WUXING_KE[day_wx]              # 我克 = 财
    sha_wx = _WUXING_INV_KE[day_wx]         # 克我 = 官杀
    er_wx = WUXING_SHENG[day_wx]            # 我生 = 食伤
    yin_wx = _WUXING_INV_SHENG[day_wx]      # 生我 = 印
    bi_wx = day_wx                           # 比劫 = 我

    default_strength = bazi_dict.get("strength", {})
    default_yongshen = bazi_dict.get("yongshen", {}).get("yongshen", "")
    default_climate = bazi_dict.get("yongshen", {}).get("climate", {}).get("label", "")

    # 默认（DM_dominant）走原有 yongshen
    if phase_id == "day_master_dominant":
        return {
            "strength": default_strength,
            "yongshen": default_yongshen,
            "xishen": _WUXING_INV_SHENG.get(default_yongshen, ""),
            "jishen": _WUXING_INV_KE.get(default_yongshen, ""),
            "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
            "phase_label": "默认 · 日主主导",
        }

    # cong_xxx 系列：日主弃命从某神
    cong_map = {
        "floating_dms_to_cong_cai": (cai_wx, er_wx, bi_wx, "弃命从财（日主虚浮 → 财星主事）"),
        "floating_dms_to_cong_sha": (sha_wx, cai_wx, yin_wx, "弃命从杀（日主虚浮 → 官杀主事）"),
        "floating_dms_to_cong_er":  (er_wx, bi_wx, yin_wx, "弃命从儿（日主虚浮 → 食伤主事）"),
        "floating_dms_to_cong_yin": (yin_wx, sha_wx, cai_wx, "弃命从印（日主虚浮 → 印星主事）"),
    }
    if phase_id in cong_map:
        ys, xs, js, label = cong_map[phase_id]
        return {
            "strength": {"label": "强（从神为主）", "score": 30, "_phase_overridden": True},
            "yongshen": ys, "xishen": xs, "jishen": js,
            "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
            "phase_label": label,
        }

    # dominating_god 系列：日主弱 + 旺神主事
    dom_map = {
        "dominating_god_cai_zuo_zhu":   (cai_wx, er_wx, bi_wx, "旺神得令·财星主事"),
        "dominating_god_guan_zuo_zhu":  (sha_wx, cai_wx, yin_wx, "旺神得令·官杀主事"),
        "dominating_god_shishang_zuo_zhu": (er_wx, bi_wx, yin_wx, "旺神得令·食伤主事"),
        "dominating_god_yin_zuo_zhu":   (yin_wx, sha_wx, cai_wx, "旺神得令·印主事"),
    }
    if phase_id in dom_map:
        ys, xs, js, label = dom_map[phase_id]
        return {
            "strength": {"label": "弱", "score": -25, "_phase_overridden": True},
            "yongshen": ys, "xishen": xs, "jishen": js,
            "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
            "phase_label": label,
        }

    # climate inversion · 调候反向
    if phase_id == "climate_inversion_dry_top":
        return {
            "strength": default_strength,
            "yongshen": "水", "xishen": "金", "jishen": "土",
            "climate": {"label": "上燥下寒", "_phase_overridden": True},
            "phase_label": "调候反向·上燥下寒（用神锁水）",
        }
    if phase_id == "climate_inversion_wet_top":
        return {
            "strength": default_strength,
            "yongshen": "火", "xishen": "木", "jishen": "水",
            "climate": {"label": "上湿下燥", "_phase_overridden": True},
            "phase_label": "调候反向·上湿下燥（用神锁火）",
        }

    # pseudo_following · 假从（保留原 yongshen + caveat）
    if phase_id == "pseudo_following":
        return {
            "strength": {"label": "弱", "score": -10, "_phase_overridden": True, "_caveat": "假从"},
            "yongshen": default_yongshen,
            "xishen": _WUXING_INV_SHENG.get(default_yongshen, ""),
            "jishen": _WUXING_INV_KE.get(default_yongshen, ""),
            "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
            "phase_label": "假从格 · 日主有印 / 时柱帮扶",
        }

    # true_following · 真从（按旺神方向）
    if phase_id == "true_following":
        # 旺神 wx 由 detector 找出；这里简化为最强非日主五行
        cnt = _wuxing_count(pillars)
        non_dms = sorted(
            [(wx, score) for wx, score in cnt.items() if wx != day_wx],
            key=lambda x: (-x[1], x[0])
        )
        dominating_wx = non_dms[0][0] if non_dms else cai_wx
        ys = dominating_wx
        xs = _WUXING_INV_SHENG.get(ys, "")
        js = _WUXING_INV_KE.get(ys, "")
        return {
            "strength": {"label": "强（从神为主）", "score": 30, "_phase_overridden": True},
            "yongshen": ys, "xishen": xs, "jishen": js,
            "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
            "phase_label": f"真从格 · 顺{ys}走",
        }

    # huaqi_to_<wx> · 化气格
    if phase_id.startswith("huaqi_to_"):
        huashen = phase_id.replace("huaqi_to_", "")
        return {
            "strength": {"label": "强（化神为主）", "score": 25, "_phase_overridden": True},
            "yongshen": huashen,
            "xishen": _WUXING_INV_SHENG.get(huashen, ""),
            "jishen": _WUXING_INV_KE.get(huashen, ""),
            "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
            "phase_label": f"化气格 · 化{huashen}",
        }

    # 兜底
    return {
        "strength": default_strength,
        "yongshen": default_yongshen,
        "xishen": _WUXING_INV_SHENG.get(default_yongshen, ""),
        "jishen": _WUXING_INV_KE.get(default_yongshen, ""),
        "climate": bazi_dict.get("yongshen", {}).get("climate", {}),
        "phase_label": phase_id,
    }


def _confidence_label(top_prob: float) -> str:
    """详见 phase_decision_protocol.md §5。"""
    if top_prob >= 0.80:
        return "high"
    if top_prob >= 0.60:
        return "mid"
    if top_prob >= 0.40:
        return "low"
    return "reject"


def decide_phase(
    bazi_dict: Dict,
    user_answers: Optional[Dict[str, str]] = None,
    dynamic_questions: Optional[List[Dict]] = None,
) -> Dict:
    """v8 核心 · phase decision。

    Args:
        bazi_dict: bazi.json 解析后的 dict（含 pillars / strength / yongshen / climate）
        user_answers: Optional[Dict[question_id, option_id]]，None = 仅算先验
        dynamic_questions: Optional list of dynamic question dicts (id, options, likelihood_table)
                           — D3 流年题由 handshake 阶段动态生成，传给本函数算后验

    Returns:
        PhaseDecision dict（详见 references/phase_decision_protocol.md §6）
    """
    detection = detect_all_phase_candidates(bazi_dict)
    detail = detection["all_detection_details"]

    prior = _compute_prior_distribution(detail)

    posterior = dict(prior)
    answered_ids: List[str] = []
    if user_answers:
        # 静态题
        try:
            from _question_bank import get_static_questions  # type: ignore
        except ImportError:
            from scripts._question_bank import get_static_questions  # type: ignore
        questions_by_id = {q.id: q for q in get_static_questions()}
        # 动态题（D3 流年题）追加进 lookup
        if dynamic_questions:
            for dq in dynamic_questions:
                questions_by_id[dq["id"]] = _DynamicQuestionShim(dq)

        for qid, opt in sorted(user_answers.items()):
            q = questions_by_id.get(qid)
            if q is None:
                continue
            answered_ids.append(qid)
            weight = 2.0 if q.weight_class == "hard_evidence" else 1.0
            for pid in posterior:
                like = q.likelihood_table.get(pid, {}).get(opt, 0.25)
                posterior[pid] *= max(like, 1e-6) ** weight
            posterior = _normalize_distribution(posterior)

    # decision: top-1
    sorted_phases = sorted(posterior.items(), key=lambda x: (-x[1], x[0]))
    top_phase = sorted_phases[0][0]
    top_prob = sorted_phases[0][1]
    confidence = _confidence_label(top_prob)

    five = _phase_five_tuple(top_phase, bazi_dict)

    triggered_summary = [
        f"{d['phase_id']}({d.get('score','')})"
        for d in detection["triggered_candidates"]
    ]
    reason_parts = []
    if triggered_summary:
        reason_parts.append("detectors: " + ", ".join(triggered_summary))
    else:
        reason_parts.append("detectors: 无触发，走默认相位")
    if answered_ids:
        reason_parts.append(f"user answered: {', '.join(answered_ids)}")

    candidates = [
        {
            "phase_id": pid,
            "prior": round(prior[pid], 6),
            "posterior": round(posterior[pid], 6),
        }
        for pid, _ in sorted_phases[:5]
    ]

    return {
        "version": 8,
        "candidates": candidates,
        "prior_distribution": {k: round(v, 6) for k, v in sorted(prior.items())},
        "posterior_distribution": {k: round(v, 6) for k, v in sorted(posterior.items())},
        "decision": top_phase,
        "decision_probability": round(top_prob, 6),
        "phase_label": five["phase_label"],
        "confidence": confidence,
        "is_provisional": user_answers is None,
        "strength_after_phase": five["strength"],
        "yongshen_after_phase": five["yongshen"],
        "xishen_after_phase": five["xishen"],
        "jishen_after_phase": five["jishen"],
        "climate_after_phase": five["climate"],
        "answered_questions": sorted(answered_ids),
        "reason": "; ".join(reason_parts),
    }


class _DynamicQuestionShim:
    """把 D3 dynamic question dict 包装成 Question-like 对象，供 decide_phase 内部使用。"""
    __slots__ = ("id", "weight_class", "likelihood_table")

    def __init__(self, q_dict: Dict):
        self.id = q_dict["id"]
        self.weight_class = q_dict.get("weight_class", "hard_evidence")
        self.likelihood_table = q_dict.get("likelihood_table", {})


def compute_question_likelihoods(
    bazi_dict: Dict,
    top_k: int = 25,
    discrimination_threshold: float = 0.18,
) -> List[Dict]:
    """v8 · 按当前命局 prior 自动从题库筛 phase-discriminative 题（按区分度倒排，取 top_k）。

    返回 list of dict（每个含：id, dimension, weight_class, prompt, options, likelihood_table,
    discrimination_power）—— handshake.py 把它打包进 v8 schema。
    """
    try:
        from _question_bank import get_static_questions, discrimination_power  # type: ignore
    except ImportError:
        from scripts._question_bank import get_static_questions, discrimination_power  # type: ignore

    detection = detect_all_phase_candidates(bazi_dict)
    prior = _compute_prior_distribution(detection["all_detection_details"])

    questions = get_static_questions()
    scored = []
    for q in questions:
        dp = discrimination_power(q, prior)
        if dp < discrimination_threshold:
            continue
        scored.append((dp, q))
    # 倒排
    scored.sort(key=lambda x: (-x[0], x[1].id))
    selected = scored[:top_k]

    out = []
    for dp, q in selected:
        out.append({
            "id": q.id,
            "dimension": q.dimension,
            "weight_class": q.weight_class,
            "prompt": q.prompt,
            "options": [{"id": o.id, "label": o.label} for o in q.options],
            "likelihood_table": {
                pid: dict(sorted(row.items())) for pid, row in sorted(q.likelihood_table.items())
            },
            "discrimination_power": round(dp, 6),
            "requires_dynamic_year": q.requires_dynamic_year,
            "evidence_note": q.evidence_note,
        })
    return out


def pairwise_discrimination_power(
    q,  # Question or _DynamicQuestionShim
    phase_a: str,
    phase_b: str,
) -> float:
    """两个 phase 之间的 L1 区分度（[0, 2]，越大越能区分）。

    用于 Round 2 confirmation：在 R1 决策的 top phase 与 runner-up 之间，
    挑出最具判别力的题目继续追问。详见 references/phase_decision_protocol.md §7。
    """
    table = getattr(q, "likelihood_table", None) or {}
    row_a = table.get(phase_a, {})
    row_b = table.get(phase_b, {})
    if not row_a or not row_b:
        return 0.0
    options = getattr(q, "options", None)
    if options:
        opt_ids = [o.id for o in options]
    else:
        opt_ids = sorted(set(row_a.keys()) | set(row_b.keys()))
    return sum(abs(row_a.get(oid, 0.0) - row_b.get(oid, 0.0)) for oid in opt_ids)


def compute_confirmation_questions(
    bazi_dict: Dict,
    decided_phase: str,
    runner_up_phase: str,
    exclude_ids: Optional[List[str]] = None,
    top_k: int = 6,
    discrimination_threshold: float = 0.30,
) -> List[Dict]:
    """v8 R2 · 在已决策 phase 与 runner-up 之间挑高判别力的静态题。

    Args:
        bazi_dict: bazi.json
        decided_phase: R1 后验 top
        runner_up_phase: R1 后验第二
        exclude_ids: R1 已经问过的 question_id 列表
        top_k: 返回数量上限
        discrimination_threshold: pairwise L1 距离下限（< 此值的题判别力不足，过滤）
    """
    try:
        from _question_bank import get_static_questions  # type: ignore
    except ImportError:
        from scripts._question_bank import get_static_questions  # type: ignore

    excluded = set(exclude_ids or [])
    scored: List[Tuple[float, "Question"]] = []
    for q in get_static_questions():
        if q.id in excluded:
            continue
        dp = pairwise_discrimination_power(q, decided_phase, runner_up_phase)
        if dp < discrimination_threshold:
            continue
        scored.append((dp, q))

    scored.sort(key=lambda x: (-x[0], x[1].id))
    selected = scored[:top_k]

    out: List[Dict] = []
    for dp, q in selected:
        out.append({
            "id": q.id,
            "dimension": q.dimension,
            "weight_class": q.weight_class,
            "prompt": q.prompt,
            "options": [{"id": o.id, "label": o.label} for o in q.options],
            "likelihood_table": {
                pid: dict(sorted(row.items())) for pid, row in sorted(q.likelihood_table.items())
            },
            "discrimination_power": round(dp, 6),
            "pairwise_target": {"a": decided_phase, "b": runner_up_phase},
            "requires_dynamic_year": q.requires_dynamic_year,
            "evidence_note": q.evidence_note,
        })
    return out


def assess_confirmation(
    r1_decision: str,
    r1_probability: float,
    r2_decision: str,
    r2_probability: float,
    confirmed_threshold: float = 0.85,
    weakly_confirmed_threshold: float = 0.65,
) -> Dict:
    """v8 R2 · 比较 R1 / R2 决策，输出 confirmation_status。

    详见 references/phase_decision_protocol.md §7。

    Returns dict:
        status: "confirmed" | "weakly_confirmed" | "decision_changed" | "uncertain"
        message: 中文短说明
        action: "render" | "render_with_caveat" | "escalate"
    """
    if r1_decision != r2_decision:
        return {
            "status": "decision_changed",
            "message": (
                f"R1 决策 {r1_decision} 经 R2 校验后翻转为 {r2_decision}（prob={r2_probability:.3f}）。"
                "建议核对出生时辰 / 性别，或采纳 R2 新决策再次 R2 验证。"
            ),
            "action": "escalate",
            "r1_decision": r1_decision,
            "r2_decision": r2_decision,
            "r1_probability": round(r1_probability, 6),
            "r2_probability": round(r2_probability, 6),
        }
    # 决策一致
    if r2_probability >= confirmed_threshold:
        return {
            "status": "confirmed",
            "message": f"R2 高度确认 {r2_decision}（prob={r2_probability:.3f} ≥ {confirmed_threshold}）。",
            "action": "render",
            "r1_decision": r1_decision,
            "r2_decision": r2_decision,
            "r1_probability": round(r1_probability, 6),
            "r2_probability": round(r2_probability, 6),
        }
    if r2_probability >= weakly_confirmed_threshold:
        return {
            "status": "weakly_confirmed",
            "message": (
                f"R2 弱确认 {r2_decision}（prob={r2_probability:.3f}，区间 "
                f"[{weakly_confirmed_threshold}, {confirmed_threshold})）；可出图但需在解读处加 caveat。"
            ),
            "action": "render_with_caveat",
            "r1_decision": r1_decision,
            "r2_decision": r2_decision,
            "r1_probability": round(r1_probability, 6),
            "r2_probability": round(r2_probability, 6),
        }
    return {
        "status": "uncertain",
        "message": (
            f"R2 后验 {r2_probability:.3f} < {weakly_confirmed_threshold}，命局结构尚有疑问；"
            "建议核对时辰 / 性别后再走 R3，或人工 caveat 出图。"
        ),
        "action": "escalate",
        "r1_decision": r1_decision,
        "r2_decision": r2_decision,
        "r1_probability": round(r1_probability, 6),
        "r2_probability": round(r2_probability, 6),
    }


# ============================================================================
# end of v8 phase decision
# ============================================================================


# ============================================================================
# end of Phase Inversion Detection
# ============================================================================


def _wuxing_count(pillars: List[Pillar]) -> Dict[str, float]:
    cnt: Dict[str, float] = {wx: 0.0 for wx in WUXING_ORDER}
    for i, p in enumerate(pillars):
        cnt[GAN_WUXING[p.gan]] += 1.0
        weight = 3.0 if i == 1 else 2.0
        for j, hg in enumerate(ZHI_HIDDEN_GAN[p.zhi]):
            cnt[GAN_WUXING[hg]] += weight * (1.0 if j == 0 else 0.3)
    return cnt


def _find_tongguan(pillars: List[Pillar]) -> Optional[str]:
    cnt = _wuxing_count(pillars)
    pairs = [
        ("木", "土", "火"),  # 木克土，火通关
        ("土", "水", "金"),  # 土克水，金通关
        ("水", "火", "木"),  # 水克火，木通关
        ("火", "金", "土"),  # 火克金，土通关
        ("金", "木", "水"),  # 金克木，水通关
    ]
    for a, b, mediator in pairs:
        if cnt[a] >= 3.0 and cnt[b] >= 3.0 and cnt[mediator] < 1.5:
            return mediator
    return None


# --- 大运起运 ---

def compute_qiyun_age_from_gregorian(date_str: str, gender: str) -> Optional[int]:
    """用 lunar-python 精确算起运岁。失败返回 None。

    `date_str` 可以是 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'。
    起运岁 = 距出生最近的节气到出生时刻的距离 / 3 天 = 1 年（顺行 / 逆行依阴阳男女）。
    """
    try:
        from lunar_python import Solar
    except ImportError:
        return None
    if " " in date_str:
        d, t = date_str.split(" ", 1)
    else:
        d, t = date_str, "12:00"
    try:
        y, mo, da = [int(x) for x in d.split("-")]
        hh, mm = [int(x) for x in t.split(":")]
        solar = Solar.fromYmdHms(y, mo, da, hh, mm, 0)
        lunar = solar.getLunar()
        ec = lunar.getEightChar()
        gender_int = 1 if gender.upper() in ("M", "MALE", "男") else 0
        yun = ec.getYun(gender_int)
        # getStartYear() = 起运虚岁；起运实岁 ≈ 虚岁 - 1
        # 实测对真太阳时影响不大；这里返回虚岁（中国传统命书一致）
        return int(yun.getStartYear())
    except Exception:
        return None


def get_dayun_sequence(
    pillars: List[Pillar],
    gender: str,
    birth_year: int,
    n_yun: int = 8,
    qiyun_age: int = 8,
) -> List[Dict]:
    """生成大运序列。

    `qiyun_age` 应由调用方计算精确值（通过 `compute_qiyun_age_from_gregorian` 或
    用户手动指定 `--qiyun-age`）。pillars 模式没有时分秒信息时，本函数无法精算，
    会沿用调用方传入的默认值（8 岁）—— 此时强烈建议用户从校验环节确认起运。
    方向按阴阳男女判断（阳男阴女顺行，阴男阳女逆行）。

    返回格式：[{ index, gan, zhi, start_age, start_year, end_age, end_year }, ...]
    """
    year_gan = pillars[0].gan
    month_gan = pillars[1].gan
    month_zhi = pillars[1].zhi

    yang = GAN_YIN_YANG[year_gan] == "阳"
    male = gender.upper() in ("M", "MALE", "男")
    forward = (yang and male) or (not yang and not male)

    # Find indices
    g_idx = GAN.index(month_gan)
    z_idx = ZHI.index(month_zhi)

    seq = []
    for i in range(n_yun):
        step = i + 1
        if forward:
            ng = GAN[(g_idx + step) % 10]
            nz = ZHI[(z_idx + step) % 12]
        else:
            ng = GAN[(g_idx - step) % 10]
            nz = ZHI[(z_idx - step) % 12]
        start_age = qiyun_age + i * 10
        start_year = birth_year + start_age
        seq.append({
            "index": i,
            "gan": ng,
            "zhi": nz,
            "start_age": start_age,
            "start_year": start_year,
            "end_age": start_age + 9,
            "end_year": start_year + 9,
        })

    return seq


def liunian_pillar(year: int) -> Pillar:
    """1984 = 甲子。计算公历年份对应的干支。"""
    base = 1984  # 甲子
    diff = year - base
    return Pillar(GAN[diff % 10], ZHI[diff % 12])


def is_fuyin(p1: Pillar, p2: Pillar) -> bool:
    return p1.gan == p2.gan and p1.zhi == p2.zhi


def is_fanyin(p1: Pillar, p2: Pillar) -> bool:
    """天克地冲"""
    g1_wx = GAN_WUXING[p1.gan]
    g2_wx = GAN_WUXING[p2.gan]
    g_ke = WUXING_KE[g1_wx] == g2_wx or WUXING_KE[g2_wx] == g1_wx
    z_chong = ZHI_CHONG.get(p1.zhi) == p2.zhi
    return g_ke and z_chong


# --- 校验：身份盲化 ---

class IdentityLeakError(ValueError):
    """Raised when input contains identity-revealing fields."""


_FORBIDDEN_KEYS = {
    "name", "nickname", "fullname", "first_name", "last_name",
    "job", "occupation", "profession", "company", "industry",
    "marriage", "spouse", "partner", "relationship",
    "education", "school", "degree",
    "history", "events", "past", "story", "experience",
}


def validate_blind_input(data: Dict) -> None:
    """Reject inputs that contain identity-revealing fields."""
    for k in data.keys():
        kl = k.lower().strip()
        if kl in _FORBIDDEN_KEYS:
            raise IdentityLeakError(
                f"Identity-revealing field '{k}' detected. "
                f"This skill enforces blind input: only pillars/gregorian + gender + birth_year allowed. "
                f"See references/fairness_protocol.md."
            )
