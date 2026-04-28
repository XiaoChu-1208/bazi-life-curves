"""scripts/_v9_guard.py — v9 统一机械护栏。

集中三类硬约束的执行点，避免分散到各个脚本里靠 LLM 自觉：

  1. enforce_v9_only_path: 阻断 v8 deprecated 入口（handshake R1 / dump-question-set
     batch），除非显式 ack flag；用于 CLI 入口和 MCP server 共用。
  2. enforce_no_phase_leak_in_message: 扫描 LLM 即将写入 analysis 的 markdown，
     拒绝越权命名（"我倾向认为你是 X 格" / "后验 X" / "你的相位是 X" / "EIG" /
     "决策反转" 等）。
  3. enforce_closing_headers: 收尾三节（declaration / love_letter / free_speech）
     统称「我想和你说的话」，必须用 v9.3 三段固定标题：
       - declaration → "## 我想和你说"
       - love_letter → "## 项目的编写者想和你说"
       - free_speech → "## 我（大模型）想和你说"
     拒绝 v9 旧白名单（"## 走到这里" / "## 写到这里我想说" / "## 不在协议里的话"）
     和 "## 承认维度·宣告" / "## 灵魂宣言" / "## 情书" 这类暴露协议结构 / 模板化措辞。

被这些 guard 拦下的调用一律返回非零 exit，让管道 fail-fast 而不是悄悄继续。

注意：本模块**只做检查与抛错**，不做任何 I/O；调用方负责把错误信息打到 stderr 并 exit。
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Iterable, Optional


# ============================================================================
# §1 · v9 唯一入口（问题 1）
# ============================================================================

class V9PathBlocked(SystemExit):
    """v8 deprecated 入口被默认 v9 护栏阻断。退出码 = 2。"""

    def __init__(self, entry_name: str, ack_flag_help: str):
        msg = (
            f"[_v9_guard] {entry_name}: BLOCKED · v9 默认路径已切换。\n"
            f"  · 推荐改用：python scripts/adaptive_elicit.py next ...\n"
            f"  · 若必须沿用旧入口（he_pan/legacy 兜底等），显式加 {ack_flag_help}。\n"
            f"  · 详见 references/handshake_protocol.md §0 + AGENTS.md §二·v9 关键约束。"
        )
        super().__init__(2)
        self.message = msg

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return self.message


def enforce_v9_only_path(
    entry_name: str,
    *,
    ack_flag: bool,
    ack_flag_help: str,
    extra_hint: str = "",
) -> None:
    """v9 默认入口护栏：未显式 ack 则 exit 2 + 写 stderr。

    调用约定：
        from _v9_guard import enforce_v9_only_path
        enforce_v9_only_path(
            "handshake.py R1",
            ack_flag=args.ack_legacy_r1,
            ack_flag_help="--ack-legacy-r1",
        )
    """
    if ack_flag:
        return
    err = V9PathBlocked(entry_name, ack_flag_help)
    print(err.message, file=sys.stderr)
    if extra_hint:
        print(extra_hint, file=sys.stderr)
    raise err


# ============================================================================
# §2 · 越权命名扫描（问题 4）
# ============================================================================

# 内部 reasoning 字段 / phase id / EIG 内部术语 → 用户可见 markdown 里全部禁出现
# 注意：用 raw string 写正则；中文字符串无需转义
_PHASE_LEAK_PATTERNS: tuple[tuple[str, str], ...] = (
    # Bazi phase id / 格局命名（agent overreach）
    (r"我(倾向|认为|判断|觉得)(你|命主)?是?[^\s]{0,4}(从|化|印|官|杀|食|伤|财)格", "phase 命名越权"),
    (r"你的?(相位|phase)是\s*[A-Za-z_]+", "phase id 越权"),
    (r"后验\s*[\d.]+|posterior\s*[\d.]+|EIG[\s=:]*\d+|信息熵|kl_divergence", "elicit 内部术语外泄"),
    (r"决策反转|decision[_-]?changed|escalate", "phase_decision 内部状态外泄"),
    (r"phase_decision|phase_candidates|prior_distribution|likelihood_table",
     "elicit/decision 内部 schema 字段名外泄"),
    (r"从.{0,3}大方向.{0,3}合计.{0,3}过阈|大方向\s*合计", "agent 自创解读（非协议）"),
    (r"\.elicit\.state\.json|\.partial\.json", "内部 state 文件名外泄"),
)


@dataclass(frozen=True)
class PhaseLeakHit:
    pattern: str
    reason: str
    snippet: str


class PhaseLeakError(SystemExit):
    """越权命名 → exit 11。"""

    def __init__(self, hits: list[PhaseLeakHit]):
        super().__init__(11)
        self.hits = hits

    def render(self) -> str:
        lines = ["[_v9_guard] PHASE LEAK · 检测到越权命名（agent overreach）："]
        for h in self.hits:
            lines.append(f"  · {h.reason}：'{h.snippet}'  (pattern: {h.pattern})")
        lines.append("  · 修法：用'结构上的紧绷感' / '某条线' 等中性叙事，禁止把内部 phase id / 后验 / EIG 转述给用户。")
        lines.append("  · 详见 references/elicitation_ethics.md §E1-§E4")
        return "\n".join(lines)


def scan_phase_leak(text: str) -> list[PhaseLeakHit]:
    """扫文本，返回所有命中（不抛错）。"""
    hits: list[PhaseLeakHit] = []
    if not text:
        return hits
    for pattern, reason in _PHASE_LEAK_PATTERNS:
        for m in re.finditer(pattern, text):
            snippet = text[max(0, m.start() - 8): m.end() + 8].replace("\n", " ")
            hits.append(PhaseLeakHit(pattern=pattern, reason=reason, snippet=snippet))
    return hits


def enforce_no_phase_leak_in_message(text: str, *, raise_on_hit: bool = True) -> list[PhaseLeakHit]:
    """扫并抛错。调用方可设 raise_on_hit=False 自行处理。"""
    hits = scan_phase_leak(text)
    if hits and raise_on_hit:
        err = PhaseLeakError(hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


# ============================================================================
# §3 · Closing 标题去模板化（问题 3 · 防"模板化收尾"感）
# ============================================================================

# v9.3：三节统称「我想和你说的话」，每节首行 H2 固定为下表三句。
# 旧 v9 白名单（"## 走到这里" / "## 写到这里我想说" / "## 不在协议里的话"）
# 已退役 → 进入 _CLOSING_HEADER_FORBIDDEN_RE，避免回潮。
_CLOSING_HEADER_WHITELIST: dict[str, tuple[str, ...]] = {
    "declaration": ("## 我想和你说",),
    "love_letter": ("## 项目的编写者想和你说",),
    "free_speech": ("## 我（大模型）想和你说",),
}

# 命中即拒绝（暴露协议结构 / 模板化 / v9 旧白名单回潮）
_CLOSING_HEADER_FORBIDDEN_RE = re.compile(
    r"^##\s*("
    r"承认维度|承认人性|位置\s*[④⑤⑥]|灵魂宣言|项目作者的爱|LLM\s*自由话|"
    r"宣告|情书|自由发言|free[\s_-]*speech|love[\s_-]*letter|declaration|"
    r"走到这里|写到这里我想说|不在协议里的话"  # v9 旧白名单已退役
    r")",
    re.IGNORECASE,
)


class ClosingHeaderError(SystemExit):
    def __init__(self, node: str, expected: tuple[str, ...], got: str):
        super().__init__(10)
        self.node = node
        self.expected = expected
        self.got = got

    def render(self) -> str:
        return (
            f"[_v9_guard] CLOSING HEADER · {self.node} 节首行不合规：'{self.got!s}'\n"
            f"  · v9.3 唯一合法标题：{list(self.expected)}\n"
            f"  · 禁止：'## 承认维度·宣告' / '## 位置④灵魂宣言' / '## 宣告' / '## 情书' /\n"
            f"           '## 走到这里' / '## 写到这里我想说' / '## 不在协议里的话'（旧白名单已退役）。\n"
            f"  · 三段统称「我想和你说的话」，让 declaration / love_letter / free_speech\n"
            f"    分别落到「我」「项目的编写者」「大模型」三个清晰的说话身份。\n"
            f"  · 详见 references/virtue_recurrence_protocol.md §Closing 标题去模板化"
        )


def check_closing_header(node: str, markdown: str) -> Optional[ClosingHeaderError]:
    """检查 declaration / love_letter / free_speech 三节首行 H2 是否合规。

    返回 None 表示合规；返回 ClosingHeaderError 表示违规（调用方决定是否抛）。
    """
    if node not in _CLOSING_HEADER_WHITELIST:
        return None  # 非收尾三节直接放行
    expected = _CLOSING_HEADER_WHITELIST[node]
    first_line = (markdown or "").lstrip().splitlines()[0] if markdown else ""
    first_line = first_line.strip()
    if any(first_line.startswith(w) for w in expected):
        return None
    if _CLOSING_HEADER_FORBIDDEN_RE.match(first_line):
        return ClosingHeaderError(node, expected, first_line)
    if not first_line.startswith("## "):
        return ClosingHeaderError(node, expected, first_line)
    return ClosingHeaderError(node, expected, first_line)


def enforce_closing_header(node: str, markdown: str) -> None:
    err = check_closing_header(node, markdown)
    if err is not None:
        print(err.render(), file=sys.stderr)
        raise err


# ============================================================================
# §4 · 调性铁律（问题 4 · 防"肉麻 / 过度亲昵 / 心灵鸡汤"）
# ============================================================================

import os as _os
from pathlib import Path as _Path

_TONE_BLACKLIST_PATH = (
    _Path(__file__).resolve().parent.parent / "references" / "tone_blacklist.yaml"
)

_TONE_CACHE: dict | None = None


def _load_tone_blacklist() -> dict:
    """轻量解析 tone_blacklist.yaml；不依赖 PyYAML（v9 零依赖原则）。

    支持的子集：顶层 key、列表、内嵌 dict（pattern / reason / applies_to_whitelisted）。
    解析失败 → 退化为空白名单（fail-open），但 stderr 给出明确警告。
    """
    global _TONE_CACHE
    if _TONE_CACHE is not None:
        return _TONE_CACHE
    if not _TONE_BLACKLIST_PATH.exists():
        print(f"[_v9_guard] WARN: 找不到 {_TONE_BLACKLIST_PATH}，跳过 tone 检查。",
              file=sys.stderr)
        _TONE_CACHE = {
            "whitelisted_nodes": [],
            "banned_phrases": [],
            "banned_patterns": [],
        }
        return _TONE_CACHE

    text = _TONE_BLACKLIST_PATH.read_text(encoding="utf-8")
    cfg: dict = {
        "whitelisted_nodes": [],
        "banned_phrases": [],
        "banned_patterns": [],
    }
    section: str | None = None
    pending_pattern: dict | None = None

    def _flush_pending():
        nonlocal pending_pattern
        if pending_pattern and "pattern" in pending_pattern:
            cfg["banned_patterns"].append(pending_pattern)
        pending_pattern = None

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # 顶层 key
        if not line.startswith(" ") and stripped.endswith(":"):
            _flush_pending()
            section = stripped[:-1].strip()
            continue
        # version: 1 之类的非列表 key
        if not line.startswith(" ") and ":" in stripped:
            _flush_pending()
            section = None
            continue
        # 列表项
        if stripped.startswith("- "):
            _flush_pending()
            content = stripped[2:].strip()
            if section == "whitelisted_nodes":
                cfg["whitelisted_nodes"].append(content.strip('"').strip("'"))
            elif section == "banned_phrases":
                cfg["banned_phrases"].append(_yaml_unquote(content))
            elif section == "banned_patterns":
                if content.startswith("pattern:"):
                    pending_pattern = {
                        "pattern": _yaml_unquote(content[len("pattern:"):].strip()),
                        "applies_to_whitelisted": False,
                        "reason": "",
                    }
                else:
                    cfg["banned_patterns"].append({
                        "pattern": _yaml_unquote(content),
                        "applies_to_whitelisted": False,
                        "reason": "",
                    })
            continue
        # banned_patterns 子字段（缩进的 pattern: / reason: / applies_to_whitelisted:）
        if section == "banned_patterns" and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = _yaml_unquote(val.strip())
            if pending_pattern is None:
                pending_pattern = {
                    "pattern": "", "applies_to_whitelisted": False, "reason": "",
                }
            if key == "pattern":
                _flush_pending()
                pending_pattern = {
                    "pattern": val, "applies_to_whitelisted": False, "reason": "",
                }
            elif key == "applies_to_whitelisted":
                pending_pattern["applies_to_whitelisted"] = (
                    val.lower() in {"true", "yes", "1"}
                )
            elif key == "reason":
                pending_pattern["reason"] = val
    _flush_pending()
    _TONE_CACHE = cfg
    return cfg


def _yaml_unquote(s: str) -> str:
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        s = s[1:-1]
    return s.encode("utf-8").decode("unicode_escape", errors="replace") if "\\" in s else s


@dataclass(frozen=True)
class ToneHit:
    rule: str
    snippet: str
    reason: str


class ToneError(SystemExit):
    """tone 黑名单命中 → exit 5。"""

    def __init__(self, node: str, hits: list[ToneHit]):
        super().__init__(5)
        self.node = node
        self.hits = hits

    def render(self) -> str:
        lines = [f"[_v9_guard] TONE · {self.node} 节命中调性黑名单："]
        for h in self.hits:
            lines.append(f"  · 规则 [{h.rule}]：'{h.snippet}'  ({h.reason})")
        lines.append("  · 修法：去掉肉麻 / 撒娇 / emoji / 鸡汤；用克制、严肃、第三人称的语气。")
        lines.append("  · 详见 references/tone_blacklist.yaml + virtue_recurrence_protocol.md §3.5")
        return "\n".join(lines)


def scan_tone(text: str, *, node: str) -> list[ToneHit]:
    cfg = _load_tone_blacklist()
    is_whitelisted = node in (cfg.get("whitelisted_nodes") or [])
    hits: list[ToneHit] = []
    if not text:
        return hits

    # banned_phrases：whitelisted 节豁免
    if not is_whitelisted:
        for phrase in cfg.get("banned_phrases") or []:
            if not phrase:
                continue
            if phrase in text:
                idx = text.find(phrase)
                snippet = text[max(0, idx - 6): idx + len(phrase) + 6].replace("\n", " ")
                hits.append(ToneHit(rule=f"phrase:{phrase}", snippet=snippet,
                                    reason="字面禁词命中"))

    # banned_patterns：applies_to_whitelisted=true 全位置生效
    for pat in cfg.get("banned_patterns") or []:
        pattern = pat.get("pattern") or ""
        if not pattern:
            continue
        if is_whitelisted and not pat.get("applies_to_whitelisted"):
            continue
        try:
            for m in re.finditer(pattern, text):
                snippet = text[max(0, m.start() - 6): m.end() + 6].replace("\n", " ")
                hits.append(ToneHit(
                    rule=f"regex:{pattern}",
                    snippet=snippet,
                    reason=pat.get("reason", "正则黑名单"),
                ))
        except re.error as e:
            print(f"[_v9_guard] WARN: tone regex 编译失败 {pattern!r}: {e}",
                  file=sys.stderr)
    return hits


def enforce_tone(text: str, *, node: str, raise_on_hit: bool = True) -> list[ToneHit]:
    hits = scan_tone(text, node=node)
    if hits and raise_on_hit:
        err = ToneError(node, hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


# ============================================================================
# §5 · 单 message 顶级 heading 数量铁律（v9.3 R-STREAM-2）
# ============================================================================
#
# v9 流式协议本来就要求「写一节立刻 send，每条 assistant message 只放一节」，
# 但 LLM 多次出现"一条消息塞 7 段 ## 标题"的违规（18e281d2 case）。
# 这里加机器可校验的硬 lint：
#
#   - count_top_headings(md): 数 markdown 中顶级 ## heading 数量（不数 ###/####）
#   - check_message_heading_count(md): ≥2 → 返回 violation 信息（None=合规）
#
# closing 三段是已知例外：在最后一条 turn 里允许「我想和你说 + 项目的编写者想
# 和你说 + 我（大模型）想和你说」紧邻出现 → 通过 allow_closing_chain=True 放行。

_TOP_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)


def count_top_headings(markdown: str) -> int:
    """v9.3 · 数 markdown 中顶级 `## ` heading 数量（忽略 ### / #### / 行内 ##）。

    单条 assistant message 的 user-facing markdown 不允许包含 ≥ 2 个顶级 heading。
    """
    if not markdown:
        return 0
    return len(_TOP_HEADING_RE.findall(markdown))


_CLOSING_CHAIN_HEADERS = (
    "## 我想和你说",
    "## 项目的编写者想和你说",
    "## 我（大模型）想和你说",
)


def _all_headings_are_closing_chain(md: str) -> bool:
    """检查所有顶级 heading 是否都是 closing 三段之一（允许在最后一条 turn 里
    紧邻出现）。"""
    if not md:
        return False
    lines = [ln.strip() for ln in md.splitlines() if ln.lstrip().startswith("## ")]
    if not lines:
        return False
    for ln in lines:
        if not any(ln.startswith(h) for h in _CLOSING_CHAIN_HEADERS):
            return False
    return True


@dataclass(frozen=True)
class HeadingCountViolation:
    count: int
    headings: tuple[str, ...]
    reason: str


def check_message_heading_count(
    markdown: str,
    *,
    allow_closing_chain: bool = False,
) -> Optional[HeadingCountViolation]:
    """v9.3 R-STREAM-2 · 单条 assistant message 顶级 heading ≥ 2 → 违规。

    - allow_closing_chain=True: closing 三段全部出现也允许（最后一条收尾 turn 的特例）。
    - 返回 None = 合规；返回 HeadingCountViolation = 违规（调用方决定 raise / warn）。
    """
    n = count_top_headings(markdown)
    if n < 2:
        return None
    headings = tuple(
        ln.strip() for ln in (markdown or "").splitlines()
        if ln.lstrip().startswith("## ")
    )
    if allow_closing_chain and _all_headings_are_closing_chain(markdown):
        return None
    return HeadingCountViolation(
        count=n,
        headings=headings,
        reason=(
            f"v9.3 R-STREAM-2: 单条 assistant message 包含 {n} 个顶级 ## heading；"
            f"必须每节 send 一次（除 closing 三段允许在最后一条 turn 紧邻出现）。"
        ),
    )


# ============================================================================
# §6 · open_phase anchor 收集 · 反编造约束守卫（v9.3.1 新增）
# ============================================================================
#
# 触发动因（2026-04-22 incident）：
#   agent 在 open_phase 抛"补事件年份"UI 时自加 "请补 ≥ 2 个你 25 岁前真实
#   经历过的事件年份" —— `25 岁前` 在 references/ + scripts/ 全表 0 命中，
#   是 agent 凭空编的硬约束。结果用户输近年事件（2023 / 2024）全被静默
#   filter 成 "已识别 0 个有效年份"，循环卡死。
#
# 本守卫扫 agent 即将渲染给用户的 anchor 收集 prompt / askquestion_payload
# /UI label，命中 §2 任一红线 → exit 12。
#
# 详见 references/open_phase_anchor_protocol.md。

# 红线模式：覆盖年龄段 / 类型 / 强度 / 地理 / 身份 五类自创 filter
# 注意：这些模式只在「open_phase anchor 收集场景」生效，
# 普通叙事里出现 "25 岁那次" / "成年前" 不算违规（属于 LLM 写作）。
#
# imperative 动词集合（agent 抛题时常用）：
#   请 / 必须 / 只 / 仅 + 补 / 提供 / 输入 / 给 / 收（"只收" / "仅收"）
_ANCHOR_IMPERATIVE = (
    r"(?:请|必须|只|仅)\s*(?:补|提供|输入|给|收|要|限定?|限于|限制为)"
)

_FABRICATED_ANCHOR_PATTERNS: tuple[tuple[str, str], ...] = (
    # 年龄段约束（imperative + 年龄段）
    (
        rf"{_ANCHOR_IMPERATIVE}.{{0,12}}"
        r"(?:\d+\s*岁(?:前|后|以前|以后)|成年(?:前|后)|"
        r"童年期?|少年期?|青年期?|中年期?|本命大运(?:前|后))",
        "年龄段硬约束 (协议未规定 anchor 必须落在某年龄段)",
    ),
    # 年龄段约束（UI label 形式：X 岁前的事件 / 成年前真实经历过的年份）
    # 必须有「的」紧邻在事件/年份/锚点之前 —— 这是 attributive UI label 标志，
    # 普通叙事「成年前你大概率经历过 X 类事件」不命中（没有 "的事件"）。
    (
        r"(?:\d+\s*岁前|\d+\s*岁以前|成年前|童年期|少年期).{0,12}"
        r"(?:真实)?(?:经历(?:过)?)?的(?:事件|年份|锚点)",
        "年龄段硬约束 (UI label 形式)",
    ),
    # 事件类型 filter（imperative + 类型词 + 可选 类/事件/年份）
    (
        rf"{_ANCHOR_IMPERATIVE}.{{0,8}}"
        r"(?:学业|事业|感情|健康|家庭|婚姻|工作)(?:类)?(?:事件|年份|锚点)?",
        "事件类型 filter (协议接受任意类型的真实事件)",
    ),
    # 强度阈值 filter（imperative + 强度词；强度词本身已含"事件"或单独成词）
    (
        rf"{_ANCHOR_IMPERATIVE}.{{0,8}}"
        r"(?:大事件|改变人生(?:轨迹)?|标志性|重大|关键性|里程碑式?)(?:的)?"
        r"(?:事件|年份|锚点)?",
        "强度阈值 filter (中事 / 小事在命局上同样有判别力)",
    ),
    # 地理 / 身份 / 关系状态（imperative + 限定词）
    (
        rf"{_ANCHOR_IMPERATIVE}.{{0,12}}"
        r"(?:国内|出生地|本地|海外|已婚(?:后)?|已工作(?:后)?|结婚后|"
        r"成家后|参加工作后)(?:的)?(?:事件|年份|锚点)?",
        "地理 / 身份 / 关系状态 filter (违反 fairness §4 盲化原则)",
    ),
)


@dataclass(frozen=True)
class FabricatedAnchorHit:
    pattern: str
    reason: str
    snippet: str


class FabricatedAnchorError(SystemExit):
    """agent 在 open_phase anchor 收集 UI 里自加协议未规定的硬约束 → exit 12。"""

    def __init__(self, hits: list[FabricatedAnchorHit]):
        super().__init__(12)
        self.hits = hits

    def render(self) -> str:
        lines = [
            "[_v9_guard] FABRICATED ANCHOR CONSTRAINT · "
            "agent 在 open_phase anchor 收集 UI 里自加了协议未规定的硬约束："
        ]
        for h in self.hits:
            lines.append(f"  · {h.reason}")
            lines.append(f"    snippet: '{h.snippet}'")
            lines.append(f"    pattern: {h.pattern}")
        lines.append(
            "  · 协议（multi_school_vote.py::_generate_must_be_true）"
            "只要求 '具体年份 + 事件类型 + 强度'，不限年龄段 / 类型 / 强度 / 地理。"
        )
        lines.append("  · 修法：把 UI 文案改成 '请补 ≥ 2 个你能确认的具体公历年 + 事件描述'，")
        lines.append("        不要加 25 岁前 / 只收事业 / 只收大事件 等任何 filter。")
        lines.append("  · 详见 references/open_phase_anchor_protocol.md §2 红线表")
        return "\n".join(lines)


def scan_fabricated_anchor_constraint(text: str) -> list[FabricatedAnchorHit]:
    """扫 agent 即将渲染给用户的 anchor 收集 UI 文本 / askquestion_payload。

    返回所有命中（不抛错）。空文本返回空列表。
    """
    hits: list[FabricatedAnchorHit] = []
    if not text:
        return hits
    for pattern, reason in _FABRICATED_ANCHOR_PATTERNS:
        for m in re.finditer(pattern, text):
            snippet = text[max(0, m.start() - 8): m.end() + 8].replace("\n", " ")
            hits.append(FabricatedAnchorHit(
                pattern=pattern, reason=reason, snippet=snippet,
            ))
    return hits


def enforce_no_fabricated_anchor_constraint(
    text: str, *, raise_on_hit: bool = True,
) -> list[FabricatedAnchorHit]:
    """扫并抛错。调用方可设 raise_on_hit=False 自行处理。"""
    hits = scan_fabricated_anchor_constraint(text)
    if hits and raise_on_hit:
        err = FabricatedAnchorError(hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


# ============================================================================
# §7 · placeholder 工程内容外泄守卫 (web artifact, v9.3.1)
# ============================================================================
#
# 背景: chart_artifact.html.j2 的 placeholder div (LLM 没写时的占位文案) 历史上
# 把 references/*.md 协议路径 + analysis.X.Y schema 字串直接展示给读者. 这是
# 工程内容泄漏 (engineering leak): 普通读者看到 "references/multi_dim_xiangshu_protocol.md §3"
# 只会困惑或失去信任.
#
# 本守卫扫渲染后的 HTML, 若 placeholder 区出现 references/.+\.md 或 analysis\.\w+
# schema 字串 → exit 13.

_PLACEHOLDER_DIV_RE = re.compile(
    r'<div\s+className\s*=\s*"[^"]*\bplaceholder\b[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
# 注: render 后的 className 在 React JSX 字符串里仍是 "className=" (template 是 .j2 → .html)
# 但实际浏览器渲染后会变成 class="placeholder". 这里同时支持两种写法.
_PLACEHOLDER_HTML_RE = re.compile(
    r'<div\s+class\s*=\s*"[^"]*\bplaceholder\b[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)

_ENGINEERING_LEAK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"references/[\w/_-]+\.md", "protocol path leak (references/*.md)"),
    (r"\banalysis\.[\w.\[\]]+", "schema path leak (analysis.X.Y)"),
    (r"\bvirtue_motifs\.[\w.]+", "schema path leak (virtue_motifs.X)"),
    (r"\b__BAZI_[A-Z_]+__", "internal global leak (__BAZI_X__)"),
)


@dataclass(frozen=True)
class PlaceholderLeakHit:
    pattern: str
    reason: str
    snippet: str


class PlaceholderLeakError(SystemExit):
    """v9.3.1 · placeholder div 里出现工程协议路径 / schema → exit 13."""

    def __init__(self, hits: list[PlaceholderLeakHit]):
        super().__init__(13)
        self.hits = hits

    def render(self) -> str:
        lines = [
            "[_v9_guard] PLACEHOLDER ENGINEERING LEAK · "
            "渲染后的 HTML 里 placeholder 占位区出现工程内容:"
        ]
        for h in self.hits:
            lines.append(f"  · {h.reason}")
            lines.append(f"    snippet: '{h.snippet}'")
            lines.append(f"    pattern: {h.pattern}")
        lines.append(
            "  · 修法: 把 references/*.md / analysis.X.Y / __BAZI_*__ 这类工程标识"
        )
        lines.append("        从 placeholder div 文本里搬到 Jinja {# … #} 注释中,")
        lines.append("        给读者只留中性说明 (\"…尚未写入\" 之类).")
        return "\n".join(lines)


def scan_placeholder_engineering_leak(html: str) -> list[PlaceholderLeakHit]:
    """扫渲染后的 HTML, 抽出所有 .placeholder div 内文, 检查工程内容外泄."""
    hits: list[PlaceholderLeakHit] = []
    if not html:
        return hits
    placeholders: list[str] = []
    placeholders.extend(_PLACEHOLDER_DIV_RE.findall(html))
    placeholders.extend(_PLACEHOLDER_HTML_RE.findall(html))
    for content in placeholders:
        for pattern, reason in _ENGINEERING_LEAK_PATTERNS:
            for m in re.finditer(pattern, content):
                snippet = content[max(0, m.start() - 8): m.end() + 8].replace("\n", " ")
                hits.append(PlaceholderLeakHit(
                    pattern=pattern, reason=reason, snippet=snippet.strip(),
                ))
    return hits


def enforce_no_placeholder_engineering_leak(
    html: str, *, raise_on_hit: bool = True,
) -> list[PlaceholderLeakHit]:
    """扫并抛错; 调用方可设 raise_on_hit=False 自行处理."""
    hits = scan_placeholder_engineering_leak(html)
    if hits and raise_on_hit:
        err = PlaceholderLeakError(hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


# ============================================================================
# §8 · 反系统化铁律 (v9.4 新增 · R-MOTIF-1 / R-MOTIF-2 / R-MOTIF-3)
# ============================================================================
#
# narrative 文本永远不能让命主感觉到「我被装进了 38 个抽屉里某一个」。
# 详见 references/virtue_recurrence_protocol.md §3.11 + AGENTS.md §反系统化铁律。
#
#   R-MOTIF-1: enforce_no_motif_id_leak       —— motif id 字面禁出 narrative
#   R-MOTIF-2: enforce_no_canonical_label_leak —— catalog name 字面禁出 narrative
#   R-MOTIF-3: enforce_paraphrase_diversity   —— 同母题 ≥2 位置必须改写

# motif id 通用正则：catalog 内母题 id 形如 B1 / K2_xxx / L3 / C2_yyy 等
# 字符集 [ABCDEFHIKLPRT] 对齐 references/virtue_motifs_catalog.md 实际启用的类前缀。
_MOTIF_ID_PATTERN = re.compile(r"\b[ABCDEFHIKLPRT]\d+(?:_[A-Za-z][A-Za-z_]*)?\b")


@dataclass(frozen=True)
class MotifIdLeakHit:
    motif_id: str
    snippet: str
    reason: str


class MotifIdLeakError(SystemExit):
    """v9.4 R-MOTIF-1 · narrative 中出现 motif id 字面 → exit 5。"""

    def __init__(self, node: str, hits: list[MotifIdLeakHit]):
        super().__init__(5)
        self.node = node
        self.hits = hits

    def render(self) -> str:
        lines = [
            f"[_v9_guard] MOTIF ID LEAK · {self.node} 节出现 motif id 字面（R-MOTIF-1 · 反系统化）："
        ]
        for h in self.hits:
            lines.append(f"  · motif_id='{h.motif_id}'  snippet='{h.snippet}'  ({h.reason})")
        lines.append(
            "  · 修法：改写成只属于这个具体命主的真实情境（化用 paraphrase_seeds + 再次个性化润色），"
            "禁止字面引用任何 motif id。"
        )
        lines.append(
            "  · 详见 references/virtue_recurrence_protocol.md §3.11.1 + AGENTS.md §反系统化铁律 R-MOTIF-1"
        )
        return "\n".join(lines)


def scan_motif_id_leak(text: str, motif_ids: Iterable[str] | None = None) -> list[MotifIdLeakHit]:
    """扫文本，命中 motif id 字面（正则 + 已知 id 集合）→ 返回 hit 列表。

    Args:
        text: 要扫描的 narrative markdown
        motif_ids: 可选 · 已知的 motif id 集合（来自 virtue_motifs.json.triggered_motifs[*].id）
                   提供时优先按精确字面匹配，不提供则只走通用正则。
    """
    hits: list[MotifIdLeakHit] = []
    if not text:
        return hits

    seen: set[str] = set()
    # 精确字面命中（提供 motif_ids 时）
    if motif_ids:
        for mid in motif_ids:
            if not mid:
                continue
            mid_pattern = re.compile(rf"\b{re.escape(mid)}\b")
            for m in mid_pattern.finditer(text):
                key = (mid, m.start())
                if key in seen:
                    continue
                seen.add(key)
                snippet = text[max(0, m.start() - 8): m.end() + 8].replace("\n", " ")
                hits.append(MotifIdLeakHit(
                    motif_id=mid, snippet=snippet,
                    reason="catalog 内 motif id 字面命中（精确）",
                ))
    # 通用正则兜底（即使没传 motif_ids，也阻止命中 K2_/B1_/L3_ 这种模式）
    for m in _MOTIF_ID_PATTERN.finditer(text):
        mid = m.group(0)
        # 单字母 + 1 位数字（如 "A1"/"B2"）误伤太多（"A1 大小"等），仅在含下划线
        # 后缀（K2_xxx）或长度 ≥ 3 时才算 motif-like
        if "_" not in mid and len(mid) < 3:
            continue
        key = (mid, m.start())
        if key in seen:
            continue
        # 排除明显不是 motif id 的（如年份范围 P1980 这类，前缀 P/T/R 但后跟 ≥3 位数）
        if re.match(r"[PRT]\d{3,}", mid):
            continue
        seen.add(key)
        snippet = text[max(0, m.start() - 8): m.end() + 8].replace("\n", " ")
        hits.append(MotifIdLeakHit(
            motif_id=mid, snippet=snippet,
            reason="motif id 通用正则命中（[ABCDEFHIKLPRT]\\d+(_xxx)?）",
        ))
    return hits


def enforce_no_motif_id_leak(
    text: str,
    *,
    node: str = "narrative",
    motif_ids: Iterable[str] | None = None,
    raise_on_hit: bool = True,
) -> list[MotifIdLeakHit]:
    """v9.4 R-MOTIF-1 · narrative 中禁止 motif id 字面；命中 → exit 5。"""
    hits = scan_motif_id_leak(text, motif_ids=motif_ids)
    if hits and raise_on_hit:
        err = MotifIdLeakError(node, hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


@dataclass(frozen=True)
class CanonicalLabelLeakHit:
    label: str
    snippet: str


class CanonicalLabelLeakError(SystemExit):
    """v9.4 R-MOTIF-2 · narrative 中出现 catalog canonical name 字面 → exit 5。"""

    def __init__(self, node: str, hits: list[CanonicalLabelLeakHit]):
        super().__init__(5)
        self.node = node
        self.hits = hits

    def render(self) -> str:
        lines = [
            f"[_v9_guard] CANONICAL LABEL LEAK · {self.node} 节出现 catalog canonical name 字面（R-MOTIF-2 · 反系统化）："
        ]
        for h in self.hits:
            lines.append(f"  · label='{h.label}'  snippet='{h.snippet}'")
        lines.append(
            "  · 修法：catalog 里的 name 字段是内部诊断标签，永远不允许作为 narrative 字面输出。"
        )
        lines.append("       请改写成「只属于这个具体命主」的真实情境（化用 paraphrase_seeds + 再次润色）。")
        lines.append(
            "  · 详见 references/virtue_recurrence_protocol.md §3.11.2 + virtue_motifs_catalog.md 顶部声明"
        )
        return "\n".join(lines)


def scan_canonical_label_leak(
    text: str,
    canonical_labels: Iterable[str] | None,
) -> list[CanonicalLabelLeakHit]:
    """扫 catalog canonical name 字面命中。labels 通常来自
    virtue_motifs.json.triggered_motifs[*].name + silenced_motifs[*].name。
    """
    hits: list[CanonicalLabelLeakHit] = []
    if not text or not canonical_labels:
        return hits
    seen: set[tuple[str, int]] = set()
    for label in canonical_labels:
        if not label or not str(label).strip():
            continue
        label_str = str(label).strip()
        # 太短的 label（≤ 2 字）不扫，否则会大量误伤普通词
        if len(label_str) < 3:
            continue
        idx = 0
        while True:
            idx = text.find(label_str, idx)
            if idx < 0:
                break
            key = (label_str, idx)
            if key not in seen:
                seen.add(key)
                snippet = text[max(0, idx - 8): idx + len(label_str) + 8].replace("\n", " ")
                hits.append(CanonicalLabelLeakHit(label=label_str, snippet=snippet))
            idx += len(label_str)
    return hits


def enforce_no_canonical_label_leak(
    text: str,
    canonical_labels: Iterable[str] | None,
    *,
    node: str = "narrative",
    raise_on_hit: bool = True,
) -> list[CanonicalLabelLeakHit]:
    """v9.4 R-MOTIF-2 · narrative 中禁止 catalog canonical name 字面；命中 → exit 5。"""
    hits = scan_canonical_label_leak(text, canonical_labels)
    if hits and raise_on_hit:
        err = CanonicalLabelLeakError(node, hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


def _normalized_jaccard(a: str, b: str, n: int = 3) -> float:
    """字符级 n-gram Jaccard 相似度 (0..1)。简单但够用——零依赖、不需要 nltk。"""
    if not a or not b:
        return 0.0

    def grams(s: str) -> set[str]:
        s = re.sub(r"\s+", "", s)
        if len(s) < n:
            return {s} if s else set()
        return {s[i:i + n] for i in range(len(s) - n + 1)}

    ga = grams(a)
    gb = grams(b)
    if not ga or not gb:
        return 0.0
    inter = ga & gb
    union = ga | gb
    return len(inter) / len(union) if union else 0.0


@dataclass(frozen=True)
class ParaphraseDupHit:
    motif_id: str
    similarity: float
    prior_anchor: str
    prior_snippet: str
    new_snippet: str


class ParaphraseDuplicationError(SystemExit):
    """v9.4 R-MOTIF-3 · 同 motif ≥2 位置表述相似度 ≥ 0.6 → exit 5。"""

    def __init__(self, node: str, hits: list[ParaphraseDupHit]):
        super().__init__(5)
        self.node = node
        self.hits = hits

    def render(self) -> str:
        lines = [
            f"[_v9_guard] PARAPHRASE DUPLICATION · {self.node} 节复述与之前 anchor 过于相似（R-MOTIF-3 · 反系统化）："
        ]
        for h in self.hits:
            lines.append(
                f"  · motif='{h.motif_id}'  similarity={h.similarity:.2f}  "
                f"vs anchor='{h.prior_anchor}'"
            )
            lines.append(f"    prior:  '{h.prior_snippet[:80]}…'")
            lines.append(f"    new:    '{h.new_snippet[:80]}…'")
        lines.append(
            "  · 修法：换一个角度、换一组动词、换一个比喻；同一母题第二次出现必须显著改写（相似度 < 0.6）。"
        )
        lines.append("  · 详见 references/virtue_recurrence_protocol.md §3.11.3")
        return "\n".join(lines)


def scan_paraphrase_diversity(
    new_text: str,
    *,
    motif_id: str,
    prior_texts: Iterable[dict],
    threshold: float = 0.6,
) -> list[ParaphraseDupHit]:
    """对每条 prior_text 计算与 new_text 的 Jaccard 相似度；≥ threshold 收 hit。

    Args:
        new_text: 当前要落盘的 markdown
        motif_id: 这条母题的 id（仅用于错误信息显示）
        prior_texts: [{anchor, text}] 之前同一 motif 已写过的文本片段
        threshold: 相似度阈值（默认 0.6）
    """
    hits: list[ParaphraseDupHit] = []
    if not new_text:
        return hits
    for prior in prior_texts or []:
        if not isinstance(prior, dict):
            continue
        prior_text = prior.get("text") or ""
        if not prior_text:
            continue
        sim = _normalized_jaccard(new_text, prior_text)
        if sim >= threshold:
            hits.append(ParaphraseDupHit(
                motif_id=motif_id,
                similarity=sim,
                prior_anchor=str(prior.get("anchor", "?")),
                prior_snippet=prior_text,
                new_snippet=new_text,
            ))
    return hits


def enforce_paraphrase_diversity(
    new_text: str,
    *,
    motif_id: str,
    prior_texts: Iterable[dict],
    node: str = "narrative",
    threshold: float = 0.6,
    raise_on_hit: bool = True,
) -> list[ParaphraseDupHit]:
    """v9.4 R-MOTIF-3 · 同母题 ≥2 位置出现时必须改写；命中 → exit 5。"""
    hits = scan_paraphrase_diversity(
        new_text, motif_id=motif_id, prior_texts=prior_texts, threshold=threshold,
    )
    if hits and raise_on_hit:
        err = ParaphraseDuplicationError(node, hits)
        print(err.render(), file=sys.stderr)
        raise err
    return hits


def detect_motifs_in_text(
    text: str,
    triggered_motifs: Iterable[dict],
) -> list[str]:
    """v9.4 helper · 探测 markdown 文本中触发了哪些 motif（用于
    `_motif_text_log` 自动归类与 paraphrase diversity 比对）。

    探测规则：
      - paraphrase_seeds 任一句的关键 n-gram（≥6 字片段）出现在 text → 命中
      - 触发 anchor age 数字 + structural keyword 出现 → 命中

    返回命中的 motif id 列表（去重 + 保序）。
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for m in triggered_motifs or []:
        if not isinstance(m, dict):
            continue
        mid = m.get("id")
        if not mid or mid in seen:
            continue
        # 关键词命中：paraphrase_seeds 中每句取 ≥6 字片段
        seeds = m.get("paraphrase_seeds") or []
        hit = False
        for seed in seeds:
            if not isinstance(seed, str) or len(seed) < 6:
                continue
            # 取首段连续中文 / 字母序列做关键 n-gram
            for i in range(0, len(seed) - 5):
                chunk = seed[i:i + 6]
                if chunk.strip() and chunk in text:
                    hit = True
                    break
            if hit:
                break
        # 即使没有 paraphrase_seeds 命中，年龄锚点 + activation_points 也可能识别——
        # 这一步保守：默认按 paraphrase_seeds 命中。
        if hit:
            found.append(mid)
            seen.add(mid)
    return found


