# 盲派定位与协议（Mangpai Protocol）

> 盲派（mangpai）作为命理学的第 4 大派别接入本 skill，但**不进入** 25% 的打分融合权重。
> 它的定位是 **应事断 + 烈度修正器**，扬其长（应期 / 应事精度）、避其短（用神之争 / 师承差异 / 不可程序化的"工作组合"）。

## 1. 为什么盲派不进 25% 融合

| 顾虑 | 说明 |
|---|---|
| **可程序化程度低** | 盲派核心方法论（"象法"、"工作组合"、"主客分明"）严重依赖经验和直觉，没有清晰的"加分 / 减分"规则可机械执行；硬拆出来是"假盲派" |
| **师承差异大** | 段建业、王虎应、李洪成等同为盲派，但具体口诀经常互相矛盾；融合后反而引入噪声 |
| **不擅长打分** | 盲派最强的是 "YYYY 年应 XX 事" 的事件断；用 0-100 的量化框架包装它，等于用错了刀 |
| **可证伪性差** | 盲派的"工作组合"含大量隐含语境，难以拆成可机械验证的条件 |

但盲派的**强项**（应事 / 应期 / 经典组合识别）确实领先于书房派——所以我们用另一种方式接入它。

## 2. 盲派在 skill 里的两个角色

### 2.1 应事断（事件层）

`scripts/mangpai_events.py` 机械识别 11 条经典盲派组合，每条对应**一个具体事件类型**（例：禄被冲 → 移居 / 工作变动 / 关键关系切换 / 身体意外）。

输出 `mangpai.json` → events 列表，每条事件含：
- 年份 / 干支 / 大运 / 年龄
- 组合名 + 师承出处（段建业 / 王虎应 / 民间口诀）
- canonical_event（应事文本，1-2 句）
- 维度 + 烈度档（重 / 中 / 轻）
- evidence（哪些干支 / 十神触发了这个组合）
- falsifiability（如果某事没发生，这条就是错的）

这些事件**不进打分**，但会：
- 在 `curves.json` → `points[].mangpai_events` 出现
- 被 LLM 在多维取象时**强制引用**作为应事证据
- 被 handshake.py 优先选为过往大波动锚点

### 2.2 烈度修正器（曲线层）

在三派融合（扶抑 / 调候 / 格局）算出当年的 final value 后，按当年所有盲派事件的 amplifier 加权 ±烈度档：

| 烈度 | 加减档度 | 典型事件 |
|---|---|---|
| 重 | ±8 分 | 禄被冲、伤官见官应期、反吟应期、财库被冲开 |
| 中 | ±4 分 | 官杀混杂应期、比劫夺财、食神制杀、七杀逢印、伤官伤尽、伏吟应期、羊刃逢冲 |
| 轻 | ±2 分 | （目前未启用，留作 v2 扩展） |

单年累加上限 ±12 分（避免多事件叠加冲爆量纲）。修正轨迹写入 `points[].mangpai_adjust`，可审计。

## 3. 11 条经典组合的应期规则

所有"应期"类组合都遵守 **"补缺规则"**：原局已经同时具备 A 和 B 的不算应期（这是终生背景），原局只有 A 缺 B、流年补出 B 才算"今年发动"。这是为了避免事件密度爆炸。

