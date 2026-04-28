#!/usr/bin/env python3
"""event_verification.py — 事件后验收敛的最终验证题

什么时候启用：
  Stage A + Stage B 跑完，融合后验 top1 已 ≥ 0.85（或人为指定）。
  抛 1 道**透明的复核题**：
    "本系统判定你这盘是 X，X 通常会让命主在 YYYY 年经历 Z。
     如果命中 → 把握度上拉到 ≥ 0.92；如果落空 → 触发回退重判。"

设计契约：
  - **透明告知**：题面**显式说**这是验证题、说出当前判定的 phase 名、
    说明命中/落空的后果。这与「命理师之道」§II「判错时要诚实」对齐。
  - **强独占年**：选 top1 phase 预测最强、其它候选完全沉默的年份。
  - **likelihood 不对称**：命中 → 后验大幅放大（top1 × 5）；落空 → 大幅缩小
    （top1 × 0.2）；记不清 / 部分 → 中性。

LLM 调用契约：
  Step V-1（生成题面）:
    给定: top1 phase + 选定年 + bazi 摘要
    要 LLM 输出 ≤80 字题面，开头明确说"复核题"。
    建议 system prompt:
      "你是命理算法的复核题生成器。需要写一道**透明的验证题**：
       告知用户当前判定 + 提出在某具体年的强预测 + 用户答是/否会引发的后果。
       要求：≤80 字 / 不带 emoji / 不命名 phase 内部 id（用中文名） /
       不要恭维或威胁性话术。"

  Step V-2（用户答完）:
    无需 LLM —— 答案直接走预定义 likelihood 表更新。

退化策略：
  - 找不到强独占年 → 不抛验证题，直接按融合后验进 deliver（带原警示档）
  - LLM 题面生成失败 → 用 fallback 模板拼一句话题面，仍可继续
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import event_year_predictor as predictor
from event_elicit import EventElicitState, _normalize


@dataclass
class VerificationPick:
    """验证题候选。"""
    year: int
    user_age: int
    top1_phase: str
    top1_phase_label: str       # 中文名（题面用）
    other_phases_silent: List[str]  # 在该年完全沉默的其它候选


def find_verification_year(
    state: EventElicitState,
    bazi: Dict,
    top1_phase: str,
    top1_phase_label: str,
    age_band: Tuple[int, int] = (16, 50),
) -> Optional[VerificationPick]:
    """挑一个 top1 强预测、其它候选都沉默的年份做验证题。

    逻辑：
      - 把 top1 的预测年集 - 其它任何候选的预测年集 = 强独占
      - 优先选已经发生过的年（若用户尚未到达该年龄，验证题没用）
      - 在已发生年里，按"用户最有印象"排序
    """
    if top1_phase not in state.candidate_phases:
        return None

    birth_year = bazi.get("birth_year")
    if not isinstance(birth_year, int):
        return None

    age_lo, age_hi = age_band
    year_lo = birth_year + age_lo
    year_hi = birth_year + age_hi

    # 当前公历年估算（本地年）
    import time
    current_year = time.localtime().tm_year
    year_hi = min(year_hi, current_year - 1)  # 验证题只能问已发生年
    if year_hi < year_lo:
        return None

    asked = set(state.asked_years)

    # top1 的预测年
    top1_years = {y for y, _ in predictor.predicted_event_years(top1_phase, bazi)
                  if year_lo <= y <= year_hi and y not in asked}

    # 其它候选 phase 的预测年并集
    other_years: set = set()
    for pid in state.candidate_phases:
        if pid == top1_phase:
            continue
        for y, _ in predictor.predicted_event_years(pid, bazi):
            if year_lo <= y <= year_hi:
                other_years.add(y)

    # 强独占年 = top1 命中 - 其它任意候选命中
    strong_solo = sorted(top1_years - other_years)
    if not strong_solo:
        return None

    # 选用户最有印象的一年（中年优先 + 近期优先）
    def _sort_key(y: int) -> Tuple[int, int]:
        age = y - birth_year
        primary = 0 if 22 <= age <= 42 else 1
        # 同档按距 28 岁排
        return (primary, abs(age - 28))

    strong_solo.sort(key=_sort_key)
    pick_year = strong_solo[0]
    silent = [pid for pid in state.candidate_phases if pid != top1_phase]
    return VerificationPick(
        year=pick_year,
        user_age=pick_year - birth_year,
        top1_phase=top1_phase,
        top1_phase_label=top1_phase_label,
        other_phases_silent=silent,
    )


# ============================================================================
# Likelihood 表（验证题专用）
#
# 不对称设计的依据：
#   - 命中 → 强证据，应让 top1 后验放大很多（× 5 → 后验从 0.85 → ~0.97）
#   - 落空 → 强反证，应让 top1 后验缩很多（× 0.2 → 后验从 0.85 → ~0.51）
#   - 部分 / 记不清 → 中性，不更新（用户不愿确认就别强迫）
# ============================================================================

VERIFICATION_LIKELIHOOD_HIT_TOP1 = 5.0
VERIFICATION_LIKELIHOOD_HIT_OTHERS = 0.5
VERIFICATION_LIKELIHOOD_MISS_TOP1 = 0.2
VERIFICATION_LIKELIHOOD_MISS_OTHERS = 1.5
VERIFICATION_LIKELIHOOD_NEUTRAL = 1.0  # part / dunno → 不动


def update_with_verification(
    state: EventElicitState,
    pick: VerificationPick,
    user_answer: str,
) -> EventElicitState:
    """用验证题答案更新后验。

    user_answer ∈ {"yes", "partial", "no", "dunno"}
    """
    new_post = dict(state.posterior)
    new_log = list(state.answer_log)
    new_asked = list(state.asked_years)

    round_idx = (max(
        (entry.get("round", 0) for entry in state.answer_log), default=-1) + 1)

    if user_answer == "yes":
        for pid in state.candidate_phases:
            if pid == pick.top1_phase:
                new_post[pid] = new_post[pid] * VERIFICATION_LIKELIHOOD_HIT_TOP1
            else:
                new_post[pid] = new_post[pid] * VERIFICATION_LIKELIHOOD_HIT_OTHERS
    elif user_answer == "no":
        for pid in state.candidate_phases:
            if pid == pick.top1_phase:
                new_post[pid] = new_post[pid] * VERIFICATION_LIKELIHOOD_MISS_TOP1
            else:
                new_post[pid] = new_post[pid] * VERIFICATION_LIKELIHOOD_MISS_OTHERS
    # partial / dunno → 不动

    new_post = _normalize(new_post)
    new_asked.append(pick.year)
    new_log.append({
        "round": round_idx,
        "stage": "V",
        "year": pick.year,
        "top1_phase": pick.top1_phase,
        "answer": user_answer,
        "posterior_after": dict(new_post),
    })

    return EventElicitState(
        candidate_phases=state.candidate_phases,
        posterior=new_post,
        asked_years=new_asked,
        answer_log=new_log,
    )


# ============================================================================
# 题面 fallback 模板（LLM 失败时用）
# ============================================================================

def fallback_question_text(pick: VerificationPick) -> str:
    """LLM 题面生成失败时的兜底句子。

    保持「命理师之道」的透明承诺：
      - 显式说"复核题"
      - 说出 phase 中文名
      - 不下定论 / 不预测未来
    """
    return (
        f"复核题 · 当前判定：{pick.top1_phase_label}。"
        f"按这一判定，你在 {pick.year} 年（{pick.user_age} 岁）"
        f"应当经历过一件比较明显的、与「{pick.top1_phase_label}」相关的事件。"
        f"如果命中，把握度会拉到 0.92+；如果完全落空，我们会回头重判。"
    )


# ============================================================================
# CLI · 调试
# ============================================================================

def _cli() -> None:
    import argparse
    import json as _json
    ap = argparse.ArgumentParser(description="验证题候选选择")
    ap.add_argument("--bazi", required=True)
    ap.add_argument("--phases", nargs="+", required=True)
    ap.add_argument("--top1", required=True, help="当前 top1 phase id")
    ap.add_argument("--top1-label", default="（待定）",
                    help="top1 phase 中文名")
    args = ap.parse_args()

    bazi = _json.loads(open(args.bazi, encoding="utf-8").read())
    n = len(args.phases)
    state = EventElicitState(
        candidate_phases=args.phases,
        posterior={p: 1.0 / n for p in args.phases},
    )
    pick = find_verification_year(state, bazi, args.top1, args.top1_label)
    if pick:
        print(f"\n=== 验证题候选 ===")
        print(f"  年份: {pick.year}（{pick.user_age} 岁）")
        print(f"  top1: {pick.top1_phase} / {pick.top1_phase_label}")
        print(f"  沉默其它候选: {pick.other_phases_silent}")
        print(f"\n  fallback 题面: {fallback_question_text(pick)}")
    else:
        print("没找到强独占年 → 跳过验证题，按融合后验进 deliver")


if __name__ == "__main__":
    _cli()
