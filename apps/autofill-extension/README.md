# CareerPilot Autofill Extension

这是 CareerPilot 的 Manifest V3 浏览器扩展 MVP。它扫描当前 ATS/招聘网站页面，把字段描述和选项发送给 CareerPilot 的 `/applications/{id}/autofill-plan`，然后只填充后端标记为 `ready` 的字段。

扩展不会点击提交、不会自动上传本地文件，也不会替未知问题猜答案。页面重新渲染或使用自定义控件时可能需要手动修正；这是浏览器自动化的边界，不能用一个通用 CSS 选择器假设所有 ATS 一致。

## 本地加载

1. 启动 CareerPilot API 并登录，复制 Access Token。
2. 打开 `chrome://extensions`，开启开发者模式，选择“加载已解压的扩展”，选中本目录。
3. 在扩展弹窗填写 API 地址、Token、申请记录 ID 和简历文档 ID。
4. 打开申请页面，先扫描，再生成计划并填写。填写后仍由用户检查并提交。

## 安全边界

Token 使用 `chrome.storage.local` 保存，仅用于访问用户自己的 CareerPilot API。生产部署应进一步限制扩展的 host permissions，并增加 Token 过期/撤销处理。
