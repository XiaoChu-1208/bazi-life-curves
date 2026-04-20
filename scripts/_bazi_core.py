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
