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
B2_ENDPOINT = os.getenv("B2_ENDPOINT") # 如 s3.us-west-004.backblazeb2.com
B2_PUBLIC_URL = os.getenv("B2_PUBLIC_URL") # 如 https://f004.backblazeb2.com/file/your-bucket/

#bot = Bot(token=TOKEN)
s3 = boto3.client(
    's3',
    endpoint_url=f'https://{B2_ENDPOINT}',
    aws_access_key_id=B2_KEY_ID,
    aws_secret_access_key=B2_APP_KEY
)

async def upload_to_b2(file_content, file_name):
    """将文件上传到 Backblaze B2"""
    s3.put_object(Bucket=B2_BUCKET, Key=file_name, Body=file_content, ContentType='image/jpeg')
    return f"{B2_PUBLIC_URL.rstrip('/')}/{file_name}"

async def process_msg(update: Update):
    if not update.message or str(update.message.from_user.id) != ALLOWED_USER_ID:
        return

    # 1. 过滤命令
    if update.message.text and update.message.text.startswith('/'):
        return

    # 在函数内部使用 async with 确保生命周期管理
    async with Bot(token=TOKEN) as bot:
        content = ""
        
        # 2. 处理图片 (逻辑保持不变)
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await bot.get_file(photo.file_id)
            file_bytes = requests.get(file.file_path).content
            file_name = f"inbox/{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.file_id[:8]}.jpg"
            
            try:
                img_url = await upload_to_b2(file_bytes, file_name)
                content = f"![]( {img_url} )\n"
            except Exception as e:
                await bot.send_message(chat_id=update.message.chat_id, text=f"⚠️ 图片上传失败: {str(e)}")
                return

        if update.message.text:
            content += update.message.text
        elif update.message.caption:
            content += update.message.caption

        if not content: return

        # 3. 发送到 inBox (同步请求)
        inbox_api = f'https://api.gudong.site/inbox/{INBOX_TOKEN}'
        try:
            res = requests.post(inbox_api, json={"content": content, "title": "TG 随手记"}, timeout=10)
            if res.json().get("code") == 0:
                # 4. 回复用户
                await bot.send_message(chat_id=update.message.chat_id, text="✅ 已存入 inBox")
        except Exception as e:
            # 如果这里报错，也会尝试通过 bot 发送，所以外面也要包一层
            pass 

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        # 这里仅解析 update，不持有 bot 实例
        update = Update.de_json(data, Bot(token=TOKEN)) 
        asyncio.run(process_msg(update))
    except Exception as e:
        print(f"Error: {e}")
    return 'ok', 200
