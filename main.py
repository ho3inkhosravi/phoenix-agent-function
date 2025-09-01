import os
import json
import requests
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

# این تابع اصلی است که توسط Appwrite اجرا می‌شود
def main(req, res):
    # --- ۱. مقداردهی اولیه و خواندن متغیرهای محیطی ---
    try:
        client = Client()
        client.set_endpoint(os.environ["APPWRITE_ENDPOINT"])
        client.set_project(os.environ["APPWRITE_PROJECT_ID"])
        client.set_key(os.environ["APPWRITE_API_KEY"])
        databases = Databases(client)

        GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
        TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
        DATABASE_ID = "ai_agent"
        USERS_COLLECTION_ID = "users"
        HISTORY_COLLECTION_ID = "chat_history"

    except Exception as e:
        print(f"Error initializing: {e}")
        return res.json({'status': 'error', 'message': 'Initialization failed'}, 500)

    # --- ۲. پردازش درخواست ورودی از تلگرام ---
    try:
        body = json.loads(req.body)
        message = body.get("message", {})
        user_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        user_text = message.get("text")
        first_name = message.get("from", {}).get("first_name", "")
        username = message.get("from", {}).get("username", "")

        if not all([user_id, chat_id, user_text]):
            return res.json({'status': 'ok', 'message': 'Not a user message.'})
    except Exception as e:
        print(f"Error parsing Telegram webhook: {e}")
        return res.json({'status': 'error', 'message': 'Invalid request body'}, 400)

    # --- ۳. پیدا کردن یا ایجاد کاربر در Appwrite ---
    appwrite_user_id = None
    try:
        query = Query.equal("userId", user_id)
        response = databases.list_documents(DATABASE_ID, USERS_COLLECTION_ID, queries=[query])
        
        if response['total'] > 0:
            appwrite_user_id = response['documents'][0]['$id']
        else:
            new_user_doc = databases.create_document(
                DATABASE_ID,
                USERS_COLLECTION_ID,
                ID.unique(),
                {'userId': user_id, 'firstName': first_name, 'username': username}
            )
            appwrite_user_id = new_user_doc['$id']
    except Exception as e:
        print(f"Error finding/creating user: {e}")
        return res.json({'status': 'error', 'message': 'Database user operation failed'}, 500)

    # --- ۴. بازیابی تاریخچه مکالمات ---
    history_for_gemini = []
    try:
        query_user = Query.equal("user", [appwrite_user_id])
        query_order = Query.order_desc("$createdAt")
        query_limit = Query.limit(10) # دریافت ۱۰ پیام آخر
        response = databases.list_documents(DATABASE_ID, HISTORY_COLLECTION_ID, queries=[query_user, query_order, query_limit])
        
        # معکوس کردن لیست تا ترتیب پیام‌ها درست شود (قدیمی به جدید)
        documents = reversed(response['documents'])
        for doc in documents:
            history_for_gemini.append({"role": doc['role'], "parts": [{"text": doc['optimized_content']}]})
    except Exception as e:
        print(f"Error getting chat history: {e}")
        # ادامه می‌دهیم حتی اگر تاریخچه یافت نشد

    # --- ۵. آماده‌سازی و فراخوانی Gemini API ---
    gemini_payload = {
        "contents": history_for_gemini + [{"role": "user", "parts": [{"text": user_text}]}]
    }
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    ai_response_text = "Sorry, I couldn't process that. Please try again." # پاسخ پیش‌فرض در صورت خطا
    try:
        response = requests.post(gemini_url, json=gemini_payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        ai_response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"Error calling Gemini API: {e}")

    # --- ۶. ارسال پاسخ به کاربر در تلگرام ---
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    telegram_payload = {'chat_id': chat_id, 'text': ai_response_text}
    try:
        requests.post(telegram_url, json=telegram_payload)
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

    # --- ۷. ذخیره پیام کاربر و پاسخ AI در دیتابیس (به صورت موازی) ---
    try:
        # ذخیره پیام کاربر
        databases.create_document(
            DATABASE_ID, HISTORY_COLLECTION_ID, ID.unique(),
            {'role': 'user', 'original_content': user_text, 'optimized_content': user_text, 'user': appwrite_user_id}
        )
        # ذخیره پاسخ مدل
        databases.create_document(
            DATABASE_ID, HISTORY_COLLECTION_ID, ID.unique(),
            {'role': 'model', 'original_content': ai_response_text, 'optimized_content': ai_response_text, 'user': appwrite_user_id}
        )
    except Exception as e:
        print(f"Error saving chat history: {e}")

    return res.json({'status': 'ok'})
