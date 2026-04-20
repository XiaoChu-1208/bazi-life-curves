#!/usr/bin/env python3
"""calibrate.py — 跑历史回测 + 个人化校准

回测：
- 读 calibration/dataset.yaml
- 对每条目算 curves，对照 notable_years 检查方向命中率
- 命中率不达 thresholds.yaml 中的阈值则非零退出（CI 友好）

个人化（--personal）：
- 读用户提供的过去若干年实际感受 → 微调 α/β/γ/λ → 写 personal/<hash>.yaml
- 不写回主 dataset.yaml（公正性要求）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List

try:
    import yaml
except ImportError as e:
    raise ImportError("PyYAML required: pip install PyYAML") from e

sys.path.insert(0, str(Path(__file__).resolve().parent))

from solve_bazi import solve as solve_bazi
from score_curves import score as score_curves
from _bazi_core import decide_phase


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "calibration" / "dataset.yaml"
PHASE_DATASET = ROOT / "calibration" / "phase_dataset.yaml"
THRESHOLDS = ROOT / "calibration" / "thresholds.yaml"
PERSONAL_DIR = ROOT / "personal"

# v8 phase_decision confidence 等级排序（由弱到强）
_CONFIDENCE_RANK = {"reject": 0, "low": 1, "mid": 2, "high": 3}


def load_dataset() -> List[Dict]:
    if not DATASET.exists():
        return []
    return yaml.safe_load(DATASET.read_text(encoding="utf-8")) or []


def load_thresholds() -> Dict:
    if not THRESHOLDS.exists():
        return {"direction_hit_rate": 0.70, "magnitude_within_one_rate": 0.60}
    return yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))


def evaluate_one(item: Dict) -> Dict:
    bazi = solve_bazi(
        pillars_str=item["pillars"],
        gregorian=None,
        gender=item["gender"],
        birth_year=item["birth_year"],
        n_years=80,
    )
    curves = score_curves(bazi, age_end=80, forecast_window=0)
    points_by_year = {p["year"]: p for p in curves["points"]}

    hits = 0
    mag_within_one = 0
    total = 0
    details = []
    for ev in item.get("notable_years", []):
        y = ev["year"]
        dim = ev["dimension"]
        expected_dir = ev["direction"]
        expected_mag = ev.get("magnitude", "medium")
        if y not in points_by_year:
            continue
        p = points_by_year[y]
        yearly = p[f"{dim}_yearly"]
        actual_dir = "up" if yearly > 55 else ("down" if yearly < 45 else "flat")

        # 量级映射
        deviation = abs(yearly - 50)
        actual_mag = "high" if deviation > 18 else ("medium" if deviation > 8 else "low")

        dir_hit = (actual_dir == expected_dir) or (expected_dir == "flat" and actual_dir == "flat")
        mag_diff = _mag_distance(actual_mag, expected_mag)
        if dir_hit:
            hits += 1
        if mag_diff <= 1:
            mag_within_one += 1
        total += 1
        details.append({
            "year": y,
            "dim": dim,
            "expected": (expected_dir, expected_mag),
            "actual": (actual_dir, actual_mag),
            "yearly": yearly,
            "dir_hit": dir_hit,
            "mag_diff": mag_diff,
        })

    return {
        "id": item.get("id", "?"),
        "pillars": item["pillars"],
        "total": total,
        "direction_hits": hits,
        "magnitude_within_one": mag_within_one,
        "details": details,
    }


def _mag_distance(a: str, b: str) -> int:
    order = {"low": 0, "medium": 1, "high": 2}
    return abs(order.get(a, 1) - order.get(b, 1))


def run_calibration() -> int:
    dataset = load_dataset()
    if not dataset:
        print("[calibrate] No dataset found, skipping.")
        return 0
    thresholds = load_thresholds()

    total = 0
    dir_hits = 0
    mag_within = 0
    per_item = []
    for item in dataset:
        result = evaluate_one(item)
        per_item.append(result)
        total += result["total"]
        dir_hits += result["direction_hits"]
        mag_within += result["magnitude_within_one"]

    if total == 0:
        print("[calibrate] No notable_years to evaluate, skipping.")
        return 0

    dir_rate = dir_hits / total
    mag_rate = mag_within / total

    print(f"[calibrate] {len(dataset)} examples, {total} year-events evaluated")
    print(f"[calibrate]   direction hit rate: {dir_rate:.2%} (threshold {thresholds['direction_hit_rate']:.2%})")
    print(f"[calibrate]   magnitude within ±1: {mag_rate:.2%} (threshold {thresholds['magnitude_within_one_rate']:.2%})")

    for r in per_item:
        if r["total"] == 0:
            continue
        dr = r["direction_hits"] / r["total"]
        print(f"  - {r['id']} ({r['pillars']}): dir {r['direction_hits']}/{r['total']} ({dr:.0%})")

    failures = []
    if dir_rate < thresholds["direction_hit_rate"]:
        failures.append("direction_hit_rate below threshold")
    if mag_rate < thresholds["magnitude_within_one_rate"]:
        failures.append("magnitude_within_one_rate below threshold")

    if failures:
        print(f"[calibrate] FAIL: {'; '.join(failures)}", file=sys.stderr)
        return 2
    print("[calibrate] PASS")
    return 0


def personal_calibrate(spec_path: str) -> int:
    """Personal calibration: read user-provided past-year experience, adjust weights."""
    PERSONAL_DIR.mkdir(exist_ok=True)
    spec = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8"))
    pillars = spec["pillars"]
    gender = spec["gender"]
    birth_year = spec["birth_year"]
    obs = spec.get("observations", [])

    # 用 (pillars, gender, birth_year) 哈希作为个人副本 ID（不含姓名）
    hkey = hashlib.sha1(f"{pillars}|{gender}|{birth_year}".encode()).hexdigest()[:12]

    # 简化：在 ±0.1 范围内网格搜 α/β/γ，使观测直方图与预测最匹配
    bazi = solve_bazi(pillars, None, gender, birth_year, n_years=80)
    best = None
    best_loss = float("inf")
    for da in (-0.1, 0, 0.1):
        for dg in (-0.1, 0, 0.1):
            db = -da - dg
            w = {"alpha": 0.30 + da, "beta": 0.40 + db, "gamma": 0.30 + dg}
            if any(v < 0.1 for v in w.values()):
                continue
            curves = score_curves(bazi, weights=w, age_end=80, forecast_window=0)
            loss = _personal_loss(curves, obs)
            if loss < best_loss:
                best_loss = loss
                best = w

    out_path = PERSONAL_DIR / f"{hkey}.yaml"
    out_path.write_text(yaml.safe_dump({"weights": best, "loss": best_loss}, allow_unicode=True), encoding="utf-8")
    print(f"[calibrate.personal] wrote {out_path}: weights={best}, loss={best_loss:.2f}")
    return 0


def _personal_loss(curves: dict, observations: List[Dict]) -> float:
    by_year = {p["year"]: p for p in curves["points"]}
    target = {"high": 75, "medium": 50, "low": 25}
    loss = 0.0
    n = 0
    for o in observations:
        y = o["year"]; dim = o["dimension"]; lab = o["level"]
        if y not in by_year:
            continue
        actual = by_year[y][f"{dim}_yearly"]
        loss += (actual - target[lab]) ** 2
        n += 1
    return loss / max(n, 1)


def load_phase_dataset(path: Path | None = None) -> Dict:
    """读 phase_dataset.yaml 并返回完整 dict（含 metadata + samples）。"""
    p = Path(path) if path else PHASE_DATASET
    if not p.exists():
        return {"metadata": {}, "samples": []}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if isinstance(raw, list):
        # 兼容：纯 list 格式（无 metadata 包裹）
        return {"metadata": {}, "samples": raw}
    return raw


def evaluate_phase_sample(sample: Dict) -> Dict:
    """对单个 phase 样本评估先验 + 后验，返回详细比对结果。"""
    bazi_input = sample.get("bazi_input", {})
    pillars = bazi_input["pillars"]
    gender = bazi_input["gender"]
    birth_year = bazi_input["birth_year"]
    expected = sample["expected_phase"]
    min_prior = float(sample.get("expected_min_prior_prob", 0.0))
    min_post = float(sample.get("expected_min_posterior_prob", 0.0))
    min_conf = sample.get("expected_min_confidence_with_answers", "low")
    answers = sample.get("simulated_user_answers")

    bazi = solve_bazi(pillars, None, gender, birth_year, n_years=80)

    prior_res = decide_phase(bazi, user_answers=None)
    prior_dist = prior_res["prior_distribution"]
    prior_top = max(prior_dist.items(), key=lambda x: (x[1], -ord(x[0][0])))
    # 稳定排序：相同概率按 phase_id 升序
    prior_top = sorted(prior_dist.items(), key=lambda x: (-x[1], x[0]))[0]
    prior_top_phase, prior_top_prob = prior_top
    prior_expected_prob = prior_dist.get(expected, 0.0)

    if answers:
        post_res = decide_phase(bazi, user_answers=answers)
    else:
        post_res = prior_res
    post_dist = post_res["posterior_distribution"]
    post_top = sorted(post_dist.items(), key=lambda x: (-x[1], x[0]))[0]
    post_top_phase, post_top_prob = post_top
    post_expected_prob = post_dist.get(expected, 0.0)
    actual_conf = post_res.get("confidence", "reject")

    return {
        "id": sample.get("id", "?"),
        "pillars": pillars,
        "expected_phase": expected,
        "answers_count": len(answers) if answers else 0,
        # prior
        "prior_top_phase": prior_top_phase,
        "prior_top_prob": prior_top_prob,
        "prior_expected_prob": prior_expected_prob,
        "prior_recall_hit": prior_top_phase == expected,
        "prior_prob_pass": prior_expected_prob >= min_prior,
        "min_prior": min_prior,
        # posterior
        "posterior_top_phase": post_top_phase,
        "posterior_top_prob": post_top_prob,
        "posterior_expected_prob": post_expected_prob,
        "posterior_recall_hit": post_top_phase == expected,
        "posterior_prob_pass": post_expected_prob >= min_post,
        "min_posterior": min_post,
        # confidence
        "actual_confidence": actual_conf,
        "expected_min_confidence": min_conf,
        "confidence_pass": (
            _CONFIDENCE_RANK.get(actual_conf, 0) >= _CONFIDENCE_RANK.get(min_conf, 0)
        ),
    }


def eval_phase_decision(phase_dataset_path: Path | None = None) -> int:
    """v8 phase_decision 评估通道。

    1. 读 phase_dataset.yaml
    2. 对每个样本算先验 + 后验
    3. 汇总 5 项指标 vs thresholds.yaml#phase_decision
    4. 返回 exit code（0=PASS，2=任一指标低于阈值）
    """
    ds = load_phase_dataset(phase_dataset_path)
    samples = ds.get("samples", [])
    metadata = ds.get("metadata", {})

    if not samples:
        path = phase_dataset_path or PHASE_DATASET
        print(f"[calibrate.phase] No samples found in {path}, skipping.")
        return 0

    thresholds_all = load_thresholds() or {}
    pd_thresh = thresholds_all.get("phase_decision", {}) or {}
    t_prior_recall = float(pd_thresh.get("prior_recall_min", 0.50))
    t_prior_prob = float(pd_thresh.get("prior_prob_pass_min", 0.50))
    t_post_recall = float(pd_thresh.get("posterior_recall_min", 0.85))
    t_post_prob = float(pd_thresh.get("posterior_prob_pass_min", 0.85))
    t_conf = float(pd_thresh.get("confidence_pass_min", 0.85))

    n = len(samples)
    schema_v = metadata.get("schema_version", "?")
    print(f"[calibrate.phase] schema_version={schema_v} · {n} samples")
    print()

    results = [evaluate_phase_sample(s) for s in samples]

    n_prior_recall = sum(1 for r in results if r["prior_recall_hit"])
    n_prior_prob = sum(1 for r in results if r["prior_prob_pass"])
    n_post_recall = sum(1 for r in results if r["posterior_recall_hit"])
    n_post_prob = sum(1 for r in results if r["posterior_prob_pass"])
    n_conf = sum(1 for r in results if r["confidence_pass"])

    for r in results:
        flags = "".join([
            "P" if r["prior_recall_hit"] else "p",
            "B" if r["prior_prob_pass"] else "b",
            "Q" if r["posterior_recall_hit"] else "q",
            "C" if r["posterior_prob_pass"] else "c",
            "F" if r["confidence_pass"] else "f",
        ])
        marker_pri = "✓" if r["prior_recall_hit"] else "✗"
        marker_pst = "✓" if r["posterior_recall_hit"] else "✗"
        print(f"  [{flags}] {r['id']}  ({r['pillars']})")
        print(f"      expected_phase = {r['expected_phase']}")
        print(f"      prior     {marker_pri} top-1={r['prior_top_phase']} ({r['prior_top_prob']:.4f})  "
              f"prior[expected]={r['prior_expected_prob']:.4f} ≥ {r['min_prior']:.2f}? "
              f"{'PASS' if r['prior_prob_pass'] else 'FAIL'}")
        print(f"      posterior {marker_pst} top-1={r['posterior_top_phase']} ({r['posterior_top_prob']:.4f})  "
              f"posterior[expected]={r['posterior_expected_prob']:.4f} ≥ {r['min_posterior']:.2f}? "
              f"{'PASS' if r['posterior_prob_pass'] else 'FAIL'}  "
              f"({r['answers_count']} answers)")
        print(f"      confidence={r['actual_confidence']} ≥ {r['expected_min_confidence']}? "
              f"{'PASS' if r['confidence_pass'] else 'FAIL'}")
        print()

    rate_prior_recall = n_prior_recall / n
    rate_prior_prob = n_prior_prob / n
    rate_post_recall = n_post_recall / n
    rate_post_prob = n_post_prob / n
    rate_conf = n_conf / n

    print(f"[calibrate.phase] === Aggregate metrics (n={n}) ===")
    print(f"  prior_recall          : {n_prior_recall}/{n} = {rate_prior_recall:.2%}  (threshold ≥ {t_prior_recall:.2%})")
    print(f"  prior_prob_pass       : {n_prior_prob}/{n} = {rate_prior_prob:.2%}  (threshold ≥ {t_prior_prob:.2%})")
    print(f"  posterior_recall      : {n_post_recall}/{n} = {rate_post_recall:.2%}  (threshold ≥ {t_post_recall:.2%})")
    print(f"  posterior_prob_pass   : {n_post_prob}/{n} = {rate_post_prob:.2%}  (threshold ≥ {t_post_prob:.2%})")
    print(f"  confidence_pass       : {n_conf}/{n} = {rate_conf:.2%}  (threshold ≥ {t_conf:.2%})")

    failures = []
    if rate_prior_recall < t_prior_recall:
        failures.append("prior_recall below threshold")
    if rate_prior_prob < t_prior_prob:
        failures.append("prior_prob_pass below threshold")
    if rate_post_recall < t_post_recall:
        failures.append("posterior_recall below threshold")
    if rate_post_prob < t_post_prob:
        failures.append("posterior_prob_pass below threshold")
    if rate_conf < t_conf:
        failures.append("confidence_pass below threshold")

    if failures:
        print(f"[calibrate.phase] FAIL: {'; '.join(failures)}", file=sys.stderr)
        return 2
    print("[calibrate.phase] PASS")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personal", help="个人化校准 spec YAML 路径")
    ap.add_argument("--symmetry", action="store_true", help="性别对称性测试")
    ap.add_argument("--phase-only", action="store_true",
                    help="仅跑 v8 phase_decision 评估通道（读 calibration/phase_dataset.yaml）")
    ap.add_argument("--phase-dataset", default=None,
                    help="phase_dataset.yaml 路径（默认 calibration/phase_dataset.yaml）")
    ap.add_argument("--soft", action="store_true",
                    help="仅报告不阻塞（用于追踪算法改进，CI 上推荐）")
    args = ap.parse_args()

    if args.personal:
        sys.exit(personal_calibrate(args.personal))

    if args.symmetry:
        sys.exit(symmetry_test())

    if args.phase_only:
        path = Path(args.phase_dataset) if args.phase_dataset else None
        code = eval_phase_decision(path)
        if args.soft:
            sys.exit(0)
        sys.exit(code)

    code = run_calibration()
    if args.soft:
        sys.exit(0)
    sys.exit(code)


def symmetry_test() -> int:
    """男命与对应女命除起运方向外，本命基线必须一致。"""
    sample = "庚午 辛巳 壬子 丁未"
    by = 1990
    bazi_m = solve_bazi(sample, None, "M", by)
    bazi_f = solve_bazi(sample, None, "F", by)
    cur_m = score_curves(bazi_m, age_end=20, forecast_window=0)
    cur_f = score_curves(bazi_f, age_end=20, forecast_window=0)
    if cur_m["baseline"] != cur_f["baseline"]:
        print(f"[symmetry] FAIL: baseline differs M={cur_m['baseline']} F={cur_f['baseline']}", file=sys.stderr)
        return 2
    if cur_m["yongshen"]["yongshen"] != cur_f["yongshen"]["yongshen"]:
        print(f"[symmetry] FAIL: yongshen differs", file=sys.stderr)
        return 2
    print("[symmetry] PASS: baseline/yongshen identical (only dayun direction differs)")
    return 0


if __name__ == "__main__":
    main()
