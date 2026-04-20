# Discriminative Question Bank · v8

> 5 维度共 ≥ 28 题的题库源文件。每题有 `id` / `dimension` / `prompt` / `options` / `likelihood_table` / `weight_class` / `discrimination_power` / 古籍出处。
>
> 本文件是 [`scripts/_question_bank.py`](../scripts/_question_bank.py) 的"人类可读源"。Python 端 dataclass 与本文件 1:1 对齐——改一边必须同步改另一边，calibrate.py 会做一致性检查。

---

## §0 题库设计原则

1. **phase-discriminative**：每题在 likelihood_table 中至少 2 个 phase 间出现 ≥ 0.20 的概率差。否则该题对决策无贡献，应剔除。
2. **falsifiability**：每题选项里必须有明确"反方向"选项（不能只问"你像不像 X"，必须问"X 还是 Y"）。
3. **无身份标签**：选项措辞严守 [fairness_protocol.md](fairness_protocol.md) §10——禁出现"升职/结婚/生育/离职/确诊/拿到 offer/创业失败"等身份/事件标签。改用方向性、体感性描述。
4. **likelihood 表的填法**：每行（phase）∑ = 1.0；填表时回到原始命理学理（《滴天髓》《子平真诠》《穷通宝鉴》等），写出"为什么这个 phase 选这个 option 概率高"的一句注脚。
5. **硬体征 vs 软自述**：D1/D3/D4 权重 2×（外部可观察事实），D2/D5 权重 1×（自述/感受）。

---

## §1 14 个候选 phase 列表（与 [phase_decision_protocol.md](phase_decision_protocol.md) §2 对齐）

```
P_DM       = day_master_dominant
P_FCAI     = floating_dms_to_cong_cai
P_FSHA     = floating_dms_to_cong_sha
P_FER      = floating_dms_to_cong_er
P_FYIN     = floating_dms_to_cong_yin
P_DGCAI    = dominating_god_cai_zuo_zhu
P_DGGUAN   = dominating_god_guan_zuo_zhu
P_DGSS     = dominating_god_shishang_zuo_zhu
P_DGYIN    = dominating_god_yin_zuo_zhu
P_CIDRY    = climate_inversion_dry_top
P_CIWET    = climate_inversion_wet_top
P_PSEUDO   = pseudo_following
P_TRUE     = true_following
P_HUAQI    = huaqi_to_<wuxing>
```

likelihood_table 不写出的 phase 视为均值（1/N_options）。

---

## §2 D1 · 民族志 × 原生家庭（6 题，hard_evidence × 2.0）

D1 题目结合 [era_windows_skeleton.yaml](era_windows_skeleton.yaml) 的出生年代窗，对父母客观事实做"phase 概率投影"。学理基础：八字父母宫（年柱 = 父母的舞台）+ 财官印的强弱。

### D1_Q1_birth_economic_condition · 出生时家庭经济
```
prompt: 你出生时（前后 2 年内）家里的经济状况大致是？
options:
  A) 富裕、宽绰，物质从未匮乏
  B) 中等偏上，紧但不缺
  C) 紧巴巴，常为钱发愁
  D) 困窘，缺过基本物资
likelihood_table_hint:
  - P_FCAI / P_DGCAI 在 A/B 概率高（财星主事 → 物质上得）
  - P_FYIN / P_DGYIN 在 A/B 概率中等（印旺多有荫庇）
  - P_DGSS / P_FER 在 C/D 概率高（食伤主事易耗财根）
  - P_DM 概率均匀（默认相位无强偏向）
出处：年柱财星 → 父母经济，《三命通会·父母篇》
```

### D1_Q2_father_presence · 父亲在场度
```
prompt: 你出生时（前后 2 年内）家里父亲在体感上的存在度是？
options:
  A) 长期在场，是家里主心骨
  B) 在场但权威感弱（长期生病/经商在外）
  C) 缺位（早逝/离异/常年外地）
  D) 在场且关系紧张（高压/严厉/冲突多）
likelihood_table_hint:
  - P_DM 在 A 高，D 中（父星正常）
  - P_FCAI / P_FSHA 在 C 高（父星无根 / 被克）
  - P_DGGUAN 在 D 高（官杀压日 → 父权强压）
  - P_FYIN 在 A 高（印旺有父荫）
出处：男命父星 = 偏财，女命父星 = 偏财；《滴天髓·父母》
```

