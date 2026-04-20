#!/usr/bin/env python3
"""handshake.py — 出图前的「下马威 / 校准握手」候选生成器。

输入：bazi.json（来自 solve_bazi.py）+ curves.json（来自 score_curves.py）+ 当前年份
输出：handshake.json，分两轮：
       - Round 1：**三个不同侧面的健康问题**（v3 改版）
                 ① 体感寒热 / 出汗（climate）
                 ② 睡眠 / 精力 / 神经状态（climate × strength）
                 ③ 易病脏腑 / 体质短板（五行最弱 → 对应脏腑）
                 → 用「命中率」定准确度：3/3 高、2/3 中、≤1/3 低（建议核对时辰）
       - Round 2：在 R1 命中 < 3 时追加，从「本性画像 + 历史锚点」池里挑 3 条交叉验证

设计原则：
  1. 脚本只挑候选 + 给文案 stub，LLM 不允许自由发挥事实
  2. 每条候选自带"为什么把握高"的依据（evidence）+ "可证伪点"（falsifiability）
  3. **R1 全部用健康问题**——这是用户回忆最稳定、最难骗的证据（终生体感）
     · 八字时辰错 1 小时会让 climate 跳一档 / 五行权重剧变 / 强弱跳档
     · 用户对"怕不怕冷"、"睡眠浅不浅"、"哪个脏腑常出问题"的回答近乎二值
  4. 命中率 → 准确度：3/3 高 → 直接进绘图 / 合盘；2/3 中 → 走 R2 凑到 ≥4/6；≤1/3 → 强烈建议核对时辰
  5. R2 候选池：本性 traits + 过往锚点（保留旧逻辑）
  6. 用于合盘场景时：每个参与方的八字都跑一遍 R1，命中率定该八字"准不准"（详见 he_pan_protocol.md）
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ---------- 文案库：日主基底（每个天干 1 段固化文字） ----------

GAN_TRAIT = {
    "甲": "直进生长型——不愿被压、不喜重复、对'卡住自己'的环境最敏感",
    "乙": "柔韧迂回型——不正面硬刚但会持续生长，对'被忽视 / 被打断'敏感",
    "丙": "外放强热型——天然引领、需要被看见，对'灰暗 / 沉闷的环境'最不耐",
    "丁": "内热专注型——表面温和但内心持续燃烧，对'失去聚焦点'最难受",
    "戊": "稳重承载型——爱掌控产出、爱建结构，对'失去主导权 / 没有成果'最敏感",
    "己": "包容培养型——爱铺垫、不爱出头，对'被强迫上前 / 失去靠山'敏感",
    "庚": "果断刚健型——直接、爱定结果，对'拖泥带水 / 没有结论'最不耐",
    "辛": "精密敏感型——爱体面、爱细节，对'粗糙 / 被怠慢'极其敏感",
    "壬": "宏大流动型——不喜被拘束、爱大场面，对'狭小重复的日常'极易厌倦",
    "癸": "渗透深思型——慢热但深入，对'浅层关系 / 被催促'最易疲惫",
}

STRENGTH_TRAIT = {
    "强":   "日主偏强 → 你天然不爱被人管、不喜屋檐下做事；'自主'对你是基础需求而不是奢侈品",
    "弱":   "日主偏弱 → 你对外部环境匹配度极敏感；环境对了能爆发，环境不对会成倍下滑",
    "中和": "日主中和 → 你在多种环境下都能适应，但最容易'被环境带偏'，所以你必须主动选环境",
    # 兼容旧 label（万一以后细分）
    "偏强": "日主偏强 → 你天然不爱被人管、不喜屋檐下做事",
    "偏弱": "日主偏弱 → 你对外部环境匹配度极敏感；环境对了能爆发，错了会成倍下滑",
    "极强": "日主极强 → 一旦下定决心几乎拽不回；护城河 + 最大固执来源",
    "极弱": "日主极弱 → 你需要很强的外援 / 系统支撑；独自硬扛容易崩",
    "从强": "从强格局 → 不能强行扶弱，顺势走才是你的命；逆着来必出问题",
    "从弱": "从弱格局 → 反而要顺从忌神 / 抑日主之力；硬扶反而崩",
}

YONGSHEN_TRAIT = {
    "金": "用神为金 → 你最舒适的活动类型是「结构化的产出 / 收割 / 定型」（写作、做产品、打磨作品、收尾）",
    "木": "用神为木 → 你最舒适的活动类型是「生发 / 扩张 / 教学」（带新人、做新业务、培育、铺路）",
    "水": "用神为水 → 你最舒适的活动类型是「流动 / 连接 / 智识」（咨询、社交、研究、跨界）",
    "火": "用神为火 → 你最舒适的活动类型是「被看见 / 演示 / 传播」（讲台、镜头、IP、表达）",
    "土": "用神为土 → 你最舒适的活动类型是「稳定 / 承载 / 管理」（运营、组织、投资管理、长期持有）",
}

# [新增 v2，2026-04，from 1996 八字失败教训]
# 体质画像（physiology）—— 直接从 climate_profile 机械导出，是命局静态结构最难骗的证据。
# 用户的"从小怕热 / 从小怕冷 / 出汗多 / 入睡难"是终生稳定的体感，比"哪一年发生了什么"
# 更适合做下马威——错八字（时辰差 1 小时）会让 climate label 跳一档，体感反馈立刻能照出来。

# 侧面 ① 寒热 / 出汗（temperature & sweat） —— 只谈温度感，不谈睡眠
HEALTH_TEMPERATURE = {
    "燥实":     "你从小就明显怕热、贪凉饮、运动后大量出汗；夏天比常人难熬、冬天反而不太怕冷；容易上火（口腔溃疡 / 痘 / 鼻血）",
    "外燥内湿": "你身体一直偏热、全身常暖、喝凉的舒服；运动 / 紧张时出汗偏多，但小时候容易着凉（地支湿底盘的体现）",
    "偏燥":     "你比一般人怕热一点、偏爱凉饮，运动后出汗偏多",
    "中和":     "你对冷热环境的体感比较平衡，没有显著的怕热 / 怕冷倾向，温度偏好和大多数人一致",
    "偏湿":     "你比一般人怕冷一点，不爱喝冰的，湿气重的环境（梅雨 / 地下室）会让你不太舒服",
    "外湿内燥": "你身体表面偏寒（手脚易凉），但内里常有暗火 —— 冬天怕冷、夏天又比别人热得快、容易急躁",
    "寒湿":     "你从小明显怕冷、不爱冰饮、手脚常年偏凉；夏天比一般人舒服、冬天难熬",
}

HEALTH_TEMPERATURE_FALSIF = {
    "燥实":     "如果你从小一直怕冷、爱热饮、手脚常年凉、不出汗 → 这条错（命局判读多半反了，常见于时辰偏 1 小时）",
    "外燥内湿": "如果你从小一直怕冷、贪热饮、手脚冰凉、运动也不出汗 → 这条错",
    "偏燥":     "如果你常年手脚冰凉 + 不出汗 + 怕冷 → 这条错",
    "中和":     "如果你属于显著的怕热或怕冷型（夏天热到崩溃 / 冬天冷到僵手）→ 这条错（命局应不是中和）",
    "偏湿":     "如果你常年体热 + 大量出汗 + 贪凉饮 → 这条错",
    "外湿内燥": "如果你内里也偏寒（一年到头不上火 / 不急躁 / 入睡很快）→ 这条错",
    "寒湿":     "如果你从小一直怕热、贪凉饮、出汗多 → 这条错",
}

# 侧面 ② 睡眠 / 精力 / 神经状态（climate × strength）
SLEEP_BY_CLIMATE = {
    "燥实":     "睡眠偏浅、入睡需要点时间、多梦或早醒（清晨 4–6 点醒来再难入睡）",
    "外燥内湿": "睡眠偏浅、躺下脑子停不下来、入睡难，但一旦睡着可以睡满",
    "偏燥":     "睡眠中等偏浅，作息一旦乱就容易失眠或多梦",
    "中和":     "睡眠规律性较好，作息一旦稳定就不太被小事干扰",
    "偏湿":     "睡眠时长够但醒来仍觉得困，午后或饭后容易犯困",
    "外湿内燥": "嗜睡 + 难醒 / 早上特别困，但夜里偶尔会被自己脑内的事吵醒（外湿压住、内燥撑起）",
    "寒湿":     "嗜睡、起床极慢、午后易困；白天精力起伏明显",
}

ENERGY_BY_STRENGTH = {
    "强":   "精力比一般人旺、坐不住、闲下来反而烦躁；耐独自连轴干",
    "弱":   "精力起伏大 —— 状态来时很猛，但稍一连续输出就会断电式疲倦；需要靠节奏 / 外援撑住",
    "中和": "精力中等且平稳，没有明显的爆发或断电感；环境匹配时持久输出",
    # 兼容旧 label
    "偏强": "精力比一般人旺、坐不住、闲下来反而烦躁",
    "极强": "精力极旺，长期单打独斗也撑得住，但对'被人管'的环境耐受度极低",
    "从强": "顺着自己的强项走时精力极旺，被强行拉去补短板时会迅速没电",
    "偏弱": "精力起伏大 —— 状态来时很猛，连续输出会断电式疲倦",
    "极弱": "精力体力偏弱，必须靠节奏 / 外援撑住，独自连轴硬扛会快速崩",
    "从弱": "顺势 / 借力时精力够用，硬扛 / 逆势硬撑会迅速透支",
}

NERVE_BY_CLIMATE = {
    "燥实":     "情绪上偏急、易上火，遇事第一反应偏激烈，事后才平复",
    "外燥内湿": "情绪上看起来稳，但内里是急性子，事赶到跟前会突然烦",
    "外湿内燥": "外面慢、内里急，憋久了会突然爆，平时不易察觉",
    "寒湿":     "情绪偏沉、慢热，遇事先反复琢磨而不是当下爆发",
}

# 侧面 ③ 易病脏腑 / 体质短板（五行最弱 → 对应脏腑）
ORGAN_BY_WUXING = {
    "木": {
        "name": "肝胆 / 筋膜 / 视力",
        "claim_tail": "易胁肋胀、情绪一压抑就肝气郁结、长期看屏幕眼干涩、颈肩筋膜偏紧",
        "falsif": "你从小到大眼睛、肝胆、情绪压抑相关的问题都没怎么遇到 → 这条错",
    },
    "火": {
        "name": "心 / 小肠 / 血脉循环",
        "claim_tail": "易心慌心悸、手脚循环差冬天易凉、运动后心跳恢复偏慢、压力大容易胸闷",
        "falsif": "你从小心血管 / 循环都很好、运动恢复也快、手脚一年到头都暖 → 这条错",
    },
    "土": {
        "name": "脾胃 / 消化 / 肌肉",
        "claim_tail": "肠胃偏弱（吃凉 / 油腻 / 不规律就闹）、易腹胀腹泻、湿气重 / 易长痘 / 易水肿",
        "falsif": "你从小肠胃极好、什么都能吃、不腹胀腹泻 → 这条错",
    },
    "金": {
        "name": "肺 / 大肠 / 皮肤 / 鼻咽",
        "claim_tail": "呼吸道偏弱（易感冒 / 鼻炎 / 咽干 / 气管敏感）、皮肤偏敏感（易过敏 / 干燥 / 起疹）、便秘或大肠功能弱",
        "falsif": "你从小呼吸道、鼻、皮肤都很皮实，从来不过敏、不感冒 → 这条错",
    },
    "水": {
        "name": "肾 / 膀胱 / 骨 / 耳 / 生殖泌尿",
        "claim_tail": "腰膝偏酸软、容易尿频或尿急、耳鸣 / 听力敏感、骨密度偏低、生殖泌尿系统偏弱",
        "falsif": "你从小到大腰、膝、生殖泌尿、耳朵都很皮实 → 这条错",
    },
}


# [新增 v6，2026-04] [v7 现代化重构，2026-04] R0 反询问·关系画像
# 设计思路：在校验最开始，主动抛 2 题关系类问题（"反询问"窗口），
# 用于校准两件事：
#   (1) 八字是否准（关系记忆 = 用户最深刻、最难骗的事件记忆）
#   (2) 命局取向（验证日主强弱 / 用神判断 / 是否走格局派 vs 扶抑派）
# 与 R1 健康三问互补：健康三问校验"体感是否符合命局结构"，R0 关系画像校验"关系结构是否符合命局结构"
#
# v7 现代化原则：
# - 命局只反映"亲密关系核心人物"的能量结构，不预设对方性别 / 是否结婚 / 是否生育
# - 删除颜值描述（"轮廓清晰 / 五官立体"等）—— 命理学不能推到外貌
# - 删除"妻 / 夫 / 配偶"二元婚姻措辞 → 改为"亲密对象 / 关系核心"
# - 删除带价值判断的措辞（"看不上 / 忍不了"）→ 改为"反复被吸引 / 互动顺畅度高"
# - 支持 orientation 切换配偶星识别（hetero/homo/bi/none/poly）

# ---- 配偶星五行 → 反复被吸引的特质类型（v7 现代化：去颜值 / 去性别 / 去价值判断） ----
WUXING_TYPE_DESC = {
    "金": "干练果决 / 有原则 / 说话直接不绕弯 / 偏冷感而不轻易迁就 / 自带边界感",
    "木": "有理想感 / 表达温和但内心有主见 / 偏成长型 / 喜欢有方向感的相处",
    "水": "聪明灵活 / 善表达善共情 / 思维跳跃 / 情绪起伏比你大 / 容易让你感到「被读懂」",
    "火": "热情外向 / 表达力强 / 把氛围带亮的那种人 / 略有些「人来疯」/ 主动型",
    "土": "稳重务实 / 安全感强 / 偏保守 / 不擅惊喜但情绪稳定 / 长期可靠",
}

# ---- 配偶宫（日支）藏干十神 → 内心偏好的关系互动模式（v7 现代化：去物化、去顺从假设） ----
SPOUSE_PALACE_TRAIT = {
    "比肩": "你偏好「同辈感 / 平起平坐」的关系模式 —— 不喜欢被对方压一头，也不想压对方",
    "劫财": "你偏好「势均力敌甚至略强于你」的关系模式 —— 完全顺从你的会让你觉得没张力",
    "食神": "你偏好「松弛 / 一起享受生活 / 互相照应」的关系模式 —— 太严肃高压的不长久",
    "伤官": "你偏好「有才华 / 有锋芒 / 能对话能切磋」的关系模式 —— 单纯老实型对你吸引力有限",
    "正财": "你偏好「踏实可预期 / 会经营生活 / 安全感强」的关系模式 —— 不靠谱的让你紧张",
    "偏财": "你偏好「灵活 / 有手段 / 能带来新鲜感」的关系模式 —— 一成不变的让你嫌闷",
    "正官": "你偏好「正派 / 有规矩有底线 / 公开关系也得体」的模式 —— 痞气 / 灰色地带让你不安",
    "七杀": "你偏好「强势 / 有压迫感 / 甚至带点危险气息」的关系模式 —— 太软的让你觉得没张力",
    "正印": "你偏好「比你成熟 / 知性 / 能照护或指导你」的关系模式 —— 完全比你幼稚的没营养感",
    "偏印": "你偏好「独特 / 有偏门才华 / 思维路径和大众不同」的模式 —— 完全主流型让你提不起劲",
}

# ---- 桃花地支（子午卯酉） + 红艳 / 沐浴 等 ----
PEACH_BLOSSOM_ZHI = {"子", "午", "卯", "酉"}

def _has_peach_blossom(bazi: dict) -> bool:
    zhis = [p["zhi"] for p in bazi["pillars"]]
    return any(z in PEACH_BLOSSOM_ZHI for z in zhis)


def _spouse_star_strength(bazi: dict) -> str:
    """
    判断配偶星旺衰（v7 按 orientation 取）：
      hetero: 男看 ke（财）/ 女看 kewo（官杀）
      homo:   男看 kewo / 女看 ke
      bi/poly: max(ke, kewo)
      none:   返回 'na'（不识别）
    返回 strong / mid / weak / na。
    """
    gender = bazi.get("gender", "M").upper()
    orient = bazi.get("orientation", "hetero").lower()
    s = bazi["strength"]
    ke = s.get("ke", 0)
    kewo = s.get("kewo", 0)
    if orient == "none":
        return "na"
    if orient in ("bi", "poly"):
        target = max(ke, kewo)
    elif orient == "homo":
        target = kewo if gender == "M" else ke
    else:
        target = ke if gender == "M" else kewo
    if target >= 5:
        return "strong"
    if target >= 2:
        return "mid"
    return "weak"


def _attitude_descriptor(bazi: dict) -> dict:
    """从配偶星旺衰 + 比劫 + 食伤 + 印 + 桃花综合推"对方对你的反应模式"。

    v7 现代化：
    - 删除 gender 分支（"男命抢不过 / 女命被分流" 改为不分性别的"主动争取型"）
    - 全部改为中性描述：不用"异性缘"、不用"配偶"，改用"亲密对象 / 你心动过的人"
    - none 取向 → 改为"自我亲密能量"画像，不预设外部关系对象
    """
    s = bazi["strength"]
    spouse_strength = _spouse_star_strength(bazi)
    bijie = s.get("same", 0)
    shishang = s.get("xie", 0)
    yin = s.get("sheng", 0)
    has_peach = _has_peach_blossom(bazi)
    orient = bazi.get("orientation", "hetero").lower()

    bits: List[str] = []
    if orient == "none":
        primary = (
            "你声明了不寻求传统亲密关系；这一题用来描述你的「自我亲密能量」 —— "
            f"食伤={shishang:.1f}（自我表达力），印={yin:.1f}（自我照护力），"
            f"比劫={bijie:.1f}（同辈协作 / 独立张力），桃花={'有' if has_peach else '无'}"
        )
    elif spouse_strength == "strong" and (shishang >= 4 or has_peach):
        primary = (
            "你心动过的对象，很多时候是对方主动靠近 / 热烈表达的那一方；"
            "你不用太费劲就能让你心动的人对你有反应"
        )
    elif spouse_strength == "weak" and bijie >= 5:
        primary = (
            "你心动过的对象，常常是「你单方面争取 / 或者跟别人竞争」的局面 —— "
            "不是你魅力不足，是结构上配偶星弱比劫旺，'需要主动经营'是常态"
        )
    elif yin >= 6:
        primary = (
            "你心动过的对象，常常是「比你成熟一些 / 想照护你 / 偏支持型」的人在主动接近；"
            "完全同辈平等型的相对少见"
        )
    elif spouse_strength == "mid" and shishang >= 3:
        primary = (
            "你能吸引到不少人，但常常是「暧昧不明 / 对方时进时退」 —— "
            "你不太能一下确定对方到底是不是认真的"
        )
    elif spouse_strength == "weak" and shishang <= 2:
        primary = (
            "你心动的次数本身不多；当你真心动时，常常是你单方面默默关注，"
            "对方未必察觉"
        )
    else:
        primary = (
            "你心动的对象对你的反应模式介于「主动」和「等你先动」之间，"
            "谁先动跟具体对象的性格更相关，没有非常一致的模式"
        )

    bits.append(primary)
    if has_peach and orient != "none":
        bits.append("（命局带桃花地支，整体被吸引的密度是够的，关键看你的接收意愿）")
    return {"text": "；".join(bits), "spouse_strength": spouse_strength,
            "bijie": bijie, "shishang": shishang, "yin": yin, "has_peach": has_peach}


def _spouse_shishen_set(bazi: dict) -> tuple:
    """v7 按 orientation 取配偶星十神集合。"""
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
    return cai if gender == "M" else guan


def _orient_role_label(bazi: dict) -> str:
    """v7 按 orientation 返回中性"配偶星"角色名。"""
    orient = bazi.get("orientation", "hetero").lower()
    if orient == "none":
        return "（不识别配偶星 · self-centered 模式）"
    if orient in ("bi", "poly"):
        return "亲密关系核心星（财 + 官杀同看）"
    if orient == "homo":
        return "亲密关系核心星（同性取向 · 男看官杀 / 女看财）"
    return "亲密关系核心星（异性取向 · 男看财 / 女看官杀）"


def _build_emotion_preference(bazi: dict) -> Optional[dict]:
    """R0 题①·偏好类型 —— 配偶星五行 + 配偶宫藏干十神。

    v7 现代化：去"妻星/夫星"二元措辞，按 orientation 取配偶星集合。
    """
    gender = bazi.get("gender", "M").upper()
    orient = bazi.get("orientation", "hetero").lower()
    pillars = bazi["pillars"]
    pillar_info = bazi["pillar_info"]
    day_zhi = pillars[2]["zhi"]
    target_shishen = _spouse_shishen_set(bazi)
    role_label = _orient_role_label(bazi)

    # none 取向：跳过 R0 题①（self-centered 模式不预设外部关系对象）
    if orient == "none":
        s = bazi["strength"]
        return {
            "category": "关系①·自我亲密能量",
            "side": "preference",
            "evidence": f"orientation=none · 食伤={s.get('xie',0):.1f} · 印={s.get('sheng',0):.1f}",
            "claim": (
                "你声明了 orientation=none（不寻求传统亲密关系）—— 此题改为校验你的「自我亲密能量」："
                f"食伤={s.get('xie',0):.1f}（越高 = 自我表达 / 创造的吸引力越强），"
                f"印={s.get('sheng',0):.1f}（越高 = 自我照护 / 独处恢复力越强）。"
                "你应该体感到：「独处不孤单 / 有自给自足的内在丰盈」。"
            ),
            "falsifiability": "如果你长期独处时强烈感到空虚 / 必须靠他人填补，这条不对。",
            "score": 9.0,
        }

    # 在 8 字里找配偶星五行
    spouse_wxs: List[str] = []
    for pi in pillar_info:
        if pi.get("gan_shishen") in target_shishen:
            spouse_wxs.append(pi["gan_wuxing"])
        if pi.get("zhi_shishen") in target_shishen:
            spouse_wxs.append(pi["zhi_wuxing"])
    spouse_wx = spouse_wxs[0] if spouse_wxs else None

    # 配偶宫藏干主气十神（"偏好的关系互动模式"）
    palace_shishen = None
    try:
        from _bazi_core import ZHI_HIDDEN_GAN, calc_shishen
        main_gan = ZHI_HIDDEN_GAN[day_zhi][0]
        palace_shishen = calc_shishen(pillars[2]["gan"], main_gan)
    except Exception:
        palace_shishen = pillar_info[2].get("zhi_shishen")

    parts: List[str] = []
    if spouse_wx and spouse_wx in WUXING_TYPE_DESC:
        parts.append(
            f"【反复被吸引的特质】你回顾真心心动过的人，往往带有 **{WUXING_TYPE_DESC[spouse_wx]}** 的气质（推断依据：{role_label}五行={spouse_wx}）"
        )
    else:
        parts.append(
            f"【反复被吸引的特质】你命局里{role_label}不显——你被吸引的对象类型常常不固定 / 凭直觉 / 没有清晰的'就是喜欢这一类'，"
            "或者你不太容易一眼心动"
        )

    if palace_shishen and palace_shishen in SPOUSE_PALACE_TRAIT:
        parts.append(f"【偏好的关系互动模式】{SPOUSE_PALACE_TRAIT[palace_shishen]}（推断依据：日支={day_zhi}，藏干主气={palace_shishen}）")

    claim = "；".join(parts)
    falsif = (
        "如果你回顾过往真心心动过的几个对象，他们的特质跟上面描述完全相反 → 这条错。"
        "（注意：'你最后跟谁在一起'不算，问的是'你主动想靠近的那一类'。"
        "命局只反映你内在的吸引模式，不反映对方的性别 / 你最终选择的关系形态——这些是你的现代选择，不在命局之内。）"
    )
    return {
        "category": "关系①·偏好类型",
        "side": "preference",
        "evidence": f"gender={gender} · orientation={orient} · 配偶星五行={spouse_wx or '无'} · 日支{day_zhi}藏干主气十神={palace_shishen}",
        "claim": claim,
        "falsifiability": falsif,
        "score": 9.6,
    }


def _build_emotion_attitude(bazi: dict) -> Optional[dict]:
    """R0 题②·对方反应模式 —— 配偶星旺衰 + 比劫 + 食伤 + 印 + 桃花综合。

    v7 现代化：去"对方对你的态度"措辞中的婚姻预设，none 取向走"自我亲密能量"。
    """
    desc = _attitude_descriptor(bazi)
    gender = bazi.get("gender", "M").upper()
    orient = bazi.get("orientation", "hetero").lower()
    role_label = _orient_role_label(bazi)

    if orient == "none":
        claim = f"【自我亲密能量】{desc['text']}"
        falsif = (
            "如果你长期独处时频繁感到空虚 / 自我表达 + 自我照护两条都低，这条不对。"
        )
    else:
        claim = (
            f"你回顾真心心动过的那些人，**他们对你的反应模式**通常是：{desc['text']}"
        )
        falsif = (
            "如果回顾你过往真心心动过的几次，对方的反应模式跟上面描述完全反向 → 这条错。"
            "（既不是描述的那种主动 / 也不是描述的那种被动，而是稳定的另一种模式）"
        )
    return {
        "category": ("关系②·自我亲密能量" if orient == "none" else "关系②·对方反应模式"),
        "side": "attitude",
        "evidence": (
            f"gender={gender} · orientation={orient} · {role_label}强度={desc['spouse_strength']} · "
            f"比劫={desc['bijie']:.1f} · 食伤={desc['shishang']:.1f} · "
            f"印={desc['yin']:.1f} · 桃花地支={'有' if desc['has_peach'] else '无'}"
        ),
        "claim": claim,
        "falsifiability": falsif,
        "score": 9.4,
    }


def build_emotion_pair(bazi: dict) -> List[dict]:
    """R0 = 关系画像 2 题：偏好类型 + 对方反应模式（none 取向 → 自我亲密能量）。"""
    out: List[dict] = []
    for fn in (_build_emotion_preference, _build_emotion_attitude):
        item = fn(bazi)
        if item is not None:
            out.append(item)
    return out


YUE_SHISHEN_TRAIT = {
    "比肩": "月柱比肩 → 你的人生主线是「与人共做 / 同辈协作」，但也最容易在合作里被均分掉利益",
    "劫财": "月柱劫财 → 你倾向冒险 / 借力 / 合伙；但要长期警惕「被合伙人吃掉」的结构性风险",
    "食神": "月柱食神 → 你的人生主线是「享受 + 创造」，会自然吸引产出型机会",
    "伤官": "月柱伤官 → 你的人生主线是「用才华突破常规」，所以你跟权威 / 标准化体制天然有摩擦",
    "正财": "月柱正财 → 你的人生主线是「稳定经营、积少成多」，对'一夜暴富'会本能慎重",
    "偏财": "月柱偏财 → 你的人生主线是「机会型 / 非工资型收入」，单一岗位会让你觉得憋屈",
    "正官": "月柱正官 → 你的人生主线是「被规则塑造，走体制 / 职业晋升路径」",
    "七杀": "月柱七杀 → 你的人生主线是「压力驱动 + 用挑战兑换成长」，没有挑战反而会萎缩",
    "正印": "月柱正印 → 你的人生主线是「学习 / 被庇护 / 学术或类学术」，环境稳定时最盛",
    "偏印": "月柱偏印 → 你的人生主线是「非主流学问 / 敏感直觉 / 独立思考」，对庸常体制不耐",
}


# ---------- 锚点文案模板 ----------

ANCHOR_CLAIM_TPL = {
    ("wealth", "up"):    "{age} 岁那年（{year} {ganzhi}）你在财务结构上有过一次明显的「上台阶」——要么收入大幅跳档、要么第一次形成有规模的资产 / 项目{tail}",
    ("wealth", "down"):  "{age} 岁那年（{year} {ganzhi}）你在财务上经历过一段明显的「失血 / 损耗」期——大额支出、投资折损、或合作分裂带走资源{tail}",
    ("wealth", "shock"): "{age} 岁那年（{year} {ganzhi}）你的财务结构经历过一次剧烈震荡——既有得也有失，或先得后失（典型的'过手不留'）{tail}",
    ("fame",   "up"):    "{age} 岁那年（{year} {ganzhi}）你在外界眼中的「被看见度 / 职业地位」明显抬升——升职、被关注、或某项工作开始有外部评价{tail}",
    ("fame",   "down"):  "{age} 岁那年（{year} {ganzhi}）你在外界关注度上明显回落、或主动 / 被动从某个公开身份退下来{tail}",
    ("fame",   "shock"): "{age} 岁那年（{year} {ganzhi}）你的公开身份 / 职业角色经历过一次大切换{tail}",
    ("spirit", "up"):    "{age} 岁那年（{year} {ganzhi}）你的精神状态曾进入一段相对舒展 / 自洽 / 有「被看懂」感的时期{tail}",
    ("spirit", "down"):  "{age} 岁那年（{year} {ganzhi}）你的精神状态经历过一段明显的低潮——压抑、长期纠结、或与重要关系撕裂{tail}",
    ("spirit", "shock"): "{age} 岁那年（{year} {ganzhi}）你的内在世界经历过一次大震动——价值观重塑、长期挣扎的'断'，或某个关键身份的告别{tail}",
}

INTERACTION_TAIL = {
    "伏吟":   "（命理触发：伏吟，「旧事重演 / 必须直面同一类课题」）",
    "反吟":   "（命理触发：反吟天克地冲，「剧变 / 一翻一覆」）",
    "财库被冲开": "（命理触发：财库被冲开，「财务结构强制跳档」）",
    "冲日柱":  "（命理触发：冲日柱，「自身处境 / 居所 / 关系强制变动」）",
    "伤官见官": "（命理触发：伤官见官，「与权威 / 体制摩擦」）",
    "三合用神局": "（命理触发：三合用神成局，「大气运聚集」）",
    "三合忌神局": "（命理触发：三合忌神成局，「忌神大势」）",
    "通关":   "（命理触发：通关元素到位，「长期堵塞被疏通」）",
    "相穿":   "（命理触发：相穿，「明伤未必痛、暗里被磨」）",
    "三会":   "（命理触发：三会成方，「整段方向被同一气势主导」）",
}

DIM_LABEL = {"spirit": "精神", "wealth": "财富", "fame": "名声"}


# ---------- 本性画像 ----------

def build_signature_traits(bazi: dict) -> List[dict]:
    """从命局结构机械导出 ≤3 条本性画像候选，按清晰度排序。"""
    out: List[dict] = []
    dm = bazi["day_master"]
    strength_label = bazi["strength"]["label"]
    yongshen = bazi["yongshen"]["yongshen"]
    pillar_info = bazi["pillar_info"]
    yue_shishen = pillar_info[1]["gan_shishen"]

    if dm in GAN_TRAIT and yongshen in YONGSHEN_TRAIT:
        out.append({
            "category": "本性基底",
            "evidence": f"日主{dm}（{bazi['day_master_wuxing']}） + 用神{yongshen}",
            "claim": f"{GAN_TRAIT[dm]}。{YONGSHEN_TRAIT[yongshen]}",
            "falsifiability": "如果你觉得自己跟以上描述完全相反（比如戊土型却最享受'被人安排 + 没产出归属感'），这条就是错的",
            "score": 9.5,
        })

    if strength_label in STRENGTH_TRAIT:
        out.append({
            "category": "反应模式",
            "evidence": f"日主强弱={strength_label}（in_season={bazi['strength']['in_season']}）",
            "claim": STRENGTH_TRAIT[strength_label],
            "falsifiability": "回想 25–35 岁那段，如果你对环境匹配度的敏感程度 / 自主需求强度 与上面描述完全反向，这条就是错的",
            "score": 8.0 if strength_label in ("中和",) else 9.0,
        })

    if yue_shishen in YUE_SHISHEN_TRAIT:
        out.append({
            "category": "主导动力",
            "evidence": f"月柱={pillar_info[1]['gan']}{pillar_info[1]['zhi']}，月干十神={yue_shishen}",
            "claim": YUE_SHISHEN_TRAIT[yue_shishen],
            "falsifiability": "回顾你最有动力 / 最压不住的那个时期，如果驱动你前进的根本动机不是上面描述的那种，这条就是错的",
            "score": 8.5,
        })

    out.sort(key=lambda x: -x["score"])
    return out


# ---------- 健康三问（v3 R1 三个不同侧面） ----------

def _build_health_temperature(bazi: dict) -> Optional[dict]:
    """侧面 ① 寒热 / 出汗 —— 命局 climate.label 直接导出。"""
    climate = bazi.get("yongshen", {}).get("climate")
    if not climate:
        return None
    label = climate["label"]
    claim = HEALTH_TEMPERATURE.get(label)
    if not claim:
        return None
    falsif = HEALTH_TEMPERATURE_FALSIF.get(label, f"如果你的寒热体感与「{label}」反向 → 这条错")
    return {
        "category": "健康①·寒热出汗",
        "side": "temperature",
        "evidence": f"climate.label={label} · 干头分={climate['干头分']:+.1f} 地支分={climate['地支分']:+.1f}",
        "claim": claim,
        "falsifiability": falsif,
        "score": 9.9,
    }


def _build_health_sleep(bazi: dict) -> Optional[dict]:
    """侧面 ② 睡眠 / 精力 / 神经状态 —— climate × strength 组装。"""
    climate = bazi.get("yongshen", {}).get("climate")
    strength_label = bazi.get("strength", {}).get("label")
    if not climate or not strength_label:
        return None
    clabel = climate["label"]
    sleep_part = SLEEP_BY_CLIMATE.get(clabel)
    energy_part = ENERGY_BY_STRENGTH.get(strength_label)
    if not sleep_part and not energy_part:
        return None
    nerve_part = NERVE_BY_CLIMATE.get(clabel)

    parts: List[str] = []
    if sleep_part:
        parts.append(f"【睡眠】{sleep_part}")
    if energy_part:
        parts.append(f"【精力】{energy_part}")
    if nerve_part:
        parts.append(f"【神经】{nerve_part}")
    claim = "；".join(parts)

    # 三段任意一段反向都算"部分对" / "不对"
    falsif_bits = []
    if sleep_part:
        if "浅" in sleep_part or "早醒" in sleep_part or "入睡需要" in sleep_part:
            falsif_bits.append("如果你常年睡得很沉、入睡极快、不易早醒")
        elif "嗜睡" in sleep_part or "犯困" in sleep_part:
            falsif_bits.append("如果你常年入睡慢 / 睡眠浅 / 早醒")
        else:
            falsif_bits.append("如果你睡眠常年极不规律 / 极差")
    if energy_part:
        if "旺" in energy_part:
            falsif_bits.append("精力一向偏弱 / 易疲倦")
        elif "弱" in energy_part or "断电" in energy_part or "节奏" in energy_part:
            falsif_bits.append("精力一向极旺 / 撑得住长期高强度")
    falsif = "；".join(falsif_bits) + " → 这条错" if falsif_bits else "如果以上睡眠 / 精力描述与你完全反向 → 这条错"

    return {
        "category": "健康②·睡眠精力",
        "side": "sleep_energy",
        "evidence": f"climate={clabel} · strength={strength_label}",
        "claim": claim,
        "falsifiability": falsif,
        "score": 9.5,
    }


def _build_health_organ(bazi: dict) -> Optional[dict]:
    """侧面 ③ 易病脏腑 —— 五行最弱（含缺失）→ 对应脏腑系统。"""
    wx_dist = bazi.get("wuxing_distribution")
    if not wx_dist:
        return None
    weakest = bazi.get("weakest_wuxing")
    if not weakest or weakest not in ORGAN_BY_WUXING:
        return None
    info = ORGAN_BY_WUXING[weakest]
    is_missing = wx_dist[weakest]["missing"]
    score_val = wx_dist[weakest]["score"]
    ratio = wx_dist[weakest]["ratio"]

    miss_word = "原局缺" + weakest if is_missing else f"原局{weakest}最弱（占比 {ratio:.0%}）"
    claim = (
        f"你**易出问题的脏腑系统是「{info['name']}」**（{miss_word}）。"
        f"具体表现：{info['claim_tail']}"
    )

    return {
        "category": "健康③·脏腑短板",
        "side": "organ",
        "evidence": f"wuxing_distribution: {weakest}={score_val:.2f}（{'缺失' if is_missing else '最弱'}） · ratio={ratio:.0%}",
        "claim": claim,
        "falsifiability": info["falsif"],
        "score": 9.3,
    }


def build_health_triple(bazi: dict) -> List[dict]:
    """生成 R1 三个不同侧面的健康问题。返回顺序固定：温度 → 睡眠精力 → 脏腑。"""
    out: List[dict] = []
    for fn in (_build_health_temperature, _build_health_sleep, _build_health_organ):
        item = fn(bazi)
        if item is not None:
            out.append(item)
    return out


def build_physiology_traits(bazi: dict) -> List[dict]:
    """legacy 兼容：保留单条体质画像，供老调用方使用。"""
    item = _build_health_temperature(bazi)
    if item is None:
        return []
    item = dict(item)
    item["category"] = "体质画像（先天）"
    return [item]


# ---------- 过往锚点 ----------

def _direction_of(value: float, baseline: float) -> str:
    delta = value - baseline
    if delta >= 12:
        return "up"
    if delta <= -12:
        return "down"
    return "shock"


def _interaction_tail(interactions: List[dict]) -> str:
    if not interactions:
        return ""
    types = [i["type"] for i in interactions]
    for key in INTERACTION_TAIL:
        if key in types:
            return INTERACTION_TAIL[key]
    return f"（命理触发：{types[0]}）"


def build_historical_anchors(curves: dict, current_year: int, max_n: int = 4) -> List[dict]:
    """从已计算的 points 中挑历史段最高把握的 ≤max_n 条大波动。

    打分公式（越高越值得用作下马威）：
      score = deviation*1.5 + conf_score*4 - dispute_penalty*6
              + interaction_bonus + recency_bonus + life_stage_bonus
    """
    points = curves["points"]
    baselines = curves["baseline"]
    history = [p for p in points if p["year"] < current_year and p["age"] >= 6]
    if not history:
        return []

    candidates = []
    for p in history:
        for dim in ("spirit", "wealth", "fame"):
            v = p[f"{dim}_yearly"]
            base = baselines[dim]
            deviation = abs(v - base)
            if deviation < 8:
                continue

            conf = p["confidence"][dim]
            conf_score = {"high": 2, "mid": 1, "low": 0}[conf]
            dispute_penalty = 1 if dim in p.get("disputed_dimensions", []) else 0

            interactions = p["interactions"]
            high_intensity = {"伏吟", "反吟", "冲日柱", "财库被冲开", "三合用神局", "三合忌神局", "伤官见官"}
            interaction_bonus = 5 if any(i["type"] in high_intensity for i in interactions) else (
                2 if interactions else 0
            )

            # 盲派事件加成：含盲派"重"烈度事件 +8，含"中"烈度 +4
            mp_events = p.get("mangpai_events", [])
            mp_bonus = 0
            for ev in mp_events:
                if ev.get("intensity") == "重":
                    mp_bonus = max(mp_bonus, 8)
                elif ev.get("intensity") == "中":
                    mp_bonus = max(mp_bonus, 4)

            years_ago = current_year - p["year"]
            recency_bonus = max(0, 5 - years_ago // 4)

            age = p["age"]
            life_stage_bonus = 3 if 25 <= age <= 45 else (
                2 if (10 <= age < 25 or 45 < age <= 60) else 0
            )

            score = (
                deviation * 1.5
                + conf_score * 4
                - dispute_penalty * 6
                + interaction_bonus
                + recency_bonus
                + life_stage_bonus
                + mp_bonus
            )

            candidates.append({
                "year": p["year"],
                "age": age,
                "ganzhi": p["ganzhi"],
                "dayun": p["dayun"],
                "dim": dim,
                "value": v,
                "baseline": base,
                "deviation": round(deviation, 1),
                "direction": _direction_of(v, base),
                "confidence": conf,
                "interactions": interactions,
                "mangpai_events": mp_events,
                "_score": score,
            })

    candidates.sort(key=lambda x: -x["_score"])

    chosen: List[dict] = []
    used_years: set = set()
    used_dims: dict = {}
    for c in candidates:
        if len(chosen) >= max_n:
            break
        if c["year"] in used_years:
            continue
        # 优先让维度铺开：每个维度先保证 1 条再考虑第 2 条
        if used_dims.get(c["dim"], 0) >= 1 and len(used_dims) < 3:
            continue
        # 同维度至多 2 条（避免 4 条全是 wealth）
        if used_dims.get(c["dim"], 0) >= 2:
            continue
        chosen.append(c)
        used_years.add(c["year"])
        used_dims[c["dim"]] = used_dims.get(c["dim"], 0) + 1

    out = []
    for c in chosen:
        # 优先用盲派事件文案（最具体、最可证伪），无盲派事件再退回三派 interaction tail
        mp_events = c.get("mangpai_events", [])
        mp_high = [e for e in mp_events if e.get("intensity") == "重"]
        mp_pick = mp_high[0] if mp_high else (mp_events[0] if mp_events else None)

        tail = _interaction_tail(c["interactions"])
        tpl = ANCHOR_CLAIM_TPL.get((c["dim"], c["direction"]))
        if not tpl:
            continue
        claim = tpl.format(age=c["age"], year=c["year"], ganzhi=c["ganzhi"], tail=tail)

        if mp_pick:
            # 盲派应事更具体，附在 claim 之后
            claim = (
                claim
                + f"\n   盲派应事（{mp_pick['school']} · {mp_pick['name']}）："
                + mp_pick["canonical_event"]
            )
            falsifiability = mp_pick["falsifiability"]
        else:
            falsifiability = (
                f"如果在 {c['year']}±1 年那段，你的{DIM_LABEL[c['dim']]}维度并没有出现"
                f"上述方向的明显波动（既无明显变好也无明显变差），这条就是错的"
            )

        evidence_parts = [
            f"{c['year']} {c['ganzhi']} · 大运 {c['dayun']} · "
            f"{DIM_LABEL[c['dim']]}={c['value']}（基线 {c['baseline']}，偏离 {c['deviation']}） · "
            f"置信度={c['confidence']}"
        ]
        if c["interactions"]:
            evidence_parts.append(f"三派互动={','.join(i['type'] for i in c['interactions'])}")
        if mp_pick:
            evidence_parts.append(f"盲派触发={mp_pick['evidence']}")
        evidence = " · ".join(evidence_parts)

        out.append({
            "category": "过往大波动" + ("（盲派应事）" if mp_pick else ""),
            "year": c["year"],
            "age": c["age"],
            "ganzhi": c["ganzhi"],
            "dim": c["dim"],
            "direction": c["direction"],
            "evidence": evidence,
            "claim": claim,
            "falsifiability": falsifiability,
            "mangpai_event": mp_pick,
            "internal_score": round(c["_score"], 2),
        })
    return out


# ---------- 组装 ----------

LLM_INSTRUCTION = """\
按【三阶段 / 最多 8 条 = R0 反询问 2 + R1 健康 3 + R2 交叉 3】校验流程把脚本给的候选转述给用户，不允许添加候选数据中没有的事实。
顺序固定：先 R0（反询问·感情画像）→ 再 R1（健康三问）→ R1 不达标才 R2。

