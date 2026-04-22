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
]
