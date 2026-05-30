import os
import asyncio
import requests
import boto3
from datetime import datetime
from flask import Flask, request
from telegram import Bot, Update

app = Flask(__name__)

# 配置信息（从 Vercel 环境变量读取）
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INBOX_TOKEN = os.getenv("INBOX_USER_TOKEN")
# 逗号分隔的允许用户 ID 列表；为空则允许所有人（仅用于群聊鉴权）
ALLOWED_USER_IDS = set(
    uid.strip() for uid in os.getenv("ALLOWED_USER_ID", "").split(",") if uid.strip()
)
# 群聊中只响应 @bot 的消息；设为 False 则响应所有消息（需同时设 ALLOWED_USER_IDS 鉴权）
GROUP_ONLY_MENTION = os.getenv("GROUP_ONLY_MENTION", "true").lower() == "true"

# B2 配置
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APP_KEY = os.getenv("B2_APP_KEY")
B2_BUCKET = os.getenv("B2_BUCKET")
B2_ENDPOINT = os.getenv("B2_ENDPOINT")
B2_PUBLIC_URL = os.getenv("B2_PUBLIC_URL")

s3 = boto3.client(
    's3',
    endpoint_url=f'https://{B2_ENDPOINT}',
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APP_KEY
)

async def upload_to_b2(file_content, file_name):
    """将文件上传到 Backblaze B2"""
    s3.put_object(Bucket=B2_BUCKET, Key=file_name, Body=file_content, ContentType='image/jpeg')
    base_url = B2_PUBLIC_URL.strip().rstrip('/')
    return f"{base_url}/{file_name}"


def is_bot_message(update: Update, bot_username: str) -> bool:
    """判断消息是否是 bot 自己发的（防止 bot echo 循环）"""
    if update.message and update.message.from_user:
        user = update.message.from_user
        # 通过 username 或 id 判断是否是自身
        if bot_username and user.username and user.username.lower() == bot_username.lower():
            return True
    # 检查 entities 中是否有 mention 指向自己
    if update.message and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mention_text = update.message.text[entity.offset:entity.offset + entity.length]
                if bot_username and mention_text.lower() == f"@{bot_username.lower()}":
                    # 这条消息包含 @bot，说明不是 bot 自己发的（bot 不会 @自己）
                    return False
    return False


def should_process_group_message(update: Update, bot_username: str) -> bool:
    """群聊中判断是否应处理此消息"""
    if not update.message:
        return False

    chat = update.message.chat
    chat_type = getattr(chat, 'type', '')

    # 私聊：始终处理（后续会走 ALLOWED_USER_IDS 鉴权）
    if chat_type == 'private':
        return True

    # 群聊 / 超级群聊：只处理包含 @bot 的 mention 消息
    if GROUP_ONLY_MENTION and bot_username:
        text = update.message.text
        if not text:
            return False
        entities = update.message.entities
        if entities:
            for entity in entities:
                if entity.type == "mention":
                    mention_text = text[entity.offset:entity.offset + entity.length]
                    if mention_text.lower() == f"@{bot_username.lower()}":
                        return True
        return False

    return True


def is_authorized(user_id: int) -> bool:
    """检查用户是否被允许使用 bot"""
    if not ALLOWED_USER_IDS:
        return True  # 不设限制则允许所有人
    return str(user_id) in ALLOWED_USER_IDS


async def process_msg(update: Update):
    if not TOKEN:
        return
    async with Bot(token=TOKEN) as bot:
        # 获取 bot 自己的 username（用于 self-message 过滤和 mention 匹配）
        me = await bot.get_me()
        bot_username: str = me.username or ""

        # 过滤 bot 自己的消息（通过判断消息是否包含 @自己 来识别）
        if update.message and update.message.from_user and me.id == update.message.from_user.id:
            return

        # 群聊 mention 过滤
        if not should_process_group_message(update, bot_username):
            return

        if not update.message:
            return

        # 用户 ID 鉴权
        if not is_authorized(update.message.from_user.id):
            return

        # 过滤命令（如 /start）
        if update.message.text and update.message.text.startswith('/'):
            return

        content = ""

        # 如果包含图片，先上传图片
        if update.message.photo:
            try:
                photo = update.message.photo[-1]
                file = await bot.get_file(photo.file_id)
                file_bytes = requests.get(file.file_path).content
                file_name = f"inbox/{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.file_id[:8]}.jpg"

                img_url = await upload_to_b2(file_bytes, file_name)
                content = f"![]({img_url.strip()})\n"
            except Exception as e:
                await bot.send_message(chat_id=update.message.chat_id, text=f"⚠️ 图片上传失败: {str(e)}")
                return

        # 处理文本内容
        if update.message.text:
            content += update.message.text
        elif update.message.caption:
            content += update.message.caption

        if not content.strip():
            return

        # 发送到 inBox
        inbox_api = f'https://api.gudong.site/inbox/{INBOX_TOKEN}'
        try:
            res = requests.post(inbox_api, json={"content": content}, timeout=10)
            if res.json().get("code") == 0:
                await bot.send_message(chat_id=update.message.chat_id, text="✅ 已存入 inBox")
            else:
                await bot.send_message(chat_id=update.message.chat_id, text=f"❌ inBox 报错: {res.json().get('msg')}")
        except Exception as e:
            print(f"Sync error: {e}")


@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, Bot(token=TOKEN))
        asyncio.run(process_msg(update))
    except Exception as e:
        print(f"Webhook Error: {e}")
    return 'ok', 200
