#!/usr/bin/env python3
"""scripts/handshake.py · v8

输出 phase-discriminative validation 题集（5 维度 ~25 题），供 Agent 用宿主结构化
AskQuestion 抛点选 UI。不再做事后判定 / 命中率统计 —— 那是 phase_posterior.py 的事。

输入：
  --bazi out/bazi.json       solve_bazi.py 的输出
  --curves out/curves.json   score_curves.py 的输出（用于 D3 流年题选年份）
  --current-year YYYY        当前年份（默认 today.year）
  --out out/handshake.json   输出路径

输出 schema 详见 references/handshake_protocol.md §2。

Hard cutover 自 v7：旧 R0/R1/R2/R3 + evaluate_responses + 命中率体系全部移除。
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
    compute_confirmation_questions,
    decide_phase,
)
from _question_bank import D3_dynamic_event_question, FAIRNESS_BLACKLIST  # type: ignore


# ============================================================================
# D3 动态流年题生成
# ============================================================================

# D3 dim → 用户语义维度
_D3_CURVE_DIM = {
    "career":   ("spirit", "fame"),  # 事业方向同时看 spirit 和 fame，取均值
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

    严守 fairness §10：选项不出现"升职/结婚/离职/生育/确诊"等身份标签词
    （由 _question_bank.D3_dynamic_event_question 内部 _check_blacklist 拦截）。
    """
    if len(candidate_phase_ids) < 2:
        return []

    birth_year = int(bazi.get("birth_year") or 0)
    if not birth_year:
        return []
    age_now = current_year - birth_year
    if age_now < min_age + 2:
        return []  # 太年轻没有足够回忆

    # 局部 import 避免循环依赖
    try:
        from score_curves import score, apply_phase_override  # type: ignore
    except Exception as e:  # pragma: no cover - 防御
        print(f"[handshake] D3 skipped (score_curves import failed): {e}", file=sys.stderr)
        return []

    # 取前 3 个候选（控制 compute）
    cand_ids = list(candidate_phase_ids[:3])
    age_end = min(age_now - 1, 80)

    # 每个 phase 算曲线 → {year: point dict}
    # 注意：apply_phase_override / score 会就地改 nested dict（strength / yongshen），
    # 必须 deepcopy；否则会污染 caller 的 bazi
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

    # 找各 phase 共同覆盖的年份
    common_years = set.intersection(*[set(d.keys()) for d in phase_year_points.values()])
    common_years = {y for y in common_years if (y - birth_year) >= min_age and y <= current_year - 1}

    # 对每个 (year, dim) 算 phase 间预测分歧
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

    # 选 top-n，且每年只生成一题
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
        # phase_curve_values 归一到 [-5, +5]：以 50 为基线，每 10 分一档
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
            "discrimination_power": round(d / 50.0, 6),  # 把曲线分歧归一到 [0,1]
            "requires_dynamic_year": q.requires_dynamic_year,
            "evidence_note": q.evidence_note,
        })
    return out


# ============================================================================
# AskQuestion payload + CLI fallback prompt
# ============================================================================

def _build_askquestion_payload(questions: List[Dict]) -> List[Dict]:
    """转成宿主 AskQuestion 工具能直接消费的格式（每题 id + prompt + options + allow_multiple）。"""
    out = []
    for q in questions:
        out.append({
            "id": q["id"],
            "prompt": q["prompt"],
            "options": [{"id": o["id"], "label": o["label"]} for o in q["options"]],
            "allow_multiple": False,
        })
    return out


def _build_cli_fallback_prompt(questions: List[Dict]) -> str:
    """无 AskQuestion 宿主时的纯文本 fallback。"""
    lines = [
        "请按以下编号回答（输入 D1_Q3=B 形式，每行一个，最后空行结束）：",
        "",
    ]
    for q in questions:
        lines.append(f"{q['id']}  [{q['dimension']} · {q['weight_class']}]")
        lines.append(f"  问：{q['prompt']}")
        for o in q["options"]:
            lines.append(f"    {o['id']}) {o['label']}")
        lines.append("")
    return "\n".join(lines)


# ============================================================================
# 顶层 build
# ============================================================================

