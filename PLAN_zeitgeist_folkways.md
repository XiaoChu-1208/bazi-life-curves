# PLAN：时代精神 × 民俗志 × 阶级先验

> **本 plan 的定位**：在现有「八字命理 + 三派打分 + 盲派应事」体系上，叠加一套**社会-文化语境层**，让命理事件能被翻译成具体时代里具体场景的人物经历。
>
> **一句话哲学**：命局给出"潜能场"，时代给出"显化通道"，民俗志给出"显化载体"。三者必须分清各自的位置——命局进算法层，时代和民俗志只进 LLM 解读层。
>
> **核心设计原则**：**以 protocol 为骨，以 LLM 为肉**。方法论必须重（写死、可审计、不依赖模型记忆），具体知识必须轻（让 LLM 凭训练知识自由发挥，加 confidence 机制约束）。

---

## 0. 设计起源（6 轮对话迭代）

按时间顺序的关键洞察：

1. **第 1 轮**：命理 + 时代 = 更现代的命理学视角（用户原始想法）
2. **第 2 轮**：只做"后事"不做"前事"——过去用时代背景做贝叶斯锐化，未来只给方向（不过拟合）
3. **第 3 轮**：阶级 / 时代叙事是**思维材料**，不是**输出语言**——可以描述处境，不能贴身份标签
4. **第 4 轮**：单年事件 → 时代区间叙事，让命理事件镶嵌在 5-10 年的社会浪潮里
5. **第 5 轮**：时代背景必须下沉到**民俗志颗粒度**——具体到当时家里有什么、流行什么、大家在学什么
6. **第 6 轮（本轮关键转折）**：**LLM 已经知道这些民俗志知识，不要硬编码**——硬编码无法覆盖非中国用户、年长用户、未来人群。把 protocol 写重，把数据写轻，让 LLM 自由发挥但用 confidence + 自检 + 反馈回流约束

**关键自我约束**：本系统扩展不能违背项目三大保障（准确 / 公正 / 可证伪）和「公正性」红线（`solve_bazi.py` 不接受身份输入）。所有新增能力放在 LLM 解读层，不进入 `score_curves.py` 的打分。

---

## 1. 整体架构（三层解读模型）

新增的解读层是一个**正交于现有打分层**的独立模块：

```
                    ┌─────────────────────────────────────┐
                    │   现有打分层（不动）                   │
                    │   solve_bazi → score_curves         │
                    │   → mangpai_events → handshake      │
                    └──────────────┬──────────────────────┘
                                   │ curves.json + mangpai.json
                                   ▼
        ┌────────────────────────────────────────────────────────────┐
        │   新增：时代-民俗志解读层（zeitgeist_layer）                 │
        │                                                            │
        │   输入：bazi.json + curves.json + mangpai.json + 出生年    │
        │   逻辑：命局阶级 prior（脚本算）                            │
        │       × era_windows 骨架（轻 YAML）                        │
        │       × LLM 凭训练知识 + protocol 推 folkways              │
        │   输出：注入 analysis.json 的 key_years / dayun_review /   │
        │        handshake candidates                                │
        └────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                    现有 render_artifact 输出 HTML
```

**三层概念**（颗粒度从宏到微）：

| 层 | 名称 | 颗粒度 | 在本设计里的位置 |
|---|---|---|---|
| 宏 | `era_windows` | 5-10 年的时代区间 | **轻 YAML 骨架**（中国主线 ~7 个 + 全球大事件主线 ~5 个，每个 30-50 行） |
| 中 | `folkways_layers` | 具体物件 / 媒介 / 流行 / 热潮 / 沟通 / 仪式 6 个 sub-layer | **方法论文档化 + 2-3 个 example**（不做硬编码数据库） |
| 微 | `cohort_experiences` | 按出生年 × 当时年龄段切 | **方法论文档化**（让 LLM 现场推） |

---

## 2. 数据策略（protocol 为骨，LLM 为肉）

### 2.1 三类资产分工

