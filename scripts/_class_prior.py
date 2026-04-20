#!/usr/bin/env python3
"""_class_prior.py — 从 bazi.json 推导命主的"阶级 prior"分布

⚠️ 重要伦理约束（详见 references/class_inference_ethics.md）：

  本模块输出的 class_prior 只是 LLM 的**内部思维材料**，
  **绝不允许**以阶级名词的形式出现在用户可见输出里。

  - 输出字段名虽然叫 "class_prior" 等，但它们仅描述"成长环境的可能形态"
  - 6 个 class tag 是给 LLM 内部 reasoning 用的范畴
  - LLM 在写文本时必须按 class_inference_ethics.md §3 替换字典转译

输入：bazi.json（含 pillar_info / strength / yongshen / dayun / day_master_wuxing）
输出：dict 含：
  - distribution: dict[class_tag → probability]
  - primary_class: 概率最高的 tag
  - evidence: list[str] LLM 内部 reasoning 用的证据
  - confidence: "high" | "mid" | "low"
  - preferred_class_markers: 给 folkways 筛选用
  - disfavored_class_markers: 给 folkways 筛选用

6 个 class tag（详见 folkways_protocol.md §6）：
  - urban_state_or_educated   (体制/读书人家庭)
  - urban_market_oriented      (市场化/经商家庭)
  - institutional_family       (公职/事业单位)
  - rural_or_county            (农村/县城)
  - freelance_artisan_family   (手艺人/个体)
  - grassroots_self_made       (草根/移动)
  - early_high_pressure        (单亲/失怙/留守等)
"""
from __future__ import annotations
from typing import Dict, List, Optional


CLASS_TAGS = [
    "urban_state_or_educated",
    "urban_market_oriented",
    "institutional_family",
    "rural_or_county",
    "freelance_artisan_family",
    "grassroots_self_made",
    "early_high_pressure",
]

CLASS_LABEL_INTERNAL_ONLY = {
    "urban_state_or_educated": "城市体制/读书人家庭（仅用于 LLM 内部 reasoning）",
    "urban_market_oriented":   "城市市场化/经商家庭（仅用于 LLM 内部 reasoning）",
    "institutional_family":    "公职/事业单位家庭（仅用于 LLM 内部 reasoning）",
    "rural_or_county":         "农村/县城家庭（仅用于 LLM 内部 reasoning）",
    "freelance_artisan_family":"手艺人/个体户家庭（仅用于 LLM 内部 reasoning）",
    "grassroots_self_made":    "草根/路径自创（仅用于 LLM 内部 reasoning）",
    "early_high_pressure":     "童年高压/单亲/失怙（仅用于 LLM 内部 reasoning）",
}

PREFERRED_MARKERS = {
    "urban_state_or_educated":   ["urban_middle", "urban_educated"],
    "urban_market_oriented":     ["urban_mass", "urban_aspirational"],
    "institutional_family":      ["urban_middle", "civil_service"],
    "rural_or_county":           ["rural_aspirational", "rural", "county_mass"],
    "freelance_artisan_family":  ["urban_mass", "artisan"],
    "grassroots_self_made":      ["urban_mass", "mobile"],
    "early_high_pressure":       ["single_parent", "distant_parent", "orphan"],
}

DISFAVORED_MARKERS = {
    "urban_state_or_educated":   ["rural", "elite"],
    "urban_market_oriented":     ["civil_service"],
    "institutional_family":      ["mobile", "rural"],
    "rural_or_county":           ["urban_middle", "elite"],
    "freelance_artisan_family":  ["civil_service", "elite"],
    "grassroots_self_made":      ["elite"],
    "early_high_pressure":       [],
}

