"""tests/test_audit_reference_consistency.py — v9.3 防回潮 audit 回归

覆盖：
1. 真实仓库当前快照 → 必须 PASS（新增/重构后 leak 不能回潮）
2. 合成 fixture：包含旧 closing header → exit12
3. 合成 fixture：包含 Step 2.7 → exit12
4. 合成 fixture：包含 tone 词但有 v9.3 命名约定 banner → PASS
5. 合成 fixture：包含 tone 词且无 banner 也无 negation token → exit12
6. 合成 fixture：banner 也救不了 closing_header / Step 2.7 类
7. CLI --strict 与默认模式区别
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "audit_reference_consistency.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import audit_reference_consistency as audit  # type: ignore  # noqa: E402


# ---------------------------------------------------------------------------
# §1 真实仓库快照必须 PASS
# ---------------------------------------------------------------------------

def test_repo_snapshot_passes():
    """跑真实仓库默认 scan target，不应有任何 leak。

    若 fail：说明新加的 reference / 协议改动引入了回潮（旧 closing header /
    旧 tone 措辞 / Step 2.7 等）。CI 阻断。"""
    hits = audit.audit()
    assert hits == [], (
        "v9.3 防回潮 audit 失败：\n"
        + "\n".join(h.render() for h in hits)
    )


# ---------------------------------------------------------------------------
# §2 合成 fixture · positive guidance（无 banner、无 negation）应被命中
# ---------------------------------------------------------------------------

def _scan_text(tmp_path: Path, name: str, text: str) -> list[audit.Hit]:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return audit._scan_file(p)


def test_old_closing_header_h2_caught(tmp_path: Path):
    """协议文件 LLM 写作引导用旧 v9 closing header → 必须被命中。"""
    md = (
        "# 假协议\n\n"
        "请写完八十年后的收尾段：\n\n"
        "## 走到这里\n"
        "你这辈子被反复抓住的那件事……\n"
    )
    hits = _scan_text(tmp_path, "fake_protocol.md", md)
    severities = {h.severity for h in hits}
    assert "exit10" in severities, f"未命中 closing_header: {hits}"
    terms = {h.term for h in hits}
    assert "## 走到这里" in terms


def test_step_27_caught(tmp_path: Path):
    """协议文件还在引 Step 2.7 → 必须被命中（deprecated）。"""
    md = (
        "# 合盘流程\n\n"
        "Step 2.7 询问输出格式 ...\n"
    )
    hits = _scan_text(tmp_path, "fake_hepan.md", md)
    severities = {h.severity for h in hits}
    assert "deprecated" in severities, f"未命中 Step 2.7: {hits}"


# ---------------------------------------------------------------------------
# §2b v9.3.1 合盘 5 条 banned_terms（he_pan v9.3 化）
# ---------------------------------------------------------------------------

def test_hepan_v8_caveat_caught(tmp_path: Path):
    """旧 SKILL.md 「合盘暂未升级到 v8」必须被命中。"""
    md = (
        "# 合盘\n\n"
        "合盘暂未升级到 v8，仍走旧 R0/R1 校验路径。\n"
    )
    hits = _scan_text(tmp_path, "fake_skill.md", md)
    terms = {h.term for h in hits}
    assert "暂未升级到 v8" in terms, f"未命中 hepan_v8_caveat: {hits}"


def test_hepan_double_r1_hit_rate_caught(tmp_path: Path):
    md = (
        "# 合盘\n\n"
        "confidence 受双方 R1 命中率限制（短板效应）。\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    terms = {h.term for h in hits}
    assert "双方 R1 命中率" in terms, f"未命中 hepan_double_r1_hit_rate: {hits}"


def test_hepan_r0_anti_query_caught(tmp_path: Path):
    md = (
        "# 关系能量\n\n"
        "由 R0 反询问做命局取向校准。\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    terms = {h.term for h in hits}
    assert "R0 反询问" in terms, f"未命中 hepan_r0_anti_query: {hits}"


def test_hepan_health_three_questions_caught(tmp_path: Path):
    md = (
        "# 合盘\n\n"
        "双方都通过了 R1 健康三问（≥ 2/3 命中）→ 解读可以重一些。\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    terms = {h.term for h in hits}
    assert "健康三问" in terms, f"未命中 hepan_health_three_questions: {hits}"


def test_hepan_terms_passed_with_negation(tmp_path: Path):
    """同行带 negation token（已退役 / banned）应放行。"""
    md = (
        "# 合盘 v9.3\n\n"
        "旧 R0/R1 健康三问路径已退役，仅 --ack-batch 兜底。\n"
        "双方 R1 命中率（已退役）改为双方 phase.confidence 短板。\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    assert hits == [], f"带 negation 应放行，实际：{hits}"


def test_tone_term_in_positive_body_caught(tmp_path: Path):
    """协议文件正向引导 LLM 写「陀氏式」措辞 + 无 v9.3 banner → 必须命中。"""
    md = (
        "# 写作模板\n\n"
        "5. 陀氏式终章：「不会过去 / 不是要变通 / 它没让你 ABC ……」\n"
        "6. 共在确认：「我刚刚和你一起走过了这个」\n"
    )
    hits = _scan_text(tmp_path, "fake_template.md", md)
    severities = {h.severity for h in hits}
    assert "exit5" in severities, f"未命中 tone 措辞: {hits}"


# ---------------------------------------------------------------------------
# §3 合成 fixture · 合法 negation 上下文应放行
# ---------------------------------------------------------------------------

def test_negation_in_same_line_passes(tmp_path: Path):
    md = (
        "# 假协议\n\n"
        "v9.3 起，「陀式 / 陀氏 / 那一刀 / 灵魂宣言」全位置封禁，命中即 exit 5。\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    assert hits == [], f"误报：{hits}"


def test_negation_in_nearby_line_passes(tmp_path: Path):
    md = (
        "# 假协议\n\n"
        "v9.3 banned_patterns 已退役以下措辞：\n"
        "\n"
        "- 灵魂宣言\n"
        "- 陀氏\n"
        "- 那一刀\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    assert hits == [], f"误报：{hits}"


def test_blockquote_passes(tmp_path: Path):
    """`>` blockquote 视为协议自述，不算正向引导。"""
    md = (
        "# 假协议\n\n"
        "> v9.3 命名约定：内部仍保留「灵魂宣言」「陀氏」等术语作为章节元名称。\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    assert hits == [], f"误报：{hits}"


def test_heading_passes(tmp_path: Path):
    """`### ★ 灵魂宣言（最高原则）` 这类章节标题视为协议元名称。"""
    md = (
        "# 假协议\n\n"
        "### ★ 灵魂宣言（最高原则）\n"
        "正文……\n"
    )
    hits = _scan_text(tmp_path, "fake.md", md)
    assert hits == [], f"误报：{hits}"


# ---------------------------------------------------------------------------
# §4 v9.3 命名约定 banner 文件级豁免
# ---------------------------------------------------------------------------

def test_file_with_v93_banner_exempts_tone(tmp_path: Path):
    """文件顶部 60 行内有 v9.3 命名约定 banner → 全文 tone 类放行。"""
    md = (
        "# 协议\n\n"
        "> **v9.3 命名约定（强制 · 在写任何 user-facing 内容前必读）**：\n"
        "> 内部仍保留「灵魂宣言」「陀氏」等术语作为章节元名称，禁止外泄。\n"
        "\n"
        "## 1. 第一部分\n"
        "陀氏写索尼娅、阿廖沙是为了承认他们的伟大。\n"
        "## 2. 第二部分\n"
        "灵魂宣言不是孤悬的，它必须被反身性铁律约束。\n"
    )
    hits = _scan_text(tmp_path, "with_banner.md", md)
    assert hits == [], f"banner 应豁免 tone 类，实际：{hits}"


def test_file_banner_does_not_exempt_closing_header(tmp_path: Path):
    """banner 不豁免 closing_header / deprecated（这两类是真正的协议矛盾）。"""
    md = (
        "# 协议\n\n"
        "> **v9.3 命名约定**：内部仍保留 declaration / love_letter / free_speech。\n"
        "\n"
        "请写：\n"
        "## 走到这里\n"  # 正向引导用旧 H2 → 必须仍命中
        "正文……\n"
    )
    hits = _scan_text(tmp_path, "banner_with_old_h2.md", md)
    severities = {h.severity for h in hits}
    assert "exit10" in severities, (
        f"banner 不应豁免 closing_header，实际：{hits}"
    )


def test_file_banner_does_not_exempt_step_27(tmp_path: Path):
    md = (
        "# 协议\n\n"
        "> **v9.3 命名约定**：内部脚手架名。\n"
        "\n"
        "Step 2.7 询问输出格式 ...\n"
    )
    hits = _scan_text(tmp_path, "banner_with_step27.md", md)
    severities = {h.severity for h in hits}
    assert "deprecated" in severities


# ---------------------------------------------------------------------------
# §5 CLI 表面行为
# ---------------------------------------------------------------------------

def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True,
    )


def test_cli_strict_passes_on_clean_repo():
    proc = _run_cli("--strict")
    assert proc.returncode == 0, (
        f"CLI --strict 在 clean 仓库应 exit 0，实际 {proc.returncode}：\n"
        f"stderr={proc.stderr}"
    )
    assert "PASS" in proc.stdout


def test_cli_default_warns_but_does_not_fail(tmp_path: Path):
    """默认（非 strict）模式：找到 leak 也只 warn，不 fail。"""
    bad = tmp_path / "bad.md"
    bad.write_text("Step 2.7 询问输出格式\n", encoding="utf-8")
    proc = _run_cli("--paths", str(bad))
    assert proc.returncode == 0, f"非 strict 不应 fail：{proc.returncode}"
    assert "deprecated" in proc.stderr or "Step 2.7" in proc.stderr


def test_cli_strict_fails_with_exit_12(tmp_path: Path):
    bad = tmp_path / "bad.md"
    bad.write_text("Step 2.7 询问输出格式\n", encoding="utf-8")
    proc = _run_cli("--strict", "--paths", str(bad))
    assert proc.returncode == 12, (
        f"--strict 应 exit 12，实际 {proc.returncode}：\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )


def test_cli_unknown_path_returns_13(tmp_path: Path):
    proc = _run_cli("--paths", str(tmp_path / "does_not_exist.md"))
    assert proc.returncode == 13
