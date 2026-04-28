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


class CurvesSchemaError(RuntimeError):
    """v9.3.1 · curves.json 关键字段缺失/类型不对; 非 partial 模式下抛出。

    与模板 resilience guard 互补:
      - 模板侧: 缺字段时降级到 NoChartFallback / meta 兜底, 不再白屏
      - 脚本侧: 非 partial 时直接 raise, 让 CI / 构建发现源头问题
        (partial 模式 / agent 流式中间产物则吞掉走模板兜底)
    """


# 必须存在 (任意分发版都不能缺) 的最小 schema, 模板访问这些字段会进 critical path
_CURVES_REQUIRED_TOP_LEVEL: tuple[str, ...] = (
    "pillars_str",
    "points",
)

# 期望存在 (缺时会触发模板兜底, 但不会白屏) 的扩展字段, 仅打 warning
_CURVES_EXPECTED_TOP_LEVEL: tuple[str, ...] = (
    "day_master",
    "birth_year",
    "baseline",
    "dayun_segments",
    "yongshen",
    "strength",
)


def validate_curves_min_schema(curves: dict, *, allow_partial: bool) -> list[str]:
    """v9.3.1 · 渲染前校验 curves 最小 schema; 缺关键字段且非 partial → raise.

    返回 warnings 列表 (即使没 raise 也可能有 expected 字段缺失). 调用方负责 print.
    """
    warnings: list[str] = []
    if not isinstance(curves, dict):
        if allow_partial:
            warnings.append(
                "curves 不是 dict (partial 模式吞掉, 模板会走 NoChartFallback)"
            )
            return warnings
        raise CurvesSchemaError(
            f"curves 必须是 dict, 实际是 {type(curves).__name__}"
        )

    missing_required = [k for k in _CURVES_REQUIRED_TOP_LEVEL if k not in curves]
    points = curves.get("points")
    points_invalid = (
        "points" in curves
        and points is not None
        and not isinstance(points, list)
    )

    if missing_required or points_invalid:
        msg_parts = []
        if missing_required:
            msg_parts.append(f"缺必填字段: {missing_required}")
        if points_invalid:
            msg_parts.append(f"points 必须是 list 或 null, 实际 {type(points).__name__}")
        msg = "curves schema 不合规: " + "; ".join(msg_parts)
        if allow_partial:
            warnings.append(msg + " (partial 模式吞掉, 模板会走 NoChartFallback)")
        else:
            raise CurvesSchemaError(
                msg + "\n  · 模板会走 NoChartFallback 不白屏, 但分发版前请补齐源数据.\n"
                "  · 若是 agent 流式中间产物, 加 --allow-partial 跳过本检查."
            )

    missing_expected = [k for k in _CURVES_EXPECTED_TOP_LEVEL if k not in curves]
    if missing_expected:
        warnings.append(
            f"curves 缺扩展字段 {missing_expected} (模板会走兜底显示 '—', 不影响渲染)"
        )

    return warnings


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


