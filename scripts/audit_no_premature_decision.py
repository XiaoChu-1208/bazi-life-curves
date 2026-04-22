#!/usr/bin/env python3
"""audit_no_premature_decision.py — v9 阻断 provisional / reject phase 落到产物

铁律：score_curves / render_artifact 默认调用本审计；任一命中 → exit 2。

阻断条件（任一即拦）：
  1. bazi.phase_decision.is_provisional == true
     —— 即 phase 还在 R0 兜底状态（未跑过 R1/R2 校验），不许直接出报告
  2. bazi.phase_decision.confidence == "reject"
     —— posterior top1 < 0.40，应该回 R3 再校验，不许 freeze 落产物
  3. bazi.phase 缺失或为空
     —— 完全没跑校验，rendering 必崩

用法：

    python scripts/audit_no_premature_decision.py --bazi output/X.bazi.json

退出码：
    0 通过
    2 阻断
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def audit(bazi: dict) -> list[str]:
    violations: list[str] = []

    phase = bazi.get("phase")
    if not phase or not isinstance(phase, dict):
        violations.append(
            "[premature] bazi.phase 缺失或为空——必须先跑 adaptive_elicit.py next 完成相位校验。"
        )
        return violations  # 后面字段都依赖 phase 存在

    pd = bazi.get("phase_decision")
    if not pd or not isinstance(pd, dict):
        violations.append(
            "[premature] bazi.phase_decision 缺失——adaptive_elicit 没写完整。"
        )
        return violations

    if pd.get("is_provisional") is True or phase.get("is_provisional") is True:
        violations.append(
            "[premature] phase_decision.is_provisional=True —— 当前还是兜底相位，"
            "未通过 R1/R2 校验。请先跑 adaptive_elicit.py next finalize 后再 render。"
        )

    conf = pd.get("confidence") or phase.get("confidence")
    if conf == "reject":
        top1 = pd.get("decision_probability", 0.0)
        violations.append(
            f"[premature] phase_decision.confidence=reject (top1={top1:.3f} < 0.40)"
            "—— posterior 没收敛，应回 R3 加题再校验，禁止 freeze 落产物。"
        )

    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="v9: 阻断 provisional / reject 相位落产物")
    ap.add_argument("--bazi", required=True, help="output/X.bazi.json 路径")
    ap.add_argument(
        "--allow-provisional",
        action="store_true",
        help="（极少用）允许 provisional 相位通过——例如 demo / regression。"
             "正常流水线不许加。",
    )
    args = ap.parse_args()

    bazi_path = Path(args.bazi)
    if not bazi_path.exists():
        print(f"[audit_no_premature_decision] 文件不存在：{bazi_path}", file=sys.stderr)
        return 2
    bazi = json.loads(bazi_path.read_text(encoding="utf-8"))

    violations = audit(bazi)
    if args.allow_provisional:
        violations = [v for v in violations if "is_provisional" not in v]

    if violations:
        print(
            f"[audit_no_premature_decision] {len(violations)} 条阻断："
            f"\n  - " + "\n  - ".join(violations),
            file=sys.stderr,
        )
        return 2

    print(
        "[audit_no_premature_decision] PASS — "
        "phase 已 finalize 且 confidence ≥ low，可继续 render。",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
