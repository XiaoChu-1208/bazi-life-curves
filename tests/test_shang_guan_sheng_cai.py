"""v9 L1-L7 · 伤官生财格 (shang_guan_sheng_cai_geju) e2e acceptance 回归测试。

固化 references/phase_architecture_v9_design.md 4 个层次能力：
  - L1 _phase_registry: 伤官族 3 phase 注册 + trigger_branches=寅申巳亥 / 辰戌丑未
  - L3 _question_bank: D6 三题对伤官族 phase 有非均匀 likelihood
  - L5 mangpai_events: phase 锁定后, shang_guan_jian_guan / bi_jie_duo_cai 反转规则触发
  - L6 score_curves: trigger 流年 (寅申巳亥) geju 派分数显著抬升

合成测试输入:
  - 伤官生财: `戊辰 辛酉 甲寅 丁卯` (甲日, 戊偏财 + 辛正官 + 寅比劫 + 丁伤官)
  - 该干支组合每 60 年重现, 不指向任何特定个人
  - 满足:
    * 伤官见(丁) + 财见(戊) → shang_guan_sheng_cai detector 触发
    * 命局有 正官(辛) → 流年伤官见官时可触发 shang_guan_jian_guan 事件
    * 命局有 财(戊辰) → 流年比劫旺时可触发 bi_jie_duo_cai 事件
    * 寅(日支) ∈ trigger_branches=寅申巳亥
"""
from __future__ import annotations

import copy

import pytest

from solve_bazi import solve  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast]


SYNTHETIC_PILLARS = "戊辰 辛酉 甲寅 丁卯"
SYNTHETIC_GENDER = "M"
SYNTHETIC_BIRTH_YEAR = 1928  # 早期重现年份, 不指向任何特定个人


@pytest.fixture(scope="module")
def bazi_raw() -> dict:
    return solve(SYNTHETIC_PILLARS, None, SYNTHETIC_GENDER, SYNTHETIC_BIRTH_YEAR)


# ──────────────────────────────────────────────────────────
# L1: _phase_registry 注册 + 三件套
# ──────────────────────────────────────────────────────────

def test_l1_shang_guan_family_registered():
    from _phase_registry import get, exists  # type: ignore

    for pid in ("shang_guan_sheng_cai",
                "shang_guan_sheng_cai_geju",
                "shang_guan_pei_yin_geju"):
        assert exists(pid), f"伤官族 phase {pid} 未注册"
        meta = get(pid)
        assert meta.dimension == "zuogong"
        assert meta.source, f"{pid} 缺古籍出处"

    # 生财类 trigger = 寅申巳亥 (四生)
    for pid in ("shang_guan_sheng_cai", "shang_guan_sheng_cai_geju"):
        triggers = set(get(pid).zuogong_trigger_branches)
        assert {"寅", "申", "巳", "亥"}.issubset(triggers), (
            f"{pid} 缺四生 trigger: {triggers}"
        )

    # 佩印类 trigger = 辰戌丑未 (四库)
    pei_yin_triggers = set(get("shang_guan_pei_yin_geju").zuogong_trigger_branches)
    assert {"辰", "戌", "丑", "未"}.issubset(pei_yin_triggers), (
        f"shang_guan_pei_yin_geju 缺四库 trigger: {pei_yin_triggers}"
    )

    # 生财格 reversal_overrides 至少含 shang_guan_jian_guan + bi_jie_duo_cai
    rev = set(get("shang_guan_sheng_cai_geju").reversal_overrides.keys())
    assert {"shang_guan_jian_guan", "bi_jie_duo_cai"}.issubset(rev), (
        f"shang_guan_sheng_cai_geju reversal_overrides 不全: {rev}"
    )


# ──────────────────────────────────────────────────────────
# L3: D6 三题 likelihood 行
# ──────────────────────────────────────────────────────────

