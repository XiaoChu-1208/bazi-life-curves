"""L7 · 身份字段 deny-list(AGENTS.md §4.5)。

solve_bazi.validate_blind_input 必须拒绝带身份标签的输入。
任何放宽这个过滤器的 PR 都会被这个测试拦下。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.fast, pytest.mark.fairness]


def _load_samples(fixtures_path: Path) -> list[dict]:
    return yaml.safe_load(
        (fixtures_path / "red_line_inputs.yaml").read_text(encoding="utf-8")
    )["samples"]


@pytest.mark.parametrize(
    "sample",
    _load_samples(Path(__file__).resolve().parent.parent / "_fixtures"),
    ids=lambda s: f"{s['key']}({'reject' if s['must_reject'] else 'allow'})",
)
def test_blind_input_validator_enforces_deny_list(sample, request):
    from _bazi_core import validate_blind_input, IdentityLeakError

    if "known_gap" in sample:
        request.applymarker(pytest.mark.xfail(
            reason=f"已知 gap: {sample['known_gap']}",
            strict=True,  # 一旦修复 → xfail 变 XPASS → CI 红 → 提醒移除标记
        ))

    payload = {sample["key"]: "anything"}
    if sample["must_reject"]:
        with pytest.raises(IdentityLeakError):
            validate_blind_input(payload)
    else:
        validate_blind_input(payload)
