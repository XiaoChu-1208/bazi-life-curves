#!/usr/bin/env python3
"""mcp_server.py — MCP (Model Context Protocol) stdio server for bazi-life-curves (v8.0)

把项目所有核心 CLI 暴露为 MCP tools，可被任何 MCP 兼容客户端调用：

    Claude Desktop · Cursor · Cline · Continue · Zed · Windsurf
    Codex CLI · Aider · Devin · LangChain MCP adapter · LlamaIndex MCP

实现了 11 个 tools，分两组：

A. 项目原生 tools（8 个）：
   - solve_bazi              · 八字解析
   - score_curves            · 4 维 × 80 年人生曲线打分
   - mangpai_events          · 盲派事件检测
   - handshake               · R0/R0'/R1/R2/R3 反询问校验
   - evaluate_handshake      · 用户答完后机械化评估
   - he_pan                  · 合盘 4 层评分
   - render_artifact         · 交互 HTML 渲染
   - engines_diagnostics     · 引擎可用性诊断

B. cantian-ai/bazi-mcp 兼容别名（3 个 · 100% 接口兼容）：
   - getBaziDetail           · 公历/八字 → 完整命局信息
   - getSolarTimes           · 八字 → 公历可能时刻列表
   - getChineseCalendar      · 公历 → 农历 + 干支 + 节气

设计原则：
- **零外部依赖**：不依赖 mcp SDK，原生实现 MCP stdio + JSON-RPC 2.0
- **Python 3.9+ 兼容**：避开 3.10+ 语法（如 match/case）
- **bit-for-bit deterministic**：所有 tool 输出与 CLI 完全一致
- **fairness_protocol §10 守卫**：身份盲化输入、orientation 必填、emotion 解读铁律
- **完整 JSON Schema**：每个 tool 都有详尽的 inputSchema，方便 AI 理解参数

运行（stdio · 给 MCP 客户端用）：
    python scripts/mcp_server.py

诊断模式（人类用 · 列出所有 tools 不启动 stdio loop）：
    python scripts/mcp_server.py --inspect

接入 Claude Desktop ~/Library/Application Support/Claude/claude_desktop_config.json：
    {
      "mcpServers": {
        "bazi-life-curves": {
          "command": "python3",
          "args": ["/abs/path/to/bazi-life-curves/scripts/mcp_server.py"]
        }
      }
    }

接入 Cursor .cursor/mcp.json：
    {
      "mcpServers": {
        "bazi-life-curves": {
          "command": "python3",
          "args": ["/abs/path/to/bazi-life-curves/scripts/mcp_server.py"]
        }
      }
    }

详见 README "MCP server 接入" 一节。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 把 scripts/ 放进 sys.path，让 import 找到所有同级模块
_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))


# ─────────────────────────────────────────────────────────────────────
# Server metadata
# ─────────────────────────────────────────────────────────────────────

SERVER_NAME = "bazi-life-curves"
SERVER_VERSION = "8.0.0"
PROTOCOL_VERSION = "2024-11-05"  # MCP protocol version


# ─────────────────────────────────────────────────────────────────────
# Tool registry
# ─────────────────────────────────────────────────────────────────────

TOOLS: List[Dict[str, Any]] = []  # 用于 tools/list
HANDLERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}


def register(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
):
    """装饰器：注册一个 MCP tool。"""
    def deco(fn: Callable[[Dict[str, Any]], Dict[str, Any]]):
        TOOLS.append({
            "name": name,
            "description": description,
            "inputSchema": input_schema,
        })
        HANDLERS[name] = fn
        return fn
    return deco


def _err(msg: str, **extra) -> Dict[str, Any]:
    return {"ok": False, "error": msg, **extra}


def _ok(data: Any, **extra) -> Dict[str, Any]:
    return {"ok": True, "data": data, **extra}


# ─────────────────────────────────────────────────────────────────────
# Tool A1: solve_bazi
# ─────────────────────────────────────────────────────────────────────

@register(
    name="solve_bazi",
    description=(
        "八字解析（v8.0 · 业内首个三引擎可选 + 天文级真太阳时）。\n"
        "输入公历或四柱字符串 + 性别 + 取向 + 可选经度，输出完整命局 JSON：\n"
        "  四柱 / 日主 / 强弱 / 用神 / 五行分布 / 大运序列 / 80 年流年 / 起运岁\n"
        "fairness §9：性别仅影响（1）大运起运方向；（2）emotion 通道配偶星识别。"
        "spirit/wealth/fame 三派打分与性别完全无关（自动回归测试保证）。\n"
        "fairness §10：orientation 必填，hetero/homo/bi/none/poly 5 选项。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pillars": {
                "type": "string",
                "description": "四柱字符串，例：'庚午 辛巳 壬子 丁未'。与 gregorian 二选一。",
            },
            "gregorian": {
                "type": "string",
                "description": "公历时刻 'YYYY-MM-DD HH:MM'。与 pillars 二选一。推荐用此模式（可用 longitude 真太阳时校正 + 起运岁精算）。",
            },
            "gender": {
                "type": "string",
                "enum": ["M", "F"],
                "description": "生理性别。仅影响大运起运方向 + emotion 配偶星识别默认值；spirit/wealth/fame 完全性别无关。",
            },
            "birth_year": {
                "type": "integer",
                "description": "出生公历年（pillars 模式必填；gregorian 模式自动从字符串解析）。",
            },
            "orientation": {
                "type": "string",
                "enum": ["hetero", "homo", "bi", "none", "poly"],
                "default": "hetero",
                "description": "关系取向。hetero=异性恋(默认)，homo=同性恋，bi=双性，none=单身/不寻求亲密关系，poly=多元关系。仅影响 emotion 通道，不影响 spirit/wealth/fame。",
            },
            "n_years": {"type": "integer", "default": 80, "description": "流年生成长度（岁），默认 80"},
            "qiyun_age": {"type": "integer", "description": "起运虚岁。gregorian 模式默认用 lunar-python 精算；pillars 模式默认 8 岁。"},
            "longitude": {
                "type": "number",
                "description": "出生地经度（° E，东经为正）。v8.0：装了 sxtwl 自动启用'天文级真太阳时'（NOAA EOT 公式 + 经度差，精度 ±15 秒）；未装 sxtwl 时用经度近似（±2 分钟）。仅 gregorian 模式生效。示例：北京 116.4 / 上海 121.5 / 乌鲁木齐 87.6。",
            },
            "engine": {
                "type": "string",
                "enum": ["lunar-python", "tyme4py", "cross-check"],
                "default": "lunar-python",
                "description": "v8.0 历法引擎：lunar-python(默认·行业事实标准) / tyme4py(节气基于寿星天文历) / cross-check(双引擎并行·节气交接边缘 case 自动 warn)。仅 gregorian 模式生效。",
            },
            "out_path": {
                "type": "string",
                "description": "可选：写盘路径。不传则只返回内联 JSON。",
            },
        },
        "anyOf": [
            {"required": ["pillars", "gender", "birth_year"]},
            {"required": ["gregorian", "gender"]},
        ],
    },
)
def tool_solve_bazi(args: Dict[str, Any]) -> Dict[str, Any]:
    import solve_bazi as sb
    if not args.get("pillars") and not args.get("gregorian"):
        return _err("Must provide either 'pillars' or 'gregorian'")
    if not args.get("gender"):
        return _err("'gender' is required (M/F)")
    data = sb.solve(
        pillars_str=args.get("pillars"),
        gregorian=args.get("gregorian"),
        gender=args["gender"],
        birth_year=args.get("birth_year"),
        n_years=args.get("n_years", 80),
        qiyun_age=args.get("qiyun_age"),
        orientation=args.get("orientation", "hetero"),
        longitude=args.get("longitude"),
        engine=args.get("engine", "lunar-python"),
    )
    if args.get("out_path"):
        Path(args["out_path"]).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _ok(data)


# ─────────────────────────────────────────────────────────────────────
# Tool A2: score_curves
# ─────────────────────────────────────────────────────────────────────

@register(
    name="score_curves",
    description=(
        "4 维 × 80 年人生曲线打分（业内唯一做时间序列曲线的命理工具）。\n"
        "三派融合（扶抑 25% + 调候 40% + 格局 30%）+ 盲派 0% 修正 + 10+ 条结构性保护。\n"
        "输入 bazi（solve_bazi 的输出），输出每年 4 维 fused 分 + 三派分歧标记 + 拐点预测。\n"
        "bit-for-bit deterministic（同输入 100 次 100 个 byte-equal 结果，可用 sha256sum 验证）。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bazi": {
                "oneOf": [
                    {"type": "object", "description": "内联 bazi.json"},
                    {"type": "string", "description": "bazi.json 文件路径"},
                ],
                "description": "solve_bazi 的输出（dict 或文件路径）",
            },
            "age_start": {"type": "integer", "default": 0},
            "age_end": {"type": "integer", "default": 80},
            "forecast_window": {"type": "integer", "default": 10, "description": "拐点预测窗口（年），默认 10"},
            "forecast_from_year": {"type": "integer", "description": "拐点预测起始公历年；不填则按 age_end 倒推"},
            "dispute_threshold": {"type": "number", "default": 20.0, "description": "三派极差超过此值即标记为派别争议年份"},
            "mangpai": {
                "oneOf": [
                    {"type": "object"},
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "可选：mangpai_events 输出（dict / 文件路径）；启用盲派烈度修正 + 事件附入 points",
            },
            "confirmed_facts": {
                "oneOf": [
                    {"type": "object"},
                    {"type": "string"},
                    {"type": "null"},
                ],
                "description": "可选：confirmed_facts.json（dict / 路径）；含 structural_corrections 时打分前应用",
            },
            "override_phase": {
                "type": "string",
                "description": "v7 P1-7 相位反演 phase_id（详见 references/phase_inversion_protocol.md）",
            },
            "out_path": {"type": "string", "description": "可选：写盘路径"},
        },
        "required": ["bazi"],
    },
)
def tool_score_curves(args: Dict[str, Any]) -> Dict[str, Any]:
    import score_curves as sc
    bazi = _load_or_dict(args["bazi"], "bazi")
    mangpai = _load_or_dict_opt(args.get("mangpai"), "mangpai")
    confirmed = _load_or_dict_opt(args.get("confirmed_facts"), "confirmed_facts")
    result = sc.score(
        bazi,
        age_start=args.get("age_start", 0),
        age_end=args.get("age_end", 80),
        forecast_from_year=args.get("forecast_from_year"),
        forecast_window=args.get("forecast_window", 10),
        dispute_threshold=args.get("dispute_threshold", 20.0),
        mangpai=mangpai,
        override_phase=args.get("override_phase"),
        confirmed_facts=confirmed,
    )
    if args.get("out_path"):
        Path(args["out_path"]).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _ok(result)


# ─────────────────────────────────────────────────────────────────────
# Tool A3: mangpai_events
# ─────────────────────────────────────────────────────────────────────

@register(
    name="mangpai_events",
    description=(
        "盲派事件检测（11 条经典组合 + 反向规则 + 护身减压 · 业内首个工程化）。\n"
        "11 条：伤官见官 / 比劫夺财 / 禄被冲 / 羊刃逢冲 / 反吟应期 / 伏吟应期 / "
        "财库被冲开 / 官杀混杂 / 七杀逢印 / 伤官伤尽 / 年财不归我。\n"
        "结构反向：身强用官 → 凶；身弱印护 → 化凶为吉（解决业内'机械读口诀'通病）。\n"
        "护身减压：识别杀印相生 / 食神制杀等保护机制时，对应事件 amplifier ×0.4。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bazi": {"oneOf": [{"type": "object"}, {"type": "string"}]},
            "age_start": {"type": "integer", "default": 0},
            "age_end": {"type": "integer", "default": 80},
            "out_path": {"type": "string"},
        },
        "required": ["bazi"],
    },
)
def tool_mangpai_events(args: Dict[str, Any]) -> Dict[str, Any]:
    import mangpai_events as mp
    bazi = _load_or_dict(args["bazi"], "bazi")
    result = mp.detect_all(bazi, args.get("age_start", 0), args.get("age_end", 80))
    if args.get("out_path"):
        Path(args["out_path"]).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _ok(result)


# ─────────────────────────────────────────────────────────────────────
# Tool A4: handshake
# ─────────────────────────────────────────────────────────────────────

@register(
    name="handshake",
    description=(
        "⚠ v9 deprecated for R1：R1 默认必须走 `adaptive_elicit.py next` 一题一轮（EIG 选题 · 5-8 题早停）。\n"
        "本 tool 仅保留两类合法用途：\n"
        "  1. R2 confirmation（--round 2 · 在 R1 决策 phase 与 runner-up 之间挑高 pairwise 题）\n"
        "  2. he_pan_orchestrator 多人合盘的 R1 兜底（v8 兼容路径，单盘新流程不要走这里）\n"
        "默认不要把它当 R1 入口用。详见 AGENTS.md §二「关键不可跳步（v9）」。\n"
        "\n"
        "[deprecated R1 docs] R0/R0'/R1/R2/R3 反询问校验。\n"
        "R0  ·  关系画像（2 题 · 取向校准）\n"
        "R0' ·  反迎合·反向探针（v7.4·防 sycophantic 偏置）\n"
        "R1  ·  健康三问（命局体感校准）\n"
        "R2  ·  历史锚点（仅 R1 < 3/3 时触发）\n"
        "R3  ·  原生家庭画像（v7.3·条件触发·仅在用户问家庭时抛）\n"
        "放行规则（机械化判定）：R0 ≥ 1/2 且 (R1 ≥ 2/3 或 R1+R2 ≥ 4/6)；"
        "R0=0 + R1≤1 → 红线触发，强制停手要时辰。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bazi": {"oneOf": [{"type": "object"}, {"type": "string"}]},
            "curves": {
                "oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}],
                "description": "score_curves 输出。默认模式必须；--dump-phase-candidates 模式可不填。",
            },
            "current_year": {"type": "integer", "description": "当前公历年；默认今年"},
            "user_responses": {
                "type": "array",
                "items": {"type": "object"},
                "description": "v7.4 · 用户对 R0/R1/R2/R3 + 反迎合 probe 的回复。"
                               "格式：[{trait_or_anchor, user_response, user_note?, side?}]。"
                               "传入后机械化判定 should_halt / accuracy_grade / red_lines_triggered。",
            },
            "dump_phase_candidates": {
                "type": "boolean",
                "default": False,
                "description": "v7 P1-7 模式：dump 4 类相位反演候选 + LLM 重跑指令；用于 R0+R1 命中率 ≤ 2/6 时。",
            },
            "default_hit_rate": {
                "type": "string",
                "description": "（仅 dump_phase_candidates 模式）当前默认相位的命中率，如 '2/6'",
            },
            "phase_id": {
                "type": "string",
                "description": "v7.2 相位反演二轮校验：按指定 phase_id 反演 bazi 后再生成 R0/R1/R2 候选",
            },
            "with_zeitgeist": {
                "type": "boolean",
                "default": False,
                "description": "v7.5 · 启用时代-民俗志层 · 生成 folkways_anchor_seeds（≤2 颗）",
            },
            "out_path": {"type": "string"},
            "ack_legacy_r1": {
                "type": "boolean",
                "default": False,
                "description": "确认本调用是合法非默认场景：R2 confirmation 或 he_pan 兜底。"
                               "未传 → stderr 打 v9 警告（提醒 agent 默认走 adaptive_elicit）。",
            },
        },
        "required": ["bazi"],
    },
)
def tool_handshake(args: Dict[str, Any]) -> Dict[str, Any]:
    import datetime as dt
    import handshake as hs
    # v9 硬阻断：默认 R1 路径已 deprecated；未显式 ack_legacy_r1 / dump_phase_candidates /
    # phase_id（R2 confirmation 用）→ 直接 _err return（MCP 不能 sys.exit），等价 CLI exit 2。
    if not args.get("ack_legacy_r1") and not args.get("dump_phase_candidates") and not args.get("phase_id"):
        return _err(
            "BLOCKED · v9 默认入口已 deprecated。R1 请改用 adaptive_elicit(action='next')。"
            "仅 R2 confirmation / he_pan 兜底 / dump_phase_candidates 可继续用本 tool；"
            "若必须沿用 R1 deprecated，传 ack_legacy_r1=true。"
            "详见 references/handshake_protocol.md §0 + AGENTS.md §二·v9 关键约束。"
        )
    bazi = _load_or_dict(args["bazi"], "bazi")

    if args.get("dump_phase_candidates"):
        result = hs.dump_phase_candidates(bazi, hit_rate_default=args.get("default_hit_rate"))
        if args.get("out_path"):
            Path(args["out_path"]).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return _ok(result)

    curves_in = args.get("curves")
    if curves_in is None:
        return _err("'curves' is required unless dump_phase_candidates=true")
    curves = _load_or_dict(curves_in, "curves")
    cy = args.get("current_year") or dt.date.today().year

    zeitgeist_context = None
    class_prior = None
    if args.get("with_zeitgeist"):
        try:
            import _zeitgeist_loader as zl
            import _class_prior as cp
            zeitgeist_context = zl.build_zeitgeist_context(bazi)
            class_prior = cp.infer_class_prior(bazi)
        except Exception as e:
            return _err(f"with_zeitgeist failed: {e}")

    result = hs.build(
        bazi, curves, cy,
        phase_id=args.get("phase_id"),
        zeitgeist_context=zeitgeist_context,
        class_prior=class_prior,
    )

    if args.get("user_responses"):
        result["evaluation"] = hs.evaluate_responses(result, args["user_responses"])

    if args.get("out_path"):
        Path(args["out_path"]).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _ok(result)


# ─────────────────────────────────────────────────────────────────────
# Tool A5: evaluate_handshake
# ─────────────────────────────────────────────────────────────────────

@register(
    name="evaluate_handshake",
    description=(
        "用户答完 R0/R1/R2/R3 后，机械化评估 should_halt / accuracy_grade / red_lines_triggered。\n"
        "（独立 tool · 方便先 build handshake → 抛给用户 → 收到回复后单独评估）"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "handshake_output": {"oneOf": [{"type": "object"}, {"type": "string"}]},
            "user_responses": {
                "type": "array",
                "items": {"type": "object"},
                "description": "[{trait_or_anchor, user_response, user_note?, side?}]",
            },
        },
        "required": ["handshake_output", "user_responses"],
    },
)
def tool_evaluate_handshake(args: Dict[str, Any]) -> Dict[str, Any]:
    import handshake as hs
    h = _load_or_dict(args["handshake_output"], "handshake_output")
    return _ok(hs.evaluate_responses(h, args["user_responses"]))


# ─────────────────────────────────────────────────────────────────────
# Tool A5b: adaptive_elicit  (v9 默认 R1 路径)
# ─────────────────────────────────────────────────────────────────────

@register(
    name="adaptive_elicit",
    description=(
        "v9 默认 R1：自适应贝叶斯 EIG 一题一轮 · 5-8 题早停（替代 v8 的 14/26 题一次性 batch）。\n"
        "用法（典型 3-step loop）：\n"
        "  1) action='next' + state（首次无 --answer）→ 拿 askquestion_payload，AskQuestion 抛单题\n"
        "  2) action='next' + state + answer='qid:opt' → 拿下一题 / 或 status='STOP' finalize\n"
        "  3) finalize 后 bazi.json 已写回，包含 phase_decision\n"
        "\n"
        "可选 batch 通道（仅当用户主动要求一次性答完时用）：\n"
        "  - action='dump_question_set' + tier='core14'|'full28'  → 导出 markdown 题集\n"
        "  - action='submit_batch' + answers={qid:opt}            → 一次性 finalize\n"
        "\n"
        "注意：默认请走 action='next'。dump_question_set 默认会发 stderr 警告（除非 ack_batch=true）。\n"
        "详见 references/multi_dim_xiangshu_protocol.md §13 + AGENTS.md §二「关键不可跳步（v9）」。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["next", "dump_question_set", "submit_batch"],
                "default": "next",
            },
            "bazi": {"oneOf": [{"type": "object"}, {"type": "string"}]},
            "curves": {"oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}]},
            "current_year": {"type": "integer"},
            # next-only
            "state": {
                "oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}],
                "description": "上一轮 state（首次为 null）。",
            },
            "state_out_path": {
                "type": "string",
                "description": "把更新后的 state 写到此路径（推荐 output/.elicit.state.json）。",
            },
            "answer": {
                "type": "string",
                "description": "上一题答案 'qid:opt'，首题不传。",
            },
            "out": {
                "type": "string",
                "description": "finalize 时写回的 bazi.json 路径。",
            },
            # batch-only
            "tier": {"type": "string", "enum": ["core14", "full28"]},
            "ack_batch": {
                "type": "boolean",
                "default": False,
                "description": "v9 一级确认：本次调用是用户主动选 batch（非默认）。"
                               "v9 已升级为 hard exit，必须再加 confirm_batch_defeats_v9=true。",
            },
            "confirm_batch_defeats_v9": {
                "type": "boolean",
                "default": False,
                "description": "v9 二级确认：你已向用户解释 batch 模式会失去 EIG 自适应选题，"
                               "且用户**仍**坚持要走 batch。必须与 ack_batch 同时传，否则 _err return。",
            },
            "answers": {
                "oneOf": [{"type": "object"}, {"type": "string"}],
                "description": "submit_batch 用：{qid:opt} dict 或文件路径。",
            },
        },
        "required": ["bazi"],
    },
)
def tool_adaptive_elicit(args: Dict[str, Any]) -> Dict[str, Any]:
    import datetime as dt
    import io
    import contextlib
    import argparse as _ap
    import adaptive_elicit as ae

    action = args.get("action", "next")
    bazi_in = args["bazi"]
    bazi = _load_or_dict(bazi_in, "bazi")
    cy = args.get("current_year") or dt.date.today().year

    # 把 dict bazi 落临时文件，让 cmd_* 复用 CLI 路径（避免重复实现）
    tmp_files: List[Path] = []
    def _ensure_path(obj_or_path: Any, suffix: str) -> str:
        if isinstance(obj_or_path, str):
            return obj_or_path
        import tempfile
        f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
        json.dump(obj_or_path, f, ensure_ascii=False)
        f.close()
        p = Path(f.name)
        tmp_files.append(p)
        return str(p)

    bazi_path = _ensure_path(bazi, ".bazi.json")
    curves_path = None
    if args.get("curves") is not None:
        curves_obj = _load_or_dict(args["curves"], "curves")
        curves_path = _ensure_path(curves_obj, ".curves.json")

    try:
        # capture stdout printed by cmd_*
        buf = io.StringIO()
        if action == "next":
            ns = _ap.Namespace(
                bazi=bazi_path,
                curves=curves_path,
                state=args.get("state_out_path") or _ensure_path(args.get("state") or {}, ".state.json"),
                answer=args.get("answer"),
                out=args.get("out") or bazi_path,
                current_year=cy,
            )
            with contextlib.redirect_stdout(buf):
                rc = ae.cmd_next(ns)
            raw = buf.getvalue().strip()
            try:
                payload = json.loads(raw) if raw else {"status": "DONE"}
            except json.JSONDecodeError:
                payload = {"status": "DONE", "stdout": raw}
            payload["_rc"] = rc
            return _ok(payload) if rc == 0 else _err(f"adaptive_elicit next rc={rc}: {raw}")

        if action == "dump_question_set":
            tier = args.get("tier")
            if tier not in ("core14", "full28"):
                return _err("dump_question_set requires tier='core14' or 'full28'")
            # v9 硬阻断：未传双重确认 → 直接 _err return（等价 CLI exit 2）
            if not (args.get("ack_batch") and args.get("confirm_batch_defeats_v9")):
                return _err(
                    "BLOCKED · adaptive_elicit dump_question_set 是 v9 deprecated 路径。"
                    "默认请用 action='next' 一题一轮 EIG 流式。"
                    "若用户**主动**坚持走 batch，同时传 ack_batch=true 与 "
                    "confirm_batch_defeats_v9=true（双 flag 二级确认）。"
                    "详见 references/handshake_protocol.md §0 + AGENTS.md §二·v9 关键约束。"
                )
            ns = _ap.Namespace(
                bazi=bazi_path,
                curves=curves_path,
                tier=tier,
                out=args.get("out"),
                current_year=cy,
                ack_batch=bool(args.get("ack_batch")),
                confirm_batch_defeats_v9=bool(args.get("confirm_batch_defeats_v9")),
            )
            with contextlib.redirect_stdout(buf):
                rc = ae.cmd_dump_question_set(ns)
            md = buf.getvalue()
            return _ok({"markdown": md, "out": args.get("out"), "_rc": rc}) if rc == 0 \
                else _err(f"dump_question_set rc={rc}")

        if action == "submit_batch":
            answers_in = args.get("answers")
            if answers_in is None:
                return _err("submit_batch requires 'answers'")
            answers_path = _ensure_path(answers_in, ".answers.json") if not isinstance(answers_in, str) \
                else answers_in
            ns = _ap.Namespace(
                bazi=bazi_path,
                curves=curves_path,
                answers=answers_path,
                out=args.get("out") or bazi_path,
                current_year=cy,
            )
            with contextlib.redirect_stdout(buf):
                rc = ae.cmd_submit_batch(ns)
            raw = buf.getvalue().strip()
            try:
                payload = json.loads(raw) if raw else {"status": "DONE"}
            except json.JSONDecodeError:
                payload = {"status": "DONE", "stdout": raw}
            payload["_rc"] = rc
            return _ok(payload) if rc == 0 else _err(f"submit_batch rc={rc}: {raw}")

        return _err(f"unknown action: {action}")
    finally:
        for p in tmp_files:
            try:
                p.unlink()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────
# Tool A6: he_pan
# ─────────────────────────────────────────────────────────────────────

@register(
    name="he_pan",
    description=(
        "合盘 4 层结构性评分（synastry · 业内极少做完整版的）。\n"
        "4 层：五行互补 + 干支互动（合冲害/三合/桃花/贵人）+ 十神互配（按关系类型）+ 大运同步度。\n"
        "支持 4 种关系类型：cooperation(合作) / marriage(婚配) / friendship(友谊) / family(家人)。\n"
        "fairness §10：婚配模式不预设双方性别，输出按结构性匹配描述。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bazis": {
                "type": "array",
                "items": {"oneOf": [{"type": "object"}, {"type": "string"}]},
                "minItems": 2,
                "description": "≥2 份 bazi（dict 或文件路径）",
            },
            "names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "对应称谓（默认 P1/P2/...）",
            },
            "rel_type": {
                "type": "string",
                "enum": ["cooperation", "marriage", "friendship", "family"],
                "description": "关系类型",
            },
            "focus_years": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "关注的公历年份列表（用于大运同步度）；默认今年-今年+10",
            },
            "out_path": {"type": "string"},
        },
        "required": ["bazis", "rel_type"],
    },
)
def tool_he_pan(args: Dict[str, Any]) -> Dict[str, Any]:
    import datetime as dt
    import he_pan as hp
    bazis = [_load_or_dict(b, f"bazis[{i}]") for i, b in enumerate(args["bazis"])]
    names = args.get("names") or [f"P{i + 1}" for i in range(len(bazis))]
    if len(names) != len(bazis):
        return _err(f"names ({len(names)}) length != bazis ({len(bazis)})")
    if args.get("focus_years"):
        focus = sorted(set(args["focus_years"]))
    else:
        cy = dt.date.today().year
        focus = list(range(cy, cy + 11))
    result = hp.build(bazis, names, args["rel_type"], focus)
    if args.get("out_path"):
        Path(args["out_path"]).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return _ok(result)


# ─────────────────────────────────────────────────────────────────────
# Tool A7: render_artifact
# ─────────────────────────────────────────────────────────────────────

@register(
    name="render_artifact",
    description=(
        "渲染交互 HTML（marked.js + Recharts + RichTooltip + details 折叠）。\n"
        "可直接塞进 Claude Artifact / 浏览器双击打开 / 微信公众号上传。\n"
        "8 条曲线（4 维 × 2 线）+ 大运分段 + 关键年份解读 + 三派分歧合并展示。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "curves": {"oneOf": [{"type": "object"}, {"type": "string"}]},
            "analysis": {
                "oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}],
                "description": "可选：含 overall / turning_points / disputes / era_narratives / dayun_reviews",
            },
            "zeitgeist": {
                "oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}],
                "description": "v7.5 · 可选：_zeitgeist_loader 输出",
            },
            "bazi": {
                "oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}],
                "description": "v7.5 · 可选：bazi（与 zeitgeist 二选一，传入会现场计算 zeitgeist + class_prior）",
            },
            "out_path": {
                "type": "string",
                "description": "HTML 输出路径（必填）",
            },
        },
        "required": ["curves", "out_path"],
    },
)
def tool_render_artifact(args: Dict[str, Any]) -> Dict[str, Any]:
    import render_artifact as ra
    curves = _load_or_dict(args["curves"], "curves")
    analysis = _load_or_dict_opt(args.get("analysis"), "analysis")
    zeitgeist = _load_or_dict_opt(args.get("zeitgeist"), "zeitgeist")
    if zeitgeist is None and args.get("bazi"):
        # 现场算 zeitgeist
        bazi_path: Optional[str] = None
        bazi_in = args["bazi"]
        if isinstance(bazi_in, str):
            bazi_path = bazi_in
        else:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".bazi.json", delete=False, encoding="utf-8"
            )
            json.dump(bazi_in, tmp, ensure_ascii=False)
            tmp.close()
            bazi_path = tmp.name
        zeitgeist = ra._compute_zeitgeist_from_bazi(bazi_path)
    html = ra.render(curves, analysis, zeitgeist)
    Path(args["out_path"]).write_text(html, encoding="utf-8")
    return _ok({
        "out_path": args["out_path"],
        "size_bytes": len(html),
        "has_analysis": bool(analysis),
        "has_zeitgeist": bool(zeitgeist and zeitgeist.get("era_windows_used")),
    })


# ─────────────────────────────────────────────────────────────────────
# Tool A8: engines_diagnostics
# ─────────────────────────────────────────────────────────────────────

@register(
    name="engines_diagnostics",
    description=(
        "返回当前 MCP server 环境的引擎/库可用性诊断（lunar-python / tyme4py / sxtwl）。"
        "用于排查为何 engine=tyme4py 不可用 / 为何真太阳时显示 fallback。"
    ),
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
)
def tool_engines_diagnostics(_args: Dict[str, Any]) -> Dict[str, Any]:
    import _engines as eng
    return _ok({
        **eng.engines_diagnostics(),
        "server_name": SERVER_NAME,
        "server_version": SERVER_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "registered_tools": [t["name"] for t in TOOLS],
    })


# ─────────────────────────────────────────────────────────────────────
# Tool B1-B3: cantian-ai/bazi-mcp 兼容别名
# ─────────────────────────────────────────────────────────────────────

@register(
    name="getBaziDetail",
    description=(
        "【cantian-ai/bazi-mcp 兼容接口】公历或八字 → 完整命局信息。\n"
        "调用本项目 solve_bazi（含三派融合用神 / 大运 / 80 年流年）。"
        "比 cantian-ai 原版多返回：strength / yongshen / wuxing_distribution / "
        "qiyun_age / dayun / liunian / true_solar_time（v8.0 含 EOT）。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "solarDatetime": {"type": "string", "description": "公历 'YYYY-MM-DD HH:MM'（cantian-ai 字段名）"},
            "lunarDatetime": {"type": "string", "description": "农历 'YYYY-MM-DD HH:MM'（cantian-ai 字段名 · 自动转公历）"},
            "gender": {"type": "integer", "enum": [0, 1], "description": "0=女, 1=男（cantian-ai 字段名 · 自动转 F/M）"},
            "eightCharProviderSect": {"type": "integer", "description": "（cantian-ai 兼容 · 已忽略，本项目用三派融合）"},
            "longitude": {"type": "number", "description": "出生地经度（° E）· v8.0 启用天文级真太阳时"},
            "orientation": {"type": "string", "default": "hetero", "description": "本项目扩展字段：hetero/homo/bi/none/poly"},
        },
    },
)
def tool_getBaziDetail(args: Dict[str, Any]) -> Dict[str, Any]:
    import solve_bazi as sb
    g = args.get("gender")
    if isinstance(g, int):
        gender = "M" if g == 1 else "F"
    else:
        gender = args.get("gender", "M")
    gregorian = args.get("solarDatetime")
    if not gregorian and args.get("lunarDatetime"):
        # 农历 → 公历
        from lunar_python import Lunar
        ld = args["lunarDatetime"].strip().replace("T", " ")
        d, t = (ld.split(" ", 1) + ["12:00"])[:2]
        y, mo, da = (int(x) for x in d.split("-"))
        hh, mm = (int(x) for x in t.split(":")[:2])
        lunar = Lunar.fromYmdHms(y, mo, da, hh, mm, 0)
        solar = lunar.getSolar()
        gregorian = (
            f"{solar.getYear():04d}-{solar.getMonth():02d}-{solar.getDay():02d} "
            f"{solar.getHour():02d}:{solar.getMinute():02d}"
        )
    if not gregorian:
        return _err("Must provide solarDatetime or lunarDatetime")
    data = sb.solve(
        pillars_str=None,
        gregorian=gregorian,
        gender=gender,
        birth_year=None,
        n_years=80,
        qiyun_age=None,
        orientation=args.get("orientation", "hetero"),
        longitude=args.get("longitude"),
        engine="lunar-python",
    )
    return _ok(data)


@register(
    name="getSolarTimes",
    description=(
        "【cantian-ai/bazi-mcp 兼容接口】八字 → 该范围内所有匹配的公历时刻。\n"
        "枚举法（lunar-python 反推），200 年窗口约 3-4 个候选。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "bazi": {"type": "string", "description": "四柱字符串 '庚午 辛巳 壬子 丁未'"},
            "gender": {"type": "string", "enum": ["M", "F"], "default": "M"},
            "year_start": {"type": "integer", "default": 1900},
            "year_end": {"type": "integer", "default": 2100},
            "max_results": {"type": "integer", "default": 8},
        },
        "required": ["bazi"],
    },
)
def tool_getSolarTimes(args: Dict[str, Any]) -> Dict[str, Any]:
    import _engines as eng
    res = eng.bazi_to_solar_times(
        args["bazi"],
        args.get("gender", "M"),
        args.get("year_start", 1900),
        args.get("year_end", 2100),
        args.get("max_results", 8),
    )
    return _ok({"candidates": res, "count": len(res)})


@register(
    name="getChineseCalendar",
    description=(
        "【cantian-ai/bazi-mcp 兼容接口】公历 → 完整中国农历信息（含农历年月日 + 干支 + 节气 + 生肖）。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "solarDatetime": {"type": "string", "description": "公历 'YYYY-MM-DD HH:MM' 或 'YYYY-MM-DD'"},
        },
        "required": ["solarDatetime"],
    },
)
def tool_getChineseCalendar(args: Dict[str, Any]) -> Dict[str, Any]:
    import _engines as eng
    return _ok(eng.gregorian_to_chinese_calendar(args["solarDatetime"]))


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _load_or_dict(x: Any, name: str) -> Dict[str, Any]:
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        return json.loads(Path(x).read_text(encoding="utf-8"))
    raise ValueError(f"{name} must be dict or filepath, got {type(x).__name__}")


def _load_or_dict_opt(x: Any, name: str) -> Optional[Dict[str, Any]]:
    if x is None:
        return None
    return _load_or_dict(x, name)


# ─────────────────────────────────────────────────────────────────────
# MCP JSON-RPC 2.0 stdio loop（零外部依赖原生实现）
# ─────────────────────────────────────────────────────────────────────

def _send(obj: Dict[str, Any]) -> None:
    """写一行 JSON 到 stdout（MCP stdio transport 是行分隔 JSON-RPC 2.0）。"""
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _log(msg: str) -> None:
    """写日志到 stderr（不影响 stdio JSON-RPC 通道）。"""
    sys.stderr.write(f"[mcp_server] {msg}\n")
    sys.stderr.flush()


def _wrap_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """跑一个 tool；异常转成 ok=false 的 content 而非 JSON-RPC error。"""
    handler = HANDLERS.get(name)
    if handler is None:
        return _err(f"Unknown tool: {name!r}", available=[t["name"] for t in TOOLS])
    try:
        return handler(args or {})
    except Exception as e:
        return _err(
            f"{type(e).__name__}: {e}",
            traceback=traceback.format_exc(limit=12),
        )


def _handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """处理一个 JSON-RPC request，返回 response（或 None 如果是 notification）。"""
    method = req.get("method")
    rid = req.get("id")
    params = req.get("params") or {}
    is_notification = "id" not in req

    # initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
                "instructions": (
                    f"{SERVER_NAME} v{SERVER_VERSION} · MCP server\n"
                    "把八字命理变成可证伪、可审计、bit-for-bit deterministic 的人生曲线。\n"
                    f"{len(TOOLS)} 个 tools 可用（含 cantian-ai/bazi-mcp 兼容别名）。"
                ),
            },
        }

    # initialized notification（客户端确认握手完成）
    if method in ("notifications/initialized", "initialized"):
        _log(f"client initialized")
        return None

    # tools/list
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": TOOLS}}

    # tools/call
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        result = _wrap_call(name, args)
        # MCP tools/call 必须返回 content[]，每项是 {type, text/...}
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": not result.get("ok", True),
            },
        }

    # ping
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}

    # shutdown / exit
    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": rid, "result": None}
    if method == "exit":
        sys.exit(0)

    if is_notification:
        return None

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {
            "code": -32601,
            "message": f"Method not found: {method}",
        },
    }


def _stdio_loop() -> None:
    """MCP stdio main loop · 行分隔 JSON-RPC 2.0。"""
    _log(f"started · {len(TOOLS)} tools registered · waiting for client on stdin")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            _send({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            })
            continue
        try:
            resp = _handle_request(req)
        except Exception as e:
            _log(f"handler exception: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id"),
                "error": {"code": -32603, "message": f"Internal error: {e}"},
            }
        if resp is not None:
            _send(resp)


# ─────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────

def _cmd_inspect() -> None:
    """诊断模式：列出所有 tools + 当前引擎可用性。"""
    import _engines as eng
    print(f"=== {SERVER_NAME} v{SERVER_VERSION} · MCP stdio server ===")
    print(f"protocolVersion: {PROTOCOL_VERSION}")
    print()
    print("--- Engines ---")
    for k, v in eng.engines_diagnostics().items():
        if isinstance(v, dict):
            mark = "✓" if v.get("available") else "✗"
            print(f"  [{mark}] {k:14s}  {v.get('role', '')}")
            if not v.get("available"):
                print(f"        install: {v.get('install', '')}")
        else:
            print(f"  {k}: {v}")
    print()
    print(f"--- Tools ({len(TOOLS)}) ---")
    for t in TOOLS:
        n_args = len((t.get("inputSchema", {}).get("properties") or {}))
        print(f"  · {t['name']:24s}  ({n_args} args)")
        first_line = (t.get("description") or "").split("\n")[0]
        if first_line:
            print(f"      → {first_line}")
    print()
    print("--- Run ---")
    print(f"  stdio:    python3 {__file__}")
    print(f"  inspect:  python3 {__file__} --inspect")
    print(f"  selftest: python3 {__file__} --selftest")


def _cmd_selftest() -> None:
    """selftest：用 examples/ 下的虚构八字跑通 5 个核心 tools。"""
    print(f"=== Self-test ===")
    examples_dir = Path(__file__).resolve().parent.parent / "examples"

    # T1: solve_bazi
    print("\n[T1] solve_bazi (pillars mode)")
    r = _wrap_call("solve_bazi", {
        "pillars": "庚午 辛巳 壬子 丁未",
        "gender": "M",
        "birth_year": 1990,
        "orientation": "hetero",
    })
    assert r["ok"], r
    bazi = r["data"]
    print(f"  ✓ pillars={bazi['pillars_str']}, 日主={bazi['day_master']}, 强弱={bazi['strength']['label']}")

    # T2: score_curves
    print("\n[T2] score_curves (inline bazi)")
    r = _wrap_call("score_curves", {"bazi": bazi, "age_end": 80})
    assert r["ok"], r
    curves = r["data"]
    print(f"  ✓ {len(curves['points'])} years, {len(curves['turning_points_future'])} future turning points")

    # T3: handshake
    print("\n[T3] handshake (build candidates)")
    r = _wrap_call("handshake", {"bazi": bazi, "curves": curves, "current_year": 2026})
    assert r["ok"], r
    h = r["data"]
    print(f"  ✓ R0={len(h['round0_candidates'])} + R1={len(h['round1_candidates'])} candidates")

    # T4: engines_diagnostics
    print("\n[T4] engines_diagnostics")
    r = _wrap_call("engines_diagnostics", {})
    assert r["ok"], r
    avail = r["data"]["available_solve_engines"]
    print(f"  ✓ available engines: {avail}")

    # T5: getChineseCalendar (cantian-ai compat)
    print("\n[T5] getChineseCalendar (cantian-ai compat)")
    r = _wrap_call("getChineseCalendar", {"solarDatetime": "1990-05-12 14:30"})
    assert r["ok"], r
    gz = r["data"]["ganzhi"]
    print(f"  ✓ 公历 1990-05-12 14:30 → 八字 {gz['year_pillar']} {gz['month_pillar']} {gz['day_pillar']} {gz['hour_pillar']}")

    print(f"\n=== ✅ All 5 tests passed · {len(TOOLS)} tools registered ===")


def main():
    ap = argparse.ArgumentParser(
        description=f"{SERVER_NAME} v{SERVER_VERSION} · MCP stdio server"
    )
    ap.add_argument("--inspect", action="store_true",
                    help="诊断模式：列出所有 tools + 引擎可用性，不启动 stdio loop")
    ap.add_argument("--selftest", action="store_true",
                    help="自检：跑通 5 个核心 tools 验证集成（用 examples/ 虚构八字）")
    args = ap.parse_args()
    if args.inspect:
        _cmd_inspect()
        return
    if args.selftest:
        _cmd_selftest()
        return
    _stdio_loop()


if __name__ == "__main__":
    main()
