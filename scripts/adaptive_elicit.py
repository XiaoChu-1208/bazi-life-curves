#!/usr/bin/env python3
"""scripts/adaptive_elicit.py · v9 · 自适应贝叶斯问答主入口

代替 v8 的"一次性抛 26 题"路径。三种 CLI 子命令：

  next               一题一轮：吃上一题答案 → 更新后验 → 决定停 / 选下一题
  dump-question-set  一次性导出题集（core14 / full28）供用户 batch 贴答
  submit-batch       一次性接收所有答案 → 直接 finalize

E1 / E2 工程约束：
- posterior / EIG / phase_candidates 仅写到 state 文件（点开头隐藏）
- stdout 输出的 askquestion_payload 仅含 prompt + options + 中性 instruction
- 不输出 "你目前最像 X 格" 类提示
- batch 模式下题集打乱 dimension 顺序 + 顶部 caveat + confidence 上限锁 mid

Usage:
    # 单题流式（默认路径）
    python scripts/adaptive_elicit.py next \\
        --bazi out/bazi.json --curves out/curves.json \\
        --state out/.elicit.state.json \\
        [--answer "D4_Q2:B"]

    # 导出 batch 题集
    python scripts/adaptive_elicit.py dump-question-set \\
        --bazi out/bazi.json --curves out/curves.json \\
        --tier core14|full28 \\
        --out out/question_set.md

    # 一次性提交答案
    python scripts/adaptive_elicit.py submit-batch \\
        --bazi out/bazi.json --curves out/curves.json \\
        --answers out/batch_answers.json \\
        --out out/bazi.json

详见 plan 自适应贝叶斯问答 v9 §A2 + §A3 + §A6'。
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bazi_core import (  # type: ignore
    detect_all_phase_candidates,
    _compute_prior_distribution,
    _phase_five_tuple,
)
from _eig_selector import (  # type: ignore
    DEFAULT_STOP_CONFIG,
    bayes_update,
    compute_eig_pool,
    pick_top_question,
    should_stop,
    weighted_eig,
)
from _question_bank import (  # type: ignore
    D1_QUESTIONS, D2_QUESTIONS, D4_QUESTIONS, D5_QUESTIONS, D6_QUESTIONS,
    D3_dynamic_event_question,
    Question,
)


# ---------------------------------------------------------------------------
# §1 候选池构造（静态 + D3 动态）
# ---------------------------------------------------------------------------

# 用于 D3 流年题的曲线维度映射（与 handshake.py 一致）
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


def _generate_d3_pool(
    bazi: Dict,
    curves: Optional[Dict],
    candidate_phase_ids: List[str],
    current_year: int,
    n_questions: int,
    min_age: int = 6,
    min_divergence: float = 3.0,
) -> List[Question]:
    """为候选 phase 生成 D3 动态流年题 Question 对象（与 handshake.py 同算法）。"""
    if not curves or len(candidate_phase_ids) < 2:
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
        print(f"[adaptive_elicit] D3 skipped (score_curves import failed): {e}",
              file=sys.stderr)
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
                print(f"[adaptive_elicit] D3 apply_phase_override fail {pid}: {e}",
                      file=sys.stderr)
                continue
        try:
            curves_pid = score(b, age_start=0, age_end=age_end)
            phase_year_points[pid] = {pt["year"]: pt for pt in curves_pid["points"]}
        except Exception as e:
            print(f"[adaptive_elicit] D3 score fail {pid}: {e}", file=sys.stderr)

    if len(phase_year_points) < 2:
        return []

    common_years = set.intersection(*[set(d.keys()) for d in phase_year_points.values()])
    common_years = {
        y for y in common_years
        if (y - birth_year) >= min_age and y <= current_year - 1
    }

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

    out: List[Question] = []
    for _, year, dim_key, vals in selected:
        age = year - birth_year
        phase_curve_values = {
            pid: round((v - 50.0) / 10.0, 4) for pid, v in vals.items()
        }
        try:
            q = D3_dynamic_event_question(age, year, dim_key, phase_curve_values)
            out.append(q)
        except AssertionError as e:
            print(f"[adaptive_elicit] D3 fairness blacklist tripped {year}/{dim_key}: {e}",
                  file=sys.stderr)
    return out


def _build_candidate_pool(
    bazi: Dict,
    curves: Optional[Dict],
    current_year: int,
    candidate_phase_ids: List[str],
    d3_n_questions: int = 4,
) -> List[Question]:
    """完整候选池：D1 + D2 + D4 + D5 + D6 静态 + D3 动态。
    顺序在选题时由 EIG 决定，与此处顺序无关，但影响 tie-break 后的 id 字典序。
    """
    static = list(D1_QUESTIONS) + list(D2_QUESTIONS) + list(D4_QUESTIONS) \
        + list(D5_QUESTIONS) + list(D6_QUESTIONS)
    dynamic = _generate_d3_pool(
        bazi=bazi,
        curves=curves,
        candidate_phase_ids=candidate_phase_ids,
        current_year=current_year,
        n_questions=d3_n_questions,
    )
    return static + dynamic


# ---------------------------------------------------------------------------
# §2 state 文件 I/O
# ---------------------------------------------------------------------------

def _bazi_fingerprint(bazi: Dict) -> str:
    """对 bazi 关键字段做 hash，用于检测 state 是否对应同一命局。"""
    keys = (
        "pillars_str",
        "gender",
        "orientation",
        "birth_year",
    )
    parts = [str(bazi.get(k, "")) for k in keys]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _load_state(path: Path) -> Optional[Dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_state(path: Path, state: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_state(bazi: Dict, prior: Dict[str, float], current_year: int) -> Dict:
    return {
        "version": 9,
        "bazi_fingerprint": _bazi_fingerprint(bazi),
        "current_year": current_year,
        "answered": {},
        "posterior": {k: float(v) for k, v in prior.items()},
        "asked_history": [],
        "top1_history": [max(prior.values())] if prior else [],
        "agent_warning": (
            "本文件包含 posterior / phase_candidates 等先验信息。"
            "禁止把本文件内容回灌给 LLM 或展示给用户（违反 elicitation_ethics.md E1/E2）。"
        ),
    }


# ---------------------------------------------------------------------------
# §3 单题流式：next 子命令
# ---------------------------------------------------------------------------

def _question_to_payload(q: Question) -> Dict:
    """转成宿主 AskQuestion 工具的单题 payload（中性，无后验信息）。"""
    return {
        "id": q.id,
        "prompt": q.prompt,
        "options": [{"id": o.id, "label": o.label} for o in q.options],
        "allow_multiple": False,
        "neutral_instruction": (
            "请按你最直觉的反应选；如不确定可挑最接近的一项。"
            "不要试图揣测题目背后想测什么。"
        ),
    }


def _question_to_cli_prompt(q: Question) -> str:
    lines = [
        f"[{q.id}] {q.prompt}",
        "",
    ]
    for o in q.options:
        lines.append(f"  {o.id}) {o.label}")
    lines.append("")
    lines.append(f"请回复 {q.id}=<选项 id>")
    return "\n".join(lines)


def _finalize_phase(bazi: Dict, posterior: Dict[str, float],
                    answered: Dict[str, str], stop_reason: str,
                    confidence_cap: Optional[str] = None) -> Dict:
    """根据最终 posterior 写出 bazi.phase / phase_decision 字段。

    confidence_cap: 若给定（e.g. "mid"），则 confidence 不允许超过该档位（batch 模式用）。
    """
    sorted_phases = sorted(posterior.items(), key=lambda x: (-x[1], x[0]))
    top_phase = sorted_phases[0][0]
    top_prob = sorted_phases[0][1]

    # confidence
    if top_prob >= 0.80:
        conf = "high"
    elif top_prob >= 0.60:
        conf = "mid"
    elif top_prob >= 0.40:
        conf = "low"
    else:
        conf = "reject"

    # batch 模式 confidence cap
    if confidence_cap:
        order = ["reject", "low", "mid", "high"]
        cap_idx = order.index(confidence_cap)
        if order.index(conf) > cap_idx:
            conf = confidence_cap

    five = _phase_five_tuple(top_phase, bazi)

    pd = {
        "version": 9,
        "decision": top_phase,
        "decision_probability": round(top_prob, 6),
        "phase_label": five["phase_label"],
        "confidence": conf,
        "is_provisional": False,
        "posterior_distribution": {k: round(v, 6) for k, v in sorted(posterior.items())},
        "answered_questions": sorted(answered.keys()),
        "n_answered": len(answered),
        "elicitation_path": "adaptive_v9",
        "stop_reason": stop_reason,
        "strength_after_phase": five["strength"],
        "yongshen_after_phase": five["yongshen"],
        "xishen_after_phase": five["xishen"],
        "jishen_after_phase": five["jishen"],
        "climate_after_phase": five["climate"],
    }
    if confidence_cap:
        pd["confidence_cap_applied"] = confidence_cap

    new_bazi = dict(bazi)
    new_bazi["phase"] = {
        "id": top_phase,
        "label": five["phase_label"],
        "is_provisional": False,
        "is_inverted": top_phase != "day_master_dominant",
        "default_phase_was": "day_master_dominant",
        "confidence": conf,
        "decision_probability": round(top_prob, 6),
    }
    new_bazi["phase_decision"] = pd
    return new_bazi


def _print_done(out_path: Path, pd: Dict) -> None:
    print(json.dumps({
        "status": "DONE",
        "decision": pd["decision"],
        "phase_label": pd["phase_label"],
        "confidence": pd["confidence"],
        "decision_probability": pd["decision_probability"],
        "n_answered": pd["n_answered"],
        "stop_reason": pd["stop_reason"],
        "out_path": str(out_path),
    }, ensure_ascii=False, indent=2))


def cmd_next(args: argparse.Namespace) -> int:
    bazi_path = Path(args.bazi)
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    curves = None
    if args.curves and Path(args.curves).exists():
        curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))

    current_year = args.current_year or dt.date.today().year
    state_path = Path(args.state)
    state = _load_state(state_path)

    fp = _bazi_fingerprint(bazi)
    if state is None or state.get("bazi_fingerprint") != fp:
        # 初始化 state
        detection = detect_all_phase_candidates(bazi)
        prior = _compute_prior_distribution(detection["all_detection_details"])
        state = _new_state(bazi, prior, current_year)

        # 0 题 fast-path（plan §A3）
        sorted_prior = sorted(prior.items(), key=lambda kv: (-kv[1], kv[0]))
        top1_prior = sorted_prior[0][1] if sorted_prior else 0.0
        if top1_prior >= 0.85:
            new_bazi = _finalize_phase(
                bazi, prior, {},
                stop_reason=f"S0 fast-path (prior top1={top1_prior:.3f} ≥ 0.85)",
            )
            out_path = Path(args.out) if args.out else bazi_path
            out_path.write_text(
                json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")
            _print_done(out_path, new_bazi["phase_decision"])
            # state 不持久化（按 plan §A3，fast-path 不写 state）
            return 0

    # 处理上一题答案
    if args.answer:
        if ":" in args.answer:
            qid, opt = args.answer.split(":", 1)
        elif "=" in args.answer:
            qid, opt = args.answer.split("=", 1)
        else:
            print(f"[adaptive_elicit] --answer must be 'qid:opt'; got {args.answer!r}",
                  file=sys.stderr)
            return 2
        qid = qid.strip()
        opt = opt.strip()

        # 找到候选池中的题
        candidate_phase_ids = _top_phases(state["posterior"], 5)
        pool = _build_candidate_pool(
            bazi=bazi,
            curves=curves,
            current_year=current_year,
            candidate_phase_ids=candidate_phase_ids,
            d3_n_questions=4,
        )
        q_lookup = {q.id: q for q in pool}
        q = q_lookup.get(qid)
        if q is None:
            print(f"[adaptive_elicit] unknown question id: {qid!r}", file=sys.stderr)
            return 2

        new_post = bayes_update(state["posterior"], q, opt)
        state["posterior"] = {k: float(v) for k, v in new_post.items()}
        state["answered"][qid] = opt
        state["asked_history"].append({
            "qid": qid,
            "answered_opt": opt,
        })
        state["top1_history"].append(max(new_post.values()))

    # 重新构造池子（D3 题需要按当前 top phase 重算）
    candidate_phase_ids = _top_phases(state["posterior"], 5)
    pool = _build_candidate_pool(
        bazi=bazi,
        curves=curves,
        current_year=current_year,
        candidate_phase_ids=candidate_phase_ids,
        d3_n_questions=4,
    )

    answered_ids = list(state["answered"].keys())
    eig_pool = compute_eig_pool(pool, state["posterior"], answered_ids=answered_ids)
    eig_values = [e for _, e in eig_pool]

    action, reason = should_stop(
        posterior=state["posterior"],
        n_asked=len(answered_ids),
        eig_pool=eig_values,
        top1_history=state.get("top1_history", []),
    )

    if action == "stop":
        new_bazi = _finalize_phase(
            bazi, state["posterior"], state["answered"],
            stop_reason=reason,
        )
        out_path = Path(args.out) if args.out else bazi_path
        out_path.write_text(
            json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")
        # 写完 state 留作审计（不删除）
        state["finalized"] = True
        state["final_decision"] = new_bazi["phase_decision"]["decision"]
        state["final_probability"] = new_bazi["phase_decision"]["decision_probability"]
        _save_state(state_path, state)
        _print_done(out_path, new_bazi["phase_decision"])
        return 0

    # continue → 选下一题
    pick = pick_top_question(pool, state["posterior"], answered_ids=answered_ids)
    if pick is None:
        # 无题可选 → 强行 finalize（防御）
        new_bazi = _finalize_phase(
            bazi, state["posterior"], state["answered"],
            stop_reason="无可选题，候选池耗尽",
        )
        out_path = Path(args.out) if args.out else bazi_path
        out_path.write_text(
            json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")
        _print_done(out_path, new_bazi["phase_decision"])
        return 0

    next_q, next_eig = pick
    state["asked_history"].append({
        "qid": next_q.id,
        "selected_eig": round(next_eig, 6),
        "stop_check": "continue",
        "reason": reason,
    })
    _save_state(state_path, state)

    # 输出单题 payload（不带后验信息）
    payload = _question_to_payload(next_q)
    cli_prompt = _question_to_cli_prompt(next_q)

    # 第一次抛题时附带 batch 通道提示（plan §A6'.3）
    n_already_asked = len(answered_ids)
    show_batch_hint = (n_already_asked == 0)
    batch_hint = None
    if show_batch_hint:
        batch_hint = _BATCH_HINT_TEXT

    print(json.dumps({
        "status": "ASK",
        "n_answered": n_already_asked,
        "askquestion_payload": payload,
        "cli_fallback_prompt": cli_prompt,
        "batch_hint": batch_hint,
        "agent_instructions": (
            "用宿主结构化 AskQuestion 抛 askquestion_payload 单题给用户。"
            "禁止口头转述题面 / 禁止暴露 batch_hint 之外的任何后验或候选信息。"
            "收到回答后再次调用本脚本：--answer 'qid:opt' 进入下一轮。"
        ),
    }, ensure_ascii=False, indent=2))
    return 0


def _top_phases(posterior: Dict[str, float], k: int = 5) -> List[str]:
    return [pid for pid, _ in sorted(
        posterior.items(), key=lambda kv: (-kv[1], kv[0])
    )[:k]]


# ---------------------------------------------------------------------------
# §4 batch 通道：dump-question-set + submit-batch
# ---------------------------------------------------------------------------

_BATCH_HINT_TEXT = (
    "如果你想一次性快速搞定，可以直接贴答案。两档可选：\n"
    "- 核心 14 题（hard evidence 主战，建议优先）\n"
    "- 完整 28 题（含主观自述，准确度更高但答题量大）\n"
    "需要的话回复 \"给我 14 题清单\" 或 \"给我 28 题清单\"，"
    "我会一次性列出所有题；否则直接答下面这第一题。"
)


def _select_core14(pool: List[Question]) -> List[Question]:
    """核心 14 题：D1×6 + D4×6 + D3×2（按 EIG 排序后取前 2）。

    D3 在调用方已生成；如果 D3 不足 2 题，从 D6 hard 题（实际为 soft）借？
    按 plan 严格 hard_evidence 主战，D6 是 soft，所以不借；不足直接少题。
    """
    d1 = [q for q in pool if q.dimension == "ethnography_family"]
    d4 = [q for q in pool if q.dimension == "tcm_body"]
    d3 = [q for q in pool if q.dimension == "yearly_event"]
    return d1 + d4 + d3[:2]


def _select_full28(pool: List[Question]) -> List[Question]:
    """完整 28 题：D1+D2+D3(全部)+D4+D5+D6 全部题。"""
    return list(pool)


def _shuffle_dimensions_deterministic(qs: List[Question], seed_bazi_fp: str) -> List[Question]:
    """打乱 dimension 顺序但保 bit-for-bit：用 bazi_fingerprint 作 seed 做确定性 shuffle。

    防止用户从题集顺序反推算法在测什么（plan §A6'.4 ethics 缓解）。
    """
    import random
    rng = random.Random(seed_bazi_fp)
    indices = list(range(len(qs)))
    rng.shuffle(indices)
    return [qs[i] for i in indices]


_BATCH_CAVEAT = (
    "> **答题提示**：请按你最直觉的反应填，不要前后翻看试图保持一致——"
    "刻意追求自洽反而会降低准确度。\n"
    "> 不要试图揣测题目想测什么；如不确定可挑最接近的一项。\n"
)


def _format_question_md(q: Question, idx: int) -> str:
    """单题 markdown 格式（用于 batch 题集导出）。"""
    lines = [
        f"### {idx}. [{q.id}] {q.prompt}",
        "",
    ]
    for o in q.options:
        lines.append(f"- **{o.id}**) {o.label}")
    lines.append("")
    return "\n".join(lines)


def cmd_dump_question_set(args: argparse.Namespace) -> int:
    # v9 守门 · stderr 警告：dump-question-set 不是默认 R1 路径，
    # 默认应该走 `adaptive_elicit.py next` 一题一轮。Agent 不要以为"一次性 14 题
    # 体验更顺"就默认走这里——那等于把 v9 自适应贝叶斯 EIG 流式问答物理消除。
    if not getattr(args, "ack_batch", False):
        print(
            "[adaptive_elicit] ⚠ WARNING: dump-question-set 不是 v9 默认 R1 路径。\n"
            "  默认请用 `adaptive_elicit.py next ...`（一题一轮 · EIG 选题 · 5-8 题早停）。\n"
            "  仅当用户**主动**要求 batch 一次答完时才用本子命令。\n"
            "  详见 AGENTS.md §二「关键不可跳步（v9）」 + handshake_protocol.md §0。\n"
            "  传 --ack-batch 表示已确认是用户主动选 batch，本警告即可消失。\n",
            file=sys.stderr,
        )

    bazi_path = Path(args.bazi)
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    curves = None
    if args.curves and Path(args.curves).exists():
        curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))

    current_year = args.current_year or dt.date.today().year
    detection = detect_all_phase_candidates(bazi)
    prior = _compute_prior_distribution(detection["all_detection_details"])
    candidate_phase_ids = _top_phases(prior, 5)

    # core14 需要 D3≥2 题；其他 tier 用默认 4 题
    d3_n = 2 if args.tier == "core14" else 4
    pool = _build_candidate_pool(
        bazi=bazi,
        curves=curves,
        current_year=current_year,
        candidate_phase_ids=candidate_phase_ids,
        d3_n_questions=d3_n,
    )

    if args.tier == "core14":
        selected = _select_core14(pool)
    elif args.tier == "full28":
        selected = _select_full28(pool)
    else:
        print(f"[adaptive_elicit] unknown tier: {args.tier}", file=sys.stderr)
        return 2

    # 打乱 dimension 顺序（防元叙事）
    fp = _bazi_fingerprint(bazi)
    shuffled = _shuffle_dimensions_deterministic(selected, fp)

    # 构造 markdown
    lines: List[str] = [
        f"# 八字相位校验 · {args.tier} 题集（共 {len(shuffled)} 题）",
        "",
        _BATCH_CAVEAT,
        "",
        "答完后请按以下格式贴回，每行一个：",
        "```",
        "D1_Q1=B",
        "D4_Q3=A",
        "...",
        "```",
        "",
        "或贴 JSON 格式：",
        "```json",
        "{\"D1_Q1\": \"B\", \"D4_Q3\": \"A\", ...}",
        "```",
        "",
        "---",
        "",
    ]
    for i, q in enumerate(shuffled, 1):
        lines.append(_format_question_md(q, i))

    out_path = Path(args.out) if args.out else None
    md_text = "\n".join(lines)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md_text, encoding="utf-8")
        # 同时输出元信息到 stdout
        print(json.dumps({
            "status": "DUMPED",
            "tier": args.tier,
            "n_questions": len(shuffled),
            "n_d1": sum(1 for q in shuffled if q.dimension == "ethnography_family"),
            "n_d2": sum(1 for q in shuffled if q.dimension == "relationship"),
            "n_d3": sum(1 for q in shuffled if q.dimension == "yearly_event"),
            "n_d4": sum(1 for q in shuffled if q.dimension == "tcm_body"),
            "n_d5_d6": sum(1 for q in shuffled if q.dimension == "self_perception"),
            "out_path": str(out_path),
            "agent_instructions": (
                "把 out_path 文件内容贴回对话给用户填答；用户回贴后调用 submit-batch 子命令。"
            ),
        }, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(md_text)
    return 0


def _parse_batch_answers(raw: Any) -> Dict[str, str]:
    """支持 dict / 字符串 'D1_Q1=A\\nD4_Q3=B' / JSON 字符串。"""
    if isinstance(raw, dict):
        return {str(k).strip(): str(v).strip() for k, v in raw.items()}
    if isinstance(raw, str):
        try:
            obj = json.loads(raw)
            if isinstance(obj, dict):
                return {str(k).strip(): str(v).strip() for k, v in obj.items()}
        except Exception:
            pass
        out: Dict[str, str] = {}
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
            elif ":" in line:
                k, v = line.split(":", 1)
            else:
                continue
            out[k.strip()] = v.strip()
        return out
    raise ValueError(f"unsupported batch answers type: {type(raw)}")


def cmd_submit_batch(args: argparse.Namespace) -> int:
    bazi_path = Path(args.bazi)
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    curves = None
    if args.curves and Path(args.curves).exists():
        curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))

    answers_path = Path(args.answers)
    raw = json.loads(answers_path.read_text(encoding="utf-8")) \
        if answers_path.suffix == ".json" \
        else answers_path.read_text(encoding="utf-8")
    answers = _parse_batch_answers(raw)
    if not answers:
        print("[adaptive_elicit] empty / unparseable batch answers", file=sys.stderr)
        return 2

    current_year = args.current_year or dt.date.today().year
    detection = detect_all_phase_candidates(bazi)
    prior = _compute_prior_distribution(detection["all_detection_details"])
    candidate_phase_ids = _top_phases(prior, 5)

    pool = _build_candidate_pool(
        bazi=bazi,
        curves=curves,
        current_year=current_year,
        candidate_phase_ids=candidate_phase_ids,
        d3_n_questions=4,
    )
    q_lookup = {q.id: q for q in pool}

    posterior = dict(prior)
    applied: List[str] = []
    skipped: List[str] = []
    for qid, opt in sorted(answers.items()):
        q = q_lookup.get(qid)
        if q is None:
            skipped.append(qid)
            continue
        posterior = bayes_update(posterior, q, opt)
        applied.append(qid)

    new_bazi = _finalize_phase(
        bazi, posterior, dict(answers),
        stop_reason=f"batch_submit (n={len(applied)}, skipped={len(skipped)})",
        confidence_cap="mid",  # plan §A6'.4 ethics 缓解
    )
    # 防御：top1 ≥ 0.97 时允许 high
    top_prob = new_bazi["phase_decision"]["decision_probability"]
    if top_prob >= DEFAULT_STOP_CONFIG["BATCH_high_floor"]:
        new_bazi = _finalize_phase(
            bazi, posterior, dict(answers),
            stop_reason=f"batch_submit (n={len(applied)}, skipped={len(skipped)}, high_unlocked)",
            confidence_cap=None,
        )

    out_path = Path(args.out) if args.out else bazi_path
    out_path.write_text(
        json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")

    pd = new_bazi["phase_decision"]
    print(json.dumps({
        "status": "DONE_BATCH",
        "decision": pd["decision"],
        "phase_label": pd["phase_label"],
        "confidence": pd["confidence"],
        "decision_probability": pd["decision_probability"],
        "n_applied": len(applied),
        "n_skipped": len(skipped),
        "skipped_ids": skipped[:10],
        "confidence_cap_applied": pd.get("confidence_cap_applied"),
        "out_path": str(out_path),
    }, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# §5 CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="v9 · 自适应贝叶斯问答主入口（取代 v8 一次性 26 题路径）"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    # next
    p_next = sub.add_parser("next", help="一题一轮：吃上一题答案 → 选下一题或 finalize")
    p_next.add_argument("--bazi", required=True)
    p_next.add_argument("--curves", required=False)
    p_next.add_argument("--state", required=True,
                        help="state 文件路径（建议放 output/.elicit.state.json，点开头）")
    p_next.add_argument("--answer", required=False,
                        help="上一题答案，格式 'qid:opt' 或 'qid=opt'")
    p_next.add_argument("--out", required=False, help="finalize 时写回的 bazi.json 路径（默认覆盖 --bazi）")
    p_next.add_argument("--current-year", type=int, default=None)

    # dump-question-set
    p_dump = sub.add_parser("dump-question-set", help="导出 batch 题集 markdown（非默认 R1 路径）")
    p_dump.add_argument("--bazi", required=True)
    p_dump.add_argument("--curves", required=False)
    p_dump.add_argument("--tier", choices=["core14", "full28"], required=True)
    p_dump.add_argument("--out", required=False, help="markdown 输出路径；不给则打印到 stdout")
    p_dump.add_argument("--current-year", type=int, default=None)
    p_dump.add_argument(
        "--ack-batch",
        action="store_true",
        help="确认这是用户主动选 batch（非默认）。不传会在 stderr 打 v9 警告，"
             "提醒 agent 默认应该走 `next` 子命令一题一轮。",
    )

    # submit-batch
    p_sub = sub.add_parser("submit-batch", help="一次性提交全部答案 → finalize")
    p_sub.add_argument("--bazi", required=True)
    p_sub.add_argument("--curves", required=False)
    p_sub.add_argument("--answers", required=True,
                       help="JSON 文件 {qid:opt} 或 文本文件每行 qid=opt")
    p_sub.add_argument("--out", required=False, help="写回 bazi.json 路径（默认覆盖 --bazi）")
    p_sub.add_argument("--current-year", type=int, default=None)

    args = ap.parse_args()

    if args.cmd == "next":
        return cmd_next(args)
    if args.cmd == "dump-question-set":
        return cmd_dump_question_set(args)
    if args.cmd == "submit-batch":
        return cmd_submit_batch(args)
    ap.error(f"unknown cmd: {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
