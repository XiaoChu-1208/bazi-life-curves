#!/usr/bin/env python3
"""render_artifact.py — curves.json (+ analysis.json + zeitgeist.json) → 自包含 HTML

输出可直接塞进 Claude Artifact（type="text/html"）。
浏览器双击即可打开，零构建。

analysis.json 结构（可选；不提供则模板里的 LLM 解读区域显示"待 LLM 写入"）：

{
  "overall": "**整图综合分析**\\n\\nMarkdown 字符串",        // 默认展开
  "life_review": {                                            // v7.5+ · 一生总评 (三维度)
    "spirit": "Markdown 字符串（精神舒畅度一生总评）",
    "wealth": "Markdown 字符串（财富一生总评）",
    "fame":   "Markdown 字符串（名声一生总评）"
  },
  "turning_points": {
    "<year>": "Markdown 字符串（多维取象）",                   // 默认展开
    ...
  },
  "disputes": {
    "<year>": "Markdown 字符串（争议解读）",                   // 默认收起
    ...
  },
  "key_years": [                                              // 关键年份评价
    {"year": 2027, "age": 37, "ganzhi": "丁未", "dayun": "丙寅",
     "kind": "peak", "headline": "...", "body": "Markdown ..."},
    ...
  ],
  "dayun_review": {                                           // 大运 headline (单数)
    "<dayun_label>": {"headline": "...", "body": "Markdown ..."},
    ...
  },
  "dayun_reviews": {                                          // v7.5 · 整篇 6-块 markdown
    "<dayun_label>": "Markdown（10 年大运综合评价 · 6 块结构 · 详见 dayun_review_template.md）",
    ...
  },
  "era_narratives": {                                         // v7.5 · 时代-民俗志区间叙事
    "<era_window_id>": "Markdown（含时代底色 / 标志性细节 / 命局节点 / 累计影响 / 证伪点）",
    ...
  },
  "confirmed_facts": { ... }                                  // 可选 · 来自 confirmed_facts.json
}

zeitgeist.json 结构（可选 · 由 _zeitgeist_loader.py 生成）：
  era_windows_used、alignments、user_dayun_segments 等；模板会按 era_window 横向展示
  时代背景骨架，并把对应 LLM 写好的 era_narratives / dayun_reviews 拼进来。

LLM 完成度审计（v9.1 · 防止"LLM 不写就静默渲染占位符"）：
  render_artifact.py 会检查 analysis.json 里 LLM 应写的关键字段是否齐备。
  - 默认（向后兼容）：在 stderr 打印 [coverage] 警告 + 缺失字段清单
  - --strict-llm：任何 LLM 必填字段缺失时 raise LlmCoverageError，让构建失败
  这是把"LLM 漏写"从前端软渲染变成显式工程信号。
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


# ---- v9.1 · LLM 完成度审计 ---------------------------------------------------

class LlmCoverageError(RuntimeError):
    """LLM 应写未写, --strict-llm 下抛出。"""


# 一份可静态枚举的"必填项"——分两档:
#   required: 任何曲线都必须有 (overall + life_review.*)
#   conditional: 视 curves / zeitgeist 内容决定 (大运 / 关键年 / era_window)
def audit_llm_coverage(curves: dict,
                       analysis: dict | None,
                       zeitgeist: dict | None) -> dict:
    """返回 {required, missing, present, coverage_pct, warnings}.

    必填字段 (LLM 应写而未写视为遗漏):
      - analysis.overall                     1 条
      - analysis.life_review.{spirit,wealth,fame}  3 条
      - analysis.dayun_reviews[<每段大运 label>]   N 条 (按 curves.dayun.segments)
      - analysis.era_narratives[<每个 era_window id>]  M 条 (按 zeitgeist.era_windows_used)
      - analysis.key_years 数组非空          1 条 (>=1 条 key_year)
    """
    analysis = analysis or {}
    zeitgeist = zeitgeist or {}

    required: list[str] = []
    missing: list[str] = []

    def _check(path: str, value) -> None:
        required.append(path)
        if not value:
            missing.append(path)
            return
        if isinstance(value, str) and not value.strip():
            missing.append(path)

    _check("analysis.overall", analysis.get("overall"))

    life = analysis.get("life_review") or {}
    for k in ("spirit", "wealth", "fame"):
        _check(f"analysis.life_review.{k}", life.get(k))

    key_years = analysis.get("key_years") or []
    required.append("analysis.key_years[>=1]")
    if not key_years:
        missing.append("analysis.key_years[>=1]")

    dayun_segments = ((curves.get("dayun") or {}).get("segments") or [])
    dayun_reviews = analysis.get("dayun_reviews") or {}
    dayun_review_legacy = analysis.get("dayun_review") or {}
    for seg in dayun_segments:
        label = seg.get("label")
        if not label:
            continue
        path = f"analysis.dayun_reviews[{label!r}]"
        required.append(path)
        v_new = dayun_reviews.get(label)
        v_old = dayun_review_legacy.get(label)
        # 任一非空即认为已写 (v_old 是旧版 {headline, body} dict, 取 body)
        ok = (isinstance(v_new, str) and v_new.strip()) or (
            isinstance(v_old, dict) and (v_old.get("body") or "").strip()
        )
        if not ok:
            missing.append(path)

    era_windows = zeitgeist.get("era_windows_used") or []
    era_narr = analysis.get("era_narratives") or {}
    for era in era_windows:
        eid = era.get("id")
        if not eid:
            continue
        path = f"analysis.era_narratives[{eid!r}]"
        required.append(path)
        v = era_narr.get(eid)
        if not (isinstance(v, str) and v.strip()):
            missing.append(path)

    present = [p for p in required if p not in missing]
    coverage_pct = round(100.0 * len(present) / len(required), 1) if required else 100.0

    warnings: list[str] = []
    if missing:
        warnings.append(
            f"LLM 解读字段未写满: {len(missing)}/{len(required)} 缺失 "
            f"(覆盖度 {coverage_pct}%)"
        )

    return {
        "required": required,
        "present": present,
        "missing": missing,
        "coverage_pct": coverage_pct,
        "warnings": warnings,
    }


def _print_coverage(report: dict, *, stream=None) -> None:
    # NOTE: 不能在默认参数里写 sys.stderr — 那样会 freeze 模块加载时刻的
    # sys.stderr 引用, 让 pytest capfd / 用户后续 sys.stderr 替换都失效。
    if stream is None:
        stream = sys.stderr
    print(
        f"[coverage] LLM 字段 {len(report['present'])}/{len(report['required'])} "
        f"({report['coverage_pct']}%)",
        file=stream,
    )
    if report["missing"]:
        print("[coverage] 缺失字段:", file=stream)
        for path in report["missing"]:
            print(f"  - {path}", file=stream)


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
    # v9.1 · 注入模板里**所有**实际引用的 ANALYSIS.* 字段;
    # 之前漏掉 life_review / dayun_review / key_years / confirmed_facts → 即使 LLM 写了也不显示。
    return tmpl.render(
        title=f"八字人生曲线图（{curves['pillars_str']}）",
        curves_json=json.dumps(curves, ensure_ascii=False),
        analysis_json=json.dumps({
            "overall": analysis.get("overall", ""),
            "life_review": analysis.get("life_review", {}),
            "turning_points": analysis.get("turning_points", {}),
            "disputes": analysis.get("disputes", {}),
            "key_years": analysis.get("key_years", []),
            "dayun_review": analysis.get("dayun_review", {}),
            "dayun_reviews": analysis.get("dayun_reviews", {}),
            "era_narratives": analysis.get("era_narratives", {}),
            "confirmed_facts": analysis.get("confirmed_facts", {}),
        }, ensure_ascii=False),
        zeitgeist_json=json.dumps(zeitgeist or {}, ensure_ascii=False),
        has_zeitgeist=bool(zeitgeist and zeitgeist.get("era_windows_used")),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curves", required=True)
    ap.add_argument("--analysis", default=None,
                    help="可选：analysis.json 路径（overall / life_review / turning_points / "
                         "disputes / key_years / dayun_review(s) / era_narratives / confirmed_facts）")
    ap.add_argument("--zeitgeist", default=None,
                    help="v7.5 · 可选：zeitgeist.json 路径（_zeitgeist_loader.py --out 的产物）")
    ap.add_argument("--bazi", default=None,
                    help="v7.5 · 可选：bazi.json 路径，用于现场计算 zeitgeist + class_prior（与 --zeitgeist 二选一）")
    ap.add_argument("--out", default="chart.html")
    ap.add_argument("--strict-llm", action="store_true",
                    help="v9.1 · 当 analysis.json 里 LLM 应写未写时, raise LlmCoverageError "
                         "(默认只在 stderr 打 [coverage] 警告)")
    ap.add_argument("--coverage-report", default=None,
                    help="v9.1 · 可选 · 把 LLM 字段覆盖度 JSON 写到该路径")
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

    coverage = audit_llm_coverage(curves, analysis, zeitgeist)
    _print_coverage(coverage)
    if args.coverage_report:
        Path(args.coverage_report).write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.strict_llm and coverage["missing"]:
        raise LlmCoverageError(
            f"LLM 字段未写满 (strict-llm): 缺 {len(coverage['missing'])}/"
            f"{len(coverage['required'])} 项, 覆盖度 {coverage['coverage_pct']}%。"
            f" 缺失: {coverage['missing']}"
        )

    html = render(curves, analysis, zeitgeist)
    Path(args.out).write_text(html, encoding="utf-8")
    n_eras = len((zeitgeist or {}).get("era_windows_used", []))
    print(f"[render_artifact] wrote {args.out} ({len(html)} bytes), "
          f"analysis={'on' if analysis else 'off'}, "
          f"zeitgeist={'on (' + str(n_eras) + ' era_windows)' if n_eras else 'off'}, "
          f"llm_coverage={coverage['coverage_pct']}%")


if __name__ == "__main__":
    main()
