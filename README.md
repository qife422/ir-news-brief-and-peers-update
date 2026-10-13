# IR新闻简报与同业数据更新 Skill

An evidence-first AI + investor-relations workflow for Trip.com Group and travel/OTA peers.

把新闻与同业变化转化为**可追溯的议题、投资者问题、回答草稿和准备动作**，并保留财报、答复版本与人工确认的会议反馈。当前能力版本 **2.0.0**，规范入口为 [SKILL.md](SKILL.md)。

本仓库用于源码异地备份、能力展示和后续更新。它是可供 Codex 使用的 Skill 与本地 Python 工具，不是公司官方 IR 平台、投资建议系统或自动对外回复服务。

## 能做什么

| 能力 | 内容与边界 |
|---|---|
| 新闻与市场简报 | 授权范围内研究旅游/OTA 信号，区分事实、分析、重要性、时效及 IR 准备动作 |
| 同业数据 | 记录公司、期间、币种、单位、GAAP/调整口径、股/ADS 基准与来源；不可比数据不混算 |
| 投资者问题雷达 | 关联材料、事实、议题、问题、追问及回答草稿；对比前次报告，显示新增、变化与缺口 |
| 财报 Q&A 与预期差异 | 从现有证据准备问答；用 Decimal 计算实际值与财报前有效 consensus 的差异，缺失/不可比/零/负基数明确标记 |
| 会议准备与反馈 | 复用适用答复与历史问题；实际问题须有原始记录和人工确认，重复导入去重，撤销同步影响计数 |
| 证据与答复有效性 | 来源有版本、文段位置及时间；撤回、替代、正文变更或到期后重新判断依赖与复核状态 |
| 输出与展示 | 独立 HTML、Markdown、来源台账和数据缺口；HTML 支持搜索、筛选、键盘、移动布局与打印 |
| 受控 Excel 流程 | 提供工作簿盘点、备份、单元格级修改和回读契约；**不附自动 Excel 更新脚本** |

PDF 可从同一 HTML 经浏览器打印导出；本仓库不附专用 PDF 导出程序。

## 工作方式

Codex 按 Skill 方法读取获准材料，判断业务关联并填写议题、问题与草稿。Python 脚本负责结构校验、时间/受众投影、确定性计算及输出；**脚本不会自行联网、调用模型、搜集新闻或生成新问题**。

材料 → 有引用的事实 → 议题与变化 → 问题/追问 → 回答草稿与缺口 → 人工审阅。

来源 ID 和引用存在不等于内容已被原文充分支持。正式措辞、处理许可、问题价值及披露边界仍需有权 IR 人员判断。

## 目录

```text
ir-news-brief-and-peers-update/
├── SKILL.md                  Skill 入口、路由与保护边界
├── agents/openai.yaml        展示名称与默认提示
├── scripts/
│   ├── validate_ir_data.py   原新闻简报数据校验
│   ├── render_html_brief.py  原新闻简报 HTML 渲染
│   ├── ir_workflow.py        雷达/财报/会议校验、投影、事件与快照
│   └── render_workflow.py    工作流 HTML/Markdown 渲染
├── references/               方法、数据治理、字段与操作契约
├── examples/                 明确标记为 Example 的演示输入
├── assets/html/              独立 HTML 模板
├── tests/                    原入口及新工作流行为测试
├── prompts.md               可复制的任务请求
├── TEST_PLAN.md              测试范围与人工验收项
└── CHANGELOG.md              版本与包装变更记录
```

## 运行要求

- Python **3.9+**；四个脚本与测试均使用标准库，不需要 API Key 或 Python 第三方包。
- 系统须有 IANA 时区数据。部分 Windows 或精简环境需额外提供时区数据库，否则 `zoneinfo` 无法识别所选时区。
- 浏览器用于阅读 HTML 和打印 PDF；联网研究、Excel 操作需使用者另行提供对应工具、材料及授权。
- 下列 shell 示例面向 macOS/Linux；Windows 请将 `python3` 与 `/tmp` 输出路径替换为本机命令和一个新建的工作目录。

## 快速体验

在仓库根目录运行。以下输入全部是演示，不能作为真实公司数据或正式答复。

