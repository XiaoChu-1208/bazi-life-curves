"""v9.3 R-STREAM-2: 单条 assistant message 顶级 ## heading 数量铁律。

scripts/_v9_guard.py::count_top_headings + check_message_heading_count 必须：

  - 数 markdown 中顶级 `## ` heading 数量（忽略 ### / #### / 行内 ##）
  - 单 message 顶级 ## ≥ 2 → return HeadingCountViolation
  - 0-1 个顶级 ## → return None（合规）
  - allow_closing_chain=True 且所有 heading 都属于 closing 三段 → 放行
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _v9_guard import (  # noqa: E402
    HeadingCountViolation,
    check_message_heading_count,
    count_top_headings,
)


# ─── count_top_headings ────────────────────────────────────────────

@pytest.mark.parametrize(
    "md, expected",
    [
        ("", 0),
        ("没有任何 heading 的纯文本", 0),
        ("## 单个 heading\n\n正文", 1),
        ("## 第一个\n\n正文\n\n## 第二个\n\n正文", 2),
        ("## A\n## B\n## C", 3),
        # ### 不算顶级
        ("### 三级 heading\n\n正文", 0),
        # #### 不算顶级
        ("#### 四级 heading", 0),
        # 行内 ## 不算
        ("正文里出现 ## 不应被算 heading", 0),
        # 顶级 + 嵌套混合
        ("## 顶级\n\n### 二级\n\n#### 三级", 1),
    ],
)
def test_count_top_headings(md: str, expected: int) -> None:
    assert count_top_headings(md) == expected


# ─── check_message_heading_count ───────────────────────────────────

def test_check_zero_heading_passes() -> None:
    assert check_message_heading_count("纯正文，没有 heading") is None


def test_check_one_heading_passes() -> None:
    assert check_message_heading_count("## 单个标题\n\n正文") is None


def test_check_two_headings_violates() -> None:
    md = "## 第一节\n\n正文\n\n## 第二节\n\n更多正文"
    v = check_message_heading_count(md)
    assert isinstance(v, HeadingCountViolation)
    assert v.count == 2
    assert "## 第一节" in v.headings
    assert "## 第二节" in v.headings
    assert "R-STREAM-2" in v.reason


def test_check_seven_headings_violates() -> None:
    md = "\n\n".join(f"## 第{i}节\n正文 {i}" for i in range(7))
    v = check_message_heading_count(md)
    assert isinstance(v, HeadingCountViolation)
    assert v.count == 7


# ─── allow_closing_chain 例外 ─────────────────────────────────────

def test_closing_chain_allowed_in_last_turn() -> None:
    """closing 三段在最后一条 turn 紧邻出现 → allow_closing_chain=True 放行。"""
    md = (
        "## 我想和你说\n\n第一段\n\n"
        "## 项目的编写者想和你说\n\n第二段\n\n"
        "## 我（大模型）想和你说\n\n第三段"
    )
    assert check_message_heading_count(md, allow_closing_chain=True) is None


def test_closing_chain_not_allowed_without_flag() -> None:
    """同样的三段，没有 allow_closing_chain 仍违规。"""
    md = (
        "## 我想和你说\n\n第一段\n\n"
        "## 项目的编写者想和你说\n\n第二段\n\n"
        "## 我（大模型）想和你说\n\n第三段"
    )
    v = check_message_heading_count(md, allow_closing_chain=False)
    assert isinstance(v, HeadingCountViolation)
    assert v.count == 3


def test_closing_chain_with_extra_heading_violates() -> None:
    """allow_closing_chain=True 但混入了非 closing 标题 → 仍违规。"""
    md = (
        "## 我想和你说\n\n第一段\n\n"
        "## 不属于 closing 的额外标题\n\n正文\n\n"
        "## 我（大模型）想和你说\n\n第三段"
    )
    v = check_message_heading_count(md, allow_closing_chain=True)
    assert isinstance(v, HeadingCountViolation)
    assert v.count == 3


def test_closing_chain_partial_subset_allowed() -> None:
    """allow_closing_chain=True 且只出现 closing 三段中的 2 段 → 放行。"""
    md = (
        "## 我想和你说\n\n第一段\n\n"
        "## 项目的编写者想和你说\n\n第二段"
    )
    assert check_message_heading_count(md, allow_closing_chain=True) is None
