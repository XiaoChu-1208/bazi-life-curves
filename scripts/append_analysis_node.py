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
    virtue_narrative.declaration               → analysis.virtue_narrative.declaration          位置④「我想和你说」（v9.3）
    virtue_narrative.love_letter               → analysis.virtue_narrative.love_letter          位置⑤「项目的编写者想和你说」（v9.3）
    virtue_narrative.free_speech               → analysis.virtue_narrative.free_speech          位置⑥「我（大模型）想和你说」（v9.3）
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

    # 写 Node 1.5 「我想和你说的话」开篇悬疑（位置①）
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
import datetime as _dt
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

# v9 五阶段节序（render_artifact --required-node-order 默认校验）：
#   ① opening         位置①（开篇悬疑 / 暗线起手）
#   ② current_dayun   当前大运段评价（包含其十年流年）
#   ③ liunian.<year>  当前大运十年内逐年流年（含平淡年也要落字）
#   ④ dayun_reviews.<其它 label> 其它大运
#   ⑤ key_years       关键流年（峰/谷/转折）
#   ⑥ overall + life_review.{spirit|wealth|fame|emotion}
#   ⑦ closing：declaration / love_letter / free_speech（去模板化标题）
#
# G 块（位置②大运末母题侧记）继续嵌在 dayun_reviews.<label> markdown 文末，
# **不**单独开 dayun_virtue.<label> node（按 §protocols_rewrite 决议保留嵌入式）。


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

    if node.startswith("liunian."):
        rest = node.split(".", 1)[1]
        try:
            year = int(rest)
        except ValueError:
            raise SystemExit(
                f"[append_analysis_node] liunian.<year> 必须是 4 位年份整数，收到 {rest!r}"
            )
        if year < 1900 or year > 2200:
            raise SystemExit(
                f"[append_analysis_node] liunian.<year> 越界（1900-2200），收到 {year}"
            )
        ln = state.setdefault("liunian", {})
        ln[str(year)] = markdown
        return f"analysis.liunian[{year}]"

    raise SystemExit(
        f"[append_analysis_node] 未知 node 路径: {node!r}\n"
        f"  支持：overall | life_review.<spirit|wealth|fame|emotion>"
        f" | virtue_narrative.<opening|convergence_notes|declaration|love_letter|free_speech>"
        f" | dayun_reviews.<label> | era_narratives.<id> | key_years.<index>"
        f" | liunian.<year>"
    )


def _append_stream_log(state: dict, node: str, location: str, size: int) -> None:
    """v9 流式可观测：每次写入追加 _stream_log 一条。

    render_artifact --require-streamed-emit 会扫此列表：若发现同一帧（≤ 60s）
    内突击塞了 ≥4 个节，判定 LLM 在伪流式（一次跑完再切片重发），exit 4。

    v9.3 R-STREAM-1：再加 agent_turn_id（来自环境变量 BAZI_AGENT_TURN_ID，
    由宿主 / Cursor / MCP 在每个 LLM turn 注入；缺失时回退到 ts_iso 当伪 turn_id）。
    若本次 turn_id 与上一次相同 → 视为「同一 turn 内连续 append_analysis_node ≥ 2 次」，
    违反 R-STREAM-1（应该写一节立刻 stop turn 让用户读到再继续）。
    违规计入 state['_stream_violations']，render_artifact --audit-stream-batching
    命中 ≥ 1 → exit 11。
    """
    log = state.setdefault("_stream_log", [])
    raw_turn = os.environ.get("BAZI_AGENT_TURN_ID", "").strip()
    ts_iso = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    ts_unix = int(_dt.datetime.now().timestamp())
    turn_id = raw_turn or f"ts:{ts_iso}"

    prev_turn_id = log[-1].get("agent_turn_id") if log else None
    same_turn_violation = bool(raw_turn) and prev_turn_id == turn_id and prev_turn_id is not None

    log.append({
        "ts_iso": ts_iso,
        "ts_unix": ts_unix,
        "node": node,
        "location": location,
        "markdown_chars": size,
        "agent_turn_id": turn_id,
    })

    if same_turn_violation:
        prev_node = log[-2].get("node", "<?>") if len(log) >= 2 else "<?>"
        print(
            f"[append_analysis_node] WARN: R-STREAM-1 违规 — agent_turn_id={turn_id!r} "
            f"内连续 append：上一次 node={prev_node!r}，本次 node={node!r}。"
            f" v9.3 流式协议要求每节 send 后立刻 stop turn。",
            file=sys.stderr,
        )
        violations = state.setdefault("_stream_violations", [])
        violations.append({
            "rule": "R-STREAM-1",
            "ts_iso": ts_iso,
            "agent_turn_id": turn_id,
            "prev_node": prev_node,
            "current_node": node,
            "reason": "same agent_turn_id append ≥ 2 nodes (no stop turn between sections)",
        })


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

    # v9 调性铁律：写入前先 tone scan + phase leak scan（whitelisted 节走例外）
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from _v9_guard import (  # type: ignore
            enforce_tone,
            enforce_no_phase_leak_in_message,
            check_message_heading_count,
        )
    except ImportError as e:
        raise SystemExit(f"[append_analysis_node] 找不到 _v9_guard：{e}")
    enforce_tone(markdown, node=args.node, raise_on_hit=True)
    enforce_no_phase_leak_in_message(markdown, raise_on_hit=True)

    # v9.3 R-STREAM-2：单节 markdown 顶级 ## heading ≥ 2 → 视为 "在一节里塞了多节"。
    # closing 三段在最后一条 turn 允许紧邻出现 → free_speech 节豁免（最末段）。
    allow_chain = args.node == "virtue_narrative.free_speech"
    violation = check_message_heading_count(markdown, allow_closing_chain=allow_chain)
    if violation is not None:
        raise SystemExit(
            f"[append_analysis_node] R-STREAM-2 违规 — node={args.node!r} 一次写入了 "
            f"{violation.count} 个顶级 ## heading：{list(violation.headings)}\n"
            f"  · v9.3 单节单 message 铁律：每节只写一个 ## 标题 + 正文，写完立即 send + stop turn。\n"
            f"  · 例外：closing 三段（declaration / love_letter / free_speech）允许在最后\n"
            f"    一条 turn 内紧邻出现，但仍只能一次 append 一节。\n"
            f"  · 详见 AGENTS.md §v9 流式铁律 R-STREAM-2"
        )

    location = _set_node(state, args.node, markdown)
    _append_stream_log(state, args.node, location, len(markdown))
    _atomic_write_json(state_path, state)

    if not args.quiet:
        print(
            f"[append_analysis_node] {len(markdown):>5} 字符 → {location}  "
            f"(state: {state_path})",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
