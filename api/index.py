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

async def process_msg(update: Update):
    if not update.message:
        return

    # 过滤 bot 自己的消息，防止 echo 循环
    # 注意：这是通过检查消息发送者是否为 bot 自己来实现的
    # 我们需要获取 bot 的信息来比较
    # 但在处理每条消息时获取 bot 信息会增加开销，这里采用简化方法
    # 或者我们可以在应用启动时获取并缓存 bot 信息
    # 为了简单起见，我们在这里检消息中是否有明确的 bot 标识
    # 实际上，最可靠的方法是在处理消息时获取 bot 信息
    # 但由于这是一个简单的 bot，我们可以接受每次查询的开销
    # 或者，我们可以假设如果消息来自一个 bot，那么它可能是我们自己
    # 不过更准确的做法是获取 bot 信息
    
    # 获取 bot 自己的信息（为了过滤自己发送的消息）
    # 注意：这个操作会增加每条消息的处理时间，但这是必要的
    try:
        async with Bot(token=TOKEN) as bot:
            me = await bot.get_me()
            # 过滤 bot 自己的消息
            if update.message.from_user and update.message.from_user.id == me.id:
                return
    except Exception as e:
        print(f"Error getting bot info: {e}")
        # 如果无法获取 bot 信息，则继续处理（可能会有轻微风险的 self-echo）
        pass

    # 1. 过滤命令（如 /start）
    if update.message.text and update.message.text.startswith('/'):
        return

    # 2. 处理消息内容
    async with Bot(token=TOKEN) as bot:
        content = ""

        # 如果包含图片，先上传图片
        if update.message.photo:
            try:
                photo = update.message.photo[-1]
                file = await bot.get_file(photo.file_id)
                file_bytes = requests.get(file.file_path).content
                file_name = f"inbox/{datetime.now().strftime('%Y%m%d%H%M%S')}_{photo.file_id[:8]}.jpg"

                img_url = await upload_to_b2(file_bytes, file_name)
                content = f"![]({img_url.strip()})
"
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