```
┌──────────────────────────────────────────────────────────────────┐
│  必须文档化（方法论 / 项目原创桥接逻辑 / 伦理约束）                  │
│  ───────────────────────────────────────────                     │
│  references/folkways_protocol.md   6 层结构 + 五行规则 + confidence │
│  references/zeitgeist_protocol.md  区间叙事 + 大运对齐策略           │
│  references/class_inference_ethics.md  思维材料 ≠ 输出语言           │
│  references/folkways_inference_prompt.md  LLM 推理 prompt 模板       │
│                                                                  │
│  → 这些都是项目原创知识，LLM 不会，必须写死                          │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  轻量化数据资产（仅作 LLM 推理参考 + 范例）                          │
│  ──────────────────────────────────────────                      │
│  references/era_windows_skeleton.yaml  中国主线骨架（每 window 30-50 行）│
│  references/folkways_examples/china_1995_2002.md  范例 1            │
│  references/folkways_examples/china_2010_2015.md  范例 2            │
│                                                                  │
│  → 不追求完备覆盖，只给 LLM "参考样式" 和 "颗粒度标杆"               │
└──────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│  LLM 自由发挥（用训练知识 + protocol 约束）                         │
│  ────────────────────────────────────────                        │
│  - 具体物件 / 流行 / 热潮的内容                                    │
│  - 非中国用户的民俗志                                              │
│  - 年长用户（1970 之前）的民俗志                                   │
│  - 未来出现的新现象                                                │
│                                                                  │
│  → 通过 3 档 confidence + 5 项自检 + 反馈回流约束                   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 `era_windows_skeleton.yaml`（轻骨架）

**目的**：给 LLM 一份"主流时代分段"的参考，让它在写区间叙事时有锚点；但 LLM 可以根据用户实际地区/年龄**调整或扩展**这个骨架。

每个 window 只写 30-50 行核心信息，不再写 sub_phases / cohort_psychology 等详细字段（让 LLM 自己根据 protocol 推）：

```yaml
# references/era_windows_skeleton.yaml
era_windows:
  # ─── 中国主线 ───
  - id: cn_reform_dawn
    region: china
    span: [1977, 1989]
    label: 改革开放第一波
    headline: 恢复高考-八十年代——理想主义与匮乏并存
    keywords: [恢复高考, 包产到户, 万元户, 文化热, 港台流入, 海子顾城, 严打, 89]
    
  - id: cn_early_market
    region: china
    span: [1990, 1994]
    label: 南巡-初步市场化
    keywords: [南巡讲话, 海南热, 第一波下海, 大哥大, 邓丽君, 91海湾战争集体震动]
    
  - id: cn_reform_late_90s
    region: china
    span: [1995, 2002]
    label: 国企改制 + 入世前夜
    headline: 一个时代结束、另一个时代尚未到来的中间地带
    keywords: [国企改制, 下岗潮, 房改, 香港回归, BP机, VCD, 学英语热, 还珠格格, 入世]
    
  - id: cn_wto_urbanization
    region: china
    span: [2003, 2009]
    label: 入世红利 + 城市化加速
    keywords: [SARS, 房价起飞, 超女, 博客, 北京奥运, 4万亿, 智能手机前夜]
    
  - id: cn_mobile_internet
    region: china
    span: [2010, 2015]
    label: 微博 + 移动互联网爆发
    keywords: [微博兴起, 智能手机普及, 双11, 4G, 中产焦虑, 创业潮, IPO热]
    
  - id: cn_platform_economy
    region: china
    span: [2016, 2022]
    label: 平台经济 + 双减 + 三年特殊时期
    keywords: [短视频, 直播带货, 出海, 双减, 互联网寒冬, 三年特殊时期, 房地产拐点]
    
  - id: cn_ai_native
    region: china
    span: [2023, 2030]
    label: AI 原生 + 反内卷
    keywords: [大模型爆发, AI Agent, 反内卷, 出海再起, 银发经济, 新质生产力]
  
  # ─── 全球大事件主线（跨地区共享）───
  - id: global_post_cold_war
    region: global
    span: [1990, 2000]
    keywords: [苏联解体, 海湾战争, 网景IPO, 多莉羊, 戴妃, 911前夜]
    
  - id: global_post_911
    region: global
    span: [2001, 2010]
    keywords: [911, 反恐战争, 智能手机诞生, 次贷危机, 奥巴马, 福岛地震]
    
  - id: global_polarization
    region: global
    span: [2011, 2020]
    keywords: [阿拉伯之春, 比特币, 脱欧, 特朗普, MeToo, 疫情]
    
  - id: global_ai_age
    region: global
    span: [2021, 2030]
    keywords: [疫情, 俄乌, AI爆发, 通胀, AGI讨论, 多极化加速]
```

**约 12-15 个 windows，整文件 ~400 行**，工作量 0.5 天。

**LLM 用法**：
- 命主出生在 1985 年中国：套 `cn_reform_dawn` + `cn_early_market` + `cn_reform_late_90s` 等
- 命主出生在 1985 年美国：套 `global_post_cold_war` + `global_post_911` 等，**LLM 自己补充 80 年代美国本土 era**（如 Reaganomics, Cold War末段等）
- 命主出生在 1965 年中国：`era_windows_skeleton` 没覆盖文革到改革开放过渡期 → **LLM 自己根据 protocol 起一个 era**（标 `confidence: mid`）

### 2.3 `folkways_examples/`（in-context learning 范例）

**目的**：给 LLM 看"production-quality 的输出长什么样"——颗粒度、6 层覆盖、五行 tag、confidence 标注、援引方式。LLM 通过 in-context learning 学会模仿这种结构。

只做 2-3 个范例，覆盖中国近代两个有代表性的时段：

```
references/folkways_examples/
├── china_1995_2002.md   # 国企改制时代 - 覆盖 70-90 后童年/青春期
├── china_2010_2015.md   # 移动互联网爆发 - 覆盖 80-00 后青年期
└── (可选) china_2016_2022.md  # 平台经济 + 双减 + 疫情
```

每个 example 是一份完整的 markdown 文档，结构如下：

```markdown
# Folkways Example: 中国 1995-2002

> 这是一份示范文档：当 LLM 给一个 1985 年生中国一线城市命主写
> 1995-2002 区间的 key_years body 时，民俗志推理应该达到这个颗粒度
> 和这种结构。

## 该 era 的 6 层 sub-layer 推理

### 1. 物质生活层（material）

| 物件 | 时间窗 | 阶级 marker | 五行 | 十神 | confidence |
|---|---|---|---|---|---|
| BP 机 | 1993-1998（peak 1996） | urban_middle | 金/水 | 食神/伤官 | high |
| 大哥大 | 1992-1997（peak 1995） | urban_elite | 金 | 正官/偏财 | high |
| 小灵通 | 1999-2006（peak 2003） | urban_mass + county | 金/水 | 食神/伤官 | high |
| 拨号上网/猫 | 1996-2002（peak 1999） | urban_educated | 水/木 | 食神/伤官/印 | high |
| VCD/DVD | 1995-2003（peak 1998） | urban_mass | 火/金 | 食神/伤官 | high |
| 21寸彩电 | 1994-2002（peak 1998） | urban_mass | 火 | 食神 | high |
| 摩托车 | 1990-2002（peak 1998） | rural_aspirational + urban_mass | 火/金 | 偏财/伤官 | mid |

... （其他 5 层 sub-layer 同样结构）

## 完整推理流程示范（命主：1985 年生男 / 一线城市 / 用神=火）

### Step 1: 阶级 prior 筛 region 和 class_marker
命局有印星护身 + 财星弱根 → urban_middle / urban_educated 权重最高
→ 优先选 region=tier1+tier2 / class_marker=urban_middle 的 folkways

### Step 2: 用神筛 wuxing
用神=火 → 优先 wuxing 含火/木 的物件
→ 顺位：VCD（火）> 21寸彩电（火）> 学英语（木火）> 拨号上网（水木）

### Step 3: 命理事件年份对齐
1996 伤官见官 → 时代 = 国企改制主峰
1998 食神泄秀 → 时代 = VCD入户高峰 + 还珠格格 + 学计算机
2001 官印相生 → 时代 = 入世 + 申奥成功

