"""v9.3 R-STREAM-1: append_analysis_node 同 turn 连续 append 检测。

scripts/append_analysis_node.py 必须：
  - 每次写入读 BAZI_AGENT_TURN_ID 环境变量，写到 _stream_log[i].agent_turn_id
  - 若 turn_id 与 _stream_log[-1].agent_turn_id 相同 → stderr WARN +
    state['_stream_violations'] append 一条
  - 缺失 BAZI_AGENT_TURN_ID 时退化用时间戳作伪 turn_id（不报 R-STREAM-1）

scripts/render_artifact.py --audit-stream-batching 必须：
  - 扫 analysis._stream_violations，长度 ≥ 1 → exit 11
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APPEND_SCRIPT = ROOT / "scripts" / "append_analysis_node.py"


def _append(state_path: Path, node: str, markdown: str, *, turn_id: str | None) -> subprocess.CompletedProcess:
    env = {"PATH": "/usr/bin:/bin"}
    if turn_id is not None:
        env["BAZI_AGENT_TURN_ID"] = turn_id
    return subprocess.run(
        [
            sys.executable,
            str(APPEND_SCRIPT),
            "--state", str(state_path),
            "--node", node,
            "--markdown", markdown,
            "--quiet",
        ],
        env=env,
        capture_output=True,
        text=True,
    )


# ─── R-STREAM-1: 同 turn 连续 append 触发违规 ───────────────────────

def test_same_turn_id_two_appends_triggers_violation(tmp_path):
    state = tmp_path / "x.analysis.partial.json"

    r1 = _append(state, "overall", "## 整图\n\n第一节正文，足够长。", turn_id="turn-A")
    assert r1.returncode == 0, r1.stderr

    r2 = _append(state, "life_review.spirit", "## 精神舒畅度\n\n第二节正文，足够长。", turn_id="turn-A")
    assert r2.returncode == 0, r2.stderr
    assert "R-STREAM-1" in r2.stderr, f"应输出 R-STREAM-1 警告: {r2.stderr}"

    data = json.loads(state.read_text(encoding="utf-8"))
    log = data.get("_stream_log") or []
    assert len(log) == 2
    assert log[0].get("agent_turn_id") == "turn-A"
    assert log[1].get("agent_turn_id") == "turn-A"

    violations = data.get("_stream_violations") or []
    assert len(violations) == 1, f"应有 1 条违规: {violations}"
    v = violations[0]
    assert v["rule"] == "R-STREAM-1"
    assert v["agent_turn_id"] == "turn-A"
    assert v["prev_node"] == "overall"
    assert v["current_node"] == "life_review.spirit"


def test_different_turn_ids_no_violation(tmp_path):
    state = tmp_path / "x.analysis.partial.json"

    r1 = _append(state, "overall", "## 整图\n\n第一节正文，足够长。", turn_id="turn-A")
    assert r1.returncode == 0, r1.stderr
    r2 = _append(state, "life_review.spirit", "## 精神舒畅度\n\n第二节正文，足够长。", turn_id="turn-B")
    assert r2.returncode == 0, r2.stderr
    assert "R-STREAM-1" not in r2.stderr

    data = json.loads(state.read_text(encoding="utf-8"))
    assert (data.get("_stream_violations") or []) == []


def test_missing_turn_id_no_violation(tmp_path):
    """无 BAZI_AGENT_TURN_ID 环境变量 → 退化伪 turn_id（不报 R-STREAM-1）。"""
    state = tmp_path / "x.analysis.partial.json"
    r1 = _append(state, "overall", "## 整图\n\n第一节正文，足够长。", turn_id=None)
    assert r1.returncode == 0, r1.stderr
    r2 = _append(state, "life_review.spirit", "## 精神舒畅度\n\n第二节正文，足够长。", turn_id=None)
    assert r2.returncode == 0, r2.stderr
    assert "R-STREAM-1" not in r2.stderr

    data = json.loads(state.read_text(encoding="utf-8"))
    assert (data.get("_stream_violations") or []) == []


# ─── R-STREAM-2: 单节 markdown 内 ≥ 2 顶级 ## → SystemExit ────────

def test_single_append_two_top_headings_blocked(tmp_path):
    state = tmp_path / "x.analysis.partial.json"
    md = "## 第一段\n\n正文 A\n\n## 第二段\n\n正文 B"
    r = _append(state, "overall", md, turn_id="turn-A")
    assert r.returncode != 0
    assert "R-STREAM-2" in r.stderr


def test_closing_chain_in_free_speech_node_passes(tmp_path):
    """closing 三段在最后一条 turn 的 free_speech 节里紧邻出现 → 允许。"""
    state = tmp_path / "x.analysis.partial.json"
    md = (
        "## 我想和你说\n\n第一段正文，足够长。\n\n"
        "## 项目的编写者想和你说\n\n第二段正文，足够长。\n\n"
        "## 我（大模型）想和你说\n\n第三段正文，足够长。"
    )
    r = _append(state, "virtue_narrative.free_speech", md, turn_id="turn-final")
    assert r.returncode == 0, f"closing chain 应放行: stderr={r.stderr}"


# ─── render_artifact --audit-stream-batching 兜底 ─────────────────

def test_render_artifact_audit_stream_batching_blocks(tmp_path):
    """analysis._stream_violations 非空 → render_artifact --audit-stream-batching exit 11。"""
    # 准备最小 curves
    curves = {
        "version": 9,
        "pillars_str": "庚午 辛巳 壬子 丁未",
        "baseline": {"spirit": 50.0, "wealth": 50.0, "fame": 50.0, "emotion": 50.0},
        "points": [],
        "dayun": {"segments": []},
        "disputes": [],
        "turning_points_future": [],
    }
    curves_path = tmp_path / "curves.json"
    curves_path.write_text(json.dumps(curves), encoding="utf-8")

    analysis = {
        "overall": "x",
        "_stream_violations": [
            {
                "rule": "R-STREAM-1",
                "agent_turn_id": "turn-A",
                "prev_node": "overall",
                "current_node": "life_review.spirit",
                "ts_iso": "2026-01-01T00:00:00+08:00",
                "reason": "same agent_turn_id append ≥ 2 nodes",
            }
        ],
    }
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    out_path = tmp_path / "out.html"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "render_artifact.py"),
            "--curves", str(curves_path),
            "--analysis", str(analysis_path),
            "--out", str(out_path),
            "--no-strict-llm",
            # 关掉其它会先 fail 的 audit
            "--no-audit-virtue-continuity",
            "--no-audit-mangpai-surface",
            "--no-audit-no-premature-decision",
            "--no-audit-closing-headers",
            "--no-require-streamed-emit",
            "--no-required-node-order",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 11, (
        f"应 exit 11 (R-STREAM-1)，实际 returncode={proc.returncode}\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    assert "R-STREAM-1" in proc.stderr


def test_render_artifact_no_violations_passes(tmp_path):
    """analysis 没有 _stream_violations → --audit-stream-batching 放行。"""
    curves = {
        "version": 9,
        "pillars_str": "庚午 辛巳 壬子 丁未",
        "baseline": {"spirit": 50.0, "wealth": 50.0, "fame": 50.0, "emotion": 50.0},
        "points": [],
        "dayun": {"segments": []},
        "disputes": [],
        "turning_points_future": [],
    }
    curves_path = tmp_path / "curves.json"
    curves_path.write_text(json.dumps(curves), encoding="utf-8")

    analysis = {"overall": "x"}
    analysis_path = tmp_path / "analysis.json"
    analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

    out_path = tmp_path / "out.html"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "render_artifact.py"),
            "--curves", str(curves_path),
            "--analysis", str(analysis_path),
            "--out", str(out_path),
            "--no-strict-llm",
            "--no-audit-virtue-continuity",
            "--no-audit-mangpai-surface",
            "--no-audit-no-premature-decision",
            "--no-audit-closing-headers",
            "--no-require-streamed-emit",
            "--no-required-node-order",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"无违规应 exit 0；实际 returncode={proc.returncode}\n"
        f"stderr={proc.stderr}"
    )
