# bazi-life-curves

> 把八字命理变成可证伪、可审计的人生曲线。
> Quantify Chinese Bazi (Four Pillars of Destiny) into auditable, falsifiable life curves.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Skill for Claude](https://img.shields.io/badge/Claude-Skill-7B68EE.svg)](https://www.anthropic.com/)

---

## 这是什么

一个把中国八字命理（四柱八字）结构化为**可量化曲线**的工具。给一个八字（或公历生辰 + 性别），自动生成：

- **4 维人生曲线 × 80 年**：精神 / 财富 / 名声 / 关系能量，每维 2 条线（当年值实线 + 5 年累积虚线）= 8 条线
- **大运评价**：每 10 年一段，含三派打分 + 盲派应事 + 关系能量看点
- **关键年份大白话解读**：peak / dip / shift，含可证伪点
- **合盘分析**：≥ 2 份八字的合作 / 婚配 / 友谊 / 家人 4 维度兼容性
- **交互式 HTML**：marked.js + Recharts + RichTooltip + details 折叠

## 跟其他八字工具的区别

| 特点 | 本工具 | 大多数命理软件 |
|---|---|---|
| 三派交叉打分（扶抑/调候/格局） | ✓ 自动融合 + 派别分歧标记 | 通常只用一派 |
| 盲派应事 + 反向规则 | ✓ 11 条经典组合 + 3 条结构反向 | 机械读口诀，无反向 |
| 结构性保护机制 | ✓ 印化护身 / 食神制杀 / 比劫帮身 / 六合解冲等十余条 | 通常仅"看到冲就 -" |
| 出图前两轮校验（健康三问 + 反询问） | ✓ R0+R1+R2 三阶段，命中 < 4/6 拒绝出图 | 不校验，直接出图 |
| 历史回测 + 置信带 | ✓ `calibrate.py` 跑历史命中率 | 全凭经验 |
| 公正性约束（身份盲化）| ✓ 不接受姓名 / 职业 / 关系状态 | 通常需要个人信息 |
| **现代化解读**（去性别歧视 / 支持 LGBTQ+ / 去婚姻预设）| ✓ `--orientation` 参数 + 删除全部"克夫旺夫"古法 | 默认异性恋 + 婚姻本位 |
| LLM 后视镜叙事防御 | ✓ 强制"推论过程 + 可证伪点"格式 | LLM 自由发挥 |

## 快速开始

### 安装

```bash
git clone https://github.com/XiaoChu-1208/bazi-life-curves.git
cd bazi-life-curves
pip install -r requirements.txt
```

### 跑一次

```bash
# 1. 解析八字
python scripts/solve_bazi.py \
  --pillars "庚午 辛巳 壬子 丁未" \
  --gender M --birth-year 1990 \
  --out output/bazi.json

# 2. 生成 4 维曲线
python scripts/score_curves.py \
  --bazi output/bazi.json \
  --out output/curves.json --age-end 80

# 3. 校验候选（你需要回答 R0 + R1）
python scripts/handshake.py \
  --bazi output/bazi.json --curves output/curves.json \
  --out output/handshake.json

# 4. 渲染 HTML 交互图
python scripts/render_artifact.py \
  --curves output/curves.json --out output/chart.html
```

打开 `output/chart.html` 即可看到交互式曲线。

### 在 Claude（或其他 AI 助手）里用

把整个目录放到 Claude Skill 路径下（`~/.claude/skills/bazi-life-curves/`），然后直接说：

> 跟它说："我想看我的人生曲线，八字是 庚午 辛巳 壬子 丁未，男，1990 年出生"

Claude 会读 `SKILL.md` 自动跑完整流程，并按设计的"两轮校验"硬门槛阻止你在错八字上做徒劳分析。

## 学理合理性

本工具的核心命理逻辑（三层独立 / 三派融合 / 格局为先 / 结构性保护机制 / 反向规则）都有 600 年古籍直接支撑：

- **三层独立**（L0 原局 / L1 大运 / L2 流年）→ 子平命理"体用之分"
- **三派打分**（扶抑 / 调候 / 格局）→ 民国徐乐吾整理的"子平三大法门"
- **格局为先**→ 《子平真诠》"先观月令以定格局，次看用神以分清浊"
- **燥湿独立维度**→ 《穷通宝鉴》"寒暖燥湿，命之大象"
- **结构性保护**（杀印相生 / 食神制杀 / 合解冲 / 三刑等）→ 《滴天髓》《三命通会》

工程化部分（量化打分 / 权重数字 / 衰减系数）是经验值，详见 [`references/methodology.md`](references/methodology.md)。

## 现代化解读规范（重要）

本工具基于中国传统八字命理（600 年体系），但所有解读语言**都去除**了原典中的：

- **性别歧视措辞**：删除"克夫 / 旺夫 / 旺妻 / 妻星 / 夫星 / 异性缘 / 女命伤官克夫 / 女命印多减分"等古法规则
- **异性恋默认**：通过 `--orientation hetero/homo/bi/none/poly` 显式支持多元关系取向
- **婚姻预设**：emotion 维度高 ≠ 婚姻顺利 / emotion 低 ≠ 单身差，纯中性描述
- **价值排序**：不假设"名声高 = 好 / 财富高 = 成功 / 婚姻 = 幸福"

**命局只反映**关系结构 / 能量模式 / 偏好的互动模式 / 关系密度
**命局不反映**对方的生理性别 / 是否结婚 / 几段关系 / 是否生育 / 关系是否被祝福

完整规范见 [`references/fairness_protocol.md`](references/fairness_protocol.md) §9-§10。

## 目录结构

```
bazi-life-curves/
├── SKILL.md                       # 主定义（Claude/Cursor 读这个）
├── USAGE.md                       # 用户视角速览
├── INSTALL.md                     # 安装指南
├── README.md                      # 本文件
├── requirements.txt               # 依赖
├── scripts/                       # 9 个核心脚本
│   ├── _bazi_core.py              # 干支 / 五行 / 十神 / 互动检测底层
│   ├── solve_bazi.py              # 八字解析（含 --orientation）
│   ├── score_curves.py            # 4 维曲线打分（三派融合 + 关系能量独立通道）
│   ├── mangpai_events.py          # 盲派应事 + 反向规则 + 护身减压
│   ├── handshake.py               # R0+R1+R2 三阶段校验候选
│   ├── render_chart.py            # 静态 PNG（matplotlib）
│   ├── render_artifact.py         # 交互 HTML（Recharts + marked.js）
│   ├── he_pan.py                  # 合盘 4 层评分
│   └── calibrate.py               # 历史回测
├── templates/
│   └── chart_artifact.html.j2     # HTML 模板
├── references/                    # 学理 / 协议 / 命局误判陷阱
│   ├── methodology.md
│   ├── scoring_rubric.md
│   ├── mangpai_protocol.md
│   ├── handshake_protocol.md
│   ├── multi_dim_xiangshu_protocol.md
│   ├── dispute_analysis_protocol.md
│   ├── prediction_protocol.md
│   ├── he_pan_protocol.md
│   ├── fairness_protocol.md       # §9-§10 现代化规范
│   ├── diagnosis_pitfalls.md      # 已踩过的坑
│   ├── accuracy_protocol.md
│   └── glossary.md
├── examples/                      # 2 个完整示例（含 HTML）
└── calibration/                   # 历史命中率数据集
```

## 已知限制

- **数据集偏小**：当前 `calibration/dataset.yaml` 只 5 人 / 15 事件，统计意义有限
- **从格 / 化气格 / 神煞**：尚未实现，遇到会按普通格局走
- **真太阳时校正**：未实现（`--longitude` 是 deferred）
- **三派权重 25/40/30** 是经验值，需更大数据集做网格搜索

详见 `SKILL.md` 末尾的 deferred 列表。

## 贡献

PR / issue 欢迎。**请勿提交**：

- 任何含真实八字 + 真实姓名 / 经历的数据（隐私）
- 带宿命论 / 性别歧视 / 婚姻强制论的解读模板
- 直接抄袭某流派师傅的口诀（请引用出处 + 师承）

## License

MIT —— 命理工具应该是公共财产，不该藏起来。

## 致谢

- 子平命理：徐乐吾整理的"子平三大法门"
- 调候派：余春台《穷通宝鉴》
- 格局派：沈孝瞻《子平真诠》
- 滴天髓：刘伯温
- 盲派：段建业、王虎应、李洪成的实战口诀
- 起运岁精算：[lunar-python](https://github.com/6tail/lunar-python)
- 渲染：marked.js、Recharts

---

**v7 现代化版本**（2026-04）—— 主要更新：
- 加 `--orientation` 参数支持 hetero/homo/bi/none/poly 取向
- 删除全部带性别歧视的古法规则（克夫旺夫 / 女命印多减分 / 配偶星弱减分等）
- emotion 维度纯中性描述：高 ≠ 婚姻顺利 / 低 ≠ 单身差
- 加 §10 现代化解读铁律：命局只推关系结构，不推对象 / 婚否 / 生育
