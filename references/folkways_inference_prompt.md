# 民俗志推理 Prompt 模板（Folkways Inference Prompt）

> 这份文档是给 LLM 的"操作手册"——讲清楚 Step 3a 写区间叙事时，从拿到上下文到产出文本的具体推理步骤。如果要在 system prompt / agent instruction 里放一段"民俗志专项指引"，就放这一份。

## 0. 前置阅读（必读）

按顺序读完以下 3 份协议（不读不可启动民俗志推理）：

1. `references/zeitgeist_protocol.md` — 时代叙事的结构原则
2. `references/folkways_protocol.md` — 民俗志的 6 层 + 五行映射 + 三档置信 + 五项自检
3. `references/class_inference_ethics.md` — 阶级 prior 的伦理红线

参考材料（如果存在则读）：

- `references/era_windows_skeleton.yaml` — 时代窗口骨架
- `references/folkways_examples/*.md` — 已写好的高质量示例（few-shot 学习）
- 用户的 `confirmed_facts.json` — 历次校验积累的事实

## 1. 整体推理流程（5 步）

```
[输入]
  ↓
1. 加载 era_windows + class_prior + 命主上下文
  ↓
2. 对齐大运 × era_window
  ↓  
3. 内部生成 folkways 候选（用户不可见）
  ↓
4. 三层过滤：confidence + 自检 + 五行匹配
  ↓
5. 写区间叙事（按 zeitgeist_protocol §3.1 标准结构）
  ↓
[输出 Markdown]
```

## 2. Step 1：加载上下文

LLM 应能拿到的输入（由 `_zeitgeist_loader.py` + `_class_prior.py` 注入）：

```python
{
  "user_birth_year": 1985,
  "user_qiyun_age": 8,
  "user_dayun_segments": [
    {"label": "庚辰", "start_age": 8, "end_age": 17, "start_year": 1993, "end_year": 2002},
    ...
  ],
  "era_windows": [
    {"id": "cn_reform_late_90s", "label": "国企改制 + 入世前夜",
     "span": [1995, 2002], "keywords": [...], "global_keywords": [...]},
    ...
  ],
  "class_prior": {
    "primary_class": "urban_state_or_educated",
    "distribution": {
      "urban_state_or_educated": 0.55,
      "urban_market_oriented": 0.25,
      "rural_or_county": 0.15,
      "other": 0.05
    },
    "evidence": [
      "年柱正印 + 月柱正官 → 体制气质",
      "起运 8 岁早 → 家庭节奏稳",
      "调候用神到位 → 资源相对充足"
    ],
    "confidence": "mid"   # 阶级推断本身就有不确定，标 mid 提醒 LLM
  },
  "yongshen_wuxing": "金",
  "weakest_wuxing": "土",
  "key_year_candidates": [
    {"year": 1996, "age": 11, "ganzhi": "丙子", "events": [...]},
    ...
  ],
  "confirmed_facts": {...}   # 历次校验
}
```

## 3. Step 2：对齐大运 × era_window

按 `zeitgeist_protocol §4`：

```
for each era_window in era_windows:
    overlap_dayuns = [d for d in dayun_segments
                       if d.start_year <= era.span[1] 
                       and d.end_year >= era.span[0]]
    
    if len(overlap_dayuns) == 1 and abs_overlap >= 0.7:
        → 情况 A（共振）→ body 写 ≥ 600 字，作 dayun_review 高光段
    elif len(overlap_dayuns) == 1:
        → 情况 C（era 跨大运）→ era 背景在第一个大运里写一段大的
    elif len(overlap_dayuns) == 2:
        → 情况 B（大运跨 era）→ 大运分两段写，加"时代切换感受"段
```

LLM 应在内部 reasoning 中**显式标注**每个 era_window 的对齐情况。

## 4. Step 3：内部生成 folkways 候选

针对每个 era_window，按以下 5 个维度内部生成 8-15 条候选条目（**全部内部 reasoning，先不输出**）：

| 维度 | 来源 | 数量目标 |
|---|---|---|
| 1. era_window.keywords 直接展开 | 骨架数据 | 3-5 条 |
| 2. era_window.global_keywords 展开 | 骨架数据 | 1-2 条（非中国用户可主导） |
| 3. 6 层 sub_layer 平均补充 | LLM 训练知识 | 每层 1-2 条 |
| 4. confirmed_facts 中相关条目 | 用户历次校验 | 0-N 条 |
| 5. folkways_examples 中相同 era 的条目 | few-shot 示例 | 0-N 条（参考其颗粒度） |

每条候选必须填写：