== Round 0（反询问·感情画像，v6 新增 · **最先抛**）==
取 round0_candidates 里的 2 条（①偏好类型 + ②对方态度）。
**这是"反询问窗口"**——主动把感情类问题抛给用户，用于：
  · 校准八字大致对/不对（感情记忆是用户最深刻、最难骗的事件记忆）
  · 协助判断命局取向（走格局派还是扶抑派 / 是否需要调候）

输出模板（必须严格按此格式）：
----
开始之前先问你两个感情相关的问题——这两题不评判 / 不打标签，只用来快速判断你的八字大概率"对/不对"，
以及该按哪种取向（格局 / 扶抑 / 调候）来给你解。请凭直觉答「对 / 不对 / 部分」。

⓪-① 【{round0[0].category}】{round0[0].claim}
   依据：{round0[0].evidence}
   可证伪点：{round0[0].falsifiability}

⓪-② 【{round0[1].category}】{round0[1].claim}
   依据：{round0[1].evidence}
   可证伪点：{round0[1].falsifiability}
----

R0 命中 → 取向准确度：
  · 2/2 → 命局取向无悬念，按 geju 主格局 / 主流扶抑直接走
  · 1/2 → 取向部分对，做分析时主动告诉用户"配偶星 / 配偶宫读法存在歧义，X 段可能更符合 [另一种取向]"
  · 0/2 → **配偶星 / 配偶宫读法可能反了**，常见原因：性别输错 / 时辰错 / 八字本身不准 → 立刻提醒用户复核