### Step 4: 输出 production-quality body（参考 §10 附录）
```

**工作量**：每个 example 1 天，2-3 个 example 共 2-3 天。

**LLM 用法**：在 Step 3a prompt 里把这 2-3 个 example 作为 few-shot 输入，告诉 LLM "你输出的颗粒度和结构应该接近这种水平"。LLM 推非中国用户/其他时代时，迁移这种结构但内容自由发挥。

### 2.4 不再做的东西（说明删减原因）

| 原计划要做的 | 现状 | 删减原因 |
|---|---|---|
| `folkways_table.yaml` 全量数据库（1500+ 条目） | **不做** | LLM 已知；硬编码无法覆盖非中国/年长用户；维护陡增 |
| `cohort_experiences.yaml` 全量代际体验库 | **不做** | 同上；LLM 凭出生年和地区可以现场推 |
| 7-8 个 era_windows 各 200 行的详尽字段 | 压缩成 30-50 行骨架 | LLM 只需要锚点和关键词；详尽字段重复 LLM 能力 |
| 城乡 5 档分支 | 仅在 protocol 里写"3 档（一二线 / 三线县城 / 乡村）作为 LLM 自检维度" | 不需要为每条数据填 region tag |
| 完整的 6 windows × 5 区域 × N 物件矩阵 | 仅 2-3 个 example | example 提供颗粒度参考，矩阵让 LLM 自己织 |

---

## 3. 推论引擎设计

数据资产铺好后，三个使用场景：

### 3.1 场景 A：handshake 校验题升级（Step 2.5）

**当前问题**：现有 round1/round2 候选大多是抽象本性 + 抽象命理事件描述，命中率受用户记忆模糊度影响大。

**升级方案**：增加第三类候选 `folkways_anchors`——把命理事件锚定到具体民俗志事件上。

#### 3.1.1 候选生成（LLM 在 Step 2.5 做）

不再由 `handshake.py` 硬生成 folkways anchor 文案，而是 `handshake.py` 给出"该年命理事件 + 命主用神 + 阶级 prior"等结构化数据，LLM 在 prompt 里**根据 protocol 自己生成**民俗志锚定的校验题。

```python
# scripts/handshake.py 输出新增字段
{
  "folkways_anchor_seeds": [
    {
      "year": 1998, "age": 14, 
      "ganzhi": "戊寅", "dayun": "辛巳",
      "bazi_event": {"name": "食神泄秀", "dimension": "fame", "deviation": +18},
      "user_yongshen": "火",
      "user_jishen": "水",
      "class_prior": {"urban_middle": 0.5, "urban_educated": 0.3, "rural": 0.2},
      "user_birth_year": 1985,
      "user_region_hint": null,   # 用户未提供时为 null
      "era_window_id": "cn_reform_late_90s",
      "instruction": "按 folkways_protocol §3 生成 1 条该年的民俗志锚定校验题"
    }
  ]
}
```

LLM 收到这个 seed 后，按 protocol 跑：
1. 读 `era_windows_skeleton[cn_reform_late_90s]` 获得时代关键词
2. 读 `folkways_examples/china_1995_2002.md` 学颗粒度
3. 用 user_yongshen=火 + class_prior 筛物件
4. 自检 5 项（见 §3.5）
5. 输出 confidence=high 的 claim

#### 3.1.2 校验题的实际呈现

升级前：

> ① 【过往大波动】你 1998 年（14 岁）应该有一次比较显著的"被看见"体验，可能是学业或表达上的。
>    依据：该年食神泄秀，名声维度偏离基线 +18，置信度 high
>    可证伪点：如果该年完全没有任何"被认可"的体验，则错

升级后：

> ① 【民俗志锚点 · 1998】你 1998 年（14 岁）那一年，家里大概率刚有了 VCD 或者你正在学校机房学五笔/Word，命局这年走食神泄秀。最可能的具体形态是：你在某个新工具/新媒介上找到了"被看见"的体验——打字比赛获奖、机房作业被老师拿来展示、用 VCD 录下自己唱歌、给笔友写长信被回信、第一次在班里做主持。
>    依据：1998 ± 1 年是 VCD 入户/学计算机/笔友/萌芽杂志的高峰期；你命局这年食神泄秀（+18），用神火/木与"学习类热潮"五行相合
>    可证伪点：如果你 1998 年家里既没买 VCD/电脑、也没参加任何与"被看见"相关的具体事件（比赛/发表/被表扬），则这条错。

#### 3.1.3 round1/round2 配比调整

| 位置 | 当前 | 升级后 |
|---|---|---|
| Round 1（3 条） | 1 体质 + 1 本性 + 1 锚点 | 1 体质 + 1 本性 + 1 **民俗志锚点** |
| Round 2（3 条） | 1 本性 + 2 锚点 | 1 本性 + 1 抽象锚点 + 1 **民俗志锚点** |

体质和本性不动（命局静态最难骗），民俗志锚点替换/补充原有的抽象事件锚点。

### 3.2 场景 B：key_years 解读（Step 3a）

**当前问题**：单年事件 + 抽象时代背景 → 解读偏抽象，"那年应该有变动"用户不知道是什么变动。

**升级方案**：把 `key_years` 重组为**区间叙事 + 区间内的命理节点**结构。

#### 3.2.1 新模板（替换 multi_dim_xiangshu_protocol.md §3.1）

```markdown
## {era_window.label} · 你 {age_at_start}–{age_at_end} 岁 · {era_window.span}

### 时代底色（这段日子整体是什么样）
{era_window.headline}

{LLM 根据 era_window.keywords + 训练知识展开 3-4 句背景描述}

这段时间里有几个标志性的细节，你大概率经历过：
- {LLM 推 5-8 条该 era 高识别度物件 / 流行 / 热潮，每条标 confidence}
  - 优先 confidence=high 的（春晚 / 还珠格格 / 香港回归这种全民现象）
  - 其次 confidence=mid 的（BP机 / VCD 这种有阶级分化的）
  - 禁止 confidence=low 的出现

### 命局给的几个具体节点