```yaml
- name: "{物件/事件名}"
  sub_layer: "{material|media|pop_culture|fads|communication|rituals}"
  time_window:
    first_appear: 1996
    peak: 1998
    declining: 2002
  region: "{tier1+tier2 | tier3+county | rural | global}"
  class_marker: "{urban_middle | urban_mass | ... | universal}"
  wuxing_tags: ["金", "火"]   # 按 folkways_protocol §5
  shishen_tags: ["食神"]
  confidence: "{high | mid | low}"
  associated_bazi_event: "{命理事件名 | null}"
  evidence_for_inference: "{为什么我（LLM）认为这条值得提}"
```

## 5. Step 4：三层过滤

### 5.1 第一层：confidence

```
filter:
  if confidence == "low": drop
  if confidence == "mid": only_use_as_secondary（备选形态 / 加条件）
  if confidence == "high": can_use_as_primary
```

### 5.2 第二层：五项自检（folkways_protocol §4）

LLM 内部对每条候选回答 5 个问题：

```
对每条 candidate：
  1. 时间窗清楚吗？（first_appear / peak / declining）
  2. 地域分布清楚吗？
  3. 阶级 marker 清楚吗？
  4. 五行 tag 清楚吗？
  5. 它对应命主的哪个命理事件？（或仅作时代背景？）

count_filled = 5 个问题中能答出的数量
if count_filled <= 3: drop
if count_filled == 4: 不能作"首选形态"，可作时代背景
if count_filled == 5: 可作"首选形态"
```

### 5.3 第三层：五行 / 阶级匹配

```
for each candidate that survives:
  # 五行匹配（提升优先级）
  if any(tag in [yongshen_wuxing] for tag in candidate.wuxing_tags):
    candidate.priority += 2   # 用神匹配，强相关
  if any(tag in [weakest_wuxing] for tag in candidate.wuxing_tags):
    candidate.priority += 1   # 短板补丁，相关
  
  # 阶级匹配
  if candidate.class_marker in class_prior.preferred_markers:
    candidate.priority += 2
  if candidate.class_marker in class_prior.disfavored_markers:
    candidate.priority -= 1   # 不一定 drop，可能转为"对照群体"

# 排序后取前 N 条
sorted_by_priority[:6-8]   # 每个 era_window 最终保留 6-8 条
```

## 6. Step 5：写区间叙事

严格按 `zeitgeist_protocol §3.1` 的标准结构。这里给一份**最小骨架模板**，照着填：

```markdown
## {era_window.label} · 你 {age_at_start}–{age_at_end} 岁 · {span[0]}–{span[1]}

### 时代底色
{1 句 headline，浓缩这段时代的核心张力}

{3-4 句背景描述。要有具体数字 / 具体事件 / 具体氛围，不要抽象口号。
 例如不要写"改革开放深入推进"，要写"国企改制进入收尾段，城市里
 大批 40-50 岁的工人面临单位关停 / 内退 / 买断工龄"}

这段时间里有几个标志性的细节，你大概率经历过：

- **{物件/事件 1}**（{时间窗}，{confidence: high/mid}）：{1 句具体描述，含时代位置}
- **{物件/事件 2}** ...
- ...（5-8 条，按 sub_layer 跨类覆盖至少 3 层）

### 命局给的几个具体节点

#### {年份 1}（{年龄}岁，{干支}，{大运}）· {命理事件名}
**命理读出**：{命局结构层面的解读}
**放在大背景里看**：
- **首选形态**（confidence: high）：{把命理事件 + folkways + 阶级 prior 联立后的具体显化}
- **备选形态 1**（confidence: mid）：{第二可能}
- **备选形态 2**（confidence: mid）：{第三可能}

#### {年份 2}（...）
...

#### {年份 N}（...）
（每个 era_window 内 2-4 个节点，跨度均匀，覆盖 ≥ 2 个维度）

### 这段区间的累计影响
{≥ 150 字。把命局结构 + 该区间所有命理节点 + 该区间集体情绪联立。
 必须包含：
 ① "你内化了什么底层叙事"
 ② "对比群体"（"没有 X 命局结构的同代人多半是 Y，你是 Z"）
 ③ 指向当下/未来的轻量延续（"这种底层叙事会在你 30+ 岁面对类似情境时被反复唤起"）}

### ⚠ 整段证伪点
如果你回忆这一整段（{span[0]}–{span[1]}）和上面描述的时代底色 / 命理节点
完全对不上，请告诉我——多半是命局的阶级 prior 或时辰判断有偏差，
需要重新校准。最关键的判别项是：{1-2 个最 high confidence 的具体细节}。
```

## 7. 写作风格约束

### 7.1 颗粒度

- 标志性细节：**具体物件/事件 + 时间窗 + 1 句描述**——不要抽象（"那时候大家都在 X"）
- 命理节点：**首选 + 备选**，不要 1 个（过拟合）也不要 5 个（稀释）
- 累计影响：**抽象但有方向**（"你内化了 X 底层叙事"）——这一段允许（且应该）抽象

