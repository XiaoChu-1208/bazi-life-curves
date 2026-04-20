---
name: bazi-life-curves
description: >-
  根据八字（或公历生辰）生成可调时间区段的「人生曲线图」+ 一生四维度评价 + 大运评价 + 关键年份大白话解读；
  也支持「合盘」—— 用户提供 ≥ 2 份八字，从合作 / 婚配 / 友谊 / 家人 4 个维度做兼容性分析。
  **v6 升级 + v7 现代化**：曲线覆盖 4 维度——精神舒畅度 / 财富 / 名声 / **关系能量**（v6 新增 · v7 重命名「感情→关系能量」+ 加 `--orientation` 取向参数支持 LGBTQ+ / 不婚），每维 2 条曲线（粗实线=当年值为主线，细虚线=5 年区段趋势为辅）= 8 条线。
  关系能量维度走**独立通道**（不参与三派融合，从配偶星 / 配偶宫 / 比劫 / 桃花 / 大运冲合单独打分），与 R0 反询问·关系画像配套。
  **v7 现代化**删除了所有"克夫 / 旺夫 / 配偶星弱减分 / 女命印多减分 / 女命食伤减分 / 男命比劫扣分高于女命"等带性别歧视和价值判断的古法规则，emotion 高 ≠ 婚姻顺利、emotion 低 ≠ 单身差，纯中性描述。详见 fairness_protocol.md §9-§10。
  采用「格局为先 + 三派交叉打分」（格局派识别主格局优先覆盖用神 → 扶抑 / 调候 / 格局再融合）+ 盲派事件断 + 烈度修正
  + 印化护身后处理（杀印相生 / 伤官见官印护 自动减压）+ 历史回测 + 置信带，保证准确、公正、可证伪。
  **v7.4 新增**：①「化气格」自动识别（甲己 / 乙庚 / 丙辛 / 丁壬 / 戊癸 五合得月令 + 化神有根 + 无破格 → 日主借合化易主，扶抑全部翻转）；
  ② 神煞分布检测（天乙贵人 / 文昌 / 驿马 / 桃花 / 华盖 / 孤辰 / 寡宿 / 空亡），命中原局 → 终生 baseline 微调（±0.3~0.4），
  大运 / 流年逢 → 当年微调（±0.5~1.0）+ 驿马触发 sigma × 1.3（波动加大）；神煞影响刻意小，只调味，不参与主格局判定；
  ③ R0 反迎合·反向探针（counter-claim probes）—— 给每条 R0 推论再附一条**完全相反**的 claim，
  两个相反命题都答「对」→ 自动判定 sycophantic，R0 命中率 × 0.5 打折；
  原命题答「不对」+ 反向命题答「对」→ 判定 mirror，建议触发相位反演重跑。
  感情维度走**独立通道**（不参与三派融合，从配偶星 / 配偶宫 / 比劫 / 桃花 / 大运冲合单独打分），与 R0 反询问·感情画像配套。
  盲派不进 25% 融合权重，仅做应事断 + 烈度修正（详见 references/mangpai_protocol.md）。
  合盘（he_pan.py）用 4 层结构性评分：五行互补 + 干支互动（合冲害 / 三合 / 桃花 / 贵人） + 十神互配（按关系类型）+ 大运同步度。
  起运岁优先用 lunar-python 精算（gregorian 模式自动），pillars 模式可通过 `--qiyun-age` 显式指定。
  用户可指定评分年龄区间和拐点预测窗口；三派分歧大的年份合并进关键年份评价，由 LLM 综合命局做有论据的解读。
  **出图 / 合盘前会做三阶段校验**：
    · **R0 反询问·感情画像**（v6 新增 · 2 题：偏好类型 + 对方态度）—— 主动抛给用户的"反询问窗口"，
 用于校准八字大致对/不对 + 协助判断该走格局派 / 扶抑派 / 调候派
 · **R1 健康三问**（寒热 / 睡眠精力 / 脏腑短板）—— 命局结构准确度
 · **R2 交叉验证**（仅 R1 < 3/3 时触发）—— 本性 + 历史锚点
 · **R3 反询问·原生家庭画像**（v7.3 新增 · 条件触发 · 2 题：①整体家庭结构 5 档分类 + ②父母存在模式合并）
 —— 仅在用户主动问家庭/父母时抛；正交于 R0/R1/R2（不算命局准确度）；
 用于决定 family 段写不写 / 怎么写，**修古法 survivorship bias 把普通家庭推成"显赫"的 systemic bug**
 放行（R0+R1+R2）：R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6）；R0=0 + R1≤1 → 八字大概率不准（请核对性别 / 时辰）。
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
2. **合盘**：用户输入 ≥ 2 份八字 + 关系类型（合作 / 婚配 / 友谊 / 家人），脚本算出 4 层结构性评分（五行互补 + 干支互动 + 十神互配 + 大运同步度），LLM 在对话里给出"亮点 + 摩擦点 + 怎么用 / 怎么避"的人话解读。**整体动作逻辑与单盘一致：先 R0 反询问 + R1 健康三问校验，再做合盘评分。**

