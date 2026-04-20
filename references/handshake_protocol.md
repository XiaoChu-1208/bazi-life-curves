# 校验握手协议（Handshake Protocol · v8 / v8.1 两轮校验）

> v8 把校验从「R0/R1/R2/R3 自然语言转述 + 命中率」整体替换为「discriminative question bank + AskQuestion 多选 + 贝叶斯后验」。
>
> **v8.1（本文件当前版本）**新增 **Round 2 confirmation 协议**：R1 用宽口径判别题选出 top phase 后，R2 在 top phase 与 runner-up 之间挑高判别力的 confirmation 题再问一次，对照 `confirmation_threshold` 决定是出图、加 caveat 出图，还是回退核对时辰 / 性别。
>
> 旧版（v6/v7）对应文件已整段废弃。`scripts/handshake.py` 输出的 `handshake.json` schema 与旧版**不向后兼容**，旧 confirmed_facts.json 通过 `scripts/save_confirmed_facts.py` 的 schema migration 自动升级到 v8。

---

## §1 设计变化总览

| 维度 | v6/v7 | v8 |
|---|---|---|
| 轮次 | R0/R1/R2/R3 分阶段 | 统一题集 + 自适应追问 |
| 题目来源 | 按默认相位生成 | 按 `detect_all_phase_candidates` 全集生成，按 `discrimination_power` 筛选 |
| 用户接口 | 自然语言转述 → 用户口头回答"对/不对/部分" | **AskQuestion 结构化点选**（强制） |
| 决策方式 | 命中率（≥4/6 通过） | 贝叶斯后验更新 |
| 维度 | 健康 + 关系 + 交叉 + 民俗 | **5 维度**：D1 民族志/家庭、D2 关系结构、D3 流年大事件（动态）、D4 中医体征、D5 自我体感 |
| 输出字段 | round0_candidates / round1_candidates / ... | `phase_candidates` + `prior_distribution` + `questions[]` + `askquestion_payload` + `cli_fallback_prompt` |

---

## §2 v8 handshake.json schema

```json
{
  "version": 8,
  "bazi_summary": {
    "pillars": ["丙子", "庚子", "己卯", "己巳"],
    "day_master": "己",
    "gender": "female",
    "birth_year": 1996
  },
  "phase_candidates": [
    {"phase_id": "floating_dms_to_cong_cai", "label": "弃命从财", "detector_score": "4/4 (P5)"},
    {"phase_id": "day_master_dominant", "label": "默认 · 日主主导", "detector_score": "baseline"}
  ],
  "prior_distribution": {
    "floating_dms_to_cong_cai": 0.46,
    "floating_dms_to_cong_er": 0.21,
    "climate_inversion_dry_top": 0.18,
    "day_master_dominant": 0.05,
    "...": "..."
  },
  "questions": [
    {
      "id": "D1_Q3_father_presence",
      "dimension": "ethnography_family",
      "weight_class": "hard_evidence",
      "prompt": "你出生时（前后 2 年内）家里父亲在体感上的存在度是？",
      "options": [
        {"id": "A", "label": "长期在场，是家里主心骨"},
        {"id": "B", "label": "在场但权威感弱（如长期生病/经商在外）"},
        {"id": "C", "label": "缺位（早逝/离异/常年外地）"},
        {"id": "D", "label": "在场且关系紧张（高压/严厉/冲突多）"}
      ],
      "likelihood_table": {
        "day_master_dominant":         {"A": 0.40, "B": 0.25, "C": 0.15, "D": 0.20},
        "floating_dms_to_cong_cai":    {"A": 0.10, "B": 0.30, "C": 0.45, "D": 0.15},
        "floating_dms_to_cong_sha":    {"A": 0.20, "B": 0.15, "C": 0.10, "D": 0.55}
      },
      "discrimination_power": 0.34,
      "requires_dynamic_year": null
    }
  ],
  "askquestion_payload": [
    {
      "id": "D1_Q3_father_presence",
      "prompt": "...",
      "options": [{"id": "A", "label": "..."}],
      "allow_multiple": false
    }
  ],
  "cli_fallback_prompt": "请按以下编号回答（输入 D1_Q3=B 形式）：\n\nD1_Q3 你出生时...\n  A) ...\n  B) ...\n",
  "decision_threshold": {
    "auto_adopt": 0.80,
    "adopt": 0.60,
    "ask_more": 0.40
  }
}
```

---

## §3 Agent 端调用规则（硬性铁律）

### §3.1 必须用结构化点选

Agent 必须用宿主的结构化问询接口（Cursor / Claude Desktop / Claude Code 的 `AskQuestion`，或类似 UI）抛 `askquestion_payload` 全部题目。

**禁止行为**：
- ❌ 把题面用自然语言复述给用户，让用户回"对/不对/部分"
- ❌ 把多选题改成自由文本输入
- ❌ 跳过若干题只问 3-5 道（必须把 v8 question bank 里全部 ~20-25 道一次抛完）
- ❌ 在抛题前先告诉用户"我倾向你是 X 相位"（会污染答案）

