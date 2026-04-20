#!/usr/bin/env python3
"""he_pan.py — 八字「合盘」脚本（synastry / compatibility）。

输入：2+ 份 bazi.json（来自 solve_bazi.py）+ 关系类型
输出：he_pan.json，含每对人之间的多维度评分 + 命理依据 + 关键加 / 减分项

支持的关系类型：
  - cooperation 合作关系：财、官、印、比劫互动 + 大运同步度
  - marriage    婚配     ：日柱合 / 五行互补 / 夫妻宫 + 桃花 / 红鸾
  - friendship  友谊     ：比肩 / 食伤同道 + 用神互助
  - family      家人     ：印星 / 比劫 / 长辈宫互动（可选第 4 维度）

设计原则：
  1. **脚本只算结构性兼容（五行 / 干支 / 十神 / 大运）**，不打"夫妻好不好"这种价值标签
  2. 每条加 / 减分都标命理依据 + 可证伪点
  3. confidence 受双方 R1 命中率限制（短板效应，详见 he_pan_protocol.md）
  4. 公正性：不接受身份信息（姓名 / 关系状态等），仅看八字结构
  5. 输出供 LLM 在对话里写人话解读，不直接给"配 / 不配"结论

Usage:
  python he_pan.py \\
    --bazi person_a.json person_b.json \\
    --names A B \\
    --type marriage \\
    --focus-years 2026 2030 \\
    --out he_pan.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bazi_core import (
    GAN_WUXING,
    ZHI_WUXING,
    ZHI_HIDDEN_GAN,
    WUXING_ORDER,
    calc_shishen,
    calc_zhi_shishen,
)


# ---------- 静态对照表 ----------

# 天干五合
GAN_HE = {
    frozenset(["甲", "己"]): "甲己合化土（中正之合）",
    frozenset(["乙", "庚"]): "乙庚合化金（仁义之合）",
    frozenset(["丙", "辛"]): "丙辛合化水（威制之合）",
    frozenset(["丁", "壬"]): "丁壬合化木（仁寿之合）",
    frozenset(["戊", "癸"]): "戊癸合化火（无情之合）",
}

# 天干相冲（七冲）
GAN_CHONG = {
    frozenset(["甲", "庚"]), frozenset(["乙", "辛"]),
    frozenset(["丙", "壬"]), frozenset(["丁", "癸"]),
    frozenset(["戊", "甲"]), frozenset(["己", "乙"]),  # 戊甲、己乙是克非冲，但常并提
}

# 地支六合
ZHI_LIU_HE = {
    frozenset(["子", "丑"]): "子丑合化土",
    frozenset(["寅", "亥"]): "寅亥合化木",
    frozenset(["卯", "戌"]): "卯戌合化火",
    frozenset(["辰", "酉"]): "辰酉合化金",
    frozenset(["巳", "申"]): "巳申合化水",
    frozenset(["午", "未"]): "午未合化日月（土）",
}

# 地支三合（取半合也算）
SAN_HE_GROUPS = [
    (["申", "子", "辰"], "水"),
    (["亥", "卯", "未"], "木"),
    (["寅", "午", "戌"], "火"),
    (["巳", "酉", "丑"], "金"),
]

# 地支六冲
ZHI_CHONG = {
    frozenset(["子", "午"]): "子午冲（水火相激）",
    frozenset(["丑", "未"]): "丑未冲（土土相破）",
    frozenset(["寅", "申"]): "寅申冲（木金相战）",
    frozenset(["卯", "酉"]): "卯酉冲（木金相战）",
    frozenset(["辰", "戌"]): "辰戌冲（土土相破）",
    frozenset(["巳", "亥"]): "巳亥冲（火水相激）",
}

# 地支相害（六穿）
ZHI_HAI = {
    frozenset(["子", "未"]), frozenset(["丑", "午"]),
    frozenset(["寅", "巳"]), frozenset(["卯", "辰"]),
    frozenset(["申", "亥"]), frozenset(["酉", "戌"]),
}

# 地支相刑
ZHI_XING = {
    # 三刑
    frozenset(["寅", "巳", "申"]): "寅巳申三刑（恃势之刑）",
    frozenset(["丑", "戌", "未"]): "丑戌未三刑（无恩之刑）",
    # 自刑
    frozenset(["辰"]): "辰辰自刑",
    frozenset(["午"]): "午午自刑",
    frozenset(["酉"]): "酉酉自刑",
    frozenset(["亥"]): "亥亥自刑",
    # 互刑
    frozenset(["子", "卯"]): "子卯刑（无礼之刑）",
}

# 桃花（按日 / 年支查 → 流年支）
TAOHUA_BY_RIZHI = {
    "申": "酉", "子": "酉", "辰": "酉",  # 申子辰桃花在酉
    "亥": "子", "卯": "子", "未": "子",  # 亥卯未桃花在子
    "寅": "卯", "午": "卯", "戌": "卯",  # 寅午戌桃花在卯
    "巳": "午", "酉": "午", "丑": "午",  # 巳酉丑桃花在午
}

# 天乙贵人（日干 → 地支）
TIANYI_BY_RIGAN = {
    "甲": ["丑", "未"], "戊": ["丑", "未"], "庚": ["丑", "未"],
    "乙": ["子", "申"], "己": ["子", "申"],
    "丙": ["亥", "酉"], "丁": ["亥", "酉"],
    "壬": ["卯", "巳"], "癸": ["卯", "巳"],
    "辛": ["寅", "午"],
}

# 五行生克
WUXING_SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
WUXING_KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

# 关系维度对应的「重点十神」
DIM_SHISHEN_FOCUS = {
    "cooperation": {
        "name": "合作关系",
        "focus": ["正财", "偏财", "正官", "七杀", "正印", "偏印", "比肩", "劫财"],
        "desc": "看双方财、官、印、比劫互配 → 利益分配 / 决策权 / 信息差",
    },
    "marriage": {
        "name": "婚配",
        "focus": ["正官", "七杀", "正财", "偏财"],  # 男看财、女看官
        "desc": "看日柱合 / 夫妻宫（日支）/ 五行互补 / 配偶星位置",
    },
    "friendship": {
        "name": "友谊",
        "focus": ["比肩", "劫财", "食神", "伤官"],
        "desc": "看比劫食伤同道 + 用神互助 → 三观合 / 同道相吸",
    },
    "family": {
        "name": "家人",
        "focus": ["正印", "偏印", "比肩", "劫财", "正官"],
        "desc": "看印星 / 比劫互动 + 长辈宫（年柱）+ 子女宫（时柱）",
    },
}


# ---------- 工具函数 ----------

def _gans_of(bazi: dict) -> List[str]:
    return [p["gan"] for p in bazi["pillars"]]


def _zhis_of(bazi: dict) -> List[str]:
    return [p["zhi"] for p in bazi["pillars"]]


def _all_wx_of(bazi: dict) -> Dict[str, float]:
    """直接复用 solve_bazi 输出的 wuxing_distribution.score。"""
    return {wx: bazi["wuxing_distribution"][wx]["score"] for wx in WUXING_ORDER}


def _shishen_of(my_day_gan: str, other_gan: str) -> str:
    return calc_shishen(my_day_gan, other_gan)


# ---------- 五行互补（双向）----------

def score_wuxing_complement(a: dict, b: dict) -> Dict:
    """A 的用神是否在 B 八字里很旺；A 的忌神是否在 B 八字里很旺。双向计算。"""
    a_yong = a["yongshen"]["yongshen"]
    a_ji = a["yongshen"].get("jishen")
    b_yong = b["yongshen"]["yongshen"]
    b_ji = b["yongshen"].get("jishen")

    a_wx = _all_wx_of(a)
    b_wx = _all_wx_of(b)
    a_total = sum(a_wx.values()) or 1.0
    b_total = sum(b_wx.values()) or 1.0

    notes = []
    score = 0.0

    # A 用神在 B 旺
    if a_yong:
        ratio = b_wx.get(a_yong, 0) / b_total
        if ratio >= 0.18:
            pts = round(ratio * 30, 1)  # 最多 +9
            score += pts
            notes.append({
                "kind": "+", "value": pts,
                "text": f"A 的用神「{a_yong}」在 B 八字里占 {ratio:.0%}（旺）→ B 能给 A 补能量"
            })
        elif ratio < 0.05:
            score -= 3
            notes.append({
                "kind": "-", "value": -3,
                "text": f"A 的用神「{a_yong}」在 B 八字里几乎没有 → B 帮不上 A 的补益"
            })

    # B 用神在 A 旺
    if b_yong:
        ratio = a_wx.get(b_yong, 0) / a_total
        if ratio >= 0.18:
            pts = round(ratio * 30, 1)
            score += pts
            notes.append({
                "kind": "+", "value": pts,
                "text": f"B 的用神「{b_yong}」在 A 八字里占 {ratio:.0%}（旺）→ A 能给 B 补能量"
            })
        elif ratio < 0.05:
            score -= 3
            notes.append({
                "kind": "-", "value": -3,
                "text": f"B 的用神「{b_yong}」在 A 八字里几乎没有 → A 帮不上 B 的补益"
            })

    # 忌神反向（对方忌神在我这里旺 = 我会触发对方的雷）
    if a_ji:
        ratio = b_wx.get(a_ji, 0) / b_total
        if ratio >= 0.25:
            pts = round(ratio * 24, 1)  # 最多 -6
            score -= pts
            notes.append({
                "kind": "-", "value": -pts,
                "text": f"A 的忌神「{a_ji}」在 B 八字里占 {ratio:.0%} → B 容易触发 A 的不舒服点"
            })
    if b_ji:
        ratio = a_wx.get(b_ji, 0) / a_total
        if ratio >= 0.25:
            pts = round(ratio * 24, 1)
            score -= pts
            notes.append({
                "kind": "-", "value": -pts,
                "text": f"B 的忌神「{b_ji}」在 A 八字里占 {ratio:.0%} → A 容易触发 B 的不舒服点"
            })

    return {"layer": "五行互补", "score": round(score, 1), "notes": notes}


# ---------- 干支互动 ----------

def score_ganzhi_interactions(a: dict, b: dict) -> Dict:
    """枚举双方四柱之间的干合 / 干冲 / 支合 / 支冲 / 支害 / 三合半合 / 桃花 / 贵人。"""
    a_gans, a_zhis = _gans_of(a), _zhis_of(a)
    b_gans, b_zhis = _gans_of(b), _zhis_of(b)
    pillar_names = ["年柱", "月柱", "日柱", "时柱"]

    notes = []
    score = 0.0

    # 干合（按柱位重要度加权：日 > 月 > 时 > 年）
    pillar_weight = {0: 0.6, 1: 0.9, 2: 1.0, 3: 0.7}
    for i, ga in enumerate(a_gans):
        for j, gb in enumerate(b_gans):
            key = frozenset([ga, gb])
            w = (pillar_weight[i] + pillar_weight[j]) / 2
            if key in GAN_HE:
                pts = round(6 * w, 1)
                score += pts
                notes.append({
                    "kind": "+", "value": pts,
                    "text": f"A.{pillar_names[i]}{ga} + B.{pillar_names[j]}{gb}：{GAN_HE[key]} → 引力 / 化合"
                })
            elif key in GAN_CHONG:
                pts = round(4 * w, 1)
                score -= pts
                notes.append({
                    "kind": "-", "value": -pts,
                    "text": f"A.{pillar_names[i]}{ga} + B.{pillar_names[j]}{gb}：天干相冲 → 直接对冲"
                })

    # 支合 / 支冲 / 支害 / 半合
    for i, za in enumerate(a_zhis):
        for j, zb in enumerate(b_zhis):
            key = frozenset([za, zb])
            w = (pillar_weight[i] + pillar_weight[j]) / 2

            if za == zb:
                # 同支（伏吟）
                pts = round(2 * w, 1)
                if i == 2 and j == 2:
                    pts += 4
                score += 0  # 中性，记录但不打分
                notes.append({
                    "kind": "·", "value": 0,
                    "text": f"A.{pillar_names[i]}{za} = B.{pillar_names[j]}{zb}：同支（伏吟） → 旧事重演 / 同频共振"
                })
            elif key in ZHI_LIU_HE:
                pts = round(7 * w, 1)
                # 日支六合：婚配关键，额外加分
                if i == 2 and j == 2:
                    pts += 5
                score += pts
                notes.append({
                    "kind": "+", "value": pts,
                    "text": f"A.{pillar_names[i]}{za} + B.{pillar_names[j]}{zb}：{ZHI_LIU_HE[key]} → 缘分 / 互相吸引" +
                            ("（日支合 = 夫妻宫合，婚配关键）" if (i == 2 and j == 2) else "")
                })
            elif key in ZHI_CHONG:
                pts = round(6 * w, 1)
                if i == 2 and j == 2:
                    pts += 4  # 日支冲：婚配大忌
                score -= pts
                notes.append({
                    "kind": "-", "value": -pts,
                    "text": f"A.{pillar_names[i]}{za} + B.{pillar_names[j]}{zb}：{ZHI_CHONG[key]}" +
                            ("（日支冲 = 夫妻宫冲，婚配大忌）" if (i == 2 and j == 2) else "") +
                            " → 直接冲撞"
                })
            elif key in ZHI_HAI:
                pts = round(3 * w, 1)
                score -= pts
                notes.append({
                    "kind": "-", "value": -pts,
                    "text": f"A.{pillar_names[i]}{za} + B.{pillar_names[j]}{zb}：相害（穿） → 暗里相磨"
                })

    # 三合 / 半合（取双方任意 2 支拼成三合局的两支视为半合）
    for group, hua_wx in SAN_HE_GROUPS:
        for sa in a_zhis:
            for sb in b_zhis:
                if sa in group and sb in group and sa != sb:
                    pts = 4.0
                    score += pts
                    notes.append({
                        "kind": "+", "value": pts,
                        "text": f"A有{sa} + B有{sb} → 半合化{hua_wx}（三合局缺 1 支） → 需要某流年第三支拱起来"
                    })

    # 桃花互见（A 日支查桃花 → B 八字是否有这个支；反之亦然）
    a_rizhi = a_zhis[2]
    b_rizhi = b_zhis[2]
    a_taohua = TAOHUA_BY_RIZHI.get(a_rizhi)
    b_taohua = TAOHUA_BY_RIZHI.get(b_rizhi)
    if a_taohua and a_taohua in b_zhis:
        score += 4
        notes.append({
            "kind": "+", "value": 4,
            "text": f"A 桃花在「{a_taohua}」，B 八字含此支 → 异性吸引 / 风流缘"
        })
    if b_taohua and b_taohua in a_zhis:
        score += 4
        notes.append({
            "kind": "+", "value": 4,
            "text": f"B 桃花在「{b_taohua}」，A 八字含此支 → 异性吸引 / 风流缘"
        })

    # 天乙贵人互见（A 日干查贵人 → B 八字含此支 → A 在 B 那里有贵人意）
    a_tianyi = TIANYI_BY_RIGAN.get(a["day_master"], [])
    b_tianyi = TIANYI_BY_RIGAN.get(b["day_master"], [])
    a_meet = [z for z in a_tianyi if z in b_zhis]
    b_meet = [z for z in b_tianyi if z in a_zhis]
    if a_meet:
        score += 5
        notes.append({
            "kind": "+", "value": 5,
            "text": f"A 的天乙贵人「{','.join(a_meet)}」出现在 B 的八字里 → B 对 A 是关键贵人"
        })
    if b_meet:
        score += 5
        notes.append({
            "kind": "+", "value": 5,
            "text": f"B 的天乙贵人「{','.join(b_meet)}」出现在 A 的八字里 → A 对 B 是关键贵人"
        })

    return {"layer": "干支互动", "score": round(score, 1), "notes": notes}


# ---------- 十神互配（按关系类型 focus） ----------

def score_shishen_match(a: dict, b: dict, rel_type: str) -> Dict:
    """看 A 把 B 的天干视作什么十神（B 在 A 的命局里扮演什么角色），双向。
    按关系类型 DIM_SHISHEN_FOCUS 给加 / 减分。
    """
    cfg = DIM_SHISHEN_FOCUS[rel_type]
    focus = set(cfg["focus"])

    notes = []
    score = 0.0

    a_dm = a["day_master"]
    b_dm = b["day_master"]
    a_gender = a["gender"]
    b_gender = b["gender"]

    # B 的日干在 A 命局里是什么十神 = B 对 A 是什么角色
    role_b_in_a = _shishen_of(a_dm, b_dm)
    role_a_in_b = _shishen_of(b_dm, a_dm)

    notes.append({
        "kind": "·", "value": 0,
        "text": f"B 的日干{b_dm}在 A 看来 = {role_b_in_a}；A 的日干{a_dm}在 B 看来 = {role_a_in_b}"
    })

    # 婚配特别：男看正财 / 偏财 = 妻；女看正官 / 七杀 = 夫
    if rel_type == "marriage":
        # 男 A
        if a_gender == "M":
            if role_b_in_a in ("正财", "偏财"):
                pts = 12 if role_b_in_a == "正财" else 8
                score += pts
                notes.append({
                    "kind": "+", "value": pts,
                    "text": f"男 A 看 B 为「{role_b_in_a}」= 妻星正配 → 婚配主轴成立"
                })
            elif role_b_in_a in ("正官", "七杀"):
                score -= 6
                notes.append({
                    "kind": "-", "value": -6,
                    "text": f"男 A 看 B 为「{role_b_in_a}」（官杀）= 反向受压 → 易「妻管严」/ 关系倒置"
                })
        # 女 A
        elif a_gender == "F":
            if role_b_in_a in ("正官", "七杀"):
                pts = 12 if role_b_in_a == "正官" else 8
                score += pts
                notes.append({
                    "kind": "+", "value": pts,
                    "text": f"女 A 看 B 为「{role_b_in_a}」= 夫星正配 → 婚配主轴成立"
                })
            elif role_b_in_a in ("正财", "偏财"):
                score -= 6
                notes.append({
                    "kind": "-", "value": -6,
                    "text": f"女 A 看 B 为「{role_b_in_a}」（财星）= 反向 → 多见「姐弟恋 / 反传统」，需双方都接受"
                })

        # 同样对 A 在 B 看来
        if b_gender == "M":
            if role_a_in_b in ("正财", "偏财"):
                pts = 12 if role_a_in_b == "正财" else 8
                score += pts
                notes.append({
                    "kind": "+", "value": pts,
                    "text": f"男 B 看 A 为「{role_a_in_b}」= 妻星正配 → 双向妻星"
                })
        elif b_gender == "F":
            if role_a_in_b in ("正官", "七杀"):
                pts = 12 if role_a_in_b == "正官" else 8
                score += pts
                notes.append({
                    "kind": "+", "value": pts,
                    "text": f"女 B 看 A 为「{role_a_in_b}」= 夫星正配 → 双向夫星"
                })

    elif rel_type == "cooperation":
        # 财官印比合作配伍
        if role_b_in_a in ("正财", "偏财"):
            score += 6
            notes.append({"kind": "+", "value": 6,
                "text": f"B 在 A 看来是「{role_b_in_a}」→ B 是 A 的财源 / 资源端"})
        if role_a_in_b in ("正财", "偏财"):
            score += 6
            notes.append({"kind": "+", "value": 6,
                "text": f"A 在 B 看来是「{role_a_in_b}」→ A 是 B 的财源 / 资源端"})
        if role_b_in_a in ("正官", "七杀") and role_a_in_b in ("正印", "偏印"):
            score += 8
            notes.append({"kind": "+", "value": 8,
                "text": "B = A 的官杀 + A = B 的印 → 对方给压力 + 我给认可，是经典「上下级 / 师徒」合作配"})
        elif role_a_in_b in ("正官", "七杀") and role_b_in_a in ("正印", "偏印"):
            score += 8
            notes.append({"kind": "+", "value": 8,
                "text": "A = B 的官杀 + B = A 的印 → 反向上下级合作配"})
        if role_b_in_a in ("比肩", "劫财") and role_a_in_b in ("比肩", "劫财"):
            score += 4
            notes.append({"kind": "·", "value": 4,
                "text": "互为比劫 → 同侪 / 平行合伙；中性偏正，但要警惕利益分配（比肩夺财）"})

    elif rel_type == "friendship":
        if role_b_in_a in ("比肩", "劫财") and role_a_in_b in ("比肩", "劫财"):
            score += 10
            notes.append({"kind": "+", "value": 10,
                "text": "互为比劫 → 同道 / 知己；最易长期友谊"})
        if role_b_in_a in ("食神", "伤官") or role_a_in_b in ("食神", "伤官"):
            score += 5
            notes.append({"kind": "+", "value": 5,
                "text": "一方为另一方食伤 → 创造力 / 玩耍力被激活，是「一起搞事」型友谊"})
        if role_b_in_a in ("七杀",) or role_a_in_b in ("七杀",):
            score -= 4
            notes.append({"kind": "-", "value": -4,
                "text": "出现七杀 → 友谊里有压制 / 较劲成分，需双方都不太敏感才能长久"})

    elif rel_type == "family":
        if role_b_in_a in ("正印", "偏印"):
            score += 8
            notes.append({"kind": "+", "value": 8,
                "text": f"B 在 A 看来 = 印星 → B 给 A 庇护 / 教养感（典型长辈 / 母性角色）"})
        if role_a_in_b in ("正印", "偏印"):
            score += 8
            notes.append({"kind": "+", "value": 8,
                "text": f"A 在 B 看来 = 印星 → A 给 B 庇护 / 教养感"})
        if role_b_in_a in ("比肩", "劫财") and role_a_in_b in ("比肩", "劫财"):
            score += 6
            notes.append({"kind": "+", "value": 6,
                "text": "互为比劫 → 兄弟姐妹 / 同辈家人，平行扶持"})
        if role_b_in_a in ("七杀",) and role_a_in_b in ("正印", "偏印"):
            score += 6
            notes.append({"kind": "+", "value": 6,
                "text": "B 对 A 是七杀 + A 对 B 是印 → 杀印相生（严父慈子的典型结构）"})

    return {"layer": f"十神互配（{cfg['name']}）", "score": round(score, 1), "notes": notes,
            "role_b_in_a": role_b_in_a, "role_a_in_b": role_a_in_b}


# ---------- 大运同步 ----------

def score_dayun_sync(a: dict, b: dict, focus_years: List[int]) -> Dict:
    """在 focus_years 区间，看双方所走大运的用神是否同步（同时旺 / 同时衰）。

    简化方案：取每年双方大运干 vs 各自用神的关系
      - 大运干属用神 / 生用神 → +1
      - 大运干属忌神 / 克用神 → -1
    然后双方同号年数 / 总年数 = 同步度。
    """
    if not focus_years:
        return {"layer": "大运同步", "score": 0.0, "notes": [], "sync_ratio": None}

    a_yong = a["yongshen"]["yongshen"]
    b_yong = b["yongshen"]["yongshen"]
    a_dayun = a["dayun"]
    b_dayun = b["dayun"]

    def dayun_polarity(year: int, dayuns: List[dict], yong: str) -> int:
        for d in dayuns:
            if d["start_year"] <= year < d["start_year"] + 10:
                gan_wx = GAN_WUXING[d["gan"]]
                if gan_wx == yong or WUXING_SHENG.get(gan_wx) == yong:
                    return 1
                if gan_wx == WUXING_KE.get(yong) or yong == WUXING_KE.get(gan_wx):
                    return -1
                return 0
        return 0

    same = 0
    diff = 0
    detail = []
    for y in focus_years:
        pa = dayun_polarity(y, a_dayun, a_yong)
        pb = dayun_polarity(y, b_dayun, b_yong)
        if pa != 0 and pb != 0:
            if pa == pb:
                same += 1
            else:
                diff += 1
        detail.append({"year": y, "a_polarity": pa, "b_polarity": pb})

    total = same + diff
    ratio = same / total if total else 0.5
    pts = round((ratio - 0.5) * 20, 1)  # ratio=1 → +10；ratio=0 → -10

    notes = [{
        "kind": "+" if pts > 0 else ("-" if pts < 0 else "·"),
        "value": pts,
        "text": (
            f"focus_years 中 {same} 年双方大运同向（同旺/同衰）、{diff} 年反向 → 同步度 {ratio:.0%}"
        ),
    }]
    return {"layer": "大运同步", "score": pts, "notes": notes,
            "sync_ratio": round(ratio, 2), "detail": detail}


# ---------- 评分汇总 ----------

def total_grade(score: float) -> Dict:
    """把汇总分映射成等级（仅供 LLM 解读时定调；用户面前不要直接打这个等级）。"""
    if score >= 50:
        return {"grade": "A", "label": "结构性高度匹配", "color": "green"}
    if score >= 25:
        return {"grade": "B", "label": "总体匹配，有亮点也有要注意的点", "color": "lightgreen"}
    if score >= 5:
        return {"grade": "C", "label": "中性 / 平淡，看双方主观经营", "color": "gray"}
    if score >= -15:
        return {"grade": "D", "label": "偏摩擦 / 需双方刻意磨合", "color": "orange"}
    return {"grade": "E", "label": "结构性高摩擦，长期相处会很累", "color": "red"}


def build_pair(a: dict, b: dict, name_a: str, name_b: str,
               rel_type: str, focus_years: List[int]) -> Dict:
    layers = []
    layers.append(score_wuxing_complement(a, b))
    layers.append(score_ganzhi_interactions(a, b))
    layers.append(score_shishen_match(a, b, rel_type))
    layers.append(score_dayun_sync(a, b, focus_years))

    total = round(sum(L["score"] for L in layers), 1)

    # 把所有 + / - notes 按绝对值排序作为"关键命理依据"
    all_notes = []
    for L in layers:
        for n in L["notes"]:
            all_notes.append({"layer": L["layer"], **n})
    plus_notes = sorted([n for n in all_notes if n["value"] > 0], key=lambda x: -x["value"])[:6]
    minus_notes = sorted([n for n in all_notes if n["value"] < 0], key=lambda x: x["value"])[:5]

    return {
        "pair": f"{name_a} ↔ {name_b}",
        "name_a": name_a, "name_b": name_b,
        "rel_type": rel_type,
        "rel_name": DIM_SHISHEN_FOCUS[rel_type]["name"],
        "rel_desc": DIM_SHISHEN_FOCUS[rel_type]["desc"],
        "pillars_a": a["pillars_str"],
        "pillars_b": b["pillars_str"],
        "day_master_a": a["day_master"],
        "day_master_b": b["day_master"],
        "yongshen_a": a["yongshen"]["yongshen"],
        "yongshen_b": b["yongshen"]["yongshen"],
        "total_score": total,
        "grade": total_grade(total),
        "layers": layers,
        "top_pluses": plus_notes,
        "top_minuses": minus_notes,
        "focus_years": focus_years,
    }


def build(bazis: List[dict], names: List[str], rel_type: str,
          focus_years: List[int]) -> Dict:
    n = len(bazis)
    if n < 2:
        raise ValueError("合盘至少需要 2 份八字")

    pairs = []
    for (i, j) in itertools.combinations(range(n), 2):
        pairs.append(build_pair(bazis[i], bazis[j], names[i], names[j],
                                rel_type, focus_years))

    return {
        "version": 1,
        "rel_type": rel_type,
        "rel_name": DIM_SHISHEN_FOCUS[rel_type]["name"],
        "rel_desc": DIM_SHISHEN_FOCUS[rel_type]["desc"],
        "n_persons": n,
        "names": names,
        "pillars": [b["pillars_str"] for b in bazis],
        "day_masters": [b["day_master"] for b in bazis],
        "yongshens": [b["yongshen"]["yongshen"] for b in bazis],
        "focus_years": focus_years,
        "pairs": pairs,
        "instruction_for_llm": LLM_INSTRUCTION,
    }


LLM_INSTRUCTION = """\
== 合盘解读规则（强制） ==