def build(
    bazi: Dict,
    curves: Optional[Dict] = None,
    current_year: Optional[int] = None,
    static_top_k: int = 22,
    d3_n_questions: int = 4,
    candidate_top_k: int = 5,
    enable_d3: bool = True,
) -> Dict:
    """v8 · 生成 phase-discriminative 题集 + 候选 phase 先验 + AskQuestion payload。

    Args:
        bazi: bazi.json 内容
        curves: curves.json 内容（D3 流年题需要；不提供则跳过 D3）
        current_year: 当前公历年；None → today.year
        static_top_k: 静态题最多保留 N 道（按 discrimination_power 倒排）
        d3_n_questions: D3 动态流年题数量
        candidate_top_k: phase_candidates 列表长度
        enable_d3: 是否启用 D3 动态流年题
    """
    if current_year is None:
        current_year = dt.date.today().year

    # 1. detector → prior
    detection = detect_all_phase_candidates(bazi)
    prior = _compute_prior_distribution(detection["all_detection_details"])

    sorted_phases = sorted(prior.items(), key=lambda x: (-x[1], x[0]))
    cand_top = sorted_phases[:candidate_top_k]
    candidate_phase_ids = [pid for pid, _ in cand_top]

    # phase_candidates 输出（含 detector 来源）
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

    # 2. 静态题（D1+D2+D4+D5）按 discrimination_power 取 top
    static_questions = compute_question_likelihoods(bazi, top_k=static_top_k)

    # 3. D3 动态流年题
    dynamic_questions: List[Dict] = []
    if enable_d3 and curves is not None:
        dynamic_questions = _generate_d3_dynamic_questions(
            bazi=bazi,
            candidate_phase_ids=candidate_phase_ids,
            current_year=current_year,
            n_questions=d3_n_questions,
        )

    # 4. 合并 + 按维度排序（D1 → D2 → D3 → D4 → D5），同维度内按 dp 倒排
    DIM_ORDER = {
        "ethnography_family": 0,
        "relationship": 1,
        "yearly_event": 2,
        "tcm_body": 3,
        "self_perception": 4,
    }
    all_questions = static_questions + dynamic_questions
    all_questions.sort(key=lambda q: (DIM_ORDER.get(q["dimension"], 99), -q["discrimination_power"], q["id"]))

    # 5. AskQuestion payload + CLI prompt
    askquestion_payload = _build_askquestion_payload(all_questions)
    cli_fallback_prompt = _build_cli_fallback_prompt(all_questions)

    # 6. 当前默认 phase（仅先验）= 后验 with no answers
    provisional_decision = decide_phase(bazi, user_answers=None)

    return {
        "version": 8,
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
            "v8 协议：必须用宿主结构化 AskQuestion 一次抛 askquestion_payload 全部 N 题，"
            "禁止用自然语言转述题面让用户口头回答。收到 user_answers 后调 phase_posterior.py "
            "算后验：≥0.80 high adopt / 0.60-0.80 mid adopt / 0.40-0.60 追问轮 / <0.40 拒绝出图。"
            "详见 references/handshake_protocol.md §3。"
        ),
    }


