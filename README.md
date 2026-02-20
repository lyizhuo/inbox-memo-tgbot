# Telegram to inBox Sync Bot

这是一个轻量级的 Telegram 机器人，旨在将你的随手笔记、灵感以及图片自动同步到 [inBox](https://inbox.gudong.site/#/) 软件。

## 🌟 功能特性

* **文本同步**：发送文字消息即可自动同步至 inBox。
* **图片支持**：发送图片后，Bot 会自动将其上传至 Backblaze B2，并以 Markdown 格式 `![](url)` 存入笔记。
* **命令过滤**：自动忽略 `/start`、`/help` 等以 `/` 开头的 Telegram 命令，避免垃圾数据。
* **权限校验**：通过 `ALLOWED_USER_ID` 限制使用者，确保你的 inBox 接口额度不被他人消耗。
* **零成本部署**：基于 Vercel 和 Backblaze B2 的免费额度，实现全链路 0 成本运行。

## 🛠️ 技术栈

* **语言**: Python 3.10+
* **框架**: Flask (Serverless Mode)
* **库**: `python-telegram-bot` (异步处理), `boto3` (S3 兼容 API)
* **部署平台**: Vercel

## 🚀 部署步骤

### 1. 准备工作

* 在 [@BotFather](https://t.me/botfather) 处获取你的 **Telegram Bot Token**。
* 获取你的 **inBox UserToken**。
* 在 **Backblaze B2** 创建一个 Bucket，获取 `Key ID`、`Application Key` 和 `Endpoint`。

### 2. 环境配置

在 Vercel 项目设置中，添加以下环境变量（Environment Variables）：

| 变量名 | 说明 | 示例 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Telegram 机器人令牌 | `123456:ABC-DEF...` |
| `INBOX_USER_TOKEN` | inBox 的 API Token | `your_token_here` |
| `ALLOWED_USER_ID` | 你的 Telegram 用户 ID | `123456789` |
| `B2_KEY_ID` | B2 的 Key ID | `0046...` |
| `B2_APP_KEY` | B2 的 Application Key | `K004...` |
| `B2_BUCKET` | B2 的桶名称 | `my-inbox-img` |
| `B2_ENDPOINT` | B2 的 S3 接口地址 | `s3.us-west-004.backblazeb2.com` |
| `B2_PUBLIC_URL` | 图片公开访问的前缀 URL | `https://f004.backblazeb2.com/file/bucket/` |

### 3. 代码上传与部署

1. 将本项目代码推送到你的 GitHub 仓库。
2. 在 Vercel 后台导入该仓库。
3. 部署完成后，你将获得一个域名（例如 `https://inbox-bot.vercel.app`）。

### 4. 激活 Webhook

在浏览器访问以下链接（替换你的实际信息），让 Telegram 开始向你的 Vercel 发送消息：

```text
https://api.telegram.org/bot<你的BOT_TOKEN>/setWebhook?url=https://<你的VERCEL域名>/api/webhook
```

## 📂 项目结构

```text
.
├── api/
│   └── index.py        # 核心逻辑：处理 Webhook、上传 B2、调用 inBox
├── requirements.txt    # 项目依赖
├── vercel.json         # Vercel 路由配置
└── README.md           # 项目说明文档

```

## 📝 注意事项

* **请求频率**：inBox API 每天限制上传 50 条笔记，请注意使用频率。
* **图片大小**：受 Vercel 免费版函数运行时间（10s）限制，建议不要发送过大的原图，以免上传超时。
* **上传的图片暂时无法在Inbox正常显示**：受Inbox限制，透过API上传的图片链接似乎无法在APP中正常显示