1. **不要直接给"配 / 不配"结论**——只解释结构性匹配项 + 给双方"如何用"的建议
2. 必须按层（五行 / 干支 / 十神 / 大运）逐层解读，每层引用 notes 里的具体项
3. 必须先告知 confidence 上限：
   - 双方都通过了 R1 健康三问（≥ 2/3 命中）→ 解读可以重一些
   - 任一方 R1 < 2/3 → 必须加 caveat："另一方八字校验不足，结论作为方向参考"
4. 关键加分项（top_pluses）：要写"为什么这个有意义" + "实际怎么用上"
5. 关键减分项（top_minuses）：要写"摩擦点是什么" + "可以怎么规避或缓冲"
6. focus_years 给的同步度：要落到具体建议（如"未来 5 年共有 4 年大运同向 → 适合一起搞大事")
7. 关系类型敏感性：
   - 婚配：日柱合 / 日支冲是关键，必须明确指出
   - 合作：财官印配是关键 + 警惕比劫夺财
   - 友谊：比劫食伤同道 = 长久；七杀过多 = 易争胜
   - 家人：印 / 比为主，看代际庇护和同辈互助

== 禁止 ==
- ❌ 不援引脚本的具体 notes，凭"感觉"打分
- ❌ 把 grade 直接报给用户（"你们是 D 级"——很伤人，应转化为人话）
- ❌ 跳过双方 R1 校验直接合盘
- ❌ 把所有节点憋在末尾一次性吐（v5 流式硬要求）

