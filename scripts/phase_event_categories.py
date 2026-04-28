#!/usr/bin/env python3
"""phase_event_categories.py — Phase → 预测事件类别（categorical 映射，纯数据）

替代 Stage B 早期版本里那种「每对 (年×phase) 调 LLM 估事件类型」的高成本路线。
一次性写好的 phase → event_category 列表，Stage B 出题时直接查表，
零 LLM 调用。

数据基础（每条都标了出处）：
  - 古籍（子平真诠 / 滴天髓 / 穷通宝鉴 / 三命通会）
  - 师承传（盲派象法）
  - 现代命理书面化总结（如盲派 mangpai_events.py 里已沉淀的 event_key）

curation 原则：
  - 每个 phase 列 1-3 个**可证伪的事件类别**——必须是用户能用「是 / 部分 / 否」
    清楚回答的具体事件，**不写**性格 / 抽象命运标签
  - 类别用大白话，不用命理术语（"升学/学术贵人" 而非 "印星岁运"）
  - 同一句子表述：以「事件描述 · 命理依据」格式写，依据靠后用括号注

后期可扩展：
  - 可加 age_band 维度（同一 phase 在不同大运段预测不同事件）
  - 可加 strength 标记（强信号事件 vs 一般信号）
  - 真要细到 dayun 级，再考虑往这里加 hash key
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple


# ─── 「以上都不是」sentinel ────────────────────────────────
# 用户在 Stage B 题里勾这个 → 表示「我那年确实有大事，但不在你给的类别里」
# 必须以这个**字面字符串**透传到 likelihood 表（不要本地化，否则查表失效）
NONE_OF_ABOVE = "__none_of_above__"


# ─── 类别全集 · 用户答题时能勾的标签 ─────────────────────────
# 设计：保持 ≤ 12 大类——再多用户头晕，UI 也放不下
EVENT_CATEGORIES: Tuple[str, ...] = (
    "升学考试 / 学术成就",
    "进入体制 / 国企 / 公职",
    "创业 / 自由职业 / 作品发表",
    "重大职业转折 / 跳槽",
    "财务大额变动（购房/破财/进财）",
    "婚姻成立 / 长期亲密关系定型",
    "婚姻 / 长期关系破裂",
    "搬家 / 异地迁居 / 出国",
    "重大疾病 / 手术 / 健康危机",
    "亲人重大变故（病故 / 重病）",
    "重要法律 / 合同事件",
    "重要奖项 / 公开认可",
)


# ─── phase → 该 phase 在岁运命中年应当呈现的事件类别 ──────────
# 注意：每个 phase 的预测应该和其它 phase **有显著差异** —— 这正是
# Stage B divergence 的语义来源。所有 phase 都填一样就没区分度了。
PHASE_EVENT_CATEGORIES: Dict[str, List[str]] = {

    # ─── baseline ───
    # 日主主导：用神扶抑常规处理，无强烈的事件类别预测
    "day_master_dominant": [],  # 空列表 → Stage B 默认所有事件都"可能"，不参与挑选

    # ─── 弃命从 X（真从）─────────────────
    # 出处：滴天髓 · 从象论
    "floating_dms_to_cong_cai": [
        "财务大额变动（购房/破财/进财）",
        "重大职业转折 / 跳槽",
        "婚姻成立 / 长期亲密关系定型",  # 财星动 → 关系定型
    ],
    "floating_dms_to_cong_sha": [
        "进入体制 / 国企 / 公职",
        "重大职业转折 / 跳槽",
        "重要法律 / 合同事件",
    ],
    "floating_dms_to_cong_er": [
        "创业 / 自由职业 / 作品发表",
        "重要奖项 / 公开认可",
        "重大职业转折 / 跳槽",
    ],
    "floating_dms_to_cong_yin": [
        "升学考试 / 学术成就",
        "进入体制 / 国企 / 公职",
        "亲人重大变故（病故 / 重病）",  # 印为母，印动主长辈相关
    ],

    # ─── 旺神得令·X 作主（与从格预测同向但更柔和）─────
    # 出处：子平真诠 · 论用神成败救应
    "dominating_god_cai_zuo_zhu": [
        "财务大额变动（购房/破财/进财）",
        "婚姻成立 / 长期亲密关系定型",
    ],
    "dominating_god_guan_zuo_zhu": [
        "进入体制 / 国企 / 公职",
        "重大职业转折 / 跳槽",
    ],
    "dominating_god_shishang_zuo_zhu": [
        "创业 / 自由职业 / 作品发表",
        "重要奖项 / 公开认可",
    ],
    "dominating_god_yin_zuo_zhu": [
        "升学考试 / 学术成就",
        "亲人重大变故（病故 / 重病）",
    ],

    # ─── 真从 detector（与 floating 系列同向）─────
    "cong_cai_zhen": [
        "财务大额变动（购房/破财/进财）",
        "婚姻成立 / 长期亲密关系定型",
    ],
    "cong_sha_zhen": [
        "进入体制 / 国企 / 公职",
        "重要法律 / 合同事件",
    ],
    "true_following": [
        # 真从但未明确顺哪个 → 不挑特定类别
        "重大职业转折 / 跳槽",
    ],
    "pseudo_following": [
        # 假从：摇摆中遇大事
        "重大职业转折 / 跳槽",
        "财务大额变动（购房/破财/进财）",
    ],

    # ─── 调候反向 ─────────────────────────
    # 出处：穷通宝鉴 · 春夏秋冬总论
    # 上燥下寒（用神=水）：水旺岁运→印库地为应（学业/医疗/居住）
    "climate_inversion_dry_top": [
        "升学考试 / 学术成就",
        "重大疾病 / 手术 / 健康危机",
    ],
    # 上湿下燥（用神=火）：火旺岁运→热度释放
    "climate_inversion_wet_top": [
        "重要奖项 / 公开认可",
        "创业 / 自由职业 / 作品发表",
    ],

    # ─── 化气格 ───────────────────────────
    # 出处：滴天髓 · 化气论
    # 化气方向→对应五行旺地为大利
    "huaqi_to_土": [
        "财务大额变动（购房/破财/进财）",  # 土主财库
        "搬家 / 异地迁居 / 出国",        # 土主居所
    ],
    "huaqi_to_金": [
        "重要法律 / 合同事件",
        "进入体制 / 国企 / 公职",
    ],
    "huaqi_to_水": [
        "升学考试 / 学术成就",
        "搬家 / 异地迁居 / 出国",  # 水主流动
    ],
    "huaqi_to_木": [
        "重大职业转折 / 跳槽",      # 木主升发
        "婚姻成立 / 长期亲密关系定型",
    ],
    "huaqi_to_火": [
        "重要奖项 / 公开认可",
        "创业 / 自由职业 / 作品发表",
    ],

    # ─── 子平八正格 ─────────────────────
    # 出处：子平真诠 · 各格条目
    "zhengguan_ge": [
        "进入体制 / 国企 / 公职",
        "婚姻成立 / 长期亲密关系定型",  # 官星亦主夫
    ],
    "qisha_ge": [
        "重大职业转折 / 跳槽",
        "重要法律 / 合同事件",
    ],
    "zhengyin_ge": [
        "升学考试 / 学术成就",
        "亲人重大变故（病故 / 重病）",  # 印主长辈
    ],
    "pianyin_ge": [
        "升学考试 / 学术成就",
        "搬家 / 异地迁居 / 出国",  # 偏印 / 枭神主漂泊
    ],
    "shishen_ge": [
        "创业 / 自由职业 / 作品发表",
        "重要奖项 / 公开认可",
    ],
    "shangguan_ge": [
        "创业 / 自由职业 / 作品发表",
        "重要法律 / 合同事件",  # 伤官见官易讼
    ],
    "zhengcai_ge": [
        "财务大额变动（购房/破财/进财）",
        "婚姻成立 / 长期亲密关系定型",
    ],
    "piancai_ge": [
        "财务大额变动（购房/破财/进财）",
        "重大职业转折 / 跳槽",
    ],
    "jianlu_ge": [
        "重大职业转折 / 跳槽",
        "财务大额变动（购房/破财/进财）",
    ],
    "yangren_ge": [
        "重大职业转折 / 跳槽",
        "重要法律 / 合同事件",  # 阳刃多见与人冲撞
    ],

    # ─── 盲派复合格 ─────────────────────
    # 出处：盲派象法 · 各格条目 + 子平真诠对应章节
    "qi_yin_xiang_sheng": [
        "升学考试 / 学术成就",       # 印星化杀 → 学问庇护
        "进入体制 / 国企 / 公职",     # 杀印相生为贵格
    ],
    "sha_yin_xiang_sheng_geju": [
        "升学考试 / 学术成就",
        "进入体制 / 国企 / 公职",
    ],
    "shang_guan_sheng_cai": [
        "创业 / 自由职业 / 作品发表",
        "财务大额变动（购房/破财/进财）",
    ],
    "shang_guan_sheng_cai_geju": [
        "创业 / 自由职业 / 作品发表",
        "财务大额变动（购房/破财/进财）",
    ],
    "shi_shen_zhi_sha_geju": [
        "重大职业转折 / 跳槽",       # 食制杀 = 主动制衡
        "重要奖项 / 公开认可",
    ],
    "shang_guan_pei_yin_geju": [
        "升学考试 / 学术成就",       # 佩印化伤
        "重大职业转折 / 跳槽",
    ],
    "yangren_chong_cai": [
        "财务大额变动（购房/破财/进财）",  # 刃冲财
        "婚姻 / 长期关系破裂",            # 刃冲婚姻位
    ],
    "yang_ren_jia_sha": [
        "重大职业转折 / 跳槽",
        "重要法律 / 合同事件",
    ],
    "shang_guan_jian_guan": [
        "重要法律 / 合同事件",       # 伤官见官 = 易讼
        "婚姻 / 长期关系破裂",
    ],

    # ─── 三命通会 / 渊海子平 special 类 ─────
    # 这些 phase 多为**结构特征**而非**事件预测**，留空或仅给 1 条最相关
    "kuigang_ge": [
        "重大职业转折 / 跳槽",  # 魁罡主刚强变动
    ],
    "jinshen_ge": [
        "重要奖项 / 公开认可",
    ],
    "ride_ge": [
        "重要奖项 / 公开认可",
    ],
    "rigui_ge": [
        "升学考试 / 学术成就",
    ],
    "riren_ge": [
        "重大职业转折 / 跳槽",
    ],
    "tianyuanyiqi": [],         # 天元一气 = 纯结构，无事件预测
    "lianggan_buza": [],
    "wuqi_chaoyuan": [],
    "jinglanchaa_ge": [],
    "si_sheng_si_bai": [
        "搬家 / 异地迁居 / 出国",   # 四生四败主动荡
        "重大职业转折 / 跳槽",
    ],
    "si_ku_ju": [
        "财务大额变动（购房/破财/进财）",  # 四库聚 = 财库
    ],
    "ma_xing_yi_dong": [
        "搬家 / 异地迁居 / 出国",   # 驿马动 = 远行
    ],
    "hua_gai_ru_ming": [
        "升学考试 / 学术成就",       # 华盖主才学
    ],
    "jin_bai_shui_qing": [
        "升学考试 / 学术成就",       # 金白水清主清贵学问
    ],
    "mu_huo_tong_ming": [
        "重要奖项 / 公开认可",       # 木火通明主大显
    ],
}


# ─── 查询 API ─────────────────────────────────────────────

def categories_for_phase(phase_id: str) -> List[str]:
    """获取 phase 的预测事件类别。未注册 / 无预测的 phase 返回空列表。"""
    return list(PHASE_EVENT_CATEGORIES.get(phase_id, []))


def divergence_score(
    phase_a: str, phase_b: str,
    posterior_a: float, posterior_b: float,
    a_predicts: bool = True,
    b_predicts: bool = True,
) -> float:
    """两个 phase 之间的事件类别分歧分（0=完全重合 / 1=完全不同）。

    a_predicts / b_predicts: 该 phase **在被问的这一年是否预测有事件**。
      - 都 False → 都没在这一年下注 → 没区分度 → 0
      - 一个 True 一个 False → 用户答 yes/no 自然分裂这两个 phase → 高分歧
      - 都 True → 看 categories 的 Jaccard 距离

    用 Jaccard 距离作为同时预测时的分歧分；后验越高的两个 phase 之间的
    分歧越值得问 → 乘以 posterior 加权。

    v3 修正（2026-04）：
      旧版只看全局 categories 重合，不考虑某 phase 在这一年是否真预测，
      结果 day_master_dominant（categories 全空）跟任何 phase 的 divergence
      都返回 0，导致 Stage B 在 baseline 是 top 候选时直接失效。
    """
    if not a_predicts and not b_predicts:
        return 0.0
    if a_predicts != b_predicts:
        # 一个预测有事、一个没说要有事 → 用户的"是/否"答案天然区分
        return 1.0 * posterior_a * posterior_b
    # 都预测了这一年有事 → 看 categories 重合
    cats_a = set(categories_for_phase(phase_a))
    cats_b = set(categories_for_phase(phase_b))
    if not cats_a and not cats_b:
        return 0.0
    if not cats_a or not cats_b:
        # 一方有 categories 一方没（罕见：phase 触发但表里没填）
        # 用户勾的类别能区分有 vs 无
        return 0.7 * posterior_a * posterior_b
    intersection = cats_a & cats_b
    union = cats_a | cats_b
    jaccard = len(intersection) / len(union)
    div = 1.0 - jaccard
    return div * posterior_a * posterior_b


def expected_categories_union(phase_ids: List[str]) -> List[str]:
    """所有候选 phase 预测类别的并集，去重保序。

    用于题面：「下面这些类别里，是否经历过任一类？」
    UI 渲染成 checkbox 清单 + 一个"以上都不是"。
    """
    seen: List[str] = []
    seen_set = set()
    for pid in phase_ids:
        for c in categories_for_phase(pid):
            if c not in seen_set:
                seen.append(c)
                seen_set.add(c)
    return seen


def likelihood_for_category_answer(
    phase_id: str,
    chosen_categories: List[str],
    answer: str,
    phase_predicts_at_year: bool = True,
) -> float:
    """给定 phase + 用户在题里勾选的事件类别 + discrete 答案，估似然。

    answer ∈ {"yes", "partial", "no", "dunno"}
    chosen_categories: 用户勾的类别。可以包含 NONE_OF_ABOVE sentinel。
    phase_predicts_at_year: **本 phase 在被问的这一年是否预测有事件**。
                            False = 本 phase 在这一年没说要有事 → 用户答任何答案
                            对它都是中性（它没有"赌"过这一年）。

    v3 修正（2026-04 上线后用户报"为什么不继续收敛"才发现）：
      - 旧版 likelihood 完全靠 categories_for_phase 全局列表，
        把"phase 在这一年是否预测"和"phase 整体是否有类别"两件事混在一起
      - day_master_dominant 全局 categories=[] 但它不是"承诺这一年没事"，
        而是"对所有年份都不下具体预测"
      - 修正：phase_predicts_at_year=False 的 phase 一律返回 0.5（中性）
      - phase_predicts_at_year=True 时按本 phase 的 categories 算具体似然

    分支表（phase_predicts_at_year=True，即本 phase 预测了这一年有事）：
      | answer | chosen 内容 | phase 有 categories | likelihood |
      | yes    | 命中 phase 预测 | 是 | 0.85 |
      | yes    | 与 phase 预测无交集 | 是 | 0.15 |
      | yes    | 部分命中 | 是 | 0.15 ~ 0.85 线性 |
      | yes    | 「以上都不是」 | 是 | 0.25（phase 错预测了一件未发生的事）|
      | yes    | 「以上都不是」 | 否 | 0.50（phase 没具体预测）|
      | yes    | 全空（信息缺失）| 任意 | 0.50 |
      | partial| 任意 | 任意 | 0.40 |
      | no     | （chosen 应为空） | 是 | 0.20（phase 预测了 → 用户说没发生 → 矛盾）|
      | no     | （chosen 应为空） | 否 | 0.50 |
      | dunno  | 任意 | 任意 | 0.50 |

    phase_predicts_at_year=False（phase 没说这一年要有事）→ 一律 0.5（中性）
    """
    if answer == "dunno":
        return 0.5

    # 本 phase 在这一年没预测事件 → 用户答案对它是中性（它没"赌"过）
    if not phase_predicts_at_year:
        return 0.5

    pred = set(categories_for_phase(phase_id))

    if answer == "no":
        if not pred:
            return 0.5
        # phase 预测了事件 + 用户说没发生 → 强矛盾
        return 0.2

    if answer == "partial":
        return 0.4

    # ─── answer == "yes" ───
    chosen = set(chosen_categories or [])

    if not chosen:
        return 0.5

    if NONE_OF_ABOVE in chosen:
        return 0.25 if pred else 0.5

    if not pred:
        # phase 预测了这一年有事但 categories 空（罕见，如 trigger_branch
        # 命中但 PHASE_EVENT_CATEGORIES 没填）→ 用户勾了类别也无法对照 → 中性
        return 0.5

    overlap = pred & chosen
    if not overlap:
        return 0.15
    overlap_ratio = len(overlap) / len(chosen)
    return 0.15 + overlap_ratio * 0.70


# ─── CLI · 调试 ─────────────────────────────────────────

def _cli() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="phase 事件类别查询")
    ap.add_argument("--phase", required=True)
    args = ap.parse_args()
    cats = categories_for_phase(args.phase)
    if not cats:
        print(f"{args.phase}: 无事件类别预测（pure structure phase）")
    else:
        print(f"{args.phase} 预测以下事件类别：")
        for c in cats:
            print(f"  · {c}")


if __name__ == "__main__":
    _cli()
