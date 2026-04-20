#!/usr/bin/env python3
"""family_profile.py — 原生家庭结构画像（v7.3 新增 · 仅输出结构标签，不打分、不画曲线）

为什么需要这个脚本：
    skill 之前没有"原生家庭"维度，LLM 被问到"我爸妈怎么样"时只能裸跑古法 +
    训练语料的 prior 自由发挥。古典命书因为 survivorship bias，几乎所有命例
    都对应"出身名门"，所以 LLM 默认会把父亲推成"大家长 / 名利双收"，把母亲
    推成"贤惠 / 高知"——和现代普通家庭的真实情况严重错位。

设计原则（重要 · 不要破坏）：
    1. **只输出结构性标签 + evidence + falsifiability**，不输出数值（避免被
       LLM 当作"显赫程度的客观分数"）
    2. 输出 5 档结构分类（显赫候选 / 中产候选 / 普通 / 波折 / 缺位）的"候选"
       含义是「**如果命局对了**，应呈现 X 模式」——必须经 R3 反询问校验后
       LLM 才能展开
    3. 父星 = 偏财（古法）；母星 = 正印（古法）—— 注意：这里**只是命局符号**，
       不预设"父母社会地位"。命局可推的是"父母在你能量场里的存在模式"，
       不可推的是"父母收入 / 职业 / 学历"
    4. 不接受任何身份信息输入（公正性要求）
    5. 输出供 handshake.py 的 R3 反询问·原生家庭画像（2 题）使用

**与 fairness_protocol.md §11 配套**：
    LLM 在 family 段写作时必须援引本脚本输出的 family_class + father_mode +
    mother_mode 标签 + R3 命中情况。禁止裸推"父亲名利双收 / 名门望族"。

Usage:
    python family_profile.py --bazi bazi.json --out family_profile.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bazi_core import (
    GAN_WUXING,
    ZHI_WUXING,
    ZHI_HIDDEN_GAN,
    ZHI_CHONG,
    ZHI_LIUHE,
    SANHE_GROUPS,
    WUXING_KE,
    calc_shishen,
)


# ---------- 父母星映射（古法符号，不预设社会地位） ----------

FATHER_SHISHEN = "偏财"   # 我克同性 = 父
MOTHER_SHISHEN = "正印"   # 生我异性 = 母
ALT_FATHER_SHISHEN = "正财"  # 备用：正财在父星缺位时也算"父辈财"
ALT_MOTHER_SHISHEN = "偏印"  # 备用：偏印也算"母辈印"

# 年/月柱的"显赫候选"指标 —— 财官印俱全 / 透官 + 印 / 偏财通根月支不被劫
WEALTHY_PROXY_SHISHEN = {"正财", "偏财", "正官", "七杀", "正印", "偏印"}

# 五档结构分类
FAMILY_CLASS_LABEL = {
    "illustrious_candidate": "显赫候选",
    "stable_candidate":      "中产候选",
    "ordinary":              "普通候选",
    "turbulent_candidate":   "波折候选",
    "absent_candidate":      "缺位候选",
}


# ---------- 辅助：定位某十神在原局的所有出现位置 ----------

def _locate_shishen(bazi: dict, target_shishen: str) -> List[dict]:
    """返回原局中所有出现 target_shishen 的位置。

    位置含 (柱位, 天干/地支, 透/藏, 五行)。
    """
    day_gan = bazi["day_master"]
    pillars = bazi["pillars"]
    pillar_info = bazi["pillar_info"]
    out: List[dict] = []
    pillar_names = ["年柱", "月柱", "日柱", "时柱"]
    for i, p in enumerate(pillars):
        # 天干
        if i != 2 and pillar_info[i].get("gan_shishen") == target_shishen:
            out.append({
                "pillar_idx": i,
                "pillar_name": pillar_names[i],
                "where": "干",
                "char": p["gan"],
                "wuxing": GAN_WUXING[p["gan"]],
                "is_root_zhi": False,
            })
        # 地支主气十神
        if pillar_info[i].get("zhi_shishen") == target_shishen:
            out.append({
                "pillar_idx": i,
                "pillar_name": pillar_names[i],
                "where": "支主气",
                "char": p["zhi"],
                "wuxing": ZHI_WUXING[p["zhi"]],
                "is_root_zhi": True,
            })
        # 地支次/余气藏干
        hidden = ZHI_HIDDEN_GAN.get(p["zhi"], [])
        for hg in hidden[1:]:  # 跳过主气（已在上面统计）
            if calc_shishen(day_gan, hg) == target_shishen:
                out.append({
                    "pillar_idx": i,
                    "pillar_name": pillar_names[i],
                    "where": "支藏",
                    "char": hg,
                    "wuxing": GAN_WUXING[hg],
                    "is_root_zhi": False,
                })
    return out


def _is_zhi_chong(zhi_a: str, zhi_b: str) -> bool:
    return ZHI_CHONG.get(zhi_a) == zhi_b


def _is_zhi_liuhe(zhi_a: str, zhi_b: str) -> bool:
    return ZHI_LIUHE.get(zhi_a) == zhi_b


def _has_sanhe_with(zhi: str, others: List[str]) -> bool:
    """zhi 是否与 others 中的任意 ≥1 个支构成三合 / 半合。"""
    for group, _wx in SANHE_GROUPS:
        if zhi in group and any(o in group and o != zhi for o in others):
            return True
    return False


def _zhi_pillar_relations(bazi: dict, target_pillar_idx: int) -> Dict[str, List[str]]:
    """target_pillar 的地支与其他柱的关系。

    返回：{"chong": [...], "liuhe": [...], "sanhe": [...]}（每个值是与之有关系的柱名列表）
    """
    pillars = bazi["pillars"]
    pillar_names = ["年柱", "月柱", "日柱", "时柱"]
    target_zhi = pillars[target_pillar_idx]["zhi"]
    others = [
        (i, p["zhi"]) for i, p in enumerate(pillars) if i != target_pillar_idx
    ]
    chong, liuhe, sanhe = [], [], []
    for i, z in others:
        if _is_zhi_chong(target_zhi, z):
            chong.append(pillar_names[i])
        if _is_zhi_liuhe(target_zhi, z):
            liuhe.append(pillar_names[i])
    other_zhis = [z for _, z in others]
    if _has_sanhe_with(target_zhi, other_zhis):
        sanhe.append("与他柱构成三合/半合")
    return {"chong": chong, "liuhe": liuhe, "sanhe": sanhe}


def _is_ku_zhi(zhi: str) -> bool:
    return zhi in {"辰", "戌", "丑", "未"}


# ---------- 父亲存在模式 ----------

# v7.3 · 父亲存在模式 —— 5 档（基于偏财 / 正财位置 + 年/月柱七杀 + 印是否化解）
FATHER_MODE_DESC = {
    "near_supportive": (
        "父亲在你早年成长中存在感偏强、偏支持型 ——"
        "可能是你和父亲关系紧密、父亲在你重大决定中起过实质性作用，"
        "或者你父亲 / 父系长辈是你早年最重要的资源 / 教养来源"
    ),
    "near_high_pressure": (
        "父亲在你早年成长中存在感偏强、但更偏「主导 / 高压 / 严」——"
        "可能是父亲对你期待 / 控制 / 压力比较明显，"
        "或者你跟父亲的关系更像「服从 / 顶撞 / 敬畏」而不是「亲近 / 撒娇」"
    ),
    "mid_distant": (
        "父亲在你能量场里偏中等距离 —— 不是缺位，但也不是早年最贴身的人，"
        "更像「在背景里、知道父亲存在、但不介入你大多数决定」的模式"
    ),
    "far_or_intermittent": (
        "父亲在你早年成长中存在感偏弱、偏远、或断续 ——"
        "可能形式是：父亲早年长期不在身边（外地工作 / 出差多）、"
        "父子关系疏远、父亲早期身体或事业波动让他无暇顾及，"
        "或父亲虽在但你和他没什么深层连接"
    ),
    "absent": (
        "父亲在你早年成长中存在感非常弱 / 缺位 ——"
        "可能形式是：父亲早离 / 早逝、父母离异且你跟母亲、"
        "父亲长期在外几乎不参与你成长，或父亲虽在但情感缺位严重；"
        "（命局只能识别「父辈位空」这个结构，不区分具体原因）"
    ),
}


def compute_father_profile(bazi: dict) -> dict:
    """父亲存在模式：基于偏财位置 + 强度 + 年柱七杀 + 印是否化解。

    返回：{mode, distance, pressure_level, evidence, claim, falsifiability}
    """
    locations = _locate_shishen(bazi, FATHER_SHISHEN)
    if not locations:
        # 偏财全无 → 看正财兜底
        locations = _locate_shishen(bazi, ALT_FATHER_SHISHEN)
        used_alt = True
    else:
        used_alt = False

    wx_dist = bazi.get("wuxing_distribution", {})
    day_master_wx = bazi["day_master_wuxing"]
    father_wx = WUXING_KE[day_master_wx]
    father_score = wx_dist.get(father_wx, {}).get("score", 0)
    father_ratio = wx_dist.get(father_wx, {}).get("ratio", 0)
    is_father_missing = wx_dist.get(father_wx, {}).get("missing", False)

    nian_qi_sha = _nian_qi_sha_check(bazi)

    if not locations:
        mode = "absent"
        distance = "absent"
        pressure_level = "n/a"
        evidence = (
            f"原局完全不见{FATHER_SHISHEN} / {ALT_FATHER_SHISHEN}（父星五行={father_wx} 缺失）"
        )
    else:
        nian_loc = next((l for l in locations if l["pillar_idx"] == 0), None)
        yue_loc = next((l for l in locations if l["pillar_idx"] == 1), None)
        ri_loc = next((l for l in locations if l["pillar_idx"] == 2), None)
        primary = nian_loc or yue_loc or ri_loc or locations[0]

        if nian_loc or yue_loc:
            distance = "near"
        elif ri_loc:
            distance = "mid"
        else:
            distance = "far"

        if nian_qi_sha["triggered"] and not nian_qi_sha["yin_resolved"]:
            pressure_level = "high"
            mode = "near_high_pressure" if distance == "near" else "mid_distant"
        elif nian_qi_sha["triggered"] and nian_qi_sha["yin_resolved"]:
            pressure_level = "mid"
            mode = "near_supportive" if distance == "near" else "mid_distant"
        elif distance == "near" and father_score >= 3:
            pressure_level = "low"
            mode = "near_supportive"
        elif distance == "near" and father_score < 1.5:
            pressure_level = "low"
            mode = "far_or_intermittent"
        elif distance == "mid":
            pressure_level = "low"
            mode = "mid_distant"
        else:
            pressure_level = "low"
            mode = "far_or_intermittent"

        if is_father_missing or father_ratio < 0.05:
            mode = "absent"
            distance = "absent"

        positions_str = ", ".join(
            f"{l['pillar_name']}/{l['where']}/{l['char']}" for l in locations
        )
        sha_part = "无"
        if nian_qi_sha["triggered"]:
            sha_part = "有 → " + ("印化解" if nian_qi_sha["yin_resolved"] else "无印化解")
        evidence = (
            f"父星=偏财（{father_wx}）"
            + ("（偏财缺，用正财兜底）" if used_alt else "")
            + f" · 出现位置=[{positions_str}]"
            + f" · 父星五行总分={father_score:.1f}（占比 {father_ratio:.0%}）"
            + f" · 年柱七杀={sha_part}"
        )

    claim = FATHER_MODE_DESC[mode]
    falsifiability = (
        "如果你回想跟父亲的实际相处模式跟上面描述明显反向 →（比如这条说"
        "「偏远 / 缺位」但你跟父亲其实非常贴近、或这条说「高压 / 主导」"
        "但你父亲其实非常温和放手）→ 父星读法可能反了，常见原因是"
        "时辰错导致月柱十神跳位，或日主性别误判。"
        "**注意**：本条只判读"
        "「父亲在你能量场里的存在模式」，**不判读**父亲的社会地位 / 职业 / 收入 / 学历，"
        "也**不判读**父亲是否健在、是否离异——这些命局推不出。"
    )

    return {
        "mode": mode,
        "mode_label": {
            "near_supportive": "贴近 · 支持型",
            "near_high_pressure": "贴近 · 高压型",
            "mid_distant": "中等距离 · 平淡",
            "far_or_intermittent": "偏远 / 断续",
            "absent": "缺位",
        }[mode],
        "distance": distance,
        "pressure_level": pressure_level,
        "evidence": evidence,
        "claim": claim,
        "falsifiability": falsifiability,
        "used_alt_star": used_alt,
    }


# ---------- 母亲存在模式 ----------

MOTHER_MODE_DESC = {
    "near_nurturing": (
        "母亲在你早年成长中存在感强、偏照护 / 教养型 ——"
        "可能是母亲是你早年最主要的照顾者、对你日常学习生活介入多，"
        "或者你跟母亲的关系密度明显高于跟父亲"
    ),
    "near_smothering": (
        "母亲在你早年成长中存在感强、但偏过度照护 / 控制 ——"
        "可能形式是：母亲过度保护 / 难以放手 / 把你早年生活安排得很满，"
        "你的独立性可能被压一些（这是结构性描述，不是价值判断）"
    ),
    "mid_distant": (
        "母亲在你能量场里偏中等距离 —— 不是缺位但也不是早年最贴身的人，"
        "母子 / 母女关系比较「正常」"
    ),
    "far_or_intermittent": (
        "母亲在你早年成长中存在感偏弱 / 远 / 断续 ——"
        "可能形式是：母亲早年因工作 / 健康 / 距离不能贴身陪伴，"
        "或母亲性格偏疏离 / 不擅长情感表达，"
        "或者母亲存在但你跟她没有特别深的连接"
    ),
    "absent": (
        "母亲在你早年成长中存在感非常弱 / 缺位 ——"
        "可能形式是：母亲早离 / 早逝、母亲长期不在身边、"
        "或母亲虽在但情感缺位严重；"
        "（命局只能识别「母辈位空」这个结构，不区分具体原因）"
    ),
}


def compute_mother_profile(bazi: dict) -> dict:
    """母亲存在模式：基于正印位置 + 旺衰 + 是否被克。"""
    locations = _locate_shishen(bazi, MOTHER_SHISHEN)
    if not locations:
        locations = _locate_shishen(bazi, ALT_MOTHER_SHISHEN)
        used_alt = True
    else:
        used_alt = False

    wx_dist = bazi.get("wuxing_distribution", {})
    day_master_wx = bazi["day_master_wuxing"]
    # 母星五行 = 生我者五行（木日主→水生木→母=水；火→木；土→火；金→土；水→金）
    mother_wx_map = {"木": "水", "火": "木", "土": "火", "金": "土", "水": "金"}
    mother_wx = mother_wx_map[day_master_wx]
    mother_score = wx_dist.get(mother_wx, {}).get("score", 0)
    mother_ratio = wx_dist.get(mother_wx, {}).get("ratio", 0)
    is_mother_missing = wx_dist.get(mother_wx, {}).get("missing", False)

    yin_broken = _check_yin_broken(bazi, mother_wx)

    if not locations:
        mode = "absent"
        distance = "absent"
        evidence = f"原局完全不见{MOTHER_SHISHEN} / {ALT_MOTHER_SHISHEN}（母星五行={mother_wx} 缺失）"
    else:
        nian_loc = next((l for l in locations if l["pillar_idx"] == 0), None)
        yue_loc = next((l for l in locations if l["pillar_idx"] == 1), None)
        ri_loc = next((l for l in locations if l["pillar_idx"] == 2), None)

        if nian_loc or yue_loc:
            distance = "near"
        elif ri_loc:
            distance = "mid"
        else:
            distance = "far"

        if mother_score >= 6 and distance == "near":
            mode = "near_smothering"
        elif mother_score >= 3 and distance == "near":
            mode = "near_nurturing"
        elif distance == "mid":
            mode = "mid_distant"
        elif yin_broken or mother_score < 1.5:
            mode = "far_or_intermittent"
        else:
            mode = "mid_distant"

        if is_mother_missing or mother_ratio < 0.05:
            mode = "absent"
            distance = "absent"

        positions_str = ', '.join(
            f"{l['pillar_name']}/{l['where']}/{l['char']}" for l in locations
        )
        evidence = (
            f"母星=正印（{mother_wx}）"
            + ("（正印缺，用偏印兜底）" if used_alt else "")
            + f" · 出现位置=[{positions_str}]"
            + f" · 母星五行总分={mother_score:.1f}（占比 {mother_ratio:.0%}）"
            + f" · 印是否被破={'是（' + yin_broken + '）' if yin_broken else '否'}"
        )

    claim = MOTHER_MODE_DESC[mode]
    falsifiability = (
        "如果你回想跟母亲的实际相处模式跟上面描述明显反向 →（比如这条说"
        "「过度照护 / 控制」但你母亲其实非常放手、或这条说「缺位」"
        "但你母亲其实是你早年最贴身的人）→ 印星读法可能反了。"
        "**注意**：本条只判读"
        "「母亲在你能量场里的存在模式」，**不判读**母亲的社会地位 / 职业 / 收入 / 学历，"
        "也**不判读**母亲是否健在 / 是否再嫁——这些命局推不出。"
    )

    return {
        "mode": mode,
        "mode_label": {
            "near_nurturing": "贴近 · 照护教养型",
            "near_smothering": "贴近 · 过度照护型",
            "mid_distant": "中等距离 · 平淡",
            "far_or_intermittent": "偏远 / 断续",
            "absent": "缺位",
        }[mode],
        "distance": distance,
        "evidence": evidence,
        "claim": claim,
        "falsifiability": falsifiability,
        "used_alt_star": used_alt,
    }


def _nian_qi_sha_check(bazi: dict) -> dict:
    """检测年柱七杀 + 是否被印化解。"""
    pillar_info = bazi["pillar_info"]
    nian_gan_ss = pillar_info[0].get("gan_shishen")
    nian_zhi_ss = pillar_info[0].get("zhi_shishen")
    triggered = (nian_gan_ss == "七杀") or (nian_zhi_ss == "七杀")

    yin_resolved = False
    if triggered:
        for pi in pillar_info:
            if pi.get("gan_shishen") in ("正印", "偏印") or pi.get("zhi_shishen") in ("正印", "偏印"):
                yin_resolved = True
                break

    return {
        "triggered": triggered,
        "yin_resolved": yin_resolved,
        "where": "干" if nian_gan_ss == "七杀" else ("支" if nian_zhi_ss == "七杀" else None),
    }


def _check_yin_broken(bazi: dict, mother_wx: str) -> Optional[str]:
    """印是否被破：印的五行被原局某天干 / 地支强克。"""
    if not mother_wx:
        return None
    breaker_wx = WUXING_KE[mother_wx]
    pillars = bazi["pillars"]
    pillar_names = ["年柱", "月柱", "日柱", "时柱"]
    breakers = []
    for i, p in enumerate(pillars):
        if i == 2:
            continue
        if GAN_WUXING[p["gan"]] == breaker_wx:
            breakers.append(f"{pillar_names[i]}干 {p['gan']}（{breaker_wx}）")
    if breakers:
        return " + ".join(breakers)
    return None


# ---------- 整体家庭结构 5 档分类 ----------

def classify_family_structure(bazi: dict, father_profile: dict, mother_profile: dict) -> dict:
    """整体家庭结构 5 档分类。

    分类逻辑（机械可判，按优先级从高到低）：
        1. 缺位候选：父星 OR 母星 在五行分布中 missing 或 < 5% → absent_candidate
        2. 波折候选：年柱与日柱反吟/伏吟、年柱七杀无印化解、年柱财被劫财紧贴
                  → turbulent_candidate
        3. 显赫候选：年/月柱合计出现财官印 ≥ 2 类（去重）+ 都不被严重冲克
                  → illustrious_candidate
        4. 中产候选：年/月柱出现财官印恰好 1 类 + 不被破
                  → stable_candidate
        5. 普通：其余（年/月柱十神是比劫 / 食伤为主，无明显财官印聚合）
                  → ordinary
    """
    pillar_info = bazi["pillar_info"]
    pillars = bazi["pillars"]

    if father_profile["mode"] == "absent" or mother_profile["mode"] == "absent":
        primary = "absent_candidate"
        primary_evidence = (
            f"父={father_profile['mode_label']} / 母={mother_profile['mode_label']} "
            f"→ 至少一方在原局五行分布中明显缺位 / < 5%"
        )
        primary_claim = (
            "你家结构里父亲或母亲其中一方的存在感明显偏弱 ——"
            "可能形式是早离 / 早逝 / 长期不在身边 / 父母离异 / 重组家庭等，"
            "命局**只识别「父辈位 OR 母辈位空」这个结构**，不区分具体原因。"
            "（同时这意味着你早年很可能比同龄人更早承担一部分自我照护 / 长辈角色）"
        )
        secondary = None
    else:
        nian_yue_shishen: List[str] = []
        for i in (0, 1):
            for key in ("gan_shishen", "zhi_shishen"):
                ss = pillar_info[i].get(key)
                if ss and ss != "日主" and ss in WEALTHY_PROXY_SHISHEN:
                    nian_yue_shishen.append(ss)

        types_present = set()
        if any(s in ("正财", "偏财") for s in nian_yue_shishen):
            types_present.add("财")
        if any(s in ("正官", "七杀") for s in nian_yue_shishen):
            types_present.add("官")
        if any(s in ("正印", "偏印") for s in nian_yue_shishen):
            types_present.add("印")

        nian_zhi = pillars[0]["zhi"]
        ri_zhi = pillars[2]["zhi"]
        nian_chong_ri = ZHI_CHONG.get(nian_zhi) == ri_zhi
        nian_fuyin = (
            pillars[0]["gan"] == pillars[2]["gan"]
            and pillars[0]["zhi"] == pillars[2]["zhi"]
        )

        nian_qi_sha = _nian_qi_sha_check(bazi)
        cai_jie_zhe = _cai_jie_jin_tie(bazi)

        is_turbulent = (
            nian_chong_ri
            or nian_fuyin
            or (nian_qi_sha["triggered"] and not nian_qi_sha["yin_resolved"])
            or cai_jie_zhe
        )

        if is_turbulent:
            primary = "turbulent_candidate"
            reasons = []
            if nian_chong_ri:
                reasons.append(f"年柱{nian_zhi}冲日支{ri_zhi}（家世根基与你之间有结构性张力）")
            if nian_fuyin:
                reasons.append("年柱与日柱伏吟（家族议题在你身上重演）")
            if nian_qi_sha["triggered"] and not nian_qi_sha["yin_resolved"]:
                reasons.append("年柱七杀无印化解（早年家庭压力直接砸到你）")
            if cai_jie_zhe:
                reasons.append(f"年柱财被劫财紧贴（{cai_jie_zhe}）")
            primary_evidence = " · ".join(reasons)
            primary_claim = (
                "你家可能经历过一些结构性波动 ——"
                "比如父辈一代的经济 / 身份 / 家庭结构有过明显起伏（变迁 / 损失 / 重组），"
                "或者家族里某些议题在你身上反复出现。"
                "（不一定是「不好」，很多有韧性的家庭都属于这一档；"
                "但跟「平稳富裕」的画面感不一样）"
            )
        elif len(types_present) >= 2:
            primary = "illustrious_candidate"
            primary_evidence = (
                f"年/月柱合计出现 {len(types_present)} 类财官印（{'/'.join(sorted(types_present))}）"
                f" · 具体十神={nian_yue_shishen}"
            )
            primary_claim = (
                "你家可能在某一代积累过明显的资源 / 名望 / 影响力 ——"
                "父辈或祖辈中至少有一人在所在领域 / 单位 / 圈子里有可识别的位置，"
                "或者你家的物质 / 文化 / 社会资源积累比同龄人的家庭更厚一些。"
                "（注意：命局只能识别「年/月柱财官印聚集」这个结构，"
                "不能区分是「祖辈显赫但父辈普通」还是「父辈才起来」，"
                "也不能给出具体的财富 / 职位 / 学历数字）"
            )
        elif len(types_present) == 1:
            primary = "stable_candidate"
            primary_evidence = (
                f"年/月柱有 1 类财官印（{list(types_present)[0]}）+ 无明显冲克破"
                f" · 具体十神={nian_yue_shishen}"
            )
            primary_claim = (
                "你家结构稳定 —— 父母至少一方有相对稳定的社会身份 / 职业 / 资源，"
                "属于「中位数家庭」的画像，没有特别突出但也没有明显波折。"
                "（这一档很常见、很多人都属于这档；"
                "你成年后大概率没有过「家里完全帮不上忙」或「家里大变故」的体感）"
            )
        else:
            primary = "ordinary"
            primary_evidence = (
                f"年/月柱无明显财官印聚合，主要十神={nian_yue_shishen if nian_yue_shishen else '比劫 / 食伤为主'}"
            )
            primary_claim = (
                "你家是普通家庭 —— 父母没有特别突出的社会位置或资源，"
                "你早年成长基本是「同辈共处 / 自己琢磨 / 不太能从家里要资源」的模式。"
                "（这一档非常常见，没有褒贬；"
                "意味着你成年后的资源主要靠自己积累，不是从家里继承）"
            )

        secondary = None
        if primary == "illustrious_candidate" and len(types_present) == 2:
            secondary = "stable_candidate"
        if primary == "turbulent_candidate" and len(types_present) >= 2:
            secondary = "illustrious_candidate"

    return {
        "primary_class": primary,
        "primary_class_label": FAMILY_CLASS_LABEL[primary],
        "primary_evidence": primary_evidence,
        "primary_claim": primary_claim,
        "secondary_class": secondary,
        "secondary_class_label": FAMILY_CLASS_LABEL[secondary] if secondary else None,
    }


def _cai_jie_jin_tie(bazi: dict) -> Optional[str]:
    """检测「年柱财被劫财紧贴」结构。"""
    pillar_info = bazi["pillar_info"]
    nian = pillar_info[0]
    yue = pillar_info[1]
    nian_has_cai = nian.get("gan_shishen") in ("正财", "偏财") or nian.get("zhi_shishen") in ("正财", "偏财")
    if not nian_has_cai:
        return None
    if yue.get("gan_shishen") in ("比肩", "劫财"):
        return f"月干={yue['gan']}（{yue['gan_shishen']}）紧贴年柱财"
    if nian.get("gan_shishen") in ("比肩", "劫财") and nian.get("zhi_shishen") in ("正财", "偏财"):
        return f"年干={nian['gan']}（{nian['gan_shishen']}）盖头年支财"
    return None


# ---------- R3 反询问·原生家庭画像 2 题 ----------

def build_r3_questions(bazi: dict, father: dict, mother: dict, family_class: dict) -> List[dict]:
    """生成 R3 反询问 2 题：① 整体家庭结构 ② 父母存在模式合并描述。"""
    q1 = {
        "category": f"原生家庭①·整体结构（{family_class['primary_class_label']}）",
        "side": "family_structure",
        "evidence": family_class["primary_evidence"],
        "claim": family_class["primary_claim"],
        "falsifiability": (
            "如果你家整体结构跟上面描述明显不符 ——"
            f"比如这条说「{family_class['primary_class_label']}」"
            "但你家其实完全是另一种画像（无明显资源 / 无明显波折 / 无明显缺位 / 或显赫程度差异极大）"
            "→ 这条错。"
            "**注意**：本条只识别「年/月柱财官印聚集 / 冲克 / 缺位」这个结构性画像，"
            "**不能**精确区分「祖辈显赫 vs 父辈才起来」、"
            "**不能**给具体的财富 / 职位 / 学历等级，"
            "**不能**判读父母是否健在 / 是否离异（这些命理推不出）。"
            "另外古典命书因为只收录显赫人物的命例（survivorship bias），"
            "「显赫候选」这一档比真实概率被高估了 5-10 倍——这条标错请直接回「不对」。"
        ),
        "score": 9.0,
        "primary_class": family_class["primary_class"],
        "secondary_class": family_class.get("secondary_class"),
    }

    father_short = father["claim"].split("——")[0].strip()
    mother_short = mother["claim"].split("——")[0].strip()
    combined_claim = (
        f"【父亲存在模式 · {father['mode_label']}】{father['claim']}\n   "
        f"【母亲存在模式 · {mother['mode_label']}】{mother['claim']}"
    )
    q2 = {
        "category": "原生家庭②·父母存在模式（合并）",
        "side": "parents_presence",
        "evidence": (
            f"父={father['evidence']}；\n   母={mother['evidence']}"
        ),
        "claim": combined_claim,
        "falsifiability": (
            "请分别校验父亲和母亲两条 ——"
            "如果父亲那条对、母亲那条不对 → 答「部分」并指出哪条不对；"
            "如果两条都明显反向 → 答「不对」（父星 / 母星读法可能反了，"
            "常见原因是时辰错导致月柱十神跳位、或日主性别误判）。"
            "**注意**：本条只判读「父母在你能量场里的存在模式」，"
            "**不判读**父母的社会地位 / 收入 / 职业 / 学历 / 是否健在 / 是否离异。"
        ),
        "score": 9.2,
        "father_mode": father["mode"],
        "mother_mode": mother["mode"],
    }
    return [q1, q2]


# ---------- 组装 + 主函数 ----------

LLM_INSTRUCTION_R3 = """\
== Round 3（反询问·原生家庭画像 2 题，v7.3 新增 · 在 R0 之后、R1 之前抛 OR 仅在用户主动问家庭/父母时抛）==

