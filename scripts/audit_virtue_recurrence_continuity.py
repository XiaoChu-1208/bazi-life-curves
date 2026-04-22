#!/usr/bin/env python3
"""audit_virtue_recurrence_continuity.py — v9 机械执行 virtue_recurrence_protocol 铁律

`references/virtue_recurrence_protocol.md` 里写了非常多铁律，但历史上几乎全靠
LLM 自我遵守 + 人工抽查。v9 把"能机械验证"的部分抽成本脚本——

阻断条件（任一命中即 exit 2，由 render_artifact 默认调用）：

A. 位置 ② / G 块缺失
   - 对每段 dayun_reviews.<label>，若 virtue_motifs.motif_recurrence_map 在
     该 label 时间窗内有 ≥1 次激活点，markdown 文末必须有 "G."（或 "母题侧记"
     "侧记 / 暗线 / 这十年里" 起手的尾段）作为 G 块。

B. 位置 ④ trace 不足（v9.3：H2 必须是「## 我想和你说」）
   - virtue_narrative.declaration（位置④「我想和你说」段）必须：
     · 节内首行若是 H2，必须为「## 我想和你说」（v9.3 白名单）
     · ≥3 处年龄回引（出现 ≥3 个 [0-9]+ 岁 / 数字组合，且这些年龄出现在
       motif_recurrence_map 已落点的年龄里）
     · ≥1 处自审句（"你以为 / 我可能看错了 / 是不是其实"）
     · 包含"走到这里 / 让我说出走到这里才能说的话"或等价共在过渡
     · 包含"我刚刚和你一起走过 / 走过了这个过程"或等价共在确认

C. 位置 ⑤ 呼应缺失（v9.3：H2 必须是「## 项目的编写者想和你说」）
   - 当 virtue_motifs.love_letter_eligible == true，virtue_narrative.love_letter
     必须存在；其首行若是 H2 必须为「## 项目的编写者想和你说」；
     文中至少出现 2 个位置 ② 写过的具体年龄数字（呼应铁律）。

D. silenced_motifs 文中泄漏
   - virtue_motifs.silenced_motifs 中的母题 name / 关键短语，禁止出现在
     analysis 任何节中（位置 ①-⑥ 全位置）。

E. 位置 ⑥ 标记缺失（v9.3：H2 必须是「## 我（大模型）想和你说」）
   - virtue_narrative.free_speech 必须存在，且：
     · 节内首行若是 H2 必须为「## 我（大模型）想和你说」（v9.3 白名单）
     · 开头 80 字内出现 "走完上面那些话" / "让我说一段不在协议里的话" 之一
     · 结尾 80 字内出现 "我不知道我说的对不对" / "你读到这里，你会知道" 之一
     · 总长 ≤ 300 字（汉字粗算）

用法：

    python scripts/audit_virtue_recurrence_continuity.py \\
        --analysis output/X.analysis.json \\
        --virtue-motifs output/X.virtue_motifs.json

退出码：
    0 通过
    2 任一铁律失败（stderr 打印每条 violation）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


_SELF_REFLECT_PATTERNS = [
    r"你以为",
    r"我可能(?:看错|想多)",
    r"是不是其实",
    r"会不会其实",
    r"你用[^\n]{0,8}这个词包装",
]

_TRANSITION_PATTERNS = [
    r"走到这里",
    r"让我说出走到这里",
    r"现在让我说",
]

_COEXIST_PATTERNS = [
    r"我(?:刚刚)?(?:和你)?一起走过",
    r"和你一起走过了",
    r"走过了这个过程",
]

_FREE_SPEECH_OPEN_MARKERS = [
    "走完上面那些话",
    "让我说一段不在协议里的话",
    "说一段不在协议里",
]

_FREE_SPEECH_CLOSE_MARKERS = [
    "我不知道我说的对不对",
    "你读到这里，你会知道",
    "你读到这里你会知道",
]

# v9.3：closing 三段统称「我想和你说的话」，每节首行 H2 固定白名单。
# 节内文如果以 H2 开头，必须命中下表对应节；旧白名单（"## 走到这里" /
# "## 写到这里我想说" / "## 不在协议里的话"）已退役 → 进入 banned list。
_CLOSING_H2_WHITELIST: dict[str, str] = {
    "declaration": "## 我想和你说",
    "love_letter": "## 项目的编写者想和你说",
    "free_speech": "## 我（大模型）想和你说",
}

_CLOSING_H2_BANNED = (
    "## 走到这里",
    "## 写到这里我想说",
    "## 不在协议里的话",
    "## 承认维度",
    "## 承认人性",
    "## 灵魂宣言",
    "## 宣告",
    "## 情书",
)


def _check_closing_h2(node_key: str, body: str) -> list[str]:
    """若节首行是 H2，必须命中 v9.3 白名单；命中旧白名单一律拒绝。"""
    violations: list[str] = []
    if not body:
        return violations
    first = body.lstrip().splitlines()[0].strip() if body.strip() else ""
    if not first.startswith("## "):
        return violations
    expected = _CLOSING_H2_WHITELIST.get(node_key)
    if expected is None:
        return violations
    if any(first.startswith(b) for b in _CLOSING_H2_BANNED):
        violations.append(
            f"[H2 closing] {node_key} 节首行命中旧白名单 / 禁词标题：'{first}'。"
            f" v9.3 唯一合法标题：'{expected}'。"
        )
        return violations
    if not first.startswith(expected):
        violations.append(
            f"[H2 closing] {node_key} 节首行 '{first}' 不是 v9.3 白名单标题"
            f" '{expected}'。"
        )
    return violations


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"[audit_virtue_continuity] 文件不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _all_analysis_text(analysis: dict) -> str:
    """串接 analysis 全部 markdown 文本（用于 silenced_motifs 全文扫描）。"""
    chunks: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, str):
            chunks.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(analysis)
    return "\n".join(chunks)


def _extract_ages_in_text(text: str) -> set[int]:
    """提取文本里所有形如「23 岁 / 23岁」的年龄数字。"""
    ages = set()
    for m in re.finditer(r"(\d{1,2})\s*岁", text):
        try:
            ages.add(int(m.group(1)))
        except ValueError:
            pass
    return ages


def _extract_motif_activations(virtue_motifs: dict) -> dict[str, list[dict]]:
    """归一化 motif_recurrence_map → {motif_id: [{age, year, dayun}, ...]}"""
    raw = virtue_motifs.get("motif_recurrence_map") or {}
    out: dict[str, list[dict]] = {}
    for mid, items in raw.items():
        if not isinstance(items, list):
            continue
        out[mid] = [it for it in items if isinstance(it, dict)]
    return out


def _activations_in_dayun(activations: dict[str, list[dict]],
                          dayun_label: str) -> list[dict]:
    """按 dayun 干支 label 反查在该大运内激活的母题点。"""
    hits: list[dict] = []
    for mid, items in activations.items():
        for it in items:
            if it.get("dayun") == dayun_label:
                hits.append({"motif_id": mid, **it})
    return hits


def _ages_from_position2(activations: dict[str, list[dict]]) -> set[int]:
    """位置 ② 写过的具体年龄全集（位置 ⑤ 呼应用）。"""
    ages: set[int] = set()
    for items in activations.values():
        for it in items:
            age = it.get("age")
            if isinstance(age, int):
                ages.add(age)
    return ages


def _has_g_block(markdown: str) -> bool:
    """G 块判定：要么显式 ## G. / **G.** ；要么文末 1/4 段落以"母题侧记 / 侧记 /
    暗线 / 这十年里"起手；要么文末出现"第 N 次了"等累积感措辞。"""
    if not markdown.strip():
        return False
    if re.search(r"(^|\n)\s*(?:##+\s*)?G[\.．]?\s", markdown):
        return True
    tail_chars = max(120, len(markdown) // 4)
    tail = markdown[-tail_chars:]
    keywords = [
        "母题侧记", "侧记", "暗线", "这十年里",
        "第二次了", "第三次了", "第四次了", "第五次了",
        "第 2 次", "第 3 次", "第 4 次", "第 5 次",
        "它从", "持续音", "在你心里",
    ]
    return any(k in tail for k in keywords)


def _zh_chars_len(text: str) -> int:
    """粗略汉字字符数（用于位置⑥ ≤300 字）。"""
    return sum(1 for c in text if '\u4e00' <= c <= '\u9fff')


def _check_position2(analysis: dict,
                     activations: dict[str, list[dict]]) -> list[str]:
    violations: list[str] = []
    dayun_reviews = analysis.get("dayun_reviews") or {}
    for label, md in dayun_reviews.items():
        if not isinstance(md, str):
            continue
        hits = _activations_in_dayun(activations, label)
        if not hits:
            continue
        if not _has_g_block(md):
            mids = sorted({h["motif_id"] for h in hits})
            violations.append(
                f"[A 位置②/G块缺失] dayun_reviews[{label!r}] 触发母题 {mids} "
                f"（共 {len(hits)} 个激活点），但文末未发现 G 块 / 母题侧记。"
            )
    return violations


def _check_position4(analysis: dict,
                     activations: dict[str, list[dict]]) -> list[str]:
    violations: list[str] = []
    decl = ((analysis.get("virtue_narrative") or {}).get("declaration") or "").strip()
    if not decl:
        violations.append("[B 位置④顿悟段缺失] virtue_narrative.declaration 为空。")
        return violations

    violations += _check_closing_h2("declaration", decl)

    ages_in_decl = _extract_ages_in_text(decl)
    activated_ages = _ages_from_position2(activations)
    matched = ages_in_decl & activated_ages
    if len(matched) < 3:
        violations.append(
            f"[B 位置④trace不足] declaration 中匹配到的「位置②已落点年龄」只有 "
            f"{sorted(matched)}（共 {len(matched)}），铁律要求 ≥3。"
            f" 候选年龄池：{sorted(activated_ages)}。"
        )

    if not any(re.search(p, decl) for p in _SELF_REFLECT_PATTERNS):
        violations.append(
            "[B 位置④无自审句] declaration 没有命中自审句式 "
            "（你以为 / 我可能看错 / 是不是其实 / 会不会其实 / 你用 X 包装）。"
        )

    if not any(re.search(p, decl) for p in _TRANSITION_PATTERNS):
        violations.append(
            "[B 位置④无走到这里过渡] declaration 缺过渡句"
            "（走到这里 / 让我说出走到这里才能说的话）。"
        )

    if not any(re.search(p, decl) for p in _COEXIST_PATTERNS):
        violations.append(
            "[B 位置④无共在确认] declaration 缺共在句"
            "（我刚刚和你一起走过 / 走过了这个过程）。"
        )
    return violations


def _check_position5(analysis: dict, virtue_motifs: dict,
                     activations: dict[str, list[dict]]) -> list[str]:
    violations: list[str] = []
    if not virtue_motifs.get("love_letter_eligible"):
        return violations
    letter = ((analysis.get("virtue_narrative") or {}).get("love_letter") or "").strip()
    if not letter:
        violations.append(
            "[C 位置⑤『项目的编写者想和你说』缺失] love_letter_eligible=true，但 "
            "virtue_narrative.love_letter 为空。"
        )
        return violations
    violations += _check_closing_h2("love_letter", letter)
    activated_ages = _ages_from_position2(activations)
    ages_in_letter = _extract_ages_in_text(letter)
    matched = ages_in_letter & activated_ages
    if len(matched) < 2:
        violations.append(
            f"[C 位置⑤呼应不足] love_letter 中匹配位置②具体年龄只有 "
            f"{sorted(matched)}（共 {len(matched)}），铁律要求 ≥2。"
        )
    return violations


def _check_silenced(analysis: dict, virtue_motifs: dict) -> list[str]:
    violations: list[str] = []
    silenced = virtue_motifs.get("silenced_motifs") or []
    if not silenced:
        return violations
    full_text = _all_analysis_text(analysis)
    motif_index = virtue_motifs.get("motif_index") or {}
    for mid in silenced:
        spec = motif_index.get(mid) or {}
        names: list[str] = []
        for key in ("name", "label", "title"):
            v = spec.get(key)
            if isinstance(v, str) and len(v) >= 3:
                names.append(v)
        for nm in names:
            if nm and nm in full_text:
                violations.append(
                    f"[D silenced泄漏] silenced 母题 {mid}（{nm!r}）被提到——"
                    "sileced_motifs 应在所有位置完全静默，连暗示都不许。"
                )
    return violations


def _check_position6(analysis: dict) -> list[str]:
    violations: list[str] = []
    free = ((analysis.get("virtue_narrative") or {}).get("free_speech") or "").strip()
    if not free:
        violations.append(
            "[E 位置⑥『我（大模型）想和你说』缺失] virtue_narrative.free_speech 为空 "
            "（所有命主无差别要求）。"
        )
        return violations
    violations += _check_closing_h2("free_speech", free)
    head = free[:80]
    tail = free[-80:]
    if not any(m in head for m in _FREE_SPEECH_OPEN_MARKERS):
        violations.append(
            f"[E 位置⑥开头标记缺失] free_speech 开头 80 字未命中任一标记："
            f"{_FREE_SPEECH_OPEN_MARKERS}"
        )
    if not any(m in tail for m in _FREE_SPEECH_CLOSE_MARKERS):
        violations.append(
            f"[E 位置⑥收尾标记缺失] free_speech 收尾 80 字未命中任一标记："
            f"{_FREE_SPEECH_CLOSE_MARKERS}"
        )
    n_zh = _zh_chars_len(free)
    if n_zh > 300:
        violations.append(
            f"[E 位置⑥超长] free_speech 汉字数 {n_zh} > 300（铁律 ≤ 300）。"
        )
    return violations


def audit(analysis: dict, virtue_motifs: dict) -> list[str]:
    activations = _extract_motif_activations(virtue_motifs)
    violations: list[str] = []
    violations += _check_position2(analysis, activations)
    violations += _check_position4(analysis, activations)
    violations += _check_position5(analysis, virtue_motifs, activations)
    violations += _check_silenced(analysis, virtue_motifs)
    violations += _check_position6(analysis)
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(
        description="v9 audit: virtue_recurrence_protocol 连续性铁律机械化",
    )
    ap.add_argument("--analysis", required=True,
                    help="output/X.analysis.json 或 .analysis.partial.json")
    ap.add_argument("--virtue-motifs", required=True,
                    help="output/X.virtue_motifs.json")
    ap.add_argument(
        "--allow-partial", action="store_true",
        help="允许位置 ④/⑤/⑥ 暂未写满（流式中间态）：缺失只 warn 不 fail",
    )
    args = ap.parse_args()

    analysis = _load_json(Path(args.analysis))
    virtue_motifs = _load_json(Path(args.virtue_motifs))

    violations = audit(analysis, virtue_motifs)

    if args.allow_partial:
        partial_safe_prefixes = (
            "[B 位置④顿悟段缺失]",
            "[C 位置⑤情书缺失]",
            "[E 位置⑥自由话缺失]",
        )
        violations = [v for v in violations if not v.startswith(partial_safe_prefixes)]

    if violations:
        print(
            f"[audit_virtue_continuity] {len(violations)} 条铁律违反："
            f"\n  - " + "\n  - ".join(violations),
            file=sys.stderr,
        )
        return 2

    print(
        f"[audit_virtue_continuity] PASS — "
        f"位置②G块 / 位置④trace+自审+共在 / 位置⑤呼应 / silenced静默 / 位置⑥首尾标记 全部通过。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
