import os
import requests
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application

app = Flask(__name__)

# 从环境变量获取配置（安全起见，不要写死在代码里）
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INBOX_TOKEN = os.getenv("INBOX_USER_TOKEN")
# 建议加上你的 Telegram User ID，防止别人刷你的 API 额度
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID") 

bot = Bot(token=TOKEN)

@app.route('/api/webhook', methods=['POST'])
async def respond():
    update = Update.de_json(request.get_json(force=True), bot)
    
    # 权限校验：只处理你发送的消息
    if str(update.message.from_user.id) != ALLOWED_USER_ID:
        return 'Unauthorized', 403

    if update.message.text:
        text = update.message.text
        inbox_url = f'https://api.gudong.site/inbox/{INBOX_TOKEN}'
        
        payload = {
            "content": text,
            "title": "来自 Telegram"
        }
        
        try:
            res = requests.post(inbox_url, json=payload, timeout=5)
            if res.json().get("code") == 0:
                await bot.send_message(chat_id=update.message.chat_id, text="✅ 已同步到 inBox")
            else:
                await bot.send_message(chat_id=update.message.chat_id, text=f"❌ 失败: {res.json().get('msg')}")
        except Exception as e:
            await bot.send_message(chat_id=update.message.chat_id, text=f"⚠️ 错误: {str(e)}")

    return 'ok'

@app.route('/')
def index():
    return "Bot is running..."