取 round3_candidates 里的 2 条（①整体家庭结构 + ②父母存在模式合并）。

**这是"原生家庭反询问窗口"**——主动把家庭结构问题抛给用户，用于：
  · 校验命局对原生家庭的读法是否对路（年/月柱十神 / 父星 / 母星位置）
  · 协助 LLM 在 family 段写作时**不裸推**（必须经 R3 校验后才能展开"显赫"或"缺位"等具体描述）

输出模板（必须严格按此格式）：
----
我顺便用 2 个原生家庭相关的问题校验一下命局结构 —— 这两题不评判 / 不打标签，
只用来判断你家的整体结构和父母存在模式跟命局的"年/月柱画像"是否对得上。
请凭直觉答「对 / 不对 / 部分」。

⚠ 重要前提（必读）：
命局只反映「父母在你能量场里的存在模式」+「年/月柱财官印聚合的结构画像」，
**不反映**父母的社会地位 / 收入 / 职业 / 学历 / 是否健在 / 是否离异。
另外古典命书因为只收录显赫人物的命例（survivorship bias），
显赫候选这一档比真实概率被高估了 5-10 倍——标错请直接回"不对"。

③-① 【{round3[0].category}】{round3[0].claim}
   依据：{round3[0].evidence}
   可证伪点：{round3[0].falsifiability}