== 输出格式 + 流式分节顺序（v5 强制）==
合盘默认走 markdown-only（无 HTML），LLM **不要先问"要不要图"**——除非用户明确说"也给我个汇总表 / 想看 HTML"。
按下面的节序**流式输出**（每写完一节立刻发出，禁止憋整段）：

  ## 概览                       ← Node 1：N 人 / 关系类型 / confidence（基于双方 R1）
  ## 总分定调                   ← Node 2：人话定调，不甩 grade
  ## 第 1 层 · 五行互补          ← Node 3
  ## 第 2 层 · 干支互动          ← Node 4
  ## 第 3 层 · 十神互配          ← Node 5
  ## 第 4 层 · 大运同步          ← Node 6
  ## 关键加分项 · 怎么用         ← Node 7（援引 top_pluses）
  ## 关键减分项 · 怎么避         ← Node 8（援引 top_minuses）
  ## 关系类型 tips              ← Node 9（按 rel_type 给特定建议）
  ## 总结                       ← Node 10：「如果决定做 X，怎样能更顺」
"""


# ---------- 命令行 ----------

def main():
    ap = argparse.ArgumentParser(description="八字合盘评分器（synastry）")
    ap.add_argument("--bazi", nargs="+", required=True,
                    help="2+ 份 bazi.json 路径")
    ap.add_argument("--names", nargs="+", default=None,
                    help="对应的称谓（默认 P1/P2/...）。仅用于显示，不进打分。")
    ap.add_argument("--type", required=True,
                    choices=list(DIM_SHISHEN_FOCUS.keys()),
                    help="关系类型：cooperation / marriage / friendship / family")
    ap.add_argument("--focus-years", type=int, nargs="*", default=None,
                    help="关注的公历年份列表（用于大运同步度），默认 今年-今年+10")
    ap.add_argument("--out", default="he_pan.json", help="输出路径")
    args = ap.parse_args()

    bazis = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.bazi]
    names = args.names if args.names else [f"P{i+1}" for i in range(len(bazis))]
    if len(names) != len(bazis):
        print("ERROR: --names 数量与 --bazi 不一致", file=sys.stderr)
        sys.exit(2)

    # v9 PR-2: 入口守卫 — 任何 bazi.is_provisional=True 或后验 < 0.60 拒合盘
    import os as _os
    _strict = _os.environ.get("BAZI_HEPAN_BYPASS_V8_GATE") != "1"
    if _strict:
        gate_errors: list = []
        for path, b, n in zip(args.bazi, bazis, names):
            phase = b.get("phase") or {}
            if phase.get("is_provisional"):
                gate_errors.append(
                    f"  · {n} ({path}): phase.is_provisional=True, "
                    f"必须先跑 phase_posterior.py 完成 v8 disambiguation."
                )
            conf = phase.get("confidence", 1.0)
            if conf < 0.60:
                gate_errors.append(
                    f"  · {n} ({path}): phase.confidence={conf:.2f} < 0.60, "
                    f"个体相位置信度不足,合盘会放大不确定。"
                )
        if gate_errors:
            print("\n[he_pan v9 GATE] 拒绝合盘 — 任一参与者 v8 phase 未确认或低置信:",
                  file=sys.stderr)
            for e in gate_errors:
                print(e, file=sys.stderr)
            print("\n建议:", file=sys.stderr)
            print("  1. 各自先跑 handshake.py 与 phase_posterior.py 完成 v8 二轮校验;",
                  file=sys.stderr)
            print("  2. 或在确认低置信可接受的前提下设 BAZI_HEPAN_BYPASS_V8_GATE=1 强行过.",
                  file=sys.stderr)
            sys.exit(3)

    if args.focus_years:
        focus = sorted(set(args.focus_years))
    else:
        cy = dt.date.today().year
        focus = list(range(cy, cy + 11))

    result = build(bazis, names, args.type, focus)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"[he_pan] wrote {args.out}: {len(bazis)} 人 · {result['rel_name']} · "
          f"{len(result['pairs'])} 对配对")
    for p in result["pairs"]:
        g = p["grade"]
        print(f"  {p['pair']}: total={p['total_score']:+.1f} 分 ({g['grade']} · {g['label']})")


if __name__ == "__main__":
    main()
