"""v9 L1-L7 · 食神制杀格 (shi_shen_zhi_sha_geju) e2e acceptance 回归测试。

固化:
  - L1 _phase_registry: shi_shen_zhi_sha_geju 注册 + trigger=寅申巳亥
  - L3 _question_bank: D6 三题对食制杀 phase 有 A 偏高的非均匀 likelihood
  - L5 mangpai_events: phase 锁定后, shi_shen_zhi_sha 反转 (positive 主动制衡)
  - L6 score_curves: trigger 流年 (寅申巳亥) geju 派显著抬升

合成测试输入:
  - 食神制杀: `庚寅 丙申 甲子 戊辰` (甲日, 庚七杀×2 + 丙食神 + 戊偏财)
  - 寅(年支)、申(月支) ∈ trigger_branches=寅申巳亥
"""
from __future__ import annotations

import copy

import pytest

from solve_bazi import solve  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast]


SYNTHETIC_PILLARS = "庚寅 丙申 甲子 戊辰"
SYNTHETIC_GENDER = "M"
SYNTHETIC_BIRTH_YEAR = 1932


@pytest.fixture(scope="module")
def bazi_raw() -> dict:
    return solve(SYNTHETIC_PILLARS, None, SYNTHETIC_GENDER, SYNTHETIC_BIRTH_YEAR)


# ──────────────────────────────────────────────────────────
# L1
# ──────────────────────────────────────────────────────────

def test_l1_shi_shen_zhi_sha_registered():
    from _phase_registry import get, exists  # type: ignore

    assert exists("shi_shen_zhi_sha_geju")
    meta = get("shi_shen_zhi_sha_geju")
    assert meta.dimension == "zuogong"
    assert "食神制杀" in meta.source

    triggers = set(meta.zuogong_trigger_branches)
    assert {"寅", "申", "巳", "亥"}.issubset(triggers), (
        f"shi_shen_zhi_sha_geju 缺四生 trigger: {triggers}"
    )

    rev = meta.reversal_overrides
    assert rev.get("shi_shen_zhi_sha") == "positive", (
        f"shi_shen_zhi_sha 未反转 positive (主动制衡获利): {rev}"
    )
    # 食制杀对 qi_sha_feng_yin 应去其凶 (印夺)
    assert rev.get("qi_sha_feng_yin") == "neutral", (
        f"食制杀格未将 qi_sha_feng_yin 设 neutral: {rev}"
    )


# ──────────────────────────────────────────────────────────
# L3
# ──────────────────────────────────────────────────────────

def test_l3_d6_likelihood_for_shi_shen_zhi_sha():
    from _question_bank import D6_QUESTIONS  # type: ignore

    for q in D6_QUESTIONS:
        row = q.likelihood_table.get("shi_shen_zhi_sha_geju", {})
        assert row, f"{q.id} 缺 shi_shen_zhi_sha_geju likelihood row"
        assert not all(abs(v - 0.25) < 0.01 for v in row.values()), (
            f"{q.id} shi_shen_zhi_sha_geju likelihood 均匀, 失去判别力"
        )

    # 食制杀 D6_Q1 A 应占优 (主动制衡型)
    q1 = next(q for q in D6_QUESTIONS if q.id == "D6_Q1_agency_style")
    row = q1.likelihood_table["shi_shen_zhi_sha_geju"]
    assert row["A"] >= 0.35, (
        f"食制杀 D6_Q1 A={row['A']:.2f} 未占优, 与'主动制衡获利'语义不符"
    )


# ──────────────────────────────────────────────────────────
# L5
# ──────────────────────────────────────────────────────────

def test_l5_shi_shen_zhi_sha_reversed_positive(bazi_raw):
    from score_curves import apply_phase_override  # type: ignore
    from mangpai_events import detect_all  # type: ignore

    b = copy.deepcopy(bazi_raw)
    apply_phase_override(b, "shi_shen_zhi_sha_geju")
    result = detect_all(b)

    ctx = result.get("phase_context_used")
    assert ctx is not None and ctx["phase_id"] == "shi_shen_zhi_sha_geju"

    events = result["events"]
    reversed_events = [
        e for e in events if "reversal" in e and e["reversal"].get("applied")
    ]
    assert len(reversed_events) >= 3, (
        f"反转事件 {len(reversed_events)} 个 < 3"
    )

    # 至少一个 shi_shen_zhi_sha polarity_after=positive
    sszs_pos = [
        e for e in events
        if e.get("key") == "shi_shen_zhi_sha"
        and e.get("reversal", {}).get("applied")
        and e["reversal"].get("polarity_after") == "positive"
    ]
    assert sszs_pos, (
        "未发现 shi_shen_zhi_sha polarity=positive 反转, "
        "违反《子平真诠·七杀格·食神制杀》"
    )


# ──────────────────────────────────────────────────────────
# L6
# ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def score_comparison(bazi_raw):
    from score_curves import score, apply_phase_override  # type: ignore

    # baseline 显式锁 day_master_dominant —— v9.2 起 P0 派别中立通道可能让默认
    # phase 变成某个 zuogong 格，与本测试的"override 触发"比较失去基线意义。
    b0 = copy.deepcopy(bazi_raw)
    b0.pop("phase", None)
    apply_phase_override(b0, "day_master_dominant")
    out0 = score(b0, age_start=0, age_end=40)
    b1 = copy.deepcopy(bazi_raw)
    apply_phase_override(b1, "shi_shen_zhi_sha_geju")
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
        f"trigger 年 spirit geju 平均 delta={avg:.2f} < 2.0"
    )
