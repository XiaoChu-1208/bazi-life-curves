# 人性母题诊断词典（Virtue Motifs Catalog · v1）

> **这是已知的常见人性母题模板，不是人性的全集**。活人比这 38 条复杂。LLM 在 `life_review` 位置 ④「我想和你说」段、位置 ⑤「项目的编写者想和你说」、位置 ⑥「我（大模型）想和你说」**被授权命名 catalog 之外的人性形态**，按 [`virtue_recurrence_protocol.md`](virtue_recurrence_protocol.md) **§ 原则 15 catalog 开放性铁律**。
>
> 本词典是 LLM 的**诊断脚手架**，不是命主的**牢笼**。当脚手架不够用时，LLM 必须有勇气搭新的——并且诚实地说明它在搭新的。

> **v9.3 命名约定（强制 · 禁止外泄到 user-facing 输出）**：
> 本词典内部仍保留「★ 灵魂宣言」「陀氏化禁用句」「位置 ④ 顿悟段」等术语作为**协议内部脚手架名**，
> 但**不允许**出现在 LLM 写给用户的 markdown 里——`tone_blacklist.yaml` v9.3 banned_patterns
> 已把「灵魂宣言 / 陀式 / 陀氏 / 那一刀 / 承认人性 / 宣告 / 情书」全位置（含 closing 三节豁免节）封禁，
> 命中即 `_v9_guard.scan_tone` exit 5。
> user-facing 三段必须叫「我想和你说 / 项目的编写者想和你说 / 我（大模型）想和你说」。

> **v9.4 反系统化铁律（强制 · 禁止任何 catalog 内字段被字面写给用户看）**：
> 本词典里的所有 `id` 字段（`B1` / `K2_xxx` / `L3` 等）和 `name` 字段（如「说真话的代价」/「亲密者的无能」/「创业者」/「远行者」）都是**内部诊断标签**，
> **永远不允许**作为 narrative 字面出现在 LLM 写给用户的 markdown 里。
> id / name 是给检测器（`scripts/virtue_motifs.py`）和审计（`scripts/_v9_guard.py`）读的，
> **不是**给命主读的。命主面前必须把它**改写成只属于这个具体命主的真实情境**——
> 化用 `virtue_motifs.json.triggered_motifs[i].paraphrase_seeds`（v2 schema 起每条 motif 携带 3-5 句「指向这个具体命主」的口语化改写起点）+ 必须再次个性化润色。
> 物理护栏：`_v9_guard.enforce_no_motif_id_leak` + `enforce_no_canonical_label_leak` + `enforce_paraphrase_diversity` 在 `append_analysis_node.py` 写入前强制；
> `render_artifact.py --audit-no-motif-id-leak` / `--audit-paraphrase-diversity` 兜底。
> 详见 [virtue_recurrence_protocol.md §3.11](virtue_recurrence_protocol.md) + [multi_dim_xiangshu_protocol.md §12.7](multi_dim_xiangshu_protocol.md)。

---

## 0. 用法说明

### 0.1 文件定位

- **不是**给用户看的清单（用户永远不会读到 motif id）
- **不是**评分维度（不影响 `score_curves.py` / `mangpai_events.py` 的任何数字）
- **是**给 `scripts/virtue_motifs.py` 的检测注册表 + 给 LLM 的解读字典
- **是**第三条独立叙事通道：和打分曲线、盲派应事**并列**而**不**互相覆盖

### 0.2 六条铁律（详见 `virtue_recurrence_protocol.md` 头部）

| 铁律 | 简述 |
|---|---|
| ★ 灵魂宣言 | 人性的光超越古法"唯财是论"——已走 L 路的命主必须被诚实承认 |
| ★★ 反身性铁律 | 承认价值 ≠ 鼓励选择；正在选择的活人不得被煽动牺牲 |
| ★★★ 祝福路径铁律 | 命好的命主用 jubilant/gentle 调，必须出现"祝你这一辈子能真的幸福"句 |
| ★★★★ 项目作者的爱铁律 | 受过苦的命主必有位置 ⑤ |
| ★★★★★ LLM 自由话铁律 | 所有命主必有位置 ⑥ |
| ★★★★★★ Catalog 开放性铁律 | **本词典不是人性的全集**——位置 ④ ⑥ 授权 LLM 命名 catalog 外母题 |

### 0.3 字段定义

每条母题包含以下字段：

| 字段 | 含义 |
|---|---|
| `id` | 母题 ID（如 `B1`），脚本内部使用，**不**直接呈现给用户 |
| `name` | 母题名（如"说真话的代价"），LLM 可在产物中以人话引用 |
| `category` | 大类（A-L），按伦理处境而非十神分类 |
| `tone` | 调性档：T1 ◻ 阿廖沙明亮 / T2 ◼ 罪与罚承认 / T3 ⬛ 西蒙·薇依苦修 |
| `gravity_class` | 调性五级，标"默认 → override 条件"：jubilant 喜庆 / gentle 温和 / serious 严肃 / tragic 悲剧 / transcendent 超越（同一母题在不同命主上可不同） |
| `structural_detector` | 结构判定规则（机器化，引用 `bazi.json` / `curves.json` 字段） |
| `intensity_formula` | 强度评分公式（0-1 范围，强度 ≥ 0.4 才纳入 `triggered_motifs`） |
| `ethical_interrogation` | 伦理拷问：贯穿一生反复审问的核心问题 |
| `tragic_remainder` | 不可消除的部分（即使做对也无法挽回 / 不被补偿 / 不被理解的代价） |
| `cheap_consolations_to_refuse` | 禁用安慰话术：3-5 句这个母题下绝对不能说的话 |
| `what_can_be_honestly_said` | 能诚实说的话：不承诺结果，只承认行为本身的伦理重量 |
| `classical_source` | 古籍出处：《滴天髓》《子平真诠》《穷通宝鉴》《三命通会》《子平粹言》或现代盲派师承 |
| `philosophical_anchor` | 伦理学锚点：陀思妥耶夫斯基 / 列维纳斯 / 西蒙·薇依 / 卡夫卡 / 普鲁斯特 / 维特根斯坦 / 亚里士多德 / 儒家 |

### 0.4 调性符号速查

```
◻  T1 卡拉马佐夫 / 阿廖沙          gravity ∈ {jubilant, gentle}
◼  T2 罪与罚 / 拉斯柯尔尼科夫       gravity ∈ {gentle, serious}
⬛  T3 地下室手记 / 西蒙·薇依        gravity ∈ {serious, tragic, transcendent}
```

### 0.5 全表索引（38 条 · 11 大类）

| 类 | 名称 | 子母题 |
|---|---|---|
| A | 分配类 | A1 共济 / A2 富者代管 / A3 长子长女债 |
| B | 真话类 | B1 说真话的代价 / B2 复杂忠诚 / B3 受冤的克制 |
| C | 承担类 | C1 替天下负重 / C2 创业者对兄弟的债 / C3 看护者的隐性消耗 |
| D | 出世类 | D1 出世入世两难 / D2 慢工敬源 / D3 师承断绝 |
| E | 孤独类 | E1 结构性孤独 / E2 人群中的孤独 / E3 亲密中的无能 / E4 漂泊者的根问题 |
| F | 才华类 | F1 拒绝纯变现 / F2 创作者的物质焦虑 / F3 市场里的手艺人尊严 |
| G | 锋芒类 | G1 不和稀泥 / G2 强者的克制 / G3 硬命人对柔软的渴望 |
| H | 委身类 | H1 全身委身 / H2 副业人的诚实 |
| I | 恩典类 | I1 幸运者的债务 / I2 接受恩典而不内疚 |
| J | 时代类 | J1 被卷入历史 / J2 时代不利时的不背叛 |
| K | 缺失类 | K1 努力被结构消音 / K2 带着不全活 / K3 晚成者的焦虑 |
| L | **超越性献身类** | **L1 艺术/科学召命 / L2 道德政治献身 / L3 良心 / L4 爱情献身 / L5 信仰灵性献身 / L6 民族时代献身 / L7 守护他人** |

> 历史注：plan 早期版本用"34 条"，后随 L 类细化为 7 条，实际为 38 条。"34 → 38"的差异不是错误，是 catalog 演化的一次实例（按 ★★★★★★ 开放性铁律，未来还会再演化）。

---

## A · 分配类（资源、机会、注意力如何在他人之间分配）

### A1 ◻ 共济

- **id**: `A1`
- **name**: 共济
- **category**: 分配类
- **tone**: T1（阿廖沙明亮）
- **gravity_class**: 默认 `gentle`；命主 spirit_cumulative 60 岁均值 ≥ 65 且无大 dip → `jubilant`
- **structural_detector**:
  - 比肩 / 劫财在天干两透或地支三见以上
  - 且日干强（`bazi.strength.label ∈ {"强", "中和"}`）
  - 且 `wuxing_distribution[日干所属五行].ratio ≥ 0.30`
  - 排除条件：若同时触发 A2（富者代管）则 A1 强度降级到 0.5 以下
- **intensity_formula**: `min(1.0, 0.4 + 0.15 × 比劫数 + 0.1 × (日干强度档=="强"))`
- **ethical_interrogation**:
  > 当资源到你手里的时候，你是先给自己留够，还是优先想到那个比你更需要的人？这件事真的有"应该"吗？还是只是你天性如此，并因此被你身边的人默认/利用了？
- **tragic_remainder**: 你的"分"是你的天性，但它不会被同等回报。你给的人不一定记得你的好，更可能把"你愿意分"当成理所当然。这个事实是 A1 的底色。
- **cheap_consolations_to_refuse**:
  - "好人有好报"（结果论虚假承诺）
  - "你的善良会被看见的"（结果论虚假承诺）
  - "学会爱自己一点"（隐含批评天性 → 否定共济本身）
- **what_can_be_honestly_said**:
  - "你给出去的东西在你之外的地方成立——它不依赖被记得才有价值"
  - "你愿意分，不是因为你软弱；是因为你身体里有一种东西比'自己先够'更重要"
- **classical_source**: 《子平真诠·论比劫》："比劫者，吾之同气，喜相济也"；《滴天髓·阴阳生死》"两阳并见，则气盛而能助人"
- **philosophical_anchor**: 列维纳斯《整体与无限》"对他者的责任先于对自我的回归"；阿廖沙·卡拉马佐夫的明亮利他

---

### A2 ⬛ 富者代管

