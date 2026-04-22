#!/usr/bin/env python3
"""scripts/audit_reference_consistency.py — v9.3 防回潮 audit

扫 LLM 在 skill 加载时会读到的所有 reference / 协议文件，找出**与机械护栏冲突**
的「正向引导」。典型冲突：

  - `references/multi_dim_xiangshu_protocol.md` 让 LLM 写 `## 走到这里`，但
    `_v9_guard._CLOSING_HEADER_FORBIDDEN_RE` 命中即 exit 10
  - `references/dayun_review_template.md` 强制「陀氏式自审句式」，但
    `tone_blacklist.yaml` v9.3 把「陀氏」全位置封禁，命中即 exit 5
  - `references/he_pan_protocol.md` 还在引「Step 2.7 询问输出格式」，但 v9.3
    SKILL.md 已删 Step 2.7，agent 跑合盘流程会被旧文档带偏

设计：

  - **scan_target**: SKILL.md / AGENTS.md / references/*.md（这些是 LLM 在 skill
    加载时会读到的「写作指南」，不是 schema / 数据 / catalog）
  - **whitelist scope**: 三类「合法引用」不算冲突：
    1. 显式负面措辞：「禁/退役/不允许/禁止/已删除/已废弃/banned/forbidden」邻近
    2. 显式 v9.3 标注：「v9.3 命名约定 / v9.3 banned / v9.3 退役」邻近
    3. 在代码块 / 表格的 forbidden 列里出现
  - **抛错**：写 stderr + exit 12（不 collide 现有 exit code）

CLI：

    python scripts/audit_reference_consistency.py [--paths SKILL.md AGENTS.md ...]
                                                  [--strict]

退出码：
  0  pass
  12 fail（找到冲突）
  13 配置错误
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# §1 默认 scan target
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SCAN: tuple[Path, ...] = (
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "AGENTS.md",
    *sorted((REPO_ROOT / "references").glob("*.md")),
)


# ---------------------------------------------------------------------------
# §2 banned terms（与 _v9_guard / tone_blacklist 一一对应）
# ---------------------------------------------------------------------------

# (term, severity, source) — severity 用于报告排序
BANNED_TERMS: tuple[tuple[str, str, str], ...] = (
    # tone_blacklist v9.3 banned_patterns
    ("陀式", "exit5", "tone_blacklist"),
    ("陀氏", "exit5", "tone_blacklist"),
    ("陀式贯穿", "exit5", "tone_blacklist"),
    ("陀氏贯穿", "exit5", "tone_blacklist"),
    ("陀式那一刀", "exit5", "tone_blacklist"),
    ("陀氏那一刀", "exit5", "tone_blacklist"),
    ("那一刀", "exit5", "tone_blacklist"),
    ("灵魂宣言", "exit5", "tone_blacklist"),
    ("承认人性", "exit5", "tone_blacklist"),
    ("承认维度", "exit5", "tone_blacklist"),
    # closing_header_forbidden（必须以 H2 形式出现才被 _v9_guard 命中，但若文档
    # 引导 LLM「首行写 ## 走到这里」也算 leak）
    ("## 走到这里", "exit10", "closing_header"),
    ("## 写到这里我想说", "exit10", "closing_header"),
    ("## 不在协议里的话", "exit10", "closing_header"),
    # SKILL.md v9.3 删除的 Step 2.7
    ("Step 2.7", "deprecated", "skill_step_27"),
    # ─── v9.3 合盘 5 条（he_pan v9.3 化）───────────────────────────
    # 旧合盘 v8 caveat：「合盘场景暂未升级到 v8，仍走旧 R0/R1 健康三问」
    ("暂未升级到 v8", "deprecated", "hepan_v8_caveat"),
    ("暂未升级到v8", "deprecated", "hepan_v8_caveat"),
    # 旧合盘 confidence 表述：「confidence 受双方 R1 命中率限制 / 双方 R1 健康三问」
    ("双方 R1 命中率", "deprecated", "hepan_double_r1_hit_rate"),
    ("双方R1命中率", "deprecated", "hepan_double_r1_hit_rate"),
    # 旧合盘 R0 反询问 + 健康三问命名（v9.3 合盘走 adaptive_elicit 多人编排）
    ("R0 反询问", "deprecated", "hepan_r0_anti_query"),
    # 「健康三问」是 v6/v7 单盘旧词；合盘文档若仍引用必须改为 adaptive_elicit
    ("健康三问", "deprecated", "hepan_health_three_questions"),
)


# ---------------------------------------------------------------------------
# §3 negation / v9.3 hint detector
# ---------------------------------------------------------------------------

# tone 类（exit5）允许的 negation tokens —— 比较宽松，因为 tone 词广泛
# 出现在协议元说明里
_NEGATION_TOKENS_TONE = (
    "禁", "退役", "不允许", "禁止", "已删除", "已废弃", "banned",
    "forbidden", "不得", "命中即", "拒绝", "封禁", "deprecate",
    "v9.3 banned", "v9.3 命名约定", "v9.3 已删除", "v9.3 退役",
    "v9.3 三段", "v9.3 重命名", "禁用", "废弃", "已退役", "兼容",
    "旧 v9", "(旧 v9)", "（旧 v9）", "exit 5", "exit 10", "exit 11",
    "已被", "已不", "旧白名单", "下表禁", "命中即拒",
    "schema 名", "node key", "协议内部", "章节元名称", "脚手架名",
    "scan_tone", "check_closing_header", "tone_blacklist",
)

# closing_header / deprecated 类（exit10 / Step 2.7）只允许"靠近"的强 negation
# token —— 出现 `v9.3 命名约定` 之类宽泛 banner **不算豁免**，因为这两类是
# 真正的协议矛盾陷阱（正向引导 LLM 写 `## 走到这里` 等 H2 / 跑 Step 2.7
# 流程），必须显式标注「已退役 / 命中即 / 禁止」才算合法引用。
_NEGATION_TOKENS_HEADER = (
    "已退役", "退役，命中", "命中即", "禁止", "已删除", "已废弃",
    "banned", "deprecated", "封禁", "(旧 v9)", "（旧 v9）",
    "旧 v9 白名单", "exit 10", "已不", "已废", "请勿", "不要写",
    "v9.3 已删除", "v9.3 退役",
)

# negation 检测窗口（命中行前后 ±N 行内任一 token 出现 → 合法）
_NEGATION_LINES = 5


def _is_legitimate_negation_context(
    lines: list[str], lineno: int, term: str, severity: str,
) -> bool:
    """判断 lines[lineno] 中出现的 term 是否处于「负面引用」语境。

    判定规则按 severity 区分：

    - tone 类（exit5）：协议章节标题 / blockquote 元说明 / 邻近 negation 都算合法
    - closing_header 类（exit10）：closing 类 leak 是真正的协议矛盾陷阱
      （正向引导 LLM 写 `## 走到这里` H2 等），只接受**邻近 negation**作为豁免
    - deprecated 类（Step 2.7 等）：同 closing_header
    """
    line = lines[lineno]
    if term not in line:
        return True

    stripped = line.lstrip()

    # tone 类才允许标题 / blockquote 豁免（这两类是协议元名称的自然栖息地）
    if severity == "exit5":
        if stripped.startswith("#"):
            return True
        if stripped.startswith(">"):
            return True

    tokens = (
        _NEGATION_TOKENS_TONE if severity == "exit5" else _NEGATION_TOKENS_HEADER
    )

    # 收集 ±N 行窗口检测 negation
    lo = max(0, lineno - _NEGATION_LINES)
    hi = min(len(lines), lineno + _NEGATION_LINES + 1)
    window_text = "\n".join(lines[lo:hi])

    if any(tok in window_text for tok in tokens):
        return True

    # 表格行 + 行内负面 token（双保险）
    if "|" in line and any(tok in line for tok in tokens):
        return True

    return False


# ---------------------------------------------------------------------------
# §4 扫描
# ---------------------------------------------------------------------------

@dataclass
class Hit:
    file: Path
    lineno: int
    line: str
    term: str
    severity: str
    source: str

    def render(self) -> str:
        excerpt = self.line.strip()
        if len(excerpt) > 160:
            excerpt = excerpt[:155] + " …"
        try:
            display_path: object = self.file.relative_to(REPO_ROOT)
        except ValueError:
            display_path = self.file
        return (
            f"  · {display_path}:{self.lineno}  "
            f"[{self.severity} · {self.source}]  hit={self.term!r}\n"
            f"      {excerpt}"
        )


# 文件顶部 ~60 行内出现以下任一字符串，视为「全文 v9.3 命名约定 banner 已声明」：
# 此后该文件的 tone-class 命中（陀氏/灵魂宣言/承认人性 等）一律放行；
# 但 closing_header 类（## 走到这里 等正向 H2 引导）和 deprecated（Step 2.7）
# 仍按原规则扫——这两类是真正的协议矛盾陷阱，不属于「内部脚手架名」。
_FILE_BANNER_TOKENS = (
    "v9.3 命名约定",
    "v9.3 命名约定（强制",
    "v9.3 命名约定（重要",
    "v9.3 命名约定 · ",
)
_FILE_BANNER_HEAD_LINES = 60

# 该 severity 不受 file-banner 豁免（即文件顶部 banner 也救不了它们）
_NO_BANNER_EXEMPT = frozenset({"exit10", "deprecated"})


def _has_v93_file_banner(lines: list[str]) -> bool:
    head = "\n".join(lines[:_FILE_BANNER_HEAD_LINES])
    return any(tok in head for tok in _FILE_BANNER_TOKENS)


def _scan_file(path: Path) -> List[Hit]:
    if not path.exists() or not path.is_file():
        return []
    hits: List[Hit] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    has_banner = _has_v93_file_banner(lines)
    for idx, line in enumerate(lines):
        ln_no = idx + 1
        for term, sev, src in BANNED_TERMS:
            if term not in line:
                continue
            if has_banner and sev not in _NO_BANNER_EXEMPT:
                continue
            if _is_legitimate_negation_context(lines, idx, term, sev):
                continue
            hits.append(Hit(path, ln_no, line, term, sev, src))
    return hits


def audit(paths: Optional[List[Path]] = None) -> List[Hit]:
    targets = list(paths) if paths else list(DEFAULT_SCAN)
    all_hits: List[Hit] = []
    for p in targets:
        all_hits.extend(_scan_file(p))
    return all_hits


# ---------------------------------------------------------------------------
# §5 CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=("v9.3 防回潮 audit：扫 SKILL/AGENTS/references 找出与"
                     "机械护栏冲突的正向引导（旧 closing header / 旧 tone /"
                     " Step 2.7 残骸）"),
    )
    ap.add_argument(
        "--paths", nargs="*", default=None,
        help="自定义 scan 目标（默认 SKILL.md + AGENTS.md + references/*.md）",
    )
    ap.add_argument(
        "--strict", action="store_true",
        help="任一 hit → exit 12；不传则只打印 warning + exit 0",
    )
    args = ap.parse_args()

    paths: Optional[List[Path]] = None
    if args.paths:
        paths = [Path(p).resolve() for p in args.paths]
        for p in paths:
            if not p.exists():
                print(f"[audit_reference_consistency] 路径不存在: {p}",
                      file=sys.stderr)
                return 13

    hits = audit(paths)
    if not hits:
        print("[audit_reference_consistency] PASS · 未发现协议回潮 leak。")
        return 0

    by_severity: dict[str, List[Hit]] = {}
    for h in hits:
        by_severity.setdefault(h.severity, []).append(h)
    order = ("exit5", "exit10", "exit11", "deprecated")
    print(
        f"[audit_reference_consistency] 发现 {len(hits)} 处 v9.3 协议回潮 leak："
        f"\n  · LLM 在 skill 加载时会读到这些文件并被旧措辞 / 旧流程带偏；"
        f"\n  · 写出来后会被 _v9_guard / tone_blacklist 在最后一刻 exit；"
        f"\n  · 表现为「按文档写 → 落盘 fail」的协议自相矛盾陷阱。",
        file=sys.stderr,
    )
    for sev in order:
        if sev not in by_severity:
            continue
        print(f"\n  [{sev}] · {len(by_severity[sev])} 处：", file=sys.stderr)
        for h in by_severity[sev]:
            print(h.render(), file=sys.stderr)
    print(
        "\n  修复建议："
        "\n    · exit5  → 把正向引导改写或加 v9.3 退役脚注（同行加「v9.3 退役 / "
        "禁 / banned」等 _NEGATION_TOKENS 之一）"
        "\n    · exit10 → closing header 必须用 v9.3 三段（`## 我想和你说` / "
        "`## 项目的编写者想和你说` / `## 我（大模型）想和你说`）"
        "\n    · deprecated → Step 2.7 等已删流程必须从协议文件里移除或加退役标注",
        file=sys.stderr,
    )

    if args.strict:
        return 12
    print(
        "[audit_reference_consistency] 非 strict 模式，本次不 fail。"
        "推荐 CI 用 --strict 阻断回潮。", file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
