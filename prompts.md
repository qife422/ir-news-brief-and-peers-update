# Prompt Templates

## Investor question radar

```text
请使用 $ir-news-brief-and-peers-update 准备携程投资者问题雷达。
工作区JSON路径：
截至时间与时区：
输出受众和允许使用的资料：
上一份报告路径（首次可空）：
重点议题及同业：

请核对原始证据，分别呈现事实、条件分析、候选问题、追问、回答草稿和缺口。
生成Markdown与HTML；公开文件只使用获准的公开证据，保留Draft并说明待审阅项。
```

## Earnings preparation

```text
请使用 $ir-news-brief-and-peers-update 准备财报Q&A。
工作区JSON路径：
财报季度、真实发布时间与准备截止时间：
实际业绩与获准consensus快照路径：
输出受众：

按可比口径计算差异，缺少有效预期时保留缺口。
从已有议题与公司公开口径准备问题和追问，不生成未披露指引。
答复按版本和证据复核，输出供管理层演练的Draft材料。
```

## Meeting preparation and feedback

```text
请使用 $ir-news-brief-and-peers-update 准备投资者会议Brief并整理反馈。
工作区JSON和获准会议记录路径：
会议日期及输出受众：
哪些真实问题已由谁确认：
待办责任人及时间（未提供则标为待指定）：

区分真实、预拟和转述问题；重复导入不增加计数，确认撤销要保留历史。
生成会前问题与适用答复、会后待办。不要外发、录音或写外部CRM。
```

## HTML IR Intelligence Brief

```text
请使用 $ir-news-brief-and-peers-update 生成 Trip.com Group IR Intelligence Brief。

交付格式：HTML，可打印为 PDF
报告状态：Draft
截至时间与时区：
覆盖时间窗口：
地区范围：
公司范围：
允许的来源：
是否允许公开搜索：
是否包含同业估值：
同业数据来源与截至时间：

要求：
1. 事实、分析、IR含义和数据缺口分层。
2. 展示重要性、影响方向、影响期限和IR动作。
3. 使用图表、图文新闻卡片和来源台账。
4. 只使用真实且有来源的图片；没有图片时保留无图状态。
5. 所有新闻与财务数据可追溯到 Source ID。
6. 先验证结构化数据，再生成HTML。
```

## Peer Workbook Update

```text
请使用 $ir-news-brief-and-peers-update 更新同业数据工作簿。

Excel文件路径：
目标公司与季度：
权威数据来源：
需要更新的指标：
是否允许检索官方IR、earnings release或SEC filing：

请先备份并盘点公式、命名范围、图表和隐藏Sheet。更新后报告：
1. 备份路径。
2. 修改的Sheet和单元格。
3. 修改前后值、单位、期间和Source ID。
4. 公式、格式、命名范围和图表引用的验证结果。
5. 剩余人工检查。
```