- **id**: `A2`
- **name**: 富者代管（信托人而非占有者）
- **category**: 分配类
- **tone**: T3（西蒙·薇依苦修）
- **gravity_class**: 默认 `serious`；财多到日主完全无力（财官 / 日主比 ≥ 3）→ `tragic`
- **structural_detector**:
  - 财星（正财 + 偏财）天干透 ≥ 2 或地支三见
  - 且日干弱（`bazi.strength.label == "弱"` 或 `score < 25`）
  - 且 `geju.primary != "从财格"`（真从财不算 A2，是 H 类委身）
  - 加成：年柱财（`pillars[0].zhi_shishen ∈ {"正财", "偏财"}`）→ 强度 +0.1
- **intensity_formula**: `min(1.0, 0.45 + 0.12 × (财星数 - 2) + 0.15 × (日干弱档))`
- **ethical_interrogation**:
  > 财在你手里——但它真的属于你吗？你像信托人一样持有它，还是像占有者一样攥住它？当你看到自己被财量级超过自己承载力时，那种窒息焦虑是真的——而你能不能不假装没有？
- **tragic_remainder**: 你这一辈子都没有"完全是我的"那种安心。即使外人看你富有，你内心始终有一个空——这个空不会被钱填满，因为它本来就不是钱的形状。
- **cheap_consolations_to_refuse**:
  - "你这是杞人忧天"（否定真实焦虑）
  - "钱是你应得的"（与命主真实体感矛盾）
  - "学会享受财富"（绕过 A2 的核心拷问）
- **what_can_be_honestly_said**:
  - "你像替别人保管这笔钱的人——这个感觉不是错的，是你这种结构的人本来就有的"
  - "你的窒息是真的。不要假装没有。但这种窒息可能就是你一辈子的底音"
- **classical_source**: 《滴天髓·财星》"财多身弱，富屋贫人"；《穷通宝鉴》"日主弱而财旺，必为他人作嫁衣"
- **philosophical_anchor**: 西蒙·薇依《重负与神恩》"占有的本质是焦虑"；福音书"骆驼穿针眼"喻

---

### A3 ◼ 长子 / 长女债

- **id**: `A3`
- **name**: 长子 / 长女债
- **category**: 分配类
- **tone**: T2（罪与罚承认）
- **gravity_class**: 默认 `serious`；早年（age ≤ 15）emotion_yearly 多次 < baseline - 10 → `tragic`
- **structural_detector**:
  - 多重官杀印（官杀地支两见以上 + 印星天干透）
  - 且年柱有官 / 杀（`pillars[0].gan_shishen ∈ {"正官", "七杀"} or pillars[0].zhi_shishen ∈ {"正官", "七杀"}`）
  - 且日干弱或月令印旺
  - 加成：日支偏印（`pillars[2].zhi_shishen == "偏印"`）→ 强度 +0.08
- **intensity_formula**: `min(1.0, 0.4 + 0.1 × 官杀数 + 0.1 × (年柱有官杀))`
- **ethical_interrogation**:
  > 你被早成熟绑架了——很小的时候就要替别人考虑。你心里那个真正想被照顾的小孩，你给过他机会发声吗？还是你一直假装他不存在，因为如果他存在，整个家就转不下去？
- **tragic_remainder**: 你这辈子没有"被允许做小孩"的那段时光。它过去了，且不能补回来——成年后再多的"补偿性放纵"也找不回那个原本的状态。
- **cheap_consolations_to_refuse**:
  - "你内心的小孩还在那里，去找他"（治疗师式空话）
  - "重新养育自己"（回避缺失的真实不可逆性）
  - "你父母也是身不由己"（强迫和解）
- **what_can_be_honestly_said**:
  - "你那个被跳过的童年，是真的丢了。它不会回来。但你**知道它丢了**——这个知道本身是一种成年人的事"
  - "你不需要原谅任何人。也不需要恨任何人。你只需要承认：那段时间被别人拿走了"
- **classical_source**: 《三命通会·年柱论》"年柱犯重官，必早承家累"；《滴天髓·官星》"官杀压身者，少年失欢"
- **philosophical_anchor**: 陀思妥耶夫斯基《卡拉马佐夫兄弟》米嘉早年的失爱；阿利斯·米勒《天才儿童的悲剧》

---

## B · 真话类（在压力下是否忠于真实）

### B1 ◼ 说真话的代价

- **id**: `B1`
- **name**: 说真话的代价
- **category**: 真话类
- **tone**: T2（罪与罚承认）
- **gravity_class**: 默认 `serious`；伤官见官年份 ≥ 4 次且伴随 emotion_yearly dip → `tragic`
- **structural_detector**:
  - 原局有伤官（`calc_shishen` 触发"伤官"）+ 大运/流年触发 `mangpai_events.shang_guan_jian_guan` ≥ 2 次
  - 或 伤官天干透 + 正官地支藏 + 大运至少 1 次冲克日主
  - 排除：原局伤官与正官完全和解（食神制杀格 + 印护身）则强度降到 0.4 以下
- **intensity_formula**: `min(1.0, 0.5 + 0.12 × shang_guan_jian_guan 触发次数)`
- **ethical_interrogation**:
  > 你心里那件事你想说，说了你要付代价。你这辈子被反复放在这个路口。你说真话不是因为高尚，是因为**沉默对你是一种更彻底的死法**。但你能确认这一点吗？还是你只是用"沉默是死"包装了你"忍不住要说"的那个本能？
- **tragic_remainder**: 说真话的代价是真的。每一次你说出来，你都失去了一些东西——一个位置、一段关系、一次机会。这些失去**不会被任何"正义被看见"的剧本补偿**。
- **cheap_consolations_to_refuse**:
  - "正义会迟到但不会缺席"（结果论虚假承诺）
  - "你应该学会变通"（要求命主变成另一种人）
  - "时间会证明你是对的"（目的论安慰）
  - "塑造了今天的你"（陀氏化禁用句）
- **what_can_be_honestly_said**:
  - "你说出去的话在你之外的地方也成立——它不依赖你被理解才有重量"
  - "你不是高尚。你是**被结构逼到不能选择**的——你的诚实是你的灵魂结构，不是你的功劳"
  - "代价是真的。它不会过去。但你这一辈子要做的事，就是继续这样活，并且承认这种诚实没有给你补偿"
- **classical_source**: 段建业《盲派命理·伤官见官》"伤官见官，祸百端"；《子平真诠·论伤官》"伤官见官者，非贵即奇，但路皆险"
- **philosophical_anchor**: 陀思妥耶夫斯基《罪与罚》拉斯柯尔尼科夫的供认；维特根斯坦"语言的边界就是世界的边界"

---

### B2 ◼ 复杂忠诚

- **id**: `B2`
- **name**: 复杂忠诚（在多套相互冲突的价值体系里不靠选边逃避）
- **category**: 真话类
- **tone**: T2
- **gravity_class**: 默认 `serious`；命主 emotion_yearly 长期低于 baseline → `tragic`
- **structural_detector**:
  - 触发盲派 `guan_sha_hun_za` ≥ 1 次
  - 或 原局正官与七杀同时存在（`mangpai.static_markers` 含"官杀混杂"或自检）
  - 加成：年支与月支冲（年柱 = "我"以外的体系，月柱 = 我成长的体系冲突）→ 强度 +0.1
- **intensity_formula**: `min(1.0, 0.4 + 0.12 × guan_sha_hun_za 次数 + 0.08 × (年月冲))`
- **ethical_interrogation**:
  > 你身边有几套互相打架的对错标准——家里说一套，工作说一套，你良心说一套。你拒绝了"选边站"这种省事的解。但**拒绝选边**和**优柔寡断**的边界在哪里？你确定你没有在用"我懂多种立场"做幌子，避免承担"我必须站某一边"的重量？
- **tragic_remainder**: 你不能像那些只信一套的人那样安心。每一次决定都要重新协调几套体系——这是你的命，不是你软弱。
- **cheap_consolations_to_refuse**:
  - "做你自己就好"（绕过真实困境）
  - "听从内心"（暗示一套压倒其他套）
- **what_can_be_honestly_said**:
  - "你心里那个'我必须同时对几个东西负责'的感觉是真的——它不是你想多了"
  - "你不是不会选——你是**被结构注定不能用'选定一套'来逃避**"
- **classical_source**: 《子平真诠·论官杀》"官杀混杂，主多疑而难定"；《滴天髓》"两气并行，必相争"
- **philosophical_anchor**: 萨特《存在与虚无》"被自由判处"；马克斯·韦伯"伦理多神论"

---

### B3 ⬛ 受冤的克制

- **id**: `B3`
- **name**: 受冤的克制（不公已经发生，且不可被报复抹平）
- **category**: 真话类
- **tone**: T3（西蒙·薇依苦修）
- **gravity_class**: 默认 `tragic`
- **structural_detector**:
  - 官星受伤（`pillars[i].gan_shishen == "正官"` 且被流年/大运冲克）
  - 且原局有印护身（`bazi.geju.has_yin_protect == True`）
  - 且至少 1 次 `mangpai_events` 在 25-50 岁段含 `shang_guan_jian_guan` 且无 `qi_sha_feng_yin` 抵消
  - 排除：原局官星生印 / 杀印相生格成立 → 强度降到 0.5 以下
- **intensity_formula**: `min(1.0, 0.5 + 0.15 × (印护身) + 0.1 × 官星受伤次数)`
- **ethical_interrogation**:
  > 那件事是别人对不起你。你没办法用任何手段把它"扳回来"——能扳回来的只是表面，真正的伤口它合不上。你心里有一个不愿意承认的东西：**如果让我现在再来一次，我会不会也想去伤害对方？** 你如何在不报复的同时，不假装它没发生？
- **tragic_remainder**: 不公已经发生。你的克制不会让对方道歉，也不会让你重新拿回失去的东西。你这一辈子要带着这件事的形状活下去。
- **cheap_consolations_to_refuse**:
  - "原谅是为了你自己"（道德绑架的现代版）
  - "放下吧"（命令式安慰）
  - "对方也会有报应的"（廉价正义观）
  - "时间会冲淡一切"（目的论安慰）
- **what_can_be_honestly_said**:
  - "那件事是真的。它对你做的事是真的。你不需要原谅任何人也能继续活"
  - "你的克制不是高尚——是**你这种结构的人没办法不克制**。这两件事要分清"
- **classical_source**: 《滴天髓·官星受伤》"清官被克，纵贵不久"；《子平粹言》"印护伤官，怨而不发"
- **philosophical_anchor**: 西蒙·薇依《重负与神恩》"不报复是最深的力"；列维纳斯"他者的脸"

