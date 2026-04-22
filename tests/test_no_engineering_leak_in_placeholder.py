"""v9.3.1 · web artifact placeholder 工程内容外泄守卫测试 (Bug 11).

背景:
  chart_artifact.html.j2 的 placeholder div 历史上把 references/*.md 协议路径 +
  analysis.X.Y schema 字串直接展示给读者. 普通用户看到 "references/multi_dim_xiangshu_protocol.md §3"
  只会困惑或失去信任. 本测试锁定:
    1. _v9_guard.scan_placeholder_engineering_leak 能命中 4 类工程标识
       (references/*.md / analysis.X.Y / virtue_motifs.X / __BAZI_X__)
    2. 渲染后的 HTML (整模板, 残缺数据 → 全部 placeholder 露出) 不再含上述任一类工程标识
    3. enforce_* 在命中时正确 exit 13
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _v9_guard import (  # noqa: E402
    PlaceholderLeakError,
    enforce_no_placeholder_engineering_leak,
    scan_placeholder_engineering_leak,
)
from render_artifact import render  # noqa: E402


# ─── §1 · scanner unit tests ──────────────────────────────────

def _wrap_placeholder(text: str) -> str:
    """构造测试用 HTML, 包含一个 placeholder div."""
    return f'<div class="placeholder">{text}</div>'


def test_scan_catches_protocol_path() -> None:
    html = _wrap_placeholder(
        "（此处由 LLM 根据 references/multi_dim_xiangshu_protocol.md §4 写入）"
    )
    hits = scan_placeholder_engineering_leak(html)
    assert any("protocol path" in h.reason for h in hits), (
        f"应命中 references/*.md 模式, 实际 {hits}"
    )


def test_scan_catches_analysis_schema() -> None:
    html = _wrap_placeholder("数据结构: analysis.key_years = [{...}]")
    hits = scan_placeholder_engineering_leak(html)
    assert any("schema path" in h.reason and "analysis" in h.pattern for h in hits)


def test_scan_catches_virtue_motifs_schema() -> None:
    html = _wrap_placeholder("条件已成立 (virtue_motifs.love_letter_eligible=true)")
    hits = scan_placeholder_engineering_leak(html)
    assert any("virtue_motifs" in h.pattern for h in hits)


def test_scan_catches_internal_global() -> None:
    html = _wrap_placeholder("当前未传 __BAZI_VIRTUE_MOTIFS__")
    hits = scan_placeholder_engineering_leak(html)
    assert any("__BAZI_" in h.pattern for h in hits)


def test_scan_neutral_text_no_hits() -> None:
    """中性占位文案不应被命中."""
    html = _wrap_placeholder(
        "综合分析尚未写入。⌛ 流式写作中, 稍后会补齐这一节。"
    )
    hits = scan_placeholder_engineering_leak(html)
    assert hits == [], f"中性文案不应命中, 实际 {hits}"


def test_scan_only_inside_placeholder_div() -> None:
    """工程内容只在 placeholder div 之外 → 不命中."""
    html = (
        '<div class="vs-hint">analysis.virtue_narrative.opening</div>'
        '<div class="era-banner">详见 references/zeitgeist_protocol.md</div>'
        '<div class="placeholder">综合分析尚未写入。</div>'
    )
    hits = scan_placeholder_engineering_leak(html)
    assert hits == [], (
        "工程内容只在 placeholder div 之外不应命中 (vs-hint / era-banner 是协议元数据卡, 不算 placeholder leak)"
    )


def test_scan_jsx_classname_form_also_caught() -> None:
    """模板源文件用 className= (JSX); 守卫应同时支持 className= 和 class= 两种写法."""
    html = (
        '<div className="placeholder">references/foo.md</div>'
        '<div class="placeholder">analysis.bar</div>'
    )
    hits = scan_placeholder_engineering_leak(html)
    assert len(hits) >= 2


# ─── §2 · enforce_* 行为 ──────────────────────────────────────

def test_enforce_raises_on_hit() -> None:
    html = _wrap_placeholder("详见 references/protocol.md §3")
    with pytest.raises(PlaceholderLeakError) as ei:
        enforce_no_placeholder_engineering_leak(html)
    assert ei.value.code == 13
    assert any("protocol" in h.reason for h in ei.value.hits)


def test_enforce_no_raise_when_clean() -> None:
    html = _wrap_placeholder("综合分析尚未写入。")
    out = enforce_no_placeholder_engineering_leak(html)
    assert out == []


def test_enforce_no_raise_when_disabled() -> None:
    html = _wrap_placeholder("references/foo.md")
    out = enforce_no_placeholder_engineering_leak(html, raise_on_hit=False)
    assert len(out) == 1


def test_enforce_empty_html() -> None:
    assert enforce_no_placeholder_engineering_leak("") == []
    assert enforce_no_placeholder_engineering_leak(None) == []  # type: ignore[arg-type]


# ─── §3 · 集成: 真实模板渲染产物不应有任何 leak ──────────────

def test_real_render_no_engineering_leak_in_placeholders() -> None:
    """残缺数据 → 大量 placeholder 露出 → 渲染产物 placeholder 区不应含工程标识."""
    curves = {
        "pillars_str": "庚午 辛巳 壬子 丁未",
        "day_master": "壬",
        "birth_year": 1990,
        "baseline": {"spirit": 50, "wealth": 50, "fame": 50, "emotion": 50},
        "points": [],  # 空 → 触发 NoChartFallback
        "yongshen": {"yongshen": "甲", "season": "夏"},
        "strength": {"label": "中和"},
        "dayun_segments": [
            {"label": "戊辰", "start_age": 5, "end_age": 14,
             "start_year": 1995, "end_year": 2004},
        ],
    }
    # 不传 analysis → 所有 LLM 字段都缺 → 全部 placeholder 露出
    html = render(curves, analysis={}, allow_partial=True)
    hits = scan_placeholder_engineering_leak(html)
    assert hits == [], (
        f"渲染后的 placeholder 区不应有工程内容外泄, 实际命中:\n"
        + "\n".join(f"  · {h.reason}: {h.snippet!r}" for h in hits)
    )


def test_real_render_empty_data_no_leak() -> None:
    """完全空数据 (只有 pillars + 空 points) 也不应 leak."""
    curves = {"pillars_str": "甲子 乙丑 丙寅 丁卯", "points": []}
    html = render(curves, analysis={}, allow_partial=True)
    hits = scan_placeholder_engineering_leak(html)
    assert hits == [], (
        f"极简数据下 placeholder 区不应有工程内容外泄, 实际命中:\n"
        + "\n".join(f"  · {h.reason}: {h.snippet!r}" for h in hits)
    )


# ─── §4 · 横幅 / coverage / zeitgeist explainer 已注入 ────────

def test_template_has_partial_banner() -> None:
    """模板必须包含 PartialBanner 组件 + IS_PARTIAL 守卫."""
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert "function PartialBanner" in text
    assert 'data-resilience-banner="partial"' in text
    assert "<PartialBanner" in text


def test_template_has_coverage_banner() -> None:
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert "function CoverageBanner" in text
    assert 'data-resilience-banner="coverage"' in text
    assert "<CoverageBanner" in text


def test_template_has_zeitgeist_empty_explain() -> None:
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert "function ZeitgeistEmptyExplain" in text
    assert "<ZeitgeistEmptyExplain" in text
    assert 'data-resilience-fallback="zeitgeist-empty"' in text


def test_render_injects_coverage_payload() -> None:
    """render() 接收 coverage_report 时应注入 payload.coverage."""
    curves = {"pillars_str": "甲子 乙丑 丙寅 丁卯", "points": []}
    cov = {
        "coverage_pct": 25.0,
        "required": ["a", "b", "c", "d"],
        "present": ["a"],
        "missing": ["b", "c", "d"],
        "warnings": [],
    }
    html = render(curves, allow_partial=True, coverage_report=cov)
    # payload 里应有 coverage_pct
    assert '"coverage_pct"' in html
    assert '25' in html


def test_render_no_coverage_omits_payload_field() -> None:
    """不传 coverage → payload.coverage = null, 模板不渲染 banner."""
    curves = {"pillars_str": "甲子 乙丑 丙寅 丁卯", "points": []}
    html = render(curves, allow_partial=True)
    assert '"coverage": null' in html or '"coverage":null' in html


def test_render_includes_generated_at_timestamp() -> None:
    """payload 应包含 generated_at 时间戳, 给 PartialBanner 显示."""
    curves = {"pillars_str": "甲子 乙丑 丙寅 丁卯", "points": []}
    html = render(curves, allow_partial=True)
    assert '"generated_at"' in html