# ============================================================================
# Round 2 confirmation handshake
# ============================================================================

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
    """v8 · 生成 Round 2 confirmation 题集。

    前置条件：bazi.json 中已经存在 phase_decision（来自 R1 phase_posterior 的输出）。

    R2 选题策略：
      - 在 R1 后验的 top phase 与 runner-up phase 之间，按 pairwise L1 区分度倒排取 top_k
      - 排除 R1 已经问过的题（依据 r1_user_answers 的 key 或 r1_handshake.questions[].id）
      - 可附加少量 D3 动态流年题，只在 decided vs runner-up 之间预测分歧大的年份生成

    详见 references/handshake_protocol.md §4。
    """
    if current_year is None:
        current_year = dt.date.today().year

    # 1. 读取 R1 后验（必须）—— 没有 R1 phase_decision 直接报错
    pd = bazi.get("phase_decision")
    if not pd:
        raise ValueError(
            "build_round2 requires bazi.phase_decision (run phase_posterior.py round=1 first)."
        )
    posterior = pd.get("posterior_distribution") or pd.get("prior_distribution") or {}
    if not posterior:
        raise ValueError("bazi.phase_decision missing posterior_distribution / prior_distribution")

    sorted_phases = sorted(posterior.items(), key=lambda x: (-x[1], x[0]))
    decided_phase = pd.get("decision") or sorted_phases[0][0]
    decided_prob = float(pd.get("decision_probability") or sorted_phases[0][1])

    # runner-up：决策之外 prob 最大的那个
    runner_up_phase = None
    runner_up_prob = 0.0
    for pid, p in sorted_phases:
        if pid != decided_phase:
            runner_up_phase = pid
            runner_up_prob = float(p)
            break
    if runner_up_phase is None:
        runner_up_phase = "day_master_dominant" if decided_phase != "day_master_dominant" else "floating_dms_to_cong_cai"

    # 2. 收集 R1 已被用户**实际作答**的 question_id（仅这些需要排除；
    #    handshake.questions 只是 R1 候选池，未必全部被问过）
    asked_ids: set = set()
    if r1_user_answers:
        asked_ids.update(r1_user_answers.keys())

    # 3. 静态题：pairwise discriminative
    static_questions = compute_confirmation_questions(
        bazi_dict=bazi,
        decided_phase=decided_phase,
        runner_up_phase=runner_up_phase,
        exclude_ids=sorted(asked_ids),
        top_k=confirm_top_k,
    )

    # 4. D3 动态题：仅在 decided vs runner_up 两个 phase 之间挑分歧最大的年份
    dynamic_questions: List[Dict] = []
    if enable_d3 and curves is not None:
        d3_pool = _generate_d3_dynamic_questions(
            bazi=bazi,
            candidate_phase_ids=[decided_phase, runner_up_phase],
            current_year=current_year,
            n_questions=d3_n_questions * 2,  # 多生成一些再过滤
            min_divergence=3.0,
        )
        # 过滤：剔除 R1 已问过的、按 pairwise dp 倒排
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
        "version": 8,
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
        "pairwise_target": {
            "a": decided_phase,
            "b": runner_up_phase,
        },
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
        },
        "agent_instructions": (
            "v8 R2 协议：用宿主结构化 AskQuestion 抛 askquestion_payload 全部 N 题给用户点选。"
            "收到 R2 user_answers 后，调 phase_posterior.py --round 2 合并 R1+R2 答案算最终后验，"
            "对照 confirmation_threshold 判 confirmed / weakly_confirmed / inconsistent。"
            "详见 references/handshake_protocol.md §4。"
        ),
    }


# ============================================================================
# CLI
# ============================================================================

def main():
    ap = argparse.ArgumentParser(
        description="v8 · 生成 phase-discriminative 题集 (handshake.json)"
    )
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--curves", required=False, default=None,
                    help="curves.json 路径（D3 动态流年题需要；不提供则只出静态题）")
    ap.add_argument("--current-year", type=int, default=None,
                    help="当前公历年（默认 today.year）")
    ap.add_argument("--out", default="handshake.json", help="输出路径")
    ap.add_argument("--static-top-k", type=int, default=22,
                    help="静态题最多保留 N 道（按 discrimination_power 倒排）")
    ap.add_argument("--d3-questions", type=int, default=4,
                    help="D3 动态流年题数量（默认 4）")
    ap.add_argument("--no-d3", action="store_true",
                    help="跳过 D3 动态流年题（用于测试 / 加速）")
    ap.add_argument("--round", type=int, default=1, choices=[1, 2],
                    help="校验轮次：1=初轮判别题；2=基于 R1 决策的 confirmation 题")
    ap.add_argument("--r1-handshake", default=None,
                    help="（round=2 必填）R1 阶段的 handshake.json，用于排除已问过的题")
    ap.add_argument("--r1-answers", default=None,
                    help="（round=2 推荐）R1 用户答案 JSON {qid:opt}")
    ap.add_argument("--confirm-top-k", type=int, default=6,
                    help="（round=2）confirmation 静态题数量上限（默认 6）")
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
            f"excluded_r1={meta['n_excluded_from_r1']}"
        )
        return

    # round = 1（默认）
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
        f"[handshake] wrote {args.out}: "
        f"phase_candidates={len(out['phase_candidates'])}, "
        f"static={meta['n_static_questions']}, dynamic={meta['n_dynamic_questions']}, "
        f"total={meta['n_total_questions']}; "
        f"provisional={decision['decision']}({decision['confidence']}, "
        f"prob={decision['decision_probability']:.3f})"
    )


if __name__ == "__main__":
    main()
