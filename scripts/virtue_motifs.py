"""virtue_motifs.py · 第三条独立叙事通道（脚本侧）

读取 `bazi.json` + `curves.json`，按 `_virtue_registry.MOTIFS` 的 38 条母题
跑结构性检测，输出 `output/virtue_motifs.json`，供 LLM 在 `life_review` 6 个
写作位置（详见 `references/virtue_recurrence_protocol.md`）使用。

零数字污染铁律：本脚本**不**修改 `score_curves.py` / `mangpai_events.py` 的
任何字段，只**读取**它们的产物，并**追加**第三层叙事通道的结构。

输出 schema（`virtue_motifs/v1`）：

    {
        "version": 1,
        "schema": "virtue_motifs/v1",
        "input_signature": {...},
        "complexity_score": 0.0-1.0,
        "love_letter_eligible": bool,    # 位置 ⑤ 触发
        "blessing_path": bool,           # 命好路径（命主全部 motif gravity ≤ gentle）
        "convergence_hint": str,         # 给 LLM 的母题聚合提示（不下定论）
        "triggered_motifs": [...],       # 强度 ≥ threshold 的母题
        "motif_recurrence_map": {...},   # {motif_id: [activation_point, ...]}
        "silenced_motifs": [...],        # catalog 内、未触发的 motif_id
        "convergence_years": [...]       # 流年 ≥3 母题汇聚的年份（位置 ③ 触发依据）
    }

本脚本是 pure function：相同输入 → 字节相同输出（bit-for-bit）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _virtue_registry import (  # noqa: E402
    MOTIFS,
    MotifSpec,
    DetectResult,
    ActivationPoint,
    GRAVITY_RANK,
    gravity_max,
    get_motif_by_id,
)


# ---------------------------------------------------------------------------
# Frozen view objects（避免对外部 dict 的偶发修改）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CtxView:
    """一份命主上下文的只读视图。所有 detector 仅读这个对象。"""
    bazi: Dict[str, Any]
    curves: Dict[str, Any]

    @property
    def pillars(self) -> List[Dict[str, str]]:
        return self.bazi.get("pillars", [])

    @property
    def pillar_info(self) -> List[Dict[str, str]]:
        return self.bazi.get("pillar_info", [])

    @property
    def day_master(self) -> str:
        return self.bazi.get("day_master", "")

    @property
    def day_master_wuxing(self) -> str:
        return self.bazi.get("day_master_wuxing", "")

    @property
    def strength(self) -> Dict[str, Any]:
        return self.bazi.get("strength", {})

    @property
    def yongshen(self) -> Dict[str, Any]:
        return self.bazi.get("yongshen", {}) or self.curves.get("yongshen", {})

    @property
    def wuxing_distribution(self) -> Dict[str, Dict[str, Any]]:
        return self.bazi.get("wuxing_distribution", {})

    @property
    def geju(self) -> Dict[str, Any]:
        return self.curves.get("geju", {})

    @property
    def shensha(self) -> Dict[str, Any]:
        return self.curves.get("shensha", {})

    @property
    def relationship_mode(self) -> Dict[str, Any]:
        return self.curves.get("relationship_mode", {})

    @property
    def points(self) -> List[Dict[str, Any]]:
        return self.curves.get("points", [])

    @property
    def dayun_segments(self) -> List[Dict[str, Any]]:
        return self.curves.get("dayun_segments", [])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _shishen_count(ctx: CtxView, targets) -> int:
    if isinstance(targets, str):
        targets = {targets}
    else:
        targets = set(targets)
    n = 0
    for p in ctx.pillar_info:
        if p.get("gan_shishen") in targets:
            n += 1
        if p.get("zhi_shishen") in targets:
            n += 1
    return n


def _has_shishen(ctx: CtxView, targets) -> bool:
    return _shishen_count(ctx, targets) > 0


def _gan_shishen_count(ctx: CtxView, targets) -> int:
    if isinstance(targets, str):
        targets = {targets}
    return sum(1 for p in ctx.pillar_info if p.get("gan_shishen") in set(targets))


def _zhi_shishen_count(ctx: CtxView, targets) -> int:
    if isinstance(targets, str):
        targets = {targets}
    return sum(1 for p in ctx.pillar_info if p.get("zhi_shishen") in set(targets))


def _shensha_found(ctx: CtxView, key: str) -> bool:
    sh = ctx.shensha.get(key, {})
    return bool(sh.get("found"))


def _mangpai_event_years(ctx: CtxView, key: str) -> List[Tuple[int, int, str, str]]:
    """返回 (age, year, dayun, evidence) 四元组列表。"""
    out = []
    for pt in ctx.points:
        for ev in pt.get("mangpai_events", []) or []:
            if ev.get("key") == key:
                out.append((
                    int(pt["age"]),
                    int(pt["year"]),
                    str(pt.get("dayun", "")),
                    str(ev.get("canonical_event") or ev.get("name") or key),
                ))
    return out


def _cumulative_mean(ctx: CtxView, field: str, age_max: int = 60) -> float:
    vals = [pt.get(field) for pt in ctx.points if pt.get("age") is not None and pt["age"] <= age_max and pt.get(field) is not None]
    return sum(vals) / len(vals) if vals else 0.0


def _yearly_below_baseline_count(ctx: CtxView, field: str, baseline_field: str, delta: float, age_min: int = 0, age_max: int = 60) -> int:
    baseline = ctx.curves.get("baseline", {}).get(baseline_field, 50.0)
    n = 0
    for pt in ctx.points:
        a = pt.get("age")
        v = pt.get(field)
        if a is None or v is None:
            continue
        if not (age_min <= a <= age_max):
            continue
        if v <= baseline - delta:
            n += 1
    return n


def _dayun_for_age(ctx: CtxView, age: int) -> str:
    for seg in ctx.dayun_segments:
        if seg.get("start_age", 0) <= age <= seg.get("end_age", 0):
            return seg.get("label", "")
    return "起运前"


def _midpoints_per_dayun(ctx: CtxView) -> List[Tuple[int, int, str]]:
    """每段大运取一个中点 (age, year, dayun_label)。给持续音类母题用。"""
    out = []
    for seg in ctx.dayun_segments:
        a0 = seg.get("start_age", 0)
        a1 = seg.get("end_age", 0)
        y0 = seg.get("start_year", 0)
        mid = (a0 + a1) // 2
        out.append((mid, y0 + (mid - a0), seg.get("label", "")))
    return out


def _structural_activation_points(ctx: CtxView, basis: str) -> List[ActivationPoint]:
    """持续音类 / 静态结构母题的激活点：每段大运中点（source='structural'）。"""
    return [ActivationPoint(a, y, d, basis, "structural") for a, y, d in _midpoints_per_dayun(ctx)]


def _event_ap(age: int, year: int, dayun: str, basis: str) -> ActivationPoint:
    """事件驱动激活点（真实流年应期，参与 convergence_year 计算）。"""
    return ActivationPoint(age, year, dayun, basis, "event")


# ---------------------------------------------------------------------------
# Detectors · 38 条
# ---------------------------------------------------------------------------

# Each detector returns DetectResult.

def detect_A1(ctx: CtxView) -> DetectResult:
    """共济：比劫 ≥ 2 + 日干强 + 日干五行 ratio ≥ 0.30。
    A2 同时强触发时降权。"""
    bj = _shishen_count(ctx, {"比肩", "劫财"})
    label = ctx.strength.get("label", "")
    day_wx = ctx.day_master_wuxing
    ratio = ctx.wuxing_distribution.get(day_wx, {}).get("ratio", 0.0)
    if bj < 2 or label not in ("强", "中和") or ratio < 0.30:
        return DetectResult.negative()
    intensity = min(1.0, 0.4 + 0.15 * bj + (0.1 if label == "强" else 0.0))
    # A2 同时强触发时降级（避免冲突）
    a2 = detect_A2(ctx)
    if a2.triggered and a2.intensity > 0.55:
        intensity = min(intensity, 0.45)
    spirit_mean = _cumulative_mean(ctx, "spirit_cumulative")
    gravity = "jubilant" if spirit_mean >= 65 else None
    basis = f"比劫{bj}见 + 日干{label} + {day_wx}占{ratio:.0%}"
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        gravity)


def detect_A2(ctx: CtxView) -> DetectResult:
    """富者代管：财 ≥ 2 + 日干弱 + 非真从财格。"""
    cai = _shishen_count(ctx, {"正财", "偏财"})
    label = ctx.strength.get("label", "")
    score = float(ctx.strength.get("score", 0.0))
    geju_primary = ctx.geju.get("primary") or ""
    if cai < 2 or "从财" in geju_primary:
        return DetectResult.negative()
    if not (label == "弱" or score < 25):
        return DetectResult.negative()
    weak_bonus = 1 if label == "弱" else 0.5
    year_cai = ctx.pillar_info[0].get("zhi_shishen") in ("正财", "偏财") if ctx.pillar_info else False
    intensity = min(1.0, 0.45 + 0.12 * (cai - 2) + 0.15 * weak_bonus + (0.1 if year_cai else 0.0))
    # 财官 / 日主 ≥ 3 → tragic
    same = float(ctx.strength.get("same", 1.0)) or 1.0
    cai_score = ctx.wuxing_distribution.get(_wx_of_cai(ctx), {}).get("score", 0.0)
    gravity = "tragic" if same > 0 and cai_score / same >= 3.0 else None
    basis = f"财{cai}透 + 日干{label}（score={score}）"
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        gravity)


def _wx_of_cai(ctx: CtxView) -> str:
    """日主所克的五行 = 财。"""
    from _bazi_core import WUXING_KE  # type: ignore
    return WUXING_KE.get(ctx.day_master_wuxing, "")


def detect_A3(ctx: CtxView) -> DetectResult:
    """长子长女债：多重官杀印 + 年柱有官/杀 + 日干弱或月令印旺。"""
    guansha = _shishen_count(ctx, {"正官", "七杀"})
    yin = _gan_shishen_count(ctx, {"正印", "偏印"})
    if guansha < 2 or yin < 1:
        return DetectResult.negative()
    if not ctx.pillar_info:
        return DetectResult.negative()
    year = ctx.pillar_info[0]
    year_has_gs = year.get("gan_shishen") in ("正官", "七杀") or year.get("zhi_shishen") in ("正官", "七杀")
    if not year_has_gs:
        return DetectResult.negative()
    label = ctx.strength.get("label", "")
    yueling_yin = len(ctx.pillar_info) >= 2 and ctx.pillar_info[1].get("zhi_shishen") in ("正印", "偏印")
    if not (label == "弱" or yueling_yin):
        return DetectResult.negative()
    day_zhi_pyin = len(ctx.pillar_info) >= 3 and ctx.pillar_info[2].get("zhi_shishen") == "偏印"
    intensity = min(1.0, 0.4 + 0.1 * guansha + 0.1 + (0.08 if day_zhi_pyin else 0.0))
    # 早年 emotion 多次低 → tragic
    early_emo_dip = _yearly_below_baseline_count(ctx, "emotion_yearly", "emotion", 10.0, age_min=0, age_max=15)
    gravity = "tragic" if early_emo_dip >= 3 else None
    basis = f"官杀{guansha}见 + 年柱有官杀 + {label or '月令印旺'}"
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        gravity)


def detect_B1(ctx: CtxView) -> DetectResult:
    """说真话的代价：原局有伤官 + shang_guan_jian_guan 应期 ≥ 2 次。"""
    sg = _has_shishen(ctx, "伤官")
    events = _mangpai_event_years(ctx, "shang_guan_jian_guan")
    if not sg or len(events) < 2:
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + 0.12 * len(events))
    aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in events)
    # ≥ 4 次且伴随 emotion 跌 → tragic
    emo_dip = _yearly_below_baseline_count(ctx, "emotion_yearly", "emotion", 10.0)
    gravity = "tragic" if len(events) >= 4 and emo_dip >= 5 else None
    return DetectResult(True, round(intensity, 4), aps, gravity)


def detect_B2(ctx: CtxView) -> DetectResult:
    """复杂忠诚：guan_sha_hun_za 应期 ≥ 1，或原局正官+七杀同在。"""
    events = _mangpai_event_years(ctx, "guan_sha_hun_za")
    natal_both = _has_shishen(ctx, "正官") and _has_shishen(ctx, "七杀")
    if len(events) < 1 and not natal_both:
        return DetectResult.negative()
    # 年支与月支冲
    year_yue_chong = False
    if len(ctx.pillar_info) >= 2:
        from _bazi_core import ZHI_CHONG  # type: ignore
        if ZHI_CHONG.get(ctx.pillar_info[0].get("zhi", "")) == ctx.pillar_info[1].get("zhi", ""):
            year_yue_chong = True
    intensity = min(1.0, 0.4 + 0.12 * len(events) + 0.08 * year_yue_chong + (0.1 if natal_both else 0.0))
    if intensity < 0.4:
        return DetectResult.negative()
    if events:
        aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in events)
    else:
        aps = tuple(_structural_activation_points(ctx, "原局官杀同在"))
    emo_below = _cumulative_mean(ctx, "emotion_cumulative") < ctx.curves.get("baseline", {}).get("emotion", 50.0)
    gravity = "tragic" if emo_below else None
    return DetectResult(True, round(intensity, 4), aps, gravity)


def detect_B3(ctx: CtxView) -> DetectResult:
    """受冤的克制：官星受伤 + 印护身 + 25-50 岁段 shang_guan_jian_guan 且无 qi_sha_feng_yin 抵消。"""
    has_zheng = _has_shishen(ctx, "正官")
    has_yin_protect = bool(ctx.geju.get("has_yin_protect"))
    if not (has_zheng and has_yin_protect):
        return DetectResult.negative()
    sgjg = [ev for ev in _mangpai_event_years(ctx, "shang_guan_jian_guan") if 25 <= ev[0] <= 50]
    qsfy = [ev for ev in _mangpai_event_years(ctx, "qi_sha_feng_yin") if 25 <= ev[0] <= 50]
    if not sgjg or qsfy:
        return DetectResult.negative()
    geju_p = ctx.geju.get("primary") or ""
    if "杀印相生" in geju_p:
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + 0.15 + 0.1 * len(sgjg))
    aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in sgjg)
    return DetectResult(True, round(intensity, 4), aps, None)


def detect_C1(ctx: CtxView) -> DetectResult:
    """替天下负重：七杀 ≥ 2 + 日干弱 + 无食神制杀 + 同年 emotion+spirit 同跌的年份 ≥ 1。"""
    qisha = _shishen_count(ctx, "七杀")
    label = ctx.strength.get("label", "")
    has_shishen_food = _has_shishen(ctx, "食神")
    if qisha < 2 or label != "弱":
        return DetectResult.negative()
    if has_shishen_food:
        return DetectResult.negative()
    base_emo = ctx.curves.get("baseline", {}).get("emotion", 50.0)
    base_spi = ctx.curves.get("baseline", {}).get("spirit", 50.0)
    crash = []
    for pt in ctx.points:
        e = pt.get("emotion_yearly")
        s = pt.get("spirit_yearly")
        if e is None or s is None:
            continue
        if e <= base_emo - 15 and s <= base_spi - 15:
            crash.append((int(pt["age"]), int(pt["year"]), str(pt.get("dayun", ""))))
    if not crash:
        return DetectResult.negative()
    intensity = min(1.0, 0.55 + 0.1 * (qisha - 1) + 0.15)  # 无食神制杀 → +0.15
    aps = tuple(_event_ap(a, y, d, "emotion+spirit 同跌：七杀压身应期") for a, y, d in crash)
    return DetectResult(True, round(intensity, 4), aps, None)


def detect_C2(ctx: CtxView) -> DetectResult:
    """创业者对兄弟的债：bi_jie_duo_cai 触发 ≥ 1 + 比劫与财天干贴近。"""
    events = _mangpai_event_years(ctx, "bi_jie_duo_cai")
    if not events:
        return DetectResult.negative()
    # 比劫与财同柱或邻柱
    bj_pos = [i for i, p in enumerate(ctx.pillar_info) if p.get("gan_shishen") in ("比肩", "劫财")]
    cai_pos = [i for i, p in enumerate(ctx.pillar_info) if p.get("gan_shishen") in ("正财", "偏财")]
    adjacent = any(abs(b - c) <= 1 for b in bj_pos for c in cai_pos)
    year_bj = ctx.pillar_info and ctx.pillar_info[0].get("gan_shishen") in ("比肩", "劫财")
    intensity = min(1.0, 0.4 + 0.12 * len(events) + (0.08 if adjacent else 0.0) + (0.08 if year_bj else 0.0))
    aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in events)
    base_w = ctx.curves.get("baseline", {}).get("wealth", 50.0)
    w_dip = _yearly_below_baseline_count(ctx, "wealth_yearly", "wealth", 10.0)
    gravity = "serious" if len(events) >= 3 and w_dip >= 5 else None
    return DetectResult(True, round(intensity, 4), aps, gravity)


def detect_C3(ctx: CtxView) -> DetectResult:
    """看护者的隐性消耗：印为忌神（粗略：日干强 + 印仍透）或日支偏印。"""
    label = ctx.strength.get("label", "")
    yin = _gan_shishen_count(ctx, {"正印", "偏印"})
    yongshen_jishen = ctx.yongshen.get("jishen", "")
    yin_is_ji = "印" in yongshen_jishen if yongshen_jishen else False
    yin_is_ji = yin_is_ji or (label == "强" and yin >= 1)
    day_zhi_pyin = len(ctx.pillar_info) >= 3 and ctx.pillar_info[2].get("zhi_shishen") == "偏印"
    if not (yin_is_ji or day_zhi_pyin):
        return DetectResult.negative()
    intensity = min(1.0, 0.4 + (0.1 if yin_is_ji else 0.0) + (0.1 if day_zhi_pyin else 0.0))
    if intensity < 0.4:
        return DetectResult.negative()
    emo_mean = _cumulative_mean(ctx, "emotion_cumulative")
    base_e = ctx.curves.get("baseline", {}).get("emotion", 50.0)
    gravity = "serious" if emo_mean < base_e - 10 else None
    basis = "印为忌神 / 枭印夺食" if yin_is_ji else "日支偏印"
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        gravity)


def detect_D1(ctx: CtxView) -> DetectResult:
    """出世入世的两难：印重 + 食伤受制；或 华盖 + 印星单透。"""
    yin = _gan_shishen_count(ctx, {"正印", "偏印"})
    shishang = _shishen_count(ctx, {"食神", "伤官"})
    yin_heavy = yin >= 2 and shishang <= 2
    huagai = _shensha_found(ctx, "huagai")
    yin_single = yin == 1 and huagai
    if not (yin_heavy or yin_single):
        return DetectResult.negative()
    kongwang_chart = ctx.shensha.get("kongwang", {}).get("in_chart", []) or []
    day_zhi = ctx.pillar_info[2].get("zhi") if len(ctx.pillar_info) >= 3 else ""
    day_kong = day_zhi in kongwang_chart
    intensity = min(1.0, 0.45 + (0.1 if yin_heavy else 0.0) + (0.1 if huagai else 0.0) + (0.12 if day_kong else 0.0))
    basis = ("印重食伤受制" if yin_heavy else "华盖+印星单透") + ("（日支空亡加成）" if day_kong else "")
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        None)


def detect_D2(ctx: CtxView) -> DetectResult:
    """慢工敬源：印 ≥ 2 + 食伤无透。"""
    yin = _gan_shishen_count(ctx, {"正印", "偏印"})
    shishang_gan = _gan_shishen_count(ctx, {"食神", "伤官"})
    if yin < 2 or shishang_gan > 0:
        return DetectResult.negative()
    tianyi = _shensha_found(ctx, "tianyi_guiren")
    intensity = min(1.0, 0.4 + 0.1 * (yin - 2) + 0.1 + (0.05 if tianyi else 0.0))
    basis = f"印星{yin}透 + 食伤无透" + ("（天乙加成）" if tianyi else "")
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        None)


def detect_D3(ctx: CtxView) -> DetectResult:
    """师承断绝：印星受冲（流年印冲日支或印柱地支被冲）+ 食伤旺。"""
    shishang = _shishen_count(ctx, {"食神", "伤官"})
    if shishang < 2:
        return DetectResult.negative()
    # 检测原局印柱地支在大运/流年中被冲的次数
    from _bazi_core import ZHI_CHONG  # type: ignore
    yin_zhi_set = set()
    for p in ctx.pillar_info:
        if p.get("zhi_shishen") in ("正印", "偏印"):
            yin_zhi_set.add(p.get("zhi"))
    if not yin_zhi_set:
        return DetectResult.negative()
    chong_years: List[Tuple[int, int, str, str]] = []
    for pt in ctx.points:
        ganzhi = pt.get("ganzhi", "")
        if len(ganzhi) >= 2:
            ln_zhi = ganzhi[1]
            for yz in yin_zhi_set:
                if ZHI_CHONG.get(yz) == ln_zhi:
                    chong_years.append((int(pt["age"]), int(pt["year"]),
                                         str(pt.get("dayun", "")),
                                         f"流年{ln_zhi}冲原局印星{yz}"))
                    break
    if not chong_years:
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + 0.05 * len(chong_years) + (0.1 if shishang >= 2 else 0.0))
    aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in chong_years[:8])
    return DetectResult(True, round(intensity, 4), aps, None)


def detect_E1(ctx: CtxView) -> DetectResult:
    """结构性孤独（持续音类）：孤辰寡宿同见 / 华盖 ≥ 2 / emotion_cumulative 60 岁均值低。"""
    guchen = _shensha_found(ctx, "guchen")
    guasu = _shensha_found(ctx, "guasu")
    huagai_chart = ctx.shensha.get("huagai", {}).get("in_chart", []) or []
    huagai_multi = len(huagai_chart) >= 2
    emo_mean = _cumulative_mean(ctx, "emotion_cumulative")
    base_e = ctx.curves.get("baseline", {}).get("emotion", 50.0)
    emo_low = emo_mean < base_e - 10
    if not (guchen and guasu) and not huagai_multi and not emo_low:
        return DetectResult.negative()
    day_zhi = ctx.pillar_info[2].get("zhi") if len(ctx.pillar_info) >= 3 else ""
    day_guhua = day_zhi in (ctx.shensha.get("guchen", {}).get("in_chart", []) or []) \
                or day_zhi in (ctx.shensha.get("guasu", {}).get("in_chart", []) or [])
    intensity = min(1.0, 0.5 + (0.15 if guchen and guasu else 0.0) + (0.1 if huagai_multi else 0.0) + (0.1 if day_guhua else 0.0) + (0.05 if emo_low else 0.0))
    parts = []
    if guchen and guasu:
        parts.append("孤辰寡宿同见")
    if huagai_multi:
        parts.append("华盖叠见")
    if emo_low:
        parts.append("emotion 长期低于基线")
    basis = " · ".join(parts) or "结构性孤独"
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, basis)),
                        None)


def detect_E2(ctx: CtxView) -> DetectResult:
    """人群中的孤独：日支孤辰 + 比劫 ≥ 2 透。"""
    from _bazi_core import GUCHEN_GUASU  # type: ignore
    if len(ctx.pillar_info) < 3:
        return DetectResult.negative()
    year_zhi = ctx.pillar_info[0].get("zhi", "")
    day_zhi = ctx.pillar_info[2].get("zhi", "")
    if year_zhi not in GUCHEN_GUASU:
        return DetectResult.negative()
    if GUCHEN_GUASU[year_zhi][0] != day_zhi:
        return DetectResult.negative()
    bijie_gan = _gan_shishen_count(ctx, {"比肩", "劫财"})
    if bijie_gan < 2:
        return DetectResult.negative()
    intensity = min(1.0, 0.45 + 0.12 + 0.08 * (bijie_gan - 1))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, f"日支孤辰{day_zhi} + 比劫{bijie_gan}透")),
                        None)


def detect_E3(ctx: CtxView) -> DetectResult:
    """亲密中的无能：日支多次被冲 / 配偶宫不安 / relationship_mode ∈ {ambiguous_dynamic, low_density}。"""
    from _bazi_core import ZHI_CHONG  # type: ignore
    if len(ctx.pillar_info) < 3:
        return DetectResult.negative()
    day_zhi = ctx.pillar_info[2].get("zhi", "")
    chong_count = 0
    chong_years: List[Tuple[int, int, str, str]] = []
    for pt in ctx.points:
        ganzhi = pt.get("ganzhi", "")
        if len(ganzhi) >= 2 and ZHI_CHONG.get(day_zhi) == ganzhi[1]:
            chong_count += 1
            chong_years.append((int(pt["age"]), int(pt["year"]),
                                str(pt.get("dayun", "")), f"流年{ganzhi[1]}冲日支{day_zhi}"))
    year_zhi = ctx.pillar_info[0].get("zhi", "")
    yue_zhi = ctx.pillar_info[1].get("zhi", "") if len(ctx.pillar_info) >= 2 else ""
    pei_unrest = ZHI_CHONG.get(day_zhi) in (year_zhi, yue_zhi)
    rmode = ctx.relationship_mode.get("primary_mode", "")
    rmode_hit = rmode in ("ambiguous_dynamic", "low_density")
    if chong_count < 3 and not pei_unrest and not rmode_hit:
        return DetectResult.negative()
    intensity = min(1.0, 0.4 + 0.05 * min(chong_count, 6) + (0.1 if pei_unrest else 0.0) + (0.1 if rmode_hit else 0.0))
    if chong_years:
        aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in chong_years[:8])
    else:
        aps = tuple(_structural_activation_points(ctx, f"配偶宫不安 / relationship_mode={rmode}"))
    return DetectResult(True, round(intensity, 4), aps, None)


def detect_E4(ctx: CtxView) -> DetectResult:
    """漂泊者的根问题：驿马 / lu_chong ≥ 2 / 日支与年支冲。"""
    from _bazi_core import ZHI_CHONG  # type: ignore
    yima = _shensha_found(ctx, "yima")
    lu_events = _mangpai_event_years(ctx, "lu_chong")
    yz = ctx.pillar_info[0].get("zhi", "") if ctx.pillar_info else ""
    dz = ctx.pillar_info[2].get("zhi", "") if len(ctx.pillar_info) >= 3 else ""
    yr_day_chong = ZHI_CHONG.get(yz) == dz
    if not yima and len(lu_events) < 2 and not yr_day_chong:
        return DetectResult.negative()
    intensity = min(1.0, 0.4 + (0.12 if yima else 0.0) + 0.08 * len(lu_events) + (0.08 if yr_day_chong else 0.0))
    if lu_events:
        aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in lu_events)
    else:
        basis_parts = [s for s, ok in [("驿马", yima), ("年日相冲", yr_day_chong)] if ok]
        aps = tuple(_structural_activation_points(ctx, " / ".join(basis_parts) or "漂泊"))
    gravity = "serious" if len(lu_events) >= 3 else None
    return DetectResult(True, round(intensity, 4), aps, gravity)


def detect_F1(ctx: CtxView) -> DetectResult:
    """拒绝纯变现：食神透 + 财星不通根（无气）。"""
    shishen_gan = _gan_shishen_count(ctx, "食神")
    if shishen_gan < 1:
        return DetectResult.negative()
    cai_score = sum(ctx.wuxing_distribution.get(_wx_of_cai(ctx), {}).get("score", 0.0) for _ in [0])
    cai_weak = cai_score < 1.5
    if not cai_weak:
        return DetectResult.negative()
    wenchang = _shensha_found(ctx, "wenchang")
    intensity = min(1.0, 0.4 + 0.1 + (0.08 if wenchang else 0.0))
    spirit_mean = _cumulative_mean(ctx, "spirit_cumulative")
    wealth_mean = _cumulative_mean(ctx, "wealth_cumulative")
    base_w = ctx.curves.get("baseline", {}).get("wealth", 50.0)
    base_s = ctx.curves.get("baseline", {}).get("spirit", 50.0)
    gravity = "serious" if wealth_mean < base_w - 10 and spirit_mean < base_s else None
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "食神不就财（财无气）")),
                        gravity)


def detect_F2(ctx: CtxView) -> DetectResult:
    """创作者的物质焦虑：伤官+食神+财星都在 + 日干弱；或 wealth dip 多 + spirit 高。"""
    sg = _has_shishen(ctx, "伤官")
    sn = _has_shishen(ctx, "食神")
    cai = _has_shishen(ctx, {"正财", "偏财"})
    label = ctx.strength.get("label", "")
    base_w = ctx.curves.get("baseline", {}).get("wealth", 50.0)
    base_s = ctx.curves.get("baseline", {}).get("spirit", 50.0)
    w_dip = _yearly_below_baseline_count(ctx, "wealth_yearly", "wealth", 15.0)
    spirit_mean = _cumulative_mean(ctx, "spirit_cumulative")
    spirit_high = spirit_mean >= base_s
    triple_weak = sg and sn and cai and label == "弱"
    talent_pattern = w_dip >= 5 and spirit_high
    if not (triple_weak or talent_pattern):
        return DetectResult.negative()
    year_cai = ctx.pillar_info and (ctx.pillar_info[0].get("gan_shishen") in ("正财", "偏财")
                                     or ctx.pillar_info[0].get("zhi_shishen") in ("正财", "偏财"))
    intensity = min(1.0, 0.45 + (0.1 if triple_weak else 0.0)
                    + (0.1 if w_dip >= 5 else 0.0)
                    + (0.08 if year_cai else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "伤官+食神+财 / wealth dip + spirit 高")),
                        None)


def detect_F3(ctx: CtxView) -> DetectResult:
    """市场里的手艺人尊严：食伤生财 + 日干弱。粗：食伤 ≥ 1 + 财 ≥ 1 + 日干弱。"""
    if ctx.strength.get("label") != "弱":
        return DetectResult.negative()
    if not (_has_shishen(ctx, {"食神", "伤官"}) and _has_shishen(ctx, {"正财", "偏财"})):
        return DetectResult.negative()
    pian_cai_gan = _gan_shishen_count(ctx, "偏财") == 0
    intensity = min(1.0, 0.4 + 0.08 + 0.1 + (0.05 if pian_cai_gan else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "食伤生财 + 日干弱")),
                        None)


def detect_G1(ctx: CtxView) -> DetectResult:
    """不和稀泥：羊刃在原局。"""
    from _bazi_core import GAN_YIN_YANG  # type: ignore
    YANGREN_TABLE = {
        "甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子",
        "乙": "寅", "丁": "巳", "己": "巳", "辛": "申", "癸": "亥",
    }
    dm = ctx.day_master
    if dm not in YANGREN_TABLE:
        return DetectResult.negative()
    yr_zhi = YANGREN_TABLE[dm]
    in_chart = any(p.get("zhi") == yr_zhi for p in ctx.pillar_info)
    if not in_chart:
        return DetectResult.negative()
    qisha = _has_shishen(ctx, "七杀")
    intensity = min(1.0, 0.4 + 0.12 + (0.1 if qisha else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, f"羊刃{yr_zhi}在原局")),
                        None)


def detect_G2(ctx: CtxView) -> DetectResult:
    """强者的克制：羊刃 + 七杀同在但无 yangren_chong 烈度高的爆发；或日干极强 + emotion 平稳。"""
    g1 = detect_G1(ctx)
    qisha = _has_shishen(ctx, "七杀")
    yangren_events = _mangpai_event_years(ctx, "yangren_chong")
    label = ctx.strength.get("label", "")
    score = float(ctx.strength.get("score", 0.0))
    base_e = ctx.curves.get("baseline", {}).get("emotion", 50.0)
    emo_mean = _cumulative_mean(ctx, "emotion_cumulative")
    calm = emo_mean >= base_e - 5
    cond_a = g1.triggered and qisha and len(yangren_events) <= 1
    cond_b = score >= 35 and calm
    if not (cond_a or cond_b):
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + (0.12 if cond_a else 0.0) + (0.1 if cond_b else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "刃杀同在不动手 / 极强而平静")),
                        None)


def detect_G3(ctx: CtxView) -> DetectResult:
    """硬命人对柔软的渴望：魁罡候选日柱（庚辰/庚戌/壬辰/戊戌）或日干极强 + 七杀透。"""
    if len(ctx.pillar_info) < 3:
        return DetectResult.negative()
    day = ctx.pillar_info[2]
    day_gz = (day.get("gan", ""), day.get("zhi", ""))
    kuigang = day_gz in {("庚", "辰"), ("庚", "戌"), ("壬", "辰"), ("戊", "戌")}
    score = float(ctx.strength.get("score", 0.0))
    qi_gan = _gan_shishen_count(ctx, "七杀") >= 1
    if not (kuigang or (score >= 35 and qi_gan)):
        return DetectResult.negative()
    base_e = ctx.curves.get("baseline", {}).get("emotion", 50.0)
    emo_low = _cumulative_mean(ctx, "emotion_cumulative") < base_e
    intensity = min(1.0, 0.45 + (0.1 if kuigang else 0.0) + (0.1 if emo_low else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "魁罡候选 / 极强+七杀")),
                        None)


def detect_H1(ctx: CtxView) -> DetectResult:
    """全身委身：geju 含化气/专旺/从格 或 五行高度集中（max ratio ≥ 0.5）。"""
    primary = ctx.geju.get("primary") or ""
    huaqi = any(k in primary for k in ("化气", "专旺", "从格", "从财", "从官", "从儿", "从势"))
    max_ratio = max((v.get("ratio", 0.0) for v in ctx.wuxing_distribution.values()), default=0.0)
    concentrated = max_ratio >= 0.5
    if not (huaqi or concentrated):
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + (0.15 if huaqi else 0.0) + (0.1 if concentrated else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, f"格局={primary or '五行集中'} max_ratio={max_ratio:.2f}")),
                        None)


def detect_H2(ctx: CtxView) -> DetectResult:
    """副业人的诚实：杂气格（月令四库 + 多十神兼透）或五行均匀（std < 0.08）。"""
    if len(ctx.pillar_info) < 2:
        return DetectResult.negative()
    yue_zhi = ctx.pillar_info[1].get("zhi", "")
    siku = yue_zhi in ("辰", "戌", "丑", "未")
    distinct_gan_shishen = len({p.get("gan_shishen") for p in ctx.pillar_info if p.get("gan_shishen") and p.get("gan_shishen") != "日主"})
    zaqi = siku and distinct_gan_shishen >= 3
    ratios = [v.get("ratio", 0.0) for v in ctx.wuxing_distribution.values() if not v.get("missing")]
    if len(ratios) >= 4:
        mean = sum(ratios) / len(ratios)
        var = sum((r - mean) ** 2 for r in ratios) / len(ratios)
        std = var ** 0.5
    else:
        std = 1.0
    even = std < 0.08 and len(ratios) >= 4
    if not (zaqi or even):
        return DetectResult.negative()
    intensity = min(1.0, 0.45 + (0.1 if zaqi else 0.0) + (0.1 if even else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, ("杂气" if zaqi else "") + ("+五行均匀" if even else ""))),
                        None)


def detect_I1(ctx: CtxView) -> DetectResult:
    """幸运者的债务：财官印全 或 三奇贵人。"""
    has_cai = _has_shishen(ctx, {"正财", "偏财"})
    has_guan = _has_shishen(ctx, {"正官", "七杀"})
    has_yin = _has_shishen(ctx, {"正印", "偏印"})
    san_qi_sets = [{"甲", "戊", "庚"}, {"乙", "丙", "丁"}, {"壬", "癸", "辛"}]
    gans_top3 = {ctx.pillar_info[i].get("gan", "") for i in range(min(3, len(ctx.pillar_info)))}
    san_qi = any(s.issubset(gans_top3) for s in san_qi_sets)
    if not ((has_cai and has_guan and has_yin) or san_qi):
        return DetectResult.negative()
    tianyi = _shensha_found(ctx, "tianyi_guiren")
    intensity = min(1.0, 0.4 + (0.1 if has_cai and has_guan and has_yin else 0.0) + (0.12 if san_qi else 0.0) + (0.08 if tianyi else 0.0))
    base = ctx.curves.get("baseline", {})
    triple_high = (base.get("spirit", 0) >= 60 and base.get("wealth", 0) >= 60 and base.get("fame", 0) >= 60)
    gravity = "jubilant" if triple_high else None
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "财官印全 / 三奇贵人")),
                        gravity)


def detect_I2(ctx: CtxView) -> DetectResult:
    """接受恩典而不内疚：天乙贵人 + (文昌 OR 华盖)；或 emotion_cumulative 60 岁均值高。"""
    tianyi = _shensha_found(ctx, "tianyi_guiren")
    wenchang = _shensha_found(ctx, "wenchang")
    huagai = _shensha_found(ctx, "huagai")
    grace = tianyi and (wenchang or huagai)
    base_e = ctx.curves.get("baseline", {}).get("emotion", 50.0)
    emo_high = _cumulative_mean(ctx, "emotion_cumulative") >= base_e + 15
    if not (grace or emo_high):
        return DetectResult.negative()
    intensity = min(1.0, 0.4 + (0.12 if grace else 0.0) + (0.1 if emo_high else 0.0))
    base = ctx.curves.get("baseline", {})
    triple_high = (base.get("spirit", 0) >= 60 and base.get("wealth", 0) >= 60 and base.get("fame", 0) >= 60)
    gravity = "jubilant" if triple_high else None
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "天乙+文昌/华盖 / emotion 长期高")),
                        gravity)


def detect_J1(ctx: CtxView) -> DetectResult:
    """被卷入历史：脚本侧暂保守不触发——依赖未来 era_window 模块。"""
    return DetectResult.negative()


def detect_J2(ctx: CtxView) -> DetectResult:
    """时代不利时的不背叛：脚本侧暂保守不触发——依赖未来 era_window 模块。"""
    return DetectResult.negative()


def detect_K1(ctx: CtxView) -> DetectResult:
    """努力被结构消音：年柱或时柱空亡，或 fame 长期低 + spirit 较高。"""
    kong = ctx.shensha.get("kongwang", {}).get("in_chart", []) or []
    if len(ctx.pillar_info) < 4:
        return DetectResult.negative()
    year_zhi = ctx.pillar_info[0].get("zhi", "")
    time_zhi = ctx.pillar_info[3].get("zhi", "")
    day_zhi = ctx.pillar_info[2].get("zhi", "")
    yt_kong = year_zhi in kong or time_zhi in kong
    base_f = ctx.curves.get("baseline", {}).get("fame", 50.0)
    base_s = ctx.curves.get("baseline", {}).get("spirit", 50.0)
    fame_low = _cumulative_mean(ctx, "fame_cumulative") < base_f - 10
    spirit_ok = _cumulative_mean(ctx, "spirit_cumulative") >= base_s - 5
    pattern_b = fame_low and spirit_ok
    if not (yt_kong or pattern_b):
        return DetectResult.negative()
    day_kong = day_zhi in kong
    intensity = min(1.0, 0.5 + (0.15 if yt_kong else 0.0) + (0.1 if pattern_b else 0.0) + (0.15 if day_kong else 0.0))
    parts = []
    if yt_kong:
        parts.append("年/时柱空亡")
    if pattern_b:
        parts.append("fame 长期低 + spirit 较高")
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, " · ".join(parts))),
                        None)


def detect_K2(ctx: CtxView) -> DetectResult:
    """带着不全活（持续音类）：五行缺一 / 用神缺位。"""
    missing = [w for w, v in ctx.wuxing_distribution.items() if v.get("missing")]
    yongshen_usability = ctx.yongshen.get("_reverse_check", {}).get("usability", "")
    yongshen_missing = yongshen_usability == "无"
    if not missing and not yongshen_missing:
        return DetectResult.negative()
    yongshen_wx = ctx.yongshen.get("yongshen", "")
    yongshen_in_missing = yongshen_wx in missing
    intensity = min(1.0, 0.55 + (0.15 if yongshen_missing else 0.0) + (0.1 if missing else 0.0)
                    + (0.1 if yongshen_in_missing else 0.0))
    parts = []
    if missing:
        parts.append(f"缺{','.join(missing)}")
    if yongshen_missing:
        parts.append(f"用神{yongshen_wx}不见")
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, " · ".join(parts))),
                        None)


def detect_K3(ctx: CtxView) -> DetectResult:
    """晚成者的焦虑：杂气格 / 蓄藏格 / 30 岁前三维均 < baseline。"""
    h2 = detect_H2(ctx)
    zaqi = h2.triggered and "杂气" in (h2.activation_points[0].trigger_basis if h2.activation_points else "")
    base = ctx.curves.get("baseline", {})
    early_low = True
    for field, key in [("spirit_cumulative", "spirit"), ("wealth_cumulative", "wealth"), ("fame_cumulative", "fame")]:
        vals = [pt.get(field) for pt in ctx.points if pt.get("age") is not None and pt["age"] < 30 and pt.get(field) is not None]
        if not vals or sum(vals) / len(vals) >= base.get(key, 50.0):
            early_low = False
            break
    yongshen_zang = not ctx.yongshen.get("_reverse_check", {}).get("透干") and ctx.yongshen.get("_reverse_check", {}).get("藏地支")
    if not (zaqi or early_low or yongshen_zang):
        return DetectResult.negative()
    intensity = min(1.0, 0.45 + (0.1 if zaqi or yongshen_zang else 0.0) + (0.1 if early_low else 0.0))
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "晚成结构（杂气/蓄藏/30 岁前三维低）")),
                        None)


# --- L 类：双门约束（结构 + 凶代价）-------------------------------------------

def _has_xiong_structure(ctx: CtxView) -> Tuple[bool, str]:
    """L 类共用的"凶结构"判定。返回 (是否触发, 原因描述)。"""
    base = ctx.curves.get("baseline", {})
    reasons = []
    w_mean = _cumulative_mean(ctx, "wealth_cumulative")
    if w_mean < base.get("wealth", 50.0) - 10:
        reasons.append(f"wealth 长期低（均值={w_mean:.1f}）")
    e_mean = _cumulative_mean(ctx, "emotion_cumulative")
    if e_mean < base.get("emotion", 50.0):
        reasons.append(f"emotion 长期低（均值={e_mean:.1f}）")
    yongshen_unusable = ctx.yongshen.get("_reverse_check", {}).get("usability") == "无"
    if yongshen_unusable:
        reasons.append("用神不见")
    # 早损迹象：forecast_window 前 spirit < 0
    forecast_from = ctx.curves.get("forecast_from_year", 9999)
    forecast_window = ctx.curves.get("forecast_window", 0)
    pre_forecast_spirit = []
    for pt in ctx.points:
        y = pt.get("year")
        if y is not None and y < forecast_from:
            v = pt.get("spirit_cumulative")
            if v is not None:
                pre_forecast_spirit.append(v)
    early_loss = pre_forecast_spirit and (sum(pre_forecast_spirit[-forecast_window:]) / max(1, len(pre_forecast_spirit[-forecast_window:]))) < 0
    if early_loss:
        reasons.append("forecast 前 spirit 累积 < 0（早损迹象）")
    return (len(reasons) >= 1, " / ".join(reasons))


def detect_L1(ctx: CtxView) -> DetectResult:
    """艺术/科学召命：食神不就财 / 华盖+印 / 文昌+驿马 + 凶结构。"""
    f1 = detect_F1(ctx)
    huagai = _shensha_found(ctx, "huagai")
    yin = _gan_shishen_count(ctx, {"正印", "偏印"}) >= 1
    wenchang = _shensha_found(ctx, "wenchang")
    yima = _shensha_found(ctx, "yima")
    structural = f1.triggered or (huagai and yin) or (wenchang and yima) or yin
    if not structural:
        return DetectResult.negative()
    has_xiong, xiong_basis = _has_xiong_structure(ctx)
    if not has_xiong:
        return DetectResult.negative()  # L 类双门：必须有代价
    structural_count = sum([f1.triggered, huagai and yin, wenchang and yima])
    intensity = min(1.0, 0.55 + 0.15 * structural_count + 0.15 * min(1, len(xiong_basis.split("/"))))
    if intensity < 0.55:
        return DetectResult.negative()
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, f"召命结构 + 凶代价：{xiong_basis}")),
                        "transcendent")


def detect_L2(ctx: CtxView) -> DetectResult:
    """道德/政治献身：伤官见官 + 七杀压身（≥ 2）+ 凶代价。"""
    sg = _has_shishen(ctx, "伤官")
    qi = _shishen_count(ctx, "七杀") >= 2
    label = ctx.strength.get("label", "")
    if not (sg and qi and label == "弱"):
        return DetectResult.negative()
    has_xiong, xiong_basis = _has_xiong_structure(ctx)
    sgjg_events = _mangpai_event_years(ctx, "shang_guan_jian_guan")
    heavy_event = len(sgjg_events) >= 3
    if not (has_xiong and heavy_event):
        return DetectResult.negative()
    tianyi = _shensha_found(ctx, "tianyi_guiren")
    huagai = _shensha_found(ctx, "huagai")
    intensity = min(1.0, 0.6 + (0.1 if tianyi else 0.0) + (0.05 if huagai else 0.0) + 0.2)
    aps = tuple(_event_ap(a, y, d, ev) for a, y, d, ev in sgjg_events)
    return DetectResult(True, round(intensity, 4), aps, "transcendent")


def detect_L3(ctx: CtxView) -> DetectResult:
    """良心：日主清纯 + 食神制杀 / 印星单透守身 + 凶代价（spirit 受压 / emotion 偏低 / 时代不合）。
    脚本侧用粗代理：日干月令同五行 OR 同序（清纯）+ 食神制杀(食神+七杀 同在) OR 印单透。
    """
    if not ctx.pillar_info:
        return DetectResult.negative()
    dm_wx = ctx.day_master_wuxing
    yue_wx = ctx.pillar_info[1].get("zhi_wuxing", "") if len(ctx.pillar_info) >= 2 else ""
    pure = dm_wx == yue_wx or yue_wx in ("水", "金") and dm_wx in ("水", "金")
    shi_zhi_sha = _has_shishen(ctx, "食神") and _has_shishen(ctx, "七杀")
    yin_single = _gan_shishen_count(ctx, {"正印", "偏印"}) == 1
    structural = pure and (shi_zhi_sha or yin_single)
    huagai = _shensha_found(ctx, "huagai")
    structural = structural or (yin_single and huagai)
    if not structural:
        return DetectResult.negative()
    has_xiong, xiong_basis = _has_xiong_structure(ctx)
    if not has_xiong:
        return DetectResult.negative()
    intensity = min(1.0, 0.55 + (0.15 if pure else 0.0) + 0.15)
    if intensity < 0.55:
        return DetectResult.negative()
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, f"清纯+食神制杀/印单透 + 凶代价：{xiong_basis}")),
                        "transcendent")


def detect_L4(ctx: CtxView) -> DetectResult:
    """爱情的献身：日支冲合活动剧烈 + 官杀混杂 + 桃花重 + 情感对应物质损失。"""
    e3 = detect_E3(ctx)
    guan_sha_zaha = _has_shishen(ctx, "正官") and _has_shishen(ctx, "七杀")
    taohua_in_chart = ctx.shensha.get("taohua", {}).get("in_chart", []) or []
    taohua_heavy = _shensha_found(ctx, "taohua") and len(taohua_in_chart) >= 1
    if not (e3.triggered and guan_sha_zaha and taohua_heavy):
        return DetectResult.negative()
    base = ctx.curves.get("baseline", {})
    emo_peak_yrs = [pt for pt in ctx.points if pt.get("emotion_yearly", 0) >= base.get("emotion", 50.0) + 10]
    cost_yrs = [pt for pt in emo_peak_yrs if (pt.get("wealth_yearly", 100) <= base.get("wealth", 50.0) - 10
                                              or pt.get("fame_yearly", 100) <= base.get("fame", 50.0) - 10)]
    if not cost_yrs:
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + 0.12 + 0.12 + 0.15 * min(1, len(cost_yrs)))
    aps = tuple(_event_ap(int(p["age"]), int(p["year"]), str(p.get("dayun", "")), "情感高峰对应物质损失") for p in cost_yrs[:6])
    return DetectResult(True, round(intensity, 4), aps, "transcendent")


def detect_L5(ctx: CtxView) -> DetectResult:
    """信仰/灵性献身：华盖叠现 + 印过旺 + 日/时空亡 + 凶代价。"""
    huagai_chart = ctx.shensha.get("huagai", {}).get("in_chart", []) or []
    huagai_multi = len(huagai_chart) >= 2
    yin_count = _shishen_count(ctx, {"正印", "偏印"})
    yin_heavy = yin_count >= 3
    kong = ctx.shensha.get("kongwang", {}).get("in_chart", []) or []
    if len(ctx.pillar_info) < 4:
        return DetectResult.negative()
    day_or_time_kong = ctx.pillar_info[2].get("zhi") in kong or ctx.pillar_info[3].get("zhi") in kong
    if not (huagai_multi and yin_heavy and day_or_time_kong):
        return DetectResult.negative()
    has_xiong, xiong_basis = _has_xiong_structure(ctx)
    if not has_xiong:
        return DetectResult.negative()
    intensity = min(1.0, 0.55 + 0.15 + 0.15)
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, f"华盖叠+印旺+空亡 + 凶代价：{xiong_basis}")),
                        "transcendent")


def detect_L6(ctx: CtxView) -> DetectResult:
    """民族/时代献身：依赖 J1/J2，脚本侧暂不触发。"""
    return DetectResult.negative()


def detect_L7(ctx: CtxView) -> DetectResult:
    """守护他人：印为忌 / 食伤被合 + 日支孤辰 + 三维平庸而 emotion 偏低。"""
    c3 = detect_C3(ctx)
    from _bazi_core import GUCHEN_GUASU  # type: ignore
    if not ctx.pillar_info or len(ctx.pillar_info) < 3:
        return DetectResult.negative()
    year_zhi = ctx.pillar_info[0].get("zhi", "")
    day_zhi = ctx.pillar_info[2].get("zhi", "")
    day_guchen = year_zhi in GUCHEN_GUASU and GUCHEN_GUASU[year_zhi][0] == day_zhi
    if not (c3.triggered and day_guchen):
        return DetectResult.negative()
    base = ctx.curves.get("baseline", {})
    spi = _cumulative_mean(ctx, "spirit_cumulative")
    wea = _cumulative_mean(ctx, "wealth_cumulative")
    fam = _cumulative_mean(ctx, "fame_cumulative")
    emo = _cumulative_mean(ctx, "emotion_cumulative")
    mediocre = (abs(spi - base.get("spirit", 50)) < 10 and abs(wea - base.get("wealth", 50)) < 10
                and abs(fam - base.get("fame", 50)) < 10)
    emo_low = emo < base.get("emotion", 50) - 5
    if not (mediocre and emo_low):
        return DetectResult.negative()
    intensity = min(1.0, 0.5 + 0.12 + 0.15)
    return DetectResult(True, round(intensity, 4),
                        tuple(_structural_activation_points(ctx, "印为忌+日支孤辰+三维平庸+emo 偏低")),
                        "transcendent")


# ---------------------------------------------------------------------------
# Detector dispatch table
# ---------------------------------------------------------------------------

_DETECTOR_TABLE = {
    "detect_A1": detect_A1, "detect_A2": detect_A2, "detect_A3": detect_A3,
    "detect_B1": detect_B1, "detect_B2": detect_B2, "detect_B3": detect_B3,
    "detect_C1": detect_C1, "detect_C2": detect_C2, "detect_C3": detect_C3,
    "detect_D1": detect_D1, "detect_D2": detect_D2, "detect_D3": detect_D3,
    "detect_E1": detect_E1, "detect_E2": detect_E2, "detect_E3": detect_E3, "detect_E4": detect_E4,
    "detect_F1": detect_F1, "detect_F2": detect_F2, "detect_F3": detect_F3,
    "detect_G1": detect_G1, "detect_G2": detect_G2, "detect_G3": detect_G3,
    "detect_H1": detect_H1, "detect_H2": detect_H2,
    "detect_I1": detect_I1, "detect_I2": detect_I2,
    "detect_J1": detect_J1, "detect_J2": detect_J2,
    "detect_K1": detect_K1, "detect_K2": detect_K2, "detect_K3": detect_K3,
    "detect_L1": detect_L1, "detect_L2": detect_L2, "detect_L3": detect_L3,
    "detect_L4": detect_L4, "detect_L5": detect_L5, "detect_L6": detect_L6, "detect_L7": detect_L7,
}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _resolve_gravity(spec: MotifSpec, result: DetectResult, blessing_path: bool) -> str:
    """决定该 motif 在该命主上的实际 gravity_class。
    - L 类一律 transcendent
    - blessing_path 命主上：禁止把 gentle 默认母题升级到 serious 及以上
    """
    base = result.gravity_override or spec.default_gravity
    if spec.is_l_class:
        return "transcendent"
    if blessing_path:
        # 命好命主：把 serious 及以上压回 gentle，避免悲剧化
        if GRAVITY_RANK.get(base, 2) >= GRAVITY_RANK["serious"]:
            return "gentle"
    return base


def _detect_blessing_path_pre(triggered_pre: List[Tuple[MotifSpec, DetectResult]]) -> bool:
    """命好路径：所有触发母题（按 default_gravity 或 override）都 ≤ gentle。"""
    if not triggered_pre:
        return True  # 没触发任何母题：默认温和
    for spec, res in triggered_pre:
        if spec.is_l_class:
            return False
        gravity = res.gravity_override or spec.default_gravity
        if GRAVITY_RANK.get(gravity, 2) >= GRAVITY_RANK["serious"]:
            return False
    return True


def _input_signature(bazi: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pillars": bazi.get("pillars_str") or " ".join(
            f"{p.get('gan')}{p.get('zhi')}" for p in bazi.get("pillars", [])
        ),
        "birth_year": bazi.get("birth_year"),
        "gender": bazi.get("gender"),
        "day_master": bazi.get("day_master"),
    }


def _make_convergence_years(motif_recurrence_map: Dict[str, List[Dict[str, Any]]],
                            triggered_motifs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """convergence_year = 命主真实流年里"母题与应期叠现"的年份。

    判定（按强度递减）：
      A. 同年 ≥ 2 条 event-driven 母题应期 → 强 convergence（convergence_strength=high）
      B. 同年 1 条 event-driven 母题应期 + 整体已触发母题 ≥ 4 → 弱 convergence
         （convergence_strength=mid）—— 表示这一年某条真实拷问浮现，背后有一整张
         拷问网络在响应。

    持续音类 / 结构型母题的大运中点占位（source='structural'）一律不参与判定——
    否则同段大运所有结构型母题会在中点假性聚合，污染位置 ③。

    每个 convergence_year 同时附带：
      - convergence_motifs：该年真实应期的 event-driven motif id 列表
      - background_motifs：当时仍活跃的全部其它已触发 motif（结构型 + 持续型）
    """
    spec_by_id = {m["id"]: m for m in triggered_motifs}
    year_to_event_motifs: Dict[int, Set[str]] = defaultdict(set)
    for mid, aps in motif_recurrence_map.items():
        if mid not in spec_by_id:
            continue
        for ap in aps:
            if ap.get("source") == "event":
                year_to_event_motifs[ap["year"]].add(mid)
    out = []
    triggered_id_set = sorted(spec_by_id.keys())
    total_triggered = len(triggered_id_set)
    for year in sorted(year_to_event_motifs.keys()):
        event_ids = sorted(year_to_event_motifs[year])
        if len(event_ids) >= 2:
            strength = "high"
        elif len(event_ids) == 1 and total_triggered >= 4:
            strength = "mid"
        else:
            continue
        ages = [ap["age"] for mid in event_ids for ap in motif_recurrence_map[mid]
                if ap["year"] == year and ap.get("source") == "event"]
        age = min(ages) if ages else 0
        background = [mid for mid in triggered_id_set if mid not in set(event_ids)]
        out.append({
            "year": year,
            "age": age,
            "is_convergence": True,
            "convergence_strength": strength,
            "convergence_motifs": event_ids,
            "background_motifs": background,
        })
    return out


def _make_convergence_hint(triggered: List[Dict[str, Any]], blessing_path: bool, love_letter_eligible: bool) -> str:
    """给 LLM 的非定论性提示——只描述聚合趋势，不命名主旋律。"""
    if not triggered:
        return "未检测到 catalog 内强母题——按 ★★★★★★ catalog 开放性铁律，LLM 应在位置 ④ 自由命名命主真正承担的核心拷问；位置 ⑥ 自由话照常激活。"
    cats = sorted({m["category"] for m in triggered})
    top = sorted(triggered, key=lambda m: -m["intensity"])[:3]
    top_desc = " / ".join(f"{m['name']}（{m['gravity_class']}）" for m in top)
    parts = [f"母题分布跨 {len(cats)} 类（{', '.join(cats)}），强度前三：{top_desc}。"]
    if blessing_path:
        parts.append("命主全部 motif 调性 ≤ gentle → 命好路径，按祝福路径铁律输出。")
    elif love_letter_eligible:
        parts.append("触发 ≥1 条 tragic/transcendent 母题 → 位置 ⑤ 项目作者的爱激活。")
    parts.append("以上为脚本聚合提示，LLM 不得将其转述为定论；位置 ④ 顿悟段必须 trace 回具体激活点。")
    return " ".join(parts)


def run(bazi: Dict[str, Any], curves: Dict[str, Any]) -> Dict[str, Any]:
    ctx = CtxView(bazi=bazi, curves=curves)

    # Step 1: run all detectors
    raw_results: List[Tuple[MotifSpec, DetectResult]] = []
    for spec in MOTIFS:
        fn = _DETECTOR_TABLE[spec.detector_id]
        try:
            res = fn(ctx)
        except Exception as e:
            res = DetectResult(False, 0.0, tuple(), None, f"detector_error: {e}")
        raw_results.append((spec, res))

    # Step 2: filter triggered (intensity >= threshold)
    triggered_pre = [(spec, res) for spec, res in raw_results
                     if res.triggered and res.intensity >= spec.intensity_threshold]

    # Step 3: blessing_path 判定
    blessing_path = _detect_blessing_path_pre(triggered_pre)

    # Step 4: 装配 triggered_motifs（带 final gravity_class）
    triggered_motifs: List[Dict[str, Any]] = []
    motif_recurrence_map: Dict[str, List[Dict[str, Any]]] = {}
    for spec, res in triggered_pre:
        gravity = _resolve_gravity(spec, res, blessing_path)
        aps_dict = [ap.to_dict() for ap in res.activation_points]
        triggered_motifs.append({
            **spec.header_dict(),
            "gravity_class": gravity,
            "intensity": res.intensity,
            "first_activation_age": min((ap.age for ap in res.activation_points), default=None),
            "activation_count": len(res.activation_points),
            "activation_points": aps_dict,
        })
        motif_recurrence_map[spec.id] = aps_dict

    triggered_motifs.sort(key=lambda m: (-m["intensity"], m["id"]))
    for rank, m in enumerate(triggered_motifs, 1):
        m["rank"] = rank

    # Step 5: silenced_motifs（catalog 内、未触发）
    triggered_ids = {m["id"] for m in triggered_motifs}
    silenced_motifs = sorted(spec.id for spec in MOTIFS if spec.id not in triggered_ids)

    # Step 6: love_letter_eligible（位置 ⑤ 触发）
    love_letter_eligible = any(
        m["gravity_class"] in ("tragic", "transcendent") or
        m["gravity_class"] == "serious"
        for m in triggered_motifs
    ) and not blessing_path
    # 命好路径下永不激活 ⑤
    if blessing_path:
        love_letter_eligible = False

    # Step 7: convergence_years（位置 ③ 触发）
    convergence_years = _make_convergence_years(motif_recurrence_map, triggered_motifs)

    # Step 8: complexity_score（伦理拷问密度，0-1）
    if triggered_motifs:
        sum_intensity = sum(m["intensity"] for m in triggered_motifs)
        n_categories = len({m["category"] for m in triggered_motifs})
        complexity_score = min(1.0, round(0.4 * (n_categories / 11.0) + 0.6 * (sum_intensity / 8.0), 4))
    else:
        complexity_score = 0.0

    # Step 9: convergence_hint
    convergence_hint = _make_convergence_hint(triggered_motifs, blessing_path, love_letter_eligible)

    return {
        "version": 1,
        "schema": "virtue_motifs/v1",
        "input_signature": _input_signature(bazi),
        "complexity_score": complexity_score,
        "love_letter_eligible": love_letter_eligible,
        "blessing_path": blessing_path,
        "convergence_hint": convergence_hint,
        "triggered_motifs": triggered_motifs,
        "motif_recurrence_map": motif_recurrence_map,
        "silenced_motifs": silenced_motifs,
        "convergence_years": convergence_years,
        "catalog_size": len(MOTIFS),
        "catalog_disclaimer": (
            "本输出基于 38 条诊断 motif（catalog v1）；按 ★★★★★★ catalog 开放性铁律，"
            "LLM 在位置 ④ ⑥ 被授权命名 catalog 之外的人性形态——任何此类自创母题"
            "必须在 trace metadata 中标 motif_origin: 'llm_invented'，供 audit_llm_invented.py 聚合。"
        ),
    }


def _stable_dump(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Virtue Motifs · 第三条独立叙事通道（read-only of bazi/curves）"
    )
    parser.add_argument("--bazi", required=True, help="bazi.json 路径")
    parser.add_argument("--curves", required=True, help="curves.json 路径")
    parser.add_argument("--out", required=True, help="输出 virtue_motifs.json 路径")
    parser.add_argument("--strict", action="store_true",
                        help="严格模式：以 stdout 输出 sha256 摘要供 bit-for-bit 验证")
    args = parser.parse_args(argv)

    bazi_path = Path(args.bazi)
    curves_path = Path(args.curves)
    out_path = Path(args.out)
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    curves = json.loads(curves_path.read_text(encoding="utf-8"))

    output = run(bazi, curves)
    text = _stable_dump(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")

    if args.strict:
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        sys.stdout.write(h + "\n")
    else:
        n_trig = len(output["triggered_motifs"])
        n_conv = len(output["convergence_years"])
        sys.stdout.write(
            f"[virtue_motifs] triggered={n_trig} silenced={len(output['silenced_motifs'])} "
            f"convergence_years={n_conv} blessing_path={output['blessing_path']} "
            f"love_letter={output['love_letter_eligible']} → {out_path}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