### D1_Q3_mother_presence · 母亲在场度与角色
```
prompt: 你出生时（前后 2 年内）家里母亲的角色更偏向？
options:
  A) 强势主事、家里实际掌权者
  B) 温和持家、与父亲分工互补
  C) 弱势 / 长期生病 / 早逝 / 缺位
  D) 与你关系紧张 / 冲突多 / 距离远
likelihood_table_hint:
  - P_FYIN / P_DGYIN 在 A/B 高（印星主事 → 母亲强或荫厚）
  - P_FCAI 在 D 高（财坏印 → 母亲被压制 / 关系疏离）
  - P_DGSS 在 A 高（食伤旺者母亲常强势）
出处：母星 = 正印；《子平真诠·六亲》
```

### D1_Q4_siblings · 兄弟姐妹
```
prompt: 你的兄弟姐妹关系大致是？
options:
  A) 多个兄弟姐妹，关系紧密互助
  B) 1-2 个，关系普通
  C) 独生 / 没有同辈手足
  D) 有手足但常争执 / 远离 / 失和
likelihood_table_hint:
  - P_DM 在 A/B 高（比劫得位）
  - P_FCAI / P_DGCAI 在 D 高（比劫被财牵扯 → 争夺）
  - P_FSHA / P_DGGUAN 在 C/D 高（官杀克比劫 → 手足受损）
出处：比劫 = 兄弟；《三命通会·兄弟篇》
```

### D1_Q5_birth_place_era · 出生地 × 时代
```
prompt: 你出生时家庭所处的环境是？（结合 era_windows_skeleton）
options:
  A) 大城市 / 中产以上家庭
  B) 中小城镇 / 工人家庭
  C) 农村 / 乡镇底层
  D) 跨地域 / 父母常迁移 / 无固定根
likelihood_table_hint:
  - P_FCAI / P_DGCAI 在 A 偏高
  - P_DGSS / P_FER 在 D 偏高（食伤主事 → 流动性强）
  - P_HUAQI 在 D 偏高（化气多有"换轨"色彩）
出处：年柱 = 大环境；era_windows_skeleton 提供分类先验
```

### D1_Q6_grandparent_influence · 祖辈影响
```
prompt: 你童年（0-12 岁）受祖辈（爷奶/外公外婆）影响的程度？
options:
  A) 由祖辈带大，影响极深
  B) 经常见面，部分影响
  C) 偶尔见面，影响小
  D) 没怎么见过 / 早逝 / 失联
likelihood_table_hint:
  - P_FYIN / P_DGYIN 在 A 高（印旺多受祖辈荫）
  - P_FCAI 在 D 高（财坏印 → 祖辈缘薄）
  - P_DM 均匀
出处：印星 = 长辈 / 祖荫；《滴天髓·六亲》
```

---

## §3 D2 · 关系结构（6 题，soft_self_report × 1.0）

升级旧 R0。关注能量流向 / 进入方式 / 被吸引对象画像。**所有题目不预设对方性别**（参考 [fairness_protocol.md](fairness_protocol.md) §10），统一用"对方 / 另一方"等中性词。

### D2_Q1_partner_attraction_type · 你被吸引对象的画像
```
prompt: 你反复被吸引的对象，最常见的画像是？
options:
  A) 强势主导型，你常跟随对方节奏
  B) 资源型 / 给予物质型，你欣赏对方供给能力
  C) 同辈对等型，势均力敌互不主导
  D) 你欣赏其才华、想推他/她"输出"的人
likelihood_table_hint:
  - P_FSHA / P_DGGUAN 在 A 高（官杀方主导 → 对方强势）
  - P_FCAI / P_DGCAI 在 B 高（财星 = 资源载体）
  - P_DM 在 C 高（日主主导 → 关系对等）
  - P_FER / P_DGSS 在 D 高（食伤外推 → 欣赏输出型）
出处：财官印食 = 关系核心人物画像；《滴天髓·夫妻》《渊海子平·妻财》
```

### D2_Q2_partner_proactive · 关系建立时谁更主动
```
prompt: 在你过往的亲密关系建立时，多数时候是？
options:
  A) 你主动追求对方居多
  B) 对方主动追求你居多
  C) 双方差不多对等
  D) 没有明确"建立"过程，关系自然滑入
likelihood_table_hint:
  - P_FCAI / P_DGCAI 在 A 高（追财 = 自己主动）
  - P_FSHA / P_DGGUAN 在 B 高（被官杀推着走 → 对方主动）
  - P_DM 在 C 高（对等）
  - P_FER / P_DGSS 在 B 偏高（食伤外露魅力 → 对方先被吸引）
  - P_HUAQI 在 D 高（化气 = 自然换轨）
出处：从财 vs 从杀 vs 日主主导的根本差异；《滴天髓·从化》
```

