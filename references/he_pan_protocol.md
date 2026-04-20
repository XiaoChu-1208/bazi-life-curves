# 合盘协议（He Pan / Synastry Protocol · v1）

> 用户输入 ≥ 2 份八字，从 4 个关系维度（合作 / 婚配 / 友谊 / 家人）做兼容性分析。
> **整体动作逻辑与单盘一致：先做下马威校验（健康三问），再做合盘评分。**

---

## 1. 4 个关系维度（rel_type）

| key | 名称 | 主要看 | 加分项 | 减分项 |
|---|---|---|---|---|
| `cooperation` | 合作关系 | 财、官、印、比劫互动 + 大运同步度 | 财官印配（资源 + 上下级 + 认可） | 比劫夺财、双方都纯比劫无财 |
| `marriage` | 婚配 | 日柱合 / 夫妻宫（日支） / 五行互补 / 配偶星 | 日干合、日支六合、桃花互见、贵人互见、男看正财 / 女看正官 | 日支冲（大忌）、忌神在对方旺、大运反向 |
| `friendship` | 友谊 | 比肩 / 食伤同道 + 用神互助 | 互为比劫（同道）、互为食伤（一起搞事） | 七杀过多 → 友谊里有较劲 |
| `family` | 家人（可选第 4 维） | 印 / 比为主 + 长辈宫 / 子女宫 | 互为印（庇护教养）、互为比劫（同辈扶持）、杀印相生（严父慈子） | 父母宫（年柱）冲、子女宫（时柱）冲 |

## 2. 评分 4 层（脚本机械算）

`scripts/he_pan.py` 对每对人组合（A↔B）计算 4 层分数，求和得到 `total_score`：

### Layer 1：五行互补（`score_wuxing_complement`）
- A 用神在 B 八字里占比 ≥ 18% → **+(ratio×30)** 分
- A 用神在 B 八字里占比 < 5% → **-3** 分
- A 忌神在 B 八字里占比 ≥ 25% → **-(ratio×24)** 分
- 双向计算

### Layer 2：干支互动（`score_ganzhi_interactions`）
- 天干合化（柱位加权：日 1.0、月 0.9、时 0.7、年 0.6）→ +6×w
- 天干相冲 → -4×w
- 地支六合 → +7×w；**日支六合婚配额外 +5**
- 地支六冲 → -6×w；**日支冲婚配额外 -4（大忌）**
- 地支相害（穿） → -3×w
- 三合 / 半合 → +4
- 桃花互见 → +4
- 天乙贵人互见 → +5

### Layer 3：十神互配（按 rel_type focus）（`score_shishen_match`）
分 4 个 rel_type 子规则：
- **婚配**：男看正财 +12 / 偏财 +8 / 官杀 -6；女看正官 +12 / 七杀 +8 / 财星 -6（双向）
- **合作**：互为财 +6 / 一方官杀+另一方印 +8 / 互为比劫 +4（中性偏正，提示比肩夺财）
- **友谊**：互为比劫 +10 / 食伤 +5 / 出现七杀 -4
- **家人**：互为印 +8 / 互为比劫 +6 / 杀印相生 +6

### Layer 4：大运同步（`score_dayun_sync`）
- 在 `focus_years` 区间，看双方所走大运的天干 vs 各自用神是否同步
- 大运干属用神 / 生用神 → polarity = +1
- 大运干属忌神 / 克用神 → polarity = -1
- 同号年数 / 总年数 = `sync_ratio`
- 得分 = (sync_ratio - 0.5) × 20，范围 [-10, +10]

## 3. 总分等级（仅供 LLM 内部定调，不直接报给用户）

| total_score | grade | label |
|---|---|---|
| ≥ 50 | A | 结构性高度匹配 |
| 25 ~ 49 | B | 总体匹配，有亮点也有要注意的点 |
| 5 ~ 24 | C | 中性 / 平淡，看双方主观经营 |
| -15 ~ 4 | D | 偏摩擦 / 需双方刻意磨合 |
| < -15 | E | 结构性高摩擦，长期相处会很累 |

