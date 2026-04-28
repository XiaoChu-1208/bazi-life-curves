#!/usr/bin/env python3
"""event_elicit_cli.py — 事件 ask-loop 的 TS-Python 边界 CLI

一脚本承包所有「无需 LLM 的纯逻辑操作」，由 TS handler 通过 subprocess 调用。
LLM 相关的步骤（事件类型预测 / 似然估计 / 自述分类 / 验证题题面）全部
留在 TS handler 端，方便统一管理 think_start/end SSE、retry、超时。

调用模式：
    python3 event_elicit_cli.py <operation> [--state-json STR] [--bazi PATH] ...

每次调用从 stdin 不收任何输入；从命令行参数读 state JSON 字符串；
输出**单行 JSON** 到 stdout（错误走 stderr + exit 1）。

所有操作的 state schema：
  {
    "candidate_phases": ["pid1", "pid2", ...],
    "posterior": {"pid1": 0.4, ...},
    "asked_years": [2018, 2020, ...],
    "answer_log": [{...}, ...]
  }
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import event_year_predictor as predictor  # type: ignore
import event_elicit as ee  # type: ignore
import event_elicit_stage_b as stage_b  # type: ignore
import event_verification as verification  # type: ignore


# ============================================================================
# state JSON 序列化 / 反序列化
# ============================================================================

def _state_to_dict(s: ee.EventElicitState) -> Dict[str, Any]:
    return {
        "candidate_phases": list(s.candidate_phases),
        "posterior": dict(s.posterior),
        "asked_years": list(s.asked_years),
        "answer_log": list(s.answer_log),
    }


def _state_from_dict(d: Dict[str, Any]) -> ee.EventElicitState:
    return ee.EventElicitState(
        candidate_phases=list(d.get("candidate_phases", [])),
        posterior=dict(d.get("posterior", {})),
        asked_years=list(d.get("asked_years", [])),
        answer_log=list(d.get("answer_log", [])),
    )


def _pick_to_dict(p: predictor.DisjointPick) -> Dict[str, Any]:
    return {
        "year": p.year,
        "sole_phase": p.sole_phase,
        "all_predictions": dict(p.all_predictions),
    }


def _pick_from_dict(d: Dict[str, Any]) -> predictor.DisjointPick:
    return predictor.DisjointPick(
        year=int(d["year"]),
        sole_phase=str(d["sole_phase"]),
        all_predictions={k: bool(v) for k, v in d["all_predictions"].items()},
    )


def _vpick_to_dict(p: verification.VerificationPick) -> Dict[str, Any]:
    return {
        "year": p.year,
        "user_age": p.user_age,
        "top1_phase": p.top1_phase,
        "top1_phase_label": p.top1_phase_label,
        "other_phases_silent": list(p.other_phases_silent),
    }


def _vpick_from_dict(d: Dict[str, Any]) -> verification.VerificationPick:
    return verification.VerificationPick(
        year=int(d["year"]),
        user_age=int(d["user_age"]),
        top1_phase=str(d["top1_phase"]),
        top1_phase_label=str(d["top1_phase_label"]),
        other_phases_silent=list(d.get("other_phases_silent", [])),
    )


# ============================================================================
# 操作分发
# ============================================================================

def op_init(args: argparse.Namespace) -> Dict[str, Any]:
    """从 elicit 后验初始化事件 state。"""
    elicit_post = json.loads(args.elicit_posterior)
    state = ee.init_event_state(elicit_post, top_k=args.top_k)
    return {"state": _state_to_dict(state)}


def op_pick_disjoint(args: argparse.Namespace) -> Dict[str, Any]:
    """挑下一批 disjoint 年（Stage A）。"""
    state = _state_from_dict(json.loads(args.state_json))
    bazi = json.loads(open(args.bazi, encoding="utf-8").read())
    batch = ee.next_question_batch(
        state, bazi, batch_size=args.batch_size,
        eig_threshold=args.eig_threshold)
    return {"batch": [_pick_to_dict(p) for p in batch]}


def op_update_stage_a(args: argparse.Namespace) -> Dict[str, Any]:
    """Stage A 答案 → Bayesian 更新。"""
    state = _state_from_dict(json.loads(args.state_json))
    batch = [_pick_from_dict(d) for d in json.loads(args.batch_json)]
    answers = json.loads(args.answers_json)
    # answers JSON: {"2018": "yes" | {"discrete":..., ...}, ...}
    parsed_answers: Dict[int, ee.AnswerInput] = {}
    for k, v in answers.items():
        parsed_answers[int(k)] = v
    new_state = ee.update_with_answers(state, batch, parsed_answers)
    return {"state": _state_to_dict(new_state)}


def op_find_overlap(args: argparse.Namespace) -> Dict[str, Any]:
    """找候选重叠年（Stage B 第一步）。"""
    state = _state_from_dict(json.loads(args.state_json))
    bazi = json.loads(open(args.bazi, encoding="utf-8").read())
    cands = stage_b.find_overlap_year_candidates(
        state, bazi, max_candidates=args.max_candidates)
    return {
        "candidates": [
            {"year": c.year, "user_age": c.user_age,
             "predicting_phases": c.predicting_phases}
            for c in cands
        ],
    }


def op_pick_stage_b(args: argparse.Namespace) -> Dict[str, Any]:
    """v2 算法版：直接从 candidates + state 挑分歧最大年（零 LLM）。"""
    state = _state_from_dict(json.loads(args.state_json))
    cands_raw = json.loads(args.candidates_json)
    cands = [
        stage_b.OverlapYearCandidate(
            year=int(c["year"]),
            user_age=int(c["user_age"]),
            predicting_phases=list(c["predicting_phases"]))
        for c in cands_raw
    ]
    pick = stage_b.select_best_overlap_year(state, cands)
    if pick is None:
        return {"pick": None}
    return {
        "pick": {
            "year": pick.year,
            "user_age": pick.user_age,
            "candidate_categories": list(pick.candidate_categories),
            "phase_categories": dict(pick.phase_categories),
            "predicting_phases": list(pick.predicting_phases),
            "divergence_score": pick.divergence_score,
        },
    }


def op_update_stage_b(args: argparse.Namespace) -> Dict[str, Any]:
    """v3 算法版：用 categorical 似然查表做 Bayesian 更新（零 LLM）。

    pick_json: {year, user_age, candidate_categories, phase_categories,
                predicting_phases, divergence_score}
    answer_json: {discrete, chosen_categories?, free_text?, summary?}
    """
    state = _state_from_dict(json.loads(args.state_json))
    pick_raw = json.loads(args.pick_json)
    pick = stage_b.StageBPick(
        year=int(pick_raw["year"]),
        user_age=int(pick_raw["user_age"]),
        candidate_categories=list(pick_raw.get("candidate_categories", [])),
        phase_categories={k: list(v) for k, v in pick_raw.get("phase_categories", {}).items()},
        predicting_phases=list(pick_raw.get("predicting_phases", [])),
        divergence_score=float(pick_raw.get("divergence_score", 0.0)),
    )
    ans = json.loads(args.answer_json)
    discrete = str(ans.get("discrete", "dunno"))
    chosen = list(ans.get("chosen_categories", []))
    free_text = str(ans.get("free_text", "") or "")
    summary = str(ans.get("summary", "") or "")
    new_state = stage_b.update_with_category_answer(
        state, pick, discrete, chosen, free_text, summary)
    return {"state": _state_to_dict(new_state)}


def op_find_verification(args: argparse.Namespace) -> Dict[str, Any]:
    """找强独占年用作验证题。"""
    state = _state_from_dict(json.loads(args.state_json))
    bazi = json.loads(open(args.bazi, encoding="utf-8").read())
    pick = verification.find_verification_year(
        state, bazi, args.top1, args.top1_label)
    if pick is None:
        return {"pick": None}
    return {
        "pick": _vpick_to_dict(pick),
        "fallback_text": verification.fallback_question_text(pick),
    }


def op_update_verification(args: argparse.Namespace) -> Dict[str, Any]:
    """验证题答案 → 更新后验。"""
    state = _state_from_dict(json.loads(args.state_json))
    pick = _vpick_from_dict(json.loads(args.pick_json))
    new_state = verification.update_with_verification(
        state, pick, args.answer)
    return {"state": _state_to_dict(new_state)}


def op_evaluate(args: argparse.Namespace) -> Dict[str, Any]:
    """融合 elicit + 事件后验，给三档判定。"""
    state = _state_from_dict(json.loads(args.state_json))
    elicit_post = json.loads(args.elicit_posterior)
    fused = ee.fuse_posteriors(
        elicit_post, state,
        elicit_weight=args.elicit_weight,
        event_weight=args.event_weight,
    )
    verdict = ee.evaluate_convergence(fused)
    return {"fused_posterior": fused, "verdict": verdict}


# ============================================================================
# main
# ============================================================================

def main() -> None:
    p = argparse.ArgumentParser(description="event ask-loop CLI")
    sub = p.add_subparsers(dest="op", required=True)

    s = sub.add_parser("init")
    s.add_argument("--elicit-posterior", required=True)
    s.add_argument("--top-k", type=int, default=4)

    s = sub.add_parser("pick-disjoint")
    s.add_argument("--bazi", required=True)
    s.add_argument("--state-json", required=True)
    s.add_argument("--batch-size", type=int, default=4)
    s.add_argument("--eig-threshold", type=float, default=0.05)

    s = sub.add_parser("update-stage-a")
    s.add_argument("--state-json", required=True)
    s.add_argument("--batch-json", required=True)
    s.add_argument("--answers-json", required=True)

    s = sub.add_parser("find-overlap")
    s.add_argument("--bazi", required=True)
    s.add_argument("--state-json", required=True)
    s.add_argument("--max-candidates", type=int, default=8)

    s = sub.add_parser("pick-stage-b")
    s.add_argument("--state-json", required=True)
    s.add_argument("--candidates-json", required=True)

    s = sub.add_parser("update-stage-b")
    s.add_argument("--state-json", required=True)
    s.add_argument("--pick-json", required=True)
    s.add_argument("--answer-json", required=True)

    s = sub.add_parser("find-verification")
    s.add_argument("--bazi", required=True)
    s.add_argument("--state-json", required=True)
    s.add_argument("--top1", required=True)
    s.add_argument("--top1-label", default="")

    s = sub.add_parser("update-verification")
    s.add_argument("--state-json", required=True)
    s.add_argument("--pick-json", required=True)
    s.add_argument("--answer", required=True,
                   choices=["yes", "partial", "no", "dunno"])

    s = sub.add_parser("evaluate")
    s.add_argument("--state-json", required=True)
    s.add_argument("--elicit-posterior", required=True)
    s.add_argument("--elicit-weight", type=float, default=1.0)
    s.add_argument("--event-weight", type=float, default=1.2)

    args = p.parse_args()

    op_map = {
        "init": op_init,
        "pick-disjoint": op_pick_disjoint,
        "update-stage-a": op_update_stage_a,
        "find-overlap": op_find_overlap,
        "pick-stage-b": op_pick_stage_b,
        "update-stage-b": op_update_stage_b,
        "find-verification": op_find_verification,
        "update-verification": op_update_verification,
        "evaluate": op_evaluate,
    }
    fn = op_map[args.op]
    try:
        result = fn(args)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        sys.stderr.write(f"[event_elicit_cli] {args.op} failed: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