### D2_Q3_partner_economic_role · 关系中的经济角色
```
prompt: 在你过往的亲密关系中，经济角色更常见是？
options:
  A) 你是主要经济输出方
  B) 对方是主要经济输出方
  C) 平摊 / 各自独立财务
  D) 经济常是关系中的冲突源
likelihood_table_hint:
  - P_FCAI / P_DGCAI 在 B 高（财场 → 对方载财）
  - P_FSHA / P_DGGUAN 在 B 偏高（对方主导 → 经济也主导）
  - P_FER / P_DGSS 在 A 高（食伤生财 → 自己输出强）
  - P_DM 在 C 高（独立平衡）
  - P_FYIN 在 B 偏高（被滋养型）
出处：财星位置 vs 食伤位置决定能量输出方向；《渊海子平·妻财》
```

### D2_Q4_partner_emotional_dependence · 谁更情感依赖谁
```
prompt: 在你过往的亲密关系中，情感依赖度更常见是？
options:
  A) 你更需要对方在场，对方相对独立
  B) 对方更需要你在场，你相对独立
  C) 高度互相依赖
  D) 双方都偏独立 / 各自有空间的伴生
likelihood_table_hint:
  - P_FYIN / P_DGYIN 在 A 高（寻求被滋养）
  - P_FCAI / P_FSHA 在 A 偏高（追/被推 → 离不开对方）
  - P_FER / P_DGSS 在 B 高（食伤外发 → 对方贴你）
  - P_DM 在 D 高（自给自足）
  - P_TRUE 在 A 极高（真从 = 极端依从）
  - P_HUAQI 在 C 高（化合 = 高度融合）
出处：印星依赖 vs 食伤外推；《滴天髓·性情》
```

### D2_Q5_relationship_pattern · 关系总体模式
```
prompt: 你过往关系的总体模式更接近哪个？
options:
  A) 长稳型，少而长
  B) 流动型，多而短，常切换
  C) 高强度爆发型，激烈短暂
  D) 低密度型，长期独处或淡如水
likelihood_table_hint:
  - P_DM 在 A 高（稳定）
  - P_FER / P_DGSS 在 B 高（食伤外发 → 流动）
  - P_FSHA / P_FCAI 在 C 高（极端从 → 高强度）
  - P_FYIN / P_DGYIN 在 A/D 偏高（守节 / 低密度）
  - P_HUAQI 在 B 高（换轨）
  - P_CIDRY / P_CIWET 在 D 偏高（体感受限 → 低密度）
出处：关系密度 = 用神 + 食伤 + 桃花的合成体感；《滴天髓·夫妻》
```

### D2_Q6_attraction_age_pattern · 吸引年龄段
```
prompt: 你反复被吸引的对象，年龄段更常见是？
options:
  A) 比你大较多（5 岁以上）
  B) 与你相仿
  C) 比你小较多（5 岁以上）
  D) 无明显规律 / 跨度很大
likelihood_table_hint:
  - P_FYIN / P_DGYIN 在 A 高（印 = 长辈 / 年长型）
  - P_FSHA / P_DGGUAN 在 A 偏高（官杀 = 年长权威）
  - P_DM 在 B 高（同辈）
  - P_FER / P_DGSS 在 C 高（食伤 = 晚辈 / 输出对象）
  - P_FCAI / P_DGCAI 在 C 偏高（财 = 我所克 → 后辈型）
  - P_HUAQI 在 D 高（化气换轨 → 跨度大）
出处：十神年龄象征；《三命通会·六亲篇》
```

---

## §4 D3 · 流年大事件（6 题动态模板，hard_evidence × 2.0）

D3 是**动态题**：实时跑 `score_curves.score_one_year()` 对每个候选 phase 算每年值（age 0 ~ now），找方差最大的 3-5 个 phase-discriminative 已活过年份，套 4 档选项模板。

