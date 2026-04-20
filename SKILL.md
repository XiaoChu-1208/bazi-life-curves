---
name: bazi-life-curves
description: >-
  根据八字（或公历生辰）生成可调时间区段的「人生曲线图」+ 一生四维度评价 + 大运评价 + 关键年份大白话解读；
  也支持「合盘」—— 用户提供 ≥ 2 份八字，从合作 / 婚配 / 友谊 / 家人 4 个维度做兼容性分析。
  **v6 升级 + v7 现代化**：曲线覆盖 4 维度——精神舒畅度 / 财富 / 名声 / **关系能量**（v6 新增 · v7 重命名「感情→关系能量」+ 加 `--orientation` 取向参数支持 LGBTQ+ / 不婚），每维 2 条曲线（粗实线=当年值为主线，细虚线=5 年区段趋势为辅）= 8 条线。
  **v7 现代化**删除了所有"克夫 / 旺夫 / 配偶星弱减分 / 女命印多减分 / 女命食伤减分 / 男命比劫扣分高于女命"等带性别歧视和价值判断的古法规则，emotion 高 ≠ 婚姻顺利、emotion 低 ≠ 单身差，纯中性描述。详见 fairness_protocol.md §9-§10。
  采用「格局为先 + 三派交叉打分」（格局派识别主格局优先覆盖用神 → 扶抑 / 调候 / 格局再融合）+ 盲派事件断 + 烈度修正
  + 印化护身后处理（杀印相生 / 伤官见官印护 自动减压）+ 历史回测 + 置信带，保证准确、公正、可证伪。
  **v7.4 新增**：①「化气格」自动识别（甲己 / 乙庚 / 丙辛 / 丁壬 / 戊癸 五合得月令 + 化神有根 + 无破格 → 日主借合化易主，扶抑全部翻转）；
  ② 神煞分布检测（天乙贵人 / 文昌 / 驿马 / 桃花 / 华盖 / 孤辰 / 寡宿 / 空亡），命中原局 → 终生 baseline 微调（±0.3~0.4），
  大运 / 流年逢 → 当年微调（±0.5~1.0）+ 驿马触发 sigma × 1.3（波动加大）；神煞影响刻意小，只参与曲线调味，不参与相位决策。
  关系能量维度走**独立通道**（不参与三派融合，从配偶星 / 配偶宫 / 比劫 / 桃花 / 大运冲合单独打分），与 v8 D2 关系结构题库配套。
  盲派不进 25% 融合权重，仅做应事断 + 烈度修正（详见 references/mangpai_protocol.md）。
  合盘（he_pan.py）用 4 层结构性评分：五行互补 + 干支互动（合冲害 / 三合 / 桃花 / 贵人） + 十神互配（按关系类型）+ 大运同步度。
  起运岁优先用 lunar-python 精算（gregorian 模式自动），pillars 模式可通过 `--qiyun-age` 显式指定。
  用户可指定评分年龄区间和拐点预测窗口；三派分歧大的年份合并进关键年份评价，由 LLM 综合命局做有论据的解读。
  **v8 校验回路全面重写**：废弃 v6/v7 的"R0/R1/R2/R3 自然语言转述 + 命中率 N/M 判定 + R0' 反迎合探针 + 事后 phase_inversion_loop 兜底"，
  整体替换为 **discriminative question bank（5 维度 ~28 题）+ 宿主 AskQuestion 结构化点选 + 贝叶斯后验 + phase_posterior 落地**：
    · **identification（算法）**：detector 穷尽 14 个候选 phase 并算先验（住在 `_bazi_core.detect_all_phase_candidates`）
    · **disambiguation（用户）**：Agent 用宿主 `AskQuestion` 一次性抛全部 N 题点选 UI，禁止把题面用自然语言转述让用户口头答"对/不对"
    · **posterior decision（算法）**：`phase_posterior.py` 算后验，≥ 0.80 high adopt / 0.60-0.80 mid adopt / 0.40-0.60 触发追问轮 / < 0.40 拒绝出图
    · 5 维度：D1 民族志 × 原生家庭 / D2 关系结构 / D3 流年大事件（动态生成）/ D4 中医体征 / D5 自我体感；硬体征（D1/D3/D4）权重 2× 软自述（D2/D5）
    · 典型边界 case：某些盘 6 个 detector 满分但旧默认输出仍是 day_master_dominant，详见 `references/diagnosis_pitfalls.md` §14。
  **v5 流式输出 + 输出格式可选**：校验通过后先问用户「要纯 markdown 流式（A · 默认 · 最快）还是 markdown 流式 + HTML 交互图（B · 多等 5-15 秒）」；
  无论选 A / B，所有文字分析都按节流式输出（写完一节立刻发出，不批量憋整段），HTML 渲染（如选）放最后一步。
  Claude 宿主下 HTML 是含 marked.js + Recharts + details 折叠的交互式 Artifact，
  整图综合分析、一生四维度评价（精神 / 财富 / 名声 / 感情）、大运评价（每 10 年一段，含感情看点）、关键年份评价（peak/dip/shift），
  先在对话流式发完文字，再可选打包成 HTML，用户可自由展开收起。
  当用户提供四柱 / 公历生辰，或要求绘制人生曲线 / 大运流年走势 / 命理趋势图 / 八字曲线 / 合盘 / 婚配 / 合伙时触发。
  触发词：八字曲线、人生曲线、大运曲线、流年走势图、命理趋势图、bazi curve、life curve、
        合盘、婚配、夫妻合婚、合伙人合盘、友谊合盘、家人合盘、八字合盘、synastry、compatibility。
---

# Bazi Life Curves（含合盘）

两条主线：

1. **单盘**：将八字命理结构转化为可调时间区段的「人生曲线图」。**v6 升级为四维度**（精神 / 财富 / 名声 / **感情**）× 2 类曲线（当年值粗实线 + 5 年区段趋势细虚线）= **8 条线**。「格局为先」识别主格局后按三派交叉打分，自动并入印化护身的后处理修正；**感情维度走独立通道**（不参与三派融合，从配偶星 / 配偶宫 / 比劫 / 桃花 / 大运冲合单独打分）。
2. **合盘**：用户输入 ≥ 2 份八字 + 关系类型（合作 / 婚配 / 友谊 / 家人），脚本算出 4 层结构性评分（五行互补 + 干支互动 + 十神互配 + 大运同步度），LLM 在对话里给出"亮点 + 摩擦点 + 怎么用 / 怎么避"的人话解读。**整体动作逻辑与单盘一致：先校验每份八字再做合盘评分；合盘暂未升级到 v8，仍走旧 R0/R1 校验路径（详见 §2.6 caveat）。**

## 用户视角速览（先告诉用户怎么用）

如果用户问 "怎么用 / 怎么触发 / 怎么开始"，请先把 `USAGE.md` 第一节"30 秒速览"完整复述给用户，然后等待用户给出八字 / 生辰。完整用户文档在 `USAGE.md`。

**关键三句话告诉用户**：

1. 你只要丢一句话给我：
   - **单盘**：八字四柱 + 性别 + 出生年，或公历生辰 + 性别
   - **合盘**：≥ 2 份八字 + 关系类型（合作 / 婚配 / 友谊 / 家人，可选）
   剩下我全自动跑。
2. **出图 / 合盘前**我会跑 v8 校验回路（一次抛 ~20-25 道结构化点选题）：
   - **算法先穷尽 phase 候选**：14 个候选相位（默认日主主导 / 弃命从财从杀从儿从印 / 旺神得令 4 种 / 调候反向上燥下寒 / 假从真从 / 化气格 …），detector 给每个候选算先验
   - **你来在候选间投票**：我会用 IDE / 客户端的结构化点选 UI（AskQuestion）把 5 维度 ~28 道选择题一次抛给你
     - **D1 民族志 × 原生家庭**（出生时家境 / 父母在场度 / 兄弟姐妹 / 出生地）—— 客观事实，权重 2×
     - **D2 关系结构**（吸引对象画像 / 谁更主动 / 经济角色 / 依赖方向）—— 自述，权重 1×
     - **D3 流年大事件**（动态生成：找 phase 候选间最分歧的几个已活过年份问"X 岁那年方向感"）—— 客观事实，权重 2×
     - **D4 中医体征**（寒热 / 睡眠 / 脏腑 / 体型 / 食欲 / 情志六问）—— 客观事实，权重 2×
     - **D5 自我体感**（压力默认策略 / 钱的态度 / 与权威关系 / 创造性出口）—— 自述，权重 1×
   - **贝叶斯后验落地**：你答完后我跑 `phase_posterior.py` 把 prior × likelihood 算成后验：
     - top-1 后验 **≥ 0.80** → 直接 adopt（high confidence），按该相位出图
     - **0.60–0.80** → adopt，但标 mid confidence + caveat
     - **0.40–0.60** → 自动追问轮（top-2 候选间最 discriminative 的 2-3 题）
     - **< 0.40** → 拒绝出图，告诉你"算法无法落地，请核对时辰 / 性别"
   - 合盘场景：单盘 v8 已上线，**合盘场景暂未升级到 v8**，仍走旧 R0/R1 校验（详见 §2.6 caveat）
