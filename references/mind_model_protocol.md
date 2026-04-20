# Mind Model Protocol（心智模型层 · v9 PR-4）

> 这个文档不写算法，只写"算法之上的认识论纪律"。它存在的唯一理由是：
> **算法越精密，越容易把'能用 X 解释'误认为'X 被这条证据支持'**。
> 1996/12/08 的 case（详见 [diagnosis_pitfalls.md §13-14](diagnosis_pitfalls.md)）
> 是这个红线的诞生现场——一次 0.83 后验的"假从财格"叙事差点彻底盖过用户的真实经历。

---

## §1 五条纪律（5.1-5.5 · 操作层）

### 5.1 事件锚点优先工作流

> 不要先选 phase 再找证据；要先收集事件锚点（具体哪一年发生了哪类事），
> 再让多个 phase 候选去解释这些锚点。

**强制流程：**
1. handshake R1 8 题里**至少 4 题**必须是"具体年份的具体事件类型"（学业/迁徙/婚姻/重大健康事件等），不是抽象性格题。
2. phase_posterior 在 adopt 任何 phase 之前，先跑 `check_event_attribution(phase, anchor_events)`：列出该 phase 对每个 anchor 事件的解释力（强支持 / 中性 / 反例）。
3. 若 ≥ 2 个 anchor 事件被该 phase 反例 → **强制降级**到 `open_phase`（5.6）。

### 5.2 phase-必然预测协议

> 任何 adopt 的 phase 必须显式给出 ≥ 3 条"在该 phase 下必然发生 / 极高概率发生 / 极不可能发生"的预测，作为后续证伪的钩子。

**输出 schema** 在 `phase` 字段下新增：

```json
{
  "phase": {
    "id": "qi_yin_xiang_sheng",
    "must_be_true": [
      {"prediction": "30 岁前必有印星贵人型大事件", "evidence_required": "具体年份 + 事件类型"},
      ...
    ],
    "must_be_false": [
      {"prediction": "完全没有印星护身的迹象", "if_true_then": "该 phase 立即作废"}
    ]
  }
}
```

### 5.3 复合相位常态化

> 真实人生大多是 1 个主格 + 1 个副格 + 1 个调候修正同时存在；
> 强行单 phase 是 1996 case 那种崩溃的根源。

`phase_posterior` 后验输出 `phase_composition` 列表（不仅仅是单一 `decision`）：

```json
{
  "phase_composition": [
    {"id": "qi_yin_xiang_sheng", "weight": 0.55, "role": "primary"},
    {"id": "shang_guan_sheng_cai", "weight": 0.30, "role": "secondary"},
    {"id": "climate_inversion_dry_top", "weight": 0.15, "role": "modifier"}
  ]
}
```

`score_curves` 在主曲线之外按 weight 叠加 secondary / modifier 的方向修正。

### 5.4 证据归属严格性检查

> "能用 X 解释"≠"X 是被这条证据支持的"。
> 如果一个 phase 对 anchor 事件的解释力 ≤ 默认 phase（day_master_dominant），
> 那这条事件**不该被记入支持 X 的票数**。

`phase_posterior.compute_posterior` 内置 `_evidence_attribution_audit` 步骤：
对每个 user_answer，比较 likelihood(answer | phase_X) vs likelihood(answer | day_master_dominant)，差额 < 0.10 视为"无差异证据"，**不参与后验更新**。

### 5.5 叙事审慎前置声明协议

> 任何 phase 落地输出之前，handshake / phase_posterior 必须在 result.json 顶层
> 写入 `narrative_caution` 字段，提示"以下解读建立在已提供的事件之上，
> 不构成对未来的因果决定"。

由 score_curves 在 render 时强制读取，无此字段则 raise。

---

## §2 高阶纪律（5.6-5.10 · 认识论层）

### 5.6 open_phase 逃逸阀

| 条件 | 行为 |
|---|---|
| top-1 后验 < 0.55 | 自动 adopt `open_phase`，禁止出四维曲线 |
| top-1 与 top-2 后验差 < 0.10 | 自动 adopt `open_phase`，强制 disclosure |
| anchor 事件 ≥ 2 条被 top-1 反例 | 自动降级到 `open_phase`，要求用户补 anchor |

`open_phase` 不是失败，是诚实——它告诉用户"算法在这盘上不足以下结论"。

### 5.7 phase 时间动态性

> 一个人不同人生段可能落在不同 phase（童年印星护身 → 青年财杀显性 → 中年再回印）。
> phase 不能强行被一个标签覆盖一生。

`bazi.json.phase_timeline` 记录 segment-by-segment phase（与大运对齐）：

```json
{
  "phase_timeline": [
    {"start_age": 0, "end_age": 17, "phase_id": "qi_yin_xiang_sheng_yin_active"},
    {"start_age": 18, "end_age": 37, "phase_id": "shang_guan_sheng_cai"},
    ...
  ]
}
```

