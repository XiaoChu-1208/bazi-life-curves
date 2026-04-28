#!/usr/bin/env python3
"""event_elicit.py — 事件后验收敛引擎（Stage A 版）

职责：
  在 elicit 校准结束、top1 < 0.85 时，跑一轮**事件 ask-loop**——
  问用户具体年份是否发生过明显事件，根据答案做独立 Bayesian 更新，
  把后验向「与用户真实经历最一致的 phase」收敛。

本模块只覆盖 Stage A（disjoint 年批次问）+ Bayesian 更新机制；
Stage B（重叠年事件类型区分）由 event_elicit_stage_b.py 承担（待建）。

设计契约：
  - **独立通道**：Stage A 的后验更新**不污染** elicit 阶段的 Bayesian state，
    最终会与 elicit 后验做联合分布融合（fuse_posteriors 函数）。
  - **多年批次**：每轮 ask 抛一批 disjoint 年（≥2 个），用户清单作答，
    一次更新所有 phase 的事件后验（详见 event_year_predictor.py 题面铁律）。
  - **「记不清」中性**：用户选记不清 → likelihood 比 1:1，**等于没答** —— 严禁
    把"记不清"当作弱否定 / 弱肯定（违反「不替用户记忆」铁律）。
  - **收敛阈值由调用方决定**：本模块只输出后验，三档警示（0.85/0.79/0.69）
    在 TS handler 里判定。

调用示意：
    state = init_event_state(elicit_posterior, candidate_phases)
    for round_i in range(max_rounds):
        batch = next_question_batch(state, bazi)  # → List[DisjointPick]
        if not batch:
            break  # Stage A 用尽，转 Stage B
        # ... 把 batch 渲染成 UI 题，等用户答 ...
        state = update_with_answers(state, batch, user_answers)
        if max(state.posterior.values()) >= 0.85:
            break  # 收敛
    return state
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import event_year_predictor as predictor


# 用户答案输入：
#   - str：4 选项之一（兼容老调用）
#   - dict：{"discrete": str, "free_text": str?, "summary": str?}
#     —— TS handler 调 LLM 把自述映射成 discrete 后传进来
AnswerInput = Union[str, Dict[str, Any]]


# ============================================================================
# 似然表（Stage A · 二维：phase 是否预测 × 用户答案）
# ============================================================================

# 用户答案 4 选项
ANSWER_YES = "yes"            # 是 · 那年发生了明显事件
ANSWER_PARTIAL = "partial"    # 部分 · 有些波动但谈不上大事
ANSWER_NO = "no"              # 否 · 那年比较平淡
ANSWER_DUNNO = "dunno"        # 记不清

ANSWER_CODES = (ANSWER_YES, ANSWER_PARTIAL, ANSWER_NO, ANSWER_DUNNO)

# P(answer | phase predicts event for this year)
LIKELIHOOD_PREDICTED: Dict[str, float] = {
    ANSWER_YES: 0.55,
    ANSWER_PARTIAL: 0.25,
    ANSWER_NO: 0.10,
    ANSWER_DUNNO: 0.10,
}

# P(answer | phase does NOT predict event for this year)
LIKELIHOOD_NOT_PREDICTED: Dict[str, float] = {
    ANSWER_YES: 0.20,
    ANSWER_PARTIAL: 0.20,
    ANSWER_NO: 0.50,
    ANSWER_DUNNO: 0.10,
}

# 不变量自检
for d in (LIKELIHOOD_PREDICTED, LIKELIHOOD_NOT_PREDICTED):
    s = sum(d.values())
    assert abs(s - 1.0) < 1e-9, f"likelihood 表不归一：{d} sum={s}"

# 「记不清」必须对预测/未预测都给同一概率，否则就是隐式逼用户回忆
assert (LIKELIHOOD_PREDICTED[ANSWER_DUNNO]
        == LIKELIHOOD_NOT_PREDICTED[ANSWER_DUNNO]), \
    "ANSWER_DUNNO 必须中性（两条似然相等），否则违反『不替用户记忆』铁律"


# ============================================================================
# 状态对象
# ============================================================================

@dataclass
class EventElicitState:
    """事件 ask-loop 的全程状态。

    posterior 是「事件通道独立后验」—— 不掺 elicit 通道。
    最终输出时由调用方做 fuse_posteriors(elicit_posterior, event_posterior)。
    """
    candidate_phases: List[str]
    """参与本轮事件收敛的候选 phase id（一般取 elicit 后验 top 3-5）"""

    posterior: Dict[str, float]
    """事件通道当前后验。初始 = uniform over candidates。"""

    asked_years: List[int] = field(default_factory=list)
    """已问过的所有年份（disjoint + 重叠都算），不再选。"""

    answer_log: List[Dict] = field(default_factory=list)
    """每轮答案 + 似然更新轨迹，供调试 / 解释 / 退款审计。
       每项 = {round, year, sole_phase, predicted_for, answer, posterior_after}
    """

    def top(self, k: int = 3) -> List[Tuple[str, float]]:
        return sorted(self.posterior.items(), key=lambda x: -x[1])[:k]


def init_event_state(
    elicit_posterior: Dict[str, float],
    top_k: int = 4,
) -> EventElicitState:
    """从 elicit 后验初始化事件 state。

    取 elicit top-k 个候选作为本轮事件收敛对象；其它 phase 不参与
    （它们的 elicit 后验已经低到没必要再问）。

    事件通道的初始 posterior = uniform —— 这是 Bayesian 通道独立的体现：
    elicit 给「先验入选名单」，事件通道在这名单上从零开始打票。
    """
    if not elicit_posterior:
        return EventElicitState(candidate_phases=[], posterior={})

    sorted_phases = sorted(elicit_posterior.items(), key=lambda x: -x[1])
    candidates = [pid for pid, _ in sorted_phases[:top_k]]
    if not candidates:
        return EventElicitState(candidate_phases=[], posterior={})

    p0 = 1.0 / len(candidates)
    return EventElicitState(
        candidate_phases=candidates,
        posterior={pid: p0 for pid in candidates},
    )


# ============================================================================
# 出题（调 predictor）
# ============================================================================

def next_question_batch(
    state: EventElicitState,
    bazi: Dict,
    batch_size: int = 4,
    eig_threshold: float = 0.05,
) -> List[predictor.DisjointPick]:
    """挑下一批 disjoint 年问用户。Stage A 用尽返回空列表。

    EIG 截断（避免空答）:
      若候选批次里所有 sole_phase 当前后验都 ≤ eig_threshold，
      意味着这批问下去**对任何 phase 都不会有意义的更新**——
      sole_phase 本身已经接近被否决，其它候选在这些年的预测都为 False
      所以无法互相区分。直接返回 []，让上层进 Stage B（事件类型区分）。

      eig_threshold 默认 0.05：sole_phase 后验 ≤ 5% 视为已死，再问浪费用户体力。
    """
    raw = predictor.select_disjoint_year_batch(
        state.candidate_phases,
        bazi,
        asked_years=set(state.asked_years),
        batch_size=batch_size,
    )
    if not raw:
        return []

    # EIG 截断：只保留 sole_phase 还有"活的"批次
    alive = [pk for pk in raw
             if state.posterior.get(pk.sole_phase, 0.0) > eig_threshold]
    if not alive:
        # 全死 → 视同 Stage A 用尽
        return []
    return alive


# ============================================================================
# Bayesian 更新
# ============================================================================

def _likelihood(answer: str, predicted: bool) -> float:
    """P(answer | phase 是否预测此年)"""
    if answer not in ANSWER_CODES:
        # 容错：未知答案视为「记不清」（中性）
        answer = ANSWER_DUNNO
    table = LIKELIHOOD_PREDICTED if predicted else LIKELIHOOD_NOT_PREDICTED
    return table[answer]


def _normalize(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(d.values())
    if s <= 0:
        # 退化：均分（不该出现，但保险起见）
        n = len(d) or 1
        return {k: 1.0 / n for k in d}
    return {k: v / s for k, v in d.items()}


def update_with_answers(
    state: EventElicitState,
    batch: List[predictor.DisjointPick],
    answers: Dict[int, "AnswerInput"],
) -> EventElicitState:
    """用一批答案做 Bayesian 更新。

    answers: {year: AnswerInput} —— 必须覆盖 batch 里所有年份；
             用户跳过的年应在 UI 端默认填 ANSWER_DUNNO。

    AnswerInput 兼容两种形态：
      1. 纯字符串 (ANSWER_YES / PARTIAL / NO / DUNNO) —— 兼容老调用
      2. dict: {"discrete": "...", "free_text": "...", "summary": "..."}
         - discrete: 必填，4 选项之一（已由 TS handler 调 LLM 分类好）
         - free_text: 用户原始自述（选填，存档审计 / 后续 Stage B 用）
         - summary: LLM ≤30 字摘要（选填，写进 answer_log，给 deliver 阶段
           的 LLM 当锚点用，让最终解读能引用用户原话）

    LLM 分类契约（TS handler 必须遵守）:
      - 收到用户表单 → 若 free_text 非空，先调 LLM 做分类（必须有 think_start
        SSE 事件，让前端显示「正在理解你的回答…」状态）→ 拿到 discrete code
        + summary 后再调本函数
      - 分类提示词建议：
          "下面是用户对『XX 年是否发生过明显事件』的自述：
           {free_text}
           请判断这段话最接近以下哪一类：
             yes: 明确表示发生过明显大事
             partial: 有些波动 / 不大不小 / 模糊承认
             no: 明确表示那年平淡 / 没什么事
             dunno: 表示记不清 / 不确定 / 回避
           只返回一行 JSON: {"discrete": "...", "summary": "≤30 字摘要"}"
      - LLM 调用失败 / 超时 / 解析失败 → fallback 为 ANSWER_DUNNO（中性，
        不会伤害用户后验），并在 summary 写上 "(自述解析失败)"
    """
    new_post = dict(state.posterior)
    new_log = list(state.answer_log)
    new_asked = list(state.asked_years)

    round_idx = (max(
        (entry.get("round", 0) for entry in state.answer_log), default=-1) + 1)

    for pick in batch:
        year = pick.year
        raw = answers.get(year, ANSWER_DUNNO)
        # 兼容两种形态
        if isinstance(raw, dict):
            ans = str(raw.get("discrete", ANSWER_DUNNO))
            free_text = str(raw.get("free_text", "") or "")
            summary = str(raw.get("summary", "") or "")
        else:
            ans = str(raw)
            free_text = ""
            summary = ""

        # 对每个候选 phase 乘以 likelihood
        for pid in state.candidate_phases:
            predicted_for_phase = pick.all_predictions.get(pid, False)
            new_post[pid] = new_post[pid] * _likelihood(ans, predicted_for_phase)
        new_post = _normalize(new_post)
        new_asked.append(year)
        log_entry = {
            "round": round_idx,
            "year": year,
            "sole_phase": pick.sole_phase,
            "predictions": dict(pick.all_predictions),
            "answer": ans,
            "posterior_after": dict(new_post),
        }
        if free_text:
            log_entry["free_text"] = free_text
        if summary:
            log_entry["summary"] = summary
        new_log.append(log_entry)

    return EventElicitState(
        candidate_phases=state.candidate_phases,
        posterior=new_post,
        asked_years=new_asked,
        answer_log=new_log,
    )


# ============================================================================
# 后验融合（事件通道 ⊗ elicit 通道）
# ============================================================================

def fuse_posteriors(
    elicit_posterior: Dict[str, float],
    event_state: EventElicitState,
    elicit_weight: float = 1.0,
    event_weight: float = 1.2,
) -> Dict[str, float]:
    """把 elicit 后验与事件后验做加权对数融合。

    log P_fused(p) = w_e × log P_elicit(p) + w_v × log P_event(p)
    再归一化。

    默认 elicit_weight=1.0, event_weight=1.2 —— 动力学立场:
      - 命主对性格的选择能反向改变命运 → elicit 通道（性格自述）不能被压扁
      - 事件比性格自述更"硬"（用户更难撒谎）→ 事件通道权重略高
      - 1:1.2 等价于事件占 55% / 性格占 45%
      - 此值刻意避开 1:1.5+（事件主导→宿命）和 1.2:1（性格主导→易被巧言蒙过）
      - 上线后看真实数据反馈再校准

    候选集只取 event_state.candidate_phases（其它 phase 在事件通道里没参与，
    强制它们继承 elicit 后验既不公平也无必要）。返回的字典 key 集合 =
    candidate_phases，方便 TS 端直接做 disclosure。
    """
    import math
    out: Dict[str, float] = {}
    for pid in event_state.candidate_phases:
        pe = max(elicit_posterior.get(pid, 1e-6), 1e-6)
        pv = max(event_state.posterior.get(pid, 1e-6), 1e-6)
        out[pid] = math.exp(
            elicit_weight * math.log(pe) + event_weight * math.log(pv))
    return _normalize(out)


# ============================================================================
# 收敛判定 · 三档阈值
# ============================================================================

CONFIDENCE_TIERS = {
    "high": 0.80,    # ≥ 0.80 → 干净 deliver（无警示）
    "soft": 0.70,    # ≥ 0.70 → deliver + 轻警示（"未到充分置信，请保留怀疑权"）
    "weak": 0.60,    # ≥ 0.60 → deliver + 重警示（"明显偏低，请优先信你的直觉"）
    # < 0.60 → low_confidence_offer（再答一轮 / 自由输入年份 / 退款）
    #
    # 2026-04 调整：原 0.85 / 0.79 / 0.69 太严苛，77.9% 落到"重警示"档不合理
    # （事件已证多 phase 但还是 77.9% 已经很有把握）。
    # 新档位：80/70/60 —— 80% 算高把握、70-80 轻警、60-70 重警、< 60 退款。
}


def evaluate_convergence(posterior: Dict[str, float]) -> Dict:
    """根据当前后验给出三档判断 + top1 信息。

    返回 {tier, top1, top1_p, top2, top2_p, can_deliver, warning_level}
    warning_level ∈ {"none", "soft", "weak", "refuse"}
    """
    if not posterior:
        return {"tier": "refuse", "top1": None, "top1_p": 0.0,
                "top2": None, "top2_p": 0.0,
                "can_deliver": False, "warning_level": "refuse"}

    sorted_p = sorted(posterior.items(), key=lambda x: -x[1])
    top1, top1_p = sorted_p[0]
    top2, top2_p = sorted_p[1] if len(sorted_p) > 1 else (None, 0.0)

    if top1_p >= CONFIDENCE_TIERS["high"]:
        warning = "none"
    elif top1_p >= CONFIDENCE_TIERS["soft"]:
        warning = "soft"
    elif top1_p >= CONFIDENCE_TIERS["weak"]:
        warning = "weak"
    else:
        warning = "refuse"

    return {
        "tier": warning,
        "top1": top1,
        "top1_p": top1_p,
        "top2": top2,
        "top2_p": top2_p,
        "can_deliver": warning != "refuse",
        "warning_level": warning,
    }


# ============================================================================
# CLI · 调试用
# ============================================================================

def _cli() -> None:
    import argparse
    import json as _json
    ap = argparse.ArgumentParser(description="事件 ask-loop 模拟器")
    ap.add_argument("--bazi", required=True)
    ap.add_argument("--elicit-posterior", required=True,
                    help='JSON 字符串：{"phase_id": probability, ...}')
    ap.add_argument("--rounds", type=int, default=5,
                    help="模拟轮数")
    ap.add_argument("--auto-answer", choices=ANSWER_CODES, default=None,
                    help="自动答（all batches 同一答案）·调试用")
    args = ap.parse_args()

    bazi = _json.loads(open(args.bazi, encoding="utf-8").read())
    elicit_post = _json.loads(args.elicit_posterior)
    state = init_event_state(elicit_post, top_k=4)

    print(f"\n=== 初始事件后验（uniform over top {len(state.candidate_phases)}）===")
    for pid, p in state.top(5):
        print(f"  {pid}: {p:.4f}")

    for r in range(args.rounds):
        batch = next_question_batch(state, bazi, batch_size=4)
        if not batch:
            print(f"\n=== Round {r}: Stage A 用尽 ===")
            break
        print(f"\n=== Round {r}: 抛批次（{len(batch)} 年）===")
        answers: Dict[int, str] = {}
        for pk in batch:
            ans = args.auto_answer or input(
                f"  {pk.year}（独占预测：{pk.sole_phase}）"
                f"答 [{'/'.join(ANSWER_CODES)}]: ").strip() or ANSWER_DUNNO
            answers[pk.year] = ans
        state = update_with_answers(state, batch, answers)
        print(f"  本轮后验：")
        for pid, p in state.top(5):
            print(f"    {pid}: {p:.4f}")
        verdict = evaluate_convergence(state.posterior)
        print(f"  收敛判定：top1={verdict['top1']} p={verdict['top1_p']:.3f} "
              f"tier={verdict['tier']}")
        if verdict["tier"] == "none":
            print(f"  ✓ 收敛到 high 档")
            break

    print(f"\n=== 最终后验 ===")
    for pid, p in state.top(5):
        print(f"  {pid}: {p:.4f}")
    print(f"答题轨迹（{len(state.answer_log)} 条）")


if __name__ == "__main__":
    _cli()