3. 出图是交互式 HTML：曲线 + **整图综合分析** + **一生四维度评价**（精神 / 财富 / 名声 / **关系能量**）+ **大运评价（含关系看点）** + **关键年份评价**；
   合盘是 markdown 解读：每对人的 4 层评分 + 关键加 / 减分项 + 大运同步度 + 怎么用 / 怎么避。

## 何时使用

### 单盘（人生曲线）
- 用户给四柱（如「庚午 辛巳 壬子 丁未」）或公历生辰 + 性别
- 用户问「我的人生曲线 / 大运走势 / 流年趋势」类问题
- 用户要看某八字未来若干年的命理预测
- 用户要看某个特定年龄段的曲线（如「画我 30–55 岁的曲线」）

### 合盘（synastry）
- 用户给 ≥ 2 份八字 + 关系背景（"我和我老公"、"我和合伙人"、"我和这个朋友"、"我和我妈"等）
- 用户问「我们配不配 / 这个合伙能成吗 / 这段关系怎么走」类问题
- 关系类型 4 选 1：
  - **合作**：合伙创业 / 同事 / 项目团队
  - **婚配**：恋爱 / 婚姻 / 夫妻
  - **友谊**：朋友 / 同道 / 长期玩伴
  - **家人**：父母 / 子女 / 兄弟姐妹（可选第 4 维度）
- 若用户没说关系类型，先问；若关系明显（"老公"→婚配 / "合伙人"→合作）可自动定。

## 工作流（严格按序）

### 0. 概览：十步流程（v8 重写：Step 2.5 / 2.55 合并为单步 phase decision + AskQuestion 校验 → phase_posterior 落地）

```
Step 0  加载 confirmed_facts.json（如已存在 → 跳过已确认 trait + 应用结构性纠错）
Step 1  解析八字（含起运岁精算 / 用户指定）—— 单盘 1 份 / 合盘 ≥ 2 份
  → Step 2 格局识别 + 三派打分（扶抑 / 调候 / 格局）+ 印化护身后处理 + 燥湿覆盖
  → Step 2a 盲派事件检测 → 应事断 + 烈度修正 + **结构反向规则**
  → Step 2b 融合 + 烈度修正（盲派不进 25% 权重；反向后的 events 直接影响曲线）
  → Step 2c **关系能量维度独立打分**：emotion_baseline + emotion_dayun_delta + emotion_liunian_delta；
            不参与三派融合，单走一条通道，保证 spirit/wealth/fame 历史回测精度不变
  → Step 2.5 v8 · phase decision + AskQuestion 校验 → phase_posterior 落地（硬门槛）
            ┌─ identification（算法）：detect_all_phase_candidates 穷尽 14 个候选 + 各 phase 的 phase_likelihoods
            │  → 乘性融合算 prior 分布（独立证据假设 + day_master_dominant baseline 0.05 兜底）
            ├─ disambiguation R1（用户）：handshake.py 生成 5 维度 ~28 道 phase-discriminative 多选题
            │  → Agent 调宿主 AskQuestion 一次性抛全部 N 题点选 UI（Cursor / Claude Desktop / Claude Code 强制）
            │  → CLI fallback：cli_fallback_prompt（编号 + <id>=<option>）
            ├─ posterior decision R1（算法）：phase_posterior.py --round 1 算后验 P(phase | R1 answers)
            │  · ≥ 0.95 且 runner-up < 0.02 → 可直接出图（仍强烈推荐走 R2）
            │  · 0.40-0.95 → **必须走 Round 2 confirmation**
            │  · < 0.40 → reject，不出图，提示核对时辰 / 性别
            ├─ confirmation R2（用户）：handshake.py --round 2 在 R1 决策 phase vs runner-up 之间
            │  挑高 pairwise 判别力的 6-8 道题（自动排除 R1 已问过的）→ AskQuestion 抛 R2
            └─ confirmation_status（算法）：phase_posterior.py --round 2 合并 R1+R2 后验
               · R2 决策 == R1 AND R2 prob ≥ 0.85 → confirmed → render
               · R2 决策 == R1 AND 0.65 ≤ R2 prob < 0.85 → weakly_confirmed → render_with_caveat
               · R2 决策 == R1 AND R2 prob < 0.65 → uncertain → escalate
               · R2 决策 != R1 → decision_changed → escalate（必须报告反转）
            合盘场景：v8 暂未覆盖，仍走旧 R0/R1（详见 §2.6 caveat）
  → Step 2.7 询问输出格式（体验门槛）
            「要 HTML 交互图，还是只要 markdown 文字分析？」
            · 单盘默认问；合盘默认 markdown（HTML 仅可选）
            · 用户选 markdown → 跳过最后的 render_artifact.py，节省 5–15 秒等待
  → 单盘分支：Step 3a **流式输出**五类 markdown（整图 + 一生四维 + 大运 + 关键年份）→ Step 3b 渲染 HTML（仅当用户选 HTML）
  → 合盘分支：Step 3' 跑 he_pan.py → **流式输出**按层解读 + 加 / 减分 + 大运同步建议
Step 4  保存本次反馈到 confirmed_facts.json（含 schema migration 到 v8；下次跑同一八字直接复用）
```

**Step 2.5 是硬门槛**：用户没在结构化 AskQuestion UI 中点完 5 维度题集、`bazi.phase_decision.is_provisional` 仍为 `true` 之前，绝对不进入 Step 3 出图 / 合盘。`render_artifact.py` 收到 `is_provisional=true` 会拒绝渲染（红线 HS-R4）。

**Step 2.7 是体验门槛**：用户不需要 HTML 时绝对不强行渲染（让用户白等几十秒）。

**Step 3 是流式输出（v5 新规则）**：
- LLM 每写完**一节**立刻发出（用户能边读边等下一节），**禁止**憋住整段最后一次性吐
- HTML 渲染（如选）放最后一步，此时用户已经读完所有文字分析了，不再有"等图"的体感
- 即使要 HTML，也必须**先把 markdown 流式发完**，HTML 是"锦上添花"而不是"等结果"

### 0. 加载历次校验记忆 → `output/confirmed_facts.json`（v3 P5 新增）

跑新八字之前先 check 工作目录下 `output/confirmed_facts.json`：

```bash
[ -f output/confirmed_facts.json ] && python3 -c "
import json; r = json.load(open('output/confirmed_facts.json'))
print(f'已有记忆: {len(r[\"validations\"])} validations + {len(r[\"free_facts\"])} facts + {len(r[\"structural_corrections\"])} 结构纠错')
"
```

- **存在** → 加载 `structural_corrections` 全部应用、跳过已 ✓ 的 trait、Round 1 优先验证之前未覆盖的维度
- **不存在** → 走全新 6 题校验

`render_artifact.py` 跑时会自动加载并注入到 ANALYSIS context；`handshake.py` 接受 `--confirmed-facts` 流转。

### 1. 解析输入 → `python scripts/solve_bazi.py`

- 接受：`--pillars "庚午 辛巳 壬子 丁未" --gender M --birth-year 1990 [--qiyun-age 8] [--orientation hetero]` 或 `--gregorian "1990-05-12 14:30" --gender M`
- **起运岁**：`gregorian` 模式自动用 `lunar-python` 精算并写入 `qiyun_source: "lunar_python_精算"`；`pillars` 模式默认 8 岁，**强烈建议显式 `--qiyun-age N` 或在 Step 2.5 校验环节让用户确认**——错 1 年大运全偏。
- **`--orientation`（v7 现代化新增）**：关系取向，仅影响 emotion 通道（不影响 spirit/wealth/fame）。
  - `hetero`（默认）异性恋：男看财 / 女看官杀（保持向后兼容）
  - `homo` 同性恋：男看官杀 / 女看财
  - `bi` 双性：财 + 官杀同看，取较旺者
  - `none` 单身主义 / 不寻求传统亲密关系：emotion 改为"自我亲密能量"通道（食伤 + 印 + 桃花主导）
  - `poly` 多元 / 开放关系：财 + 官杀同看，桃花权重 ×1.7
  - **询问时机**：解析输入时如未指定，默认 hetero。如果用户主动声明取向 / 询问时主动告知，再传参。**不要主动盘问**用户的取向（隐私）。
- **严禁接受**姓名 / 职业 / 婚姻关系状态 / 过去经历等任何身份上下文（公正性要求）。仅 `--orientation` 取向声明是允许的（取向不暴露具体经历）
- 输出 `bazi.json`（含 `qiyun_age` / `qiyun_source` / `orientation`）

### 2. 格局识别 + 三派打分 → `python scripts/score_curves.py`

`score_curves.py` 在打分前会自动调用 `apply_geju_override`，并且 `solve_bazi.py` 在选用神时已经做了"燥湿优先"判定：

- **燥湿独立维度（v2 关键）**：`_bazi_core.climate_profile()` 把命局"燥湿"做成独立于身强弱的维度——干头分（4 个天干，权重 0.6）+ 地支分（4 个地支，权重 0.4）→ 总分 → 6 个 label：`燥实 / 偏燥 / 中和 / 偏湿 / 寒湿 / 外燥内湿 / 外湿内燥`。极端 label（燥实 / 寒湿 / 外燥内湿 / 外湿内燥）会**优先于身强弱覆盖用神**：
  - `燥实` / `外燥内湿` → 用神 = 水（润降 / 让地支水透干）
  - `寒湿` / `外湿内燥` → 用神 = 火（暖局 / 让地支火透干）

  这是"月令决定论"误判教训的产物（典型反例：干头丙庚己己 + 地支双子湿冷，纯按月令算就把调候判反）——详见 `references/diagnosis_pitfalls.md` §1-§2。
