# 题库审计报告 · v9

> 由 [scripts/audit_questions.py](../scripts/audit_questions.py) 生成。8 维 ambiguity detector + 命理词典扫描。**只读静态分析**，不读用户数据。

## Severity 汇总

| Severity | 题数 | 含义 |
|---|---|---|
| [CRIT] **critical** | 0 | 命理词典直接泄露（必须修，违反 elicitation_ethics §E1） |
| [HIGH] **high** | 1 | 诱导 / 反事实 / 多概念混选项（强烈建议改） |
| [MED ] **medium** | 4 | 模糊量词 / 主观评价 / 时间口径不清（建议改） |
| [LOW ] **low** | 4 | 双重否定 / 选项语义重叠（标记观察） |
| [ OK ] **ok** | 16 | 无任何命中 |

**Total**: 25 道静态题

## [HIGH] HIGH（1 题）

### [D1_Q2_father_presence] · ethnography_family / hard_evidence
**Q**: 你出生时（前后 2 年内）家里父亲在体感上的存在度是？

- `A3_multi_concept`: opt:在场且关系紧张（高压 / 严厉 / 冲突多）|markers=['且']

## [MED ] MEDIUM（4 题）

### [D1_Q1_birth_economic_condition] · ethnography_family / hard_evidence
**Q**: 你出生时（前后 2 年内）家里的经济状况大致是？

- `A2_subjective_judgment`: 中等

### [D1_Q6_grandparent_influence] · ethnography_family / hard_evidence
**Q**: 你童年（0-12 岁）受祖辈（爷奶 / 外公外婆）影响的程度？

- `A1_vague_quantifier`: 经常
- `A4_temporal_ambiguous`: 偶尔

### [D2_Q2_partner_proactive] · relationship / soft_self_report
**Q**: 在你过往的亲密关系建立时，多数时候是？

- `A1_vague_quantifier`: 差不多
- `A7_option_overlap`: common['主动追求']: '你主动追求对方居多' ∩ '对方主动追求你居多'

### [D4_Q4_body_type] · tcm_body / hard_evidence
**Q**: 你成年后的体型最常见是？

- `A2_subjective_judgment`: 中等

## [LOW ] LOW（4 题）

### [D2_Q3_partner_economic_role] · relationship / soft_self_report
**Q**: 在你过往的亲密关系中，经济角色更常见是？

- `A7_option_overlap`: common['是主要经济输出方']: '你是主要经济输出方' ∩ '对方是主要经济输出方'

### [D2_Q4_partner_emotional_dependence] · relationship / soft_self_report
**Q**: 在你过往的亲密关系中，情感依赖度更常见是？

- `A7_option_overlap`: common['相对独立']: '你更需要对方在场，对方相对独立' ∩ '对方更需要你在场，你相对独立'

### [D2_Q6_attraction_age_pattern] · relationship / soft_self_report
**Q**: 你反复被吸引的对象，年龄段更常见是？

- `A7_option_overlap`: common['较多（5 岁以上）']: '比你大较多（5 岁以上）' ∩ '比你小较多（5 岁以上）'

### [D6_Q3_gains_source] · self_perception / soft_self_report
**Q**: 到目前为止，你最重要的几次「得失变化」更多来自？

- `A7_option_overlap`: common['关键决策']: '少数几个关键决策 / 一次定型的选择' ∩ '关键决策 + 日常经营并重，两者贡献相近'

## [ OK ] OK（16 题）

- `D1_Q3_mother_presence`（ethnography_family）: 你出生时（前后 2 年内）家里母亲的角色更偏向？…
- `D1_Q4_siblings`（ethnography_family）: 你的兄弟姐妹关系大致是？…
- `D1_Q5_birth_place_era`（ethnography_family）: 你出生时家庭所处的环境是？（结合 era_windows_skeleton）…
- `D2_Q1_partner_attraction_type`（relationship）: 你反复被吸引的对象，最常见的画像是？…
- `D2_Q5_relationship_pattern`（relationship）: 你过往关系的总体模式更接近哪个？…
- `D4_Q1_cold_heat`（tcm_body）: 你的整体寒热倾向是？…
- `D4_Q2_sleep`（tcm_body）: 你过去 3 年的整体睡眠状况是？…
- `D4_Q3_organs`（tcm_body）: 你长期感觉的'薄弱'部位最接近？…
- `D4_Q5_appetite`（tcm_body）: 你长期的食欲与口味偏好是？…
- `D4_Q6_emotion_temperament`（tcm_body）: 你的长期情志倾向最像哪一种？…
- `D5_Q1_default_strategy`（self_perception）: 遇到大压力时，你最本能的反应是？…
- `D5_Q2_money_attitude`（self_perception）: 你对金钱的本能态度更接近？…
- `D5_Q3_authority_relation`（self_perception）: 你与权威 / 规则系统的关系更接近？…
- `D5_Q4_creative_outlet`（self_perception）: 你最自然的'创造性输出'方式是？…
- `D6_Q1_agency_style`（self_perception）: 在人生大方向上，你更接近哪一种推进模式？…
- `D6_Q2_life_rhythm`（self_perception）: 回顾你人生到目前为止的整体节奏，更像哪一种？…
