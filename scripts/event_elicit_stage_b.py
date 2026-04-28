#!/usr/bin/env python3
"""event_elicit_stage_b.py — Stage B 重叠年事件类别区分（v2 · 算法版）

v2 升级：彻底去掉 Stage B 期间的 LLM 调用——出题、似然全部走
phase_event_categories.PHASE_EVENT_CATEGORIES 查表 + Jaccard 分歧分。

什么时候启用：
  Stage A（event_elicit.py · disjoint 年清单题）用尽 / EIG 截断后，
  剩下若干"多个候选 phase 都预测有事件"的重叠年。
  Stage B 任务：在这些年里挑分歧最大的一年问，让用户勾事件类别。

  分歧分公式：
    score(year) = Σ_{i<j} divergence(phase_i, phase_j; posterior_i, posterior_j)
                 (i,j ∈ 该年命中的候选 phase)
    divergence(p_i, p_j; π_i, π_j) = (1 - jaccard(cats_i, cats_j)) × π_i × π_j

LLM 在 Stage B 唯一保留的位置：
  当用户除了勾选项还填了自述时，TS handler 调一次 classifyFreeText
  把自述映射成 (discrete + summary) —— 这一步与 Stage A 共用。

退化策略：
  - 候选年里所有 phase 都没事件类别预测（如 day_master_dominant 主导
    +几个 special phase）→ Stage B 无可问年 → 转验证题或定档
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import event_year_predictor as predictor
import phase_event_categories as cat_table
from event_elicit import EventElicitState, _normalize


# ============================================================================
# 候选重叠年枚举（与 v1 相同）
# ============================================================================

@dataclass
class OverlapYearCandidate:
    """一个候选重叠年 + 在该年预测有事件的所有 phase。"""
    year: int
    user_age: int
    predicting_phases: List[str]

    def __repr__(self) -> str:
        return (f"OverlapYearCandidate(year={self.year}, "
                f"age={self.user_age}, phases={self.predicting_phases})")


def find_overlap_year_candidates(
    state: EventElicitState,
    bazi: Dict,
    max_candidates: int = 8,
    age_band: Tuple[int, int] = (5, 60),
    min_overlap: int = 1,
) -> List[OverlapYearCandidate]:
    """找候选年（≥ min_overlap 个 phase 在该年预测有事件）。

    v3 默认 min_overlap=1（旧版 2）：
      candidate_phases 里包含 baseline phase（如 day_master_dominant）时，
      它永远不在任何年的 predicting_phases 里 → 旧 min_overlap=2 会过滤掉
      大量"只有一个具体 phase 预测、baseline 不参与"的年份，导致 Stage B
      在 baseline 是 top 候选时无题可问，整轮答题白做。
      改成 1 后：单 phase 预测的年也能成为 Stage B 题——用户答 yes/no
      会让该 phase ↑ 或 ↓，baseline 走中性更新，posterior 自然位移。
    """
    if len(state.candidate_phases) < 2:
        return []

    birth_year = bazi.get("birth_year")
    if not isinstance(birth_year, int):
        return []

    age_lo, age_hi = age_band
    year_lo = birth_year + age_lo
    year_hi = birth_year + age_hi
    # 硬限：只问命主已经经历过的年份（同 Stage A）
    import time
    current_year = time.localtime().tm_year
    year_hi = min(year_hi, current_year - 1)
    if year_hi < year_lo:
        return []
    asked = set(state.asked_years)

    grid: Dict[str, Set[int]] = {}
    for pid in state.candidate_phases:
        years = {y for y, _ in predictor.predicted_event_years(pid, bazi)
                 if year_lo <= y <= year_hi and y not in asked}
        grid[pid] = years

    all_years: Set[int] = set().union(*grid.values())
    overlaps: List[OverlapYearCandidate] = []
    for year in all_years:
        hitting = [pid for pid in state.candidate_phases if year in grid[pid]]
        if len(hitting) >= min_overlap:
            overlaps.append(OverlapYearCandidate(
                year=year,
                user_age=year - birth_year,
                predicting_phases=hitting,
            ))

    def _sort_key(c: OverlapYearCandidate) -> Tuple[int, int, int]:
        primary = 0 if 18 <= c.user_age <= 45 else 1
        secondary = -len(c.predicting_phases)
        return (primary, secondary, abs(c.user_age - 30))

    overlaps.sort(key=_sort_key)
    return overlaps[:max_candidates]


# ============================================================================
# Stage B 出题 · 算法版
# ============================================================================

@dataclass
class StageBPick:
    """Stage B 选定的一道题。

    所有数据都来自 phase_event_categories 查表 —— 零 LLM。
    """
    year: int
    user_age: int
    candidate_categories: List[str]   # 题面给用户勾的类别清单
    phase_categories: Dict[str, List[str]]  # 每个候选 phase 的预测类别（用于似然）
    predicting_phases: List[str]      # **本年命中**的候选 phase（用于 likelihood 区分）
    divergence_score: float


def select_best_overlap_year(
    state: EventElicitState,
    candidates: List[OverlapYearCandidate],
) -> Optional[StageBPick]:
    """挑分歧最大的一年。

    v3：跑全候选 phase × 全候选 phase 的两两分歧（不仅是这年命中的 phase），
    把"在该年是否预测"作为分歧分的输入。这样：
      - day_master vs pseudo_following 在某年（pseudo 命中、day_master 没）
        会得到非零分歧，Stage B 不再因 baseline 在场就失效。
    """
    if not candidates:
        return None

    all_phases = list(state.candidate_phases)

    best: Optional[Tuple[float, OverlapYearCandidate]] = None
    for c in candidates:
        predicts_set = set(c.predicting_phases)
        score = 0.0
        for i in range(len(all_phases)):
            for j in range(i + 1, len(all_phases)):
                pi, pj = all_phases[i], all_phases[j]
                score += cat_table.divergence_score(
                    pi, pj,
                    state.posterior.get(pi, 0.0),
                    state.posterior.get(pj, 0.0),
                    a_predicts=pi in predicts_set,
                    b_predicts=pj in predicts_set,
                )
        if score <= 0:
            continue
        if best is None or score > best[0]:
            best = (score, c)

    if best is None:
        return None

    score, cand = best
    cats_union = cat_table.expected_categories_union(cand.predicting_phases)
    if not cats_union:
        # 命中的 phase 全没 categories（罕见，比如全是 special 结构类）
        # → 无题面可拼，跳过
        return None
    phase_cats = {pid: cat_table.categories_for_phase(pid)
                  for pid in cand.predicting_phases}
    return StageBPick(
        year=cand.year,
        user_age=cand.user_age,
        candidate_categories=cats_union,
        phase_categories=phase_cats,
        predicting_phases=list(cand.predicting_phases),
        divergence_score=score,
    )


# ============================================================================
# Bayesian 更新（用 categorical 似然查表，零 LLM）
# ============================================================================

def update_with_category_answer(
    state: EventElicitState,
    pick: StageBPick,
    discrete: str,                     # yes / partial / no / dunno
    chosen_categories: List[str],      # yes 时用户勾的类别
    free_text: str = "",
    summary: str = "",
) -> EventElicitState:
    """用用户答案 + 勾选的类别做 Bayesian 更新（categorical 似然查表）。

    类别勾选可以为空（用户只勾 discrete 没勾类别 → 视为 partial 退化）。
    """
    new_post = dict(state.posterior)
    new_log = list(state.answer_log)
    new_asked = list(state.asked_years)

    round_idx = (max(
        (entry.get("round", 0) for entry in state.answer_log), default=-1) + 1)

    log_entry: Dict[str, Any] = {
        "round": round_idx,
        "stage": "B",
        "year": pick.year,
        "candidate_categories": list(pick.candidate_categories),
        "phase_categories": dict(pick.phase_categories),
        "discrete": discrete,
        "chosen_categories": list(chosen_categories),
    }
    if free_text:
        log_entry["free_text"] = free_text
    if summary:
        log_entry["summary"] = summary

    if discrete == "dunno":
        log_entry["status"] = "dunno_neutral"
        log_entry["posterior_after"] = dict(new_post)
        new_log.append(log_entry)
        new_asked.append(pick.year)
        return EventElicitState(
            candidate_phases=state.candidate_phases,
            posterior=new_post,
            asked_years=new_asked,
            answer_log=new_log,
        )

    eps = 1e-3
    likelihoods: Dict[str, float] = {}
    predicts_set = set(pick.predicting_phases or [])
    for pid in state.candidate_phases:
        # 关键：phase 在这一年是否预测了事件 → 决定它是否参与本题更新
        # 不在 predicting_phases 里 → likelihood 0.5（中性 · 没赌过这年）
        lik = cat_table.likelihood_for_category_answer(
            pid, chosen_categories, discrete,
            phase_predicts_at_year=(pid in predicts_set),
        )
        lik = max(eps, min(1.0 - eps, lik))
        likelihoods[pid] = lik
        new_post[pid] = new_post[pid] * lik

    new_post = _normalize(new_post)
    log_entry["likelihoods"] = likelihoods
    log_entry["posterior_after"] = dict(new_post)
    new_log.append(log_entry)
    new_asked.append(pick.year)

    return EventElicitState(
        candidate_phases=state.candidate_phases,
        posterior=new_post,
        asked_years=new_asked,
        answer_log=new_log,
    )


# ============================================================================
# CLI · 调试
# ============================================================================

def _cli() -> None:
    import argparse
    import json as _json
    ap = argparse.ArgumentParser(description="Stage B 候选年枚举 + 算法挑年")
    ap.add_argument("--bazi", required=True)
    ap.add_argument("--phases", nargs="+", required=True)
    ap.add_argument("--asked", nargs="*", type=int, default=[])
    args = ap.parse_args()

    bazi = _json.loads(open(args.bazi, encoding="utf-8").read())
    n = len(args.phases)
    state = EventElicitState(
        candidate_phases=args.phases,
        posterior={p: 1.0 / n for p in args.phases},
        asked_years=args.asked,
    )
    cands = find_overlap_year_candidates(state, bazi, max_candidates=10)
    print(f"\n=== Stage B 候选重叠年（{len(cands)} 个） ===")
    for c in cands:
        print(f"  {c.year}（{c.user_age} 岁）· phases={c.predicting_phases}")

    pick = select_best_overlap_year(state, cands)
    print(f"\n=== 最分歧年 ===")
    if pick:
        print(f"  {pick.year}（{pick.user_age} 岁）· score={pick.divergence_score:.4f}")
        print(f"  题面候选类别：")
        for c in pick.candidate_categories:
            print(f"    · {c}")
        print(f"  各 phase 预测类别：")
        for pid, cats in pick.phase_categories.items():
            print(f"    {pid}: {cats}")
    else:
        print("  无 → Stage B 用尽")


if __name__ == "__main__":
    _cli()
