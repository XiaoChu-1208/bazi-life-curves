#!/usr/bin/env python3
"""scripts/streaming_pipeline.py — v9.3 React-style streaming generator pipeline

把 v9 的「先一次性跑 score_curves 拿 curves.json，再 LLM 一段段写」改造成真正的
streaming generator：脚本算一段就 yield 一段，Agent 收到立即写 + send + stop turn，
然后下一次 turn 再 `--resume --next` 拿下一段，**不等全部生成完**。

6 个 stage 顺序：

    1. current_dayun            # 命主"今天"所在大运段（dayun_segments[i] + 该 10 年片段）
    2. current_dayun_liunian    # 当前 10 年逐年流年 + mangpai_events 命中
    3. other_dayuns             # 其它大运 segment 列表（不含 current）
    4. key_years                # peak/dip/shift + dispute_threshold 命中
    5. overall_and_life_review  # 整图统计 + 4 维 baseline + final aggregate
    6. closing                  # virtue_motifs declaration / love_letter / free_speech 数据钩子

输出：

  - stdout: NDJSON，每行一个 stage payload：`{"stage": "...", "payload": {...}, "ts_iso": "..."}`
  - 状态文件 `output/X.stream_state.json`：记录 cursor + 已完成 stage 的 payload 缓存，
    支持 `--resume <state> --next` 增量推进。

CLI 模式：

    # 全量一次性出 6 stage（用于 e2e / 渲染兜底）
    python scripts/streaming_pipeline.py stream --bazi X.json --stage all --state out/X.stream.json

    # 单 stage（典型 LLM 流式驱动）
    python scripts/streaming_pipeline.py stream --bazi X.json --stage current_dayun --state out/X.stream.json
    python scripts/streaming_pipeline.py stream --bazi X.json --resume out/X.stream.json --next

设计原则：

  - **只读 + bit-for-bit 等价**：内部一次性调用 `score_curves.score(...)` 计算所有曲线，
    各 stage 仅从结果里 slice 自己那一份；与旧的批量 `score_curves.py --out curves.json`
    产物完全一致（test 验证）。
  - **状态可序列化**：state 文件用 plain JSON，render_artifact 可通过 `--from-stream-state`
    反向还原一份与 curves.json 等价的 dict 喂给现有渲染管线（也就保留了 HTML 出图能力）。
  - **零依赖 PyYAML / 零网络**：与 v9 零依赖原则一致；仅依赖 stdlib + 已有 scripts/。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# §1 stage 定义
# ---------------------------------------------------------------------------

STAGES: tuple[str, ...] = (
    "current_dayun",
    "current_dayun_liunian",
    "other_dayuns",
    "key_years",
    "overall_and_life_review",
    "closing",
)

STREAM_STATE_VERSION = "v9.3"


# ---------------------------------------------------------------------------
# §2 工具：原子写 + state 读写
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp",
                                    dir=str(path.parent))
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


def _load_state(path: Optional[Path]) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"[streaming_pipeline] {path} 不是合法 JSON: {e}")


def _empty_state(bazi_path: str) -> dict:
    return {
        "version": STREAM_STATE_VERSION,
        "bazi_path": bazi_path,
        "completed_stages": [],
        "stages": {},
        "ts_started_iso": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------------------------
# §3 一次性算 curves（缓存到 state["_curves_cache_key"]）
# ---------------------------------------------------------------------------

def _compute_curves(bazi_path: Path,
                    *,
                    mangpai_path: Optional[Path] = None,
                    age_start: int = 0,
                    age_end: int = 80) -> tuple[dict, dict, Optional[dict]]:
    """加载 bazi.json + 调用 score_curves.score；返回 (bazi, curves, mangpai)。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from score_curves import score  # type: ignore

    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))
    mangpai = None
    if mangpai_path is not None and mangpai_path.exists():
        mangpai = json.loads(mangpai_path.read_text(encoding="utf-8"))

    curves = score(
        bazi,
        age_start=age_start,
        age_end=age_end,
        mangpai=mangpai,
    )
    return bazi, curves, mangpai


# ---------------------------------------------------------------------------
# §4 各 stage 的 payload 生成函数
# ---------------------------------------------------------------------------

def _stage_current_dayun(bazi: dict, curves: dict) -> dict:
    """命主"今天"所在大运段：bazi.current_dayun_label + 对应 dayun_segment + 该 10 年的
    summary（avg / peak / dip / 触发 phase / 关键互动）。"""
    label = bazi.get("current_dayun_label") or ""
    segments = curves.get("dayun_segments") or []
    cur_seg = next((s for s in segments if s.get("label") == label), None)
    pts = curves.get("points") or []
    cur_pts: List[dict] = []
    if cur_seg is not None:
        for p in pts:
            if cur_seg["start_age"] <= p["age"] <= cur_seg["end_age"]:
                cur_pts.append(p)
    summary = _summarize_points(cur_pts)
    return {
        "current_dayun_label": label,
        "segment": cur_seg,
        "n_years": len(cur_pts),
        "summary": summary,
        "phase": curves.get("phase") or {},
        "interactions_unique": _unique_interactions(cur_pts),
    }


