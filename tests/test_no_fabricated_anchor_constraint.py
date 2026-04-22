"""v9.3.1: open_phase anchor 收集 · 反 agent 编造硬约束守卫测试。

scripts/_v9_guard.py::scan_fabricated_anchor_constraint 必须：
  - 命中 agent 在 anchor 收集 UI / prompt 里自加的协议未规定 filter
  - 覆盖 5 类红线：年龄段 / 事件类型 / 强度 / 地理 / 身份 / 关系状态
  - 对协议合规的中性 prompt（"请补 ≥ 2 个具体公历年 + 事件描述"）不误报
  - 对叙事文本里出现的 "25 岁那次" / "成年前" 等 LLM 写作不误报

历史 incident（驱动本测试）：
  2026-04-22 · agent 在 open_phase UI 里写 "请补 ≥ 2 个你 25 岁前真实经历过的
  事件年份"，把用户输的 2023 / 2024 全部静默 filter 成 "已识别 0 个有效年份"，
  导致用户对话循环卡死。详见 references/open_phase_anchor_protocol.md §5。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from _v9_guard import (  # noqa: E402
    FabricatedAnchorError,
    enforce_no_fabricated_anchor_constraint,
    scan_fabricated_anchor_constraint,
)


# ─── §1 历史 incident 原句 · 必须命中 ─────────────────────────────

def test_historical_25_age_constraint_caught() -> None:
    """2026-04-22 incident 原话必须被拦下来。"""
    text = "请补 ≥ 2 个你 25 岁前真实经历过的事件年份（公历年）"
    hits = scan_fabricated_anchor_constraint(text)
    assert len(hits) >= 1, (
        f"历史 incident 原句未被拦截：{text!r}"
    )
    assert any("年龄段" in h.reason for h in hits), (
        f"未识别为年龄段约束：{[h.reason for h in hits]}"
    )


# ─── §2 五类红线 · 每类至少一条命中 ───────────────────────────────

@pytest.mark.parametrize("text", [
    "请补 ≥ 2 个你 25 岁前的事件",
    "请补 30 岁前真实经历过的年份",
    "只收成年前的锚点",
    "请提供童年期的标志事件",
    "必须输入本命大运前的事件年份",
])
def test_age_window_constraints_caught(text: str) -> None:
    hits = scan_fabricated_anchor_constraint(text)
    assert len(hits) >= 1, f"年龄段红线未命中：{text!r}"


@pytest.mark.parametrize("text", [
    "请补 ≥ 2 个学业事件",
    "只收事业类年份",
    "请提供 ≥ 2 个感情事件",
    "仅收健康事件",
])
def test_event_type_filter_caught(text: str) -> None:
    hits = scan_fabricated_anchor_constraint(text)
    assert len(hits) >= 1, f"事件类型 filter 未命中：{text!r}"


@pytest.mark.parametrize("text", [
    "请补 ≥ 2 个大事件",
    "只收改变人生轨迹的事件",
    "仅收标志性事件",
    "请输入重大事件年份",
])
def test_intensity_filter_caught(text: str) -> None:
    hits = scan_fabricated_anchor_constraint(text)
    assert len(hits) >= 1, f"强度阈值 filter 未命中：{text!r}"


@pytest.mark.parametrize("text", [
    "请补国内事件",
    "只收出生地的年份",
    "请提供已婚后的事件",
    "仅收已工作后的锚点",
])
def test_geo_identity_filter_caught(text: str) -> None:
    hits = scan_fabricated_anchor_constraint(text)
    assert len(hits) >= 1, f"地理/身份 filter 未命中：{text!r}"


# ─── §3 协议合规的中性 prompt · 不得误报 ─────────────────────────

@pytest.mark.parametrize("text", [
    "请补 ≥ 2 个你能确认的具体公历年 + 事件描述",
    "请输入 ≥ 2 条事件年份（YYYY 格式）+ 简短描述",
    "三派对你这张盘的当前 phase 没有形成 ≥ 0.55 的共识 —— "
    "我不替你定一种读法。请补 ≥ 2 个具体年份与事件。",
    "例如：2005, 2012, 2018",
    "(可选) 简短描述发生了什么 (200 字内)",
])
def test_neutral_prompts_not_flagged(text: str) -> None:
    hits = scan_fabricated_anchor_constraint(text)
    assert hits == [], (
        f"协议合规的中性 prompt 不应被误报：{text!r}\n"
        f"误报命中：{[(h.reason, h.snippet) for h in hits]}"
    )


# ─── §4 LLM 叙事文本 · 不得误报 ────────────────────────────────
#
# `references/virtue_recurrence_protocol.md` 等叙事文本里出现 "25 岁那次" /
# "成年前" 是 LLM 写作的合法用法，不是 agent 在 anchor 收集 UI 里加 filter。
# 守卫只盯"请/必须/只/仅 + 补/提供/输入/给"这种 imperative 抛题动作。

@pytest.mark.parametrize("text", [
    "走到这里，那个 25 岁的剧本以另一种皮重演",
    "你 25 岁那次（伤官见官应期）是这一类经历的头一次",
    "成年前你大概率经历过 X 类事件",
    "童年期的家庭画像偏波折",
])
def test_narrative_text_not_flagged(text: str) -> None:
    hits = scan_fabricated_anchor_constraint(text)
    assert hits == [], (
        f"LLM 叙事文本不应被守卫拦截：{text!r}\n"
        f"误报命中：{[(h.reason, h.snippet) for h in hits]}"
    )


# ─── §5 enforce_* 抛错路径 ────────────────────────────────────

def test_enforce_raises_on_fabricated() -> None:
    with pytest.raises(FabricatedAnchorError) as exc:
        enforce_no_fabricated_anchor_constraint(
            "请补 ≥ 2 个你 25 岁前真实经历过的事件年份"
        )
    assert exc.value.code == 12, (
        f"FabricatedAnchorError 退出码必须是 12，实际：{exc.value.code}"
    )
    assert len(exc.value.hits) >= 1


def test_enforce_does_not_raise_on_neutral() -> None:
    hits = enforce_no_fabricated_anchor_constraint(
        "请补 ≥ 2 个你能确认的具体公历年 + 事件描述"
    )
    assert hits == []


def test_enforce_raise_on_hit_false_returns_hits() -> None:
    hits = enforce_no_fabricated_anchor_constraint(
        "请补 ≥ 2 个你 25 岁前真实经历过的事件年份",
        raise_on_hit=False,
    )
    assert len(hits) >= 1


# ─── §6 边界 case ────────────────────────────────────────────

@pytest.mark.parametrize("text", ["", None])
def test_empty_input_returns_empty(text) -> None:
    assert scan_fabricated_anchor_constraint(text) == []


def test_render_contains_protocol_pointer() -> None:
    err = FabricatedAnchorError([
        # 制造一条假命中以渲染错误信息
    ])
    # hits 为空时也能 render（不抛 IndexError 等）
    rendered = err.render()
    assert "open_phase_anchor_protocol.md" in rendered, (
        "错误信息必须指向 open_phase_anchor_protocol.md"
    )
