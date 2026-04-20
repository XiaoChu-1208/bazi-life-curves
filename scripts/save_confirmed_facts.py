#!/usr/bin/env python3
"""save_confirmed_facts.py — 用户校验反馈固化器（P5，2026-04）。

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
        "schema_version": 8,
        "bazi_key": _bazi_key(bazi),
        "pillars_str": " ".join(p["gan"] + p["zhi"] for p in bazi["pillars"]),
        "gender": bazi.get("gender"),
        "birth_year": bazi.get("birth_year"),
        "first_seen": dt.date.today().isoformat(),
        "last_updated": dt.date.today().isoformat(),
        "validations": [],          # 旧 R1/R2 反馈条目（v7 兼容）
        "user_choices": {},          # v8 · 合并视图 {question_id: option_id}（兼容老读取方）
        "user_choices_by_round": {   # v8.1 · 区分 R1 / R2 答案（两轮校验协议）
            "r1": {},
            "r2": {},
        },
        "phase_decision": None,      # v8 · 最近一次 phase_posterior 的输出快照
        "phase_confirmation": None,  # v8.1 · R2 confirmation_status 快照
        "free_facts": [],            # 自由形式的"已确认 / 已纠正"事实
        "structural_corrections": [],  # 结构性纠错（如：用户体感→重判 climate）
    }


def _migrate_record(rec: Dict, bazi: dict) -> Dict:
    """v7 → v8 / v8.1 schema migration · 兼容旧 confirmed_facts.json。"""
    if not rec:
        return _empty_record(bazi)
    sv = rec.get("schema_version", 0)
    # v7 → v8
    if sv < 8:
        rec.setdefault("user_choices", {})
        rec.setdefault("phase_decision", None)
        sv = 8
    # v8 → v8.1（增加 round-tracking）
    rec.setdefault("user_choices_by_round", {"r1": dict(rec.get("user_choices") or {}), "r2": {}})
    rec.setdefault("phase_confirmation", None)
    rec["schema_version"] = 8
    rec["last_updated"] = dt.date.today().isoformat()
    return rec


def append_user_choices(
    rec: Dict,
    choices: Dict[str, str],
    phase_decision: Optional[Dict] = None,
    round_label: str = "r1",
    phase_confirmation: Optional[Dict] = None,
):
    """v8 · 把 user_answers + 后验快照写入 confirmed_facts；按 round 分桶存储。"""
    rec.setdefault("user_choices", {}).update(choices)
    by_round = rec.setdefault("user_choices_by_round", {"r1": {}, "r2": {}})
    by_round.setdefault(round_label, {}).update(choices)
    if phase_decision is not None:
        rec["phase_decision"] = phase_decision
    if phase_confirmation is not None:
        rec["phase_confirmation"] = phase_confirmation
    rec["last_updated"] = dt.date.today().isoformat()


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
    # v8 · 新增 phase posterior 集成
    ap.add_argument("--user-choices", default=None,
                    help="v8 · user_answers.json 路径（{question_id: option_id}）；"
                         "传入会调 phase_posterior.update_posterior 算后验，写回 bazi.phase + bazi.phase_decision")
    ap.add_argument("--questions", default=None,
                    help="v8 · handshake.json 路径（含动态 D3 题的 likelihood_table）。"
                         "仅 --user-choices 模式下使用。")
    ap.add_argument("--write-bazi", default=None,
                    help="v8 · 把更新后的 bazi 写到此路径（默认覆盖 --bazi）")
    ap.add_argument("--round", default="r1", choices=["r1", "r2"],
                    help="v8.1 · 当前 --user-choices 属于哪一轮（默认 r1）")
    # v8.1 · Round 2 confirmation 模式
    ap.add_argument("--r1-handshake", default=None,
                    help="v8.1 R2 · R1 handshake.json 路径（仅 --round r2 用）")
    ap.add_argument("--r1-answers", default=None,
                    help="v8.1 R2 · R1 用户答案 JSON")
    ap.add_argument("--r2-handshake", default=None,
                    help="v8.1 R2 · R2 handshake.json 路径")
    ap.add_argument("--r2-answers", default=None,
                    help="v8.1 R2 · R2 用户答案 JSON")

    # v9 L7 · phase_full_override
    ap.add_argument("--phase-full-override", default=None, metavar="PHASE_ID",
                    help="v9 L7 · 用户固化式 phase 级联覆盖。PHASE_ID 必须在 _phase_registry 注册，"
                         "例如 yangren_chong_cai / shang_guan_sheng_cai_geju / floating_dms_to_cong_cai。"
                         "写入 structural_corrections 并锁死 bazi.phase_decision。"
                         "用 --reason 附原因说明。")

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
    rec = _migrate_record(rec, bazi)

    # v8.1 · Round 2 confirmation 模式（独立路径）
    if args.round == "r2" and (args.r1_answers or args.r2_answers):
        if not (args.r1_handshake and args.r1_answers and args.r2_handshake and args.r2_answers):
            ap.error("--round r2 confirmation 需要 --r1-handshake / --r1-answers / --r2-handshake / --r2-answers 全部提供")
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from phase_posterior import update_posterior_round2  # type: ignore
        r1_handshake = json.loads(Path(args.r1_handshake).read_text(encoding="utf-8"))
        r2_handshake = json.loads(Path(args.r2_handshake).read_text(encoding="utf-8"))
        r1_answers = json.loads(Path(args.r1_answers).read_text(encoding="utf-8"))
        r2_answers = json.loads(Path(args.r2_answers).read_text(encoding="utf-8"))
        new_bazi, confirmation = update_posterior_round2(
            bazi=bazi,
            r1_handshake=r1_handshake,
            r1_answers=r1_answers,
            r2_handshake=r2_handshake,
            r2_answers=r2_answers,
        )
        bazi_out = Path(args.write_bazi) if args.write_bazi else Path(args.bazi)
        bazi_out.write_text(json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")
        append_user_choices(rec, r1_answers,
                            phase_decision=None,
                            round_label="r1")
        append_user_choices(rec, r2_answers,
                            phase_decision=new_bazi.get("phase_decision"),
                            phase_confirmation=new_bazi.get("phase_confirmation"),
                            round_label="r2")
        print(f"[save_confirmed_facts R2] +r1={len(r1_answers)} +r2={len(r2_answers)} → "
              f"status={confirmation['status']} action={confirmation['action']}")
        print(f"[save_confirmed_facts R2] wrote {bazi_out}")
    # v8 · --user-choices 模式：算后验 → 写回 bazi + 同步 user_choices/phase_decision
    elif args.user_choices:
        choices = json.loads(Path(args.user_choices).read_text(encoding="utf-8"))
        if not isinstance(choices, dict):
            raise ValueError("--user-choices file must be a JSON object {question_id: option_id}")
        handshake_data = None
        if args.questions and Path(args.questions).exists():
            handshake_data = json.loads(Path(args.questions).read_text(encoding="utf-8"))
        # 局部 import 避免循环
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from phase_posterior import update_posterior  # type: ignore
        new_bazi = update_posterior(bazi, handshake_data, choices)
        bazi_out = Path(args.write_bazi) if args.write_bazi else Path(args.bazi)
        bazi_out.write_text(json.dumps(new_bazi, ensure_ascii=False, indent=2), encoding="utf-8")
        append_user_choices(rec, choices, phase_decision=new_bazi.get("phase_decision"),
                            round_label=args.round)
        pd = new_bazi["phase_decision"]
        print(f"[save_confirmed_facts] +user_choices ({args.round}): {len(choices)} answers → "
              f"phase={pd['decision']} confidence={pd['confidence']} prob={pd['decision_probability']:.4f}")
        print(f"[save_confirmed_facts] wrote {bazi_out} (v8 phase_decision)")

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

    if args.phase_full_override:
        # v9 L7 · 验证 phase_id 在 _phase_registry 注册
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from _phase_registry import exists, get  # type: ignore
            if not exists(args.phase_full_override):
                ap.error(f"--phase-full-override {args.phase_full_override!r} 未在 _phase_registry 注册，"
                         f"请用 core_phase_ids() / all_ids() 查已注册 phase")
            meta = get(args.phase_full_override)
        except ImportError:
            ap.error("未找到 _phase_registry（需要 v9 L1）")

        before_phase = bazi.get("phase", {}).get("id", "day_master_dominant")
        if not args.reason:
            ap.error("--phase-full-override 必须带 --reason 说明（e.g. '用户 / 命理顾问确认'）")
        append_structural(
            rec, "phase_full_override",
            before=before_phase,
            after=args.phase_full_override,
            reason=args.reason,
        )
        print(f"[save_confirmed_facts] +phase_full_override: "
              f"{before_phase} → {args.phase_full_override} "
              f"(dimension={meta.dimension}, school={meta.school})")

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
