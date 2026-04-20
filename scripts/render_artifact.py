#!/usr/bin/env python3
"""render_artifact.py — curves.json (+ analysis.json) → 自包含 HTML

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
  }
}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError as e:
    raise ImportError("Jinja2 required: pip install Jinja2") from e

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def render(curves: dict, analysis: dict | None = None) -> str:
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
        }, ensure_ascii=False),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curves", required=True)
    ap.add_argument("--analysis", default=None,
                    help="可选：analysis.json 路径，包含 overall / turning_points / disputes 三段 markdown")
    ap.add_argument("--out", default="chart.html")
    args = ap.parse_args()
    curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))
    analysis = None
    if args.analysis:
        analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    html = render(curves, analysis)
    Path(args.out).write_text(html, encoding="utf-8")
    print(f"[render_artifact] wrote {args.out} ({len(html)} bytes), "
          f"analysis={'on' if analysis else 'off'}")


if __name__ == "__main__":
    main()
