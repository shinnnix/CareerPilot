# CareerPilot 网申自动填写调研与设计

## 调研结论

现有开源项目大致分为两类：浏览器扩展负责读取和写入 ATS 页面；桌面/本地自动化应用负责搜索职位、生成材料、用 Playwright 操作浏览器。值得参考的实现包括：

- [Resume Bridge](https://github.com/cloud-oc/resume-bridge)：Manifest V3，支持字段扫描、规则/语义匹配、开放题草稿、Greenhouse/Lever/北森/Moka 等站点适配，默认把资料和密钥放在浏览器 IndexedDB。
- [geckguy/AutoApply](https://github.com/geckguy/AutoApply)：本地后端加扩展，保存 profile、fill rules、saved answers 和 learned corrections，支持多页表单并在提交前停止。
- [ritsth/job-autofill-extension](https://github.com/ritsth/job-autofill-extension)：按 ATS 拆分 Greenhouse、Lever、Workday、Ashby 适配器，提供可编辑开放题答案和资格/签证提示。
- [AbhishekMandapmalvi/AutoApply](https://github.com/AbhishekMandapmalvi/AutoApply)：本地桌面应用，覆盖职位搜索、简历/求职信生成、Playwright 填写以及多个 ATS，但自动化范围更大、运行依赖更多。
- [S03-5/resume-autofill](https://github.com/S03-5/resume-autofill)：面向中文招聘网站的扩展，支持简历识别、字段记忆、撤销和申请台账。
- [abhayiitbhu/jobs-auto-apply](https://github.com/abhayiitbhu/jobs-auto-apply)：把回答解析分成已确认记忆、结构化 profile、RAG、LLM 四层，低置信问题进入 pending queue，不直接猜测。

## 共同不足

1. **字段语义和来源不可验证。** 很多实现把模型输出直接写入 DOM，无法回答“这个电话/工作年限来自哪段材料”。CareerPilot 的计划字段包含 `source_id`、`evidence`、`confidence` 和 `status`，并保存 `autofill_runs` 审计记录。
2. **未知问题容易被模型补全。** 签证、薪资、工作年限、授权声明等错误代价很高。CareerPilot 对开放题、文件上传和未识别字段只生成 `review`/`unsupported`，不会自动填写。
3. **ATS 页面不是稳定 HTML。** Workday 等页面会重新渲染，自定义控件、分页和 shadow DOM 会让通用 selector 失效。扩展只使用当前可见字段的稳定 `id/name`，并把站点适配器留作后续增量，不伪装成“所有网站都可靠”。
4. **自动提交和批量投递带来合规与质量风险。** 竞品即使有 review mode，也常常把搜索、生成、填写、提交串成自动流水线。CareerPilot 的扩展没有提交权限，申请状态仍由现有状态机和用户操作推进。
5. **隐私边界模糊。** 云端 LLM 可能接收整份简历和敏感申请信息。CareerPilot 复用已有用户隔离和文档安全扫描；扩展只发送当前表单字段计划，Token 用于用户自己的 API，后续可增加本地模型和字段级脱敏。

## 当前集成

后端新增 `POST /api/v1/applications/{application_id}/autofill-plan`：请求包含简历文档 ID 和当前页面字段，响应包含每个字段的值、置信度、来源、证据和审核状态。计划生成后会写入 `autofill_runs`，但不会改变申请状态。

`apps/autofill-extension` 是一个无需构建工具的 Manifest V3 MVP：扫描 `input`、`textarea`、`select`，调用上述接口，只填写 `ready` 字段，跳过文件输入和开放题。用户仍然检查页面并手动提交。

## 下一步

- 增加 ATS adapter 接口和 Greenhouse/Lever 的可访问名称定位，减少对 CSS selector 的依赖。
- 给 `review` 字段增加人工修正回写，形成按站点和字段的确认记忆；记忆必须绑定用户和来源，不能把一次修正当成全局事实。
- 增加字段级脱敏、Token 过期处理和扩展权限白名单。
- 为动态多页表单增加页面快照、DOM 变化检测和可重试的填充步骤，但继续禁止自动提交。