R0 完成后**不论命中几条**都继续 R1（R0 只是取向校准，R1 才是命局结构校准）。
两层都过（R0 ≥ 1/2 + R1 ≥ 2/3）才允许进 Step 2.7（询问输出格式）。

== Round 1（首轮 3 条 = 三个不同侧面的健康问题，v3 改版）==
取 round1_candidates 里的 3 条，固定顺序为：
  ① 健康①·寒热出汗（temperature） —— 命局 climate 直接导出
  ② 健康②·睡眠精力（sleep_energy）—— climate × strength 组装
  ③ 健康③·脏腑短板（organ）       —— 五行最弱 → 对应脏腑

输出模板（必须严格按此格式）：
----
在画图 / 合盘之前，我先用 3 个不同侧面的「健康/体感」问题来校验一下八字的准确度。
**请逐条回 「对 / 不对 / 部分」**。这三条都是终生稳定的体感证据，最不容易自欺。
（命中率 → 准确度：3/3 高 → 直接进下一步；2/3 中 → 我再给你 3 条交叉验证；
  ≤ 1/3 低 → 八字十有八九不准，请核对出生时辰）

① 【{round1[0].category}】{round1[0].claim}
   依据：{round1[0].evidence}
   可证伪点：{round1[0].falsifiability}

