"""L7 · orientation 覆盖测试(fairness_protocol §10)。

5 种取向(hetero/homo/bi/none/poly)在打分阶段都不能崩溃,
且 spirit/wealth/fame 三维与 hetero 必须 byte-equal
(orientation 只影响 emotion + relationship_mode)。

如果某分支在 emotion 计算里漏写,会让某个取向用户拿到全 0 emotion
或直接抛异常 — 这就是"现代化承诺悄悄破"的典型场景。
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.fairness]


ORIENTATIONS = ["hetero", "homo", "bi", "none", "poly"]


@pytest.fixture(scope="module")
def curves_by_orientation(canonical_pillars):
    """同一八字 × 5 种 orientation 的 curves。"""
    from solve_bazi import solve
    from score_curves import score

    sample = canonical_pillars[0]  # 取第一个就够了 — 我们测的是 orientation 分支覆盖
    out: dict[str, dict] = {}
    for orient in ORIENTATIONS:
        for gender in ("M", "F"):  # 两性别都跑,确保 homo/hetero 互换分支也覆盖到
            bazi = solve(
                sample["pillars"], None, gender, sample["birth_year"],
                n_years=60, orientation=orient,
            )
            curves = score(bazi, age_end=60, forecast_window=0)
            out[f"{orient}_{gender}"] = curves
    return out


@pytest.mark.parametrize("orient", ORIENTATIONS)
@pytest.mark.parametrize("gender", ["M", "F"])
def test_each_orientation_runs_clean(curves_by_orientation, orient, gender):
    """5 × 2 = 10 种组合都必须能跑通,且产出合法分数。"""
    curves = curves_by_orientation[f"{orient}_{gender}"]
    assert curves["points"], f"{orient}/{gender} 没出 points"
    assert curves["orientation"] == orient

    for p in curves["points"]:
        for dim in ("spirit_yearly", "wealth_yearly", "fame_yearly", "emotion_yearly"):
            v = p.get(dim)
            assert v is not None, f"{orient}/{gender} age={p['age']} 缺 {dim}"
            assert 0 <= v <= 100, f"{orient}/{gender} age={p['age']} {dim}={v} 越界"


@pytest.mark.parametrize("gender", ["M", "F"])
def test_orientation_does_not_affect_three_dims(curves_by_orientation, gender):
    """同性别下,5 种 orientation 的 spirit/wealth/fame 三维必须完全相同 ——
    orientation 只影响 emotion 通道。"""
    base = curves_by_orientation[f"hetero_{gender}"]
    base_pts = {p["age"]: p for p in base["points"]}

    for orient in ("homo", "bi", "none", "poly"):
        other = curves_by_orientation[f"{orient}_{gender}"]
        other_pts = {p["age"]: p for p in other["points"]}
        common = sorted(set(base_pts) & set(other_pts))
        diffs = []
        for age in common:
            for dim in ("spirit_yearly", "wealth_yearly", "fame_yearly"):
                if base_pts[age][dim] != other_pts[age][dim]:
                    diffs.append((age, dim, base_pts[age][dim], other_pts[age][dim]))
        assert not diffs, (
            f"\n  gender={gender} orientation={orient} 与 hetero 在三维上有差异(前 5):\n"
            + "\n".join(
                f"    age={a} {d}: hetero={hv} {orient}={ov}"
                for a, d, hv, ov in diffs[:5]
            )
            + "\n  违反 §4.3 — orientation 不应影响 spirit/wealth/fame。\n"
        )


def test_relationship_mode_present_for_all_orientations(curves_by_orientation):
    """v7 现代化:每种 orientation 都必须能产出 relationship_mode 描述。"""
    for key, curves in curves_by_orientation.items():
        rm = curves.get("relationship_mode")
        assert rm and rm.get("primary_mode"), (
            f"  {key}: relationship_mode 缺失或没有 primary_mode"
        )
