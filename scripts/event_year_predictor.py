#!/usr/bin/env python3
"""event_year_predictor.py — Phase × 流年/大运 预测命中矩阵（纯 Python · 零 LLM）

设计目标：
  对每个候选 phase，计算它在这盘的哪些年份「应当」发生明显事件。
  这是 event_elicit.py Stage A（disjoint 年发问）的数据基础。

命中规则（按优先级合并）：
  1. registry 的 `zuogong_trigger_branches` —— 大运/流年地支命中即触发
  2. phase 相关的「十神标签」 —— 流年 gan_shishen / zhi_shishen 命中即触发
  3. registry 的 `reversal_overrides` 对应的 mangpai event keys —— 此处暂不用
     （mangpai_events.py 已经独立产出年份级 events，可后续融合）

输出：
  predicted_event_years(phase_id, bazi) → List[Tuple[int, str]]
    每项 = (公历年, 命中原因简标签)，按年份去重排序

Stage A 上层逻辑（select_disjoint_year）：
  对每个候选 phase 跑一次 predicted_event_years → 取交叉
  找 disjoint 年（只命中 1 个 phase），按用户能否记得排序（成年期优先）

注意：
  - **不**预测「事件类型」—— Stage A 只问"那年是否发生明显事情"
  - 事件类型的细分由 Stage B（LLM 现算）承担
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import _phase_registry as registry


# ============================================================================
# 五行 / 干支 基础表
# ============================================================================

GAN_TO_WUXING: Dict[str, str] = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

ZHI_TO_WUXING: Dict[str, str] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土",
    "巳": "火", "午": "火", "未": "土", "申": "金", "酉": "金",
    "戌": "土", "亥": "水",
}


# ============================================================================
# Phase → 相关十神集合
#
# 用于流年预测：当流年的 gan_shishen / zhi_shishen 落在该集合内，视为命中。
# 十神名称与 bazi.json.liunian[*].gan_shishen 字段对齐：
#   "比肩" / "劫财" / "食神" / "伤官" / "偏财" / "正财" /
#   "七杀" / "正官" / "偏印" / "正印"
#
# 设计原则：
#   - 每个 phase 只列「核心相关」十神（命中度高）
#   - 不在表里的 phase 走默认（baseline / 无强预测）—— 那种 phase 在 disjoint
#     年判定里不会有票（也不会被错误命中）
# ============================================================================

PHASE_RELEVANT_SHISHEN: Dict[str, Set[str]] = {
    # ─── 从格 ─── 弃命从 X → X 类十神岁运为大利
    "floating_dms_to_cong_cai": {"偏财", "正财"},
    "floating_dms_to_cong_sha": {"七杀", "正官"},
    "floating_dms_to_cong_er": {"食神", "伤官"},
    "floating_dms_to_cong_yin": {"偏印", "正印"},
    "cong_cai_zhen": {"偏财", "正财"},
    "cong_sha_zhen": {"七杀", "正官"},
    "true_following": {"偏财", "正财", "七杀", "正官", "食神", "伤官"},
    "pseudo_following": {"偏财", "正财", "七杀", "正官", "食神", "伤官"},

    # ─── 旺神得令 · X 作主 ─── 同从格逻辑（X 流年事件密集）
    "dominating_god_cai_zuo_zhu": {"偏财", "正财"},
    "dominating_god_guan_zuo_zhu": {"七杀", "正官"},
    "dominating_god_shishang_zuo_zhu": {"食神", "伤官"},
    "dominating_god_yin_zuo_zhu": {"偏印", "正印"},

    # ─── 子平八正格 ─── 该格岁运 = 同类十神出现
    "zhengguan_ge": {"正官"},
    "qisha_ge": {"七杀"},
    "zhengyin_ge": {"正印"},
    "pianyin_ge": {"偏印"},
    "shishen_ge": {"食神"},
    "shangguan_ge": {"伤官"},
    "zhengcai_ge": {"正财"},
    "piancai_ge": {"偏财"},
    "jianlu_ge": {"比肩"},
    "yangren_ge": {"劫财"},

    # ─── 盲派 / 复合格 ─── 取构成该格的两类十神同时为相关
    "qi_yin_xiang_sheng": {"七杀", "正官", "偏印", "正印"},
    "sha_yin_xiang_sheng_geju": {"七杀", "正官", "偏印", "正印"},
    "shang_guan_sheng_cai": {"伤官", "食神", "偏财", "正财"},
    "shang_guan_sheng_cai_geju": {"伤官", "食神", "偏财", "正财"},
    "shang_guan_pei_yin_geju": {"伤官", "偏印", "正印"},
    "shi_shen_zhi_sha_geju": {"食神", "七杀"},
    "shang_guan_jian_guan": {"伤官", "正官"},
    "yang_ren_jia_sha": {"劫财", "七杀"},
    "yangren_chong_cai": {"劫财", "偏财", "正财"},

    # ─── 调候反向 ─── 调候用神的五行流年命中
    # （climate 类不直接用十神，由 _climate_phase_relevant_wuxing 单独处理）
    # 占位，避免 KeyError
    "climate_inversion_dry_top": set(),
    "climate_inversion_wet_top": set(),

    # ─── 化气格 ─── 化气目标五行的同行流年（独立逻辑，见下）
    # 占位
    **{f"huaqi_to_{wx}": set() for wx in ("土", "金", "水", "木", "火")},

    # ─── special / structure 类 ─── 无明确流年规律，留空（这些 phase
    # 在 disjoint 年判定里不参与，靠 Stage B 处理）
    "kuigang_ge": set(),
    "jinshen_ge": set(),
    "ride_ge": set(),
    "rigui_ge": set(),
    "riren_ge": {"劫财"},
    "tianyuanyiqi": set(),
    "lianggan_buza": set(),
    "wuqi_chaoyuan": set(),
    "jinglanchaa_ge": set(),
    "si_sheng_si_bai": set(),
    "si_ku_ju": set(),
    "ma_xing_yi_dong": set(),
    "hua_gai_ru_ming": set(),
    "jin_bai_shui_qing": set(),
    "mu_huo_tong_ming": set(),

    # baseline
    "day_master_dominant": set(),
}


# ============================================================================
# 化气 / 调候 ─ 五行级命中
# ============================================================================

# huaqi_to_X：流年五行 == X 视为命中（化气目标五行的同行）
def _huaqi_target_wuxing(phase_id: str) -> Optional[str]:
    if phase_id.startswith("huaqi_to_"):
        return phase_id[len("huaqi_to_"):]
    return None


# climate_inversion_dry_top：上燥下寒 → 用神为水 → 水五行流年命中
# climate_inversion_wet_top：上湿下燥 → 用神为火 → 火五行流年命中
_CLIMATE_PHASE_TARGET_WUXING = {
    "climate_inversion_dry_top": "水",
    "climate_inversion_wet_top": "火",
}


def _wuxing_for_year(gan: str, zhi: str) -> Set[str]:
    """流年 / 大运 的五行集合（干 + 支）"""
    result: Set[str] = set()
    if gan in GAN_TO_WUXING:
        result.add(GAN_TO_WUXING[gan])
    if zhi in ZHI_TO_WUXING:
        result.add(ZHI_TO_WUXING[zhi])
    return result


# ============================================================================
# 主入口
# ============================================================================

HitReason = str  # "trigger_branch" | "shishen" | "wuxing"


def predicted_event_years(
    phase_id: str,
    bazi: Dict,
) -> List[Tuple[int, HitReason]]:
    """对给定 phase 预测它在这盘的哪些公历年应当发生事件。

    返回按年份升序去重的 [(year, reason)] 列表。reason 是命中规则简标签，
    供调试与 ask-loop 题面生成参考（不直接吐给用户）。
    """
    try:
        meta = registry.get(phase_id)
    except KeyError:
        return []

    # ─ 准备命中条件 ─
    trigger_branches: Set[str] = set(meta.zuogong_trigger_branches or ())
    relevant_shishen: Set[str] = PHASE_RELEVANT_SHISHEN.get(phase_id, set())

    huaqi_wx = _huaqi_target_wuxing(phase_id)
    climate_wx = _CLIMATE_PHASE_TARGET_WUXING.get(phase_id)
    target_wuxing: Set[str] = set()
    if huaqi_wx:
        target_wuxing.add(huaqi_wx)
    if climate_wx:
        target_wuxing.add(climate_wx)

    # 大运起始年集合（含起始 +1，用户对"刚换大运那一两年"印象最深）
    dayun_anchor_years: Set[int] = set()
    for dy in bazi.get("dayun", []) or []:
        sy = dy.get("start_year")
        if isinstance(sy, int):
            dayun_anchor_years.add(sy)
            dayun_anchor_years.add(sy + 1)

    hits: Dict[int, HitReason] = {}

    # ─ 大运扫描（粗粒度） ─
    # shishen / 五行 类命中只在**大运层面**判定 —— 否则像 pseudo_following 这种
    # 「财/官/食伤都算」的 phase 会把每个流年都命中、disjoint 年判定全部失效。
    for dy in bazi.get("dayun", []) or []:
        gan = dy.get("gan", "")
        zhi = dy.get("zhi", "")
        start_year = dy.get("start_year")
        if not isinstance(start_year, int):
            continue
        # 1) trigger 支：大运直接命中（强信号）
        if zhi in trigger_branches or gan in trigger_branches:
            hits.setdefault(start_year, "trigger_branch_dayun")
            continue
        # 2) 化气 / 调候五行：大运五行命中
        if target_wuxing and (_wuxing_for_year(gan, zhi) & target_wuxing):
            hits.setdefault(start_year, "wuxing_dayun")
            continue
        # 3) shishen：用大运起始年所在 liunian 的十神标签判定
        if relevant_shishen:
            for ln in bazi.get("liunian", []) or []:
                if ln.get("year") == start_year:
                    if (ln.get("gan_shishen") in relevant_shishen
                            or ln.get("zhi_shishen") in relevant_shishen):
                        hits.setdefault(start_year, "shishen_dayun")
                    break

    # ─ 流年扫描（细粒度·只允许 trigger 支） ─
    # 流年级别只用 trigger_branches —— 这是 phase metadata 显式标注的「应期支」，
    # 比泛十神匹配狭窄、判别力强得多。
    if trigger_branches:
        for ln in bazi.get("liunian", []) or []:
            year = ln.get("year")
            if not isinstance(year, int):
                continue
            if ln.get("zhi") in trigger_branches or ln.get("gan") in trigger_branches:
                hits.setdefault(year, "trigger_branch")

    return sorted(hits.items())


# ============================================================================
# Disjoint 年选择 · Stage A 核心
# ============================================================================

class DisjointPick:
    """Stage A 选出的一道题。

    sole_phase 是该年份**唯一命中**的候选 phase（其它候选都不预期事件）。
    用户答 "是" → 强支持 sole_phase；答 "否" → 强反对 sole_phase。
    """
    __slots__ = ("year", "sole_phase", "all_predictions")

    def __init__(self, year: int, sole_phase: str,
                 all_predictions: Dict[str, bool]):
        self.year = year
        self.sole_phase = sole_phase
        self.all_predictions = all_predictions  # {phase_id: hit?}

    def __repr__(self) -> str:
        return f"DisjointPick(year={self.year}, sole={self.sole_phase})"


def _user_age_in_year(year: int, birth_year: int) -> int:
    return year - birth_year


def select_disjoint_year_batch(
    candidate_phases: List[str],
    bazi: Dict,
    asked_years: Set[int],
    batch_size: int = 4,
    age_band: Tuple[int, int] = (5, 60),
) -> List[DisjointPick]:
    """**批次**选 disjoint 年（每年只命中一个候选 phase）。

    为什么是批次而不是单年：
      单年提问 → 用户在「这年是不是应该发生大事」的暗示下倾向虚假肯定。
      批次问 → 把 N 个年份并排呈现，用户看作一张清单逐项作答，
      心理压力分散，"没发生 / 记不清" 更容易被诚实选择。

    批次构造策略：
      1. 先按用户回忆质量排候选（16-40 岁优先）
      2. 在 batch_size 限额内**优先覆盖不同的 sole_phase**——
         一批里同时有支持 A、支持 B、支持 C 的年份，避免一批全指向同一 phase
         （那种批次也会引导）。
      3. 同 sole_phase 名额满了再补其它年份。

    age_band 默认 (8, 60)：避开婴幼儿（记不清）与暮年（未到达）。

    UI 题面铁律（题目生成方必须遵守，否则就是引导）：
      - 文案必须包含「如实回答 · 没发生就直接说没发生 · 记不清就选记不清」
      - **不要**写"这年应当 X" / "这年命中 Y"等暗示
      - **不要**只问一年（单年问 = 引导）—— 调用方收到 [DisjointPick] 必须
        全部一次性渲染成清单题
    """
    if len(candidate_phases) < 2:
        return []

    birth_year = bazi.get("birth_year")
    if not isinstance(birth_year, int):
        return []

    age_min, age_max = age_band
    year_lo = birth_year + age_min
    year_hi = birth_year + age_max

    # 硬限：只问命主**已经经历过**的年份。
    # 命主才 20 岁却被问 35 岁那年发生过什么事是 user-hostile，
    # 也会让 Bayesian 全部走 dunno，整轮答题白做。
    import time
    current_year = time.localtime().tm_year
    year_hi = min(year_hi, current_year - 1)
    if year_hi < year_lo:
        return []  # 命主还太年轻 / age_band 全在未来

    # 每个 phase 的命中年集合
    grid: Dict[str, Set[int]] = {}
    for pid in candidate_phases:
        years = {y for y, _ in predicted_event_years(pid, bazi)
                 if year_lo <= y <= year_hi and y not in asked_years}
        grid[pid] = years

    # 统计每年的命中 phase（disjoint = 仅 1 个）
    all_years: Set[int] = set().union(*grid.values())
    candidates: List[Tuple[int, str]] = []
    for year in all_years:
        hitting = [pid for pid in candidate_phases if year in grid[pid]]
        if len(hitting) == 1:
            candidates.append((year, hitting[0]))

    if not candidates:
        return []

    # 排序：用户最有印象的年优先（16-40 岁段，靠近 28）
    def _sort_key(item: Tuple[int, str]) -> Tuple[int, int]:
        year, _ = item
        age = _user_age_in_year(year, birth_year)
        primary = 0 if 16 <= age <= 40 else 1
        return (primary, abs(age - 28))

    candidates.sort(key=_sort_key)

    # 优先覆盖不同 sole_phase
    picked: List[Tuple[int, str]] = []
    seen_phases: Set[str] = set()
    leftovers: List[Tuple[int, str]] = []
    for item in candidates:
        _, sole = item
        if sole not in seen_phases:
            picked.append(item)
            seen_phases.add(sole)
            if len(picked) >= batch_size:
                break
        else:
            leftovers.append(item)
    # 不同 sole_phase 用尽后继续填
    for item in leftovers:
        if len(picked) >= batch_size:
            break
        picked.append(item)

    out: List[DisjointPick] = []
    for year, sole_phase in picked:
        all_preds = {pid: (year in grid[pid]) for pid in candidate_phases}
        out.append(DisjointPick(
            year=year, sole_phase=sole_phase, all_predictions=all_preds))
    return out


def select_disjoint_year(
    candidate_phases: List[str],
    bazi: Dict,
    asked_years: Set[int],
    age_band: Tuple[int, int] = (8, 60),
) -> Optional[DisjointPick]:
    """单年版 · 兼容旧调用方。**新代码请用 select_disjoint_year_batch**。"""
    batch = select_disjoint_year_batch(
        candidate_phases, bazi, asked_years, batch_size=1, age_band=age_band)
    return batch[0] if batch else None


# ============================================================================
# CLI · 调试用
# ============================================================================

def _cli() -> None:
    import argparse
    import json as _json
    ap = argparse.ArgumentParser(description="Phase × 年份预测命中矩阵")
    ap.add_argument("--bazi", required=True, help="bazi.json path")
    ap.add_argument("--phases", nargs="+", required=True,
                    help="候选 phase id 列表（≥2 个）")
    ap.add_argument("--asked", nargs="*", type=int, default=[],
                    help="已问过的年份（不再选）")
    args = ap.parse_args()

    bazi = _json.loads(open(args.bazi, encoding="utf-8").read())
    print(f"\n=== 候选 phase 各自的预测年份 ===\n")
    for pid in args.phases:
        years = predicted_event_years(pid, bazi)
        try:
            label = registry.get(pid).name_cn
        except KeyError:
            label = pid
        print(f"{label} ({pid}): {len(years)} 年")
        for y, reason in years[:20]:
            print(f"  {y} · {reason}")
        if len(years) > 20:
            print(f"  ... +{len(years) - 20}")
        print()

    batch = select_disjoint_year_batch(
        args.phases, bazi, set(args.asked), batch_size=4)
    print("=== Stage A disjoint 年批次（一题问 N 年） ===")
    if batch:
        for pk in batch:
            print(f"  {pk.year} · 唯一命中 {pk.sole_phase} · 预测分布 {pk.all_predictions}")
    else:
        print("  没有 disjoint 年 → 转 Stage B")


if __name__ == "__main__":
    _cli()
