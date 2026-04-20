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

    # 4 地支主气（月支权重 × 3，其他 × 2）
    for i, p in enumerate(pillars):
        weight = 3.0 if i == 1 else 2.0
        hidden = ZHI_HIDDEN_GAN[p.zhi]
        _count(GAN_WUXING[hidden[0]], weight)
        for sub in hidden[1:]:
            _count(GAN_WUXING[sub], weight * 0.3)

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

    return {
        "score": round(score, 2),
        "label": label,
        "in_season": in_season,
        "same": round(same, 2),
        "sheng": round(sheng, 2),
        "xie": round(xie, 2),
        "ke": round(ke, 2),
        "kewo": round(kewo, 2),
    }


# --- 燥湿独立画像（lessons learned 2026-04 后新增） ---
#
# 关键洞察（来自 1996 八字 丙子庚子己卯己巳 的失败经验）：
# 月令决定"季节寒暖"，但**天干能量场**才决定"体感和性格的明面表现"。
# 干头 = 丙庚己己（三土火金全燥）→ 实际是燥实命；
# 旧 select_yongshen 只看月令子水 + 身弱 → 错判用神为火土。
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
        label = "外燥内湿"           # 干头极燥 + 地支湿（如 1996 丙庚己己 + 双子）
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

    [改进 v2，2026-04，from 1996 八字失败教训]：
    - **燥实命**（climate.label = 燥实，总分 ≥ 4）→ 用神 = 水（润降），
      不论身强弱。同样身弱，燥实命用神是水；寒湿命才是火 —— 完全相反。
    - **寒湿命**（总分 ≤ -4）→ 用神 = 火（暖局），不论身强弱。
    - **偏燥 / 偏湿**：燥湿方向上微调（影响 jishen），主选用神仍按身强弱走。
    - **中和**：原 (强→克泄耗、弱→生扶、中和→调候) 规则。

    1996 八字（丙子庚子己卯己巳）失败案例：
    旧规则 → 月令子水 + 身弱 → 用神 = 火土（错）
    新规则 → 干头丙庚己己全燥 → 燥实命 → 用神 = 水（对，且匹配"从小怕热"体感）
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

    输入是 bazi.json 解析后的 dict（含 pillars / strength / climate / pillar_info）。
    输出 list 按 confidence 降序排序，仅 triggered=True 的进入。
    """
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi_dict["pillars"]]
    strength = bazi_dict["strength"]
    climate = bazi_dict.get("yongshen", {}).get("climate") or climate_profile(pillars)

    results = [
        detect_floating_day_master(pillars, strength),
        detect_dominating_god(pillars, strength),
        detect_climate_inversion(pillars, climate),
        detect_pseudo_following(pillars, strength),
        detect_three_qi_cheng_xiang(pillars, strength),
        detect_huaqi_pattern(pillars),
    ]
    triggered = [r for r in results if r["triggered"]]
    not_triggered = [r for r in results if not r["triggered"]]

    # v7.2 · 触发候选按置信度排序：先按 hit/total 比值降序，平手时按 hit 绝对值降序
    # （hit 越多 = 越多条件命中 = detector 内在更扎实），P4 没分数 → ratio=0.5/hit=0
    def _conf(det: Dict) -> tuple[float, int]:
        s = det.get("score", "")
        if not s or "/" not in str(s):
            return (0.5, 0)
        try:
            hit, tot = str(s).split("/")
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

def compute_qiyun_info_from_gregorian(date_str: str, gender: str) -> Optional[Dict]:
    """用 lunar-python 精确算起运信息。失败返回 None。

    `date_str` 可以是 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'。
    起运岁 = 距下一节气（顺行）/上一节气（逆行）到出生时刻的距离 / 3 天 = 1 年。

    返回 dict：
        {
          "qiyun_age_xu": int,        # 虚岁起运（lunar-python 的 getStartYear，向下取整）
          "qiyun_year_offset": float, # 起运实数岁（精确到月），用于推算大运换运年
          "qiyun_start_year": int,    # 第 1 步大运的精确换运公历年
          "qiyun_start_solar": str,   # 第 1 步大运的精确换运公历日期 'YYYY-MM-DD HH:MM:SS'
          "qiyun_age_real": int,      # 实岁起运（年数部分，向下取整），= qiyun_start_year - birth_year
        }
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
        start_solar = yun.getStartSolar()
        start_year_real = int(start_solar.getYear())
        return {
            "qiyun_age_xu": int(yun.getStartYear()),
            "qiyun_year_offset": (
                int(yun.getStartYear()) + int(yun.getStartMonth()) / 12.0
                + int(yun.getStartDay()) / 365.25
            ),
            "qiyun_start_year": start_year_real,
            "qiyun_start_solar": start_solar.toYmdHms(),
            "qiyun_age_real": start_year_real - y,
        }
    except Exception:
        return None


def compute_qiyun_age_from_gregorian(date_str: str, gender: str) -> Optional[int]:
    """[向后兼容] 返回起运虚岁。新代码请用 compute_qiyun_info_from_gregorian。"""
    info = compute_qiyun_info_from_gregorian(date_str, gender)
    if info is None:
        return None
    return info["qiyun_age_xu"]


def get_dayun_sequence(
    pillars: List[Pillar],
    gender: str,
    birth_year: int,
    n_yun: int = 8,
    qiyun_age: int = 8,
    qiyun_start_year: Optional[int] = None,
) -> List[Dict]:
    """生成大运序列。

    `qiyun_age` 应由调用方计算精确值（通过 `compute_qiyun_age_from_gregorian` 或
    用户手动指定 `--qiyun-age`）。pillars 模式没有时分秒信息时，本函数无法精算，
    会沿用调用方传入的默认值（8 岁）—— 此时强烈建议用户从校验环节确认起运。
    方向按阴阳男女判断（阳男阴女顺行，阴男阳女逆行）。

    `qiyun_start_year`（v7.7 新增）：第 1 步大运的精确换运公历年（来自
    lunar-python 的 yun.getStartSolar().getYear()）。若提供则**优先使用**，
    避免「虚岁向下取整 + birth_year + qiyun_age 简化算法」造成的 ±1 年偏差
    （典型场景：起运 9 年 5 个月，简化算法会输出 1996+9=2005，但实际换运在
    2006-05，其他主流软件都标 2006）。

    返回格式：[{ index, gan, zhi, start_age, start_year, end_age, end_year }, ...]
    """
    year_gan = pillars[0].gan
    month_gan = pillars[1].gan
    month_zhi = pillars[1].zhi

    yang = GAN_YIN_YANG[year_gan] == "阳"
    male = gender.upper() in ("M", "MALE", "男")
    forward = (yang and male) or (not yang and not male)

    g_idx = GAN.index(month_gan)
    z_idx = ZHI.index(month_zhi)

    # 优先使用精确换运年；否则退回简化算法
    if qiyun_start_year is not None:
        first_start_year = qiyun_start_year
        first_start_age = qiyun_start_year - birth_year
    else:
        first_start_age = qiyun_age
        first_start_year = birth_year + qiyun_age

    seq = []
    for i in range(n_yun):
        step = i + 1
        if forward:
            ng = GAN[(g_idx + step) % 10]
            nz = ZHI[(z_idx + step) % 12]
        else:
            ng = GAN[(g_idx - step) % 10]
            nz = ZHI[(z_idx - step) % 12]
        start_age = first_start_age + i * 10
        start_year = first_start_year + i * 10
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