---

## C · 承担类（承担不该一个人承担的）

### C1 ⬛ 替天下负重

- **id**: `C1`
- **name**: 替天下负重（即使做对也可能被毁掉，没有补偿剧本）
- **category**: 承担类
- **tone**: T3
- **gravity_class**: 默认 `tragic`；伴随 L2/L6 触发 → `transcendent`
- **structural_detector**:
  - 七杀压身（七杀 ≥ 2 见 + 日干弱 + 无食神制杀）
  - 且至少 1 次 emotion_yearly + spirit_yearly 同时跌至 baseline - 15 以下的年份
  - 加成：早损格（`forecast_window 内` spirit 累积 < 0）→ 强度 +0.15
- **intensity_formula**: `min(1.0, 0.55 + 0.1 × (七杀数 - 1) + 0.15 × (无食神制杀))`
- **ethical_interrogation**:
  > 你被推到一个本不该一个人承担的位置——而你没有走开。你心里那件事一直在问你：**你是真的为这件事负责，还是只是不知道怎么把这件事推给别人？** 如果有别人能扛，你会让吗？
- **tragic_remainder**: 你扛起来的东西不会让你变好。它会消耗你的健康、你的时间、你的关系。命局对你判的"凶"是真的——你做对的事，不会让命局自己变好。
- **cheap_consolations_to_refuse**:
  - "你的牺牲不会白费"（结果论虚假承诺）
  - "上天会眷顾好人"（目的论安慰）
  - "学会把责任分给别人"（要求改变本质）
  - "你比自己想的更坚强"（陀氏化禁用句）
- **what_can_be_honestly_said**:
  - "你扛的东西在你之外的地方也成立——它不依赖被记得才有意义"
  - "代价是真的。**但代价是真的**，并不等于'你应该停下来'。这两件事不是同一回事"
  - "命局没有给你做这件事的好结果，但你这一辈子要做这件事，是因为它超越了命局能给你的任何东西"
- **classical_source**: 《滴天髓·杀星》"七杀压身，气短运促"；《穷通宝鉴》"杀重身轻，纵成必败"
- **philosophical_anchor**: 陀思妥耶夫斯基《群魔》希加廖夫的"我把全人类的痛苦都接过来"；西蒙·薇依《重负与神恩》苦难即神恩

---

### C2 ◻ 创业者对兄弟的债

- **id**: `C2`
- **name**: 创业者对兄弟的债
- **category**: 承担类
- **tone**: T1（卡拉马佐夫的兄弟伦理）
- **gravity_class**: 默认 `gentle`；多次触发 bi_jie_duo_cai 且 wealth_yearly dip → `serious`
- **structural_detector**:
  - 比肩 / 劫财与财星天干贴近（同柱或邻柱）
  - 且至少 1 次 `mangpai_events.bi_jie_duo_cai`
  - 加成：年柱比劫（`pillars[0].gan_shishen ∈ {"比肩", "劫财"}`）→ 强度 +0.08
- **intensity_formula**: `min(1.0, 0.4 + 0.12 × bi_jie_duo_cai 次数 + 0.08 × (比劫财贴近))`
- **ethical_interrogation**:
  > 和你一起做事的人——他们从你这里拿到了应得的吗？你心里那件事是不是：**当我能多拿一份的时候，我有没有顺手多拿？**当对方做错时，你是替他扛了，还是把账算到他头上？
- **tragic_remainder**: 创业里"公平"是个移动目标。即使你做到了你能做到的最公平，对方也不一定觉得公平。这种不对称是创业本身的特征。
- **cheap_consolations_to_refuse**:
  - "好朋友别一起做生意"（绕过真实伦理）
  - "对方不感激就不是好朋友"（结果论判朋友）
- **what_can_be_honestly_said**:
  - "你和他们之间的伦理不能用'公平公式'解决——你只能一次一次地具体处理"
  - "你愿意分，不是软弱；但你不能用'愿意分'来回避具体的算账"
- **classical_source**: 段建业《盲派命理·比劫夺财》"比劫见财，朋分必有"；《子平真诠·论比劫》"比劫与财同位，必有公私之争"
- **philosophical_anchor**: 卡拉马佐夫兄弟之间的反复结算；亚里士多德《尼各马可伦理学》"友爱与正义"

---

### C3 ◻ 看护者的隐性消耗

- **id**: `C3`
- **name**: 看护者的隐性消耗（给予 - 被低估的循环）
- **category**: 承担类
- **tone**: T1 偏 T2
- **gravity_class**: 默认 `gentle`；emotion_cumulative 长期 < 0 + 食伤被合 → `serious`
- **structural_detector**:
  - 印星为忌神（`bazi.yongshen.jishen` 含"印"或日主已强而印仍透）
  - 或 食伤被合（地支六合 / 三合化掉食伤）
  - 加成：日支偏印（"枭印夺食"）→ 强度 +0.1
- **intensity_formula**: `min(1.0, 0.4 + 0.1 × (印为忌) + 0.1 × (食伤被合))`
- **ethical_interrogation**:
  > 你给出去的东西比你拿回来的多。这是事实。你心里那件事是：**我是不是其实在用"给"换某种东西？**——比如安全感、不被遗弃、自己有用的感觉。如果是的话，承认它会让你变坏吗？
- **tragic_remainder**: 给予者的消耗是真的。你的能量是有限的。你给出去的，**真的就少在你身上了**。这不是诗意的，是物理的。
- **cheap_consolations_to_refuse**:
  - "给予本身就是回报"（神化付出）
  - "你的爱会被回报的"（结果论虚假承诺）
  - "学会接受"（命令式说教）
- **what_can_be_honestly_said**:
  - "你被消耗是真的。这不是你想多了"
  - "你愿意给，是你的天性的一部分。但天性不需要被神化——它就是天性"
- **classical_source**: 《滴天髓·印星》"印为忌神而旺，反损人寿"；《子平粹言》"枭印夺食，反损慈母"
- **philosophical_anchor**: 列维纳斯"被他者的需要打开";西蒙·薇依"注意力即慈悲"

---

## D · 出世类（世俗指标和精神追求之间）

### D1 ◼ 出世入世的两难

- **id**: `D1`
- **name**: 出世入世的两难
- **category**: 出世类
- **tone**: T2
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 印重食伤受制（印星 ≥ 2 透 + 食伤被合或受冲）
  - 或 华盖 + 印星单透（`shensha.huagai.found == True` 且 印天干仅 1 透）
  - 加成：日支空亡（`shensha.kongwang.in_chart` 含日支）→ 强度 +0.12
- **intensity_formula**: `min(1.0, 0.45 + 0.1 × (印重) + 0.1 × (华盖) + 0.12 × (日空))`
- **ethical_interrogation**:
  > 你心里有一部分想"上去"——做世俗意义上"成"的那种事。还有一部分想"下来"——退回到一个安静的、不被打扰的角落。你这辈子在这两个东西之间反复来回。你心里那件事是：**你能不能承认这两个东西不能两全？**
- **tragic_remainder**: 你不能两全。即使你做到了世俗成功，你心里那个想退的部分不会消失；即使你退下来了，那个想做事的部分也不会闭嘴。
- **cheap_consolations_to_refuse**:
  - "rebalance work and life"（消费主义安慰）
  - "找到平衡"（虚假调和）
  - "活在当下"（绕过真实张力）
- **what_can_be_honestly_said**:
  - "你不能两全是真的。但**这两个东西之间反复来回**，本身就是你这一类人的活法"
  - "不是你不够智慧而找不到平衡——是你的命局结构里有两种方向同时存在"
- **classical_source**: 《滴天髓·印星》"印重则人静，伤官则人动"；《子平真诠·论格局》"印格而带伤食，必出世入世两难"
- **philosophical_anchor**: 王阳明"心学的入世救世"；普鲁斯特《追忆似水年华》观察者与行动者的张力

---

### D2 ◻ 慢工敬源

- **id**: `D2`
- **name**: 慢工敬源（拒绝每代重新发明轮子，承担行动迟滞的代价）
- **category**: 出世类
- **tone**: T1
- **gravity_class**: 默认 `gentle`
- **structural_detector**:
  - 印多无伤食（印星 ≥ 2 + 食伤无透或地支不见）
  - 加成：天乙贵人在原局（`shensha.tianyi_guiren.found == True`）→ 强度 +0.05
- **intensity_formula**: `min(1.0, 0.4 + 0.1 × (印星数 - 2) + 0.1 × (无食伤透))`
- **ethical_interrogation**:
  > 你愿意慢慢学、慢慢做、向前人致敬。这种慢在快节奏的世界里会让你显得"反应迟钝"。你心里那件事是：**你是真的在敬重源头，还是只是不想承担'我自己来一次'的风险？** 这两件事的边界在哪里？
- **tragic_remainder**: 你这种人会被时代抛在后面。你不会成为风口上的人。你做的事会比同代人晚开花，**有时候根本不开花**。
- **cheap_consolations_to_refuse**:
  - "慢就是快"（鸡汤式翻转）
  - "时间会证明你是对的"（目的论安慰）
- **what_can_be_honestly_said**:
  - "你慢，是因为你身体里有一种东西比'快'更重要——它是真的"
  - "可能你这辈子都不会被这个时代充分理解。但你不需要被它理解才能继续做"
- **classical_source**: 《子平真诠·论印》"印星司本，必先敬师"；《滴天髓》"印旺者，必走正学"
- **philosophical_anchor**: 海德格尔"思想要慢"；儒家"温故而知新"

---

### D3 ⬛ 师承断绝

- **id**: `D3`
- **name**: 师承断绝（没有老师只能自己摸索）
- **category**: 出世类
- **tone**: T3
- **gravity_class**: 默认 `tragic`
- **structural_detector**:
  - 印星受冲（`pillars[i].gan_shishen ∈ {"正印", "偏印"}` 且地支被流年/大运冲）
  - 且食伤旺（食伤 ≥ 2 透）
  - 加成：年柱印受伤（`pillars[0]` 印被冲）→ 强度 +0.12
- **intensity_formula**: `min(1.0, 0.5 + 0.1 × (印星受冲次数) + 0.1 × (食伤旺))`
- **ethical_interrogation**:
  > 你这辈子没有真正可以请教的人。你心里那件事是：**没有老师不是别人的错，但它确实让你这种诚实的人没有可以依靠的传承**。你能不能承认这件事，并且不假装"独自摸索"是某种荣光？