② 【{round1[1].category}】{round1[1].claim}
   依据：{round1[1].evidence}
   可证伪点：{round1[1].falsifiability}

③ 【{round1[2].category}】{round1[2].claim}
   依据：{round1[2].evidence}
   可证伪点：{round1[2].falsifiability}
----

== Round 2（追问 3 条，仅在 Round 1 命中 < 3 时触发）==
取 round2_candidates 里的 3 条（本性画像 + 历史大波动），覆盖 R1 没出现过的维度：
----
为了把八字校验得更扎实，我再给你 3 条交叉验证。请继续回「对 / 不对 / 部分」。
两轮合计命中 ≥ 4/6 → 进入下一步；< 4 → 八字十有八九不准（多半是时辰偏 1 小时）。

④ ...   ⑤ ...   ⑥ ...
----

== Round 3（反询问·原生家庭画像 2 题，v7.3 新增 · **条件触发**）==
取 round3_candidates 里的 2 条（①整体家庭结构 + ②父母存在模式合并）。

**触发时机**（重要 · 默认 NOT 触发，避免无关问题打扰用户）：
- ✓ 用户在初次提问中提到「家庭 / 父母 / 父亲 / 母亲 / 原生家庭 / 出身 / 家世 / 我爸 / 我妈」等关键词 → **必须抛 R3**
- ✓ 用户在分析过程中追问「我家怎么样 / 我爸是什么样 / 我妈呢」 → **必须抛 R3**（在写 family 段之前）
- ✗ 用户没主动问家庭 → **不要抛 R3**（不写 family 段也不会缺胳膊少腿）

