# Phase Inversion Validation Loop · 相位反演校验循环

> **方法论编号**：P1-7（v7 新增）
> **本协议解决的问题**：当默认算法对一份命局的"相位"判定方向反了（日主主导 vs 旺神主导 / 调候方向反 / 假从误判 / 用神反向），R0/R1 命中率会很低。当前 Skill 把"命中率低"一律归因为"八字错 / 时辰错"，**漏掉了第三种可能** —— **算法读反了**。本协议建立一套机械化的反向假设搜索 + 闭环纠错流程。

---

## 0. 真实案例（本协议的诞生原因）

某用户 1996 年八字 `丙子 庚子 己卯 己巳`：

- **默认 Skill 推法**：壬水日主主导（实际是己土）+ 印星化杀 + 身弱用印 → R0/R1 命中率 ≈ 30%
- **LLM 反向推法**：丙火财星主事 + 日主借力 + 上燥下寒 → R0/R1 命中率 ≈ 90%

**幅度差** = 60 个百分点。在校验里这是「**决定性证据**」级别。

LLM 是人肉修正的，但下一个用户的 LLM 不一定会做这个反向假设。**核心算法漏了一层关键判断**。本协议把这层判断工程化、机械化、纳入闭环。

---

## 1. 问题分类 · 什么是"相位反向"

「相位（phase）」 = 命局算法选择的"读法主线"。同一份命盘可以按多种相位读，结论 180° 相反：

| 相位编号 | 名称 | 默认推法 | 反向推法 | 触发场景 |
|---|---|---|---|---|
| **P1** | 日主虚浮反演（v7.1 重写）| 日主当家 → 用印比帮身 | 弃命从势 → 用财官杀（从财 / 从杀 / 从儿）| 比劫不通根 + 月令克泄日主 + 旺神成势 |
| **P2** | 旺神得令反主事 | 日主为主 + 财官为客 | 旺神为主 + 日主为辅 | 月令旺神成势 + 全局簇拥 |
| **P3** | 调候反向 | 寒湿用火 / 燥实用水 | 表层 vs 里层方向相反（上燥下寒 / 外燥内湿）| 干头 vs 地支 燥湿对冲 |
| **P4** | 假从 / 真从边界（v7.1 重写）| 弱身有微根 → 不从 | 区分有印护身（假从）vs 完全无救（真从）| 日主弱 + 看比劫根 / 印根 / 时柱自坐 |
| **P5** | 三气成象 / 财官印连环（v7.1 新增）| 单一旺神主导 | 多神成势 + 流通生化 → 流通方向 = 主事 | 日主真弱 + ≥ 2 个非日主 ≥ 3 分 + top2 ≥ 8 + 含连环生化链 |

> 这五类不是穷举，但覆盖了 95% 的"读反"场景。**P5 专门处理 P1 漏掉的"假从有印 / 财官印三气"场景**（详见 v7.1 升级记录）。

---

## 2. 核心思想 · R 命中率作为反向回推信号

### 升级前

```
R0 + R1 + R2 命中率
   ↓
  ≥ 4/6 → 进入出图（happy path）
  ≤ 3/6 → 加 caveat 进入出图（中置信）
  ≤ 1/3 → 红线 → 停手要时辰
```

### 升级后（加入相位反演）

```
R0 + R1 + R2 命中率
   ↓
  ≥ 4/6 → 进入出图（happy path）
  ≤ 2/6 → 【P1-7 触发：相位反演校验循环】（不再直接停手）
       ↓
       (a) 枚举 4 类相位反演候选 → 逐个重判命局
       (b) 不重新问用户，复用 R0/R1 答案与候选重新匹配
       (c) 找命中率最高的相位
       ↓
       命中率最高的相位 ≥ 4/6 → 写 confirmed_facts.structural_corrections
                                → score_curves --override-phase 重跑
                                → 重新出图（带「相位已反演」标记）
       所有相位 < 4/6 → 此时才真正判"八字错 / 时辰错"
```

---

## 3. 4 类相位反演的学理依据 + 检测条件

