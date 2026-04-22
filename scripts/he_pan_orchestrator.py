#!/usr/bin/env python3
"""he_pan_orchestrator.py — v9.3 多人合盘编排器（adaptive_elicit 多人 state 管理）

v9.3 起，合盘场景与单盘走**同一套** v9 adaptive_elicit 路径。
本编排器维护一份 `<out-dir>/hepan.plan.json`，记录每位成员的 phase decision 状态：

  status ∈ { pending, in_progress, finalized }

并依次驱动每个 pending / in_progress 的成员去跑 v9 adaptive_elicit（单题流式贝叶斯）。
每个成员独立维护：

  <out-dir>/p<i>.bazi.json            ← solve_bazi.py 的 fork（编排器复制原 bazi 进 out-dir 后再喂给 adaptive_elicit）
  <out-dir>/p<i>.elicit.state.json    ← v9 自适应 state（schema 与单盘一致）
  <out-dir>/p<i>.virtue_motifs.json   ← virtue_motifs.py 输出（he_pan.py --require-virtue-motifs 必检）

v9.3 模式总览
─────────────────────────────────────────────────
| --mode 值        | 行为                                                                  |
|------------------|-----------------------------------------------------------------------|
| plan-v9 (新默认) | 列出每人 phase status + 下一步建议（answer_next_question / run_virtue / ready_to_run_he_pan） |
| next-person      | 找到当前 pending / in_progress 的第一人，调 adaptive_elicit.next 出单题 / 终态 |
| next-question    | 同 next-person，但限定单一 person（--person <name>）                    |
| ─── deprecated ─ | ─────────────────── 旧 v8 batch 模式（命令行需 --ack-batch 显式声明） ─ |
| plan             | 旧 batch 模式 plan（exit 2 除非 --ack-batch）                            |
| collect-r1       | 旧 v8 R1 一次性合并问卷（exit 2 除非 --ack-batch）                       |
| apply-answers    | 旧 v8 batch answers apply（exit 2 除非 --ack-batch）                     |

Exit codes
─────────────────────────────────────────────────
| code | 含义                                                                       |
|------|----------------------------------------------------------------------------|
|  0   | 成功 / 计划已输出 / 单题已输出                                                |
|  2   | 旧 batch 模式（plan / collect-r1 / apply-answers）被调用但未带 --ack-batch     |
|  3   | --he-pan 模式时仍有人 phase 未 finalize（兼容旧路径）                          |
|  4   | user_answers 缺前缀或 prefix mismatch（旧 batch）                              |
|  7   | virtue_motifs 缺失（仅在 --require-virtue-motifs 模式下）                      |

使用（v9.3 推荐）：
  python he_pan_orchestrator.py --mode plan-v9 \\
    --bazi p1.json p2.json --names Alice Bob \\
    --out-dir /tmp/hepan_state/

  python he_pan_orchestrator.py --mode next-person \\
    --bazi p1.json p2.json --names Alice Bob \\
    --out-dir /tmp/hepan_state/

旧 batch 兼容：
  python he_pan_orchestrator.py --mode plan --ack-batch \\
    --bazi p1.json p2.json --names Alice Bob
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))


# ===== 共用 =====

def _load_bazi(p: str | Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _phase_status(b: dict) -> dict:
    ph = b.get("phase") or {}
    return {
        "id": ph.get("id"),
        "label": ph.get("label"),
        "is_provisional": bool(ph.get("is_provisional", True)),
        "confidence": ph.get("confidence"),
    }


def _prefix(name: str) -> str:
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


# ===== v9.3 plan-v9 / next-person / next-question =====

def _person_paths(out_dir: Path, idx: int, name: str) -> dict:
    """每人在 out_dir 下的标准化文件路径。"""
    stem = f"p{idx + 1}"
    return {
        "stem": stem,
        "name": name,
        "bazi": out_dir / f"{stem}.bazi.json",
        "state": out_dir / f"{stem}.elicit.state.json",
        "virtue_motifs": out_dir / f"{stem}.virtue_motifs.json",
        "curves": out_dir / f"{stem}.curves.json",
    }


def _person_status(paths: dict, original_bazi_path: str) -> str:
    """status ∈ { pending, in_progress, finalized }。"""
    bazi_in_out = paths["bazi"]
    if not bazi_in_out.exists():
        # 还没复制到 out_dir，状态视为 pending
        b = _load_bazi(original_bazi_path)
    else:
        b = _load_bazi(bazi_in_out)
    ph = b.get("phase") or {}
    is_prov = bool(ph.get("is_provisional", True))
    conf = ph.get("confidence")
    if not is_prov and conf is not None and conf >= 0.60:
        return "finalized"
    if paths["state"].exists():
        return "in_progress"
    return "pending"


def _next_step_hint(status: str, paths: dict) -> str:
    if status == "pending":
        return (
            f"copy {paths['bazi'].name} into out_dir and run "
            f"`adaptive_elicit.py next --bazi {paths['bazi']} --state {paths['state']}` "
            "to start v9 single-question elicitation"
        )
    if status == "in_progress":
        return (
            f"continue v9 elicitation: "
            f"`adaptive_elicit.py next --bazi {paths['bazi']} --state {paths['state']} "
            "[--answer ...]`"
        )
    if status == "finalized":
        if not paths["virtue_motifs"].exists():
            return (
                f"phase finalized; now run "
                f"`virtue_motifs.py --bazi {paths['bazi']} --curves {paths['curves']} "
                f"--out {paths['virtue_motifs']}`"
            )
        return "ready (this person done; check other persons or proceed to he_pan.py)"
    return "unknown"


def plan_v9(
    bazi_paths: List[str],
    names: List[str],
    out_dir: Path,
) -> dict:
    """v9.3 多人 plan：每人 phase status + 下一步指示。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    persons = []
    next_actions = []
    for idx, (orig_path, n) in enumerate(zip(bazi_paths, names)):
        paths = _person_paths(out_dir, idx, n)
        status = _person_status(paths, orig_path)
        b = _load_bazi(paths["bazi"] if paths["bazi"].exists() else orig_path)
        ph_st = _phase_status(b)
        persons.append({
            "name": n,
            "stem": paths["stem"],
            "original_bazi_path": orig_path,
            "out_dir_paths": {
                "bazi": str(paths["bazi"]),
                "state": str(paths["state"]),
                "virtue_motifs": str(paths["virtue_motifs"]),
                "curves": str(paths["curves"]),
            },
            "status": status,
            "phase": ph_st,
            "virtue_motifs_present": paths["virtue_motifs"].exists(),
            "next_step": _next_step_hint(status, paths),
        })
        if status != "finalized" or not paths["virtue_motifs"].exists():
            next_actions.append({"name": n, "action": _next_step_hint(status, paths)})

    all_finalized = all(p["status"] == "finalized" for p in persons)
    all_virtue = all(p["virtue_motifs_present"] for p in persons)

    if not all_finalized:
        next_global = "answer_next_question"
    elif not all_virtue:
        next_global = "run_virtue_motifs"
    else:
        next_global = "ready_to_run_he_pan"

    return {
        "kind": "he_pan_orchestrator_plan_v9",
        "version": "v9.3",
        "n_persons": len(bazi_paths),
        "out_dir": str(out_dir),
        "persons": persons,
        "next_global_action": next_global,
        "next_actions_per_person": next_actions,
        "warnings": _build_warnings([
            {**p["phase"], "name": p["name"]} for p in persons
        ]),
        "ux_note": (
            "v9.3 合盘走单盘同一套 adaptive_elicit 单题流式路径。"
            "每个 pending / in_progress 的成员独立跑 adaptive_elicit.next，"
            "由本编排器跨成员选择「下一个该问谁」。每人 finalize 后需各跑 "
            "virtue_motifs.py，最终 he_pan.py --require-virtue-motifs 入口守门。"
            "旧 R0/R1 健康三问批量 batch 路径已退役（仅 --ack-batch 兜底）。"
        ),
    }


