#!/usr/bin/env python3
"""multi_school_vote.py — v9 PR-6 多流派加权投票 + open_phase 逃逸阀

流程:
  1. 对 bazi 跑每个 phase_candidate 流派的 judge, 收集所有 phase 候选
  2. 候选按 phase id 聚合; 每条票 = school_weight * candidate_confidence
  3. 总票数归一化 → posterior 分布
  4. ratify_only 流派 (紫微/铁板) 不出候选, 但通过 fallback_phase_candidates 投赞同票
  5. consensus_level: top1_posterior, top1_top2_gap
  6. open_phase 逃逸阀:
       top1 < 0.55 OR top1_top2_gap < 0.10 → 落 open_phase

输出 JSON:
  {
    "phase_composition": [{id, weight, role}, ...],
    "decision": "phase_id 或 open_phase",
    "consensus_level": "high" | "medium" | "low",
    "top1_posterior": 0.62,
    "top1_top2_gap": 0.18,
    "alternative_readings": [{school, phase_id, confidence, ...}, ...],
    "rare_phase_scan": [...],
    "schools_voted": {school_id: [candidates]},
  }

CLI:
  python multi_school_vote.py --bazi bazi.json [--out vote.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _school_registry import SCHOOLS, get_phase_candidate_schools


OPEN_PHASE_THRESHOLDS = {
    "top1_min": 0.55,
    "top1_top2_gap_min": 0.10,
}


def vote(bazi: dict,
         fallback_phase_candidates: List[Dict] = None) -> Dict:
    """主入口: 跑所有 school, 加权投票, 输出 phase_composition + open_phase 决策."""
    schools_voted: Dict[str, List[Dict]] = {}
    weighted_votes: Dict[str, float] = defaultdict(float)
    candidates_by_id: Dict[str, List[Dict]] = defaultdict(list)
    raw_total_weight = 0.0

    for school_id in get_phase_candidate_schools():
        info = SCHOOLS[school_id]
        try:
            cands = info["judge"](bazi) or []
        except Exception as e:
            cands = []
        schools_voted[school_id] = cands
        weight = info["weight"]
        raw_total_weight += weight
        for c in cands:
            pid = c["id"]
            vote_strength = weight * c.get("confidence", 0.7)
            weighted_votes[pid] += vote_strength
            candidates_by_id[pid].append({
                "school": school_id,
                "school_label": info["label"],
                "confidence": c.get("confidence"),
                "evidence": c.get("evidence"),
            })

    # 兜底候选回流投票 (按各自 school 的 weight)
    fallback_phase_candidates = fallback_phase_candidates or []
    for fc in fallback_phase_candidates:
        sch = fc.get("school", "fallback")
        wt = SCHOOLS.get(sch, {}).get("weight", 0.5)
        pid = fc["id"]
        vote_strength = wt * fc.get("match_confidence", 0.5) * 0.7  # 兜底打 7 折
        weighted_votes[pid] += vote_strength
        candidates_by_id[pid].append({
            "school": sch,
            "school_label": SCHOOLS.get(sch, {}).get("label", sch),
            "confidence": fc.get("match_confidence"),
            "evidence": fc.get("古书引用") or fc.get("evidence") or "(LLM fallback)",
            "via": "llm_fallback",
        })

    # 归一化
    total_weight = sum(weighted_votes.values()) or 1.0
    posteriors = {pid: round(v / total_weight, 4)
                  for pid, v in weighted_votes.items()}

    sorted_phases = sorted(posteriors.items(), key=lambda x: x[1], reverse=True)
    if sorted_phases:
        top1_id, top1_p = sorted_phases[0]
        top2_id, top2_p = sorted_phases[1] if len(sorted_phases) > 1 else (None, 0.0)
        gap = top1_p - top2_p
    else:
        top1_id, top1_p, top2_id, gap = None, 0.0, None, 0.0

    # open_phase 逃逸阀
    open_phase_triggered = False
    open_reasons = []
    if top1_p < OPEN_PHASE_THRESHOLDS["top1_min"]:
        open_phase_triggered = True
        open_reasons.append(
            f"top1_posterior={top1_p:.2f} < {OPEN_PHASE_THRESHOLDS['top1_min']}"
        )
    if 0 < gap < OPEN_PHASE_THRESHOLDS["top1_top2_gap_min"]:
        open_phase_triggered = True
        open_reasons.append(
            f"top1_top2_gap={gap:.2f} < {OPEN_PHASE_THRESHOLDS['top1_top2_gap_min']}"
        )

    if open_phase_triggered:
        decision = "open_phase"
        consensus = "low"
    elif top1_p >= 0.70:
        decision = top1_id
        consensus = "high"
    else:
        decision = top1_id
        consensus = "medium"

    # 5.3 phase_composition: top 3 按 weight
    phase_composition = []
    for i, (pid, p) in enumerate(sorted_phases[:3]):
        role = ["primary", "secondary", "modifier"][i] if i < 3 else "minor"
        phase_composition.append({
            "id": pid,
            "weight": p,
            "role": role,
        })

    # 5.10 alternative_readings: 包含 top 5 (含 LLM 兜底来源标记)
    alternative_readings = []
    for pid, p in sorted_phases[:5]:
        for c in candidates_by_id[pid]:
            alternative_readings.append({
                "phase_id": pid,
                "posterior": p,
                "school": c["school"],
                "school_label": c["school_label"],
                "school_confidence": c["confidence"],
                "evidence": c["evidence"],
                "via": c.get("via", "school_judge"),
                "if_this_is_right_then": _phase_implication(pid),
            })

    # rare_phase_scan: 来自 PR-5 的全量 detector 扫描结果
    try:
        from rare_phase_detector import scan_from_bazi
        rare_phase_scan = scan_from_bazi(bazi)
    except Exception:
        rare_phase_scan = []

    return {
        "version": "v9-PR6",
        "decision": decision,
        "consensus_level": consensus,
        "top1_posterior": top1_p,
        "top1_top2_gap": gap,
        "open_phase_triggered": open_phase_triggered,
        "open_phase_reasons": open_reasons,
        "phase_composition": phase_composition,
        "alternative_readings": alternative_readings,
        "rare_phase_scan": rare_phase_scan,
        "schools_voted": {
            sid: [{"id": c["id"], "confidence": c.get("confidence"),
                   "evidence": c.get("evidence")}
                  for c in cands]
            for sid, cands in schools_voted.items()
        },
        "posteriors_full": posteriors,
        "ratify_schools_note": (
            "Tier 3 (紫微 / 铁板神数) 在算法中无法独立判, "
            "走 references/llm_fallback_protocol.md 由对话内 LLM 兜底."
        ),
        "narrative_caution": (
            "本投票结果为算法对你提供事件之上的最佳后验估计, "
            "不构成对未来人生剧本的确定预测. "
            "任何与你强烈直觉冲突的判定, 请保留终极裁定权 (HS-R7.3)."
        ),
        "must_be_true": _generate_must_be_true(decision, phase_composition),
    }


def _phase_implication(phase_id: str) -> str:
    """每个 phase 给一句'若此判正确则相应预期'话术 (5.10 多流派备解)."""
    impl = {
        "qi_yin_xiang_sheng": "印星贵人型大事件 (升学 / 体制提拔 / 学术贵人) 应集中在 印星岁运",
        "shang_guan_sheng_cai": "才华变现型大事件 (作品 / 商业突破) 应集中在 食伤生财岁运",
        "floating_dms_to_cong_cai": "财星岁运为大利, 印比岁运反而碍事",
        "floating_dms_to_cong_sha": "官杀岁运为大利, 食伤护身之运反而别扭",
        "huaqi_to_土": "用神锁定为土, 土旺岁运为大利, 木克土岁运为忌",
        "huaqi_to_金": "用神锁定为金, 金旺岁运为大利, 火克金岁运为忌",
        "huaqi_to_水": "用神锁定为水, 水旺岁运为大利, 土克水岁运为忌",
        "huaqi_to_木": "用神锁定为木, 木旺岁运为大利, 金克木岁运为忌",
        "huaqi_to_火": "用神锁定为火, 火旺岁运为大利, 水克火岁运为忌",
        "climate_inversion_dry_top": "用神锁水, 燥火大运反成限制",
        "climate_inversion_wet_top": "用神锁火, 寒湿大运反成限制",
        "day_master_dominant": "日主主导 / 扶抑常规处理, 用神顺日主强弱",
        "open_phase": "算法在此盘上不下结论 — 请补充更多事件锚点",
    }
    return impl.get(phase_id, f"({phase_id} 暂未填实证含义, 请扩 _phase_implication)")


def _generate_must_be_true(decision: str, composition: List[Dict]) -> List[Dict]:
    """5.2 phase-必然预测: 给 adopt phase 列出 must_be_true / must_be_false 钩子."""
    if decision == "open_phase":
        return [{
            "prediction": "在用户补充至少 2 个具体年份的具体事件后, 算法应能落到某个 phase",
            "evidence_required": "具体年份 + 事件类型 + 该事件的强度 (大事 / 中事 / 小事)",
        }]
    return [{
        "prediction": f"adopted phase '{decision}' 应能解释用户至少 2 条 anchor 事件",
        "evidence_required": "对每条 anchor, 该 phase 给出 likelihood >= default phase",
    }]


def main():
    ap = argparse.ArgumentParser(description="v9 PR-6 多流派加权投票")
    ap.add_argument("--bazi", required=True, help="bazi.json path")
    ap.add_argument("--fallback", default=None,
                    help="可选: LLM 兜底产物 (fallback_phase_candidates JSON)")
    ap.add_argument("--out", default=None, help="输出 vote.json (默认 stdout)")
    args = ap.parse_args()

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    fallback = []
    if args.fallback:
        f = json.loads(Path(args.fallback).read_text(encoding="utf-8"))
        fallback = f.get("fallback_phase_candidates", f if isinstance(f, list) else [])

    result = vote(bazi, fallback)
    out_str = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out_str, encoding="utf-8")
        print(f"[multi_school_vote] wrote {args.out} · "
              f"decision={result['decision']} consensus={result['consensus_level']} "
              f"top1={result['top1_posterior']:.2f}")
    else:
        print(out_str)


if __name__ == "__main__":
    main()
