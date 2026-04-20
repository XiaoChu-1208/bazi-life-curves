#!/usr/bin/env python3
"""he_pan_orchestrator.py — v9 多人 v8 编排器（PR-2 · PR-4 共用）

对 N 份 bazi.json 串行做：
  1. 检查每份 phase.is_provisional —— 若仍 provisional, 调用 handshake 输出多人命名空间问卷
  2. 等待用户答完, 收集 user_answers (前缀 p1_/p2_/...)
  3. 拆分回各自命名空间, 调用 phase_posterior 重算每个人
  4. 全部 finalized 后, 调用 he_pan 生成合盘

编排模式：
  --plan           只输出"接下来要做什么"的执行计划, 不调任何子步骤 (适合 LLM 读)
  --collect-r1     输出 N × R1 问卷, 一次性给用户
  --apply-answers  从 stdin / file 读 user_answers, 拆分并各自 finalize, 写回各 bazi.json
  --he-pan         在所有 bazi.json finalized 后跑 he_pan 并写 he_pan.json

使用：
  python he_pan_orchestrator.py \
    --bazi p1.json p2.json --names Alice Bob \
    --type marriage --out he_pan.json --plan

Exit codes:
  0 - 成功 / 计划已输出
  3 - 任一人 phase 未 finalized 且 --he-pan 模式被触发
  4 - user_answers 缺前缀或 prefix mismatch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_bazi(p: str) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _phase_status(b: dict) -> dict:
    ph = b.get("phase") or {}
    return {
        "id": ph.get("id"),
        "label": ph.get("label"),
        "is_provisional": bool(ph.get("is_provisional", True)),
        "confidence": ph.get("confidence"),
    }


def plan(bazi_paths: List[str], names: List[str]) -> dict:
    """输出执行计划 JSON (LLM 友好)。"""
    statuses = []
    needs_r1 = []
    for p, n in zip(bazi_paths, names):
        b = _load_bazi(p)
        st = _phase_status(b)
        statuses.append({"name": n, "path": p, **st})
        if st["is_provisional"]:
            needs_r1.append({"name": n, "path": p, "prefix": _prefix(n)})
    return {
        "kind": "he_pan_orchestrator_plan",
        "n_persons": len(bazi_paths),
        "statuses": statuses,
        "needs_r1_count": len(needs_r1),
        "needs_r1_for": needs_r1,
        "next_action": (
            "answer_r1_for_listed_persons" if needs_r1
            else "ready_to_run_he_pan"
        ),
        "warnings": _build_warnings(statuses),
        "ux_note": (
            "v9: 多人合盘的 R1 问卷会按前缀 p1_/p2_/... 命名空间合并，"
            "答完一次性 apply 即可；若一人答错可单独重跑该人的 phase_posterior。"
            "总题量预计 = 人数 × 8。建议各自先跑单盘 v8 再合盘以减轻 UX 负担。"
        ),
    }


def _prefix(name: str) -> str:
    """name → 前缀（p1_/p2_/...）。这里用稳定的 hash-free 顺序 prefix。"""
    return f"{name.lower().replace(' ', '_')}_"


def _build_warnings(statuses: List[dict]) -> List[str]:
    warns = []
    for s in statuses:
        if s["is_provisional"]:
            warns.append(f"{s['name']}: phase.is_provisional=True, 不能直接合盘")
        elif s.get("confidence") is not None and s["confidence"] < 0.60:
            warns.append(
                f"{s['name']}: confidence={s['confidence']:.2f}<0.60, "
                f"合盘会放大不确定 (HS-R7 必须披露)"
            )
    return warns


def collect_r1(bazi_paths: List[str], names: List[str]) -> dict:
    """生成多人 R1 命名空间合并问卷。

    委派 handshake 各自跑一遍, 然后给每个 question_id 加 prefix。
    """
    try:
        from handshake import build as handshake_build  # type: ignore
    except ImportError as e:
        return {"kind": "error", "message": f"handshake not importable: {e}"}

    merged_questions = []
    person_meta = []
    for p, n in zip(bazi_paths, names):
        b = _load_bazi(p)
        prefix = _prefix(n)
        try:
            hs = handshake_build(b)
        except Exception as e:
            return {"kind": "error", "message": f"handshake.build failed for {n}: {e}"}

        ask_payload = hs.get("askquestion_payload") or {}
        questions = ask_payload.get("questions") or []
        for q in questions:
            qid = q.get("id", "")
            q2 = dict(q)
            q2["id"] = f"{prefix}{qid}"
            q2["_belongs_to"] = n
            merged_questions.append(q2)
        person_meta.append({
            "name": n, "path": p, "prefix": prefix,
            "question_count": len(questions),
        })

    return {
        "kind": "he_pan_orchestrator_r1",
        "person_meta": person_meta,
        "askquestion_payload": {
            "title": f"多人合盘 v8 R1 ({len(bazi_paths)} 人)",
            "questions": merged_questions,
        },
        "total_question_count": len(merged_questions),
        "ux_warning": (
            f"共 {len(merged_questions)} 题，按 prefix 拆分回各人。"
            f"建议分批回答，每人 8 题为单元。"
        ),
    }


def split_answers(user_answers: Dict[str, str], names: List[str]) -> Dict[str, Dict[str, str]]:
    """按 prefix 把扁平 answers 拆回 {name: {qid: option_id}}。"""
    out: Dict[str, Dict[str, str]] = {n: {} for n in names}
    unmatched: List[str] = []
    for full_qid, opt in user_answers.items():
        matched = False
        for n in names:
            pre = _prefix(n)
            if full_qid.startswith(pre):
                out[n][full_qid[len(pre):]] = opt
                matched = True
                break
        if not matched:
            unmatched.append(full_qid)
    if unmatched:
        raise ValueError(
            f"answers contain {len(unmatched)} question_ids without recognised prefix "
            f"({_prefix(names[0])} ...): {unmatched[:3]}"
        )
    return out


def apply_answers(bazi_paths: List[str], names: List[str],
                  user_answers: Dict[str, str]) -> dict:
    """对每个人重算 phase 并写回各自 bazi.json。"""
    try:
        from phase_posterior import compute_posterior  # type: ignore
    except ImportError as e:
        return {"kind": "error", "message": f"phase_posterior not importable: {e}"}

    per_person = split_answers(user_answers, names)
    summary = []
    for p, n in zip(bazi_paths, names):
        b = _load_bazi(p)
        ans = per_person.get(n, {})
        if not ans:
            summary.append({"name": n, "skipped": True, "reason": "no answers"})
            continue
        try:
            posterior = compute_posterior(b, ans)
        except Exception as e:
            summary.append({"name": n, "error": str(e)})
            continue
        b["phase"] = {
            "id": posterior["decision"],
            "label": posterior.get("phase_label"),
            "is_provisional": False,
            "is_inverted": posterior["decision"] != "day_master_dominant",
            "confidence": posterior.get("confidence"),
            "decision_probability": posterior.get("decision_probability"),
            "default_phase_was": "day_master_dominant",
        }
        b["phase_posterior"] = posterior
        Path(p).write_text(json.dumps(b, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        summary.append({
            "name": n, "path": p,
            "phase_id": b["phase"]["id"],
            "confidence": b["phase"]["confidence"],
            "n_answers": len(ans),
        })
    return {"kind": "he_pan_orchestrator_apply", "summary": summary}


def main():
    ap = argparse.ArgumentParser(description="v9 he_pan multi-person v8 orchestrator")
    ap.add_argument("--bazi", nargs="+", required=True, help="2+ bazi.json paths")
    ap.add_argument("--names", nargs="+", help="对应称谓 (默认 P1/P2/...)")
    ap.add_argument("--mode", required=True,
                    choices=["plan", "collect-r1", "apply-answers"],
                    help="plan: 只输出执行计划; collect-r1: 出多人合并问卷; "
                         "apply-answers: 读 stdin JSON 拆分并 finalize")
    ap.add_argument("--out", default=None, help="输出路径 (默认 stdout)")
    args = ap.parse_args()

    names = args.names if args.names else [f"P{i+1}" for i in range(len(args.bazi))]
    if len(names) != len(args.bazi):
        print("ERROR: --names 数量与 --bazi 不一致", file=sys.stderr)
        sys.exit(2)

    if args.mode == "plan":
        result = plan(args.bazi, names)
    elif args.mode == "collect-r1":
        result = collect_r1(args.bazi, names)
    else:  # apply-answers
        try:
            payload = json.loads(sys.stdin.read())
            ua = payload.get("user_answers") or payload
        except Exception as e:
            print(f"ERROR: invalid stdin JSON: {e}", file=sys.stderr)
            sys.exit(4)
        result = apply_answers(args.bazi, names, ua)

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"[he_pan_orchestrator] wrote {args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
