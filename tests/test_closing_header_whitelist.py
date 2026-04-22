"""v9.3: closing 三段「我想和你说的话」白名单 + 旧白名单已退役测试。

scripts/_v9_guard.py::check_closing_header 必须：
  - 接受 v9.3 三段固定 H2：
      declaration → "## 我想和你说"
      love_letter → "## 项目的编写者想和你说"
      free_speech → "## 我（大模型）想和你说"
  - 拒绝 v9 旧白名单（"## 走到这里" / "## 写到这里我想说" / "## 不在协议里的话"）
  - 拒绝任何 "## 承认维度" / "## 承认人性" / "## 灵魂宣言" / "## 宣告" / "## 情书" / "## 位置④" 等暴露协议结构 / 模板化标题
  - 对非 closing 节（任意其它 node key）一律放行
"""
from __future__ import annotations

import pytest

from _v9_guard import check_closing_header


# ─── v9.3 新白名单：必须放行 ───────────────────────────────────────

@pytest.mark.parametrize(
    "node, header",
    [
        ("declaration", "## 我想和你说"),
        ("declaration", "## 我想和你说\n\n正文…"),
        ("love_letter", "## 项目的编写者想和你说"),
        ("love_letter", "## 项目的编写者想和你说\n\n正文…"),
        ("free_speech", "## 我（大模型）想和你说"),
        ("free_speech", "## 我（大模型）想和你说\n\n正文…"),
    ],
)
def test_v93_whitelist_passes(node: str, header: str) -> None:
    assert check_closing_header(node, header) is None


# ─── v9 旧白名单：已退役，命中即拒 ────────────────────────────

@pytest.mark.parametrize(
    "node, header",
    [
        ("declaration", "## 走到这里"),
        ("declaration", "## 走到这里 · 收尾"),
        ("love_letter", "## 写到这里我想说"),
        ("love_letter", "## 写到这里我想说\n正文"),
        ("free_speech", "## 不在协议里的话"),
        ("free_speech", "## 不在协议里的话\n\n正文"),
    ],
)
def test_v9_legacy_whitelist_rejected(node: str, header: str) -> None:
    err = check_closing_header(node, header)
    assert err is not None, (
        f"v9 旧白名单 {header!r} 必须被拒绝，但 check_closing_header 返回 None"
    )


# ─── 暴露协议结构 / 模板化措辞：必须拒 ────────────────────────────

@pytest.mark.parametrize(
    "node, header",
    [
        ("declaration", "## 承认维度·宣告"),
        ("declaration", "## 承认维度 · 宣告"),
        ("declaration", "## 承认人性"),
        ("declaration", "## 位置④灵魂宣言"),
        ("declaration", "## 灵魂宣言"),
        ("declaration", "## 宣告"),
        ("love_letter", "## 给你（本人）的一封信"),
        ("love_letter", "## 位置⑤情书"),
        ("love_letter", "## 情书"),
        ("free_speech", "## 位置⑥ LLM 自由话"),
        ("free_speech", "## 自由发言"),
        ("free_speech", "## free_speech"),
        ("free_speech", "## Free Speech"),
        ("free_speech", "## declaration"),
    ],
)
def test_template_headers_rejected(node: str, header: str) -> None:
    err = check_closing_header(node, header)
    assert err is not None, (
        f"模板化 / 暴露协议结构标题 {header!r} 必须被拒绝"
    )


# ─── 非 closing 节：任意 H2 都放行 ──────────────────────────────

@pytest.mark.parametrize(
    "node",
    [
        "overall",
        "life_review.spirit",
        "dayun_reviews.辛丑",
        "key_years.0",
        "virtue_narrative.opening",
        "virtue_narrative.convergence_notes",
    ],
)
def test_non_closing_nodes_pass(node: str) -> None:
    for header in (
        "## 走到这里",
        "## 任意标题",
        "## 承认维度·宣告",
        "## 灵魂宣言",
    ):
        assert check_closing_header(node, header) is None, (
            f"非 closing 节 {node!r} 不应被 closing 标题白名单拦截"
        )


# ─── 错误形态：空 markdown / 非 H2 / 缺标题 ────────────────────

@pytest.mark.parametrize("node", ["declaration", "love_letter", "free_speech"])
def test_empty_or_non_h2_rejected(node: str) -> None:
    for body in (
        "正文，但没有 H2",
        "# 一级标题",
        "### 三级标题",
        "## ",  # 空标题
    ):
        err = check_closing_header(node, body)
        assert err is not None, (
            f"closing 节 {node!r} 首行非合法 H2 {body!r} 必须被拒绝"
        )