| Key | 中文 | 触发要求 | 应事 |
|---|---|---|---|
| `shang_guan_jian_guan` | 伤官见官 | 原局有伤官缺正官（或反），流年补出 | 与权威 / 体制摩擦、官非、降职 |
| `guan_sha_hun_za` | 官杀混杂 | 原局有官缺杀（或反），流年补出 | 多重压力左右为难、女命婚波 |
| `bi_jie_duo_cai` | 比劫夺财 | 原局有财，流年带比劫 | 合伙折利、被分财、配偶 / 兄弟财损 |
| `lu_chong` | 禄被冲 | 流年支冲日干禄位 | 移居 / 职业 / 关系切换、身体意外 |
| `yangren_chong` | 羊刃逢冲 | 流年支冲日干羊刃（仅阳干） | 突发事件、激烈情绪、强决断 |
| `shi_shen_zhi_sha` | 食神制杀 | 原局有杀，流年天干食神 | 化煞为权、用作品 / 项目化压力 |
| `qi_sha_feng_yin` | 七杀逢印（杀印相生） | 原局有杀，流年天干印星 | 贵人提拔、进入更高体系 |
| `shang_guan_shang_jin` | 伤官伤尽 | 原局伤官 ≥ 2 见，流年/大运再引动 | 才华突破、跟旧体制告别 |
| `fanyin_yingqi` | 反吟应期 | 流年与日柱天克地冲 | 身体 / 居所 / 关系剧变（一翻一覆） |
| `fuyin_yingqi` | 伏吟应期 | 流年与原局某柱伏吟 | 旧事重演、必须直面同一类课题 |
| `cai_ku_chong_kai` | 财库被冲开 | 原局/大运的财库被流年冲 | 财务结构跳档（得 or 失看用神） |

加 1 条**静态终生标记**：

| Key | 中文 | 触发要求 | 终生影响 |
|---|---|---|---|
| `nian_cai_bu_gui_wo` | 年财不归我 | 年柱有正/偏财，且年支与日/月支无六合无三合 | 原生家庭财在你之外，需自起炉灶 |

## 4. LLM 必须如何使用这些数据

在 **Step 3a 多维取象** 阶段（见 SKILL.md），对关键 10 年的每条拐点：

- **必须**先列出该年所有 `mangpai_events`（如果有）
- **必须**用 mangpai 的 `canonical_event` 作为应事的"骨"，再展开六维取象
- **不允许**忽略 mangpai 事件直接写"我觉得这年会..."

在 **下马威 / handshake** 阶段，handshake.py 会优先把"含盲派高烈度事件"的过往年份选作锚点，因为这些年份的应事最具体、最容易被用户当场验证。

## 5. 与三大书房派的边界

| 任务 | 主用 | 辅用 |
|---|---|---|
| 给某年某维度打 0-100 分 | 三派融合（扶抑 / 调候 / 格局，各 25/40/30） | 盲派烈度 ±修正 |
| 判断哪派打分最贴近 | 三派之间的 spread | （盲派不参与） |
| 解读"今年应什么具体事" | **盲派 events** | 三派的 interactions（已识别的伏吟 / 反吟 / 库冲等） |
| 解读"派别为什么分歧" | dispute_analysis_protocol（三派） | （盲派不进入这个流程） |
| 下马威 / 握手锚点 | handshake.py 综合三派偏离度 + **盲派事件优先** | — |

## 6. 关闭盲派的方法

如果用户明确要求"只用书房派、不用盲派"：

```bash
# 不传 --mangpai 即可
python scripts/score_curves.py --bazi bazi.json --out curves.json --age-end 60
```

`curves.json` 里 `mangpai_enabled=false`，points 里也没有 `mangpai_events` 字段。LLM 在多维取象时只用三派的 interactions。

## 7. 盲派事件的可证伪原则

每条 mangpai event 都自带 `falsifiability`，用户可当场判 yes/no。如果某条用户明确否认（"那年我没移居 / 没换工作 / 没受伤"），LLM 在解读时**必须**：

1. 接受用户的否认
2. 把该事件的烈度修正在解读中"反向折扣"（例：盲派给该年精神 -8，但用户否认应事，则把这 8 分折回去当 0 解读）
3. 把这条记入 caveats 让用户知道哪部分被打折

## H. v9 高置信度铁律（机械护栏 · audit_mangpai_surface 实施）

> **6d0abb46 case 暴露的 bug**：盲派给出 `confidence == high` 的事件（例：年财不归我 / 重烈度反吟 / 大运同向加成的禄被冲），LLM 在分析叙事里没有提到。
> 命主明确反馈："你甚至没发现盲派那几个指标置信度其实是很高的。"

