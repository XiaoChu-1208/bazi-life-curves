#!/usr/bin/env python3
"""rare_phase_detector.py — v9 PR-5 算法可判定的特殊格批量扫描器

对 references/rare_phases_catalog.md 中 "算法可判定=Yes" 的条目实现 detector.
每个 detector 签名: (pillars: List[Pillar], day_gan: str, ...) -> Optional[Dict].

返回 None 表示未触发; 返回 dict {id, school, evidence, confidence} 表示触发.

注: 这里不实现 ratify_only (Tier 3 紫微/铁板) 的判定 — 那部分由 LLM fallback
协议化指令在对话里完成 (参 references/llm_fallback_protocol.md).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from _bazi_core import (
    GAN, ZHI, GAN_WUXING, ZHI_WUXING, ZHI_HIDDEN_GAN,
    WUXING_SHENG, WUXING_KE, ZHI_CHONG,
    Pillar, calc_shishen, calc_zhi_shishen,
    compute_dayuan_root_strength,
)


# ============================================================
# 工具函数
# ============================================================

def _all_stems(pillars: List[Pillar]) -> List[str]:
    return [p.gan for p in pillars]


def _all_branches(pillars: List[Pillar]) -> List[str]:
    return [p.zhi for p in pillars]


def _shishen_count(day_gan: str, pillars: List[Pillar]) -> Dict[str, int]:
    """十神出现次数 (干 + 支主气)."""
    cnt: Dict[str, int] = {}
    for i, p in enumerate(pillars):
        if i != 2:
            ss = calc_shishen(day_gan, p.gan)
            cnt[ss] = cnt.get(ss, 0) + 1
        ss_z = calc_zhi_shishen(day_gan, p.zhi)
        cnt[ss_z] = cnt.get(ss_z, 0) + 1
    return cnt


# ============================================================
# Tier 1.A · 八正格 (10 条 → 取 8 + 建禄阳刃 2 = 10)
# ============================================================

# 月令本气透干: 月支主气在天干 (年/月/时柱) 出现 → 月令格成立
def _month_qi_transparent(pillars: List[Pillar], day_gan: str) -> Optional[str]:
    month_zhi = pillars[1].zhi
    main_hidden = ZHI_HIDDEN_GAN[month_zhi][0]
    stems_other = [p.gan for i, p in enumerate(pillars) if i != 2]
    if main_hidden in stems_other:
        ss = calc_shishen(day_gan, main_hidden)
        return ss
    return None


def detect_zhengguan_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "正官":
        return {"id": "zhengguan_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为正官", "confidence": 0.85}


def detect_qisha_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "七杀":
        return {"id": "qisha_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为七杀", "confidence": 0.85}


def detect_zhengyin_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "正印":
        return {"id": "zhengyin_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为正印", "confidence": 0.85}


def detect_pianyin_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "偏印":
        return {"id": "pianyin_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为偏印", "confidence": 0.85}


def detect_shishen_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "食神":
        return {"id": "shishen_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为食神", "confidence": 0.85}


def detect_shangguan_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "伤官":
        return {"id": "shangguan_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为伤官", "confidence": 0.85}


def detect_zhengcai_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "正财":
        return {"id": "zhengcai_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为正财", "confidence": 0.85}


def detect_piancai_ge(pillars, day_gan):
    if _month_qi_transparent(pillars, day_gan) == "偏财":
        return {"id": "piancai_ge", "school": "ziping_zhenquan",
                "evidence": "月令本气透干为偏财", "confidence": 0.85}


JIANLU_MAP = {"甲": "寅", "乙": "卯", "丙": "巳", "丁": "午",
              "戊": "巳", "己": "午", "庚": "申", "辛": "酉",
              "壬": "亥", "癸": "子"}

YANGREN_MAP = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}


def detect_jianlu_ge(pillars, day_gan):
    if pillars[1].zhi == JIANLU_MAP.get(day_gan):
        return {"id": "jianlu_ge", "school": "ziping_zhenquan",
                "evidence": f"日主{day_gan}临月令禄位{JIANLU_MAP[day_gan]}",
                "confidence": 0.95}


def detect_yangren_ge(pillars, day_gan):
    if day_gan in YANGREN_MAP and pillars[1].zhi == YANGREN_MAP[day_gan]:
        return {"id": "yangren_ge", "school": "ziping_zhenquan",
                "evidence": f"阳干{day_gan}临月令刃位{YANGREN_MAP[day_gan]}",
                "confidence": 0.95}


# ============================================================
# Tier 1.D · 杂格 (实现高频 / 易判几条)
# ============================================================

KUIGANG_RIZHU = {("庚", "辰"), ("庚", "戌"), ("壬", "辰"), ("戊", "戌")}
JINSHEN_RIZHU = {("乙", "丑"), ("己", "巳"), ("癸", "酉")}
RIDE_RIZHU = {("甲", "寅"), ("丙", "辰"), ("戊", "辰"), ("庚", "辰"), ("壬", "戌")}
RIGUI_RIZHU = {("丁", "酉"), ("丁", "亥"), ("癸", "卯"), ("癸", "巳")}
RIREN_RIZHU = {("戊", "午"), ("丙", "午"), ("壬", "子")}


def detect_kuigang_ge(pillars, day_gan):
    if (pillars[2].gan, pillars[2].zhi) in KUIGANG_RIZHU:
        return {"id": "kuigang_ge", "school": "yuanhai_ziping",
                "evidence": f"日柱{pillars[2].gan}{pillars[2].zhi} 为魁罡",
                "confidence": 0.95}


def detect_jinshen_ge(pillars, day_gan):
    if (pillars[2].gan, pillars[2].zhi) in JINSHEN_RIZHU:
        return {"id": "jinshen_ge", "school": "yuanhai_ziping",
                "evidence": f"日柱{pillars[2].gan}{pillars[2].zhi} 为金神",
                "confidence": 0.95}


def detect_ride_ge(pillars, day_gan):
    if (pillars[2].gan, pillars[2].zhi) in RIDE_RIZHU:
        return {"id": "ride_ge", "school": "sanming_tonghui",
                "evidence": f"日柱{pillars[2].gan}{pillars[2].zhi} 为日德",
                "confidence": 0.90}


def detect_rigui_ge(pillars, day_gan):
    if (pillars[2].gan, pillars[2].zhi) in RIGUI_RIZHU:
        return {"id": "rigui_ge", "school": "sanming_tonghui",
                "evidence": f"日柱{pillars[2].gan}{pillars[2].zhi} 为日贵",
                "confidence": 0.90}


def detect_riren_ge(pillars, day_gan):
    if (pillars[2].gan, pillars[2].zhi) in RIREN_RIZHU:
        return {"id": "riren_ge", "school": "sanming_tonghui",
                "evidence": f"日柱{pillars[2].gan}{pillars[2].zhi} 为日刃",
                "confidence": 0.95}


def detect_tianyuanyiqi(pillars, day_gan):
    stems = _all_stems(pillars)
    if len(set(stems)) == 1:
        return {"id": "tianyuanyiqi", "school": "sanming_tonghui",
                "evidence": f"四柱天干同为{stems[0]}, 天元一气",
                "confidence": 1.0}


def detect_lianggan_buza(pillars, day_gan):
    stems = _all_stems(pillars)
    if len(set(stems)) == 2:
        return {"id": "lianggan_buza", "school": "sanming_tonghui",
                "evidence": f"四柱天干仅 {sorted(set(stems))} 两字, 两干不杂",
                "confidence": 0.95}


def detect_wuqi_chaoyuan(pillars, day_gan):
    """五气朝元: 五行齐全且月令气足"""
    wxs = set()
    for p in pillars:
        wxs.add(GAN_WUXING[p.gan])
        wxs.add(ZHI_WUXING[p.zhi])
    if len(wxs) >= 5:
        return {"id": "wuqi_chaoyuan", "school": "sanming_tonghui",
                "evidence": "五行齐全, 五气朝元",
                "confidence": 0.85}


def detect_jinglanchaa_ge(pillars, day_gan):
    """井栏叉格: 庚日 + 申子辰三合水局"""
    if day_gan != "庚":
        return None
    branches = set(_all_branches(pillars))
    if {"申", "子", "辰"}.issubset(branches):
        return {"id": "jinglanchaa_ge", "school": "yuanhai_ziping",
                "evidence": "庚日见申子辰全, 井栏叉格",
                "confidence": 0.95}


# ============================================================
# Tier 1.C · 从格 / 化气格 (基于 root_strength 严格判定)
# ============================================================

def detect_cong_cai_zhen(pillars, day_gan):
    rs = compute_dayuan_root_strength(day_gan, _all_branches(pillars))
    if rs["total_root"] >= 0.30:
        return None
    cnt = _shishen_count(day_gan, pillars)
    cai = cnt.get("正财", 0) + cnt.get("偏财", 0)
    if cai >= 4 and cnt.get("正印", 0) + cnt.get("偏印", 0) == 0:
        return {"id": "cong_cai_zhen", "school": "ditian_sui",
                "evidence": f"日主{day_gan}无根 + 财星{cai}见 + 无印",
                "confidence": 0.90}


def detect_cong_sha_zhen(pillars, day_gan):
    rs = compute_dayuan_root_strength(day_gan, _all_branches(pillars))
    if rs["total_root"] >= 0.30:
        return None
    cnt = _shishen_count(day_gan, pillars)
    sha = cnt.get("七杀", 0) + cnt.get("正官", 0)
    if sha >= 4 and cnt.get("正印", 0) + cnt.get("偏印", 0) == 0:
        return {"id": "cong_sha_zhen", "school": "ditian_sui",
                "evidence": f"日主{day_gan}无根 + 官杀{sha}见 + 无印",
                "confidence": 0.90}


# ============================================================
# Tier 2 · 盲派 (实现高频)
# ============================================================

def detect_yang_ren_jia_sha(pillars, day_gan):
    """阳刃 + 七杀同柱或紧贴"""
    if day_gan not in YANGREN_MAP:
        return None
    yangren_zhi = YANGREN_MAP[day_gan]
    cnt = _shishen_count(day_gan, pillars)
    has_yangren = any(p.zhi == yangren_zhi for p in pillars)
    has_qisha = cnt.get("七杀", 0) >= 1
    if has_yangren and has_qisha:
        return {"id": "yang_ren_jia_sha", "school": "mangpai",
                "evidence": f"阳刃{yangren_zhi} + 七杀并见",
                "confidence": 0.85}


def detect_shang_guan_jian_guan(pillars, day_gan):
    cnt = _shishen_count(day_gan, pillars)
    if cnt.get("伤官", 0) >= 1 and cnt.get("正官", 0) >= 1:
        return {"id": "shang_guan_jian_guan", "school": "mangpai",
                "evidence": "伤官 + 正官并见",
                "confidence": 0.80}


def detect_qi_yin_xiang_sheng(pillars, day_gan):
    """杀印相生 = 七杀 + 印星互生"""
    cnt = _shishen_count(day_gan, pillars)
    sha = cnt.get("七杀", 0)
    yin = cnt.get("正印", 0) + cnt.get("偏印", 0)
    if sha >= 1 and yin >= 1:
        return {"id": "qi_yin_xiang_sheng", "school": "mangpai_geju",
                "evidence": f"七杀{sha}见 + 印星{yin}见, 杀印相生",
                "confidence": 0.80}


def detect_shang_guan_sheng_cai(pillars, day_gan):
    cnt = _shishen_count(day_gan, pillars)
    sg = cnt.get("伤官", 0)
    cai = cnt.get("正财", 0) + cnt.get("偏财", 0)
    if sg >= 1 and cai >= 1:
        return {"id": "shang_guan_sheng_cai", "school": "mangpai_geju",
                "evidence": f"伤官{sg}见 + 财星{cai}见, 伤官生财",
                "confidence": 0.80}


def detect_si_sheng_si_bai(pillars, day_gan):
    branches = set(_all_branches(pillars))
    if {"寅", "申", "巳", "亥"}.issubset(branches):
        return {"id": "si_sheng_si_bai", "school": "mangpai",
                "evidence": "寅申巳亥四生齐",
                "confidence": 0.95}
    if {"子", "午", "卯", "酉"}.issubset(branches):
        return {"id": "si_sheng_si_bai", "school": "mangpai",
                "evidence": "子午卯酉四败齐",
                "confidence": 0.95}
    if {"辰", "戌", "丑", "未"}.issubset(branches):
        return {"id": "si_sheng_si_bai", "school": "mangpai",
                "evidence": "辰戌丑未四库齐",
                "confidence": 0.95}


def detect_si_ku_ju(pillars, day_gan):
    branches = set(_all_branches(pillars))
    ku = {"辰", "戌", "丑", "未"} & branches
    if len(ku) >= 4:
        return {"id": "si_ku_ju", "school": "mangpai",
                "evidence": "四库齐备",
                "confidence": 0.95}


def detect_ma_xing_yi_dong(pillars, day_gan):
    """驿马星动: 寅申巳亥逢冲"""
    branches = _all_branches(pillars)
    pairs = [("寅", "申"), ("巳", "亥")]
    for a, b in pairs:
        if a in branches and b in branches:
            return {"id": "ma_xing_yi_dong", "school": "mangpai",
                    "evidence": f"驿马{a}{b}逢冲, 主迁徙",
                    "confidence": 0.85}


def detect_hua_gai_ru_ming(pillars, day_gan):
    """华盖入命: 辰戌丑未坐华盖位 (年支三合或日支三合的'墓库')"""
    branches = _all_branches(pillars)
    if pillars[2].zhi in {"辰", "戌", "丑", "未"}:
        return {"id": "hua_gai_ru_ming", "school": "mangpai",
                "evidence": f"日支{pillars[2].zhi}坐华盖",
                "confidence": 0.75}


def detect_jin_bai_shui_qing(pillars, day_gan):
    if day_gan not in {"庚", "辛"}:
        return None
    cnt_water = sum(1 for p in pillars if ZHI_WUXING[p.zhi] == "水") + \
                sum(1 for p in pillars if GAN_WUXING[p.gan] == "水")
    if cnt_water >= 3:
        return {"id": "jin_bai_shui_qing", "school": "mangpai",
                "evidence": f"日主{day_gan}金 + 水{cnt_water}见, 金白水清",
                "confidence": 0.85}


def detect_mu_huo_tong_ming(pillars, day_gan):
    if day_gan not in {"甲", "乙"}:
        return None
    if pillars[1].zhi in {"午", "未", "巳"}:
        return {"id": "mu_huo_tong_ming", "school": "mangpai",
                "evidence": f"日主{day_gan}木 + 月令{pillars[1].zhi}火, 木火通明",
                "confidence": 0.85}


def detect_yangren_chong_cai(pillars, day_gan):
    """刃冲财做功格 (盲派做功体系):
    - 阳干日主 + 命局有羊刃 (不限月支, 年/日/时支均可) + 命局有财星
    - 羊刃支与财星支构成六冲 (子午冲 / 卯酉冲)
    - 日主有根 (不是从格)
    - 盲派师承传口诀: "用刃为体, 冲财做功" — 主动出击型取财结构

    与 yangren_ge (严格子平正格, 必须刃在月支) 互补:
    本 detector 覆盖 "刃不在月支但参与做功" 的盲派变格.
    """
    if day_gan not in YANGREN_MAP:
        return None
    yangren_zhi = YANGREN_MAP[day_gan]
    branches = _all_branches(pillars)
    if yangren_zhi not in branches:
        return None
    rs = compute_dayuan_root_strength(day_gan, branches)
    if rs["total_root"] < 1.0:
        return None
    cnt = _shishen_count(day_gan, pillars)
    cai = cnt.get("正财", 0) + cnt.get("偏财", 0)
    if cai < 1:
        return None
    chong_zhi = ZHI_CHONG.get(yangren_zhi)
    if not chong_zhi or chong_zhi not in branches:
        return None
    chong_pillar = next((p for p in pillars if p.zhi == chong_zhi), None)
    if chong_pillar is None:
        return None
    chong_ss = calc_zhi_shishen(day_gan, chong_zhi)
    if chong_ss not in {"正财", "偏财"}:
        return None
    return {"id": "yangren_chong_cai", "school": "mangpai_zuogong",
            "evidence": f"日主{day_gan}强根 + 羊刃{yangren_zhi} + {yangren_zhi}{chong_zhi}冲, "
                        f"以刃冲财({chong_ss}={chong_zhi})做功",
            "confidence": 0.85}


# ============================================================
# 主入口: 批量扫描
# ============================================================

DETECTOR_FUNCS = [
    # Tier 1.A
    detect_zhengguan_ge, detect_qisha_ge,
    detect_zhengyin_ge, detect_pianyin_ge,
    detect_shishen_ge, detect_shangguan_ge,
    detect_zhengcai_ge, detect_piancai_ge,
    detect_jianlu_ge, detect_yangren_ge,
    # Tier 1.D
    detect_kuigang_ge, detect_jinshen_ge,
    detect_ride_ge, detect_rigui_ge, detect_riren_ge,
    detect_tianyuanyiqi, detect_lianggan_buza, detect_wuqi_chaoyuan,
    detect_jinglanchaa_ge,
    # Tier 1.C
    detect_cong_cai_zhen, detect_cong_sha_zhen,
    # Tier 2
    detect_yang_ren_jia_sha, detect_shang_guan_jian_guan,
    detect_qi_yin_xiang_sheng, detect_shang_guan_sheng_cai,
    detect_si_sheng_si_bai, detect_si_ku_ju,
    detect_ma_xing_yi_dong, detect_hua_gai_ru_ming,
    detect_jin_bai_shui_qing, detect_mu_huo_tong_ming,
    detect_yangren_chong_cai,
]


def scan_all(pillars: List[Pillar], day_gan: str) -> List[Dict]:
    """批量扫描所有 detector, 返回触发的 phase 列表.

    返回 hit dict 字段严格保持 v8 格式：{id, school, evidence, confidence}
    不追加其他字段（bit-for-bit 保护：multi_school_vote / curves.json 使用此结果）。
    v9 的 dimension / metadata 由 enrich_with_registry() 按需单独调用。
    """
    out = []
    for fn in DETECTOR_FUNCS:
        try:
            res = fn(pillars, day_gan)
        except Exception as e:
            res = None
        if res is not None:
            out.append(res)
    return out


def enrich_with_registry(hits: List[Dict]) -> List[Dict]:
    """v9 · 从 _phase_registry 取 dimension / zuogong_trigger_branches 等 metadata。

    返回**新的 list of new dict**，不就地修改原 hit（避免污染缓存或并发访问）。
    注册表未覆盖的 id 退化为 dimension='special'，不参与 zuogong 聚合。

    调用点：_bazi_core.detect_all_phase_candidates 的 v9 扩展；
            phase_posterior.py 启动 R3 时；
            mangpai_events.py 读取 reversal_overrides 时。
    """
    try:
        from _phase_registry import exists, get
    except Exception:
        return [dict(h, dimension=h.get("dimension", "special")) for h in hits]

    out = []
    for hit in hits:
        nh = dict(hit)
        pid = nh.get("id", "")
        if exists(pid):
            meta = get(pid)
            nh["dimension"] = meta.dimension
            nh["name_cn"] = meta.name_cn
            if meta.zuogong_trigger_branches:
                nh["zuogong_trigger_branches"] = list(meta.zuogong_trigger_branches)
            if meta.reversal_overrides:
                nh["reversal_overrides"] = dict(meta.reversal_overrides)
        else:
            nh["dimension"] = "special"
        out.append(nh)
    return out


def scan_from_bazi(bazi: dict) -> List[Dict]:
    """原 v8 接口，返回不带 dimension 的 hit 列表（bit-for-bit 兼容）。"""
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = pillars[2].gan
    return scan_all(pillars, day_gan)


def scan_from_bazi_enriched(bazi: dict) -> List[Dict]:
    """v9 · 带 registry metadata 的 hit 列表（供 P7 聚合 / phase_posterior 使用）。"""
    return enrich_with_registry(scan_from_bazi(bazi))