def _resolve_curves_path(orig_bazi_path: str, target_curves: Path) -> Optional[Path]:
    """猜原 bazi 旁边是否有同 stem 的 curves.json，若有则复制到 out_dir。"""
    src_bazi = Path(orig_bazi_path)
    candidates = [
        src_bazi.with_name(src_bazi.stem.replace("bazi", "curves") + ".json"),
        src_bazi.with_name("curves.json"),
        src_bazi.with_name(f"{src_bazi.stem}.curves.json"),
    ]
    for c in candidates:
        if c.exists():
            target_curves.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(c, target_curves)
            return target_curves
    return None


def next_person(
    bazi_paths: List[str],
    names: List[str],
    out_dir: Path,
    only_person: Optional[str] = None,
) -> dict:
    """选出第一个 pending / in_progress 的人，初始化其 out_dir 镜像。

    实际的 adaptive_elicit.next 调用由 LLM / shell wrapper 在收到本计划后执行。
    本函数只负责：
      1. 找到下一个该处理的人
      2. 若是 pending：把原 bazi.json / curves.json 复制到 out_dir 标准化路径
      3. 输出推荐运行的 adaptive_elicit / virtue_motifs 命令行
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    target_idx = None
    target_paths = None

    for idx, (orig_path, n) in enumerate(zip(bazi_paths, names)):
        if only_person and n != only_person:
            continue
        paths = _person_paths(out_dir, idx, n)
        status = _person_status(paths, orig_path)
        if status != "finalized" or not paths["virtue_motifs"].exists():
            target_idx = idx
            target_paths = paths
            target_status = status
            target_orig = orig_path
            target_name = n
            break

    if target_paths is None:
        return {
            "kind": "he_pan_orchestrator_next",
            "version": "v9.3",
            "status": "all_done",
            "message": "所有成员已 finalized 且 virtue_motifs 已生成；可以直接跑 he_pan.py。",
            "next_command": (
                f"python scripts/he_pan.py --bazi "
                + " ".join(str(_person_paths(out_dir, i, n)['bazi']) for i, n in enumerate(names))
                + f" --names {' '.join(names)} --type <marriage|cooperation|friendship|family> "
                f"--require-virtue-motifs --out {out_dir}/he_pan.json"
            ),
        }

    if target_status == "pending":
        if not target_paths["bazi"].exists():
            shutil.copy2(target_orig, target_paths["bazi"])
        _resolve_curves_path(target_orig, target_paths["curves"])

    curves_arg = (
        f"--curves {target_paths['curves']} "
        if target_paths["curves"].exists() else ""
    )
    next_cmd_elicit = (
        f"python scripts/adaptive_elicit.py next "
        f"--bazi {target_paths['bazi']} "
        f"{curves_arg}"
        f"--state {target_paths['state']}"
    )
    next_cmd_virtue = (
        f"python scripts/virtue_motifs.py "
        f"--bazi {target_paths['bazi']} "
        f"--curves {target_paths['curves']} "
        f"--out {target_paths['virtue_motifs']}"
    )

    return {
        "kind": "he_pan_orchestrator_next",
        "version": "v9.3",
        "next_person": {
            "name": target_name,
            "stem": target_paths["stem"],
            "status": target_status,
            "out_dir_paths": {
                "bazi": str(target_paths["bazi"]),
                "state": str(target_paths["state"]),
                "virtue_motifs": str(target_paths["virtue_motifs"]),
                "curves": str(target_paths["curves"]),
            },
        },
        "next_command_elicit": next_cmd_elicit,
        "next_command_virtue_after_finalize": next_cmd_virtue,
        "instruction": (
            f"对 {target_name} 跑 adaptive_elicit.next；finalize 后再跑 virtue_motifs.py；"
            f"再调本脚本 --mode next-person 处理下一人，直至 status=all_done。"
        ),
    }


# ===== 旧 v8 batch 模式（deprecated · 需 --ack-batch）=====

def plan(bazi_paths: List[str], names: List[str]) -> dict:
    """[deprecated v9.3] 旧 batch plan（保留供历史兼容）。"""
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
        "deprecated_v9_3": True,
        "n_persons": len(bazi_paths),
        "statuses": statuses,
        "needs_r1_count": len(needs_r1),
        "needs_r1_for": needs_r1,
        "next_action": (
            "answer_next_question_via_adaptive_elicit (v9.3 推荐 · 用 plan-v9 / next-person)"
            if needs_r1 else "ready_to_run_he_pan"
        ),
        "warnings": _build_warnings(statuses),
        "ux_note": (
            "[deprecated v9.3] 此模式为旧 v8 batch 路径，已被 plan-v9 / next-person 替代。"
            "请改用 --mode plan-v9 走单题流式 adaptive_elicit。"
        ),
    }


def collect_r1(bazi_paths: List[str], names: List[str]) -> dict:
    """[deprecated v9.3] 旧 v8 R1 一次性问卷。"""
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
        "deprecated_v9_3": True,
        "person_meta": person_meta,
        "askquestion_payload": {
            "title": f"[deprecated v9.3] 多人合盘 v8 R1 ({len(bazi_paths)} 人)",
            "questions": merged_questions,
        },
        "total_question_count": len(merged_questions),
        "ux_warning": (
            f"[deprecated v9.3] 共 {len(merged_questions)} 题。"
            f"v9.3 已改走 adaptive_elicit 多人单题流式（plan-v9 / next-person）。"
        ),
    }


def split_answers(user_answers: Dict[str, str], names: List[str]) -> Dict[str, Dict[str, str]]:
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
    """[deprecated v9.3] 旧 batch finalize。"""
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
    return {
        "kind": "he_pan_orchestrator_apply",
        "deprecated_v9_3": True,
        "summary": summary,
    }


# ===== 入口 =====

LEGACY_MODES = {"plan", "collect-r1", "apply-answers"}
V9_MODES = {"plan-v9", "next-person", "next-question"}


def main():
    ap = argparse.ArgumentParser(
        description="v9.3 he_pan multi-person adaptive_elicit orchestrator"
    )
    ap.add_argument("--bazi", nargs="+", required=True, help="2+ bazi.json paths")
    ap.add_argument("--names", nargs="+", help="对应称谓 (默认 P1/P2/...)")
    ap.add_argument(
        "--mode", required=True,
        choices=sorted(V9_MODES | LEGACY_MODES),
        help="v9.3: plan-v9 / next-person / next-question; "
             "legacy (deprecated, 需 --ack-batch): plan / collect-r1 / apply-answers",
    )
    ap.add_argument(
        "--out-dir",
        default=None,
        help="v9.3 多人 state 目录（plan-v9 / next-person 必填，"
             "默认 ./hepan_state/）",
    )
    ap.add_argument(
        "--person",
        default=None,
        help="next-question 模式下指定单一成员 name",
    )
    ap.add_argument(
        "--ack-batch",
        action="store_true",
        help="显式声明知晓 v9.3 已用 adaptive_elicit 多人路径替代 batch；"
             "未带此 flag 时旧模式 plan / collect-r1 / apply-answers 一律 exit 2",
    )
    ap.add_argument("--out", default=None, help="输出路径 (默认 stdout)")
    args = ap.parse_args()

    names = args.names if args.names else [f"P{i+1}" for i in range(len(args.bazi))]
    if len(names) != len(args.bazi):
        print("ERROR: --names 数量与 --bazi 不一致", file=sys.stderr)
        sys.exit(2)

    if args.mode in LEGACY_MODES and not args.ack_batch:
        print(
            f"\n[he_pan_orchestrator v9.3] 模式 '{args.mode}' 是旧 v8 batch 路径 "
            f"(已退役 / banned)。\n"
            f"v9.3 起合盘走 adaptive_elicit 多人单题流式：\n"
            f"  python {Path(__file__).name} --mode plan-v9 "
            f"--bazi {' '.join(args.bazi)} --names {' '.join(names)} "
            f"--out-dir {args.out_dir or './hepan_state/'}\n"
            f"\n如确实需要兼容跑旧 batch 路径，请加 --ack-batch 显式声明。",
            file=sys.stderr,
        )
        sys.exit(2)

    out_dir = Path(args.out_dir) if args.out_dir else Path("./hepan_state/")

    if args.mode == "plan-v9":
        result = plan_v9(args.bazi, names, out_dir)
    elif args.mode == "next-person":
        result = next_person(args.bazi, names, out_dir)
    elif args.mode == "next-question":
        result = next_person(args.bazi, names, out_dir, only_person=args.person)
    elif args.mode == "plan":
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