### H.1 confidence 字段（v9 新增）

`scripts/mangpai_events.py` 在每条事件 / 静态标记里写入 `confidence ∈ {high, mid, low}`：

| confidence | 触发条件 |
|---|---|
| `high` | 重烈度 + 大运/原局结构同向加成（triple 印证）；或所有静态终生标记（例：`nian_cai_bu_gui_wo`） |
| `mid` | 重烈度但只有 liunian 单点应期 / 中烈度 + 大运同向加成 |
| `low` | 中烈度无加成 / 轻烈度 |

### H.2 高置信度强制 surface 铁律

| 铁律 | 说明 | 机械实施 |
|---|---|---|
| **每条 `confidence=high` 事件必须显式出现在叙事** | 显式 = 年份 + 干支 / canonical_event 关键短语在 `dayun_reviews` / `key_years` / `liunian` / `overall` 里能搜到 | `scripts/audit_mangpai_surface.py` |
| **静态终生标记必须在 `overall` 或某段 `dayun_reviews` 显式提到** | 不能只放进 `mangpai.json` 数据里然后只字不提 | 同上 |
| **render_artifact 默认 `--audit-mangpai-surface`** | 漏掉一条即 exit 6（除非 `--allow-partial`） | `scripts/render_artifact.py · _run_v9_audits()` |

### H.3 与 §4 的关系

§4 已经写过 "**必须**先列出该年所有 mangpai_events / **必须**用 canonical_event 作为应事的'骨'"——
H 节是把这个铁律**机械化**：原先靠 LLM 自觉，v9 起由 `audit_mangpai_surface.py` 自动检查。

漏掉中 / 低置信度事件 = 警告（不阻断）；漏掉**高**置信度事件 = exit 6 阻断渲染。

### H.4 盲派 / 子平正格与 phase decision 的冲突警示（v9 · 修 6d0abb46 case bug）

**bug 二**：盲派 _patterns / 格局_（不是 events，是 `rare_phase_detector.py` 输出的
`yang_ren_jia_sha`、`qi_yin_xiang_sheng`、`yangren_chong_cai` 这一类）conf ≥ 0.80，
但最终 `phase_decision.decision` 选了 `day_master_dominant`（mid），冲突被默默淹没。

**修法**（详见 [phase_decision_protocol.md §7.5](phase_decision_protocol.md)）：

1. `_bazi_core.decide_phase` 输出新增 `mangpai_conflict_alert` 字段（severity = high / mid / low）
2. `phase_posterior.update_posterior` 在所有 confidence 档位都跑 alert 检查；
   severity=high 时强制建议 R3（即使 R1 confidence ∈ {mid, high}）
3. `audit_mangpai_surface.py --bazi <bazi.json>` 要求 alert.conflicting_hits 的每一条
   `name_cn` 都在 analysis 文本中字面出现（severity=high 还要求叙事里出现承认冲突的关键词）；
   失败 exit 3
4. `render_artifact.py` 默认透传 `--bazi`；HTML 顶部渲染「盲派强冲突 · 必读」/
   「盲派冲突」/「盲派提示」三档警示卡

> **设计原则**：v9 不修改 `_p7_zuogong_aggregator` 的权重曲线（保 bit-for-bit）。
> 盲派 zuogong 在算法层面仍是「附加证据通道」，但当其结论与最终 decision 高置信度
> 冲突时，**必须 surface**（不能默默淹没）。最终裁决权交给用户的 R3 confirmation。

## 8. v2 路线图（暂不实现）

- 引入更多盲派组合：金神格、魁罡格、十恶大败日、孤辰寡宿、华盖（盲派化）等
- 引入"工作组合"识别（多个十神同框做一件事的语义识别）
- 大运层面的事件（不只看流年）
- 盲派的"主客分明"判定（年柱不归我、月柱归父母位等）的程序化