# === 推断规则的权重 ===
# 思路：从年柱+月柱十神（早期家庭氛围）+ 用神 + 起运岁 + 调候 综合打分
W_YEAR_GAN_SHISHEN = {
    "正印":   {"urban_state_or_educated": 3.0, "institutional_family": 2.0, "freelance_artisan_family": -0.5},
    "偏印":   {"urban_state_or_educated": 1.5, "early_high_pressure": 1.5, "rural_or_county": 0.8},
    "正官":   {"institutional_family": 3.0, "urban_state_or_educated": 1.5},
    "七杀":   {"grassroots_self_made": 2.0, "urban_market_oriented": 1.5, "early_high_pressure": 1.0},
    "正财":   {"urban_market_oriented": 2.5, "institutional_family": 1.0, "freelance_artisan_family": 1.5},
    "偏财":   {"urban_market_oriented": 3.0, "freelance_artisan_family": 2.0, "grassroots_self_made": 1.0},
    "食神":   {"urban_state_or_educated": 1.5, "urban_market_oriented": 1.0, "freelance_artisan_family": 1.5},
    "伤官":   {"urban_market_oriented": 1.5, "grassroots_self_made": 2.0, "freelance_artisan_family": 1.5},
    "比肩":   {"rural_or_county": 1.5, "grassroots_self_made": 1.5, "urban_market_oriented": 1.0},
    "劫财":   {"grassroots_self_made": 2.0, "rural_or_county": 1.5, "early_high_pressure": 1.0},
}

W_MONTH_GAN_SHISHEN = {
    "正印":   {"urban_state_or_educated": 2.5, "institutional_family": 1.5},
    "偏印":   {"urban_state_or_educated": 1.5, "freelance_artisan_family": 1.0},
    "正官":   {"institutional_family": 2.5, "urban_state_or_educated": 1.0},
    "七杀":   {"grassroots_self_made": 1.5, "urban_market_oriented": 1.0, "early_high_pressure": 0.8},
    "正财":   {"urban_market_oriented": 2.0, "institutional_family": 0.8},
    "偏财":   {"urban_market_oriented": 2.5, "freelance_artisan_family": 1.5, "grassroots_self_made": 1.0},
    "食神":   {"urban_state_or_educated": 1.5, "freelance_artisan_family": 1.0},
    "伤官":   {"urban_market_oriented": 1.5, "grassroots_self_made": 1.5, "freelance_artisan_family": 1.0},
    "比肩":   {"rural_or_county": 1.0, "grassroots_self_made": 1.5},
    "劫财":   {"grassroots_self_made": 1.5, "rural_or_county": 1.0},
}


def _accumulate(scores: Dict[str, float], delta: Dict[str, float], factor: float = 1.0) -> None:
    for k, v in delta.items():
        scores[k] = scores.get(k, 0.0) + v * factor


def _softmax_normalize(scores: Dict[str, float], temperature: float = 1.0) -> Dict[str, float]:
    """简单的归一化（不用 softmax，避免极化）。负数截断为 0，再按比例。"""
    pos = {k: max(0.0, v) for k, v in scores.items()}
    total = sum(pos.values())
    if total <= 0:
        return {k: 1.0 / len(CLASS_TAGS) for k in CLASS_TAGS}
    return {k: round(v / total, 3) for k, v in pos.items()}


