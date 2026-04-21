"""v9 L1-L7 · 杀印相生格 (sha_yin_xiang_sheng_geju) e2e acceptance 回归测试。

固化:
  - L1 _phase_registry: 杀印族 2 phase 注册 (sha_yin_xiang_sheng_geju + qi_yin_xiang_sheng)
  - L3 _question_bank: D6 三题对杀印族 phase 有 B/C 偏高的非均匀 likelihood
  - L5 mangpai_events: phase 锁定后, qi_sha_feng_yin 反转 (positive 化煞为权)
  - L6 score_curves: trigger 流年 (寅申巳亥) geju 派显著抬升

合成测试输入:
  - 杀印相生: `庚午 戊寅 甲子 壬申` (甲日, 庚七杀 + 壬偏印 + 子正印)
  - 寅(月支)、申(时支) ∈ trigger_branches=寅申巳亥
"""
from __future__ import annotations

import copy

import pytest

from solve_bazi import solve  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast]


SYNTHETIC_PILLARS = "庚午 戊寅 甲子 壬申"
SYNTHETIC_GENDER = "M"
SYNTHETIC_BIRTH_YEAR = 1930


@pytest.fixture(scope="module")
def bazi_raw() -> dict:
    return solve(SYNTHETIC_PILLARS, None, SYNTHETIC_GENDER, SYNTHETIC_BIRTH_YEAR)


# ──────────────────────────────────────────────────────────
# L1
# ──────────────────────────────────────────────────────────

def test_l1_sha_yin_family_registered():
    from _phase_registry import get, exists  # type: ignore

    for pid in ("sha_yin_xiang_sheng_geju", "qi_yin_xiang_sheng"):
        assert exists(pid), f"杀印族 phase {pid} 未注册"
        meta = get(pid)
        assert meta.dimension == "zuogong"
        assert meta.source

        triggers = set(meta.zuogong_trigger_branches)
        assert {"寅", "申", "巳", "亥"}.issubset(triggers), (
            f"{pid} 缺四生 trigger: {triggers}"
        )

        rev = meta.reversal_overrides
        assert rev.get("qi_sha_feng_yin") == "positive", (
            f"{pid} 未将 qi_sha_feng_yin 设为 positive (化煞为权): {rev}"
        )


# ──────────────────────────────────────────────────────────
# L3
# ──────────────────────────────────────────────────────────

def test_l3_d6_likelihood_for_sha_yin_family():
    from _question_bank import D6_QUESTIONS  # type: ignore

    for q in D6_QUESTIONS:
        for pid in ("sha_yin_xiang_sheng_geju", "qi_yin_xiang_sheng"):
            row = q.likelihood_table.get(pid, {})
            assert row, f"{q.id} 缺 {pid} likelihood row"
            assert not all(abs(v - 0.25) < 0.01 for v in row.values()), (
                f"{q.id} {pid} likelihood 均匀, 失去判别力"
            )

    # 杀印族在 D6_Q1 上 B/C 合计应高于 A/D (借外力 + 耐心型)
    q1 = next(q for q in D6_QUESTIONS if q.id == "D6_Q1_agency_style")
    row = q1.likelihood_table["sha_yin_xiang_sheng_geju"]
    assert row["B"] + row["C"] > row["A"] + row["D"], (
        f"杀印族 D6_Q1 B+C={row['B']+row['C']:.2f} 未超过 A+D={row['A']+row['D']:.2f}, "
        f"与'借印化煞、耐心借势'语义不符"
    )


# ──────────────────────────────────────────────────────────
# L5
# ──────────────────────────────────────────────────────────

def test_l5_qi_sha_feng_yin_reversed_positive(bazi_raw):
    from score_curves import apply_phase_override  # type: ignore
    from mangpai_events import detect_all  # type: ignore

    b = copy.deepcopy(bazi_raw)
    apply_phase_override(b, "sha_yin_xiang_sheng_geju")
    result = detect_all(b)

    ctx = result.get("phase_context_used")
    assert ctx is not None and ctx["phase_id"] == "sha_yin_xiang_sheng_geju"

    events = result["events"]
    reversed_events = [
        e for e in events if "reversal" in e and e["reversal"].get("applied")
    ]
    assert len(reversed_events) >= 3, (
        f"反转事件 {len(reversed_events)} 个 < 3, L5 DSL 未覆盖足"
    )

    # 至少有一个 qi_sha_feng_yin 反转 polarity_after=positive
    qsfy_positive = [
        e for e in events
        if e.get("key") == "qi_sha_feng_yin"
        and e.get("reversal", {}).get("applied")
        and e["reversal"].get("polarity_after") == "positive"
    ]
    assert qsfy_positive, (
        "未发现 qi_sha_feng_yin polarity=positive 反转, "
        "违反《滴天髓·七杀》'逢印化杀, 反凶为吉'"
    )


# ──────────────────────────────────────────────────────────
# L6
# ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def score_comparison(bazi_raw):
    from score_curves import score, apply_phase_override  # type: ignore

    b0 = copy.deepcopy(bazi_raw)
    out0 = score(b0, age_start=0, age_end=40)
    b1 = copy.deepcopy(bazi_raw)
    apply_phase_override(b1, "sha_yin_xiang_sheng_geju")
    out1 = score(b1, age_start=0, age_end=40)
    return out0["points"], out1["points"]


def test_l6_zuogong_modifier_on_si_sheng_years(score_comparison):
    y0, y1 = score_comparison
    by_age0 = {p["age"]: p for p in y0}
    by_age1 = {p["age"]: p for p in y1}

    trigger_zhi = {"寅", "申", "巳", "亥"}
    trigger_ages = [a for a, p in by_age1.items() if p["ganzhi"][-1] in trigger_zhi]
    assert len(trigger_ages) >= 5

    deltas = [
        by_age1[a]["school_scores"]["spirit"]["geju"]
        - by_age0[a]["school_scores"]["spirit"]["geju"]
        for a in trigger_ages
    ]
    avg = sum(deltas) / len(deltas)
    assert avg >= 2.0, (
        f"trigger 年 spirit geju 平均 delta={avg:.2f} < 2.0, L6 modifier 退化"
    )
