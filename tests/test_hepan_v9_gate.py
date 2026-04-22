"""v9.3 PR-2 · he_pan v9.3 入口守卫 + 多人 adaptive_elicit 编排器测试

覆盖场景：
  1. provisional bazi 应被 he_pan CLI 拒绝（exit 3）
  2. confidence < 0.60 应被拒绝（exit 3）
  3. 全员 finalized 且 confidence ≥ 0.60 + 提供 virtue_motifs.json → 通过
  4. BAZI_HEPAN_BYPASS_V8_GATE=1 兜底放过 provisional
  5. 缺 virtue_motifs.json → exit 7
  6. BAZI_HEPAN_SKIP_VIRTUE=1 兜底放过 missing virtue_motifs
  7. orchestrator plan-v9 模式输出 schema
  8. orchestrator next-person 模式找到 pending 成员
  9. orchestrator legacy plan / collect-r1 / apply-answers 默认 exit 2，--ack-batch 才允许
+ split_answers 命名空间拆分（旧 batch 兼容）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
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


def _write_virtue(path: Path, motif_ids=("loyalty_under_pressure",)):
    """v9.3 he_pan.py --require-virtue-motifs 入口要求每人都有 virtue_motifs.json。"""
    path.write_text(
        json.dumps({"version": 9, "motifs": [{"id": m, "confidence": "high"} for m in motif_ids]}),
        encoding="utf-8",
    )


def _run_hepan(tmp_path: Path, b1: dict, b2: dict,
               env_extra: dict = None,
               with_virtue: bool = True,
               require_virtue: bool = True) -> subprocess.CompletedProcess:
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    out = tmp_path / "he_pan.json"
    p1.write_text(json.dumps(b1, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(b2, ensure_ascii=False), encoding="utf-8")
    if with_virtue:
        _write_virtue(p1.with_name("p1.virtue_motifs.json"))
        _write_virtue(p2.with_name("p2.virtue_motifs.json"))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS) + ":" + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    cmd = [sys.executable, str(SCRIPTS / "he_pan.py"),
           "--bazi", str(p1), str(p2), "--names", "Alice", "Bob",
           "--type", "marriage", "--out", str(out)]
    if not require_virtue:
        cmd.append("--no-require-virtue-motifs")
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


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
# Scenario 3: 全员通过（v9.3 同时要求 virtue_motifs 已生成）
# ------------------------------------------------------------

def test_hepan_accepts_finalized_high_confidence_with_virtue(tmp_path):
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
# Scenario 5: 缺 virtue_motifs.json → exit 7（v9.3 新增）
# ------------------------------------------------------------

def test_hepan_rejects_missing_virtue_motifs(tmp_path):
    b1 = _make_bazi(provisional=False, confidence=0.85)
    b2 = _make_bazi(provisional=False, confidence=0.90, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2, with_virtue=False)
    assert r.returncode == 7, f"缺 virtue_motifs 应 exit 7, got {r.returncode}\nstderr={r.stderr}"
    assert "virtue_motifs" in r.stderr.lower()


# ------------------------------------------------------------
# Scenario 6: BAZI_HEPAN_SKIP_VIRTUE=1 兜底放过缺失（v9.3 新增）
# ------------------------------------------------------------

def test_hepan_skip_virtue_env_allows_missing(tmp_path):
    b1 = _make_bazi(provisional=False, confidence=0.85)
    b2 = _make_bazi(provisional=False, confidence=0.90, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2, with_virtue=False,
                   env_extra={"BAZI_HEPAN_SKIP_VIRTUE": "1"})
    assert r.returncode == 0, f"SKIP_VIRTUE=1 应通过, got {r.returncode}\nstderr={r.stderr}"


# ------------------------------------------------------------
# Scenario 6b: --no-require-virtue-motifs CLI flag 等效
# ------------------------------------------------------------

def test_hepan_no_require_virtue_flag(tmp_path):
    b1 = _make_bazi(provisional=False, confidence=0.85)
    b2 = _make_bazi(provisional=False, confidence=0.90, day_gan="丙")
    r = _run_hepan(tmp_path, b1, b2, with_virtue=False, require_virtue=False)
    assert r.returncode == 0, f"--no-require-virtue-motifs 应通过, got {r.returncode}\nstderr={r.stderr}"


# ------------------------------------------------------------
# Orchestrator v9.3 plan-v9 + next-person
# ------------------------------------------------------------

def test_orchestrator_plan_v9_mode(tmp_path):
    from he_pan_orchestrator import plan_v9
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.85, day_gan="丙")
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    p1.write_text(json.dumps(b1, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(b2, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "hepan_state"
    res = plan_v9([str(p1), str(p2)], ["Alice", "Bob"], out_dir)
    assert res["kind"] == "he_pan_orchestrator_plan_v9"
    assert res["version"] == "v9.3"
    assert res["n_persons"] == 2
    assert res["next_global_action"] in {
        "answer_next_question", "run_virtue_motifs",
    }
    statuses = {p["name"]: p["status"] for p in res["persons"]}
    assert statuses["Alice"] == "pending"
    assert statuses["Bob"] in {"pending", "finalized"}
    assert any("Alice" in w for w in res["warnings"])


def test_orchestrator_next_person_finds_pending(tmp_path):
    from he_pan_orchestrator import next_person, plan_v9
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.85, day_gan="丙")
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    p1.write_text(json.dumps(b1, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(b2, ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "hepan_state"
    plan_v9([str(p1), str(p2)], ["Alice", "Bob"], out_dir)
    res = next_person([str(p1), str(p2)], ["Alice", "Bob"], out_dir)
    assert res["kind"] == "he_pan_orchestrator_next"
    assert res["next_person"]["name"] == "Alice"
    assert "adaptive_elicit.py next" in res["next_command_elicit"]


# ------------------------------------------------------------
# Orchestrator legacy batch 模式 — 默认 exit 2，--ack-batch 才允许
# ------------------------------------------------------------

def _run_orchestrator(tmp_path, b1, b2, mode, ack_batch=False):
    p1 = tmp_path / "p1.json"
    p2 = tmp_path / "p2.json"
    p1.write_text(json.dumps(b1, ensure_ascii=False), encoding="utf-8")
    p2.write_text(json.dumps(b2, ensure_ascii=False), encoding="utf-8")
    cmd = [sys.executable, str(SCRIPTS / "he_pan_orchestrator.py"),
           "--bazi", str(p1), str(p2), "--names", "Alice", "Bob",
           "--mode", mode]
    if ack_batch:
        cmd.append("--ack-batch")
    return subprocess.run(cmd, capture_output=True, text=True)


def test_orchestrator_legacy_plan_requires_ack_batch(tmp_path):
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.85, day_gan="丙")
    r = _run_orchestrator(tmp_path, b1, b2, mode="plan", ack_batch=False)
    assert r.returncode == 2, f"legacy plan 无 --ack-batch 应 exit 2, got {r.returncode}\nstderr={r.stderr}"
    assert "deprecated" in r.stderr.lower() or "v9.3" in r.stderr


def test_orchestrator_legacy_plan_with_ack_batch_allowed(tmp_path):
    b1 = _make_bazi(provisional=True, confidence=0.95)
    b2 = _make_bazi(provisional=False, confidence=0.85, day_gan="丙")
    r = _run_orchestrator(tmp_path, b1, b2, mode="plan", ack_batch=True)
    assert r.returncode == 0, f"legacy plan + --ack-batch 应允许, got {r.returncode}\nstderr={r.stderr}"
    payload = json.loads(r.stdout)
    assert payload.get("deprecated_v9_3") is True


# ------------------------------------------------------------
# Orchestrator: split_answers (legacy batch 兼容)
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