def _stage_current_dayun_liunian(bazi: dict, curves: dict) -> dict:
    label = bazi.get("current_dayun_label") or ""
    segments = curves.get("dayun_segments") or []
    cur_seg = next((s for s in segments if s.get("label") == label), None)
    pts = curves.get("points") or []
    cur_pts: List[dict] = []
    if cur_seg is not None:
        for p in pts:
            if cur_seg["start_age"] <= p["age"] <= cur_seg["end_age"]:
                cur_pts.append(p)
    return {
        "current_dayun_label": label,
        "n_years": len(cur_pts),
        "yearly_points": cur_pts,
    }


def _stage_other_dayuns(bazi: dict, curves: dict) -> dict:
    label = bazi.get("current_dayun_label") or ""
    segments = curves.get("dayun_segments") or []
    pts = curves.get("points") or []
    others: List[dict] = []
    for seg in segments:
        if seg.get("label") == label:
            continue
        seg_pts = [p for p in pts if seg["start_age"] <= p["age"] <= seg["end_age"]]
        others.append({
            "segment": seg,
            "n_years": len(seg_pts),
            "summary": _summarize_points(seg_pts),
            "interactions_unique": _unique_interactions(seg_pts),
        })
    return {
        "n_segments": len(others),
        "segments": others,
    }


def _stage_key_years(bazi: dict, curves: dict) -> dict:
    forecast = curves.get("turning_points_future") or []
    disputes = curves.get("disputes") or []
    pts = curves.get("points") or []
    # peak/dip in entire span
    peaks: List[dict] = []
    if pts:
        for dim in ("spirit", "wealth", "fame", "emotion"):
            key = f"{dim}_yearly"
            top = max(pts, key=lambda p: p.get(key, 0))
            bot = min(pts, key=lambda p: p.get(key, 0))
            peaks.append({
                "dimension": dim,
                "peak": {"year": top["year"], "age": top["age"], "value": top.get(key)},
                "dip": {"year": bot["year"], "age": bot["age"], "value": bot.get(key)},
            })
    return {
        "turning_points_future": forecast,
        "disputes": disputes,
        "extremes": peaks,
        "dispute_threshold": curves.get("dispute_threshold"),
    }


def _stage_overall_and_life_review(bazi: dict, curves: dict) -> dict:
    pts = curves.get("points") or []
    base = curves.get("baseline") or {}
    aggregate: Dict[str, Any] = {}
    for dim in ("spirit", "wealth", "fame", "emotion"):
        key = f"{dim}_yearly"
        vals = [p.get(key, 0) for p in pts]
        if vals:
            aggregate[dim] = {
                "mean": round(sum(vals) / len(vals), 2),
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
                "baseline": base.get(dim),
            }
        else:
            aggregate[dim] = {
                "mean": None, "min": None, "max": None,
                "baseline": base.get(dim),
            }
    return {
        "n_years": len(pts),
        "age_range": [curves.get("age_start"), curves.get("age_end")],
        "baseline": base,
        "aggregate": aggregate,
        "phase": curves.get("phase") or {},
        "geju": curves.get("geju") or {},
        "yongshen": curves.get("yongshen") or {},
        "strength": curves.get("strength"),
    }


def _stage_closing(bazi: dict,
                   curves: dict,
                   *,
                   virtue_motifs: Optional[dict] = None) -> dict:
    """closing 数据钩子：来自 virtue_motifs.json（若给）。declaration / love_letter /
    free_speech 三段标题/可写性由协议规定，本 stage 只负责把数据 / 触发条件透传出去。"""
    vm = virtue_motifs or {}
    return {
        "love_letter_eligible": bool(vm.get("love_letter_eligible")),
        "convergence_years": vm.get("convergence_years") or [],
        "triggered_motifs": vm.get("triggered_motifs") or [],
        "headers": {
            "declaration": "## 我想和你说",
            "love_letter": "## 项目的编写者想和你说",
            "free_speech": "## 我（大模型）想和你说",
        },
    }


# ---------------------------------------------------------------------------
# §5 stage 拆分辅助
# ---------------------------------------------------------------------------

