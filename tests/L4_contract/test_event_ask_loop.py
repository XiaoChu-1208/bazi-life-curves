"""L4 · v9.6 事件 ask-loop 引擎契约层。

守 references/event_ask_loop_protocol.md §9 工程不变量：

- §1.3 似然表归一性 + 「记不清」中性铁律
- §1.4 Bayesian 更新后归一
- §2.1 Stage B 静态映射表非空 + 类别全集 ≤ 12 大类
- §4 收敛阈值 4 档（high 0.80 / soft 0.70 / weak 0.60 / refuse < 0.60）
- §5 fuse_posteriors 返回 keys ⊆ candidate_phases 且归一
- §6 apply_event_finalize 写回 bazi.json 后必带 event_loop_finalized=true +
  elicitation_path="event_loop_v9.6"

测试不依赖 LLM、不依赖网络、不依赖 examples/——纯 Bayesian 数学单测。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.contract]


# ---------------------------------------------------------------------------
# §1 Stage A 似然表 + 中性铁律
# ---------------------------------------------------------------------------

def test_stage_a_likelihood_tables_normalized():
    """两条似然表必须归一（各加和 == 1.0）。"""
    import event_elicit as ee
    assert abs(sum(ee.LIKELIHOOD_PREDICTED.values()) - 1.0) < 1e-9
    assert abs(sum(ee.LIKELIHOOD_NOT_PREDICTED.values()) - 1.0) < 1e-9


def test_stage_a_dunno_must_be_neutral():
    """ANSWER_DUNNO 在两条似然表里必须等概率，否则违反「不替用户记忆」铁律。"""
    import event_elicit as ee
    assert (
        ee.LIKELIHOOD_PREDICTED[ee.ANSWER_DUNNO]
        == ee.LIKELIHOOD_NOT_PREDICTED[ee.ANSWER_DUNNO]
    ), "ANSWER_DUNNO 必须中性"


def test_stage_a_yes_supports_predicted_phase():
    """yes 答案的似然必须 P(yes|predicted) > P(yes|not_predicted)，否则方向反了。"""
    import event_elicit as ee
    assert (
        ee.LIKELIHOOD_PREDICTED[ee.ANSWER_YES]
        > ee.LIKELIHOOD_NOT_PREDICTED[ee.ANSWER_YES]
    )


def test_stage_a_no_undermines_predicted_phase():
    """no 答案的似然必须 P(no|predicted) < P(no|not_predicted)，否则方向反了。"""
    import event_elicit as ee
    assert (
        ee.LIKELIHOOD_PREDICTED[ee.ANSWER_NO]
        < ee.LIKELIHOOD_NOT_PREDICTED[ee.ANSWER_NO]
    )


# ---------------------------------------------------------------------------
# §1.4 Bayesian 更新归一性 + 单调性
# ---------------------------------------------------------------------------

def test_init_event_state_uniform_over_top_k():
    """init_event_state 应在 top-k 候选上输出 uniform 后验。"""
    import event_elicit as ee
    elicit_post = {"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.07, "e": 0.03}
    state = ee.init_event_state(elicit_post, top_k=3)
    assert len(state.candidate_phases) == 3
    assert set(state.candidate_phases) == {"a", "b", "c"}
    p0 = 1.0 / 3
    for pid in state.candidate_phases:
        assert abs(state.posterior[pid] - p0) < 1e-9


def test_update_with_answers_keeps_normalized():
    """每轮更新后 posterior 必须归一（Σ == 1.0）。"""
    import event_elicit as ee
    import event_year_predictor as predictor

    state = ee.init_event_state({"a": 0.5, "b": 0.5}, top_k=2)
    # 构造一个人造 batch：2018 年只 a 命中，2020 年只 b 命中
    batch = [
        predictor.DisjointPick(year=2018, sole_phase="a", all_predictions={"a": True, "b": False}),
        predictor.DisjointPick(year=2020, sole_phase="b", all_predictions={"a": False, "b": True}),
    ]
    answers = {2018: ee.ANSWER_YES, 2020: ee.ANSWER_NO}
    new_state = ee.update_with_answers(state, batch, answers)
    assert abs(sum(new_state.posterior.values()) - 1.0) < 1e-9
    # a 在 2018 yes（命中）+ 2020 no（不命中）双重支持 → posterior(a) > posterior(b)
    assert new_state.posterior["a"] > new_state.posterior["b"]


def test_update_dunno_does_not_shift_posterior():
    """所有人答 dunno → posterior 不变（中性铁律）。"""
    import event_elicit as ee
    import event_year_predictor as predictor

    state = ee.init_event_state({"a": 0.5, "b": 0.5}, top_k=2)
    batch = [
        predictor.DisjointPick(year=2018, sole_phase="a", all_predictions={"a": True, "b": False}),
        predictor.DisjointPick(year=2020, sole_phase="b", all_predictions={"a": False, "b": True}),
    ]
    answers = {2018: ee.ANSWER_DUNNO, 2020: ee.ANSWER_DUNNO}
    new_state = ee.update_with_answers(state, batch, answers)
    for pid in state.candidate_phases:
        assert abs(new_state.posterior[pid] - state.posterior[pid]) < 1e-9, (
            f"{pid}: dunno 不应改变后验，但 {state.posterior[pid]:.6f} → {new_state.posterior[pid]:.6f}"
        )


# ---------------------------------------------------------------------------
# §2 Stage B 静态映射表
# ---------------------------------------------------------------------------

def test_event_categories_non_empty_strings():
    """EVENT_CATEGORIES 必须全部是非空中文字符串，且 ≤ 12 大类。"""
    import phase_event_categories as cat
    assert isinstance(cat.EVENT_CATEGORIES, tuple)
    assert 1 <= len(cat.EVENT_CATEGORIES) <= 12, "EVENT_CATEGORIES 应保持 ≤ 12 大类（UI 限制）"
    for c in cat.EVENT_CATEGORIES:
        assert isinstance(c, str) and c.strip()


def test_none_of_above_sentinel_present():
    """NONE_OF_ABOVE 哨兵字符串必须存在且不为空。"""
    import phase_event_categories as cat
    assert cat.NONE_OF_ABOVE
    assert cat.NONE_OF_ABOVE != ""


# ---------------------------------------------------------------------------
# §4 收敛阈值 4 档
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("top1_p,expected_tier", [
    (0.95, "none"),    # ≥ 0.80 high → warning_level = "none"
    (0.80, "none"),    # 边界
    (0.75, "soft"),    # ≥ 0.70 → soft
    (0.70, "soft"),
    (0.65, "weak"),    # ≥ 0.60 → weak
    (0.60, "weak"),
    (0.55, "refuse"),  # < 0.60 → refuse（注：必须 top1 > 0.5 才是真 top1）
])
def test_evaluate_convergence_tiers(top1_p: float, expected_tier: str):
    """收敛阈值四档映射，参 §4 + event_elicit.py CONFIDENCE_TIERS。

    注意：测试 top1_p 必须 > 0.5，否则 "rest" 反而成了 top1。
    实际场景里 < 0.50 是分散到 ≥ 3 个候选的极低置信，refuse 行为同样适用。
    """
    import event_elicit as ee
    posterior = {"top": top1_p, "rest": 1.0 - top1_p}
    verdict = ee.evaluate_convergence(posterior)
    assert verdict["warning_level"] == expected_tier, (
        f"top1_p={top1_p} 应得 {expected_tier} 档，但拿到 {verdict['warning_level']}"
    )


def test_evaluate_convergence_three_way_low_confidence():
    """3 候选 ≈uniform 的情况（top1 ≈ 0.34）→ refuse。"""
    import event_elicit as ee
    verdict = ee.evaluate_convergence({"a": 0.36, "b": 0.33, "c": 0.31})
    assert verdict["warning_level"] == "refuse"
    assert verdict["can_deliver"] is False


def test_evaluate_convergence_can_deliver_threshold():
    """can_deliver: tier != "refuse" 即可 deliver；< 0.60 必拒。"""
    import event_elicit as ee
    assert ee.evaluate_convergence({"a": 0.65, "b": 0.35})["can_deliver"] is True
    assert ee.evaluate_convergence({"a": 0.55, "b": 0.45})["can_deliver"] is False


# ---------------------------------------------------------------------------
# §5 fuse_posteriors 输出契约
# ---------------------------------------------------------------------------

def test_fuse_posteriors_keys_subset_of_candidates():
    """融合后验的 keys 必须 ⊆ event_state.candidate_phases。"""
    import event_elicit as ee
    state = ee.init_event_state({"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1}, top_k=2)
    # candidate_phases = {"a", "b"}
    fused = ee.fuse_posteriors({"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1}, state)
    assert set(fused.keys()) == set(state.candidate_phases) == {"a", "b"}


def test_fuse_posteriors_normalized():
    """融合后验必须归一。"""
    import event_elicit as ee
    state = ee.init_event_state({"a": 0.5, "b": 0.5}, top_k=2)
    state.posterior = {"a": 0.7, "b": 0.3}
    fused = ee.fuse_posteriors({"a": 0.6, "b": 0.4}, state)
    assert abs(sum(fused.values()) - 1.0) < 1e-9


def test_fuse_posteriors_event_weight_pulls_toward_event_channel():
    """event_weight=1.2 略大于 elicit_weight=1.0：事件通道在分歧时占微弱主导。"""
    import event_elicit as ee
    state = ee.init_event_state({"a": 0.5, "b": 0.5}, top_k=2)
    # elicit 倾向 a (0.7)，事件倾向 b (0.7) —— 完全相反
    state.posterior = {"a": 0.3, "b": 0.7}
    fused = ee.fuse_posteriors(
        {"a": 0.7, "b": 0.3}, state, elicit_weight=1.0, event_weight=1.2)
    assert fused["b"] > fused["a"], (
        "事件通道权重 1.2 > elicit 1.0，分歧时事件应略胜出"
    )


# ---------------------------------------------------------------------------
# §6 apply_event_finalize 写回字段
# ---------------------------------------------------------------------------

def test_apply_event_finalize_writes_marker_fields(tmp_path: Path):
    """apply_event_finalize 必须写入 event_loop_finalized=true + elicitation_path。

    用 examples/guan_yin_xiang_sheng.bazi.json 作为真实 fixture（含
    _finalize_phase 需要的所有字段）。复制到 tmp_path 后执行写回。
    """
    import shutil
    import subprocess

    project_root = Path(__file__).resolve().parent.parent.parent
    src = project_root / "examples" / "guan_yin_xiang_sheng.bazi.json"
    if not src.exists():
        pytest.skip(f"examples 缺 fixture：{src}")

    bazi_path = tmp_path / "bazi.json"
    shutil.copy(src, bazi_path)

    # 构造一个针对该盘的合法 posterior（用 bazi 当前 phase 的 id）
    src_bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    current_phase_id = (
        src_bazi.get("phase", {}).get("id")
        or src_bazi.get("phase_decision", {}).get("decision")
        or "guan_yin_xiang_sheng"
    )
    posterior = {current_phase_id: 0.82, "_other_dummy_": 0.18}

    scripts = project_root / "scripts"
    result = subprocess.run(
        ["python3", str(scripts / "apply_event_finalize.py"),
         "--bazi", str(bazi_path),
         "--posterior", json.dumps(posterior),
         "--stop-reason", "event_loop_converged"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, (
        f"apply_event_finalize 退出码 != 0\n"
        f"  stderr: {result.stderr[:500]}\n"
        f"  stdout: {result.stdout[:500]}"
    )

    new_bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    pd = new_bazi.get("phase_decision", {})
    assert pd.get("event_loop_finalized") is True
    assert pd.get("elicitation_path") == "event_loop_v9.6"


# ---------------------------------------------------------------------------
# §7 CLI 子命令完整性
# ---------------------------------------------------------------------------

def test_event_elicit_cli_has_all_subcommands():
    """event_elicit_cli.py 必须暴露 9 个子命令（参 SKILL.md §2.6b 编排序列）。"""
    import event_elicit_cli as cli
    expected_ops = {
        "op_init", "op_pick_disjoint", "op_update_stage_a",
        "op_find_overlap", "op_pick_stage_b", "op_update_stage_b",
        "op_find_verification", "op_update_verification", "op_evaluate",
    }
    actual_ops = {n for n in dir(cli) if n.startswith("op_")}
    assert expected_ops.issubset(actual_ops), (
        f"缺少子命令：{expected_ops - actual_ops}"
    )


# ---------------------------------------------------------------------------
# §10 与 adaptive_elicit._finalize_phase 的复用契约
# ---------------------------------------------------------------------------

def test_apply_event_finalize_reuses_adaptive_elicit_finalize():
    """apply_event_finalize 必须 import adaptive_elicit（保证字段写入逻辑同源）。"""
    import apply_event_finalize as aef
    # _finalize_phase 是 adaptive_elicit 的私有函数，aef 必须能访问到
    assert hasattr(aef, "adaptive_elicit")
    assert hasattr(aef.adaptive_elicit, "_finalize_phase")
