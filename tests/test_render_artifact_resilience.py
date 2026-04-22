"""v9.3.1 · render_artifact 残缺数据 resilience 测试.

修复 4 条 P0 崩溃路径 (Bug 3 / 4 / 6 / 12):
  - curves.points 缺失 / null / 空 → 模板必须走 NoChartFallback, 不抛错
  - curves.yongshen / strength 缺失 → 模板首屏 meta 用兜底 '—', 不抛错
  - 任意 React 子树抛错 → 顶层 ErrorBoundary 渲染可读错误卡片, 不留空 #app
  - render_artifact.validate_curves_min_schema: 非 partial 缺关键字段 → CurvesSchemaError;
    partial 模式吞掉走 warnings + 模板兜底.

注意: 这是模板字符串级测试 (检查输出 HTML 含特定 marker),
不依赖浏览器跑 React. 真正 React 崩溃路径靠 ErrorBoundary 注入的
data-resilience-fallback="error-boundary" + componentDidCatch 防御.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from render_artifact import (  # noqa: E402
    CurvesSchemaError,
    render,
    validate_curves_min_schema,
)


# ─── fixtures ───────────────────────────────────────────────────

def _ok_curves() -> dict:
    return {
        "version": 9,
        "pillars_str": "庚午 辛巳 壬子 丁未",
        "day_master": "壬",
        "birth_year": 1990,
        "baseline": {"spirit": 50, "wealth": 50, "fame": 50, "emotion": 50},
        "points": [
            {"age": 10, "year": 2000, "dayun": "戊辰",
             "spirit_yearly": 55.0, "wealth_yearly": 50.0,
             "fame_yearly": 48.0, "emotion_yearly": 52.0},
            {"age": 11, "year": 2001, "dayun": "戊辰",
             "spirit_yearly": 56.0, "wealth_yearly": 51.0,
             "fame_yearly": 49.0, "emotion_yearly": 52.0},
        ],
        "yongshen": {"yongshen": "甲", "season": "夏", "tongguan": "丙"},
        "strength": {"label": "中和"},
        "dayun_segments": [
            {"label": "戊辰", "start_age": 5, "end_age": 14,
             "start_year": 1995, "end_year": 2004},
        ],
    }


# ─── §1 · validate_curves_min_schema (脚本侧) ──────────────────

def test_schema_ok_no_warnings() -> None:
    """完整 curves → 无警告无错."""
    warnings = validate_curves_min_schema(_ok_curves(), allow_partial=False)
    assert warnings == []


def test_schema_missing_required_strict_raises() -> None:
    """非 partial + 缺 points → CurvesSchemaError."""
    bad = _ok_curves()
    del bad["points"]
    with pytest.raises(CurvesSchemaError) as exc:
        validate_curves_min_schema(bad, allow_partial=False)
    assert "points" in str(exc.value)


def test_schema_missing_required_partial_warns() -> None:
    """partial 模式 + 缺 points → 不 raise, 返回 warning."""
    bad = _ok_curves()
    del bad["points"]
    warnings = validate_curves_min_schema(bad, allow_partial=True)
    assert any("points" in w for w in warnings), warnings


def test_schema_points_wrong_type_raises() -> None:
    """points: dict (不是 list/null) → 即使 partial 也警告或 raise."""
    bad = _ok_curves()
    bad["points"] = {"oops": "not a list"}
    with pytest.raises(CurvesSchemaError):
        validate_curves_min_schema(bad, allow_partial=False)


def test_schema_points_null_ok_with_partial() -> None:
    """points: null + partial → 不 raise (流式早期常态)."""
    bad = _ok_curves()
    bad["points"] = None
    warnings = validate_curves_min_schema(bad, allow_partial=True)
    # null 不算 invalid, 但 _CURVES_REQUIRED_TOP_LEVEL 仍要求 key 存在 → 这里 key 在
    assert isinstance(warnings, list)


def test_schema_curves_not_dict() -> None:
    """curves 完全不是 dict → 非 partial 必 raise."""
    with pytest.raises(CurvesSchemaError):
        validate_curves_min_schema("not a dict", allow_partial=False)
    warnings = validate_curves_min_schema("not a dict", allow_partial=True)
    assert any("dict" in w for w in warnings)


def test_schema_missing_expected_just_warns() -> None:
    """缺 yongshen / strength 等扩展字段 → 即使非 partial 也只是 warning."""
    bad = _ok_curves()
    del bad["yongshen"]
    del bad["strength"]
    warnings = validate_curves_min_schema(bad, allow_partial=False)
    assert any("yongshen" in w or "strength" in w for w in warnings)


# ─── §2 · render() 不崩 + HTML 含 fallback marker ──────────────

def test_render_full_data_no_fallback_markers() -> None:
    """完整数据 → HTML 含 NoChartFallback 类名 (因 hasChartData=true 故运行时不展示),
    不出现 ErrorBoundary triggered marker."""
    html = render(_ok_curves(), allow_partial=False)
    assert "<html" in html.lower()
    # ErrorBoundary 组件存在但未触发, 故不应该有 data-resilience-fallback="error-boundary" 实例
    # 不过 class 定义 / 函数定义会在 script 里, 所以单 NoChartFallback 字串会在
    assert "NoChartFallback" in html
    assert "ErrorBoundary" in html


def test_render_empty_points_partial_returns_html() -> None:
    """points: [] + partial → render 不抛错; HTML 含 NoChartFallback 渲染分支."""
    bad = _ok_curves()
    bad["points"] = []
    html = render(bad, allow_partial=True)
    # NoChartFallback 组件代码在 + chart-wrap 分支被 hasChartData 守卫
    assert "NoChartFallback" in html
    assert "no-chart-fallback" in html  # CSS class / data-resilience-fallback marker


def test_render_missing_yongshen_partial_returns_html() -> None:
    """缺 yongshen → 模板首屏 meta 用 || '—' 兜底, render 不抛错."""
    bad = _ok_curves()
    del bad["yongshen"]
    html = render(bad, allow_partial=True)
    assert "<html" in html.lower()
    # 用神字段不应该出现 (因为 yongshen 整个对象缺失就不渲染)
    # 但其它 meta 仍正常
    assert "日主" in html


def test_render_missing_strength_partial_returns_html() -> None:
    """缺 strength → meta 显示 '—' 而不是 TypeError."""
    bad = _ok_curves()
    del bad["strength"]
    html = render(bad, allow_partial=True)
    assert "<html" in html.lower()


def test_render_missing_pillars_str_partial_uses_default_title() -> None:
    """缺 pillars_str + partial → render 不抛 KeyError, 用默认标题."""
    bad = _ok_curves()
    del bad["pillars_str"]
    html = render(bad, allow_partial=True)
    assert "八字人生曲线图" in html


def test_render_minimal_curves_partial() -> None:
    """极简 curves (只有 pillars_str + points: []) + partial → 模板能 render."""
    minimal = {"pillars_str": "庚午 辛巳 壬子 丁未", "points": []}
    html = render(minimal, allow_partial=True)
    assert "<html" in html.lower()
    assert "NoChartFallback" in html


# ─── §3 · ErrorBoundary 已注入到模板 ────────────────────────

def test_template_has_error_boundary_class() -> None:
    """模板必须包含 ErrorBoundary 类定义 + 顶层包裹."""
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert "class ErrorBoundary extends React.Component" in text
    assert "componentDidCatch" in text
    # 顶层 render 必须用 ErrorBoundary 包 App
    assert "<ErrorBoundary>" in text
    assert "<App />" in text
    # data-resilience-fallback marker 给 e2e 测试用
    assert 'data-resilience-fallback="error-boundary"' in text


def test_template_has_no_chart_fallback() -> None:
    """模板必须包含 NoChartFallback 兜底 + hasChartData 守卫."""
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert "function NoChartFallback" in text
    assert "hasChartData" in text
    assert 'data-resilience-fallback="no-chart"' in text


def test_template_curves_default_empty_dict() -> None:
    """模板 module top: CURVES = window.__BAZI_CURVES__ || {} (防 null)."""
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert "window.__BAZI_CURVES__ || {}" in text


def test_template_meta_uses_optional_chains() -> None:
    """首屏 meta 必须避免 CURVES.x.y 裸链, 改成 (CURVES.x && CURVES.x.y) 守卫.

    检查策略: 守卫表达式存在 + 旧的纯直链 (无短路) 不再以 unguarded 形式出现.
    """
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    # 旧的脆弱直链 (放在 meta 顶层无守卫) 已剥离
    assert "{CURVES.strength.label}" not in text, "首屏 meta 仍含脆弱直链 CURVES.strength.label"
    # 必须出现守卫表达式 (允许守卫之后的安全引用)
    assert "(CURVES.strength && CURVES.strength.label)" in text, (
        "首屏 meta 缺 (CURVES.strength && CURVES.strength.label) 守卫"
    )
    assert "(CURVES.yongshen && CURVES.yongshen.yongshen)" in text, (
        "首屏 meta 缺 (CURVES.yongshen && CURVES.yongshen.yongshen) 守卫"
    )


# ─── §4 · render() + buildSeries 空数组路径 (回归) ──────────

def test_render_curves_with_only_pillars_no_crash() -> None:
    """流式最早期 (curves 只有 pillars + 空 points) 应能渲染."""
    curves = {"pillars_str": "甲子 乙丑 丙寅 丁卯", "points": []}
    html = render(curves, analysis={}, allow_partial=True)
    assert "<html" in html.lower()
    assert "NoChartFallback" in html


# ─── §5 · 注入安全 (Bug 2 / 5) ─────────────────────────────────

def test_safe_json_escapes_script_close_tag() -> None:
    """v9.3.1 · 数据里含 '</script>' 字串 → escape 成 '\\u003c/script>',
    HTML 里物理消失这个 token, 浏览器不会提前关闭 script tag."""
    from render_artifact import _safe_json

    payload = {"text": "</script><svg/onload=alert(1)>"}
    out = _safe_json(payload)
    assert "</script>" not in out
    assert "\\u003c" in out


def test_render_payload_no_script_close_tag_in_data_block() -> None:
    """JSON 块里即使 LLM 写了 '</script>' 也不会泄漏成 raw close tag."""
    curves = _ok_curves()
    analysis = {
        "overall": "测试 </script><img src=x onerror=alert(1)> 注入",
        "life_review": {"spirit": "</script>", "wealth": "", "fame": "", "emotion": ""},
    }
    html = render(curves, analysis, allow_partial=True)
    # data 块用 application/json + escape '<', '</script>' 在 raw 数据段不应出现
    # (模板里 <script type="application/json"> 之外的 vanilla JS 不会包含这个串)
    # 抽出 <script type="application/json"> ... </script> 之间的内容验证
    import re
    m = re.search(
        r'<script type="application/json"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert m, "缺 application/json data 块"
    data_block = m.group(1)
    assert "</script>" not in data_block, (
        "JSON 数据块里仍有 raw '</script>' close tag, 注入面未关闭"
    )
    assert "\\u003c/script>" in data_block, (
        "'</script>' 应被 escape 成 '\\u003c/script>' 而不是物理删除"
    )


def test_render_payload_escapes_html_comment_open() -> None:
    """JSON 数据里含 '<!--' → escape 成 '\\u003c!--',
    防止 IE/老浏览器把 script 内容当 HTML 注释吞掉."""
    curves = _ok_curves()
    analysis = {"overall": "<!-- evil --><script>alert(1)</script>"}
    html = render(curves, analysis, allow_partial=True)
    import re
    m = re.search(
        r'<script type="application/json"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    )
    assert m
    data_block = m.group(1)
    assert "<!--" not in data_block
    assert "<script>" not in data_block


def test_template_marked_html_renderer_disabled() -> None:
    """模板必须配置 marked 关闭 raw HTML 透传."""
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    # 关 raw HTML
    assert "configureMarked" in text
    assert "renderer:" in text
    # 过滤 javascript: 链接
    assert "javascript:" in text
    assert "walkTokens" in text


def test_template_uses_application_json_data_block() -> None:
    """模板必须用 <script type='application/json'> 而不是 inline <script>{...}</script>."""
    template_path = ROOT / "templates" / "chart_artifact.html.j2"
    text = template_path.read_text(encoding="utf-8")
    assert 'type="application/json"' in text
    assert 'id="__bazi_data__"' in text
    # 旧的 inline 注入语句 (window.__BAZI_X__ = {{ ... }}) 应已迁移
    # window.__BAZI_X__ = ... 仍存在, 但应是 IIFE 里从 JSON.parse 得到, 不应再有 Jinja {{ }}
    assert "{{ curves_json" not in text
    assert "{{ analysis_json" not in text


def test_render_only_one_data_script_block() -> None:
    """即使 LLM 数据里塞了多个 '</script>' 字符串, 模板里 application/json 块仍只有 1 个."""
    curves = _ok_curves()
    analysis = {
        "overall": "</script></script></script>",
        "life_review": {
            "spirit": "</script>", "wealth": "</script>",
            "fame": "</script>", "emotion": "</script>",
        },
    }
    html = render(curves, analysis, allow_partial=True)
    # application/json 块只有 1 个
    import re
    json_blocks = re.findall(
        r'<script type="application/json"[^>]*>',
        html,
    )
    assert len(json_blocks) == 1, f"data script 块数量应为 1, 实际 {len(json_blocks)}"


def test_safe_json_escapes_line_separators() -> None:
    """U+2028 / U+2029 在老 JS 引擎里会被当作行终止符把 JSON 切断."""
    from render_artifact import _safe_json
    out = _safe_json({"text": "a\u2028b\u2029c"})
    assert "\u2028" not in out
    assert "\u2029" not in out
    assert "\\u2028" in out
    assert "\\u2029" in out
