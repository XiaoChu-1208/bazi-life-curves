# 安装指南

`bazi-life-curves` 遵循 [Anthropic Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) 通用规范。
一份产物，三处可用：Claude Desktop、Claude Code、Cursor。

## 主存放路径

推荐主存放在 `~/.claude/skills/bazi-life-curves/`，其他宿主用软链 / 复制方式接入。

## 1. Claude Desktop

确认 `~/.claude/skills/` 目录存在且 Claude Desktop 已启用 skill 扫描。

```bash
mkdir -p ~/.claude/skills
# 把当前目录复制 / 软链到 ~/.claude/skills/bazi-life-curves
ls ~/.claude/skills/bazi-life-curves/SKILL.md
# → 应能看到此文件
```

重启 Claude Desktop。在新对话中输入「画一下八字 庚午 辛巳 壬子 丁未 男 1990 的人生曲线」即可触发。

## 2. Claude Code

### 个人级（默认所有 Claude Code 项目可用）

```bash
mkdir -p ~/.claude/skills
ln -sf ~/.claude/skills/bazi-life-curves ~/.claude/skills/bazi-life-curves
```

### 项目级（仅当前项目可用）

```bash
cd <your-project>
mkdir -p .claude/skills
ln -sf ~/.claude/skills/bazi-life-curves .claude/skills/bazi-life-curves
```

## 3. Cursor

Cursor 的 user-level skill 目录是 `~/.cursor/skills-cursor/`。

```bash
mkdir -p ~/.cursor/skills-cursor
ln -sf ~/.claude/skills/bazi-life-curves ~/.cursor/skills-cursor/bazi-life-curves
```

也可以放到项目级 `<project>/.cursor/skills/` 或 `<project>/.cursor/skills-cursor/`。

## 4. 通用 / 其他 Agent SDK

只要 agent 框架支持「读 SKILL.md frontmatter + description 决定是否触发 + 加载主体 + 调用 scripts/」即可。
SKILL.md 已合规：

- `name` 全小写、连字符、≤64 字符、不含保留词
- `description` 含触发词
- `references/` / `scripts/` 渐进加载

## 5. 安装 Python 依赖

```bash
cd ~/.claude/skills/bazi-life-curves
pip install -r requirements.txt
```

依赖：

- `lunar-python`：公历 ↔ 干支转换
- `matplotlib`：PNG fallback 渲染
- `PyYAML`：calibration / personal 配置
- `Jinja2`：HTML Artifact 模板

## 6. 首次使用前自检

```bash
cd ~/.claude/skills/bazi-life-curves

# 回测命中率（v1 baseline 阈值）
python3 scripts/calibrate.py

# 性别对称性测试（同八字男女除大运方向外基线必须一致）
python3 scripts/calibrate.py --symmetry

# 重新生成两个示例的图（验证渲染管线）
cd examples
python3 ../scripts/solve_bazi.py --pillars "丁巳 甲辰 戊寅 庚申" --gender M --birth-year 1977 --out shang_guan_sheng_cai.bazi.json
python3 ../scripts/score_curves.py --bazi shang_guan_sheng_cai.bazi.json --out shang_guan_sheng_cai.curves.json --strict --age-cap 60
python3 ../scripts/render_artifact.py --curves shang_guan_sheng_cai.curves.json --out shang_guan_sheng_cai.html
python3 ../scripts/render_chart.py --curves shang_guan_sheng_cai.curves.json --out shang_guan_sheng_cai.png
open shang_guan_sheng_cai.html  # 浏览器看 HTML
open shang_guan_sheng_cai.png   # 看 PNG
```

通过条件：

1. `calibrate.py` 输出 `[calibrate] PASS`
2. `calibrate.py --symmetry` 输出 `[symmetry] PASS`
3. `score_curves.py --strict` 输出 `strict double-blind: OK`
4. HTML 浏览器打开能看到 6 条曲线 + 大运色带 + 拐点标注 + 可 hover
5. PNG 中文不乱码、布局与 HTML 一致

## 7. 触发方式

在对话中输入以下任一形式即可触发：

- 「画一下八字 庚午 辛巳 壬子 丁未 男 1990 的人生曲线」
- 「我的公历生辰是 1990-05-12 14:30 男，看看 50 年大运曲线」
- 「画八字曲线」/「人生曲线图」/「大运走势图」/「流年趋势图」/「命理趋势图」

LLM 会读 `SKILL.md`，按工作流调用 `scripts/`，并根据当前宿主能力选择 HTML Artifact 或 PNG 输出。

## 8. 卸载

```bash
# Claude Desktop / Code 个人级
rm -rf ~/.claude/skills/bazi-life-curves

# Cursor 软链
rm ~/.cursor/skills-cursor/bazi-life-curves

# 项目级
rm <your-project>/.claude/skills/bazi-life-curves
rm <your-project>/.cursor/skills/bazi-life-curves
```

## 9. 升级 / 调试

- 算法改动后必须跑 `python3 scripts/calibrate.py` 验证不退化
- 所有评分由脚本生成，LLM **不直接改数字**（见 `references/fairness_protocol.md`）
- 报 bug 时附带 `bazi.json` + `curves.json` 即可复现（不含身份信息）