## 用户视角速览（先告诉用户怎么用）

如果用户问 "怎么用 / 怎么触发 / 怎么开始"，请先把 `USAGE.md` 第一节"30 秒速览"完整复述给用户，然后等待用户给出八字 / 生辰。完整用户文档在 `USAGE.md`。

**关键三句话告诉用户**：

1. 你只要丢一句话给我：
   - **单盘**：八字四柱 + 性别 + 出生年，或公历生辰 + 性别
   - **合盘**：≥ 2 份八字 + 关系类型（合作 / 婚配 / 友谊 / 家人，可选）
   剩下我全自动跑。
2. **出图 / 合盘前**我会做三阶段校验（v6 加 R0 反询问）：
   - **Round 0 = 反询问·感情画像**（v6 新增 · 2 题：偏好类型 + 对方态度）—— 我主动抛给你，凭直觉答即可，用来快速校准八字大致对/不对 + 该按哪种取向（格局 / 扶抑 / 调候）解
   - **Round 1 = 三个不同侧面的健康问题**（寒热体感 / 睡眠精力 / 易病脏腑），用「命中率」定准确度：
     - 3/3 命中 → 直接进入下一步
     - 2/3 → 我再追 3 条交叉验证（R1+R2 ≥ 4/6 才放行 + 加 caveat）
     - ≤ 1/3 → 八字十有八九不准，请核对出生时辰
   - **整体放行条件**：R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6）；R0 = 0/2 且 R1 ≤ 1/3 → 大概率性别 / 时辰错了，请复核
   - 合盘场景下**每份八字都要单独跑 R1**（R0 仅对你自己跑，因为对方的感情史你未必清楚）
3. 出图是交互式 HTML：曲线 + **整图综合分析** + **一生四维度评价**（精神 / 财富 / 名声 / **感情**）+ **大运评价（含感情看点）** + **关键年份评价**；
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

### 0. 概览：十步流程（v3 更新，v4 加合盘分支，v5 加流式输出 + 输出格式选择，v6 加 R0 反询问 + 感情维度）

