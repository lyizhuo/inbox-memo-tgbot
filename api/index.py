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
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

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
    # 确保 URL 拼接没有空格
    base_url = B2_PUBLIC_URL.strip().rstrip('/')
    return f"{base_url}/{file_name}"

async def process_msg(update: Update):
    if not update.message or str(update.message.from_user.id) != ALLOWED_USER_ID:
        return

    # 1. 过滤命令（如 /start）
    if update.message.text and update.message.text.startswith('/'):
        return

    async with Bot(token=TOKEN) as bot:
        content = ""
        
        # 2. 如果包含图片，先上传图片
        if update.message.photo:
            try:
                photo = update.message.photo[-1]
                file = await bot.get_file(photo.file_id)
                file_bytes = requests.get(file.file_path).content
                file_name = f"inbox/{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.file_id[:8]}.jpg"
                
                img_url = await upload_to_b2(file_bytes, file_name)
                # 修复后的紧凑 Markdown 格式
                content = f"![]({img_url.strip()})\n"
            except Exception as e:
                await bot.send_message(chat_id=update.message.chat_id, text=f"⚠️ 图片上传失败: {str(e)}")
                return # 图片上传失败则中断，防止发送残缺笔记

        # 3. 处理文本内容
        # 如果是图片消息，文字在 caption 中；如果是纯文字消息，文字在 text 中
        if update.message.text:
            content += update.message.text
        elif update.message.caption:
            content += update.message.caption

        # 如果最终既没有图片也没有文字，则不处理
        if not content.strip():
            return

        # 4. 发送到 inBox (同步请求)
        inbox_api = f'https://api.gudong.site/inbox/{INBOX_TOKEN}'
        try:
            res = requests.post(inbox_api, json={"content": content, "title": "TG 随手记"}, timeout=10)
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
