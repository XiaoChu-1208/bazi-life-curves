#!/usr/bin/env python3
"""scripts/handshake.py · v9

v9 hard cutover：默认问答路径改成 [scripts/adaptive_elicit.py](adaptive_elicit.py)。
本文件保留两个用途：

  1) `--round 2` confirmation 题集（**主用途**）：基于 R1 决策的 phase 与
     runner-up 之间，按 EIG（限定 2-phase 后验）挑判别力最强的题。
  2) `--round 1` 兼容入口（**deprecated**）：仅给 he_pan_orchestrator / mcp_server /
     旧 examples 兜底；输出 askquestion_payload 不带任何 phase / 后验字段。
     新代码请直接调 `adaptive_elicit.py next ...`。

R1 输出对前端只暴露 prompt + options + neutral_instruction；
phase_candidates / prior_distribution 仅留在顶层供 LLM 内部 reasoning
（下游必须遵守 elicitation_ethics §E1：禁止把这些字段呈现给用户）。

详见 references/handshake_protocol.md v9 段 + plan 自适应贝叶斯问答 v9 §A4 / §A6。
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bazi_core import (  # type: ignore
    detect_all_phase_candidates,
    _compute_prior_distribution,
    compute_question_likelihoods,
    decide_phase,
)
from _eig_selector import weighted_eig  # type: ignore
from _question_bank import (  # type: ignore
    D3_dynamic_event_question,
    FAIRNESS_BLACKLIST,
    get_static_questions,
)


# ============================================================================
# D3 动态流年题生成（与 adaptive_elicit.py 同算法 · 抽 helper 复用）
# ============================================================================

_D3_CURVE_DIM = {
    "career":   ("spirit", "fame"),
    "money":    ("wealth",),
    "emotion":  ("emotion",),
    "overall":  ("spirit", "wealth", "fame"),
}


def _avg_dim_value(point: Dict, dims: Tuple[str, ...]) -> float:
    keys = [f"{d}_yearly" for d in dims]
    vals = [point.get(k, 50.0) for k in keys]
    return sum(vals) / max(len(vals), 1)


def _generate_d3_dynamic_questions(
    bazi: Dict,
    candidate_phase_ids: List[str],
    current_year: int,
    n_questions: int = 4,
    min_age: int = 6,
    min_divergence: float = 3.0,
) -> List[Dict]:
    """跨候选 phase 跑 score_curves，找已活过年份中 phase 间预测最分歧的 n 个，
    套 D3 4 档模板生成动态题。
    """
    if len(candidate_phase_ids) < 2:
        return []

    birth_year = int(bazi.get("birth_year") or 0)
    if not birth_year:
        return []
    age_now = current_year - birth_year
    if age_now < min_age + 2:
        return []

    try:
        from score_curves import score, apply_phase_override  # type: ignore
    except Exception as e:
        print(f"[handshake] D3 skipped (score_curves import failed): {e}", file=sys.stderr)
        return []

    cand_ids = list(candidate_phase_ids[:3])
    age_end = min(age_now - 1, 80)

    phase_year_points: Dict[str, Dict[int, Dict]] = {}
    for pid in cand_ids:
        b = copy.deepcopy(bazi)
        if pid != "day_master_dominant":
            try:
                b = apply_phase_override(b, pid)
            except Exception as e:
                print(f"[handshake] D3 apply_phase_override failed for {pid}: {e}", file=sys.stderr)
                continue
        try:
            curves_pid = score(b, age_start=0, age_end=age_end)
            phase_year_points[pid] = {pt["year"]: pt for pt in curves_pid["points"]}
        except Exception as e:
            print(f"[handshake] D3 score failed for {pid}: {e}", file=sys.stderr)

    if len(phase_year_points) < 2:
        return []

    common_years = set.intersection(*[set(d.keys()) for d in phase_year_points.values()])
    common_years = {y for y in common_years if (y - birth_year) >= min_age and y <= current_year - 1}

    candidates: List[Tuple[float, int, str, Dict[str, float]]] = []
    for year in common_years:
        for dim_key, curve_dims in _D3_CURVE_DIM.items():
            phase_vals = {
                pid: _avg_dim_value(phase_year_points[pid][year], curve_dims)
                for pid in phase_year_points
            }
            divergence = max(phase_vals.values()) - min(phase_vals.values())
            if divergence >= min_divergence:
                candidates.append((divergence, year, dim_key, phase_vals))

    candidates.sort(key=lambda x: (-x[0], x[1], x[2]))
    selected: List[Tuple[float, int, str, Dict[str, float]]] = []
    used_years = set()
    for d, year, dim_key, vals in candidates:
        if year in used_years:
            continue
        selected.append((d, year, dim_key, vals))
        used_years.add(year)
        if len(selected) >= n_questions:
            break

    out: List[Dict] = []
    for d, year, dim_key, vals in selected:
        age = year - birth_year
        phase_curve_values = {pid: round((v - 50.0) / 10.0, 4) for pid, v in vals.items()}
        try:
            q = D3_dynamic_event_question(age, year, dim_key, phase_curve_values)
        except AssertionError as e:
            print(f"[handshake] D3 fairness blacklist tripped for year {year}/{dim_key}: {e}", file=sys.stderr)
            continue
        out.append({
            "id": q.id,
            "dimension": q.dimension,
            "weight_class": q.weight_class,
            "prompt": q.prompt,
            "options": [{"id": o.id, "label": o.label} for o in q.options],
            "likelihood_table": {
                pid: dict(sorted(row.items())) for pid, row in sorted(q.likelihood_table.items())
            },
            "discrimination_power": round(d / 50.0, 6),
            "requires_dynamic_year": q.requires_dynamic_year,
            "evidence_note": q.evidence_note,
        })
    return out


# ============================================================================
# AskQuestion payload helpers
# ============================================================================

_NEUTRAL_INSTRUCTION = (
    "请按你最直觉的反应选；如不确定可挑最接近的一项。"
    "不要试图揣测题目背后想测什么。"
)


def _build_askquestion_payload(questions: List[Dict]) -> List[Dict]:
    """转成宿主 AskQuestion 工具能直接消费的格式。

    v9 · 强制只暴露 prompt + options，**不暴露**：
      - phase_candidates / prior_distribution / posterior
      - decision_threshold / provisional_decision
      - discrimination_power / pairwise_target / evidence_note
    （详见 elicitation_ethics §E1 / §E2）
    """
    out = []
    for q in questions:
        out.append({
            "id": q["id"],
            "prompt": q["prompt"],
            "options": [{"id": o["id"], "label": o["label"]} for o in q["options"]],
            "allow_multiple": False,
            "neutral_instruction": _NEUTRAL_INSTRUCTION,
        })
    return out


def _build_cli_fallback_prompt(questions: List[Dict]) -> str:
    """无 AskQuestion 宿主时的纯文本 fallback。"""
    lines = [
        "请按以下编号回答（输入 D1_Q3=B 形式，每行一个，最后空行结束）：",
        "",
    ]
    for q in questions:
        lines.append(f"{q['id']}")
        lines.append(f"  问：{q['prompt']}")
        for o in q["options"]:
            lines.append(f"    {o['id']}) {o['label']}")
        lines.append("")
    return "\n".join(lines)


# ============================================================================
# §A · build (R1) · v9 deprecated 兼容入口
# ============================================================================

_R1_DEPRECATION_MSG = (
    "[handshake.py R1] DEPRECATED · v9 hard cutover · "
    "请改用 `python scripts/adaptive_elicit.py next` 一题一轮自适应问答；"
    "本入口仅为 he_pan_orchestrator / mcp_server / 旧 examples 兜底，"
    "输出仍是一次性题集，但 askquestion_payload 已剥离所有后验字段。"
)


def build(
    bazi: Dict,
    curves: Optional[Dict] = None,
    current_year: Optional[int] = None,
    static_top_k: int = 22,
    d3_n_questions: int = 4,
    candidate_top_k: int = 5,
    enable_d3: bool = True,
) -> Dict:
    """[deprecated v9] 一次性题集生成。

    R1 默认路径已迁到 [adaptive_elicit.py](adaptive_elicit.py)。本函数保留兼容接口，
    但输出 schema 标记 `deprecated_v9: True`。

    输出对外 askquestion_payload **不再包含** 任何 phase / 后验信息（已剥离）。
    顶层仍保留 `phase_candidates` / `prior_distribution` 字段供 LLM 内部 reasoning，
    但 elicitation_ethics §E1 强制：**禁止把它们呈现给用户**。
    """
    if current_year is None:
        current_year = dt.date.today().year

    print(_R1_DEPRECATION_MSG, file=sys.stderr)

    detection = detect_all_phase_candidates(bazi)
    prior = _compute_prior_distribution(detection["all_detection_details"])

    sorted_phases = sorted(prior.items(), key=lambda x: (-x[1], x[0]))
    cand_top = sorted_phases[:candidate_top_k]
    candidate_phase_ids = [pid for pid, _ in cand_top]

    triggered_by_phase: Dict[str, str] = {}
    for det in detection["triggered_candidates"]:
        sp = det.get("suggested_phase")
        if sp and sp not in triggered_by_phase:
            triggered_by_phase[sp] = f"{det['phase_id']}({det.get('score','')})".strip()

    phase_candidates = []
    for pid, p in cand_top:
        phase_candidates.append({
            "phase_id": pid,
            "prior": round(p, 6),
            "detector_source": triggered_by_phase.get(pid, "baseline"),
        })

    static_questions = compute_question_likelihoods(bazi, top_k=static_top_k)

    dynamic_questions: List[Dict] = []
    if enable_d3 and curves is not None:
        dynamic_questions = _generate_d3_dynamic_questions(
            bazi=bazi,
            candidate_phase_ids=candidate_phase_ids,
            current_year=current_year,
            n_questions=d3_n_questions,
        )

    DIM_ORDER = {
        "ethnography_family": 0,
        "relationship": 1,
        "yearly_event": 2,
        "tcm_body": 3,
        "self_perception": 4,
    }
    all_questions = static_questions + dynamic_questions
    all_questions.sort(key=lambda q: (DIM_ORDER.get(q["dimension"], 99), -q["discrimination_power"], q["id"]))

    askquestion_payload = _build_askquestion_payload(all_questions)
    cli_fallback_prompt = _build_cli_fallback_prompt(all_questions)

    provisional_decision = decide_phase(bazi, user_answers=None)

    return {
        "version": 9,
        "deprecated_v9": True,
        "deprecation_notice": _R1_DEPRECATION_MSG,
        "round": 1,
        "current_year": current_year,
        "bazi_summary": {
            "pillars": [f"{p['gan']}{p['zhi']}" for p in bazi.get("pillars", [])],
            "day_master": bazi.get("day_master"),
            "day_master_wuxing": bazi.get("day_master_wuxing"),
            "gender": bazi.get("gender"),
            "orientation": bazi.get("orientation"),
            "birth_year": bazi.get("birth_year"),
            "qiyun_age": bazi.get("qiyun_age"),
        },
        "phase_candidates": phase_candidates,
        "prior_distribution": {k: round(v, 6) for k, v in sorted(prior.items())},
        "provisional_decision": {
            "decision": provisional_decision["decision"],
            "confidence": provisional_decision["confidence"],
            "decision_probability": provisional_decision["decision_probability"],
            "is_provisional": True,
        },
        "questions": all_questions,
        "askquestion_payload": askquestion_payload,
        "cli_fallback_prompt": cli_fallback_prompt,
        "decision_threshold": {
            "auto_adopt": 0.80,
            "adopt": 0.60,
            "ask_more": 0.40,
        },
        "_meta": {
            "n_static_questions": len(static_questions),
            "n_dynamic_questions": len(dynamic_questions),
            "n_total_questions": len(all_questions),
            "fairness_blacklist_applied": True,
            "blacklist_terms": sorted(FAIRNESS_BLACKLIST),
        },
        "agent_instructions": (
            "[v9 deprecated] 兼容入口。新代码请用 adaptive_elicit.py 走自适应问答。"
            "若必须沿用本入口：用宿主 AskQuestion 一次抛 askquestion_payload 全部题，"
            "禁止把 phase_candidates / prior_distribution / decision_threshold 等"
            "字段展示或转述给用户（违反 elicitation_ethics.md §E1 / §E2）。"
        ),
    }


# ============================================================================
# §B · build_round2 · 主用途 · EIG 选题（限定在 R1 决策 vs runner-up）
# ============================================================================

def _eig_two_phase(
    q,
    decided_phase: str,
    runner_up_phase: str,
    decided_prob: float,
    runner_up_prob: float,
) -> float:
    """在 2-phase 后验 [decided, runner_up] 上算 weighted_eig，用于 R2 选题排序。

    比 v8 pairwise_discrimination_power（纯 L1 距离）更接近"信息论意义上"的判别力，
    且与单题流式 adaptive_elicit 用同一个排序函数（同源逻辑保 bit-for-bit）。
    """
    s = decided_prob + runner_up_prob
    if s <= 0:
        post = {decided_phase: 0.5, runner_up_phase: 0.5}
    else:
        post = {decided_phase: decided_prob / s, runner_up_phase: runner_up_prob / s}
    return weighted_eig(q, post)


def _compute_confirmation_questions_eig(
    bazi_dict: Dict,
    decided_phase: str,
    runner_up_phase: str,
    decided_prob: float,
    runner_up_prob: float,
    exclude_ids: Optional[List[str]] = None,
    top_k: int = 6,
    eig_threshold: float = 0.02,
) -> List[Dict]:
    """v9 R2 · 用 weighted_eig（2-phase 后验）挑 confirmation 题。

    behavior：
      - EIG 用对称的 2-phase 后验（{decided:0.5, runner_up:0.5}）算，
        防止 R1 已极度确定（如 0.99）时所有题 EIG≈0 → 选不出题
      - 用真实 R1 后验排 tie-break，但不参与门槛判定
      - 若全部题低于 eig_threshold，则放弃门槛、强制返回 top_k
    """
    excluded = set(exclude_ids or [])
    scored: List[Tuple[float, float, "object"]] = []
    for q in get_static_questions():
        if q.id in excluded:
            continue
        eig_symmetric = _eig_two_phase(q, decided_phase, runner_up_phase, 0.5, 0.5)
        eig_real = _eig_two_phase(
            q, decided_phase, runner_up_phase,
            max(decided_prob, 1e-6), max(runner_up_prob, 1e-6),
        )
        scored.append((eig_symmetric, eig_real, q))

    scored.sort(key=lambda x: (-x[0], -x[1], x[2].id))
    above = [t for t in scored if t[0] >= eig_threshold]
    selected = above[:top_k] if above else scored[:top_k]
    selected = [(s, q) for s, _, q in selected]

    out: List[Dict] = []
    for eig, q in selected:
        out.append({
            "id": q.id,
            "dimension": q.dimension,
            "weight_class": q.weight_class,
            "prompt": q.prompt,
            "options": [{"id": o.id, "label": o.label} for o in q.options],
            "likelihood_table": {
                pid: dict(sorted(row.items())) for pid, row in sorted(q.likelihood_table.items())
            },
            "weighted_eig": round(eig, 6),
            "discrimination_power": round(eig, 6),  # 兼容字段
            "pairwise_target": {"a": decided_phase, "b": runner_up_phase},
            "requires_dynamic_year": q.requires_dynamic_year,
            "evidence_note": q.evidence_note,
        })
    return out


def build_round2(
    bazi: Dict,
    r1_handshake: Optional[Dict] = None,
    r1_user_answers: Optional[Dict[str, str]] = None,
    curves: Optional[Dict] = None,
    current_year: Optional[int] = None,
    confirm_top_k: int = 6,
    d3_n_questions: int = 2,
    enable_d3: bool = True,
) -> Dict:
    """v9 · Round 2 confirmation 题集（**主 entrypoint**）。

    前置条件：bazi.json 中已经存在 phase_decision（来自 R1 phase_posterior /
    adaptive_elicit 的输出）。

    R2 选题策略（v9 升级）：
      - 在 R1 决策 phase 与 runner-up 之间用 weighted_eig 挑高判别力题
      - 排除 R1 已经问过的题
      - 可附加少量 D3 动态流年题（仅 decided vs runner-up 间预测分歧大的年份）

    详见 references/handshake_protocol.md §4 v9。
    """
    if current_year is None:
        current_year = dt.date.today().year

    pd = bazi.get("phase_decision")
    if not pd:
        raise ValueError(
            "build_round2 requires bazi.phase_decision "
            "(run adaptive_elicit.py 或 phase_posterior.py round=1 first)."
        )
    posterior = pd.get("posterior_distribution") or pd.get("prior_distribution") or {}
    if not posterior:
        raise ValueError("bazi.phase_decision missing posterior_distribution / prior_distribution")

    sorted_phases = sorted(posterior.items(), key=lambda x: (-x[1], x[0]))
    decided_phase = pd.get("decision") or sorted_phases[0][0]
    decided_prob = float(pd.get("decision_probability") or sorted_phases[0][1])

    runner_up_phase = None
    runner_up_prob = 0.0
    for pid, p in sorted_phases:
        if pid != decided_phase:
            runner_up_phase = pid
            runner_up_prob = float(p)
            break
    if runner_up_phase is None:
        runner_up_phase = (
            "day_master_dominant"
            if decided_phase != "day_master_dominant"
            else "floating_dms_to_cong_cai"
        )

    asked_ids: set = set()
    if r1_user_answers:
        asked_ids.update(r1_user_answers.keys())

    # v9 · EIG 选题（替代 v8 的 pairwise L1）
    static_questions = _compute_confirmation_questions_eig(
        bazi_dict=bazi,
        decided_phase=decided_phase,
        runner_up_phase=runner_up_phase,
        decided_prob=decided_prob,
        runner_up_prob=runner_up_prob,
        exclude_ids=sorted(asked_ids),
        top_k=confirm_top_k,
    )

    dynamic_questions: List[Dict] = []
    if enable_d3 and curves is not None:
        d3_pool = _generate_d3_dynamic_questions(
            bazi=bazi,
            candidate_phase_ids=[decided_phase, runner_up_phase],
            current_year=current_year,
            n_questions=d3_n_questions * 2,
            min_divergence=3.0,
        )
        scored: List[Tuple[float, Dict]] = []
        for q in d3_pool:
            if q.get("id") in asked_ids:
                continue
            row_a = q.get("likelihood_table", {}).get(decided_phase, {})
            row_b = q.get("likelihood_table", {}).get(runner_up_phase, {})
            if not row_a or not row_b:
                continue
            opt_ids = [o["id"] for o in q["options"]]
            pdp = sum(abs(row_a.get(oid, 0.0) - row_b.get(oid, 0.0)) for oid in opt_ids)
            if pdp < 0.30:
                continue
            q2 = dict(q)
            q2["discrimination_power"] = round(pdp, 6)
            q2["pairwise_target"] = {"a": decided_phase, "b": runner_up_phase}
            scored.append((pdp, q2))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        dynamic_questions = [q for _, q in scored[:d3_n_questions]]

    DIM_ORDER = {
        "ethnography_family": 0,
        "relationship": 1,
        "yearly_event": 2,
        "tcm_body": 3,
        "self_perception": 4,
    }
    all_questions = static_questions + dynamic_questions
    all_questions.sort(key=lambda q: (DIM_ORDER.get(q["dimension"], 99), -q["discrimination_power"], q["id"]))

    askquestion_payload = _build_askquestion_payload(all_questions)
    cli_fallback_prompt = _build_cli_fallback_prompt(all_questions)

    return {
        "version": 9,
        "round": 2,
        "current_year": current_year,
        "bazi_summary": {
            "pillars": [f"{p['gan']}{p['zhi']}" for p in bazi.get("pillars", [])],
            "day_master": bazi.get("day_master"),
            "day_master_wuxing": bazi.get("day_master_wuxing"),
            "gender": bazi.get("gender"),
            "birth_year": bazi.get("birth_year"),
        },
        "round1_summary": {
            "decision": decided_phase,
            "decision_probability": round(decided_prob, 6),
            "runner_up": runner_up_phase,
            "runner_up_probability": round(runner_up_prob, 6),
            "answered_question_ids": sorted(asked_ids),
        },
        "pairwise_target": {"a": decided_phase, "b": runner_up_phase},
        "questions": all_questions,
        "askquestion_payload": askquestion_payload,
        "cli_fallback_prompt": cli_fallback_prompt,
        "confirmation_threshold": {
            "confirmed": 0.85,
            "weakly_confirmed": 0.65,
        },
        "_meta": {
            "n_static_questions": len(static_questions),
            "n_dynamic_questions": len(dynamic_questions),
            "n_total_questions": len(all_questions),
            "n_excluded_from_r1": len(asked_ids),
            "fairness_blacklist_applied": True,
            "selection_method": "weighted_eig_two_phase",
        },
        "agent_instructions": (
            "v9 R2 协议：用宿主结构化 AskQuestion 抛 askquestion_payload 全部 N 题给用户。"
            "askquestion_payload 已剥离所有后验信息；禁止把 round1_summary / pairwise_target "
            "等顶层字段呈现给用户（elicitation_ethics §E1）。收到 R2 user_answers 后调 "
            "phase_posterior.py --round 2 算最终后验 + confirmation_status。"
            "详见 references/handshake_protocol.md §4 v9。"
        ),
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    ap = argparse.ArgumentParser(
        description="v9 · phase confirmation handshake (R2 主 · R1 deprecated)"
    )
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--curves", required=False, default=None,
                    help="curves.json 路径（D3 动态流年题需要）")
    ap.add_argument("--current-year", type=int, default=None,
                    help="当前公历年（默认 today.year）")
    ap.add_argument("--out", default="handshake.json", help="输出路径")
    ap.add_argument("--static-top-k", type=int, default=22,
                    help="(R1 deprecated) 静态题最多保留 N 道")
    ap.add_argument("--d3-questions", type=int, default=4,
                    help="D3 动态流年题数量")
    ap.add_argument("--no-d3", action="store_true", help="跳过 D3 动态流年题")
    ap.add_argument("--round", type=int, default=1, choices=[1, 2],
                    help="校验轮次：1=v9 deprecated 兼容入口；2=R2 confirmation（主用途）")
    ap.add_argument("--r1-handshake", default=None,
                    help="（round=2 可选）R1 阶段的 handshake.json")
    ap.add_argument("--r1-answers", default=None,
                    help="（round=2 推荐）R1 用户答案 JSON {qid:opt}")
    ap.add_argument("--confirm-top-k", type=int, default=6,
                    help="（round=2）confirmation 静态题数量上限（默认 6）")
    ap.add_argument("--strict-v9", action="store_true",
                    help="[v9 已默认开] round=1 时硬错出（强制走 adaptive_elicit）。保留兼容老脚本。")
    ap.add_argument("--ack-legacy-r1", action="store_true",
                    help="v9 · 显式承认要走 R1 deprecated 一次性题集路径。"
                         "未传此 flag 时 round=1 默认 exit 2（v9 硬切换）。"
                         "仅 he_pan_orchestrator / mcp_server 兜底 / 旧 examples 才允许使用。")
    args = ap.parse_args()

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    curves = None
    if args.curves and Path(args.curves).exists():
        curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))

    if args.round == 2:
        r1_handshake = None
        if args.r1_handshake and Path(args.r1_handshake).exists():
            r1_handshake = json.loads(Path(args.r1_handshake).read_text(encoding="utf-8"))
        r1_answers = None
        if args.r1_answers and Path(args.r1_answers).exists():
            r1_answers = json.loads(Path(args.r1_answers).read_text(encoding="utf-8"))

        out = build_round2(
            bazi=bazi,
            r1_handshake=r1_handshake,
            r1_user_answers=r1_answers,
            curves=curves,
            current_year=args.current_year,
            confirm_top_k=args.confirm_top_k,
            d3_n_questions=max(2, args.d3_questions // 2),
            enable_d3=not args.no_d3,
        )

        Path(args.out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        meta = out["_meta"]
        r1s = out["round1_summary"]
        print(
            f"[handshake R2] wrote {args.out}: "
            f"target={r1s['decision']}(p={r1s['decision_probability']:.3f}) vs "
            f"runner_up={r1s['runner_up']}(p={r1s['runner_up_probability']:.3f}); "
            f"static={meta['n_static_questions']}, dynamic={meta['n_dynamic_questions']}, "
            f"excluded_r1={meta['n_excluded_from_r1']}, "
            f"selection={meta['selection_method']}"
        )
        return

    # round = 1（deprecated 兼容入口）
    # v9 硬切换：默认 exit 2；显式 --ack-legacy-r1 才放行；--strict-v9 兼容老 CI
    from _v9_guard import enforce_v9_only_path
    enforce_v9_only_path(
        "handshake.py R1",
        ack_flag=(args.ack_legacy_r1 and not args.strict_v9),
        ack_flag_help="--ack-legacy-r1",
        extra_hint=(
            "推荐改用：\n"
            f"  python scripts/adaptive_elicit.py next --bazi {args.bazi} "
            f"--curves {args.curves or '<curves.json>'} "
            "--state output/.elicit.state.json"
        ),
    )

    out = build(
        bazi=bazi,
        curves=curves,
        current_year=args.current_year,
        static_top_k=args.static_top_k,
        d3_n_questions=args.d3_questions,
        enable_d3=not args.no_d3,
    )

    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    meta = out["_meta"]
    decision = out["provisional_decision"]
    print(
        f"[handshake R1 · deprecated_v9] wrote {args.out}: "
        f"phase_candidates={len(out['phase_candidates'])}, "
        f"static={meta['n_static_questions']}, dynamic={meta['n_dynamic_questions']}, "
        f"total={meta['n_total_questions']}; "
        f"provisional={decision['decision']}({decision['confidence']}, "
        f"prob={decision['decision_probability']:.3f}) "
        f"--- 新代码请改用 adaptive_elicit.py"
    )


if __name__ == "__main__":
    main()
