# 命局误判陷阱手册（diagnosis_pitfalls.md）

> 本文件固化"已经踩过的坑"，每个坑都对应一个真实案例 + 修复后的规则。
> 跑新八字之前，先扫一遍 §0 红线表；跑完之后，对照 §1-§8 自检。

## §0 红线（违反任意一条 → 立即停下重判）

| # | 红线 | 触发条件 | 处理 |
|---|------|----------|------|
| R1 | **体质画像被 ✗** | handshake Round 1 第一条（physiology）用户回答"不对" | 不论其他几条命中率都要先停下，重判 climate / yongshen / strength |
| R2 | **用神反向校验 = "无"** | yongshen 五行在原局完全不见（不透干、不通月令、不藏地支） | 拒绝该用神，回退到 climate 用神或回退到中和调候 |
| R3 | **格局识别 reject ≠ 空 但仍硬套** | detect_geju 返回 rejected 但 LLM 在分析时仍按该格局解读 | 严格按 primary=null 走，不能借口"近似格局"硬套 |
| R4 | **Round 1+2 命中 < 4/6 仍出图** | handshake 总命中率不达阈值 | 一律不出图，告诉用户"八字十有八九不准，先核对时辰" |
| R5 | **LLM 在拿到结果之前先讲故事** | LLM 在工具未返回前就生成"基于 X 你是 Y" | 必须先 solve_bazi → score → handshake → 再讲推论 |
| R6 | **class_prior 标签直接吐给用户**（v7.5）| 输出里出现"你是 [城市知识分子 / 体制内 / 草根]"等身份命名 | 立刻改写为情境描述；详见 §13.1 + class_inference_ethics §3 |
| R7 | **未来 era_window 写得跟过去一样细**（v7.5）| era.span 上限 > current_year 但 LLM 写"你 X 年会经历 Y" | 强制降级为"方向性提示"，禁出现具体年份事件；详见 §13.3 |
| R8 | **folkways_anchor R2 题缺 7 铁律**（v7.5）| 缺 ≥ 2 个 suggested_direction / 缺时间窗 / 缺证伪点 / confidence=low | 不允许输出，按 §13.7 + handshake_protocol §5.4 重写 |
| R9 | **illustrious_candidate + R3 ✗ 仍写"显赫家世"**（v7.5）| primary_class = illustrious_candidate 且 R3「整体结构」标 ✗ | 强制降级，禁用"显赫/名门/名利双收"措辞；详见 §13.5 |

---

## §1 月令决定论（最容易犯）

**典型反例结构**：日主己土 + 月令子水 + 干头多火多燥土
- 月令子水 + 身弱 → 旧规则判"寒湿命，用神火土"
- 实际：干头四字均为火 / 燥金 / 燥土 = 燥实命，用神 = 水
- 体感反馈通常是"从小怕热、贪冷"——直接证伪"寒湿"

**修复**：
- `_bazi_core.climate_profile()` 把"燥湿"做成独立维度，不依赖月令
- 干头分（权重 0.6）+ 地支分（权重 0.4）→ 总分 → label
- `select_yongshen()` 把 climate 放在身强弱之前

**自检规则**：
> 月令只代表"季节寒暖"。**干头能量场**才是"体感"和"性格明面"的真正决定者。
> 月令子水 ≠ 寒湿命；月令午火 ≠ 燥实命。看的是干头 4 字 + 地支辅助。

---

## §2 干头能量场被忽略

**案例**：同上。
- 旧脚本只在 `_wuxing_count` 里把干和支按权重相加算"总量"
- 没有"干头独立画像"——所以"干头全燥但地支全湿"这种**外燥内湿**结构看不出来

**修复**：
- `climate_profile.干头分` 和 `地支分` 分别独立输出
- 当 `干头分 ≥ 6 且 地支分 < -2` → 触发新 label "外燥内湿"
- 反之触发 "外湿内燥"

