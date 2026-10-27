# CareerPilot Autofill Extension

CareerPilot 的 Manifest V3 浏览器扩展。它扫描当前 ATS/招聘网站页面，把字段描述和选项发送给 CareerPilot 的 `/applications/{id}/autofill-plan`，然后只填充后端标记为 `ready` 的字段。

扩展不会点击提交、不会自动上传本地文件，也不会替未知问题猜答案。页面重新渲染或使用自定义控件时可能需要手动修正；这是浏览器自动化的边界，不能用一个通用 CSS 选择器假设所有 ATS 一致。

## 本地加载

1. 启动 CareerPilot API 并登录，复制 Access Token。
2. 打开 `chrome://extensions`，开启开发者模式，选择“加载已解压的扩展”，选中本目录。
3. 在扩展弹窗填写 API 地址、Token、投递记录 ID 和简历文档 ID。
4. 打开投递页面，先扫描，再生成计划并填写。填写后仍由用户检查并提交。

## 网申个人信息的三条同步通道（plan §5.1.4）

| 通道 | 机制 | 前置条件 |
|---|---|---|
| ① 直连 | 页面 `chrome.runtime.sendMessage(extensionId, {type:'CAREERPILOT_PROFILE_SYNC', ...})` → `background.js` 的 `onMessageExternal` 写入 `chrome.storage.local`，并回 `{ok, profileVersion}` | 在 CareerPilot「网申个人信息」页填入扩展 ID |
| ② 页面存储 | `content.js` 在页面打上 `data-careerpilot-ext` 标记，页面据此提示可用；精简快照写在 `localStorage['careerpilot.profile.v1.sync']`（不含敏感字段） | 扩展已注入该页面 |
| ③ JSON 粘贴 | 弹窗里粘贴导出的 JSON，校验 `schemaVersion` 后保存 | 无 |

`externally_connectable` 只允许本机 `localhost:8080` / `127.0.0.1:8080`（以及 Vite 默认的 5173）调用，避免任意站点推送数据。

同步冲突按 `profileVersion` 判定，新者胜；同一版本重复推送不会重复写入。

## 安全边界

- Token 使用 `chrome.storage.local` 保存，仅用于访问用户自己的 CareerPilot API。生产部署应进一步限制扩展的 host permissions，并增加 Token 过期/撤销处理。
- 个人信息默认剔除身份证号、学号；只有在页面显式勾选「包含敏感字段」后才会出现在同步载荷里。
- 扩展本身不发 AI 请求：LLM 增强只发生在网页端与本机 API 之间。