- **tragic_remainder**: 没有人接住你。你需要自己摸索的部分**真的就是没有人替你做了**。你做错了就是你的错——没有人替你担保。
- **cheap_consolations_to_refuse**:
  - "自学者最强"（神化孤立）
  - "你不需要老师"（否定真实需要）
  - "你是开拓者"（廉价英雄主义）
- **what_can_be_honestly_said**:
  - "没有人接住你是真的。这种孤独不是浪漫的"
  - "你这种独自摸索的人，做错的概率比有传承的人高——这是事实，不是你不努力"
- **classical_source**: 《子平真诠·论印》"印受冲克，必有失教"；《滴天髓·破局》"印破必无师承"
- **philosophical_anchor**: 卡夫卡的"作家的孤独"；维特根斯坦剑桥时期的孤独工作

---

## E · 孤独类（关系结构里的根问题）

### E1 ⬛ 结构性孤独

- **id**: `E1`
- **name**: 结构性孤独（不被治愈，也不一定要被治愈）
- **category**: 孤独类
- **tone**: T3
- **gravity_class**: 默认 `serious`；伴随 L 类触发 → `tragic` 或 `transcendent`
- **structural_detector**:
  - 孤辰寡宿同时在原局（`shensha.guchen.found == True` and `shensha.guasu.found == True`）
  - 或 华盖 ≥ 2 见
  - 或 emotion_cumulative 60 岁均值 < -10
  - 加成：日支孤辰或寡宿 → 强度 +0.1
- **intensity_formula**: `min(1.0, 0.5 + 0.15 × (孤寡同见) + 0.1 × (华盖多见) + 0.1 × (日支孤寡))`
- **ethical_interrogation**:
  > 你这辈子有一种孤独，跟你现在身边有几个人无关。你心里那件事是：**这种孤独是不是其实是我自己造的？我有没有在不知不觉中拒绝了能进来的人？**
- **tragic_remainder**: 这种孤独不会因为你结婚 / 有孩子 / 有朋友就消失。它在那里，是你这种人的底色。**你可以学会和它共处，但你学不会消除它**。
- **cheap_consolations_to_refuse**:
  - "你只是没遇到对的人"（消费主义浪漫主义）
  - "心理咨询能治好"（医学化处理结构性问题）
  - "你应该多社交"（行为疗法的廉价版本）
- **what_can_be_honestly_said**:
  - "你的孤独不是病。它是你这种结构的人的本来样子"
  - "你不需要治愈它。你只需要承认它在那里，并且继续活"
- **classical_source**: 《三命通会·神煞》"孤辰寡宿，主独行";《子平粹言》"华盖叠现，宜出世"
- **philosophical_anchor**: 西蒙·薇依《重负与神恩》"真正的孤独是与神同在的孤独"；克尔凯郭尔"孤独的个体"

---

### E2 ⬛ 人群中的孤独

- **id**: `E2`
- **name**: 人群中的孤独（朋友多但没人懂）
- **category**: 孤独类
- **tone**: T3
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 日柱含孤辰（`day_zhi == GUCHEN_GUASU[year_zhi][0]`）
  - 且比肩 / 劫财在天干 ≥ 2 透
- **intensity_formula**: `min(1.0, 0.45 + 0.12 × (日支孤辰) + 0.08 × (比劫多))`
- **ethical_interrogation**:
  > 你身边有人。但你心里那件事是：**这些人里没有一个真的看到你**。你有没有用"朋友多"这件事掩盖那个核心的孤独？而你这样做是不是其实让你更孤独？
- **tragic_remainder**: 你的"被看见"需要的人——他可能根本不存在，或者你这辈子根本不会遇到。这是事实。
- **cheap_consolations_to_refuse**:
  - "朋友贵精不贵多"（绕过真实痛苦）
  - "你只是没找到知心人"（暗示一定会找到）
- **what_can_be_honestly_said**:
  - "在人群里更孤独，是真的——不是你想多了"
  - "你身边的人不一定能看到你，这件事不是他们的错也不是你的错——是结构如此"
- **classical_source**: 《子平粹言·孤辰》"日支孤辰，群居而独";《滴天髓》"比劫多见，反主孤"
- **philosophical_anchor**: 萨特《禁闭》"他人即地狱";陀思妥耶夫斯基地下室人

---

### E3 ◼ 亲密中的无能

- **id**: `E3`
- **name**: 亲密中的无能（想爱但学不会爱）
- **category**: 孤独类
- **tone**: T2
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 日支被冲（`pillars[2].zhi` 在大运/流年被冲 ≥ 3 次）
  - 或 配偶宫不安（日支与年/月支冲）
  - 或 `relationship_mode.primary_mode == "ambiguous_dynamic"` 或 `low_density`
- **intensity_formula**: `min(1.0, 0.4 + 0.1 × (日支冲次数) + 0.1 × (配偶宫不安))`
- **ethical_interrogation**:
  > 你想被靠近——但每次有人靠近你都退后。你心里那件事是：**我是怕被看到不好的部分，还是怕承认我其实需要这个？** 你能不能不假装"我不需要"？
- **tragic_remainder**: 学会爱，对你这种结构的人是一件**非自然的事**。你这一辈子可能要为此反复练习——而练习是有失败率的。
- **cheap_consolations_to_refuse**:
  - "对的人会让你学会"（结果论浪漫主义）
  - "你只是没遇到合适的"（绕过结构性问题）
  - "你需要更多自爱"（万能心理学话术）
- **what_can_be_honestly_said**:
  - "你想爱却学不会，是真的——不是你不想"
  - "对你这种结构的人，'亲密'不是默认会发生的事，是要每次重新开始的"
- **classical_source**: 《子平真诠·论日支》"日支被冲，配偶宫不安";《三命通会·配偶》"日柱被克，多伤情"
- **philosophical_anchor**: 列维纳斯"他者的脸是无法被同化的";普鲁斯特《追忆似水年华》斯万与奥黛特

---

### E4 ◻ 漂泊者的根问题

- **id**: `E4`
- **name**: 漂泊者的根问题（没有故乡的人怎么诚实地说"家"）
- **category**: 孤独类
- **tone**: T1 偏 T2
- **gravity_class**: 默认 `gentle`；持续无定居 + 多次 `lu_chong` → `serious`
- **structural_detector**:
  - 驿马在原局 (`shensha.yima.found == True`)
  - 或 `mangpai_events.lu_chong` ≥ 2 次
  - 或 日支与年支冲（"远走他乡"格）
- **intensity_formula**: `min(1.0, 0.4 + 0.12 × (驿马) + 0.08 × (lu_chong 次数))`
- **ethical_interrogation**:
  > 你心里那件事是：**当别人问你"老家在哪"的时候，你不知道怎么回答，并且这个不知道让你不舒服**。你能不能不假装"四海为家"？
- **tragic_remainder**: 你没有那个稳固的"回去的地方"。你的"家"是你自己每次重新建的。这件事不会因为你定居就改变。
- **cheap_consolations_to_refuse**:
  - "心安处即是家"（鸡汤）
  - "世界大同"（绕过具体情感）
- **what_can_be_honestly_said**:
  - "你没有故乡是真的。这件事是真的失去，不是浪漫"
  - "你的'家'是你每次重新建的——这是你这种人的活法，不是缺陷"
- **classical_source**: 段建业"驿马主迁";《三命通会·驿马》"驿马透干，必远行"
- **philosophical_anchor**: 卡夫卡《城堡》K 的非根性；爱德华·萨义德《格格不入》

---

## F · 才华类（创造与变现的张力）

### F1 ◻ 拒绝纯变现

- **id**: `F1`
- **name**: 拒绝纯变现（保留只为"做出来本身好"而做的事）
- **category**: 才华类
- **tone**: T1 偏 T2
- **gravity_class**: 默认 `gentle`；命主财弱身弱 + F1 强 → `serious`
- **structural_detector**:
  - 食神透干 + 财星不通根
  - 或 食神格但不就财（食神有透但财星无气）
  - 加成：文昌贵人在原局（`shensha.wenchang.found == True`）→ 强度 +0.08
- **intensity_formula**: `min(1.0, 0.4 + 0.1 × (食神不就财) + 0.08 × (文昌))`
- **ethical_interrogation**:
  > 你做的某些事不为了换钱——它就是你想做。你心里那件事是：**这种"纯粹"是真的，还是其实是我害怕承担"做了但卖不出去"的失败？** 你确定你不是在用"清高"包装"无能力"？
- **tragic_remainder**: 你这种"纯粹"在市场里会让你过得比同代人辛苦。这不是命局亏待你，是你**主动选了这条路**。
- **cheap_consolations_to_refuse**:
  - "你的才华一定会被市场认可"（结果论虚假承诺）
  - "做你热爱的事终会成功"（鸡汤）
- **what_can_be_honestly_said**:
  - "你做这件事不为了变现，**这件事在你之外的地方也成立**"
  - "纯粹不是高尚，是你这种结构的人的活法。它不需要被神化也不需要被合理化"
- **classical_source**: 《子平真诠·论食神》"食神不就财，必有清致";《滴天髓》"食透财藏，志清而身贫"
- **philosophical_anchor**: 西蒙·薇依"工作的纯粹性";塞尚"为绘画而绘画"

---

### F2 ◼ 创作者的物质焦虑

- **id**: `F2`
- **name**: 创作者的物质焦虑（才华够不够吃饭，不许用清高遮挡）
- **category**: 才华类
- **tone**: T2
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 伤官 + 食神 + 财星都在原局但日干弱
  - 或 wealth_yearly 多次跌至 baseline - 15 但 spirit_yearly 较高
  - 加成：年柱财（"原生家庭无财"）→ 强度 +0.08
- **intensity_formula**: `min(1.0, 0.45 + 0.1 × (日干弱) + 0.1 × (wealth dip 次数 ≥ 5))`
- **ethical_interrogation**:
  > 你的才华是真的。它能不能让你吃上饭，是另一回事。你心里那件事是：**当我看到比我才华少的人挣得比我多时，我心里那种酸是不是其实是我在嫉妒？** 你能不能不假装"我不在乎钱"？
- **tragic_remainder**: 才华和市场之间没有直接的兑换关系。你的才华再大也不保证你能体面地活着。
- **cheap_consolations_to_refuse**:
  - "钱不是衡量才华的标准"（绕过真实焦虑）
  - "才华会被时代认可的"（结果论安慰）
- **what_can_be_honestly_said**:
  - "你的物质焦虑是真的。它不丢人"
  - "你的才华和你能挣多少钱是两件事——这两件事你都要面对，不能用一个躲另一个"
