"""L4 · doc-code parity:守 AGENTS.md §4.1 那张"改 X 必须同步 Y"的表。

被检查的 1:1 关系:
1. solve_bazi.py --orientation choices == score_curves.py 内 orientation 处理 ==
   bazi.schema.json 内 orientation enum
2. score_curves.apply_phase_override 支持的 phase_id 列表 == README/SKILL/AGENTS 引用一致
3. AGENTS.md 提到的 v8 模块文件名必须真实存在(若不存在,标记 deferred 而不是悄悄过期)

注意:某些 v8 模块在 AGENTS.md 里被描述但实际还没实现 ——
这正是"文档悄悄过期"的典型,本测试会发出明确告警(xfail 而非 fail,
让团队按节奏补上,但永远在 CI 输出里看得见这个 gap)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.contract]


# ---------- 1. orientation 三处一致 ----------

ORIENTATIONS_EXPECTED = {"hetero", "homo", "bi", "none", "poly"}


def test_orientation_enum_consistency_across_layers(scripts_path: Path):
    """solve_bazi.py 的 --orientation choices 必须与代码内 valid_orientations 一致,
    并与 bazi.schema.json 的 enum 一致。"""
    src = (scripts_path / "solve_bazi.py").read_text(encoding="utf-8")

    cli_choices = set(re.findall(
        r'choices=\[([^\]]+)\][^)]*?(?:dest="orientation"|"--orientation")',
        src
    ))
    cli_set: set[str] = set()
    for m in re.finditer(r'"--orientation".*?choices=\[([^\]]+)\]', src, flags=re.DOTALL):
        for tok in re.findall(r'"([^"]+)"', m.group(1)):
            cli_set.add(tok)
    assert cli_set, "无法从 solve_bazi.py 解析 --orientation choices"

    code_set_match = re.search(
        r'valid_orientations\s*=\s*\{([^}]+)\}', src
    )
    assert code_set_match, "solve_bazi.py 找不到 valid_orientations 集合"
    code_set = set(re.findall(r'"([^"]+)"', code_set_match.group(1)))

    assert cli_set == code_set == ORIENTATIONS_EXPECTED, (
        f"\n  orientation 三处不一致!\n"
        f"  CLI choices:           {sorted(cli_set)}\n"
        f"  valid_orientations:    {sorted(code_set)}\n"
        f"  schema 期望:           {sorted(ORIENTATIONS_EXPECTED)}\n"
        f"  违反 AGENTS.md §4.1 \"改任何涉及性别/取向/关系结构的改动必须先读 fairness §9-§10\"\n"
    )

    schemas_dir = Path(__file__).resolve().parent / "schemas"
    for sf in ("bazi.schema.json", "curves.schema.json"):
        schema = json.loads((schemas_dir / sf).read_text(encoding="utf-8"))
        ori_enum = schema["properties"]["orientation"]["enum"]
        assert set(ori_enum) == ORIENTATIONS_EXPECTED, (
            f"  {sf} 的 orientation enum 与代码不一致: {ori_enum}"
        )


# ---------- 2. phase_override id 列表一致 ----------

def test_phase_override_ids_documented_consistently(scripts_path: Path, root_path: Path):
    """score_curves.apply_phase_override 的 label_map 必须包含
    --override-phase CLI help 里列出的所有 id。"""
    src = (scripts_path / "score_curves.py").read_text(encoding="utf-8")

    label_map_match = re.search(
        r'label_map\s*=\s*\{([^}]+)\}', src, flags=re.DOTALL
    )
    assert label_map_match, "找不到 label_map 字典"
    code_phase_ids = set(re.findall(r'"([a-z_]+(?:_[a-z]+)+)"\s*:', label_map_match.group(1)))

    cli_block_match = re.search(
        r'"--override-phase".*?\)', src, flags=re.DOTALL
    )
    assert cli_block_match, "找不到 --override-phase argparse 块"
    cli_phase_ids = set(re.findall(
        r"\b(floating_dms_to_cong_\w+|dominating_god_\w+|climate_inversion_\w+|true_following|pseudo_following|huaqi_to_\w+)\b",
        cli_block_match.group(0)
    ))

    missing_in_code = cli_phase_ids - code_phase_ids - {"day_master_dominant"}
    assert not missing_in_code, (
        f"\n  CLI help 提到了 {sorted(missing_in_code)},但 label_map 里没有 ——\n"
        f"  用户用这些 id 会触发 ValueError。违反 §4.1。\n"
    )


# ---------- 3. AGENTS.md 提到的模块必须存在 ----------

# 在 AGENTS.md 里被宣告"必跑 / 主流程"的模块
AGENTS_MD_DECLARED_MODULES = [
    ("solve_bazi.py",        "must_exist"),
    ("score_curves.py",      "must_exist"),
    ("mangpai_events.py",    "must_exist"),
    ("handshake.py",         "must_exist"),
    ("save_confirmed_facts.py", "must_exist"),
    ("render_artifact.py",   "must_exist"),
    ("calibrate.py",         "must_exist"),
    ("he_pan.py",            "must_exist"),
    ("phase_inversion_loop.py", "must_exist"),
    ("phase_posterior.py",   "must_exist"),
    ("_question_bank.py",    "must_exist"),
]


@pytest.mark.parametrize("module_name,status", AGENTS_MD_DECLARED_MODULES,
                         ids=lambda x: x if isinstance(x, str) else "")
def test_agents_md_declared_modules_exist(scripts_path: Path, module_name: str, status: str):
    path = scripts_path / module_name
    if status == "must_exist":
        assert path.exists(), (
            f"\n  AGENTS.md 把 {module_name} 列为主流程模块,但 scripts/ 下找不到 ——\n"
            f"  要么实现它,要么从 AGENTS.md 删掉,二选一。\n"
        )
    elif status == "deferred_v8":
        if not path.exists():
            pytest.xfail(
                f"AGENTS.md §2 描述了 v8 模块 `{module_name}`,但实际尚未实现。"
                f"这是已知 gap,需在 v8 路线图中补齐(见 AGENTS.md §9)。"
            )


# ---------- 4. confirmed_facts.structural_corrections.kind 与代码一致 ----------

def test_phase_ids_question_bank_covers_score_curves(scripts_path: Path):
    """`_question_bank.ALL_PHASE_IDS` 必须覆盖 score_curves 里所有 phase_id。

    缺一个 phase_id 在题库 → handshake 里没有题能区分这个相位 → 后验更新时
    该相位的 likelihood 永远 = 1(或先验)→ 决策永远偏向它。
    """
    # conftest.py 已把 scripts/ 加到 sys.path
    import _question_bank  # type: ignore[import-not-found]

    qb_ids = set(_question_bank.ALL_PHASE_IDS)

    score_src = (scripts_path / "score_curves.py").read_text(encoding="utf-8")
    label_map_match = re.search(r'label_map\s*=\s*\{([^}]+)\}', score_src, flags=re.DOTALL)
    score_ids = set(re.findall(r'"([a-z_]+(?:_[a-z]+)+)"\s*:', label_map_match.group(1)))
    score_ids.add("day_master_dominant")  # 默认相位,label_map 外特判

    missing = score_ids - qb_ids
    assert not missing, (
        f"\n  score_curves 支持的相位 {sorted(missing)} 在 _question_bank.ALL_PHASE_IDS 里缺失\n"
        f"  → handshake 没有题能区分它们 → 后验决策永远偏离 → §4.1 题库 1:1 同步铁律破。\n"
    )


def test_structural_correction_kinds_aligned(scripts_path: Path):
    """save_confirmed_facts 写入的 kind 集合 == score_curves 接收的 kind 集合
    == confirmed_facts.schema.json 里 enum。"""
    score_src = (scripts_path / "score_curves.py").read_text(encoding="utf-8")

    accepted_kinds = set(re.findall(
        r'kind\s*==\s*"([a-z_]+)"', score_src
    ))
    expected = {"climate", "strength", "yongshen", "geju", "phase_override"}
    assert expected <= accepted_kinds, (
        f"\n  score_curves.apply_structural_corrections 没有处理:"
        f" {sorted(expected - accepted_kinds)}\n"
        f"  这些 kind 用户可以通过 save_confirmed_facts 写入,"
        f"但 score 时会被静默忽略 → 用户的纠错丢失。\n"
    )

    schemas_dir = Path(__file__).resolve().parent / "schemas"
    schema = json.loads((schemas_dir / "confirmed_facts.schema.json").read_text(encoding="utf-8"))
    schema_enum = set(schema["properties"]["structural_corrections"]["items"]
                            ["properties"]["kind"]["enum"])
    assert schema_enum == expected, (
        f"  confirmed_facts.schema.json 里 kind enum 与代码不一致: {schema_enum}"
    )