### D3_template_age_X_overall_direction · X 岁那年综合方向
```
prompt: 你 {X} 岁那一年（约 {year} 年），整体感觉是？
options:
  A) 明显向上 / 顺风顺水
  B) 明显向下 / 受挫连连
  C) 大起大落 / 起伏剧烈
  D) 平稳 / 没什么特别记忆
likelihood_table_动态生成:
  - 对每个 phase，把该年 score_one_year 输出值映射到 4 档：
    > +2.0   → A 概率 0.6, C 概率 0.2, B 概率 0.1, D 概率 0.1
    < -2.0   → B 概率 0.6, C 概率 0.2, A 概率 0.1, D 概率 0.1
    波动 > 3 → C 概率 0.5, A 0.2, B 0.2, D 0.1
    abs < 1.0 → D 概率 0.5, A 0.2, B 0.2, C 0.1
fairness 黑名单：
  options 严禁出现"升职/结婚/生育/离职/确诊/拿到 offer/分手/创业"等具体事件
出处：流年节奏是 phase 决策最强信号；《穷通宝鉴·流年篇》
```

### D3_template_age_X_emotion_direction · X 岁那年感情方向
### D3_template_age_X_career_direction · X 岁那年事业方向
### D3_template_age_X_health_direction · X 岁那年身体方向
### D3_template_age_X_money_direction · X 岁那年财务方向
### D3_template_age_X_relationship_direction · X 岁那年关系方向

具体年份由动态生成器 `_question_bank.D3_dynamic_event_question(bazi, candidate_phases)` 决定。生成规则：
1. 对每个 candidate_phase 跑 score_curves，取曲线（age 0 ~ now-1）
2. 计算每年所有 phase 间的方差（沿 phase 轴）
3. 取方差 top-K 年份（K=3-5）
4. 对每个选定年份，按 6 个维度模板各生成 1 题（视方差性质选维度）

---

## §5 D4 · 中医体征（6 题，hard_evidence × 2.0）

扩展旧 R1 健康三问到完整六问。

### D4_Q1_cold_heat · 寒热体感
```
prompt: 你的整体寒热倾向是？
options:
  A) 怕冷、手脚常凉、爱穿厚
  B) 怕热、爱出汗、爱冷饮
  C) 上热下寒（脸红脚冷 / 口干腿凉）
  D) 上寒下热（咽痒脚心热）/ 寒热不定
likelihood_table_hint:
  - P_CIDRY 在 B/C 高（上燥下寒）
  - P_CIWET 在 A/D 高（上湿下燥）
  - P_DM 按命局 climate 默认
出处：《黄帝内经·素问》寒热辨证；干头 vs 地支冷暖独立判
```

### D4_Q2_sleep · 睡眠
```
prompt: 你过去 3 年的整体睡眠状况是？
options:
  A) 入睡快、深睡足、醒后清爽
  B) 多梦 / 浅眠 / 易醒，醒后疲乏
  C) 入睡难，但睡着后较深
  D) 睡眠时长足，但晨起仍困倦 / 沉重
likelihood_table_hint:
  - P_DM 在 A 高（神安）
  - P_CIDRY 在 C 高（上热扰心 → 难入睡）
  - P_CIWET 在 D 高（湿浊困脾 → 沉困）
  - P_DGSS / P_FER 在 B 高（食伤泄秀 → 神浮多梦）
  - P_FYIN 在 A 偏高（印安神）
  - P_DGGUAN / P_FSHA 在 C 偏高（官杀压神 → 入睡难）
出处：心神 / 脾湿 / 肾水睡眠三辨；《黄帝内经·素问》《伤寒论·辨阳明病》
```

### D4_Q3_organs · 脏腑薄弱处
```
prompt: 你长期的"薄弱"部位最接近？
options:
  A) 心 / 神（心慌、易焦虑、口腔溃疡反复）
  B) 脾胃（消化弱、胃胀、易腹泻或便秘）
  C) 肺呼吸 / 皮肤（鼻炎、过敏、皮肤干）
  D) 肝肾 / 腰膝（腰酸、膝软、精力不足）
likelihood_table_hint:
  - P_CIDRY 在 C 高（燥伤肺）+ A 偏高（火扰心）
  - P_CIWET 在 B 高（湿困脾）+ D 偏高（寒湿伤肾）
  - P_DGGUAN 在 D 偏高（官杀克身 → 紧绷）
  - P_DGSS 在 A 偏高（食伤泄气 → 心神不宁）
  - P_FYIN / P_DGYIN 在 D 偏高（印旺多内向 self-care）
  - P_DM 均匀
出处：五脏 → 五行对应；《黄帝内经·素问·阴阳应象大论》
```

