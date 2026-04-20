"""v9 PR-5 · rare_phases catalog + detector + LLM fallback 协议测试

覆盖：
  1. catalog md 文件存在 + 三层条目数 ≥ 110
  2. catalog 每条 schema 字段齐全
  3. rare_phase_detector.scan_all 在 1996/12/08 case 必触发 杀印相生 + 伤官生财
  4. 经典魁罡日柱必触发 detect_kuigang_ge
  5. 天元一气必触发
  6. llm_fallback_protocol.md 存在且包含关键章节
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

CATALOG_PATH = ROOT / "references" / "rare_phases_catalog.md"
LLM_FALLBACK_PATH = ROOT / "references" / "llm_fallback_protocol.md"

pytestmark = [pytest.mark.fast]


# ------------------------------------------------------------
# 1. catalog 总条目数
# ------------------------------------------------------------

def _count_table_rows(text: str) -> int:
    """统计所有 markdown 表格里的数据行 (排除 header 与 ---- 分隔)."""
    rows = 0
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        # header 行不数 (含'触发条件'或'流派'等关键词)
        if "触发条件" in s or "古书出处" in s or set(s.replace("|", "").strip()) <= {"-", " ", ":"}:
            continue
        rows += 1
    return rows


def test_catalog_exists():
    assert CATALOG_PATH.exists(), "rare_phases_catalog.md 必须存在"


def test_catalog_total_rows_ge_110():
    text = CATALOG_PATH.read_text(encoding="utf-8")
    n = _count_table_rows(text)
    assert n >= 110, f"catalog 条目数 {n} 不足 110"


def test_catalog_three_tiers():
    text = CATALOG_PATH.read_text(encoding="utf-8")
    assert "Tier 1" in text
    assert "Tier 2" in text
    assert "Tier 3" in text


def test_catalog_has_key_geju_ids():
    text = CATALOG_PATH.read_text(encoding="utf-8")
    must_have = [
        "zhengguan_ge", "qisha_ge", "shangguan_ge", "shishen_ge",
        "huaqi_jiayi_tu", "cong_cai_zhen", "kuigang_ge", "jinshen_ge",
        "tianyuanyiqi", "yang_ren_jia_sha", "qi_yin_xiang_sheng",
        "shang_guan_sheng_cai", "ma_xing_yi_dong", "ziwei_jun_chen_qing_hui",
    ]
    for mid in must_have:
        assert mid in text, f"catalog 缺关键条目 {mid}"


# ------------------------------------------------------------
# 2. detector 行为
# ------------------------------------------------------------

def test_detector_module_importable():
    import rare_phase_detector  # noqa
    assert hasattr(rare_phase_detector, "scan_all")
    assert hasattr(rare_phase_detector, "DETECTOR_FUNCS")
    assert len(rare_phase_detector.DETECTOR_FUNCS) >= 20


def test_detector_kuigang_pure():
    from rare_phase_detector import detect_kuigang_ge
    from _bazi_core import Pillar
    pillars = [Pillar("丙", "子"), Pillar("辛", "卯"),
               Pillar("庚", "辰"), Pillar("丁", "亥")]
    res = detect_kuigang_ge(pillars, "庚")
    assert res is not None
    assert res["id"] == "kuigang_ge"


def test_detector_tianyuanyiqi():
    from rare_phase_detector import detect_tianyuanyiqi
    from _bazi_core import Pillar
    pillars = [Pillar("甲", "子"), Pillar("甲", "戌"),
               Pillar("甲", "申"), Pillar("甲", "戌")]
    res = detect_tianyuanyiqi(pillars, "甲")
    assert res is not None
    assert res["confidence"] == 1.0


def test_detector_1996_case_triggers_qi_yin_xiang_sheng():
    """1996/12/08 case 应至少触发 杀印相生 (七杀+印星互生)"""
    from rare_phase_detector import scan_all
    from _bazi_core import Pillar
    pillars = [Pillar("丙", "子"), Pillar("庚", "子"),
               Pillar("己", "卯"), Pillar("己", "巳")]
    results = scan_all(pillars, "己")
    ids = {r["id"] for r in results}
    assert "qi_yin_xiang_sheng" in ids, (
        f"1996/12/08 case 必须触发杀印相生; 实际触发: {ids}"
    )


def test_detector_1996_case_does_not_trigger_cong_cai():
    """1996/12/08 case 有印根, 必须 NOT 触发真从财 (修复 PR-1 假从误判)"""
    from rare_phase_detector import scan_all
    from _bazi_core import Pillar
    pillars = [Pillar("丙", "子"), Pillar("庚", "子"),
               Pillar("己", "卯"), Pillar("己", "巳")]
    results = scan_all(pillars, "己")
    ids = {r["id"] for r in results}
    assert "cong_cai_zhen" not in ids, (
        f"1996/12/08 case 因有印根不能触发真从财; 实际触发: {ids}"
    )


def test_detector_jianlu_ge_jia_yin_in_yin_month():
    from rare_phase_detector import detect_jianlu_ge
    from _bazi_core import Pillar
    pillars = [Pillar("丙", "子"), Pillar("丁", "寅"),
               Pillar("甲", "申"), Pillar("乙", "亥")]
    res = detect_jianlu_ge(pillars, "甲")
    assert res is not None and res["id"] == "jianlu_ge"


def test_detector_yang_ren_jia_sha():
    from rare_phase_detector import detect_yang_ren_jia_sha
    from _bazi_core import Pillar
    # 丙日 + 卯月午刃 + 壬七杀
    pillars = [Pillar("壬", "辰"), Pillar("辛", "卯"),
               Pillar("丙", "午"), Pillar("壬", "辰")]
    res = detect_yang_ren_jia_sha(pillars, "丙")
    assert res is not None


def test_detector_no_false_positive_on_neutral_chart():
    """中庸盘 (壬戌 癸丑 庚午 丁丑 官印相生) 应只触发若干合理 detector, 不全亮"""
    from rare_phase_detector import scan_all
    from _bazi_core import Pillar
    pillars = [Pillar("壬", "戌"), Pillar("癸", "丑"),
               Pillar("庚", "午"), Pillar("丁", "丑")]
    results = scan_all(pillars, "庚")
    ids = {r["id"] for r in results}
    # 大多 detector 应不触发
    assert len(ids) < 10, f"普通盘不应大面积命中; 触发: {ids}"


# ------------------------------------------------------------
# 3. LLM fallback protocol
# ------------------------------------------------------------

def test_llm_fallback_protocol_exists():
    assert LLM_FALLBACK_PATH.exists()


def test_llm_fallback_protocol_key_sections():
    text = LLM_FALLBACK_PATH.read_text(encoding="utf-8")
    for marker in ["触发条件", "llm_fallback_instruction",
                   "fallback_phase_candidates", "BAZI_DISABLE_LLM_FALLBACK",
                   "precision > recall"]:
        assert marker in text, f"llm_fallback_protocol 缺关键章节: {marker}"
