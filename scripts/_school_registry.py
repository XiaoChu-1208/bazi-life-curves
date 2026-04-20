"""v9 PR-6 · 多流派注册表

每个流派提供:
  - weight: 投票权重
  - vote_type:
      "phase_candidate" — 可独立提出 phase 候选 + 投票
      "ratify_only"     — 不出 phase 候选, 仅对其他派的候选投赞同/反对
  - judge: callable(bazi) -> List[Dict{id, label, confidence, evidence}]

子平真诠 / 滴天髓 / 穷通宝鉴 / 盲派 都是 phase_candidate.
紫微斗数 / 铁板神数 仅 ratify (来自用户对话 §"C. A+B+紫微/铁板").
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional


def _ziping_zhenquan_judge(bazi: dict) -> List[Dict]:
    """子平真诠 — 月令格 + 八正格优先, 复用 rare_phase_detector tier1.A"""
    try:
        from rare_phase_detector import (
            detect_zhengguan_ge, detect_qisha_ge,
            detect_zhengyin_ge, detect_pianyin_ge,
            detect_shishen_ge, detect_shangguan_ge,
            detect_zhengcai_ge, detect_piancai_ge,
            detect_jianlu_ge, detect_yangren_ge,
        )
        from _bazi_core import Pillar
    except ImportError:
        return []
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = pillars[2].gan
    out = []
    for fn in [detect_zhengguan_ge, detect_qisha_ge, detect_zhengyin_ge,
               detect_pianyin_ge, detect_shishen_ge, detect_shangguan_ge,
               detect_zhengcai_ge, detect_piancai_ge,
               detect_jianlu_ge, detect_yangren_ge]:
        r = fn(pillars, day_gan)
        if r:
            r["from_school"] = "ziping_zhenquan"
            out.append(r)
    return out


def _ditian_sui_judge(bazi: dict) -> List[Dict]:
    """滴天髓 — 化气格 + 从格 + 通根度严判"""
    try:
        from _bazi_core import Pillar, detect_huaqi_pattern, compute_dayuan_root_strength
        from rare_phase_detector import detect_cong_cai_zhen, detect_cong_sha_zhen
    except ImportError:
        return []
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = pillars[2].gan
    out = []

    try:
        huaqi = detect_huaqi_pattern(pillars)
        if huaqi.get("triggered"):
            out.append({
                "id": huaqi["suggested_phase"],
                "from_school": "ditian_sui",
                "school": "ditian_sui",
                "evidence": "化气格触发: " + str(huaqi.get("evidence", {})),
                "confidence": 0.85,
            })
    except Exception:
        pass

    for fn in (detect_cong_cai_zhen, detect_cong_sha_zhen):
        r = fn(pillars, day_gan)
        if r:
            r["from_school"] = "ditian_sui"
            out.append(r)

    rs = compute_dayuan_root_strength(day_gan, [p.zhi for p in pillars])
    if rs["label"] in ("中根", "强根"):
        out.append({
            "id": "day_master_dominant",
            "from_school": "ditian_sui",
            "school": "ditian_sui",
            "evidence": f"日主{day_gan} {rs['label']} (total={rs['total_root']})",
            "confidence": 0.55 + min(rs["total_root"] / 10.0, 0.30),
        })
    return out


def _qiongtong_baojian_judge(bazi: dict) -> List[Dict]:
    """穷通宝鉴 — 调候为先, 月令季节 + 燥湿决定 phase

    走 detect_climate_inversion (而非裸 label) 兼容 v7 阈值.
    """
    try:
        from _bazi_core import Pillar, climate_profile, detect_climate_inversion
    except ImportError:
        return []
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    out = []
    try:
        climate = climate_profile(pillars)
        inv = detect_climate_inversion(pillars, climate)
    except Exception:
        return []

    if inv.get("triggered") and inv.get("suggested_phase", "").startswith("climate_inversion_"):
        out.append({
            "id": inv["suggested_phase"],
            "from_school": "qiongtong_baojian",
            "school": "qiongtong_baojian",
            "evidence": f"{inv.get('suggested_label')} | climate.label={climate.get('label')}",
            "confidence": 0.75,
        })
    return out


def _mangpai_judge(bazi: dict) -> List[Dict]:
    """盲派 — 杀印 / 伤官生财 / 阳刃驾杀 等象法 + 大运层结构"""
    try:
        from _bazi_core import Pillar
        from rare_phase_detector import (
            detect_qi_yin_xiang_sheng,
            detect_shang_guan_sheng_cai,
            detect_yang_ren_jia_sha,
            detect_shang_guan_jian_guan,
            detect_si_sheng_si_bai,
            detect_ma_xing_yi_dong,
            detect_jin_bai_shui_qing,
            detect_mu_huo_tong_ming,
        )
    except ImportError:
        return []
    pillars = [Pillar(p["gan"], p["zhi"]) for p in bazi["pillars"]]
    day_gan = pillars[2].gan
    out = []
    for fn in (
        detect_qi_yin_xiang_sheng, detect_shang_guan_sheng_cai,
        detect_yang_ren_jia_sha, detect_shang_guan_jian_guan,
        detect_si_sheng_si_bai, detect_ma_xing_yi_dong,
        detect_jin_bai_shui_qing, detect_mu_huo_tong_ming,
    ):
        r = fn(pillars, day_gan)
        if r:
            r["from_school"] = "mangpai"
            out.append(r)
    return out


def _ziwei_doushu_judge(bazi: dict) -> List[Dict]:
    """紫微 — ratify only. 真实判定需要紫微星盘, 此处仅做最弱占位 (LLM fallback 兜)."""
    return []


def _tiekan_shenshu_judge(bazi: dict) -> List[Dict]:
    """铁板神数 — ratify only. 真实判定需要考语库, 此处仅占位."""
    return []


SCHOOLS: Dict[str, Dict] = {
    "ziping_zhenquan": {
        "label": "子平真诠",
        "weight": 1.0,
        "vote_type": "phase_candidate",
        "judge": _ziping_zhenquan_judge,
    },
    "ditian_sui": {
        "label": "滴天髓",
        "weight": 1.0,
        "vote_type": "phase_candidate",
        "judge": _ditian_sui_judge,
    },
    "qiongtong_baojian": {
        "label": "穷通宝鉴",
        "weight": 0.9,
        "vote_type": "phase_candidate",
        "judge": _qiongtong_baojian_judge,
    },
    "mangpai": {
        "label": "盲派 (无名/王虎应/段建业)",
        "weight": 0.9,
        "vote_type": "phase_candidate",
        "judge": _mangpai_judge,
    },
    "ziwei_doushu": {
        "label": "紫微斗数",
        "weight": 0.3,
        "vote_type": "ratify_only",
        "judge": _ziwei_doushu_judge,
    },
    "tiekan_shenshu": {
        "label": "铁板神数",
        "weight": 0.3,
        "vote_type": "ratify_only",
        "judge": _tiekan_shenshu_judge,
    },
}


def get_phase_candidate_schools() -> List[str]:
    return [k for k, v in SCHOOLS.items() if v["vote_type"] == "phase_candidate"]


def get_ratify_only_schools() -> List[str]:
    return [k for k, v in SCHOOLS.items() if v["vote_type"] == "ratify_only"]