### 7.2 语调

- 用第二人称"你"
- 描述事实/场景，不命名身份（详见 `class_inference_ethics.md`）
- 避免命理黑话堆砌，让外行也能看懂大致意思
- 可以适度抒情（"你大概率内化的是..."），但不能滑向算命口吻（"你注定..."）

### 7.3 诚实度

- 不熟悉的部分老老实实说不熟悉
- 标 confidence 是写给读者看的（high/mid 都要标）
- 备选形态用 "或者" / "也可能"，不要装作很确定

## 8. 防错速查

| 现象 | 原因 | 修复 |
|---|---|---|
| 用户回 "对不上" 一整段 | confidence 标过高 / 阶级 prior 错 | 整段标 mid，让用户提供 confirm 信号 |
| 民俗志条目和命主城市对不上 | 没用 region 过滤 | 加"如果你当时在 X 城市..."条件 |
| 命理节点写得太抽象 | 没把 folkways 联立进来 | 重写"放在大背景里看"段，给具体场景 |
| 阶级 label 出现在输出 | 没读 class_inference_ethics | 立即按 §3 替换字典改写 |
| 未来年份写了具体事件 | 没遵守"前事细 / 后事粗" | 改为"方向 + 大类 + 避坑" |
| 区间内 4 个节点都谈财富 | 没注意维度多样性 | 至少覆盖 2 个不同维度 |
| 过度使用 mangpai 经典组合名 | 把术语当文案 | 用大白话解释一遍 |

## 9. 完整推理示例（缩略版）

输入：1985 年生男性，命主走 1995-2002 期间的 era_window cn_reform_late_90s，class_prior = urban_state_or_educated。

**LLM 内部 reasoning**（不输出）：

```
1. 对齐：用户庚辰大运 1993-2002 与 cn_reform_late_90s [1995, 2002] 重合度 80% → 情况 A 共振
2. folkways 候选生成（12 条）：
   - VCD 入户（高峰 1998，urban+county，火金，high）
   - BP 机/小灵通（1996-2000，urban_middle，金水，mid）
   - 学计算机热（1998-2002，全国，金水，high）
   - 学英语热（1995-2000，全国，木火，high）
   - 还珠格格（1998-1999，全国，火，high）
   - 香港回归（1997，全国，火金，high）
   - 朱镕基 + 国企下岗（1995-1998，全国但 city 重，金土，high）
   - 亚洲金融危机（1997-1998，全球但中国感受弱，金水，mid）
   - 南方周末 / 三联 / 萌芽（urban_educated，木水，high）
   - QQ 兴起（1999-2002，urban_youth，水火，mid）
   - 房改（1998-2000，urban，土，high）
   - 申奥成功（2001，全国，火，high）
3. 三层过滤后保留 7 条（drop 亚洲金融危机 / QQ 偏后 / BP 机 mid）
4. 五行 / 阶级匹配（命主 yongshen=金，class_prior=urban_state_or_educated）：
   - 学计算机（金水）+ 学英语（木火）+ VCD（火金）→ 高优先级
   - 香港回归 / 还珠格格 / 申奥 → 全民共同记忆，作时代底色
   - 朱镕基国企下岗 → urban_state_or_educated 家庭可能直接被影响 → 作命理节点的"首选形态"
5. 命理节点选择：1996（11岁）丙子年伤官见印 + 1998（13岁）戊寅年财库被冲 + 2001（16岁）辛巳年起 → 选 3 个
```

**LLM 输出**（按 §6 模板）：