⚠️ **不要把 grade 直接报给用户**——尤其 D / E 等级，会让人不舒服。LLM 必须把它转化为人话，描述具体的"摩擦点"和"如何缓冲"，而不是甩等级。

## 4. 与下马威校验的关系（强制）

合盘前必须保证八字本身是准的，否则一切结构性配伍都是空中楼阁。

### 4.1 每份八字单独跑 R1 健康三问

```bash
for i in 1 2; do
  python scripts/handshake.py --bazi /tmp/p${i}_bazi.json --curves /tmp/p${i}_curves.json --out /tmp/p${i}_hs.json
done
```

LLM 把每个八字的 R1 转述给用户，让用户**分别**回答：
- 用户**自己的八字**：用户对自己的健康体感最熟，必须 R1 ≥ 2/3
- **对方的八字**（配偶 / 合伙人 / 朋友 / 家人）：用户能答多少答多少
  - 用户能答的健康问题里，命中率 ≥ 2/3 → 该方位 confidence = high
  - 用户只能答 1 个 / 完全答不上 → 该方位 confidence = low（标 caveat）

### 4.2 合盘 confidence 由短板决定

| 双方 R1 | 合盘 confidence | LLM 解读权限 |
|---|---|---|
| 都 ≥ 2/3 | high | 可以重一些，给具体年份 / 具体场景建议 |
| 一方 ≥ 2/3、另一方 < 2/3 | mid | 必须加 caveat："另一方八字校验不足，结论仅作方向参考" |
| 双方都 < 2/3 | low | 劝退 / 让用户先核对双方八字（多见于对方时辰不准） |

### 4.3 红线（沿用 handshake_protocol.md §5）

- 寒热体感 ✗ → 命局 climate 多半反了，不进合盘
- 脏腑短板 ✗ → 五行权重多半算偏，不进合盘

## 5. LLM 解读规则（强制）

### 5.1 必做

1. **按层逐一解读**：五行互补 → 干支互动 → 十神互配 → 大运同步，每层至少援引 2 条 notes
2. **加分项 / 减分项要写"怎么用 / 怎么避"**：
   - 加分（top_pluses）：为什么这条结构有意义 + 实操中怎么用上（比如"日支六合 → 你们一起做决定时容易达成共识，重要决策建议同桌当面谈，不要异地分头决定"）
   - 减分（top_minuses）：摩擦点是什么 + 怎么缓冲（比如"日支冲 → 同住时小事易摩擦，建议各自有独立空间 + 重大节日错峰相处"）
3. **focus_years 大运同步度**要落到具体建议（"未来 5 年共有 4 年同向 → 适合一起搞大事 / 创业 / 买大件"或反过来"未来 5 年只有 1 年同向 → 各自做事，重大共同决策推迟到 2030 后"）
4. **关系类型敏感性**：
   - 婚配：日柱合 / 日支冲必须明确指出，是婚配关键
   - 合作：财官印配 + 警惕比劫夺财
   - 友谊：比劫食伤同道 = 长久；七杀过多 = 易争胜
   - 家人：代际庇护（印） + 同辈互助（比）

### 5.2 禁止

- ❌ 直接给"配 / 不配"二元结论
- ❌ 把 grade 直接报给用户（"你们是 D 级"）
- ❌ 跳过双方 R1 校验直接合盘
- ❌ 不援引脚本 notes 凭"感觉"打分
- ❌ 在合盘里夹带"前世今生 / 命中注定"等不可证伪话术
- ❌ 给"建议分手 / 建议结婚 / 建议合伙"这种代替用户做决定的话——只给"如果决定做 X，怎样能更顺"

## 6. 工作流（合盘版）