```
Step 0  加载 confirmed_facts.json（如已存在 → 跳过已确认 trait + 应用结构性纠错）
Step 1  解析八字（含起运岁精算 / 用户指定）—— 单盘 1 份 / 合盘 ≥ 2 份
  → Step 2 格局识别 + 三派打分（扶抑 / 调候 / 格局）+ 印化护身后处理 + 燥湿覆盖
  → Step 2a 盲派事件检测 → 应事断 + 烈度修正 + **结构反向规则**（v3 P1）
  → Step 2b 融合 + 烈度修正（盲派不进 25% 权重；反向后的 events 直接影响曲线）
  → Step 2c **感情维度独立打分**（v6 新增）：emotion_baseline + emotion_dayun_delta + emotion_liunian_delta；
            不参与三派融合，单走一条通道，保证 spirit/wealth/fame 历史回测精度不变
  → Step 2.5 下马威校验（硬门槛 · v6 三阶段 · v7.3 加 R3 条件触发）
            **Round 0**（v6 新增 · 反询问·感情画像 2 题）：
                ① 偏好类型（基于配偶星五行 + 配偶宫藏干十神）
                ② 对方态度（基于配偶星旺衰 + 比劫 + 食伤 + 印 + 桃花综合）
                作用：取向校准（八字大致对/不对 + 是否走格局派 / 扶抑派 / 调候派）
                R0 = 0/2 → 配偶星 / 配偶宫读法可能反了，提示用户复核性别 / 时辰
            **Round 1**（健康三问）：寒热 / 睡眠精力 / 脏腑短板，命中率定命局准确度
            **Round 2**（仅 R1 < 3/3 时触发）：本性 + 历史锚点
            **Round 3**（v7.3 新增 · **条件触发** · 反询问·原生家庭画像 2 题）：
                ① 整体家庭结构（5 档：显赫/中产/普通/波折/缺位 候选）
                ② 父母存在模式合并（父亲贴近/偏远/高压/缺位 + 母亲同上）
                作用：family 段写不写 / 怎么写。**正交于 R0/R1/R2，不算入命局准确度**
                **触发条件**：仅在用户主动问"家庭/父母/出身"等关键词时抛 R3
                R3 = 0/2 → family 段不展开（命局对家庭的读法可能反了）
            放行（R0+R1+R2）：R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6）
            合盘场景：R0 仅对自己跑（对方感情史你未必清楚）；R1 双方都跑；R3 跟单盘一样按需触发
  → Step 2.55 【v7 强制】R0+R1+R2 ≤ 2/6 时 → 相位反演校验循环（P1-7）
            handshake.py --dump-phase-candidates 输出 4 类相位反演候选
                ① 日主虚浮（弃命从财/杀/儿/印）
                ② 旺神得令反主事（财/杀/食伤/印当家）
                ③ 调候反向（外燥内湿 / 上燥下寒）
                ④ 假从 / 真从边界
            LLM 跟用户讲"算法可能读反了" → 用户同意 → score_curves --override-phase X 重跑
                → 重跑后命中率 ≥ 4/6 → 写 confirmed_facts.phase_override → 进 Step 3
                → 全部候选都 < 4/6 → 才进入时辰扫描（Step 2.5 §12）
            （命中率 ≥ 4/6 时本步跳过；4 类 detect 都未触发时本步也跳过）
  → Step 2.7 询问输出格式（v5 · 体验门槛）
            「要 HTML 交互图，还是只要 markdown 文字分析？」
            · 单盘默认问；合盘默认 markdown（HTML 仅可选）
            · 用户选 markdown → 跳过最后的 render_artifact.py，节省 5–15 秒等待
  → 单盘分支：Step 3a **流式输出**五类 markdown（整图 + 一生四维 + 大运 + 关键年份）→ Step 3b 渲染 HTML（仅当用户选 HTML）
  → 合盘分支：Step 3' 跑 he_pan.py → **流式输出**按层解读 + 加 / 减分 + 大运同步建议
Step 4  保存本次反馈到 confirmed_facts.json（v3 P5：下次跑同一八字直接复用）
```

**Step 2.5 是硬门槛**：用户没确认八字"准"之前，绝对不进入 Step 3 出图 / 合盘，避免在错八字上做大量徒劳分析。**v6 在原 R1+R2 之上加 R0 反询问 = 三阶段双层准确度判定**（取向准确度 R0 + 命局准确度 R1）。

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

  这是 1996 八字（丙子庚子己卯己巳）"月令决定论"误判教训的产物——详见 `references/diagnosis_pitfalls.md` §1-§2。
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

### 2.5 下马威校验（硬门槛 · v6 三阶段：R0 反询问 + R1 健康三问 + R2 交叉验证 · 必须等用户回应）→ `python scripts/handshake.py`

```bash
python scripts/handshake.py \
  --bazi bazi.json --curves curves.json \
  --current-year 2026 \      # 默认 today.year
  --out handshake.json
```

**v6 改版**：在原 v3 的"R1 健康三问 + R2 交叉验证"前面加 **R0 反询问·感情画像**（2 题），形成三阶段校验：

- `round0_candidates`（v6 新增 · **必须最先抛**）：固定 2 条
  - **⓪-① 感情①·偏好类型**（preference） —— 配偶星五行（男看正/偏财，女看正/七杀）+ 配偶宫（日支）藏干十神
  - **⓪-② 感情②·对方态度**（attitude） —— 配偶星旺衰 + 比劫多寡 + 食伤显隐 + 印多遮蔽 + 桃花地支综合
  - 作用：**取向校准**（八字大致对/不对 + 该走格局派 / 扶抑派 / 调候派）；R0 = 0/2 提示用户复核性别 / 时辰
- `round1_candidates`：固定 3 条（v3 健康三问，不变）
  - **① 健康①·寒热出汗**（temperature） —— 命局 climate.label 直接导出
  - **② 健康②·睡眠精力**（sleep_energy） —— climate × strength 组装
  - **③ 健康③·脏腑短板**（organ） —— 五行最弱 → 对应脏腑系统
