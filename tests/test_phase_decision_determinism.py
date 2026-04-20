"""v8 · phase_decision determinism + gender symmetry tests.

详见:
- references/phase_decision_protocol.md §11 (bit-for-bit determinism)
- references/fairness_protocol.md §5 / §9-§10 (性别对称承诺)

两条核心承诺:
1. 同一份 bazi_dict 反复跑 decide_phase, 序列化后必须 byte-equal
2. 同一份八字翻转性别 (M ↔ F), phase_decision.decision 必须保持一致 ——
   spirit/wealth/fame 三派与性别无关; 只有 emotion 通道允许性别影响。
"""
from __future__ import annotations

import hashlib
import json

import pytest

# tests/conftest.py 已经把 scripts/ 注入 sys.path
from _bazi_core import decide_phase  # type: ignore  # noqa: E402
from solve_bazi import solve  # type: ignore  # noqa: E402

pytestmark = [pytest.mark.fast, pytest.mark.fairness]


# 覆盖不同 phase 触发路径的金标准八字
# - cong_cai 候选 (己土日主、财官旺、climate 偏寒)
# - calibration dataset 中的 jobs / einstein (默认相位 / 多 detector 触发)
TEST_CASES = [
    ("cong_cai_candidate", "丙子 庚子 己卯 己巳", "F", 1996),
    ("jobs_steve",         "乙未 戊寅 甲戌 甲戌", "M", 1955),
    ("einstein",           "己卯 丁卯 庚午 壬午", "M", 1879),
    ("guan_yin_xiang_sheng", "壬戌 癸丑 庚午 丁丑", "F", 1982),
]


def _phase_decision_hash(pd: dict) -> str:
    """phase_decision dict → sha256 (key 排序 + 中文不转义)。"""
    return hashlib.sha256(
        json.dumps(pd, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    "case_id,pillars,gender,birth_year",
    TEST_CASES,
    ids=[c[0] for c in TEST_CASES],
)
def test_decide_phase_bit_for_bit_determinism(case_id, pillars, gender, birth_year):
    """同输入跑 100 次, phase_decision 序列化 sha256 必须完全一致。"""
    bazi = solve(pillars, None, gender, birth_year)
    hashes = set()
    for _ in range(100):
        pd = decide_phase(bazi)
        hashes.add(_phase_decision_hash(pd))
    assert len(hashes) == 1, (
        f"\n  {case_id}: phase_decision 不确定 (100 次出现 {len(hashes)} 个不同 hash)\n"
        f"  违反 phase_decision_protocol §11 bit-for-bit determinism 铁律。"
    )


@pytest.mark.parametrize(
    "case_id,pillars,birth_year",
    [(c[0], c[1], c[3]) for c in TEST_CASES],
    ids=[c[0] for c in TEST_CASES],
)
def test_phase_decision_gender_symmetry(case_id, pillars, birth_year):
    """性别 F → M 翻转后, phase_decision 关键字段必须保持一致。

    fairness §9 承诺: spirit/wealth/fame 三派与性别无关; emotion 通道允许性别影响。
    phase_decision 是 spirit/wealth/fame 的根基决策, 必须性别无关。

    注: 大运序列虽然依赖性别 (阳男阴女顺/阴男阳女逆), 但 detector 输入是
        pillars + strength + climate, 不读 dayun, 所以 phase 决策天然对称。
    """
    b_f = solve(pillars, None, "F", birth_year)
    b_m = solve(pillars, None, "M", birth_year)
    pd_f = decide_phase(b_f)
    pd_m = decide_phase(b_m)

    assert pd_f["decision"] == pd_m["decision"], (
        f"\n  {case_id}: 性别翻转改变了 phase decision: "
        f"F→{pd_f['decision']} vs M→{pd_m['decision']}\n"
        f"  违反 fairness_protocol §9: phase 决策不应依赖 gender。"
    )

    # 用神 / 喜神 / 忌神不依赖 gender, 必须 byte-equal
    assert pd_f["yongshen_after_phase"] == pd_m["yongshen_after_phase"], (
        f"\n  {case_id}: 性别翻转改变了 yongshen: "
        f"F→{pd_f['yongshen_after_phase']} vs M→{pd_m['yongshen_after_phase']}"
    )
    assert pd_f["xishen_after_phase"] == pd_m["xishen_after_phase"], (
        f"\n  {case_id}: 性别翻转改变了 xishen: "
        f"F→{pd_f['xishen_after_phase']} vs M→{pd_m['xishen_after_phase']}"
    )
    assert pd_f["jishen_after_phase"] == pd_m["jishen_after_phase"], (
        f"\n  {case_id}: 性别翻转改变了 jishen: "
        f"F→{pd_f['jishen_after_phase']} vs M→{pd_m['jishen_after_phase']}"
    )
    assert pd_f["strength_after_phase"] == pd_m["strength_after_phase"], (
        f"\n  {case_id}: 性别翻转改变了 strength: "
        f"F→{pd_f['strength_after_phase']} vs M→{pd_m['strength_after_phase']}"
    )

    # phase_label / climate 也应一致 (都来自 _phase_five_tuple, 不读 gender)
    assert pd_f["phase_label"] == pd_m["phase_label"], (
        f"\n  {case_id}: 性别翻转改变了 phase_label"
    )
    assert pd_f["climate_after_phase"] == pd_m["climate_after_phase"], (
        f"\n  {case_id}: 性别翻转改变了 climate"
    )

    # 先验分布也应完全一致 (prior 只看 detector, detector 不看 gender)
    assert pd_f["prior_distribution"] == pd_m["prior_distribution"], (
        f"\n  {case_id}: 性别翻转改变了 prior_distribution\n"
        f"  说明某个 detector 内部读取了 gender 字段, 违反 fairness §9。"
    )


@pytest.mark.parametrize(
    "case_id,pillars,birth_year",
    [
        ("cong_cai_candidate", "丙子 庚子 己卯 己巳", 1996),
        ("jobs_steve",         "乙未 戊寅 甲戌 甲戌", 1955),
    ],
    ids=["cong_cai_candidate", "jobs_steve"],
)
def test_phase_decision_with_user_answers_determinism(case_id, pillars, birth_year):
    """带 user_answers 的后验同样必须 bit-for-bit determinism。"""
    bazi = solve(pillars, None, "F", birth_year)
    answers = {
        "D4_Q1_cold_heat": "B",
        "D2_Q3_partner_economic_role": "B",
    }
    hashes = set()
    for _ in range(50):
        pd = decide_phase(bazi, user_answers=answers)
        hashes.add(_phase_decision_hash(pd))
    assert len(hashes) == 1, (
        f"\n  {case_id}: posterior 不确定 (50 次出现 {len(hashes)} 个不同 hash)\n"
        f"  说明贝叶斯更新流程引入了非确定性 (字典遍历顺序 / set 序列化等)。"
    )
