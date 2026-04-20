"""L4 · pipeline 契约层。

每改一次 score_curves / solve_bazi,这里会拦下"悄悄改字段名 / 改类型"
导致下游 render_artifact 默默渲染空白的最经典 bug 模式。

测试方法:
1. 现场跑 solve_bazi.solve() / score_curves.score() 拿当前真实输出
2. 对照 schemas/*.json 校验
3. 同时校验 examples/ 下的历史产物 — 防"既有产物已经不符合 schema"
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

pytestmark = [pytest.mark.fast, pytest.mark.contract]


SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


# ---------------------- 现场运行 ----------------------

@pytest.fixture(scope="module")
def freshly_solved_bazi(canonical_pillars):
    """对 canonical pillars 现场跑 solve_bazi → 返回 (id, bazi dict) 列表。"""
    from solve_bazi import solve

    out = []
    for sample in canonical_pillars:
        bazi = solve(
            pillars_str=sample["pillars"],
            gregorian=None,
            gender="M",
            birth_year=sample["birth_year"],
            n_years=80,
        )
        out.append((sample["id"], bazi))
    return out


@pytest.fixture(scope="module")
def freshly_scored_curves(freshly_solved_bazi):
    """对每个 bazi 跑 score_curves → 返回 (id, curves dict) 列表。"""
    from score_curves import score

    out = []
    for sid, bazi in freshly_solved_bazi:
        curves = score(bazi, age_end=80, forecast_window=0)
        out.append((sid, curves))
    return out


# ---------------------- bazi.schema ----------------------

def test_solve_bazi_output_matches_schema(freshly_solved_bazi):
    schema = _load_schema("bazi.schema.json")
    for sid, bazi in freshly_solved_bazi:
        try:
            jsonschema.validate(bazi, schema)
        except jsonschema.ValidationError as e:
            pytest.fail(
                f"\n  solve_bazi(`{sid}`) 输出违反 bazi.schema.json:\n"
                f"  path={'.'.join(str(p) for p in e.absolute_path)}\n"
                f"  msg={e.message}\n"
            )


# ---------------------- curves.schema ----------------------

def test_score_curves_output_matches_schema(freshly_scored_curves):
    schema = _load_schema("curves.schema.json")
    for sid, curves in freshly_scored_curves:
        try:
            jsonschema.validate(curves, schema)
        except jsonschema.ValidationError as e:
            pytest.fail(
                f"\n  score_curves(`{sid}`) 输出违反 curves.schema.json:\n"
                f"  path={'.'.join(str(p) for p in e.absolute_path)}\n"
                f"  msg={e.message}\n"
            )


def test_curves_yearly_values_in_range(freshly_scored_curves):
    """spirit/wealth/fame/emotion 任何一年都必须落在 [0, 100]。

    这是"打分" 的语义不变量,任何超出都会让前端图表 Y 轴异常 + LLM 解读失真。
    """
    for sid, curves in freshly_scored_curves:
        for p in curves["points"]:
            for dim in ("spirit_yearly", "wealth_yearly", "fame_yearly"):
                v = p[dim]
                assert 0 <= v <= 100, (
                    f"  {sid} 在 {p['year']} 年 {dim}={v} 越界"
                )
            if "emotion_yearly" in p:
                assert 0 <= p["emotion_yearly"] <= 100, (
                    f"  {sid} 在 {p['year']} 年 emotion_yearly={p['emotion_yearly']} 越界"
                )


def test_curves_age_monotonic(freshly_scored_curves):
    """points 必须按年龄严格递增,不能有重复或逆序。"""
    for sid, curves in freshly_scored_curves:
        ages = [p["age"] for p in curves["points"]]
        assert ages == sorted(ages), f"{sid} points 年龄不严格递增: {ages[:10]}..."
        assert len(set(ages)) == len(ages), f"{sid} points 出现重复年龄"


def test_render_required_fields_subset_of_curves(freshly_scored_curves):
    """模板里直接引用的字段必须在 curves 输出里都存在 — 守 contract 最常见破口。"""
    REQUIRED = {
        "points", "dayun_segments", "baseline", "yongshen",
        "pillars_str", "day_master", "strength",
    }
    for sid, curves in freshly_scored_curves:
        missing = REQUIRED - curves.keys()
        assert not missing, (
            f"  curves(`{sid}`) 缺少 render_artifact 必需字段: {sorted(missing)}"
        )


# ---------------------- 历史 examples 也要符合 schema ----------------------

def _existing_example_files(root: Path, pattern: str) -> list[Path]:
    return sorted((root / "examples").glob(pattern))


@pytest.mark.parametrize(
    "bazi_file",
    _existing_example_files(Path(__file__).resolve().parent.parent.parent, "*.bazi.json"),
    ids=lambda p: p.name,
)
def test_existing_bazi_examples_match_schema(bazi_file: Path):
    schema = _load_schema("bazi.schema.json")
    data = json.loads(bazi_file.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        pytest.fail(
            f"\n  历史样本 {bazi_file.name} 不符合当前 bazi.schema.json:\n"
            f"  path={'.'.join(str(p) for p in e.absolute_path)}\n"
            f"  msg={e.message}\n"
            f"  → 要么补 schema(向前兼容),要么重新生成样本。\n"
        )


@pytest.mark.parametrize(
    "curves_file",
    _existing_example_files(Path(__file__).resolve().parent.parent.parent, "*.curves.json"),
    ids=lambda p: p.name,
)
def test_existing_curves_examples_match_schema(curves_file: Path):
    schema = _load_schema("curves.schema.json")
    data = json.loads(curves_file.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        pytest.fail(
            f"\n  历史样本 {curves_file.name} 不符合当前 curves.schema.json:\n"
            f"  path={'.'.join(str(p) for p in e.absolute_path)}\n"
            f"  msg={e.message}\n"
        )
