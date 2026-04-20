# Contributing to bazi-life-curves

> 中文优先，欢迎英文 PR / issue。
> 这是一个把"600 年子平命理"变成"现代可证伪工程"的项目，对学理严谨度和工程一致性都有较高要求。

---

## 我可以贡献什么

### ✅ 鼓励

- **新的盲派事件 / 结构性保护机制** —— 必须附古籍出处或现代盲派师承（段建业 / 王虎应 / 李洪成等）
- **历史命主的匿名回测数据** —— 八字 + 出生年代 + 真实大事件年份（绝对不要带姓名 / 城市 / 单位）
- **现代化解读规范的改进** —— fairness_protocol §10 的语言重构建议
- **HTML 渲染优化** —— Recharts / marked.js / 移动端适配
- **国际化 i18n** —— 把 references/glossary.md 的中英对照扩展到完整多语言
- **新算法 phase override** —— 化气格 / 从格 / 一行得气 / 两神成象 等特殊格局的判定与影响
- **bug 修复** —— 命理判错、HTML 渲染异常、CLI 参数失效

### ❌ 拒绝

- **含真实姓名 / 经历的八字数据**（隐私红线）
- **带宿命论 / 性别歧视 / 婚姻强制论的解读模板**（违反 fairness_protocol §10）
- **直接抄袭某流派师傅口诀**（请引用出处 + 师承，禁止直接照搬付费课程内容）
- **"这个准不准" 类无脚本可重现的 issue** —— 请附完整的 `bazi.json` + `confirmed_facts.json` + 你认为错误的字段
- **引入大模型 SDK / 重型机器学习依赖**（torch / tensorflow / transformers）—— 保持工具轻量、CPU 5 秒跑完

---

## 开发流程

### 1. 环境准备

```bash
git clone https://github.com/XiaoChu-1208/bazi-life-curves.git
cd bazi-life-curves
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 改之前先读对应协议

| 你想改什么 | 必读文档 |
|---|---|
| 三派权重 / 用神判定 | `references/methodology.md` + `references/scoring_rubric.md` |
| 盲派事件 / 反向 / 护身 | `references/mangpai_protocol.md` |
| handshake 题目 / 放行规则 | `references/handshake_protocol.md` |
| 化气格 / 神煞 | `references/diagnosis_pitfalls.md` |
| 性别 / 取向 / 关系结构 | `references/fairness_protocol.md §9-§10` |
| 合盘 4 层评分 | `references/he_pan_protocol.md` |

详见 `AGENTS.md` 的"修改算法时的硬性约束"。

### 3. 跑回归

```bash
mkdir -p output

python scripts/solve_bazi.py --pillars "甲子 丁卯 丙寅 戊戌" --gender M --birth-year 1984 --orientation hetero --out output/test.bazi.json
python scripts/score_curves.py --bazi output/test.bazi.json --out output/test.curves.json --age-end 80
diff <(python scripts/score_curves.py --bazi output/test.bazi.json --strict | sha256sum) \
     <(python scripts/score_curves.py --bazi output/test.bazi.json --strict | sha256sum)
# 必须输出空（同输入 100 次 100 个 byte-equal 结果）

python scripts/calibrate.py
# spirit_recall ≥ 0.70, wealth_recall ≥ 0.75, fame_recall ≥ 0.65, fp_rate ≤ 0.15
```

### 4. 性别对称性自检

任何动到 spirit / wealth / fame 三维的改动，**必须**通过：同八字翻转性别 → 三维 byte-equal（仅 emotion 因配偶星识别可不同）。

### 5. PR 标题格式

```
[scripts/score_curves] 添加化气格 phase override
[references/mangpai_protocol] 修正"伤官伤尽" 的反向规则
[fix] handshake R0 反迎合探针误判 sycophantic
```

### 6. PR 描述模板

```markdown
## What
（具体改了什么）

## Why
（为什么要改 · 古籍出处 / 用户报错 / 回测数据）

## Test
- [ ] 端到端跑通两个 examples
- [ ] bit-for-bit deterministic 校验通过
- [ ] calibration 跑分变化（recall / fp_rate）
- [ ] 性别对称性自检通过（如适用）

## References
- 古籍出处：《XXX》卷 X
- 协议文档同步更新：references/XXX.md
```

---

## Code of Conduct

参见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

---

## License

提交 PR 即表示同意你的贡献以 MIT License 发布。
