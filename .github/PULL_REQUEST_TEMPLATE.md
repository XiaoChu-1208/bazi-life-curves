<!--
  PR 标题格式：[scripts/score_curves] 添加化气格 phase override
  详见 CONTRIBUTING.md
-->

## What · 改了什么

<!-- 一两句话说清这个 PR 干了什么 -->

## Why · 为什么改

<!-- 古籍出处 / 用户报错 / 回测数据驱动 -->

- 古籍出处：
- 关联 issue：#

## How · 怎么改的

<!-- 关键设计选择、为什么不用其他方案 -->

## Tests · 测试

- [ ] 端到端跑通 `examples/guan_yin_xiang_sheng` 与 `examples/shang_guan_sheng_cai`
- [ ] bit-for-bit deterministic 校验通过（同输入 sha256sum 一致）
- [ ] `scripts/calibrate.py` 跑分变化（请贴 recall / fp_rate 前后对比）
- [ ] 性别对称性自检通过（同八字翻转性别 → spirit/wealth/fame byte-equal）
- [ ] 协议文档已同步更新（references/）

## fairness_protocol §10 自检

- [ ] 没有引入"克夫 / 旺夫 / 配偶星弱 = 差 / 单身 = 差" 类措辞
- [ ] 没有把 `--orientation` 的 5 选项硬编码为 hetero 默认
- [ ] emotion 解读保持中性 relationship_mode

## Breaking changes · 破坏性改动

- [ ] 无
- [ ] 有（请描述影响 + 迁移路径）

## License

- [ ] 我同意以 MIT License 贡献此 PR