- **格局派"为先"**：识别原局是否构成 `伤官生财 / 食神生财 / 杀印相生 / 官印相生 / 食神制杀 / 财格 …` 之一。**每个格局都有成立条件**——例如"伤官生财格"必须满足「身不弱 + 财透干或通月令」，否则放进 `geju.rejected` 不强行套；详见 `references/diagnosis_pitfalls.md` §4。
- **用神反向校验**：所有用神（无论来自身强弱、climate 还是 geju）都要做 `_yongshen_reverse_check`——usability 不能为 "无"（即原局完全不见这个五行）。若为 "无" → 拒绝覆盖回退。
- **印化护身后处理**：流年 / 大运凡触发「七杀」「伤官见官」时，自动检测原局是否有印星（干 / 支均查），有则将原本 -12 的「伤官见官」减为 -4 + 标记为 `伤官见官·印化护身`，将「七杀压身」转为 `+6 fame / +4 spirit` 的杀印相生。
- **【v7.4 #5】化气格自动识别**：`apply_geju_override` 内会先调用 `_bazi_core.detect_huaqi_pattern`，
  五合（甲己 / 乙庚 / 丙辛 / 丁壬 / 戊癸）满足 4 + 1 条件 → 直接走 `huaqi_to_<五行>` phase override，
  日主借合化易主、用神锁定为化神、强弱翻为"强"（按化神为主读）。
  优先级最高，化气格定型后跳过常规格局识别。
- **【v7.4 #5】神煞分布**：`_bazi_core.detect_shensha` 检测 8 类神煞（天乙贵人 / 文昌 / 驿马 / 桃花 / 华盖 / 孤辰 / 寡宿 / 空亡）。
  原局命中 → 终生 baseline 微调（±0.3~0.4）；大运 / 流年地支命中 → 当年微调（±0.5~1.0），
  驿马触发 → 当年 sigma × 1.3（波动加大，反映动 / 调岗 / 出行）。
  神煞影响刻意小，不参与主格局判定，只是局部调味。

如果用户明确要求「按你的扶抑用神来打，不要被格局 / climate 覆盖」，可手动在 `bazi.json` 里给 `yongshen._locked = true` 后再次跑 `score_curves.py`。

### 2a. 盲派事件检测 → `python scripts/mangpai_events.py`

```bash
python scripts/mangpai_events.py \
  --bazi bazi.json --out mangpai.json \
  --age-start 0 --age-end 60
```

机械识别 11 条盲派经典组合（伤官见官 / 官杀混杂 / 比劫夺财 / 禄被冲 / 羊刃逢冲 / 食神制杀 / 七杀逢印 / 伤官伤尽 / 反吟应期 / 伏吟应期 / 财库被冲开）+ 静态终生标记（年财不归我）。每条事件含师承出处、应事文本、维度、烈度档（重 / 中 / 轻）、可证伪点。详见 `references/mangpai_protocol.md`。

**v3 关键升级：结构反向规则（P1）** —— `detect_reversal_context(bazi)` 根据命局结构（强印 / 身弱 / 杀坐日）判定哪些盲派事件方向需要反转，然后在 events 出炉前调用 `apply_reversal_rules` 直接改 dims/amplifier。三条机械规则：

| 触发结构 | key | 反向后含义 |
|---|---|---|
| 强印护身 + 伤官透干 + 非身强 | `shang_guan_jian_guan` | 与权威接触 = **被认证 / 上位**（不是摩擦） |
| 身弱 | `bi_jie_duo_cai` | 比劫 = **同道扶起 / 合伙助力**（不是损财） |
| 七杀坐日 + 强印 + 身弱 | `guan_sha_hun_za` | 多重压力 = **多重机会 / 决断力被反复验证** |

输出 `mangpai.json.reversal_context` 顶层暴露给 handshake 和 LLM。**LLM 不要再自由发挥反向解读** —— 反向已机械化进曲线分数，只需告知用户"本命的某些盲派事件方向是反向的"。详见 `references/diagnosis_pitfalls.md` §9。

### 2b. 融合 + 烈度修正

完整参数（含盲派整合）：

```bash
python scripts/score_curves.py \
  --bazi bazi.json --out curves.json \
  --mangpai mangpai.json \             # 启用盲派烈度修正 + 应事嵌入；省略则纯三派
  --age-start 0 --age-end 60 \         # 评分年龄区间（默认 0–60）
  --forecast-from-year 2026 \          # 拐点预测起始公历年份（默认从 age-end 倒推 forecast-window）
  --forecast-window 10 \               # 拐点窗口（默认 10 年）
  --dispute-threshold 20 \             # 三派极差超过此值即标为「派别争议年份」（默认 20）
  --strict                             # 双盲自检
```

盲派的处理：
- 三派（扶抑 / 调候 / 格局）按 25/40/30 权重融合得到当年 final value
- 然后**盲派烈度修正**：当年所有触发的盲派事件按烈度档 ±值（重 ±8 / 中 ±4 / 轻 ±2，单年累加上限 ±12）
- 修正轨迹 + 事件文本写入 `points[].mangpai_adjust` 与 `points[].mangpai_events`
- 盲派的"位置"：详见 `references/mangpai_protocol.md`。一句话——**事件断 + 烈度修正器，不进 25% 融合权重**

**用户表述 → 参数映射**：

| 用户说 | 参数 |
|---|---|
| "未来 5 年" / "看看未来 5 年" | `--forecast-window 5 --forecast-from-year <今年>` |
| "30–55 岁" / "中年这段" | `--age-start 30 --age-end 55` |
| "全生" / "整个一生" | `--age-start 0 --age-end 80`（最长 80） |
| "近 10 年怎么走" | `--age-start <现在年龄-2> --age-end <现在年龄+10>`（带前后对照） |
| "把分歧大的年份都标出来" / "敏感一点" | `--dispute-threshold 15` |
| "只看大趋势，别太敏感" | `--dispute-threshold 25` |

LLM **不直接生成数字**，只能解释脚本输出。

### 2.5 v8 · phase decision + AskQuestion 校验 → phase_posterior 落地（硬门槛）

> **v8 重大变化总览**（与 v6/v7 对比表）：
>
> | 维度 | v6/v7 | v8 |
> |---|---|---|
> | 轮次 | R0 / R1 / R2 / R3 分阶段，按命中率推进 | **统一题集**（5 维度 ~28 题）+ 自适应追问，无固定轮次 |
> | 题目来源 | 按"默认相位"生成自然语言 claim | 按 `detect_all_phase_candidates` **全集 14 个 phase** 生成 + 按 `discrimination_power` 筛选 |
> | 用户接口 | LLM 把题面**自然语言转述**给用户，让用户口头答「对 / 不对 / 部分」 | **宿主 AskQuestion 结构化点选 UI**（强制），用户在 4 个选项里点击 |
> | 决策方式 | "命中率 N/M ≥ 阈值"硬门槛 | **贝叶斯后验** P(phase \| answers)，按概率 adopt / 追问 / reject |
> | 反迎合 | R0' 反向探针（counter-claim probes） | 由题库的 **phase-discriminative + falsifiability 设计原则**取代（每题至少 2 个 phase 间 ≥ 0.20 概率差 + 必须有反方向选项） |
> | 维度 | 健康（R1）+ 感情（R0）+ 交叉（R2）+ 家庭（R3 条件触发） | **5 维度全开**：D1 民族志 × 原生家庭 / D2 关系结构 / D3 流年大事件（动态生成）/ D4 中医体征 / D5 自我体感 |
> | 失败兜底 | 命中率 ≤ 2/6 → 触发 Step 2.55 phase_inversion_loop 事后反演 | **identification 提到 `solve_bazi.py` 一等公民**，detector 算先验直接落 `bazi.phase`；`phase_inversion_loop.py` 标 deprecated |
> | 落地阈值 | R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6） | top-1 后验 ≥ 0.80 high / 0.60-0.80 mid / 0.40-0.60 追问轮 / < 0.40 reject |
>
> 典型边界 case：某些盘 6 个 detector 满分（P5 三气成象 4/4 + P3 调候反向 3/3 + P4 假从触发），但旧架构 `bazi.json` 仍按 `day_master_dominant` 输出。详见 `references/diagnosis_pitfalls.md` §14。

#### 心智模型 · identification vs disambiguation

| 责任方 | 任务 | 输出 |
|---|---|---|
| 算法（detector）| identification —— 穷尽结构性自洽的可能 phase | 候选 phase 全集 + 各 phase 的先验概率 |
| 用户（AskQuestion）| disambiguation —— 通过外部观察事实在候选间投票 | 多选答案 |
| 算法（decide_phase）| posterior decision —— 贝叶斯综合 prior + likelihood | 后验分布 + top-1 phase + 置信度 |

**关键边界**：算法负责"我能想到的可能"，用户负责"在我能想到的可能里哪一个像你"。算法不能因为"我自己倾向选 A"就只把按 A 生成的题面抛给用户校验——这是 v6/v7 把题面只按默认相位生成的根本错误。