```markdown
## 国企改制 + 入世前夜 · 你 11–17 岁 · 1995–2002

### 时代底色
这是中国 90 年代最有"真实分裂感"的一段——同一座城市里，有人下岗
排队领买断金，有人开始搞股票/电脑培训班，有人收到了第一个 BP 机。
1995-1998 是"紧"的尾段：国企改制收尾，亚洲金融风暴刮过香港和韩国，
普通家庭对"稳定"二字开始重新审视。1998 一场抗洪 + 朱镕基整顿，社会
情绪触底；之后的 4 年（98-02）是某种"换档"——房改、互联网、申奥、
入世前夜，都在这 4 年里铺垫好。

这段时间里有几个标志性的细节，你大概率经历过：

- **VCD 入户**（高峰 1998 ± 1，high）：那时候 21 寸彩电 + VCD 几乎是"
  小康家庭"的标配，看《泰坦尼克》《大话西游》都是从 VCD 开始的
- **学计算机热**（1998-2002 高峰，high）：少年宫 / 单位机房 / 第一批
  电脑培训班开始大量出现，家长会鼓励孩子学打字 / Logo / Windows 98
- **学英语热**（疯狂英语 / 新概念，1995-2000 高峰，high）：学校晨读、
  录音机、三个月速成班
- **还珠格格 / 大宅门 / F4**（1998-2000，high）：电视全民现象级，全国孩子
  的暑假被这些剧绑定
- **南方周末 / 萌芽 / 三联**（一直 high）：家里有读书人气质的家庭，每周或
  每月有固定订阅
- **香港回归 + 朱镕基整顿 + 98 抗洪**（1997-1998，high）：三件大事密集，
  全国情绪从紧张到悲壮再到团结
- **房改启动**（1998-2000，high）：国企单位的福利分房进入末尾段，"自己买
  房"开始作为一个新概念被讨论

### 命局给的几个具体节点

#### 1996 年（11 岁，丙子，庚辰大运）· 伤官配印
**命理读出**：丙子年伤官气重，但年柱印星护身，伤官泄秀有方向
**放在大背景里看**：
- **首选形态**（high）：这一年你在某项学习/才能上被外部看见过——
  最可能是学校竞赛 / 写作 / 演讲 / 计算机比赛，老师明确表扬过
- **备选形态 1**（mid）：家里给你买了一件让你"被同辈关注"的物件
  （新自行车 / 钢琴 / 电脑 / VCD 自带麦克风）
- **备选形态 2**（mid）：你在这一年第一次有"我能用某个工具/才华
  让别人注意到我"的实感

#### 1998 年（13 岁，戊寅，庚辰大运）· 财库被冲开 + 印星受冲
**命理读出**：戊寅年地支寅 → 冲申金（你的用神之一），印星受冲
意味着家庭支撑结构被外部摇动
**放在大背景里看**：
- **首选形态**（high，因 class_prior = urban_state_or_educated）：
  这一年你家最可能经历过一次明显的"单位变动"——父母中至少一方
  的工作环境发生了肉眼可见的调整（部门撤并 / 内退 / 转岗 / 减薪 /
  福利缩减）。这是 1998 整顿期国企家庭的典型震感
- **备选形态 1**（mid）：父母没动，但身边亲戚/邻居有动，你目睹了
  那种"稳定也会塌"的氛围
- **备选形态 2**（mid）：搬家 / 转学 / 学区变动等结构性扰动

#### 2001 年（16 岁，辛巳，辛巳大运起）· 大运换柱
**命理读出**：进入辛巳大运，金气接替，伤官 + 偏财格局开始浮现
**放在大背景里看**：
- **首选形态**（high）：这一年你内在第一次有了"我要走和父母不一样
  的路"的萌芽——可能是文理分科、第一次填志愿、或者第一次看到了
  一种"父母不熟悉的成功路径"（互联网创业 / 留学 / 自由职业）
- **备选形态**（mid）：家里气氛因申奥成功 + 入世通过有过一段轻松感

### 这段区间的累计影响
你在一个家庭和社会都在重新洗牌的时间窗里完成了童年到少年的转换。
命局的"印星护身"在这段时间起了关键作用——同样这段时代里，没有
印星护身的孩子很多人留下了长久的不安全感（"我家就是从那时候开始
走下坡路"），而你大概率内化的是"世界会变，但稳里能找到我自己的
路"的底层叙事。这段时期被你内化的另一个东西是"才华 + 工具 = 被
看见的通道"——和你同辈但没有印 + 食伤结构的人多半内化的是"必须
拼资源 / 拼关系"，你的内化是"我自己琢磨明白一个东西，就有人会注意
到我"。这种底层叙事会在你 30+ 岁面对职场转折 / 行业洗牌时被反复
唤起——你会比同辈更愿意"先躲进学习里再说"。

### ⚠ 整段证伪点
如果你回忆 1995-2002 整段，以下任意一项明显对不上 → 阶级 prior 错：
- 你家在 1998 ± 2 年**完全没有**任何单位变动 / 经济压力 / 父母焦虑
- 你**完全没接触过**电脑 / 英语速成班 / VCD 这一类"新工具"
告诉我哪一项对不上，我会重新校准。
```

## 10. 自检清单（写完后过一遍）

- [ ] 5 个推理步骤都跑了（对齐 → 候选 → 三层过滤 → 写）
- [ ] 区间叙事按 §6 完整模板写
- [ ] folkways 条目跨 sub_layer 至少 3 层
- [ ] 命理节点 2-4 个，跨度均匀
- [ ] 累计影响段 ≥ 150 字
- [ ] 整段证伪点写了
- [ ] 没出现 §5 红线关键词（class_inference_ethics）
- [ ] 未来年份没写具体事件
- [ ] confidence 都标了（每条 folkways + 每个首选/备选形态）
