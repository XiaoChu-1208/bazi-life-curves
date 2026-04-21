#!/usr/bin/env python3
"""append_analysis_node.py — v9 流式可观测增量落盘工具

LLM 每写完一节 analysis（Node 1 整图 / Node 2 spirit / ... / Node N free_speech），
立刻调用本脚本把这节的 markdown 写到 `output/X.analysis.partial.json` 里。
用户随时可以：

    python scripts/render_artifact.py \\
        --curves output/X.curves.json \\
        --analysis output/X.analysis.partial.json \\
        --virtue-motifs output/X.virtue_motifs.json \\
        --allow-partial \\
        --out output/X.partial.html

…来看 LLM 写到哪儿了，未写的节会显示「⌛ 流式写作中」占位。

这是 v9 流式铁律的物理可观测面 —— 防止 LLM 自报"已经分节了"但实际还在憋整段。

支持的 node key（与 chart_artifact.html.j2 / render_artifact.py LIFE_REVIEW_SCHEMA 对齐）：

    overall                                    → analysis.overall
    life_review.spirit / wealth / fame / emotion → analysis.life_review.{spirit|wealth|fame|emotion}
    virtue_narrative.opening                   → analysis.virtue_narrative.opening              位置①
    virtue_narrative.convergence_notes         → analysis.virtue_narrative.convergence_notes    位置③
    virtue_narrative.declaration               → analysis.virtue_narrative.declaration          位置④
    virtue_narrative.love_letter               → analysis.virtue_narrative.love_letter          位置⑤
    virtue_narrative.free_speech               → analysis.virtue_narrative.free_speech          位置⑥
    dayun_reviews.<label>                      → analysis.dayun_reviews[<label>]
    era_narratives.<id>                        → analysis.era_narratives[<id>]
    key_years.<index>                          → analysis.key_years[<index>] (markdown 写到 .body)

用法：

    # 写 Node 1 整图综合分析（从 stdin）
    echo "## 整图综合分析\\n\\nMarkdown 内容..." | \\
        python scripts/append_analysis_node.py --state output/test1.analysis.partial.json --node overall

    # 写 Node 5 emotion（从文件）
    python scripts/append_analysis_node.py \\
        --state output/test1.analysis.partial.json \\
        --node life_review.emotion \\
        --markdown-file /tmp/node5_emotion.md

    # 写 Node 1.5 承认维度·开篇悬疑（位置①）
    python scripts/append_analysis_node.py \\
        --state output/test1.analysis.partial.json \\
        --node virtue_narrative.opening \\
        --markdown "这一生的主题词，可能是「..」。但要等到 50 岁回头看才确认。"

    # 写大运段评价
    python scripts/append_analysis_node.py \\
        --state output/test1.analysis.partial.json \\
        --node "dayun_reviews.戊午" \\
        --markdown-file /tmp/dayun_wuwu.md

每次调用都是「读 → merge → 原子写回」，所以多次调用幂等可叠加。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

VALID_LIFE_REVIEW_KEYS = {"spirit", "wealth", "fame", "emotion"}
VALID_VIRTUE_KEYS = {
    "opening",
    "convergence_notes",
    "declaration",
    "love_letter",
    "free_speech",
}


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"[append_analysis_node] {path} 不是合法 JSON: {e}")


def _atomic_write_json(path: Path, data: dict) -> None:
    """原子写：先写 .tmp 再 rename。避免中途崩溃留下半截 JSON 让下次 render 崩。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _set_node(state: dict, node: str, markdown: str) -> str:
    """把 markdown 写到 state 对应路径。返回人类可读的写入位置描述。"""
    if node == "overall":
        state["overall"] = markdown
        return "analysis.overall"

    if node.startswith("life_review."):
        sub = node.split(".", 1)[1]
        if sub not in VALID_LIFE_REVIEW_KEYS:
            raise SystemExit(
                f"[append_analysis_node] 未知 life_review key: {sub!r}（支持：{sorted(VALID_LIFE_REVIEW_KEYS)}）"
            )
        state.setdefault("life_review", {})[sub] = markdown
        return f"analysis.life_review.{sub}"

    if node.startswith("virtue_narrative."):
        sub = node.split(".", 1)[1]
        if sub not in VALID_VIRTUE_KEYS:
            raise SystemExit(
                f"[append_analysis_node] 未知 virtue_narrative key: {sub!r}（支持：{sorted(VALID_VIRTUE_KEYS)}）"
            )
        state.setdefault("virtue_narrative", {})[sub] = markdown
        return f"analysis.virtue_narrative.{sub}"

    if node.startswith("dayun_reviews."):
        label = node.split(".", 1)[1]
        if not label:
            raise SystemExit("[append_analysis_node] dayun_reviews.<label> 不能为空")
        state.setdefault("dayun_reviews", {})[label] = markdown
        return f"analysis.dayun_reviews[{label!r}]"

    if node.startswith("era_narratives."):
        eid = node.split(".", 1)[1]
        if not eid:
            raise SystemExit("[append_analysis_node] era_narratives.<id> 不能为空")
        state.setdefault("era_narratives", {})[eid] = markdown
        return f"analysis.era_narratives[{eid!r}]"

    if node.startswith("key_years."):
        rest = node.split(".", 1)[1]
        try:
            idx = int(rest)
        except ValueError:
            raise SystemExit(
                f"[append_analysis_node] key_years.<index> 必须是整数，收到 {rest!r}"
            )
        ky = state.setdefault("key_years", [])
        # 自动扩容（前面的 slot 用空 dict 占位，避免 IndexError）
        while len(ky) <= idx:
            ky.append({})
        # 把 markdown 写进 .body；如已有结构化字段就保留
        if not isinstance(ky[idx], dict):
            ky[idx] = {}
        ky[idx]["body"] = markdown
        return f"analysis.key_years[{idx}].body"

    raise SystemExit(
        f"[append_analysis_node] 未知 node 路径: {node!r}\n"
        f"  支持：overall | life_review.<spirit|wealth|fame|emotion>"
        f" | virtue_narrative.<opening|convergence_notes|declaration|love_letter|free_speech>"
        f" | dayun_reviews.<label> | era_narratives.<id> | key_years.<index>"
    )


