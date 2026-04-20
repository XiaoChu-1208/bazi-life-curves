#!/usr/bin/env python3
"""phase_inversion_loop.py — v7.2 / v8 Auto-Loop · 相位反演校验循环编排器。

把 P1-7 协议的 "dump → 选 → 重跑 → 二轮校验" 4 步拆解成一条命令搞定，
减少 LLM 手动写 shell 调度的负担。

工作流程：
    1. dump phase candidates（按 P1-P5 detect 出 N 个候选）
    2. 自动选 top-1 候选（也可 --pick <phase_id> 显式指定）
    3. 跑 score_curves --override-phase <pick> → curves_inverted.json
    4. 跑 handshake --phase-id <pick> → handshake_round2.json（二轮校验题）
    5. 打印 LLM 该如何向用户呈现二轮校验

LLM 流程：
    [Round 1 命中率 ≤ 2/6]
       ↓ 自动调用本脚本
    [打印二轮 6 题给用户]
       ↓ 用户作答
    [LLM 算二轮命中率]
       ├ ≥ 4/6 → 调用 save_confirmed_facts.py 写 phase_override → 后续都用反演相位
       └ < 4/6 → 换下一个候选（再调本脚本 + --pick <next_id>）
                 / 全部不达标 → 真正建议核对时辰

使用：
    # 自动选 top-1 候选
    python scripts/phase_inversion_loop.py --bazi out/bazi.json --out-dir out/

    # 显式指定候选
    python scripts/phase_inversion_loop.py --bazi out/bazi.json --pick floating_dms_to_cong_cai --out-dir out/

    # JSON 模式（仅打印 JSON，便于 LLM 解析）
    python scripts/phase_inversion_loop.py --bazi out/bazi.json --json --out-dir out/
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))


def run(cmd: list[str], capture: bool = False) -> str:
    if capture:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            sys.exit(r.returncode)
        return r.stdout
    else:
        r = subprocess.run(cmd)
        if r.returncode != 0:
            sys.exit(r.returncode)
        return ""


def main():
    ap = argparse.ArgumentParser(description="v8 Auto-Loop 相位反演校验循环编排器")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--out-dir", default="output", help="输出目录")
    ap.add_argument("--age-end", type=int, default=60)
    ap.add_argument("--pick", default=None,
                    help="显式选择 phase_id；不指定时自动选 top-1（按 detector_score 排）")
    ap.add_argument("--default-hit-rate", default=None,
                    help="可选：当前默认相位的命中率（如 '1/6'），写进 phase_candidates.json")
    ap.add_argument("--json", action="store_true",
                    help="JSON 模式：只输出最终结果 JSON，便于 LLM 解析")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    candidates_path = out_dir / "phase_candidates.json"
    curves_inverted_path = out_dir / "curves_phase_inverted.json"
    handshake_round2_path = out_dir / "handshake_round2.json"

    # Step 1 · dump candidates
    cmd_dump = [
        sys.executable, str(SCRIPT_DIR / "handshake.py"),
        "--bazi", args.bazi,
        "--dump-phase-candidates",
        "--out", str(candidates_path),
    ]
    if args.default_hit_rate:
        cmd_dump += ["--default-hit-rate", args.default_hit_rate]
    if not args.json:
        print(f"[loop] step1 · dump phase candidates → {candidates_path}")
    run(cmd_dump)

    candidates_doc = json.loads(candidates_path.read_text(encoding="utf-8"))
    cands = candidates_doc.get("phase_candidates", [])
    if not cands:
        msg = {
            "status": "no_candidates",
            "message": (
                "默认相位算法没识别出任何反向可能性。命中率低更可能是八字本身错（最常见：性别字段填错 / "
                "出生时辰差 1 小时）。建议先核对原始输入再来。"
            ),
            "candidates_path": str(candidates_path),
        }
        if args.json:
            print(json.dumps(msg, ensure_ascii=False, indent=2))
        else:
            print(f"[loop] no candidates 触发 → {msg['message']}")
        return

    # Step 2 · pick
    if args.pick:
        chosen = next((c for c in cands if c["phase_id"] == args.pick), None)
        if chosen is None:
            valid = [c["phase_id"] for c in cands]
            sys.exit(f"--pick {args.pick!r} not in detected candidates: {valid}")
    else:
        chosen = cands[0]  # detect_all 返回的顺序是按 score 从大到小
    pick_id = chosen["phase_id"]
    if not args.json:
        print(f"[loop] step2 · pick = {pick_id} ({chosen.get('phase_label')})")

    # Step 3 · score_curves --override-phase
    cmd_score = [
        sys.executable, str(SCRIPT_DIR / "score_curves.py"),
        "--bazi", args.bazi,
        "--out", str(curves_inverted_path),
        "--age-end", str(args.age_end),
        "--override-phase", pick_id,
    ]
    if not args.json:
        print(f"[loop] step3 · score_curves --override-phase → {curves_inverted_path}")
    run(cmd_score)

    # Step 4 · handshake --phase-id（生成二轮校验 6 题）
    cmd_hs = [
        sys.executable, str(SCRIPT_DIR / "handshake.py"),
        "--bazi", args.bazi,
        "--curves", str(curves_inverted_path),
        "--phase-id", pick_id,
        "--out", str(handshake_round2_path),
    ]
    if not args.json:
        print(f"[loop] step4 · handshake --phase-id (二轮校验题) → {handshake_round2_path}")
    run(cmd_hs)

    handshake_doc = json.loads(handshake_round2_path.read_text(encoding="utf-8"))

    # Step 5 · 输出 LLM 指令
    other_cands = [c["phase_id"] for c in cands if c["phase_id"] != pick_id]
    summary = {
        "status": "round2_ready",
        "pick": pick_id,
        "pick_label": chosen.get("phase_label"),
        "pick_evidence": chosen.get("evidence"),
        "pick_explain_for_user": chosen.get("llm_explain_for_user"),
        "n_candidates_total": len(cands),
        "other_candidates_for_fallback": other_cands,
        "files": {
            "phase_candidates": str(candidates_path),
            "curves_inverted": str(curves_inverted_path),
            "handshake_round2": str(handshake_round2_path),
        },
        "round2_questions": {
            "round0": handshake_doc["round0_candidates"],
            "round1": handshake_doc["round1_candidates"],
            "round2": handshake_doc["round2_candidates"],
        },
        "next_step_for_llm": (
            f"按 handshake_round2.json 的 instruction_for_llm 把【二轮 6 题】抛给用户作答。"
            f"用户答完 → 算二轮命中率：\n"
            f"  · ≥ 4/6 → 落地。调用 save_confirmed_facts.py 写 kind=phase_override / "
            f"after={pick_id}，然后用 score_curves --confirmed-facts 重跑后续。\n"
            f"  · < 4/6 + 还有候选 → 重跑本脚本 + --pick {other_cands[0] if other_cands else '<next>'}\n"
            f"  · 全部候选都 < 4/6 → 真正建议用户核对时辰。"
        ),
        "save_command_template": (
            f"python scripts/save_confirmed_facts.py --bazi {args.bazi} "
            f"--out {out_dir}/confirmed_facts.json "
            f"--add-structural phase_override day_master_dominant {pick_id} "
            f"--reason '二轮校验命中率 X/6 → 反演相位落地'"
        ),
        "rerun_with_confirmed_command_template": (
            f"python scripts/score_curves.py --bazi {args.bazi} "
            f"--confirmed-facts {out_dir}/confirmed_facts.json "
            f"--out {out_dir}/curves_final.json --age-end {args.age_end}"
        ),
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print()
        print(f"[loop] ✓ 完成 · 接下来的动作：")
        print(f"  1. 把 {handshake_round2_path} 里的 R0/R1/R2 6 题抛给用户作答")
        print(f"  2. 算二轮命中率 → ≥ 4/6 落地 / < 4/6 换 --pick {other_cands[0] if other_cands else '<next>'}")
        print(f"  3. 落地命令模板：")
        print(f"     {summary['save_command_template']}")
        print(f"     {summary['rerun_with_confirmed_command_template']}")


if __name__ == "__main__":
    main()