```bash
python3 scripts/ir_workflow.py validate examples/ir-workspace.example.json

ir_demo_dir=$(mktemp -d /tmp/ir-demo.XXXXXX)
python3 scripts/ir_workflow.py report examples/ir-workspace.example.json "$ir_demo_dir/radar.json" --mode radar
python3 scripts/render_workflow.py examples/ir-workspace.example.json "$ir_demo_dir/radar.html" --mode radar
python3 scripts/render_workflow.py examples/ir-workspace.example.json "$ir_demo_dir/earnings.html" --mode earnings
python3 scripts/render_workflow.py examples/ir-workspace.example.json "$ir_demo_dir/meeting.md" --mode meeting
python3 scripts/ir_workflow.py snapshot examples/ir-workspace.example.json "$ir_demo_dir/snapshot.json"
```

打开所选输出目录中的 HTML 即可查看。新工作流拒绝覆盖已有文件；重复运行使用新目录。core CLI 要求父目录已存在，renderer 会创建缺失父目录。`--audience public|internal` 控制投影，`--as-of` 设置带时区的截至时间，`--previous` 指向较早的同受众报告。

原新闻简报入口保持兼容：

```bash
python3 scripts/validate_ir_data.py examples/ir-brief-data.example.json
python3 scripts/render_html_brief.py examples/ir-brief-data.example.json "$ir_demo_dir/brief.html"
```

真实工作区、商业数据、会议纪要、输出及历史快照保存在使用者的业务项目，**不要放进公开 Skill 仓库**。

## 用 Skill 发起任务

```text
请使用 $ir-news-brief-and-peers-update 准备投资者问题雷达。
工作区 JSON：<路径>
主体公司与同业：Trip.com Group / Booking Holdings
截至时间与时区：<明确时间>
允许的来源与处理环境：<获准资料；是否允许公开研究>
输出受众：public 或 internal
上一份报告：<首次可空>
请输出 HTML 与 Markdown，分别标明事实、分析、预拟问题、回答草稿、缺口和准备动作。
```

财报及会议请求见 [prompts.md](prompts.md)，精确字段和 CLI 见 [workspace-schema.md](references/workspace-schema.md)。

## 丢失后恢复

在你的 Skill 规范目录的父目录（例如工作区的 `skills/`）运行：

```bash
git clone https://github.com/qife422/ir-news-brief-and-peers-update.git
cd ir-news-brief-and-peers-update
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

必须恢复**完整仓库**，不只下载 `SKILL.md`：脚本、references、模板、Example 和测试都是能力的一部分。目标目录已有同名内容时先检查并保全，禁止覆盖恢复；不要同时维护第二份可编辑规范源。使用者原有的 Skill 发现链接若已失效，应在确认目标路径后重新指向这一唯一目录。

这能恢复 GitHub 已推送的 Skill 版本；不能恢复未推送的修改、被排除的业务数据、联系人、凭据、商业快照或外部系统状态。业务数据需按自身许可与备份规则另行保护。

## 后续更新

拉取前先确认没有需要保留的本地改动：

```bash
git status --short
git pull --ff-only
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

若有本地改动或分支分叉，先保留并比较差异，不使用强制覆盖或硬重置。Git 历史可查看每个已推送版本。

维护者修改后：更新相关文档/测试及 [CHANGELOG.md](CHANGELOG.md)，运行验证，用明确的文件路径暂存，检查 staged diff，再 commit 和 push。不要为备份方便直接提交整个业务项目；不要 force push 以“修复”更新冲突。**本地 commit 不是异地备份，push 成功并核对远端才是。**

## 验证与限制

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

当前基线有 **80 项测试**，覆盖原简报入口、时间与版本、来源失效、复核 digest、受众隔离、财务口径、反馈去重/撤销、非覆写及渲染引用。详见 [TEST_PLAN.md](TEST_PLAN.md)。测试不证明真实数据许可、每条自然语言的充分支持、投资者问题概率、业务收益或正式披露合规。

输出保持 `Example` 或 `Draft`；单条回答可有已记录的复核状态，但 `Final` 仍需用户或指定审阅人明确接受。内部或 licensed 材料及其依赖不得进入公开输出，不能靠隐藏 DOM 字段代替数据隔离。

## 上传范围与授权

仓库仅包含可复用规范、代码、模板、演示输入和测试。不包含业务项目 `data/`、真实报告、内部纪要、Excel 工作簿、验证截图、临时产物、凭据、`.Rhistory` 或系统文件。`.gitignore` 是辅助防线，不代替逐文件检查。

当前未设置开源许可证；公开用于展示和本人恢复，复用或再分发前请向仓库维护者确认授权。内容不代表任何公司官方观点。