#### {年份 1}（{年龄}岁，{干支}，{大运}）
**命理读出**：{命局事件简述，例如"伤官见官"}
**放在大背景里看**：{结合 era_window 子节奏 + folkways + 命局阶级 prior 的具体化解读}
- **首选形态**：{最可能的具体显化（必须是 confidence=high 或 mid）}
- **备选形态 1**：{第二可能}
- **备选形态 2**：{第三可能}

#### {年份 2}（...）
... 

### 这段区间的累计影响（≥ 150 字）
{从命局结构 + 该区间所有命理节点 + 该区间集体情绪出发，
 推论命主在这段时间里"内化了什么底层叙事"}

### ⚠ 整段证伪点
如果你回忆这一整段（{era_window.span}）和上面描述的时代底色 / 命理节点完全对不上，
请告诉我——多半是命局的阶级 prior 或时辰判断有偏差，需要重新校准。
```

#### 3.2.2 大运 × era_window 对齐策略

命局自带 10 年大运分段，时代区间是 5-10 年，两者通常错位。三种对齐情况：

```
情况 A：大运 ≈ era_window（误差 < 2 年）
  → 共振区，叙事最强烈，body 写最长（≥ 600 字）
  → 这段是用户人生的"时代命运共振点"

情况 B：大运跨越两个 era_window（前 N 年 A 区间，后 10-N 年 B 区间）
  → 大运分两段写，每段嵌入对应 era_window 背景
  → 在两段交界处加一段"时代切换感受"

情况 C：一个 era_window 跨越两个大运
  → 时代背景写一段大的，下面分两段大运分别讲命理节点
```

对齐计算放在 `scripts/_zeitgeist_loader.py`（轻量），把对齐结果传给 LLM。

### 3.3 场景 C：dayun_review 大运评价（Step 3a）

每段 10 年大运评价的 body 必须包含一段「时代镶嵌」：

```markdown
**{大运干支} · {年龄段} · {年份段}**

> headline: ...

**这 10 年的命理属性**：{从扶抑/调候/格局判出的大运属性}

**镶嵌的时代**：你这段大运基本对应 {era_window.label}（{对齐情况说明}）。
当时整个社会的底色是 {LLM 推 1-2 句}，而你身处这股浪里命局走的是 
{大运十神 + 五行}——意味着你在这段时代里大概率以 {具体的姿态} 参与其中。

**实际表现的可能形态**：
- 如果你属于 {阶级 prior 选中的群体}，这段时间最可能体现为 {具体场景}
- 如果命局某些条件不同（{反例条件}），则可能体现为 {另一种场景}

**建议**：{基于该大运 + 时代窗口的可操作建议}
```

### 3.4 三档 confidence 机制（约束 LLM 自由发挥的关键 ①）

让 LLM 在生成每条民俗志推论时**必须**标 confidence：

| 档 | 含义 | 用法 |
|---|---|---|
| **high** | 该物件/事件在该地区该时段是被广泛报道的标志性现象 | 直接写入"首选形态" |
| **mid** | 该物件/事件流行但有阶级/地域分化 | 写入"备选形态"或注明条件 |
| **low** | 推测可能但不确定 | **禁止出现在输出**，转为"如果……请告诉我"的开放问题 |

**判断标准**（写在 folkways_protocol.md 里供 LLM 自检）：

```
high 标准（满足以下 ≥ 2 条）：
  - 全国/全地区性媒体集中报道
  - 跨阶级跨城乡都有共同记忆
  - 在主要历史叙事中被反复提及
  - 即使不同政治立场也都承认这个现象存在
  
  示例：1997 香港回归 / 1998 还珠格格 / 2008 北京奥运 /
        1985 Live Aid / 2001 911 / 2008 金融危机

mid 标准（满足以下 ≥ 1 条）：
  - 限定某个阶级 / 城乡 / 行业群体
  - 流行有时间和地理梯度（一线先 → 三线后）
  - 不同代际/地区的回忆颗粒度不同
  
  示例：BP 机（urban_middle 1996 / county 1999） /
        VCD（一线 1995 / 县城 1999） / 拨号上网

low 标准（任一条即为 low，禁止出现在输出）：
  - 你（LLM）只能猜测但无法给出具体时间窗
  - 该现象的存在本身就有争议
  - 你不熟悉该地区/年代的具体情况
  
  → 转为开放问题："你那时候是不是在 X 城市 / 做 Y 工作？告诉我后我能更具体"
```

### 3.5 LLM 自检表（约束 LLM 自由发挥的关键 ②）

在 `references/folkways_protocol.md` 里写死，每条民俗志推论输出前必须能回答 5 个问题：

```
□ 1. 这个物件 / 事件的时间窗（first_appear / peak / declining）是哪一段？
     → 答不出 → confidence 自动降为 low → 不能写入输出
     
□ 2. 它的地域分布是什么？（一线 / 三线 / 县城 / 乡村；中国/全球）
     → 答不出 → 必须在输出中注明"地域不确定"
     
□ 3. 它的阶级 marker 是什么？（普及型 / 中产标志 / 精英标志）
     → 答不出 → 不能用作"首选形态"，只能用作"备选形态"
     
□ 4. 它的五行 tag 是什么？（按 folkways_protocol §4 的规则推）
     → 答不出 → 不能参与"用神匹配筛选"，只能作为时代背景描述
     
□ 5. 它对应该用户的哪个命理事件？
     → 答不出 → 这条不应该写在 key_years 里，转为整段时代背景描述
     