**自检规则**：
> 看一个命局首先看 4 个天干。天干是"上层场"（外显、体感、社交人格），地支是"底盘"（内蕴、财源、隐藏特质）。两者的方向可以完全相反——这种命主体感会非常分裂（如外热内寒、外强内弱）。

---

## §3 用神选择没做反向校验

**案例**：曾出现过用神 = 木，但原局 4 柱完全没有木气也没有月令木 → 用神空中楼阁。

**修复**：
- `score_curves._yongshen_reverse_check()` 对每个候选用神判定 usability：
  - 强：透干 + 通月令
  - 中：透干 OR 通月令
  - 弱：仅藏地支非月令（需大运 / 流年透出才能流通）
  - 无：完全不见 → 拒绝该用神
- `apply_geju_override()` 在覆盖前后都跑反向校验

**自检规则**：
> 用神不是"应该是什么"，而是"原局里能取到什么"。取不到的用神 = 没用神。
> 反向校验"无" → 一定要回退或换思路，不能硬上。

---

## §4 格局派识别太粗（缺成立条件）

**典型反例结构**：身弱 + 月干透伤官 + 财不透干仅通月令
- 旧规则：月干透伤官 + 见财 → 判"伤官生财格" → 用神覆盖为水
- 但身弱不能任伤官 + 财不透干 → 不构成完整伤官生财格
- 结果：用神方向偶然蒙对（水），但"伤官生财"的应事方向（盲派"伤官见官"等）全错

**修复**：每个格局都加成立条件
- 伤官 / 食神生财格：身不弱 + 财透干或通月令
- 杀印相生格：印有根（透干 OR 通月令）+ 身不极弱
- 官印相生：官 / 印同时透干 + 印有根
- 食神制杀：食 / 杀同时透干，且食有根
- 财格用财：身强 + 财在月令 + 食伤生财链通

不成立的格局放进 `rejected` 字段，附明确原因。

**自检规则**：
> 格局派 ≠ "看到月干透什么就是什么格"。要看：
> 1. 月令是否当令？
> 2. 月干 / 时干透出？
> 3. 身能不能任？
> 4. 用神 / 喜神 在原局有没有真根？
> 任何一条不达标 → 不是这个格。

---

## §5 时柱权重被低估

**典型反例**：时柱十神（如时柱印 / 时柱伤官）独立 trait
- 旧脚本时柱权重和年柱一样
- 但 30 岁后人生进入"时柱期"，时柱的影响力被严重低估

**修复**：
- 30 岁后大运 + 流年互动时，时柱地支贡献权重 +30%
- 时柱十神（如时柱印 = 老年靠子女 / 文化、时柱伤官 = 晚年仍有创造力）单独抽取做 trait 候选

**自检规则**：
> 0-15 岁看年柱、16-30 看月柱、30-45 看日柱、45+ 看时柱。
> 时柱不是"补充信息"——是 30 岁后的主战场。

---

## §6 体感 / 物理反馈进不来 handshake

**典型反例**：某些"上燥下寒"型盘曾反复跑了 4 轮才发现"湿寒"判错——只要在 Round 1 第一条问"你怕热还是怕冷"就 1 句话搞定。

**修复**：
- handshake 新增 `build_physiology_traits()`，从 climate_profile 机械导出体质画像
- Round 1 强制第一条 = 体质画像（最高把握 + 最难骗）
- 体质画像被 ✗ → 列为 R1 红线，不论其他命中率都停下重判

**自检规则**：
> 用户对"事件"的回忆不可靠（年份会错、原因会美化），但对"体感"的回忆很可靠（终生稳定）。
> "怕热 / 怕冷"、"出汗多少"、"入睡难易"、"手脚温度"是命局结构最直接的物理校验。

---

## §7 LLM 后视镜叙事（最隐蔽）

**症状**：
- 用户说 "2024 升职了" → LLM 立即推断"2024 是用神到位 + 官星到位"
- 但其实 2024 用神可能没到位，是别的机制（如比劫年但人靠岳父助力）
- LLM 把"事件"反推成"命理逻辑"，看似自洽，其实是拟合

