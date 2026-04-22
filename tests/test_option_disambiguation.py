"""v9.3 · 选项消歧铁律覆盖测试。

scripts/_question_bank.py 中：
  - _MIN_OPTION_LABEL_CHARS = 12（强迫 label ≥12 字，写出"核心描述 + 场景边界"）
  - _check_option_disambiguation：每题至少 1 个 option label 包含「消歧括号备注」，
    备注内出现 _DISAMB_HINT_TOKENS 任一 token（"也算 / 含 / 偏 / 主要 / 大致 / ≤ / ≥" 等）。

本测试覆盖：
  1. 全量 STATIC_QUESTIONS（D1+D2+D4+D5+D6 共 25 题）模块加载时已 strict=True
     通过 _check_option_disambiguation；这里再 explicit 再扫一遍做 regression 兜底。
  2. 反例：构造一个 4 个 label 都没有括号备注的 fake Question → strict raise。
  3. 反例：括号有但备注里没有 hint token（如 "(纯描述)"）→ strict raise。
  4. label 短于 _MIN_OPTION_LABEL_CHARS → _check_plain_language strict raise。
"""
from __future__ import annotations

import pytest

from _question_bank import (
    STATIC_QUESTIONS,
    Question,
    QuestionOption,
    _MIN_OPTION_LABEL_CHARS,
    _check_option_disambiguation,
    _check_plain_language,
)


# ─── 1. 全量题库 regression ────────────────────────────────────────

@pytest.mark.parametrize("q", STATIC_QUESTIONS, ids=lambda q: q.id)
def test_every_static_question_has_disambiguation_option(q: Question) -> None:
    """每道静态题必须至少 1 个 option label 带「消歧括号备注」。"""
    issues = _check_option_disambiguation(q, strict=False)
    assert issues == [], (
        f"{q.id} 缺少消歧括号备注：{issues}"
    )


@pytest.mark.parametrize("q", STATIC_QUESTIONS, ids=lambda q: q.id)
def test_every_static_question_label_meets_min_chars(q: Question) -> None:
    """每道静态题的每个 option label 必须 ≥ _MIN_OPTION_LABEL_CHARS 字。"""
    for o in q.options:
        assert len(o.label) >= _MIN_OPTION_LABEL_CHARS, (
            f"{q.id} 选项 {o.id} label 仅 {len(o.label)} 字（< {_MIN_OPTION_LABEL_CHARS}）：{o.label!r}"
        )


# ─── 2. 反例：4 个 label 都没括号 → strict raise ────────────────────

def _fake_question_no_brackets() -> Question:
    """4 个 label 都没有任何括号备注 → 必须 raise。"""
    return Question(
        id="FAKE_NO_BRACKETS",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="测试题面：你长期默认更接近哪种工作风格？",
        options=[
            QuestionOption("A", "稳健派工作风格、按部就班完成任务也行"),
            QuestionOption("B", "进攻派工作风格、敢于拍板冲在前面也行"),
            QuestionOption("C", "灵活派工作风格、看场合切换不固定也行"),
            QuestionOption("D", "佛系派工作风格、不争不抢躺平也行"),
        ],
        likelihood_table={
            "day_master_dominant": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        },
    )


def test_no_bracket_disamb_raises() -> None:
    q = _fake_question_no_brackets()
    with pytest.raises(AssertionError, match="v9.3 选项消歧铁律"):
        _check_option_disambiguation(q, strict=True)


# ─── 3. 反例：括号有但没有 hint token ──────────────────────────────

def _fake_question_brackets_no_hint() -> Question:
    """4 个 label 的括号备注里没有 hint token（"也算 / 含 / 偏 ..."），仅是纯描述 → 必须 raise。"""
    return Question(
        id="FAKE_BRACKETS_NO_HINT",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="测试题面：你长期默认更接近哪种工作风格？",
        options=[
            QuestionOption("A", "稳健派工作风格（一种描述方式而已）"),
            QuestionOption("B", "进攻派工作风格（另一种描述方式而已）"),
            QuestionOption("C", "灵活派工作风格（第三种描述方式而已）"),
            QuestionOption("D", "佛系派工作风格（最后一种描述方式而已）"),
        ],
        likelihood_table={
            "day_master_dominant": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        },
    )


def test_brackets_without_hint_token_raises() -> None:
    q = _fake_question_brackets_no_hint()
    with pytest.raises(AssertionError, match="v9.3 选项消歧铁律"):
        _check_option_disambiguation(q, strict=True)


# ─── 4. 反例：label 短于 _MIN_OPTION_LABEL_CHARS → plain language raise ─

def _fake_question_short_label() -> Question:
    """label 短于 12 字 → _check_plain_language strict raise。"""
    return Question(
        id="FAKE_SHORT_LABEL",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="测试题面：你长期默认更接近哪种工作风格？",
        options=[
            QuestionOption("A", "稳健（含按部就班也算）"),
            QuestionOption("B", "进攻派工作风格、敢于冲在前面（含拍板也算）"),
            QuestionOption("C", "灵活派工作风格、看场合切换不固定（含变换也算）"),
            QuestionOption("D", "佛系派工作风格、不争不抢躺平（含随缘也算）"),
        ],
        likelihood_table={
            "day_master_dominant": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        },
    )


def test_short_label_raises_plain_language() -> None:
    q = _fake_question_short_label()
    with pytest.raises(AssertionError):
        _check_plain_language(q, strict=True)


# ─── 5. 正例：有 hint token 的备注通过 strict ───────────────────────

def _fake_question_valid() -> Question:
    return Question(
        id="FAKE_VALID",
        dimension="self_perception",
        weight_class="soft_self_report",
        prompt="测试题面：你长期默认更接近哪种工作风格？",
        options=[
            QuestionOption("A", "稳健派工作风格（含按部就班、不冒险也算）"),
            QuestionOption("B", "进攻派工作风格、敢于拍板冲在前面"),
            QuestionOption("C", "灵活派工作风格、看场合切换不固定"),
            QuestionOption("D", "佛系派工作风格、不争不抢长期躺平"),
        ],
        likelihood_table={
            "day_master_dominant": {"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        },
    )


def test_valid_question_passes_strict() -> None:
    q = _fake_question_valid()
    issues = _check_option_disambiguation(q, strict=True)
    assert issues == []
