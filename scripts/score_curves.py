#!/usr/bin/env python3
"""score_curves.py — 三派交叉打分 → curves.json

输入 bazi.json（来自 solve_bazi.py），输出 curves.json：
- 每年 6 条线的值（精神 / 财富 / 名声 各实+虚）
- 置信带上下界
- 三派分歧标记
- 关键拐点列表
- 大运分段（含背景色带）

打分由脚本完全确定性产生，LLM 不参与数字生成（公正性）。
评分细则见 references/scoring_rubric.md，权重模型见 references/methodology.md。
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bazi_core import (
    Pillar,
    GAN, ZHI, GAN_WUXING, ZHI_WUXING, ZHI_HIDDEN_GAN,
    WUXING_ORDER, WUXING_SHENG, WUXING_KE, WUXING_BEI_SHENG,
    ZHI_CHONG, ZHI_CHUAN, ZHI_LIUHE, SANHE_GROUPS, SANHUI_GROUPS,
    KU_BENQI,
    calc_shishen, calc_zhi_shishen,
    is_fuyin, is_fanyin,
)


DEFAULT_WEIGHTS = {"alpha": 0.30, "beta": 0.40, "gamma": 0.30}
DEFAULT_LAMBDA = {"spirit": 0.85, "wealth": 0.92, "fame": 0.96, "emotion": 0.88}

# v6 新增：感情维度静态表
ZHI_LIU_HE = {  # 地支六合
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳", "午": "未", "未": "午",
}
PEACH_BLOSSOM_ZHIS = {"子", "午", "卯", "酉"}


# ---------- 格局识别（格局派"为先"判定） ----------

def detect_geju(bazi: dict) -> dict:
    """识别原局主格局。"格局为先"——先认格局，再讲扶抑。

    [改进 v2，2026-04，from 1996 八字失败教训]：
    每个格局都加了**成立条件**——避免"看到月干透伤官 + 见财"就盲目判伤官生财。
    1996 八字（丙子庚子己卯己巳）反例：身弱 + 财不透干 + 印浮 → 不构成伤官生财格。

    成立条件总览：
    - 伤官生财格：身不弱（中和或偏强）+ 财星透干或月令旺
    - 食神生财格：同上
    - 杀印相生格：印星有根（透干 或 通月令）+ 身不能极弱
    - 官印相生格：官 / 印同时透干 + 印有根
    - 食神制杀格：食 / 杀同时透干，且食有根
    - 财格用财：身强 + 财在月令 + 食伤生财链通
    """
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = pillars[2].gan
    dm_wx = GAN_WUXING[day_gan]
    strength_label = bazi["strength"]["label"]
    month_zhi = pillars[1].zhi

    yue_p = pillars[1]
    yue_gan_shi = calc_shishen(day_gan, yue_p.gan)
    yue_zhi_shi = calc_zhi_shishen(day_gan, yue_p.zhi)

    other_idx = [0, 1, 3]
    has_shishen = lambda ss: any(
        calc_shishen(day_gan, pillars[i].gan) == ss for i in other_idx
    ) or any(
        calc_zhi_shishen(day_gan, pillars[i].zhi) == ss for i in other_idx
    )
    has_zheng_pian = lambda group: any(
        calc_shishen(day_gan, pillars[i].gan) in group for i in other_idx
    ) or any(
        calc_zhi_shishen(day_gan, pillars[i].zhi) in group for i in other_idx
    )
    # 是否在干上透出（成立条件中比"任何位置出现"严格得多）
    cai_透干 = any(calc_shishen(day_gan, pillars[i].gan) in ("正财", "偏财") for i in other_idx)
    yin_透干 = any(calc_shishen(day_gan, pillars[i].gan) in ("正印", "偏印") for i in other_idx)
    guan_透干 = any(calc_shishen(day_gan, pillars[i].gan) in ("正官", "七杀") for i in other_idx)
    sg_透干 = any(calc_shishen(day_gan, pillars[i].gan) in ("食神", "伤官") for i in other_idx)

    primary = None
    secondary: List[str] = []
    yongshen_override = None
    notes_parts: List[str] = []
    rejected: List[str] = []  # 候选过但被成立条件 reject 的格局

    cai_set = ("正财", "偏财")
    yin_set = ("正印", "偏印")
    sg_set = ("食神", "伤官")
    guan_set = ("正官", "七杀")

    has_yin = has_zheng_pian(yin_set)
    has_cai = has_zheng_pian(cai_set)
    has_sg = has_zheng_pian(sg_set)
    has_guan = has_zheng_pian(guan_set)
    has_qisha = has_shishen("七杀")

    # 月令是不是财 / 印 / 官（"通月令"判定）
    yue_zhi_5x = ZHI_WUXING[month_zhi]
    cai_通月令 = WUXING_KE[dm_wx] == yue_zhi_5x
    yin_通月令 = WUXING_BEI_SHENG[dm_wx] == yue_zhi_5x if "WUXING_BEI_SHENG" in globals() else (yue_zhi_5x in {wx for wx in WUXING_ORDER if WUXING_SHENG[wx] == dm_wx})
    guan_通月令 = WUXING_KE[yue_zhi_5x] == dm_wx if False else any(WUXING_KE[wx] == dm_wx for wx in [yue_zhi_5x])
    sg_通月令 = WUXING_SHENG[dm_wx] == yue_zhi_5x

    # === 1. 伤官生财 / 食神生财 ===
    if yue_gan_shi == "伤官" and has_cai:
        # 成立条件：身不弱 + 财透干或财通月令
        if strength_label not in ("弱", "极弱") and (cai_透干 or cai_通月令):
            primary = "伤官生财"
            yongshen_override = WUXING_KE[dm_wx]
            notes_parts.append(f"月干透伤官 + 财{'透干' if cai_透干 else '通月令'} + 身{strength_label}，伤官生财格成立")
            if has_yin:
                secondary.append("印星护身")
        else:
            reason_parts = []
            if strength_label in ("弱", "极弱"):
                reason_parts.append(f"身{strength_label}不能任伤官泄秀")
            if not (cai_透干 or cai_通月令):
                reason_parts.append("财不透干也不通月令（财源浮浅）")
            rejected.append(f"伤官生财格不成立：{' + '.join(reason_parts)}")
    elif yue_gan_shi == "食神" and has_cai:
        if strength_label not in ("弱", "极弱") and (cai_透干 or cai_通月令):
            primary = "食神生财"
            yongshen_override = WUXING_KE[dm_wx]
            notes_parts.append(f"月干透食神 + 财{'透干' if cai_透干 else '通月令'}，食神生财格成立")
        else:
            rejected.append(f"食神生财格不成立：身{strength_label} 或 财不透 / 不通月令")

    # === 2. 杀印相生（强力格局） ===
    if primary is None and has_qisha and has_yin:
        # 成立条件：印有根（印透干 OR 印通月令）+ 身不极弱
        if (yin_透干 or yin_通月令) and strength_label != "极弱":
            primary = "杀印相生"
            yongshen_override = WUXING_BEI_SHENG[dm_wx] if "WUXING_BEI_SHENG" in globals() else next(wx for wx in WUXING_ORDER if WUXING_SHENG[wx] == dm_wx)
            notes_parts.append(f"七杀 + 印{'透干' if yin_透干 else '通月令'}，杀印相生格 → 用印化杀")
        else:
            rejected.append("杀印相生格不成立：印不透干也不通月令（印星形在意散，护身不彻底）")

    # === 3. 官印相生（月支官 + 透干 + 见印） ===
    if primary is None and yue_zhi_shi in guan_set and yue_gan_shi == yue_zhi_shi:
        if has_yin and (yin_透干 or yin_通月令):
            primary = "官印相生" if yue_zhi_shi == "正官" else "杀印相生"
            yongshen_override = WUXING_BEI_SHENG[dm_wx] if "WUXING_BEI_SHENG" in globals() else next(wx for wx in WUXING_ORDER if WUXING_SHENG[wx] == dm_wx)
            notes_parts.append("月支官杀透干 + 印有根，官印相生 / 杀印相生")
        elif has_sg and yue_zhi_shi == "七杀" and sg_透干:
            primary = "食神制杀"
            yongshen_override = WUXING_SHENG[dm_wx]
            notes_parts.append("月支七杀 + 食透干，食神制杀格")

    # === 4. 财格 + 身强 ===
    if primary is None and yue_zhi_shi in cai_set and strength_label == "强" and (cai_透干 or has_sg):
        primary = "财格"
        yongshen_override = WUXING_KE[dm_wx]
        notes_parts.append("月支财星 + 身强 + 财通道畅，财格用财")

    # === 5. 弃格 fallback ===
    if primary is None and yue_gan_shi in sg_set and strength_label in ("弱", "极弱"):
        notes_parts.append(f"月干{yue_gan_shi}但身{strength_label}，不构成完整食伤格局")

    return {
        "primary": primary,
        "secondary": secondary,
        "yongshen_override": yongshen_override,
        "rejected": rejected,
        "notes": "；".join(notes_parts) if notes_parts else "无明确格局",
        "has_yin_protect": has_yin and (yin_透干 or yin_通月令),
        "has_yin_浮": has_yin and not (yin_透干 or yin_通月令),
        "_diag": {
            "cai_透干": cai_透干, "cai_通月令": cai_通月令,
            "yin_透干": yin_透干, "yin_通月令": yin_通月令,
            "guan_透干": guan_透干, "sg_透干": sg_透干,
        },
    }


def _yongshen_reverse_check(bazi: dict, candidate_yongshen: str) -> dict:
    """反向校验：候选用神在原局是否真的可用。

    判断标准：
    - 透干（强可用）
    - 通月令（强可用）
    - 仅藏地支非月令（弱可用，需大运 / 流年透出才能起作用）
    - 完全不见（不可用，应慎用此用神）
    """
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    透干 = any(GAN_WUXING[p.gan] == candidate_yongshen for p in pillars)
    month_zhi = pillars[1].zhi
    通月令 = ZHI_WUXING[month_zhi] == candidate_yongshen
    藏地支 = any(
        ZHI_WUXING[p.zhi] == candidate_yongshen or
        any(GAN_WUXING.get(g) == candidate_yongshen for g in ZHI_HIDDEN_GAN.get(p.zhi, []))
        for p in pillars
    )
    if 透干 and 通月令:
        usability, note = "强", f"用神 {candidate_yongshen} 透干且通月令 → 强可用"
    elif 透干 or 通月令:
        usability, note = "中", f"用神 {candidate_yongshen} {'透干' if 透干 else '通月令'} → 可用"
    elif 藏地支:
        usability, note = "弱", f"用神 {candidate_yongshen} 仅藏地支非月令 → 弱可用，需大运 / 流年透出才能流通"
    else:
        usability, note = "无", f"⚠ 用神 {candidate_yongshen} 在原局完全不见 → 不应作为用神，命局不取此五行"
    return {"usability": usability, "note": note, "透干": 透干, "通月令": 通月令, "藏地支": 藏地支}


def apply_geju_override(bazi: dict) -> dict:
    """在 bazi 字典上叠加格局信息，并在 yongshen_override 存在时覆盖用神五行。

    [改进 v2，2026-04]：覆盖前后都做反向校验：
    - climate_override 用神（来自 select_yongshen）→ 校验是否在原局真的可用
    - geju_override 用神 → 同样校验
    - 若校验"无" → 拒绝覆盖，回退到 climate 用神

    若 bazi['yongshen']['_locked'] 为真，则跳过覆盖（用户手动指定）。
    """
    # 先校验当前用神（来自 select_yongshen + climate）
    cur_ys = bazi.get("yongshen", {}).get("yongshen")
    if cur_ys:
        bazi["yongshen"]["_reverse_check"] = _yongshen_reverse_check(bazi, cur_ys)

    if bazi.get("yongshen", {}).get("_locked"):
        return bazi

    # v7.4 #5 · 自动识别化气格（优先级最高 · 直接走 phase_override）
    try:
        from _bazi_core import detect_huaqi_pattern, Pillar as _P
        huaqi = detect_huaqi_pattern([_P(p["gan"], p["zhi"]) for p in bazi["pillars"]])
        if huaqi.get("triggered"):
            phase_id = huaqi["suggested_phase"]
            bazi = apply_phase_override(bazi, phase_id)
            bazi["phase"]["auto_detected"] = True
            bazi["phase"]["detection_source"] = "detect_huaqi_pattern"
            bazi["phase"]["evidence"] = huaqi.get("evidence", {})
            return bazi  # 化气格定型 → 不再走常规格局识别
    except Exception:
        pass  # 化气格检测失败不影响主流程

    geju = detect_geju(bazi)
    bazi["geju"] = geju
    if geju["yongshen_override"]:
        candidate = geju["yongshen_override"]
        check = _yongshen_reverse_check(bazi, candidate)
        if check["usability"] == "无":
            geju["override_rejected"] = (
                f"格局识别为「{geju['primary']}」建议用 {candidate}，但反向校验：{check['note']} → 拒绝覆盖"
            )
        else:
            original = bazi["yongshen"]["yongshen"]
            if original != candidate:
                bazi["yongshen"]["yongshen"] = candidate
                bazi["yongshen"]["_geju_override_from"] = original
                bazi["yongshen"]["_geju_override_reason"] = (
                    f"格局派识别为「{geju['primary']}」→ 用神由 {original} 覆盖为 {candidate}（{check['note']}）"
                )
                bazi["yongshen"]["_reverse_check"] = check
    return bazi


# ---------- L0 原局基线 ----------

def l0_baseline(bazi: dict) -> Dict[str, float]:
    """原局基线（人一生不变）。"""
    strength = bazi["strength"]
    yong = bazi["yongshen"]
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = pillars[2].gan

    # Spirit 基线：根据日主中和度 + 印星比劫支撑
    spirit = 50.0
    spirit += -abs(strength["score"]) * 0.15  # 中和最舒适
    spirit += min(strength["sheng"], 8) * 1.0  # 印有支撑
    spirit += min(strength["same"], 6) * 0.6  # 比劫同党
    spirit += -min(strength["kewo"], 8) * 1.2  # 官杀压身
    if yong.get("tongguan"):
        spirit += 4  # 通关需求清晰，知道往哪走

    # Wealth 基线：身能任财（强）+ 财星结构
    wealth = 50.0
    if strength["label"] == "强":
        wealth += min(strength["ke"], 8) * 1.2  # 强身见财
    elif strength["label"] == "弱":
        wealth -= min(strength["ke"], 8) * 0.8  # 弱身见财成负担
    wealth += min(strength["xie"], 6) * 0.8  # 食伤生财链路潜质
    # 库里有财
    for p in pillars:
        if p.zhi in KU_BENQI:
            ku_main = KU_BENQI[p.zhi]
            if calc_shishen(day_gan, ku_main) in ("正财", "偏财"):
                wealth += 3

    # Fame 基线：印 + 官 + 食伤外显
    fame = 50.0
    fame += min(strength["sheng"], 8) * 1.0
    fame += min(strength["kewo"], 6) * 0.6
    fame += min(strength["xie"], 6) * 1.0  # 食伤更外显
    # 官印相生原局
    has_guan = any(calc_shishen(day_gan, p.gan) in ("正官", "七杀") for i, p in enumerate(pillars) if i != 2)
    has_yin = any(calc_shishen(day_gan, p.gan) in ("正印", "偏印") for i, p in enumerate(pillars) if i != 2)
    if has_guan and has_yin:
        fame += 6

    return {
        "spirit": _clip(spirit),
        "wealth": _clip(wealth),
        "fame": _clip(fame),
    }


# ---------- L0/L1/L2 感情维度（v6 新增 · v7 现代化 · 独立通道，不参与三派融合） ----------
#
# 设计原则（v7 现代化重构）：
# 1. **保留命理学结构**：用配偶星 / 配偶宫 / 桃花 / 比劫识别"亲密关系核心"——这是 600 年的
#    五行结构判定方法，结构层面有效。
# 2. **去掉古法的价值判断**：不再有"配偶星弱 = 减分"、"女命印多 = 减分"、"女命食伤 = 减分"
#    （"克夫 / 旺夫 / 伤官克夫"等观念已删除——这些是物化伴侣的封建残余）。
# 3. **支持多元关系取向**：通过 bazi.orientation（hetero/homo/bi/none/poly）调整配偶星识别：
#    - hetero（默认）: 男看财 / 女看官杀（保持向后兼容）
#    - homo: 男看官杀 / 女看财（同性核心关系人）
#    - bi: 同时看财 + 官杀，取较旺者
#    - none: 不识别配偶星，emotion 通道改为"自我亲密能量"（桃花 + 比劫主导，无外向预设）
#    - poly: 配偶星 + 桃花权重提高，反映关系密度 / 流动性
# 4. **emotion 高 ≠ 婚姻顺利**：emotion 高 = 关系能量充沛 + 主导权清晰；emotion 低 = 关系
#    能量稀薄 OR 处于关系切换 / 独处期。**纯中性**，不暗示"婚姻 = 好事 / 单身 = 差事"。
# 5. **不参与三派融合 / 不参与 disputes**：避免污染三派 disputes 检测。
# 6. **配套 R0 反询问 · 关系画像**：用户已在 R0 验证了"偏好类型 + 对方态度"的命局读法。
#    见 fairness_protocol.md §9 / §10 现代化解读规范。


def _spouse_strength(bazi: dict) -> float:
    """根据 orientation 返回配偶星强度。

    hetero: 男 → ke（财）/ 女 → kewo（官杀）
    homo:   男 → kewo（官杀）/ 女 → ke（财）
    bi:     max(ke, kewo)
    none:   返回 0（不识别配偶星）
    poly:   max(ke, kewo)（与 bi 同，但下游加权不同）
    """
    gender = bazi.get("gender", "M").upper()
    orient = bazi.get("orientation", "hetero").lower()
    s = bazi["strength"]
    ke = s.get("ke", 0)
    kewo = s.get("kewo", 0)

    if orient == "none":
        return 0.0
    if orient in ("bi", "poly"):
        return max(ke, kewo)
    if orient == "homo":
        return kewo if gender == "M" else ke
    return ke if gender == "M" else kewo


def emotion_baseline(bazi: dict) -> float:
    """关系能量维度基线 (0-100)。

    v7 现代化：
    - 配偶星弱不再扣分（单身 / 关系稀薄是中性状态，非"差")
    - 删除"女命印多 -4"、"女命食伤旺 -2"（带性别歧视的微调）
    - 删除 gender 在比劫扣分上的差异（同样的结构对所有性别影响相同）
    - 支持 orientation 切换配偶星识别方式
    """
    orient = bazi.get("orientation", "hetero").lower()
    s = bazi["strength"]
    pillars = bazi["pillars"]
    day_zhi = pillars[2]["zhi"]

    base = 50.0

    # 配偶星旺衰（按 orientation 取）
    spouse = _spouse_strength(bazi)
    if orient == "none":
        # 不识别配偶星 → 跳过，emotion 改由桃花 + 比劫 + 食伤主导
        pass
    else:
        if spouse >= 5:
            base += 8  # 配偶星旺 → 关系能量场强
        elif spouse >= 2:
            base += 2  # 配偶星中 → 常态
        # spouse < 1（配偶星弱）不再扣分 —— 命局只表达"非外向关系导向"，非缺陷

    # 桃花地支数（子午卯酉）
    n_peach = sum(1 for p in pillars if p["zhi"] in PEACH_BLOSSOM_ZHIS)
    peach_weight = 2.5 if orient == "poly" else 1.5
    base += n_peach * peach_weight

    # 日支被命局其他柱冲（配偶宫位有结构波动）
    other_zhis = [pillars[i]["zhi"] for i in (0, 1, 3)]
    if any(ZHI_CHONG.get(z) == day_zhi for z in other_zhis):
        base -= 8 if orient != "none" else 4

    # 日支被合（六合配偶宫，关系黏度偏高）
    if any(ZHI_LIU_HE.get(z) == day_zhi for z in other_zhis):
        base += 4 if orient != "none" else 2

    # 比劫多 → 关系里"竞争 / 共享 / 主动争取"模式（不分性别同等扣分）
    if s.get("same", 0) >= 5:
        base -= 5 if orient != "none" else 2

    # 食伤外显 → 表达力 / 吸引力（不分性别同等加分）
    base += min(s.get("xie", 0), 6) * 0.6

    return _clip(base)


def derive_relationship_mode(bazi: dict) -> dict:
    """v7 新增：从命局结构推关系模式（中性描述，无价值判断）。

    返回 {primary_mode, secondary_traits, note} —— 用于 LLM 解读和 R0 候选生成。
    """
    s = bazi["strength"]
    spouse = _spouse_strength(bazi)
    bijie = s.get("same", 0)
    shishang = s.get("xie", 0)
    yin = s.get("sheng", 0)
    pillars = bazi["pillars"]
    has_peach = any(p["zhi"] in PEACH_BLOSSOM_ZHIS for p in pillars)
    orient = bazi.get("orientation", "hetero").lower()

    if orient == "none":
        return {
            "primary_mode": "self_centered",
            "label": "自我中心型 / 单身舒适度高",
            "note": "你声明了不寻求传统亲密关系；emotion 通道反映的是你的'自我亲密能量'"
                    "（自我表达 / 独处恢复 / 内在丰盈度），不预设关系对象。",
        }

    if spouse >= 5 and (shishang >= 4 or has_peach):
        mode = "outward_attractive"
        label = "外向吸引型 / 关系能量充沛"
    elif spouse < 1 and bijie >= 5:
        mode = "competitive_pursuit"
        label = "竞争争取型 / 缘分密度需主动经营"
    elif yin >= 6:
        mode = "nurture_oriented"
        label = "被照护型 / 偏好支持性关系"
    elif spouse >= 2 and shishang >= 3:
        mode = "ambiguous_dynamic"
        label = "暧昧流动型 / 关系定义需主动澄清"
    elif spouse < 2 and shishang <= 2:
        mode = "low_density"
        label = "低密度型 / 心动稀少但稳定"
    else:
        mode = "balanced"
        label = "中性平衡型 / 无明显倾向"

    return {
        "primary_mode": mode,
        "label": label,
        "secondary_traits": {
            "spouse_strength": round(spouse, 2),
            "bijie": round(bijie, 2),
            "shishang": round(shishang, 2),
            "yin": round(yin, 2),
            "has_peach": has_peach,
        },
        "note": "命局只反映关系结构 / 能量模式，不预设对方性别 / 是否结婚 / 是否生育。"
                "这些是你的现代选择，不在命局之内。",
    }


def _spouse_set_by_orient(bazi: dict) -> tuple:
    """按 orientation 返回配偶星十神集合。"""
    gender = bazi.get("gender", "M").upper()
    orient = bazi.get("orientation", "hetero").lower()
    cai = ("正财", "偏财")
    guan = ("正官", "七杀")
    if orient == "none":
        return ()
    if orient in ("bi", "poly"):
        return cai + guan
    if orient == "homo":
        return guan if gender == "M" else cai
    return cai if gender == "M" else guan  # hetero


def emotion_dayun_delta(bazi: dict, dy_p: Pillar) -> float:
    """大运对关系能量维度的常态影响（10 年区间）。

    v7 现代化：
    - 配偶星集合按 orientation 取（hetero/homo/bi/poly/none）
    - 删除"女命伤官见正官 -6"（克夫论的代码体现，已删除）
    - 删除"男命财弱 + 大运比劫 -4"的性别专属规则（改为不分性别的同等扣分）
    """
    day_zhi = bazi["pillars"][2]["zhi"]
    day_gan = bazi["day_master"]
    orient = bazi.get("orientation", "hetero").lower()

    delta = 0.0
    g_shi = calc_shishen(day_gan, dy_p.gan)
    z_shi = calc_zhi_shishen(day_gan, dy_p.zhi)
    spouse_set = _spouse_set_by_orient(bazi)
    bijie_set = ("比肩", "劫财")

    # 大运地支冲日支（配偶宫位被冲，10 年关系结构易动）
    if ZHI_CHONG.get(dy_p.zhi) == day_zhi:
        delta -= 12 if orient != "none" else 6
    # 大运地支合日支（配偶宫位被合，10 年关系黏度高）
    if ZHI_LIU_HE.get(dy_p.zhi) == day_zhi:
        delta += 8 if orient != "none" else 4

    # 大运十神 = 配偶星
    if spouse_set:
        if g_shi in spouse_set:
            delta += 6
        if z_shi in spouse_set:
            delta += 8  # 地支力量更足

    # 大运十神 = 比劫（关系里的"竞争 / 共享"模式被激活，不分性别）
    if g_shi in bijie_set:
        delta -= 4
    if z_shi in bijie_set:
        delta -= 6

    # 大运桃花（poly 取向桃花权重更高）
    if dy_p.zhi in PEACH_BLOSSOM_ZHIS:
        delta += 5 if orient == "poly" else 3

    # 配偶星弱 + 大运比劫旺：关系结构压力（不分性别）
    if spouse_set and _spouse_strength(bazi) < 2 and (g_shi in bijie_set or z_shi in bijie_set):
        delta -= 4

    return delta


def emotion_liunian_delta(bazi: dict, ln_p: Pillar) -> float:
    """流年对关系能量维度的当年影响。

    v7 现代化：配偶星集合按 orientation 取；删除"女命伤官见正官 -4"（克夫论）。
    """
    day_zhi = bazi["pillars"][2]["zhi"]
    day_gan = bazi["day_master"]
    orient = bazi.get("orientation", "hetero").lower()

    delta = 0.0
    g_shi = calc_shishen(day_gan, ln_p.gan)
    z_shi = calc_zhi_shishen(day_gan, ln_p.zhi)
    spouse_set = _spouse_set_by_orient(bazi)
    bijie_set = ("比肩", "劫财")

    # 流年地支冲日支（关系结构起波）
    if ZHI_CHONG.get(ln_p.zhi) == day_zhi:
        delta -= 6 if orient != "none" else 3
    # 流年地支合日支（关系结构亲近）
    if ZHI_LIU_HE.get(ln_p.zhi) == day_zhi:
        delta += 5 if orient != "none" else 2

    # 流年配偶星
    if spouse_set:
        if g_shi in spouse_set:
            delta += 4
        if z_shi in spouse_set:
            delta += 4

    # 流年桃花
    if ln_p.zhi in PEACH_BLOSSOM_ZHIS:
        delta += 3 if orient == "poly" else 2

    # 流年比劫（不分性别）
    if g_shi in bijie_set or z_shi in bijie_set:
        delta -= 3

    return delta


def emotion_year_value(bazi: dict, base: float, dy_p: Pillar, ln_p: Pillar,
                      dy_amp: float = 1.5, ln_amp: float = 1.3) -> float:
    """单年感情值。base 是 emotion_baseline 一次算好的常数。"""
    dy_d = emotion_dayun_delta(bazi, dy_p)
    ln_d = emotion_liunian_delta(bazi, ln_p)
    # 模型：v = 0.45*base + 0.55*50 + 0.6*dy_amp*dy_d + 0.5*ln_amp*ln_d
    v = 0.45 * base + 0.55 * 50 + 0.6 * dy_amp * dy_d + 0.5 * ln_amp * ln_d
    return _clip(v)


# ---------- L1 大运修正 ----------

def _shishen_delta(shishen: str, strength_label: str, weight: float = 1.0) -> Dict[str, float]:
    """根据十神和日主强弱返回 (spirit, wealth, fame) 增量。weight 用于区分 gan/zhi 影响。"""
    s = w = f = 0.0
    if shishen == "正印":
        s += 8 * weight; f += 10 * weight
    elif shishen == "偏印":
        s += 5 * weight; f += 6 * weight
    elif shishen == "比肩":
        s += 6 * weight
        if strength_label == "强":
            w -= 4 * weight
    elif shishen == "劫财":
        s += 3 * weight
        if strength_label == "强":
            w -= 8 * weight
    elif shishen == "食神":
        if strength_label != "弱":
            f += 10 * weight; w += 6 * weight; s += 4 * weight
        else:
            s -= 4 * weight
    elif shishen == "伤官":
        if strength_label != "弱":
            f += 14 * weight; w += 8 * weight
        else:
            s -= 6 * weight; f += 4 * weight
    elif shishen == "正财":
        if strength_label == "强":
            w += 14 * weight
        else:
            w -= 6 * weight; s -= 3 * weight
    elif shishen == "偏财":
        if strength_label == "强":
            w += 16 * weight
        else:
            w -= 5 * weight
    elif shishen == "正官":
        if strength_label != "弱":
            f += 12 * weight; s += 4 * weight
        else:
            s -= 4 * weight
    elif shishen == "七杀":
        if strength_label == "强":
            f += 8 * weight; s -= 2 * weight
        else:
            s -= 12 * weight
    return {"spirit": s, "wealth": w, "fame": f}


def l1_dayun_adjust(bazi: dict, dayun_pillar: Pillar) -> Dict[str, Dict[str, float]]:
    """大运对原局的影响（区间常态）。返回三派各自的 delta。"""
    yong = bazi["yongshen"]
    day_gan = bazi["day_master"]
    yongshen_wx = yong["yongshen"]
    jishen_wx = yong["jishen"]
    tongguan_wx = yong.get("tongguan")
    strength_label = bazi["strength"]["label"]

    g_wx = GAN_WUXING[dayun_pillar.gan]
    z_wx = ZHI_WUXING[dayun_pillar.zhi]
    is_yong = (g_wx == yongshen_wx) or (z_wx == yongshen_wx)
    is_ji = (g_wx == jishen_wx) or (z_wx == jishen_wx)
    is_tong = tongguan_wx is not None and (g_wx == tongguan_wx or z_wx == tongguan_wx)

    g_shi = calc_shishen(day_gan, dayun_pillar.gan)
    z_shi = calc_zhi_shishen(day_gan, dayun_pillar.zhi)

    # 扶抑派：用神 / 忌神 + 十神（gan + zhi 都看，zhi 权重更大因为是大运地支）
    fy = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}
    if is_yong:
        fy["spirit"] += 14; fy["wealth"] += 12; fy["fame"] += 10
    if is_ji:
        fy["spirit"] -= 16; fy["wealth"] -= 14; fy["fame"] -= 12
    for k, d in _shishen_delta(g_shi, strength_label, weight=1.0).items():
        fy[k] += d
    for k, d in _shishen_delta(z_shi, strength_label, weight=1.4).items():
        fy[k] += d

    # 调候派
    th = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}
    season = yong.get("season", "春")
    needed = {"春": "金", "夏": "水", "秋": "木", "冬": "火"}[season]
    if g_wx == needed:
        th["spirit"] += 6; th["fame"] += 4
    if z_wx == needed:
        th["spirit"] += 10; th["wealth"] += 6; th["fame"] += 6
    anti = {"春": "土", "夏": "火", "秋": "金", "冬": "水"}[season]
    if g_wx == anti:
        th["spirit"] -= 5
    if z_wx == anti:
        th["spirit"] -= 8; th["wealth"] -= 4

    # 格局派
    gj = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}
    if is_tong:
        gj["spirit"] += 12; gj["wealth"] += 8; gj["fame"] += 8
    # 财官印枢纽强化
    if g_shi in ("正财", "偏财") and z_shi in ("食神", "伤官"):
        gj["wealth"] += 12  # 食伤生财链
    if g_shi in ("正官",) and z_shi in ("正印", "偏印"):
        gj["fame"] += 14  # 官印相生
    if g_shi in ("七杀",) and z_shi in ("正印", "偏印") and strength_label == "弱":
        gj["fame"] += 12; gj["spirit"] += 6  # 杀印相生
    # 大运冲日柱
    if ZHI_CHONG.get(dayun_pillar.zhi) == bazi["pillars"][2]["zhi"]:
        gj["spirit"] -= 8; gj["wealth"] -= 4

    return {"fuyi": fy, "tiaohou": th, "geju": gj}


# ---------- L2 流年修正 ----------

def l2_liunian_adjust(
    bazi: dict, dayun_p: Pillar, ln_p: Pillar
) -> Tuple[Dict[str, Dict[str, float]], List[Dict]]:
    yong = bazi["yongshen"]
    day_gan = bazi["day_master"]
    yongshen_wx = yong["yongshen"]
    jishen_wx = yong["jishen"]
    tongguan_wx = yong.get("tongguan")
    strength_label = bazi["strength"]["label"]
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]

    g_wx = GAN_WUXING[ln_p.gan]
    z_wx = ZHI_WUXING[ln_p.zhi]

    g_shi = calc_shishen(day_gan, ln_p.gan)
    z_shi = calc_zhi_shishen(day_gan, ln_p.zhi)

    interactions = []

    # 扶抑派：用神 / 忌神 + 十神
    fy = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}
    if g_wx == yongshen_wx:
        fy["spirit"] += 6; fy["wealth"] += 4; fy["fame"] += 4
    if z_wx == yongshen_wx:
        fy["spirit"] += 8; fy["wealth"] += 6; fy["fame"] += 6
    if g_wx == jishen_wx:
        fy["spirit"] -= 6; fy["wealth"] -= 4; fy["fame"] -= 4
    if z_wx == jishen_wx:
        fy["spirit"] -= 8; fy["wealth"] -= 6; fy["fame"] -= 6
    for k, d in _shishen_delta(g_shi, strength_label, weight=0.8).items():
        fy[k] += d
    for k, d in _shishen_delta(z_shi, strength_label, weight=1.1).items():
        fy[k] += d

    # 七杀有印化的特例（流年）—— 干 / 支 都看
    dm_wx_local = GAN_WUXING[day_gan]
    yin_wx = WUXING_SHENG[dm_wx_local]
    has_yin_in_yuanju = (
        any(GAN_WUXING[p.gan] == yin_wx for p in pillars)
        or any(ZHI_WUXING[p.zhi] == yin_wx for p in pillars)
    )
    if (g_shi == "七杀" or z_shi == "七杀") and has_yin_in_yuanju:
        fy["fame"] += 6
        fy["spirit"] += 4  # 杀印相生

    # 调候派
    th = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}
    season = yong.get("season", "春")
    needed = {"春": "金", "夏": "水", "秋": "木", "冬": "火"}[season]
    if g_wx == needed:
        th["spirit"] += 4; th["fame"] += 2
    if z_wx == needed:
        th["spirit"] += 6; th["wealth"] += 4
    anti = {"春": "土", "夏": "火", "秋": "金", "冬": "水"}[season]
    if g_wx == anti:
        th["spirit"] -= 4
    if z_wx == anti:
        th["spirit"] -= 5

    # 格局派
    gj = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}

    if tongguan_wx and (g_wx == tongguan_wx or z_wx == tongguan_wx):
        gj["spirit"] += 10; gj["wealth"] += 6; gj["fame"] += 6
        interactions.append({"type": "通关", "wuxing": tongguan_wx, "magnitude": "中"})

    # 财库被冲开
    for p in pillars:
        if p.zhi in KU_BENQI and ZHI_CHONG.get(ln_p.zhi) == p.zhi:
            ku_main = KU_BENQI[p.zhi]
            ku_shi = calc_shishen(day_gan, ku_main)
            if ku_shi in ("正财", "偏财"):
                gj["wealth"] += 16
                interactions.append({"type": "财库被冲开", "pillar": str(p), "magnitude": "高"})
            elif ku_shi in ("正官", "七杀"):
                gj["fame"] += 12
                interactions.append({"type": "官库被冲开", "pillar": str(p), "magnitude": "中"})
            elif ku_shi in ("食神", "伤官"):
                gj["fame"] += 10; gj["wealth"] += 6
                interactions.append({"type": "食伤库被冲开", "pillar": str(p), "magnitude": "中"})

    # 伏吟（与原局任一柱完全相同）
    for i, p in enumerate(pillars):
        if is_fuyin(p, ln_p):
            fuyin_with = ["年柱", "月柱", "日柱", "时柱"][i]
            gj["spirit"] -= 6
            interactions.append({"type": "伏吟", "with": fuyin_with, "magnitude": "中"})
            break

    # 反吟（天克地冲）
    for i, p in enumerate(pillars):
        if is_fanyin(p, ln_p):
            gj["spirit"] -= 10; gj["wealth"] -= 6; gj["fame"] += 4
            interactions.append({"type": "反吟", "with": ["年柱","月柱","日柱","时柱"][i], "magnitude": "高"})
            break

    # 流年支冲日柱
    if ZHI_CHONG.get(ln_p.zhi) == bazi["pillars"][2]["zhi"]:
        gj["spirit"] -= 8; gj["wealth"] -= 4
        interactions.append({"type": "冲日柱", "magnitude": "高"})

    # 相穿
    for i, p in enumerate(pillars):
        if ZHI_CHUAN.get(p.zhi) == ln_p.zhi:
            gj["spirit"] -= 5
            interactions.append({"type": "相穿", "with": ["年柱","月柱","日柱","时柱"][i], "magnitude": "低"})
            break

    # 三合 / 三会成局（含原局两支 + 流年第三支）
    pillar_zhi = [p.zhi for p in pillars]
    for group, group_wx in SANHE_GROUPS:
        if ln_p.zhi in group:
            others_in = [z for z in group if z != ln_p.zhi and z in pillar_zhi]
            if len(others_in) >= 2:
                if group_wx == yongshen_wx:
                    gj["spirit"] += 10; gj["wealth"] += 6; gj["fame"] += 6
                    interactions.append({"type": "三合用神局", "wuxing": group_wx, "magnitude": "高"})
                elif group_wx == jishen_wx:
                    gj["spirit"] -= 10; gj["wealth"] -= 6
                    interactions.append({"type": "三合忌神局", "wuxing": group_wx, "magnitude": "高"})

    # 财格 / 食伤生财链（流年财星 + 原局食伤）
    if g_shi in ("正财", "偏财"):
        has_shi_shang = any(
            calc_shishen(day_gan, p.gan) in ("食神", "伤官")
            for i, p in enumerate(pillars) if i != 2
        )
        if has_shi_shang and strength_label != "弱":
            gj["wealth"] += 8

    # 伤官见官（原局有官，流年伤官）→ 名声下挫
    # 但若原局 / 流年有印化，则伤官见官的负面被印化大幅吸收（甚至转为正向：印克伤官护身）
    if g_shi == "伤官":
        has_guan = any(
            calc_shishen(day_gan, p.gan) in ("正官", "七杀")
            for i, p in enumerate(pillars) if i != 2
        ) or any(
            calc_zhi_shishen(day_gan, p.zhi) in ("正官", "七杀")
            for i, p in enumerate(pillars) if i != 2
        )
        if has_guan:
            yin_wx2 = WUXING_SHENG[GAN_WUXING[day_gan]]
            has_yin_protect = (
                any(GAN_WUXING[p.gan] == yin_wx2 for p in pillars)
                or any(ZHI_WUXING[p.zhi] == yin_wx2 for p in pillars)
                or GAN_WUXING[ln_p.gan] == yin_wx2
                or ZHI_WUXING[ln_p.zhi] == yin_wx2
            )
            if has_yin_protect:
                gj["fame"] -= 4
                gj["spirit"] -= 3
                interactions.append({"type": "伤官见官·印化护身", "magnitude": "中"})
            else:
                gj["fame"] -= 12
                interactions.append({"type": "伤官见官", "magnitude": "高"})

    return {"fuyi": fy, "tiaohou": th, "geju": gj}, interactions


# ---------- 三派融合 ----------

SCHOOL_NAMES = ("fuyi", "tiaohou", "geju")
SCHOOL_LABELS = {"fuyi": "扶抑派", "tiaohou": "调候派", "geju": "格局派"}


def fuse_schools(
    base: Dict[str, float],
    schools_l1: Dict[str, Dict[str, float]],
    schools_l2: Dict[str, Dict[str, float]],
    weights: Dict[str, float],
) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, Dict[str, float]]]:
    """三派加性融合 → (final_value, confidence, divergence, per_school_scores)。

    模型：year = α·base + (1-α)·50 + β·1.6·l1_delta + γ·1.4·l2_delta
    每派 delta 是有符号修正量（-30~+30）。
    """
    a, b, g = weights["alpha"], weights["beta"], weights["gamma"]
    AMPLIFY_L1 = 1.6
    AMPLIFY_L2 = 1.4
    out: Dict[str, float] = {}
    confidence: Dict[str, str] = {}
    divergence: Dict[str, float] = {}
    per_school_out: Dict[str, Dict[str, float]] = {}

    for dim in ("spirit", "wealth", "fame"):
        per_school: Dict[str, float] = {}
        for school in SCHOOL_NAMES:
            l1d = schools_l1[school][dim]
            l2d = schools_l2[school][dim]
            v = a * base[dim] + (1 - a) * 50 + b * AMPLIFY_L1 * l1d + g * AMPLIFY_L2 * l2d
            per_school[school] = round(_clip(v), 1)
        per_school_out[dim] = per_school

        vals = list(per_school.values())
        spread = max(vals) - min(vals)
        divergence[dim] = round(spread, 2)
        if spread <= 10:
            final = sum(vals) / 3
            confidence[dim] = "high"
        elif spread <= 20:
            final = statistics.median(vals)
            confidence[dim] = "mid"
        else:
            final = statistics.median(vals) * 0.85 + 50 * 0.15
            confidence[dim] = "low"
        out[dim] = _clip(final)

    return out, confidence, divergence, per_school_out


def _clip(v: float, lo: float = 8.0, hi: float = 96.0) -> float:
    return max(lo, min(hi, v))


# ---------- 累积线（虚线）：指数衰减加权 ----------

def cumulative_curve(yearly: List[float], lam: float) -> List[float]:
    raw: List[float] = []
    acc = 0.0
    for v in yearly:
        acc = lam * acc + (v - 50)  # 以 50 为基线，sum deviations
        raw.append(acc)
    if not raw:
        return []
    # 标准化到 [10, 95]
    rmin, rmax = min(raw), max(raw)
    if rmax - rmin < 1e-9:
        return [50.0] * len(raw)
    return [10.0 + (x - rmin) / (rmax - rmin) * 85.0 for x in raw]


# ---------- 主入口 ----------

def apply_structural_corrections(bazi: dict, confirmed_facts: dict | None) -> Tuple[dict, List[dict]]:
    """v7.2 · 根据 confirmed_facts.structural_corrections 修正 bazi 的 climate / strength / yongshen / geju / phase。

    用户在前序校验中已经把"原本判 燥实，但我体感是寒湿"或"算法默认主导，但 R0+R1+R2 验证后改用从财格"
    这种纠错固化进了 confirmed_facts.json；score 时应该尊重这些纠错，避免把同一错误再算一遍。

    支持的 kind:
        climate         → 修改 bazi["yongshen"]["climate"]["label"]
        strength        → 修改 bazi["strength"]["label"]
        yongshen        → 修改 bazi["yongshen"]["yongshen"]
        geju            → 修改 bazi["geju"]["primary"]
        phase_override  → 调用 apply_phase_override(bazi, after) 整体反演相位（v7.1+）
    """
    applied: List[dict] = []
    if not confirmed_facts:
        return bazi, applied
    corrections = confirmed_facts.get("structural_corrections", []) or []
    if not corrections:
        return bazi, applied

    import copy
    bazi = copy.deepcopy(bazi)

    for c in corrections:
        kind = c.get("kind")
        before = c.get("before")
        after = c.get("after")
        reason = c.get("reason", "")
        if not kind or not after:
            continue

        if kind == "climate":
            climate = bazi.setdefault("yongshen", {}).setdefault("climate", {})
            climate["label"] = after
            climate.setdefault("structural_correction_history", []).append({
                "before": before, "after": after, "reason": reason,
            })
            applied.append({"kind": "climate", "before": before, "after": after, "reason": reason})

        elif kind == "strength":
            strength = bazi.setdefault("strength", {})
            strength["label"] = after
            strength.setdefault("structural_correction_history", []).append({
                "before": before, "after": after, "reason": reason,
            })
            applied.append({"kind": "strength", "before": before, "after": after, "reason": reason})

        elif kind == "yongshen":
            yong = bazi.setdefault("yongshen", {})
            yong["yongshen"] = after
            yong.setdefault("structural_correction_history", []).append({
                "before": before, "after": after, "reason": reason,
            })
            applied.append({"kind": "yongshen", "before": before, "after": after, "reason": reason})

        elif kind == "geju":
            geju = bazi.setdefault("geju", {})
            geju["primary"] = after
            geju.setdefault("structural_correction_history", []).append({
                "before": before, "after": after, "reason": reason,
            })
            applied.append({"kind": "geju", "before": before, "after": after, "reason": reason})

        elif kind == "phase_override":
            # v7.1+ phase 反演：after = phase_id（如 "floating_dms_to_cong_cai"）
            bazi = apply_phase_override(bazi, after)
            applied.append({"kind": "phase_override", "before": before or "day_master_dominant",
                            "after": after, "reason": reason})

    return bazi, applied


def apply_phase_override(bazi: dict, phase_id: str) -> dict:
    """v7 P1-7 · 相位反演：按 phase_id 改写 strength.label / yongshen / climate / 加 phase 字段。

    详见 references/phase_inversion_protocol.md §4.2

    支持的 phase_id：
        day_master_dominant         (默认 · 不反演)
        floating_dms_to_cong_cai    日主虚浮 → 从财格
        floating_dms_to_cong_sha    日主虚浮 → 从杀格
        floating_dms_to_cong_er     日主虚浮 → 从儿格（食伤）
        floating_dms_to_cong_yin    日主虚浮 → 从印格
        dominating_god_cai_zuo_zhu  旺神得令·财星主事
        dominating_god_guan_zuo_zhu 旺神得令·官杀主事
        dominating_god_shishang_zuo_zhu  旺神得令·食伤主事
        dominating_god_yin_zuo_zhu  旺神得令·印星主事
        climate_inversion_dry_top   调候反向·上燥下寒（用神锁水）
        climate_inversion_wet_top   调候反向·上湿下燥（用神锁火）
        true_following              真从格（按从神方向）
        pseudo_following            假从格（仍扶身但加 caveat）
    """
    if phase_id == "day_master_dominant" or not phase_id:
        bazi.setdefault("phase", {"id": "day_master_dominant", "label": "默认 · 日主主导"})
        return bazi

    pid = phase_id
    label_map = {
        "floating_dms_to_cong_cai": "弃命从财（日主虚浮 → 财星主事）",
        "floating_dms_to_cong_sha": "弃命从杀（日主虚浮 → 官杀主事）",
        "floating_dms_to_cong_er": "弃命从儿（日主虚浮 → 食伤主事）",
        "floating_dms_to_cong_yin": "弃命从印（日主虚浮 → 印星主事）",
        "dominating_god_cai_zuo_zhu": "旺神得令·财星主事 · 日主借力",
        "dominating_god_guan_zuo_zhu": "旺神得令·官杀主事 · 日主受制",
        "dominating_god_shishang_zuo_zhu": "旺神得令·食伤主事 · 日主泄秀",
        "dominating_god_yin_zuo_zhu": "旺神得令·印主事 · 日主被庇护",
        "climate_inversion_dry_top": "调候反向·上燥下寒（用神锁水）",
        "climate_inversion_wet_top": "调候反向·上湿下燥（用神锁火）",
        "true_following": "真从格 · 按从神方向走",
        "pseudo_following": "假从格 · 仍按弱身扶身但加 caveat",
        # v7.4 #5 · 化气格（5 种）
        "huaqi_to_土": "化土格（甲己合化土）· 命局主导改为土",
        "huaqi_to_金": "化金格（乙庚合化金）· 命局主导改为金",
        "huaqi_to_水": "化水格（丙辛合化水）· 命局主导改为水",
        "huaqi_to_木": "化木格（丁壬合化木）· 命局主导改为木",
        "huaqi_to_火": "化火格（戊癸合化火）· 命局主导改为火",
    }
    if pid not in label_map:
        raise ValueError(f"unknown --override-phase id: {pid!r}, valid: {list(label_map.keys()) + ['day_master_dominant']}")

    bazi["phase"] = {
        "id": pid,
        "label": label_map[pid],
        "is_inverted": True,
        "default_phase_was": "day_master_dominant",
    }
    bazi.setdefault("yongshen", {})
    bazi.setdefault("strength", {})

    # v9 root_strength 否决守卫：从格 / 化气格类 phase 必须满足无根/微根门槛
    # 修 1996/12/08 case 假从误判（详见 references/diagnosis_pitfalls.md §13-14）
    _rs = (bazi.get("strength") or {}).get("root_strength") or {}
    if _rs:
        rs_total = _rs.get("total_root", 0.0)
        rs_yin = _rs.get("yin_root", 0.0)
        rs_label = _rs.get("label", "")
        warns = []
        if pid.startswith("floating_dms_to_cong_") or pid == "true_following":
            if rs_total >= 0.30:
                warns.append(
                    f"day_master.root_strength={rs_label}(total={rs_total:.2f}); "
                    f"真从格门槛要求 total<0.30。建议改判为 pseudo_following 或杀印相生格。"
                )
            if rs_yin >= 0.50:
                warns.append(
                    f"yin_root={rs_yin:.2f}>=0.50（有印根）；从格典型不容许印护身。"
                    f"参考 references/diagnosis_pitfalls.md §14。"
                )
        if pid.startswith("huaqi_to_") and rs_total >= 1.50:
            warns.append(
                f"化气格要求日主无根(total<1.5); 当前 total={rs_total:.2f}({rs_label})；"
                f"建议改判为复合相位 + 化神调候。"
            )
        if warns:
            bazi["phase"]["_root_strength_warnings"] = warns

    # ① 从势类：日主从弱反推为"按强读" + 用神锁定为"从神"方向
    if pid.startswith("floating_dms_to_cong_") or pid == "true_following":
        bazi["strength"]["_phase_orig_label"] = bazi["strength"].get("label")
        bazi["strength"]["_phase_orig_score"] = bazi["strength"].get("score")
        bazi["strength"]["label"] = "强"  # 从神为主 → 按强势日主读
        bazi["strength"]["score"] = 30
        cong_to_wuxing = {
            "floating_dms_to_cong_cai": _strength_to_dom_wuxing(bazi, "ke"),
            "floating_dms_to_cong_sha": _strength_to_dom_wuxing(bazi, "kewo"),
            "floating_dms_to_cong_er": _strength_to_dom_wuxing(bazi, "xie"),
            "floating_dms_to_cong_yin": _strength_to_dom_wuxing(bazi, "sheng"),
            "true_following": _strength_to_dom_wuxing(bazi, None),
        }
        new_ys = cong_to_wuxing.get(pid)
        if new_ys:
            bazi["yongshen"]["_phase_orig_yongshen"] = bazi["yongshen"].get("yongshen")
            bazi["yongshen"]["yongshen"] = new_ys
            bazi["yongshen"]["_phase_override_reason"] = f"{label_map[pid]} → 用神锁定 {new_ys}"
            bazi["yongshen"]["_locked"] = True

    # ② 旺神得令：保留 strength.label，但改写 yongshen 为"旺神维持方向"
    elif pid.startswith("dominating_god_"):
        dom_dim = {
            "dominating_god_cai_zuo_zhu": "ke",
            "dominating_god_guan_zuo_zhu": "kewo",
            "dominating_god_shishang_zuo_zhu": "xie",
            "dominating_god_yin_zuo_zhu": "sheng",
        }[pid]
        new_ys = _strength_to_dom_wuxing(bazi, dom_dim)
        if new_ys:
            bazi["yongshen"]["_phase_orig_yongshen"] = bazi["yongshen"].get("yongshen")
            bazi["yongshen"]["yongshen"] = new_ys
            bazi["yongshen"]["_phase_override_reason"] = f"{label_map[pid]} → 用神锁定 {new_ys}"
            bazi["yongshen"]["_locked"] = True

    # ③ 调候反向：锁用神为"制反方向"
    elif pid == "climate_inversion_dry_top":
        bazi["yongshen"]["_phase_orig_yongshen"] = bazi["yongshen"].get("yongshen")
        bazi["yongshen"]["yongshen"] = "水"
        bazi["yongshen"]["_phase_override_reason"] = "上燥下寒 → 用神锁定 水"
        bazi["yongshen"]["_locked"] = True
    elif pid == "climate_inversion_wet_top":
        bazi["yongshen"]["_phase_orig_yongshen"] = bazi["yongshen"].get("yongshen")
        bazi["yongshen"]["yongshen"] = "火"
        bazi["yongshen"]["_phase_override_reason"] = "上湿下燥 → 用神锁定 火"
        bazi["yongshen"]["_locked"] = True

    # ④ 假从：strength 保持，用神保持，仅加 caveat 标记
    elif pid == "pseudo_following":
        bazi["yongshen"]["_phase_caveat"] = "假从格 · 用神扶身但置信度降低；大运若顺从神则按从势补充读"

    # ⑤ 化气格（v7.4 #5）：日主借合化易主 → 用神锁定为化神，扶抑全部翻转
    elif pid.startswith("huaqi_to_"):
        huashen = pid.split("_")[-1]
        bazi["strength"]["_phase_orig_label"] = bazi["strength"].get("label")
        bazi["strength"]["_phase_orig_score"] = bazi["strength"].get("score")
        bazi["strength"]["label"] = "强"  # 化神为主 → 按强势读
        bazi["strength"]["score"] = 35
        bazi["yongshen"]["_phase_orig_yongshen"] = bazi["yongshen"].get("yongshen")
        bazi["yongshen"]["yongshen"] = huashen  # 用神 = 化神（生扶化神之物 = 喜）
        bazi["yongshen"]["_phase_override_reason"] = (
            f"化{huashen}格 · 日主借合化易主 → 用神锁定 {huashen}（生扶化神为喜，克化神为忌）"
        )
        bazi["yongshen"]["_locked"] = True
        # 化神维度旗帜：score / scoring_rubric 在维度配置时可读取此字段
        bazi["yongshen"]["_huashen"] = huashen

    return bazi


def _strength_to_dom_wuxing(bazi: dict, dim: str | None) -> str | None:
    """根据 strength 字段或全局 _wuxing_count 推回旺神所属五行。

    dim ∈ {ke (财), kewo (官杀), xie (食伤), sheng (印), None (取最强)}
    """
    from _bazi_core import GAN_WUXING, WUXING_KE, WUXING_SHENG, WUXING_ORDER, ZHI_HIDDEN_GAN

    pillars_d = bazi["pillars"]
    day_gan = bazi.get("day_master") or pillars_d[2]["gan"]
    day_wx = GAN_WUXING[day_gan]
    cnt = {wx: 0.0 for wx in WUXING_ORDER}
    for i, p in enumerate(pillars_d):
        cnt[GAN_WUXING[p["gan"]]] += 1.0
        weight = 3.0 if i == 1 else 2.0
        for j, hg in enumerate(ZHI_HIDDEN_GAN[p["zhi"]]):
            cnt[GAN_WUXING[hg]] += weight * (1.0 if j == 0 else 0.3)

    if dim is None:
        candidates = [(wx, score) for wx, score in cnt.items() if wx != day_wx]
        candidates.sort(key=lambda x: -x[1])
        return candidates[0][0] if candidates else None

    if dim == "ke":
        return next((wx for wx in WUXING_ORDER if WUXING_KE.get(day_wx) == wx), None)
    if dim == "kewo":
        return next((wx for wx in WUXING_ORDER if WUXING_KE.get(wx) == day_wx), None)
    if dim == "xie":
        return next((wx for wx in WUXING_ORDER if WUXING_SHENG.get(day_wx) == wx), None)
    if dim == "sheng":
        return next((wx for wx in WUXING_ORDER if WUXING_SHENG.get(wx) == day_wx), None)
    return None


def score(
    bazi: dict,
    weights: Dict[str, float] | None = None,
    lambdas: Dict[str, float] | None = None,
    age_start: int = 0,
    age_end: int = 60,
    forecast_from_year: int | None = None,
    forecast_window: int = 10,
    dispute_threshold: float = 20.0,
    mangpai: dict | None = None,
    override_phase: str | None = None,
    confirmed_facts: dict | None = None,
) -> dict:
    """计算 [age_start, age_end] 范围内的曲线 + 未来 forecast_window 年的拐点表。

    参数:
        age_start, age_end: 评分年龄区间（含两端），默认 0–60
        forecast_from_year: 拐点表起始公历年份；None 则取出生年 + age_end - forecast_window
        forecast_window: 拐点窗口长度（年），默认 10
        dispute_threshold: 三派极差超过此值则判定为「派别争议年份」，默认 20
        mangpai: mangpai_events.detect_all 的返回值；若提供则启用盲派烈度修正
                 （不进 25% 融合权重，仅在三派融合后 ±烈度档；事件文本附入 points）
        override_phase: 显式指定相位 id（v7.1）；优先级高于 confirmed_facts.phase_override
        confirmed_facts: confirmed_facts.json 的内容（v7.2）；若提供则在打分前应用
                 structural_corrections（已确认的 climate / strength / yongshen / geju / phase_override 纠错）。
    """
    weights = weights or DEFAULT_WEIGHTS
    lambdas = lambdas or DEFAULT_LAMBDA
    bazi, sc_applied = apply_structural_corrections(bazi, confirmed_facts)

    # v8 · 优先级：override_phase（CLI 调试强制） > bazi.phase.id（来自 solve_bazi/phase_posterior） > 默认
    # 仅当 phase 不是默认相位时才反演（DM_dominant 不需要走 apply_phase_override）
    effective_phase_id: str | None = override_phase
    if not effective_phase_id:
        bp = bazi.get("phase") or {}
        candidate_pid = bp.get("id")
        if candidate_pid and candidate_pid != "day_master_dominant":
            effective_phase_id = candidate_pid
    if effective_phase_id:
        bazi = apply_phase_override(bazi, effective_phase_id)
    bazi = apply_geju_override(bazi)  # 格局为先：先识别格局，再用其覆盖用神
    base = l0_baseline(bazi)
    emo_base = emotion_baseline(bazi)  # v6 关系能量维度基线（独立通道，v7 现代化）
    base["emotion"] = emo_base
    relationship_mode = derive_relationship_mode(bazi)  # v7 中性关系模式描述
    dayun = bazi["dayun"]
    liunian = bazi["liunian"]

    # 盲派事件按年份索引
    mangpai_events_by_year: Dict[int, List[dict]] = {}
    if mangpai and mangpai.get("events"):
        for ev in mangpai["events"]:
            mangpai_events_by_year.setdefault(ev["year"], []).append(ev)

    # v7.4 #5 · 神煞预计算：原局命中 → 终生 baseline；目标地支表 → 大运/流年逢则当年触发
    try:
        from _bazi_core import detect_shensha, SHENSHA_IMPACT, Pillar as _Psh
        _shensha = detect_shensha([_Psh(p["gan"], p["zhi"]) for p in bazi["pillars"]])
        # 把命中的"终生 baseline"加到 base 里
        for ss_key, ss_info in _shensha.items():
            impact = SHENSHA_IMPACT.get(ss_key, {})
            if ss_info["found"]:
                for dim, delta in impact.get("in_chart_bonus", {}).items():
                    if dim in base:
                        base[dim] = _clip(base[dim] + delta)
                    elif dim == "emotion":
                        base["emotion"] = _clip(base.get("emotion", 50) + delta)
                for dim, delta in impact.get("in_chart_penalty", {}).items():
                    if dim in base:
                        base[dim] = _clip(base[dim] + delta)
                    elif dim == "emotion":
                        base["emotion"] = _clip(base.get("emotion", 50) + delta)
        bazi["shensha"] = _shensha
    except Exception as _e:
        _shensha = {}
        bazi["shensha"] = {}

    if age_start < 0:
        age_start = 0
    if age_end < age_start:
        raise ValueError(f"age_end ({age_end}) must be >= age_start ({age_start})")

    def find_dayun(age: int):
        for d in dayun:
            if d["start_age"] <= age <= d["end_age"]:
                return d
        return None

    points = []
    spirit_yearly: List[float] = []
    wealth_yearly: List[float] = []
    fame_yearly: List[float] = []
    emotion_yearly: List[float] = []  # v6 感情维度（独立通道）

    for ln in liunian:
        age = ln["age"]
        if age < age_start:
            continue
        if age > age_end:
            break
        dy = find_dayun(age)
        if dy is None:
            dy_p = Pillar(bazi["pillars"][1]["gan"], bazi["pillars"][1]["zhi"])
            dy_label = "起运前"
            transition = False
        else:
            dy_p = Pillar(dy["gan"], dy["zhi"])
            dy_label = dy["gan"] + dy["zhi"]
            transition = (age == dy["start_age"]) or (age == dy["end_age"])

        ln_p = Pillar(ln["gan"], ln["zhi"])
        l1 = l1_dayun_adjust(bazi, dy_p)
        l2, interactions = l2_liunian_adjust(bazi, dy_p, ln_p)

        values, confidence, divergence, per_school = fuse_schools(base, l1, l2, weights)

        if transition:
            for dim in values:
                values[dim] = 50 + (values[dim] - 50) * 0.7

        # 盲派烈度修正：在三派融合分数上 ±烈度档（不进入 25% 融合权重）
        year_mp_events = mangpai_events_by_year.get(ln["year"], [])
        mp_adjust = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0}
        for ev in year_mp_events:
            for dim, delta in ev.get("amplifier", {}).items():
                if dim in mp_adjust:
                    mp_adjust[dim] += delta
        # 限幅，避免单年盲派叠加冲爆
        for dim in mp_adjust:
            mp_adjust[dim] = max(-12, min(12, mp_adjust[dim]))
            values[dim] = _clip(values[dim] + mp_adjust[dim])

        # v7.4 #5 · 神煞当年触发（大运 / 流年地支命中 target_zhi → 微调 ±0.5~1.0）
        ss_adjust = {"spirit": 0.0, "wealth": 0.0, "fame": 0.0, "emotion": 0.0}
        ss_triggered_this_year: List[str] = []
        for ss_key, ss_info in _shensha.items():
            impact = SHENSHA_IMPACT.get(ss_key, {})
            target_set = set(ss_info.get("target_zhi", []))
            if not target_set:
                continue
            zhi_hits_this_year = []
            if ln_p.zhi in target_set:
                zhi_hits_this_year.append(("liunian", ln_p.zhi))
            if dy is not None and dy_p.zhi in target_set:
                zhi_hits_this_year.append(("dayun", dy_p.zhi))
            if not zhi_hits_this_year:
                continue
            ss_triggered_this_year.append(impact.get("label", ss_key))
            for dim, delta in impact.get("yearly_bonus", {}).items():
                if dim in ss_adjust:
                    ss_adjust[dim] += delta
            for dim, delta in impact.get("yearly_penalty", {}).items():
                if dim in ss_adjust:
                    ss_adjust[dim] += delta
            # 驿马 → 该年波动幅度 +30%（不直接加分，影响 sigma）
            # 注：volatility 处理在后续 sigma 计算阶段
        for dim in ("spirit", "wealth", "fame"):
            ss_adjust[dim] = max(-3, min(3, ss_adjust[dim]))  # 神煞影响小于盲派
            values[dim] = _clip(values[dim] + ss_adjust[dim])

        spirit_yearly.append(values["spirit"])
        wealth_yearly.append(values["wealth"])
        fame_yearly.append(values["fame"])

        # v6 感情维度（独立通道：不参与三派融合 / 不参与 disputes）
        emo_v = emotion_year_value(bazi, emo_base, dy_p, ln_p)
        if transition:
            emo_v = 50 + (emo_v - 50) * 0.7
        # v7.4 #5 · 神煞 emotion 调整（桃花 / 孤辰寡宿）
        emo_v = _clip(emo_v + ss_adjust.get("emotion", 0.0))
        emotion_yearly.append(emo_v)
        values["emotion"] = emo_v
        confidence["emotion"] = "high"  # 感情通道不存在三派分歧
        divergence["emotion"] = 0.0

        # 该年是否出现派别争议（任一维度极差超过阈值）
        is_disputed = any(divergence[dim] > dispute_threshold for dim in divergence)
        disputed_dims = [dim for dim in divergence if divergence[dim] > dispute_threshold]

        points.append({
            "age": age,
            "year": ln["year"],
            "ganzhi": ln["gan"] + ln["zhi"],
            "dayun": dy_label,
            "spirit_yearly": round(values["spirit"], 1),
            "wealth_yearly": round(values["wealth"], 1),
            "fame_yearly": round(values["fame"], 1),
            "emotion_yearly": round(values["emotion"], 1),
            "confidence": confidence,
            "divergence": divergence,
            "school_scores": per_school,
            "interactions": interactions,
            "transition": transition,
            "is_disputed": is_disputed,
            "disputed_dimensions": disputed_dims,
            "mangpai_events": [
                {"key": e["key"], "name": e["name"], "intensity": e["intensity"],
                 "canonical_event": e["canonical_event"], "evidence": e["evidence"],
                 "school": e["school"], "falsifiability": e["falsifiability"]}
                for e in year_mp_events
            ],
            "mangpai_adjust": {k: round(v, 1) for k, v in mp_adjust.items()},
            "shensha_triggered": ss_triggered_this_year,
            "shensha_adjust": {k: round(v, 1) for k, v in ss_adjust.items()},
        })

    spirit_cum = cumulative_curve(spirit_yearly, lambdas["spirit"])
    wealth_cum = cumulative_curve(wealth_yearly, lambdas["wealth"])
    fame_cum = cumulative_curve(fame_yearly, lambdas["fame"])
    emotion_cum = cumulative_curve(emotion_yearly, lambdas.get("emotion", 0.88))
    for i, pt in enumerate(points):
        pt["spirit_cumulative"] = round(spirit_cum[i], 1)
        pt["wealth_cumulative"] = round(wealth_cum[i], 1)
        pt["fame_cumulative"] = round(fame_cum[i], 1)
        pt["emotion_cumulative"] = round(emotion_cum[i], 1)

    for pt in points:
        sigma = {}
        # v7.4 #5 · 驿马触发当年 → sigma × 1.3（波动幅度加大，反映"动 / 调岗 / 出行"）
        yima_volatility = 1.3 if "驿马" in pt.get("shensha_triggered", []) else 1.0
        for dim in ("spirit", "wealth", "fame"):
            base_sig = 5.0
            div_factor = pt["divergence"][dim] / 20.0
            inter_factor = 1.0 + 0.15 * len(pt["interactions"])
            sigma[dim] = round(base_sig * (1 + div_factor) * inter_factor * yima_volatility, 2)
        sigma["emotion"] = round(5.0 * (1.0 + 0.10 * len(pt["interactions"])) * yima_volatility, 2)
        pt["sigma"] = sigma

    dayun_segments = []
    for d in dayun:
        if d["end_age"] < age_start or d["start_age"] > age_end:
            continue
        seg_start = max(d["start_age"], age_start)
        seg_end = min(d["end_age"], age_end)
        dayun_segments.append({
            "label": d["gan"] + d["zhi"],
            "start_age": seg_start,
            "end_age": seg_end,
            "start_year": d["start_year"] + (seg_start - d["start_age"]),
            "end_year": d["start_year"] + (seg_end - d["start_age"]),
        })

    if forecast_from_year is None:
        forecast_from_year = max((p["year"] for p in points), default=bazi["birth_year"]) - forecast_window
    forecast = _detect_turning_points(points, forecast_from_year, forecast_window)

    disputes = _collect_disputes(points, dispute_threshold, base, weights)

    return {
        "version": 3,
        "weights": weights,
        "lambdas": lambdas,
        "age_start": age_start,
        "age_end": age_end,
        "forecast_from_year": forecast_from_year,
        "forecast_window": forecast_window,
        "dispute_threshold": dispute_threshold,
        "baseline": {k: round(v, 1) for k, v in base.items()},
        "pillars_str": bazi["pillars_str"],
        "day_master": bazi["day_master"],
        "strength": bazi["strength"],
        "yongshen": bazi["yongshen"],
        "geju": bazi.get("geju", {}),
        "phase": bazi.get("phase", {"id": "day_master_dominant", "label": "默认 · 日主主导", "is_inverted": False}),
        "shensha": bazi.get("shensha", {}),
        "birth_year": bazi["birth_year"],
        "gender": bazi["gender"],
        "orientation": bazi.get("orientation", "hetero"),
        "relationship_mode": relationship_mode,
        "qiyun_age": bazi.get("qiyun_age"),
        "dayun_segments": dayun_segments,
        "points": points,
        "turning_points_future": forecast,
        "disputes": disputes,
        "school_labels": SCHOOL_LABELS,
        "mangpai_enabled": bool(mangpai),
        "mangpai_static_markers": (mangpai or {}).get("static_markers", []),
        "mangpai_school_position": (mangpai or {}).get(
            "school_position",
            "mangpai disabled — pass --mangpai mangpai.json to enable"
        ),
        "structural_corrections_applied": sc_applied,
    }


def _collect_disputes(
    points: List[Dict], threshold: float, base: Dict[str, float], weights: Dict[str, float]
) -> List[Dict]:
    """收集所有派别争议年份的详情（供 LLM 分析使用）。

    每条 dispute 含：
        year/age/ganzhi/dayun
        dimension（争议维度）
        spread（极差）
        per_school（三派各自的 final 分数）
        leader/laggard（最高/最低派）
        interpretation_hints（程序化推断的争议方向，供 LLM 参考）
    """
    out = []
    for p in points:
        for dim in p["disputed_dimensions"]:
            ps = p["school_scores"][dim]
            sorted_schools = sorted(ps.items(), key=lambda x: x[1], reverse=True)
            leader, leader_v = sorted_schools[0]
            laggard, laggard_v = sorted_schools[-1]
            mid_school, mid_v = sorted_schools[1]
            hints = _dispute_hints(dim, leader, laggard, p)
            out.append({
                "year": p["year"],
                "age": p["age"],
                "ganzhi": p["ganzhi"],
                "dayun": p["dayun"],
                "dimension": dim,
                "spread": round(p["divergence"][dim], 1),
                "final_value": p[f"{dim}_yearly"],
                "per_school": ps,
                "leader_school": leader,
                "leader_value": leader_v,
                "laggard_school": laggard,
                "laggard_value": laggard_v,
                "mid_school": mid_school,
                "mid_value": mid_v,
                "interactions": p["interactions"],
                "interpretation_hints": hints,
            })
    out.sort(key=lambda x: (x["year"], x["dimension"]))
    return out


def _dispute_hints(dim: str, leader: str, laggard: str, point: Dict) -> List[str]:
    """程序化生成争议方向的提示（不下结论，供 LLM 推论的事实素材）。"""
    hints: List[str] = []
    pair = (leader, laggard)
    interactions_types = [i["type"] for i in point["interactions"]]

    if pair == ("fuyi", "geju") or pair == ("geju", "fuyi"):
        hints.append("扶抑派 ↔ 格局派 分歧：用神 / 忌神判定 与 原局格局规则给出反向信号；常见于格局成局但用神受冲、或用神到位但格局已破。")
    if pair == ("tiaohou", "fuyi") or pair == ("fuyi", "tiaohou"):
        hints.append("调候派 ↔ 扶抑派 分歧：寒暖燥湿调和的需求与扶抑日主的需求在该年指向不同五行。")
    if pair == ("tiaohou", "geju") or pair == ("geju", "tiaohou"):
        hints.append("调候派 ↔ 格局派 分歧：调候五行恰与原局格局的关键字相冲或相生过头。")

    if "伏吟" in interactions_types:
        hints.append("年内出现伏吟，传统派别对其吉凶判断历来不一（旧事重演 vs 内省深化），这是分歧主因之一。")
    if "反吟" in interactions_types:
        hints.append("年内出现反吟（天克地冲），格局派偏向「剧变多事」，扶抑派看用神是否被冲，调候派看是否调和。")
    if any("库被冲开" in t for t in interactions_types):
        hints.append("年内库被冲开，格局派看好（库开则发），但若开出忌神字，扶抑派会反对。")
    if "通关" in interactions_types:
        hints.append("年内出现通关元素，扶抑派与格局派同时看好，调候派若与所需季节方向冲突则不认同。")
    if "三合用神局" in interactions_types or "三合忌神局" in interactions_types:
        hints.append("年内有三合成局，方向极性强；分歧通常源于该局是否真正「会成」（三支须并见且不被刑冲破坏）。")

    if not hints:
        leader_label = SCHOOL_LABELS.get(leader, leader)
        laggard_label = SCHOOL_LABELS.get(laggard, laggard)
        hints.append(f"{leader_label} 偏正面、{laggard_label} 偏负面；分歧来自基础打分逻辑差异，无显著互动事件。")

    return hints


def _detect_turning_points(points: List[Dict], from_year: int, n_years: int) -> List[Dict]:
    out = []
    in_window = [p for p in points if from_year <= p["year"] <= from_year + n_years]
    for p in in_window:
        if not p["interactions"]:
            continue
        # 任一事件且变动幅度足够
        for inter in p["interactions"]:
            # 决定主要影响维度（启发式）
            if "财" in inter["type"] or "财库" in inter["type"]:
                dim = "wealth"
            elif "官" in inter["type"]:
                dim = "fame"
            elif inter["type"] in ("伏吟", "相穿", "反吟"):
                dim = "spirit"
            else:
                dim = "spirit"
            yearly = p[f"{dim}_yearly"]
            direction = "up" if yearly > 55 else ("down" if yearly < 45 else "flat")
            # 距今越远，置信度降级
            dist = p["year"] - from_year
            if dist <= 3:
                conf_cap = "high"
            elif dist <= 7:
                conf_cap = "mid"
            else:
                conf_cap = "low"
            conf = p["confidence"][dim]
            # 取较低者
            if (conf == "high" and conf_cap != "high") or (conf == "mid" and conf_cap == "low"):
                conf = conf_cap
            out.append({
                "year": p["year"],
                "age": p["age"],
                "ganzhi": p["ganzhi"],
                "dayun": p["dayun"],
                "trigger": inter["type"] + (f"·{inter.get('with','')}" if inter.get("with") else "")
                           + (f"·{inter.get('wuxing','')}" if inter.get("wuxing") else ""),
                "dimension": dim,
                "direction": direction,
                "magnitude": inter.get("magnitude", "中"),
                "confidence": conf,
                "yearly_value": yearly,
            })
    # 去重 + 按年份排序
    out.sort(key=lambda x: (x["year"], x["dimension"]))
    return out


def main():
    ap = argparse.ArgumentParser(description="Score curves from bazi.json → curves.json")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--out", default="curves.json", help="curves.json 输出路径")
    ap.add_argument("--age-start", type=int, default=0, help="评分起始年龄，默认 0")
    ap.add_argument("--age-end", type=int, default=60, help="评分结束年龄，默认 60")
    ap.add_argument("--age-cap", type=int, default=None,
                    help="（兼容旧参数）等价于 --age-end")
    ap.add_argument("--forecast-from-year", type=int, default=None,
                    help="拐点预测起始公历年份，None 时自动取 age_end 倒推 forecast-window 年")
    ap.add_argument("--forecast-window", type=int, default=10, help="拐点预测窗口（年），默认 10")
    ap.add_argument("--forecast-years", type=int, default=None,
                    help="（兼容旧参数）等价于 --forecast-window")
    ap.add_argument("--dispute-threshold", type=float, default=20.0,
                    help="三派极差超过此值即标记为派别争议年份，默认 20")
    ap.add_argument("--mangpai", default=None,
                    help="可选：mangpai.json 路径（mangpai_events.py 输出）；启用盲派烈度修正 + 事件附入 points")
    ap.add_argument("--strict", action="store_true", help="启用双盲自检")
    ap.add_argument("--confirmed-facts", default=None,
                    help="v7.2 · 可选：confirmed_facts.json 路径；若含 structural_corrections 则在打分前应用 "
                         "（支持 climate / strength / yongshen / geju / phase_override 5 种 kind）。"
                         "用 scripts/save_confirmed_facts.py 写入。")
    ap.add_argument("--override-phase", default=None,
                    help="v7 P1-7 相位反演 · 当 R0/R1 命中率 ≤ 2/6 时按反向假设重跑。"
                         "可选：day_master_dominant (默认) / "
                         "floating_dms_to_cong_cai / floating_dms_to_cong_sha / "
                         "floating_dms_to_cong_er / floating_dms_to_cong_yin / "
                         "dominating_god_cai_zuo_zhu / dominating_god_guan_zuo_zhu / "
                         "dominating_god_shishang_zuo_zhu / dominating_god_yin_zuo_zhu / "
                         "climate_inversion_dry_top / climate_inversion_wet_top / "
                         "true_following / pseudo_following。"
                         "详见 references/phase_inversion_protocol.md")
    args = ap.parse_args()

    age_end = args.age_end if args.age_cap is None else args.age_cap
    forecast_window = args.forecast_window if args.forecast_years is None else args.forecast_years

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    mangpai_data = None
    if args.mangpai:
        mangpai_data = json.loads(Path(args.mangpai).read_text(encoding="utf-8"))
    confirmed = None
    if args.confirmed_facts and Path(args.confirmed_facts).exists():
        confirmed = json.loads(Path(args.confirmed_facts).read_text(encoding="utf-8"))

    result = score(
        bazi,
        age_start=args.age_start,
        age_end=age_end,
        forecast_from_year=args.forecast_from_year,
        forecast_window=forecast_window,
        dispute_threshold=args.dispute_threshold,
        mangpai=mangpai_data,
        override_phase=args.override_phase,
        confirmed_facts=confirmed,
    )

    if args.strict:
        bazi2 = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
        result2 = score(
            bazi2,
            age_start=args.age_start,
            age_end=age_end,
            forecast_from_year=args.forecast_from_year,
            forecast_window=forecast_window,
            dispute_threshold=args.dispute_threshold,
            mangpai=mangpai_data,
            override_phase=args.override_phase,
            confirmed_facts=confirmed,
        )
        a = json.dumps(result, ensure_ascii=False, sort_keys=True)
        b = json.dumps(result2, ensure_ascii=False, sort_keys=True)
        if a != b:
            print("[score_curves] STRICT FAILED: double-blind mismatch", file=sys.stderr)
            sys.exit(2)
        print("[score_curves] strict double-blind: OK")

    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    mp_count = sum(len(p["mangpai_events"]) for p in result["points"]) if mangpai_data else 0
    sc_count = len(result.get("structural_corrections_applied", []))
    print(f"[score_curves] wrote {args.out}: ages {args.age_start}-{age_end}, "
          f"{len(result['points'])} years, "
          f"{len(result['turning_points_future'])} future turning points, "
          f"{len(result['disputes'])} disputed (year×dim) entries, "
          f"mangpai={'on' if mangpai_data else 'off'} ({mp_count} events embedded), "
          f"confirmed_facts={'on' if confirmed else 'off'} ({sc_count} structural corrections applied)")


if __name__ == "__main__":
    main()