**防御**：
- LLM 在分析关键年时，必须先**写出推论过程**（"我看到 X → 因此推 Y"）
- 推论过程要有可证伪点（"如果 Y 不成立，那 X 应该呈现 Z 现象"）
- 用户可以反驳推论过程，不仅反驳结论

**自检规则**：
> 看到一个事件 → 不要立刻反推命理逻辑。先看：流年大运五行透了什么 / 冲什么 / 合什么，再看十神，再看格局，再看可能的应事方向（多种），最后才匹配事件。
> 如果只有一种解释能匹配事件——多半是后视镜。

---

## §8 命中阈值偏松

**症状**：Round 1 + Round 2 一共 6 条命中 3 条就出图 → 实际上不准。

**修复**：
- Round 1 ≥ 2/3 才进 Round 2
- Round 1 + Round 2 必须 ≥ 4/6 才出图
- 体质画像（physiology）单独是 R1 红线

**自检规则**：
> 出图前问自己一句："如果命中率不达标我会怎么样"。如果回答"那我就不出图"——继续。如果回答"那也得给用户一个交代"——停下，明确告诉用户"八字不准我不能出图"。

---

## 跑新八字时的执行清单

```
[ ] 1. solve_bazi → 拿到 strength + climate
[ ] 2. 看 climate.label：是否极端（燥实 / 寒湿 / 外燥内湿 / 外湿内燥）？是 → climate_override 触发
[ ] 3. 看 yongshen._reverse_check.usability：≠ "无" 才能继续
[ ] 4. score_curves → 看 geju.primary：null 就别强行套格局；看 geju.rejected
[ ] 5. handshake → Round 1 第一条必是体质画像
[ ] 6. 用户反馈 → 体质画像被 ✗ → 立即停下重判
[ ] 7. Round 1 ≥ 2/3 → Round 2；< 2 → 直接告诉用户八字不准
[ ] 8. Round 2 → 合计 ≥ 4/6 才出图
[ ] 8.5 Round 0+1+2 ≤ 2/6 → 【v7 强制】跑 handshake --dump-phase-candidates → 跟用户讨论反向假设
[ ] 9. 出图后的 LLM 分析：每个推论必须有"推论过程"+"可证伪点"
```

---

## §12 「相位反向陷阱」（v7 新增 · 2026-04 真实 case study）

### 背景：本协议的诞生案例

一类典型边界 case：日主己土 + 干头多火多燥土 + 月支水：

- **默认 Skill 推法**：日主己土弱 + 用神水（climate_override 已触发，方向对）→ 但 emotion / spirit / wealth 的整体读法仍按"身弱被克 + 印化杀"框架展开 → R0+R1 命中率 ≈ 30%
- **反向推法**：丙火财星主事 + 日主借力 + 上燥下寒 → 命中率 ≈ 90%

幅度差 60%。这是「**算法的相位选择反了**」，不是八字错。

### 这个案例暴露的盲区

1. `select_yongshen` 的 climate_override 已经把用神改对了（水），**但相位框架还是按"日主主导"**走；
2. `apply_geju_override` 的格局识别没识别出来（4 个 detect 在 v7 之前都没有）；
3. `evaluate_responses` 在命中率低时只会输出 "high/mid/low/reject"，**没有第三条路 = 反向假设**；
4. 用户最终是靠 LLM 人肉反推救回来的——下次用户的 LLM 不一定会做。

### v7 的修复

加入 4 个 detect（P1-P4，详见 `phase_inversion_protocol.md`）+ `score_curves --override-phase` + `handshake --dump-phase-candidates` + `SKILL.md Step 2.6` 强制工作流。

典型边界 case 跑出来的 dump：

```
$ python scripts/handshake.py --bazi /tmp/.../bazi.json --dump-phase-candidates --default-hit-rate "2/6"
[handshake] phase-dump → /tmp/.../phase_dump.json: 2 个相位反演候选 ↓
  · climate_inversion_dry_top  (P3_climate_inversion, score=3/3)
      → 调候反向·上燥下寒（用神锁水：让地支水透干，制干头燥）
  · true_following  (P4_pseudo_following)
      → 真从格 · 日主根被破或无根，按从神方向走
```