### P1 · 日主虚浮反演（弃命从势）

**学理**：《滴天髓·从象》"从象不一而足，要在审其轻重，察其向背"。日主太弱无根可借时，命局气势从旺神而走，不可逆推扶身。

**检测条件**（`detect_floating_day_master`）：

| 条件 | 阈值 | 备注 |
|---|---|---|
| 日主同党分数（same + sheng） | ≤ 2.0 | 几乎无根 |
| 月令是否生扶日主 | False | 月令克 / 泄日主 |
| 日支是否日主同党 | False | 配偶宫不护身 |
| 全局是否有印 | False（或印被合化）| 没救兵 |
| 旺神（最强非日主五行）总分 | ≥ 12 | 旺神成势 |

满足 4 / 5 → 日主虚浮，触发反演候选：从财 / 从杀 / 从儿 / 从印（按旺神是哪类十神决定）

### P2 · 旺神得令反主事

**学理**：《穷通宝鉴·总论》"看命之法，先看月令为提纲，提纲所司为命主之主气"。月令旺神簇拥时，财 / 杀 才是命局主角，日主只是承接者。

**检测条件**（`detect_dominating_god`）：

| 条件 | 阈值 |
|---|---|
| 月令旺神（非日主同党）权重 | ≥ 月令权重总分的 65% |
| 旺神在天干透出 | True（透干 = 主事力强）|
| 旺神是否得到生扶 | True（被生 / 被合）|
| 旺神 vs 日主同党比 | ≥ 2.0 |

满足 3 / 4 → 旺神得令，触发反演候选：以旺神所属十神为主事星重新生成 baseline

### P3 · 调候反向（外燥内湿 / 上燥下寒）

**学理**：《穷通宝鉴·四时调候》调候不仅看月令，还要看 "干头 vs 地支" 的对冲。当前 `climate_profile` 已经识别"外燥内湿"等极端对冲，但**没有反演到主事星 / 用神层面**。

**检测条件**（`detect_climate_inversion`）：

| 条件 | 阈值 |
|---|---|
| climate.label ∈ {"外燥内湿", "外湿内燥"} | True |
| 干头分 vs 地支分 符号相反且绝对值都 ≥ 4 | True |
| 默认用神方向跟干头主导方向一致（默认看了表象）| True |

满足 2 / 3 → 调候反向，触发反演：用神 = 制干头那一方（外燥内湿 → 用水制丙丁，不是用火助燥）

> **跟现有逻辑的区别**：`select_yongshen` 已经在 climate.label = 外燥内湿 时把用神改为水，但**没有把这个改写传播到 `apply_geju_override` 之后**。如果格局识别又把用神改回火，调候反向就被吃掉了。本协议要求 `--override-phase climate_inverted` 强制锁定调候用神。

### P4 · 假从 / 真从边界（v7.1 重写）

**学理**：《子平真诠·从化篇》"凡格局有真有假，真者从化无碍，假者似从而非"。
- **真从** = 日主完全无救（无印 / 无比劫通根 / 时柱也无帮扶）→ 完全顺旺神走
- **假从** = 日主有印护身或时柱比劫帮扶 → 顺势从财杀但能保全自身

**检测条件**（`detect_pseudo_following`，v7.1）：

判断 `has_self_help`：满足任一即为"假从"，全不满足即为"真从"
- `bijie_grounded`：地支主气有同党
- `yin_grounded`：天干有印 + 地支主气有"生我"五行
- `shi_zuo_yin`：时干印 + 时支自坐印根
- `shi_zuo_bijie`：时干同党 + 时支支撑

**触发**：日主 support ≤ 5.5（边界）OR 比劫不通根且 support ≤ 5.5
**kind 区分**：has_self_help = True → `pseudo_following`；False → `true_following`

> v7 旧版只看日支主气一个字段，导致 1996 case `丙子庚子己卯己巳` 被判反为"真从"
> （日支卯木非同党 → 旧 has_root=False → 真从），实际 LLM 诊断是"假从财格"
> （时柱己巳 → 时干同党 + 时支巳藏丙印有根 → 应判假从）。v7.1 改为综合 4 字段判断。

