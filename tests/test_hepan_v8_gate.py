"""v9 PR-2 · he_pan v8 入口守卫 + 多人编排器测试

覆盖 3 场景：
  1. provisional bazi 应被 he_pan CLI 拒绝
  2. confidence < 0.60 应被拒绝
  3. 全员 finalized 且 confidence >= 0.60 应通过
+ orchestrator plan 模式输出格式
+ split_answers 命名空间拆分
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

pytestmark = [pytest.mark.fast]


def _make_bazi(provisional: bool, confidence: float, day_gan: str = "壬") -> dict:
    return {
        "version": 3,
        "input_kind": "pillars",
        "gender": "M",
        "orientation": "hetero",
        "birth_year": 1990,
        "pillars": [
            {"gan": "庚", "zhi": "午"}, {"gan": "辛", "zhi": "巳"},
            {"gan": day_gan, "zhi": "子"}, {"gan": "丁", "zhi": "未"}
        ],
        "pillars_str": "庚午 辛巳 壬子 丁未",
        "day_master": day_gan,
        "day_master_wuxing": "水",
        "strength": {"label": "中和", "score": 0,
                     "same": 1, "sheng": 1, "xie": 1, "ke": 1, "kewo": 1,
                     "root_strength": {"stem": day_gan, "stem_wx": "水",
                                       "bijie_root": 1.0, "yin_root": 0.5,
                                       "total_root": 1.5, "label": "中根",
                                       "details": []}},
        "yongshen": {"yongshen": "金"},
        "wuxing_distribution": {wx: {"score": s, "ratio": s / 8.0}
                                for wx, s in [("木", 0), ("火", 3), ("土", 1),
                                              ("金", 2), ("水", 2)]},
        "qiyun_age": 8,
        "dayun": [], "liunian": [],
        "phase": {
            "id": "day_master_dominant",
            "label": "默认 · 日主主导",
            "is_provisional": provisional,
            "is_inverted": False,
            "confidence": confidence,
        },
    }


def _run_hepan(tmp_path: Path, b1: dict, b2: dict, env_extra: dict = None) -> subprocess.CompletedProcess:
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    out = tmp_path / "he_pan.json"
    p1.write_text(json.dumps(b1, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(b2, ensure_ascii=False), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS) + ":" + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "he_pan.py"),
         "--bazi", str(p1), str(p2), "--names", "Alice", "Bob",
         "--type", "marriage", "--out", str(out)],
        capture_output=True, text=True, env=env,
    )


# ------------------------------------------------------------
# Scenario 1: provisional 被拒
# ------------------------------------------------------------

def test_hepan_rejects_provisional_phase(tmp_path):
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.95, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2)
    assert r.returncode == 3, f"应该 exit 3, got {r.returncode}\nstderr={r.stderr}"
    assert "is_provisional" in r.stderr or "provisional" in r.stderr.lower()


# ------------------------------------------------------------
# Scenario 2: confidence < 0.60 被拒
# ------------------------------------------------------------

def test_hepan_rejects_low_confidence(tmp_path):
    b1 = _make_bazi(provisional=False, confidence=0.55)
    b2 = _make_bazi(provisional=False, confidence=0.95, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2)
    assert r.returncode == 3, f"应该 exit 3, got {r.returncode}\nstderr={r.stderr}"
    assert "confidence" in r.stderr.lower()


# ------------------------------------------------------------
# Scenario 3: 全员通过
# ------------------------------------------------------------

def test_hepan_accepts_finalized_high_confidence(tmp_path):
    b1 = _make_bazi(provisional=False, confidence=0.85)
    b2 = _make_bazi(provisional=False, confidence=0.90, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2)
    assert r.returncode == 0, f"应该 exit 0, got {r.returncode}\nstderr={r.stderr}"
    out = tmp_path / "he_pan.json"
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "pairs" in data


# ------------------------------------------------------------
# Scenario 4: bypass env var
# ------------------------------------------------------------

def test_hepan_bypass_env_allows_provisional(tmp_path):
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.95, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2,
                   env_extra={"BAZI_HEPAN_BYPASS_V8_GATE": "1"})
    assert r.returncode == 0, f"bypass 后应通过, got {r.returncode}\nstderr={r.stderr}"


# ------------------------------------------------------------
# Orchestrator: split_answers
# ------------------------------------------------------------

def test_orchestrator_split_answers():
    from he_pan_orchestrator import split_answers
    answers = {
        "alice_q1": "A", "alice_q2": "B",
        "bob_q1": "C", "bob_q2": "D",
    }
    out = split_answers(answers, ["Alice", "Bob"])
    assert out["Alice"] == {"q1": "A", "q2": "B"}
    assert out["Bob"] == {"q1": "C", "q2": "D"}


def test_orchestrator_split_answers_unmatched_raises():
    from he_pan_orchestrator import split_answers
    with pytest.raises(ValueError, match="prefix"):
        split_answers({"q1": "A"}, ["Alice", "Bob"])


def test_orchestrator_plan_mode(tmp_path):
    from he_pan_orchestrator import plan
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.85, day_gan="丙")
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    p1.write_text(json.dumps(b1, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(b2, ensure_ascii=False), encoding="utf-8")
    res = plan([str(p1), str(p2)], ["Alice", "Bob"])
    assert res["kind"] == "he_pan_orchestrator_plan"
    assert res["n_persons"] == 2
    assert res["needs_r1_count"] == 1
    assert res["next_action"] == "answer_r1_for_listed_persons"
    assert any("Alice" in w for w in res["warnings"])