def test_l3_d6_likelihood_for_shang_guan_family():
    from _question_bank import D6_QUESTIONS  # type: ignore

    for q in D6_QUESTIONS:
        for pid in ("shang_guan_sheng_cai_geju", "shang_guan_pei_yin_geju"):
            row = q.likelihood_table.get(pid, {})
            assert row, f"{q.id} 缺 {pid} likelihood row"
            # 非均匀分布
            assert not all(abs(v - 0.25) < 0.01 for v in row.values()), (
                f"{q.id} {pid} likelihood 是均匀分布, 失去判别力"
            )

    # 佩印格 B 占优 (耐心经营型)
    row_pei_yin_q1 = next(
        q.likelihood_table["shang_guan_pei_yin_geju"]
        for q in D6_QUESTIONS if q.id == "D6_Q1_agency_style"
    )
    assert row_pei_yin_q1["B"] >= 0.40, (
        f"佩印格 D6_Q1 B={row_pei_yin_q1['B']:.2f} 未占优, 与'耐心经营'语义不符"
    )


# ──────────────────────────────────────────────────────────
# L5: mangpai_events 反转 (phase 锁定后)
# ──────────────────────────────────────────────────────────

def test_l5_reversal_under_shang_guan_sheng_cai_geju(bazi_raw):
    from score_curves import apply_phase_override  # type: ignore
    from mangpai_events import detect_all  # type: ignore

    b = copy.deepcopy(bazi_raw)
    apply_phase_override(b, "shang_guan_sheng_cai_geju")
    result = detect_all(b)

    ctx = result.get("phase_context_used")
    assert ctx is not None and ctx["phase_id"] == "shang_guan_sheng_cai_geju"
    assert ctx["dimension"] == "zuogong"

    events = result["events"]
    reversed_events = [
        e for e in events if "reversal" in e and e["reversal"].get("applied")
    ]
    assert len(reversed_events) >= 3, (
        f"反转事件 {len(reversed_events)} 个 < 3, L5 DSL 覆盖不足"
    )

    # 至少触发 shang_guan_jian_guan / bi_jie_duo_cai 中的一个反转
    keys_reversed = {e.get("key") for e in reversed_events}
    assert keys_reversed & {"shang_guan_jian_guan", "bi_jie_duo_cai"}, (
        f"未触发伤官族 reversal_overrides 任何 key, 实际反转 key={keys_reversed}"
    )


# ──────────────────────────────────────────────────────────
# L6: score_curves zuogong_modifier (trigger 年 geju 抬升)
# ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def score_comparison(bazi_raw):
    from score_curves import score, apply_phase_override  # type: ignore

    # baseline 显式锁 day_master_dominant —— v9.2 起 P0 派别中立通道可能让默认
    # phase 变成某个 zuogong 格，与本测试的"override 触发"比较失去基线意义。
    b0 = copy.deepcopy(bazi_raw)
    b0.pop("phase", None)
    apply_phase_override(b0, "day_master_dominant")
    out0 = score(b0, age_start=0, age_end=40)
    b1 = copy.deepcopy(bazi_raw)
    apply_phase_override(b1, "shang_guan_sheng_cai_geju")
    out1 = score(b1, age_start=0, age_end=40)
    return out0["points"], out1["points"]


def test_l6_zuogong_modifier_lifts_geju_on_si_sheng_years(score_comparison):
    """trigger zhi (寅申巳亥) 流年, geju 派分数显著抬升 (avg delta ≥ 2.0)。"""
    y0, y1 = score_comparison
    by_age0 = {p["age"]: p for p in y0}
    by_age1 = {p["age"]: p for p in y1}

    trigger_zhi = {"寅", "申", "巳", "亥"}
    trigger_ages = [a for a, p in by_age1.items() if p["ganzhi"][-1] in trigger_zhi]
    assert len(trigger_ages) >= 5, (
        f"trigger 流年样本 {len(trigger_ages)} 过少"
    )

    deltas = [
        by_age1[a]["school_scores"]["spirit"]["geju"]
        - by_age0[a]["school_scores"]["spirit"]["geju"]
        for a in trigger_ages
    ]
    avg = sum(deltas) / len(deltas)
    assert avg >= 2.0, (
        f"trigger 年 spirit geju 平均 delta={avg:.2f} < 2.0, L6 modifier 退化"
    )
