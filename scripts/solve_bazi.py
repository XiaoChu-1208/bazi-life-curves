#!/usr/bin/env python3
"""solve_bazi.py — 输入八字（或公历），输出 bazi.json

身份盲化：仅接受 pillars 或 gregorian + gender + birth_year。
拒绝任何身份字段（姓名、职业、关系等）。

Usage:
    python solve_bazi.py --pillars "庚午 辛巳 壬子 丁未" --gender M --birth-year 1990 --out bazi.json
    python solve_bazi.py --gregorian "1990-05-12 14:30" --gender M --out bazi.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bazi_core import (
    parse_pillars,
    pillars_from_gregorian,
    day_master_strength,
    select_yongshen,
    get_dayun_sequence,
    compute_qiyun_age_from_gregorian,
    liunian_pillar,
    calc_shishen,
    calc_zhi_shishen,
    GAN_WUXING,
    ZHI_WUXING,
    WUXING_ORDER,
    validate_blind_input,
    _wuxing_count,
)


def solve(
    pillars_str: str | None,
    gregorian: str | None,
    gender: str,
    birth_year: int | None,
    n_years: int = 80,
    qiyun_age: int | None = None,
    orientation: str = "hetero",
) -> dict:
    qiyun_source = "user_specified" if qiyun_age is not None else None
    if pillars_str:
        pillars = parse_pillars(pillars_str)
        if birth_year is None:
            raise ValueError("--birth-year required when using --pillars")
        by = birth_year
    elif gregorian:
        pillars, by = pillars_from_gregorian(gregorian, gender)
        if qiyun_age is None:
            calc = compute_qiyun_age_from_gregorian(gregorian, gender)
            if calc is not None:
                qiyun_age = calc
                qiyun_source = "lunar_python_精算"
    else:
        raise ValueError("Must provide --pillars or --gregorian")

    if qiyun_age is None:
        qiyun_age = 8
        qiyun_source = "默认值 8（pillars 模式无法精算，强烈建议在校验环节人工确认起运岁）"

    strength = day_master_strength(pillars)
    yong = select_yongshen(pillars, strength)
    dayun = get_dayun_sequence(pillars, gender, by, n_yun=8, qiyun_age=qiyun_age)

    # 流年表（出生年到 birth_year + n_years）
    liunian = []
    for age in range(0, n_years + 1):
        year = by + age
        p = liunian_pillar(year)
        liunian.append({
            "age": age,
            "year": year,
            "gan": p.gan,
            "zhi": p.zhi,
            "gan_shishen": calc_shishen(pillars[2].gan, p.gan),
            "zhi_shishen": calc_zhi_shishen(pillars[2].gan, p.zhi),
        })

    # 原局每柱的十神标注
    pillar_info = []
    for i, p in enumerate(pillars):
        name = ["年柱", "月柱", "日柱", "时柱"][i]
        pillar_info.append({
            "position": name,
            "gan": p.gan,
            "zhi": p.zhi,
            "gan_wuxing": GAN_WUXING[p.gan],
            "zhi_wuxing": ZHI_WUXING[p.zhi],
            "gan_shishen": calc_shishen(pillars[2].gan, p.gan) if i != 2 else "日主",
            "zhi_shishen": calc_zhi_shishen(pillars[2].gan, p.zhi),
        })

    wx_cnt = _wuxing_count(pillars)
    wx_total = sum(wx_cnt.values()) or 1.0
    wuxing_distribution = {
        wx: {
            "score": round(wx_cnt[wx], 2),
            "ratio": round(wx_cnt[wx] / wx_total, 3),
            "missing": wx_cnt[wx] < 0.5,
        }
        for wx in WUXING_ORDER
    }
    sorted_wx = sorted(WUXING_ORDER, key=lambda w: wx_cnt[w])
    weakest_wx = sorted_wx[0]
    strongest_wx = sorted_wx[-1]

    valid_orientations = {"hetero", "homo", "bi", "none", "poly"}
    o = orientation.lower() if orientation else "hetero"
    if o not in valid_orientations:
        raise ValueError(f"--orientation must be one of {valid_orientations}, got {orientation!r}")

    return {
        "version": 3,
        "input_kind": "pillars" if pillars_str else "gregorian",
        "gender": gender.upper(),
        "orientation": o,
        "birth_year": by,
        "pillars": [{"gan": p.gan, "zhi": p.zhi} for p in pillars],
        "pillars_str": " ".join(str(p) for p in pillars),
        "pillar_info": pillar_info,
        "day_master": pillars[2].gan,
        "day_master_wuxing": GAN_WUXING[pillars[2].gan],
        "strength": strength,
        "yongshen": yong,
        "wuxing_distribution": wuxing_distribution,
        "weakest_wuxing": weakest_wx,
        "strongest_wuxing": strongest_wx,
        "qiyun_age": qiyun_age,
        "qiyun_source": qiyun_source,
        "dayun": dayun,
        "liunian": liunian,
    }


def main():
    ap = argparse.ArgumentParser(description="Parse Bazi → bazi.json (blind input).")
    ap.add_argument("--pillars", help="四柱字符串：'庚午 辛巳 壬子 丁未'")
    ap.add_argument("--gregorian", help="公历：'1990-05-12 14:30'")
    ap.add_argument("--gender", required=True, choices=["M", "F", "m", "f"],
                    help="生理性别 · 仅用于：(1) 大运起运方向（阳男阴女顺、阴男阳女逆）"
                         "(2) emotion 通道的配偶星识别默认值（可被 --orientation 覆盖）。"
                         "spirit/wealth/fame 三派打分与性别无关。")
    ap.add_argument("--orientation", default="hetero",
                    choices=["hetero", "homo", "bi", "none", "poly"],
                    help="关系取向 · 用于 emotion 通道：hetero(异性恋·默认)/homo(同性恋)/"
                         "bi(双性)/none(单身主义/不寻求亲密关系)/poly(多元关系)。"
                         "影响配偶星识别（hetero 男看财女看官杀；homo 反之；bi 同时看；"
                         "none 改为'自我亲密能量'解读；poly 改为'关系密度+流动性'解读）。"
                         "不影响 spirit/wealth/fame 任何打分。")
    ap.add_argument("--birth-year", type=int, help="出生公历年份（pillars 模式必需）")
    ap.add_argument("--n-years", type=int, default=80, help="流年生成长度（岁），默认 80")
    ap.add_argument("--qiyun-age", type=int, default=None,
                    help="起运岁（虚岁）。gregorian 模式默认用 lunar-python 精算；"
                         "pillars 模式默认 8 岁，强烈建议显式指定。")
    ap.add_argument("--out", default="bazi.json", help="输出 JSON 路径")
    args = ap.parse_args()

    extras = {k: v for k, v in vars(args).items() if v is not None and k not in {
        "pillars", "gregorian", "gender", "orientation", "birth_year", "n_years", "qiyun_age", "out"
    }}
    validate_blind_input(extras)

    data = solve(
        pillars_str=args.pillars,
        gregorian=args.gregorian,
        gender=args.gender,
        birth_year=args.birth_year,
        n_years=args.n_years,
        qiyun_age=args.qiyun_age,
        orientation=args.orientation,
    )
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[solve_bazi] wrote {args.out}: 八字={data['pillars_str']}, "
          f"日主={data['day_master']}({data['day_master_wuxing']}), "
          f"强弱={data['strength']['label']}, "
          f"用神={data['yongshen']['yongshen']}, "
          f"起运={data['qiyun_age']}岁（{data['qiyun_source']}）")


if __name__ == "__main__":
    main()