### P5 · 三气成象 / 财官印连环（v7.1 新增）

**学理**：《滴天髓·体用篇》"流通生化，体用相宜"、《穷通宝鉴》气机论。当日主弱 + 命局存在「财生官 + 官生印 + 印生身」或「食伤生财 + 财生官」等"三气流通"结构，命局主旋律不是"日主主导"而是"流通方向 = 主事"。

**检测条件**（`detect_three_qi_cheng_xiang`）：

| 条件 | 阈值 |
|---|---|
| `cond_1` | 至少 2 个非日主五行 ≥ 3 分（说明气机流通成势）|
| `cond_2` | 最强两个非日主五行总和 ≥ 8（成势）|
| `cond_3` | **日主真弱** = label='弱' AND score ≤ -20 AND 比劫不通根（**强制 AND，防中和命误报**）|
| `has_chain` | 存在连环生化链（A→B→C 或 A→B→日主）（**强制要求**，确保是流通而非杂乱多神）|

**触发**：4 个条件**全部满足**才触发（防误报）。

**suggested_phase** = `floating_dms_to_cong_<最强非日主五行所属十神>`，例如：
- 最强 = 财（水）→ `floating_dms_to_cong_cai`
- 最强 = 官杀（木）→ `floating_dms_to_cong_sha`
- 最强 = 食伤（金）→ `floating_dms_to_cong_er`
- 最强 = 印（火）→ `floating_dms_to_cong_yin`

**与 P1 的关系**：
- **P1** 处理"单一旺神 ≥ 8 分"主导的简单场景
- **P5** 处理"≥ 2 个非日主五行成势 + 流通生化"的复杂场景（P1 漏掉的 case）
- **回归测试**：guan_yin_xiang_sheng（强身）+ shang_guan_sheng_cai（中和）→ P5 不触发（cond_3 = False）
- **正例**：1996 `丙子庚子己卯己巳` → P5 4/4 全触发 → suggested_phase = `floating_dms_to_cong_cai`，跟 LLM 人肉诊断的"假从财格 / 财官印三气成象"完全一致

> P5 是从一个真实失败 case study 反推出来的（详见 §11 v7.1 升级记录）。

---

## 4. 相位反演的工程实现（v7 MVP）

### 4.1 `_bazi_core.py` 新增 4 个 detect 函数

```python
def detect_floating_day_master(pillars, strength) -> dict:
    """P1 · 日主虚浮检测，返回 {triggered, score, suggested_phase, evidence}。"""

def detect_dominating_god(pillars, strength) -> dict:
    """P2 · 旺神得令检测，返回 {triggered, dominating_wuxing, dominating_shishen, ...}。"""

def detect_climate_inversion(pillars, climate) -> dict:
    """P3 · 调候反向检测，返回 {triggered, current_yongshen, suggested_yongshen, ...}。"""

def detect_pseudo_following(pillars, strength) -> dict:
    """P4 · 假从 / 真从边界检测，返回 {triggered, kind: 'true' | 'pseudo', ...}。"""

def detect_all_phase_candidates(bazi) -> list[dict]:
    """跑全部 4 类 detect，按 confidence 降序返回候选列表。"""
```

### 4.2 `score_curves.py` 新增 `--override-phase` 参数

```bash
# 用法
python scripts/score_curves.py \
  --bazi output/bazi.json \
  --override-phase floating_dms_to_cong_cai \  # 反演为"从财格"
  --out output/curves_phase_inverted.json

# 可选 phase 列表（每个对应一组 structural_corrections）
phase 选项                         描述
--------------------------------- ---------------------------------------
day_master_dominant               默认（不反演）
floating_dms_to_cong_cai          日主虚浮 → 从财格
floating_dms_to_cong_sha          日主虚浮 → 从杀格
floating_dms_to_cong_er           日主虚浮 → 从儿格（食伤）
floating_dms_to_cong_yin          日主虚浮 → 从印格
dominating_god_cai_zuo_zhu        旺神得令·财星主事
dominating_god_guan_zuo_zhu       旺神得令·官杀主事
climate_inversion_dry_top         调候反向·上燥下寒（用神锁水）
climate_inversion_wet_top         调候反向·上湿下燥（用神锁火）
true_following                    真从格（日主根被破）
pseudo_following                  假从格（日主有微根，仍扶身但加 caveat）
```

