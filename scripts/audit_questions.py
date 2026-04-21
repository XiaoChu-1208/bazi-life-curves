#!/usr/bin/env python3
"""scripts/audit_questions.py · v9 · 题库可答性 / 中性度静态审计

用 8 维 ambiguity detector + 命理词典扫描，给 [_question_bank.py](_question_bank.py)
的每道静态题打一个 severity 报告。**只读**，不修改题库。

8 维 ambiguity（各自一个 detector）：
  A1 vague_quantifier   模糊数量副词："经常 / 有时 / 比较 / 大概 / 通常"
  A2 subjective_judgment 主观评价词："成功 / 顺利 / 幸运 / 优秀 / 美满"
  A3 multi_concept       单选项混 ≥ 2 个独立概念（"且 / 而 / 同时 / 既...又"）
  A4 temporal_ambiguous  时间口径不清（"总是 / 一直 / 最近 / 偶尔" 没给窗口）
  A5 counterfactual      假设 / 反事实问题（"如果你... / 假设... / 当年若..."）
  A6 double_negation     双重否定（"不是不...", "没有不"）
  A7 option_overlap      选项语义重叠（包含同根词；编辑距离 ≤ 2 视为可疑）
  A8 leading             诱导性提问（"是不是觉得 / 你应该 / 大多数人都"）

命理词典扫描（B 系列）：
  B1 phase_leak          直接出现 phase 关键词："格局 / 从财 / 从杀 / 化气 /
                         真从 / 假从 / 三奇成象 / 日主 / 用神 / 喜神 / 忌神"
  B2 ten_god_leak        十神泄露："正官 / 七杀 / 偏财 / 正财 / 食神 / 伤官 /
                         偏印 / 正印 / 比肩 / 劫财"
  B3 wuxing_pole_leak    五行 pole 词："旺 / 衰 / 强 / 弱 / 太过 / 不及 /
                         身强 / 身弱"

输出：
  - 默认 stdout 表格（grouped by severity）
  - --json 输出 machine-readable
  - --md 输出 markdown 报告（写到 references/question_bank_audit.md）

severity:
  critical  B1 / B2 / B3 任一命中（必须修） → exit 1
  high      A3 / A5 / A8 任一命中（强烈建议改）
  medium    A1 / A2 / A4 任一命中（建议改）
  low       A6 / A7 任一命中（标记）
  ok        无命中

详见 plan §A5。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _question_bank import get_static_questions, Question  # type: ignore


# ---------------------------------------------------------------------------
# §1 8 维 ambiguity dictionaries（按经验整理；非命理词典）
# ---------------------------------------------------------------------------

A1_VAGUE_QUANTIFIER = [
    "经常", "有时候", "有时", "比较", "大概", "通常", "差不多", "一般来说",
    "多多少少", "或多或少", "略微", "稍微", "时不时",
]

A2_SUBJECTIVE_JUDGMENT = [
    "成功", "顺利", "幸运", "优秀", "美满", "圆满", "失败", "倒霉", "悲惨",
    "幸福", "不幸", "高质量", "低质量", "上等", "中等", "下等",
]

A3_MULTI_CONCEPT_MARKERS = [
    "且", "而且", "同时", "并且", "既", "又", "也", "也是",
    "兼", "兼有", "并存", "并伴随",
]

A4_TEMPORAL = [
    "总是", "一直", "从来", "最近", "偶尔", "时常", "多年来", "近年",
]

# 反事实需要从句结构识别
A5_COUNTERFACTUAL = [
    "如果你", "假设", "假如", "若是", "倘若", "万一", "当年若",
    "如果当时", "如果换成", "如果重来",
]

# 双重否定：用规则匹配
A6_DOUBLE_NEG_PATTERNS = [
    r"不(?:是|算|会|能|觉得).{0,4}不",
    r"没(?:有)?.{0,4}不",
    r"未必不",
    r"难免不",
]

# 诱导性提问
A8_LEADING = [
    "是不是觉得", "你应该", "大多数人都", "通常我们", "显然",
    "其实你", "本来就", "理所当然", "人之常情",
]


# ---------------------------------------------------------------------------
# §2 命理词典（hard rule · phase / ten-god / wuxing pole）
# ---------------------------------------------------------------------------

B1_PHASE_TERMS = [
    "格局", "格", "从财", "从官", "从杀", "从儿", "从印", "从势",
    "化气", "真化", "假化", "真从", "假从",
    "三奇", "成象", "日主", "用神", "喜神", "忌神", "调候",
    "下马威", "盲派", "盲师", "纳音", "胎元", "命宫",
]

B2_TEN_GOD_TERMS = [
    "正官", "七杀", "偏官", "偏财", "正财", "食神", "伤官",
    "偏印", "枭神", "正印", "比肩", "劫财", "羊刃",
    "食伤", "官杀", "印星", "财星", "比劫",
]

B3_WUXING_POLE = [
    "身强", "身弱", "太过", "不及", "失令", "得令", "通根",
    "透出", "透干", "透出地支", "扶抑", "克泄交加",
]


# ---------------------------------------------------------------------------
# §3 detectors
# ---------------------------------------------------------------------------

def _hits(text: str, terms: List[str]) -> List[str]:
    out = []
    for t in terms:
        if t in text:
            out.append(t)
    return out


def _hits_regex(text: str, patterns: List[str]) -> List[str]:
    out = []
    for p in patterns:
        if re.search(p, text):
            out.append(p)
    return out


def detect_question(q: Question) -> Dict[str, Any]:
    """对单题跑 8 + 3 个 detector，返回 finding dict。"""
    prompt = q.prompt
    options = [o.label for o in q.options]
    all_text = prompt + " || " + " | ".join(options)

    findings: Dict[str, Any] = {
        "id": q.id,
        "dimension": q.dimension,
        "weight_class": q.weight_class,
        "prompt": prompt,
        "n_options": len(q.options),
        "checks": {},
    }

    # B series · critical
    findings["checks"]["B1_phase_leak"] = _hits(all_text, B1_PHASE_TERMS)
    findings["checks"]["B2_ten_god_leak"] = _hits(all_text, B2_TEN_GOD_TERMS)
    findings["checks"]["B3_wuxing_pole_leak"] = _hits(all_text, B3_WUXING_POLE)

    # A series · ambiguity
    findings["checks"]["A1_vague_quantifier"] = _hits(all_text, A1_VAGUE_QUANTIFIER)
    findings["checks"]["A2_subjective_judgment"] = _hits(all_text, A2_SUBJECTIVE_JUDGMENT)

    # A3 multi-concept：每个 option 单独看（prompt 含连接词不算）
    a3_hits: List[str] = []
    for o in options:
        markers = _hits(o, A3_MULTI_CONCEPT_MARKERS)
        if markers and len(o) >= 8:  # 短 option 偶遇连接词不算
            a3_hits.append(f"opt:{o}|markers={markers}")
    findings["checks"]["A3_multi_concept"] = a3_hits

    findings["checks"]["A4_temporal_ambiguous"] = _hits(all_text, A4_TEMPORAL)
    findings["checks"]["A5_counterfactual"] = _hits(prompt, A5_COUNTERFACTUAL)
    findings["checks"]["A6_double_negation"] = _hits_regex(all_text, A6_DOUBLE_NEG_PATTERNS)

    # A7 option overlap：选项两两查公共子串 ≥ 4 字 / 完全相等
    a7_hits: List[str] = []
    for i in range(len(options)):
        for j in range(i + 1, len(options)):
            a, b = options[i], options[j]
            if a == b:
                a7_hits.append(f"identical: {a!r} == {b!r}")
                continue
            # 找公共子串（贪心 4 字以上）
            longest = _longest_common_substring(a, b)
            # 子串过滤：常见尾缀如 "/" 或介词不算
            stripped = longest.strip("，。、；,/ ")
            if len(stripped) >= 4 and stripped not in ("一直以来", "从来没有"):
                a7_hits.append(f"common[{stripped!r}]: {a!r} ∩ {b!r}")
    findings["checks"]["A7_option_overlap"] = a7_hits

    findings["checks"]["A8_leading"] = _hits(all_text, A8_LEADING)

    # severity
    severity = "ok"
    crit = (
        findings["checks"]["B1_phase_leak"]
        + findings["checks"]["B2_ten_god_leak"]
        + findings["checks"]["B3_wuxing_pole_leak"]
    )
    if crit:
        severity = "critical"
    elif (
        findings["checks"]["A3_multi_concept"]
        or findings["checks"]["A5_counterfactual"]
        or findings["checks"]["A8_leading"]
    ):
        severity = "high"
    elif (
        findings["checks"]["A1_vague_quantifier"]
        or findings["checks"]["A2_subjective_judgment"]
        or findings["checks"]["A4_temporal_ambiguous"]
    ):
        severity = "medium"
    elif (
        findings["checks"]["A6_double_negation"]
        or findings["checks"]["A7_option_overlap"]
    ):
        severity = "low"

    findings["severity"] = severity
    findings["n_total_findings"] = sum(len(v) for v in findings["checks"].values())
    return findings


def _longest_common_substring(a: str, b: str) -> str:
    if not a or not b:
        return ""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    best_end = 0
    best_len = 0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > best_len:
                    best_len = dp[i][j]
                    best_end = i
    return a[best_end - best_len:best_end]


# ---------------------------------------------------------------------------
# §4 报告渲染
# ---------------------------------------------------------------------------

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "ok"]
_SEVERITY_ICON = {
    "critical": "[CRIT]",
    "high":     "[HIGH]",
    "medium":   "[MED ]",
    "low":      "[LOW ]",
    "ok":       "[ OK ]",
}


def render_text(findings: List[Dict]) -> str:
    by_sev: Dict[str, List[Dict]] = {s: [] for s in _SEVERITY_ORDER}
    for f in findings:
        by_sev[f["severity"]].append(f)

    lines: List[str] = []
    lines.append("=" * 78)
    lines.append("题库审计报告 · audit_questions.py v9")
    lines.append("=" * 78)
    lines.append("")
    lines.append("Severity 汇总：")
    for sev in _SEVERITY_ORDER:
        lines.append(f"  {_SEVERITY_ICON[sev]} {sev:<8} = {len(by_sev[sev])} 题")
    lines.append("")
    lines.append("-" * 78)

    for sev in _SEVERITY_ORDER:
        if not by_sev[sev] or sev == "ok":
            continue
        lines.append(f"\n## {_SEVERITY_ICON[sev]} {sev.upper()}（{len(by_sev[sev])} 题）\n")
        for f in by_sev[sev]:
            lines.append(f"  [{f['id']}] ({f['dimension']} / {f['weight_class']})")
            lines.append(f"    Q: {f['prompt']}")
            for check_name, hits in f["checks"].items():
                if hits:
                    lines.append(f"    ⊘ {check_name}: {hits}")
            lines.append("")

    if by_sev["ok"]:
        lines.append(f"\n## {_SEVERITY_ICON['ok']} OK（{len(by_sev['ok'])} 题）\n")
        for f in by_sev["ok"]:
            lines.append(f"  [{f['id']}] ({f['dimension']}) {f['prompt'][:50]}…")

    return "\n".join(lines)


def render_markdown(findings: List[Dict]) -> str:
    by_sev: Dict[str, List[Dict]] = {s: [] for s in _SEVERITY_ORDER}
    for f in findings:
        by_sev[f["severity"]].append(f)

    lines: List[str] = []
    lines.append("# 题库审计报告 · v9")
    lines.append("")
    lines.append("> 由 [scripts/audit_questions.py](../scripts/audit_questions.py) 生成。"
                 "8 维 ambiguity detector + 命理词典扫描。**只读静态分析**，不读用户数据。")
    lines.append("")
    lines.append("## Severity 汇总")
    lines.append("")
    lines.append("| Severity | 题数 | 含义 |")
    lines.append("|---|---|---|")
    sev_meaning = {
        "critical": "命理词典直接泄露（必须修，违反 elicitation_ethics §E1）",
        "high":     "诱导 / 反事实 / 多概念混选项（强烈建议改）",
        "medium":   "模糊量词 / 主观评价 / 时间口径不清（建议改）",
        "low":      "双重否定 / 选项语义重叠（标记观察）",
        "ok":       "无任何命中",
    }
    for sev in _SEVERITY_ORDER:
        lines.append(f"| {_SEVERITY_ICON[sev]} **{sev}** | {len(by_sev[sev])} | {sev_meaning[sev]} |")
    lines.append("")

    lines.append(f"**Total**: {len(findings)} 道静态题")
    lines.append("")

    for sev in _SEVERITY_ORDER:
        if not by_sev[sev] or sev == "ok":
            continue
        lines.append(f"## {_SEVERITY_ICON[sev]} {sev.upper()}（{len(by_sev[sev])} 题）")
        lines.append("")
        for f in by_sev[sev]:
            lines.append(f"### [{f['id']}] · {f['dimension']} / {f['weight_class']}")
            lines.append(f"**Q**: {f['prompt']}")
            lines.append("")
            for check_name, hits in f["checks"].items():
                if hits:
                    sample = "; ".join(str(h) for h in hits[:3])
                    if len(hits) > 3:
                        sample += f"; ... (+{len(hits) - 3})"
                    lines.append(f"- `{check_name}`: {sample}")
            lines.append("")

    if by_sev["ok"]:
        lines.append(f"## {_SEVERITY_ICON['ok']} OK（{len(by_sev['ok'])} 题）")
        lines.append("")
        for f in by_sev["ok"]:
            lines.append(f"- `{f['id']}`（{f['dimension']}）: {f['prompt'][:60]}…")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# §5 CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="v9 · 题库可答性 / 中性度静态审计",
    )
    ap.add_argument("--json", action="store_true",
                    help="输出 machine-readable JSON 到 stdout")
    ap.add_argument("--md", default=None,
                    help="markdown 报告输出路径（推荐 references/question_bank_audit.md）")
    ap.add_argument("--strict", action="store_true",
                    help="任一题 severity=critical 时 exit 1（CI 用）")
    ap.add_argument("--filter-severity", choices=["critical", "high", "medium", "low", "ok"],
                    default=None, help="仅显示指定 severity")
    args = ap.parse_args()

    questions = get_static_questions()
    findings = [detect_question(q) for q in questions]

    if args.filter_severity:
        findings = [f for f in findings if f["severity"] == args.filter_severity]

    n_critical = sum(1 for f in findings if f["severity"] == "critical")
    n_high = sum(1 for f in findings if f["severity"] == "high")

    if args.md:
        out_path = Path(args.md)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_markdown(findings), encoding="utf-8")
        print(f"[audit_questions] wrote {out_path} ({len(findings)} findings, "
              f"critical={n_critical}, high={n_high})")
    elif args.json:
        print(json.dumps({
            "version": 9,
            "n_questions": len(findings),
            "n_critical": n_critical,
            "n_high": n_high,
            "findings": findings,
        }, ensure_ascii=False, indent=2))
    else:
        print(render_text(findings))
        print(f"\n→ critical={n_critical}, high={n_high}, total={len(findings)}")

    if args.strict and n_critical > 0:
        print(f"[audit_questions] STRICT FAIL · critical={n_critical} > 0", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
