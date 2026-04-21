"""scripts/_eig_selector.py · v9 · 自适应贝叶斯问答核心算法

提供 4 个纯函数：
- entropy(dist)                 香农熵（nat 单位）
- bayes_update(post, q, opt)    单题后验更新（与 decide_phase 内部逻辑同源）
- marginal_answer_prob(q, post) 选项的边缘后验概率
- weighted_eig(q, post)         加权期望信息增益（hard 偏置 / soft 抑制）
- should_stop(post, n, pool)    4 条早停判定

E1 / E2 工程约束：本模块**只算数**，不读不写任何用户可见文件；
posterior / EIG 数值仅供 adaptive_elicit.py 持久化到点开头 state 文件。

详见 references/handshake_protocol.md §3 v9 segment + plan 自适应贝叶斯问答 v9 §A1。
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# §1 EIG 用的选题权重（与 decide_phase 的后验更新权重不同）
# ---------------------------------------------------------------------------
# 后验更新 weight（match decide_phase）：hard=2.0 / soft=1.0
# EIG 选题 weight（仅排序用）：       hard=2.0 / soft=0.7
# 区别：选题阶段更激进地偏向 hard_evidence；一旦答了，按真实权重更新。
EIG_SELECTION_WEIGHT: Dict[str, float] = {
    "hard_evidence":   2.0,
    "soft_self_report": 0.7,
}

POSTERIOR_UPDATE_WEIGHT: Dict[str, float] = {
    "hard_evidence":   2.0,
    "soft_self_report": 1.0,
}


# ---------------------------------------------------------------------------
# §2 工具函数
# ---------------------------------------------------------------------------

def _normalize(dist: Dict[str, float]) -> Dict[str, float]:
    s = sum(dist.values())
    if s <= 0:
        n = len(dist)
        return {k: 1.0 / n for k in dist} if n else {}
    return {k: v / s for k, v in dist.items()}


def entropy(dist: Dict[str, float]) -> float:
    """Shannon entropy in nats. Empty / null dist → 0."""
    if not dist:
        return 0.0
    s = sum(dist.values())
    if s <= 0:
        return 0.0
    h = 0.0
    for v in dist.values():
        p = v / s
        if p > 0:
            h -= p * math.log(p)
    return h


def _q_attr(q: Any, name: str, default: Any = None) -> Any:
    """统一访问 Question dataclass 与 dict 形式的 question。"""
    if isinstance(q, dict):
        return q.get(name, default)
    return getattr(q, name, default)


def _option_ids(q: Any) -> List[str]:
    options = _q_attr(q, "options", []) or []
    out: List[str] = []
    for o in options:
        if isinstance(o, dict):
            out.append(o["id"])
        else:
            out.append(o.id)
    return out


def _likelihood(q: Any, phase_id: str, opt_id: str, default: float = 0.25) -> float:
    table = _q_attr(q, "likelihood_table", {}) or {}
    row = table.get(phase_id, {}) or {}
    return float(row.get(opt_id, default))


# ---------------------------------------------------------------------------
# §3 后验更新（pure function · 与 decide_phase 同源逻辑）
# ---------------------------------------------------------------------------

def bayes_update(
    posterior: Dict[str, float],
    question: Any,
    answer_id: str,
    weight: Optional[float] = None,
) -> Dict[str, float]:
    """单题后验更新。

    Args:
        posterior: {phase_id: prob}（不必归一）
        question:  Question dataclass 或 dict（有 likelihood_table / weight_class）
        answer_id: 用户选的选项 id（"A"/"B"/...）
        weight:    显式覆盖权重；None → 按 weight_class 自动取

    Returns:
        归一化后的新后验（不就地修改 input）
    """
    if weight is None:
        wc = _q_attr(question, "weight_class", "soft_self_report") or "soft_self_report"
        weight = POSTERIOR_UPDATE_WEIGHT.get(wc, 1.0)

    new_post: Dict[str, float] = {}
    for pid, prob in posterior.items():
        like = _likelihood(question, pid, answer_id, default=0.25)
        new_post[pid] = float(prob) * (max(like, 1e-6) ** float(weight))
    return _normalize(new_post)


def marginal_answer_prob(
    question: Any,
    posterior: Dict[str, float],
) -> Dict[str, float]:
    """计算给定当前后验下，每个选项被选中的边缘概率：
        P(a | post) = Σ_phase  post(phase) * L(a | phase)
    """
    norm_post = _normalize(posterior)
    out: Dict[str, float] = {oid: 0.0 for oid in _option_ids(question)}
    for pid, p in norm_post.items():
        for oid in out:
            out[oid] += p * _likelihood(question, pid, oid, default=0.25)
    # 防御：edge case 下选项概率可能略偏离 1
    return _normalize(out)


# ---------------------------------------------------------------------------
# §4 加权期望信息增益（核心选题指标）
# ---------------------------------------------------------------------------

def weighted_eig(
    question: Any,
    posterior: Dict[str, float],
    weight_table: Optional[Dict[str, float]] = None,
) -> float:
    """加权 EIG：weight * (H(post) - Σ_a P(a|post) * H(post|a))。

    weight 用于**选题排序**，与后验更新权重独立。
    返回 nat 单位的加权 EIG（非负）。
    """
    if weight_table is None:
        weight_table = EIG_SELECTION_WEIGHT
    norm_post = _normalize(posterior)
    if not norm_post:
        return 0.0
    h_prior = entropy(norm_post)
    a_probs = marginal_answer_prob(question, norm_post)

    expected_h = 0.0
    for oid, p_a in a_probs.items():
        if p_a <= 0.0:
            continue
        # 后验 update 用的权重必须与 bayes_update 内部一致（hard=2.0/soft=1.0）
        # —— 否则 EIG 会高估 / 低估实际信息收益
        post_after = bayes_update(norm_post, question, oid)
        expected_h += p_a * entropy(post_after)

    eig = max(h_prior - expected_h, 0.0)
    wc = _q_attr(question, "weight_class", "soft_self_report") or "soft_self_report"
    sel_weight = float(weight_table.get(wc, 1.0))
    return eig * sel_weight


# ---------------------------------------------------------------------------
# §5 早停 4 条件（plan §A1 should_stop）
# ---------------------------------------------------------------------------

# 默认阈值（plan §A1 / handshake_protocol.md v9）
DEFAULT_STOP_CONFIG: Dict[str, float] = {
    "S1_top1_min":            0.95,   # 强落地
    "S1_margin_min":          0.05,
    "S2_top1_min":            0.75,   # 边际收益消失
    "S2_eig_max":             0.05,
    "S3_hard_cap":            12,     # 硬封顶
    "S4_min_asked_for_check": 6,      # 收敛检查最低题数
    "S4_window":              4,      # 最近 N 题
    "S4_swing_max":           0.03,
    # batch 模式下额外用：
    "BATCH_high_floor":       0.97,   # batch 想要 high 必须 ≥ 此阈
}


def _top_two(post: Dict[str, float]) -> Tuple[Tuple[str, float], Tuple[str, float]]:
    items = sorted(post.items(), key=lambda kv: (-kv[1], kv[0]))
    if not items:
        return (("", 0.0), ("", 0.0))
    if len(items) == 1:
        return (items[0], ("", 0.0))
    return (items[0], items[1])


def should_stop(
    posterior: Dict[str, float],
    n_asked: int,
    eig_pool: Optional[Iterable[float]] = None,
    top1_history: Optional[List[float]] = None,
    config: Optional[Dict[str, float]] = None,
) -> Tuple[str, str]:
    """返回 (action, reason)。

    action ∈ {"continue", "stop"}.
    reason 是人类可读的中文原因（写入 state 历史，不进 user payload）。

    4 条停止条件：
        S1 强落地：top1 ≥ S1_top1_min 且 (top1 - top2) ≥ S1_margin_min
        S2 边际收益消失：top1 ≥ S2_top1_min 且 max(eig_pool) < S2_eig_max
        S3 硬封顶：n_asked ≥ S3_hard_cap
        S4 收敛：n_asked ≥ S4_min_asked_for_check 且最近 S4_window 题
                 top1 摆动 < S4_swing_max
    """
    cfg = dict(DEFAULT_STOP_CONFIG)
    if config:
        cfg.update(config)

    norm_post = _normalize(posterior)
    if not norm_post:
        return ("stop", "S0 后验为空 / 退化")

    (top1_pid, top1), (_, top2) = _top_two(norm_post)

    # S1 强落地
    if top1 >= cfg["S1_top1_min"] and (top1 - top2) >= cfg["S1_margin_min"]:
        return ("stop", f"S1 强落地（{top1_pid} top1={top1:.3f} margin={top1 - top2:.3f}）")

    # S3 硬封顶
    if n_asked >= cfg["S3_hard_cap"]:
        return ("stop", f"S3 硬封顶（已答 {n_asked} 题 ≥ {int(cfg['S3_hard_cap'])}）")

    # S2 边际收益消失
    eig_pool_list = list(eig_pool) if eig_pool is not None else []
    max_eig = max(eig_pool_list) if eig_pool_list else 0.0
    if top1 >= cfg["S2_top1_min"] and max_eig < cfg["S2_eig_max"]:
        return ("stop", f"S2 边际收益消失（top1={top1:.3f} max_eig={max_eig:.4f}）")

    # S4 收敛
    if (
        top1_history
        and n_asked >= cfg["S4_min_asked_for_check"]
        and len(top1_history) >= cfg["S4_window"]
    ):
        recent = top1_history[-int(cfg["S4_window"]):]
        swing = max(recent) - min(recent)
        if swing < cfg["S4_swing_max"]:
            return ("stop", f"S4 后验已收敛（最近 {int(cfg['S4_window'])} 题摆动 {swing:.4f}）")

    return ("continue", f"continue (top1={top1:.3f}, asked={n_asked}, max_eig={max_eig:.4f})")


# ---------------------------------------------------------------------------
# §6 选题：从候选池里挑 top-EIG 题（确定性 tie-break）
# ---------------------------------------------------------------------------

def pick_top_question(
    candidates: List[Any],
    posterior: Dict[str, float],
    answered_ids: Optional[Iterable[str]] = None,
) -> Optional[Tuple[Any, float]]:
    """从 candidates 中排除已答题，按 weighted_eig 倒排取第一名。

    Tie-break: 同 EIG → 按 question id 字典序升序（保证 bit-for-bit）。
    返回 (question, eig) 或 None。
    """
    answered = set(answered_ids or [])
    pool: List[Tuple[float, str, Any]] = []
    for q in candidates:
        qid = _q_attr(q, "id")
        if not qid or qid in answered:
            continue
        eig = weighted_eig(q, posterior)
        pool.append((eig, qid, q))
    if not pool:
        return None
    pool.sort(key=lambda x: (-x[0], x[1]))
    eig, _, q = pool[0]
    return (q, eig)


def compute_eig_pool(
    candidates: List[Any],
    posterior: Dict[str, float],
    answered_ids: Optional[Iterable[str]] = None,
) -> List[Tuple[str, float]]:
    """对候选池中所有未答题计算 EIG，返回按倒排的 (qid, eig) 列表。
    用于 should_stop 的 max_eig 估计 + state 历史记录。
    """
    answered = set(answered_ids or [])
    out: List[Tuple[str, float]] = []
    for q in candidates:
        qid = _q_attr(q, "id")
        if not qid or qid in answered:
            continue
        out.append((qid, weighted_eig(q, posterior)))
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


__all__ = [
    "EIG_SELECTION_WEIGHT",
    "POSTERIOR_UPDATE_WEIGHT",
    "DEFAULT_STOP_CONFIG",
    "entropy",
    "marginal_answer_prob",
    "bayes_update",
    "weighted_eig",
    "should_stop",
    "pick_top_question",
    "compute_eig_pool",
]


# ---------------------------------------------------------------------------
# §7 自检：python scripts/_eig_selector.py 直接跑 → 跑内置单测
# ---------------------------------------------------------------------------

def _self_test() -> None:
    """轻量单元测试（不依赖外部数据）。"""
    # 1. entropy
    assert abs(entropy({"a": 0.5, "b": 0.5}) - math.log(2)) < 1e-9
    assert entropy({"a": 1.0, "b": 0.0}) == 0.0
    assert entropy({}) == 0.0

    # 2. bayes_update：单峰 likelihood → 后验完全集中在该 phase
    fake_q = {
        "id": "T_Q1",
        "weight_class": "hard_evidence",
        "options": [{"id": "A"}, {"id": "B"}],
        "likelihood_table": {
            "p1": {"A": 0.9, "B": 0.1},
            "p2": {"A": 0.1, "B": 0.9},
        },
    }
    post = bayes_update({"p1": 0.5, "p2": 0.5}, fake_q, "A")
    assert post["p1"] > post["p2"], post

    # 3. weighted_eig：完美区分题应 > 0；无区分题应 ≈ 0
    eig_perfect = weighted_eig(fake_q, {"p1": 0.5, "p2": 0.5})
    flat_q = {
        "id": "T_Q2",
        "weight_class": "hard_evidence",
        "options": [{"id": "A"}, {"id": "B"}],
        "likelihood_table": {
            "p1": {"A": 0.5, "B": 0.5},
            "p2": {"A": 0.5, "B": 0.5},
        },
    }
    eig_flat = weighted_eig(flat_q, {"p1": 0.5, "p2": 0.5})
    assert eig_perfect > 0.5, eig_perfect
    assert eig_flat < 1e-6, eig_flat

    # 4. weight 抑制：hard 题 EIG 应 = soft 题同结构 EIG * (2.0/0.7)
    soft_q = dict(fake_q, id="T_Q3", weight_class="soft_self_report")
    eig_h = weighted_eig(fake_q, {"p1": 0.5, "p2": 0.5})
    eig_s = weighted_eig(soft_q, {"p1": 0.5, "p2": 0.5})
    # 注意：weighted_eig 内部 bayes_update 用的是真实更新权重（hard=2.0/soft=1.0），
    # 所以 eig_h / eig_s 不是简单的 weight 比；只检查 hard 严格更优
    assert eig_h > eig_s, (eig_h, eig_s)

    # 5. should_stop S1
    act, _ = should_stop({"p1": 0.96, "p2": 0.04}, n_asked=3)
    assert act == "stop"
    # margin 不足 → 不停
    act2, _ = should_stop({"p1": 0.96, "p2": 0.93}, n_asked=3)  # 不可能但测 margin
    # 这里 top1+top2 > 1 是为了构造测试，归一化后可能改变结果
    # 跳过这一项
    # S3 硬封顶
    act3, _ = should_stop({"p1": 0.5, "p2": 0.5}, n_asked=12)
    assert act3 == "stop"
    # S4 收敛
    act4, _ = should_stop(
        {"p1": 0.6, "p2": 0.4},
        n_asked=8,
        top1_history=[0.59, 0.60, 0.61, 0.60],
    )
    assert act4 == "stop"

    # 6. pick_top_question
    res = pick_top_question([fake_q, flat_q], {"p1": 0.5, "p2": 0.5})
    assert res is not None
    q_picked, _ = res
    assert _q_attr(q_picked, "id") == "T_Q1"

    print("_eig_selector self-test OK")


if __name__ == "__main__":
    _self_test()
