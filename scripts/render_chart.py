#!/usr/bin/env python3
"""render_chart.py — curves.json → matplotlib PNG（PNG fallback）

视觉与 render_artifact.py 对齐：4 色 × 实/虚 = 8 线 + 置信带 + 大运色带 + 拐点标注。
v6 新增 emotion 维度（情感 · 粉色），与精神 / 财富 / 名声 同图绘制。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams


# 中文字体回退链
_FONT_CANDIDATES = [
    "PingFang SC", "Heiti SC", "STHeiti", "Songti SC",
    "Arial Unicode MS", "Hiragino Sans GB",
    "Noto Sans CJK SC", "Source Han Sans SC",
    "WenQuanYi Micro Hei", "SimHei", "DejaVu Sans",
]
rcParams["font.sans-serif"] = _FONT_CANDIDATES
rcParams["axes.unicode_minus"] = False


COLOR_SPIRIT = "#8B7BC7"   # 紫
COLOR_WEALTH = "#4A9D7F"   # 绿
COLOR_FAME = "#D88E5C"     # 橙
COLOR_EMOTION = "#D8639E"  # 粉（v6 感情维度）

DAYUN_BAND_COLORS = ["#F5F2EA", "#EDF2F4", "#F0E7E7", "#E7F0EE", "#F3EFE8"]


def render_png(curves: dict, out_path: str) -> None:
    pts = curves["points"]
    if not pts:
        raise ValueError("No points to render")

    ages = [p["age"] for p in pts]
    years = [p["year"] for p in pts]

    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)

    # 大运背景色带
    for i, seg in enumerate(curves.get("dayun_segments", [])):
        color = DAYUN_BAND_COLORS[i % len(DAYUN_BAND_COLORS)]
        ax.axvspan(seg["start_age"], seg["end_age"] + 1, color=color, alpha=0.5, zorder=0)
        # 大运标签
        ax.text(
            (seg["start_age"] + seg["end_age"]) / 2,
            98,
            seg["label"],
            ha="center", va="top", fontsize=10, color="#666",
            zorder=1,
        )

    # 8 条线（v6：4 维度 × 实/虚）
    series = [
        ("spirit_yearly", COLOR_SPIRIT, "-", "精神 · 当年", 2.4),
        ("spirit_cumulative", COLOR_SPIRIT, "--", "精神 · 累积", 1.6),
        ("wealth_yearly", COLOR_WEALTH, "-", "财富 · 当年", 2.4),
        ("wealth_cumulative", COLOR_WEALTH, "--", "财富 · 累积", 1.6),
        ("fame_yearly", COLOR_FAME, "-", "名声 · 当年", 2.4),
        ("fame_cumulative", COLOR_FAME, "--", "名声 · 累积", 1.6),
        ("emotion_yearly", COLOR_EMOTION, "-", "感情 · 当年", 2.4),
        ("emotion_cumulative", COLOR_EMOTION, "--", "感情 · 累积", 1.6),
    ]
    for key, color, ls, label, lw in series:
        ys = [p[key] for p in pts]
        ax.plot(ages, ys, color=color, linestyle=ls, linewidth=lw, label=label, zorder=3)

        # 置信带（只对 yearly 画）
        if key.endswith("_yearly"):
            dim = key.split("_")[0]
            sigma = [p["sigma"][dim] for p in pts]
            upper = [y + s for y, s in zip(ys, sigma)]
            lower = [y - s for y, s in zip(ys, sigma)]
            ax.fill_between(ages, lower, upper, color=color, alpha=0.10, zorder=2)

    # 拐点标注（取未来 N 年，避开同年重叠）
    annotated_years = set()
    for tp in curves.get("turning_points_future", []):
        if tp["year"] in annotated_years:
            continue
        if tp["confidence"] == "low":
            continue
        annotated_years.add(tp["year"])
        x = tp["age"]
        dim = tp["dimension"]
        y = tp["yearly_value"]
        color = {"spirit": COLOR_SPIRIT, "wealth": COLOR_WEALTH, "fame": COLOR_FAME, "emotion": COLOR_EMOTION}.get(dim, "#666")
        ax.axvline(x=x, ymin=0, ymax=1, color=color, alpha=0.25, linestyle=":", linewidth=1, zorder=2)
        ax.annotate(
            tp["trigger"],
            xy=(x, y), xytext=(x, y + 6),
            ha="center", fontsize=8, color="#444",
            arrowprops=dict(arrowstyle="-", color=color, alpha=0.5, lw=0.8),
            zorder=4,
        )

    # 低置信度年份灰阶覆盖
    for p in pts:
        low_count = sum(1 for v in p["confidence"].values() if v == "low")
        if low_count >= 2:
            ax.axvspan(p["age"] - 0.3, p["age"] + 0.3, color="#999", alpha=0.10, zorder=1)

    # 派别争议年份：黄色竖带 + 底部「派」标记
    disputed_ages = sorted({d["age"] for d in curves.get("disputes", [])})
    for age in disputed_ages:
        ax.axvspan(age - 0.4, age + 0.4, color="#E8B947", alpha=0.18, zorder=1)
        ax.text(age, 1.5, "派", ha="center", va="bottom", fontsize=8,
                color="#B07A26", zorder=4,
                bbox=dict(boxstyle="round,pad=0.15", fc="#FFF3D9", ec="#E8B947", lw=0.5))

    # 双轴刻度
    ax.set_xlim(min(ages) - 0.5, max(ages) + 0.5)
    ax.set_ylim(0, 100)
    ax.set_xlabel("年龄 / 岁")
    ax.set_ylabel("评分（0–100）")
    ax.set_title(f"八字人生曲线图 · {curves['pillars_str']}（日主 {curves['day_master']}，{curves['strength']['label']}）")
    ax.grid(True, alpha=0.2, zorder=0)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=9)

    # 顶轴：公历年份
    ax2 = ax.twiny()
    ax2.set_xlim(ax.get_xlim())
    tick_ages = [a for a in ages if a % 5 == 0]
    tick_years = [years[ages.index(a)] for a in tick_ages]
    ax2.set_xticks(tick_ages)
    ax2.set_xticklabels(tick_years, fontsize=8, color="#666")
    ax2.set_xlabel("公历年份", color="#666")

    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curves", required=True)
    ap.add_argument("--out", default="chart.png")
    args = ap.parse_args()
    curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))
    render_png(curves, args.out)
    print(f"[render_chart] wrote {args.out}")


if __name__ == "__main__":
    main()