- `round2_candidates`：1 本性画像 + 2 历史锚点（旧 R1 池移到 R2，作为交叉验证）

**为什么 R1 全部用健康问题**：
- 用户对"从小怕不怕冷 / 睡得浅不浅 / 哪个脏腑老出问题"的回答近乎二值，记忆终生稳定
- 错八字（时辰差 1 小时）会让 climate 跳档 + 五行权重剧变 → 健康三维同时跳档，**一查就露馅**
- 三个不同侧面 = 三次独立投票，避免单一维度偶然撞中
- 不需要用户回忆任何具体事件 / 关系 / 职业 → 满足 fairness_protocol 的盲化要求

**LLM 必须严格按以下三轮模板**把候选转述给用户，禁止添加候选数据中没有的事实：

**Round 0**（v6 新增 · 反询问·感情画像 2 题 · **最先抛**）：

```
开始之前先问你两个感情相关的问题——这两题不评判 / 不打标签，只用来快速判断你的八字大概率"对/不对"，
以及该按哪种取向（格局 / 扶抑 / 调候）来给你解。请凭直觉答「对 / 不对 / 部分」。

⓪-① 【感情①·偏好类型】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}

⓪-② 【感情②·对方态度】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}
```

R0 命中 → 取向准确度（不论命中几条，都继续走 R1）：
- 2/2 → 命局取向无悬念，按主流派系走
- 1/2 → 取向部分对，做分析时主动注明"X 处取向有歧义"
- 0/2 → 配偶星 / 配偶宫读法可能反了 → 提醒用户复核性别 / 时辰，**仍继续 R1 看命局准确度**

**Round 0' · 反迎合·反向探针（v7.4 #3 新增 · 强制在 R0 ② 答完后立刻抛 · R1 之前）**：

```
为了避免你"迎合性"答题（命局推啥就说啥），我再抛 2 条**故意构造的反向陈述**让你校验。
你只需对每条回 「对 / 不对 / 部分」，按你真实记忆答即可——
如果你两条都答「对」，意味着相反的两种描述你都觉得像，逻辑上不可能 → 我会自动给 R0 命中率打折。

⓪'-① 【关系①·反向探针（防迎合）】{round0_counter_probes[0].claim}
   依据：{round0_counter_probes[0].evidence}
   可证伪点：{round0_counter_probes[0].falsifiability}

⓪'-② 【关系②·反向探针（防迎合）】{round0_counter_probes[1].claim}
   依据：{round0_counter_probes[1].evidence}
   可证伪点：{round0_counter_probes[1].falsifiability}
```

反迎合判定（机械化在 `evaluate_responses` 里跑，LLM 不要自己算 / 不要改 claim）：
- **consistent**（原 + 反对应一致 / 部分一致）→ R0 命中率正常
- **sycophantic**（n_contradictions ≥ 1：原 = 对 且 反 = 对）→ **R0 命中率 × 0.5 打折**，advisory caveat 提示用户重新校准
- **mirror**（n_mirror_signals ≥ 1：原 = 不对 + 反 = 对）→ 命局推反了，建议触发 `--dump-phase-candidates` 跑相位反演

详见 `references/handshake_protocol.md` §5.5。

**Round 1**（首轮 3 条 = 健康三问）：

```
在画图 / 合盘之前，我先用 3 个不同侧面的「健康/体感」问题来校验一下八字的准确度。
请逐条回 「对 / 不对 / 部分」。这三条都是终生稳定的体感证据，最不容易自欺。
（命中率 → 准确度：3/3 高 → 直接进下一步；2/3 中 → 我再给你 3 条交叉验证；
  ≤ 1/3 低 → 八字十有八九不准，请核对出生时辰）

① 【健康①·寒热出汗】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}

② 【健康②·睡眠精力】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}

③ 【健康③·脏腑短板】{claim}
   依据：{evidence}
   可证伪点：{falsifiability}
```

**Round 2**（追问 3 条 = 1 本性 + 2 历史锚点，仅在 R1 命中 < 3 时触发）：

```
为了把八字校验得更扎实，我再给你 3 条交叉验证。请继续回「对 / 不对 / 部分」。
两轮合计 6 条命中 ≥ 4 → 进入下一步；< 4 → 八字十有八九不准（多半是时辰偏 1 小时）。

④ ...   ⑤ ...   ⑥ ...
```

