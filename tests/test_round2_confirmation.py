"""v8.1 · Round 2 confirmation 测试。

覆盖三件事：
1. `pairwise_discrimination_power` 的边界与对称性
2. `compute_confirmation_questions` 排除 R1 已答 + 按 pairwise dp 倒排
3. `assess_confirmation` 对四种 (status, action) 路径的判定
4. End-to-end：handshake R1 → posterior R1 → handshake R2 → posterior R2，
   验证 `phase_confirmation` 字段写入 bazi.json，且 confirmed 路径下 `decision`
   与 R1 决策一致。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from _bazi_core import (  # type: ignore  # noqa: E402
    assess_confirmation,
    compute_confirmation_questions,
    decide_phase,
    pairwise_discrimination_power,
)
from _question_bank import get_static_questions  # type: ignore  # noqa: E402
from solve_bazi import solve  # type: ignore  # noqa: E402

import handshake  # type: ignore  # noqa: E402
import phase_posterior  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# §1 pairwise_discrimination_power 行为
# ---------------------------------------------------------------------------

def test_pairwise_dp_symmetric_and_zero_when_identical():
    qs = get_static_questions()
    q = qs[0]
    a = "day_master_dominant"
    b = "floating_dms_to_cong_cai"
    dp_ab = pairwise_discrimination_power(q, a, b)
    dp_ba = pairwise_discrimination_power(q, b, a)
    assert dp_ab == pytest.approx(dp_ba)
    assert pairwise_discrimination_power(q, a, a) == pytest.approx(0.0)
    assert 0.0 <= dp_ab <= 2.0


def test_pairwise_dp_zero_when_phase_missing():
    qs = get_static_questions()
    q = qs[0]
    # 题库不会有 "fake_phase"，应安全返回 0
    assert pairwise_discrimination_power(q, "day_master_dominant", "fake_phase") == 0.0


# ---------------------------------------------------------------------------
# §2 compute_confirmation_questions 排除 + 排序
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cong_cai_bazi():
    return solve(
        pillars_str="丙子 庚子 己卯 己巳",
        gregorian=None,
        gender="F",
        birth_year=1936,
    )


def test_confirmation_questions_exclude_asked(cong_cai_bazi):
    decided = "floating_dms_to_cong_cai"
    runner_up = "pseudo_following"
    asked = ["D1_Q4_siblings", "D2_Q1_partner_attraction_type"]
    qs = compute_confirmation_questions(
        bazi_dict=cong_cai_bazi,
        decided_phase=decided,
        runner_up_phase=runner_up,
        exclude_ids=asked,
        top_k=8,
    )
    assert len(qs) > 0, "应至少返回 1 道 confirmation 题"
    returned_ids = {q["id"] for q in qs}
    assert not (returned_ids & set(asked)), "返回的题不能包含 R1 已答过的"
    # 按 pairwise dp 倒排
    dps = [q["discrimination_power"] for q in qs]
    assert dps == sorted(dps, reverse=True), "confirmation 题必须按 dp 倒排"
    # 每题都标 pairwise_target
    for q in qs:
        assert q["pairwise_target"] == {"a": decided, "b": runner_up}


def test_confirmation_questions_respect_top_k(cong_cai_bazi):
    qs = compute_confirmation_questions(
        bazi_dict=cong_cai_bazi,
        decided_phase="floating_dms_to_cong_cai",
        runner_up_phase="day_master_dominant",
        exclude_ids=[],
        top_k=3,
    )
    assert len(qs) <= 3


# ---------------------------------------------------------------------------
# §3 assess_confirmation 四条路径
# ---------------------------------------------------------------------------

def test_assess_confirmation_confirmed():
    a = assess_confirmation("X", 0.8, "X", 0.95)
    assert a["status"] == "confirmed"
    assert a["action"] == "render"


def test_assess_confirmation_weakly_confirmed():
    a = assess_confirmation("X", 0.8, "X", 0.75)
    assert a["status"] == "weakly_confirmed"
    assert a["action"] == "render_with_caveat"


def test_assess_confirmation_uncertain():
    a = assess_confirmation("X", 0.8, "X", 0.50)
    assert a["status"] == "uncertain"
    assert a["action"] == "escalate"


def test_assess_confirmation_decision_changed():
    a = assess_confirmation("X", 0.8, "Y", 0.85)
    assert a["status"] == "decision_changed"
    assert a["action"] == "escalate"


# ---------------------------------------------------------------------------
# §4 End-to-end: handshake R1 → R2 → posterior 合并 + confirmation_status 写入
# ---------------------------------------------------------------------------

def test_e2e_round2_confirmed_path(tmp_path: Path, cong_cai_bazi):
    bazi = dict(cong_cai_bazi)
    # R1 handshake
    h1 = handshake.build(bazi=bazi, curves=None, current_year=2026, enable_d3=False)
    assert h1["round"] == 1
    assert h1["questions"], "R1 必须返回非空题集"

    # 模拟 cong_cai 倾向的 R1 答案：取最像 cong_cai 的选项
    r1_answers = {}
    for q in h1["questions"][:6]:
        cong_row = q["likelihood_table"].get("floating_dms_to_cong_cai", {})
        if not cong_row:
            continue
        best_opt = max(cong_row.items(), key=lambda x: x[1])[0]
        r1_answers[q["id"]] = best_opt

    # R1 posterior
    new_bazi = phase_posterior.update_posterior(bazi, h1, r1_answers)
    assert new_bazi["phase_decision"]["decision"] == "floating_dms_to_cong_cai"
    assert new_bazi["phase_decision"]["confidence"] in ("high", "mid")

    # R2 handshake：基于 R1 决策的 confirmation 题
    h2 = handshake.build_round2(
        bazi=new_bazi,
        r1_handshake=h1,
        r1_user_answers=r1_answers,
        curves=None,
        current_year=2026,
        confirm_top_k=6,
        enable_d3=False,
    )
    assert h2["round"] == 2
    assert h2["round1_summary"]["decision"] == "floating_dms_to_cong_cai"
    assert h2["pairwise_target"]["a"] == "floating_dms_to_cong_cai"
    # R2 题不能含 R1 已答过的
    r2_ids = {q["id"] for q in h2["questions"]}
    assert not (r2_ids & set(r1_answers.keys())), "R2 不能复用 R1 已答题"

    # R2 答案：继续选最像 cong_cai 的选项
    r2_answers = {}
    for q in h2["questions"]:
        cong_row = q["likelihood_table"].get("floating_dms_to_cong_cai", {})
        if not cong_row:
            continue
        best_opt = max(cong_row.items(), key=lambda x: x[1])[0]
        r2_answers[q["id"]] = best_opt

    # R2 posterior + confirmation
    final_bazi, confirmation = phase_posterior.update_posterior_round2(
        bazi=new_bazi,
        r1_handshake=h1,
        r1_answers=r1_answers,
        r2_handshake=h2,
        r2_answers=r2_answers,
    )
    assert confirmation["status"] in ("confirmed", "weakly_confirmed")
    assert confirmation["action"] in ("render", "render_with_caveat")
    assert final_bazi["phase"]["confirmation_status"] == confirmation["status"]
    assert final_bazi["phase_confirmation"]["status"] == confirmation["status"]
    assert final_bazi["phase_confirmation"]["n_r1_answers"] == len(r1_answers)
    assert final_bazi["phase_confirmation"]["n_r2_answers"] == len(r2_answers)
    # decision 应稳定为 cong_cai
    assert final_bazi["phase"]["id"] == "floating_dms_to_cong_cai"


def test_e2e_round2_decision_changed_path(tmp_path: Path, cong_cai_bazi):
    """模拟用户 R1 答 cong_cai，但 R2 完全反过来选最像 day_master_dominant 的选项。

    单单凭 R2 5-6 道软证据未必能翻盘，但本测试只需证明 confirmation_status 字段被
    正确计算 + 写入即可（confirmed / weakly_confirmed 两种合理结果都接受）。
    """
    bazi = dict(cong_cai_bazi)
    h1 = handshake.build(bazi=bazi, curves=None, current_year=2026, enable_d3=False)

    r1_answers = {}
    for q in h1["questions"][:6]:
        cong_row = q["likelihood_table"].get("floating_dms_to_cong_cai", {})
        if cong_row:
            r1_answers[q["id"]] = max(cong_row.items(), key=lambda x: x[1])[0]

    new_bazi = phase_posterior.update_posterior(bazi, h1, r1_answers)
    h2 = handshake.build_round2(
        bazi=new_bazi,
        r1_handshake=h1,
        r1_user_answers=r1_answers,
        curves=None,
        current_year=2026,
        confirm_top_k=6,
        enable_d3=False,
    )

    # R2 故意全选 day_master_dominant 倾向最强的选项
    r2_answers = {}
    for q in h2["questions"]:
        dm_row = q["likelihood_table"].get("day_master_dominant", {})
        if dm_row:
            r2_answers[q["id"]] = max(dm_row.items(), key=lambda x: x[1])[0]

    final_bazi, confirmation = phase_posterior.update_posterior_round2(
        bazi=new_bazi,
        r1_handshake=h1,
        r1_answers=r1_answers,
        r2_handshake=h2,
        r2_answers=r2_answers,
    )
    # confirmation_status 必须是已定义的四种之一
    assert confirmation["status"] in (
        "confirmed", "weakly_confirmed", "uncertain", "decision_changed"
    )
    assert confirmation["action"] in ("render", "render_with_caveat", "escalate")
    # decision 与 confirmation 互相对齐
    assert final_bazi["phase"]["id"] == confirmation["r2_decision"]
    assert final_bazi["phase_decision"]["decision"] == confirmation["r2_decision"]


def test_round2_handshake_requires_r1_phase_decision():
    """没跑过 R1 phase_posterior 的 bazi（phase_decision 缺失）应明确报错。"""
    raw = solve(
        pillars_str="丙子 庚子 己卯 己巳",
        gregorian=None,
        gender="F",
        birth_year=1936,
    )
    bazi_no_pd = {k: v for k, v in raw.items() if k != "phase_decision"}
    with pytest.raises(ValueError, match="phase_decision"):
        handshake.build_round2(
            bazi=bazi_no_pd,
            r1_handshake=None,
            r1_user_answers={},
            curves=None,
            current_year=2026,
            enable_d3=False,
        )