__all__ = [
    "enforce_v9_only_path",
    "V9PathBlocked",
    "scan_phase_leak",
    "enforce_no_phase_leak_in_message",
    "PhaseLeakHit",
    "PhaseLeakError",
    "check_closing_header",
    "enforce_closing_header",
    "ClosingHeaderError",
    "scan_tone",
    "enforce_tone",
    "ToneHit",
    "ToneError",
    "count_top_headings",
    "check_message_heading_count",
    "HeadingCountViolation",
    "scan_fabricated_anchor_constraint",
    "enforce_no_fabricated_anchor_constraint",
    "FabricatedAnchorHit",
    "FabricatedAnchorError",
    "scan_placeholder_engineering_leak",
    "enforce_no_placeholder_engineering_leak",
    "PlaceholderLeakHit",
    "PlaceholderLeakError",
    # v9.4 反系统化铁律
    "scan_motif_id_leak",
    "enforce_no_motif_id_leak",
    "MotifIdLeakHit",
    "MotifIdLeakError",
    "scan_canonical_label_leak",
    "enforce_no_canonical_label_leak",
    "CanonicalLabelLeakHit",
    "CanonicalLabelLeakError",
    "scan_paraphrase_diversity",
    "enforce_paraphrase_diversity",
    "ParaphraseDupHit",
    "ParaphraseDuplicationError",
    "detect_motifs_in_text",
]