LLM 看到这个 dump 后**必须**按以下话术跟用户沟通（不允许改）：

> 命中率 2/6 比较低，但这**不一定意味着**八字错。
> 我有 2 个相位反向假设，最有希望的是「**调候反向·上燥下寒**」——
> 你的命局表面看是寒湿命（月令水旺 + 日支也接寒湿），但天干一片燥火土，
> **真正主导你体感和性格的是天干的燥**，不是地支的寒。
> 现实表现可能是：自小怕热不怕冷 / 性格急躁 / 需要"水"来润降。
>
> 要不要我按这个反向假设重跑一次曲线？

用户同意 → 跑 `--override-phase climate_inversion_dry_top` → 重新校验 → 进 Step 3。

### 这种陷阱的通用形态

| 表象 | 真实相位 | 学理依据 |
|---|---|---|
| 日主弱 + 月令克泄 → 默认按身弱补印 | 弃命从势：从财 / 从杀 / 从儿 / 从印 | 《滴天髓·从象》|
| 月令旺神成势 + 透干 → 默认按日主为主 | 旺神得令反主事 | 《穷通宝鉴·总论》|
| 月令寒 / 燥（按月令调候）| 干头 vs 地支对冲（外燥内湿 / 上燥下寒）| 《穷通宝鉴·四时调候》|
| 日主有微根 → 默认不从 | 微根被合冲拔 → 真从 | 《子平真诠·从化篇》|

### 🚨 不允许做的事

- ❌ R0+R1 ≤ 2/6 时第一句话就判"八字错 / 时辰错"
- ❌ 跳过 `--dump-phase-candidates` 直接重跑 / 直接出图
- ❌ 反演重跑后假装"还是默认相位"——必须明确告知用户「相位 = X」
- ❌ 4 个 detect 都未触发时硬要反演（n_triggered=0 时直接走时辰扫描）

---

## §13 「时代-民俗志层陷阱」（v7.5 新增 · 2026-04）

> 把 era_window + folkways + class_prior 引入解读后，新出现 7 类典型踩坑。
> 每跑一段历史段叙事之前对照这一节自检。

### §13.1 把 class_prior 当作"用户身份"直接吐出

**症状**：LLM 看到 `class_prior_top1 = "urban_state_or_educated"` 后，在输出里写"你是城市知识分子家庭出身"、"你属于体制内中产阶层"。

**为什么错**：
1. class_prior 只是**概率分布的 top1**，不是事实；
2. 这种叙事会给用户贴**身份标签**，违反 `class_inference_ethics.md` 的核心原则；
3. 用户实际可能是 urban_state_or_educated 0.375 + grassroots_self_made 0.144 的混合形态——简单贴 top1 标签会丢掉重要分量。

**修复**：
- LLM 把 class_prior 当**思维材料**用，**不允许**作为输出语言
- 输出时只能描述"情境 / 场景 / 处境"，不允许出现"你是 X 阶级 / X 家庭出身"这类身份命名
- 详见 `class_inference_ethics.md §3 替换字典`

**自检规则**：
> 看到 class_prior 的内部标签后，把"你是 [标签]"在心里翻译成"你那段时间所处的环境通常会让人接触到 [具体情境]"——后者才是允许输出的形态。

---

### §13.2 把"时代背景"贴成"你一定经历了 X"

**症状**：LLM 看到 era_window = `cn_reform_late_90s` 后，直接写"你那年家里下岗了 / 转学了"。

**为什么错**：
- era_window 是**社会层面**的时代底色，不是**个体层面**的事件
- 同一个时代里，绝大多数人不会经历"下岗"——给的是概率背景，不是必然事件

**修复**：
- 必须按 `folkways_inference_prompt.md` 的 7 步推理流走：先建立时代底色 → 再用命局 anchor 推可能事件 → 必须给 ≥ 2 个 suggested directions 让用户选 → 必须有可证伪点
- 严禁把 era_window 的关键词直接套到用户身上（如 era 关键词含"下岗" → 不允许直接写"你家下岗了"）

