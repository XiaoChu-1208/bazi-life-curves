#!/usr/bin/env python3
"""scripts/phase_posterior.py · v8

读 bazi.json + handshake.json + user_answers.json，调 _bazi_core.decide_phase 算后验，
把 phase + phase_decision（is_provisional=False）写回 bazi.json。

支持两轮校验：
  --round 1（默认）：把 R1 用户答案做后验，写 bazi.phase / phase_decision
  --round 2         ：把 R1+R2 答案合并做后验，再与 R1 决策比对，写 confirmation 字段

Usage round 1:
  python scripts/phase_posterior.py \\
    --bazi out/bazi.json \\
    --questions out/handshake.r1.json \\
    --answers out/user_answers.r1.json \\
    --out out/bazi.json

Usage round 2:
  python scripts/phase_posterior.py --round 2 \\
    --bazi out/bazi.json \\
    --r1-handshake out/handshake.r1.json --r1-answers out/user_answers.r1.json \\
    --r2-handshake out/handshake.r2.json --r2-answers out/user_answers.r2.json \\
    --out out/bazi.json

详见 references/phase_decision_protocol.md §5-§7、references/handshake_protocol.md §3-§4。
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 允许从仓库根直接运行
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bazi_core import decide_phase, assess_confirmation  # type: ignore


def _extract_dynamic_questions(handshake: Optional[Dict]) -> List[Dict]:
    """从 handshake.json 抽出 D3 动态题（带 likelihood_table）传给 decide_phase。"""
    if not handshake:
        return []
    out = []
    for q in handshake.get("questions", []):
        qid = q.get("id", "")
        if qid.startswith("D3_") and q.get("likelihood_table"):
            out.append({
                "id": qid,
                "weight_class": q.get("weight_class", "hard_evidence"),
                "likelihood_table": q["likelihood_table"],
            })
    return out


def update_posterior(
    bazi: Dict,
    handshake: Optional[Dict],
    user_answers: Dict[str, str],
) -> Dict:
    """R1 核心 API：算后验 + 写回 bazi 的 phase / phase_decision 字段。

    返回**新的** bazi dict（不就地改）。
    v9 L4：若 R1 置信度不足（reject 档）且存在强 rare zuogong hit，
             pd.rare_phase_fallback_suggestion 会被填充（供上层决定是否走 R3）。
    """
    dynamic_questions = _extract_dynamic_questions(handshake)
    pd = decide_phase(bazi, user_answers=user_answers, dynamic_questions=dynamic_questions)

    # v9 L4 · R3 降级建议
    action = _check_threshold(pd)
    if action in ("reject", "ask_more"):
        suggestion = _suggest_round3(bazi, pd)
        if suggestion is not None:
            pd["rare_phase_fallback_suggestion"] = suggestion

    new_bazi = dict(bazi)
    new_bazi["phase"] = {
        "id": pd["decision"],
        "label": pd["phase_label"],
        "is_provisional": False,
        "is_inverted": pd["decision"] != "day_master_dominant",
        "default_phase_was": "day_master_dominant",
        "confidence": pd["confidence"],
        "decision_probability": pd["decision_probability"],
    }
    new_bazi["phase_decision"] = pd
    return new_bazi


def update_posterior_round2(
    bazi: Dict,
    r1_handshake: Optional[Dict],
    r1_answers: Dict[str, str],
    r2_handshake: Optional[Dict],
    r2_answers: Dict[str, str],
) -> Tuple[Dict, Dict]:
    """R2 核心 API：合并 R1+R2 答案 → 最终后验 → 与 R1 决策比对 → confirmation_status。

    Returns:
        (new_bazi, confirmation): new_bazi 已写入 phase / phase_decision / phase_confirmation
                                  confirmation 单独返回方便上层 CLI 打印
    """
    # 1. 提取所有动态题（R1 + R2）
    dynamic_questions: List[Dict] = []
    seen_dq_ids = set()
    for hs in (r1_handshake, r2_handshake):
        for dq in _extract_dynamic_questions(hs):
            if dq["id"] not in seen_dq_ids:
                dynamic_questions.append(dq)
                seen_dq_ids.add(dq["id"])

    # 2. 单独算 R1 决策（仅用 R1 答案）作为对照基线
    pd_r1 = decide_phase(bazi, user_answers=r1_answers, dynamic_questions=dynamic_questions)

    # 3. 合并 R1+R2 答案算 R2 决策
    merged_answers: Dict[str, str] = {}
    merged_answers.update(r1_answers or {})
    merged_answers.update(r2_answers or {})  # R2 同 ID 覆盖 R1（用户改主意）
    pd_r2 = decide_phase(bazi, user_answers=merged_answers, dynamic_questions=dynamic_questions)

    # 4. confirmation_status
    confirmation = assess_confirmation(
        r1_decision=pd_r1["decision"],
        r1_probability=pd_r1["decision_probability"],
        r2_decision=pd_r2["decision"],
        r2_probability=pd_r2["decision_probability"],
    )

    # 5. 写回 bazi —— 采纳 R2 决策（R2 是 R1 的 superset 验证）
    new_bazi = dict(bazi)
    new_bazi["phase"] = {
        "id": pd_r2["decision"],
        "label": pd_r2["phase_label"],
        "is_provisional": False,
        "is_inverted": pd_r2["decision"] != "day_master_dominant",
        "default_phase_was": "day_master_dominant",
        "confidence": pd_r2["confidence"],
        "decision_probability": pd_r2["decision_probability"],
        "confirmation_status": confirmation["status"],
    }
    new_bazi["phase_decision"] = pd_r2
    new_bazi["phase_confirmation"] = {
        **confirmation,
        "round1_phase_decision": {
            "decision": pd_r1["decision"],
            "decision_probability": pd_r1["decision_probability"],
            "confidence": pd_r1["confidence"],
        },
        "round2_phase_decision": {
            "decision": pd_r2["decision"],
            "decision_probability": pd_r2["decision_probability"],
            "confidence": pd_r2["confidence"],
        },
        "n_r1_answers": len(r1_answers or {}),
        "n_r2_answers": len(r2_answers or {}),
    }
    return new_bazi, confirmation


def _check_threshold(pd: Dict) -> Optional[str]:
    """根据 R1 后验返回 ("adopt" | "ask_more" | "reject") 之一，None 表示通过。"""
    conf = pd.get("confidence", "reject")
    if conf in ("high", "mid"):
        return None  # adopt
    if conf == "low":
        return "ask_more"
    return "reject"


def _suggest_round3(bazi: Dict, pd: Dict) -> Optional[Dict]:
    """v9 L4 · R1 reject / low 时，若存在强 rare zuogong hit，建议 R3 targeted confirmation。

    返回 None = 不建议 R3；否则返回 {suggested_phase, conf, rare_hits, targeted_questions}
    """
    try:
        from rare_phase_detector import scan_from_bazi_enriched
        hits = scan_from_bazi_enriched(bazi)
    except Exception:
        return None
    zuogong_hits = [h for h in hits if h.get("dimension") == "zuogong"]
    if not zuogong_hits:
        return None
    # 取 confidence 最高者
    top = max(zuogong_hits, key=lambda h: float(h.get("confidence", 0.0)))
    if float(top.get("confidence", 0.0)) < 0.70:
        return None

    # 构造 targeted questions：
    #   - D6_Q1 / D6_Q2 / D6_Q3 是标准做功视角题，R1 若未问过则建议追加
    try:
        from _question_bank import D6_QUESTIONS  # type: ignore
        targeted = [
            {"id": q.id, "prompt": q.prompt,
             "options": [{"id": o.id, "label": o.label} for o in q.options]}
            for q in D6_QUESTIONS
        ]
    except Exception:
        targeted = []

    return {
        "reason": f"R1 后验 {pd['decision_probability']:.3f} < 接受阈值，但检测到 zuogong rare hit（{top['id']}, conf={top.get('confidence')}）",
        "suggested_phase": top["id"],
        "suggested_phase_cn": top.get("name_cn", top["id"]),
        "rare_hits_summary": [
            {"id": h["id"], "confidence": h.get("confidence"),
             "evidence": h.get("evidence", "")[:100]}
            for h in zuogong_hits
        ],
        "targeted_questions": targeted,
        "usage": ("如用户对做功视角有共鸣，将这 3 题答案合并进 R1 重算后验；"
                  "若仍未通过 ≥ 0.40 阈值，降级到 llm_fallback（render_with_caveat）。"),
    }


def update_posterior_round3(
    bazi: Dict,
    r1_handshake: Optional[Dict],
    r1_answers: Dict[str, str],
    r3_answers: Dict[str, str],
) -> Dict:
    """v9 L4 · R3 = R1 答案 + R3 targeted D6 答案的合并后验。

    不生成新 handshake（D6 题库已静态化在 _question_bank）；r3_answers 的 qid 必须是 D6_*。
    返回的 new_bazi 带 phase_decision.round3_merged = True。
    """
    dynamic_questions = _extract_dynamic_questions(r1_handshake)
    merged: Dict[str, str] = dict(r1_answers or {})
    merged.update(r3_answers or {})
    pd = decide_phase(bazi, user_answers=merged, dynamic_questions=dynamic_questions)
    pd["round3_merged"] = True
    pd["round3_n_extra_answers"] = len(r3_answers or {})

    new_bazi = dict(bazi)
    new_bazi["phase"] = {
        "id": pd["decision"],
        "label": pd["phase_label"],
        "is_provisional": False,
        "is_inverted": pd["decision"] != "day_master_dominant",
        "default_phase_was": "day_master_dominant",
        "confidence": pd["confidence"],
        "decision_probability": pd["decision_probability"],
        "round": "R3",
    }
    new_bazi["phase_decision"] = pd
    return new_bazi


def _load_json(path: Optional[str]) -> Optional[Dict]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="v8 · phase posterior update CLI")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径（输入 + 默认输出）")
    ap.add_argument("--out", required=False,
                    help="输出 bazi.json 路径（默认覆盖 --bazi）")
    ap.add_argument("--round", type=int, default=1, choices=[1, 2, 3],
                    help="校验轮次：1=R1 算初版后验；2=合并 R1+R2；3=R1+D6 targeted（v9 L4 rare-phase fallback）")

    # round=1 args
    ap.add_argument("--questions", required=False,
                    help="（round=1）handshake.json 路径（含 D3 题 likelihood_table；可选）")
    ap.add_argument("--answers", required=False,
                    help="（round=1）user_answers.json 路径，格式 {qid:opt}")

    # round=2 args
    ap.add_argument("--r1-handshake", required=False,
                    help="（round=2 必填）R1 handshake.json")
    ap.add_argument("--r1-answers", required=False,
                    help="（round=2 必填）R1 user_answers.json")
    ap.add_argument("--r2-handshake", required=False,
                    help="（round=2 必填）R2 handshake.json")
    ap.add_argument("--r2-answers", required=False,
                    help="（round=2 必填）R2 user_answers.json")

    # round=3 args （v9 L4 · rare-phase R3 targeted confirmation）
    ap.add_argument("--r3-answers", required=False,
                    help="（round=3 必填）D6_* 答案 JSON（{qid:opt}）")
    args = ap.parse_args()

    bazi_path = Path(args.bazi)
    out_path = Path(args.out) if args.out else bazi_path
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))

    if args.round == 3:
        for k in ("questions", "answers", "r3_answers"):
            if not getattr(args, k):
                ap.error(f"--{k.replace('_','-')} required when --round 3")
        r1_handshake = _load_json(args.questions)
        r1_answers = _load_json(args.answers) or {}
        r3_answers = _load_json(args.r3_answers) or {}
        if not isinstance(r1_answers, dict) or not isinstance(r3_answers, dict):
            raise ValueError("answers JSON must be object {qid: opt}")
        new_bazi = update_posterior_round3(bazi, r1_handshake, r1_answers, r3_answers)
        out_path.write_text(json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")
        pd = new_bazi["phase_decision"]
        print(f"[phase_posterior R3] decision={pd['decision']} "
              f"confidence={pd['confidence']} prob={pd['decision_probability']:.4f} "
              f"(merged {pd['round3_n_extra_answers']} D6 answers)")
        print(f"[phase_posterior R3] wrote {out_path}")
        return

    if args.round == 2:
        for k in ("r1_handshake", "r1_answers", "r2_handshake", "r2_answers"):
            if not getattr(args, k):
                ap.error(f"--{k.replace('_','-')} required when --round 2")

        r1_handshake = _load_json(args.r1_handshake)
        r2_handshake = _load_json(args.r2_handshake)
        r1_answers = _load_json(args.r1_answers) or {}
        r2_answers = _load_json(args.r2_answers) or {}
        if not isinstance(r1_answers, dict) or not isinstance(r2_answers, dict):
            raise ValueError("r1/r2 answers JSON must be objects {qid: opt}")

        new_bazi, confirmation = update_posterior_round2(
            bazi=bazi,
            r1_handshake=r1_handshake,
            r1_answers=r1_answers,
            r2_handshake=r2_handshake,
            r2_answers=r2_answers,
        )
        out_path.write_text(
            json.dumps(new_bazi, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        pd = new_bazi["phase_decision"]
        action = confirmation["action"].upper()
        msg = (
            f"[phase_posterior R2] {confirmation['status']}: "
            f"R1={confirmation['r1_decision']}(p={confirmation['r1_probability']:.3f}) → "
            f"R2={confirmation['r2_decision']}(p={confirmation['r2_probability']:.3f}) → action={action}"
        )
        print(msg)
        print(f"[phase_posterior R2] {confirmation['message']}")
        print(f"[phase_posterior R2] wrote {out_path}")
        return

    # round = 1（默认）
    if not args.answers:
        ap.error("--answers required when --round 1")

    handshake = _load_json(args.questions)
    user_answers = _load_json(args.answers)
    if not isinstance(user_answers, dict):
        raise ValueError("user_answers.json must be a JSON object {question_id: option_id}")

    new_bazi = update_posterior(bazi, handshake, user_answers)

    out_path.write_text(
        json.dumps(new_bazi, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pd = new_bazi["phase_decision"]
    action = _check_threshold(pd)
    msg = (
        f"[phase_posterior R1] decision={pd['decision']} "
        f"confidence={pd['confidence']} prob={pd['decision_probability']:.4f}"
    )
    if action == "ask_more":
        msg += "  ← LOW confidence → 建议追问 top-2 间最 discriminative 的 2-3 题"
    elif action == "reject":
        msg += "  ← REJECT → 后验 < 0.40，请核对时辰 / 性别"
    else:
        msg += "  ← R1 通过 → 建议进入 Round 2 confirmation 验证"
    print(msg)
    print(f"[phase_posterior R1] wrote {out_path}")


if __name__ == "__main__":
    main()