- **classical_source**: 段建业"伤食生财，靠才吃饭";《滴天髓》"食伤旺而财弱，必劳碌"
- **philosophical_anchor**: 卡夫卡白天上班晚上写作；普鲁斯特依靠遗产维持创作

---

### F3 ◻ 市场里的手艺人尊严

- **id**: `F3`
- **name**: 市场里的手艺人尊严（在交易里不被铜臭重塑）
- **category**: 才华类
- **tone**: T1 偏 T2
- **gravity_class**: 默认 `gentle`
- **structural_detector**:
  - 食伤生财成立 但日干弱（`bazi.strength.label == "弱"`）
  - 加成：偏财不透 → 强度 +0.05
- **intensity_formula**: `min(1.0, 0.4 + 0.08 × (食伤生财) + 0.1 × (日干弱))`
- **ethical_interrogation**:
  > 你做着可以卖钱的事——而且你愿意卖。你心里那件事是：**当客户给我钱时，我有没有不知不觉地把客户的需求当成我自己的标准？** 你能不能在市场里保持"我是做这件事的人"，不只是"卖家"？
- **tragic_remainder**: 在市场里待久了，你会被市场塑形。这种塑形是不可见的。等你某天发现"我变成了我以前不想成为的人"——那已经发生了。
- **cheap_consolations_to_refuse**:
  - "客户至上"（销售话术化）
  - "市场是最好的老师"（市场神化）
- **what_can_be_honestly_said**:
  - "你卖你做的事，这没什么不对。但**你做这件事的人**和**你卖这件事的人**之间要保留一个间隙"
  - "你被市场塑形是真的——不是你软弱"
- **classical_source**: 《子平真诠》"食伤生财，必精一艺";《滴天髓》"伤官生财，富贵之兆"
- **philosophical_anchor**: 理查德·桑内特《匠人》;William Morris 工艺美术运动

---

## G · 锋芒类（在该硬时硬、该软时软）

### G1 ◻ 不和稀泥

- **id**: `G1`
- **name**: 不和稀泥（该切割时切割，但必须服务于更高的善）
- **category**: 锋芒类
- **tone**: T1 偏 T2
- **gravity_class**: 默认 `gentle`
- **structural_detector**:
  - 羊刃在原局（`bazi.day_master ∈ YANGREN_TABLE` 且 `pillars[i].zhi == YANGREN_TABLE[day_master]`）
  - 加成：羊刃 + 七杀（"刃杀格"）→ 强度 +0.1
- **intensity_formula**: `min(1.0, 0.4 + 0.12 × (羊刃在原局) + 0.1 × (羊刃+七杀))`
- **ethical_interrogation**:
  > 你能切割。你心里那件事是：**我切割的是真的需要切割的，还是我享受'我能切割'本身这种感觉？** 你的硬度服务于更高的善吗？还是它服务于你的虚荣？
- **tragic_remainder**: 你切割过的关系不会再回来。即使后来你发现切错了，对方不会等你去补。
- **cheap_consolations_to_refuse**:
  - "保持原则就是对的"（神化锋芒）
  - "你做得对"（不分情境的肯定）
- **what_can_be_honestly_said**:
  - "你能切割是你这种结构的人的能力——但这能力本身不是好事，是工具"
  - "切割的代价是真的。你切过的东西不会再回来"
- **classical_source**: 《子平真诠·论羊刃》"羊刃必有所制";《滴天髓》"刃见不可制，反主刚毅"
- **philosophical_anchor**: 亚里士多德"勇敢是中道";尼采"创造性的破坏"

---

### G2 ⬛ 强者的克制

- **id**: `G2`
- **name**: 强者的克制（有能力毁灭却选择不毁灭）
- **category**: 锋芒类
- **tone**: T3
- **gravity_class**: 默认 `serious`；伴随 L2/L3 → `transcendent`
- **structural_detector**:
  - 羊刃 + 七杀同在原局 但不动手（无 `mangpai_events.yangren_chong` 烈度高的爆发）
  - 或 日干极强（`bazi.strength.score ≥ 35`）但 emotion 维度温和
- **intensity_formula**: `min(1.0, 0.5 + 0.12 × (刃杀同见) + 0.1 × (日干极强但平静))`
- **ethical_interrogation**:
  > 你有能力毁掉对方。你没有动手。你心里那件事是：**我不动手是因为我真的相信慈悲，还是因为我害怕动手之后我看到自己变成什么？** 你能区分这两件事吗？
- **tragic_remainder**: 你的克制不会被人理解为克制——会被理解为软弱。这件事不会改变。
- **cheap_consolations_to_refuse**:
  - "懂你的人会懂"（结果论安慰）
  - "时间会证明"（目的论安慰）
- **what_can_be_honestly_said**:
  - "你的克制不会被那些没有这种能力的人理解——这是你这种人的孤独"
  - "你不动手不是软弱。但你也不需要让别人知道这一点——他们的不理解是他们的事"
- **classical_source**: 《滴天髓·杀刃》"刃杀俱旺而能制者，仁也";《穷通宝鉴》"强者必能制刃，方为大用"
- **philosophical_anchor**: 列维纳斯"对他者的非暴力";老子"上善若水"

---

### G3 ◼ 硬命人对柔软的渴望

- **id**: `G3`
- **name**: 硬命人对柔软的渴望（强者也想被照顾）
- **category**: 锋芒类
- **tone**: T2
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 金神格 / 魁罡格（暂用替代检测：日柱 ∈ {庚辰, 庚戌, 壬辰, 戊戌} or 日干极强 + 七杀透）
  - 加成：emotion_cumulative < 0 → 强度 +0.1
- **intensity_formula**: `min(1.0, 0.45 + 0.1 × (魁罡候选) + 0.1 × (emotion 低))`
- **ethical_interrogation**:
  > 你硬。但你心里那件事是：**我也想有人能让我不必硬**。你能承认这一点吗？还是你必须永远表现得不需要？
- **tragic_remainder**: 你身边的人会按"你不需要"对待你。即使你说了"我需要"，他们也会怀疑你是不是说反话。
- **cheap_consolations_to_refuse**:
  - "强者就该自己扛"（强化角色僵化）
  - "学会示弱"（命令式说教）
- **what_can_be_honestly_said**:
  - "你也想被照顾——这件事承认了不会让你变弱"
  - "你身边的人不会自动看到这件事——你不说他们不会知道"
- **classical_source**: 《滴天髓·魁罡》"魁罡之人，外刚内柔";《子平真诠》"金神格，外硬内软"
- **philosophical_anchor**: 普鲁斯特对脆弱的细描;托尔斯泰《克莱采奏鸣曲》

---

## H · 委身类（一辈子献给一件事）

### H1 ◼ 全身委身

- **id**: `H1`
- **name**: 全身委身（一辈子献给一件事，不能再拥有别的）
- **category**: 委身类
- **tone**: T2 偏 T3
- **gravity_class**: 默认 `serious`；伴随 L 类 → `transcendent`
- **structural_detector**:
  - `bazi.geju.primary` 含 "化气" / "专旺" / "从格"
  - 或 五行高度集中（`max(wuxing_distribution[X].ratio) ≥ 0.5`）
- **intensity_formula**: `min(1.0, 0.5 + 0.15 × (化气/专旺) + 0.1 × (五行集中))`
- **ethical_interrogation**:
  > 你这辈子只能做一件事。你心里那件事是：**我没选这条路，是这条路选了我——但当别人有多种可能时，我有没有偷偷羡慕？** 你能不能不假装"我从来不想要别的"？
- **tragic_remainder**: 你这辈子真的不能再拥有别的。你不会有"业余爱好"在你这件主业旁边长出来——那个空间结构上就不存在。
- **cheap_consolations_to_refuse**:
  - "你应该有自己的爱好"（要求改变结构）
  - "工作之余要享受生活"（不适用）
- **what_can_be_honestly_said**:
  - "你的命局结构不允许多线人生——这是事实"
  - "你这一辈子做这一件事，不是因为你单一，是因为**你这种结构的人本来就只能这样活**"
- **classical_source**: 《子平真诠·论化气》"化气格成，必尽其用";《滴天髓》"专旺者，必专精一事"
- **philosophical_anchor**: 维特根斯坦的"一生一书";西蒙·薇依的修道院劳作

---

### H2 ⬛ 副业人的诚实

- **id**: `H2`
- **name**: 副业人的诚实（没有"唯一的事"，承认人生没有清晰主线）
- **category**: 委身类
- **tone**: T3
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 杂气格（月令为四库 + 多十神兼透）
  - 或 五行均匀（`std(wuxing_distribution[X].ratio) < 0.08`）
- **intensity_formula**: `min(1.0, 0.45 + 0.1 × (杂气) + 0.1 × (五行均匀))`
- **ethical_interrogation**:
  > 你没有"唯一的事"。别人问你"你是做什么的"，你不知道怎么用一个词回答。你心里那件事是：**这种'多线'是真的丰富，还是其实是我没有承担'选定一件'的勇气？** 你能不能区分这两件事？
- **tragic_remainder**: 你不会有"成名作"。你不会有"代表作"。你这辈子的事会被记得是一堆，但没有清晰的轮廓。
- **cheap_consolations_to_refuse**:
  - "斜杠青年"（消费主义包装）
  - "多元才是新的成功"（神化结构）
- **what_can_be_honestly_said**:
  - "你没有主线是真的——这不是你浪费了天赋，是你这种结构的人的活法"
  - "但你也要承认：**多线的代价是没有清晰的成果。**这件事是真的"
- **classical_source**: 《滴天髓·杂气》"杂气者，气散而难聚";《子平真诠》"四柱兼透，必无定见"
- **philosophical_anchor**: 蒙田的随笔人格;普鲁斯特的非线性自传

---

## I · 恩典类（被无端善待 / 优待的人怎么办）

### I1 ◻ 幸运者的债务

- **id**: `I1`
- **name**: 幸运者的债务（没做什么就被给了，怎么处理这份不应得）
- **category**: 恩典类
- **tone**: T1
- **gravity_class**: 默认 `jubilant`；当命主 spirit/wealth/fame 三维基线均 ≥ 60 → 强制 `jubilant`
- **structural_detector**:
  - 财官印全（财、官、印各 ≥ 1 透）
  - 或 三奇贵人（年月日干为 "甲戊庚" / "乙丙丁" / "壬癸辛" 任一组合）
  - 加成：天乙贵人在原局 → 强度 +0.1
