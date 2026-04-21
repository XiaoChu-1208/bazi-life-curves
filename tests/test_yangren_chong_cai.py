"""v9 L1-L7 · 刃冲财做功格 (yangren_chong_cai) e2e acceptance 回归测试。

本测试固化 references/phase_architecture_v9_design.md 所承诺的 7 层能力，
任一 layer 回退都会被本文件拦住。

合成测试输入: 丙子 丙申 壬午 乙巳 (pillars 模式, birth_year=1936)
   - 该干支组合每 60 年重复出现一次, 不指向任何特定个人
   - 满足 yangren_chong_cai detector 全部触发条件:
     * 阳干日主 (壬日)
     * 命局有阳刃 (午, 在日支)
     * 命局有财星 (丙火, 在年/月柱)
     * 阳刃支(午)与财根(子)构成六冲
     * 日主有根 (申金印 + 子水比劫)

v8.1 已知缺陷: phase_posterior 候选池只有 14 个 core phase (全部 power 视角),
yangren_chong_cai 根本不会出现在 prior_distribution, 导致 R1 直接 reject.
本测试集就是为了拦住这种"做功视角被系统性忽略"的回退。

v9 修复 (7 层):
  - L1 _phase_registry: 统一 54 个 phase 的 metadata
  - L2 rare_phase_detector 接入 prior (P7_zuogong_aggregator)
  - L3 D6 做功视角 3 题 + likelihood_table
  - L4 phase_posterior R3 降级路径 (低 R1 置信 + 强 zuogong 候选)
  - L5 mangpai_events 反转 DSL (做功格翻转 yangren_chong/bi_jie_duo_cai polarity)
  - L6 score_curves zuogong_modifier (trigger 年 geju 派上浮)
  - L7 save_confirmed_facts phase_full_override (用户显式锁定)
"""
from __future__ import annotations

import copy

import pytest

# tests/conftest.py 已注入 scripts/ 到 sys.path
from solve_bazi import solve  # type: ignore  # noqa: E402
from _bazi_core import decide_phase  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast]


# 合成 fixture: pillars 模式, 不带具体公历日/经度/时分, 不指向任何特定个人
SYNTHETIC_PILLARS = "丙子 丙申 壬午 乙巳"
SYNTHETIC_GENDER = "F"
SYNTHETIC_BIRTH_YEAR = 1936  # 该干支组合早期重现年份, 与近现代任何已知人物均无关联


@pytest.fixture(scope="module")
def bazi_raw() -> dict:
    return solve(SYNTHETIC_PILLARS, None, SYNTHETIC_GENDER, SYNTHETIC_BIRTH_YEAR)


# ──────────────────────────────────────────────────────────
# L1: _phase_registry 基础承诺
# ──────────────────────────────────────────────────────────

def test_l1_phase_registry_has_yangren_chong_cai():
    from _phase_registry import get, exists, all_ids  # type: ignore

    assert exists("yangren_chong_cai")
    meta = get("yangren_chong_cai")
    assert meta.dimension == "zuogong"
    assert "mangpai" in meta.school
    assert "盲派" in meta.source
    # trigger branches 覆盖 子/午/卯/酉 (刃应期四仲)
    assert set(("子", "午", "卯", "酉")).issubset(set(meta.zuogong_trigger_branches))
    # 反转 overrides 至少包括 yangren_chong/bi_jie_duo_cai/fuyin_yingqi/fanyin_yingqi
    keys = set(meta.reversal_overrides.keys())
    assert {"yangren_chong", "bi_jie_duo_cai"}.issubset(keys)
    # all_ids 至少 50+ (14 v8 core + 5 zuogong + 其他 rare)
    assert len(all_ids()) >= 50