完整协议：[`references/phase_decision_protocol.md`](references/phase_decision_protocol.md)。

#### 跑 handshake 出题集

```bash
python scripts/handshake.py \
  --bazi out/bazi.json --curves out/curves.json \
  --current-year 2026 \      # 默认 today.year（D3 流年题需要换算 age）
  --out out/handshake.json
```

输出 `handshake.json` v8 schema 关键字段：

```json
{
  "version": 8,
  "phase_candidates": [
    {"phase_id": "floating_dms_to_cong_cai", "label": "弃命从财", "detector_score": "4/4 (P5)"},
    {"phase_id": "day_master_dominant", "label": "默认 · 日主主导", "detector_score": "baseline"}
  ],
  "prior_distribution": {
    "floating_dms_to_cong_cai": 0.46,
    "floating_dms_to_cong_er": 0.21,
    "climate_inversion_dry_top": 0.18,
    "day_master_dominant": 0.05
  },
  "questions": [
    {"id": "D1_Q3_father_presence", "dimension": "ethnography_family",
     "weight_class": "hard_evidence", "prompt": "...", "options": [...],
     "likelihood_table": {...}, "discrimination_power": 0.34}
  ],
  "askquestion_payload": [
    {"id": "D1_Q3_father_presence", "prompt": "...", "options": [...], "allow_multiple": false}
  ],
  "cli_fallback_prompt": "请按以下编号回答（输入 D1_Q3=B 形式）：\n\nD1_Q3 ...\n  A) ...\n",
  "decision_threshold": {"auto_adopt": 0.80, "adopt": 0.60, "ask_more": 0.40}
}
```

完整 schema：[`references/handshake_protocol.md`](references/handshake_protocol.md) §2。

#### 5 个维度的设计原则

| 维度 | 题数 | 权重 | 内容 |
|---|---|---|---|
| **D1 · 民族志 × 原生家庭** | 6 | hard_evidence × 2.0 | 出生时家境 / 父母在场度（父 + 母） / 兄弟姐妹 / 出生地 × 时代（结合 `era_windows_skeleton.yaml`） / 祖辈影响 |
| **D2 · 关系结构** | 6 | soft_self_report × 1.0 | 吸引对象画像 / 谁更主动 / 经济角色 / 情感依赖方向 / 关系总体模式 / 吸引年龄段（升级旧 R0） |
| **D3 · 流年大事件**（动态）| ~5 | hard_evidence × 2.0 | 跨候选 phase 跑 `score_curves.score_one_year()` 找方差最大的 3-5 个**已活过年份**，套 4 档方向选项（向上 / 向下 / 大起大落 / 平稳） |
| **D4 · 中医体征** | 6 | hard_evidence × 2.0 | 寒热 / 睡眠 / 脏腑薄弱处 / 体型体格 / 食欲口味 / 情志倾向（扩展旧 R1 健康三问到完整六问） |
| **D5 · 自我体感** | 4 | soft_self_report × 1.0 | 压力默认策略 / 钱的态度 / 与权威关系 / 创造性输出方式（本性画像兜底） |

**题库设计原则**（住在 `references/discriminative_question_bank.md` §0）：
1. **phase-discriminative**：每题在 likelihood_table 中至少 2 个 phase 间 ≥ 0.20 概率差，否则剔除
2. **falsifiability**：每题选项必须有明确"反方向"选项（不只问"你像不像 X"，必须问"X 还是 Y 还是 Z 还是 W"）
3. **无身份标签**：选项措辞严守 `references/fairness_protocol.md` §10，**禁出现**"升职 / 结婚 / 生育 / 离职 / 确诊 / 拿到 offer / 创业失败 / 分手"等具体事件，改用方向性、体感性描述
4. **likelihood_table**：每行（phase）∑ = 1.0；学理出处回到《滴天髓》《子平真诠》《穷通宝鉴》《三命通会》

#### Step 2.5 v8 · AskQuestion 执行协议（Agent 必跑 5 步）

**1) 读 `handshake.json` 的 `askquestion_payload`**

跑 `handshake.py` 后从 `out/handshake.json` 取 `askquestion_payload` 数组（每项含 `id` / `prompt` / `options` / `allow_multiple`）和 `cli_fallback_prompt` 兜底文案。

**2) 调宿主 AskQuestion 工具一次抛全部 N 道**

| 宿主 | 抛题方式 |
|---|---|
| **Cursor** | 用 `AskQuestion` 工具，每题作为一个 question 项，options 直接传 `askquestion_payload[i].options`，**一次性抛全部 N 题**（不分轮） |
| **Claude Desktop / Claude Code** | 同上，调宿主结构化问询接口 |
| **CLI / 无 AskQuestion 宿主** | 回退到 `cli_fallback_prompt`，逐题列出选项让用户输入 `<question_id>=<option_id>` 形式（如 `D1_Q3=B`） |

**3) 收 `user_answers.json` → 调 `phase_posterior.py`**

```bash
# 把用户答案存为 user_answers.json：{"D1_Q3_father_presence": "B", "D4_Q1_cold_heat": "C", ...}
python scripts/phase_posterior.py \
  --bazi out/bazi.json \
  --questions out/handshake.json \
  --answers out/user_answers.json \
  --out out/bazi.json    # 写回同一 bazi.json，phase_decision.is_provisional=False
```

`phase_posterior.py` 算后验公式：

```
P(phase_i | answers) ∝ prior(phase_i) × ∏_j likelihood(answer_j | phase_i)^{w_j}

其中 w_j = 2.0 if question_j.weight_class == "hard_evidence" else 1.0
     likelihood(answer_j | phase_i) = question_j.likelihood_table[phase_i][answer_option_j]
```

硬体征（D1 / D3 / D4）权重 2× 软自述（D2 / D5）。

**4) R1 后验阈值 → 行动**（与 `references/phase_decision_protocol.md` §5 对齐）

| R1 后验 top-1 概率 | 行动 | confidence |
|---|---|---|
| **≥ 0.95** 且 runner-up < 0.02 | 可直接出图（**强烈推荐仍走 Round 2**） | high |
| **0.60 – 0.95** | 必须走 **Round 2 confirmation**（详见 §2.6） | mid / high |
| **0.40 – 0.60** | 必须走 **Round 2**（confirmation_threshold 决定是否出图） | low |
| **< 0.40** | **拒绝出图**：报告"算法无法落地，请核对时辰 / 性别"，**禁止**调 `score_curves` / `render_artifact` | reject |

**5) 严禁用自然语言转述题面让用户口头答"对/不对/部分"**

❌ **错误做法（v6/v7 旧风格）**：
```
我看你日主弱，月令子水当令，那这样问你：你从小是不是怕冷、手脚常凉？请回答「对 / 不对 / 部分」。
```

✓ **正确做法（v8）**：直接调宿主 AskQuestion，把 `askquestion_payload[i].prompt` 原样作为问题文案，把 `options` 原样作为 4 个点选项。**不要改写、不要浓缩、不要预先告诉用户"我倾向你是 X 相位"**（会污染答案）。

#### 红线（违反任意一条 → 立即停下）

| # | 红线 | 触发 | 处理 |
|---|------|------|------|
| HS-R1 | Agent 用自然语言转述题面 | 任何 `questions[i].prompt` 被改写或浓缩 | 立即停下，重新走 `askquestion_payload` |
| HS-R2 | 跳过 < 0.40 拒判路径 | 后验 < 0.40 仍调 `score_curves` 出图 | 强制返回 reject 文案 |
| HS-R3 | 后验 < 0.60 没追问就 adopt | 0.40-0.60 区间被当 mid 落地 | 强制走追问轮 |
| HS-R4 | `is_provisional=true` 状态下出图 | `render_artifact` 收到 `phase_decision.is_provisional=true` | 拒绝渲染，要求先跑 `phase_posterior` |
| HS-R5 | D3 流年题踩 fairness §10 黑名单 | options 中含"升职 / 结婚 / 离职 / 生育 / 确诊"等身份标签词 | `_question_bank.py` 单元测试拦截，不允许进 prompt |

#### 禁止

- ❌ 跳过 Step 2.5 直接出图 / 合盘
- ❌ Agent 在抛题前先告诉用户"我看你这个八字大概率是 X 相位"（污染答案）
- ❌ 把多选题改成自由文本输入 / 改成"对 / 不对 / 部分"二元
- ❌ 跳过若干题只问 3-5 道（必须把题库全部 ~20-25 道一次抛完，按 `discrimination_power` 已经过筛选了）
- ❌ 后验 < 0.40 时不报 reject 仍硬出图
- ❌ 用旧 `phase_inversion_loop.py` 流程（v8 已替代，详见 §2.55 deprecated）

完整规则见 `references/handshake_protocol.md`、`references/phase_decision_protocol.md`、`references/discriminative_question_bank.md` 和 `references/diagnosis_pitfalls.md` §14（命名 case）。

### 2.6 v8.1 · Round 2 confirmation（第二轮校验，**必跑**）

> R1 是宽口径的 disambiguation；R2 是**第二批独立证据**的 confirmation。R1 答得再像 cong_cai 也可能是偶然命中——R2 用 R1 决策 phase 与 runner-up phase 之间高判别力的题再问一次，决定是否真的出图。

#### 跑 Round 2 handshake

