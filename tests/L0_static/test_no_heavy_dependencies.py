"""L0 · 守 AGENTS.md 4.6 节"禁止重型依赖"。

requirements.txt 里只允许列表内的包;任何 ML / DL 框架被引入会让
"5 秒跑完 / CPU only"承诺崩塌。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast, pytest.mark.static]


FORBIDDEN_PACKAGES = {
    "torch", "tensorflow", "keras", "jax",
    "transformers", "sentence-transformers",
    "openai", "anthropic", "google-generativeai",
    "litellm", "langchain", "llama-index",
}

REQ_RE = re.compile(r"^([a-zA-Z0-9_.-]+)")


def _parse_requirements(path: Path) -> set[str]:
    pkgs: set[str] = set()
    if not path.exists():
        return pkgs
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = REQ_RE.match(line)
        if m:
            pkgs.add(m.group(1).lower())
    return pkgs


def test_requirements_no_heavy_ml(root_path: Path):
    """生产 requirements.txt 不能引入任何 ML / LLM SDK。"""
    pkgs = _parse_requirements(root_path / "requirements.txt")
    bad = pkgs & FORBIDDEN_PACKAGES
    assert not bad, (
        f"\n\n  requirements.txt 引入了被禁止的重型依赖: {sorted(bad)}\n"
        f"  违反 AGENTS.md §4.6:本工具承诺 CPU 5 秒跑完。\n"
        f"  如属可选集成,请放到 requirements-optional.txt。\n"
    )


def test_requirements_dev_no_heavy_ml(root_path: Path):
    """harness 自身 dev 依赖也不应引入 ML SDK。"""
    pkgs = _parse_requirements(root_path / "requirements-dev.txt")
    bad = pkgs & FORBIDDEN_PACKAGES
    assert not bad, f"requirements-dev.txt 含重型依赖: {sorted(bad)}"