### §3.2 Cursor / Claude Desktop / Claude Code 宿主

调用 `AskQuestion`，每题作为一个 question 项，options 直接传 `askquestion_payload[i].options`。一次性抛全部 N 题（不分轮）。

### §3.3 CLI / 无 AskQuestion 宿主

回退到 `cli_fallback_prompt`，逐题列出选项让用户输入 `<question_id>=<option_id>` 形式（如 `D1_Q3=B`）。

### §3.4 答案回收

收到用户答案后，调：

```bash
python scripts/phase_posterior.py \
  --bazi out/bazi.json \
  --questions out/handshake.json \
  --answers out/user_answers.json \
  --out out/bazi.json
```

`phase_posterior.py` 会：
1. 算后验 `P(phase | answers)`
2. 写回 `bazi.phase` + `bazi.phase_decision`
3. 设 `is_provisional=False`

---

## §4 Round 2 confirmation 协议（v8.1 新增）

### §4.1 为什么要两轮？

R1 是**宽口径判别**：在 18 个候选 phase 之间用 `discrimination_power(prior)` 排序选题。
R1 后验 top-1 即使 ≥ 0.80（high），仍存在「答对几道家庭题就被推到从财」的偶然命中风险——
没有第二批*独立*证据来 confirm。R2 的存在就是要拿第二批证据问一次：

- **题目挑选目标变了**：不再是 prior 加权的全局判别力，而是 **decided phase vs runner-up phase
  的 pairwise L1 区分度**（`_bazi_core.pairwise_discrimination_power`）；
- **题源排除 R1 已答过的**：避免循环喂同一类信号；
- **可生成新一批 D3 流年题**：现在只针对 decided vs runner-up 两个 phase 找预测分歧最大的年份。

### §4.2 Round 2 handshake CLI

R1 走完 `phase_posterior.py` 之后（bazi.json 已写入 `phase_decision`），跑：

```bash
python scripts/handshake.py --round 2 \
  --bazi out/bazi.json \
  --curves out/curves.json \
  --r1-handshake out/handshake.r1.json \
  --r1-answers out/user_answers.r1.json \
  --current-year 2026 \
  --out out/handshake.r2.json
```

输出 `handshake.r2.json` 字段（与 R1 不同的部分）：

```json
{
  "version": 8,
  "round": 2,
  "round1_summary": {
    "decision": "floating_dms_to_cong_cai",
    "decision_probability": 0.999,
    "runner_up": "pseudo_following",
    "runner_up_probability": 0.0001,
    "answered_question_ids": ["D1_Q1_birth_economic_condition", "D1_Q3_mother_presence", "..."]
  },
  "pairwise_target": {"a": "floating_dms_to_cong_cai", "b": "pseudo_following"},
  "questions": [/* 6-8 道 confirmation 题 */],
  "askquestion_payload": [...],
  "confirmation_threshold": {
    "confirmed": 0.85,
    "weakly_confirmed": 0.65
  }
}
```

### §4.3 Round 2 posterior + confirmation_status

R2 用户答案到位后：

```bash
python scripts/phase_posterior.py --round 2 \
  --bazi out/bazi.json \
  --r1-handshake out/handshake.r1.json --r1-answers out/user_answers.r1.json \
  --r2-handshake out/handshake.r2.json --r2-answers out/user_answers.r2.json \
  --out out/bazi.json
```

`phase_posterior.py` 在内部：
1. 单独算 R1 决策（仅 R1 答案）作为 baseline；
2. 合并 R1+R2 答案算最终决策；
3. 把两者送进 `_bazi_core.assess_confirmation()` 决策 confirmation_status；
4. 把 R2 决策写到 `bazi.phase` + `bazi.phase_decision`，并把 confirmation 快照写到 `bazi.phase_confirmation`。

### §4.4 confirmation_status → 出图行动

| 条件 | status | action | 行为 |
|---|---|---|---|
| R2 决策 == R1 决策 AND R2 prob ≥ 0.85 | `confirmed` | `render` | 直接出图 |
| R2 决策 == R1 决策 AND 0.65 ≤ R2 prob < 0.85 | `weakly_confirmed` | `render_with_caveat` | 出图但解读处加 caveat |
| R2 决策 == R1 决策 AND R2 prob < 0.65 | `uncertain` | `escalate` | 回退核对时辰 / 性别，或人工 caveat 出图 |
| R2 决策 != R1 决策 | `decision_changed` | `escalate` | **必须**报告决策反转，建议核对时辰 / 性别，或采纳 R2 决策再走一轮 R2 |

### §4.5 单轮 R1 旧阈值（fallback / 跳过 R2 时）

R2 是默认推荐路径；若 R1 后验 ≥ 0.95 且无 runner-up 竞争（runner-up < 0.02），可跳过 R2 直接出图。否则按下表：

