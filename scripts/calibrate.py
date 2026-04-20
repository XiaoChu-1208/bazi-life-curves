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


ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "calibration" / "dataset.yaml"
THRESHOLDS = ROOT / "calibration" / "thresholds.yaml"
PERSONAL_DIR = ROOT / "personal"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--personal", help="个人化校准 spec YAML 路径")
    ap.add_argument("--symmetry", action="store_true", help="性别对称性测试")
    ap.add_argument("--soft", action="store_true",
                    help="仅报告不阻塞（用于追踪算法改进，CI 上推荐）")
    args = ap.parse_args()

    if args.personal:
        sys.exit(personal_calibrate(args.personal))

    if args.symmetry:
        sys.exit(symmetry_test())

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