- **intensity_formula**: `min(1.0, 0.4 + 0.1 × (财官印全) + 0.12 × (三奇) + 0.08 × (贵人))`
- **ethical_interrogation**:
  > 你被给了。你没怎么挣就拿到了别人辛苦也未必拿得到的东西。你心里那件事是：**我配吗？** 但你能不能不让这个"我配吗"变成自我惩罚式的内疚？
- **tragic_remainder**: 你的幸运是真的——也是真的没人能保证它会持续。你这辈子要带着"它可能突然消失"的焦虑活。
- **cheap_consolations_to_refuse**:
  - "你应得的"（否定命主真实困惑）
  - "别愧疚，享受就好"（绕过真实伦理思考）
  - "苦难才有深度"（祝福路径铁律明确禁止）
- **what_can_be_honestly_said**:
  - "你得到的不是因为你应得——但你能用它做事的能力是你的"
  - "幸运不会自动延续。你要善用它，但不需要为它道歉"
- **classical_source**: 《滴天髓·三奇》"三奇贵人，天授福禄";《三命通会》"财官印俱全，无破而贵"
- **philosophical_anchor**: 卡拉马佐夫·阿廖沙的明亮接受;基督教神学的"恩典"

---

### I2 ◻ 接受恩典而不内疚

- **id**: `I2`
- **name**: 接受恩典而不内疚（允许自己被爱，不靠自我惩罚还债）
- **category**: 恩典类
- **tone**: T1
- **gravity_class**: 默认 `jubilant`；命好命主默认强制 `jubilant`
- **structural_detector**:
  - 天乙贵人在原局 + 福星 / 月德（暂用：天乙贵人 + 文昌 + 华盖任二）
  - 或 emotion_cumulative 60 岁均值 ≥ 30
- **intensity_formula**: `min(1.0, 0.4 + 0.12 × (贵人) + 0.1 × (emotion 高))`
- **ethical_interrogation**:
  > 别人爱你。你心里那件事是：**我能不能允许自己被爱，并且不立刻想"我要怎么还"？** 你能不能让爱进来，而不立刻把它转成债？
- **tragic_remainder**: （这条母题几乎没有 tragic_remainder——这是 I 类的特点。但要承认：被爱的人有时候会害怕失去爱，并因此把爱推开）
- **cheap_consolations_to_refuse**:
  - "你必须先爱自己才能被爱"（治疗师式说教）
  - "享受当下"（消费主义安慰）
- **what_can_be_honestly_said**:
  - "你被爱不是因为你做了什么。你也不需要为此还什么"
  - "允许自己被爱，是你这一辈子的功课"
- **classical_source**: 《三命通会·福星》"福星贵人，主一生顺受";《滴天髓》"印旺无伤，受人提携"
- **philosophical_anchor**: 阿廖沙·卡拉马佐夫;新约"白白得来的恩典"

---

## J · 时代类（个人选择与历史洪流）

### J1 ◼ 被卷入历史

- **id**: `J1`
- **name**: 被卷入历史（个人意愿对时代洪流的极限）
- **category**: 时代类
- **tone**: T2
- **gravity_class**: 默认 `serious`；伴随 L6 → `tragic` 或 `transcendent`
- **structural_detector**:
  - 地支三合或三会成局（脚本 detect 三合局）
  - 且命主出生年份处于 era_window keywords 含 "动荡" / "革命" / "战争" / "变迁" 之时段
  - 或 命主壮年大运处于此类 era_window
- **intensity_formula**: `min(1.0, 0.45 + 0.1 × (三合三会) + 0.15 × (壮年遇动荡 era))`
- **ethical_interrogation**:
  > 时代裹挟着你。你心里那件事是：**我哪些选择是我自己的，哪些是时代替我做的？** 你能不能既承认时代的力量，又不用它免除你自己的责任？
- **tragic_remainder**: 时代不会等你想清楚。它推着你走。你这辈子很多事不是你选的——但**没有人能替你承担它的后果**。
- **cheap_consolations_to_refuse**:
  - "时代造就英雄"（神化结构）
  - "你应该顺应时代"（消解个人责任）
- **what_can_be_honestly_said**:
  - "你被卷入是真的。你的选择空间比想象的小"
  - "但这不能让你免责——你做的事仍然是你做的"
- **classical_source**: 《三命通会·三合》"三合成局，必应大事";段建业"地支会方，时代之兆"
- **philosophical_anchor**: 黑格尔"历史的诡计";托尔斯泰《战争与和平》

---

### J2 ⬛ 时代不利时的不背叛

- **id**: `J2`
- **name**: 时代不利时的不背叛（时代走错了，仍不跟着走错）
- **category**: 时代类
- **tone**: T3
- **gravity_class**: 默认 `tragic`；伴随 L2/L6 → `transcendent`
- **structural_detector**:
  - 用神被时代结构性压制（命主用神 vs 所处 era_window 主导能量相冲）
  - 例：命主用神为木，但壮年处于"金气主导"era（如战时）
  - 加成：用神在原局已弱（`yongshen._reverse_check.usability == "无"`）→ 强度 +0.15
- **intensity_formula**: `min(1.0, 0.5 + 0.15 × (用神被压) + 0.1 × (用神弱))`
- **ethical_interrogation**:
  > 你周围的人都在跟着时代走错的方向。你心里那件事是：**我能不能在大家都错的时候，仍然不错？** 而且你能不能不把"我没错"变成"我比他们高"那种廉价的优越？
- **tragic_remainder**: 你这种坚持不会让时代变好，也不会让你过得好。它只是让你心里有一个东西没有塌。
- **cheap_consolations_to_refuse**:
  - "时代终会过去"（结果论安慰）
  - "正确的会胜利"（历史目的论）
- **what_can_be_honestly_said**:
  - "你不跟着错，是你这种结构的人的本能——不是你高尚"
  - "代价是真的。你这辈子可能就在不利的时代里度过"
- **classical_source**: 《滴天髓·用神》"用神被时令克，必逆境而显";《穷通宝鉴》"时背用神，志清而身困"
- **philosophical_anchor**: 鲁迅"于无声处听惊雷";潘霍华《狱中书简》

---

## K · 缺失类（结构性的不全和不被记录）

### K1 ⬛ 努力被结构消音

- **id**: `K1`
- **name**: 努力被结构消音（做了但不被记录的人生）
- **category**: 缺失类
- **tone**: T3
- **gravity_class**: 默认 `tragic`
- **structural_detector**:
  - 空亡在年柱或时柱（`shensha.kongwang.in_chart` 含 `pillars[0].zhi` 或 `pillars[3].zhi`）
  - 或 截路空亡组合
  - 或 fame_yearly 长期低于 baseline + spirit_yearly 较高（"没被记得的有功者"）
  - 加成：日支空亡 → 强度 +0.15
- **intensity_formula**: `min(1.0, 0.5 + 0.15 × (年/时柱空亡) + 0.1 × (fame 低 vs spirit 高))`
- **ethical_interrogation**:
  > 你做了。没人记得。你心里那件事是：**我能不能不假装"被看见"对我不重要？** 同时——**我能不能不被这个"没被看见"驯化成只为被看见而做事？**
- **tragic_remainder**: 你的工作真的就不在历史的记录里。即使你 100 年后被人发现，那也是 100 年后的事——你这辈子是没有了。
- **cheap_consolations_to_refuse**:
  - "你的努力会被看见的"（结果论虚假承诺）
  - "梵高死后才出名"（廉价历史比较）
  - "时间会证明你的价值"（目的论安慰）
- **what_can_be_honestly_said**:
  - "你做的事在你之外的地方也成立——它不需要被记录就有重量"
  - "你这辈子可能不会被看见。这件事是真的——不是你不努力"
- **classical_source**: 《子平真诠·论空亡》"空亡之人，劳而无功";《三命通会》"年支空亡，祖业无承"
- **philosophical_anchor**: 西蒙·薇依"无名者";卡夫卡死前要求烧掉手稿

---

### K2 ⬛ 带着不全活

- **id**: `K2`
- **name**: 带着不全活（先天结构性缺失）
- **category**: 缺失类
- **tone**: T3
- **gravity_class**: 默认 `tragic`
- **structural_detector**:
  - `wuxing_distribution` 中有任一五行 `missing == True`
  - 或 用神缺位（`yongshen._reverse_check.usability == "无"`）
  - 加成：用神所属五行完全不见 → 强度 +0.15
- **intensity_formula**: `min(1.0, 0.55 + 0.15 × (用神缺位) + 0.1 × (五行缺))`
- **ethical_interrogation**:
  > 你身上有一个东西从一开始就缺。它不是你后来弄丢的，是它本来就没有。你心里那件事是：**我能不能不假装它没缺？同时不让"我缺"变成我用来要求别人补偿我的工具？**
- **tragic_remainder**: 缺的东西不会长出来。你这辈子要带着这个空活——它不会被填满，最多你学会和它共处。
- **cheap_consolations_to_refuse**:
  - "你可以自己创造你需要的"（虚假自助）
  - "缺失是另一种完整"（鸡汤式翻转）
  - "塑造了你"（陀氏化禁用句）
- **what_can_be_honestly_said**:
  - "你缺的东西是真的缺。它不会回来"
  - "但**带着不全活**——这本身是一种活法，不是失败"
- **classical_source**: 《滴天髓·缺位》"五行缺一，必有不全";《穷通宝鉴》"用神不见，命有大遗"
- **philosophical_anchor**: 西蒙·薇依"重负是神恩";克尔凯郭尔"亚伯拉罕的信"

---

### K3 ◼ 晚成者的焦虑

- **id**: `K3`
- **name**: 晚成者的焦虑（30 岁看不见自己，且不许用"大器晚成"自我安慰）
- **category**: 缺失类
- **tone**: T2
- **gravity_class**: 默认 `serious`
- **structural_detector**:
  - 杂气格（月令四库 + 多十神兼透）
  - 或 蓄藏格（用神在地支藏未透）
  - 或 命主在 30 岁前 spirit/wealth/fame 三维均 < baseline
- **intensity_formula**: `min(1.0, 0.45 + 0.1 × (杂气/蓄藏) + 0.1 × (30 岁前低迷))`
- **ethical_interrogation**:
  > 你 30 岁看自己——一片模糊。你心里那件事是：**我能不能不靠"大器晚成"安慰自己**？同时——**我能不能不放弃**？