```bash
python scripts/handshake.py --round 2 \
  --bazi out/bazi.json \
  --curves out/curves.json \
  --r1-handshake out/handshake.r1.json \
  --r1-answers out/user_answers.r1.json \
  --current-year 2026 \
  --out out/handshake.r2.json
```

输出 `handshake.r2.json` 关键字段：

```json
{
  "version": 8, "round": 2,
  "round1_summary": {
    "decision": "floating_dms_to_cong_cai",
    "decision_probability": 0.999,
    "runner_up": "pseudo_following",
    "runner_up_probability": 0.0001,
    "answered_question_ids": [...]
  },
  "pairwise_target": {"a": "floating_dms_to_cong_cai", "b": "pseudo_following"},
  "questions": [/* 6-8 道高 pairwise dp 的题，自动排除 R1 已问过的 */],
  "askquestion_payload": [...],
  "confirmation_threshold": {"confirmed": 0.85, "weakly_confirmed": 0.65}
}
```

#### Agent 抛 R2 题

调宿主 AskQuestion 抛 `askquestion_payload` 全部 6-8 题，收到 `user_answers.r2.json` 后：

```bash
python scripts/phase_posterior.py --round 2 \
  --bazi out/bazi.json \
  --r1-handshake out/handshake.r1.json --r1-answers out/user_answers.r1.json \
  --r2-handshake out/handshake.r2.json --r2-answers out/user_answers.r2.json \
  --out out/bazi.json
```

#### confirmation_status → 出图行动

| 条件 | confirmation_status | action | Agent 行为 |
|---|---|---|---|
| R2 决策 == R1 决策 AND R2 prob ≥ 0.85 | `confirmed` | `render` | 直接出图 |
| R2 决策 == R1 决策 AND 0.65 ≤ R2 prob < 0.85 | `weakly_confirmed` | `render_with_caveat` | 出图但解读处加 caveat："本盘 phase 决策为弱确认，部分维度证据不齐" |
| R2 决策 == R1 决策 AND R2 prob < 0.65 | `uncertain` | `escalate` | 报告"R2 后验不足以确认 R1 决策"，建议核对时辰 / 性别 |
| R2 决策 != R1 决策 | `decision_changed` | `escalate` | **必须**报告决策反转，建议核对时辰 / 性别，或采纳 R2 决策再走一轮 R2 |

#### Round 2 红线（在 §2.5 红线之外补充）

| # | 红线 | 触发 | 处理 |
|---|------|------|------|
| HS-R6 | `decision_changed` 仍出图 | R2 决策与 R1 反转，但 Agent 直接渲染 | 强制 escalate 文案，要求核对时辰 / 性别 |
| HS-R7 | R1 后验 < 0.95 跳过 R2 | R1 mid/low 区间未走 confirmation 就渲染 | 强制走 Round 2 |

完整规则见 `references/handshake_protocol.md` §4 和 `references/phase_decision_protocol.md` §7。

### 2.55 [DEPRECATED · v8] 旧 phase_inversion_loop 事后反演路径

> **v8 起本节整体废弃**。下文仅作为兼容性说明保留，**新流程不要走这里**。

旧 v6/v7 把"相位反演"做成"R0+R1+R2 命中率 ≤ 2/6 时才触发"的事后兜底机制（`phase_inversion_loop.py` + `handshake.py --dump-phase-candidates` + `score_curves --override-phase`）。这个设计的根本错误是：**算法的 identification 能力（穷尽候选）远超过产品的 disambiguation 接口（让用户在候选间投票）**——detector 已经知道这盘走反了，但默认 `bazi.json` 仍按 `day_master_dominant` 输出，因此用户解读全按错相位讲。

v8 的 `phase_decision_protocol.md` 把 phase decision 提到 `solve_bazi.py` 阶段的强制一等公民：

1. `solve_bazi.py` 末尾必须调 `decide_phase(user_answers=None)` 算先验，把 `phase` + `phase_decision` 写进 `bazi.json`，初始 `is_provisional=True`
2. `score_curves.py` 默认读 `bazi.phase.id` 走 `apply_phase_override`，不再"忘读"
3. `handshake.py` 通过 5 维度 28 题让用户校验，answers 经贝叶斯后验落地
4. 后验 ≥ 0.60 → adopt；< 0.40 → 报"算法无法落地，请核对时辰"

**`phase_inversion_loop.py` 脚本仍可运行**（避免破坏旧 confirmed_facts），但只剩"调试用手工分步"价值。新跑流程 / 新场景不要再调用它。详见 `references/phase_decision_protocol.md` §7 和 `references/diagnosis_pitfalls.md` §14。

### 2.6 合盘分支（仅当输入 ≥ 2 份八字时执行）→ `python scripts/he_pan.py`

> **v8 caveat**：合盘场景**暂未升级到 v8**。每份八字单独跑校验时，仍走旧 R0/R1 健康三问 + 命中率判定路径（不调 v8 AskQuestion + phase_posterior）。计划在后续版本中把合盘的双方校验都迁到 v8 question bank，目前的 4 层评分逻辑、加 / 减分规则、解读铁律不受影响。

```bash
# 每份八字都先 solve_bazi.py + score_curves.py + handshake.py（Step 1 / 2 / 2.5 全跑）
# Step 2.5 通过后再跑 he_pan.py：

python scripts/he_pan.py \
  --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json [/tmp/p3_bazi.json ...] \
  --names 男方 女方 \
  --type marriage \                            # cooperation | marriage | friendship | family
  --focus-years 2026 2027 2028 2029 2030 \     # 默认 今年-今年+10
  --out /tmp/he_pan.json
```

**4 层评分**（每对人组合 A↔B）：

| 层 | 来源 | 加 / 减分要点 |
|---|---|---|
| 五行互补 | A 用神在 B 八字中的占比 / A 忌神在 B 八字中的占比（双向） | 用神 ≥ 18% +(ratio×30) ；忌神 ≥ 25% -(ratio×24) |
| 干支互动 | 双方四柱之间的干合 / 干冲 / 支六合 / 三合半合 / 支冲 / 支害 / 桃花 / 天乙贵人 | 日支六合婚配 +5 加成；日支冲婚配 -4 大忌 |
| 十神互配（按 rel_type） | A 看 B 的日干是什么十神 / 反之 | 婚配：男看正财、女看正官 +12；合作：财官印配 +6~+8；友谊：互比劫 +10；家人：互印 +8 / 杀印相生 +6 |
| 大运同步 | focus_years 区间双方大运对各自用神的极性是否同号 | (sync_ratio - 0.5) × 20，范围 [-10, +10] |

**总分等级**（仅供 LLM 内部定调，**不要直接报给用户**）：A ≥50 / B 25-49 / C 5-24 / D -15~4 / E < -15。把它转化为人话（"摩擦点 / 怎么缓冲 / 大运同步建议"），不要甩等级。

**LLM 解读规则（强制 · v5 流式输出）**：

**流式分节顺序**（每写完一节立刻发出，**禁止憋整段**）：

```
[Node 1] 概览：双方八字 + 关系类型 + confidence 说明（基于双方 R1）
[Node 2] 总分定调（人话，不甩 grade）—— 1 段
[Node 3] 第 1 层 · 五行互补 解读（援引 ≥ 2 条 notes）
[Node 4] 第 2 层 · 干支互动 解读（援引 ≥ 2 条 notes，标出关键合 / 冲）
[Node 5] 第 3 层 · 十神互配 解读（按 rel_type 重点）
[Node 6] 第 4 层 · 大运同步 解读（focus_years 哪些年同向 / 反向）
[Node 7] 关键加分项（top_pluses）—— 怎么用
[Node 8] 关键减分项（top_minuses）—— 怎么避
[Node 9] 关系类型特定 tips：
         - 婚配：日柱合 / 日支冲是关键，必须明确指出
         - 合作：财官印配 + 警惕比劫夺财
         - 友谊：比劫食伤同道 = 长久；七杀过多 = 易争胜
         - 家人：印 / 比为主，看代际庇护和同辈互助
[Node 10] 总结：1 段大白话总结 + "如果决定做 X，怎样能更顺"
```

每节用 markdown 标题（`## 概览` / `## 第 1 层 · 五行互补` 等）。**合盘默认走 markdown-only（Step 2.7 默认 A），不渲染 HTML**——合盘是关系解读，没有"曲线图"那种刚需 HTML 的内容。仅当用户明说"也给我个汇总表 / 想看 HTML"时才走 B（render_artifact.py 不支持合盘，可用简单的 HTML 表格 + notes 列表）。

**禁止**：
- ❌ 直接给"配 / 不配"二元结论
- ❌ 把 grade 直接报给用户
- ❌ 跳过双方 R1 校验直接合盘
- ❌ 不援引脚本 notes 凭"感觉"打分
- ❌ 给"建议分手 / 建议结婚 / 建议合伙"代替用户做决定的话——只给"如果决定做 X，怎样能更顺"
- ❌ **把所有节点憋在末尾一次性吐**（v5 流式硬要求 —— 每节立即发出）

完整规则见 `references/he_pan_protocol.md`。

### 2.7 询问输出格式（v5 新增 · 体验门槛）

**只要 R1 校验通过，就在进入 Step 3 之前主动问一次输出格式**——不要默认渲染 HTML，
HTML 渲染单盘要 5–15 秒、合盘也要 3–5 秒，用户没要的时候是纯浪费等待。

