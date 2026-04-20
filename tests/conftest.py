"""Harness 全局 fixture / 路径解析。

把 scripts/ 加到 sys.path,让测试能直接 `from solve_bazi import solve` 等,
和 scripts/calibrate.py 一致的方式。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
EXAMPLES = ROOT / "examples"
REFERENCES = ROOT / "references"
TEMPLATES = ROOT / "templates"
TESTS = ROOT / "tests"
FIXTURES = TESTS / "_fixtures"

sys.path.insert(0, str(SCRIPTS))

# v9 PR-2: tests 自动允许 pillars 模式 8 岁默认起运,以保持 calibration / e2e 测试稳定
# 真实生产用户走 CLI 时拿不到这个环境变量,会强制要求显式 --qiyun-age
os.environ.setdefault("BAZI_ALLOW_PILLARS_DEFAULT_QIYUN", "1")


@pytest.fixture(scope="session")
def root_path() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def scripts_path() -> Path:
    return SCRIPTS


@pytest.fixture(scope="session")
def examples_path() -> Path:
    return EXAMPLES


@pytest.fixture(scope="session")
def references_path() -> Path:
    return REFERENCES


@pytest.fixture(scope="session")
def templates_path() -> Path:
    return TEMPLATES


@pytest.fixture(scope="session")
def fixtures_path() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def canonical_pillars():
    """一组覆盖不同结构的"金标准"八字,用于 fairness/contract 测试。

    挑选标准:
    - 强 / 弱 / 中和 至少各 1 例
    - 覆盖不同月令季节(春夏秋冬)
    - 覆盖典型格局(官印 / 食伤生财 / 杀印 等)
    - 全部用历史名人或 examples 里已有的八字,避免随机性
    """
    return [
        {
            "id": "guan_yin_xiang_sheng",
            "pillars": "壬戌 癸丑 庚午 丁丑",
            "birth_year": 1982,
            "note": "官印相生格(examples 既有)",
        },
        {
            "id": "shang_guan_sheng_cai",
            "pillars": "甲子 丁卯 丙寅 戊戌",
            "birth_year": 1984,
            "note": "伤官生财格(examples 既有)",
        },
        {
            "id": "jobs_steve",
            "pillars": "乙未 戊寅 甲戌 甲戌",
            "birth_year": 1955,
            "note": "calibration dataset",
        },
        {
            "id": "buffet_warren",
            "pillars": "庚午 甲申 庚辰 庚辰",
            "birth_year": 1930,
            "note": "calibration dataset",
        },
        {
            "id": "einstein",
            "pillars": "己卯 丁卯 庚午 壬午",
            "birth_year": 1879,
            "note": "calibration dataset",
        },
    ]