**自检规则**：
> 当你想写"你 X 年经历了 Y"时，停一下。问自己 5 个问题（folkways_protocol §4 五项自检）：时间窗 ±2 年？ era_window 对得上？class_marker 对得上？yongshen / 命局事件 anchor 在那个区间？给了 ≥ 2 个备选 direction？任何一项答不上 → 改写为"那段时间最可能的几种情境是 a / b / c，是不是其中之一？"。

---

### §13.3 把"未来 era_window"也细写

**症状**：LLM 给 2030-2034 那段写得跟 2010-2014 一样详细，列出"你那时会经历 AI 行业 X 周期 / 新能源 Y 政策"等。

**为什么错**：
- 协议红线："**前事细，后事粗**"
- 未来段不存在"已经发生"的可证伪事件——细写就是在过拟合不存在的事实

**修复**：
- 对 `current_year` 之后的 era_window，自动转为"方向性提示"，不写具体节点
- 仅给 2-3 句"该段时代倾向 X 类机会 / Y 类风险，对你的 [大运取向] 是 [助 / 阻]"
- 不允许写"你在 2032 年会 X"

**自检规则**：
> 看 era_window.span：上限 > current_year → 自动降级为"方向性提示"模板，不允许出现"你 X 年 / 你那年"这种细节句式。

---

### §13.4 folkways 细节用错时代

**症状**：给 2010-2015 段写"你那时正赶上微博兴起、QQ 空间流行"。

**为什么错**：微博 2009 兴起，2013 后才被微信替代；QQ 空间高峰是 2008-2011。把不同时代的 folkways 串错 → 用户立刻反驳"那时早就没人用 QQ 空间了"。

**修复**：
- 每个 folkways 细节必须过 `folkways_protocol §4` 的"时间窗"自检
- 严禁把同一组 folkways 套在所有时代（移动互联网 ≠ 短视频时代 ≠ AI 时代）
- 优先参考 `references/folkways_examples/*.md` 的样本时代切片

**自检规则**：
> 写每条具体 folkways 之前，问自己："这个东西的真实流行窗口是几年到几年？"对不上 → 换。

---

### §13.5 给 illustrious_candidate（古典格局疑似显赫）写"显赫家世"

**症状**：class_prior 出 `illustrious_candidate` 后，LLM 写"你父辈/祖辈中有名望人物"。

**为什么错**：
- 古典命书有 survivorship bias —— 流传下来的命例 99% 是显赫案例，所以"年/月柱财官印聚合"这种结构在古书里被高估了 5-10 倍
- 真实分布里这种结构主要出现在**普通中产 / 体制内** + 极少数显赫案例
- 直接贴"显赫家世"会让 99% 的用户觉得"完全不对"

**修复**：
- handshake R3「原生家庭①·整体结构」被 ✗ 时**强制降级**：禁用"显赫 / 名门 / 名利双收"
- 改写为"年/月柱财官印聚合的结构在你身上没有外显为外部资源 / 名望——结构性画像被现代环境改写了"
- 详见 handshake_protocol §5.4 + family_profile.md

**自检规则**：
> illustrious_candidate 标签出现时，先看 R3 命中：未通过 / 0 命中 → 必须降级表达；2/2 命中 → 才允许谨慎说"父辈/祖辈中可能有人在某领域有可识别的位置"，但仍不允许"显赫"措辞。

---

### §13.6 era_windows 与大运对齐用错 situation

**症状**：用户大运 1995-2004 是壬寅，对应 era_window 是 cn_reform_late_90s (1995-1999) + cn_wto_age (2000-2007)，alignment situation = `B_dayun_spans_eras`。LLM 把整个壬寅大运用同一段时代叙事写完，没区分前后两个 era。

**为什么错**：1995-1999 vs 2000-2007 是两个不同时代底色（朱镕基改革末段 vs 入世后开放高峰）。混在一起写会丢掉"时代切换"这个最有信息量的事件。