任意 1 项答不出 → 该条不能进入"首选形态"
任意 2 项答不出 → 该条完全不能写
```

这是让"民俗志推论"不沦为 LLM 自由发挥的根本约束——**LLM 必须在 prompt 里显式回答这 5 个问题，回答不全的条目被自动过滤**。

### 3.6 用户反馈回流（约束 LLM 自由发挥的关键 ③）

如果用户在 handshake 中说"不对，1998 年我家还没有 VCD" → 写入 `confirmed_facts.json` → 下次同区域同年代的命主跑时，把这条作为 prior 信号传给 LLM：

```jsonc
// confirmed_facts.json
{
  "folkways_corrections": [
    {
      "user_birth_year_range": [1980, 1990],
      "user_region_hint": "county",
      "era_window_id": "cn_reform_late_90s",
      "correction": "VCD 在县城真实普及高峰是 2000-2003，不是 1998",
      "confidence_after_correction": "mid",
      "reported_by": "user_xxx",
      "timestamp": "2026-04-21"
    }
  ]
}
```

LLM 在生成时会读这个文件，作为校正性 prior。这是用**集体反馈**逐步校准 LLM 的内置知识，比死磕一份数据库优雅得多。

### 3.7 可选的 micro-YAML 校正层（兜底）

如果未来发现 LLM 在某些区域/年代反复出错，可以**针对性**补一份 micro-YAML：

```yaml
# references/folkways_corrections.yaml （可选 · 仅当 LLM 反复出错时补）
overrides:
  - region: china_county
    period: [1995, 2000]
    correction: "VCD 在县城真实普及高峰是 2000-2003，不是 1998-1999"
    
  - region: china_rural
    period: [1990, 2010]
    correction: "电视机普及在中西部农村比一线晚 5-10 年"
```

这是**校正层**而非**主数据层**，工作量按需扩展。

---

## 4. 命局五行 × 民俗志的语义映射（项目原创）

这是让"民俗志推论"和命理打通的关键 - 不是 LLM"自由发挥"，而是结构化匹配。**这一节必须文档化**（LLM 不会，是项目原创）。

### 4.1 五行 tag 推断规则（写在 folkways_protocol.md §4）

LLM 给民俗志条目打五行 tag 时，按以下规则推（不是凭"印=印章=文书"那种传统取象自由发挥）：

```
金：定型 / 收割 / 切割 / 结构化 / 高精度
  - 实例：BP 机、大哥大、Walkman、自行车、计算器
  - 现代：iPhone、机械表、AI 芯片、剃须刀

木：生发 / 教学 / 培育 / 知识 / 文化
  - 实例：图书馆、学校、补习班、读书、培训
  - 现代：Coursera、知乎、教育视频

水：流动 / 连接 / 智识 / 信息 / 跨界
  - 实例：BBS、QQ、邮件、电话、写信、报纸
  - 现代：微信、Twitter、新闻 App、AI Agent

火：被看见 / 演示 / 传播 / 表达 / 镜头
  - 实例：电视、电影、广播、磁带、KTV
  - 现代：抖音、直播、Podcast、社交媒体

土：稳定 / 承载 / 持有 / 收藏 / 不动产
  - 实例：房子、家具、邮票、文物、单位福利
  - 现代：房产、长期持有股票、收藏

复合 tag 规则：
  - 智能手机 = 金 (硬件) + 火 (屏幕传播) + 水 (信息流)
  - VCD = 火 (影像) + 金 (光盘介质)
  - 学英语 = 木 (教育) + 火 (表达)
  - 学计算机 = 金 (机器) + 水 (信息) + 食神/伤官 (表达)
```

### 4.2 LLM 筛选规则（强制）

LLM 在写某年取象时，**必须先按命主用神筛选民俗志条目**：

```
1. LLM 凭训练知识列出该年活跃的 folkways 候选（≥ 5 条）
2. 给每条按 §4.1 规则推 wuxing + shishen tag
3. 按命主 yongshen 筛 wuxing 匹配（用神为火 → 优先 wuxing 含火/木 的条目）
4. 按命主该年 shishen 互动筛（如食神泄秀年 → 优先 shishen 含食神 的条目）
5. 按阶级 prior 筛 region / class_marker
6. 取 top 1-2 作为"首选形态"，top 3-5 作为"备选形态"
```

### 4.3 输出强制约束（写在 folkways_protocol.md §5）

- 必须按 §3.5 自检表过 5 项
- 必须按 §3.4 标 confidence
- **禁止凭空编造"那年流行 X"**——如果 LLM 自己都说不出该现象的 5 个属性（时间窗 / 地域 / 阶级 / 五行 / 对应命理事件），不能写
- 如果某年某区域确实不熟悉，**必须如实说**"这一年的具体细节我不掌握，只能讲命理结构"

---

## 5. 阶级先验推断模块

### 5.1 命局 → 阶级先验的映射表（脚本算，内部使用，不输出）

```python
# scripts/_class_prior.py

CLASS_PRIOR_RULES = [
    # (条件函数, 标签, 权重)
    (lambda b: b.has_strong_yin_protect(), "urban_state_or_educated", 0.5),
    (lambda b: b.cai_xing_through_with_root(), "urban_market_oriented", 0.4),
    (lambda b: b.guan_sha_clear_with_root(), "institutional_family", 0.4),
    (lambda b: b.bi_jie_heavy_no_zhi(), "rural_or_county", 0.3),
    (lambda b: b.shi_shang_xiu_no_root(), "freelance_artisan_family", 0.3),
    (lambda b: b.cai_guan_both_lost(), "grassroots_self_made", 0.4),
    (lambda b: b.day_master_weak_qi_sha_heavy(), "early_high_pressure", 0.3),
    # ... 共 10-15 条
]

def infer_class_prior(bazi) -> dict:
    """返回 {tag: weight} 字典，所有 tag 都是描述性的，不是评价性的。
    
    ⚠ 重要：返回值仅供 LLM 内部筛选 folkways 条目使用，
            严禁作为输出文本的 label 出现。
    """
    scores = defaultdict(float)
    for cond, tag, w in CLASS_PRIOR_RULES:
        if cond(bazi):
            scores[tag] += w
    total = sum(scores.values()) or 1.0
    return {k: v/total for k, v in scores.items()}
```

### 5.2 阶级 tag → folkways 筛选的映射（在 protocol 里描述，不做硬编码 YAML）

```
urban_state_or_educated:
  prefer_class_marker: [urban_middle, urban_educated]
  prefer_region: [tier1, tier2]
  prefer_fads: [learning, education]

urban_market_oriented:
  prefer_class_marker: [urban_mass, urban_aspirational]
  prefer_region: [tier1, tier2, tier3]
  prefer_fads: [business, investment]

