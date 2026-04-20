"""L7 · 性别对称性铁律(AGENTS.md §4.3 / fairness_protocol §9-§10)。

同八字 M ↔ F:
- baseline.spirit / wealth / fame               → 必须 byte-equal(原局静态部分)
- yongshen.yongshen                             → 必须相等(用神选取与性别无关)
- 起运前 spirit/wealth/fame 三维(age < qiyun_age) → 必须 byte-equal
  (此时只有原局影响,大运未到)
- 起运后允许差异                               → 大运方向依赖性别(阳男阴女顺、阴男阳女逆)
                                                  这是命理学结构事实,不是公平性问题
- emotion_yearly                                → 允许任何差异(配偶星识别按 orientation/gender)

注:本测试与 scripts/calibrate.py --symmetry 对齐,
但额外覆盖了"起运前 yearly 也必须对称"。
"""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.fairness]


@pytest.fixture(scope="module")
def m_vs_f_curves(canonical_pillars):
    """对每个 canonical 八字,生成 M / F 两个版本的 curves。"""
    from solve_bazi import solve
    from score_curves import score

    out = []
    for sample in canonical_pillars:
        bazi_m = solve(sample["pillars"], None, "M", sample["birth_year"], n_years=80)
        bazi_f = solve(sample["pillars"], None, "F", sample["birth_year"], n_years=80)
        cur_m = score(bazi_m, age_end=80, forecast_window=0)
        cur_f = score(bazi_f, age_end=80, forecast_window=0)
        out.append((sample["id"], cur_m, cur_f))
    return out


def test_baseline_three_dims_equal(m_vs_f_curves):
    for sid, m, f in m_vs_f_curves:
        for dim in ("spirit", "wealth", "fame"):
            assert m["baseline"][dim] == f["baseline"][dim], (
                f"\n  {sid}: baseline.{dim} 在 M/F 之间不等 "
                f"(M={m['baseline'][dim]}, F={f['baseline'][dim]})\n"
                f"  违反 fairness_protocol §9 \"同八字 spirit/wealth/fame 三维必须 byte-equal\"\n"
            )


def test_yongshen_equal(m_vs_f_curves):
    for sid, m, f in m_vs_f_curves:
        assert m["yongshen"]["yongshen"] == f["yongshen"]["yongshen"], (
            f"  {sid}: yongshen 在 M/F 之间不等 — 用神选取不应依赖性别"
        )


def test_pre_qiyun_yearly_byte_equal(m_vs_f_curves):
    """起运前(age < qiyun_age)三维 byte-equal。

    起运前没有大运影响,只有原局,所以 M/F 必须完全相同。
    这是性别对称性最严格的测试 — 任何差异 = 原局打分意外依赖了性别字段。
    """
    for sid, m, f in m_vs_f_curves:
        qy_m = m.get("qiyun_age") or 8
        qy_f = f.get("qiyun_age") or 8
        cutoff = min(qy_m, qy_f)
        if cutoff <= 0:
            continue
        m_pts = {p["age"]: p for p in m["points"] if p["age"] < cutoff}
        f_pts = {p["age"]: p for p in f["points"] if p["age"] < cutoff}
        common = sorted(set(m_pts) & set(f_pts))
        if not common:
            continue

        diffs = []
        for age in common:
            for dim in ("spirit_yearly", "wealth_yearly", "fame_yearly"):
                if m_pts[age][dim] != f_pts[age][dim]:
                    diffs.append((age, dim, m_pts[age][dim], f_pts[age][dim]))
        assert not diffs, (
            f"\n  {sid}: 起运前(age < {cutoff})三维出现 M/F 差异(前 5 条):\n"
            + "\n".join(
                f"    age={a} {d}: M={mv} F={fv}" for a, d, mv, fv in diffs[:5]
            )
            + "\n  起运前不存在大运影响,这种差异说明原局打分意外依赖了 gender 字段。\n"
            + "  违反 fairness_protocol §9。\n"
        )


def test_post_qiyun_diff_only_from_dayun_direction(m_vs_f_curves):
    """起运后允许差异,但差异来源必须可追溯到大运起运方向(阳男阴女顺/阴男阳女逆)。

    具体表现:M/F 的 dayun_segments 应该是"完全不同的天干地支序列"
    (而不是同序列但分数计算不同 — 后者就是 bug)。
    """
    for sid, m, f in m_vs_f_curves:
        m_dyseq = [seg["label"] for seg in m["dayun_segments"]]
        f_dyseq = [seg["label"] for seg in f["dayun_segments"]]
        if m_dyseq == f_dyseq:
            pytest.fail(
                f"  {sid}: M 与 F 的大运序列竟然完全一致 ({m_dyseq[:3]}...) — "
                f"违反阳男阴女顺/阴男阳女逆规则,solve_bazi.get_dayun_sequence 有 bug。"
            )


def test_emotion_may_differ_but_must_be_finite(m_vs_f_curves):
    """emotion 允许不同,但两个性别都必须落在合法区间且不全为 0。"""
    for sid, m, f in m_vs_f_curves:
        m_emo = [p.get("emotion_yearly", 50) for p in m["points"]]
        f_emo = [p.get("emotion_yearly", 50) for p in f["points"]]
        for label, vals in (("M", m_emo), ("F", f_emo)):
            assert all(0 <= v <= 100 for v in vals), (
                f"  {sid} {label}: emotion 越界"
            )
            assert any(v > 0 for v in vals), (
                f"  {sid} {label}: emotion 全部为 0 — 大概率某分支没覆盖"
            )
