"""tests/test_streaming_pipeline.py — v9.3 改动 5.4

覆盖：
1. 6 个 stage 顺序与 STAGES 常量一致
2. 每个 stage payload 的 schema 稳定（必备字段 + 类型）
3. `--stage all` 与逐 stage `--next` 增量结果 bit-for-bit 等价
4. `--resume` 后能正确 pick up cursor，不重跑已完成 stage
5. e2e：跑一个真实 case（examples/shang_guan_sheng_cai.bazi.json）
6. render_artifact `--from-stream-state` 能从 state 还原 curves 喂渲染管线
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
EXAMPLES = REPO_ROOT / "examples"
PIPELINE = SCRIPTS / "streaming_pipeline.py"
RENDER = SCRIPTS / "render_artifact.py"

EXPECTED_STAGES: tuple[str, ...] = (
    "current_dayun",
    "current_dayun_liunian",
    "other_dayuns",
    "key_years",
    "overall_and_life_review",
    "closing",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run_pipeline(args: list[str], *, cwd: Path = REPO_ROOT) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(PIPELINE), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _parse_ndjson(stdout: str) -> list[dict]:
    out: list[dict] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


# ---------------------------------------------------------------------------
# §1 STAGES 常量稳定（防止后续误改顺序）
# ---------------------------------------------------------------------------

def test_stages_constant_matches_expected():
    sys.path.insert(0, str(SCRIPTS))
    import streaming_pipeline as sp  # type: ignore
    assert sp.STAGES == EXPECTED_STAGES


# ---------------------------------------------------------------------------
# §2 --stage all 6 段顺序 + schema
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def example_bazi() -> Path:
    p = EXAMPLES / "shang_guan_sheng_cai.bazi.json"
    if not p.exists():
        pytest.skip(f"缺少示例 bazi: {p}")
    return p


def test_stage_all_emits_six_stages_in_order(tmp_path: Path, example_bazi: Path):
    state = tmp_path / "stream_state.json"
    rc, out, err = _run_pipeline([
        "stream",
        "--bazi", str(example_bazi),
        "--stage", "all",
        "--state", str(state),
    ])
    assert rc == 0, f"stage all 失败：\nstdout={out}\nstderr={err}"
    records = _parse_ndjson(out)
    assert [r["stage"] for r in records] == list(EXPECTED_STAGES)
    for r in records:
        assert "stage" in r and "payload" in r and "ts_iso" in r
        assert isinstance(r["payload"], dict)

    # state 文件落盘且 completed_stages 完整
    assert state.exists(), "state 文件未落盘"
    s = json.loads(state.read_text(encoding="utf-8"))
    assert s["completed_stages"] == list(EXPECTED_STAGES)
    assert set(s["stages"].keys()) == set(EXPECTED_STAGES)


def test_each_stage_payload_schema(tmp_path: Path, example_bazi: Path):
    """6 个 stage payload 必备字段稳定。"""
    state = tmp_path / "stream_state.json"
    rc, out, _ = _run_pipeline([
        "stream", "--bazi", str(example_bazi),
        "--stage", "all", "--state", str(state),
    ])
    assert rc == 0
    by_stage = {r["stage"]: r["payload"] for r in _parse_ndjson(out)}

    # current_dayun
    cd = by_stage["current_dayun"]
    for k in ("current_dayun_label", "segment", "n_years", "summary",
              "phase", "interactions_unique"):
        assert k in cd, f"current_dayun 缺字段 {k!r}"
    assert isinstance(cd["interactions_unique"], list)

    # current_dayun_liunian
    cdl = by_stage["current_dayun_liunian"]
    for k in ("current_dayun_label", "n_years", "yearly_points"):
        assert k in cdl, f"current_dayun_liunian 缺字段 {k!r}"
    assert isinstance(cdl["yearly_points"], list)

    # other_dayuns
    od = by_stage["other_dayuns"]
    assert "n_segments" in od and "segments" in od
    assert isinstance(od["segments"], list)

    # key_years
    ky = by_stage["key_years"]
    for k in ("turning_points_future", "disputes", "extremes",
              "dispute_threshold"):
        assert k in ky, f"key_years 缺字段 {k!r}"
    assert isinstance(ky["extremes"], list)
    if ky["extremes"]:
        assert {"dimension", "peak", "dip"} <= set(ky["extremes"][0].keys())

    # overall_and_life_review
    ov = by_stage["overall_and_life_review"]
    for k in ("n_years", "age_range", "baseline", "aggregate",
              "phase", "geju", "yongshen", "strength"):
        assert k in ov, f"overall_and_life_review 缺字段 {k!r}"
    for dim in ("spirit", "wealth", "fame", "emotion"):
        assert dim in ov["aggregate"], f"aggregate 缺维度 {dim!r}"
        for stat in ("mean", "min", "max", "baseline"):
            assert stat in ov["aggregate"][dim]

    # closing
    cl = by_stage["closing"]
    for k in ("love_letter_eligible", "convergence_years",
              "triggered_motifs", "headers"):
        assert k in cl, f"closing 缺字段 {k!r}"
    assert cl["headers"]["declaration"] == "## 我想和你说"
    assert cl["headers"]["love_letter"] == "## 项目的编写者想和你说"
    assert cl["headers"]["free_speech"] == "## 我（大模型）想和你说"


# ---------------------------------------------------------------------------
# §3 --next / --resume 增量推进 == --stage all
# ---------------------------------------------------------------------------

def test_resume_next_equivalent_to_stage_all(tmp_path: Path, example_bazi: Path):
    # --stage all baseline
    state_all = tmp_path / "all.json"
    rc, out_all, _ = _run_pipeline([
        "stream", "--bazi", str(example_bazi),
        "--stage", "all", "--state", str(state_all),
    ])
    assert rc == 0
    payloads_all = {r["stage"]: r["payload"] for r in _parse_ndjson(out_all)}

    # 增量：6 次 --resume --next
    state_inc = tmp_path / "inc.json"
    payloads_inc: dict[str, dict] = {}
    for i in range(len(EXPECTED_STAGES)):
        rc, out, err = _run_pipeline([
            "stream", "--bazi", str(example_bazi),
            "--resume", str(state_inc), "--next",
        ])
        assert rc == 0, f"第 {i} 次 --next 失败：{err}"
        records = _parse_ndjson(out)
        assert len(records) == 1, f"--next 第 {i} 次 emit 多条（{len(records)} 条）"
        rec = records[0]
        assert rec["stage"] == EXPECTED_STAGES[i], (
            f"--next 顺序不对，第 {i} 步应该是 "
            f"{EXPECTED_STAGES[i]!r}，实际 {rec['stage']!r}"
        )
        payloads_inc[rec["stage"]] = rec["payload"]

    # 全部跑完后再 --next 应返回 0 + stderr 提示
    rc, out, err = _run_pipeline([
        "stream", "--bazi", str(example_bazi),
        "--resume", str(state_inc), "--next",
    ])
    assert rc == 0
    assert "都已完成" in err

    # bit-for-bit 等价
    assert set(payloads_inc.keys()) == set(payloads_all.keys())
    for stage in EXPECTED_STAGES:
        assert payloads_inc[stage] == payloads_all[stage], (
            f"stage {stage!r} 增量与一次性结果不等价"
        )


# ---------------------------------------------------------------------------
# §4 --resume cursor pickup（跑两段后从中间继续）
# ---------------------------------------------------------------------------

def test_resume_picks_up_cursor(tmp_path: Path, example_bazi: Path):
    state = tmp_path / "cursor.json"
    # 第一次跑 2 个 stage
    for _ in range(2):
        rc, out, _ = _run_pipeline([
            "stream", "--bazi", str(example_bazi),
            "--resume", str(state), "--next",
        ])
        assert rc == 0
    s = json.loads(state.read_text(encoding="utf-8"))
    assert s["completed_stages"] == [EXPECTED_STAGES[0], EXPECTED_STAGES[1]]

    # 再跑一次，应该出 stage[2]
    rc, out, _ = _run_pipeline([
        "stream", "--bazi", str(example_bazi),
        "--resume", str(state), "--next",
    ])
    assert rc == 0
    rec = _parse_ndjson(out)[0]
    assert rec["stage"] == EXPECTED_STAGES[2]


# ---------------------------------------------------------------------------
# §5 render_artifact --from-stream-state 能从 state 还原渲染（e2e 兜底）
# ---------------------------------------------------------------------------

def test_render_from_stream_state(tmp_path: Path, example_bazi: Path):
    state = tmp_path / "stream.json"
    rc, _, err = _run_pipeline([
        "stream", "--bazi", str(example_bazi),
        "--stage", "all", "--state", str(state),
    ])
    assert rc == 0, err

    out_html = tmp_path / "out.html"
    proc = subprocess.run(
        [sys.executable, str(RENDER),
         "--from-stream-state", str(state),
         "--out", str(out_html),
         "--no-strict-llm",
         "--allow-partial"],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"render_artifact --from-stream-state 失败：\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
    assert out_html.exists() and out_html.stat().st_size > 0
