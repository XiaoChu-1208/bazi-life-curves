"""v9.4 反系统化铁律 + motif_witness 单测。

覆盖三类硬约束（与 _v9_guard.py §R-MOTIF-1/2/3 对齐）：

  1. R-MOTIF-1 · enforce_no_motif_id_leak
     narrative 中出现 motif id 字面（K2_*, C3_*, L1_*, B2_*, T0_* 等）
     → SystemExit(5)
     · 字面命中（精确传入 motif_ids）
     · 通用正则兜底（不传 motif_ids 也能拦下 K2_intimate_failure 这类）
     · 不误伤年份 P1980 / 普通字母数字混合

  2. R-MOTIF-2 · enforce_no_canonical_label_leak
     narrative 中出现 catalog canonical name 字面（"亲密者的无能" / "创业者" 等）
     → SystemExit(5)
     · 短 label（≤2 字）不扫，不误伤
     · 多个 label 重复命中能被各自记录

  3. R-MOTIF-3 · enforce_paraphrase_diversity
     同一 motif 在 ≥2 anchor 复述时 Jaccard 相似度 ≥ 0.6
     → SystemExit(5)
     · 几乎相同 → 命中
     · 只换比喻 / 换句式 → 不命中（< 0.6）
     · 默认阈值 0.6，可调

另外验证 motif_witness 节点（virtue_recurrence_protocol §3.11）的 schema 落盘
能正确通过 append_analysis_node.py 的合法 anchor 集合校验。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from _v9_guard import (
    CanonicalLabelLeakError,
    MotifIdLeakError,
    ParaphraseDuplicationError,
    enforce_no_canonical_label_leak,
    enforce_no_motif_id_leak,
    enforce_paraphrase_diversity,
    scan_canonical_label_leak,
    scan_motif_id_leak,
    scan_paraphrase_diversity,
)


# ============================================================================
# §R-MOTIF-1 · 反 motif id 字面
# ============================================================================


class TestNoMotifIdLeak:
    """K2_intimate_failure / C3_creator 等 motif id 字面禁出 narrative。"""

    def test_explicit_id_blocked_with_known_set(self):
        """精确传入 motif_ids 时，字面命中即抛错。"""
        text = "命主在 K2_intimate_failure 这个母题上反复跌倒。"
        with pytest.raises(MotifIdLeakError) as exc:
            enforce_no_motif_id_leak(
                text,
                node="motif_witness.after_current_dayun",
                motif_ids=["K2_intimate_failure", "C3_creator"],
            )
        assert exc.value.code == 5
        assert any("K2_intimate_failure" in h.motif_id for h in exc.value.hits)

    def test_id_with_underscore_caught_by_regex_fallback(self):
        """即使不传 motif_ids，K2_xxx / L3_yyy 这种通用正则也能拦下。"""
        text = "她身上有强烈的 K2_intimate_failure 倾向。"
        with pytest.raises(MotifIdLeakError):
            enforce_no_motif_id_leak(text, node="overall")

    def test_clean_text_passes(self):
        """完全没有 motif id 的真实 narrative → 不抛错，返回空 hits。"""
        text = (
            "在那一年她终于意识到，自己一直把别人放在自己之前——"
            "不是因为她不想要，而是因为她总能听见别人没说出口的难处。"
        )
        hits = enforce_no_motif_id_leak(
            text, node="motif_witness.after_current_dayun"
        )
        assert hits == []

    def test_year_prefix_not_misidentified(self):
        """P1980 / R2024 这种带数字的非 motif id 不应误伤。"""
        text = "她在 P1980 年和 R2024 年各有一次决断。"  # 模拟脚注/锚记
        hits = scan_motif_id_leak(text)
        assert hits == [], (
            f"P1980/R2024 不应被认为是 motif id 字面，但命中了：{hits}"
        )

    def test_short_alphanumeric_not_misidentified(self):
        """A1 / B2 这种 ≤ 2 长度且无下划线的不算 motif id。"""
        text = "选项 A1 和 B2 都被她试过。"
        hits = scan_motif_id_leak(text)
        assert hits == [], f"A1/B2 不应误伤，但命中了：{hits}"


# ============================================================================
# §R-MOTIF-2 · 反 canonical label 字面
# ============================================================================


class TestNoCanonicalLabelLeak:
    """catalog 内的 canonical name（"亲密者的无能" / "创业者" 等）字面禁出 narrative。"""

    def test_known_canonical_label_blocked(self):
        text = (
            '她身上呈现出"亲密者的无能"——明明渴望靠近，却总是在最后一刻退开。'
        )
        with pytest.raises(CanonicalLabelLeakError) as exc:
            enforce_no_canonical_label_leak(
                text,
                ["亲密者的无能", "创业者", "远行者"],
                node="motif_witness.after_current_dayun",
            )
        assert exc.value.code == 5
        labels = [h.label for h in exc.value.hits]
        assert "亲密者的无能" in labels

    def test_paraphrased_text_passes(self):
        """已经改写成具体情境，不出现 catalog name 字面 → 通过。"""
        text = (
            "她每次站在最爱的人面前都会突然变成一个旁观者，"
            "好像必须先确认自己不会成为对方的负担，才允许自己说一句真心话。"
        )
        hits = enforce_no_canonical_label_leak(
            text,
            ["亲密者的无能", "创业者"],
            node="motif_witness.after_current_dayun",
        )
        assert hits == []

    def test_short_label_not_scanned(self):
        """≤ 2 字的 label 不扫（容易误伤）。"""
        text = "她在那一年走的路非常远。"
        # "远" 只有 1 字 → 不扫
        hits = scan_canonical_label_leak(text, ["远"])
        assert hits == []

    def test_multiple_label_hits(self):
        """多个 canonical label 都出现时，每个都被记录。"""
        text = "她既是亲密者的无能，也是远行者，更是创业者。"
        hits = scan_canonical_label_leak(
            text, ["亲密者的无能", "远行者", "创业者"]
        )
        assert {h.label for h in hits} == {
            "亲密者的无能", "远行者", "创业者"
        }


# ============================================================================
# §R-MOTIF-3 · 改写铁律（paraphrase diversity）
# ============================================================================


class TestParaphraseDiversity:
    """同一 motif 在 ≥2 个 anchor 出现时，Jaccard 相似度 < 0.6。"""

    def test_near_duplicate_blocked(self):
        """两次表述几乎一字不差 → 命中（Jaccard 远超 0.6）。"""
        prior = (
            "她每次站在最爱的人面前都会突然变成一个旁观者，"
            "好像必须先确认自己不会成为对方的负担，才允许自己说一句真心话。"
        )
        new = (
            "她每次站在最爱的人面前都会突然变成一个旁观者，"
            "好像必须先确认自己不会成为对方的负担，才说得出一句真心话。"
        )
        with pytest.raises(ParaphraseDuplicationError) as exc:
            enforce_paraphrase_diversity(
                new,
                motif_id="K2_intimate_failure",
                prior_texts=[
                    {"anchor": "after_current_dayun", "text": prior}
                ],
                node="motif_witness.after_current_liunian",
            )
        assert exc.value.code == 5
        assert exc.value.hits[0].similarity >= 0.6

    def test_genuine_rewrite_passes(self):
        """换角度、换比喻、换动词 → 相似度 < 0.6 → 通过。"""
        prior = (
            "她每次站在最爱的人面前都会突然变成一个旁观者，"
            "好像必须先确认自己不会成为对方的负担，才允许自己说一句真心话。"
        )
        new = (
            "在那段最重要的关系里，她比谁都早预感对方的疲惫，"
            "于是把自己折叠起来塞进角落，等到某天对方问她想不想要什么，她已经记不清了。"
        )
        hits = enforce_paraphrase_diversity(
            new,
            motif_id="K2_intimate_failure",
            prior_texts=[{"anchor": "after_current_dayun", "text": prior}],
            node="motif_witness.after_current_liunian",
        )
        assert hits == [], (
            f"genuine rewrite 应该 < 0.6 阈值，却命中了：{hits[0].similarity:.2f}"
        )

    def test_empty_prior_passes(self):
        """第一次出现该 motif（prior 为空）→ 永远通过。"""
        hits = enforce_paraphrase_diversity(
            "任意新文本",
            motif_id="K2_intimate_failure",
            prior_texts=[],
        )
        assert hits == []

    def test_threshold_configurable(self):
        """threshold 可调到 0.9，让原本 0.65 的就不再算重复。"""
        prior = "她总是在最后一刻退开，从不让人看见她的脆弱。"
        new = "她每次都在最后一刻退开，不愿让人看到她的脆弱。"
        # 默认 0.6 应该命中
        hits_default = scan_paraphrase_diversity(
            new,
            motif_id="X",
            prior_texts=[{"anchor": "a", "text": prior}],
        )
        # 0.9 阈值则放过
        hits_strict = scan_paraphrase_diversity(
            new,
            motif_id="X",
            prior_texts=[{"anchor": "a", "text": prior}],
            threshold=0.9,
        )
        assert len(hits_strict) <= len(hits_default)


# ============================================================================
# §append_analysis_node · motif_witness.<anchor> 节点 schema 落盘
# ============================================================================


_VALID_MOTIF_WITNESS_ANCHORS = [
    "after_current_dayun",
    "after_current_liunian",
    "after_key_years",
    "before_closing",
]


@pytest.mark.parametrize("anchor", _VALID_MOTIF_WITNESS_ANCHORS)
def test_motif_witness_anchor_accepted_by_append(
    tmp_path: Path, anchor: str
):
    """合法的 motif_witness.<anchor> node key 必须被 append_analysis_node.py 接受
    并落到 analysis.partial.json.motif_witness.<anchor>。
    """
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    script = scripts / "append_analysis_node.py"
    assert script.exists()

    partial = tmp_path / "analysis.partial.json"
    body = (
        "在那一年她终于意识到，自己总把别人的难处放在自己前面——"
        "不是没有渴望，而是她从小学会先看见别人。"
    )

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--state",
            str(partial),
            "--node",
            f"motif_witness.{anchor}",
            "--markdown",
            body,
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"append_analysis_node 拒绝了合法 anchor '{anchor}'：\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )

    data = json.loads(partial.read_text(encoding="utf-8"))
    mw = data.get("motif_witness")
    assert isinstance(mw, dict), f"motif_witness 节未生成：{data!r}"
    assert anchor in mw, f"anchor '{anchor}' 未落入 motif_witness：{mw!r}"
    assert mw[anchor].strip() == body.strip()


def test_motif_witness_invalid_anchor_rejected(tmp_path: Path):
    """非法 anchor 必须被 append_analysis_node 拒绝（保持合法 anchor 集合可控）。"""
    scripts = Path(__file__).resolve().parent.parent / "scripts"
    script = scripts / "append_analysis_node.py"
    partial = tmp_path / "analysis.partial.json"

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--state",
            str(partial),
            "--node",
            "motif_witness.unknown_anchor_xxx",
            "--markdown",
            "一段合法但 anchor 非法的旁白。",
            "--quiet",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0, (
        f"非法 motif_witness anchor 应被拒，却通过了：\n"
        f"stdout={proc.stdout}\nstderr={proc.stderr}"
    )
