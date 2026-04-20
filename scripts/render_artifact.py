#!/usr/bin/env python3
"""render_artifact.py — curves.json (+ analysis.json + zeitgeist.json) → 自包含 HTML

输出可直接塞进 Claude Artifact（type="text/html"）。
浏览器双击即可打开，零构建。

analysis.json 结构（可选；不提供则模板里的 LLM 解读区域显示"待 LLM 写入"）：

{
  "overall": "**整图综合分析**\\n\\nMarkdown 字符串",        // 默认展开
  "turning_points": {
    "<year>": "Markdown 字符串（多维取象）",                   // 默认展开
    ...
  },
  "disputes": {
    "<year>": "Markdown 字符串（争议解读）",                   // 默认收起
    ...
  },
  // v7.5 新增（时代-民俗志层 · 由 LLM 现场写）：
  "era_narratives": {
    "<era_window_id>": "Markdown（区间叙事 · 含时代底色 / 标志性细节 / 命局节点 / 累计影响 / 证伪点）",
    ...
  },
  "dayun_reviews": {
    "<dayun_label>": "Markdown（10 年大运综合评价 · 6 块结构 · 详见 dayun_review_template.md）",
    ...
  }
}

zeitgeist.json 结构（可选 · 由 _zeitgeist_loader.py 生成）：
  era_windows_used、alignments、user_dayun_segments 等；模板会按 era_window 横向展示
  时代背景骨架，并把对应 LLM 写好的 era_narratives / dayun_reviews 拼进来。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as e:
    raise ImportError("Jinja2 required: pip install Jinja2") from e

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _compute_zeitgeist_from_bazi(bazi_path: str) -> dict | None:
    """v7.5 · 用 _zeitgeist_loader + _class_prior 现场推 zeitgeist。失败返回 None。"""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import _zeitgeist_loader as zl
        import _class_prior as cp
        bazi = json.loads(Path(bazi_path).read_text(encoding="utf-8"))
        ctx = zl.build_zeitgeist_context(bazi)
        ctx["class_prior_internal"] = cp.infer_class_prior(bazi)
        return ctx
    except Exception as e:
        print(f"[render_artifact] WARN: compute zeitgeist failed ({e})", file=sys.stderr)
        return None


def render(curves: dict,
           analysis: dict | None = None,
           zeitgeist: dict | None = None) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("chart_artifact.html.j2")
    analysis = analysis or {}
    return tmpl.render(
        title=f"八字人生曲线图（{curves['pillars_str']}）",
        curves_json=json.dumps(curves, ensure_ascii=False),
        analysis_json=json.dumps({
            "overall": analysis.get("overall", ""),
            "turning_points": analysis.get("turning_points", {}),
            "disputes": analysis.get("disputes", {}),
            "era_narratives": analysis.get("era_narratives", {}),
            "dayun_reviews": analysis.get("dayun_reviews", {}),
        }, ensure_ascii=False),
        zeitgeist_json=json.dumps(zeitgeist or {}, ensure_ascii=False),
        has_zeitgeist=bool(zeitgeist and zeitgeist.get("era_windows_used")),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curves", required=True)
    ap.add_argument("--analysis", default=None,
                    help="可选：analysis.json 路径（overall / turning_points / disputes / "
                         "era_narratives / dayun_reviews）")
    ap.add_argument("--zeitgeist", default=None,
                    help="v7.5 · 可选：zeitgeist.json 路径（_zeitgeist_loader.py --out 的产物）")
    ap.add_argument("--bazi", default=None,
                    help="v7.5 · 可选：bazi.json 路径，用于现场计算 zeitgeist + class_prior（与 --zeitgeist 二选一）")
    ap.add_argument("--out", default="chart.html")
    args = ap.parse_args()
    curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))
    analysis = None
    if args.analysis:
        analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))

    zeitgeist = None
    if args.zeitgeist:
        zeitgeist = json.loads(Path(args.zeitgeist).read_text(encoding="utf-8"))
    elif args.bazi:
        zeitgeist = _compute_zeitgeist_from_bazi(args.bazi)

    html = render(curves, analysis, zeitgeist)
    Path(args.out).write_text(html, encoding="utf-8")
    n_eras = len((zeitgeist or {}).get("era_windows_used", []))
    print(f"[render_artifact] wrote {args.out} ({len(html)} bytes), "
          f"analysis={'on' if analysis else 'off'}, "
          f"zeitgeist={'on (' + str(n_eras) + ' era_windows)' if n_eras else 'off'}")


if __name__ == "__main__":
    main()