def _read_markdown(args) -> str:
    if args.markdown is not None:
        return args.markdown
    if args.markdown_file is not None:
        path = Path(args.markdown_file)
        if not path.exists():
            raise SystemExit(f"[append_analysis_node] markdown 文件不存在: {path}")
        return path.read_text(encoding="utf-8")
    # 否则读 stdin
    if sys.stdin.isatty():
        raise SystemExit(
            "[append_analysis_node] 必须提供 --markdown / --markdown-file，"
            "或从 stdin 管道传入 markdown 内容"
        )
    return sys.stdin.read()


def main() -> None:
    ap = argparse.ArgumentParser(
        description="v9 流式可观测：增量把 analysis Node markdown 写到 partial JSON",
    )
    ap.add_argument(
        "--state",
        required=True,
        help="output/X.analysis.partial.json 路径（不存在会自动创建）",
    )
    ap.add_argument(
        "--node",
        required=True,
        help="节路径，例如：overall | life_review.emotion | virtue_narrative.opening "
        "| dayun_reviews.戊午 | key_years.3",
    )
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--markdown", default=None, help="直接传 markdown 字符串")
    src.add_argument(
        "--markdown-file",
        default=None,
        help="从文件读 markdown（推荐：长 markdown 用 heredoc 写到 /tmp 再传文件）",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="静默模式，不输出写入摘要（默认会打印 '已写入 X 字符到 Y'）",
    )
    args = ap.parse_args()

    state_path = Path(args.state)
    state = _load_state(state_path)
    markdown = _read_markdown(args)

    if not markdown.strip():
        raise SystemExit(
            f"[append_analysis_node] 拒绝写入空 markdown 到 {args.node}"
            f"（流式 emit 也至少要写一句话占位）"
        )

    location = _set_node(state, args.node, markdown)
    _atomic_write_json(state_path, state)

    if not args.quiet:
        print(
            f"[append_analysis_node] {len(markdown):>5} 字符 → {location}  "
            f"(state: {state_path})",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
