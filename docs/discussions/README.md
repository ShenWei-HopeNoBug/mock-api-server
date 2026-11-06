# discussions/ — 思维碰撞记录

探索性方案讨论、竞品分析、方向推演的**记录性文档**。
不承诺实施；讨论收敛并立项后，实施文档归 `plans/`，本文档保留作背景依据。

## 文档索引

| 文档 | 说明 |
|---|---|
| [PRODUCT_DIRECTION_DISCUSSION](PRODUCT_DIRECTION_DISCUSSION.md) | 产品定位、业界方案对比与迭代方向讨论记录 |
| [TEST_GROUP_DESIGN_DISCUSSION](TEST_GROUP_DESIGN_DISCUSSION.md) | 测试组（测试任务）概念与 Playwright 编排方案讨论记录 |

## 命名

- SCREAMING_SNAKE_CASE，以 `_DISCUSSION` 结尾
- 例：`TEST_GROUP_DESIGN_DISCUSSION.md`

## 约定

- 文档头部标注：讨论日期、参与者、快照性质声明
- 已立项实施的讨论：头部追加「已立项：<plans/ 链接>」，正文冻结
- 后续讨论轮次：文末新开「续：YYYY-MM-DD」节追加，不改写既有内容
- 与 `reports/` 的界限：reports 记对现状的评审结论/问题台账；
  discussions 记对未来的探索、选项与取舍推理