def test_l1_zuogong_dimension_phases_registered():
    """除 yangren_chong_cai 外, registry 应至少注册其它 4+ 个 zuogong phase,
    确保架构对'做功体系'是面向族群的、非过拟合到单 case。"""
    from _phase_registry import all_ids, get  # type: ignore

    zuogong_ids = [pid for pid in all_ids() if get(pid).dimension == "zuogong"]
    assert len(zuogong_ids) >= 5, (
        f"zuogong 维度 phase 数 {len(zuogong_ids)} 过少, 做功体系覆盖不足: {zuogong_ids}"
    )
    # 必须包含的 8 个代表 phase（覆盖刃 / 伤官 / 杀印 / 食制 / 通明白清 五大族）
    # v9.1 扩展防止族群覆盖被回退
    must_have = {
        "yangren_chong_cai",          # 刃做功族
        "yang_ren_jia_sha",           # 刃做功族
        "shang_guan_sheng_cai",       # 伤官生财族
        "shang_guan_pei_yin_geju",    # 伤官佩印族
        "sha_yin_xiang_sheng_geju",   # 杀印族
        "shi_shen_zhi_sha_geju",      # 食制杀
        "mu_huo_tong_ming",           # 木火通明
        "jin_bai_shui_qing",          # 金白水清
    }
    missing = must_have - set(zuogong_ids)
    assert not missing, f"以下经典做功格未注册到 registry: {missing}"


# ──────────────────────────────────────────────────────────
# L2: rare-phase 接入 prior
# ──────────────────────────────────────────────────────────

def test_l2_yangren_chong_cai_in_prior_distribution(bazi_raw):
    pd = decide_phase(bazi_raw)
    prior = pd.get("prior_distribution", {})
    assert "yangren_chong_cai" in prior, (
        f"yangren_chong_cai 未进入 prior_distribution (L2 退化); "
        f"top5: {sorted(prior.items(), key=lambda x: -x[1])[:5]}"
    )
    p = prior["yangren_chong_cai"]
    assert p >= 0.20, (
        f"yangren_chong_cai prior={p:.3f} 过低 (期望 ≥ 0.20); "
        f"说明 P7_zuogong_aggregator 权重或 detector 命中强度退化"
    )


def test_l2_day_master_dominant_still_top1_without_d6(bazi_raw):
    """无 D6 证据时, day_master_dominant 仍应 top1 (fairness: 做功格不可无凭据强推)。"""
    pd = decide_phase(bazi_raw)
    posterior = pd.get("posterior_distribution", {})
    top = max(posterior.items(), key=lambda x: x[1])
    assert top[0] == "day_master_dominant", (
        f"无 D6 答案时 top1 应为 day_master_dominant, 实际为 {top[0]} (置信 {top[1]:.3f})"
    )


# ──────────────────────────────────────────────────────────
# L3 + L4: D6 做功视角题 + R3 置信降级路径
# ──────────────────────────────────────────────────────────

def test_l3_l4_r3_with_d6_aaa_elects_yangren_chong_cai(bazi_raw):
    """合成案例对 D6_Q1/Q2/Q3 均选 A (主动/剧烈/关键决策) 后, top1 锁定 yangren_chong_cai。"""
    answers = {
        "D6_Q1_agency_style": "A",
        "D6_Q2_life_rhythm": "A",
        "D6_Q3_gains_source": "A",
    }
    pd = decide_phase(bazi_raw, user_answers=answers)
    posterior = pd.get("posterior_distribution", {})
    top = max(posterior.items(), key=lambda x: x[1])
    assert top[0] == "yangren_chong_cai", (
        f"D6 全 A 后 top1 应为 yangren_chong_cai, 实际为 {top[0]}; "
        f"top5: {sorted(posterior.items(), key=lambda x: -x[1])[:5]}"
    )
    assert top[1] >= 0.60, (
        f"D6 全 A 后 yangren_chong_cai posterior={top[1]:.3f} 过低 (期望 ≥ 0.60)"
    )


def test_l3_d6_questions_registered_in_bank():
    """D6 三题必须在 STATIC_QUESTIONS 中存在且对至少 4 个 zuogong phase 有判别力。"""
    from _question_bank import STATIC_QUESTIONS  # type: ignore

    ids = {q.id for q in STATIC_QUESTIONS}
    for qid in ("D6_Q1_agency_style", "D6_Q2_life_rhythm", "D6_Q3_gains_source"):
        assert qid in ids, f"D6 问题 {qid} 未注册到 STATIC_QUESTIONS"

    d6 = [q for q in STATIC_QUESTIONS if q.id.startswith("D6_")]
    # 通用性 guard: 每题 likelihood_table 至少对 4 个不同 zuogong phase 有非均匀分布
    for q in d6:
        non_uniform_zuogong = []
        for pid in ("yangren_chong_cai", "yang_ren_jia_sha", "riren_ge", "shang_guan_sheng_cai"):
            row = q.likelihood_table.get(pid, {})
            if row and not all(abs(v - 0.25) < 0.01 for v in row.values()):
                non_uniform_zuogong.append(pid)
        assert len(non_uniform_zuogong) >= 4, (
            f"{q.id} 仅对 {len(non_uniform_zuogong)}/4 经典做功格有判别 likelihood, "
            f"过拟合嫌疑 (做功视角应是族群化判别, 非单 phase): {non_uniform_zuogong}"
        )


