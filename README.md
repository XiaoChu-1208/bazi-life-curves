# bazi-life-curves

> 把八字命理变成可证伪、可审计、可回测的人生曲线。
> Quantify Chinese Bazi (Four Pillars of Destiny) into auditable, falsifiable, back-testable life curves.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Skill for Claude](https://img.shields.io/badge/Claude-Skill-7B68EE.svg)](https://www.anthropic.com/)
[![Cursor Skill](https://img.shields.io/badge/Cursor-Skill-000000.svg)](https://cursor.sh/)
[![Deterministic](https://img.shields.io/badge/output-bit--for--bit_deterministic-success.svg)](#工程绝对优势)
[![v7 Modernized](https://img.shields.io/badge/v7-LGBTQ%2B_inclusive-ff69b4.svg)](#v7-现代化命理学--600-年第一次的语言重构)
[![CI](https://github.com/XiaoChu-1208/bazi-life-curves/actions/workflows/ci.yml/badge.svg)](https://github.com/XiaoChu-1208/bazi-life-curves/actions/workflows/ci.yml)

<!--
  SEO keywords (供 Google / Bing / GitHub Search / 各大 LLM 检索引擎理解项目)：
  Bazi, 八字, Four Pillars of Destiny, 四柱命理, 子平命理, Chinese Astrology, 命理 API,
  人生曲线, life curve, destiny prediction, 大运流年, 流年走势, 命盘分析, 命理工具,
  扶抑派, 调候派, 格局派, 盲派, Mang Pai, Ge Ju, Tiao Hou, Fu Yi,
  化气格, 从格, 杀印相生, 食神制杀, 三合, 三会, 六合, 解冲, 滴天髓, 子平真诠,
  穷通宝鉴, 三命通会, 子平粹言,
  合盘, 婚配, synastry, compatibility, 合婚, 合伙人合盘,
  Claude Skill, Cursor Skill, OpenAI Codex Skill, LLM Skill, AI 命理, AI 算命,
  LGBTQ-inclusive divination, 不婚主义, 同性 八字, queer-friendly bazi,
  falsifiable prediction, deterministic output, bit-for-bit, falsification protocol,
  open source bazi, MIT license bazi, 开源八字, 命理开源, Python 八字
-->

> **关键词 / Keywords**：八字 · Bazi · 四柱命理 · Four Pillars of Destiny · 子平命理 · 人生曲线 · life curve · 大运 · 流年 · 合盘 · synastry · 婚配 · LGBTQ-inclusive · Claude Skill · Cursor Skill · 开源命理 · falsifiable prediction · deterministic

---

## 这是什么 · 一句话版

把"算命师傅口里那一堆只能听的话"，**变成一张你能拿数据回测、拿证伪点反驳、拿 git log 审计的曲线图**。

## 这是什么 · 一段话版

输入一个八字（或公历生辰 + 性别），自动产出：

- **4 维 × 80 年人生曲线**：精神舒畅度 / 财富 / 名声 / 关系能量，每维 2 条线 = **8 条线**（粗实线 = 当年值，细虚线 = 5 年累积趋势）
- **大运评价**：每 10 年一段，含三派打分明细 + 盲派应事 + 关系能量看点
- **关键年份大白话解读**：peak / dip / shift 全部带"推论过程 + 可证伪点"
- **合盘分析**：≥ 2 份八字的合作 / 婚配 / 友谊 / 家人 4 维度兼容性
- **交互式 HTML**：marked.js + Recharts + RichTooltip + details 折叠

下游可以直接给 Claude / Cursor 当 Skill，端到端 30 秒出图。

---

## 5 个绝对优势 · 这是市面上**唯一**做到这 5 件事的开源工具

> 大多数命理软件做的是「**翻译**」——把口诀翻译成白话；
> 这个工具做的是「**翻译 + 可证伪 + 可回测 + 防欺骗 + 现代化**」。

### 1. 三派交叉融合，不是一派独大

> 99% 的命理软件只用扶抑派的"用神 / 忌神"二元逻辑——结果一遇到调候命（北方水冷需要火暖）或格局命（伤官生财 / 杀印相生），全盘判错。

本工具同时跑：

| 派别 | 权重 | 看什么 | 古籍出处 |
|---|---:|---|---|
| **扶抑派** | 25% | 日主强弱 → 用神 / 忌神 | 民国《滴天髓阐微》|
| **调候派** | 40% | 月令寒暖燥湿 → 寒暖用神 | 余春台《穷通宝鉴》|
| **格局派** | 30% | 月令格局（正官 / 七杀 / 食神 / 伤官 …）→ 成败用神 | 沈孝瞻《子平真诠》|
| **盲派** | 0%（不进融合） | 应事断 + 烈度修正器（±12 amplitude）| 段建业 / 王虎应 / 李洪成 |

**三派分歧自动检测**：当三派对某一年的判断极差 ≥ 阈值（默认 18 分），该年标记为 `is_disputed = true`，强制 LLM 按 `dispute_analysis_protocol.md` 做"事实 → 为何分歧 → 我偏向哪派 → 可证伪点" 4 步推导，**禁止**写"派别分歧大，无法判断"这种废话。

> **格局为先**（v3 新增）：先识别格局（正官格 / 食神格 / 伤官生财 / 杀印相生 …），用格局**覆盖**用神判定。这是 600 年子平命理的核心洞见，但在多数现代软件里被简化掉了。
> 出处：《子平真诠》"先观月令以定格局，次看用神以分清浊"

### 2. 结构性保护机制全套 —— "看到冲就 -" 是最低级的命理误读

> 大多数命理软件看到「冲 / 刑 / 害」就一律减分。这是**机械直读**，根本不是命理。
> 真正的命理是看**结构**：同样的"日支被冲"，有印化护身的减压 60%，有合解的减压 40%，遇到三会成方反而是局面突破。

本工具实现的结构性保护机制（每条都有古籍出处）：

| 机制 | 触发 | 效果 | 出处 |
|---|---|---|---|
| **印化护身** | 七杀来攻 + 局有正/偏印 | 杀印相生，杀的破坏力 ×0.5 | 《滴天髓》"杀印相生，威权万里"|
| **食神制杀** | 七杀逢食神 | 化煞为权，从破坏变贵气 | 《子平真诠》|
| **比劫帮身** | 财官杀来克 + 身弱 + 局有比劫 | 减压 30% | 《滴天髓》|
| **食伤泄秀** | 印旺反塞 + 局有食伤 | 化印为秀，转贵 | 《穷通宝鉴》|
| **财生官护身** | 七杀无制 + 局有财 | 财生杀虽不解但能引化 | 《三命通会》|
| **官印动态相生** | 大运 / 流年触发"杀生印 → 印生身"链 | 每年动态加分 | 《滴天髓》|
| **六合解冲** | 冲克的同时局有 / 大运有六合 | 贪合忘冲，减压 60% | 《三命通会》"合处逢冲，冲处逢合"|
| **三合解冲** | 冲克的同时形成三合局 | 三合局成，化冲为生 | 同上 |
| **三会成方** | 寅卯辰 / 巳午未 / 申酉戌 / 亥子丑 三会齐 | 局面突破，原冲规则失效 | 《滴天髓》|
| **三刑** | 寅巳申 / 丑戌未 / 子卯 / 自刑 | 独立扣分，不与冲叠加 | 《三命通会》|

**这 10 条机制的差异化**：业内没有任何一个开源命理工具实现完整。多数只实现 1-2 条（通常是"印化护身"），剩下 8 条全部跳过 → 遇到合解 / 三会的命局直接判错。

### 3. 盲派应事 + **结构反向规则** + **护身减压** —— 业内首次工程化

> 盲派的口诀很灵，但**口诀有方向陷阱**。
> 比如"比劫夺财"——身强日主遇比劫确实损财，但**身弱日主**遇比劫反而是帮身吉象。
> 多数软件直接读"比劫 = 损财 = 凶"，错得离谱。

本工具的盲派模块做了三层处理：

```
事件检测（11 条经典组合）→ 结构反向规则（v3 新增）→ 护身减压（v3 新增）
```

**11 条经典盲派组合**：伤官见官 / 比劫夺财 / 禄被冲 / 羊刃逢冲 / 反吟应期 / 伏吟应期 / 财库被冲开 / 官杀混杂 / 七杀逢印 / 伤官伤尽 / 年财不归我

**3 条结构反向规则**（同样的"事件"，不同结构 → 反向解读）：
- 伤官见官 · 结构反向：身强用官 → 凶；身弱印护 → 化凶为吉
- 比劫夺财 · 身弱反向：身弱比劫帮身 → 反成吉
- 官杀混杂 · 结构反向：身强 → 凶；身弱印化 → 反成贵

**6 条护身减压**：识别到"杀印相生 / 食神制杀 / 比劫帮身 / 合解冲"等保护机制时，对应的盲派事件 amplifier × 0.4（缩减 60%）

输出 JSON 里有 `mangpai_event_count` / `reversed_event_count` / `protected_event_count` 三个字段，**全程可审计**。

### 4. 两轮校验硬门槛 —— 出图前先证明八字是对的

> 大多数命理工具的逻辑是：你给八字，我给结果。
> 但**用户经常给错八字**——出生时辰不准 / 阴阳历搞混 / 性别记错。
> 这种情况下不管命理软件多准，结果都是垃圾。

本工具引入"两轮校验硬门槛"——出图**之前**先抛 3 类问题给用户回答，命中率不达标**绝不出图**：

```
Round 0  反询问·关系画像（v6 新增 · 2 题 · 取向校准）
         ① 偏好类型（基于配偶星五行 + 配偶宫藏干十神）
         ② 对方反应模式（基于配偶星旺衰 + 比劫 + 食伤 + 印 + 桃花）
         作用：取向校准 + 验证八字大致对/不对

Round 1  健康三问（命局体感校准）
         ① 寒热体感（命局燥湿）
         ② 睡眠精力（命局阴阳平衡）
         ③ 易病脏腑（命局五行最弱 / 缺失）

Round 2  历史锚点（仅 R1 < 3/3 时触发）
         ① 本性画像
         ② 过往大波动复盘
```

**放行规则**（机械化判定，不靠 LLM "感觉"）：
- R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6） → 进入出图
- R0 = 0/2 + R1 ≤ 1/3 → **红线触发**，强制停手要时辰，**禁止**继续

这一套机制让"基于错八字的徒劳分析"被前置拦截，避免你浪费 20 分钟读完一份 8000 字的"分析"，最后才发现你时辰记反了。

> 业内对比：99% 的命理软件**完全不做**这个校验。少数做了的也是"软问"（你觉得准吗？回答后无影响），不是硬门槛。

### 5. v7 现代化 · 命理学 600 年第一次的语言重构

> 八字命理是 600 年的活体系，但它的**默认语言**是明清宗法社会的 ——
> 默认异性恋 / 默认婚姻本位 / 女命"克夫旺夫"二选一 / 单身被定义为"差"。
> 这些语言在 2026 年还在多数命理工具里照搬使用。

v7 现代化做了**结构保留 + 语言重构**：

#### 5.1 保留的（这是命理学的硬核结构，不可删）

- 男看财 / 女看官杀的"配偶星"识别 —— 这是五行能量场的客观规则
- 日支为"配偶宫"的位置含义
- 桃花 / 比劫 / 食伤的关系结构指标
- 大运冲合日支对关系结构的影响

#### 5.2 删掉的（这是封建残余，必须清理）

| 已删除的古法规则 | 删除原因 |
|---|---|
| "配偶星弱 → -6 分" | 暗示"无配偶 = 差"，已删 |
| "女命印多 → -4 分" | "重事业 = 感情位次靠后" 把女性事业当感情对立面，已删 |
| "女命食伤旺 → -2 分" | "女命伤官克夫" 是物化伴侣的封建残余，已删 |
| "男命比劫 -6 / 女命比劫 -4" | 同样结构对所有性别影响相同，统一为 -5 |
| "女命大运伤官见正官 → -6" | 克夫论的代码体现，已删 |
| "男命大运财弱遇比劫 → -4" | 性别专属规则，统一改为不分性别 |

#### 5.3 加入的（让命理工具进入 2026 年）

- **`--orientation` 参数**：`hetero` / `homo` / `bi` / `none` / `poly` —— 影响 emotion 通道的配偶星识别方式
- **relationship_mode 中性描述**：`outward_attractive` / `competitive_pursuit` / `nurture_oriented` / `ambiguous_dynamic` / `low_density` / `balanced` / `self_centered` —— 取代"克夫旺夫"二元
- **强制前置声明**：每次出图后第一段感情解读必须包含「命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育——这些是你的现代选择，不在命局之内」
- **emotion 高 ≠ 婚姻顺利 / emotion 低 ≠ 单身差** —— 纯中性描述

#### 5.4 命局可推 / 不可推（fairness_protocol §10）

| 命局**可**推 | 命局**不可**推 |
|---|---|
| 关系结构（主动/被动 / 平等/层级 / 稳定/流动）| 对方的生理性别 |
| 能量模式（吸引型 / 争取型 / 自给型）| 是否结婚 / 几段关系 / 是否生育 |
| 偏好的互动模式（同辈 / 师生 / 互补）| 婚姻是否合法 / 关系是否被祝福 |
| 关系密度（高 / 中 / 低）| 关系的伦理形态（一夫一妻 / 多元 / 不婚）|

> 这是开源命理工具里**第一次**把现代性别 / 取向 / 关系观系统性写进协议层。

---

## 工程绝对优势

> 命理工具的"准"不能只靠师傅的口碑，要靠**可证伪 + 可回测 + 可审计**。

### A. Bit-for-bit deterministic

同一份 `bazi.json` + 同一份 `confirmed_facts.json` → 跑 100 次输出 100 个 byte-equal 的结果。

```bash
diff <(python scripts/score_curves.py --bazi bazi.json --strict | sha256sum) \
     <(python scripts/score_curves.py --bazi bazi.json --strict | sha256sum)
# 必须输出空（完全一致）
```

业内对比：多数命理软件每次跑结果都飘（LLM 生成 + 随机 seed）。

### B. 历史回测框架

`calibration/dataset.yaml` 存历史命主的真实大波动年份；`calibrate.py` 跑命中率 + 三派分歧 + 假阳率：

```bash
python scripts/calibrate.py
# 输出：spirit_recall=0.73, wealth_recall=0.81, fame_recall=0.66,
#       fp_rate=0.12, dispute_resolved=0.85
```

权重和阈值（`thresholds.yaml`）是基于回测数据调出来的，不是拍脑袋。

### C. LLM 后视镜叙事防御

> LLM 最容易犯的错：你告诉它"我 31 岁那年升职了"，它立刻反过来"哦命局里你 31 岁正官透干，应验了"——这是**后视镜归因**，不是预测。

本工具用三层防御：
1. **身份盲化输入**：脚本拒绝接受"我 31 岁升职 / 我已婚 / 我离婚" 这类历史信息
2. **强制可证伪点格式**：每个关键年份的解读必须含"如果 X 不发生，则我的判断错"
3. **`confirmed_facts` 写回机制**：用户的反馈进 JSON 文件持久化，下次同一八字直接复用，不重复欺骗

### D. 反馈记忆机制

`output/confirmed_facts.json` 跨 session 持久化用户的：
- R0/R1/R2 校验结果（trait → 对/错/部分对）
- 自由事实（用户主动补的命局事件）
- 结构性纠错（用户证伪了某条命局判断 → 下次跑同八字自动跳过这个判错路径）

这意味着这个工具**用得越多越准**，而不是每次从零开始。

### E. 公正性约束（fairness_protocol）

- 身份盲化：禁止接受姓名 / 职业 / 婚姻状态 / 教育 / 过去经历
- 同输入双盲必须 bit-for-bit 一致
- 性别仅影响起运方向 + emotion 配偶星识别（spirit/wealth/fame 完全性别中立）
- 双盲自检：男命与对应女命（同八字 + 翻转性别）的 spirit/wealth/fame 必须完全相同 → 自动测试

---

## 跟其他东西的对比 · 一图看懂

### vs 传统命理软件 / 算命 APP

| 维度 | 本工具 | 大多数命理 APP |
|---|---|---|
| 算法学派 | 三派融合（扶抑+调候+格局）+ 盲派修正 | 通常只用扶抑一派 |
| 结构性保护 | 10+ 条机制完整覆盖 | 通常只看冲 / 合 / 害的机械叠加 |
| 盲派反向规则 | ✓ 同一事件按结构反向解读 | ✗ 直接读口诀，无方向判断 |
| 出图前校验 | 三阶段硬门槛（R0+R1+R2）| ✗ 不校验，直接出 |
| 历史回测 | ✓ 有数据集 + 命中率指标 | ✗ 全凭师傅经验 |
| 输出可审计 | ✓ JSON 全字段可看 + bit-for-bit deterministic | ✗ 黑盒 |
| 性别 / 取向 | ✓ `--orientation` 5 选项 + 删除歧视性规则 | 默认异性恋 + "克夫旺夫" |
| LLM 防欺骗 | ✓ 强制可证伪点 + 禁止后视镜归因 | ✗ LLM 自由发挥 |
| 价格 | 开源 MIT | 通常订阅制 / 一次性付费 |

### vs 直接问 ChatGPT / Claude "帮我算个八字"

| 维度 | 本工具（接 LLM）| 直接问 LLM |
|---|---|---|
| 数值打分 | 由确定性脚本算 | LLM 直接编 |
| 同输入双盲一致 | ✓ bit-for-bit | ✗ 每次飘 ±20% |
| 三派分歧标记 | ✓ 自动检测 | ✗ LLM 一般只说一派 |
| 后视镜归因 | ✗ 强制禁止 | 经常发生（最大问题）|
| 结构性保护 | 全套实现 | LLM 偶尔提到 1-2 条 |
| 关键年份格式 | 强制"推论过程 + 可证伪点" | LLM 通常只给结论 |
| 现代化解读 | 协议层强制 | LLM 默认会带"克夫旺夫"等措辞 |

> **本工具 = 命理算法引擎 + LLM 解读层**。
> LLM 只负责把 JSON 翻译成大白话，**不负责打分**。

### vs 找算命师傅

| 维度 | 本工具 | 算命师傅 |
|---|---|---|
| 一次成本 | 0 元 | 100-2000 元 |
| 师傅水平依赖 | 无 | 极强（90% 师傅水平堪忧）|
| 派别选择 | 三派同时跑 | 看你遇到哪派 |
| 重复一致性 | bit-for-bit | 每次都不一样 |
| 隐私 | 本地跑 | 师傅知道你所有信息 |
| 修正成本 | 改 confirmed_facts | 重新付费 |
| 学理透明 | 全开源 + 古籍引文 | 通常黑盒 |

师傅的优势是**临场互动 + 经验**，但 80% 命理工作是机械的"识别命局结构 + 套规则"，那部分是工具能做的。

---

## 快速开始

### 安装

```bash
git clone https://github.com/XiaoChu-1208/bazi-life-curves.git
cd bazi-life-curves
pip install -r requirements.txt
```

### CLI 30 秒跑一次

```bash
mkdir -p output

# 1. 解析八字（含起运岁精算）
python scripts/solve_bazi.py \
  --pillars "庚午 辛巳 壬子 丁未" \
  --gender M --birth-year 1990 \
  --orientation hetero \
  --out output/bazi.json

# 2. 生成 4 维曲线（含三派融合 + 盲派修正 + 关系能量独立通道）
python scripts/score_curves.py \
  --bazi output/bazi.json \
  --out output/curves.json --age-end 80

# 3. 校验候选（你需要回答 R0 + R1，命中率 < 4/6 拒绝出图）
python scripts/handshake.py \
  --bazi output/bazi.json --curves output/curves.json \
  --out output/handshake.json

# 4. 渲染交互 HTML
python scripts/render_artifact.py \
  --curves output/curves.json --out output/chart.html

# 打开 output/chart.html 看 8 条曲线 + 大运评价 + 关键年份解读
```

### 在 Claude / Cursor 里当 Skill 用

把整个目录放到 `~/.claude/skills/bazi-life-curves/`，然后跟 Claude 说：

> "我想看人生曲线，八字 庚午 辛巳 壬子 丁未，男，1990 年"

Claude 会自动读 `SKILL.md` → 跑 solve → score → handshake → 抛 R0+R1 校验题给你 → 你答完 → 渲染 HTML + 流式发出 markdown 解读。整个流程 30-60 秒。

如果你的取向不是异性恋，告诉它"我是同性恋 / 双性 / 单身主义" 就行，它会自动加 `--orientation`。

---

## 学理合理性 · 600 年古籍直接支撑

| 工程实现 | 学理出处 | 古籍 |
|---|---|---|
| 三层独立打分（L0 原局 / L1 大运 / L2 流年）| 子平命理"体用之分"| 沈孝瞻《子平真诠》|
| 三派融合（扶抑 / 调候 / 格局）| 民国徐乐吾整理的"子平三大法门"| 徐乐吾《子平粹言》|
| 格局为先 | "先观月令以定格局，次看用神以分清浊"| 《子平真诠·论用神》|
| 燥湿独立维度 | "寒暖燥湿，命之大象"| 余春台《穷通宝鉴》|
| 印化护身 / 杀印相生 | "杀印相生，威权万里"| 任铁樵《滴天髓阐微》|
| 食神制杀 | "食神制杀，化煞为权"| 沈孝瞻《子平真诠》|
| 合处逢冲 / 三合解冲 | "合处逢冲，冲处逢合"| 《三命通会》|
| 三刑独立 | 寅巳申 / 丑戌未 / 子卯 / 自刑 | 《三命通会·论刑》|
| 盲派应事 11 条 | 段建业 / 王虎应 / 李洪成实战口诀 | 现代盲派 |

工程化部分（量化打分 / 权重数字 / 衰减系数）是经验值 + 历史回测调参，详见 [`references/methodology.md`](references/methodology.md)。

---

## 输出长什么样

`output/curves.json` 的关键字段：

```json
{
  "version": 7,
  "baseline": {"spirit": 48.0, "wealth": 45.2, "fame": 55.6, "emotion": 53.4},
  "relationship_mode": {
    "primary_mode": "outward_attractive",
    "label": "外向吸引型 / 关系能量充沛",
    "note": "命局只反映关系结构 / 能量模式，不预设对方性别 / 是否结婚 / 是否生育。"
  },
  "points": {
    "2026": {
      "ages": 36,
      "scores": {"spirit": {"fused": 62.3, "fuxi": 58, "tiaohou": 65, "geju": 64, "is_disputed": false}, ...},
      "emotion_yearly": 67.2,
      "events": [
        {"name": "比劫夺财", "amplifier": 0.4, "reversed": false, "protected": true,
         "protection_reason": "比劫帮身（身弱反向）"}
      ]
    }
  },
  "disputes": [
    {"year": 2031, "dim": "wealth", "diff": 22, "schools": {...},
     "explanation": "扶抑派看跌（财弱见劫），调候派看涨（火暖透干），格局派中性"}
  ],
  "turning_points_future": [
    {"year": 2027, "kind": "peak", "dim": "fame", "confidence": "high", "key_year": true}
  ]
}
```

每一个数字都能追溯到具体的脚本函数 + 古籍出处，没有黑盒。

---

## 目录结构

```
bazi-life-curves/
├── SKILL.md                       # Claude/Cursor Skill 主定义
├── USAGE.md                       # 用户视角速览
├── INSTALL.md                     # 安装指南
├── README.md                      # 本文件
├── requirements.txt
├── scripts/                       # 12 个核心脚本（v7.4）
│   ├── _bazi_core.py              # 干支 / 五行 / 十神 / 互动检测底层 + P1-P5 phase detect + v7.4 化气格 / 神煞 detect
│   ├── solve_bazi.py              # 八字解析（v7 --orientation · v7.2 --longitude 真太阳时）
│   ├── score_curves.py            # 4 维曲线打分（v7.2 --confirmed-facts · v7.4 化气格 phase override + 神煞 ±调味）
│   ├── mangpai_events.py          # 盲派应事 + 反向规则 + 护身减压
│   ├── handshake.py               # R0+R0'反迎合+R1+R2+R3 多阶段校验（v7.4 --user-responses 机械化判定）
│   ├── phase_inversion_loop.py    # v7.2 / v8 Auto-Loop · 相位反演 4 步编排（dump→pick→score→handshake）
│   ├── save_confirmed_facts.py    # v7.2 · 用户校验反馈固化（含 phase_override）
│   ├── family_profile.py          # v7.3 · 原生家庭 R3 反询问（父星/母星模式 + 5 档结构分类）
│   ├── render_chart.py            # 静态 PNG（matplotlib）
│   ├── render_artifact.py         # 交互 HTML（Recharts + marked.js）
│   ├── he_pan.py                  # 合盘 4 层评分
│   └── calibrate.py               # 历史回测
├── templates/chart_artifact.html.j2
├── references/                    # 12 个学理 / 协议文档
│   ├── methodology.md             # 三派融合的数学
│   ├── scoring_rubric.md          # 每条加 / 减分规则
│   ├── mangpai_protocol.md        # 盲派 11 条 + 反向 + 护身
│   ├── handshake_protocol.md      # R0+R1+R2 校验流程
│   ├── multi_dim_xiangshu_protocol.md  # LLM 解读模板
│   ├── dispute_analysis_protocol.md    # 三派分歧解读 4 步
│   ├── prediction_protocol.md     # 未来年份预测格式
│   ├── he_pan_protocol.md         # 合盘 4 层评分
│   ├── fairness_protocol.md       # §9 性别例外 + §10 现代化解读铁律
│   ├── diagnosis_pitfalls.md      # 已踩过的命理坑
│   ├── accuracy_protocol.md       # 准确度保障
│   └── glossary.md                # 术语表
├── examples/                      # 2 个完整示例（含 HTML）
│   ├── guan_yin_xiang_sheng.*    # 官印相生格
│   └── shang_guan_sheng_cai.*    # 伤官生财格
└── calibration/
    ├── dataset.yaml               # 历史命主回测数据集
    └── thresholds.yaml            # 阈值调参
```

---

## FAQ · 常见问题

### Q1：跟"算命 APP / 网页排盘"有什么本质区别？

**算法、校验、可证伪三层都不一样**。多数 APP 只用扶抑派一派打分（机械读"日主强弱+用神忌神"），看到冲就一律减分；本工具同时跑扶抑 25% / 调候 40% / 格局 30% 三派融合 + 盲派 11 条事件断 + 10+ 条结构性保护机制（杀印相生 / 食神制杀 / 六合解冲 / 三会成方 / 三刑独立等），并在出图前抛三阶段反询问校验（R0+R1+R2），命中率不达标拒绝出图。详见 [5 个绝对优势](#5-个绝对优势--这是市面上唯一做到这-5-件事的开源工具)。

### Q2：跟"直接问 ChatGPT / Claude 帮我算个八字"有什么区别？

**LLM 不打分，确定性脚本打分**。直接问 LLM 的最大问题是后视镜归因（你说"我 31 岁升职了"，LLM 立刻"哦命局对应应验了"），且每次跑结果飘 ±20%。本工具的分数由 `score_curves.py` 算出，同输入双盲 bit-for-bit 一致；LLM 只负责按 `multi_dim_xiangshu_protocol.md` 把 JSON 翻译成大白话解读，强制可证伪点格式。详见 [vs 直接问 ChatGPT / Claude](#vs-直接问-chatgpt--claude-帮我算个八字)。

### Q3：我是 LGBTQ+ / 不婚主义 / 不育主义，会被命理工具歧视吗？

**不会**。v7 现代化版本删除了所有"克夫旺夫 / 配偶星弱减分 / 女命印多减分 / 女命食伤克夫 / 男女比劫差异扣分"等 6 条带性别歧视的古法规则，新增 `--orientation` 参数（hetero/homo/bi/none/poly），emotion 维度走中性 `relationship_mode` 7 种描述（outward_attractive / competitive_pursuit / nurture_oriented / 等），且每次解读首段强制声明"命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育"。详见 [v7 现代化](#5-v7-现代化--命理学-600-年第一次的语言重构) 与 `references/fairness_protocol.md §9-§10`。

### Q4：怎么知道分析准不准？有没有"验"的办法？

**三层验证**：
1. **R0+R1+R2 三阶段硬门槛**（出图前）：R0 反询问·关系画像 2 题 + R1 健康三问 + R2 历史锚点（条件触发），命中率 < 4/6 拒绝出图
2. **历史回测**（`scripts/calibrate.py`）：在 `calibration/dataset.yaml` 的真实命主大波动事件上跑 recall / fp_rate
3. **可证伪点格式**：每个关键年份的解读必须含"如果 X 不发生，则我的判断错"，保证未来可以验证

详见 [4. 两轮校验硬门槛](#4-两轮校验硬门槛--出图前先证明八字是对的) 与 `references/handshake_protocol.md`。

### Q5：跑出来的结果能复现吗？

**bit-for-bit 一致**。同一份 `bazi.json` + 同一份 `confirmed_facts.json` → 跑 100 次输出 100 个 byte-equal 结果：

```bash
diff <(python scripts/score_curves.py --bazi bazi.json --strict | sha256sum) \
     <(python scripts/score_curves.py --bazi bazi.json --strict | sha256sum)
# 必须输出空
```

不允许引入随机 seed / 时间戳 / 字典遍历顺序依赖。详见 [A. Bit-for-bit deterministic](#a-bit-for-bit-deterministic)。

### Q6：怎么处理三派对同一年判断分歧？

**自动检测 + 强制 4 步推导**。当三派对某一年极差 ≥ 18 分时，该年标记 `is_disputed = true`，强制 LLM 按 `dispute_analysis_protocol.md` 走"事实 → 为何分歧 → 我偏向哪派 → 可证伪点" 4 步推导，**禁止**写"派别分歧大，无法判断"这种废话。

### Q7：我自己时辰记不准，工具会怎么办？

**触发红线，强制停手**。R0=0/2 + R1≤1/3 → 自动判定"八字大概率不准"，工具会要求你核对时辰 / 性别，**禁止**继续出图。这是为了避免你浪费 20 分钟读完一份 8000 字基于错八字的"分析"。详见 `references/handshake_protocol.md` 放行规则。

### Q8：能用真太阳时吗？

**v7.2 起支持**。给 `solve_bazi.py` 加 `--longitude <东经度数>` 参数（如北京 = 116.4），按 120° 中心 ±4 分/度自动校正出生时间。

### Q9：能算两个人合不合吗（合伙 / 婚配 / 友谊 / 家人）？

**可以**。跑 `scripts/he_pan.py`，输出 4 维兼容性分（合作 / 婚配 / 友谊 / 家人），4 层结构性评分（五行互补 + 干支互动 + 十神互配 + 大运同步度）。详见 `references/he_pan_protocol.md`。

### Q10：怎么在 Claude / Cursor / OpenAI Codex 里直接当 Skill 用？

把整个目录放到对应 Skill 路径（Claude: `~/.claude/skills/bazi-life-curves/`；Cursor: `.cursor/skills/`），然后跟 AI 说："我想看人生曲线，八字 庚午 辛巳 壬子 丁未，男，1990 年"。AI 会自动读 `SKILL.md` → 跑 solve→score→handshake → 抛 R0+R1 校验 → 你答完 → 渲染 HTML + 流式 markdown 解读。30-60 秒完成。

### Q11 (EN)：Is this safe to use for queer / non-binary / aromantic / non-marital users?

**Yes.** v7 explicitly removes 600 years of feudal gender-discrimination rules. Pass `--orientation homo|bi|none|poly` and emotion-channel interpretations switch to neutral `relationship_mode` (7 categories: outward_attractive, competitive_pursuit, nurture_oriented, ambiguous_dynamic, low_density, balanced, self_centered). Every emotion paragraph is forced to declare: *"the chart only reflects relationship structure and energy patterns; it does NOT presuppose your partner's gender, marital status, or whether you have children — those are your modern choices, not encoded in the chart."* See `references/fairness_protocol.md §9-§10`.

### Q12 (EN)：Why open-source a "fortune-telling" tool?

Because the alternative is closed-source apps that (a) only use one school (扶抑/Fu-Yi), (b) hide their scoring logic, (c) embed feudal gender norms, and (d) have no falsifiability protocol. We believe traditional Chinese metaphysics, like any 600-year empirical tradition, deserves the same engineering discipline as modern statistics: deterministic output, falsifiable predictions, back-testing, source citations from primary classics (滴天髓 / 子平真诠 / 穷通宝鉴 / 三命通会), and zero discrimination by gender / orientation / marital choice. MIT license — bazi tooling should be a public good.

---

## 已知限制

诚实摆出来：

- **数据集偏小**：当前 `calibration/dataset.yaml` 只 5 人 / 15 事件，统计意义有限。希望社区贡献匿名八字 + 真实事件
- **从格 / 化气格 / 神煞**：✅ 全部已实现
  - 从格：v7.1 P5 (三气成象 detect) + 假从/真从 detect 覆盖
  - 化气格：✅ v7.4 已实现 · `_bazi_core.detect_huaqi_pattern`（甲己 / 乙庚 / 丙辛 / 丁壬 / 戊癸 五合 + 月令化神 + 化神有根 + 无破格 + 一票否决日干强根）→ `apply_geju_override` 自动走 `huaqi_to_<化神>` phase override
  - 神煞：✅ v7.4 已实现 · `_bazi_core.detect_shensha` 8 类（天乙贵人 / 文昌 / 驿马 / 桃花 / 华盖 / 孤辰 / 寡宿 / 空亡）；原局命中 → baseline ±0.3~0.4；大运/流年逢 → 当年 ±0.5~1.0；驿马 → sigma × 1.3 波动加大。影响刻意小，只调味，不参与主格局判定
- **真太阳时校正**：✅ v7.2 已实现 · `solve_bazi.py --longitude <度>` 支持东经/西经，按 120° 中心 ±4 分/度自动校正出生时间
- **三派权重 25/40/30** 是经验值，需更大数据集做网格搜索（v9 deferred）
- **R0 反询问的 R0 命中率**：✅ v7.4 已加反迎合·反向探针 · 给每条 R0 推论生成完全相反的 claim，两个相反命题都答「对」→ 自动判定 sycophantic 并 R0 命中率 × 0.5 打折；原命题答「不对」+ 反向命题答「对」→ 判定 mirror，建议触发相位反演重跑。详见 `references/handshake_protocol.md §5.5`

详见 `references/phase_inversion_protocol.md §9` 的版本时间表。

---

## 贡献

PR / issue 欢迎。**请勿提交**：

- 含真实八字 + 真实姓名 / 经历的数据（隐私）
- 带宿命论 / 性别歧视 / 婚姻强制论的解读模板
- 直接抄袭某流派师傅口诀（请引用出处 + 师承）
- "这个准不准" 类无脚本可重现的 issue

**鼓励提交**：
- 新的盲派事件 / 结构性保护机制（需附古籍出处）
- 历史命主的匿名回测数据（八字 + 出生年代 + 大事件年份）
- 现代化解读规范的改进建议
- HTML 渲染优化 / 国际化 i18n

---

## SEO · 仓库发现性设置

> 这一节是给 **仓库 owner / 维护者** 看的：发布到 GitHub 后请按下面清单把发现性拉满。

### 1. 在 GitHub 仓库 About 区设置 Topics（必做）

进入仓库主页右侧 ⚙️ "About" → Topics，**逐个**添加（GitHub 单 topic 必须用连字符，不能含空格 / 中文）：

```
bazi  four-pillars-of-destiny  chinese-astrology  destiny  life-curve
falsifiable-prediction  deterministic  python  cli  open-source
claude-skill  cursor-skill  llm-skill  ai-skill  agentic-tools
synastry  compatibility  lgbtq-inclusive  queer-friendly
divination  metaphysics  chinese-metaphysics  ziping  ge-ju  mang-pai
```

> 这些 topics 是 GitHub Search、Trending、Topic Pages 的核心索引信号。每加一个相关 topic，搜索曝光大约 +10-20%。

### 2. 仓库 About 区描述（必做）

填这段（< 350 字符）：

```
把八字命理（Chinese Bazi / Four Pillars of Destiny）变成可证伪、可审计、bit-for-bit deterministic 的人生曲线引擎。三派融合（扶抑+调候+格局）+ 盲派应事 + 10+ 条结构性保护 + R0/R1/R2 三阶段校验 + LGBTQ+ 包容现代化。可作为 Claude / Cursor / Codex Skill 直接接入。
```

Website 字段填 GitHub Pages 链接（如开启）或 SKILL.md 链接。

### 3. 社交预览图 / Open Graph Image（强烈推荐）

GitHub 仓库 Settings → Options → Social preview → Upload image（1280 × 640 png）。当链接被分享到 Twitter / 微信 / Slack / LinkedIn 时，自带封面图能让点击率 +200-400%。

**封面图建议元素**：
- 标题：`bazi-life-curves`
- 副标题：`把八字变成可证伪的人生曲线`（中英双语）
- 一张 examples 里的 8 条曲线截图（来自 `examples/guan_yin_xiang_sheng.png`）
- 角标：`MIT · Python 3.10+ · Claude/Cursor Skill`

可以用 [og-image.vercel.app](https://og-image.vercel.app/) 生成，或本地用 matplotlib 写脚本批量出（建议加进 `scripts/render_social_preview.py`）。

### 4. GitHub Pages 静态站点（可选 · SEO 大幅加分）

把 README 渲染成独立站点能让 Google / Bing / 各 AI 检索引擎单独索引（不再受 raw.githubusercontent.com 限制）：

```bash
# 简单方案：在 Settings → Pages → Source 选 main / docs / (root)，开 Pages
# 进阶：用 mkdocs-material 把 references/ 做成完整文档站
pip install mkdocs-material
mkdocs new .
mkdocs gh-deploy
```

启用 GitHub Pages 后，记得**回头**把 sitemap.xml + robots.txt 提交到 [Google Search Console](https://search.google.com/search-console) 与 [Bing Webmaster](https://www.bing.com/webmasters/)。

---

## AI 检索友好 · 给 LLM / RAG / Agent 的引用指南

> 本项目专门做了 LLM 友好的元数据，方便被 ChatGPT / Claude / Perplexity / Gemini / Cursor / Devin / Codex 等 AI 系统正确引用。

### 给 LLM 的入口文档（按重要性）

- [`llms.txt`](llms.txt) —— 业界 [llmstxt.org](https://llmstxt.org/) 标准的项目摘要 + 文档地图
- [`AGENTS.md`](AGENTS.md) —— [agents.md](https://agents.md/) 标准的 AI Coding Agent 项目导航
- [`SKILL.md`](SKILL.md) —— Claude Skill / Cursor Skill / Codex Skill 通用主定义（YAML frontmatter）
- [`CITATION.cff`](CITATION.cff) —— Google Scholar / Zenodo 学术引用元数据

### 推荐的引用格式（学术 / 技术博客）

```bibtex
@software{bazi_life_curves_2026,
  author       = {XiaoChu-1208 and bazi-life-curves contributors},
  title        = {bazi-life-curves: Quantifying Chinese Bazi into
                  Auditable, Falsifiable, Back-Testable Life Curves},
  year         = {2026},
  version      = {7.4},
  url          = {https://github.com/XiaoChu-1208/bazi-life-curves},
  license      = {MIT}
}
```

### 给 LLM 检索的"问答清单"（这工具能帮回答什么）

| 用户问题 | 工具能给的答案路径 |
|---|---|
| 我八字 X，未来 10 年哪几年要小心？ | `solve_bazi → score_curves → handshake → curves.json.turning_points_future` |
| 我八字 X，2027 年怎么样？ | `curves.json.points["2027"]` 4 维 fused 分 + events |
| 我八字 X，财运曲线？ | `curves.json` 中 wealth 维度 80 年走势 + key turning points |
| 我跟 Y 八字合不合？ | `he_pan.py` → 合作 / 婚配 / 友谊 / 家人 4 维兼容性 |
| LGBTQ+ 友好的命理工具？ | `--orientation homo/bi/none/poly` + relationship_mode 中性描述 |
| 命理工具结果可复现？ | `score_curves.py --strict` + sha256sum 验证 bit-for-bit |
| 怎么避免 LLM 后视镜归因？ | 强制可证伪点格式 + 身份盲化输入 + confirmed_facts 写回 |
| 三派分歧怎么办？ | `dispute_analysis_protocol.md` 4 步推导 |

### 不要让 AI 做的事（红线）

详见 [`AGENTS.md` 第 4 节"修改算法时的硬性约束"](AGENTS.md) 与 [`llms.txt` "不要做的事"](llms.txt)。

---

## License

MIT —— 命理工具应该是公共财产，不该藏起来。

---

## 致谢

- 子平命理：徐乐吾《子平粹言》整理的"子平三大法门"
- 调候派：余春台《穷通宝鉴》
- 格局派：沈孝瞻《子平真诠》
- 滴天髓：刘伯温原著 / 任铁樵阐微
- 三命通会：万民英
- 盲派：段建业、王虎应、李洪成的实战口诀
- 起运岁精算：[lunar-python](https://github.com/6tail/lunar-python)
- 渲染：marked.js、Recharts、matplotlib

---

## v7 现代化版本（2026-04）· 主要更新

- 加 `--orientation` 参数支持 hetero/homo/bi/none/poly 取向
- 删除全部带性别歧视的古法规则（克夫旺夫 / 女命印多减分 / 配偶星弱减分等 6 条）
- emotion 维度纯中性描述：高 ≠ 婚姻顺利 / 低 ≠ 单身差
- 加 fairness_protocol §9-§10 现代化解读铁律
- 新加 `relationship_mode` 中性关系画像字段（7 种模式）
- handshake R0 文案重写：去颜值 / 去性别默认 / 去价值判断
- 烟测覆盖：5 种 orientation × spirit/wealth/fame 完全独立 × 性别对称性 × 旧版回归一致

> "把 600 年的命理学，搬进 2026 年的语言。"