**修复**：
- 按 `dayun_review_template.md §2 三种 alignment situation` 分别处理：
  - **A_resonance**（一对一对齐）：直接写一段
  - **B_dayun_spans_eras**（大运跨多个 era）：明确分段写"前 X 年是 era_A 底色 / 后 Y 年是 era_B 底色，命主在切换点 (Z 年) 经历了 ..."
  - **C_era_spans_dayuns**（一个 era 跨多个大运）：在 era 叙事里明确指出"你的 [大运 1] 和 [大运 2] 都活在同一时代底色里，但因为大运不同 → 你对它的体感是 ..."

**自检规则**：
> 看 alignment.primary_situation 字段，按 dayun_review_template.md §2 走对应分支，禁止"用一个时代覆盖整个大运"。

---

### §13.7 民俗志锚点（folkways_anchor）写得跟普通历史锚点一样模糊

**症状**：handshake `folkways_anchor_seeds` 已经给了 era_window + suggested_directions，LLM 却只写"你 X 岁那年财富大波动"——丢失了时代上下文。

**为什么错**：违反 `handshake_protocol §5.4` 的 7 条铁律。folkways_anchor 的价值就在于"时代镶嵌 + 给用户具体情境选项让他认领"。

**修复**：每个 folkways_anchor R2 题必须包含：
1. **时间窗 ±1-2 年**（禁"小时候"）
2. **1 句 era_window 背景**（如"1998 ± 1 年是国企整顿 + 朱镕基改革高峰"）
3. **≥ 2 个 suggested_direction**（让用户选，不要问"是不是 X"）
4. **明确 1 句可证伪点**
5. **过 folkways_protocol §4 五项自检**
6. **遵守 class_inference_ethics**（禁身份命名）
7. **confidence 必须 high 或 mid**

**自检规则**：
> 写完每个 folkways_anchor R2 题，回头数一下：1）有没有具体年份范围？2）有没有铺一句时代背景？3）有没有 ≥ 2 个备选方向？4）有没有明确证伪点？任何一条缺失 → 不允许输出。

---

### 跑 v7.5 时代-民俗志层的执行清单（叠加在 §1-§12 之上）

```
[ ] 1. 跑 _class_prior.py → 拿 primary_class（仅供内部 reasoning）
[ ] 2. 跑 _zeitgeist_loader.py → 拿 era_windows_used + alignments
[ ] 3. 跑 handshake.py --with-zeitgeist → 拿 folkways_anchor_seeds
[ ] 4. 写每个 era_window 叙事时：
       [ ] 走 §13.2 7 步流程（先底色 → 再 anchor → 再 directions）
       [ ] 过 folkways_protocol §4 五项自检
       [ ] 严守 class_inference_ethics（禁身份命名）
       [ ] era.span > current_year → 自动降级为"方向性提示"
[ ] 5. 写大运评价时：
       [ ] 看 alignment.primary_situation → 按 dayun_review_template §2 对应分支走
       [ ] 跨 era 的大运必须明确分段
[ ] 6. 写 family 段时（仅在用户问 family 时）：
       [ ] R3 命中 0/2 → 不展开
       [ ] illustrious_candidate + R3 ✗ → 强制降级（禁"显赫"措辞）
[ ] 7. 写 folkways_anchor R2 题时：
       [ ] 7 条铁律全部满足才允许输出
       [ ] confidence < mid → 直接丢，不允许 low
```

---

### 这一类陷阱的本质

v7.5 把"时代背景 / 民俗志细节 / class_prior"当成 LLM **思维材料**而不是输出语言。
LLM 容易踩的坑都来自一个方向：**把内部 reasoning 直接吐给用户**。

护栏的核心是 4 个分离：
1. **概率 vs 事实**：class_prior top1 ≠ 用户身份；folkways suggested_direction ≠ 一定经历
2. **思维材料 vs 输出语言**：class_inference_ethics §3 替换字典是必经环节
3. **后事详 vs 前事粗**：current_year 是"详写 / 粗写"的硬边界
4. **骨架 vs 现场**：era_windows_skeleton 是骨架，folkways 细节由 LLM 现场推、过自检后才能输出

