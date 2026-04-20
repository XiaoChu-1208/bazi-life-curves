# Security Policy

## Supported Versions

| 版本 | 状态 |
|---|---|
| v7.4.x | ✅ 当前 stable |
| v7.3.x | ✅ 安全补丁支持 |
| v7.2.x | ⚠️ 仅严重漏洞 |
| < v7.2 | ❌ 不再支持 |

## 报告漏洞

- **代码执行 / 路径穿越 / 反序列化漏洞**：请通过 GitHub Private Vulnerability Reporting 提交（仓库 Security 标签页）
- **隐私泄漏类**（如脚本意外把用户八字 / confirmed_facts.json 写到 stdout / log）：请按 P0 优先级处理，48 小时内会响应
- **依赖漏洞**：直接开 issue 即可（lunar-python / matplotlib / Jinja2 / PyYAML）

## 隐私铁律

`bazi-life-curves` 处理的是用户的出生信息（八字 = 出生年月日时），属于**敏感个人信息**。任何贡献者必须：

- ❌ 禁止把用户的真实八字 / confirmed_facts.json 提交到本仓库
- ❌ 禁止在 issue / PR 描述中粘贴他人八字
- ✅ 必须确保所有日志默认不打印完整八字（应输出 `****-**-** **:**` 这类掩码）
- ✅ `output/` 目录必须保持在 `.gitignore` 中

测试用八字请使用 `examples/` 下两个虚构示例（官印相生格 / 伤官生财格），它们与真实人物无关。