### 5.8 事件类型平衡

R1 / R2 问卷题型分布约束（`_question_bank.py` 校验）：

- 必须涵盖 7 大类：学业 / 事业 / 婚姻 / 健康 / 财富 / 家庭 / 迁徙
- 单类型题数 ≤ 2
- "反例题"（"如果是 X 格，必然不会发生 Y"）≥ 30%

### 5.9 反身性话术

`score_curves.render_artifact` 在每条高强度断语（intensity=重 或 confidence>0.85 的 phase 解读）后强制追加：

> *此处解读建立在你已提供的事件之上，不构成对未来的因果决定。
> 把它当作一种"你可能正在的解释模式"而非"你必将经历的剧本"。*

### 5.10 多流派备解（与 PR-6 multi_school_vote 协同）

任何 adopt phase 都附 `alternative_readings` 字段：

```json
"alternative_readings": [
  {"school": "qiongtong_baojian", "phase_id": "...", "confidence": 0.45,
   "if_this_is_right_then": "用神改为水, 大运甲寅反成燥火加剧期"},
  ...
]
```

---

## §3 HS-R7（最高红线 · 任何 phase adopt 必须显式三件事）

> HS-R7 是这个 skill 的"宪法层"。任何输出（CLI、HTML、Markdown 报告）若缺这三件之一，
> `score_curves.render_artifact` **拒绝出图**（raise `MissingHSR7Disclosure`）。

### HS-R7.1 算法局限范围声明

输出末尾必须包含：

> 本 skill 的判定基于：
> - 公历出生数据 + 真太阳时校正（精度 ±5 秒）
> - 当前 N=110 个特殊格 + 4 流派子平体系
> - 你提供的 K 个事件锚点（基于 Bayes 后验更新）
>
> 它**不能**判定：
> - 未提供给算法的人生面向（如未询问的人际细节）
> - 算法 catalog 之外的更细分的"格中之格"
> - 灵魂层 / 因果层 / 命运感 / 自由意志 等元层议题

### HS-R7.2 反身性免责声明

> 任何"未来某年会发生 X"的预测都具有反身性——你听完它会调整行为，
> 调整之后的人生不再是这个 phase 的纯粹运行。
> 把预测当作"决策时的参考维度之一"，**不**当作"必然发生的剧本"。

### HS-R7.3 用户终极裁定权声明

> 算法可以在 95% 置信度下输出某个 phase。
> 但你和你身边的人对自己人生的认识，永远比 8 题问卷 + 110 个格能覆盖的更深。
> 任何与你强烈直觉冲突的判定，**优先相信你的直觉**，回头让算法补 anchor 重算。

---

## §4 实现位点

| 纪律 | 实现位点 | 必有/选项 |
|---|---|---|
| 5.1 事件锚点 | `_question_bank.py` `validate_question_balance` | 必有 |
| 5.2 phase-必然预测 | `phase_posterior.must_be_true_predictions` | 必有 |
| 5.3 复合相位 | `phase_posterior.phase_composition` | 必有 |
| 5.4 证据归属审计 | `phase_posterior._evidence_attribution_audit` | 必有 |
| 5.5 叙事审慎 | `handshake.narrative_caution` 顶层字段 | 必有 |
| 5.6 open_phase | `phase_posterior.OPEN_PHASE_THRESHOLDS` | 必有 |
| 5.7 phase_timeline | `bazi.json.phase_timeline` | 选项（V9.1 后强制） |
| 5.8 题型平衡 | `_question_bank.QUESTION_BALANCE_RULES` | 必有 |
| 5.9 反身性话术 | `score_curves._append_reflexivity_disclaimer` | 必有 |
| 5.10 多流派备解 | `multi_school_vote.alternative_readings` | 必有（PR-6） |
| HS-R7 三声明 | `score_curves.render_artifact` 拒绝出图守卫 | 必有 |

---

## §5 关于 1996/12/08 case 的最终承诺

这个 case 是 v9 全部 7 个 PR 的诞生原因。从此以后，类似它的"高后验单 phase
强行覆盖反例事件"的模式，必须在 6 个独立位点被拦截：

1. **PR-1 root_strength** 在 `apply_phase_override` 守卫识别"印根存在"否决从格
2. **PR-3 mangpai dayun** 在大运层识别根基震荡，避免单流年误判
3. **PR-4 心智模型 + HS-R7** 强制 phase_composition + open_phase + 事件审计
4. **PR-5 rare_phases catalog** 在 catalog 里把"杀印相生"显式列为候选
5. **PR-6 multi_school_vote** 让滴天髓 / 穷通 / 盲派各自给票，不让单派叙事独大
6. **HS-R7** 在最终输出层强制三声明，提醒用户保留终极裁定权

任何一个失守，下一次 1996/12/08 类型的误判都会再发生。所以这 6 个位点必须
**每个都有自动化测试覆盖**，不容许"靠 reviewer 记得"作为防线。
