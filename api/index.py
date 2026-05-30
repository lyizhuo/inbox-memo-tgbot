import os
import asyncio
import requests
import boto3
from datetime import datetime
from flask import Flask, request
from telegram import Bot, Update

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INBOX_TOKEN = os.getenv("INBOX_USER_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

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
    s3.put_object(Bucket=B2_BUCKET, Key=file_name, Body=file_content, ContentType='image/jpeg')
    base_url = B2_PUBLIC_URL.strip().rstrip('/')
    return f"{base_url}/{file_name}"

async def process_msg(update: Update):
    if not update.message:
        return

    # 过滤 bot 自己的消息
    if update.message.from_user and update.message.from_user.is_bot:
        return

    # 群聊：只响应 @inbox_memo_bot 的消息
    chat = update.message.chat
    if chat.type in ('group', 'supergroup'):
        bot_username = None
        text = update.message.text or update.message.caption or ""
        # 检查 entities 中是否有 mention
        if update.message.entities:
            for entity in update.message.entities:
                if entity.type == "mention":
                    mention_text = text[entity.offset:entity.offset + entity.length]
                    # 先获取 bot username 做匹配
                    async with Bot(token=TOKEN) as bot:
                        me = await bot.get_me()
                        bot_username = me.username
                        if mention_text.lower() == f"@{bot_username.lower()}":
                            break
            else:
                # 没有匹配到 @bot，检查是否根本没有 mention
                has_bot_mention = False
                if update.message.entities:
                    for entity in update.message.entities:
                        if entity.type == "mention":
                            mention_text = text[entity.offset:entity.offset + entity.length]
                            if bot_username and mention_text.lower() == f"@{bot_username.lower()}":
                                has_bot_mention = True
                                break
                if not has_bot_mention:
                    return
        else:
            # 群聊中没有 entity，说明不是 @bot 的消息
            return

    # 过滤命令
    if update.message.text and update.message.text.startswith('/'):
        return

    async with Bot(token=TOKEN) as bot:
        me = await bot.get_me()
        # 再次过滤 bot 自己
        if update.message.from_user and update.message.from_user.id == me.id:
            return

        content = ""
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

        if update.message.text:
            content += update.message.text
        elif update.message.caption:
            content += update.message.caption

        if not content.strip():
            return

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
