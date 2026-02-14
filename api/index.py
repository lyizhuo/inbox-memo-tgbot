import os
import asyncio
import requests
from flask import Flask, request
from telegram import Bot, Update

app = Flask(__name__)

# 从环境变量读取（请确保在 Vercel 后台已配置）
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INBOX_TOKEN = os.getenv("INBOX_USER_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

bot = Bot(token=TOKEN)

async def process_msg(update: Update):
    # 权限检查
    if str(update.message.from_user.id) != ALLOWED_USER_ID:
        return
    
    if update.message.text:
        text = update.message.text
        inbox_api = f'https://api.gudong.site/inbox/{INBOX_TOKEN}'
        
        # 构造发送给 inBox 的数据
        payload = {
            "content": text,
            "title": "Telegram 笔记"
        }
        
        try:
            # 使用 requests 发送同步请求（在 Serverless 中这样最稳妥）
            res = requests.post(inbox_api, json=payload, timeout=8)
            res_data = res.json()
            
            msg_text = "✅ 已同步到 inBox" if res_data.get("code") == 0 else f"❌ 失败：{res_data.get('msg')}"
            await bot.send_message(chat_id=update.message.chat_id, text=msg_text)
        except Exception as e:
            await bot.send_message(chat_id=update.message.chat_id, text=f"⚠️ 请求出错: {str(e)}")

@app.route('/api/webhook', methods=['POST'])
def webhook():
    # Vercel 的 Flask 运行在 WSGI 下，处理异步需要一点小技巧
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(process_msg(update))
    return 'ok', 200

@app.route('/')
def index():
    return "Bot is running..."