每个 `--override-phase` 对应一组写入 `bazi` 的 patch：

```json
// 例：floating_dms_to_cong_cai
{
  "strength.label": "强",  // 反演：从财格按"强"读
  "strength.score": 30,
  "yongshen.yongshen": "财（按从神）",
  "yongshen._phase_override": "floating_dms_to_cong_cai",
  "phase": {
    "primary": "弃命从财",
    "main_actor": "财星",
    "day_master_role": "从神 / 配角"
  }
}
```

### 4.3 `handshake.py` 新增 `evaluate_responses_with_phase_search`

```python
def evaluate_responses_with_phase_search(
    bazi: dict,
    handshake_candidates: dict,
    user_responses: list[dict],
) -> dict:
    """
    1. 计算默认相位的命中率
    2. 如果 ≥ 4/6 → 直接返回（不需反演）
    3. 如果 ≤ 2/6 → 跑 detect_all_phase_candidates(bazi)
    4. 对每个 phase candidate：
       - 复用 bazi + override_phase 重新计算 R0/R1 候选
       - 用原 R0/R1 用户答案匹配新候选 → 算新命中率
    5. 选命中率最高的 phase
    6. 返回 {
        "default_phase_hit_rate": 2/6,
        "best_inverted_phase": "floating_dms_to_cong_cai",
        "best_inverted_hit_rate": 5/6,
        "should_rerun_with_phase": "floating_dms_to_cong_cai",
        "rerun_command": "python scripts/score_curves.py --bazi ... --override-phase floating_dms_to_cong_cai ...",
        "structural_corrections_to_save": [...]
      }
    """
```

### 4.4 SKILL.md 工作流插入 Step 2.6

```
Step 2.5  R0+R1+R2 校验
   ↓
   命中率 ≥ 4/6 → 跳过 Step 2.6，直接进 Step 3
   命中率 ≤ 2/6 → 进入 Step 2.6 ↓
Step 2.6  【P1-7 相位反演校验循环】
   - handshake.py 自动 dump 4 类相位候选
   - LLM 收到 dump → 跟用户说："命中率低，但我有 N 个反向假设可以试，要不要试 [候选 X]？"
   - 用户 OK → 跑 score_curves --override-phase X → 重新生成 R0/R1 候选 → 重新问用户 → 命中率跳升 → 进 Step 3
   - 用户拒绝 / 所有候选都 < 4/6 → 此时才停手要时辰
   ↓
Step 3   出图 / 解读（带「相位已反演」标记）
```

---

## 5. LLM 在 Step 2.6 的强制话术

LLM 在 R 命中率 ≤ 2/6 时**必须**做的事：

### 5.1 不允许直接说"八字错了"

❌ **禁止**：
- "命中率太低，可能你时辰记错了"（一上来就归罪用户）
- "你确认下八字对不对？"（懒惰回避）

### 5.2 必须先说反向假设

✅ **强制**模板：

> 命中率比较低（X/6），但这**不一定意味着**八字错。常见的另一种可能是「**算法的读法方向反了**」。
>
> 我已经跑了 4 类反向假设，按命中率匹配度排序，最有希望的是：
> - **候选 1**: [候选名称] · 假设你的命局是 [简短描述] · 复用你刚才的回答匹配，命中率 = [X/6]
> - **候选 2**: [候选名称] · ...
>
> 我建议先试候选 1。这意味着我会用 `--override-phase [phase_id]` 重跑曲线，**完全免费**——如果重跑后命中率还低，那时再判时辰错。
>
> 要不要试？

### 5.3 重跑后必须明确告知"已反演"

✅ **强制**模板：