**命中率 → 准确度（v6 强制双层等级表）**：

第一层 · 取向准确度（R0）：

| R0 命中 | 取向 grade | 含义 |
|---|---|---|
| 2/2 | high | 命局取向无悬念，可按主流派系（geju 主格局 / 经典扶抑）直接走 |
| 1/2 | mid  | 取向部分对，分析时主动注明"X 处取向有歧义" |
| 0/2 | low  | 配偶星 / 配偶宫读法可能反了 → 性别 / 时辰可能错；**仍继续 R1**，但若 R1 也 ≤ 1/3 → 强烈建议核对 |

第二层 · 命局准确度（R1）：

| R1 命中 | accuracy_grade | 后续动作 |
|---|---|---|
| **3/3** | high   | 若 R0 ≥ 1/2 → 直接进入下一步（绘图 / 合盘评分）；R0 = 0 → 进但加强 caveat |
| **2/3** | mid    | 触发 Round 2；R1+R2 ≥ 4/6 → 继续 + 加 caveat；< 4/6 → 停 |
| **1/3** | low    | 触发 Round 2；R1+R2 ≥ 4/6 → 谨慎继续 + 强 caveat；< 4/6 → 停 |
| **0/3** | reject | 不再追问，强烈建议核对八字本身（时辰多半错） |

**整体放行**：R0 ≥ 1/2 且（R1 ≥ 2/3 或 R1+R2 ≥ 4/6）。
**整体拒绝**：R0 = 0/2 且 R1 ≤ 1/3 → 八字大概率不准（最常见：性别输错 / 时辰差 1 小时）→ 让用户复核后再来。

**红线规则（v6 三红线）**：

| 触发条件 | 行动 |
|---|---|
| ★ 健康①·寒热出汗 ✗ | **立即停下**，climate.label 多半判错了，告知用户："寒热体感没对上 → climate 判读可能反了 → 我需要重新审视命局结构再给你跑一遍" |
| ★ 健康③·脏腑短板 ✗ | **立即停下**，五行权重多半算偏（常见于时辰错导致月柱 / 时柱跳位），建议用 `--gregorian` 重新解析或时辰 ±1 小时对比 |
| ★ 感情①·偏好类型 ✗ + R1 ≤ 1/3 | **立即停下**（v6 新增），配偶星 / 性别 多半弄错了，告知用户："感情偏好和健康两层都不对 → 八字基础数据有较大概率不准 → 建议先核对（1）性别 是否正确（2）出生时辰 是否准确" |
| 健康②·睡眠精力 ✗（其他都对） | 不算红线，按命中率走（2/3 → mid），caveat 注明"strength 判读边界处可能略偏" |

**禁止**：
- ❌ 跳过 Step 2.5 直接出图 / 合盘
- ❌ 改写 R1 的 3 条 claim（必须原样转述脚本文案）
- ❌ R1 里加历史锚点 / 事件类候选（v3 R1 全部是健康问题）
- ❌ 红线触发后绕过去继续

**Round 3**（v7.3 新增 · **条件触发 · 反询问·原生家庭画像 2 题**）：

handshake.py 在生成 `handshake.json` 时会顺带生成 `round3_candidates`（来自 `family_profile.py`），但 R3 是**条件触发**的——LLM 不是默认抛 R3，而是按以下规则决定：

- ✓ 用户在初次提问中提到「家庭 / 父母 / 父亲 / 母亲 / 原生家庭 / 出身 / 家世 / 我爸 / 我妈」等关键词 → **必须抛 R3**（建议在 R0 之后、R1 之前抛）
- ✓ 用户在分析过程中追问「我家怎么样 / 我爸是什么样 / 我妈呢」 → **必须抛 R3**（在写 family 段之前）
- ✗ 用户没主动问家庭 → **不要抛 R3**（也不要写 family 段）

R3 候选 2 条：
- **③-① 原生家庭①·整体结构**：5 档候选（显赫候选 / 中产候选 / 普通 / 波折候选 / 缺位候选）
- **③-② 原生家庭②·父母存在模式合并**：父亲 + 母亲存在模式（贴近 / 偏远 / 高压 / 缺位 等）

R3 命中级别 → family 段权重（**正交于 R0/R1/R2，不算入命局准确度**）：

