"""L0 · 守 AGENTS.md 4.4 节"bit-for-bit deterministic 铁律"。

任何形式的随机性 / 当前时间 / UUID 都会破坏可复算性。
本测试用 AST 扫描 scripts/ 下所有 .py 文件,拒绝以下调用:
    random.* / secrets.* / uuid.uuid1/4 / datetime.now / datetime.today /
    time.time / time.monotonic / time.perf_counter

说明:`import datetime` 本身不禁(timedelta、date.fromisoformat 等是确定的),
只禁会引入不确定性的具体调用。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.static]


FORBIDDEN_CALLS = {
    # (module_alias, attr) 形式
    ("random", None),  # 任何 random.* 都禁
    ("secrets", None),
    ("uuid", "uuid1"),
    ("uuid", "uuid4"),
    ("datetime", "now"),
    ("datetime", "today"),
    ("dt", "now"),  # `import datetime as dt` 的常见 alias
    ("dt", "today"),
    ("time", "time"),
    ("time", "monotonic"),
    ("time", "perf_counter"),
    ("time", "process_time"),
}

# 允许使用上述调用的脚本(白名单).这些脚本的输出**不进入**打分产物,
# 而是写时间戳到用户记录文件 / 命令行日志中,与 determinism 无关。
ALLOWLIST_FILES = {
    "save_confirmed_facts.py",  # 写 last_updated 时间戳
    "handshake.py",             # 用 dt.date.today() 标记当前年份
    "he_pan.py",                # 报告生成时间
    "he_pan_orchestrator.py",   # v9 PR-2 多人 v8 编排器,串脚本不进打分
    "mcp_server.py",            # MCP 服务,非打分路径
    "phase_inversion_loop.py",  # 编排器,只串脚本不进打分
}

# 进入"确定性产物"链的核心脚本 — 一定要严格守
DETERMINISTIC_CORE = {
    "_bazi_core.py",
    "_engines.py",
    "_class_prior.py",
    "_question_bank.py",
    "_zeitgeist_loader.py",
    "solve_bazi.py",
    "score_curves.py",
    "mangpai_events.py",
    "phase_posterior.py",
    "render_chart.py",
    "render_artifact.py",
    "calibrate.py",
    "family_profile.py",
}


def _find_forbidden_calls(tree: ast.AST) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # 形如 random.choice() / dt.now() / time.time()
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            mod = func.value.id
            attr = func.attr
            for f_mod, f_attr in FORBIDDEN_CALLS:
                if mod == f_mod and (f_attr is None or attr == f_attr):
                    hits.append((node.lineno, f"{mod}.{attr}"))
                    break
        # 形如 datetime.datetime.now()
        elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute):
            inner = func.value
            if isinstance(inner.value, ast.Name) and inner.value.id == "datetime" and func.attr in ("now", "today"):
                hits.append((node.lineno, f"datetime.datetime.{func.attr}"))
    return hits


@pytest.mark.parametrize(
    "py_file",
    sorted((Path(__file__).resolve().parent.parent.parent / "scripts").glob("*.py")),
    ids=lambda p: p.name,
)
def test_no_nondeterministic_calls_in_core(py_file: Path):
    """核心脚本里禁止任何不确定调用(随机/当前时间/UUID)。"""
    if py_file.name in ALLOWLIST_FILES:
        pytest.skip(f"{py_file.name} 在 ALLOWLIST 中(写时间戳/编排器,不进打分产物)")
    if py_file.name not in DETERMINISTIC_CORE:
        pytest.fail(
            f"\n  {py_file.name} 既不在 DETERMINISTIC_CORE 也不在 ALLOWLIST。\n"
            f"  新增脚本必须在本测试文件里显式归类(避免漏守 determinism)。\n"
        )
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    hits = _find_forbidden_calls(tree)
    assert not hits, (
        f"\n\n  {py_file.name} 中发现破坏 determinism 的调用:\n"
        + "\n".join(f"    line {ln}: {call}()" for ln, call in hits)
        + f"\n\n  违反 AGENTS.md §4.4 「bit-for-bit deterministic 铁律」。"
        f"\n  如确需,请把脚本加入 ALLOWLIST_FILES 并说明它不进入打分产物链路。\n"
    )
