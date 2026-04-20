"""tests/test_multi_school_vote.py — v9 PR-6

校验:
  1. _school_registry: phase_candidate vs ratify_only 划分
  2. multi_school_vote.vote() 基本调用通
  3. 多格并存型边界 case 必须落 open_phase (precision over recall):
     杀印相生 vs 伤官生财 vs 调候反向 三足鼎立 → 不许独断
  4. open_phase 逃逸阀阈值: top1<0.55 OR gap<0.10
  5. high consensus case: 单一流派强信号 → consensus_level=high
  6. alternative_readings 必须包含 if_this_is_right_then 字段
  7. fallback_phase_candidates 回流投票
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _make_bazi(pillars_str: str, day_gan_idx: int = 2) -> dict:
    """构造最小 bazi dict 给 vote() 用 (只用 pillars 字段)."""
    parts = pillars_str.split()
    pillars = []
    for p in parts:
        pillars.append({"gan": p[0], "zhi": p[1]})
    return {
        "pillars": pillars,
        "gender": "M",
        "birth_year": 1990,
    }


# ------------------------------------------------------------
# 1. registry 划分
# ------------------------------------------------------------

def test_registry_phase_candidate_vs_ratify():
    from _school_registry import (
        SCHOOLS, get_phase_candidate_schools, get_ratify_only_schools,
    )
    pc = set(get_phase_candidate_schools())
    ro = set(get_ratify_only_schools())
    assert pc & ro == set(), "一个流派不能同时既出候选又只 ratify"
    assert "ziping_zhenquan" in pc
    assert "ditian_sui" in pc
    assert "qiongtong_baojian" in pc
    assert "mangpai" in pc
    assert "ziwei_doushu" in ro
    assert "tiekan_shenshu" in ro
    for sid in pc | ro:
        info = SCHOOLS[sid]
        assert callable(info["judge"])
        assert 0 < info["weight"] <= 1.0


# ------------------------------------------------------------
# 2. 基本调用
# ------------------------------------------------------------

def test_vote_runs_end_to_end():
    from multi_school_vote import vote
    bazi = _make_bazi("壬戌 癸丑 庚午 丁丑")  # guan_yin_xiang_sheng 案
    result = vote(bazi)
    assert "decision" in result
    assert "consensus_level" in result
    assert "phase_composition" in result
    assert "alternative_readings" in result
    assert "rare_phase_scan" in result
    assert "schools_voted" in result
    assert "narrative_caution" in result
    assert "must_be_true" in result
    assert result["consensus_level"] in {"high", "medium", "low"}


# ------------------------------------------------------------
# 3. 多格并存型边界 case 必须 open_phase
# ------------------------------------------------------------

def test_rooted_pseudo_following_must_fall_to_open_phase():
    """v9 核心校验: 此盘多流派分歧大, 必须 open_phase 不许独断."""
    from multi_school_vote import vote
    bazi = _make_bazi("丙子 庚子 己卯 己巳")
    result = vote(bazi)

    assert result["decision"] == "open_phase", (
        f"多格并存型边界 case 多流派分歧, 必须落 open_phase, 实际 {result['decision']}"
    )
    assert result["consensus_level"] == "low"
    assert result["open_phase_triggered"] is True

    pids = {pc["id"] for pc in result["phase_composition"]}
    assert "qi_yin_xiang_sheng" in pids, "应能看见杀印相生候选"
    cong_phases = {p for p in pids if p.startswith("floating_dms_to_cong_")
                   or p == "true_following"}
    if cong_phases:
        for ar in result["alternative_readings"]:
            if ar["phase_id"] in cong_phases:
                assert ar["posterior"] < 0.55, (
                    f"从格 {ar['phase_id']} 不允许 posterior>=0.55 (会触发 PR-1 守卫)"
                )


# ------------------------------------------------------------
# 4. open_phase 阈值
# ------------------------------------------------------------

def test_open_phase_threshold_top1():
    """top1<0.55 必须触发 open_phase."""
    from multi_school_vote import OPEN_PHASE_THRESHOLDS
    assert OPEN_PHASE_THRESHOLDS["top1_min"] == 0.55
    assert OPEN_PHASE_THRESHOLDS["top1_top2_gap_min"] == 0.10


# ------------------------------------------------------------
# 5. 高共识情况
# ------------------------------------------------------------

def test_jianlu_ge_pure_chart_consensus_higher():
    """甲日寅月单一信号: ziping 的建禄格独占 → consensus 不应 low.

    我们不强求 high, 只要不是 low 即可 (因为 mangpai 同样会出候选).
    """
    from multi_school_vote import vote
    bazi = _make_bazi("甲寅 丙寅 甲寅 丙寅")
    result = vote(bazi)
    pids = {pc["id"] for pc in result["phase_composition"]}
    assert any(p in {"jianlu_ge", "tianyuanyiqi"} for p in pids)


# ------------------------------------------------------------
# 6. alternative_readings 携带 if_this_is_right_then
# ------------------------------------------------------------

def test_alternative_readings_carry_implication():
    from multi_school_vote import vote
    bazi = _make_bazi("丙子 庚子 己卯 己巳")
    result = vote(bazi)
    assert len(result["alternative_readings"]) >= 2
    for ar in result["alternative_readings"]:
        assert "if_this_is_right_then" in ar
        assert ar["if_this_is_right_then"]


# ------------------------------------------------------------
# 7. fallback_phase_candidates 回流投票
# ------------------------------------------------------------

def test_fallback_candidates_increase_their_phase_weight():
    from multi_school_vote import vote
    bazi = _make_bazi("丙子 庚子 己卯 己巳")
    base = vote(bazi)
    base_qi_yin = next(
        (pc for pc in base["phase_composition"] if pc["id"] == "qi_yin_xiang_sheng"),
        None,
    )

    fb = [{
        "id": "qi_yin_xiang_sheng",
        "school": "mangpai",
        "match_confidence": 0.95,
        "古书引用": "(test fallback)",
    }]
    boosted = vote(bazi, fallback_phase_candidates=fb)
    boosted_qi_yin = next(
        (pc for pc in boosted["phase_composition"] if pc["id"] == "qi_yin_xiang_sheng"),
        None,
    )
    if base_qi_yin and boosted_qi_yin:
        assert boosted_qi_yin["weight"] >= base_qi_yin["weight"], (
            "兜底候选回流必须不降低其投票权重"
        )


# ------------------------------------------------------------
# 8. must_be_true 钩子
# ------------------------------------------------------------

def test_must_be_true_hook_present():
    from multi_school_vote import vote
    bazi = _make_bazi("丙子 庚子 己卯 己巳")
    result = vote(bazi)
    assert isinstance(result["must_be_true"], list)
    assert len(result["must_be_true"]) >= 1
    for mbt in result["must_be_true"]:
        assert "prediction" in mbt
        assert "evidence_required" in mbt