> 已经按 [候选名称] 重跑。这次命中率 = [Y/6]（vs 默认 X/6），跳升 [Z 个百分点]。
>
> 这意味着你的命局的正确读法是「**[新相位的命理学描述]**」，而不是默认的「**[默认相位]**」。
>
> 接下来的曲线和分析都是在新相位下生成的。出图后第一段我会再次明确这点，避免你按"默认相位"的语义去理解。

---

## 6. 跟现有保护机制的关系

| 现有机制 | 跟相位反演的关系 |
|---|---|
| `apply_geju_override`（v3）| 处理"明显格局" → 修用神。**不处理"反相位"**——格局派只在"看月令就能识别"时生效。本协议补的是"格局派识别失败但实际是反相位"的边缘场景 |
| `apply_structural_corrections`（Documents 版有，v7 .claude 版尚未实现） | 接受用户已确认的纠错。本协议把"相位反演"作为一种新的 `structural_correction.kind`，写回 confirmed_facts.json |
| `climate_profile`（v2）| 识别"外燥内湿"等对冲，已修用神。本协议保证这个修法**不被后续 geju override 覆盖回去**（加 `_phase_locked` 标记）|
| `_yongshen_reverse_check` | 校验单个用神是否在原局可用。本协议在更高层级校验"整个相位"是否在 R0/R1 上可证伪 |

---

## 7. 边界 / 限制

### 7.1 本协议不解决什么

- ❌ 不解决"八字真的错了"——只是把"算法读反"先排除掉
- ❌ 不能识别神煞 / 化气格 / 反吟伏吟应期等更高阶情况（deferred）
- ❌ 不能完全自动化（用户必须确认相位反演）—— 因为 R0/R1 用户答案本身可能有偏差

### 7.2 警告信号

- 如果 4 个 phase candidate 命中率都很接近（差 ≤ 1） → 不可信，应回退到默认相位 + 加 caveat
- 如果某个 phase candidate 命中率突然 = 6/6（完美匹配）→ 可疑，可能用户在迎合，应做一道交叉验证

### 7.3 数据回流

每次成功的相位反演必须写回 `confirmed_facts.structural_corrections` 一组结构化纠错：

```json
{
  "kind": "phase_override",
  "value": "floating_dms_to_cong_cai",
  "evidence": {
    "default_phase_hit_rate": "2/6",
    "inverted_phase_hit_rate": "5/6",
    "swing": "+50%",
    "detect_evidence": {
      "day_master_root": 1.5,
      "dominating_wuxing": "火",
      "dominating_score": 14
    }
  },
  "reason": "P1 日主虚浮 + P2 旺神得令同时触发，反演为从财格后命中率跳升 50%"
}
```

下次跑同一个 `bazi_key` → Step 0 自动加载，跳过相位反演，直接用 override 跑。

---

## 8. 跟 fairness_protocol 的关系

相位反演**不**违反 fairness_protocol：

- `--override-phase` 不接受身份字段，只接受机器可枚举的 phase ID
- R0/R1 用户答案是匿名的（trait / health / event 文本），不含姓名 / 职业 / 关系
- 反演后的 baseline / dayun / liunian 计算逻辑跟默认相位完全相同（只是输入的 strength.label / yongshen 不同）

唯一例外：相位反演后**确实**会改写 spirit / wealth / fame 的 baseline（比如从财格的 wealth baseline 会重新算）。这是**必要的**——如果不改写，反演就没意义。

---

## 9. 落地时间表（v7+）

| 阶段 | 内容 | 状态 |
|---|---|---|
| **v7 MVP** | 协议文档 + 4 个 detect (P1-P4) + score_curves --override-phase + handshake dump 候选 + LLM 话术强制 | ✓ |
| **v7.1 增补** | 重写 P1（看比劫 / 印通根而非点数）+ 重写 P4（综合判 has_self_help）+ 新增 P5（三气成象）| ✓ |
| **v8 Auto-Loop** | handshake 自动调用 score_curves 重跑 + 用户一句话确认即落地 | deferred |
| **v9 Calibration** | 相位反演的命中率历史回测 + 每类 phase 的假阳率 / 假阴率 | deferred |
| **v10 Multi-Phase Ensemble** | 不强制选一个相位，对前 2 个相位都跑曲线并叠加置信带 | deferred |