# ──────────────────────────────────────────────────────────
# L5: mangpai_events 反转 DSL
# ──────────────────────────────────────────────────────────

def test_l5_mangpai_reversal_triggered_under_yangren_chong_cai(bazi_raw):
    """phase=yangren_chong_cai 锁定后, 应有批量 mangpai 事件被反转 DSL 改写。"""
    from score_curves import apply_phase_override  # type: ignore
    from mangpai_events import detect_all  # type: ignore

    b = copy.deepcopy(bazi_raw)
    apply_phase_override(b, "yangren_chong_cai")
    result = detect_all(b)

    ctx_used = result.get("phase_context_used")
    assert ctx_used is not None, "phase_context_used 缺失: L5 detect_all 未识别做功格"
    assert ctx_used["phase_id"] == "yangren_chong_cai"
    assert ctx_used["dimension"] == "zuogong"

    events = result["events"]
    reversed_events = [e for e in events if "reversal" in e and e["reversal"].get("applied")]
    assert len(reversed_events) >= 10, (
        f"反转事件数 {len(reversed_events)} 过少 (期望 ≥ 10), L5 DSL 可能覆盖不全"
    )

    # 关键反转 1: yangren_chong → polarity_after=positive (任意年份, 不绑特定流年以避隐私)
    yc_positive = [
        e for e in events
        if e.get("key") == "yangren_chong"
        and e.get("reversal", {}).get("applied")
        and e["reversal"].get("polarity_after") == "positive"
    ]
    assert yc_positive, (
        "未发现任何 'yangren_chong-polarity=positive' 反转; "
        "违反盲派口诀'刃做功变通'"
    )

    # 关键反转 2: bi_jie_duo_cai → polarity_after=neutral
    bj_neutral = [
        e for e in events
        if e.get("key") == "bi_jie_duo_cai"
        and e.get("reversal", {}).get("applied")
        and e["reversal"].get("polarity_after") == "neutral"
    ]
    assert bj_neutral, (
        "未发现 bi_jie_duo_cai 任何年份反转 neutral; 印护比劫口诀失效"
    )


def test_l5_no_reversal_when_phase_not_zuogong(bazi_raw):
    """bit-for-bit 保护: phase=day_master_dominant 时 detect_all 不应走反转路径。"""
    from mangpai_events import detect_all  # type: ignore

    b = copy.deepcopy(bazi_raw)
    # 默认 phase 是 day_master_dominant (solve_bazi 已算出来)
    assert b.get("phase", {}).get("id", "day_master_dominant") == "day_master_dominant"
    result = detect_all(b)
    assert "phase_context_used" not in result, (
        "默认 phase 下 detect_all 也生成了 phase_context_used → 破坏 v8.1 bit-for-bit"
    )
    reversed_events = [e for e in result["events"] if "reversal" in e]
    assert reversed_events == [], (
        f"默认 phase 下不应有任何 reversal 字段, 实际 {len(reversed_events)} 个事件带 reversal"
    )


# ──────────────────────────────────────────────────────────
# L6: score_curves zuogong_modifier
# ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def score_comparison(bazi_raw):
    """跑两次 score: baseline vs yangren_chong_cai override, 返回 (y0, y1)。"""
    from score_curves import score, apply_phase_override  # type: ignore

    b0 = copy.deepcopy(bazi_raw)
    out0 = score(b0, age_start=0, age_end=40)
    b1 = copy.deepcopy(bazi_raw)
    apply_phase_override(b1, "yangren_chong_cai")
    out1 = score(b1, age_start=0, age_end=40)
    return out0["points"], out1["points"]


