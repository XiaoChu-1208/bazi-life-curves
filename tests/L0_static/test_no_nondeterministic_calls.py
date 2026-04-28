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
    "render_artifact.py",       # v9.3.1 渲染 HTML 报告, 仅展示 generated_at 给读者, 不进打分链路
    "phase_inversion_loop.py",  # 编排器,只串脚本不进打分
    "adaptive_elicit.py",       # v9 自适应问答主入口:用 dt.date.today() 取当前年份;
                                # 用 random.Random(bazi_fp) 做 batch 题集**确定性**洗牌
                                # —— 不进打分产物（只生成用户题集 / state 文件），bit-for-bit 由 fingerprint 保证
    "streaming_pipeline.py",    # v9.3 React-style streaming generator: 仅写 ts_iso 到 NDJSON / state 文件
                                # （编排时间戳，便于审计 stage 推进），不进入打分产物链路；
                                # 真正的曲线计算转交给 score_curves.score()，bit-for-bit 仍由 score_curves 保证
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
    "rare_phase_detector.py",  # v9 PR-5 特殊格 detector,纯静态判定
    "_school_registry.py",     # v9 PR-6 多流派注册表,纯静态判定
    "multi_school_vote.py",    # v9 PR-6 加权投票,纯静态聚合
    "_phase_registry.py",      # v9 L1 phase 注册表,纯静态 metadata
    "_mangpai_reversal.py",    # v9 L5 反转规则引擎,纯 yaml + 模式匹配
    "_eig_selector.py",        # v9 自适应贝叶斯问答核心算法,纯函数无 IO
    "audit_questions.py",      # v9 静态审计工具,纯静态分析(只读 _question_bank.py)
    "_virtue_registry.py",     # v9 承认维度 38 母题注册表,纯静态 metadata + detector
    "virtue_motifs.py",        # v9 承认维度独立通道,纯函数（输入 bazi+curves → 母题列表）
    "audit_llm_invented.py",   # v9 catalog 演化反馈,纯函数（扫描目录 → 自创母题候选清单）
    "append_analysis_node.py", # v9 流式可观测落盘,纯函数（读 partial → 写 partial,无随机/时间）
    "_v9_guard.py",            # v9 统一机械护栏,纯字符串/正则检查与抛错,无 IO/随机/时间
    "audit_mangpai_surface.py",          # v9 审计工具,纯静态文本/JSON 扫描,无随机/时间
    "audit_no_premature_decision.py",    # v9 审计工具,纯静态 JSON 字段检查
    "audit_virtue_recurrence_continuity.py",  # v9 审计工具,纯静态文本/JSON 扫描
    "audit_reference_consistency.py",    # v9.3 防回潮审计,纯静态 markdown 扫描
    # v9.6 事件 ask-loop 引擎(纯 Bayesian / 查表逻辑, 无随机/时间; 详见 references/event_ask_loop_protocol.md)
    "event_elicit.py",                   # Stage A 后验初始化 + Bayesian 更新 (纯函数 + assert 守不变量)
    "event_year_predictor.py",           # phase × 年份命中矩阵 (查 _phase_registry, 纯 predicate)
    "event_elicit_stage_b.py",           # 重叠年事件类型判别 (Jaccard 加权 + 查 phase_event_categories)
    "event_verification.py",             # 验证题候选 + likelihood 不对称 (纯 predicate + 似然查表)
    "phase_event_categories.py",         # phase → 事件类别静态映射表 (纯数据)
    "event_elicit_cli.py",               # 9 个子命令分发器 (subprocess 边界, 纯 JSON IO 无随机/时间)
    "apply_event_finalize.py",           # 写回 bazi.json (delegate to adaptive_elicit._finalize_phase)
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