| R3 命中 | family 段写法 |
|---|---|
| 2/2 | 高置信展开（按 primary_class）。**显赫候选** + 用户确认 → 可以谨慎说"父辈/祖辈中可能有人在某领域有可识别的位置" |
| 1/2 | 中置信。命中那条可展开；未命中那条标"取向歧义"或省略 |
| 0/2 | **family 段不展开具体内容**，只写一句"原生家庭推断未通过校验，本次不展开（命局对家庭的读法可能反了）" |

R3 红线（v7.3 新增）：
- ★ 整体结构标"不对"且 `primary_class = illustrious_candidate` → **必须降级**，禁用"显赫 / 名门 / 名利双收"等措辞（修古法 survivorship bias 的 systemic bug）
- ★ 父母存在模式两条都标"不对" → 父星 / 母星读法多半反了 → family 段直接省略

**为什么 v7.3 加 R3**：古法和 LLM 训练语料对原生家庭有严重的 survivorship bias —— 古典命书几乎只收录显赫人物的命例，导致"年柱财官印聚合"在书里反复对应"显赫家世"，但普通人的同样结构在古籍里几乎不出现。LLM 裸推家庭 = 90% 概率把普通家庭描述成"大家长 / 名利双收 / 出身有底蕴"。R3 反询问就是把这个偏置交回给用户校验，**校验通过的"显赫"才能说，没校验过 / 校验不通过 → family 段降级或省略**。完整解读铁律见 `references/fairness_protocol.md` §11 + `references/multi_dim_xiangshu_protocol.md` §11。

**合盘场景的特殊要求**（详见 `references/he_pan_protocol.md` §4）：
- 用户输入多份八字 → **每份都要单独跑一次 R1 健康三问**
- 用户对自己的八字答得最准；对方（配偶 / 合伙人 / 朋友 / 家人）的健康问题答多少算多少
- 主体本人八字必须 R1 ≥ 2/3 才放行合盘
- 对方八字若 R1 < 2/3，合盘 confidence 降级 + caveat："另一方八字校验不足，结论作为方向参考"

完整规则见 `references/handshake_protocol.md`、`references/he_pan_protocol.md` §4 和 `references/diagnosis_pitfalls.md` §0 红线表。

### 2.55 【v7 强制 · v7.2 加二轮校验】R0+R1+R2 ≤ 2/6 时 · 相位反演校验循环（P1-7）

**触发条件**：Step 2.5 总命中率 ≤ 2/6（含 R0 + R1 + R2）。
**目的**：在跳到"八字错 / 时辰错"结论之前，先排除「**算法的相位选择反了**」这种可能。**反演不是直接信，要再让用户答一遍二轮校验**——命中率 ≥ 4/6 才落地。

**为什么必须做**：某用户 1996 八字 `丙子 庚子 己卯 己巳`，默认相位命中率 1/6 = 17%，反向到 `floating_dms_to_cong_cai` (P5 三气成象 4/4) 后跳到 5/6 ≈ 83%——66 个百分点的差异。这是算法的盲区，不是用户的八字错。详见 `references/phase_inversion_protocol.md` §11 和 `references/diagnosis_pitfalls.md §12`。

#### v7.2 推荐用法 · 一条命令搞定 4 步（Auto-Loop）

```bash
python scripts/phase_inversion_loop.py \
    --bazi out/bazi.json \
    --out-dir out/ \
    --default-hit-rate "1/6"
```

它会自动：
1. dump 5 类相位反演候选（P1 日主虚浮 / P2 旺神得令 / P3 调候反向 / P4 假从-真从 / P5 三气成象）
2. 自动选 top-1（按 detector 置信度排序）
3. 跑 `score_curves --override-phase <pick>` → `curves_phase_inverted.json`
4. 跑 `handshake --phase-id <pick>` → `handshake_round2.json`（**按反演相位重新生成 6 题**）

输出含完整的 `next_step_for_llm` + 落地命令模板。

#### LLM 必守的 4 条话术铁律（v7.2）

1. **不允许第一句话就说"八字错"**：必须先讲"另一种可能是算法读反"
2. **不允许反演后默默重跑**：必须先用 `pick_explain_for_user` 跟用户说清楚反演是什么
3. **二轮校验是强制的**：把 `handshake_round2.json` 的 6 题完整抛给用户重新作答，**禁止**根据反演候选直接出图
4. **重跑后必须明确告知"已反演"**：第一段输出必带「相位 = X，不是默认相位」

#### 二轮校验落地条件

