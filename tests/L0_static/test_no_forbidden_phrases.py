"""L0 · 守 AGENTS.md §4.3 「现代化解读铁律」。

扫描所有【会被用户看到】的文案文件,拒绝出现 forbidden_phrases.yaml
里列出的物化伴侣 / 性别预设 / 价值判断短语。

不扫:
- references/*.md          (协议文档,允许讨论"为什么禁")
- scripts/*.py             (源码,注释里允许讨论)
- AGENTS.md / SKILL.md     (规则定义本身)
- tests/                   (本测试自己引用了这些词)

扫:
- templates/**/*.j2        (Jinja2 模板,直接渲染)
- examples/*.md            (示例解读文本)
- examples/*.analysis.json (LLM analysis 输出文本字段)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.fast, pytest.mark.static, pytest.mark.fairness]


def _load_forbidden(fixtures_path: Path) -> tuple[list[str], list[str]]:
    data = yaml.safe_load((fixtures_path / "forbidden_phrases.yaml").read_text(encoding="utf-8"))
    return data["forbidden_phrases"], data["forbidden_value_judgments"]


def _scan_text(text: str, phrases: list[str]) -> list[str]:
    return [p for p in phrases if p in text]


def _collect_user_facing_files(root_path: Path) -> list[Path]:
    files: list[Path] = []
    files.extend((root_path / "templates").rglob("*.j2"))
    files.extend((root_path / "examples").glob("*.md"))
    files.extend((root_path / "examples").glob("*.analysis.json"))
    return sorted(files)


def _extract_user_text_from_analysis_json(path: Path) -> str:
    """从 analysis.json 里抽出所有面向用户的字符串值,合并成一段文本。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""
    chunks: list[str] = []

    def walk(node):
        if isinstance(node, str):
            chunks.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return "\n".join(chunks)


@pytest.mark.parametrize(
    "user_file",
    _collect_user_facing_files(Path(__file__).resolve().parent.parent.parent),
    ids=lambda p: p.name,
)
def test_no_forbidden_phrases_in_user_facing_files(
    user_file: Path, fixtures_path: Path
):
    forbidden_phrases, forbidden_judgments = _load_forbidden(fixtures_path)
    if user_file.suffix == ".json":
        text = _extract_user_text_from_analysis_json(user_file)
    else:
        text = user_file.read_text(encoding="utf-8")

    phrase_hits = _scan_text(text, forbidden_phrases)
    judgment_hits = _scan_text(text, forbidden_judgments)

    assert not phrase_hits, (
        f"\n\n  用户可见文案 {user_file.name} 出现 fairness 红线词: {phrase_hits}\n"
        f"  违反 AGENTS.md §4.3 现代化解读铁律。\n"
        f"  如需保留用于'反例讨论',请把文件路径改到 references/ 或加注释说明。\n"
    )
    assert not judgment_hits, (
        f"\n\n  用户可见文案 {user_file.name} 出现价值判断短语: {judgment_hits}\n"
        f"  违反'命局只反映结构,不下价值结论'的承诺。\n"
    )