**抛 R3 的位置**：在 R0 之后、R1 之前；或在 R1/R2 通过后、写 family 段之前。
不要把 R3 跟 R0/R1 混在一组里抛——R3 是独立的"原生家庭专项校验"。

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
  · 2/2 → 高置信，按 primary_class 展开（比如真显赫候选 + 用户确认 → 可以谨慎说"父辈/祖辈中可能有人在某领域有可识别的位置"）
  · 1/2 → 中置信，命中那条可展开；未命中那条标"取向歧义"或省略
  · 0/2 → 低置信，**family 段不展开具体内容**，只写一句"原生家庭推断未通过校验，本次不展开（命局对家庭的读法可能反了）"

R3 红线（v7.3 新增）：
  ★ 若【原生家庭①·整体结构】被标"不对"且 primary_class = illustrious_candidate
    → 这是 LLM 最容易翻车的场景（古法 survivorship bias 推过头，把"年柱财官印聚合"
       当成了"显赫家世"）→ family 段必须降级、**禁用**"显赫 / 名门 / 名利双收"等措辞
  ★ 若【原生家庭②·父母存在模式】两条都被标"不对"
    → 父星 / 母星读法多半反了 → family 段直接省略

R3 命中级别和 R0/R1 校验是**正交**的（R3 不算入命局准确度，仅决定 family 段写不写 / 怎么写）。

