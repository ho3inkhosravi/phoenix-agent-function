import os
import json
import requests
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID
from appwrite.query import Query

def main(req, res):
    # --- بلوک عیب‌یابی ضدضربه ---
    try:
        print("Function execution started.")
        print(f"Request body type: {type(req.body)}")
        print(f"Raw request body received: {req.body}")

        # --- ۱. مقداردهی اولیه ---
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

        # --- ۲. پردازش درخواست ورودی ---
        if not req.body:
            print("Exiting: Request body is empty.")
            return res.json({'status': 'ok', 'message': 'Empty body received.'})

        body = json.loads(req.body)
        message = body.get("message", {})
        user_id = message.get("from", {}).get("id")
        chat_id = message.get("chat", {}).get("id")
        user_text = message.get("text")
        first_name = message.get("from", {}).get("first_name", "")
        username = message.get("from", {}).get("username", "")

        if not all([user_id, chat_id, user_text]):
            print("Exiting: Not a standard user text message.")
            return res.json({'status': 'ok', 'message': 'Not a user message.'})
        
        print(f"Processing message from user ID: {user_id}")

        # --- ۳. پیدا کردن یا ایجاد کاربر ---
        appwrite_user_id = None
        query = Query.equal("userId", user_id)
        response = databases.list_documents(DATABASE_ID, USERS_COLLECTION_ID, queries=[query])
        
        if response['total'] > 0:
            appwrite_user_id = response['documents'][0]['$id']
            print(f"Found existing user with Appwrite ID: {appwrite_user_id}")
        else:
            new_user_doc = databases.create_document(
                DATABASE_ID, USERS_COLLECTION_ID, ID.unique(),
                {'userId': user_id, 'firstName': first_name, 'username': username}
            )
            appwrite_user_id = new_user_doc['$id']
            print(f"Created new user with Appwrite ID: {appwrite_user_id}")

        # --- ۴. بازیابی تاریخچه ---
        history_for_gemini = []
        query_user = Query.equal("user", [appwrite_user_id])
        query_order = Query.order_desc("$createdAt")
        query_limit = Query.limit(10)
        response = databases.list_documents(DATABASE_ID, HISTORY_COLLECTION_ID, queries=[query_user, query_order, query_limit])
        
        documents = reversed(response['documents'])
        for doc in documents:
            history_for_gemini.append({"role": doc['role'], "parts": [{"text": doc['optimized_content']}]})
        print(f"Retrieved {len(history_for_gemini)} messages from history.")

        # --- ۵. فراخوانی Gemini ---
        gemini_payload = {"contents": history_for_gemini + [{"role": "user", "parts": [{"text": user_text}]}]}
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        
        response = requests.post(gemini_url, json=gemini_payload, headers={'Content-Type': 'application/json'})
        response.raise_for_status()
        ai_response_text = response.json()['candidates'][0]['content']['parts'][0]['text']
        print("Successfully received response from Gemini.")

        # --- ۶. ارسال پاسخ به تلگرام ---
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        telegram_payload = {'chat_id': chat_id, 'text': ai_response_text}
        requests.post(telegram_url, json=telegram_payload)
        print("Successfully sent response to Telegram.")

        # --- ۷. ذخیره مکالمات ---
        databases.create_document(
            DATABASE_ID, HISTORY_COLLECTION_ID, ID.unique(),
            {'role': 'user', 'original_content': user_text, 'optimized_content': user_text, 'user': appwrite_user_id}
        )
        databases.create_document(
            DATABASE_ID, HISTORY_COLLECTION_ID, ID.unique(),
            {'role': 'model', 'original_content': ai_response_text, 'optimized_content': ai_response_text, 'user': appwrite_user_id}
        )
        print("Successfully saved conversation to database.")
        
        return res.json({'status': 'ok'})

    except Exception as e:
        # --- بلوک مدیریت خطای جامع ---
        error_message = f"An unexpected error occurred: {str(e)}"
        print(error_message)
        return res.json({'status': 'error', 'message': error_message}, 500)