| 后验 top-1（仅 R1） | 行动 | confidence |
|---|---|---|
| ≥ 0.95 且 runner-up < 0.02 | 可直接出图（**强烈建议仍走 R2**） | high |
| 0.60 – 0.95 | **走 Round 2 confirmation** | mid / high |
| 0.40 – 0.60 | **走 Round 2**（confirmation 阈值更高，决定是否出图） | low |
| < 0.40 | **拒绝出图**：报告"算法无法落地，请核对时辰 / 性别" | reject |

---

## §5 红线（违反任意一条 → 立即停下）

| # | 红线 | 触发 | 处理 |
|---|------|------|------|
| HS-R1 | Agent 用自然语言转述题面 | 任何 questions[i].prompt 被改写或浓缩 | 立即停下，重新走 askquestion_payload |
| HS-R2 | 跳过 < 0.40 拒判路径 | 后验 < 0.40 仍调 score_curves 出图 | 强制返回 reject 文案 |
| HS-R3 | 后验 < 0.60 没追问 / 没走 R2 就 adopt | 0.40-0.60 区间被当 mid 落地 | 强制走 Round 2 confirmation |
| HS-R4 | `is_provisional=true` 状态下出图 | render_artifact 收到 phase_decision.is_provisional=true | 拒绝渲染，要求先跑 phase_posterior |
| HS-R5 | D3 流年题踩 fairness §10 黑名单 | options 中含"升职/结婚/离职/生育/确诊"等身份标签词 | _question_bank.py 单元测试拦截，不允许进 prompt |
| HS-R6 | R2 confirmation_status=`decision_changed` 仍出图 | R2 决策与 R1 反转，但 Agent 直接渲染未报告 | 强制 escalate 文案，要求核对时辰 / 性别 |
| HS-R7 | R1 后验 < 0.95 跳过 R2 直接出图 | R1 mid/low 区间未走 confirmation 即渲染 | 强制走 Round 2 |

---

## §6 5 个维度的设计原则（详见 [discriminative_question_bank.md](discriminative_question_bank.md)）

- **D1 · 民族志 × 原生家庭**（hard_evidence，权重 2×）：结合 [era_windows_skeleton.yaml](era_windows_skeleton.yaml) 出生年代 + 父母推算年代 → 家庭画像 prior。问父母在场 / 经济状况 / 兄弟姐妹 / 出生地等客观事实。
- **D2 · 关系结构**（soft_self_report，权重 1×）：升级旧 R0，问能量流向 / 进入方式 / 被吸引对象画像。
- **D3 · 流年大事件**（hard_evidence，权重 2×，**动态**）：跨候选 phase 跑 score_curves 找最分歧年份，套 4 档选项问"X 岁那年体感方向"。严守 [fairness_protocol.md](fairness_protocol.md) §10。
- **D4 · 中医体征**（hard_evidence，权重 2×）：寒热 / 睡眠 / 脏腑 / 体型 / 食欲 / 情志六问。
- **D5 · 自我体感**（soft_self_report，权重 1×）：本性画像兜底，少量。

每维度 ≥ 4-6 题，硬体征（D1/D3/D4）权重 2× 软自述（D2/D5）。

---

## §7 与下游的接口契约（两轮校验闭环）

```
solve_bazi.py        → bazi.json（含临时 phase_decision，is_provisional=true）
score_curves.py      → curves.json（按 bazi.phase.id 走 apply_phase_override）
handshake.py R1      → handshake.r1.json（22 静态 + 4 动态题）
[Agent AskQuestion R1] → user_answers.r1.json
phase_posterior.py R1 → bazi.json（写入 R1 phase_decision，is_provisional=false）
handshake.py --round 2 → handshake.r2.json（基于 R1 决策的 6 道 confirmation 题）
[Agent AskQuestion R2] → user_answers.r2.json
phase_posterior.py --round 2 → bazi.json（写入 R2 phase_decision + phase_confirmation）
            ↓
     confirmation_status:
       confirmed       → render_artifact.py
       weakly_confirmed → render_artifact.py（解读 caveat）
       uncertain       → escalate（核对时辰 / 性别）
       decision_changed → escalate（必须报告反转）
```

- `scripts/save_confirmed_facts.py --round r2 --r1-handshake ... --r1-answers ... --r2-handshake ... --r2-answers ...` 在背后做同样的两轮事 + 写 `confirmed_facts.json`（按 round 分桶；保留人类可读 trace）
- `scripts/score_curves.py` 默认读 `bazi.phase.id` 走 `apply_phase_override`
- `scripts/render_artifact.py` 读 `bazi.phase_decision` + `bazi.phase_confirmation` + 各曲线 → 出图（confirmation=weakly_confirmed 时加 caveat）

---

## §8 旧 R0/R1/R2/R3 的迁移

- 旧 R1（健康三问）→ D4 维度题库（扩展到 6 题）
- 旧 R0（感情画像）→ D2 维度题库（升级为多选）
- 旧 R2（本性 + 历史锚点）→ 拆分到 D5（本性）+ D3（历史锚点改为流年题）
- 旧 R3（family / folkways）→ D1 维度题库（结合 era_windows_skeleton）
- 旧 `evaluate_responses` 命中率函数 → 完全移除，由 `decide_phase` 后验更新代替