- **tragic_remainder**: "晚成"不是必然的。它可能晚成，也可能根本不成。你 30 岁的不确定**是真的不确定**，不是被故事化的悬念。
- **cheap_consolations_to_refuse**:
  - "大器晚成"（自我神化的廉价版）
  - "梵高 30 岁还在卖颜料"（廉价历史比较）
  - "你只是还没找到方向"（虚假指引）
- **what_can_be_honestly_said**:
  - "你 30 岁看不见自己是真的。这种焦虑不是你想多了"
  - "你可能真的不会成。但**继续做**——不是因为你相信会成，是因为你这种结构的人不能不做"
- **classical_source**: 《滴天髓·蓄藏》"蓄藏之命，必晚发";《子平真诠·论库》"杂气格，必杂气透出方显"
- **philosophical_anchor**: 卡夫卡 31 岁还是保险公司职员;塞尚 50 岁后才被承认

---

## L · 超越性选择 / 献身类

> **本质**：一个人**为比自己更大的东西**做出**违背"对自己有利"的选择**。这种"更大的东西"可以是艺术、科学、真理、上帝、爱、正义、良心、一个具体的人、一个民族、一个理想……
>
> **共同性质**：必然伴随古法意义上的"凶"——财损 / 官损 / 孤独 / 早夭。但**伦理上是超越性的**——LLM 必须有勇气说出来。
>
> **特殊文体规则**（与 A-K 类不同 · 详见 `virtue_recurrence_protocol.md` 持续音规则）：
> - 持续音类（一辈子的底色，不是被某个流年触发）—— 不写"第 N 次"，写"它从 X 岁就在你心里"
> - 在 ≥ 3 个大运段都浮现
> - 允许位置 ① 开篇就直接给出价值判断（"命书上是凶，但你做的是对的"）—— 不必等到位置 ④
> - 顿悟段必须显式说出"命局判错"或等价表述
> - 必须配反身性免责（"我不是在让你去走这条路。我是在承认你已经走过的路"）
>
> **L 类检测约束（最关键）**：
> - L 类母题**必须同时满足**：(1) 命局有相应的结构标志；(2) 命局存在"凶"的客观结构（财损 / 官损 / 孤独 / 早损 / 用神被压等）
> - 如果一个人触发 L 的"道德选择"标志但**没有付出任何代价**，则**不**判为 L 类（避免把廉价美德标签给"嘴上正义但生活舒服"的人）
> - L 类一旦触发，强度评分倾向于"主线"——它必然成为顿悟段的核心轴
> - **L 类一律标记 `gravity_class = transcendent`**

---

### L1 ⬛ 艺术 / 科学的召命

- **id**: `L1`
- **name**: 艺术 / 科学的召命
- **category**: 超越性献身类
- **tone**: T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 食神不就财（食神透 + 财星无气）
  - 或 华盖加印（`shensha.huagai.found == True` + 印星天干透）
  - 或 文昌驿马（文昌 + 驿马同在原局）
  - 或 印星单透守身
  - **AND（凶结构必备）**：以下任一：wealth_cumulative 60 岁均值 < -10；emotion_cumulative 60 岁均值 < 0；fame_yearly 长期低于 baseline；命主早损迹象（forecast_window spirit < 0）
- **intensity_formula**: `min(1.0, 0.55 + 0.15 × (结构标志数) + 0.15 × (凶结构强度))`
- **ethical_interrogation**:
  > 你做的事不被市场也不被时代以你需要的速度回应。你心里那件事是：**我做这个是为了它本身，还是为了某天会被认可？** 这个问题没有答案——但你停不下来。**你做这件事不是因为你选了它，是因为它选了你**。
- **tragic_remainder**: 你这辈子可能根本不会被同代人完整理解。你做的事可能要 50 年、100 年才会被看见——而你那时候已经不在了。
- **cheap_consolations_to_refuse**:
  - "你的天才会被发现的"（结果论虚假承诺）
  - "梵高死后才出名"（廉价历史比较）
  - "为艺术殉道是浪漫的"（神化苦难）
- **what_can_be_honestly_said**:
  - "命局没有给你这个选择以好结果……但你这一辈子要做这个选择，是因为它超越了命局能给你的任何东西"
  - "**你做的事在你之外的地方也成立**——它不依赖被认可才有重量"
  - "**我不是在让你去走这条路。我是在承认你已经走过的路**"
- **classical_source**: 《滴天髓·华盖》"华盖之命，必有所专";《子平真诠》"食神不就财，必为艺人"
- **philosophical_anchor**: 梵高、卡夫卡、塞尚、玻尔兹曼、维特根斯坦；陀思妥耶夫斯基对艺术家的描绘

---

### L2 ⬛ 道德 / 政治献身

- **id**: `L2`
- **name**: 道德 / 政治献身
- **category**: 超越性献身类
- **tone**: T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 伤官见官 + 七杀压身（伤官透 + 七杀 ≥ 2）
  - 加成：天乙贵人在原局（"天授其位"）+ 华盖
  - **AND（凶结构必备）**：早损格 OR emotion 大幅长期低 OR 多次重型 mangpai 事件（特别是 shang_guan_jian_guan 重 + 反吟应期）
- **intensity_formula**: `min(1.0, 0.6 + 0.15 × (结构标志) + 0.2 × (凶结构强度))`
- **ethical_interrogation**:
  > 你这辈子被反复审问的是：**当对的事和对自己有利的事分开时，你站在哪一边**？而且你心里有一个更深的问题：**我做这些事是为了正义本身，还是为了证明自己是个有正义感的人？** 即使你怀疑动机，你还是没办法不做——这件事大于"我自己动机干净不干净"。
- **tragic_remainder**: 你被你抗争的对象实际地伤害了。命局给你的是真实的、肉身的、不可挽回的代价：健康、自由、亲人、或全部。古法到这里只能说"凶"。
- **cheap_consolations_to_refuse**:
  - "正义会胜利的"（历史目的论）
  - "你做对的事会被铭记"（结果论虚假承诺）
  - "你的牺牲换来了 X"（必须避免任何"换来"句式 → 反身性）
- **what_can_be_honestly_said**:
  - "**命局判的凶没错——代价是真的。但你做的事是对的**"
  - "**有些事就是值得用一辈子的'凶'去换的。你换了**"
  - "**这件事在你之外的任何地方都成立**——不依赖时代承认你、历史记住你、任何人最终知道这是你做的"
  - "**我不是在让你去走这条路。我是在承认你已经走过的路**"
- **classical_source**: 《滴天髓·伤官见官》"伤官见官，奇而险";段建业《盲派命理》"伤官见官 + 七杀，必有所抗"
- **philosophical_anchor**: 林昭《十四万言书》;潘霍华《狱中书简》;甘地、马丁·路德·金、苏格拉底《申辩》

---

### L3 ⬛ 良心

- **id**: `L3`
- **name**: 良心（拒绝随波逐流）
- **category**: 超越性献身类
- **tone**: T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 日主清纯（`bazi.day_master_wuxing` 与月令气场和谐 + 无杂气混乱）
  - 且 食神制杀格（食神透 + 七杀 + 食神在适当位置制杀）
  - 或 印星单透守身（仅 1 个印星但守住日主）
  - 加成：华盖
  - **AND（凶结构必备）**：spirit_cumulative 长期受压 OR 感情 / 关系长期偏弱 OR 与时代的不合
- **intensity_formula**: `min(1.0, 0.55 + 0.15 × (清纯) + 0.15 × (凶结构))`
- **ethical_interrogation**:
  > 你这辈子被反复审问的是：**当所有人都说一件事是对的时，你能不能仍然不做？** 你心里那件事是：**我不做不是因为我清高，是我心里有一个东西做这件事会塌**。
- **tragic_remainder**: 你的良心不会让你过得好。它会让你被身边的人当成"麻烦的人"、"想得太多的人"、"不合群的人"。这种孤立是真的。
- **cheap_consolations_to_refuse**:
  - "懂你的人会懂"（结果论安慰）
  - "你的纯粹会被欣赏"（虚假承诺）
- **what_can_be_honestly_said**:
  - "你不能做某些事是真的——不是你选不做，是你身体里有一个东西做了会塌"
  - "**我不是在让你保持纯洁。我是在承认你这种结构的人本来就不能跟着大家走**"
- **classical_source**: 《滴天髓·清气》"日主清纯，必出良吏";《子平真诠》"食神制杀，化煞为清"
- **philosophical_anchor**: 索尼娅·马尔梅拉多娃;阿廖沙·卡拉马佐夫;米什金（白痴）

---

### L4 ◼ 爱情的献身

- **id**: `L4`
- **name**: 爱情的献身（为一个人放弃世俗位置）
- **category**: 超越性献身类
- **tone**: T2 偏 T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 日支冲合活动剧烈（多次大运 / 流年冲合日支）
  - 且 七杀正官杂（官杀混杂）
  - 且 桃花重（`shensha.taohua.found == True` + 桃花地支多见）
  - **AND（凶结构必备）**：因情感选择导致的客观损失（emotion 高峰对应 wealth/fame dip）OR 配偶宫被冲克且无救
- **intensity_formula**: `min(1.0, 0.5 + 0.12 × (日支活动) + 0.12 × (桃花) + 0.15 × (情感代价))`
- **ethical_interrogation**:
  > 你为一个人放弃了你本可以拥有的位置。你心里那件事是：**我是真的爱他，还是我用'爱'包装了某种'我要逃离原来的人生'的渴望？** 你能区分这两件事吗？
- **tragic_remainder**: 即使爱是真的，代价也是真的。你失去的位置不会回来。你的选择被身边的人认为"不值得"——这件事不会改变。
- **cheap_consolations_to_refuse**:
  - "为爱付出的都值得"（神化爱）
  - "他/她值得你这样"（结果论判定）
- **what_can_be_honestly_said**:
  - "你这辈子被一个人改变了——这是事实。这个改变是真的，代价也是真的"
  - "**我不是在评价你的选择。我是在承认这件事在你身上发生了**"
- **classical_source**: 《三命通会·桃花》"桃花透官，必为情困";《滴天髓·配偶宫》"日支被冲合，必有情变"
- **philosophical_anchor**: 安娜·卡列尼娜;艾洛伊丝与阿伯拉尔;托尔斯泰晚年与索菲娅

---

### L5 ⬛ 信仰 / 灵性献身

- **id**: `L5`
- **name**: 信仰 / 灵性献身（为神/灵性追求放弃一切）
- **category**: 超越性献身类
- **tone**: T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 华盖叠现（`shensha.huagai.found == True` + 华盖地支 ≥ 2 见）
  - 且 印星过旺（印星 ≥ 3 透或地支 ≥ 3 见）
  - 且 空亡日 / 时（`shensha.kongwang.in_chart` 含日或时支）
  - **AND（凶结构必备）**：wealth 持续低迷 OR 关系长期偏弱 OR 命主选择独身 / 出家 / 隐居路径的命局信号