**LLM 强制输出模板**：

```
校验通过 ✓。在我开始写分析之前，问一下你想要哪种输出：

(A) 纯 markdown 流式输出 —— 我每写完一节就立刻发给你，最快、最适合手机 / 复制 / 转发
(B) markdown 流式 + 最后渲染 HTML 交互图 —— 多等 5-15 秒，可以鼠标 hover 查看每年详情、details 折叠

回 A 或 B（默认 A）。
```

**默认值规则**：
- 单盘：默认 A（流式 markdown），用户明说要图 / 要 artifact / 要 HTML / 要交互再走 B
- 合盘：默认 A（合盘是关系解读，没有"曲线图"那种刚需 HTML 的内容；可选 HTML 是评分汇总表 + notes 列表）
- 用户已经在初次提问里说过「画图 / 出 artifact / 给我图」 → 直接走 B，不用再问
- 用户已经在初次提问里说过「就给我文字 / 不用图 / 直接说就行」 → 直接走 A，不用再问

**禁止**：
- ❌ 跳过 Step 2.7 默认走 HTML（让用户白等 5-15 秒）
- ❌ 在用户明显不想要图（"就口头说说"、"快点告诉我结论"）时仍渲染 HTML
- ❌ 用户回了 A 之后还是把 HTML 也跑了

### 3a-pre. 时代-民俗志解读层（v7.5 新增 · 在写 key_years / dayun_review 之前必读）

写任何 `key_years` body / `dayun_review.body` 之前，**必须**先按以下流程构造"时代-民俗志上下文"：

```
1. 加载 references/era_windows_skeleton.yaml （时代窗口骨架，5-10 年一段）
2. 调用 scripts/_zeitgeist_loader.py 把 era_windows 与命主大运对齐
3. 调用 scripts/_class_prior.py 推导 class_prior（内部思维材料 · 不输出 label）
4. 按 references/folkways_inference_prompt.md 5 步流程生成 folkways 候选
5. 三层过滤（confidence + 五项自检 + 五行/阶级匹配）
6. 按 references/zeitgeist_protocol.md §3.1 区间叙事模板写
7. 按 references/dayun_review_template.md 模板组织大运段落
```

**关键铁律（违反任一即作废重写）**：

- **前事细 / 后事粗**：过去年份可给"首选 + 备选"具体形态；未来年份**只能**给方向 + 大类 + 避坑，禁止具体事件
- **思维材料 ≠ 输出语言**：阶级 prior 是 LLM 内部 reasoning 工具，**绝不**以阶级名词形式出现在用户可见输出里——见 `references/class_inference_ethics.md`
- **三档置信**：每条民俗志推论必须标 `confidence ∈ {high, mid, low}`，**low 不能出现在断言中**（可转开放问题）
- **五项自检**：每条 folkways 候选必须能回答 5 个问题（时间窗 / 地域 / 阶级 marker / 五行 tag / 对应命理事件）；2 项答不出 → 该条不能写
- **区间为骨，节点为肉**：每个 era_window 写一段完整叙事（时代底色 + 标志性细节 + 命理节点 + 累计影响 + 整段证伪点），命理节点镶嵌在区间内

参见：
- `references/zeitgeist_protocol.md`（区间叙事结构 + 大运 × era_window 对齐）
- `references/folkways_protocol.md`（6 sub-layer + 五行映射 + 三档置信 + 五项自检）
- `references/class_inference_ethics.md`（思维材料 ≠ 输出语言；§5 红线关键词清单）
- `references/folkways_inference_prompt.md`（完整 5 步推理模板 + 自检清单）
- `references/folkways_examples/*.md`（few-shot 示例，模仿其颗粒度）

### 3a. LLM 流式输出五类评价（v5 流式 + v6 加感情维度：每写完一节立刻发出）

按 `references/multi_dim_xiangshu_protocol.md` 的强制框架，**严格按下面的"流式分节顺序"**逐节输出：每写完一节立刻发出（用户能边读边等下一节），**禁止**把所有内容憋在末尾一次性吐。

**v7.5 重要变更**：`dayun_review.body` 和 `key_years.body` 不再是"单年六维取象"格式，全部按 §3a-pre 的"区间叙事 + 节点镶嵌"重写。

**流式分节顺序（v6 强制 · 共 N 节，比 v5 多一节"一生·感情"）**：

```
[Node 1] 整图综合分析（overall · 必含 4 条曲线的整体形状 + 关系）
         ↓ 立刻发出
[Node 2] 一生四维度评价 · 精神（life_review.spirit）
         ↓ 立刻发出
[Node 3] 一生四维度评价 · 财富（life_review.wealth）
         ↓ 立刻发出
[Node 4] 一生四维度评价 · 名声（life_review.fame）
         ↓ 立刻发出
[Node 5] 一生四维度评价 · **感情**（life_review.emotion · v6 新增 · 必须援引 R0 命中情况）
         ↓ 立刻发出
[Node 6..K] 大运评价 · 每段 1 节（按时间从早到晚，dayun_segments 逐段，**每段必带"感情看点"行**）
            ↓ 每写完一段立刻发出
[Node K+1..N] 关键年份评价 · 每条 1 节（按 year 升序，含三派分歧说明 + emotion 偏离 ≥ 12 的必须带【感情·v6】行）
              ↓ 每写完一条立刻发出
```

每节用 markdown 标题（`## 整图综合分析` / `## 一生 · 感情` / `## 大运评价 · 辛丑（25–34 岁）` / `## 关键年份 · 2031 (35 岁 辛亥)` 等），方便用户视觉扫描和折叠。

**Node 5 感情段写作要求**（v6）：
- 标题必带 R0 命中：`## 一生 · 感情（援引 R0：偏好类型 = X / 对方态度 = Y / 命中 = N/2）`
- R0 = 2/2 → 高置信展开；R0 = 1/2 → 注明歧义；R0 = 0/2 → **必须双解**
- 必写"感情线 vs 财富/名声/精神线在哪几年同步、哪几年对冲"——这是用户最关心的"鱼和熊掌"问题
- 详见 `references/multi_dim_xiangshu_protocol.md` §10 感情维度专项解读模板

**3b 走 HTML 路径时**，所有节点写完后再把它们汇总成 `analysis.json`（结构见下方），调用 `render_artifact.py` 注入 HTML。**3b 不走 HTML 时直接进 Step 4，结束**。

`analysis.json` 结构（仅在 Step 2.7 选 B / HTML 时需要构造）：

```jsonc
// analysis.json
{
  "overall": "Markdown 字符串（整图综合分析 · 命格定位 · 一生主线）",

  "life_review": {                                      // 一生四维度评价（卡片网格 · v6 加 emotion）
    "spirit":  "Markdown：精神舒畅度的一生走势 + 体感建议",
    "wealth":  "Markdown：财富的一生走势 + 钱从哪来 / 高峰区段 / 防漏点",
    "fame":    "Markdown：名声的一生走势 + 被看见的方式 / 警惕陷阱",
    "emotion": "Markdown（v6）：感情走势 + 援引 R0 命中 + 偏好类型 + 对方态度在大运/流年的展开 + 与事业的同步/对冲"
  },

  "dayun_review": {                                     // 大运评价（按 dayun_segments.label 索引）
    "辛丑": { "headline": "一句话概括", "body": "Markdown：这 10 年的命理属性 + 主线 + 实际表现 + 建议" },
    "壬寅": { "headline": "...",       "body": "..." },
    ...
  },

  "key_years": [                                        // 关键年份评价（peak/dip/shift）
    {
      "year": 2031, "age": 35, "ganzhi": "辛亥", "dayun": "癸卯",
      "kind": "peak",          // peak | dip | shift
      "headline": "财富单年最高峰",
      "body": "Markdown：触发命理 + 大白话推论过程 + 可能取象 + 建议 + 极端假设"
    },
    ...
  ]
}
```

**强制要求（严禁简化）**：
- `overall`：整图综合分析 + 命格定位（援引 `curves["geju"]`）+ 一生主线 + **4 条曲线的整体形状 + 关系**（v6）
- `life_review.{spirit,wealth,fame,emotion}`：每个维度 ≥ 200 字大白话；spirit/wealth/fame 结合三派分数 + 命理依据；**emotion 必须援引 R0 命中情况 + 偏好类型 + 对方态度在 dayun 的展开**
- `dayun_review[label]`：每段 10 年大运都要写（**含起运前段 + 65 岁以后只要 dayun_segments 里有就要写**），含 1 行 headline + Markdown body（命理属性 / 主线 / 实际表现 / 建议）
- `key_years`：把过往的"用户已确认事件年份" + 未来的"高峰 / 低谷 / 拐点"都列入；每条 ≥ 250 字，必须包含**推论过程的大白话描述**（"为什么我推这一年是 X"），有盲派事件的必须援引 `points[year].mangpai_events` 文本
- 旧版 `turning_points` / `disputes` 字段已废弃 → 全部合并到 `key_years` 里（disputed 年份在 key_years body 里加一段「⚠ 三派分歧」说明）

