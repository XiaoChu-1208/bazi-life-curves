# bazi-life-curves

> 把八字命理变成可证伪、可审计、可回测的人生曲线。
> Quantify Chinese Bazi (Four Pillars of Destiny) into auditable, falsifiable, back-testable life curves.

[License: MIT](https://opensource.org/licenses/MIT)
[Python 3.10+](https://www.python.org/)
[Skill for Claude](https://www.anthropic.com/)
[Cursor Skill](https://cursor.sh/)
[MCP Server](#当-mcp-server-用v80--11-个-tools)
[Deterministic](#工程绝对优势)
[v7 Modernized](#5-v7-现代化--命理学-600-年第一次的语言重构)
[v9 Precision](#v9-范式转换--把命理师之道工程化)
[v9 OpenPhase](#open_phase-逃逸阀--工具的伦理底线)
[v9.1 Mangpai Zuogong](#v91--盲派做功视角接入--给力量视角以外的命局一条活路)
[Ethics](#写在最前--命理师之道)
[CI](https://github.com/XiaoChu-1208/bazi-life-curves/actions/workflows/ci.yml)



> **关键词 / Keywords**：八字 · Bazi · 四柱命理 · Four Pillars of Destiny · 子平命理 · 人生曲线 · life curve · 大运 · 流年 · 合盘 · synastry · 婚配 · LGBTQ-inclusive · Claude Skill · Cursor Skill · MCP server · 开源命理 · falsifiable prediction · deterministic · 真太阳时 EOT · 双引擎 · cantian-ai compatible

---

## 写在最前 · 命理师之道

> 这一段不是项目介绍，是这个工具自己的伦理底色。
> 在你读任何一行代码、任何一个分数、任何一条解读之前——请先读它。

命理这门学问已经走过 1500 年。它精微，所以足以照亮人生的暗角；
它也危险——**它越精准，离真正的"命"就越远；它越自信，对人的伤害就越深。**

一句"你是弃命从财格"在算命师傅口中也许只值 5 秒钟，
在用户的脑海里却可能改写未来 50 年的人生选择。
一行"印比岁运是阻力"如果是错的，
用户回避掉的，可能恰恰是命中真正的贵人。

所以这个工具的第一条原则不是"算得准"，而是——**判错时要诚实，存疑时要承认，分歧时要展示，与你直觉冲突时要把裁定权还给你**。

我们把这一条原则拆成三句话：

- **尊重学理 · 一派不能独断**
子平真诠重月令格局、滴天髓重日主气化、穷通宝鉴重调候季节、盲派重象法应事，紫微铁板与子平在不同维度——600 年来从来没有哪个流派宣称能独自覆盖所有人盘。
本工具同时跑 6 大流派加权投票，是回到命理学本来的多元面貌，不允许任何一派、也不允许任何一个高置信度的算法一锤定音。
- **尊重边界 · 算法允许说"我不知道"**
当流派各执一词、最高后验不到 0.55、或前两个候选势均力敌时，工具会落 `open_phase`（逃逸阀），把所有可能性陈列给你，**而不是赌一个最像的答案**。
这是工具诚实的底线——一份"我在你这盘上不下结论"的输出，比一份"95% 把握错的"输出，对你的人生珍贵得多。
- **尊重你 · 终极裁定权永远在你手上**
算法可以在很高的置信度下输出某个相位。但你和你身边的人对自己人生的认识，永远比 8 题问卷 + 110 个特殊格能覆盖的更深。
**任何与你强烈直觉冲突的判定，请优先相信你的直觉。** 然后回头让算法补锚点重算。

我们认为，一个合格的命理学产品，应当**对学理敬畏到骨子里——读古籍、引出处、跑回测、做证伪**；
也应当**对人敬畏到骨子里——不预言、不独断、不替人决定、不把"算得准"当作压过用户直觉的权柄**。

> *真正的命理师从不替天下决定，他只是把可能性铺在你面前。*
> *这个工具，也是。*

这套伦理观的工程化体现是 v9 的 [HS-R7 最高红线](#hs-r7-最高红线--三声明强制注入) 与 [心智模型协议](references/mind_model_protocol.md)，强制写进每一份输出，**任何输出缺这三声明都拒绝出图**。

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


| 派别      | 权重       | 看什么                             | 古籍出处            |
| ------- | -------- | ------------------------------- | --------------- |
| **扶抑派** | 25%      | 日主强弱 → 用神 / 忌神                  | 民国《滴天髓阐微》       |
| **调候派** | 40%      | 月令寒暖燥湿 → 寒暖用神                   | 余春台《穷通宝鉴》       |
| **格局派** | 30%      | 月令格局（正官 / 七杀 / 食神 / 伤官 …）→ 成败用神 | 沈孝瞻《子平真诠》       |
| **盲派**  | 0%（不进融合） | 应事断 + 烈度修正器（±12 amplitude）      | 段建业 / 王虎应 / 李洪成 |


**三派分歧自动检测**：当三派对某一年的判断极差 ≥ 阈值（默认 18 分），该年标记为 `is_disputed = true`，强制 LLM 按 `dispute_analysis_protocol.md` 做"事实 → 为何分歧 → 我偏向哪派 → 可证伪点" 4 步推导，**禁止**写"派别分歧大，无法判断"这种废话。

> **格局为先**（v3 新增）：先识别格局（正官格 / 食神格 / 伤官生财 / 杀印相生 …），用格局**覆盖**用神判定。这是 600 年子平命理的核心洞见，但在多数现代软件里被简化掉了。
> 出处：《子平真诠》"先观月令以定格局，次看用神以分清浊"

### 2. 结构性保护机制全套 —— "看到冲就 -" 是最低级的命理误读

> 大多数命理软件看到「冲 / 刑 / 害」就一律减分。这是**机械直读**，根本不是命理。
> 真正的命理是看**结构**：同样的"日支被冲"，有印化护身的减压 60%，有合解的减压 40%，遇到三会成方反而是局面突破。

本工具实现的结构性保护机制（每条都有古籍出处）：


| 机制         | 触发                        | 效果              | 出处                |
| ---------- | ------------------------- | --------------- | ----------------- |
| **印化护身**   | 七杀来攻 + 局有正/偏印             | 杀印相生，杀的破坏力 ×0.5 | 《滴天髓》"杀印相生，威权万里"  |
| **食神制杀**   | 七杀逢食神                     | 化煞为权，从破坏变贵气     | 《子平真诠》            |
| **比劫帮身**   | 财官杀来克 + 身弱 + 局有比劫         | 减压 30%          | 《滴天髓》             |
| **食伤泄秀**   | 印旺反塞 + 局有食伤               | 化印为秀，转贵         | 《穷通宝鉴》            |
| **财生官护身**  | 七杀无制 + 局有财                | 财生杀虽不解但能引化      | 《三命通会》            |
| **官印动态相生** | 大运 / 流年触发"杀生印 → 印生身"链     | 每年动态加分          | 《滴天髓》             |
| **六合解冲**   | 冲克的同时局有 / 大运有六合           | 贪合忘冲，减压 60%     | 《三命通会》"合处逢冲，冲处逢合" |
| **三合解冲**   | 冲克的同时形成三合局                | 三合局成，化冲为生       | 同上                |
| **三会成方**   | 寅卯辰 / 巳午未 / 申酉戌 / 亥子丑 三会齐 | 局面突破，原冲规则失效     | 《滴天髓》             |
| **三刑**     | 寅巳申 / 丑戌未 / 子卯 / 自刑       | 独立扣分，不与冲叠加      | 《三命通会》            |


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


| 已删除的古法规则            | 删除原因                          |
| ------------------- | ----------------------------- |
| "配偶星弱 → -6 分"       | 暗示"无配偶 = 差"，已删                |
| "女命印多 → -4 分"       | "重事业 = 感情位次靠后" 把女性事业当感情对立面，已删 |
| "女命食伤旺 → -2 分"      | "女命伤官克夫" 是物化伴侣的封建残余，已删        |
| "男命比劫 -6 / 女命比劫 -4" | 同样结构对所有性别影响相同，统一为 -5          |
| "女命大运伤官见正官 → -6"    | 克夫论的代码体现，已删                   |
| "男命大运财弱遇比劫 → -4"    | 性别专属规则，统一改为不分性别               |


#### 5.3 加入的（让命理工具进入 2026 年）

- `**--orientation` 参数**：`hetero` / `homo` / `bi` / `none` / `poly` —— 影响 emotion 通道的配偶星识别方式
- **relationship_mode 中性描述**：`outward_attractive` / `competitive_pursuit` / `nurture_oriented` / `ambiguous_dynamic` / `low_density` / `balanced` / `self_centered` —— 取代"克夫旺夫"二元
- **强制前置声明**：每次出图后第一段感情解读必须包含「命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育——这些是你的现代选择，不在命局之内」
- **emotion 高 ≠ 婚姻顺利 / emotion 低 ≠ 单身差** —— 纯中性描述

#### 5.4 命局可推 / 不可推（fairness_protocol §10）


| 命局**可**推                    | 命局**不可**推               |
| --------------------------- | ----------------------- |
| 关系结构（主动/被动 / 平等/层级 / 稳定/流动） | 对方的生理性别                 |
| 能量模式（吸引型 / 争取型 / 自给型）       | 是否结婚 / 几段关系 / 是否生育      |
| 偏好的互动模式（同辈 / 师生 / 互补）       | 婚姻是否合法 / 关系是否被祝福        |
| 关系密度（高 / 中 / 低）             | 关系的伦理形态（一夫一妻 / 多元 / 不婚） |


> 这是开源命理工具里**第一次**把现代性别 / 取向 / 关系观系统性写进协议层。

---

## v9 范式转换 · 把"命理师之道"工程化

> v1–v8 解决的是「算得准不准」；v9 解决的是「算得准之后，**该不该独断**」。
> 这是命理工具的伦理学问题——而 v9 把它当作头等约束，重写了整套架构。

### 一类典型失败模式（v9 的起点）

某些八字结构看起来"日主几乎无根"——比如日主土星、月支水旺、财星杂多、印星藏在地支不透干。旧算法链很容易这样走：把藏在地支主气里的印星贡献漏算 → 日主被判为"无根" → 触发"弃命从财格" → 单流派给出高后验 → 输出"印比岁运是阻力, 财官岁运为大利"。

而真实情况是：地支主气里的印星本身就贡献了完整的根，整个日主完全立得住——这类盘根本不是从格，而是杀印相生 / 伤官生财 / 调候反向等多格并存。一旦算法独断了一个错的 phase，**后续解读会自动按这个 phase 圆故事，把反例事件也强行解读成"应验"**——叙事一旦立起来，反例越多，反而被算法当作越多的支持证据。

这暴露了底层四个深层缺陷：粒度（藏干当二元，不分本气/中气/余气）、独断（一派给候选就 adopt）、叙事（adopt 后按 phase 圆故事）、逃逸（算法没有"我不知道"的合法出口）。

> *算法越精密，越容易把"能用 X 解释"误认作"X 被这条证据支持"——*
> *一旦陷入叙事的深度逻辑里，自己出不来了。*

这一句话，定义了 v9 的全部工作。

### 核心范式 · "Precision over Recall, 多解共存, 不允许独断"


| 维度      | v1–v8                   | v9                                             |
| ------- | ----------------------- | ---------------------------------------------- |
| **目标**  | recall 优先，每盘都给 phase    | precision 优先，不能独断时落 `open_phase`               |
| **决策**  | 单流派 detector 最高分就 adopt | 6 大流派加权投票，top1<0.55 OR gap<0.10 → `open_phase` |
| **多解**  | 默认单一 phase              | 默认输出复合相位（主 / 副 / 调候修正）+ 多流派备解                  |
| **叙事**  | adopt 之后按 phase 圆故事     | 反身性 disclaimer 强制注入                            |
| **裁定权** | 算法独断                    | 用户终极裁定权高于算法，与直觉冲突时**优先相信直觉**                   |


### 六条独立拦截位点（v9 一句话总览）

每一条都防同一类误判被算法不同位置重新引入：

1. **通根度严判** — 把藏干贡献按"本气 1.0 / 中气 0.5 / 余气 0.2"分级，不再当 0/1。
2. **入口守卫** — 起运岁不能精算的 `pillars` 模式弃用；合盘要求每方都过 v8 校验。
3. **大运层应事** — 盲派反吟/伏吟不只看流年与命局，还要看大运层。
4. **HS-R7 三声明** — 算法局限 / 反身性 / 用户裁定权，缺一即拒绝出图。
5. **罕见格全集 + LLM 兜底** — 子平 60 + 盲派 30 + 紫微铁板 20，共 110 条特殊格全列出，算法判不出走协议化 inline fallback。
6. **多流派加权投票** — 子平真诠 / 滴天髓 / 穷通宝鉴 / 盲派 / 紫微 / 铁板加权投票，决定是 adopt 还是落 `open_phase`。

> 工程实现细节、PR 拆分、文件位置请看 `[CHANGELOG.md](CHANGELOG.md)` 与 `[references/](references/)`。

### `open_phase` 逃逸阀 · 工具的伦理底线

> 命理工具的最大错误**不是判错，而是判错之后还自信**。
> 当算法只有 34% 把握的时候，它说"你是 X 相位"和它说"我在这盘上不下结论"——
> 二者对用户人生的影响差距是巨大的。

**触发条件**（任一满足即落 `open_phase`）：

- top1 后验 < 0.55（没有任何流派达到多数派支持）
- top1 与 top2 后验差 < 0.10（前两候选势均力敌）
- ≥ 2 条用户事件锚点被 top1 反例

**落 `open_phase` 时，Agent 必须**：不独断输出某 phase；把所有备解列出，每条带 `if_this_is_right_then` 实证含义；请用户补 ≥ 2 条具体事件年份重投票；必带 HS-R7.3 disclaimer。

### HS-R7 最高红线 · 三声明强制注入

任何 v9 输出 **缺这三件之一就拒绝出图**（`MissingHSR7Disclosure`）：

- **HS-R7.1 算法局限范围声明** — 明示算法能判什么、不能判什么。能：基于真太阳时 + 110 特殊格 + 多流派 + 用户事件锚点的贝叶斯后验；**不能**：未询问的人际细节、catalog 之外的"格中之格"、灵魂 / 因果 / 自由意志等元层议题。
- **HS-R7.2 反身性免责声明** — *任何"未来某年会发生 X"的预测都具有反身性——你听完它会调整行为，调整之后的人生不再是这个 phase 的纯粹运行。把预测当作决策时的参考维度，不当作必然发生的剧本。*
- **HS-R7.3 用户终极裁定权声明** — *算法可以在很高的置信度下输出某个 phase。但你和你身边的人对自己人生的认识，永远比 8 题问卷 + 110 个格能覆盖的更深。任何与你强烈直觉冲突的判定，**优先相信你的直觉**，回头让算法补 anchor 重算。*

### 为什么这样更合理 · 三个理由

**学理上：命理学本身就是流派多元的。** 子平真诠重月令格局、滴天髓重日主气化、穷通宝鉴重调候季节、盲派重象法应事——600 年来从没有哪个流派宣称能独自覆盖所有人盘。任何工具只用一派打分，在学理上已经输了一半。

**心理上：错误叙事的伤害是不对称的。** 算法对的时候用户得到边际收益，算法错的时候用户损失的是关键人生节点（提前回避了真贵人 / 错配了真凶险）。这种**不对称性**要求算法的默认动作是"诚实展示分歧"，而不是"赌一个最高后验"。

**统计上：贝叶斯后验要求先验诚实。** 后验再高也只是"在这一派内最像"——多流派加权投票本质是**让先验更诚实**：4 派共识的才是命局的"客观可见性"，4 派各执一词的应该诚实承认"算法在此盘的可见性低"。

### v9 不变量 · 任何后续 PR 不允许破坏

1. 六条独立拦截位点必须**每条都有自动化测试覆盖**，不容许靠 reviewer 记得作为防线。
2. `open_phase` 阈值必须保守，放宽需要数据集 ablation 证明。
3. 多流派权重必须公开可调，不允许任何一派 weight > 1.0。
4. HS-R7 三声明不允许任何输出绕过——包括开发 / 调试 / strict=False。
5. `rare_phases_catalog.md` 是公开 catalog，任何新加的格必须带古书出处 + 可判定标记 + 典型应验。

> 这五条是 v9 的"宪法层"。任何 PR 触碰这五条，**即使测试全绿也必须先讨论再合**。详见 `[references/mind_model_protocol.md](references/mind_model_protocol.md)` 与 `[CHANGELOG.md](CHANGELOG.md)`。

---

## v9.1 · 盲派做功视角接入 · 给"力量视角"以外的命局一条活路

> v1–v9 的 14 个核心 phase 全部围绕**力量视角**：日主旺衰 / 从格 / 化气 / 调候。
> 但盲派 600 年的口诀传承告诉我们，相当一部分命局的主结构不是"日主多强"，
> 而是"刃在做什么、伤官在做什么、杀印在做什么"——这叫**做功视角**。
> v9.1 用 7 层架构把"做功视角"整体接进来，而不是给某一个 case 加个特判。

### 触发问题 · 一类典型的"识别盲区"

某些命局阳干日主有根、命中带阳刃、刃支与财支正六冲——盲派一眼看出是**刃冲财做功**：
日主用刃为体，主动出击取财，应期年（子/午/卯/酉）剧烈兑现。

但 v8.1 的算法链是这样卡住的：

1. **识别层**：`rare_phase_detector` 能命中 `yangren_chong_cai`（confidence 0.85）
2. **决策层**：`phase_posterior` 候选池**只有 14 个 power 视角的 core phase**——`yangren_chong_cai` 根本不在候选池里 → R1 直接 reject
3. **解读层**：即便用户在 R2 反复申诉，算法找不到对应的 phase，最后回落到 `day_master_dominant` → 解读完全偏离命局主结构
4. **打分层**：`mangpai_events` 把 `yangren_chong` / `bi_jie_duo_cai` 一律当负面事件 → 应期年的"剧烈兑现"被错算成"破财夺财"

这不是算法粒度问题，是**整条流水线对"做功视角"零认知**。任何单点修复都治标不治本。

### 7 层架构改造 · 让"做功视角"成为一等公民

| 层 | 文件 | 做了什么 |
|---|---|---|
| L1 · Phase Registry | `scripts/_phase_registry.py` | 统一 54 个 phase 的 metadata：`dimension`（power / bridge / **zuogong**）、出处、触发地支、反转规则 |
| L2 · Prior 聚合 | `scripts/_bazi_core.py` + `scripts/rare_phase_detector.py` | `P7_zuogong_aggregator`：把 rare-phase detector 的 zuogong-dim 命中聚合成一个 prior 证据，进入贝叶斯先验分布 |
| L3 · D6 判别题 | `scripts/_question_bank.py` | 新增 3 道**做功视角**题（推进模式 / 节奏形态 / 得失来源），likelihood_table 对 4+ 个经典做功格都有判别力 |
| L4 · R3 降级路径 | `scripts/phase_posterior.py` | R1 后验置信不足但 rare-phase 有强命中时，触发 Round 3 confirmation（专问 D6） |
| L5 · 反转 DSL | `references/mangpai_reversal_rules.yaml` + `scripts/_mangpai_reversal.py` | 做功格下，`yangren_chong` 反转为 positive、`bi_jie_duo_cai` 反转为 neutral 等盲派口诀以 YAML 规则化 |
| L6 · 应期年加成 | `scripts/score_curves.py` `_apply_zuogong_modifier` | trigger 地支（如阳刃四仲 子/午/卯/酉）流年，geju 派分数显著抬升 |
| L7 · 用户拍板锁定 | `scripts/save_confirmed_facts.py` | `--phase-full-override <PHASE_ID> --reason "..."` 把任意 registered phase 锁死，级联效应贯穿 L5/L6 |

### 关键设计原则

- **方法论先于配置** — 整套架构是面向 `dimension == "zuogong"` 的**一族 phase**，不是面向某个特定 phase。任何新做功格只需在 registry 加 metadata + 在 DSL 加规则即可激活，无须改任何业务代码。
- **bit-for-bit 可降级** — 默认 phase（`day_master_dominant`）下 detect_all 不走反转路径、不进 prior 聚合、不触发 modifier，确保历史 examples 的 sha256 完全不变（保护既有用户的 confirmed_facts.json 不失效）。
- **不允许无凭据强推** — 即使 rare-phase detector 给出 0.85 confidence，无 R3 用户答案时 `day_master_dominant` 仍 top1。做功视角必须由用户的人生节奏证据驱动，不允许算法自作主张推翻力量视角。
- **古籍出处铁律** — 每个新 phase / 每条反转规则必须带 `source` 字段引古书（盲派师承传 / 子平真诠 / 滴天髓 / 三命通会），无出处不予注册。

### 当前覆盖度 · 诚实的方法论 vs 配置矩阵

`tests/test_yangren_chong_cai.py::test_l1_zuogong_dimension_phases_registered` 强制 zuogong phase ≥ 5。当前注册了 11 个 zuogong phase，但配置层填充进度不一：

| 维度 | 已激活 phase | 配置完整度 |
|---|---|---|
| 刃做功族 | `yangren_chong_cai`（刃冲财）/ `yang_ren_jia_sha`（阳刃驾杀）/ `riren_ge`（日刃格） | trigger_branches + reversal + D6 likelihood 三件齐全 |
| 伤官族 | `shang_guan_sheng_cai` / `shang_guan_sheng_cai_geju` / `shang_guan_pei_yin_geju` | reversal 已配，trigger / D6 部分（伤官生财含 D6） |
| 杀印族 | `sha_yin_xiang_sheng_geju` / `qi_yin_xiang_sheng` | reversal 部分配置 |
| 食制杀 | `shi_shen_zhi_sha_geju` | metadata 仅 |
| 通明 / 白清 | `mu_huo_tong_ming` / `jin_bai_shui_qing` | metadata 仅 |

> **方法论是通用的** — L1/L2/L5/L6/L7 的骨架对所有 zuogong phase 都生效，无须改代码。
> **配置仍在补全** — 后续 PR 会按"古籍出处 + e2e fixture"流程，把伤官族 / 杀印族的 `trigger_branches`、D6 likelihood、反转规则全部填齐。
> 这是**有意识的方法论先行 + 配置渐进**策略，不是过拟合到单个 case。

### 验收 · `tests/test_yangren_chong_cai.py` · 11 个 e2e

合成八字（`丙子 丙申 壬午 乙巳`，pillars 模式 + 早期 birth_year=1936，不指向任何特定个人）打通 L1–L7 全链路，任一层退化都阻断合并：

- L1: phase registry 必须包含 4+ 经典做功格
- L2: 默认答案下 `yangren_chong_cai` 进入 prior（≥ 0.20），但 top1 仍是 `day_master_dominant`
- L3: D6 三题对 4+ 经典做功格都有非均匀 likelihood（防过拟合 guard）
- L4: D6 全选"主动出击"后 posterior `yangren_chong_cai` ≥ 0.60
- L5: 锁定后反转事件 ≥ 10 条，关键反转必触发
- L6: 应期年（子/午/卯/酉）geju 派 spirit 维度平均抬升 ≥ 3.0，非应期年明显较低
- L7: `phase_full_override` 锁死 phase_decision（`decision_probability=1.0`）

详见 [`references/phase_architecture_v9_design.md`](references/phase_architecture_v9_design.md)。

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
3. `**confirmed_facts` 写回机制**：用户的反馈进 JSON 文件持久化，下次同一八字直接复用，不重复欺骗

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

### F. 双引擎交叉验证（v8.0 · 业内首次）

节气交接的边缘 case（出生时刻在节令前后 30 分钟内）是命理软件的最大事故源——**月柱算错一格，整张盘的格局/用神/大运全错**。本工具默认装 `[lunar-python](https://github.com/6tail/lunar-python)`（行业事实标准）作为主引擎，并支持可选 `[tyme4py](https://github.com/6tail/tyme4py)`（节气基于"寿星天文历"sxwnl）作为副引擎并行计算：

```bash
python scripts/solve_bazi.py --gregorian "1990-05-12 14:30" --gender M --engine cross-check --out bazi.json
# 输出含：engine_cross_check.is_consistent = true / false
# false 时自动标注分歧位置 + 双引擎结果对照，用户可决定信哪个 / 是否核对原始时辰
```

业内对比：99% 的命理工具只用单一日历库；只要库底层 bug，全行业静默错。

### G. 天文级真太阳时（v8.0 · NOAA EOT 公式）

> 命理软件 99% 只做"经度差"修正（`(lng - 120) × 4 分钟`），忽略**均时差 EOT**——
> 因地球轨道椭圆 + 黄赤交角，真太阳时与平太阳时一年内偏差最大 ±16 分钟（11 月初最大），
> 这足以让冬季出生的命主时柱错一格。

本工具用 NOAA 标准公式实现"经度差 + EOT"完整校正（纯 Python 实现，零额外依赖，**精度 ±15 秒**）：

```bash
python scripts/solve_bazi.py --gregorian "1990-11-03 12:00" --gender M --longitude 87.6 --out bazi.json
# 真太阳时=经度 87.6° E + 时区 UTC+8 → 经度差 -129.6 min + 均时差 +16.4 min
#         = 总偏移 -113.2 min；钟表 12:00 → 真太阳时 10:06
```

业内对比：cantian-ai/bazi-mcp / 多数排盘 APP 都只做经度差，本工具是开源 SOTA。

---

## 跟其他东西的对比 · 一图看懂

### vs 传统命理软件 / 算命 APP


| 维度      | 本工具                                      | 大多数命理 APP          |
| ------- | ---------------------------------------- | ------------------ |
| 算法学派    | 三派融合（扶抑+调候+格局）+ 盲派修正                     | 通常只用扶抑一派           |
| 结构性保护   | 10+ 条机制完整覆盖                              | 通常只看冲 / 合 / 害的机械叠加 |
| 盲派反向规则  | ✓ 同一事件按结构反向解读                            | ✗ 直接读口诀，无方向判断      |
| 出图前校验   | 三阶段硬门槛（R0+R1+R2）                         | ✗ 不校验，直接出          |
| 历史回测    | ✓ 有数据集 + 命中率指标                           | ✗ 全凭师傅经验           |
| 输出可审计   | ✓ JSON 全字段可看 + bit-for-bit deterministic | ✗ 黑盒               |
| 性别 / 取向 | ✓ `--orientation` 5 选项 + 删除歧视性规则         | 默认异性恋 + "克夫旺夫"     |
| LLM 防欺骗 | ✓ 强制可证伪点 + 禁止后视镜归因                       | ✗ LLM 自由发挥         |
| 价格      | 开源 MIT                                   | 通常订阅制 / 一次性付费      |


### vs 直接问 ChatGPT / Claude "帮我算个八字"


| 维度      | 本工具（接 LLM）      | 直接问 LLM           |
| ------- | --------------- | ----------------- |
| 数值打分    | 由确定性脚本算         | LLM 直接编           |
| 同输入双盲一致 | ✓ bit-for-bit   | ✗ 每次飘 ±20%        |
| 三派分歧标记  | ✓ 自动检测          | ✗ LLM 一般只说一派      |
| 后视镜归因   | ✗ 强制禁止          | 经常发生（最大问题）        |
| 结构性保护   | 全套实现            | LLM 偶尔提到 1-2 条    |
| 关键年份格式  | 强制"推论过程 + 可证伪点" | LLM 通常只给结论        |
| 现代化解读   | 协议层强制           | LLM 默认会带"克夫旺夫"等措辞 |


> **本工具 = 命理算法引擎 + LLM 解读层**。
> LLM 只负责把 JSON 翻译成大白话，**不负责打分**。

### vs 找算命师傅


| 维度     | 本工具               | 算命师傅           |
| ------ | ----------------- | -------------- |
| 一次成本   | 0 元               | 100-2000 元     |
| 师傅水平依赖 | 无                 | 极强（90% 师傅水平堪忧） |
| 派别选择   | 三派同时跑             | 看你遇到哪派         |
| 重复一致性  | bit-for-bit       | 每次都不一样         |
| 隐私     | 本地跑               | 师傅知道你所有信息      |
| 修正成本   | 改 confirmed_facts | 重新付费           |
| 学理透明   | 全开源 + 古籍引文        | 通常黑盒           |


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

### 当 MCP server 用（v8.0 · 11 个 tools）

跟 Skill 不同，**MCP server 是协议级集成**：任何 MCP 兼容客户端（Claude Desktop / Cursor / Cline / Continue / Zed / Windsurf / Codex CLI / Aider / Devin / LangChain / LlamaIndex 等）都能直接调用本工具的 11 个 tools，不需要 LLM 学 Skill 文档。

**11 个 tools 一览**：


| tool                  | 用途                                           |
| --------------------- | -------------------------------------------- |
| `solve_bazi`          | 八字解析（三引擎可选 + 天文级真太阳时）                        |
| `score_curves`        | 4 维 × 80 年人生曲线打分                             |
| `mangpai_events`      | 盲派 11 条经典组合事件检测                              |
| `handshake`           | R0/R0'/R1/R2/R3 反询问校验                        |
| `evaluate_handshake`  | 用户答完后机械化评估命中率                                |
| `he_pan`              | 合盘 4 层结构性评分                                  |
| `render_artifact`     | 渲染交互 HTML（marked.js + Recharts）              |
| `engines_diagnostics` | 引擎可用性诊断                                      |
| `getBaziDetail`       | **cantian-ai/bazi-mcp 兼容**：公历/八字 → 完整命局      |
| `getSolarTimes`       | **cantian-ai/bazi-mcp 兼容**：八字 → 公历可能时刻       |
| `getChineseCalendar`  | **cantian-ai/bazi-mcp 兼容**：公历 → 农历 + 干支 + 节气 |


> 后 3 个是 `[cantian-ai/bazi-mcp](https://github.com/cantian-ai/bazi-mcp)` 的接口别名 → 已经接了 cantian-ai 的应用零改动可以切到本工具，立刻获得三派融合 / R0/R1 校验 / fairness 等增强。

**接入 Claude Desktop**（macOS）：

把下面这块合并到 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "bazi-life-curves": {
      "command": "python3",
      "args": ["/abs/path/to/bazi-life-curves/scripts/mcp_server.py"]
    }
  }
}
```

重启 Claude Desktop，然后在对话里说：

> "用 bazi-life-curves MCP 帮我算 1990-05-12 14:30 出生男 北京（116.4°E）的命局，画出 80 岁人生曲线"

**接入 Cursor**：项目根目录已自带 `.cursor/mcp.json` 模板，直接打开 Cursor 就生效。

**手动验证 MCP server**：

```bash
# 列出 11 个 tools + 引擎可用性
python scripts/mcp_server.py --inspect

# 跑 5 个核心 tools 的端到端自检
python scripts/mcp_server.py --selftest

# 跑 stdio 服务（让 MCP 客户端接）
python scripts/mcp_server.py
```

> **零外部依赖**：MCP server 用纯 Python 实现 JSON-RPC 2.0 over stdio，
> 不依赖 mcp SDK，Python 3.9+ 即可（项目核心要 3.10+，MCP server 单独宽松）。

### 可选依赖（v8.0 双引擎 + 天文历）

```bash
# 启用 --engine tyme4py / --engine cross-check 双引擎交叉验证
# 真太阳时 EOT 已用 NOAA 公式（精度 ±15 秒，零依赖），不需要装 sxtwl
pip install -r requirements-optional.txt
```

---

## 学理合理性 · 600 年古籍直接支撑


| 工程实现                          | 学理出处                | 古籍         |
| ----------------------------- | ------------------- | ---------- |
| 三层独立打分（L0 原局 / L1 大运 / L2 流年） | 子平命理"体用之分"          | 沈孝瞻《子平真诠》  |
| 三派融合（扶抑 / 调候 / 格局）            | 民国徐乐吾整理的"子平三大法门"    | 徐乐吾《子平粹言》  |
| 格局为先                          | "先观月令以定格局，次看用神以分清浊" | 《子平真诠·论用神》 |
| 燥湿独立维度                        | "寒暖燥湿，命之大象"         | 余春台《穷通宝鉴》  |
| 印化护身 / 杀印相生                   | "杀印相生，威权万里"         | 任铁樵《滴天髓阐微》 |
| 食神制杀                          | "食神制杀，化煞为权"         | 沈孝瞻《子平真诠》  |
| 合处逢冲 / 三合解冲                   | "合处逢冲，冲处逢合"         | 《三命通会》     |
| 三刑独立                          | 寅巳申 / 丑戌未 / 子卯 / 自刑 | 《三命通会·论刑》  |
| 盲派应事 11 条                     | 段建业 / 王虎应 / 李洪成实战口诀 | 现代盲派       |


工程化部分（量化打分 / 权重数字 / 衰减系数）是经验值 + 历史回测调参，详见 `[references/methodology.md](references/methodology.md)`。

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

### Q8：能用真太阳时吗？精度多少？

**v7.2 起支持，v8.0 升级到天文级精度**。给 `solve_bazi.py` 加 `--longitude <东经度数>` 参数（如北京 = 116.4），自动启用：

- **经度差校正**：按时区中心 ±4 分/度（v7.2 起）
- **NOAA 均时差 EOT 公式**（v8.0 新加）：纯 Python 实现，零额外依赖，一年内 ±16 分钟波动，**精度 ±15 秒**

业内 99% 命理工具只做经度差，本工具是开源 SOTA。详见 [G. 天文级真太阳时](#g-天文级真太阳时v80--noaa-eot-公式)。

### Q9：能算两个人合不合吗（合伙 / 婚配 / 友谊 / 家人）？

**可以**。跑 `scripts/he_pan.py`，输出 4 维兼容性分（合作 / 婚配 / 友谊 / 家人），4 层结构性评分（五行互补 + 干支互动 + 十神互配 + 大运同步度）。详见 `references/he_pan_protocol.md`。

### Q10：怎么在 Claude / Cursor / OpenAI Codex 里直接当 Skill 用？

把整个目录放到对应 Skill 路径（Claude: `~/.claude/skills/bazi-life-curves/`；Cursor: `.cursor/skills/`），然后跟 AI 说："我想看人生曲线，八字 庚午 辛巳 壬子 丁未，男，1990 年"。AI 会自动读 `SKILL.md` → 跑 solve→score→handshake → 抛 R0+R1 校验 → 你答完 → 渲染 HTML + 流式 markdown 解读。30-60 秒完成。

### Q11 (EN)：Is this safe to use for queer / non-binary / aromantic / non-marital users?

**Yes.** v7 explicitly removes 600 years of feudal gender-discrimination rules. Pass `--orientation homo|bi|none|poly` and emotion-channel interpretations switch to neutral `relationship_mode` (7 categories: outward_attractive, competitive_pursuit, nurture_oriented, ambiguous_dynamic, low_density, balanced, self_centered). Every emotion paragraph is forced to declare: *"the chart only reflects relationship structure and energy patterns; it does NOT presuppose your partner's gender, marital status, or whether you have children — those are your modern choices, not encoded in the chart."* See `references/fairness_protocol.md §9-§10`.

### Q12 (EN)：Why open-source a "fortune-telling" tool?

Because the alternative is closed-source apps that (a) only use one school (扶抑/Fu-Yi), (b) hide their scoring logic, (c) embed feudal gender norms, and (d) have no falsifiability protocol. We believe traditional Chinese metaphysics, like any 600-year empirical tradition, deserves the same engineering discipline as modern statistics: deterministic output, falsifiable predictions, back-testing, source citations from primary classics (滴天髓 / 子平真诠 / 穷通宝鉴 / 三命通会), and zero discrimination by gender / orientation / marital choice. MIT license — bazi tooling should be a public good.

### Q13：能在 AI agent 里直接调用吗？（MCP）

**可以，v8.0 起内置 MCP server**。任何 MCP 兼容客户端（Claude Desktop / Cursor / Cline / Continue / Zed / Windsurf / Codex CLI / Aider / Devin / LangChain / LlamaIndex 等）都能通过 stdio JSON-RPC 直接调用本工具的 11 个 tools，无需 LLM 学 Skill 文档：

```bash
python scripts/mcp_server.py --inspect    # 列出 11 个 tools
python scripts/mcp_server.py --selftest   # 端到端自检
python scripts/mcp_server.py              # 启动 stdio 服务
```

11 个 tools 含 8 个项目原生 tool（solve_bazi / score_curves / mangpai_events / handshake / evaluate_handshake / he_pan / render_artifact / engines_diagnostics）+ 3 个 `[cantian-ai/bazi-mcp](https://github.com/cantian-ai/bazi-mcp)` 兼容别名（getBaziDetail / getSolarTimes / getChineseCalendar），cantian-ai 用户**零改动**可切到本工具，立刻获得三派融合 + R0/R1 校验 + fairness 等全部增强。

详见 [当 MCP server 用](#当-mcp-server-用v80--11-个-tools)。

### Q14：双引擎交叉验证是什么？什么时候要用？

**v8.0 新加**。命理软件最大事故源是节气交接（出生时刻在节令前后 30 分钟内）的月柱算错——一格之差，整张盘的格局/用神/大运全错。本工具默认装 `[lunar-python](https://github.com/6tail/lunar-python)`（行业事实标准）作为主引擎，并支持可选 `[tyme4py](https://github.com/6tail/tyme4py)`（节气基于"寿星天文历"sxwnl）作为副引擎并行计算：

```bash
pip install -r requirements-optional.txt
python scripts/solve_bazi.py --gregorian "1990-05-12 14:30" --gender M --engine cross-check --out bazi.json
# 输出含 engine_cross_check.is_consistent；false 时自动列出分歧位置 + 双引擎结果对照
```

**什么时候要用**：（a）出生时刻在节令前后 30 分钟内的；（b）历史回测要求最高确定性的；（c）你对单一日历库 bug 风险敏感的。**99% 普通命主用默认引擎即可**。详见 [F. 双引擎交叉验证](#f-双引擎交叉验证v80--业内首次)。

---

## 已知限制

诚实摆出来：

- **数据集偏小**：当前 `calibration/dataset.yaml` 只 5 人 / 15 事件，统计意义有限。希望社区贡献匿名八字 + 真实事件
- **从格 / 化气格 / 神煞**：✅ 全部已实现
  - 从格：v7.1 P5 (三气成象 detect) + 假从/真从 detect 覆盖
  - 化气格：✅ v7.4 已实现 · `_bazi_core.detect_huaqi_pattern`（甲己 / 乙庚 / 丙辛 / 丁壬 / 戊癸 五合 + 月令化神 + 化神有根 + 无破格 + 一票否决日干强根）→ `apply_geju_override` 自动走 `huaqi_to_<化神>` phase override
  - 神煞：✅ v7.4 已实现 · `_bazi_core.detect_shensha` 8 类（天乙贵人 / 文昌 / 驿马 / 桃花 / 华盖 / 孤辰 / 寡宿 / 空亡）；原局命中 → baseline ±0.3~~0.4；大运/流年逢 → 当年 ±0.5~~1.0；驿马 → sigma × 1.3 波动加大。影响刻意小，只调味，不参与主格局判定
- **真太阳时校正**：✅ v8.0 升级到天文级精度 · NOAA 均时差 EOT 公式（精度 ±15 秒，零依赖）+ 经度差校正；业内 99% 工具仍只做经度差近似（±16 分钟）
- **双引擎交叉验证**：✅ v8.0 新加 · `--engine cross-check` 同时跑 lunar-python + tyme4py，节气交接边缘 case 自动 warn
- **MCP server**：✅ v8.0 新加 · `scripts/mcp_server.py` 暴露 11 个 tools（含 cantian-ai/bazi-mcp 接口兼容别名），任何 MCP 客户端可接
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

- `[llms.txt](llms.txt)` —— 业界 [llmstxt.org](https://llmstxt.org/) 标准的项目摘要 + 文档地图
- `[AGENTS.md](AGENTS.md)` —— [agents.md](https://agents.md/) 标准的 AI Coding Agent 项目导航
- `[SKILL.md](SKILL.md)` —— Claude Skill / Cursor Skill / Codex Skill 通用主定义（YAML frontmatter）
- `[CITATION.cff](CITATION.cff)` —— Google Scholar / Zenodo 学术引用元数据

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


| 用户问题                 | 工具能给的答案路径                                                                   |
| -------------------- | --------------------------------------------------------------------------- |
| 我八字 X，未来 10 年哪几年要小心？ | `solve_bazi → score_curves → handshake → curves.json.turning_points_future` |
| 我八字 X，2027 年怎么样？     | `curves.json.points["2027"]` 4 维 fused 分 + events                           |
| 我八字 X，财运曲线？          | `curves.json` 中 wealth 维度 80 年走势 + key turning points                       |
| 我跟 Y 八字合不合？          | `he_pan.py` → 合作 / 婚配 / 友谊 / 家人 4 维兼容性                                      |
| LGBTQ+ 友好的命理工具？      | `--orientation homo/bi/none/poly` + relationship_mode 中性描述                  |
| 命理工具结果可复现？           | `score_curves.py --strict` + sha256sum 验证 bit-for-bit                       |
| 怎么避免 LLM 后视镜归因？      | 强制可证伪点格式 + 身份盲化输入 + confirmed_facts 写回                                      |
| 三派分歧怎么办？             | `dispute_analysis_protocol.md` 4 步推导                                        |


### 不要让 AI 做的事（红线）

详见 `[AGENTS.md` 第 4 节"修改算法时的硬性约束"](AGENTS.md) 与 `[llms.txt` "不要做的事"](llms.txt)。

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

## 版本时间线

完整 release notes 详见 `[CHANGELOG.md](CHANGELOG.md)`.

### v9.0.0（2026-04）· Precision-Over-Recall · 多流派交叉投票 · open_phase 逃逸阀

> 触发动因: 一类"印根足够却被旧算法误判为弃命从财"的边界 case 反思 (详见 §"v9 范式转换" + `references/diagnosis_pitfalls.md` §13-14 + `references/mind_model_protocol.md`).

7 个 PR 一览:

- **PR-1** 通根度严判 (`本气/中气/余气` 1.0/0.5/0.2) → 修假从误判 (`_bazi_core.py::compute_dayuan_root_strength` + `score_curves.py::apply_phase_override` 守卫)
- **PR-2** `--pillars` 模式弃用 + `he_pan` v8 入口守卫 + 多人编排器 (`solve_bazi.py` + `he_pan.py` + 新 `he_pan_orchestrator.py`)
- **PR-3** 盲派 `dayun` 层 fanyin/fuyin 4 个 detector + 大运首年触发机制 (`mangpai_events.py::detect_dayun_`*)
- **PR-4** 心智模型协议 (10 项戒律) + HS-R7 最高红线 (新 `references/mind_model_protocol.md` + `score_curves.py::hsr7_audit`)
- **PR-5** 罕见格全集 ~110 条 (子平 60 + 盲派 30 + 紫微/铁板 20) + 30 个算法可判定 detector + LLM inline fallback (新 `references/rare_phases_catalog.md` + `references/llm_fallback_protocol.md` + `rare_phase_detector.py`)
- **PR-6** 多流派加权投票 + `open_phase` 逃逸阀 (新 `_school_registry.py` + `multi_school_vote.py` · top1<0.55 OR gap<0.10 → `decision="open_phase"`)
- **PR-7** v9 集成: `score_curves.score()` 自动注入 `multi_school_vote` + 此 README v9 章节 + `CHANGELOG.md`

测试基线: **155 passed, 6 skipped, 2 xfailed** (其中 60 个新增测试覆盖 v9 模块).

### v8.0.0（2026-04）· 双引擎 + MCP server + EOT 真太阳时

- v8.0 双引擎交叉验证 (`--engine cross-check` 同时跑 lunar-python + tyme4py)
- v8.0 NOAA 均时差 EOT 公式 (精度 ±15 秒, 零额外依赖)
- v8.0 MCP server (`scripts/mcp_server.py` 11 个 tools, 含 cantian-ai/bazi-mcp 兼容别名)
- v8 校验回路重写 (废弃 R0/R1/R2/R3 自然语言转述 → discriminative question bank + AskQuestion + 贝叶斯后验 + phase_posterior 落地)

### v7 现代化版本（2026-04）· LGBTQ+ 包容 + 600 年语言重构

- 加 `--orientation` 参数支持 hetero/homo/bi/none/poly 取向
- 删除全部带性别歧视的古法规则（克夫旺夫 / 女命印多减分 / 配偶星弱减分等 6 条）
- emotion 维度纯中性描述：高 ≠ 婚姻顺利 / 低 ≠ 单身差
- 加 fairness_protocol §9-§10 现代化解读铁律
- 新加 `relationship_mode` 中性关系画像字段（7 种模式）
- handshake R0 文案重写：去颜值 / 去性别默认 / 去价值判断
- 烟测覆盖：5 种 orientation × spirit/wealth/fame 完全独立 × 性别对称性 × 旧版回归一致

> "把 600 年的命理学, 搬进 2026 年的语言, 然后再装一道 v9 的诚实闸门——
>  让算法在没把握的时候敢说『我不知道』, 把终极裁定权还给用户。"