def _safe_json(obj) -> str:
    """v9.3.1 · 把对象序列化为可安全嵌入 HTML <script type="application/json"> 的 JSON.

    防御点:
      - replace '<' → '\\u003c': 让 '</script>' / '<!--' / '<script>' 在 raw text
        模式下都不会提前终止 script tag (这是 OWASP / Django mark_safe_lazy 同款手法)
      - replace U+2028 / U+2029: 老 JS 引擎里这两个会被当作行终止符把 JSON 切断
    """
    return (
        json.dumps(obj, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render(curves: dict,
           analysis: dict | None = None,
           zeitgeist: dict | None = None,
           virtue_motifs: dict | None = None,
           allow_partial: bool = False,
           coverage_report: dict | None = None) -> str:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    tmpl = env.get_template("chart_artifact.html.j2")
    analysis = analysis or {}
    # v9.1 · 注入模板里**所有**实际引用的 ANALYSIS.* 字段;
    # 之前漏掉 life_review / dayun_review / key_years / confirmed_facts → 即使 LLM 写了也不显示。
    # v9.2 · virtue_narrative + virtue_motifs（承认维度独立通道，不画曲线）+ allow_partial（流式部分渲染）
    # v9.3.1 · partial 模式可能缺 pillars_str, 走兜底而不是 KeyError 炸掉
    # v9.3.1 · 安全加固: 全部 JSON 数据合并到单个 <script type="application/json">
    # 块, 用 _safe_json escape '<', 物理消除 `</script>` 注入面.
    pillars_str = curves.get("pillars_str") if isinstance(curves, dict) else None
    title = f"八字人生曲线图（{pillars_str}）" if pillars_str else "八字人生曲线图"
    # v9.3.1 · coverage 注入到模板, 让 CoverageBanner 透明展示哪些字段没写
    coverage_payload = None
    if isinstance(coverage_report, dict):
        coverage_payload = {
            "coverage_pct": coverage_report.get("coverage_pct"),
            "required": coverage_report.get("required") or [],
            "present": coverage_report.get("present") or [],
            "missing": coverage_report.get("missing") or [],
            "warnings": coverage_report.get("warnings") or [],
        }

    from datetime import datetime, timezone
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    payload = {
        "title": title,
        "generated_at": generated_at,
        "curves": curves,
        "analysis": {
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
            # v9.4 · 母题侧记独立节点（每个 anchor 一段 80-200 字第三人称累加叙事）
            "motif_witness": analysis.get("motif_witness", {}),
        },
        "zeitgeist": zeitgeist or {},
        "has_zeitgeist": bool(zeitgeist and zeitgeist.get("era_windows_used")),
        "virtue_motifs": virtue_motifs,
        "has_virtue_motifs": bool(virtue_motifs),
        "partial": bool(allow_partial),
        "coverage": coverage_payload,
    }
    return tmpl.render(
        title=title,
        bazi_payload_json=_safe_json(payload),
        allow_partial=bool(allow_partial),
    )


def _run_v9_audits(args, analysis, virtue_motifs) -> None:
    """v9 strict audit 串：任一 fail → SystemExit（exit code 与 audit 子脚本一致）。

    所有 audit 都默认开；用户可通过 --no-<flag> 单独关掉。
    """
    import subprocess as _sp
    scripts_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(scripts_dir))

    # 1) require-streamed-emit + required-node-order：扫 analysis._stream_log
    if (args.require_streamed_emit or args.required_node_order) and analysis is not None:
        log = analysis.get("_stream_log") or []
        if args.require_streamed_emit:
            _enforce_streamed_emit(log)
        if args.required_node_order:
            _enforce_node_order(log)

    # 2) audit-closing-headers：扫 declaration / love_letter / free_speech 首行
    if args.audit_closing_headers and analysis is not None:
        try:
            from _v9_guard import enforce_closing_header  # type: ignore
        except ImportError as e:
            raise SystemExit(f"[render_artifact] 找不到 _v9_guard: {e}")
        vn = analysis.get("virtue_narrative") or {}
        for node_key in ("declaration", "love_letter", "free_speech"):
            md = vn.get(node_key) or ""
            if md:
                enforce_closing_header(node_key, md)

    # 3) audit-virtue-continuity：调用子脚本
    if args.audit_virtue_continuity and args.analysis and args.virtue_motifs:
        rc = _sp.call([
            sys.executable,
            str(scripts_dir / "audit_virtue_recurrence_continuity.py"),
            "--analysis", args.analysis,
            "--virtue-motifs", args.virtue_motifs,
        ])
        if rc != 0:
            raise SystemExit(rc)

    # 4) audit-mangpai-surface：调用子脚本
    if args.audit_mangpai_surface and args.analysis and args.mangpai:
        cmd = [
            sys.executable,
            str(scripts_dir / "audit_mangpai_surface.py"),
            "--mangpai", args.mangpai,
            "--analysis", args.analysis,
        ]
        # v9 · 把 bazi 传过去，让 audit 同时检查 phase_decision.mangpai_conflict_alert
        if args.bazi:
            cmd += ["--bazi", args.bazi]
        rc = _sp.call(cmd)
        if rc != 0:
            raise SystemExit(rc)

    # 5) audit-no-premature-decision：调用子脚本（需要 --bazi）
    if args.audit_no_premature_decision and args.bazi:
        rc = _sp.call([
            sys.executable,
            str(scripts_dir / "audit_no_premature_decision.py"),
            "--bazi", args.bazi,
        ])
        if rc != 0:
            raise SystemExit(rc)

    # 7) audit-motif-witness-cumulative (v9.4)：累加性
    if (
        getattr(args, "audit_motif_witness_cumulative", False)
        and analysis is not None
    ):
        _audit_motif_witness_cumulative(analysis, virtue_motifs)

    # 8) audit-no-motif-id-leak (v9.4 R-MOTIF-1) + canonical label leak (R-MOTIF-2)
    if (
        getattr(args, "audit_no_motif_id_leak", False)
        and analysis is not None
        and virtue_motifs
    ):
        _audit_no_motif_label_leak(analysis, virtue_motifs)

    # 9) audit-paraphrase-diversity (v9.4 R-MOTIF-3)
    if (
        getattr(args, "audit_paraphrase_diversity", False)
        and analysis is not None
    ):
        _audit_paraphrase_diversity(analysis)

    # 6) audit-stream-batching (v9.3 R-STREAM-1)：扫 analysis._stream_violations
    if args.audit_stream_batching and analysis is not None:
        violations = analysis.get("_stream_violations") or []
        if isinstance(violations, list) and len(violations) > 0:
            print(
                f"[render_artifact] R-STREAM-1 违规：检测到 {len(violations)} 条同一 "
                f"agent_turn_id 内连续 append（应每节 send 后 stop turn）：",
                file=sys.stderr,
            )
            for v in violations[:10]:
                if not isinstance(v, dict):
                    continue
                print(
                    f"  · turn={v.get('agent_turn_id')!r}  prev={v.get('prev_node')!r}  "
                    f"current={v.get('current_node')!r}  ts={v.get('ts_iso')}",
                    file=sys.stderr,
                )
            print(
                "  · v9.3 流式协议要求：写完一节立刻 send，stop turn，让下一条 turn 再写下一节。\n"
                "  · 详见 AGENTS.md §v9 流式铁律 R-STREAM-1。",
                file=sys.stderr,
            )
            raise SystemExit(11)


def _iter_narrative_fields(analysis: dict):
    """yield (node_label, text) 遍历 analysis 内**所有** narrative markdown 字段。"""
    if not isinstance(analysis, dict):
        return
    overall = analysis.get("overall")
    if isinstance(overall, str) and overall.strip():
        yield ("analysis.overall", overall)
    for k, v in (analysis.get("life_review") or {}).items():
        if isinstance(v, str) and v.strip():
            yield (f"analysis.life_review.{k}", v)
    for k, v in (analysis.get("virtue_narrative") or {}).items():
        if isinstance(v, str) and v.strip():
            yield (f"analysis.virtue_narrative.{k}", v)
    for k, v in (analysis.get("dayun_reviews") or {}).items():
        if isinstance(v, str) and v.strip():
            yield (f"analysis.dayun_reviews[{k}]", v)
    for k, v in (analysis.get("era_narratives") or {}).items():
        if isinstance(v, str) and v.strip():
            yield (f"analysis.era_narratives[{k}]", v)
    for k, v in (analysis.get("motif_witness") or {}).items():
        if isinstance(v, str) and v.strip():
            yield (f"analysis.motif_witness[{k}]", v)
    for i, ky in enumerate(analysis.get("key_years") or []):
        if isinstance(ky, dict):
            body = ky.get("body")
            if isinstance(body, str) and body.strip():
                yield (f"analysis.key_years[{i}].body", body)
    for year, v in (analysis.get("liunian") or {}).items():
        if isinstance(v, str) and v.strip():
            yield (f"analysis.liunian[{year}]", v)


def _audit_motif_witness_cumulative(analysis: dict, virtue_motifs: dict | None) -> None:
    """v9.4 · 检查 motif_witness 累加性：第 ≥2 个 anchor 必须呼应之前 anchor 的母题关键词。

    简化判定：从前序 anchor 的文本中抽取与触发母题相关的"标志短语"（基于
    paraphrase_seeds 的 6-字片段），新 anchor 必须命中至少 1 个，否则报警。
    若 virtue_motifs 未提供 paraphrase_seeds，则降级为：要求新 anchor 与之前 anchor
    的字符 n-gram Jaccard 相似度 ≥ 0.05（极宽松，仅防"完全无关"）。
    """
    mw = analysis.get("motif_witness") or {}
    if not isinstance(mw, dict) or len(mw) < 2:
        return
    # 按写入顺序近似为 dict 插入顺序（Python 3.7+ 保序）
    anchors = list(mw.keys())
    triggered = (virtue_motifs or {}).get("triggered_motifs") or []
    seed_phrases: list[str] = []
    for m in triggered:
        for s in (m.get("paraphrase_seeds") or []) if isinstance(m, dict) else []:
            if isinstance(s, str) and len(s) >= 6:
                seed_phrases.append(s)

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from _v9_guard import _normalized_jaccard  # type: ignore
    except ImportError:
        _normalized_jaccard = None  # type: ignore

    def _has_echo(curr_text: str, prev_text: str) -> bool:
        if seed_phrases:
            # 只要有任一 seed 的 ≥6 字 chunk 同时出现在 prev 与 curr，即视为"呼应了同一母题"
            for seed in seed_phrases:
                for i in range(0, len(seed) - 5):
                    chunk = seed[i:i + 6]
                    if chunk in prev_text and chunk in curr_text:
                        return True
            return False
        if _normalized_jaccard:
            return _normalized_jaccard(curr_text, prev_text) >= 0.05
        return True  # 没有判据时不阻断

    fail = []
    for i in range(1, len(anchors)):
        curr_anchor = anchors[i]
        curr_text = mw.get(curr_anchor) or ""
        if not curr_text.strip():
            continue
        prev_blob = "\n".join(mw.get(a) or "" for a in anchors[:i])
        if not _has_echo(curr_text, prev_blob):
            fail.append((curr_anchor, anchors[:i]))

    if fail:
        print(
            "[render_artifact] R-MOTIF-WITNESS-CUMULATIVE 违规：以下 anchor 未呼应之前 anchor 的母题：",
            file=sys.stderr,
        )
        for curr, priors in fail:
            print(f"  · {curr!r} 未呼应 {priors}", file=sys.stderr)
        print(
            "  · v9.4 motif_witness 铁律：每段必须显式呼应之前 anchor 已写过的母题，"
            "命主才能感受到 fate master 的累加凝视。\n"
            "  · 详见 references/virtue_recurrence_protocol.md §3.10",
            file=sys.stderr,
        )
        raise SystemExit(5)


def _audit_no_motif_label_leak(analysis: dict, virtue_motifs: dict) -> None:
    """v9.4 R-MOTIF-1 + R-MOTIF-2 · 扫所有 narrative 字段的 motif id / canonical name 字面。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from _v9_guard import (  # type: ignore
            scan_motif_id_leak,
            scan_canonical_label_leak,
        )
    except ImportError as e:
        raise SystemExit(f"[render_artifact] 找不到 _v9_guard: {e}")

    triggered = virtue_motifs.get("triggered_motifs") or []
    silenced = virtue_motifs.get("silenced_motifs") or []
    motif_ids: list[str] = []
    canonical_labels: list[str] = []
    for m in triggered:
        if isinstance(m, dict):
            if m.get("id"):
                motif_ids.append(m["id"])
            if m.get("name"):
                canonical_labels.append(m["name"])
    for m in silenced:
        if isinstance(m, dict):
            if m.get("id"):
                motif_ids.append(m["id"])
            if m.get("name"):
                canonical_labels.append(m["name"])
        elif isinstance(m, str):
            motif_ids.append(m)

    any_hit = False
    for label, text in _iter_narrative_fields(analysis):
        id_hits = scan_motif_id_leak(text, motif_ids=motif_ids)
        if id_hits:
            any_hit = True
            print(
                f"[render_artifact] R-MOTIF-1 motif id leak · {label}：",
                file=sys.stderr,
            )
            for h in id_hits[:5]:
                print(f"  · '{h.motif_id}'  snippet='{h.snippet}'", file=sys.stderr)
        cn_hits = scan_canonical_label_leak(text, canonical_labels)
        if cn_hits:
            any_hit = True
            print(
                f"[render_artifact] R-MOTIF-2 canonical label leak · {label}：",
                file=sys.stderr,
            )
            for h in cn_hits[:5]:
                print(f"  · '{h.label}'  snippet='{h.snippet}'", file=sys.stderr)
    if any_hit:
        print(
            "  · 修法：narrative 中永远不出现 motif id 与 catalog 内 canonical name 字面。"
            "化用 paraphrase_seeds 的意思，再次个性化润色为只属于这个命主的具体情境。\n"
            "  · 详见 references/virtue_recurrence_protocol.md §3.11.1 / §3.11.2",
            file=sys.stderr,
        )
        raise SystemExit(5)


def _audit_paraphrase_diversity(analysis: dict) -> None:
    """v9.4 R-MOTIF-3 · 同一 motif 在 _motif_text_log 中 ≥2 条 → 任两条相似度必须 < 0.6。"""
    log = analysis.get("_motif_text_log") or {}
    if not isinstance(log, dict) or not log:
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from _v9_guard import _normalized_jaccard  # type: ignore
    except ImportError as e:
        raise SystemExit(f"[render_artifact] 找不到 _v9_guard: {e}")

    fails: list[tuple[str, str, str, float]] = []
    for mid, entries in log.items():
        if not isinstance(entries, list) or len(entries) < 2:
            continue
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                ti = (entries[i] or {}).get("text") or ""
                tj = (entries[j] or {}).get("text") or ""
                if not ti or not tj:
                    continue
                sim = _normalized_jaccard(ti, tj)
                if sim >= 0.6:
                    fails.append((
                        mid,
                        (entries[i] or {}).get("anchor", "?"),
                        (entries[j] or {}).get("anchor", "?"),
                        sim,
                    ))
    if fails:
        print(
            "[render_artifact] R-MOTIF-3 paraphrase 改写不足：以下 motif 的两段表述过于相似：",
            file=sys.stderr,
        )
        for mid, a, b, sim in fails[:10]:
            print(
                f"  · motif='{mid}'  similarity={sim:.2f}  anchors=({a!r}, {b!r})",
                file=sys.stderr,
            )
        print(
            "  · 修法：换一个角度、换一组动词、换一个比喻；同一母题第二次必须显著改写（< 0.6）。\n"
            "  · 详见 references/virtue_recurrence_protocol.md §3.11.3",
            file=sys.stderr,
        )
        raise SystemExit(5)


def _enforce_streamed_emit(log: list) -> None:
    """检测同一 60s 帧内塞 ≥4 节 → 伪流式（exit 4）。"""
    if not isinstance(log, list) or len(log) < 4:
        return
    bucket: dict[int, int] = {}
    for entry in log:
        ts = entry.get("ts_unix") if isinstance(entry, dict) else None
        if not isinstance(ts, int):
            continue
        slot = ts // 60
        bucket[slot] = bucket.get(slot, 0) + 1
    for slot, n in bucket.items():
        if n >= 4:
            print(
                f"[render_artifact] 伪流式判定：60s 帧内塞了 {n} 个节 "
                f"(ts_unix slot={slot * 60})——v9 流式铁律 exit 4。"
                f" 请确实做到「写一节立刻 append_analysis_node 落盘」。",
                file=sys.stderr,
            )
            raise SystemExit(4)


_NODE_ORDER_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("opening",        ("virtue_narrative.opening",)),
    ("dayun",          ("dayun_reviews.",)),
    ("liunian",        ("liunian.",)),
    ("key_years",      ("key_years.",)),
    ("overall",        ("overall", "life_review.")),
    ("closing",        ("virtue_narrative.declaration",
                        "virtue_narrative.love_letter",
                        "virtue_narrative.free_speech",
                        "virtue_narrative.convergence_notes")),
]

# v9.4 · motif_witness 节点不参与五阶段节序校验（它是穿插在各阶段之间的"旁白
# message"），归类时直接 skip 而不是 fail；详见 multi_dim_xiangshu_protocol.md §13.1
_NODE_ORDER_SKIP_PREFIXES: tuple[str, ...] = ("motif_witness.",)


def _classify_node(node: str) -> int:
    for skip_pref in _NODE_ORDER_SKIP_PREFIXES:
        if node.startswith(skip_pref):
            return -2  # 中性 skip：既不算违序也不参与节序流
    for i, (_grp, prefixes) in enumerate(_NODE_ORDER_GROUPS):
        for pref in prefixes:
            if node == pref or node.startswith(pref):
                return i
    return -1


def _enforce_node_order(log: list) -> None:
    """五阶段节序铁律：

      0 opening → 1 dayun → 2 liunian → 3 key_years → 4 overall/life_review → 5 closing

    允许在同段内多次 append，也允许 dayun↔liunian 交错（同一大运段内
    先写 dayun_review 再写其十年 liunian），但**不允许大跨度回退**。
    """
    if not isinstance(log, list) or not log:
        return
    seen_max = -1
    violations: list[str] = []
    for entry in log:
        node = entry.get("node") if isinstance(entry, dict) else None
        if not isinstance(node, str):
            continue
        idx = _classify_node(node)
        if idx < 0:
            continue
        # 允许 dayun (1) ↔ liunian (2) 任意交错；其它阶段必须单调向前
        if idx in (1, 2) and seen_max in (1, 2):
            seen_max = max(seen_max, idx)
            continue
        if idx + 1 < seen_max:  # 大跨度回退（跳 ≥1 个阶段）
            violations.append(
                f"节序回退：写 {node!r}（阶段 {idx}） 但已经写到阶段 {seen_max}"
            )
        seen_max = max(seen_max, idx)

    if violations:
        print(
            f"[render_artifact] 五阶段节序违规：{len(violations)} 条："
            f"\n  - " + "\n  - ".join(violations) +
            "\n  · 五阶段：opening → 当前大运+流年（1↔2 可交错）→ key_years → overall/life_review → closing。"
            "\n  · 详见 references/multi_dim_xiangshu_protocol.md §13.1 节序铁律。",
            file=sys.stderr,
        )
        raise SystemExit(4)


def _curves_from_stream_state(state_path: Path) -> dict:
    """v9.3 · 从 streaming_pipeline 的 stream_state.json 还原一份与 curves.json
    等价的 dict，喂给 render_artifact 现有渲染管线。

    state['stages']['overall_and_life_review'] / 'other_dayuns' / 'current_dayun' /
    'current_dayun_liunian' / 'key_years' 各自携带必要片段；本函数把它们重新
    拼成 curves.json schema（version / baseline / points / dayun_segments /
    turning_points_future / disputes / phase 等）。
    """
    state = json.loads(state_path.read_text(encoding="utf-8"))
    stages = state.get("stages") or {}

    overall = stages.get("overall_and_life_review") or {}
    other = stages.get("other_dayuns") or {}
    cur = stages.get("current_dayun") or {}
    cur_ln = stages.get("current_dayun_liunian") or {}
    ky = stages.get("key_years") or {}

    segments: list[dict] = []
    if cur.get("segment"):
        segments.append(cur["segment"])
    for o in (other.get("segments") or []):
        if o.get("segment"):
            segments.append(o["segment"])
    segments.sort(key=lambda s: s.get("start_age", 0))

    points: list[dict] = list(cur_ln.get("yearly_points") or [])
    points.sort(key=lambda p: p.get("year", 0))

    return {
        "version": 3,
        "from_stream_state": True,
        "stream_state_path": str(state_path),
        "baseline": overall.get("baseline") or {"spirit": 50, "wealth": 50, "fame": 50, "emotion": 50},
        "phase": overall.get("phase") or {"id": "day_master_dominant", "label": "默认 · 日主主导"},
        "geju": overall.get("geju") or {},
        "yongshen": overall.get("yongshen") or {},
        "strength": overall.get("strength"),
        "age_start": (overall.get("age_range") or [0, 80])[0],
        "age_end": (overall.get("age_range") or [0, 80])[1],
        "dayun_segments": segments,
        "points": points,
        "turning_points_future": ky.get("turning_points_future") or [],
        "disputes": ky.get("disputes") or [],
        "dispute_threshold": ky.get("dispute_threshold") or 20.0,
        "pillars_str": "(from_stream_state)",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curves", required=False, default=None,
                    help="curves.json 路径（v9.3 起若提供 --from-stream-state 则可选）")
    ap.add_argument("--from-stream-state", default=None,
                    help="v9.3 · 从 streaming_pipeline 的 stream_state.json 还原 curves，"
                         "无需依赖批量 score_curves.py 产物。与 --curves 二选一。")
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
    # v9 默认全部 strict；用户可显式 --no-* 关掉单项审计
    ap.add_argument("--strict-llm", action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：当 analysis.json 里 LLM 应写未写时，raise LlmCoverageError。"
                         "--no-strict-llm 关掉降级为 stderr warning。")
    ap.add_argument("--allow-partial", action="store_true",
                    help="v9.2 · 流式渲染模式：缺字段时显示「⌛ 流式写作中」占位，不抛错也不算 fail。"
                         "用于 agent 边写边刷 HTML 看进度（最终产物仍要去掉此 flag 跑覆盖率审计）。"
                         "**partial 模式自动关掉所有下方 v9 strict 审计**。")
    ap.add_argument("--require-final-version", action="store_true",
                    help="v9.3.1 · 构建分发版时拒绝 partial: 与 --allow-partial 同时给会 raise. "
                         "防止意外把流式中间产物当成最终版发出去 (顶部还会有黄条提示).")
    ap.add_argument("--coverage-report", default=None,
                    help="v9.1 · 可选 · 把 LLM 字段覆盖度 JSON 写到该路径")

    # v9 strict audits（默认全开；partial 模式自动跳过）
    ap.add_argument("--require-streamed-emit",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：检查 analysis._stream_log，若同一帧（≤60s）内塞了 ≥4 个节，"
                         "判定 LLM 在伪流式（一次跑完再切片重发），exit 4。")
    ap.add_argument("--required-node-order",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：校验 _stream_log 里节序符合五阶段（opening → 当前大运 + liunian "
                         "→ 其它大运 → key_years → overall/life_review → closing）。")
    ap.add_argument("--audit-virtue-continuity",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：调用 scripts/audit_virtue_recurrence_continuity.py 阻断"
                         "位置②G块缺失 / 位置④trace 不足 / silenced 泄漏 / 位置⑥首尾标记缺失。")
    ap.add_argument("--audit-mangpai-surface",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：调用 scripts/audit_mangpai_surface.py 阻断"
                         "high confidence 盲派事件未在叙事里 surface。")
    ap.add_argument("--audit-closing-headers",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：declaration / love_letter / free_speech 三节标题必须去模板化"
                         "（## 走到这里 / ## 写到这里我想说 / ## 不在协议里的话）。")
    ap.add_argument("--audit-no-premature-decision",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9 默认开：若给 --bazi，阻断 phase_decision.is_provisional=true / "
                         "confidence=reject 进入产物。")
    ap.add_argument("--audit-stream-batching",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9.3 默认开：扫 analysis._stream_violations，若 R-STREAM-1 "
                         "（同 agent_turn_id 内连续 append_analysis_node ≥ 2 节）≥ 1 → exit 11。"
                         "用于物理拦截 LLM 在一个 turn 里塞多节、绕过 stop turn 的违规。")
    ap.add_argument("--audit-motif-witness-cumulative",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9.4 默认开：扫 analysis.motif_witness.<anchor>，"
                         "第 ≥ 2 个 anchor 必须显式呼应之前 anchor 的母题（关键词命中），"
                         "否则视为没做到累加感 → exit 5。详见 virtue_recurrence_protocol.md §3.10。")
    ap.add_argument("--audit-no-motif-id-leak",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9.4 默认开 · R-MOTIF-1：扫所有 narrative 字段（dayun_reviews / "
                         "liunian / key_years / motif_witness / virtue_narrative.*），"
                         "命中 motif id 字面（K2_xxx / B1 / L3 等）→ exit 5。"
                         "详见 virtue_recurrence_protocol.md §3.11.1。")
    ap.add_argument("--audit-paraphrase-diversity",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="v9.4 默认开 · R-MOTIF-3：同一母题在 ≥ 2 个 narrative 位置出现时，"
                         "字符 n-gram Jaccard 相似度必须 < 0.6，否则 → exit 5。"
                         "依赖 analysis._motif_text_log。详见 virtue_recurrence_protocol.md §3.11.3。")
    ap.add_argument("--mangpai", default=None,
                    help="v9 audit-mangpai-surface 用：output/X.mangpai.json 路径。")
    args = ap.parse_args()
    # v9.3.1 · partial vs final-version 互斥校验
    if args.require_final_version and args.allow_partial:
        raise SystemExit(
            "[render_artifact] --require-final-version 与 --allow-partial 互斥: "
            "前者用于构建分发版, 后者用于流式中间产物."
        )
    if args.from_stream_state:
        curves = _curves_from_stream_state(Path(args.from_stream_state))
    elif args.curves:
        curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))
    else:
        raise SystemExit(
            "[render_artifact] 必须提供 --curves 或 --from-stream-state 之一。"
        )
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

    # v9.3.1 · curves schema 预检 (与模板 resilience guard 互补)
    schema_warnings = validate_curves_min_schema(curves, allow_partial=args.allow_partial)
    for w in schema_warnings:
        print(f"[curves-schema] {w}", file=sys.stderr)

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

    # ─── v9 strict audits（partial 模式跳过）────────────────────────────
    if not args.allow_partial:
        _run_v9_audits(args, analysis, virtue_motifs)

    html = render(
        curves, analysis, zeitgeist, virtue_motifs,
        allow_partial=args.allow_partial,
        coverage_report=coverage,
    )
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