**禁止**：
- ❌ 跳过这一步直接进 3b（导致 details 区是空的）
- ❌ 给空话术（"需要综合判断" / "因人而异"）
- ❌ 不援引盲派应事就写 key_years
- ❌ **把所有节点憋在末尾一次性吐**（v5 流式硬要求 —— 每节立即发出）
- ❌ 用户在 Step 2.7 已选 A / markdown-only 时还把内容塞进 analysis.json 跑 render_artifact.py

### 3b. 渲染 HTML（仅当 Step 2.7 用户选 B；选 A 时跳过）

**前置条件**：用户在 Step 2.7 明确选 B（要 HTML 交互图）。否则**直接进 Step 4**。

```
if Step 2.7 == B AND 当前宿主 ∈ {Claude Desktop, Claude Web, claude.ai}:
    # 把已流式输出的所有节点汇总成 analysis.json
    python scripts/render_artifact.py \
      --curves curves.json \
      --analysis analysis.json \         # 把 3a 各节 markdown 注入 details 折叠区
      --out chart.html
    # 把 chart.html 内容用 artifact 块返回（type="text/html"）
    # 此时用户已经读完所有文字分析，HTML 是"锦上添花"，不再有"等图"焦虑

elif Step 2.7 == B AND 当前宿主 ∈ {Cursor, Claude Code CLI, 其他}:
    python scripts/render_chart.py --curves curves.json --out chart.png
    # 显示 PNG 路径（分析已在 Step 3a 流式发完，无需再贴一遍）

elif Step 2.7 == A:
    pass  # 跳过渲染，直接进 Step 4
```

Artifact 默认折叠状态（仅 HTML 路径）：
- 整图综合分析：**默认展开**
- 一生四维度评价（精神 / 财富 / 名声 / **感情**）卡片：**默认展开**
- 大运评价：**第一段默认展开，其余收起**
- 关键年份评价：**前 2 条默认展开，其余收起**

**给用户的话术建议**：
- 选 A 完成后："以上就是全部分析。如果之后想看交互图（鼠标 hover 查看每年详情），告诉我一声我再给你渲染。"
- 选 B 完成后：先把流式 markdown 给完，再发 artifact，并告知"图里的内容和上面文字一致，方便你折叠 / 翻看。"

### 4. 输出四件套 + 保存反馈记忆（v3 P5 · v6 升级为 4 维）

1. **图**（Artifact 或 PNG，**8 条线**：4 维度 × 实/虚 + 大运背景色带 + **RichTooltip 悬停**）
2. **一生四维度评价**（精神 / 财富 / 名声 / **感情** 各 ≥ 200 字大白话）
3. **大运评价**（每 10 年一段 · headline + body **+ 感情看点行**）
4. **关键年份评价**（peak / dip / shift · 含大白话推论过程 + 盲派应事 + 三派分歧说明 + emotion 大动的【感情·v6】行）

**v6 RichTooltip 内容**（鼠标 hover 任意年份点显示）：年份 + 年龄 + 干支 + 大运 + **4 维**当年值 + **4 维**趋势值 + 互动 tag + 盲派 tag（含反向标记） + 关键年高亮 box（提示用户跳转到下方详解）。所有 `key_years` 在图上还有竖线标记（▲ peak / ▼ dip / ◆ shift）。

**Step 4：保存反馈记忆** —— 用户答完 v8 AskQuestion 题集后，`phase_posterior.py` 已经把 phase 写回 `bazi.json`；同时把 `user_answers.json` 沉淀到 `output/confirmed_facts.json` 供下次复用：

```bash
# v8 主路径：把 user_answers + 后验决策写入 confirmed_facts（含 schema migration）
python3 scripts/save_confirmed_facts.py \
    --bazi output/bazi.json \
    --user-choices output/user_answers.json \
    --out output/confirmed_facts.json

# 自由事实（结构性、不带身份标签）
python3 scripts/save_confirmed_facts.py --bazi output/bazi.json --add-fact \
  "用户 2024 年事业方向有正向波动；曲线曾误判为 fame down，已通过反向规则修正"

# 结构性纠错（用于下次跳过这个判错路径，例如 climate 标签）
python3 scripts/save_confirmed_facts.py --bazi output/bazi.json --add-structural \
  climate "湿寒命" "外燥内湿" --reason "用户从小怕热 → 体感证伪"
```

下次跑同一八字时（同 `bazi_key` = pillars+gender+birth_year），Step 0 自动加载，不再重复踩坑。

### 5. 关键年份的 LLM 强制解读（已并入 `key_years`）

旧版「派别争议年份」单独成节已废弃；所有三派分歧大的年份（`points[year].is_disputed == true`）都必须收纳进 `analysis.key_years`，在该年的 body 里加一段「⚠ 三派分歧」按 `references/dispute_analysis_protocol.md` Step A→D 输出：

```
⚠ 三派分歧说明：
事实：扶抑派 X 分 / 调候派 Y 分 / 格局派 Z 分（极差 N），融合 V 分。
为何分歧：[1-2 句解释三派各自看到了什么]
我的判断：[偏向哪派 / 取中 / 双向]，因为本命局 [格局/印化/用神] + 本年互动 [具体事件] →
合理推论：[偏 up/down/双向波动]，置信度 [low/mid]
可证伪点：如果 [具体事实] 发生 / 不发生，则我的判断错。
```

**禁止**：
- ❌「派别分歧大，无法判断」
- ❌ 直接报融合值当结论
- ❌「需要更多信息」
- ❌ 不援引命局结构、只用玄学话术
- ❌ 把 dispute 单独列一大堆（已废弃，必须并入 key_years）

完整规则见 `references/dispute_analysis_protocol.md`。

## 三大保障 + 七项强制（必须遵守 · v8 重写校验回路）

- **准确**：分数来自脚本（单盘=「格局为先 + 三派交叉」+「emotion 独立通道」、合盘=「五行 + 干支 + 十神 + 大运」4 层），**禁止 LLM 直接打分**
- **公正**：身份信息不得进入打分流程；同输入双盲必须 bit-for-bit 一致；合盘也只看八字结构、不接收姓名 / 关系状态 / 历史
- **预测性**：未来年份 / focus_years 必须给出 (方向, 置信度) 二元组；低置信度年份图上标灰
- **争议解读（强制）**：每个 disputed 年份都必须并入 key_years 并按 dispute_analysis_protocol Step A–D 解读
- **合盘解读（强制）**：4 层评分必须按 he_pan_protocol §5 解读（按层 → 加 / 减分 → 大运同步 → confidence），禁止甩 grade、禁止给"配/不配"结论
- **流式输出（强制 · v5）**：Step 3a / 合盘解读必须按节流式发出（每写完一节立刻发，禁止憋整段）；Step 2.7 必须先问用户要 markdown-only 还是要 HTML，禁止默认渲染 HTML 让用户白等
- **v8 校验回路（强制 · 替代旧 R0/R1/R2/R3 + 命中率 + phase_inversion）**：Step 2.5 必须按 v8 协议跑 —— ① `handshake.py` 生成 5 维度 ~28 题 + `askquestion_payload`；② Agent 调宿主 **AskQuestion 结构化点选** UI 一次抛全部题（**禁止**用自然语言转述题面让用户口头答"对/不对/部分"，CLI 宿主 fallback 到 `cli_fallback_prompt`）；③ `phase_posterior.py` 算贝叶斯后验 P(phase | answers)；④ 后验阈值落地：≥ 0.80 high adopt / 0.60-0.80 mid adopt / 0.40-0.60 触发追问轮（top-2 候选间最 discriminative 2-3 题，最多 1 轮）/ < 0.40 reject 不出图。`bazi.phase_decision.is_provisional=true` 时 `render_artifact.py` 必须拒绝渲染。详见 `references/phase_decision_protocol.md` + `references/handshake_protocol.md` + `references/discriminative_question_bank.md` 和 `references/diagnosis_pitfalls.md` §14（典型边界 case 详解）。
- **现代化解读铁律（强制 · v7）**：emotion 维度的解读**必须**遵守 fairness_protocol.md §10：
  - **命局可推**：关系结构 / 能量模式 / 偏好的互动模式 / 关系密度
  - **命局不可推**：对方生理性别 / 是否结婚 / 几段关系 / 是否生育 / 关系是否被祝福
  - **禁用措辞**："克夫 / 旺夫 / 旺妻 / 妻星 / 夫星 / 配偶 / 异性缘 / 你应该结婚 / 晚婚 = 命不好 / 你会跟 X 类人结婚"
  - **emotion 高 ≠ 婚姻顺利，emotion 低 ≠ 单身差**——纯中性描述
  - **必须前置声明**：出图后第一段感情解读必须包含「命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育——这些是你的现代选择，不在命局之内」
  - **不接受用户的关系状态作为输入**（"我已婚 / 我跟 X 在一起 5 年" → 接受为现实但不回写打分、不掺入后视镜叙事）