def test_l6_zuogong_modifier_lifts_geju_on_trigger_years(score_comparison):
    """trigger zhi (子/午/卯/酉) 流年, geju 派分数应比 baseline 显著抬升。

    用集合化判断, 不绑定具体流年/年龄, 避免泄露任何具体生辰锚点。
    """
    y0, y1 = score_comparison
    by_age0 = {p["age"]: p for p in y0}
    by_age1 = {p["age"]: p for p in y1}

    trigger_zhi = {"子", "午", "卯", "酉"}
    trigger_ages = [a for a, p in by_age1.items() if p["ganzhi"][-1] in trigger_zhi]
    nontrigger_ages = [a for a, p in by_age1.items() if p["ganzhi"][-1] not in trigger_zhi]

    assert len(trigger_ages) >= 5, "trigger zhi 流年样本太少, 测试代表性不够"

    # trigger 年: spirit geju delta 平均 ≥ 3.0
    deltas_trigger = []
    for age in trigger_ages:
        s0 = by_age0[age]["school_scores"]
        s1 = by_age1[age]["school_scores"]
        deltas_trigger.append(s1["spirit"]["geju"] - s0["spirit"]["geju"])
    avg_trigger = sum(deltas_trigger) / len(deltas_trigger)
    assert avg_trigger >= 3.0, (
        f"trigger 年 spirit geju 平均 delta={avg_trigger:.2f} 不足 3.0, L6 modifier 退化"
    )

    # 非 trigger 年: spirit geju delta 平均 < trigger 年水平
    if nontrigger_ages:
        deltas_nontrigger = []
        for age in nontrigger_ages:
            s0 = by_age0[age]["school_scores"]
            s1 = by_age1[age]["school_scores"]
            deltas_nontrigger.append(s1["spirit"]["geju"] - s0["spirit"]["geju"])
        avg_non = sum(deltas_nontrigger) / len(deltas_nontrigger)
        assert avg_non < avg_trigger, (
            f"非 trigger 年 spirit geju 平均 delta={avg_non:.2f} ≥ trigger 年 {avg_trigger:.2f}, "
            f"zuogong_modifier 触发条件可能失控"
        )


# ──────────────────────────────────────────────────────────
# L7: phase_full_override 落地
# ──────────────────────────────────────────────────────────

def test_l7_phase_full_override_via_structural_corrections(bazi_raw):
    """模拟 save_confirmed_facts 产出的 phase_full_override 结构能被 score 正确消费。"""
    from score_curves import apply_structural_corrections  # type: ignore

    confirmed_facts = {
        "structural_corrections": [
            {
                "kind": "phase_full_override",
                "before": "day_master_dominant",
                "after": "yangren_chong_cai",
                "reason": "test fixture",
            }
        ]
    }
    b = copy.deepcopy(bazi_raw)
    b_out, sc_applied = apply_structural_corrections(b, confirmed_facts)
    assert b_out["phase"]["id"] == "yangren_chong_cai"
    pd = b_out["phase_decision"]
    assert pd["decision"] == "yangren_chong_cai"
    assert pd.get("decision_probability") == 1.0
    assert pd.get("confidence") == "user_locked"
    assert pd.get("is_provisional") is False
    assert pd.get("lock_source") == "confirmed_facts.phase_full_override"
    assert any(
        s.get("kind") == "phase_full_override" and s.get("after") == "yangren_chong_cai"
        for s in sc_applied
    )


# ──────────────────────────────────────────────────────────
# 确定性 guard
# ──────────────────────────────────────────────────────────

def test_determinism_yangren_chong_cai_with_d6_answers(bazi_raw):
    import hashlib
    import json as _json

    answers = {
        "D6_Q1_agency_style": "A",
        "D6_Q2_life_rhythm": "A",
        "D6_Q3_gains_source": "A",
    }
    hashes = set()
    for _ in range(30):
        pd = decide_phase(bazi_raw, user_answers=answers)
        h = hashlib.sha256(
            _json.dumps(pd, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        hashes.add(h)
    assert len(hashes) == 1, (
        f"D6+zuogong 路径上 decide_phase 非确定 (30 次出现 {len(hashes)} 个 hash)"
    )
