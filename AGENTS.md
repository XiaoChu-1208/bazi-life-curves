# AGENTS.md · 给 AI 编码代理的项目导航

> 本文件遵循 [agents.md](https://agents.md/) 通行约定，被 Cursor / Claude Code / OpenAI Codex CLI / Aider / Continue / Devin 等 AI Coding Agent 自动读取。
> 如果你是人类开发者，请直接读 [README.md](README.md)；如果你是 AI 助手，从这里开始。

---

## 一、项目是什么

`bazi-life-curves` 是一个把中国传统八字命理（Four Pillars of Destiny / 子平命理）量化成**可证伪、可审计、可回测、bit-for-bit deterministic** 的人生曲线引擎。它不是 LLM 包装层 —— **打分由确定性 Python 脚本完成**，LLM 只负责把 JSON 翻译成大白话解读。

- 语言：Python 3.10+
- 入口：`scripts/` 下 12 个独立 CLI 脚本，按 pipeline 顺序运行
- 产物：`output/curves.json` + `output/chart.html` + 流式 markdown 解读
- Skill 接入：`SKILL.md` 是 Claude / Cursor Skill 主定义（YAML frontmatter）

---

## 二、Pipeline 标准流程（不要跳步）

```
solve_bazi.py                  # 解析八字（含起运岁精算 + --orientation 取向 + --longitude 真太阳时）
    ↓ output/bazi.json
score_curves.py                # 4 维曲线打分（spirit/wealth/fame/emotion · 80 年）
    ↓ output/curves.json
mangpai_events.py              # 盲派事件检测 + 反向规则 + 护身减压（可选 · score_curves 已内置基础调用）
    ↓ output/curves.json (events 字段)
adaptive_elicit.py next        # v9 · 自适应贝叶斯单题流式问答（默认 R1 路径）
    ↓ 循环 ASK → AskQuestion 单题 → answer → ASK ...
    ↓ 触发 S1/S2/S3/S4 早停（通常 5-8 题，最多 12 题；prior top1 ≥ 0.85 直接 0 题 fast-path）
    ↓ output/.elicit.state.json   # 内含 posterior / asked_history（点开头隐藏 · LLM 不得回灌）
    ↓ output/bazi.json            # bazi.phase + bazi.phase_decision（is_provisional=false）
[可选 batch 通道]
adaptive_elicit.py dump-question-set --tier core14|full28
    → 用户贴题集 markdown 一次答完
adaptive_elicit.py submit-batch
    → output/bazi.json（confidence 默认上限 mid · top1≥0.97 才解锁 high）

[deprecated v9] handshake.py (round 1)  # v8 一次性 26 题路径，仅 he_pan_orchestrator/mcp_server 兜底
    ↓ output/handshake.r1.json [deprecated_v9: true · askquestion_payload 已剥离后验]
[Agent 调宿主 AskQuestion 抛点选 UI → 用户答案 → user_answers.r1.json]
phase_posterior.py (round 1)   # v8 · 贝叶斯后验更新（兼容路径）

handshake.py --round 2         # v9 · 基于 R1 决策的 EIG 选题 confirmation（限定 2-phase 后验）
    ↓ output/handshake.r2.json # 含 round1_summary + pairwise_target + 6-8 道 confirmation 题
[Agent 调宿主 AskQuestion 抛 R2 题 → user_answers.r2.json]
phase_posterior.py --round 2   # v8.1 · 合并 R1+R2 算最终后验 + confirmation_status
    ↓ output/bazi.json         # bazi.phase / phase_decision / phase_confirmation
[save_confirmed_facts.py --round r2 --r1-* --r2-* 写回 confirmed_facts.json（按 round 分桶）]
    ↓ output/confirmed_facts.json
render_artifact.py             # 交互 HTML（Recharts + marked.js）·
                               #   confirmation=weakly_confirmed 时解读自动加 caveat
    ↓ output/chart.html

[deprecated] phase_inversion_loop.py  # v7 老路径，保留可运行但不再是主流程
```

**关键不可跳步（v9）**：

- **R1 默认路径必须走 `adaptive_elicit.py next`**，不要再用 `handshake.py` 默认入口（已 deprecated_v9）
- 不能跳过 R1 elicit + 必要时的 R2 confirmation 直接渲染 HTML —— `bazi.phase_decision.is_provisional=true` 时 render_artifact 必须拒绝
- **Agent 必须用宿主结构化 `AskQuestion` 抛 `askquestion_payload`，禁止用自然语言转述题面让用户口头回答**（违反 = 破坏 phase 决策的 likelihood 计算前提）
- **第一次抛单题前必须给用户 [batch_elicitation_prompt.md](references/batch_elicitation_prompt.md) §1 开场白**（介绍 batch 通道）
- **不得把 `.elicit.state.json` / `posterior` / `phase_candidates` 等内部字段呈现或转述给用户**（[elicitation_ethics.md](references/elicitation_ethics.md) §E1）；不得在 elicit 中途命名 phase（§E2）；不得倒推进度（§E3）；不得揭示题目意图（§E4）
- **R1 后验 < 0.95 或 runner-up ≥ 0.02 时必须走 Round 2 confirmation**（详见 [handshake_protocol.md §4](references/handshake_protocol.md) HS-R7）
- **R2 confirmation_status=`decision_changed` 时必须 escalate 报告决策反转，不允许直接出图**（HS-R6）
- 不能让 LLM 自己改 `curves.json` 的数值 —— 那是 `score_curves.py` 的职责
- 不能在 `solve_bazi.py` 之外推导八字 —— 起运岁、真太阳时、orientation 全部依赖该脚本
- 后验 < 0.40 → **拒绝出图**，提示用户复核时辰 / 性别（详见 [phase_decision_protocol.md](references/phase_decision_protocol.md) §5）

---

## 三、目录结构

```
bazi-life-curves/
├── SKILL.md                       # Claude/Cursor Skill 主定义（看这个理解端到端工作流）
├── README.md                      # 用户视角总览
├── USAGE.md / INSTALL.md          # 速览与安装
├── AGENTS.md                      # 本文件
├── llms.txt                       # LLM 检索入口（简化版导航）
├── CITATION.cff                   # 学术引用元数据
├── PLAN_zeitgeist_folkways.md     # 时代风气 / 民俗修正设计文档
├── requirements.txt               # 依赖：lunar-python / matplotlib / PyYAML / Jinja2
├── scripts/                       # 12 个核心脚本
│   ├── _bazi_core.py              # 干支/五行/十神/互动/化气格/神煞底层（不要直接 CLI）
│   ├── solve_bazi.py              # 入口 1
│   ├── score_curves.py            # 入口 2
│   ├── mangpai_events.py          # 入口 3（可选）
│   ├── adaptive_elicit.py         # 入口 4（必跑）· v9 自适应贝叶斯单题流式 + batch 双通道
│   ├── _eig_selector.py           # v9 EIG 算法核心（pure function · 4 条早停）
│   ├── handshake.py               # 入口 4 兼容（deprecated R1 + EIG-based R2 confirmation）
│   ├── phase_posterior.py         # 入口 4.5 · v8 用户答案 → 贝叶斯后验 → 落地 phase
│   ├── _question_bank.py          # v8 5 维度 28 题 dataclass（与 references/discriminative_question_bank.md 1:1）
│   ├── audit_questions.py         # v9 题库可答性 / 中性度静态审计（8 维 ambiguity + 命理词典）
│   ├── phase_inversion_loop.py    # [deprecated v8] 老 R0/R1/R2 反演路径，保留可运行
│   ├── save_confirmed_facts.py    # 校验反馈固化（v8 加 --user-choices 参数 + schema migration）
│   ├── family_profile.py          # [legacy] 旧 R3 原生家庭，逻辑已迁入 D1 题库
│   ├── render_chart.py            # 静态 PNG
│   ├── render_artifact.py         # 交互 HTML
│   ├── he_pan.py                  # 合盘评分
│   └── calibrate.py               # 历史回测
├── references/                    # 13 个学理/协议文档（修改算法前必读对应协议）
├── examples/                      # 2 套完整产物（官印相生格 / 伤官生财格）
├── templates/chart_artifact.html.j2
├── calibration/                   # dataset.yaml + thresholds.yaml
└── output/                        # 用户运行产物（gitignore 屏蔽，含真实八字）
```

---

## 四、修改算法时的硬性约束

### 4.1 任何打分规则的改动 → 必须更新对应协议文档

| 修改文件 | 必须同步更新 |
|---|---|
| `score_curves.py` 的扶抑/调候/格局权重 | `references/methodology.md` + `references/scoring_rubric.md` |
| `mangpai_events.py` 的事件 / 反向 / 护身 | `references/mangpai_protocol.md` |
| `adaptive_elicit.py` / `_eig_selector.py` 的选题 / 早停 / state schema | `references/handshake_protocol.md` §0 (v9) + `references/elicitation_ethics.md` |
| `handshake.py` 的 R2 confirmation 题（deprecated R1 也在此）| `references/handshake_protocol.md` (v8 / §4 v8.1 + v9 §0) |
| `_bazi_core.py` 的 detector / decide_phase / pairwise_discrimination_power / assess_confirmation | `references/phase_decision_protocol.md` (v8 / §7 v8.1) + `references/diagnosis_pitfalls.md` §14 |
| `_question_bank.py` / `references/discriminative_question_bank.md` 题目 / likelihood_table | 两边必须 1:1 同步；calibrate.py 做一致性检查 |
| `phase_posterior.py` 后验阈值 / R1 决策规则 / R2 confirmation_status | `references/phase_decision_protocol.md` §5 / §7 |
| `he_pan.py` 的 4 层评分 | `references/he_pan_protocol.md` |
| 任何涉及性别 / 取向 / 关系结构的改动 | **必须**先读 `references/fairness_protocol.md §9-§10`，违反会破坏现代化承诺 |

### 4.2 古籍出处铁律

新加任何"机制 / 规则 / 应事 / 反向"，**必须**在协议文档同步加古籍出处（《滴天髓阐微》《子平真诠》《穷通宝鉴》《三命通会》《子平粹言》或现代盲派师承）。**禁止**自创无源规则。

### 4.3 现代化解读铁律（fairness_protocol §10）

- ❌ "克夫" / "旺夫" / "妨夫" / "妨妻" 等措辞
- ❌ "配偶星弱 = 单身 = 差" / "女命印多 = 重事业 = 感情位次靠后" 等价值判断
- ❌ "男看财 / 女看官" 的语言（结构识别可保留，但解读层必须用 `--orientation` 决定的中性表述）
- ✅ 必须使用 `relationship_mode` 7 种中性描述：outward_attractive / competitive_pursuit / nurture_oriented / ambiguous_dynamic / low_density / balanced / self_centered
- ✅ 每次 emotion 解读首段必须强制声明：「命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育」

### 4.4 Bit-for-bit deterministic 铁律

任何 PR 必须通过：

```bash
diff <(python scripts/score_curves.py --bazi examples/guan_yin_xiang_sheng.bazi.json --strict | sha256sum) \
     <(python scripts/score_curves.py --bazi examples/guan_yin_xiang_sheng.bazi.json --strict | sha256sum)
# 必须输出空（同输入 100 次 100 个 byte-equal 结果）
```

不允许引入：随机 seed / 时间戳 / 字典遍历顺序依赖 / set 序列化。

### 4.5 LLM 后视镜归因防御铁律

任何接受用户输入的脚本（`adaptive_elicit.py` / `handshake.py` / `save_confirmed_facts.py`）**必须**：

- 拒绝 "我 X 岁升职 / 我已婚 / 我离婚 / 我读了 X 大学" 这类**带具体身份标签**的事实
- 只接受 "我 X 岁那年财务有大波动（涨/跌）" 这类**结构性事实**
- 写回 `confirmed_facts.json` 时强制脱敏字段名

---

## 五、运行 / 测试

### 5.1 一键端到端跑两个示例（验证你没改坏）

```bash
mkdir -p output

python scripts/solve_bazi.py --pillars "甲子 丁卯 丙寅 戊戌" --gender M --birth-year 1984 --orientation hetero --qiyun-age 8 --out output/test1.bazi.json
python scripts/score_curves.py --bazi output/test1.bazi.json --out output/test1.curves.json --age-end 80
# v9 默认：自适应单题流式（循环到 finalize；非交互测试可改用 batch）
python scripts/adaptive_elicit.py next --bazi output/test1.bazi.json --curves output/test1.curves.json --state output/.test1.elicit.state.json
# 或 batch 模式：导出 → 填答 → 提交
python scripts/adaptive_elicit.py dump-question-set --bazi output/test1.bazi.json --curves output/test1.curves.json --tier core14 --out output/test1.questions.md
# [...用户填答 → 写到 output/test1.answers.json...]
# python scripts/adaptive_elicit.py submit-batch --bazi output/test1.bazi.json --answers output/test1.answers.json
python scripts/render_artifact.py --curves output/test1.curves.json --out output/test1.html
```

### 5.2 历史回测

```bash
python scripts/calibrate.py
# 期望输出：spirit_recall ≥ 0.70, wealth_recall ≥ 0.75, fame_recall ≥ 0.65, fp_rate ≤ 0.15
```

### 5.3 性别对称性自检（fairness_protocol 强制要求）

同八字翻转性别（M→F / F→M），spirit/wealth/fame 三维必须 byte-equal；只有 emotion 因配偶星识别可不同。

---

## 六、依赖管理

- 仅允许添加广泛使用、有积极维护的库
- 添加新依赖必须在 `requirements.txt` 用 `>=` 写最低版本
- **禁止**引入：torch / tensorflow / 任何大模型 SDK（保持工具轻量、可在 CPU 跑 < 5 秒完成）

---

## 七、PR / Issue 规范

- PR 标题格式：`[scripts/score_curves] 添加化气格 phase override`
- 任何打分逻辑改动必须附：
  - 古籍出处引文
  - 至少 1 个 `examples/` 下的回归对比
  - `calibration/` 跑分变化（recall / fp_rate）
- 不接受 "感觉这样准" 类无脚本可重现的 issue

---

## 八、我（AI agent）应该如何回答用户

### 当用户问"算个八字"

1. 先用 `solve_bazi.py` 解析（询问性别 + 公历生辰 + 取向）
2. 跑 `score_curves.py`
3. **R1（v9 默认）**：跑 `adaptive_elicit.py next` 进入自适应单题流式
   - 第一次抛题前必须按 [batch_elicitation_prompt.md](references/batch_elicitation_prompt.md) §1 给用户开场白（介绍 batch 通道）
   - 用户若选 batch：跑 `dump-question-set --tier core14|full28` 把题集贴回 → 用户填答 → `submit-batch`
   - 用户若选流式：每轮调宿主 AskQuestion 抛 `askquestion_payload` 单题，回答后 `--answer 'qid:opt'` 进下一轮
   - 全程**禁止**把 `posterior` / `phase_candidates` / `EIG` 转述给用户，**禁止**在 finalize 前命名 phase（[elicitation_ethics.md](references/elicitation_ethics.md) §E1–§E4）
4. R1 finalize 后 `bazi.json` 直接写入 `phase` + `phase_decision`，不需要单独跑 `phase_posterior.py --round 1`
5. **R2**（仅在 R1 confidence < high 或想再次确认时）：跑 `handshake.py --round 2`（EIG 选 confirmation 题）→ AskQuestion 抛 → `phase_posterior.py --round 2`
6. 看 `phase_confirmation.action`：`render` / `render_with_caveat` 直接出图；`escalate` 时**必须**报告决策反转或不确定，建议核对时辰 / 性别
7. 用 `render_artifact.py` 出 HTML，或按 `multi_dim_xiangshu_protocol.md` 流式输出 markdown 解读

### 当用户问"我 X 年怎么样"

读 `output/curves.json` 的 `points[X]` 字段，按 `prediction_protocol.md` 强制输出"推论过程 + 可证伪点"格式。**禁止**直接说"X 年好/坏"。

### 当用户问"跟 Y 合不合"

跑 `he_pan.py`，按 `he_pan_protocol.md` 4 层评分（合作 / 婚配 / 友谊 / 家人）输出。

### 当用户告诉你"我 31 岁升职了，命局对吗"

**红线**：不要立刻"哦命局应验了"。按 `accuracy_protocol.md` 走身份盲化路径，用 `save_confirmed_facts.py` 只把"31 岁财务/事业有正向波动"写入，**禁止**写入"升职"这种带身份的标签。

---

## 九、版本与演进

当前主版本：v7.4（2026-04）

- v7：现代化语言重构 + LGBTQ+ 包容
- v7.1：P5 三气成象 / 假从真从 detect
- v7.2：相位反演 Auto-Loop + 真太阳时 + confirmed_facts 持久化
- v7.3：R3 原生家庭反询问
- v7.4：化气格 + 神煞 + R0' 反迎合反向探针

详见 `references/phase_inversion_protocol.md §9` 版本时间表。
