"""audit_llm_invented.py · catalog 演化反馈机制（运维侧 · 可选）

按 ★★★★★★ catalog 开放性铁律 + 原则 15，扫描历史 LLM 输出（位置 ④ 顿悟段、
位置 ⑥ LLM 自由话）的 trace metadata，聚合所有标记为 `motif_origin: "llm_invented"`
的自创母题候选记录，输出"自创母题候选清单"供人审决定是否纳入 catalog。

输入扫描目录里的 LLM 解读 JSON / markdown / log 文件——任何包含 trace block 的
文本格式都行。匹配模式：

    motif_origin: llm_invented
    proposed_name: <name>
    proposed_detector_sketch: <sketch>

输出到 stdout 或 --out。统计：
    - 每个 proposed_name 出现的命主数 / 次数
    - 配套的 proposed_detector_sketch（去重展示）
    - 建议候选阈值：≥ N 个不同命主反复出现 → 列入 catalog 演化清单

本工具是 pure function：相同输入目录 → 字节相同输出。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


_MOTIF_ORIGIN_RE = re.compile(r"motif_origin\s*[:=]\s*['\"]?llm_invented['\"]?", re.IGNORECASE)
_PROPOSED_NAME_RE = re.compile(r"proposed_name\s*[:=]\s*['\"]([^'\"\n]+)['\"]", re.IGNORECASE)
_PROPOSED_SKETCH_RE = re.compile(
    r"proposed_detector_sketch\s*[:=]\s*['\"]([^'\"\n]+)['\"]", re.IGNORECASE
)
_BAZI_HASH_RE = re.compile(r"bazi[_-]?(?:signature|hash|id)\s*[:=]\s*['\"]([0-9a-f\-]+)['\"]", re.IGNORECASE)


def _scan_text(text: str, source: str) -> List[Dict[str, str]]:
    """扫描一段文本，返回所有 llm_invented 记录。"""
    if not _MOTIF_ORIGIN_RE.search(text):
        return []
    records: List[Dict[str, str]] = []
    name_matches = _PROPOSED_NAME_RE.findall(text)
    sketch_matches = _PROPOSED_SKETCH_RE.findall(text)
    bazi_matches = _BAZI_HASH_RE.findall(text)
    bazi_id = bazi_matches[0] if bazi_matches else "unknown"
    n = max(len(name_matches), 1)
    for i in range(n):
        name = name_matches[i] if i < len(name_matches) else "(unnamed)"
        sketch = sketch_matches[i] if i < len(sketch_matches) else "(no sketch)"
        records.append({
            "source": source,
            "bazi_id": bazi_id,
            "proposed_name": name.strip(),
            "proposed_detector_sketch": sketch.strip(),
        })
    return records


def _scan_dir(root: Path) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    if not root.exists():
        return out
    candidates = sorted(
        list(root.rglob("*.md")) + list(root.rglob("*.json"))
        + list(root.rglob("*.txt")) + list(root.rglob("*.log"))
    )
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        out.extend(_scan_text(text, str(path)))
    return out


def _aggregate(records: List[Dict[str, str]], min_unique_bazi: int) -> Dict[str, Any]:
    name_to_bazi: Dict[str, Set[str]] = defaultdict(set)
    name_to_sketches: Dict[str, Set[str]] = defaultdict(set)
    name_to_sources: Dict[str, List[str]] = defaultdict(list)
    for r in records:
        name = r["proposed_name"]
        name_to_bazi[name].add(r["bazi_id"])
        name_to_sketches[name].add(r["proposed_detector_sketch"])
        name_to_sources[name].append(r["source"])

    candidates: List[Dict[str, Any]] = []
    for name in sorted(name_to_bazi.keys()):
        unique_bazi = len(name_to_bazi[name])
        candidates.append({
            "proposed_name": name,
            "unique_bazi_count": unique_bazi,
            "total_occurrences": len(name_to_sources[name]),
            "sketches": sorted(name_to_sketches[name]),
            "promotion_recommended": unique_bazi >= min_unique_bazi,
            "sample_sources": sorted(set(name_to_sources[name]))[:5],
        })

    candidates.sort(key=lambda c: (-c["unique_bazi_count"], c["proposed_name"]))

    return {
        "schema": "audit_llm_invented/v1",
        "total_invented_records": len(records),
        "unique_proposed_names": len(name_to_bazi),
        "min_unique_bazi_for_promotion": min_unique_bazi,
        "candidates": candidates,
        "note": (
            "按 ★★★★★★ catalog 开放性铁律 + 原则 15 catalog 演化反馈机制："
            "promotion_recommended=true 的候选应进入人审流程，决定是否纳入下一版 catalog。"
            "永远不号称'完全'——catalog 会从 38 → 50 → 70，但不变成命主的牢笼。"
        ),
    }


def _stable_dump(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description="audit_llm_invented · catalog 演化反馈机制扫描器"
    )
    parser.add_argument("--scan", required=True,
                        help="要扫描的根目录（递归 .md / .json / .txt / .log）")
    parser.add_argument("--out", default="-",
                        help="输出 JSON 路径（默认 stdout）")
    parser.add_argument("--min-unique-bazi", type=int, default=3,
                        help="≥ 该值个不同命主 → promotion_recommended=true（默认 3）")
    args = parser.parse_args(argv)

    records = _scan_dir(Path(args.scan))
    out = _aggregate(records, args.min_unique_bazi)
    text = _stable_dump(out)
    if args.out == "-":
        sys.stdout.write(text)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        sys.stdout.write(
            f"[audit_llm_invented] records={out['total_invented_records']} "
            f"unique_names={out['unique_proposed_names']} → {args.out}\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