def _summarize_points(pts: List[dict]) -> Dict[str, Any]:
    if not pts:
        return {"n": 0}
    s = {"n": len(pts)}
    for dim in ("spirit", "wealth", "fame", "emotion"):
        key = f"{dim}_yearly"
        vals = [p.get(key, 0) for p in pts]
        s[dim] = {
            "mean": round(sum(vals) / len(vals), 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
            "first_year": pts[0]["year"],
            "last_year": pts[-1]["year"],
        }
    return s


def _unique_interactions(pts: List[dict]) -> List[str]:
    seen: List[str] = []
    bag: set[str] = set()
    for p in pts:
        for it in p.get("interactions") or []:
            key = it.get("key") if isinstance(it, dict) else str(it)
            if key and key not in bag:
                bag.add(key)
                seen.append(key)
    return seen


# ---------------------------------------------------------------------------
# §6 主流程
# ---------------------------------------------------------------------------

def _emit(stage: str, payload: dict) -> None:
    """把单个 stage payload 写到 stdout（NDJSON 一行）。"""
    record = {
        "stage": stage,
        "payload": payload,
        "ts_iso": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    sys.stdout.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _next_pending_stage(state: dict) -> Optional[str]:
    completed = set(state.get("completed_stages") or [])
    for s in STAGES:
        if s not in completed:
            return s
    return None


def _generate_stage(stage: str,
                    bazi: dict,
                    curves: dict,
                    *,
                    virtue_motifs: Optional[dict]) -> dict:
    if stage == "current_dayun":
        return _stage_current_dayun(bazi, curves)
    if stage == "current_dayun_liunian":
        return _stage_current_dayun_liunian(bazi, curves)
    if stage == "other_dayuns":
        return _stage_other_dayuns(bazi, curves)
    if stage == "key_years":
        return _stage_key_years(bazi, curves)
    if stage == "overall_and_life_review":
        return _stage_overall_and_life_review(bazi, curves)
    if stage == "closing":
        return _stage_closing(bazi, curves, virtue_motifs=virtue_motifs)
    raise SystemExit(f"[streaming_pipeline] 未知 stage: {stage!r}（合法：{list(STAGES)}）")


def _run_stages(stages: List[str],
                state: dict,
                state_path: Optional[Path],
                *,
                bazi: dict,
                curves: dict,
                virtue_motifs: Optional[dict]) -> None:
    completed = list(state.get("completed_stages") or [])
    cache: Dict[str, Any] = dict(state.get("stages") or {})
    for s in stages:
        payload = _generate_stage(s, bazi, curves, virtue_motifs=virtue_motifs)
        _emit(s, payload)
        cache[s] = payload
        if s not in completed:
            completed.append(s)
    state["completed_stages"] = completed
    state["stages"] = cache
    state["ts_updated_iso"] = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
    if state_path is not None:
        _atomic_write_json(state_path, state)


def _cmd_stream(args: argparse.Namespace) -> int:
    bazi_path = Path(args.bazi)
    if not bazi_path.exists():
        raise SystemExit(f"[streaming_pipeline] --bazi 不存在: {bazi_path}")

    state_path: Optional[Path] = Path(args.state) if args.state else None
    resume_path: Optional[Path] = Path(args.resume) if args.resume else None
    if resume_path is not None and state_path is None:
        state_path = resume_path
    state = _load_state(resume_path) if resume_path else (
        _load_state(state_path) if state_path else {}
    )
    if not state:
        state = _empty_state(str(bazi_path))

    mangpai_path = Path(args.mangpai) if args.mangpai else None
    virtue_motifs_path = Path(args.virtue_motifs) if args.virtue_motifs else None
    virtue_motifs = (
        json.loads(virtue_motifs_path.read_text(encoding="utf-8"))
        if virtue_motifs_path and virtue_motifs_path.exists()
        else None
    )

    bazi, curves, _ = _compute_curves(
        bazi_path,
        mangpai_path=mangpai_path,
        age_start=args.age_start,
        age_end=args.age_end,
    )

    if args.stage == "all":
        target_stages = list(STAGES)
    elif args.next or args.resume:
        nxt = _next_pending_stage(state)
        if nxt is None:
            print("[streaming_pipeline] 所有 stage 都已完成", file=sys.stderr)
            return 0
        target_stages = [nxt]
    else:
        if args.stage not in STAGES:
            raise SystemExit(
                f"[streaming_pipeline] 未知 --stage {args.stage!r}；合法：{list(STAGES)} 或 'all'"
            )
        target_stages = [args.stage]

    _run_stages(
        target_stages, state, state_path,
        bazi=bazi, curves=curves, virtue_motifs=virtue_motifs,
    )
    print(
        f"[streaming_pipeline] emitted {len(target_stages)} stage(s): "
        f"{target_stages}; total completed = {len(state['completed_stages'])}/{len(STAGES)}",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# §7 CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description="v9.3 React-style streaming generator pipeline · 6 个 stage 增量 yield",
    )
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("stream", help="emit 一个或多个 stage 到 stdout (NDJSON)")
    sp.add_argument("--bazi", required=True, help="bazi.json 路径（solve_bazi 产物）")
    sp.add_argument(
        "--stage",
        default=None,
        help=f"stage 名（{'|'.join(STAGES)}）或 'all'；与 --next/--resume 互斥",
    )
    sp.add_argument("--next", action="store_true",
                    help="自动选下一个未完成的 stage（搭配 --resume）")
    sp.add_argument("--resume", default=None,
                    help="resume from output/X.stream_state.json（兼具 --state 角色）")
    sp.add_argument("--state", default=None,
                    help="state 文件路径；不传则只 emit 不落盘（适合 stage=all 一次性）")
    sp.add_argument("--mangpai", default=None,
                    help="可选 mangpai.json，启用盲派烈度修正")
    sp.add_argument("--virtue-motifs", default=None,
                    help="可选 virtue_motifs.json，仅 closing stage 使用")
    sp.add_argument("--age-start", type=int, default=0)
    sp.add_argument("--age-end", type=int, default=80)
    sp.set_defaults(func=_cmd_stream)

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
