#!/usr/bin/env python3
"""mangpai_events.py — 盲派经典组合识别 → 事件断 + 烈度修正建议

定位（详见 references/mangpai_protocol.md）：
  - 盲派不进入三派（扶抑/调候/格局）的 25% 打分融合权重
  - 盲派负责两件事：
      (a) 应事断：YYYY 年应什么具体事件（写入 events 列表，供 LLM 取象引用）
      (b) 烈度修正：在三派融合后的曲线上 ±烈度档（重±8 中±4 轻±2）

为什么不进打分融合：
  - 盲派内部不同师承（段建业/王虎应/李洪成）规则差异大，融合反而引入噪声
  - 盲派的强项是"应事/应期"，跟 0-100 分量化天然不兼容
  - 把它当"事件触发器 + 烈度调整器"，扬长避短

机械识别的 11 条经典组合（每条都引出处与可证伪条件）：
  1. 伤官见官      段建业《盲派命理》
  2. 官杀混杂      《滴天髓》《盲派命理》通用
  3. 比劫夺财      盲派民间口诀
  4. 禄被冲        段建业《盲派命理》
  5. 羊刃逢冲      盲派民间口诀
  6. 食神制杀      盲派/格局派共认
  7. 七杀逢印      盲派/格局派共认
  8. 伤官伤尽      王虎应解
  9. 反吟应期      盲派"应期"模型
  10. 伏吟应期     盲派"应期"模型
  11. 财库被冲开   盲派/格局派共认

  + 1 条静态标记：年财不归我（终生标记，不绑定流年）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bazi_core import (
    Pillar,
    GAN, ZHI, GAN_WUXING, ZHI_WUXING, ZHI_HIDDEN_GAN, GAN_YIN_YANG,
    WUXING_SHENG, WUXING_KE,
    ZHI_CHONG,
    KU_BENQI,
    calc_shishen, calc_zhi_shishen,
    is_fuyin, is_fanyin,
    liunian_pillar,
)


# 日干禄位（建禄）
LU_TABLE = {
    "甲": "寅", "乙": "卯",
    "丙": "巳", "丁": "午",
    "戊": "巳", "己": "午",
    "庚": "申", "辛": "酉",
    "壬": "亥", "癸": "子",
}

# 阳干羊刃（帝旺位）
YANGREN_TABLE = {
    "甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子",
}

# 烈度档 → 修正额度
INTENSITY_AMPLIFIER = {"重": 8, "中": 4, "轻": 2}


# ---------- 工具 ----------

def _all_gans(pillars: List[Pillar]) -> List[str]:
    return [p.gan for p in pillars]


def _all_zhi_main_gans(pillars: List[Pillar]) -> List[str]:
    return [ZHI_HIDDEN_GAN[p.zhi][0] for p in pillars]


def _shishen_present(day_gan: str, gans: List[str], zhis: List[str], target_shishen: str) -> List[str]:
    """返回 gans/zhis 中所有匹配 target_shishen 的位置标记，如 ['年干', '月支主气']。"""
    out = []
    for i, g in enumerate(gans):
        if calc_shishen(day_gan, g) == target_shishen:
            out.append(["年", "月", "日", "时"][i] + "干")
    for i, z in enumerate(zhis):
        main = ZHI_HIDDEN_GAN[z][0]
        if calc_shishen(day_gan, main) == target_shishen:
            out.append(["年", "月", "日", "时"][i] + "支")
    return out


def _has_shishen_in_pillars(day_gan: str, pillars: List[Pillar], shishen: str) -> List[str]:
    return _shishen_present(day_gan, _all_gans(pillars), [p.zhi for p in pillars], shishen)


def _ku_with_what(zhi: str, day_gan: str) -> Optional[str]:
    """库藏的本气十神（戊辰库藏癸 → 视该癸的十神）。返回十神或 None。"""
    if zhi not in KU_BENQI:
        return None
    benqi = KU_BENQI[zhi]
    return calc_shishen(day_gan, benqi)


# ---------- 各组合检测器（每个返回 Optional[Event]） ----------

def _evt(year: int, age: int, ganzhi: str, dayun: str, key: str, name: str,
         school: str, canonical: str, dims: List[Tuple[str, int]],
         intensity: str, evidence: str, reference: str,
         falsifiability: str) -> Dict:
    amplifier = {dim: INTENSITY_AMPLIFIER[intensity] * sign for dim, sign in dims}
    return {
        "year": year,
        "age": age,
        "ganzhi": ganzhi,
        "dayun": dayun,
        "key": key,
        "name": name,
        "school": school,
        "canonical_event": canonical,
        "dimensions": [{"dim": d, "sign": s} for d, s in dims],
        "intensity": intensity,
        "amplifier": amplifier,
        "evidence": evidence,
        "reference": reference,
        "falsifiability": falsifiability,
    }


def _natal_has(day_gan: str, natal: List[Pillar], shishen_set) -> bool:
    if isinstance(shishen_set, str):
        shishen_set = {shishen_set}
    for p in natal:
        if calc_shishen(day_gan, p.gan) in shishen_set:
            return True
        if calc_zhi_shishen(day_gan, p.zhi) in shishen_set:
            return True
    return False


def _motion_has(day_gan: str, motion: List[Pillar], shishen_set) -> Optional[str]:
    """检查 motion(大运/流年) 中是否带某十神，返回 evidence 或 None。"""
    if isinstance(shishen_set, str):
        shishen_set = {shishen_set}
    found = []
    for p, name in motion:
        gsh = calc_shishen(day_gan, p.gan)
        zsh = calc_zhi_shishen(day_gan, p.zhi)
        if gsh in shishen_set:
            found.append(f"{name}天干{p.gan}={gsh}")
        if zsh in shishen_set:
            found.append(f"{name}地支{p.zhi}主气={zsh}")
    return "; ".join(found) if found else None


def _liunian_has(day_gan: str, ln: Pillar, target_set) -> Optional[str]:
    """流年（仅看 ln 自身）是否带某十神。返回 evidence 或 None。"""
    if isinstance(target_set, str):
        target_set = {target_set}
    gsh = calc_shishen(day_gan, ln.gan)
    zsh = calc_zhi_shishen(day_gan, ln.zhi)
    parts = []
    if gsh in target_set:
        parts.append(f"流年天干{ln.gan}={gsh}")
    if zsh in target_set:
        parts.append(f"流年地支{ln.zhi}主气={zsh}")
    return "; ".join(parts) if parts else None


def _dayun_amplifier(day_gan: str, dy: Pillar, target_set) -> str:
    """大运是否额外带某十神（用于事件 evidence 加注）。"""
    if isinstance(target_set, str):
        target_set = {target_set}
    gsh = calc_shishen(day_gan, dy.gan)
    zsh = calc_zhi_shishen(day_gan, dy.zhi)
    parts = []
    if gsh in target_set:
        parts.append(f"大运天干{dy.gan}={gsh}")
    if zsh in target_set:
        parts.append(f"大运地支{dy.zhi}主气={zsh}")
    return "（大运同向加成：" + "; ".join(parts) + "）" if parts else ""


def detect_shang_guan_jian_guan(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[Tuple[str, str]]:
    """伤官见官应期：原局有一方但缺另一方，且**流年**补出才算应期。
    原局两边都有 → 是终生背景，不算流年事件。
    """
    natal_has_shang = _natal_has(day_gan, natal, "伤官")
    natal_has_guan = _natal_has(day_gan, natal, "正官")
    if natal_has_shang and natal_has_guan:
        return None
    if not (natal_has_shang or natal_has_guan):
        return None
    if natal_has_shang and not natal_has_guan:
        ev = _liunian_has(day_gan, ln, "正官")
        if ev:
            amp = _dayun_amplifier(day_gan, dy, "正官")
            return f"原局有伤官缺正官，{ev} → 应期 {amp}", ""
    if natal_has_guan and not natal_has_shang:
        ev = _liunian_has(day_gan, ln, "伤官")
        if ev:
            amp = _dayun_amplifier(day_gan, dy, "伤官")
            return f"原局有正官缺伤官，{ev} → 应期 {amp}", ""
    return None


def detect_guan_sha_hun_za(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[str]:
    """官杀混杂应期：原局有官无杀（或有杀无官），且**流年**补出另一方才算应期。"""
    natal_zheng = _natal_has(day_gan, natal, "正官")
    natal_qi = _natal_has(day_gan, natal, "七杀")
    if natal_zheng and natal_qi:
        return None
    if not (natal_zheng or natal_qi):
        return None
    if natal_zheng and not natal_qi:
        ev = _liunian_has(day_gan, ln, "七杀")
        if ev:
            amp = _dayun_amplifier(day_gan, dy, "七杀")
            return f"原局有正官无七杀，{ev} → 补出七杀 {amp}"
    if natal_qi and not natal_zheng:
        ev = _liunian_has(day_gan, ln, "正官")
        if ev:
            amp = _dayun_amplifier(day_gan, dy, "正官")
            return f"原局有七杀无正官，{ev} → 补出正官 {amp}"
    return None


def detect_bi_jie_duo_cai(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[str]:
    """比劫夺财应期：原局有财，**流年**带比肩/劫财。"""
    if not _natal_has(day_gan, natal, {"正财", "偏财"}):
        return None
    ev = _liunian_has(day_gan, ln, {"比肩", "劫财"})
    if not ev:
        return None
    amp = _dayun_amplifier(day_gan, dy, {"比肩", "劫财"})
    return f"原局有财，{ev} {amp}"


def detect_lu_chong(day_gan: str, ln: Pillar) -> Optional[str]:
    """禄被冲：日干禄位被流年地支冲。"""
    lu = LU_TABLE.get(day_gan)
    if not lu:
        return None
    if ZHI_CHONG.get(lu) == ln.zhi:
        return f"日干{day_gan}的禄位={lu}，流年支={ln.zhi}（{lu}{ln.zhi}相冲）"
    return None


def detect_yangren_chong(day_gan: str, ln: Pillar) -> Optional[str]:
    """羊刃逢冲：阳干日主，羊刃被流年支冲。"""
    yr = YANGREN_TABLE.get(day_gan)
    if not yr:
        return None
    if ZHI_CHONG.get(yr) == ln.zhi:
        return f"日干{day_gan}的羊刃={yr}，流年支={ln.zhi}（{yr}{ln.zhi}相冲）"
    return None


def detect_shi_shen_zhi_sha(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[str]:
    """食神制杀应期：原局有七杀，且流年天干带食神（强触发）；
    若大运也是食神则烈度更高，但本检测要求流年才算应期。"""
    if not _natal_has(day_gan, natal, "七杀"):
        return None
    if calc_shishen(day_gan, ln.gan) != "食神":
        return None
    extra = ""
    if calc_shishen(day_gan, dy.gan) == "食神":
        extra = "，且大运{dyg}也是食神，化煞力度倍增".format(dyg=dy.gan)
    return f"原局有七杀，流年{ln.gan}={('食神')}{extra}"


def detect_qi_sha_feng_yin(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[str]:
    """七杀逢印应期：原局七杀，流年天干带印星（杀印相生）。"""
    if not _natal_has(day_gan, natal, "七杀"):
        return None
    gsh = calc_shishen(day_gan, ln.gan)
    if gsh not in ("正印", "偏印"):
        return None
    extra = ""
    if calc_shishen(day_gan, dy.gan) in ("正印", "偏印"):
        extra = "，且大运{dyg}也是印星，杀印相生格成立".format(dyg=dy.gan)
    return f"原局有七杀，流年{ln.gan}={gsh}{extra}"


def detect_shang_guan_shang_jin(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[str]:
    """伤官伤尽（王虎应解）：原局伤官 ≥ 2 见，流年/大运再引动伤官。"""
    natal_shang_count = sum(
        1 for p in natal
        if calc_shishen(day_gan, p.gan) == "伤官" or calc_zhi_shishen(day_gan, p.zhi) == "伤官"
    )
    if natal_shang_count < 2:
        return None
    motion_shang = []
    for p, name in [(dy, "大运"), (ln, "流年")]:
        if calc_shishen(day_gan, p.gan) == "伤官" or calc_zhi_shishen(day_gan, p.zhi) == "伤官":
            motion_shang.append(f"{name}({p.gan}{p.zhi})")
    if not motion_shang:
        return None
    return f"原局伤官 {natal_shang_count} 见，{','.join(motion_shang)} 再引动"


def detect_fanyin_yingqi(natal: List[Pillar], ln: Pillar) -> Optional[str]:
    """反吟应期（盲派特别关注）：流年与日柱天克地冲。"""
    if is_fanyin(natal[2], ln):
        return f"流年{ln.gan}{ln.zhi} 与 日柱{natal[2].gan}{natal[2].zhi} 天克地冲"
    return None


def detect_fuyin_yingqi(natal: List[Pillar], ln: Pillar) -> Optional[Tuple[str, int]]:
    """伏吟应期：流年与原局某柱伏吟。返回 (evidence, 柱位 0/1/2/3) 或 None。"""
    for i, p in enumerate(natal):
        if is_fuyin(p, ln):
            return f"流年{ln.gan}{ln.zhi} 与 {['年','月','日','时'][i]}柱伏吟", i
    return None


def detect_dayun_fuyin_natal(natal: List[Pillar], dy: Pillar) -> Optional[Tuple[str, int]]:
    """v9 PR-3 · 大运伏吟原局某柱。返回 (evidence, 柱位) 或 None。

    盲派：大运伏吟某柱 → 该柱所主十年情境被'十年级'地放大 / 凝固。
    比 流年伏吟 影响时长 × 10。
    """
    for i, p in enumerate(natal):
        if is_fuyin(p, dy):
            return (
                f"大运{dy.gan}{dy.zhi} 与 {['年','月','日','时'][i]}柱"
                f"({p.gan}{p.zhi}) 伏吟",
                i,
            )
    return None


def detect_dayun_fanyin_rizhu(natal: List[Pillar], dy: Pillar) -> Optional[str]:
    """v9 PR-3 · 大运反吟日柱（天克地冲）。

    盲派：大运天克地冲日主 → 该 10 年身体 / 居所 / 婚姻 / 立身根基级别震荡。
    比单流年反吟 严重得多，常对应大事件群（搬迁、婚变、重病、转行）。
    """
    if is_fanyin(natal[2], dy):
        return (
            f"大运{dy.gan}{dy.zhi} 与 日柱{natal[2].gan}{natal[2].zhi} 天克地冲；"
            f"十年级根基震荡"
        )
    return None


def detect_liunian_fuyin_dayun(dy: Pillar, ln: Pillar) -> Optional[str]:
    """v9 PR-3 · 流年伏吟当下大运。

    盲派：流年与大运同柱 → 该年的大运主题被'当年放大'，常对应大运
    标志性事件的高发年。
    """
    if is_fuyin(dy, ln):
        return f"流年{ln.gan}{ln.zhi} 与 大运{dy.gan}{dy.zhi} 伏吟；大运主题年内集中爆发"
    return None


def detect_liunian_fanyin_dayun(dy: Pillar, ln: Pillar) -> Optional[str]:
    """v9 PR-3 · 流年反吟当下大运（天克地冲）。

    盲派：流年天克地冲大运 → 该年与大运主题对撞，常应'大运主题被打断'
    或'大运转折点提前'。
    """
    if is_fanyin(dy, ln):
        return f"流年{ln.gan}{ln.zhi} 与 大运{dy.gan}{dy.zhi} 天克地冲；大运主题对撞"
    return None


def detect_cai_ku_chong_kai(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar
) -> Optional[str]:
    """财库被冲开：原局/大运有财库（辰戌丑未中藏的本气是财），被流年支冲开。"""
    candidates = []
    for p in natal + [dy]:
        z = p.zhi
        ku_ss = _ku_with_what(z, day_gan)
        if ku_ss in ("正财", "偏财"):
            if ZHI_CHONG.get(z) == ln.zhi:
                candidates.append(f"{z}({KU_BENQI[z]}{ku_ss}库) 被流年{ln.zhi}冲开")
    if not candidates:
        return None
    return "; ".join(candidates)


# ---------- 静态标记 ----------

def detect_static_markers(day_gan: str, natal: List[Pillar]) -> List[Dict]:
    """返回不绑定流年的终生标记。"""
    markers = []
    # 年财不归我：年柱有正财，但年柱与日支/月支无合无生
    year_p = natal[0]
    year_gan_ss = calc_shishen(day_gan, year_p.gan)
    year_zhi_ss = calc_zhi_shishen(day_gan, year_p.zhi)
    has_year_cai = year_gan_ss in ("正财", "偏财") or year_zhi_ss in ("正财", "偏财")
    if has_year_cai:
        # 简化判定：年支与日支/月支 无三合 / 无六合 即视为"不归我"
        connected = False
        from _bazi_core import ZHI_LIUHE, SANHE_GROUPS
        for other_zhi in [natal[1].zhi, natal[2].zhi]:
            if ZHI_LIUHE.get(year_p.zhi) == other_zhi:
                connected = True
                break
            for group, _ in SANHE_GROUPS:
                if year_p.zhi in group and other_zhi in group:
                    connected = True
                    break
        if not connected:
            markers.append({
                "key": "nian_cai_bu_gui_wo",
                "name": "年财不归我",
                "school": "盲派民间口诀",
                "canonical_event": "原生家庭 / 长辈层面的财在你之外，不直接归你掌控；你需要自己另起炉灶",
                "dimensions": [{"dim": "wealth", "sign": 0}],
                "intensity": "静态",
                "amplifier": {},
                "evidence": f"年柱={year_p.gan}{year_p.zhi}，{year_gan_ss}/{year_zhi_ss}，且年支与日/月支无六合无三合",
                "reference": "盲派民间口诀（段建业《盲派命理》收录）",
                "falsifiability": "如果你成年后确实大量继承 / 直接享用了原生家庭的财（房产、生意、长辈遗产已转入你名下），这条就是错的",
            })
    return markers


# ---------- 主调度 ----------

DETECTOR_REGISTRY = [
    {
        "key": "shang_guan_jian_guan",
        "name": "伤官见官",
        "school": "段建业《盲派命理》",
        "fn": detect_shang_guan_jian_guan,
        "uses_dy_ln": True,
        "canonical_event": "与权威 / 上司 / 体制摩擦；可能涉及官非、降职、离职、合同纠纷，或主动跟旧规则切割",
        "dims": [("fame", -1), ("spirit", -1)],
        "intensity": "重",
        "falsifiability": "如果该年没有任何与权威 / 体制 / 规则的摩擦事件（无离职、无纠纷、无主动切割），这条就是错的",
    },
    {
        "key": "guan_sha_hun_za",
        "name": "官杀混杂",
        "school": "《滴天髓》《盲派命理》通用",
        "fn": detect_guan_sha_hun_za,
        "uses_dy_ln": True,
        "canonical_event": "身份 / 职业 / 婚姻同时承受多重压力，左右为难、不易决断；女命常应婚姻波折",
        "dims": [("spirit", -1)],
        "intensity": "中",
        "falsifiability": "如果该年并无『被多重身份 / 责任挤压』的明显感受，这条就是错的",
    },
    {
        "key": "bi_jie_duo_cai",
        "name": "比劫夺财",
        "school": "盲派民间口诀",
        "fn": detect_bi_jie_duo_cai,
        "uses_dy_ln": True,
        "canonical_event": "合伙折利、被分财、借出不还，或配偶 / 兄弟姐妹层面的财务受损",
        "dims": [("wealth", -1)],
        "intensity": "中",
        "falsifiability": "如果该年财务上既无被分走、无借出不还、配偶 / 兄弟姐妹也无财务损失，这条就是错的",
    },
    {
        "key": "lu_chong",
        "name": "禄被冲",
        "school": "段建业《盲派命理》",
        "fn": detect_lu_chong,
        "uses_dy_ln": False,
        "canonical_event": "移居 / 工作变动 / 关键关系切换，或身体上有意外（轻则磕碰，重则大病大手术）",
        "dims": [("spirit", -1)],
        "intensity": "重",
        "falsifiability": "如果该年既无明显的居所 / 职业切换，又无身体上的强变动，这条就是错的",
    },
    {
        "key": "yangren_chong",
        "name": "羊刃逢冲",
        "school": "盲派民间口诀",
        "fn": detect_yangren_chong,
        "uses_dy_ln": False,
        "canonical_event": "突发性事件多发——意外、争执、强烈情绪爆发，或主动做出激烈的决定",
        "dims": [("spirit", -1)],
        "intensity": "中",
        "falsifiability": "如果该年没有任何突发性事件 / 强烈情绪爆发 / 激烈决定，这条就是错的",
    },
    {
        "key": "shi_shen_zhi_sha",
        "name": "食神制杀",
        "school": "盲派 / 格局派共认",
        "fn": detect_shi_shen_zhi_sha,
        "uses_dy_ln": True,
        "canonical_event": "把外部压力 / 挑战转化为产出（作品、项目、决策成果），化煞为权",
        "dims": [("fame", 1), ("wealth", 1)],
        "intensity": "中",
        "falsifiability": "如果该年并未产出明显的'用作品 / 项目化解压力'的事件，这条就是错的",
    },
    {
        "key": "qi_sha_feng_yin",
        "name": "七杀逢印（杀印相生）",
        "school": "盲派 / 格局派共认",
        "fn": detect_qi_sha_feng_yin,
        "uses_dy_ln": True,
        "canonical_event": "贵人扶持 / 上级提拔 / 进入更高的体系；压力被转化为身份提升",
        "dims": [("fame", 1)],
        "intensity": "中",
        "falsifiability": "如果该年没有贵人 / 上级 / 体系层面的提拔或接纳，这条就是错的",
    },
    {
        "key": "shang_guan_shang_jin",
        "name": "伤官伤尽",
        "school": "王虎应解",
        "fn": detect_shang_guan_shang_jin,
        "uses_dy_ln": True,
        "canonical_event": "才华突破 / 跟旧体制告别 / 自立山头；可能伴随短期高光后的代价",
        "dims": [("fame", 1), ("spirit", 0)],
        "intensity": "中",
        "falsifiability": "如果该年既无才华上的突破，也无主动跟旧体制告别的事件，这条就是错的",
    },
    {
        "key": "fanyin_yingqi",
        "name": "反吟应期",
        "school": "盲派应期模型",
        "fn": detect_fanyin_yingqi,
        "uses_dy_ln": False,
        "natal_only": True,
        "canonical_event": "天克地冲应期：身体 / 居所 / 关系层面的剧变，常应'一翻一覆'——先得后失或先失后得",
        "dims": [("spirit", -1), ("wealth", 0)],
        "intensity": "重",
        "falsifiability": "如果该年并无身体 / 居所 / 关系的剧变事件（哪怕是先得后失），这条就是错的",
    },
    {
        "key": "fuyin_yingqi",
        "name": "伏吟应期",
        "school": "盲派应期模型",
        "fn": detect_fuyin_yingqi,
        "uses_dy_ln": False,
        "natal_only": True,
        "canonical_event": "旧事重演 / 必须直面同一类课题；情绪上多内省、纠结、'怎么又是这个'",
        "dims": [("spirit", -1)],
        "intensity": "中",
        "falsifiability": "如果该年并未出现重复性的旧事 / 旧关系 / 旧课题再现，这条就是错的",
    },
    {
        "key": "cai_ku_chong_kai",
        "name": "财库被冲开",
        "school": "盲派 / 格局派共认",
        "fn": detect_cai_ku_chong_kai,
        "uses_dy_ln": True,
        "canonical_event": "财务结构跳档：要么得财（库开则发），要么破财（开出忌神字），具体方向看本命用神",
        "dims": [("wealth", 1)],
        "intensity": "重",
        "falsifiability": "如果该年财务结构毫无波动（既无大笔进出也无资产形态变化），这条就是错的",
    },
    # v9 PR-3 · 大运层 反吟伏吟（每个大运段触发一次,而非按年）
    {
        "key": "dayun_fuyin_natal",
        "name": "大运伏吟原局",
        "school": "盲派应期模型 v9",
        "fn": detect_dayun_fuyin_natal,
        "uses_dy_ln": False,
        "dayun_only": True,  # 新签名: fn(natal, dy)
        "canonical_event": (
            "十年级凝固/放大: 该柱所主的人生面向(年=祖业童年/月=父母事业/"
            "日=婚姻自身/时=子女晚景)被'重复刻进十年',常应反复同一类大事件"
        ),
        "dims": [("spirit", -1)],
        "intensity": "重",
        "falsifiability": "如果该大运十年中,所伏吟柱位主管的人生面向毫无重复性大事,这条就错了",
    },
    {
        "key": "dayun_fanyin_rizhu",
        "name": "大运反吟日柱",
        "school": "盲派应期模型 v9",
        "fn": detect_dayun_fanyin_rizhu,
        "uses_dy_ln": False,
        "dayun_only": True,
        "canonical_event": (
            "十年级根基震荡: 身体/居所/婚姻/立身根基级别的大事群(搬迁/婚变/重病/转行/移民)"
        ),
        "dims": [("spirit", -1), ("wealth", -1)],
        "intensity": "重",
        "falsifiability": "如果该大运十年中并无根基级别大事(身体/婚姻/居所/职业有重大转折),这条就错了",
    },
    {
        "key": "liunian_fuyin_dayun",
        "name": "流年伏吟大运",
        "school": "盲派应期模型 v9",
        "fn": detect_liunian_fuyin_dayun,
        "uses_dy_ln": False,
        "dayun_ln_only": True,  # 新签名: fn(dy, ln)
        "canonical_event": "大运主题在该年集中爆发,标志性事件高发年",
        "dims": [("fame", 1)],
        "intensity": "中",
        "falsifiability": "如果该年并未发生与大运主题强相关的标志性事件,这条就错了",
    },
    {
        "key": "liunian_fanyin_dayun",
        "name": "流年反吟大运",
        "school": "盲派应期模型 v9",
        "fn": detect_liunian_fanyin_dayun,
        "uses_dy_ln": False,
        "dayun_ln_only": True,
        "canonical_event": "大运主题对撞: 该年常应'大运主题被打断'或'大运转折点提前'",
        "dims": [("spirit", -1)],
        "intensity": "中",
        "falsifiability": "如果该年与所在大运的主题轨迹完全平稳无对撞,这条就错了",
    },
]


def detect_year_events(
    day_gan: str, natal: List[Pillar], dy: Pillar, ln: Pillar,
    year: int, age: int, dayun_label: str,
    is_dayun_first_year: bool = False,
) -> List[Dict]:
    """v9 PR-3: 新增 is_dayun_first_year 参数.

    当 is_dayun_first_year=True 时, dayun_only detector (fn(natal, dy))
    才会触发并仅在该大运首年记录一次, 避免大运 detector 被流年级触发 10 次.
    """
    out = []
    for d in DETECTOR_REGISTRY:
        fn = d["fn"]
        if d.get("dayun_only"):
            if not is_dayun_first_year:
                continue
            evidence = fn(natal, dy)
        elif d.get("dayun_ln_only"):
            evidence = fn(dy, ln)
        elif d.get("natal_only"):
            evidence = fn(natal, ln)
        elif d["uses_dy_ln"]:
            evidence = fn(day_gan, natal, dy, ln)
        else:
            evidence = fn(day_gan, ln)
        if evidence is None:
            continue
        if isinstance(evidence, tuple):
            evidence = evidence[0]
        out.append(_evt(
            year=year, age=age, ganzhi=ln.gan + ln.zhi, dayun=dayun_label,
            key=d["key"], name=d["name"], school=d["school"],
            canonical=d["canonical_event"], dims=d["dims"],
            intensity=d["intensity"], evidence=evidence,
            reference=d["school"], falsifiability=d["falsifiability"],
        ))
    return out


def detect_all(bazi: dict, age_start: int = 0, age_end: int = 80) -> Dict:
    natal = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = natal[2].gan
    dayun = bazi["dayun"]
    liunian = bazi["liunian"]

    def find_dayun(age: int):
        for d in dayun:
            if d["start_age"] <= age <= d["end_age"]:
                return d
        return None

    events: List[Dict] = []
    for ln in liunian:
        age = ln["age"]
        if age < age_start or age > age_end:
            continue
        dy = find_dayun(age)
        if dy is None:
            dy_p = Pillar(natal[1].gan, natal[1].zhi)
            dy_label = "起运前"
            is_dy_first = False
        else:
            dy_p = Pillar(dy["gan"], dy["zhi"])
            dy_label = dy["gan"] + dy["zhi"]
            is_dy_first = (age == dy["start_age"])
        ln_p = Pillar(ln["gan"], ln["zhi"])
        events.extend(detect_year_events(
            day_gan, natal, dy_p, ln_p, ln["year"], age, dy_label,
            is_dayun_first_year=is_dy_first,
        ))

    static = detect_static_markers(day_gan, natal)

    return {
        "version": 1,
        "school_position": "mangpai (盲派) — 不进 25% 打分融合，仅做应事断 + 烈度修正",
        "intensity_amplifier_table": INTENSITY_AMPLIFIER,
        "static_markers": static,
        "events": events,
        "events_count_by_key": {
            d["key"]: sum(1 for e in events if e["key"] == d["key"])
            for d in DETECTOR_REGISTRY
        },
    }


def main():
    ap = argparse.ArgumentParser(description="盲派经典组合事件检测")
    ap.add_argument("--bazi", required=True)
    ap.add_argument("--out", default="mangpai.json")
    ap.add_argument("--age-start", type=int, default=0)
    ap.add_argument("--age-end", type=int, default=80)
    args = ap.parse_args()

    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    result = detect_all(bazi, args.age_start, args.age_end)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = result["events_count_by_key"]
    nonzero = {k: v for k, v in counts.items() if v}
    print(f"[mangpai_events] wrote {args.out}: {len(result['events'])} 流年事件 + "
          f"{len(result['static_markers'])} 静态标记")
    if nonzero:
        print(f"  按组合: {nonzero}")


if __name__ == "__main__":
    main()