rural_or_county:
  prefer_class_marker: [rural_aspirational, rural]
  prefer_region: [county, rural]
  prefer_material: [摩托车, 黑白电视末班车, 缝纫机]
```

LLM 收到 class_prior 后，按这个映射筛选 folkways 候选。

### 5.3 ⚠ 伦理护栏（强制写进 class_inference_ethics.md）

核心 3 条：

1. **思维材料 ≠ 输出语言**：阶级 prior 是 LLM 内部筛选 folkways 的依据，不允许出现在用户可见文本中
2. **只描述处境，不命名身份**：可以说"你父母可能在那段时间经历了岗位变动"，不能说"你出身工人阶级"
3. **自检规则**：每段输出过一遍——把所有阶级名词去掉，剩下的描述是否仍然成立？如果不成立，你只是在贴标签

完整规则见 §10 之后再展开（在实际写 protocol 时填详）。

---

## 6. 实施 Phasing

### Phase 0：方法论文档（1-2 工作日）

不写数据，先把"为什么这么做 / 怎么做 / 哪些不能做"写清楚。

| 交付物 | 内容 | 工作量 |
|---|---|---|
| `references/zeitgeist_protocol.md` | 区间设计原则 + retro/prospective 双模式 + 大运对齐策略 | 0.5 天 |
| `references/folkways_protocol.md` | 6 sub-layer 设计 + 五行映射规则 + confidence 三档 + 5 项自检表 + 援引规则 | 0.5 天 |
| `references/class_inference_ethics.md` | 阶级 prior 使用边界 + 伦理护栏 + 自检清单 | 0.3 天 |
| `references/folkways_inference_prompt.md` | LLM 推理 prompt 模板 + few-shot 调用范例 | 0.3 天 |
| 修订 `SKILL.md` | 把新增 Step 3a 的"时代-民俗志解读层"写进六步流程图 | 0.2 天 |

### Phase 1：轻量数据底座（1-2 工作日）

| 交付物 | 内容 | 工作量 |
|---|---|---|
| `references/era_windows_skeleton.yaml` | 中国主线 7 windows + 全球大事件主线 4-5 windows，每个 30-50 行 | 0.5 天 |
| `references/folkways_examples/china_1995_2002.md` | production-quality 范例 1（覆盖 70-90 后童年/青春期） | 1 天 |
| `references/folkways_examples/china_2010_2015.md` | production-quality 范例 2（覆盖 80-00 后青年期） | 0.5 天 |

**关键决策**：相比之前 5-7 天的数据底座，这里压缩到 1-2 天。LLM 自由发挥 + 2 个范例 + 骨架 = 比 1500+ 条目硬编码效果更好。

### Phase 2：推论引擎升级（2-3 工作日）

| 交付物 | 修改 |
|---|---|
| `references/multi_dim_xiangshu_protocol.md` | 加 §3.4「区间叙事模板」+ §3.5「民俗志援引规则」 |
| `references/handshake_protocol.md` | 加 §2.3「民俗志锚点候选」+ Round 1/2 配比调整说明 |
| 新增 `references/dayun_review_template.md` | 把当前散落的大运评价规范集中，加「时代镶嵌」段 |

### Phase 3：工程接入（2-3 工作日）

| 交付物 | 内容 |
|---|---|
| `scripts/_zeitgeist_loader.py`（新） | 加载 era_windows_skeleton + 大运 × era 对齐算法 |
| `scripts/_class_prior.py`（新） | 命局 → 阶级 prior 推断（脚本算，纯结构化输出） |
| `scripts/handshake.py` 修改 | 加 `folkways_anchor_seeds` 输出字段（不生成文案，只给 seed） |
| `scripts/render_artifact.py` 修改 | 加载 era_windows_skeleton + folkways_examples + class_prior 注入 LLM prompt 上下文；HTML 模板加「时代镶嵌」section |
| `templates/chart_artifact.html.j2` 修改 | 区间叙事用新的卡片样式；民俗志锚点在 handshake 里用特殊标识 |

### Phase 4：验证与校准（2-3 工作日）

| 交付物 | 内容 |
|---|---|
| 拿 `examples/shang_guan_sheng_cai`（1990 年生，覆盖 1995-2002）重跑 | 输出 before/after 对比 |
| 拿 `examples/guan_yin_xiang_sheng` 重跑 | 同上 |
| 拿一个**非中国/年长**的虚构八字跑（如美国 1965 男） | 验证 LLM 自由发挥能力是否符合 protocol |
| `calibration/zeitgeist_metrics.yaml`（新） | 加新校准指标：民俗志锚点命中率、区间叙事可证伪命中率 |
| `references/diagnosis_pitfalls.md` 增补 | 把"民俗志推论错位"和"阶级 prior 判反"的常见坑写进去 |

### Phase 5：长期维护机制（持续）

| 机制 | 设计 |
|---|---|
| 用户反馈回流 | 用户在 handshake 中确认 / 否定的民俗志锚点 → 写入 `confirmed_facts.json.folkways_corrections` → LLM 下次推理时读取作为 prior |
| 校正层增量补充 | 当某区域/年代 LLM 反复出错时，按需补 `references/folkways_corrections.yaml` |
| 数据质量审计 | 每季度 review 一次校正记录 + example 文档是否需要更新 |

### 总工作量估算

| 阶段 | 工作量 | 累计 |
|---|---|---|
| Phase 0 | 1-2 天 | 1-2 天 |
| Phase 1 | 1-2 天 | 2-4 天 |
| Phase 2 | 2-3 天 | 4-7 天 |
| Phase 3 | 2-3 天 | 6-10 天 |
| Phase 4 | 2-3 天 | 8-13 天 |

**端到端 demo 时间**：6-7 工作日完成 Phase 0+1+2 + Phase 3 最小可用版本 + Phase 4 单 example 跑通。

---

## 7. 风险与边界

### 7.1 已识别风险（核心是"LLM 自由发挥"如何约束）

| 风险 | 应对 |
|---|---|
| LLM 编造不存在的物件 / 事件 | §3.5 五项自检 + §3.4 confidence 三档 + 强制只用 high/mid |
| LLM 时间窗记错（VCD 说成 1996 普及实际 1998） | §3.6 用户反馈回流 + §3.7 可选 micro-YAML 校正层 |
| LLM 对某些区域/年代不熟悉（非洲 1970s 等） | 必须如实说"细节不掌握，只讲命理结构"——禁止瞎编 |
| 阶级 prior 判反 → 整段推论方向错 | handshake 加「整段证伪点」让用户能一句话否定整个区间，触发重判 |
| LLM 把 90 年代细节用在 80 年代 | 自检表第 1 项强制要求时间窗 + few-shot example 给颗粒度 |
| 民俗志推论带建设者的视角偏差 | Phase 4 加非中国虚构八字测试 + 长期反馈校准 |
| LLM 把阶级 prior 当成输出 label | class_inference_ethics.md 自检规则 + render 阶段做关键词过滤（如发现"工人阶级"等词警告） |

### 7.2 红线（绝不能做）

- ❌ 把阶级 / 时代 prior 写入 `score_curves.py` 打分逻辑（破坏公正性 + 双盲对称性）
- ❌ 把任何身份标签写进用户可见的输出文本
- ❌ 用民俗志推论合理化任何对未来的精确预测（保持"前事细 / 后事粗"的认识论原则）
- ❌ LLM 对不熟悉的区域/年代瞎编（必须 graceful 降级到"只讲命理结构"）

### 7.3 此设计相对硬编码方案的真实代价

承认 trade-off：

- 中国 1970-2010 这段（占用户绝大多数）的细节准确度**可能略低于硬编码方案**
  - 物件普及时间窗的精确度（VCD 实际 1998 普及，LLM 可能说 1996）
  - 地域分化的颗粒度（LLM 对县城 vs 一线的差异感不如人工填写）
  - 一些非主流但用户共鸣度高的细节（地区特有的小吃、电视台节目）

- 换来的是：
  - **无限的地域 / 年代覆盖**（非中国用户、年长用户、未来人群）
  - **零数据维护成本**
  - **更自然的取象**（不受预设条目约束）
  - **工作量从 13-20 天降到 8-13 天**

- 兜底机制：
  - Phase 4 验证发现重大偏差 → 补 example 或 micro-YAML 校正
  - 用户反馈回流机制长期校准

---

## 8. ⚠ 关键决策点（需用户拍板）

旧 plan 里有 5 个决策点，新设计下：
- 决策 3（数据起点）失效：不再有"硬编码起点"概念，LLM 自由覆盖
- 决策 5（handshake 民俗志题占比）暂定为「平衡」（R1/R2 各 1 条民俗志 + 抽象锚点 + 体质/本性）

剩下 3 个决策点：

### 决策 1：时代区间颗粒度

| 选项 | 优点 | 缺点 |
|---|---|---|
| 5 年一段 | 时代切换更精细 | era_windows 数量翻倍 |
| **7-10 年一段（推荐）** | 与大运段量级相当，对齐算法简单；叙事单元厚重 | 区间内部需要 sub_phases 切节奏（让 LLM 自己推） |

### 决策 2：城乡分支策略

| 选项 | 含义 |
|---|---|
| 不分（用 universal） | 所有 folkways 推论用一套，class_prior 仅用于物件优先级 |
| **3 档（推荐）：tier1+tier2 / tier3+county / rural** | LLM 在自检表第 2 项判断地域 + 输出时按"如果你属于 X 区域 → 形态 Y"分支 |

### 决策 3：folkways_examples 数量

| 选项 | 范围 |
|---|---|
| 1 个：仅 china_1995_2002 | 只覆盖 70-90 后中国童年/青春期 |
| **2 个（推荐）：1995-2002 + 2010-2015** | 覆盖 70-00 后两段关键时代，兼顾 in-context learning 多样性 |
| 3 个：再加 2016-2022 | 更全但工作量陡增；可作为 Phase 5 长期补充 |

---

## 9. 第一刀建议（增量起步路径）

```
Day 1: Phase 0 三份 protocol（zeitgeist / folkways / class_inference_ethics）+ 第四份 prompt 模板
       → 你过一遍方法论是否清晰

