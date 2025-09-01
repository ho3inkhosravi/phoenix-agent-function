# کد نهایی برای عیب‌یابی متغیرهای محیطی
import os

def main(context):
    context.log("--- Starting Environment Variable Health Check ---")
    
    # خواندن تمام متغیرها
    project_id = os.environ.get("APPWRITE_PROJECT_ID")
    api_key = os.environ.get("APPWRITE_API_KEY")
    endpoint = os.environ.get("APPWRITE_ENDPOINT")
    
    # چاپ مقادیر برای بررسی
    # استفاده از f-string با '' برای دیدن فاصله‌های احتمالی
    context.log(f"Project ID: '{project_id}'")
    context.log(f"API Key: '{api_key}'")
    context.log(f"Endpoint: '{endpoint}'")
    
    # بررسی طول مقادیر برای پیدا کردن کاراکترهای پنهان
    if project_id:
        context.log(f"Length of Project ID: {len(project_id)}")
    if api_key:
        context.log(f"Length of API Key: {len(api_key)}")
    if endpoint:
        context.log(f"Length of Endpoint: {len(endpoint)}")

    context.log("--- Health Check Finished ---")
    
    # همیشه یک پاسخ موفقیت‌آمیز برمی‌گردانیم
    return context.res.json({'status': 'ok', 'message': 'Health check complete. Please review the logs.'})
