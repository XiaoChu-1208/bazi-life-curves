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
    Pillar,
    GAN_WUXING,
    ZHI_WUXING,
    WUXING_ORDER,
    validate_blind_input,
    _wuxing_count,
)
from _engines import (
    SUPPORTED_ENGINES,
    HAS_TYME4PY,
    solve_pillars as _engine_solve_pillars,
    compute_true_solar_time as _engine_true_solar_time,
)


def _apply_true_solar_time(
    gregorian: str,
    longitude: float,
    timezone_offset_hours: float = 8.0,
) -> tuple[str, dict]:
    """v8.0 · 真太阳时校正（升级到天文级精度）。

    - 优先用 sxtwl 计算"经度差 + 均时差 EOT"两项叠加（精度 ±5 秒）
    - 未装 sxtwl 时 fallback 到 v7.2 的经度近似 (lng-120)×4 分钟（精度 ±2 分钟）

    返回：(校正后的 gregorian 字符串, info dict)
    """
    info = _engine_true_solar_time(gregorian, longitude, timezone_offset_hours)
    return info["true_solar_time"], info


def solve(
    pillars_str: str | None,
    gregorian: str | None,
    gender: str,
    birth_year: int | None,
    n_years: int = 80,
    qiyun_age: int | None = None,
    orientation: str = "hetero",
    longitude: float | None = None,
    engine: str = "lunar-python",
) -> dict:
    qiyun_source = "user_specified" if qiyun_age is not None else None
    true_solar_info: dict | None = None
    cross_check_info: dict | None = None
    if pillars_str:
        # v9 PR-2: pillars 模式弃用警告
        # qiyun_age 无法精算（需公历日期），dayun/liunian 起算误差可达 ±2 岁
        import warnings as _warnings
        _warnings.warn(
            "--pillars 模式自 v9 起进入弃用流程：起运岁(qiyun_age)无法精算，"
            "若不显式指定 --qiyun-age 将默认 8 岁，dayun/liunian 起算可能偏离 ±2 岁。"
            "强烈建议改用 --gregorian + --longitude 以启用 lunar-python 精算。"
            "详见 USAGE.md §为什么推荐公历输入。",
            DeprecationWarning,
            stacklevel=2,
        )
        pillars = parse_pillars(pillars_str)
        if birth_year is None:
            raise ValueError("--birth-year required when using --pillars")
        by = birth_year
        if qiyun_age is None:
            # v9: pillars 模式默认 qiyun_age 改为强制要求显式指定
            import os as _os
            if _os.environ.get("BAZI_ALLOW_PILLARS_DEFAULT_QIYUN") != "1":
                raise ValueError(
                    "v9: --pillars 模式必须显式 --qiyun-age（旧默认 8 岁已弃用）。"
                    "若必须沿用旧行为，请设环境变量 BAZI_ALLOW_PILLARS_DEFAULT_QIYUN=1，"
                    "但仅推荐用于 legacy 测试和 calibration 回归。"
                )
        if longitude is not None:
            true_solar_info = {
                "longitude": longitude,
                "warning": "pillars 模式不会用 longitude 重算柱位（柱位已固定）。"
                           "若想用真太阳时校正，请改用 --gregorian + --longitude。",
            }
    elif gregorian:
        if longitude is not None:
            gregorian_corrected, true_solar_info = _apply_true_solar_time(gregorian, longitude)
        else:
            gregorian_corrected = gregorian
        # v8.0 · 通过引擎抽象层解算（lunar-python / tyme4py / cross-check）
        if engine == "lunar-python":
            # 兼容路径：保持跟旧版逐字节一致
            pillars, by = pillars_from_gregorian(gregorian_corrected, gender)
        else:
            fp, cross_check_info = _engine_solve_pillars(
                gregorian_corrected, gender, engine=engine
            )
            pillars = [
                Pillar(fp.year_gan, fp.year_zhi),
                Pillar(fp.month_gan, fp.month_zhi),
                Pillar(fp.day_gan, fp.day_zhi),
                Pillar(fp.hour_gan, fp.hour_zhi),
            ]
            # 出生年沿用 gregorian 字符串中的年份（与 lunar-python 行为一致）
            by = int(gregorian_corrected.split("-", 1)[0])
        if qiyun_age is None:
            calc = compute_qiyun_age_from_gregorian(gregorian_corrected, gender)
            if calc is not None:
                qiyun_age = calc
                qiyun_source = (
                    "lunar_python_精算（已校正真太阳时）" if longitude is not None
                    else "lunar_python_精算"
                )
    else:
        raise ValueError("Must provide --pillars or --gregorian")

    if qiyun_age is None:
        # v9: legacy fallback（仅在 BAZI_ALLOW_PILLARS_DEFAULT_QIYUN=1 时走到这里）
        qiyun_age = 8
        qiyun_source = "legacy_default_8（v9 弃用 · 仅 BAZI_ALLOW_PILLARS_DEFAULT_QIYUN=1 时启用）"

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

    bazi_dict = {
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
        "day_master_root_strength": strength.get("root_strength"),
        "strength": strength,
        "yongshen": yong,
        "wuxing_distribution": wuxing_distribution,
        "weakest_wuxing": weakest_wx,
        "strongest_wuxing": strongest_wx,
        "qiyun_age": qiyun_age,
        "qiyun_source": qiyun_source,
        "true_solar_time": true_solar_info,
        "engine": engine,
        "engine_cross_check": cross_check_info,
        "dayun": dayun,
        "liunian": liunian,
    }

    # v8 · 算 phase_decision（仅先验，is_provisional=True）
    # 用户答 handshake 题之后，phase_posterior.py 会用 user_answers 重算并把 is_provisional 设为 False
    try:
        from _bazi_core import decide_phase  # type: ignore
        provisional = decide_phase(bazi_dict, user_answers=None)
        bazi_dict["phase"] = {
            "id": provisional["decision"],
            "label": provisional["phase_label"],
            "is_provisional": True,
            "is_inverted": provisional["decision"] != "day_master_dominant",
            "default_phase_was": "day_master_dominant",
            "confidence": provisional["confidence"],
            "decision_probability": provisional["decision_probability"],
        }
        bazi_dict["phase_decision"] = provisional
    except Exception as _e:
        # solve_bazi 必须能输出，即使 decide_phase 失败也不阻塞
        bazi_dict["phase"] = {
            "id": "day_master_dominant",
            "label": "默认 · 日主主导",
            "is_provisional": True,
            "is_inverted": False,
            "_decide_phase_error": str(_e),
        }

    return bazi_dict


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
    ap.add_argument("--longitude", type=float, default=None,
                    help="v7.2 · 出生地经度（° E，东经为正、西经为负），用于真太阳时校正。"
                         "v8.0 升级：装了 sxtwl 自动启用「天文级真太阳时」（含均时差 EOT，精度 ±5 秒）；"
                         "未装 sxtwl 时 fallback 到经度近似 (lng-120)×4 分钟（精度 ±2 分钟）。"
                         "仅在 --gregorian 模式下生效（--pillars 模式柱位已固定）。"
                         "示例：北京 116.4 / 上海 121.5 / 乌鲁木齐 87.6 / 西安 108.9。")
    ap.add_argument("--engine", default="lunar-python", choices=list(SUPPORTED_ENGINES),
                    help="v8.0 · 历法引擎选择："
                         "lunar-python（默认 · 行业事实标准）/ "
                         "tyme4py（新一代 · 节气基于寿星天文历 sxwnl）/ "
                         "cross-check（双引擎并行 · 节气交接边缘 case 自动抛 warning）。"
                         "tyme4py / cross-check 需先 pip install tyme4py。"
                         "仅 --gregorian 模式生效（pillars 模式柱位已固定，无歧义）。")
    ap.add_argument("--out", default="bazi.json", help="输出 JSON 路径")
    args = ap.parse_args()

    extras = {k: v for k, v in vars(args).items() if v is not None and k not in {
        "pillars", "gregorian", "gender", "orientation", "birth_year", "n_years", "qiyun_age",
        "longitude", "engine", "out",
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
        longitude=args.longitude,
        engine=args.engine,
    )
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tst = data.get("true_solar_time")
    tst_msg = f", 真太阳时={tst['note']}" if tst and "note" in tst else ""
    cc = data.get("engine_cross_check") or {}
    cc_msg = ""
    if cc:
        if cc.get("is_consistent") is True:
            cc_msg = f", 引擎双引擎一致 ✓"
        elif cc.get("is_consistent") is False:
            cc_msg = f", ⚠️ 双引擎不一致（{len(cc.get('mismatch_positions', []))} 处分歧 · 见 engine_cross_check 字段）"
        elif cc.get("warning"):
            cc_msg = f", {cc['warning'][:60]}…"
    print(f"[solve_bazi] wrote {args.out}: 八字={data['pillars_str']}, "
          f"日主={data['day_master']}({data['day_master_wuxing']}), "
          f"强弱={data['strength']['label']}, "
          f"用神={data['yongshen']['yongshen']}, "
          f"起运={data['qiyun_age']}岁（{data['qiyun_source']}）, "
          f"引擎={data['engine']}"
          f"{tst_msg}{cc_msg}")


if __name__ == "__main__":
    main()