family 段写作必须遵守 fairness_protocol.md §11（原生家庭解读铁律）：
- 必须援引 R3 命中（"R3 = 2/2 → 高置信展开"）
- 必须前置声明（"命局只反映父母在你能量场里的存在模式，不反映社会地位 / 职业 / 学历 / 是否健在"）
- 禁用措辞清单：参考 §11.2

== 命中率 → 准确度判定（必须严格执行 · v6 改双层）==

第一层 · 取向准确度（R0）：
| R0 命中 | 取向 grade | 后续 |
|---|---|---|
| 2/2 | high  | 命局取向无悬念，按主流派系（geju 主格局 / 经典扶抑）直接走 |
| 1/2 | mid   | 取向部分对，分析时主动注明"在 X 处取向有歧义" |
| 0/2 | low   | 配偶星 / 配偶宫读法可能反了 → 提醒用户复核性别 / 时辰，**仍继续 R1** |

第二层 · 命局准确度（R1）：
| R1 命中  | accuracy_grade | 后续动作 |
|---|---|---|
| 3/3      | high           | 若 R0 ≥ 1/2 → 直接进 Step 2.7；R0 = 0 → 进但加强 caveat |
| 2/3      | mid            | 触发 Round 2；R1+R2 ≥ 4/6 → 继续，加 caveat；< 4/6 → 停 |
| 1/3      | low            | 触发 Round 2；R1+R2 ≥ 4/6 → 谨慎继续 + 强 caveat；< 4/6 → 停 |
| 0/3      | reject         | 不再追问，强烈建议核对八字本身（时辰多半错） |

**整体放行条件**：R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6）。
**整体拒绝条件**：R0 = 0/2 且 R1 ≤ 1/3 → 八字大概率不准（最常见：性别输错 / 时辰差 1 小时）→ 让用户复核后再来。

== 红线规则（v3 调整）==
★ 若【健康①·寒热出汗】被用户标 "✗"：
  → climate.label 多半判错了，**不论其他几条命中率都要先停下**，
    告诉用户："寒热体感没对上 → climate 判读可能反了 → 我需要重新审视命局结构再给你跑一遍"。
  → 不要绕过这一条直接进下一步。

★ 若【健康③·脏腑短板】被用户标 "✗"：
  → 五行权重多半算偏了（常见于时辰错导致月柱 / 时柱跳位），需重核八字。

★ 若【感情①·偏好类型】被用户标 "✗" 且 R1 命中 ≤ 1/3：
  → 配偶星五行 / 性别 多半弄错了（最常见：性别字段输错、或时辰跳位导致月柱财官位置变动），**立即停下**，
    告诉用户："感情偏好和健康两层都不对 → 八字基础数据有较大概率不准 → 建议你先核对（1）性别 是否正确（2）出生时辰 是否准确"。

== 合盘场景特别说明 ==
- 用户输入多份八字做合盘时，**每份八字都要单独跑 R0 + R1**。
- R0 在合盘中**只对用户自己的八字问**（用户对对方的感情史不一定知道——除非是夫妻 / 直系家人，且用户主动承担作答）。对方八字仅跑 R1（健康三问可由用户代答 / 凭对对方的了解作答）。
- 只有自己 R0+R1 通过 + 对方 R1 ≥ 2/3 的组合才进合盘评分；任何一方不达 → caveat 或退回让用户复核。
- 用户对自己的八字答得最准；对配偶 / 合伙人的八字若答不上来 → 注明"对方信息不全，合盘结论降权"。

== 校验通过 → 进入 Step 2.7（询问输出格式）== v5 强制
R1（或 R1+R2）通过后**绝对不要直接进 Step 3 渲染 HTML**，先主动问用户：

----
校验通过 ✓。在我开始写分析之前，问一下你想要哪种输出：

(A) 纯 markdown 流式输出 —— 我每写完一节就立刻发给你，最快、最适合手机 / 复制 / 转发
(B) markdown 流式 + 最后渲染 HTML 交互图 —— 多等 5-15 秒，可以鼠标 hover 查看每年详情、details 折叠

回 A 或 B（默认 A）。
----

默认值：单盘默认 A；合盘默认 A（合盘没有"曲线图"刚需 HTML）。
若用户初次提问已说"画图 / 出 artifact / 给我图" → 直接走 B；说"口头说说 / 不用图" → 直接走 A。

== Step 3a 必须流式分节输出（v5 硬要求 · v6 加感情维度）==
无论 A / B，所有文字分析必须**按节流式输出**：每写完一节立刻发出，**禁止**把整段憋到末尾一次性吐。
节序：整图综合分析 → 一生**四**维度（精神 → 财富 → 名声 → **感情**）→ 大运评价（每段 1 节，含感情看点）→ 关键年份（每条 1 节）。
每节用 markdown 标题（## 整图综合分析 / ## 一生 · 感情 / ## 大运评价 · 辛丑（25-34 岁）/ ## 关键年份 · 2031 等）。
**感情维度的内容来源**：R0 你已经验证过用户的"偏好类型 + 对方态度"，写感情段时必须援引 R0 的命中情况
（例如："你 R0 验证了喜欢[木]型 + 对方常主动 → 那么大运走 火 / 木 时感情更顺，走 金 / 水 时易冷淡 / 暧昧"）。
HTML 渲染（仅 B）放最后一步，此时用户已读完文字，不再有"等图"焦虑。