def infer_class_prior(bazi: dict) -> dict:
    """主入口：根据 bazi.json 推导 class_prior 分布。

    Args:
        bazi: solve_bazi.py 输出的 dict（必须含 pillar_info / strength / yongshen / dayun）
    
    Returns:
        见模块 docstring
    """
    scores: Dict[str, float] = {k: 0.0 for k in CLASS_TAGS}
    evidence: List[str] = []
    
    pillar_info = bazi.get("pillar_info", [])
    if len(pillar_info) < 4:
        return _fallback_uniform("pillar_info incomplete")
    
    year_pi = pillar_info[0]
    month_pi = pillar_info[1]
    day_pi = pillar_info[2]
    
    # === Rule 1: 年柱十神 (早期家庭画像主信号) ===
    year_gan_shishen = year_pi.get("gan_shishen")
    year_zhi_shishen = year_pi.get("zhi_shishen")
    if year_gan_shishen in W_YEAR_GAN_SHISHEN:
        _accumulate(scores, W_YEAR_GAN_SHISHEN[year_gan_shishen], factor=1.0)
        evidence.append(f"年干={year_pi['gan']}（{year_gan_shishen}）→ {_top_tags_for(W_YEAR_GAN_SHISHEN[year_gan_shishen])}")
    if year_zhi_shishen in W_YEAR_GAN_SHISHEN:
        _accumulate(scores, W_YEAR_GAN_SHISHEN[year_zhi_shishen], factor=0.6)
        evidence.append(f"年支={year_pi['zhi']}（{year_zhi_shishen}）→ 同上加权 0.6")
    
    # === Rule 2: 月柱十神 (家庭主导动力 / 父辈职业类型) ===
    month_gan_shishen = month_pi.get("gan_shishen")
    if month_gan_shishen in W_MONTH_GAN_SHISHEN:
        _accumulate(scores, W_MONTH_GAN_SHISHEN[month_gan_shishen], factor=1.2)
        evidence.append(f"月干={month_pi['gan']}（{month_gan_shishen}）→ 父辈主导动力倾向")
    
    # === Rule 3: 起运岁 (家庭节奏稳定度信号) ===
    qiyun_age = bazi.get("qiyun_age", 8)
    if qiyun_age <= 6:
        scores["urban_state_or_educated"] += 1.5
        scores["institutional_family"] += 1.0
        scores["early_high_pressure"] -= 0.5
        evidence.append(f"起运 {qiyun_age} 岁早 → 家庭节奏偏稳")
    elif qiyun_age >= 10:
        scores["grassroots_self_made"] += 1.0
        scores["rural_or_county"] += 0.5
        scores["urban_state_or_educated"] -= 0.5
        evidence.append(f"起运 {qiyun_age} 岁晚 → 早年路径需自创")
    
    # === Rule 4: 用神到位度（资源充足程度的间接信号）===
    yongshen = bazi.get("yongshen", {})
    yongshen_wx = yongshen.get("yongshen")
    if yongshen_wx:
        # 用神在原局是否有根（粗略：是否在四柱五行中出现）
        all_wx = []
        for pi in pillar_info:
            all_wx.append(pi.get("gan_wuxing"))
            all_wx.append(pi.get("zhi_wuxing"))
        if yongshen_wx in all_wx:
            scores["urban_state_or_educated"] += 0.8
            scores["institutional_family"] += 0.5
            evidence.append(f"用神={yongshen_wx} 在原局有根 → 资源相对充足")
        else:
            scores["grassroots_self_made"] += 1.0
            scores["rural_or_county"] += 0.5
            scores["early_high_pressure"] += 0.5
            evidence.append(f"用神={yongshen_wx} 原局缺 → 早年资源相对短缺")
    
    # === Rule 5: 印星总量 (印 = 庇护 / 教育 / 学术资源) ===
    yin_count = sum(1 for pi in pillar_info 
                    if pi.get("gan_shishen") in ("正印", "偏印")
                    or pi.get("zhi_shishen") in ("正印", "偏印"))
    if yin_count >= 3:
        scores["urban_state_or_educated"] += 2.0
        scores["institutional_family"] += 1.0
        evidence.append(f"印星 {yin_count}+ 重 → 家庭偏教育/庇护型")
    elif yin_count == 0:
        scores["grassroots_self_made"] += 1.5
        scores["urban_market_oriented"] += 0.5
        scores["early_high_pressure"] += 0.5
        evidence.append("原局无印 → 早年缺庇护信号")
    
    # === Rule 6: 财星总量 (财 = 经商 / 流动资产) ===
    cai_count = sum(1 for pi in pillar_info 
                    if pi.get("gan_shishen") in ("正财", "偏财")
                    or pi.get("zhi_shishen") in ("正财", "偏财"))
    if cai_count >= 3:
        scores["urban_market_oriented"] += 2.0
        scores["freelance_artisan_family"] += 1.0
        evidence.append(f"财星 {cai_count}+ 重 → 家庭偏市场化/流动")
    
    # === Rule 7: 食伤总量 (食伤 = 才华 / 表达 / 自由职业) ===
    shishang_count = sum(1 for pi in pillar_info 
                          if pi.get("gan_shishen") in ("食神", "伤官")
                          or pi.get("zhi_shishen") in ("食神", "伤官"))
    if shishang_count >= 3:
        scores["freelance_artisan_family"] += 1.5
        scores["urban_market_oriented"] += 0.5
        evidence.append(f"食伤 {shishang_count}+ 重 → 偏才华/表达型家庭")
    
    # === Rule 8: 比劫总量 (比劫 = 同辈竞争 / 兄弟协作) ===
    bijie_count = sum(1 for pi in pillar_info 
                       if pi.get("gan_shishen") in ("比肩", "劫财")
                       or pi.get("zhi_shishen") in ("比肩", "劫财"))
    if bijie_count >= 3:
        scores["rural_or_county"] += 1.0
        scores["grassroots_self_made"] += 1.0
        evidence.append(f"比劫 {bijie_count}+ 重 → 偏同辈竞争/兄弟协作")
    
    # === Rule 9: 七杀重 + 印缺 → 早年高压 ===
    qisha_count = sum(1 for pi in pillar_info 
                       if pi.get("gan_shishen") == "七杀"
                       or pi.get("zhi_shishen") == "七杀")
    if qisha_count >= 2 and yin_count == 0:
        scores["early_high_pressure"] += 2.0
        scores["grassroots_self_made"] += 1.0
        evidence.append("七杀 ≥ 2 + 无印 → 早年高压信号")
    
    # === 归一化 ===
    distribution = _softmax_normalize(scores)
    
    primary = max(distribution.items(), key=lambda kv: kv[1])
    primary_class = primary[0]
    primary_prob = primary[1]
    
    # === 计算 confidence ===
    sorted_probs = sorted(distribution.values(), reverse=True)
    margin = sorted_probs[0] - sorted_probs[1] if len(sorted_probs) >= 2 else 0
    if primary_prob >= 0.45 and margin >= 0.15:
        confidence = "high"
    elif primary_prob >= 0.30 and margin >= 0.08:
        confidence = "mid"
    else:
        confidence = "low"
    
    # === 给 folkways 筛选用的 markers ===
    preferred_markers = []
    disfavored_markers = []
    for tag, prob in distribution.items():
        if prob >= 0.20:
            preferred_markers.extend(PREFERRED_MARKERS.get(tag, []))
            disfavored_markers.extend(DISFAVORED_MARKERS.get(tag, []))
    preferred_markers = list(dict.fromkeys(preferred_markers))
    disfavored_markers = list(dict.fromkeys(disfavored_markers))
    
    return {
        "primary_class": primary_class,
        "primary_class_label_internal_only": CLASS_LABEL_INTERNAL_ONLY[primary_class],
        "distribution": distribution,
        "evidence": evidence,
        "confidence": confidence,
        "preferred_class_markers": preferred_markers,
        "disfavored_class_markers": disfavored_markers,
        "_disclaimer": (
            "⚠️ 此 class_prior 仅供 LLM 内部 reasoning。"
            "禁止以阶级名词形式输出给用户。"
            "详见 references/class_inference_ethics.md。"
        ),
    }


