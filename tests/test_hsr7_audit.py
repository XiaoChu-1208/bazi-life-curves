"""v9 PR-4 · HS-R7 守卫 + 心智模型字段测试

覆盖：
  - 缺失字段时 strict=False 仅记录, strict=True raise
  - HSR7_DISCLOSURE_TEXT 三声明完整
  - append_reflexivity_disclaimer 追加正确文本
  - score() 输出 curves 包含 hsr7_audit 字段
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from score_curves import (  # noqa: E402
    HSR7_REQUIRED_FIELDS,
    HSR7_DISCLOSURE_TEXT,
    MissingHSR7Disclosure,
    hsr7_audit,
    append_reflexivity_disclaimer,
)


pytestmark = [pytest.mark.fast]


def test_hsr7_disclosure_three_statements():
    keys = set(HSR7_DISCLOSURE_TEXT.keys())
    assert keys == {"limitations", "reflexivity", "user_authority"}
    for v in HSR7_DISCLOSURE_TEXT.values():
        assert isinstance(v, str)
        assert len(v) > 30


def test_hsr7_required_fields_lists_5_protocol_items():
    assert "narrative_caution" in HSR7_REQUIRED_FIELDS
    assert "phase_composition" in HSR7_REQUIRED_FIELDS
    assert "alternative_readings" in HSR7_REQUIRED_FIELDS
    assert "must_be_true" in HSR7_REQUIRED_FIELDS


def test_hsr7_audit_warning_when_missing(monkeypatch):
    monkeypatch.delenv("BAZI_STRICT_HSR7", raising=False)
    bazi = {"phase": {"id": "day_master_dominant"}}
    audit = hsr7_audit(bazi, {}, strict=False)
    assert audit["missing_fields"]
    # 默认 warning 模式不应抛
    assert "narrative_caution" in str(audit["missing_fields"])


def test_hsr7_audit_strict_raises():
    bazi = {"phase": {"id": "day_master_dominant"}}
    with pytest.raises(MissingHSR7Disclosure, match="HS-R7"):
        hsr7_audit(bazi, {}, strict=True)


def test_hsr7_audit_passes_when_all_fields_present():
    bazi = {
        "phase": {
            "id": "qi_yin_xiang_sheng",
            "narrative_caution": "ok",
            "phase_composition": [],
            "alternative_readings": [],
            "must_be_true": [],
        }
    }
    audit = hsr7_audit(bazi, {}, strict=True)
    assert audit["missing_fields"] == []


def test_append_reflexivity_disclaimer_adds_text():
    out = append_reflexivity_disclaimer("某年大有作为")
    assert "某年大有作为" in out
    assert "反身" not in out  # 我们用了'反身性'话术但不需要这个 keyword
    assert "解释模式" in out
    assert "剧本" in out


def test_append_reflexivity_disclaimer_empty_passthrough():
    assert append_reflexivity_disclaimer("") == ""


def test_score_output_contains_hsr7_audit(tmp_path):
    """端到端: solve_bazi -> score -> curves 必须有 hsr7_audit"""
    from solve_bazi import solve
    from score_curves import score

    bazi = solve(
        pillars_str="壬戌 癸丑 庚午 丁丑",
        gregorian=None,
        gender="M",
        birth_year=1982,
        n_years=80,
    )
    curves = score(bazi, age_start=0, age_end=40)
    assert "hsr7_audit" in curves
    assert "hsr7_disclosure" in curves["hsr7_audit"]
    assert set(curves["hsr7_audit"]["hsr7_disclosure"].keys()) == {
        "limitations", "reflexivity", "user_authority"
    }
    assert curves["hsr7_audit"]["mind_model_protocol_ref"].endswith(
        "mind_model_protocol.md"
    )


def test_mind_model_protocol_doc_exists():
    p = ROOT / "references" / "mind_model_protocol.md"
    assert p.exists(), "PR-4 必须创建 mind_model_protocol.md"
    text = p.read_text(encoding="utf-8")
    for marker in ["HS-R7", "5.6 open_phase", "5.10", "1996/12/08"]:
        assert marker in text, f"protocol doc 缺关键章节: {marker}"