| 二轮命中率 | 动作 |
|---|---|
| **≥ 4/6** | 写 `confirmed_facts.structural_corrections` (kind=phase_override) → 进 Step 3 出图（带「相位 = X」标记） |
| **< 4/6 且还有候选** | 重跑 `phase_inversion_loop.py --pick <next_id>` 试下一个候选 |
| **全部候选都 < 4/6** | 真正进入"建议核对时辰"流程（详见 `references/diagnosis_pitfalls.md §0`） |

#### 落地命令（用户二轮命中率 ≥ 4/6 后）

```bash
# 1. 写入 confirmed_facts
python scripts/save_confirmed_facts.py \
    --bazi out/bazi.json \
    --out out/confirmed_facts.json \
    --add-structural phase_override day_master_dominant <pick> \
    --reason '二轮校验命中率 5/6 → 反演相位落地'

# 2. 用 confirmed_facts 重跑 score_curves（之后所有重算都自动应用反演）
python scripts/score_curves.py \
    --bazi out/bazi.json \
    --confirmed-facts out/confirmed_facts.json \
    --out out/curves_final.json
```

#### v7 旧用法（仍可用 · 手工分步）

```bash
python scripts/handshake.py --bazi out/bazi.json --dump-phase-candidates --out out/phase_dump.json
python scripts/score_curves.py --bazi out/bazi.json --override-phase <pick> --out out/curves_inverted.json
python scripts/handshake.py --bazi out/bazi.json --curves out/curves_inverted.json --phase-id <pick> --out out/handshake_round2.json
```

#### 跳过相位反演的条件

- 默认相位 R0+R1+R2 ≥ 4/6（happy path，本来就不需要）
- `dump_phase_candidates` 返回 `n_triggered = 0`（5 类 detect 都没触发，命中率低更可能是八字错）
- 用户明确说"我确定八字对，不需要试反向假设"

#### 禁止

- ❌ R0+R1+R2 ≤ 2/6 时跳过这一步直接判"八字错 / 时辰错"
- ❌ 跳过 `--dump-phase-candidates` 直接 `score_curves --override-phase`（必须先看 detect 触发了什么）
- ❌ **跳过二轮校验**（v7.2 强制）：phase 反演候选挑出来后，必须按 `--phase-id` 重新生成 6 题让用户答，不允许直接相信
- ❌ 反演重跑后第一段还按默认相位的语义解读

完整流程见 `references/phase_inversion_protocol.md` §5 + §11 和 `references/handshake_protocol.md §13`。

### 2.6 合盘分支（仅当输入 ≥ 2 份八字时执行）→ `python scripts/he_pan.py`

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

**Step 4：保存反馈记忆** —— 用户给完 R1+R2 反馈或后续校正后，调用 `save_confirmed_facts.py` 把反馈写回 `output/confirmed_facts.json`：

