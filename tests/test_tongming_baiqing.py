"""v9 L1-L7 · 木火通明 + 金白水清 e2e acceptance 回归测试。

合并测试两个流通做功类 phase（结构同质，秀气外发）：
  - mu_huo_tong_ming   (trigger=巳午, 火地)
  - jin_bai_shui_qing  (trigger=亥子, 水地)

固化:
  - L1 _phase_registry: 两个 phase 注册 + trigger_branches 正确
  - L3 _question_bank: D6 三题 likelihood 行存在 + C 主导 (顺势而为)
  - L5 by-design 留空 (无明确事件反转规则) → 不测反转
  - L6 score_curves: trigger 流年 (巳午 / 亥子) geju 派显著抬升

合成测试输入:
  - 木火通明: `丙午 甲午 甲寅 丁卯` (甲日, 月令午火, 火支多)
  - 金白水清: `壬子 壬子 庚申 壬午` (庚日, 壬×3 + 子×2 ≥ 3 水)
  - 均不指向任何特定个人
"""
from __future__ import annotations

import copy

import pytest

from solve_bazi import solve  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast]


MHTM_PILLARS = "丙午 甲午 甲寅 丁卯"  # 木火通明
JBSQ_PILLARS = "壬子 壬子 庚申 壬午"  # 金白水清
SYNTHETIC_BIRTH_YEAR = 1928


@pytest.fixture(scope="module")
def bazi_mhtm() -> dict:
    return solve(MHTM_PILLARS, None, "M", SYNTHETIC_BIRTH_YEAR)


@pytest.fixture(scope="module")
def bazi_jbsq() -> dict:
    return solve(JBSQ_PILLARS, None, "M", SYNTHETIC_BIRTH_YEAR)


# ──────────────────────────────────────────────────────────
# L1
# ──────────────────────────────────────────────────────────

def test_l1_tongming_baiqing_registered():
    from _phase_registry import get, exists  # type: ignore

    for pid, expected_triggers in [
        ("mu_huo_tong_ming", {"巳", "午"}),
        ("jin_bai_shui_qing", {"亥", "子"}),
    ]:
        assert exists(pid), f"{pid} 未注册"
        meta = get(pid)
        assert meta.dimension == "zuogong"
        assert "滴天髓" in meta.source, f"{pid} 缺《滴天髓》出处"
        triggers = set(meta.zuogong_trigger_branches)
        assert expected_triggers.issubset(triggers), (
            f"{pid} 缺 trigger {expected_triggers}: 实际 {triggers}"
        )
        # by-design 留空, 不要求 reversal_overrides
        assert meta.reversal_overrides == {}, (
            f"{pid} 不应有 reversal_overrides (by-design 留空), "
            f"实际: {meta.reversal_overrides}"
        )


# ──────────────────────────────────────────────────────────
# L3
# ──────────────────────────────────────────────────────────

def test_l3_d6_likelihood_for_tongming_baiqing():
    from _question_bank import D6_QUESTIONS  # type: ignore

    for q in D6_QUESTIONS:
        for pid in ("mu_huo_tong_ming", "jin_bai_shui_qing"):
            row = q.likelihood_table.get(pid, {})
            assert row, f"{q.id} 缺 {pid} likelihood row"
            assert not all(abs(v - 0.25) < 0.01 for v in row.values()), (
                f"{q.id} {pid} likelihood 均匀, 失去判别力"
            )

    # D6_Q1 上, C (随机应变 / 顺势) 应是该族的最高项
    q1 = next(q for q in D6_QUESTIONS if q.id == "D6_Q1_agency_style")
    for pid in ("mu_huo_tong_ming", "jin_bai_shui_qing"):
        row = q1.likelihood_table[pid]
        top_opt = max(row.items(), key=lambda kv: kv[1])[0]
        assert top_opt == "C", (
            f"{pid} D6_Q1 top 应为 C (顺势而为), 实际 {top_opt}: {row}"
        )


# ──────────────────────────────────────────────────────────
# L6: 木火通明 trigger=巳午
# ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def score_comparison_mhtm(bazi_mhtm):
    from score_curves import score, apply_phase_override  # type: ignore

    # baseline 显式锁 day_master_dominant —— v9.2 起 P0 派别中立通道可能让默认
    # phase 变成某个 zuogong 格，与本测试的"override 触发"比较失去基线意义。
    b0 = copy.deepcopy(bazi_mhtm)
    b0.pop("phase", None)
    apply_phase_override(b0, "day_master_dominant")
    out0 = score(b0, age_start=0, age_end=40)
    b1 = copy.deepcopy(bazi_mhtm)
    apply_phase_override(b1, "mu_huo_tong_ming")
    out1 = score(b1, age_start=0, age_end=40)
    return out0["points"], out1["points"]


def test_l6_mu_huo_tong_ming_lifts_geju_on_fire_years(score_comparison_mhtm):
    y0, y1 = score_comparison_mhtm
    by_age0 = {p["age"]: p for p in y0}
    by_age1 = {p["age"]: p for p in y1}

    trigger_zhi = {"巳", "午"}
    trigger_ages = [a for a, p in by_age1.items() if p["ganzhi"][-1] in trigger_zhi]
    assert len(trigger_ages) >= 4, (
        f"巳午 trigger 流年样本 {len(trigger_ages)} 过少"
    )

    deltas = [
        by_age1[a]["school_scores"]["spirit"]["geju"]
        - by_age0[a]["school_scores"]["spirit"]["geju"]
        for a in trigger_ages
    ]
    avg = sum(deltas) / len(deltas)
    assert avg >= 2.0, (
        f"木火通明 trigger 年 spirit geju avg delta={avg:.2f} < 2.0"
    )


# ──────────────────────────────────────────────────────────
# L6: 金白水清 trigger=亥子
# ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def score_comparison_jbsq(bazi_jbsq):
    from score_curves import score, apply_phase_override  # type: ignore

    # baseline 显式锁 day_master_dominant —— v9.2 起 P0 派别中立通道可能让默认
    # phase 变成某个 zuogong 格，与本测试的"override 触发"比较失去基线意义。
    b0 = copy.deepcopy(bazi_jbsq)
    b0.pop("phase", None)
    apply_phase_override(b0, "day_master_dominant")
    out0 = score(b0, age_start=0, age_end=40)
    b1 = copy.deepcopy(bazi_jbsq)
    apply_phase_override(b1, "jin_bai_shui_qing")
    out1 = score(b1, age_start=0, age_end=40)
    return out0["points"], out1["points"]


def test_l6_jin_bai_shui_qing_lifts_geju_on_water_years(score_comparison_jbsq):
    y0, y1 = score_comparison_jbsq
    by_age0 = {p["age"]: p for p in y0}
    by_age1 = {p["age"]: p for p in y1}

    trigger_zhi = {"亥", "子"}
    trigger_ages = [a for a, p in by_age1.items() if p["ganzhi"][-1] in trigger_zhi]
    assert len(trigger_ages) >= 4, (
        f"亥子 trigger 流年样本 {len(trigger_ages)} 过少"
    )

    deltas = [
        by_age1[a]["school_scores"]["spirit"]["geju"]
        - by_age0[a]["school_scores"]["spirit"]["geju"]
        for a in trigger_ages
    ]
    avg = sum(deltas) / len(deltas)
    assert avg >= 2.0, (
        f"金白水清 trigger 年 spirit geju avg delta={avg:.2f} < 2.0"
    )