- **原生家庭解读铁律（强制 · v8 经 D1 题库校验）**：family 段的解读**必须**遵守 fairness_protocol.md §11：
  - **命局可推**：父母在你能量场里的存在模式 + 年/月柱财官印聚合的结构画像（5 档：显赫候选 / 中产 / 普通 / 波折 / 缺位）
  - **命局不可推**：父母的社会地位 / 收入 / 职业 / 学历 / 是否健在 / 是否离异 / 是否再嫁
  - **禁用措辞**："出身名门 / 名门望族 / 家世优渥 / 家世显赫 / 父亲名利双收 / 母亲贤惠 / 大家长 / 严父慈母 / 父能传财"
  - **D1 题库校验已并入 v8 主回路**（不再走 v7.3 R3 单独条件触发）：D1 6 题（家境 / 父在场 / 母在场 / 兄弟姐妹 / 出生地 × 时代 / 祖辈影响）随每次 handshake 一起抛，phase_posterior 把答案直接吸收进相位决策；family 段写不写、写多细，由 D1 相关 hard_evidence 题的后验信号 + 用户是否主动问家庭 共同决定
  - **修古法 survivorship bias**：古典命书只收录显赫人物的命例，所以"年柱财官印聚合"在古籍里反复对应"显赫家世"——但在现代普通人的同样结构上，真实概率远低于古法暗示。D1 校验通过的"显赫"才能说，没校验过 / 校验不通过 → family 段降级或省略

## v9 范式转换（2026-04 重写 · precision-over-recall · 多流派交叉投票 · open_phase 逃逸阀）

> **触发动因**：一类"印根足够却被旧算法误判为弃命从财"的边界 case 反思。详见 `references/diagnosis_pitfalls.md` §14 + `references/mind_model_protocol.md`。
> **v9 不是 v8 的小修，是结构性的范式转换**：之前是"算法独断 → 让用户答题校验" → 现在是"多流派加权投票 + open_phase 逃逸阀 + 必出多解备选 + LLM 兜底特殊格"。

### v9 核心改动一览

| 改动 | 文件 | 触发 |
|---|---|---|
| **PR-1** 通根度严判 (`本气/中气/余气` 1.0/0.5/0.2) → 修假从误判 | `scripts/_bazi_core.py::compute_dayuan_root_strength` + `scripts/score_curves.py::apply_phase_override` 守卫 | 任何 `cong_*` / `huaqi_to_*` phase override |
| **PR-2** `--pillars` 模式弃用 (`qiyun_age` 不可精算) + `he_pan` v8 入口守卫 | `scripts/solve_bazi.py` + `scripts/he_pan.py` + `scripts/he_pan_orchestrator.py` | `phase.is_provisional=true` 或 `confidence<0.60` 直接拒合盘 |
| **PR-3** 盲派 `dayun` 层 fanyin/fuyin detector | `scripts/mangpai_events.py::detect_dayun_*` | 大运首年 + 流年伏吟/反吟大运 |
| **PR-4** 心智模型协议 + HS-R7 最高红线 | `references/mind_model_protocol.md` + `scripts/score_curves.py::hsr7_audit` | 任何对外报告必带反身性 disclaimer |
| **PR-5** 罕见格全集 (~110 ZiPing/Mangpai/紫微/铁板) + LLM inline fallback | `references/rare_phases_catalog.md` + `references/llm_fallback_protocol.md` + `scripts/rare_phase_detector.py::scan_all` | 算法判定 Yes 的格直接出, No 的走 LLM 兜底 |
| **PR-6** 多流派加权投票 + open_phase 逃逸阀 | `scripts/_school_registry.py` + `scripts/multi_school_vote.py` | top1<0.55 OR top1_top2_gap<0.10 → `decision="open_phase"` |

### v9 何时落 `open_phase`

- 子平 / 滴天髓 / 穷通 / 盲派 各自出候选 → 加权投票
- 若 top1 后验 < 0.55 → 不许独断
- 输出 `phase_composition` (top3 with role) + `alternative_readings` (top5 with `if_this_is_right_then`)
- 落 open_phase 时主报告必须显式陈述"算法在此盘上不下结论, 请补充更多事件锚点"

### v9 报告必带字段（HS-R7 守卫）

任何 score 产物必须有：
- `multi_school_vote.decision` ∈ {phase_id, "open_phase"}
- `multi_school_vote.consensus_level` ∈ {high, medium, low}
- `multi_school_vote.alternative_readings`（多流派备解 with `if_this_is_right_then`）
- `hsr7_audit`（缺字段会 warning，BAZI_STRICT_HSR7=1 时 raise）

落 open_phase 时, Agent **必须**在对话里把 alternative_readings 全部列出, 并要求用户补 ≥ 2 个具体事件年份再重判。

## 何时阅读 USAGE.md / references/

- **用户问"怎么用 / 怎么触发 / 不会用"** → `USAGE.md`（直接复述给用户）
- **v9 范式入门 + 假从误判教训** → `references/mind_model_protocol.md`（v9 强制） + `references/diagnosis_pitfalls.md` §13-14
- **算法可判定的特殊格 (~30) + LLM 兜底协议 (~80 罕见格)** → `references/rare_phases_catalog.md` + `references/llm_fallback_protocol.md`（v9 强制）
- **每次接到八字 / 生日，进入 Step 2.5 之前** → `references/phase_decision_protocol.md`（v8 强制）+ `references/handshake_protocol.md`（v8 强制）+ `references/discriminative_question_bank.md`（v8 题库源文件）
- **任何后验落地 / 阈值 / phase 决策疑问** → `references/phase_decision_protocol.md` §5 + `references/diagnosis_pitfalls.md` §14（典型边界 case）
- **[deprecated v8] 旧 R0+R1+R2 命中率 / 相位反演兜底** → `references/phase_inversion_protocol.md` 仅作历史参考，新流程不读
- **每次合盘前 / 用户给 ≥ 2 份八字** → `references/he_pan_protocol.md`（强制）
- **每次跑 Step 2a 之前 / 用户问"盲派怎么看"** → `references/mangpai_protocol.md`（强制）
- **每次进入 Step 3a 写 LLM 分析之前** → `references/multi_dim_xiangshu_protocol.md`（强制）
- **每次进入 Step 3a 写 key_years / dayun_review 之前** → `references/zeitgeist_protocol.md` + `references/folkways_protocol.md` + `references/folkways_inference_prompt.md`（强制 · v7.5 · 时代-民俗志解读层）+ `references/class_inference_ethics.md`（伦理红线必读）
- **写 dayun_review 段时** → `references/dayun_review_template.md`（v7.5 新增 · 大运段标准模板）
- 用户问「为什么这年高/低」 → `references/methodology.md` + `references/scoring_rubric.md`
- 用户质疑准确性 → `references/accuracy_protocol.md` + `calibration/dataset.yaml`
- 用户质疑公正性 / 偏向 → `references/fairness_protocol.md`
- 用户问未来怎么走 → `references/prediction_protocol.md`
- **见到 ⚠ 争议年份 / 处理 `disputes` 数组** → `references/dispute_analysis_protocol.md`
- **每次开跑新八字之前 / 反复跑了 2 轮还不准** → `references/diagnosis_pitfalls.md`（已踩过的坑 + 红线表）
- 出现陌生术语（伏吟 / 通关 / 调候 等） → `references/glossary.md`

## 何时阅读 examples/

- 想直观理解输出形态 → `examples/shang_guan_sheng_cai.md`（伤官生财格）/ `examples/guan_yin_xiang_sheng.md`（官印相生格）

## 输出规范

### 单盘输出
| 字段 | 说明 |
|---|---|
| `chart` | Artifact（HTML，type="text/html"，含 marked.js + Recharts + details 折叠 + 整图分析 / 一生评价 / 大运评价 / 关键年份评价四类 markdown）或 PNG 路径；**v6 起 8 条曲线（4 维度 × 实/虚）** |
| `score_table` | Markdown 表格：年份 / 年龄 / 干支 / 大运 / 精神(当/趋势) / 财富(当/趋势) / 名声(当/趋势) / **感情(当/趋势)** / 置信度 |
| `life_review` | 一生**四维度**评价（精神 / 财富 / 名声 / **感情** 各 ≥ 200 字） |
| `dayun_review` | 每段 10 年大运 headline + body |
| `key_years` | 关键年份评价（peak / dip / shift），含大白话推论过程 + 盲派应事 + 三派分歧说明 |
| `mangpai_events` | 按年汇总的盲派应事（仅当 Step 2a 启用） |
| `caveats` | 派别分歧大 / 低置信度年份的免责声明 |

### 合盘输出
| 字段 | 说明 |
|---|---|
| `pair_overview` | 每对人的概览：双方八字 / 日主 / 用神 / 总分定调（人话，非 grade） |
| `layer_breakdown` | 4 层评分逐层解读（五行 / 干支 / 十神 / 大运），每层至少援引 2 条 notes |
| `top_pluses_review` | 关键加分项 → "为什么有意义 + 怎么用上"（≥ 4 条） |
| `top_minuses_review` | 关键减分项 → "摩擦点是什么 + 怎么缓冲"（≥ 3 条） |
| `dayun_sync_advice` | 基于 focus_years 同步度的具体建议（哪些年适合 / 不适合一起搞大事） |
| `confidence_note` | 双方 R1 命中率 → 合盘 confidence + 必要的 caveat |
| `relationship_specific_tips` | 按 rel_type 的特定建议（婚配 / 合作 / 友谊 / 家人） |

## 第一次使用前

```bash
cd ~/.claude/skills/bazi-life-curves
pip install -r requirements.txt
python scripts/calibrate.py             # 跑回测，命中率必须达标才算可用
python scripts/calibrate.py --symmetry  # 性别对称性测试
```
