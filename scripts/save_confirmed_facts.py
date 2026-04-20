#!/usr/bin/env python3
"""save_confirmed_facts.py — 用户校验反馈固化器（P5，2026-04，from 1996 八字失败教训）。

为什么需要这个？
================
失败模式：每次跑同一八字都要重新问一轮校验问题；用户答过的"对/不对/部分对"
没有被记下来，下一次重跑的 LLM 又会重新踩相同的坑。

解决方案：用户每次校验完，把 R1/R2 反馈 + 文字补充固化到一个本地 JSON：
  - 默认存到工作目录 `output/confirmed_facts.json`（项目内）
  - 也可以指定 `--memory-dir ~/.bazi-curves-memory/` 跨项目持久化
  - 文件名按八字本身做 key（同一八字所有信息合并）

`render_artifact.py` 跑的时候自动读这个文件，注入到 LLM analysis context，
让 LLM 在写 overall / dayun_review 时能直接复用"上次用户已确认的事实 / 已纠正的偏差"，
不再重复问，也不再重复犯错。

使用方式
========

# 把这次校验的反馈写进 confirmed_facts.json
python3 save_confirmed_facts.py --bazi output/bazi.json --append <<EOF
{
  "round": "R1",
  "trait_or_anchor": "外燥内湿（干头烈、地支湿）",
  "user_response": "对",
  "user_note": null
}
{
  "round": "R1",
  "trait_or_anchor": "包容培养型——爱铺垫、不爱出头",
  "user_response": "部分对",
  "user_note": "我以前都是带头做原创动画的导演，管二三十人的公司"
}
EOF

# 列出已确认事实
python3 save_confirmed_facts.py --bazi output/bazi.json --list

# 添加自由形式的"已确认事件 / 已纠正偏差"
python3 save_confirmed_facts.py --bazi output/bazi.json --add-fact \\
    "用户 2014 年得新人奖（fame 上升），脚本曾误判为 down，已经反向"
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _bazi_key(bazi: dict) -> str:
    """八字唯一 key：八字字符串 + 性别 + 出生年（避免名字撞车）。"""
    pillars = "".join(p["gan"] + p["zhi"] for p in bazi["pillars"])
    gender = bazi.get("gender", "?")
    birth = bazi.get("birth_year", "?")
    return f"{pillars}_{gender}_{birth}"


def _load(path: Path) -> Dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _empty_record(bazi: dict) -> Dict:
    return {
        "bazi_key": _bazi_key(bazi),
        "pillars_str": " ".join(p["gan"] + p["zhi"] for p in bazi["pillars"]),
        "gender": bazi.get("gender"),
        "birth_year": bazi.get("birth_year"),
        "first_seen": dt.date.today().isoformat(),
        "last_updated": dt.date.today().isoformat(),
        "validations": [],         # R1/R2 反馈条目
        "free_facts": [],          # 自由形式的"已确认 / 已纠正"事实
        "structural_corrections": [],  # 结构性纠错（如：用户体感→重判 climate）
    }


def append_validation(rec: Dict, items: List[Dict]):
    rec["validations"].extend(items)
    rec["last_updated"] = dt.date.today().isoformat()


def append_fact(rec: Dict, fact: str, source: str = "manual"):
    rec["free_facts"].append({
        "added": dt.date.today().isoformat(),
        "fact": fact,
        "source": source,
    })
    rec["last_updated"] = dt.date.today().isoformat()


def append_structural(rec: Dict, kind: str, before: str, after: str, reason: str):
    rec["structural_corrections"].append({
        "added": dt.date.today().isoformat(),
        "kind": kind,
        "before": before,
        "after": after,
        "reason": reason,
    })
    rec["last_updated"] = dt.date.today().isoformat()


def main():
    ap = argparse.ArgumentParser(description="confirmed_facts 读写工具 (P5)")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径（用来生成 bazi_key）")
    ap.add_argument("--out", default="output/confirmed_facts.json",
                    help="confirmed_facts.json 路径（默认项目 output/）")
    ap.add_argument("--memory-dir", default=None,
                    help="可选：跨项目持久化目录（如 ~/.bazi-curves-memory/）")
    ap.add_argument("--append", action="store_true",
                    help="从 stdin 读 JSON Lines 形式的 validation items 追加")
    ap.add_argument("--add-fact", default=None, help="追加一条自由形式事实")
    ap.add_argument("--add-structural", nargs=3, metavar=("KIND", "BEFORE", "AFTER"),
                    help="追加一条结构性纠错（如 climate 燥湿 寒湿） + --reason")
    ap.add_argument("--reason", default="", help="--add-structural 的原因说明")
    ap.add_argument("--list", action="store_true", help="列出所有已确认事实")

    args = ap.parse_args()

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    out_path = Path(args.out)

    # 跨项目持久化路径（可选）
    mem_path = None
    if args.memory_dir:
        mem_dir = Path(args.memory_dir).expanduser()
        mem_path = mem_dir / f"{_bazi_key(bazi)}.json"

    # 优先从 memory_dir 加载（更权威），再合并 project-local
    rec = _load(mem_path) if (mem_path and mem_path.exists()) else _load(out_path)
    if not rec:
        rec = _empty_record(bazi)

    if args.append:
        # stdin 是 JSON Lines
        items = []
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[skip] bad line: {line[:60]}... ({e})", file=sys.stderr)
        append_validation(rec, items)
        print(f"[save_confirmed_facts] +{len(items)} validations")

    if args.add_fact:
        append_fact(rec, args.add_fact)
        print(f"[save_confirmed_facts] +fact: {args.add_fact}")

    if args.add_structural:
        kind, before, after = args.add_structural
        append_structural(rec, kind, before, after, args.reason)
        print(f"[save_confirmed_facts] +structural correction: {kind}: {before} → {after}")

    if args.list:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        return

    _save(out_path, rec)
    if mem_path:
        _save(mem_path, rec)
    print(f"[save_confirmed_facts] wrote {out_path}"
          + (f" + {mem_path}" if mem_path else "")
          + f"  ({len(rec['validations'])} validations, "
          + f"{len(rec['free_facts'])} free facts, "
          + f"{len(rec['structural_corrections'])} structural corrections)")


if __name__ == "__main__":
    main()
