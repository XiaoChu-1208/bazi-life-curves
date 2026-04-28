#!/usr/bin/env python3
"""apply_event_finalize.py — 把事件 ask-loop 最终融合后验**写回** bazi.json

线上发现 (2026-04)：事件 ask-loop 算出的新后验只更新了 in-memory state，
**没同步到** bazi.json.phase_decision —— 导致 deliver pipeline 仍按 elicit
原判定写解读，事件题白答了。

本脚本：
  1. 读 bazi.json
  2. 用新的 fused posterior 调 adaptive_elicit._finalize_phase（同一套
     phase / phase_decision 字段写入逻辑，包括重新算 strength_after_phase /
     yongshen_after_phase / xishen / jishen / climate 等所有 derived 字段）
  3. 写回 bazi.json

注意：只更新 bazi.json。curves.json 和 virtue_motifs.json 必须由编排者
（Claude / 调用方）再分别调 score_curves.py 和 virtue_motifs.py 重跑
——否则 deliver 拿到的曲线还是旧 phase 算的。

完整编排步骤详见 references/event_ask_loop_protocol.md。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import adaptive_elicit  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser(
        description="把事件 ask-loop 后验写回 bazi.json")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--posterior", required=True,
                    help="JSON 字符串：{phase_id: probability, ...}")
    ap.add_argument("--stop-reason", default="event_loop_converged",
                    help="写进 phase_decision.stop_reason")
    ap.add_argument("--answered", default="{}",
                    help="JSON 字符串：{qid: answer} —— 通常 event-loop 不传，留空字典")
    args = ap.parse_args()

    bazi_path = Path(args.bazi)
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    posterior = json.loads(args.posterior)
    answered = json.loads(args.answered)

    # 用 adaptive_elicit._finalize_phase 重写 bazi.phase / phase_decision
    # 同一个函数会重新算 strength / yongshen / xishen / jishen / climate
    # 让 derived 字段跟新 phase 一致。
    new_bazi = adaptive_elicit._finalize_phase(
        bazi, posterior, answered, args.stop_reason)

    # 加一个标记字段，让下游知道这是事件 loop 改写过的
    if "phase_decision" in new_bazi and isinstance(new_bazi["phase_decision"], dict):
        new_bazi["phase_decision"]["event_loop_finalized"] = True
        new_bazi["phase_decision"]["elicitation_path"] = "event_loop_v9.6"

    bazi_path.write_text(
        json.dumps(new_bazi, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pd = new_bazi.get("phase_decision", {})
    print(json.dumps({
        "status": "DONE",
        "decision": pd.get("decision"),
        "phase_label": pd.get("phase_label"),
        "confidence": pd.get("confidence"),
        "decision_probability": pd.get("decision_probability"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