```
Step 0  收集 N 份八字（≥ 2）+ 关系类型 + 关注年份
Step 1  对每份八字跑 solve_bazi.py
Step 2  对每份八字跑 score_curves.py（生成各自 curves.json）
Step 2.5 对每份八字跑 handshake.py → 健康三问
        ↓
        LLM 把每个八字的 R1 三问分组转述给用户，逐人收集 「对 / 不对 / 部分」
        ↓
        分别评定每份八字的 accuracy_grade（high/mid/low/reject）
        ↓
        若用户自己的八字 < mid → 走 Round 2 凑 4/6；仍不达标 → 让用户复核出生时辰
        若对方八字 < mid → 标 caveat 但允许继续，合盘结论降权
Step 2.7 询问输出格式（合盘默认 A · markdown 流式）
        ↓
        LLM 主动问："要纯 markdown 流式（A·默认），还是也想要 HTML 汇总表（B·多等几秒）"
        合盘默认 A —— 合盘没有"曲线图"刚需 HTML
Step 3  跑 he_pan.py（生成 he_pan.json）
Step 4  LLM 在对话里按 §5 规则**流式分节写解读**（每写完一节立刻发出，禁止憋整段）：
        ▸ Node 1 概览：N 人 / 关系类型 / confidence（基于双方 R1）
        ▸ Node 2 总分定调（人话，不甩 grade）
        ▸ Node 3 第 1 层 · 五行互补 解读
        ▸ Node 4 第 2 层 · 干支互动 解读
        ▸ Node 5 第 3 层 · 十神互配 解读
        ▸ Node 6 第 4 层 · 大运同步 解读
        ▸ Node 7 关键加分项：怎么用
        ▸ Node 8 关键减分项：怎么避
        ▸ Node 9 关系类型 tips（婚 / 合 / 友 / 家 各有侧重）
        ▸ Node 10 总结 + "如果决定做 X，怎样能更顺"
        每节用 markdown 标题（## 概览 / ## 第 1 层 · 五行互补 …）
Step 5  保存反馈到 confirmed_facts.json（每方一条）
```

**v5 流式硬要求**：上述 10 节必须按节流式输出，禁止把整段汇总憋到末尾一次性吐。Step 2.7 不能跳过——合盘默认 A，仅当用户明说要 HTML 才跑 B。

## 7. 命令行示例

```bash
# 双人婚配
python scripts/he_pan.py \
  --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json \
  --names 男方 女方 \
  --type marriage \
  --focus-years 2026 2027 2028 2029 2030 \
  --out /tmp/he_pan_marriage.json

# 三人合作（创业团队）
python scripts/he_pan.py \
  --bazi /tmp/p1_bazi.json /tmp/p2_bazi.json /tmp/p3_bazi.json \
  --names CEO CTO COO \
  --type cooperation \
  --focus-years 2026 2027 2028 \
  --out /tmp/he_pan_team.json
# 输出含所有 C(3,2)=3 对配对的评分

# 友谊
python scripts/he_pan.py --bazi a.json b.json --names 我 朋友A --type friendship --out hp.json

# 家人
python scripts/he_pan.py --bazi a.json b.json --names 我 母亲 --type family --out hp.json
```

## 8. 输出 schema 简表

```jsonc
{
  "version": 1,
  "rel_type": "marriage",
  "rel_name": "婚配",
  "n_persons": 2,
  "names": ["男方", "女方"],
  "pillars": ["庚午 辛巳 壬子 丁未", "甲子 丙寅 戊午 庚申"],
  "focus_years": [2026, 2027, ...],
  "pairs": [
    {
      "pair": "男方 ↔ 女方",
      "total_score": -9.1,
      "grade": {"grade": "D", "label": "...", "color": "orange"},
      "layers": [
        {"layer": "五行互补", "score": 1.3, "notes": [...]},
        {"layer": "干支互动", "score": 5.6, "notes": [...]},
        {"layer": "十神互配（婚配）", "score": -6.0, "notes": [...]},
        {"layer": "大运同步", "score": -10.0, "notes": [...], "sync_ratio": 0.0, "detail": [...]}
      ],
      "top_pluses": [...],   // 排序后取 top 6
      "top_minuses": [...],  // 排序后取 top 5
    }
  ]
}
```

## 9. 与 fairness / accuracy / prediction 协议的关系

- **fairness_protocol.md**：合盘只看八字结构，不接受姓名 / 关系状态 / 历史 → 满足盲化；且任何"配/不配"结论必须可证伪
- **accuracy_protocol.md**：合盘准确度受双方 R1 命中率限制，短板效应 → confidence 自动降级
- **prediction_protocol.md**：focus_years 的同步度建议必须给 (方向, confidence) 二元组