Day 2: era_windows_skeleton.yaml 全 12-15 个 windows + folkways_examples/china_1995_2002.md
       → 第一个范例做透

Day 3: 改 multi_dim_xiangshu_protocol.md + handshake_protocol.md
       + 写 _zeitgeist_loader.py + _class_prior.py（最小可用）

Day 4: 改 handshake.py + render_artifact.py + chart_artifact.html.j2

Day 5: 拿 examples/shang_guan_sheng_cai（1990 年生，正好覆盖 1995-2002）跑端到端

Day 6: 输出 before/after 对比文档；拿一个虚构非中国/年长八字测 LLM 自由发挥能力

Day 7: 根据 Day 5-6 反馈微调 + 写 folkways_examples/china_2010_2015.md（第二范例）

Day 8+: 长期维护机制上线（反馈回流 / 校正层）
```

**第一个里程碑（Day 5 末）**：能拿一个 1990 年生的命主，看到他 1995-2002 这段被时代-民俗志解读后的 key_year body，对比之前的版本，判断这条路是否真的把"理解一个人"的能力提升了。

**第二个里程碑（Day 6 末）**：能拿一个虚构的美国 1965 / 日本 1975 / 中国 1955 八字跑通，验证 LLM 自由发挥模式是否在非中国/年长场景下也能给出合规输出（confidence 标对、自检过五项、不瞎编）。

---

## 10. 附录：参考实现样例

### 10.1 1995-2002 window 的 production-quality 解读输出

（按完成 Phase 0+1+2+3 后预期产出的 key_years body）

> ### 1995–2002 · 你 11–18 岁 · 国企改制 + 入世前夜
> 
> 这 8 年是你成长里很关键的一段大背景。整个社会处在「一个时代结束、另一个时代尚未到来」的中间地带——单位制开始松动、铁饭碗叙事第一次大规模动摇、互联网在远处萌芽、港台流行文化全面渗透。大人比较紧张，但孩子能感受到那种"大门正在打开"的隐约气息。
> 
> 这段时间里有几个标志性的细节，你大概率经历过：
> - **物件**：家里第一台 VCD（1998 前后入户高峰，confidence: high）、父亲单位发 BP 机（1996 是分水岭，confidence: mid - 城镇中产家庭典型）、镇上第一家网吧（1999-2001，confidence: high）
> - **流行**：还珠格格（1998 全民现象，confidence: high）、F4 流星花园（2001-2002 末段，confidence: high）、周杰伦范特西冲击（2001，confidence: high）
> - **热潮**：疯狂英语跟读"How are you"、学校机房学五笔/Word、《读者》《萌芽》是放学后必备
> - **沟通**：写信给笔友、留同学录、在公用电话亭排队、第一次用 QQ（2001 前后）
> - **集体仪式**：97 香港回归、98 抗洪、99 澳门回归、2001 申奥成功 + 入世——每一年你都坐在电视机前
> 
> 在你命局里，这 8 年大运正好走在 **辛巳大运的中后段**，三派都判这是个相对平衡的段落。命局给出的几个具体节点是：
> 
> #### 1996 年（12 岁，丙子流年）· 伤官见官
> **命理读出**：原局印星护着，但这年伤官透出来撞官星，是一次和"权威系统"的小摩擦。
> **放在大背景里看**：1996 年正处国企改制深水区、下岗潮主峰。
> - **首选形态**：父母中至少一方的工作发生重要变动（下岗 / 转岗 / 单位重组），家里气氛紧张了一阵，但你被印星护着没受直接冲击。
> - **备选形态 1**：转学 / 小升初分班（与"权威系统"的另一种摩擦）
> - **备选形态 2**：搬家（97 年前后福利分房末班车前夕）
> 
> #### 1998 年（14 岁，戊寅流年）· 食神泄秀
> **命理读出**：上一年的紧张消化掉了，命局走得轻快一些，名声维度偏离基线 +18。
> **放在大背景里看**：1998 是 VCD 入户高峰、还珠格格全民现象、学校开始普及计算机课的关键年。
> - **首选形态**：你在某个新工具/新媒介上找到了"被看见"的体验——打字比赛、机房作业被老师拿来展示、用 VCD 录下自己唱歌、给笔友写长信被回信、第一次在班里做主持。
> - **备选形态**：成绩跃升 / 进了某个班 / 第一次在班里做主持。
> 
> #### 2001 年（17 岁，辛巳流年）· 官印相生
> **命理读出**：印星被官星生起来，是命局里"上一个台阶"的节点。
> **放在大背景里看**：正赶上中国入世前后这个新窗口打开 + 申奥成功带来的集体兴奋。
> - **首选形态**：一次重要的考试 / 升学 / 选拔，让你进入了一个明显更大的平台（重点高中、保送、竞赛获奖）。
> - **备选形态**：第一次明确意识到"我和家乡同学的人生路径要分叉了"。
> 
> ### 这段区间的累计影响
> 你在一个家庭和社会都在重新洗牌的时间窗里完成了童年到青春期的转换。命局的"印星护身"在这段时间起了关键作用——同样这段时代里，没有印星护身的孩子很多人留下了长久的不安全感（"我家就是从那时候开始走下坡路"），而你大概率内化的是"世界会变但我能稳住"的底层叙事。这种底层叙事会在你 30+ 岁面对类似不确定性时被反复唤起，是你区别于很多同龄人的一个心理资本，也可能是你对"稳定的执念"的来源。
> 
> ### ⚠ 整段证伪点
> 如果你回忆这一整段（1995-2002）和上面描述的时代底色 / 命理节点完全对不上，请告诉我——多半是命局的阶级 prior 或时辰判断有偏差，下面的 2003-2009 区间也需要重新校准。

### 10.2 非中国八字示例（验证 LLM 自由发挥）

（按 Day 6 测试目标，举一个虚构美国 1965 年生命主预期产出的 key_years body 片段）

> ### 1980–1989 · 你 15–24 岁 · Reaganomics + Cold War 末段
> 
> 这 10 年是你从青春期到大学毕业的关键段。整个美国社会的底色是"乐观主义回归 + 个人奋斗叙事 + 冷战进入收官"——MTV 1981 年开播、PC 进入家庭、Wall Street 的"贪婪是好的"、苏联开始露出疲态、柏林墙在你 24 岁那年倒塌。
> 
> 这段时间里几个标志性的细节，你大概率经历过：
> - **物件**：家里的第一台 PC（IBM PC 或 Apple II，1981-1985 入户，confidence: mid）、Walkman（1980-1985 高峰，confidence: high）、VHS 录像带 + 录像店（1983-1990 高峰，confidence: high）
> - **流行**：MTV / Michael Jackson Thriller（1982，confidence: high）、E.T.（1982）/ Back to the Future（1985）、Madonna 出道（1983）
> - **集体仪式**：1986 挑战者号爆炸、1989 柏林墙倒塌
> 
> ⚠ 中国 90 年代 BP 机这种细节在你这段时间不适用——这是按你出生地推的美国本土 folkways。如果你其实是亚裔移民家庭/在海外华人社区长大，请告诉我，会切换 prior。
> 
> （后续命理节点解读省略...）

注意上述美国场景**完全靠 LLM 训练知识 + protocol 自检生成**，没有任何美国 folkways YAML。同时主动提示了"如果文化背景不匹配请告诉我"——这是对自己 confidence 的诚实表达。

---

## 文档版本

| 版本 | 日期 | 变更 |
|---|---|---|
| v0.1 | 2026-04-20 | 初稿，硬编码数据库设计 |
| v0.2 | 2026-04-21 | **重大重构**：改为「protocol 为骨，LLM 为肉」设计；删除 folkways_table.yaml + cohort_experiences.yaml 全量数据库；era_windows 缩成轻骨架；新增 confidence 三档 + 5 项自检 + 反馈回流机制；工作量 13-20 天 → 8-13 天；自动覆盖非中国/年长用户 |
