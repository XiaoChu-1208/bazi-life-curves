#!/usr/bin/env python3
"""_zeitgeist_loader.py — 加载 era_windows_skeleton.yaml + 与命主大运对齐

用法：
    from _zeitgeist_loader import load_era_windows, align_with_dayun
    
    eras = load_era_windows("references/era_windows_skeleton.yaml")
    alignments = align_with_dayun(bazi["dayun"], eras["china_main"])
    # alignments: list of {dayun, era_window, overlap_situation, overlap_years}

或 CLI：
    python scripts/_zeitgeist_loader.py --bazi out/bazi.json --out out/zeitgeist.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any


REFS_DIR = Path(__file__).resolve().parent.parent / "references"
DEFAULT_YAML_PATH = REFS_DIR / "era_windows_skeleton.yaml"


def _yaml_load(path: Path) -> dict:
    """轻量 YAML 加载（避免引入 PyYAML 依赖；只支持本项目 era_windows_skeleton 的子集）。
    
    如果系统装了 PyYAML 就用，否则退回简易解析。
    """
    try:
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except ImportError:
        return _simple_yaml_load(path.read_text(encoding="utf-8"))


def _simple_yaml_load(text: str) -> dict:
    """简易 YAML 解析（仅适用于 era_windows_skeleton.yaml 的固定结构）。
    
    支持：
      - 顶层 key: value
      - 顶层 key: 后面跟列表（- 开头）
      - 列表元素是 dict（缩进 4 空格）
      - 多行 string（| 开头）
      - 简单的 [a, b, c] 内联列表
    """
    result: Dict[str, Any] = {}
    current_key: Optional[str] = None
    current_list: Optional[list] = None
    current_dict: Optional[dict] = None
    multiline_buffer: Optional[List[str]] = None
    multiline_target_key: Optional[str] = None
    multiline_indent = 0
    
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if multiline_buffer is not None:
            if line and not line[0].isspace() and stripped and not stripped.startswith("#"):
                if current_dict is not None:
                    current_dict[multiline_target_key] = "\n".join(multiline_buffer).rstrip()
                else:
                    result[multiline_target_key] = "\n".join(multiline_buffer).rstrip()
                multiline_buffer = None
                multiline_target_key = None
            else:
                if not stripped:
                    multiline_buffer.append("")
                else:
                    multiline_buffer.append(line[multiline_indent:] if len(line) >= multiline_indent else line.lstrip())
                i += 1
                continue
        
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        
        indent = len(line) - len(line.lstrip())
        
        if indent == 0 and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "" or val == "|":
                if val == "|":
                    multiline_buffer = []
                    multiline_target_key = key
                    multiline_indent = 2
                    current_key = key
                    current_list = None
                    current_dict = None
                else:
                    next_line_idx = i + 1
                    while next_line_idx < len(lines) and not lines[next_line_idx].strip():
                        next_line_idx += 1
                    if next_line_idx < len(lines) and lines[next_line_idx].strip().startswith("-"):
                        result[key] = []
                        current_list = result[key]
                        current_key = key
                        current_dict = None
                    else:
                        result[key] = None
                        current_key = key
            else:
                result[key] = _parse_scalar(val)
                current_key = None
                current_list = None
                current_dict = None
        
        elif stripped.startswith("- ") and current_list is not None:
            item_content = stripped[2:].strip()
            if ":" in item_content:
                k, _, v = item_content.partition(":")
                new_dict = {k.strip(): _parse_scalar(v.strip())}
                current_list.append(new_dict)
                current_dict = new_dict
            else:
                current_list.append(_parse_scalar(item_content))
        
        elif current_dict is not None and ":" in stripped:
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip()
            if v == "|":
                multiline_buffer = []
                multiline_target_key = k
                multiline_indent = indent + 2
            else:
                current_dict[k] = _parse_scalar(v)
        
        i += 1
    
    if multiline_buffer is not None:
        if current_dict is not None:
            current_dict[multiline_target_key] = "\n".join(multiline_buffer).rstrip()
        else:
            result[multiline_target_key] = "\n".join(multiline_buffer).rstrip()
    
    return result


def _parse_scalar(s: str):
    """简易标量解析。"""
    s = s.strip()
    if not s:
        return None
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(p.strip()) for p in inner.split(",")]
    if s.lower() in ("null", "~"):
        return None
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s


def load_era_windows(path: Optional[str] = None) -> dict:
    """加载 era_windows_skeleton.yaml。

    Returns:
        含 china_main / global_main / china_pre_1977 / alignment_hint / usage_hint 字段
    """
    p = Path(path) if path else DEFAULT_YAML_PATH
    if not p.exists():
        raise FileNotFoundError(f"era_windows_skeleton not found: {p}")
    return _yaml_load(p)


def _overlap_years(span_a: List[int], span_b: List[int]) -> int:
    """计算两个 [start, end] 区间的重合年数。"""
    a1, a2 = span_a
    b1, b2 = span_b
    return max(0, min(a2, b2) - max(a1, b1) + 1)


def _classify_overlap(dayun_span: List[int], era_span: List[int]) -> Tuple[str, float]:
    """分类大运 × era 的对齐情况。
    
    Returns:
        (situation, ratio): 
          situation ∈ {"A_resonance", "B_dayun_spans_eras", "C_era_spans_dayuns", "no_overlap"}
          ratio: 重合占大运比例
    """
    overlap = _overlap_years(dayun_span, era_span)
    if overlap == 0:
        return ("no_overlap", 0.0)
    
    dayun_len = dayun_span[1] - dayun_span[0] + 1
    era_len = era_span[1] - era_span[0] + 1
    overlap_ratio_dayun = overlap / dayun_len
    overlap_ratio_era = overlap / era_len
    
    if overlap_ratio_dayun >= 0.7 and overlap_ratio_era >= 0.5:
        return ("A_resonance", overlap_ratio_dayun)
    if overlap_ratio_dayun >= 0.7 and overlap_ratio_era < 0.5:
        return ("C_era_spans_dayuns", overlap_ratio_dayun)
    return ("B_dayun_spans_eras", overlap_ratio_dayun)


def align_with_dayun(dayun_list: List[dict], 
                     era_windows: List[dict], 
                     birth_year: Optional[int] = None) -> List[dict]:
    """把命主的大运段与 era_windows 对齐。

    Args:
        dayun_list: bazi["dayun"]，每项含 start_age / start_year / end_age / end_year / gan / zhi
        era_windows: era_windows_skeleton 的 china_main 或 global_main
        birth_year: 用于补全 start_year 缺失场景

    Returns:
        list of dict：每个大运 + 它覆盖的 era_windows + 对齐情况
    """
    out = []
    for du in dayun_list:
        if "start_year" not in du or "end_year" not in du:
            continue
        dayun_span = [du["start_year"], du["end_year"]]
        overlapping_eras = []
        for era in era_windows:
            if "span" not in era:
                continue
            situation, ratio = _classify_overlap(dayun_span, era["span"])
            if situation == "no_overlap":
                continue
            overlapping_eras.append({
                "era_id": era.get("id"),
                "era_label": era.get("label"),
                "era_span": era["span"],
                "era_keywords": era.get("keywords", []),
                "overlap_situation": situation,
                "overlap_ratio_to_dayun": round(ratio, 2),
                "overlap_years": _overlap_years(dayun_span, era["span"]),
            })
        out.append({
            "dayun_label": (du.get("gan", "") or "") + (du.get("zhi", "") or ""),
            "dayun_index": du.get("index"),
            "dayun_span_year": dayun_span,
            "dayun_span_age": [du.get("start_age"), du.get("end_age")],
            "covering_eras": overlapping_eras,
            "primary_situation": _summarize_dayun_situation(overlapping_eras),
        })
    return out


def _summarize_dayun_situation(overlapping_eras: List[dict]) -> str:
    """大运的总体对齐情况（A/B/C）。"""
    if not overlapping_eras:
        return "no_match"
    if len(overlapping_eras) == 1:
        return overlapping_eras[0]["overlap_situation"]
    return "B_dayun_spans_eras"


def select_china_or_global(bazi: dict, eras: dict) -> List[dict]:
    """根据命主信息选择优先用的 era_windows 序列。
    
    默认优先 china_main；若 birth_year < 1977 则用 china_pre_1977 + china_main。
    （未来可扩展处理非中国用户。）
    """
    birth_year = bazi.get("birth_year") or 1990
    out = []
    if birth_year < 1977:
        out.extend(eras.get("china_pre_1977", []))
    out.extend(eras.get("china_main", []))
    return out


def build_zeitgeist_context(bazi: dict, 
                             eras: Optional[dict] = None) -> dict:
    """主入口：基于 bazi.json 构造完整的 zeitgeist 上下文（供 LLM 读）。

    Returns:
        {
            "era_windows_used": [...],        # 与命主相关的 era_windows
            "global_eras_used": [...],         # 全球主线（作辅助背景）
            "alignments": [...],               # 大运 × era 对齐
            "user_birth_year": ...,
            "user_qiyun_age": ...,
            "_meta": {...}
        }
    """
    eras = eras or load_era_windows()
    
    primary_eras = select_china_or_global(bazi, eras)
    global_eras = eras.get("global_main", [])
    
    alignments = align_with_dayun(
        bazi.get("dayun", []),
        primary_eras,
        birth_year=bazi.get("birth_year"),
    )
    
    used_era_ids = set()
    for al in alignments:
        for cov in al["covering_eras"]:
            used_era_ids.add(cov["era_id"])
    era_windows_used = [e for e in primary_eras if e.get("id") in used_era_ids]
    
    return {
        "era_windows_used": era_windows_used,
        "global_eras_available": global_eras,
        "alignments": alignments,
        "user_birth_year": bazi.get("birth_year"),
        "user_qiyun_age": bazi.get("qiyun_age"),
        "user_dayun_segments": [
            {
                "label": al["dayun_label"],
                "start_year": al["dayun_span_year"][0],
                "end_year": al["dayun_span_year"][1],
                "start_age": al["dayun_span_age"][0],
                "end_age": al["dayun_span_age"][1],
            }
            for al in alignments
        ],
        "_meta": {
            "total_eras_in_skeleton_china": len(eras.get("china_main", [])),
            "total_eras_used_for_user": len(era_windows_used),
            "skeleton_version": eras.get("version"),
        },
        "_disclaimer": (
            "era_windows 是骨架；具体的 sub_phases / folkways 细节由 LLM 现场推。"
            "详见 references/zeitgeist_protocol.md + references/folkways_protocol.md。"
        ),
    }


def main():
    import argparse
    
    ap = argparse.ArgumentParser(description="加载 era_windows + 与命主大运对齐")
    ap.add_argument("--bazi", required=True, help="bazi.json 路径")
    ap.add_argument("--out", default=None, help="输出路径（默认 stdout）")
    ap.add_argument("--era-skeleton", default=None, help="自定义 era_windows_skeleton.yaml 路径")
    args = ap.parse_args()
    
    bazi = json.loads(Path(args.bazi).read_text(encoding="utf-8"))
    eras = load_era_windows(args.era_skeleton) if args.era_skeleton else load_era_windows()
    ctx = build_zeitgeist_context(bazi, eras)
    
    output = json.dumps(ctx, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"[_zeitgeist_loader] wrote {args.out}")
        print(f"  era_windows_used = {len(ctx['era_windows_used'])} 个")
        print(f"  alignments = {len(ctx['alignments'])} 段大运")
        for al in ctx["alignments"][:3]:
            covered = "/".join(c["era_id"] for c in al["covering_eras"]) or "(none)"
            print(f"    · {al['dayun_label']}({al['dayun_span_year'][0]}-{al['dayun_span_year'][1]}) → {covered} [{al['primary_situation']}]")
    else:
        print(output)


if __name__ == "__main__":
    main()
