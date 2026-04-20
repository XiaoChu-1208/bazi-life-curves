#!/usr/bin/env python3
"""_mangpai_reversal.py — v9 mangpai 反转规则引擎

加载 references/mangpai_reversal_rules.yaml, 对给定 event_key + phase_context
返回是否反转 + 反转后的 meaning / intensity / polarity。

设计：
  - 纯内置 yaml（没装 pyyaml 时 fallback 到 manual parse，见 _minimal_yaml）
  - 纯函数 + lru_cache（线程安全，无副作用）
  - 禁止 exec / eval，DSL 只支持 `==` / `!=` / `in` / `not_in`

详见 references/phase_architecture_v9_design.md §4.5
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_REPO_ROOT = Path(__file__).resolve().parent.parent
_RULES_PATH = _REPO_ROOT / "references" / "mangpai_reversal_rules.yaml"


@dataclass(frozen=True)
class ReversalResult:
    triggered: bool
    reversed_meaning: Optional[str] = None
    intensity_after: Optional[str] = None
    polarity_after: Optional[str] = None  # 'positive' / 'neutral' / 'negative'
    source: Optional[str] = None
    rule_index: Optional[int] = None


_NO_REVERSAL = ReversalResult(triggered=False)


# ============================================================================
# YAML 最小解析（避免强制依赖 pyyaml）
# ============================================================================

def _load_yaml(path: Path) -> Dict:
    try:
        import yaml  # type: ignore
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        pass
    # fallback: manual parse（支持本文件实际用到的语法子集）
    return _minimal_yaml(path.read_text(encoding="utf-8"))


def _minimal_yaml(text: str) -> Dict:
    """迷你 YAML 解析器，仅支持本规则文件用到的语法：
       key: value
       key:
         - list_item
       key: [a, b, c]
       多行 | 折叠字符串

       限制：不支持复杂嵌套 / 引用 / 锚点。足够应付 reversal_rules.yaml。
    """
    import re
    lines = text.split("\n")

    def strip_comment(s: str) -> str:
        # 行内 # 注释（仅在非字符串值中）
        m = re.search(r"\s+#", s)
        if m and "'" not in s[:m.start()] and '"' not in s[:m.start()]:
            return s[:m.start()]
        return s

    i = 0
    n = len(lines)
    root: Dict = {}

    def parse_scalar(v: str) -> Any:
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1]
            if not inner.strip():
                return []
            return [parse_scalar(x) for x in inner.split(",")]
        if v == "true": return True
        if v == "false": return False
        if v == "null" or v == "": return None
        try:
            if "." in v: return float(v)
            return int(v)
        except ValueError:
            return v.strip("'\"")

    def indent_of(s: str) -> int:
        return len(s) - len(s.lstrip(" "))

    def parse_block(start_idx: int, min_indent: int) -> Tuple[Any, int]:
        """返回 (value, next_idx)。"""
        nonlocal n
        idx = start_idx
        # 跳过空行和注释
        while idx < n:
            raw = lines[idx]
            s = strip_comment(raw).rstrip()
            if not s.strip() or s.lstrip().startswith("#"):
                idx += 1
                continue
            break
        if idx >= n:
            return None, idx
        first = strip_comment(lines[idx]).rstrip()
        cur_indent = indent_of(first)
        if cur_indent < min_indent:
            return None, idx
        # list?
        if first.lstrip().startswith("- "):
            out_list = []
            while idx < n:
                raw = lines[idx]
                s = strip_comment(raw).rstrip()
                if not s.strip() or s.lstrip().startswith("#"):
                    idx += 1
                    continue
                if indent_of(s) < cur_indent:
                    break
                if indent_of(s) != cur_indent:
                    break
                if not s.lstrip().startswith("- "):
                    break
                item_first = s.lstrip()[2:]  # 去掉 "- "
                # 同行 item: "- key: value" 或 "- value"
                if ":" in item_first and not item_first.strip().startswith("|"):
                    # 一个 dict item，首行 key 就在 "- " 后面
                    k, _, v = item_first.partition(":")
                    item: Dict = {}
                    if v.strip():
                        item[k.strip()] = _parse_value(v.strip(), idx, cur_indent + 2)[0]
                    else:
                        # 多行 dict
                        val, idx = parse_block(idx + 1, cur_indent + 2)
                        if isinstance(val, dict) and val is not None:
                            item.update(val)
                            out_list.append(item)
                            continue
                    idx += 1
                    # 读取后续 key
                    while idx < n:
                        raw2 = lines[idx]
                        s2 = strip_comment(raw2).rstrip()
                        if not s2.strip() or s2.lstrip().startswith("#"):
                            idx += 1
                            continue
                        ind2 = indent_of(s2)
                        if ind2 <= cur_indent:
                            break
                        # 这一行是 item 的子 key
                        k2, sep, v2 = s2.strip().partition(":")
                        if sep != ":":
                            idx += 1
                            continue
                        val2, idx = _parse_value(v2.strip(), idx, ind2)
                        item[k2.strip()] = val2
                    out_list.append(item)
                else:
                    out_list.append(parse_scalar(item_first))
                    idx += 1
            return out_list, idx
        # dict
        out_dict: Dict = {}
        while idx < n:
            raw = lines[idx]
            s = strip_comment(raw).rstrip()
            if not s.strip() or s.lstrip().startswith("#"):
                idx += 1
                continue
            ind = indent_of(s)
            if ind < cur_indent:
                break
            if ind != cur_indent:
                break
            if ":" not in s:
                break
            k, _, v = s.partition(":")
            k = k.strip()
            v = v.strip()
            val, idx = _parse_value(v, idx, cur_indent + 2)
            out_dict[k] = val
        return out_dict, idx

    def _parse_value(v: str, cur_line_idx: int, child_indent: int) -> Tuple[Any, int]:
        """返回 (解析后的 value, new_idx)。v 是冒号后的值字符串，cur_line_idx 是当前行。"""
        if v == "|":
            # 多行 literal 字符串
            result_lines = []
            idx2 = cur_line_idx + 1
            while idx2 < n:
                raw = lines[idx2]
                if not raw.strip():
                    result_lines.append("")
                    idx2 += 1
                    continue
                if indent_of(raw) < child_indent:
                    break
                result_lines.append(raw[child_indent:] if len(raw) >= child_indent else raw.lstrip())
                idx2 += 1
            return "\n".join(result_lines).rstrip() + "\n", idx2
        if v == "":
            # 下一行是 block
            val, new_idx = parse_block(cur_line_idx + 1, child_indent)
            return val, new_idx
        # 行内 scalar
        return parse_scalar(v), cur_line_idx + 1

    val, _ = parse_block(0, 0)
    return val if isinstance(val, dict) else {}


# ============================================================================
# 规则加载（lru_cache）
# ============================================================================

@lru_cache(maxsize=1)
def _load_rules() -> List[Dict]:
    if not _RULES_PATH.exists():
        return []
    data = _load_yaml(_RULES_PATH)
    return data.get("rules", []) or []


# ============================================================================
# DSL 求值
# ============================================================================

def _get_path(context: Dict, path: str) -> Any:
    """按点分路径取值。不存在返回 None。"""
    cur: Any = context
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur


def _eval_cond(cond: Dict, context: Dict) -> bool:
    path = cond.get("path")
    op = cond.get("op")
    value = cond.get("value")
    if path is None or op is None:
        return False
    actual = _get_path(context, path)
    if op == "==":
        return actual == value
    if op == "!=":
        return actual != value
    if op == "in":
        return actual in (value or [])
    if op == "not_in":
        return actual not in (value or [])
    return False


def _match(rule: Dict, context: Dict) -> bool:
    conds = rule.get("reverse_when", [])
    if not conds:
        return False
    return all(_eval_cond(c, context) for c in conds)


# ============================================================================
# 对外 API
# ============================================================================

def evaluate_reversal(event_key: str, phase_context: Dict) -> ReversalResult:
    """对 (event_key, phase_context) 返回 ReversalResult。

    phase_context 应包含：
      - phase: Dict {id, dimension, reversal_overrides: {event_key: polarity}}
      - strength: Dict {label}
      - has_yin_hu_shen: bool (optional)

    命中优先级：按 yaml 中 rules 顺序，首个命中即返回。
    """
    rules = _load_rules()
    for i, r in enumerate(rules):
        if r.get("event_key") != event_key:
            continue
        if _match(r, phase_context):
            return ReversalResult(
                triggered=True,
                reversed_meaning=r.get("reversed_meaning"),
                intensity_after=r.get("intensity_after"),
                polarity_after=_derive_polarity_after(
                    r.get("default_polarity", "negative"),
                    phase_context.get("phase", {}).get("reversal_overrides", {}).get(event_key),
                ),
                source=r.get("source"),
                rule_index=i,
            )
    return _NO_REVERSAL


def _derive_polarity_after(default: str, override: Optional[str]) -> str:
    if override in ("positive", "neutral", "negative"):
        return override
    # 默认反转 = 翻符号
    return {"negative": "positive", "positive": "negative"}.get(default, "neutral")


def build_phase_context(bazi: Dict) -> Dict:
    """从 bazi dict 构造 phase_context（给 evaluate_reversal 用）。"""
    phase = bazi.get("phase") or {}
    phase_id = phase.get("id", "day_master_dominant")
    strength = bazi.get("strength", {}) or {}

    reversal_overrides: Dict[str, str] = {}
    dimension = "power"
    try:
        from _phase_registry import get, exists  # type: ignore
        if exists(phase_id):
            meta = get(phase_id)
            dimension = meta.dimension
            reversal_overrides = dict(meta.reversal_overrides)
    except Exception:
        pass

    # 外部直接 override（支持 confirmed_facts 写入）
    ext_override = bazi.get("phase", {}).get("reversal_overrides") or {}
    if isinstance(ext_override, dict):
        reversal_overrides.update(ext_override)

    return {
        "phase": {
            "id": phase_id,
            "dimension": dimension,
            "reversal_overrides": reversal_overrides,
        },
        "strength": {
            "label": strength.get("label", ""),
            "total_root": strength.get("total_root", 0.0),
        },
        "has_yin_hu_shen": _has_yin_protection(bazi),
    }


def _has_yin_protection(bazi: Dict) -> bool:
    """简化判断：命局是否有印星护身。基于 pillars 与 day_gan 五行推。"""
    try:
        from _bazi_core import GAN_WUXING, WUXING_SHENG  # type: ignore
    except Exception:
        return False
    pillars = bazi.get("pillars", [])
    if not pillars:
        return False
    day_gan = pillars[2].get("gan")
    if not day_gan or day_gan not in GAN_WUXING:
        return False
    day_wx = GAN_WUXING[day_gan]
    yin_wx = {k for k, v in WUXING_SHENG.items() if v == day_wx}
    for p in pillars:
        g = p.get("gan", "")
        if g in GAN_WUXING and GAN_WUXING[g] in yin_wx:
            return True
    return False


if __name__ == "__main__":
    # smoke test
    import sys, json
    rules = _load_rules()
    print(f"Loaded {len(rules)} reversal rules from {_RULES_PATH}")
    for i, r in enumerate(rules):
        print(f"  [{i}] event_key={r['event_key']:20s} conds={len(r.get('reverse_when', []))} source={r.get('source','')[:40]}")

    # 测试 1: yangren_chong_cai phase + yangren_chong 事件 → 应反转
    ctx = {
        "phase": {"id": "yangren_chong_cai", "dimension": "zuogong",
                  "reversal_overrides": {"yangren_chong": "positive",
                                          "bi_jie_duo_cai": "neutral"}},
        "strength": {"label": "强"},
    }
    res = evaluate_reversal("yangren_chong", ctx)
    print(f"\n[test1] yangren_chong 在 yangren_chong_cai phase 下反转: {res.triggered}")
    if res.triggered:
        print(f"  polarity_after={res.polarity_after}")
        print(f"  meaning={res.reversed_meaning[:80]}...")
        print(f"  source={res.source}")

    # 测试 2: day_master_dominant phase + yangren_chong 事件 → 不反转
    ctx2 = {"phase": {"id": "day_master_dominant", "dimension": "power",
                      "reversal_overrides": {}},
            "strength": {"label": "中和"}}
    res2 = evaluate_reversal("yangren_chong", ctx2)
    print(f"\n[test2] yangren_chong 在 day_master_dominant phase 下反转: {res2.triggered}")
