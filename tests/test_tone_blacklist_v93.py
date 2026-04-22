"""v9.3: tone_blacklist.yaml 新增禁词测试。

要求：
  - 「承认人性 / 承认维度 / 陀式 / 陀氏 / 陀式贯穿 / 陀氏贯穿 / 陀式那一刀 /
     陀氏那一刀 / 那一刀 / 灵魂宣言 / 宣告 / 情书」一律命中即 ToneError(exit 5)
  - 这些禁词「不进豁免列表」 → 即便在 whitelisted_nodes（love_letter /
     free_speech）也命中
  - 内部 schema 字段名（virtue_narrative.declaration / love_letter / free_speech）
     不受影响（不是 user-facing 文案）
"""
from __future__ import annotations

import pytest

from _v9_guard import scan_tone, ToneError, enforce_tone


_V93_BANNED = [
    "承认人性",
    "承认维度",
    "陀式",
    "陀氏",
    "陀式贯穿",
    "陀氏贯穿",
    "陀式那一刀",
    "陀氏那一刀",
    "那一刀",
    "灵魂宣言",
    "宣告",
    "情书",
]


@pytest.mark.parametrize("phrase", _V93_BANNED)
def test_v93_phrase_banned_in_overall(phrase: str) -> None:
    """非 whitelisted 节直接命中 → 至少 1 个 hit。"""
    text = f"前缀文字……{phrase}……后缀文字"
    hits = scan_tone(text, node="overall")
    assert hits, f"v9.3 禁词 {phrase!r} 在 'overall' 节没有被 scan_tone 命中"


@pytest.mark.parametrize("phrase", _V93_BANNED)
@pytest.mark.parametrize("node", [
    "virtue_narrative.love_letter",
    "virtue_narrative.free_speech",
])
def test_v93_phrase_banned_in_whitelisted_nodes(phrase: str, node: str) -> None:
    """v9.3 新增禁词不进 whitelisted 豁免——love_letter / free_speech 也禁。"""
    text = f"我想对你说……{phrase}……"
    hits = scan_tone(text, node=node)
    assert hits, (
        f"v9.3 禁词 {phrase!r} 在豁免节 {node!r} 仍必须被命中"
        f"（plan: 不进 whitelisted_nodes 豁免列表）"
    )


@pytest.mark.parametrize("phrase", _V93_BANNED)
def test_v93_enforce_raises_tone_error(phrase: str) -> None:
    """enforce_tone 命中 → 抛 ToneError(exit 5)。"""
    text = f"测试……{phrase}……"
    with pytest.raises(ToneError) as exc:
        enforce_tone(text, node="overall")
    assert exc.value.code == 5


def test_legitimate_text_passes() -> None:
    """合法文本（未命中任何 v9.3 / v9 禁词）应通过。"""
    text = (
        "## 我想和你说\n\n"
        "走到这里，我想说，你的一生不只是数字，更是一段段被你自己走过来的路。\n"
    )
    # 非 closing 节直接 scan_tone
    hits = scan_tone(text, node="overall")
    # 注意：「走到这里」作为内文过渡词未被禁；只有作为 closing H2 时被 _v9_guard 拦截
    assert not hits, f"合法文本被误命中：{[(h.rule, h.snippet) for h in hits]}"


def test_node_key_in_schema_not_affected() -> None:
    """node key 字符串本身（出现在 path / log）不应被禁——只 user-facing 文案禁。

    通过验证 scan_tone 只看 text 内容，不看 node 名本身。
    """
    text = "本节正文是一段普通叙事，无任何禁词。"
    # node 名包含 "love_letter" / "declaration" / "free_speech" 不影响 scan
    hits = scan_tone(text, node="virtue_narrative.love_letter")
    assert not hits


@pytest.mark.parametrize(
    "phrase",
    ["承认人性 · 陀式贯穿", "承认人性·陀式贯穿"],
)
def test_compound_phrase_banned(phrase: str) -> None:
    """复合短语 也必命中（至少其组成禁词被命中）。"""
    text = f"……{phrase}……"
    hits = scan_tone(text, node="overall")
    assert hits, f"复合禁词 {phrase!r} 必须被命中"