### D4_Q4_body_type · 体型体格
```
prompt: 你成年后的体型最常见是？
options:
  A) 偏瘦、骨架小 / 不易长肉
  B) 中等、匀称
  C) 偏壮 / 易长肉 / 易浮肿
  D) 起伏大 / 体重常波动
likelihood_table_hint:
  - P_CIDRY 在 A 高（阴液不足 → 偏瘦）
  - P_CIWET 在 C 高（湿气重 → 浮肿型）
  - P_DM 在 B 高（中和）
  - P_DGSS / P_FER 在 D 偏高（食伤泄秀 → 代谢起伏）
  - P_FCAI / P_DGCAI 在 C 偏高（财厚易聚肉）
出处：燥湿 → 体型；现代体质辨证 + 《伤寒论·辨痰饮病》
```

### D4_Q5_appetite · 食欲口味
```
prompt: 你长期的食欲与口味偏好是？
options:
  A) 食量大、口重（爱辣 / 咸 / 厚味）
  B) 食量小、清淡，吃多易胀
  C) 偏好甜食 / 碳水 / 温热饮食
  D) 偏好生冷 / 凉饮 / 重水分
likelihood_table_hint:
  - P_CIDRY 在 D 高（上热怕燥 → 爱凉爱水）
  - P_CIWET 在 C 高（爱温热）+ B 偏高（湿困胃口差）
  - P_DGCAI / P_FCAI 在 A 高（财 = 食禄 → 食欲旺）
  - P_FYIN / P_DGYIN 在 B 偏高（口味淡 / 守节）
  - P_DGSS 在 A/D 平分（食伤外露 → 重口或贪凉）
出处：寒热口味偏好；《黄帝内经·素问·五味篇》
```

### D4_Q6_emotion_temperament · 情志倾向
```
prompt: 你的长期情志倾向最像哪一种？
options:
  A) 急躁 / 易上火 / 一点就炸
  B) 沉郁 / 易思虑 / 容易"想太多"
  C) 平和 / 起伏小
  D) 情绪起伏剧烈，时而高昂时而低落
likelihood_table_hint:
  - P_DM 在 C 高（中和）
  - P_CIDRY 在 A 高（上火 → 急躁）
  - P_CIWET 在 B 高（湿郁 → 沉思）
  - P_DGSS / P_FER 在 D 高（食伤泄秀 → 情绪外放起伏）
  - P_DGGUAN / P_FSHA 在 B 偏高（官压 → 内沉）
  - P_TRUE / P_PSEUDO 在 D 偏高（从化结构 → 情绪两极）
出处：五志七情；《黄帝内经·素问·阴阳应象大论》
```

---

## §6 D5 · 自我体感（4 题，soft_self_report × 1.0）

本性画像兜底，少量。

### D5_Q1_default_strategy · 遇压力时的默认策略
```
prompt: 遇到大压力时，你最本能的反应是？
options:
  A) 主动迎击，靠自己硬扛
  B) 借外力 / 找资源 / 找支持系统
  C) 顺势而为 / 等局势变
  D) 切换轨道 / 换个赛道重来
likelihood_table_hint:
  - P_DM 在 A 高（自主硬扛）
  - P_DGYIN / P_FYIN 在 B 高（印 = 找资源 / 靠山）
  - P_TRUE / P_PSEUDO / P_FCAI / P_FSHA 在 C 高（顺势从势）
  - P_HUAQI 在 D 高（换轨型）
  - P_DGSS / P_FER 在 D 偏高（食伤外发 → 另开一局）
出处：从化 vs 自主 vs 化轨 三类核心差异；《滴天髓·性情》《滴天髓·从化》
```

### D5_Q2_money_attitude · 对金钱的本能态度
```
prompt: 你对金钱的本能态度更接近？
options:
  A) 主动管理 / 重视积累 / 擅长保值
  B) 善于撬动 / 借力生财 / 资源整合
  C) 看淡 / 够用就好 / 不主动追求
  D) 起伏大 / 来去快 / 不擅积蓄
likelihood_table_hint:
  - P_DM 在 A 高（自主管理）
  - P_FCAI / P_DGCAI 在 B 高（追财借财）
  - P_FYIN / P_DGYIN 在 C 高（守节 / 看淡）
  - P_FER / P_DGSS 在 D 高（食伤泄秀 → 财路波动）
  - P_HUAQI 在 D 偏高（换轨型 → 起伏）
出处：财星 vs 印星 vs 食伤的金钱观差异；《渊海子平·财》
```

