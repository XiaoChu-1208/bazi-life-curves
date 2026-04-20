"""v9 PR-1 · root_strength 测试矩阵

覆盖：
  1. 无根 / 微根 / 弱根 / 中根 / 强根 五档 label
  2. bijie_root vs yin_root 区分
  3. 印根边界 case 黄金回归：必须有 yin_root，不能落"无根"
  4. 真从财格典型盘必须落"无根"
  5. day_master_strength 嵌入 root_strength 字段
  6. apply_phase_override 守卫：有印根时从格触发 _root_strength_warnings
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from _bazi_core import (  # noqa: E402
    compute_dayuan_root_strength,
    parse_pillars,
    day_master_strength,
)


pytestmark = [pytest.mark.fast]


# ------------------------------------------------------------
# 1. 五档 label 阈值
# ------------------------------------------------------------

@pytest.mark.parametrize(
    "stem,branches,expected_label,expected_total_range",
    [
        # 无根：日主丁火 + 子申酉酉 (申中藏壬戊不算印/比，酉无藏火木)
        ("丁", ["子", "申", "酉", "酉"], "无根", (0.0, 0.30)),
        # 微根：日主丁火 + 子申酉亥 (亥中甲中气=印 0.5)
        ("丁", ["子", "申", "酉", "亥"], "微根", (0.30, 0.70)),
        # 弱根：日主己 + 子子卯巳 (巳本丙印1.0+戊余比0.2 = 1.2) — 印根边界 case
        ("己", ["子", "子", "卯", "巳"], "弱根", (0.70, 1.50)),
        # 中根：日主庚 + 申丑辰未 (申本庚比1.0; 丑本己印1.0; 辰本戊印1.0; 未本己印1.0 + 中乙不算)
        # 实际太多变 → 用己土 + 戌酉巳卯 (戌本戊1.0+丁余0.2; 巳本丙1.0+戊余0.2 = 2.4)
        ("己", ["戌", "酉", "巳", "卯"], "中根", (1.50, 2.50)),
        # 强根：己 + 全土 / 全火支 (巳午未戌)
        ("己", ["巳", "午", "未", "戌"], "强根", (2.50, 99.0)),
    ],
)
def test_root_strength_label_thresholds(stem, branches, expected_label, expected_total_range):
    rs = compute_dayuan_root_strength(stem, branches)
    assert rs["label"] == expected_label, (
        f"stem={stem} branches={branches} expected {expected_label} but got {rs['label']} "
        f"(total={rs['total_root']}, bijie={rs['bijie_root']}, yin={rs['yin_root']})"
    )
    lo, hi = expected_total_range
    assert lo <= rs["total_root"] < hi, (
        f"total_root={rs['total_root']} not in [{lo},{hi})"
    )


# ------------------------------------------------------------
# 2. bijie vs yin 区分
# ------------------------------------------------------------

def test_bijie_only_no_yin():
    """日主庚 + 申酉戌 = 全比劫，零印根"""
    rs = compute_dayuan_root_strength("庚", ["申", "酉", "戌", "丑"])
    assert rs["bijie_root"] > 0
    # 庚金的印 = 土，丑/戌中藏己/戊
    assert rs["yin_root"] >= 0  # 戌余气有戊（不算印）丑本气是己（土生金算印）
    assert rs["bijie_root"] >= rs["yin_root"]


def test_yin_dominant_with_some_bijie():
    """日主甲 + 子亥申酉：印旺为主、亥中甲中气有少量比劫"""
    rs = compute_dayuan_root_strength("甲", ["子", "亥", "酉", "申"])
    assert rs["yin_root"] > rs["bijie_root"]
    assert rs["yin_root"] >= 2.0  # 子(癸1.0) + 亥(壬1.0) + 申(壬中0.5)
    # 亥中藏甲（中气）→ bijie_root 不为 0
    assert rs["bijie_root"] == 0.5


# ------------------------------------------------------------
# 3. 印根边界 case 黄金回归
# ------------------------------------------------------------

def test_rooted_pseudo_following_boundary_must_have_yin_root():
    """diagnosis_pitfalls §14 要求：日支主气印星结构 yin_root>0、不能落'无根'，
    否则会误触假从。代表结构：日主己土 + 月支水 + 时支巳 (巳本气丙=正印)。"""
    pillars = parse_pillars("丙子,庚子,己卯,己巳")
    rs = compute_dayuan_root_strength("己", [p.zhi for p in pillars])
    assert rs["yin_root"] >= 1.0, f"巳中本气丙=印 应贡献 1.0，实际 {rs['yin_root']}"
    assert rs["label"] != "无根"
    assert rs["label"] != "微根"
    assert rs["total_root"] >= 0.30


# ------------------------------------------------------------
# 4. 真从财格门槛
# ------------------------------------------------------------

def test_true_following_threshold_unrooted():
    """真从格门槛：必须 total<0.30。构造日主丁火 + 子申酉酉 = 0"""
    rs = compute_dayuan_root_strength("丁", ["子", "申", "酉", "酉"])
    assert rs["total_root"] < 0.30, (
        f"全水金支应零根，实际 total={rs['total_root']} details={rs['details']}"
    )
    assert rs["label"] == "无根"


# ------------------------------------------------------------
# 5. day_master_strength 嵌入
# ------------------------------------------------------------

def test_day_master_strength_embeds_root():
    pillars = parse_pillars("丙子,庚子,己卯,己巳")
    dms = day_master_strength(pillars)
    assert "root_strength" in dms
    assert dms["root_strength"]["label"] == "弱根"
    assert dms["root_strength"]["yin_root"] >= 1.0


# ------------------------------------------------------------
# 6. apply_phase_override 守卫
# ------------------------------------------------------------

def _mock_bazi(stem, branches, root_strength, **extra):
    """构造最小可用 bazi dict，覆盖 apply_phase_override 所需字段"""
    base = {
        "day_master": stem,
        "day_master_wuxing": {"甲": "木", "乙": "木", "丙": "火", "丁": "火",
                              "戊": "土", "己": "土", "庚": "金", "辛": "金",
                              "壬": "水", "癸": "水"}[stem],
        "pillars": [
            {"gan": "甲", "zhi": branches[0]},
            {"gan": "乙", "zhi": branches[1]},
            {"gan": stem, "zhi": branches[2]},
            {"gan": "丁", "zhi": branches[3]},
        ],
        "strength": {
            "label": "弱", "score": -33,
            "same": 0, "sheng": 0, "xie": 0, "ke": 0, "kewo": 0,
            "root_strength": root_strength,
        },
        "yongshen": {"yongshen": "火"},
        "wuxing_distribution": {"木": 1, "火": 1, "土": 3, "金": 1, "水": 2},
    }
    base.update(extra)
    return base


def test_apply_phase_override_root_warning_on_floating_dms():
    from score_curves import apply_phase_override

    rs = {"stem": "己", "stem_wx": "土",
          "bijie_root": 0.2, "yin_root": 1.0, "total_root": 1.2,
          "label": "弱根", "details": []}
    bazi = _mock_bazi("己", ["子", "子", "卯", "巳"], rs)
    out = apply_phase_override(bazi, "floating_dms_to_cong_cai")
    warns = out["phase"].get("_root_strength_warnings") or []
    assert len(warns) >= 2, f"应至少 2 条警告，实际：{warns}"
    assert any("yin_root" in w for w in warns)


def test_apply_phase_override_no_warning_when_truly_floating():
    from score_curves import apply_phase_override

    rs = {"stem": "丁", "stem_wx": "火",
          "bijie_root": 0.0, "yin_root": 0.0, "total_root": 0.0,
          "label": "无根", "details": []}
    bazi = _mock_bazi("丁", ["子", "申", "酉", "酉"], rs,
                      wuxing_distribution={"木": 0, "火": 1, "土": 0, "金": 4, "水": 3})
    out = apply_phase_override(bazi, "floating_dms_to_cong_cai")
    assert "_root_strength_warnings" not in out["phase"]


def test_apply_phase_override_huaqi_warning_on_rooted():
    from score_curves import apply_phase_override

    rs = {"stem": "甲", "stem_wx": "木",
          "bijie_root": 2.0, "yin_root": 1.5, "total_root": 3.5,
          "label": "强根", "details": []}
    bazi = _mock_bazi("甲", ["寅", "卯", "亥", "子"], rs,
                      wuxing_distribution={"木": 4, "火": 1, "土": 1, "金": 1, "水": 1})
    out = apply_phase_override(bazi, "huaqi_to_土")
    warns = out["phase"].get("_root_strength_warnings") or []
    assert len(warns) >= 1
    assert any("化气格" in w for w in warns)