---

## §14 「detector 满分但默认输出反向」（v8 新增 · 2026-04 真实 case study）

> 本节是 v8 校验回路重构的命名 case，所有 phase_decision 实现都以此为 regression 基准。

### §14.1 典型边界 case · "detector 满分但默认输出反向"

```
代表结构：日主己土 + 月令子水 + 干头多火多燥土 + 时支带印的中根盘
detector 命中：
  - P5 三气成象 4/4（水/木/火三气流通 + 日主真弱 + 含连环生化）
  - P3 调候反向 3/3（上燥下寒，干头多燥，地支多湿）
  - P4 假从触发（日主无根从财但月干透出庚金破格 → 假从）
默认 bazi.json 输出：
  strength = 弱
  yongshen = 火
  phase = day_master_dominant   ← 错！6 个 detector 都说不是这个 phase
```

**为什么默认输出错？**

旧 v7.4 架构里 `solve_bazi.py` 单线程跑 `select_yongshen()` → 只看 strength.label = 弱 + climate = 上燥下寒 → 选用神 = 火 → 写 `phase = day_master_dominant`。`detect_all_phase_candidates` 的 4 个 detector 输出**根本没有进 `bazi.json`**，只在 `phase_inversion_loop.py` 的"事后兜底"流程里被消费。换言之：**算法已经知道这盘走反了，但产品不知道**。

跑出来的解读自然按"日主弱用神火"叙事，**与真实体感（怕热贪冷、流年节奏对不上扶身建议）完全相反**。

### §14.2 修复 · phase-driven validation loop（v8）

[phase_decision_protocol.md](phase_decision_protocol.md) 把 phase decision 提到 `solve_bazi.py` 阶段的强制一等公民：

1. `solve_bazi.py` 末尾必须调 `decide_phase(user_answers=None)` 算先验，把 `phase` + `phase_decision` 写进 `bazi.json`，`is_provisional=True`
2. `score_curves.py` 默认读 `bazi.phase.id` 走 `apply_phase_override`，不再"忘读"
3. handshake 通过 [discriminative_question_bank.md](discriminative_question_bank.md) 5 维度 28 题让用户校验，answers 经贝叶斯后验落地
4. 后验 ≥ 0.6 → adopt；< 0.4 → 报"算法无法落地，请核对时辰"

### §14.3 自检规则

> **bazi.json 必须永远有 `phase` 字段**（即使 `id = day_master_dominant`，也要显式写出，不能依赖默认值）。
> **`score_curves` 的主路径必须读 `bazi.phase`**，`--override-phase` 退化为调试用 flag。
> **`solve_bazi` 的 `select_yongshen` 输出顶层 `strength` / `yongshen` 仅作"默认假设"留底**，下游消费看 `phase_decision.yongshen_after_phase`。

### §14.4 regression 测试

[calibration/phase_dataset.yaml](../calibration/phase_dataset.yaml) 把这一类边界结构列为主 regression case：

- `expected_phase = floating_dms_to_cong_cai`（或 `floating_dms_to_cong_er`，视 D3 答案而定）
- 仅先验下 `decide_phase` 必须把 `day_master_dominant` 后验压到 < 0.30
- 含 `simulated_user_answers` 时 top-1 后验 ≥ 0.85

### §14.5 为什么这个坑值得单独命名

这一类陷阱的本质：**算法的 identification 能力（穷尽候选）远超过产品的 disambiguation 接口（让用户在候选间投票）**。旧架构把 disambiguation 做成"事后兜底"，所以 identification 的成果被废了一半。v8 把两者强制对齐：identification 算几个候选，disambiguation 接口必须在这几个候选里选一个，不能默默回退到默认相位。

> 跑任何新八字时：先看 `phase_decision.candidates` 数量，再看 `phase_decision.confidence`。candidates 多 + confidence = low → 必须走 AskQuestion 校验，不能跳过直接出图。