def _top_tags_for(weights: Dict[str, float], top_n: int = 2) -> str:
    sorted_tags = sorted(weights.items(), key=lambda kv: -kv[1])[:top_n]
    return " / ".join(t for t, _ in sorted_tags)


def _fallback_uniform(reason: str) -> dict:
    uniform = {k: round(1.0 / len(CLASS_TAGS), 3) for k in CLASS_TAGS}
    return {
        "primary_class": "unknown",
        "primary_class_label_internal_only": "无法推断（数据不足）",
        "distribution": uniform,
        "evidence": [f"fallback_reason: {reason}"],
        "confidence": "low",
        "preferred_class_markers": [],
        "disfavored_class_markers": [],
        "_disclaimer": (
            "⚠️ class_prior 推断失败，已退回均匀分布。"
            "LLM 应在输出中诚实告知「未掌握命主家庭背景」。"
        ),
    }


def main():
    import argparse
    import json
    from pathlib import Path
    
    ap = argparse.ArgumentParser(description="推导 class_prior（仅供 LLM 内部 reasoning，禁止以阶级名词输出）")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--out", default=None, help="输出路径（默认 stdout）")
    args = ap.parse_args()
    
    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    result = infer_class_prior(bazi)
    
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"[_class_prior] wrote {args.out}")
        print(f"  primary_class = {result['primary_class']} ({result['confidence']})")
        for ev in result["evidence"][:5]:
            print(f"  · {ev}")
    else:
        print(output)


if __name__ == "__main__":
    main()