数据不足时（脚本只挑出 N < 6 条），如实输出 N 条并告知用户"脚本只挑出 N 条不强行凑"。
"""


PHASE_RERUN_HINTS = {
    "floating_dms_to_cong_cai": (
        "弃命从财（日主虚浮 → 财星主事）。"
        "你的命局可能不是「日主当家用印比帮身」，而是「日主无根 → 跟着旺财走」。"
        "现实表现：早年/全程**靠他人/外部资源借力**，自我能量薄但善于借势；财运是命局主旋律，单打独斗反而吃力。"
    ),
    "floating_dms_to_cong_sha": (
        "弃命从杀（日主虚浮 → 官杀主事）。"
        "你不是「身弱被官杀压」，而是「日主无根 → 全力顺从权威/制度/规则」。"
        "现实表现：在体系/职场/规则压力下反而出状态；自由职业反而焦虑；适合服务大平台或高强度系统。"
    ),
    "floating_dms_to_cong_er": (
        "弃命从儿（日主虚浮 → 食伤主事）。"
        "命局走「我生」方向 —— 不是日主自身在表达，而是用自己的输出/作品/孩子/造物来定义自己。"
        "现实表现：表达欲/创作欲/生育欲是命局主旋律，压住表达 = 全身憋屈。"
    ),
    "floating_dms_to_cong_yin": (
        "弃命从印（日主虚浮 → 印主事）。"
        "命局走「生我」方向 —— 你不是自立型，而是被庇护型，靠学历/母系/老师/宗教/上司护身。"
        "现实表现：脱离庇护就乏力，背靠组织反而强；越读书/越被重视越好。"
    ),
    "dominating_god_cai_zuo_zhu": (
        "旺神得令·财星主事。日主有根但财星压主 —— **财星才是命局主角**，日主只是承接者。"
        "现实表现：人生主线就是「跟钱/资源/物质打交道」，而非「修身立志」式的传统读法。"
    ),
    "dominating_god_guan_zuo_zhu": (
        "旺神得令·官杀主事。**官杀是命局主角**，日主在其压制 / 调用之下运转。"
        "现实表现：天然适合在权威/上下级/竞争系统里运转，自由职业易心慌。"
    ),
    "dominating_god_shishang_zuo_zhu": (
        "旺神得令·食伤主事。**食伤是命局主角**，日主泄秀。"
        "现实表现：表达/输出 = 主旋律，压住表达 = 命局错位。"
    ),
    "dominating_god_yin_zuo_zhu": (
        "旺神得令·印星主事。**印是命局主角**，日主被庇护。"
        "现实表现：依附型 / 学者型 / 学生型 / 母系或体系庇护型。"
    ),
    "climate_inversion_dry_top": (
        "调候反向·上燥下寒。表面看是寒湿命（月令子水/亥水等），但天干一片燥火土 —— "
        "**真正主导你体感和性格的是天干的燥**，不是地支的寒。"
        "现实表现：自小怕热不怕冷 / 性格急躁 / 需要水来润降；用神锁水（不是按身弱用火）。"
    ),
    "climate_inversion_wet_top": (
        "调候反向·上湿下燥。表面看是燥实命，但天干一片寒湿 —— "
        "**真正主导是天干的寒**，不是地支的火。"
        "现实表现：自小怕冷不怕热 / 内里有暗火急躁；用神锁火。"
    ),
    "true_following": (
        "真从格。日主有微根但根被冲合破坏，整体气势从旺神而走。"
        "现实表现：跟从势类相同，但置信度更高（已校验微根被破）。"
    ),
    "pseudo_following": (
        "假从格。日主有微根，看起来像从但其实根稳。"
        "现实表现：仍按弱身扶身读，但要加 caveat —— 大运若顺从神方向，按从势补充读。"
    ),
}


def dump_phase_candidates(bazi: dict, hit_rate_default: Optional[str] = None) -> dict:
    """v7 P1-7 · 当 R0+R1 命中率 ≤ 2/6 时，dump 4 类相位反演候选 + 重跑指令。

    详见 references/phase_inversion_protocol.md §4.3

    输入：
        bazi: bazi.json 解析后的 dict
        hit_rate_default: 当前默认相位的命中率（如 '2/6'），仅用于在输出里记录

    输出：
        {
            "default_hit_rate": ...,
            "phase_candidates": [
                {phase_id, label, evidence, llm_explain, rerun_command}, ...
            ],
            "llm_instruction": "..."
        }
    """
    import _bazi_core as bc

    detection = bc.detect_all_phase_candidates(bazi)
    bazi_path_hint = "<bazi.json>"

    candidates_out: List[dict] = []
    for det in detection["triggered_candidates"]:
        sp = det["suggested_phase"]
        if sp == "day_master_dominant":
            continue
        candidates_out.append({
            "phase_id": sp,
            "phase_label": det.get("suggested_label", ""),
            "from_detector": det["phase_id"],
            "detector_score": det.get("score", ""),
            "evidence": det["evidence"],
            "llm_explain_for_user": PHASE_RERUN_HINTS.get(
                sp, f"反演为 {sp}，详见 phase_inversion_protocol.md"
            ),
            "rerun_command": (
                f"python scripts/score_curves.py --bazi {bazi_path_hint} "
                f"--out <out>/curves_phase_inverted.json --override-phase {sp}"
            ),
        })

    return {
        "version": 1,
        "purpose": "P1-7 相位反演候选（R 命中率 ≤ 2/6 时供 LLM 选择重跑用）",
        "default_hit_rate": hit_rate_default,
        "default_phase": "day_master_dominant",
        "default_phase_label": "默认 · 日主主导（用神 + 扶抑 + 调候）",
        "n_triggered": detection["summary"]["n_triggered"],
        "phase_candidates": candidates_out,
        "all_detection_details": detection["all_detection_details"],
        "llm_instruction": (
            "【强制】R0+R1 命中率 ≤ 2/6 时，**不要**直接判定「八字错 / 时辰错」。"
            "先按 phase_candidates 顺序，跟用户说：「命中率比较低，但这不一定意味着八字错。"
            "另一种常见可能是『算法读法方向反了』。我有 N 个反向假设，最有希望的是 X，"
            "因为 [evidence]。要不要按 X 重跑一次？」"
            "用户同意 → 按 rerun_command 跑 → 重新生成 R0/R1 候选 → 重新匹配命中率。"
            "若全部相位重跑后仍 < 4/6 → 此时才真正判定八字错。"
            "详见 references/phase_inversion_protocol.md §5"
        ),
    }


def apply_phase_to_bazi(bazi: dict, phase_id: str) -> dict:
    """v7.2 · 把 score_curves.apply_phase_override 的结果反映到 bazi 上，供 handshake 按新相位生成问题。

    这是「相位反演二轮校验」的关键：phase 反演后，命局的 strength.label / yongshen /
    climate 都已经变了，因此 R0（感情画像）、R1（健康三问）的文案也应该按**新相位**重新生成，
    再让用户答一遍 → 看新命中率有没有 ≥ 4/6（达标 → 真落地；不达标 → 换候选 / 核对时辰）。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import score_curves as sc
    return sc.apply_phase_override(bazi, phase_id)


