"""v9.1 · render_artifact.py LLM 完成度审计 + 字段注入 回归测试

背景:
  在 v9.1 之前, render_artifact.render() 只把 overall / turning_points / disputes /
  era_narratives / dayun_reviews 5 个字段塞进 ANALYSIS, 但模板 chart_artifact.html.j2
  实际还引用了 life_review / dayun_review (单数) / key_years / confirmed_facts。
  → 即使 LLM 老老实实把这些字段写到 analysis.json 里, render 后仍然只显示
    "（此处由 LLM 写入...）" 占位符——纯静默 bug。

本测试锁定:
  T1  render() 必须把模板用到的所有 ANALYSIS.* 字段都注入 (回归保护)
  T2  audit_llm_coverage() 对完整 analysis 返回 missing=[]
  T3  audit_llm_coverage() 对空 analysis 报告 overall + life_review.{spirit,wealth,fame} 缺失
  T4  audit_llm_coverage() 在 curves 有大运段时把 dayun_reviews[label] 列入必填
  T5  audit_llm_coverage() 在 zeitgeist 有 era_windows_used 时把 era_narratives[id] 列入必填
  T6  --strict-llm 路径下缺失字段 raise LlmCoverageError
  T7  默认 (非 strict) 路径下不 raise, 只产生 warnings
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from render_artifact import (  # noqa: E402
    LlmCoverageError,
    audit_llm_coverage,
    render,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _minimal_curves() -> dict:
    """模板能渲染过的最小 curves 结构。"""
    return {
        "version": 9,
        "pillars_str": "庚午 辛巳 壬子 丁未",
        "baseline": {"spirit": 50.0, "wealth": 50.0, "fame": 50.0, "emotion": 50.0},
        # v9.3.1 · points 必须是 list (旧 fixture 错写成 dict, 新 schema 守卫拒收)
        "points": [],
        "dayun": {
            "segments": [
                {"label": "戊辰", "start_age": 5, "end_age": 14,
                 "start_year": 1995, "end_year": 2004},
                {"label": "丁卯", "start_age": 15, "end_age": 24,
                 "start_year": 2005, "end_year": 2014},
            ],
        },
        "disputes": [],
        "turning_points_future": [],
    }


def _zeitgeist_with_two_eras() -> dict:
    return {
        "era_windows_used": [
            {"id": "cn_wto_age", "label": "入世+城市化",
             "span": [2003, 2008], "keywords": ["WTO", "房地产"]},
            {"id": "cn_mobile_internet", "label": "移动互联网",
             "span": [2009, 2015], "keywords": ["智能手机", "App"]},
        ],
    }


def _full_analysis() -> dict:
    return {
        "overall": "整图综合分析的 markdown 文本，足够长。",
        "life_review": {
            "spirit": "精神舒畅度一生总评。",
            "wealth": "财富一生总评。",
            "fame": "名声一生总评。",
            "emotion": "感情/关系一生总评。",
        },
        "virtue_narrative": {
            "opening": "开篇悬疑提示（位置①）。",
            "declaration": "灵魂宣言（位置④）。",
            "free_speech": "LLM 自由话（位置⑥）。",
        },
        "key_years": [
            {"year": 2007, "age": 18, "ganzhi": "丁亥", "kind": "shift",
             "headline": "升学", "body": "..."}
        ],
        "dayun_reviews": {
            "戊辰": "戊辰大运 6 块完整 markdown。",
            "丁卯": "丁卯大运 6 块完整 markdown。",
        },
        "era_narratives": {
            "cn_wto_age": "入世+城市化区间叙事。",
            "cn_mobile_internet": "移动互联网区间叙事。",
        },
    }


# ---------------------------------------------------------------------------
# T1 · 字段注入回归 (核心 bug)
# ---------------------------------------------------------------------------

def test_render_injects_all_template_referenced_fields():
    """模板里 ANALYSIS.life_review / dayun_review / key_years / confirmed_facts
    必须出现在 render() 产物中, 否则就是回归到 v9.1 之前的静默 bug。"""
    curves = _minimal_curves()
    analysis = _full_analysis()
    analysis["confirmed_facts"] = {"validations": []}
    analysis["dayun_review"] = {"戊辰": {"headline": "稳", "body": "..."}}

    html = render(curves, analysis, zeitgeist=None)

    # 模板把 analysis_json 作为 JS 字符串嵌进去, 检查关键字符串都在产物里
    assert "精神舒畅度一生总评" in html, "life_review.spirit 未注入到 ANALYSIS"
    assert "财富一生总评" in html, "life_review.wealth 未注入到 ANALYSIS"
    assert "名声一生总评" in html, "life_review.fame 未注入到 ANALYSIS"
    assert "升学" in html, "key_years headline 未注入"
    assert "戊辰大运 6 块完整 markdown" in html, "dayun_reviews 未注入"


def test_render_injects_emotion_dimension_and_virtue_narrative():
    """v9 · render() 必须把 life_review.emotion + virtue_narrative.* + virtue_motifs 都注入。"""
    curves = _minimal_curves()
    analysis = _full_analysis()
    analysis["life_review"]["emotion"] = "感情/关系一生总评_TOKEN_E"
    analysis["virtue_narrative"]["opening"] = "OPEN_TOKEN_V1"
    analysis["virtue_narrative"]["declaration"] = "DECL_TOKEN_V4"
    analysis["virtue_narrative"]["love_letter"] = "LOVE_TOKEN_V5"
    analysis["virtue_narrative"]["free_speech"] = "FREE_TOKEN_V6"
    motifs = {
        "love_letter_eligible": True,
        "convergence_years": [2007],
        "triggered_motifs": [
            {"id": "M01_test", "label": "测试母题", "gravity": "medium",
             "activations": [{"year": 2007}]},
        ],
    }
    html = render(curves, analysis, zeitgeist=None, virtue_motifs=motifs)
    assert "感情/关系一生总评_TOKEN_E" in html
    assert "OPEN_TOKEN_V1" in html
    assert "DECL_TOKEN_V4" in html
    assert "LOVE_TOKEN_V5" in html
    assert "FREE_TOKEN_V6" in html
    assert "M01_test" in html, "virtue_motifs.triggered_motifs 未注入"


def test_render_partial_flag_sets_window_global():
    curves = _minimal_curves()
    html = render(curves, _full_analysis(), zeitgeist=None, allow_partial=True)
    assert "__BAZI_PARTIAL__ = true" in html


def test_render_legacy_dayun_review_singular_also_works():
    """旧版 analysis.dayun_review (单数, {label: {headline, body}}) 也要被注入。"""
    curves = _minimal_curves()
    html = render(curves, {
        "overall": "x",
        "dayun_review": {"戊辰": {"headline": "HEADLINE_TOKEN", "body": "BODY_TOKEN"}},
    })
    assert "HEADLINE_TOKEN" in html, "legacy dayun_review.headline 未注入"


# ---------------------------------------------------------------------------
# T2 · 完整 analysis 应该全绿
# ---------------------------------------------------------------------------

def test_audit_full_analysis_zero_missing():
    curves = _minimal_curves()
    zeitgeist = _zeitgeist_with_two_eras()
    analysis = _full_analysis()
    # v9 · 必须注入 virtue_motifs（哪怕空）才不触发"未启用"警告；
    # love_letter_eligible=False → love_letter 不必填；
    # convergence_years=[] → convergence_notes 不必填。
    virtue_motifs = {"love_letter_eligible": False, "convergence_years": []}

    report = audit_llm_coverage(curves, analysis, zeitgeist, virtue_motifs)
    assert report["missing"] == [], f"应零缺失, 实际: {report['missing']}"
    assert report["coverage_pct"] == 100.0
    assert report["warnings"] == []


# ---------------------------------------------------------------------------
# T3 · 空 analysis 必报 overall + life_review 缺失
# ---------------------------------------------------------------------------

def test_audit_empty_analysis_reports_basic_misses():
    curves = _minimal_curves()
    report = audit_llm_coverage(curves, analysis=None, zeitgeist=None)

    assert "analysis.overall" in report["missing"]
    assert "analysis.life_review.spirit" in report["missing"]
    assert "analysis.life_review.wealth" in report["missing"]
    assert "analysis.life_review.fame" in report["missing"]
    assert "analysis.life_review.emotion" in report["missing"], \
        "v9 · 第 4 维 emotion 必须列入必填"
    assert "analysis.virtue_narrative.opening" in report["missing"]
    assert "analysis.virtue_narrative.declaration" in report["missing"]
    assert "analysis.virtue_narrative.free_speech" in report["missing"]
    assert "analysis.key_years[>=1]" in report["missing"]
    assert report["coverage_pct"] < 50.0
    assert len(report["warnings"]) >= 1


def test_audit_warns_when_virtue_motifs_missing():
    """v9 · 不传 virtue_motifs 时必须给出独立 warning（即使其他都齐）。"""
    curves = _minimal_curves()
    zeitgeist = _zeitgeist_with_two_eras()
    analysis = _full_analysis()
    report = audit_llm_coverage(curves, analysis, zeitgeist, virtue_motifs=None)
    assert any("virtue_motifs" in w for w in report["warnings"]), \
        f"应包含 virtue_motifs 未启用 warning, 实际: {report['warnings']}"


def test_audit_love_letter_required_only_when_eligible():
    """v9 · love_letter 仅在 motifs.love_letter_eligible=true 时才必填。"""
    curves = _minimal_curves()
    analysis = _full_analysis()
    # love_letter 没写
    eligible = {"love_letter_eligible": True, "convergence_years": []}
    not_eligible = {"love_letter_eligible": False, "convergence_years": []}

    r_yes = audit_llm_coverage(curves, analysis, zeitgeist=None, virtue_motifs=eligible)
    r_no = audit_llm_coverage(curves, analysis, zeitgeist=None, virtue_motifs=not_eligible)
    assert "analysis.virtue_narrative.love_letter" in r_yes["missing"]
    assert "analysis.virtue_narrative.love_letter" not in r_no["missing"]


def test_audit_convergence_notes_required_when_motifs_converge():
    """v9 · convergence_notes 仅在 motifs.convergence_years 非空时才必填。"""
    curves = _minimal_curves()
    analysis = _full_analysis()
    motifs_with_conv = {"love_letter_eligible": False, "convergence_years": [2007, 2015]}
    motifs_without = {"love_letter_eligible": False, "convergence_years": []}

    r_with = audit_llm_coverage(curves, analysis, zeitgeist=None, virtue_motifs=motifs_with_conv)
    r_without = audit_llm_coverage(curves, analysis, zeitgeist=None, virtue_motifs=motifs_without)
    assert "analysis.virtue_narrative.convergence_notes" in r_with["missing"]
    assert "analysis.virtue_narrative.convergence_notes" not in r_without["missing"]


# ---------------------------------------------------------------------------
# T4 · 大运段必填
# ---------------------------------------------------------------------------

def test_audit_dayun_segments_required_per_label():
    curves = _minimal_curves()  # 含 戊辰 / 丁卯 两段
    analysis = {
        "overall": "x",
        "life_review": {"spirit": "a", "wealth": "b", "fame": "c"},
        "key_years": [{"year": 2007}],
        "dayun_reviews": {"戊辰": "已写"},  # 故意只写一段
    }
    report = audit_llm_coverage(curves, analysis, zeitgeist=None)
    assert any("丁卯" in m for m in report["missing"]), \
        f"丁卯 大运未写应被列出, 实际 missing: {report['missing']}"
    assert not any("'戊辰'" in m for m in report["missing"]), "戊辰 已写不应被列出"


# ---------------------------------------------------------------------------
# T5 · era_windows 必填
# ---------------------------------------------------------------------------

def test_audit_era_windows_required_per_id():
    curves = _minimal_curves()
    zeitgeist = _zeitgeist_with_two_eras()
    analysis = _full_analysis()
    analysis["era_narratives"] = {"cn_wto_age": "已写"}  # 漏 cn_mobile_internet

    report = audit_llm_coverage(curves, analysis, zeitgeist)
    assert any("cn_mobile_internet" in m for m in report["missing"])
    assert not any("'cn_wto_age'" in m for m in report["missing"])


# ---------------------------------------------------------------------------
# T6 · strict 模式必 raise
# ---------------------------------------------------------------------------

def test_strict_mode_raises_on_missing(tmp_path, monkeypatch, capsys):
    import render_artifact as ra

    curves_path = tmp_path / "curves.json"
    curves_path.write_text(json.dumps(_minimal_curves()), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "render_artifact.py",
        "--curves", str(curves_path),
        "--out", str(tmp_path / "out.html"),
        "--strict-llm",
    ])
    with pytest.raises(LlmCoverageError) as ei:
        ra.main()
    assert "strict-llm" in str(ei.value)
    assert "覆盖度" in str(ei.value)


# ---------------------------------------------------------------------------
# T7 · `--no-strict-llm` 显式降级路径：不 raise，只警告
#
# v9.3 起，`--strict-llm` 默认 True（与 `--require-streamed-emit` 等其它 v9 strict 审计统一），
# 用户需显式 `--no-strict-llm` 才能降级到只 stderr 警告。
# 老的"默认就是非 strict"语义已经在 v9.3 升级中废弃，本测试相应改名 + 改实现。
# ---------------------------------------------------------------------------

def test_no_strict_llm_only_warns_no_raise(tmp_path, monkeypatch, capfd):
    import render_artifact as ra

    curves_path = tmp_path / "curves.json"
    out_path = tmp_path / "out.html"
    curves_path.write_text(json.dumps(_minimal_curves()), encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "render_artifact.py",
        "--curves", str(curves_path),
        "--out", str(out_path),
        "--no-strict-llm",
    ])
    ra.main()  # 不应 raise
    assert out_path.exists()
    captured = capfd.readouterr()
    assert "[coverage]" in captured.err
    assert "缺失字段" in captured.err