③-② 【{round3[1].category}】{round3[1].claim}
   依据：{round3[1].evidence}
   可证伪点：{round3[1].falsifiability}
----

R3 命中 → family 段权重：
  · 2/2 → 高置信，可以按 primary_class 展开（比如真显赫候选 + 用户确认 → 可以说"父辈/祖辈中可能有人在某领域有可识别的位置"）
  · 1/2 → 中置信，命中那条可展开；未命中那条标"取向歧义"或省略
  · 0/2 → 低置信，**family 段不展开具体内容**，只写一句"原生家庭推断未通过校验，本次不展开（命局对家庭的读法可能反了）"

R3 命中级别和 R0/R1 校验是**正交**的（R3 不算入命局准确度，仅用于决定 family 段写不写 / 怎么写）。

R3 红线：
  · 若【原生家庭①·整体结构】被标"不对"且 primary_class = illustrious_candidate
    → 这是 LLM 最容易翻车的场景（古法 survivorship bias 推过头），family 段必须降级
  · 若【原生家庭②·父母存在模式】两条都被标"不对"
    → 父星 / 母星读法多半反了，family 段直接省略

== R3 触发时机 ==
- **默认**：在 R0 之后、R1 之前抛出（若用户在初次提问中问到 family / 父母 / 家庭等关键词）
- **可选**：若用户初次提问完全没提家庭，可省略 R3（不写 family 段也不会缺胳膊少腿）
- **不要**：在 R0/R1/R2 全部完成后再追加 R3——会让校验环节显得太冗长