---

## 11. v7.1 升级记录 · 真实失败 case 反推增补

### 11.1 触发本次升级的 case

某用户 1996 八字 `丙子 庚子 己卯 己巳`（同 §0 的 case）：

**v7 MVP 的诊断结果**：
- ✅ P3 调候反向 3/3 触发 → `climate_inversion_dry_top`（用神锁水）
- ⚠️ P4 真从格触发 → `true_following`（**方向判反了**——LLM 实际诊断为"假从财"）
- ❌ P1 日主虚浮 2/5 不触发（漏掉 floating_dms_to_cong_cai）
- ❌ P2 旺神得令 1/4 不触发

**LLM 人肉诊断**（凭经验）：「**假从财格 / 财官印三气成象**」+「**上燥下寒**」

**对比**：v7 MVP 命中 1/3 关键相位，方向判反 1 个，漏掉 1 个最核心的。

### 11.2 v7.1 修复 3 个 bug

| Bug | v7 MVP 错在哪 | v7.1 修复 |
|---|---|---|
| **P1 阈值过严** | `support ≤ 2` 把 1996 case 的 support=4.6 排除；`无印` 是死条件，把"假从有印"全排除 | 改为「比劫不通根（看地支主气）」+「印不通根（看印是否有支撑）」；旺神阈值 12 → 8 |
| **P4 has_root 判断不全** | 只看日支主气一个字段，忽略时柱印根 / 时柱比劫自坐 | 综合 4 字段 `has_self_help = bijie_grounded OR yin_grounded OR shi_zuo_yin OR shi_zuo_bijie`，让"假从有印"被正确识别 |
| **缺 P5 三气成象 detect** | 没有处理"≥ 2 个非日主五行成势 + 流通生化"的复杂场景 | 新增 P5，强制要求 4 条件全满足（含连环生化），1996 触发 4/4 |

### 11.3 v7.1 后的 1996 case 输出

```
$ python scripts/handshake.py --bazi /tmp/.../bazi.json --dump-phase-candidates
[handshake] phase-dump: 3 个相位反演候选 ↓
  · climate_inversion_dry_top (P3, 3/3)  → 调候反向·上燥下寒（用神锁水）
  · pseudo_following          (P4)        → 假从格 · 日主有印 / 时柱帮扶
  · floating_dms_to_cong_cai  (P5, 4/4)  → 三气成象·财(水)为主神 · 含连环生化
```

→ 跟 LLM 人肉诊断的 3 项关键结论**完全一致**。

### 11.4 防误报回归测试

| 命局 | strength | 期望 | v7.1 实际 |
|---|---|---|---|
| `guan_yin_xiang_sheng`（官印相生标准命）| 强 +28 | 不应触发任何反演 | ✓ 0 candidates |
| `shang_guan_sheng_cai`（伤官生财标准命）| 中和 +12 | 不应触发任何反演 | ✓ 0 candidates |
| `1996 丙子庚子己卯己巳`（边缘 case）| 弱 -30 | 至少触发 P3 + P5 | ✓ 3 candidates，方向准确 |

**P5 cond_3 的 3-AND 设计是关键防线**：必须同时满足 `label='弱' AND score≤-20 AND 比劫不通根`。中和命和强命都会被这一条挡住。

---

## 10. 检查清单（每次跑相位反演前）

- [ ] 默认相位的 R0+R1+R2 命中率 ≤ 2/6（满足触发条件）
- [ ] `detect_all_phase_candidates` 返回了至少 1 个候选
- [ ] 候选命中率 ≥ 4/6（达标）
- [ ] 候选命中率比默认相位**至少**高 2 个绝对值（避免噪音）
- [ ] 用户已知情同意"我们要用反演相位重跑"
- [ ] 重跑后第一段输出明确告知"已反演到 [phase]"
- [ ] confirmed_facts 已写入 `kind: phase_override`

任意一条 NO → 不允许进入相位反演重跑。