```bash
# 写入 R1/R2 反馈（JSON Lines）
echo '{"round":"R1","trait_or_anchor":"外燥内湿","user_response":"对"}
{"round":"R1","trait_or_anchor":"包容低调","user_response":"部分对","user_note":"我是带头型"}' \
  | python3 scripts/save_confirmed_facts.py --bazi output/bazi.json --append

# 自由事实
python3 scripts/save_confirmed_facts.py --bazi output/bazi.json --add-fact \
  "用户 2024 年升职 + 论文奖；脚本曾误判为 fame down，已通过 P1 反向规则修正"

# 结构性纠错（用于下次跳过这个判错路径）
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

## 三大保障 + 六项强制（必须遵守 · v6 加 R0 反询问 · v7 加现代化解读铁律 + 相位反演 · v7.3 加原生家庭 R3 反询问）

- **准确**：分数来自脚本（单盘=「格局为先 + 三派交叉」+「emotion 独立通道」、合盘=「五行 + 干支 + 十神 + 大运」4 层），**禁止 LLM 直接打分**
- **公正**：身份信息不得进入打分流程；同输入双盲必须 bit-for-bit 一致；合盘也只看八字结构、不接收姓名 / 关系状态 / 历史
- **预测性**：未来年份 / focus_years 必须给出 (方向, 置信度) 二元组；低置信度年份图上标灰
- **争议解读（强制）**：每个 disputed 年份都必须并入 key_years 并按 dispute_analysis_protocol Step A–D 解读
- **合盘解读（强制）**：4 层评分必须按 he_pan_protocol §5 解读（按层 → 加 / 减分 → 大运同步 → confidence），禁止甩 grade、禁止给"配/不配"结论
- **流式输出（强制 · v5）**：Step 3a / 合盘解读必须按节流式发出（每写完一节立刻发，禁止憋整段）；Step 2.7 必须先问用户要 markdown-only 还是要 HTML，禁止默认渲染 HTML 让用户白等
- **R0 反询问 + 双层准确度（强制 · v6）**：Step 2.5 必须先抛 R0 反询问·关系画像 2 题（偏好类型 + 对方反应模式）做"取向校准"，再抛 R1 健康/重大事件 3 题做"命局校准"；最终 `accuracy_grade` 必须按 R0 + R1 双层判定（详见 §2.5），命中红线（关系①✗ + R1 ≤ 1/3）必须停手要时辰
- **相位反演校验（强制 · v7 · P1-7）**：当 Step 2.5 R0+R1+R2 命中率 ≤ 2/6 时，**禁止**第一句话就判"八字错 / 时辰错"。**必须**先跑 Step 2.55 的 `handshake.py --dump-phase-candidates`，按 4 类相位反演候选（日主虚浮 / 旺神得令 / 调候反向 / 假从-真从）跟用户讨论"算法是否读反"，用户同意后用 `score_curves --override-phase X` 重跑。只有 4 类候选都跑过且 < 4/6 才进入时辰扫描。详见 `references/phase_inversion_protocol.md` 和 `references/diagnosis_pitfalls.md §12`。
- **现代化解读铁律（强制 · v7）**：emotion 维度的解读**必须**遵守 fairness_protocol.md §10：
  - **命局可推**：关系结构 / 能量模式 / 偏好的互动模式 / 关系密度
  - **命局不可推**：对方生理性别 / 是否结婚 / 几段关系 / 是否生育 / 关系是否被祝福
  - **禁用措辞**："克夫 / 旺夫 / 旺妻 / 妻星 / 夫星 / 配偶 / 异性缘 / 你应该结婚 / 晚婚 = 命不好 / 你会跟 X 类人结婚"
  - **emotion 高 ≠ 婚姻顺利，emotion 低 ≠ 单身差**——纯中性描述
  - **必须前置声明**：出图后第一段感情解读必须包含「命局只反映关系结构和能量模式，不预设对方性别 / 是否结婚 / 是否生育——这些是你的现代选择，不在命局之内」
  - **不接受用户的关系状态作为输入**（"我已婚 / 我跟 X 在一起 5 年" → 接受为现实但不回写打分、不掺入后视镜叙事）
- **原生家庭解读铁律（强制 · v7.3）**：family 段的解读**必须**遵守 fairness_protocol.md §11：
  - **命局可推**：父母在你能量场里的存在模式 + 年/月柱财官印聚合的结构画像（5 档：显赫候选 / 中产 / 普通 / 波折 / 缺位）
  - **命局不可推**：父母的社会地位 / 收入 / 职业 / 学历 / 是否健在 / 是否离异 / 是否再嫁
  - **禁用措辞**："出身名门 / 名门望族 / 家世优渥 / 家世显赫 / 父亲名利双收 / 母亲贤惠 / 大家长 / 严父慈母 / 父能传财"
  - **R3 反询问校验是必经**：写 family 段前必须抛 R3 反询问 2 题（整体结构 + 父母存在模式），R3 = 0/2 时 family 段直接降级为一句话
  - **修古法 survivorship bias**：古典命书只收录显赫人物的命例，所以"年柱财官印聚合"在古籍里反复对应"显赫家世"——但在现代普通人的同样结构上，真实概率远低于古法暗示。R3 校验通过的"显赫"才能说，没校验过 / 校验不通过 → family 段降级或省略
  - **触发条件**：仅在用户主动问"家庭/父母/出身"等关键词时抛 R3 + 写 family 段；用户没问 → 不要"为了完整性"硬写

## 何时阅读 USAGE.md / references/

- **用户问"怎么用 / 怎么触发 / 不会用"** → `USAGE.md`（直接复述给用户）
- **每次接到八字 / 生日，进入 Step 2.5 之前** → `references/handshake_protocol.md`（强制）
- **R0+R1+R2 命中率 ≤ 2/6 时（进入 Step 2.55 之前）** → `references/phase_inversion_protocol.md`（强制 · v7 新增）
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
