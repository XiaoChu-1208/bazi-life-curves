"""v9 PR-3 · 大运层 fanyin/fuyin detector 测试"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _bazi_core import Pillar  # noqa: E402
from mangpai_events import (  # noqa: E402
    detect_dayun_fuyin_natal,
    detect_dayun_fanyin_rizhu,
    detect_liunian_fuyin_dayun,
    detect_liunian_fanyin_dayun,
    detect_year_events,
    DETECTOR_REGISTRY,
)


pytestmark = [pytest.mark.fast]


def test_dayun_fuyin_natal_hits_year_pillar():
    natal = [Pillar("丙", "子"), Pillar("庚", "子"), Pillar("己", "卯"), Pillar("己", "巳")]
    dy = Pillar("丙", "子")
    res = detect_dayun_fuyin_natal(natal, dy)
    assert res is not None
    evidence, idx = res
    assert idx == 0  # 年柱
    assert "年柱" in evidence
    assert "丙子" in evidence


def test_dayun_fuyin_natal_no_match():
    natal = [Pillar("丙", "子"), Pillar("庚", "子"), Pillar("己", "卯"), Pillar("己", "巳")]
    dy = Pillar("壬", "申")
    assert detect_dayun_fuyin_natal(natal, dy) is None


def test_dayun_fanyin_rizhu_天克地冲():
    natal = [Pillar("丙", "子"), Pillar("庚", "子"), Pillar("己", "卯"), Pillar("己", "巳")]
    # 己卯 反吟 → 天克：乙(木克土) 地冲：酉
    dy = Pillar("乙", "酉")
    ev = detect_dayun_fanyin_rizhu(natal, dy)
    assert ev is not None
    assert "乙酉" in ev
    assert "日柱" in ev or "己卯" in ev


def test_dayun_fanyin_rizhu_no_match():
    natal = [Pillar("丙", "子"), Pillar("庚", "子"), Pillar("己", "卯"), Pillar("己", "巳")]
    dy = Pillar("丙", "戌")
    assert detect_dayun_fanyin_rizhu(natal, dy) is None


def test_liunian_fuyin_dayun():
    dy = Pillar("丙", "子")
    ln = Pillar("丙", "子")
    ev = detect_liunian_fuyin_dayun(dy, ln)
    assert ev is not None
    assert "丙子" in ev


def test_liunian_fanyin_dayun():
    dy = Pillar("丙", "子")
    ln = Pillar("壬", "午")
    ev = detect_liunian_fanyin_dayun(dy, ln)
    assert ev is not None


def test_detector_registry_has_4_new_dayun_keys():
    keys = {d["key"] for d in DETECTOR_REGISTRY}
    assert "dayun_fuyin_natal" in keys
    assert "dayun_fanyin_rizhu" in keys
    assert "liunian_fuyin_dayun" in keys
    assert "liunian_fanyin_dayun" in keys


def test_dayun_only_fires_only_on_first_year():
    """dayun_only detectors 必须只在大运首年触发, 否则 10 年里会重复 10 次"""
    natal = [Pillar("丙", "子"), Pillar("庚", "子"), Pillar("己", "卯"), Pillar("己", "巳")]
    dy = Pillar("丙", "子")  # 与年柱伏吟
    ln = Pillar("甲", "辰")  # 任意流年

    # is_dayun_first_year=True 应该出现 dayun_fuyin_natal 事件
    evs_first = detect_year_events(
        "己", natal, dy, ln, year=2020, age=24, dayun_label="丙子",
        is_dayun_first_year=True,
    )
    keys_first = {e["key"] for e in evs_first}
    assert "dayun_fuyin_natal" in keys_first

    # is_dayun_first_year=False 时不应触发
    evs_mid = detect_year_events(
        "己", natal, dy, ln, year=2025, age=29, dayun_label="丙子",
        is_dayun_first_year=False,
    )
    keys_mid = {e["key"] for e in evs_mid}
    assert "dayun_fuyin_natal" not in keys_mid


def test_liunian_fanyin_dayun_fires_every_year_when_match():
    """流年级 detector 每年都该独立判定"""
    natal = [Pillar("丙", "子"), Pillar("庚", "子"), Pillar("己", "卯"), Pillar("己", "巳")]
    dy = Pillar("丙", "子")
    ln = Pillar("壬", "午")  # 反吟丙子

    for is_first in (True, False):
        evs = detect_year_events(
            "己", natal, dy, ln, year=2020, age=24, dayun_label="丙子",
            is_dayun_first_year=is_first,
        )
        keys = {e["key"] for e in evs}
        assert "liunian_fanyin_dayun" in keys, f"is_first={is_first}"