== family 段写作必须遵守 fairness_protocol.md §11 ==
- 必须援引 R3 命中（"R3 = 2/2 → 高置信展开"）
- 必须前置声明（"命局只反映父母在你能量场里的存在模式，不反映社会地位 / 职业 / 学历 / 是否健在"）
- 禁用措辞清单：参考 §11.2
"""


def build_family_profile(bazi: dict) -> dict:
    """主入口：组装 family_profile.json。"""
    father = compute_father_profile(bazi)
    mother = compute_mother_profile(bazi)
    family_class = classify_family_structure(bazi, father, mother)
    r3 = build_r3_questions(bazi, father, mother, family_class)

    return {
        "version": "v7.3",
        "schema_purpose": (
            "原生家庭结构画像 —— 仅输出结构性标签 + R3 反询问候选，"
            "不打分、不画曲线。供 LLM 在 family 段写作前必须援引（防止裸推 / 古法显赫偏置）。"
        ),
        "pillars_str": bazi.get("pillars_str"),
        "day_master": bazi["day_master"],
        "day_master_wuxing": bazi["day_master_wuxing"],
        "father_profile": father,
        "mother_profile": mother,
        "family_class": family_class,
        "round3_candidates": r3,
        "instruction_for_llm": LLM_INSTRUCTION_R3,
        "fairness_note": (
            "见 references/fairness_protocol.md §11 原生家庭解读铁律。"
            "命局可推：父母在你能量场里的存在模式 + 年/月柱财官印聚合的结构画像。"
            "命局不可推：父母的社会地位 / 收入 / 职业 / 学历 / 是否健在 / 是否离异 / 婚姻状态。"
        ),
    }


def main():
    ap = argparse.ArgumentParser(description="生成原生家庭结构画像（family_profile.json · v7.3）")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--out", default="family_profile.json", help="输出路径")
    args = ap.parse_args()

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    result = build_family_profile(bazi)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fc = result["family_class"]
    print(
        f"[family_profile] wrote {args.out}: "
        f"整体={fc['primary_class_label']}"
        + (f"（次档 {fc['secondary_class_label']}）" if fc.get("secondary_class") else "")
        + f" · 父={result['father_profile']['mode_label']}"
        + f" · 母={result['mother_profile']['mode_label']}"
    )


if __name__ == "__main__":
    main()
