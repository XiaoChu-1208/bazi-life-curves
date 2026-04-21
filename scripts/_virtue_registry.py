"""Virtue Motifs Registry · v1

NOTE: This is the diagnostic baseline (38 motifs · 11 categories), NOT the
totality of human ethical situations. Per ★★★★★★ catalog 开放性铁律
(see `references/virtue_recurrence_protocol.md` §0), the LLM is authorized to
name out-of-catalog humanity motifs at writing positions ④ and ⑥ under strict
constraints. This file only feeds machine detection of the 38 known templates.

Full motif specifications (ethical_interrogation / tragic_remainder / cheap_consolations /
what_can_be_honestly_said / classical_source / philosophical_anchor) live in
`references/virtue_motifs_catalog.md`. This module only carries fields needed
for **detection** and **trace** — narrative content is read from the markdown
catalog by the LLM, not from this registry.

Design constraints:
- Pure functions. No randomness, no time, no I/O. Bit-for-bit deterministic.
- Detectors take frozen inputs and emit `DetectResult`. They never mutate.
- Detectors are conservative: when in doubt, **do not trigger**. False
  positives are worse than false negatives because they impose an unfitting
  motif on the命主.
- L 类 detectors require the dual gate: structural标志 AND objective "凶"
  structure (see catalog L-class header).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActivationPoint:
    age: int
    year: int
    dayun: str
    trigger_basis: str
    source: str = "structural"  # "structural" (大运中点占位) | "event" (真实流年应期)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "age": self.age,
            "year": self.year,
            "dayun": self.dayun,
            "trigger_basis": self.trigger_basis,
            "source": self.source,
        }


@dataclass(frozen=True)
class DetectResult:
    triggered: bool
    intensity: float  # 0.0 - 1.0
    activation_points: Tuple[ActivationPoint, ...]
    gravity_override: Optional[str] = None  # one of {jubilant, gentle, serious, tragic, transcendent}
    detector_notes: str = ""

    @staticmethod
    def negative() -> "DetectResult":
        return DetectResult(False, 0.0, tuple(), None, "")


@dataclass(frozen=True)
class MotifSpec:
    id: str
    name: str
    category: str
    tone: str                       # T1 / T2 / T3
    default_gravity: str            # jubilant / gentle / serious / tragic / transcendent
    is_l_class: bool                # L 类需要 cost gate（见 catalog 附录 A）
    is_persistent: bool             # 持续音类（L 类全部 + E1 + K2）
    intensity_threshold: float      # >= threshold 才纳入 triggered_motifs
    detector_id: str                # 用于 audit；与 detectors.py 中函数名对应

    def header_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "tone": self.tone,
            "default_gravity": self.default_gravity,
            "is_l_class": self.is_l_class,
            "is_persistent": self.is_persistent,
        }


# ---------------------------------------------------------------------------
# Registry · 38 motifs (按 catalog 顺序 A→L)
# ---------------------------------------------------------------------------

# `intensity_threshold = 0.4` is the catalog default; some L 类抬高到 0.55。
MOTIFS: Tuple[MotifSpec, ...] = (
    # A · 分配类
    MotifSpec("A1", "共济", "分配类", "T1", "gentle", False, False, 0.4, "detect_A1"),
    MotifSpec("A2", "富者代管", "分配类", "T3", "serious", False, False, 0.4, "detect_A2"),
    MotifSpec("A3", "长子长女债", "分配类", "T2", "serious", False, False, 0.4, "detect_A3"),
    # B · 真话类
    MotifSpec("B1", "说真话的代价", "真话类", "T2", "serious", False, False, 0.4, "detect_B1"),
    MotifSpec("B2", "复杂忠诚", "真话类", "T2", "serious", False, False, 0.4, "detect_B2"),
    MotifSpec("B3", "受冤的克制", "真话类", "T3", "tragic", False, False, 0.4, "detect_B3"),
    # C · 承担类
    MotifSpec("C1", "替天下负重", "承担类", "T3", "tragic", False, False, 0.5, "detect_C1"),
    MotifSpec("C2", "创业者对兄弟的债", "承担类", "T1", "gentle", False, False, 0.4, "detect_C2"),
    MotifSpec("C3", "看护者的隐性消耗", "承担类", "T1", "gentle", False, False, 0.4, "detect_C3"),
    # D · 出世类
    MotifSpec("D1", "出世入世两难", "出世类", "T2", "serious", False, False, 0.4, "detect_D1"),
    MotifSpec("D2", "慢工敬源", "出世类", "T1", "gentle", False, False, 0.4, "detect_D2"),
    MotifSpec("D3", "师承断绝", "出世类", "T3", "tragic", False, False, 0.4, "detect_D3"),
    # E · 孤独类
    MotifSpec("E1", "结构性孤独", "孤独类", "T3", "serious", False, True, 0.45, "detect_E1"),
    MotifSpec("E2", "人群中的孤独", "孤独类", "T3", "serious", False, False, 0.4, "detect_E2"),
    MotifSpec("E3", "亲密中的无能", "孤独类", "T2", "serious", False, False, 0.4, "detect_E3"),
    MotifSpec("E4", "漂泊者的根问题", "孤独类", "T1", "gentle", False, False, 0.4, "detect_E4"),
    # F · 才华类
    MotifSpec("F1", "拒绝纯变现", "才华类", "T1", "gentle", False, False, 0.4, "detect_F1"),
    MotifSpec("F2", "创作者的物质焦虑", "才华类", "T2", "serious", False, False, 0.4, "detect_F2"),
    MotifSpec("F3", "市场里的手艺人尊严", "才华类", "T1", "gentle", False, False, 0.4, "detect_F3"),
    # G · 锋芒类
    MotifSpec("G1", "不和稀泥", "锋芒类", "T1", "gentle", False, False, 0.4, "detect_G1"),
    MotifSpec("G2", "强者的克制", "锋芒类", "T3", "serious", False, False, 0.45, "detect_G2"),
    MotifSpec("G3", "硬命人对柔软的渴望", "锋芒类", "T2", "serious", False, False, 0.4, "detect_G3"),
    # H · 委身类
    MotifSpec("H1", "全身委身", "委身类", "T2", "serious", False, True, 0.5, "detect_H1"),
    MotifSpec("H2", "副业人的诚实", "委身类", "T3", "serious", False, False, 0.4, "detect_H2"),
    # I · 恩典类
    MotifSpec("I1", "幸运者的债务", "恩典类", "T1", "jubilant", False, False, 0.4, "detect_I1"),
    MotifSpec("I2", "接受恩典而不内疚", "恩典类", "T1", "jubilant", False, False, 0.4, "detect_I2"),
    # J · 时代类（依赖 era 信息·脚本暂保守不触发，留给未来 era_window 模块）
    MotifSpec("J1", "被卷入历史", "时代类", "T2", "serious", False, False, 0.45, "detect_J1"),
    MotifSpec("J2", "时代不利时的不背叛", "时代类", "T3", "tragic", False, False, 0.5, "detect_J2"),
    # K · 缺失类
    MotifSpec("K1", "努力被结构消音", "缺失类", "T3", "tragic", False, False, 0.5, "detect_K1"),
    MotifSpec("K2", "带着不全活", "缺失类", "T3", "tragic", False, True, 0.55, "detect_K2"),
    MotifSpec("K3", "晚成者的焦虑", "缺失类", "T2", "serious", False, False, 0.45, "detect_K3"),
    # L · 超越性献身类（必须双门：结构 + 凶代价）
    MotifSpec("L1", "艺术/科学召命", "超越性献身类", "T3", "transcendent", True, True, 0.55, "detect_L1"),
    MotifSpec("L2", "道德政治献身", "超越性献身类", "T3", "transcendent", True, True, 0.6, "detect_L2"),
    MotifSpec("L3", "良心", "超越性献身类", "T3", "transcendent", True, True, 0.55, "detect_L3"),
    MotifSpec("L4", "爱情的献身", "超越性献身类", "T2", "transcendent", True, True, 0.5, "detect_L4"),
    MotifSpec("L5", "信仰/灵性献身", "超越性献身类", "T3", "transcendent", True, True, 0.55, "detect_L5"),
    MotifSpec("L6", "民族/时代献身", "超越性献身类", "T2", "transcendent", True, True, 0.55, "detect_L6"),
    MotifSpec("L7", "守护他人", "超越性献身类", "T2", "transcendent", True, True, 0.5, "detect_L7"),
)

assert len(MOTIFS) == 38, f"Catalog 应为 38 条，实际 {len(MOTIFS)}"
assert len({m.id for m in MOTIFS}) == 38, "母题 id 重复"


def get_motif_by_id(motif_id: str) -> MotifSpec:
    for m in MOTIFS:
        if m.id == motif_id:
            return m
    raise KeyError(motif_id)


# ---------------------------------------------------------------------------
# Gravity classification helpers
# ---------------------------------------------------------------------------

GRAVITY_RANK = {
    "jubilant": 1,
    "gentle": 2,
    "serious": 3,
    "tragic": 4,
    "transcendent": 5,
}


def gravity_max(*levels: str) -> str:
    """取调性五级中最高的那一级（rank 越大越深）。"""
    levels = [g for g in levels if g in GRAVITY_RANK]
    if not levels:
        return "gentle"
    return max(levels, key=lambda g: GRAVITY_RANK[g])