def build_family_pair(bazi: dict) -> List[dict]:
    """v7.3 · R3 反询问·原生家庭画像 2 题。

    委托给 family_profile.build_family_profile() 然后只取 round3_candidates。
    若加载失败（缺脚本 / bazi 字段不全）→ 返回空 list（R3 是可选的，不影响 R0/R1/R2）。
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import family_profile as fp
        result = fp.build_family_profile(bazi)
        return result.get("round3_candidates", [])
    except Exception as e:
        print(f"[handshake] WARN: build_family_pair failed ({e}); R3 skipped", file=sys.stderr)
        return []


def build(bazi: dict, curves: dict, current_year: int, phase_id: Optional[str] = None) -> dict:
    if phase_id and phase_id != "day_master_dominant":
        bazi = apply_phase_to_bazi(bazi, phase_id)
        # 同步 curves 里的 strength / yongshen 字段（curves 在 score_curves --override-phase 跑过时本来就反演了，
        # 这里兜底：如果用户传的是默认 curves，至少健康三问会按新相位走）
        if "strength" in bazi:
            curves = dict(curves)
            curves["strength"] = bazi["strength"]
        if "yongshen" in bazi:
            curves = dict(curves)
            curves["yongshen"] = bazi["yongshen"]
    traits = build_signature_traits(bazi)
    anchors = build_historical_anchors(curves, current_year, max_n=4)
    health_triple = build_health_triple(bazi)  # v3 R1 = 健康三问
    emotion_pair = build_emotion_pair(bazi)    # v6 R0 = 反询问·感情画像 2 题
    family_pair = build_family_pair(bazi)      # v7.3 R3 = 反询问·原生家庭画像 2 题

    # Round 0: 反询问·感情画像 2 题（v6 新增）—— 最先抛给用户
    # 校验"事件取向"是否符合命局结构 + 协助判断"该走格局派还是扶抑派"
    round0: List[dict] = list(emotion_pair[:2])

    # Round 3: 反询问·原生家庭画像 2 题（v7.3 新增 · 条件触发 · 默认仅在用户问家庭/父母时抛）
    # 注意 R3 的编号是 ③ 但生成时机是「在 R0 之后、R1 之前」or「仅当用户主动问家庭」
    # （编号沿用是为了和 emotion ⓪ / health ① ② ③ 区分）
    round3: List[dict] = list(family_pair[:2])

    # Round 1: 三个不同侧面的健康问题（固定顺序：温度 → 睡眠精力 → 脏腑）
    round1: List[dict] = list(health_triple[:3])

    # 若健康三问凑不齐 3 条（极少数缺数据情形），用 traits / anchors 凑数
    if len(round1) < 3:
        for t in traits:
            if len(round1) >= 3:
                break
            round1.append(t)
        for a in anchors:
            if len(round1) >= 3:
                break
            round1.append(a)

    # Round 2: 1 本性 + 2 锚点（旧逻辑保留，作为交叉验证）
    round2: List[dict] = []
    if traits:
        round2.append(traits[0])
    for a in anchors[:2]:
        round2.append(a)
    # 若仍 < 3，从剩余 traits 补
    if len(round2) < 3 and len(traits) > 1:
        for t in traits[1:]:
            if len(round2) >= 3:
                break
            round2.append(t)
    if len(round2) < 3 and len(anchors) > 2:
        for a in anchors[2:]:
            if len(round2) >= 3:
                break
            round2.append(a)

    return {
        "version": 7,
        "current_year": current_year,
        "pillars_str": curves["pillars_str"],
        "day_master": curves["day_master"],
        "strength_label": curves["strength"]["label"],
        "yongshen": curves["yongshen"]["yongshen"],
        "climate_label": curves["yongshen"].get("climate", {}).get("label"),
        "weakest_wuxing": bazi.get("weakest_wuxing"),
        "qiyun_age": curves.get("qiyun_age"),
        "geju": curves.get("geju", {}),
        "phase": bazi.get("phase") or curves.get("phase") or {
            "id": "day_master_dominant", "label": "默认 · 日主主导", "is_inverted": False,
        },
        "round0_candidates": round0,
        "round1_candidates": round1,
        "round2_candidates": round2,
        "round3_candidates": round3,
        "candidates_chosen": round0 + round1 + round2 + round3,
        "candidates_pool": {
            "emotion_pair": emotion_pair,
            "health_triple": health_triple,
            "signature_traits": traits,
            "historical_anchors": anchors,
            "family_pair": family_pair,
        },
        "selection_rule": (
            "Round 0 = 反询问·感情画像（v6 新增，2 题：①偏好类型 + ②对方态度），"
            "在最开始抛给用户做「取向校准」——验证八字大致对/不对 + 协助判断走格局派还是扶抑派；"
            "Round 1 = 三个不同侧面的健康问题（固定：①寒热出汗 + ②睡眠精力 + ③脏腑短板），全部从命局静态结构导出；"
            "Round 2 = 1 本性 trait + 2 历史锚点（用作交叉验证）。"
            "Round 3 = 反询问·原生家庭画像（v7.3 新增，2 题：①整体家庭结构 + ②父母存在模式合并）—— "
            "**条件触发**：仅在用户主动问 family / 父母 / 家庭 / 出身 等关键词时抛；"
            "正交于 R0/R1/R2（不算入命局准确度），仅用于决定 family 段写不写 / 怎么写。"
            "若健康三问缺数据（< 3 条）→ 由 traits / anchors 补足 R1；"
            "本性 traits 按 (基底 → 反应模式 → 主导动力) 顺序；"
            "锚点 anchors 按 (deviation*1.5 + conf*4 - dispute*6 + interaction_bonus + recency_bonus + life_stage_bonus + mp_bonus) 排序。"
        ),
        "accuracy_grading": {
            "rule": (
                "v6 改版：分两层判定。"
                "（一）取向准确度 = R0 命中数（满分 2）：2/2 取向高（命局结构 + 用户事件高度一致）；"
                "1/2 取向中（部分对，可能要在格局/扶抑取向上做选择）；0/2 取向低（八字大概率不准 / 或者你对自己感情认知偏差大）。"
                "（二）命局准确度 = R1 命中数（满分 3）：3/3 高、2/3 中、≤1/3 低。"
                "整体放行：R0 ≥ 1/2 且 R1 ≥ 2/3 → 进；R1 < 2/3 → 走 R2 凑 ≥ 4/6；"
                "R0 = 0 + R1 ≤ 1 → 强烈建议核对时辰 / 性别。"
            ),
            "high":   "直接进入下一步（绘图 / 合盘评分）",
            "mid":    "触发 Round 2；R1+R2 合计 ≥ 4/6 继续 + 加 caveat",
            "low":    "触发 Round 2；R1+R2 合计 ≥ 4/6 谨慎继续 + 强 caveat",
            "reject": "不再追问，强烈建议核对八字本身（时辰多半错）",
        },
        "pass_threshold": {
            "round0": "命中 ≥ 1/2 → 取向 OK；2/2 → 命局取向无悬念（格局/扶抑可直接按主流派走）；0/2 → 配偶星 / 配偶宫读法可能反了，停下重审日支 + 配偶星（也常见于性别 / 时辰输错）",
            "round1": "命中 ≥ 2/3 → 通过；命中 3/3 → 可跳过 Round 2 直接进入下一步",
            "round2": "Round 1 + Round 2 合计命中 ≥ 4/6 → 进入下一步；否则视为八字不准（强烈建议核对时辰）",
            "round3": (
                "v7.3 新增 · R3 命中 → 决定 family 段写不写 / 怎么写："
                "2/2 → 高置信展开（按 primary_class）；"
                "1/2 → 命中那条可展开、未命中那条省略或标「取向歧义」；"
                "0/2 → family 段不展开具体内容，只写一句「原生家庭推断未通过校验，本次不展开」。"
                "R3 与 R0/R1/R2 正交，不算入命局准确度。"
                "**触发条件**：仅在用户主动问 family / 父母 / 家庭 / 出身 等关键词时抛 R3。"
            ),
            "red_line_temperature": "★ 健康①·寒热出汗 ✗ → climate 判读多半反了，停下重判命局结构",
            "red_line_organ": "★ 健康③·脏腑短板 ✗ → 五行权重多半算偏，停下重核八字（常见于时辰错）",
            "red_line_emotion_preference": "★ 感情①·偏好类型 ✗ 且 R1 也 ≤ 1/3 → 八字大概率不准（最常见是性别 / 时辰输错），停下复核",
            "red_line_family_illustrious_miss": (
                "★ v7.3 新增 · 原生家庭①·整体结构标「不对」且 primary_class = illustrious_candidate "
                "→ 这是 LLM 最容易翻车的场景（古法 survivorship bias 推过头）"
                "→ family 段必须降级、禁用「显赫 / 名门 / 名利双收」等措辞，"
                "改写为「年/月柱财官印聚合的结构在你身上没有外显为『资源 / 名望』，"
                "结构性画像被现代环境改写了」。"
            ),
            "red_line_family_parents_both_miss": (
                "★ v7.3 新增 · 原生家庭②·父母存在模式两条都标「不对」"
                "→ 父星 / 母星读法多半反了 → family 段直接省略，"
                "告知用户「父母存在模式校验未通过」"
            ),
        },
        "qixiang_decision_hint": {
            "格局可信":   "R0 ≥ 1/2 + 命局成格 → 优先按 geju 主格局取用神（格局派）",
            "扶抑可信":   "R0 ≥ 1/2 + 命局未明显成格 → 走经典扶抑（按 strength 调用神）",
            "调候优先":   "R0 ≥ 1/2 + climate.label ∈ {燥实, 寒湿} → 调候用神优先于格局/扶抑",
            "三派分歧大": "R0 = 0 + R1 = 2/3 + climate ∈ {外燥内湿, 外湿内燥} → 取向上保留双解，不强行二选一",
        },
        "instruction_for_llm": LLM_INSTRUCTION,
    }


def main():
    ap = argparse.ArgumentParser(description="生成出图前的下马威候选 (handshake.json)")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--curves", required=False, default=None,
                    help="curves.json 路径（默认模式必须；--dump-phase-candidates 模式可不填）")
    ap.add_argument("--current-year", type=int, default=None,
                    help="当前公历年（用于挑选历史段锚点；默认 today.year）")
    ap.add_argument("--out", default="handshake.json", help="输出路径")
    ap.add_argument("--dump-phase-candidates", action="store_true",
                    help="v7 P1-7 模式 · 不生成 R0/R1/R2 候选，而是 dump 4 类相位反演候选 + LLM 重跑指令；"
                         "用于 R0+R1 命中率 ≤ 2/6 时让 LLM 选反向假设重跑 score_curves。"
                         "详见 references/phase_inversion_protocol.md")
    ap.add_argument("--default-hit-rate", default=None,
                    help="（仅 --dump-phase-candidates 模式）当前默认相位的命中率，如 '2/6'，仅用于记录在输出里")
    ap.add_argument("--phase-id", default=None,
                    help="v7.2 · 「相位反演二轮校验」专用 · 按指定 phase_id 反演 bazi 后再生成 R0/R1/R2 候选；"
                         "用户对二轮的命中率 ≥ 4/6 → 真落地（写 confirmed_facts.phase_override）；"
                         "< 4/6 → 换下一个候选 / 或建议核对时辰。"
                         "phase_id 取值同 score_curves.py --override-phase。")
    args = ap.parse_args()

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))

    if args.dump_phase_candidates:
        result = dump_phase_candidates(bazi, hit_rate_default=args.default_hit_rate)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        n_cand = len(result["phase_candidates"])
        print(f"[handshake] phase-dump → {args.out}: {n_cand} 个相位反演候选 ↓")
        for c in result["phase_candidates"]:
            print(f"  · {c['phase_id']}  ({c['from_detector']}, score={c['detector_score']})")
            print(f"      → {c['phase_label']}")
        if n_cand == 0:
            print("  （无候选触发：默认相位算法没识别出明显的反向可能性。"
                  "命中率低更可能是八字本身错 / 时辰错，建议核对原始输入。）")
        return

    if not args.curves:
        ap.error("--curves is required unless --dump-phase-candidates is set")

    cy = args.current_year or dt.date.today().year
    curves = json.loads(Path(args.curves).read_text(encoding="utf-8"))
    result = build(bazi, curves, cy, phase_id=args.phase_id)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    phase_msg = ""
    if args.phase_id and args.phase_id != "day_master_dominant":
        ph = result.get("phase", {})
        phase_msg = f" · 已按相位反演 [{args.phase_id}] ({ph.get('label')}) 重生成 6 题用作二轮校验"
    n_r3 = len(result.get("round3_candidates", []))
    r3_part = f" + R3={n_r3}（条件触发 · 仅在用户问家庭时抛）" if n_r3 else ""
    print(f"[handshake] wrote {args.out}: "
          f"R0={len(result['round0_candidates'])} + R1={len(result['round1_candidates'])} + R2={len(result['round2_candidates'])}"
          f"{r3_part} "
          f"(of {len(result['candidates_pool']['emotion_pair'])} emotion + "
          f"{len(result['candidates_pool']['signature_traits'])} traits + "
          f"{len(result['candidates_pool']['historical_anchors'])} anchors + "
          f"{len(result['candidates_pool'].get('family_pair', []))} family)"
          f"{phase_msg}")


if __name__ == "__main__":
    main()
