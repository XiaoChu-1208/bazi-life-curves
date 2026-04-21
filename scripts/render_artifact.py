#!/usr/bin/env python3
"""render_artifact.py — curves.json (+ analysis.json + zeitgeist.json) → 自包含 HTML

输出可直接塞进 Claude Artifact（type="text/html"）。
浏览器双击即可打开，零构建。

analysis.json 结构（可选；不提供则模板里的 LLM 解读区域显示"待 LLM 写入"）：

{
  "overall": "**整图综合分析**\\n\\nMarkdown 字符串",        // 默认展开
  "life_review": {                                            // v9 · 一生总评 (四维度)
    "spirit":  "Markdown 字符串（精神舒畅度一生总评）",
    "wealth":  "Markdown 字符串（财富一生总评）",
    "fame":    "Markdown 字符串（名声一生总评）",
    "emotion": "Markdown 字符串（感情/关系一生总评 · v9 新增）"
  },
  "virtue_narrative": {                                       // v9 · 承认维度（德性暗线）独立通道
    "opening":           "Markdown · 位置① 开篇悬疑提示（life_review 起笔即写）",
    "convergence_notes": "Markdown · 位置③ 母题汇聚总览",
    "declaration":       "Markdown · 位置④ 灵魂宣言（一生评价收尾）",
    "love_letter":       "Markdown · 位置⑤ 情书（仅 motifs.love_letter_eligible 时写）",
    "free_speech":       "Markdown · 位置⑥ LLM 自由话"
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
                       zeitgeist: dict | None,
                       virtue_motifs: dict | None = None) -> dict:
    """返回 {required, missing, present, coverage_pct, warnings}.

    必填字段 (LLM 应写而未写视为遗漏):
      - analysis.overall                     1 条
      - analysis.life_review.{spirit,wealth,fame,emotion}  4 条 (v9 加 emotion)
      - analysis.virtue_narrative.{opening,declaration,free_speech}  3 条 (v9 承认维度)
        + love_letter 仅在 virtue_motifs.love_letter_eligible=true 时必填
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
    for k in ("spirit", "wealth", "fame", "emotion"):
        _check(f"analysis.life_review.{k}", life.get(k))

    # v9 · 承认维度（德性暗线）必填三件套：开篇悬疑 + 灵魂宣言 + 自由话；
    # love_letter 仅在 virtue_motifs.love_letter_eligible=true 时才必填。
    virtue = analysis.get("virtue_narrative") or {}
    for k in ("opening", "declaration", "free_speech"):
        _check(f"analysis.virtue_narrative.{k}", virtue.get(k))
    if isinstance(virtue_motifs, dict) and virtue_motifs.get("love_letter_eligible"):
        _check("analysis.virtue_narrative.love_letter", virtue.get("love_letter"))
    if isinstance(virtue_motifs, dict) and (virtue_motifs.get("convergence_years") or []):
        _check("analysis.virtue_narrative.convergence_notes", virtue.get("convergence_notes"))

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
    if virtue_motifs is None:
        warnings.append(
            "未注入 virtue_motifs.json — 承认维度（德性暗线）骨架缺失。"
            "请先跑 `python scripts/virtue_motifs.py --bazi ... --curves ... --out ...`，"
            "再用 `--virtue-motifs <path>` 重渲染（否则 HTML 上承认卡片只能写空话）。"
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
    for w in report.get("warnings", []):
        # missing 已在上面打过；这里只补打非 missing 类的（如 virtue_motifs 未启用）
        if w.startswith("LLM 解读字段未写满"):
            continue
        print(f"[coverage] {w}", file=stream)


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
           zeitgeist: dict | None = None,
           virtue_motifs: dict | None = None,
           allow_partial: bool = False) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("chart_artifact.html.j2")
    analysis = analysis or {}
    # v9.1 · 注入模板里**所有**实际引用的 ANALYSIS.* 字段;
    # 之前漏掉 life_review / dayun_review / key_years / confirmed_facts → 即使 LLM 写了也不显示。
    # v9.2 · virtue_narrative + virtue_motifs（承认维度独立通道，不画曲线）+ allow_partial（流式部分渲染）
    return tmpl.render(
        title=f"八字人生曲线图（{curves['pillars_str']}）",
        curves_json=json.dumps(curves, ensure_ascii=False),
        analysis_json=json.dumps({
            "overall": analysis.get("overall", ""),
            "life_review": analysis.get("life_review", {}),
            "virtue_narrative": analysis.get("virtue_narrative", {}),
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
        virtue_motifs_json=json.dumps(virtue_motifs, ensure_ascii=False) if virtue_motifs is not None else "null",
        has_virtue_motifs=bool(virtue_motifs),
        allow_partial=bool(allow_partial),
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
    ap.add_argument("--virtue-motifs", default=None,
                    help="v9 · 可选：virtue_motifs.json 路径（scripts/virtue_motifs.py 产物）。"
                         "缺失时 HTML 上承认维度卡片会显示「未启用」提示，并禁用 love_letter 必填。")
    ap.add_argument("--out", default="chart.html")
    ap.add_argument("--strict-llm", action="store_true",
                    help="v9.1 · 当 analysis.json 里 LLM 应写未写时, raise LlmCoverageError "
                         "(默认只在 stderr 打 [coverage] 警告)")
    ap.add_argument("--allow-partial", action="store_true",
                    help="v9.2 · 流式渲染模式：缺字段时显示「⌛ 流式写作中」占位，不抛错也不算 fail。"
                         "用于 agent 边写边刷 HTML 看进度（最终产物仍要去掉此 flag 跑覆盖率审计）。")
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

    virtue_motifs = None
    if args.virtue_motifs:
        virtue_motifs = json.loads(Path(args.virtue_motifs).read_text(encoding="utf-8"))

    coverage = audit_llm_coverage(curves, analysis, zeitgeist, virtue_motifs)
    _print_coverage(coverage)
    if args.coverage_report:
        Path(args.coverage_report).write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.strict_llm and coverage["missing"] and not args.allow_partial:
        raise LlmCoverageError(
            f"LLM 字段未写满 (strict-llm): 缺 {len(coverage['missing'])}/"
            f"{len(coverage['required'])} 项, 覆盖度 {coverage['coverage_pct']}%。"
            f" 缺失: {coverage['missing']}"
        )

    html = render(curves, analysis, zeitgeist, virtue_motifs, allow_partial=args.allow_partial)
    Path(args.out).write_text(html, encoding="utf-8")
    n_eras = len((zeitgeist or {}).get("era_windows_used", []))
    print(f"[render_artifact] wrote {args.out} ({len(html)} bytes), "
          f"analysis={'on' if analysis else 'off'}, "
          f"zeitgeist={'on (' + str(n_eras) + ' era_windows)' if n_eras else 'off'}, "
          f"virtue_motifs={'on' if virtue_motifs else 'off'}, "
          f"partial={'on' if args.allow_partial else 'off'}, "
          f"llm_coverage={coverage['coverage_pct']}%")


if __name__ == "__main__":
    main()