### D5_Q3_authority_relation · 与权威 / 规则的关系
```
prompt: 你与权威 / 规则系统的关系更接近？
options:
  A) 自己定规则 / 不愿被管
  B) 在规则内争上游 / 善用规则
  C) 服从规则 / 适应权威
  D) 体制外 / 边缘化 / 与规则保持距离
likelihood_table_hint:
  - P_DM 在 A 高（自主立规）
  - P_FSHA / P_DGGUAN 在 C 高（被官杀压 → 服从）
  - P_FCAI / P_DGCAI 在 B 高（财 = 规则内争上游）
  - P_FER / P_DGSS 在 D 高（食伤克官 → 反规则）
  - P_FYIN / P_DGYIN 在 C 偏高（印 = 体制庇护）
  - P_HUAQI 在 D 偏高
出处：官杀 vs 食伤 = 规则态度的两极；《滴天髓·官杀》
```

### D5_Q4_creative_outlet · 创造性输出的方式
```
prompt: 你最自然的"创造性输出"方式是？
options:
  A) 表达 / 内容 / 表演型输出
  B) 组织 / 系统建设 / 资源整合
  C) 学习 / 研究 / 知识沉淀
  D) 没有明显输出冲动 / 不需要外显
likelihood_table_hint:
  - P_FER / P_DGSS 在 A 高（食伤 = 表达）
  - P_FCAI / P_DGCAI 在 B 高（财 = 资源整合）
  - P_FYIN / P_DGYIN 在 C 高（印 = 学习沉淀）
  - P_FSHA / P_DGGUAN 在 B 偏高（官杀 = 体制内做事）
  - P_TRUE 在 D 偏高（无独立输出冲动）
  - P_HUAQI 在 D 偏高（换轨期暂无外显）
出处：食伤 / 财 / 印 = 三种主要输出原型；《滴天髓·性情》
```

---

## §7 likelihood_table 填表规范

每个题目必须在 [`scripts/_question_bank.py`](../scripts/_question_bank.py) 的 dataclass 中给出完整 likelihood_table。规范：

```python
likelihood_table = {
    "day_master_dominant":      {"A": 0.40, "B": 0.30, "C": 0.20, "D": 0.10},
    "floating_dms_to_cong_cai": {"A": 0.10, "B": 0.30, "C": 0.45, "D": 0.15},
    # ... 其他 phase
}
# 每行 ∑ 必须 = 1.0（_question_bank.py 加载时会断言）
# 未列出的 phase 视为均匀分布（每个 option 概率 = 1/N_options）
```

每题在 dataclass 里挂 `evidence_note` 字段写学理出处一句话。

---

## §8 discrimination_power 计算

```python
def discrimination_power(likelihood_table: dict, prior: dict) -> float:
    # 用 KL divergence between phases 的简化版：
    # 算每对 phase 在 option 分布上的 L1 距离，按 prior 加权求和
    phases = list(likelihood_table.keys())
    total = 0.0
    pair_count = 0
    for i, pi in enumerate(phases):
        for pj in phases[i+1:]:
            l1 = sum(abs(likelihood_table[pi][o] - likelihood_table[pj][o])
                     for o in likelihood_table[pi])
            weight = prior.get(pi, 0.05) * prior.get(pj, 0.05)
            total += l1 * weight
            pair_count += 1
    return total / max(pair_count, 1)
```

阈值：题目 `discrimination_power < 0.25` 时不进 askquestion_payload（对当前命局无价值）。

---

## §9 学理出处汇总

| 维度 | 主要古籍 | 现代参考 |
|---|---|---|
| D1 | 《三命通会·父母兄弟篇》《子平真诠·六亲》《滴天髓·六亲》 | 民国后命理实证派 |
| D2 | 《滴天髓·夫妻》《渊海子平·妻财》 | 旧版 R0 reasoning |
| D3 | 《穷通宝鉴·流年》《滴天髓·流年大运》 | score_curves 实测 |
| D4 | 《黄帝内经·素问》《伤寒论》 | 现代体质辨证 |
| D5 | 《滴天髓·性情》 | 心理学性格类型 |
