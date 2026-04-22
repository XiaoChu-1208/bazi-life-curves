#!/usr/bin/env python3
"""audit_mangpai_surface.py — v9 高置信度盲派事件必须显式出现在叙事里

5 类问题之 #5：6d0abb46 case 跑完后，模型没意识到几条 confidence=high 的盲派
事件其实是高置信度的，结果分析里完全没有 surface 这些事件。本脚本机械阻断这种
"高信号被吃掉"——

铁律：mangpai.json 里 confidence ∈ {"high"} 的所有事件，必须在 analysis JSON
对应的叙事节里被字面提及（年份、ganzhi、key、或 canonical_event 关键短语）。

匹配判定（任一即视为 surfaced）：
  · key 字面出现（如 "shang_guan_jian_guan"）—— 一般不会，但兜底
  · year 字面出现（如 "2024"），且同段叙事里出现 name / canonical_event 短语
  · ganzhi 字面 + name 字面同段
  · 静态标记 "年财不归我" 直接搜 name

用法：

    python scripts/audit_mangpai_surface.py \\
        --mangpai output/X.mangpai.json \\
        --analysis output/X.analysis.json \\
        --bazi output/X.bazi.json    # 可选：开启 phase_decision.mangpai_conflict_alert 审计
        --emit-checklist             # 可选：把 high confidence 列表打到 stdout

退出码：
    0 通过
    2 任一 high confidence 事件未被 surface
    3 phase_decision.mangpai_conflict_alert.severity ∈ {high, mid} 的冲突 hits
      未在叙事中被字面提及（决策与盲派 / 子平正格高置信度结论冲突，必须显式承认）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict | list:
    if not path.exists():
        raise SystemExit(f"[audit_mangpai_surface] 文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten_text(obj: Any) -> str:
    """串接 analysis 里所有字符串。"""
    chunks: list[str] = []

    def _walk(o: Any) -> None:
        if isinstance(o, str):
            chunks.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    _walk(obj)
    return "\n".join(chunks)


def _short_anchor(canonical: str) -> str:
    """从 canonical_event 截取前 6-12 字作为锚短语（避免对长描述全文匹配）。"""
    if not canonical:
        return ""
    # 取首句的前 12 字
    first = canonical.split("；")[0].split(",")[0].split("，")[0]
    return first[:12]


def _high_confidence_events(mangpai: dict) -> list[dict]:
    events = mangpai.get("events") or []
    static_markers = mangpai.get("static_markers") or []
    out = []
    for e in events + static_markers:
        if not isinstance(e, dict):
            continue
        if e.get("confidence") == "high":
            out.append(e)
    return out


def _is_surfaced(event: dict, analysis_text: str) -> bool:
    name = event.get("name") or ""
    key = event.get("key") or ""
    year = event.get("year")
    ganzhi = event.get("ganzhi") or ""
    canonical = event.get("canonical_event") or ""
    anchor = _short_anchor(canonical)

    # 1) name 字面命中（最强信号）
    if name and name in analysis_text:
        return True
    # 2) key 字面命中（拼音 / 内部 id）
    if key and key in analysis_text:
        return True
    # 3) year + 锚短语 同时出现
    if year and str(year) in analysis_text and anchor and anchor in analysis_text:
        return True
    # 4) ganzhi + 锚短语 同时出现
    if ganzhi and ganzhi in analysis_text and anchor and anchor in analysis_text:
        return True
    return False


def audit(mangpai: dict, analysis: dict) -> tuple[list[str], list[dict]]:
    high_events = _high_confidence_events(mangpai)
    if not high_events:
        return [], []
    text = _flatten_text(analysis)
    missed: list[dict] = []
    for ev in high_events:
        if not _is_surfaced(ev, text):
            missed.append(ev)

    violations: list[str] = []
    for ev in missed:
        tag = []
        if ev.get("year"):
            tag.append(f"{ev['year']}")
        if ev.get("ganzhi"):
            tag.append(ev["ganzhi"])
        if ev.get("name"):
            tag.append(ev["name"])
        head = " / ".join(tag) if tag else ev.get("key", "?")
        violations.append(
            f"[mangpai-high 未 surface] {head}（confidence=high）—— 必须在 "
            "dayun_reviews / liunian / key_years / overall 任一节里被显式提及。"
            f" canonical: {ev.get('canonical_event', '')[:40]}…"
        )
    return violations, high_events


def audit_phase_conflict_alert(bazi: dict, analysis: dict) -> tuple[list[str], dict | None]:
    """v9 · phase_decision.mangpai_conflict_alert 必须 surface。

    判定：alert.severity ∈ {high, mid} 时，每条 conflicting_hit 的 name_cn 必须在
    analysis 文本中字面出现。high 严重度还要求 alert.advisory 关键词（"冲突"或"张力"
    或"承认"）至少有一个在 overall / dayun_reviews 任意一节里。

    返回 (violations, alert)：alert 为 None 表示无 alert，跳过审计。
    """
    pd = (bazi or {}).get("phase_decision") or {}
    alert = pd.get("mangpai_conflict_alert")
    if not isinstance(alert, dict):
        return [], None

    severity = alert.get("severity", "low")
    if severity == "low":
        return [], alert

    text = _flatten_text(analysis)
    violations: list[str] = []
    hits = alert.get("conflicting_hits", []) or []
    missing_hits: list[dict] = []
    for h in hits:
        name = h.get("name_cn") or h.get("id") or ""
        hit_id = h.get("id") or ""
        if not name and not hit_id:
            continue
        if name in text or (hit_id and hit_id in text):
            continue
        missing_hits.append(h)

    if missing_hits:
        for h in missing_hits:
            tag = h.get("name_cn") or h.get("id")
            violations.append(
                f"[mangpai-conflict-alert/{severity}] 冲突 hit「{tag}」"
                f"(conf={h.get('confidence')}, school={h.get('school')}) 未在叙事中提及。"
                f"决策相位 {alert.get('decision_phase')} 与之不一致，必须显式承认这种张力。"
            )

    if severity == "high":
        keywords = ("冲突", "张力", "承认", "盲派", "另一相位", "另一种判读")
        if not any(kw in text for kw in keywords):
            violations.append(
                f"[mangpai-conflict-alert/high] severity=high 但叙事中未出现承认冲突的"
                f"任一关键词（{'/'.join(keywords)}）。advisory: {alert.get('advisory', '')[:80]}…"
            )

    return violations, alert


def main() -> int:
    ap = argparse.ArgumentParser(
        description="v9: 高置信度盲派事件 + phase_decision.mangpai_conflict_alert 必须 surface 到叙事",
    )
    ap.add_argument("--mangpai", required=True, help="output/X.mangpai.json")
    ap.add_argument("--analysis", required=True, help="output/X.analysis.json")
    ap.add_argument(
        "--bazi", required=False, default=None,
        help="output/X.bazi.json —— 提供后启用 phase_decision.mangpai_conflict_alert 审计",
    )
    ap.add_argument(
        "--emit-checklist", action="store_true",
        help="额外打印 high confidence 事件清单到 stdout（用于 LLM 写稿前对照）",
    )
    ap.add_argument(
        "--allow-partial", action="store_true",
        help="流式中间态：缺失只 warn 不 fail",
    )
    args = ap.parse_args()

    mangpai = _load_json(Path(args.mangpai))
    analysis = _load_json(Path(args.analysis))
    if not isinstance(mangpai, dict) or not isinstance(analysis, dict):
        raise SystemExit("[audit_mangpai_surface] 期望两个文件都是 JSON 对象")

    bazi: dict | None = None
    if args.bazi:
        b = _load_json(Path(args.bazi))
        if isinstance(b, dict):
            bazi = b

    violations, high_events = audit(mangpai, analysis)
    conflict_violations: list[str] = []
    conflict_alert: dict | None = None
    if bazi is not None:
        conflict_violations, conflict_alert = audit_phase_conflict_alert(bazi, analysis)

    if args.emit_checklist:
        payload = {
            "high_confidence_events": [
                {
                    "year": ev.get("year"),
                    "ganzhi": ev.get("ganzhi"),
                    "name": ev.get("name"),
                    "key": ev.get("key"),
                    "intensity": ev.get("intensity"),
                    "canonical_event": ev.get("canonical_event"),
                }
                for ev in high_events
            ],
        }
        if conflict_alert is not None:
            payload["mangpai_conflict_alert"] = conflict_alert
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if not violations and not conflict_violations:
        msg = f"[audit_mangpai_surface] PASS — high confidence 事件 {len(high_events)} 条全部已 surface"
        if conflict_alert is not None:
            msg += f"；conflict_alert(severity={conflict_alert.get('severity')}) hits 也已被叙事承认"
        print(msg + "。", file=sys.stderr)
        return 0

    all_violations = violations + conflict_violations

    if args.allow_partial:
        print(
            f"[audit_mangpai_surface] WARN（partial 放行）：{len(all_violations)} 条未 surface："
            f"\n  - " + "\n  - ".join(all_violations),
            file=sys.stderr,
        )
        return 0

    print(
        f"[audit_mangpai_surface] {len(all_violations)} 条审计失败"
        f"（events={len(violations)}, conflict_alert={len(conflict_violations)}）："
        f"\n  - " + "\n  - ".join(all_violations),
        file=sys.stderr,
    )
    if conflict_violations and not violations:
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