- **intensity_formula**: `min(1.0, 0.55 + 0.15 × (华盖+印旺) + 0.15 × (凶结构))`
- **ethical_interrogation**:
  > 你这辈子被某个超越性的东西吸引——它可能叫上帝、道、空、绝对、爱本身。你心里那件事是：**我追求它是因为它真的存在，还是我用'追求它'逃避世俗的责任？** 你能不能区分？
- **tragic_remainder**: 你为这个追求放弃的世俗的东西不会回来。即使你的追求"成了"（通常没人能确认），代价也已经付了。
- **cheap_consolations_to_refuse**:
  - "你会得到神的回报"（宗教功利化）
  - "灵性追求是最高的"（神化结构）
- **what_can_be_honestly_said**:
  - "你这条路在世俗看来是凶——它就是凶"
  - "**这条路上你不孤独——但你的孤独不会被任何同行者解决**"
  - "**我不是在让你出家。我是在承认你这种结构的人本来就被这种东西吸引**"
- **classical_source**: 《滴天髓·华盖》"华盖叠见，必近宗教";《三命通会》"印多空亡，必出尘世"
- **philosophical_anchor**: 特蕾莎修女;十字若望;托尔斯泰晚年;西蒙·薇依

---

### L6 ◼ 民族 / 时代献身

- **id**: `L6`
- **name**: 民族 / 时代献身（把自己捐给一个时代或民族）
- **category**: 超越性献身类
- **tone**: T2 偏 T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 用神被时代结构性压制（J2 触发条件）
  - 且 七杀透 + 食伤明理（食伤透干 + 与七杀对位）
  - **AND（凶结构必备）**：出生年份处于时代动荡期 + 命主壮年遇 J1 触发 + 命主 emotion/wealth 长期低迷
- **intensity_formula**: `min(1.0, 0.55 + 0.15 × (J2 触发) + 0.15 × (时代压力))`
- **ethical_interrogation**:
  > 你的命被绑在了一个时代/民族上。你心里那件事是：**我是真的为这个比我大的东西负责，还是我用'献身'包装了我对个人生活的逃避？** 你能不能既承担时代，又承认你也是一个个人？
- **tragic_remainder**: 时代/民族不会感谢你。即使它最终好了，那个好也不是你的——你那时候已经不在或者老了。你这辈子是付出去了。
- **cheap_consolations_to_refuse**:
  - "民族会铭记你"（虚假承诺）
  - "你的牺牲不会白费"（结果论安慰）
- **what_can_be_honestly_said**:
  - "**你不是被时代推到这里——你是主动走到这里的。命局只是给了你敢走到这里的灵魂**"
  - "**我不是在让你为时代去死。我是在承认你已经在为它活**"
- **classical_source**: 段建业"用神被时代压制，必有志士";《滴天髓》"杀透食配，必有大任"
- **philosophical_anchor**: 鲁迅;闻一多;玻利瓦尔;切·格瓦拉

---

### L7 ◼ 守护他人

- **id**: `L7`
- **name**: 守护他人（把人生让给具体他人）
- **category**: 超越性献身类
- **tone**: T2 偏 T3
- **gravity_class**: `transcendent`（已走语境）
- **structural_detector**:
  - 印为忌神（C3 触发条件加重）
  - 或 食伤被合
  - 且 日支孤辰（`day_zhi == GUCHEN_GUASU[year_zhi][0]`）
  - **AND（凶结构必备）**：命主一辈子 spirit/wealth/fame 三维平庸但 emotion 长期偏低（"为他人活"的客观信号）
- **intensity_formula**: `min(1.0, 0.5 + 0.12 × (印为忌+食伤被合) + 0.15 × (凶结构))`
- **ethical_interrogation**:
  > 你的人生让给了具体的人——孩子、伴侣、父母、学生、被照护者。你心里那件事是：**我是真的爱他们，还是我用'爱他们'回避'我自己想要什么'这个问题？** 你能不能两件事都承认？
- **tragic_remainder**: 你照顾的人不会以你给出的强度回报你。他们也不应该被要求这样回报——但你的付出确实就是不会被等量收回。
- **cheap_consolations_to_refuse**:
  - "母爱无私是最伟大的"（神化牺牲）
  - "你的孩子会感激你"（结果论虚假承诺）
  - "牺牲是值得的"（必须避免）
- **what_can_be_honestly_said**:
  - "你给出去的不会被等量收回——这是事实，不是不公"
  - "**这种照顾是你这种结构的人的活法**——不是你要被神化，是你的灵魂结构装不下别的"
  - "**我不是在赞美牺牲。我是在承认你这一辈子做的事**"
- **classical_source**: 《子平粹言》"印为忌而旺，反损人";段建业"日支孤辰 + 印重，多为他人活"
- **philosophical_anchor**: 列维纳斯"对他者的责任无限制";无名母亲;德蕾莎修女对临终者

---

## 附录 A · L 类与其他类的关键区分

| 对比 | A-K 类 | L 类 |
|---|---|---|
| 关注对象 | 局部抉择 / 关系结构 / 资源分配 | **整个生命形态被一件比自己大的事抓住** |
| 触发频率 | 流年事件触发 | **持续音**——一辈子的底色，不是被某个流年触发 |
| 文体规则 | "第 N 次出现" 累积感 | "**它从 X 岁就在你心里**"持续感 |
| 顿悟段允许直接价值判断 | 不允许 | **允许且必须**（"命书上是凶，但你做的是对的"） |
| 代价是否必备 | 不必 | **必须**（无代价 ≠ L 类，避免廉价美德标签） |
| 反身性免责 | 不必 | **必须**（"我不是在让你去走这条路"） |
| gravity_class | 默认按 tone 推 | **一律 transcendent** |

| 比 | 区别 |
|---|---|
| **L 类 vs F 类** | F 才华类是「市场与创造之间的张力」（仍以变现为参照系）；L 类与市场无关，与**召命本身的真假**有关 |
| **L 类 vs C 类** | C 承担类是「被压上责任的人如何活下去」（被动）；L 类是**主动选择献身**（即使代价知道是凶仍然主动走） |
| **L 类 vs B 类** | B 真话类是「在压力下是否忠于真实」（局部选择）；L 类是「**用一辈子献给一件比自己大的事**」（整体生命形态） |

---

## 附录 B · gravity_class 调性五级速查

| 等级 | 适用 | LLM 语气示范 |
|---|---|---|
| **jubilant 喜庆** | I2、A1 轻、命好命主 I 类全部 | "祝你这一辈子能真的幸福"；"愿你保有 X" |
| **gentle 温和** | F1、E4 轻、D2、C2 轻 | "希望你能 X / 记得 X"；"小心 X" |
| **serious 严肃** | B1、B2、A2 主线、F2、C2 重、E3 | "代价是真的，但 X 在你之外的地方也成立" |
| **tragic 悲剧** | C1、E1 重、E2、B3、K2 主线 | "不会过去——但带着它活，本身也是一种活法" |
| **transcendent 超越** | L 类全部（已走语境）、G2 + L 类、C1 + L 类 | "命局判的是凶——但你做的事是对的。我不是在让你去走这条路" |

> **命好命主特殊保护**：当命主全部触发母题的 gravity_class 都 ∈ {jubilant, gentle}，**禁止**强加 serious 及以上调性，**禁止**强加 L 类，顿悟段**必须**包含"祝你这一辈子能真的幸福"或等价祝福句式。

> **悲剧倾向自检**：脚本在生成 portrait 前检查 gravity 分布，若命主结构温和但分配出过多 tragic 调，强制降级。

---

## 附录 C · 检测器使用约定（给 `scripts/virtue_motifs.py`）

每条 motif 在 `_virtue_registry.py` 中以 dataclass 形式注册：

```python
@dataclass(frozen=True)
class MotifSpec:
    id: str                          # "B1"
    name: str                        # "说真话的代价"
    category: str                    # "真话类"
    tone: str                        # "T2"
    default_gravity: str             # "serious"
    detector: Callable[[Bazi, Curves], DetectResult]
    intensity_formula: str           # 用于 audit
    requires_cost_for_L: bool        # L 类必备 = True
```

`DetectResult` 包含：

```python
@dataclass(frozen=True)
class DetectResult:
    triggered: bool
    intensity: float                  # 0-1
    activation_points: List[ActivationPoint]   # [(age, year, dayun, trigger_basis)]
    gravity_override: Optional[str]   # 根据周围结构判定的 override
```

`ActivationPoint` 字段：

```python
@dataclass(frozen=True)
class ActivationPoint:
    age: int
    year: int
    dayun: str             # "戊午"
    trigger_basis: str     # "原局有伤官缺正官，流年补出正官 → 应期"
```

详见 `references/virtue_recurrence_protocol.md` § 协议规范 + `scripts/virtue_motifs.py` 实现注释。

---

## 附录 D · 这个 catalog 不是终点

按 ★★★★★★ catalog 开放性铁律，本词典是 **诊断起点**，不是 **人性的全集**。LLM 在 `life_review` 位置 ④（顿悟段）、位置 ⑥（自由话）**被授权命名 catalog 之外的人性形态**，但必须：

1. **谦卑标记**："在我这套词典的 38 条里，没找到完全对应的"
2. **真实 trace**：≥3 个具体激活点（年龄 + 结构基础）
3. **结构性自审**："我可能看错了 / 你比这个名字大"
4. **给出 ethical_interrogation + tragic_remainder**
5. **频次硬上限**：位置 ④ ≤ 1 个 / 位置 ⑥ ≤ 1 个
6. **不绕过 silenced**：catalog 内被 silence 的母题禁止用"自创"做后门
7. **trace metadata 标 `motif_origin: "llm_invented"`**——供 `audit_llm_invented.py` 聚合，作为 catalog 演化的反馈

> 这个 catalog 会从 38 → 50 → 70，但**永远不号称"完全"**。这是它最重要的特征。

---

> 文档版本：v1（2026-04 初稿）
> 维护原则：每加一条 motif 必须同时给出 (1) detector (2) ethical_interrogation (3) tragic_remainder (4) cheap_consolations_to_refuse (5) what_can_be_honestly_said (6) classical_source (7) philosophical_anchor。**禁止**只加名字不加全字段。
