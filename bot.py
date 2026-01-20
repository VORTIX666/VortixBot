from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# ====================== إعداداتك ======================
PAGE_ACCESS_TOKEN = "EAANedrFZCBBsBQlCCb9IENCGd6JbnB6ZBwpAtljYJBVyLlwMZA0aUD4J3ZCEiImQHiC1CqEHhroZAoYpOa3GfKZBj1zZCBJGfDt3ynk5AvrZB7fsoPQduxUQHaVUbe640b0KXTKwrJrEkcuuSMTXgZBWLAMa1HvOCWAKTa1ZAMzoVlZBGAyslvmlUJN5ug0aaKEErVFFhISHQZDZD"  # غيّره لو انتهى صلاحيته
VERIFY_TOKEN = "verify123"  # نفس اللي حطيته في Facebook webhook settings

# Groq API Key (مجاني - سجل في https://console.groq.com/keys)
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "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"  # ضع مفتاحك هنا أو في .env

# للحفظ البسيط للسياق (conversation history) لكل مستخدم - يمكن تحسينه بـ database لاحقًا
conversation_history = {}  # {sender_id: [{"role": "user/system", "content": "..."}]}

# ====================== إرسال رسالة للمستخدم ======================
def send_message(recipient_id, text):
    url = "https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {
        "recipient": {"id": recipient_id},
        "message": {"text": text}
    }
    try:
        response = requests.post(url, params=params, json=data)
        response.raise_for_status()
        print(f"رسالة مرسلة لـ {recipient_id}")
    except Exception as e:
        print(f"خطأ في إرسال الرسالة: {e}")

# ====================== الحصول على رد من Groq ======================
def get_ai_reply(sender_id, user_text):
    # إضافة رسالة المستخدم للسياق
    if sender_id not in conversation_history:
        conversation_history[sender_id] = [
            {"role": "system", "content": "أنت مساعد ذكي وودود جدًا، تجاوب دائمًا بالعربية (فصحى أو عامية مغربية حسب اللهجة)، كن مفيدًا، مرحًا، ومباشرًا. إذا كان السؤال بالعامية جاوب بنفس الأسلوب."}
        ]

    conversation_history[sender_id].append({"role": "user", "content": user_text})

    # حد أقصى للسياق عشان ما يتجاوز الـ token limit
    messages = conversation_history[sender_id][-15:]  # آخر 15 رسالة فقط (تقريبًا)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",  # أو "mixtral-8x22b-2410" أو "gemma2-27b-it" – جرب اللي يعجبك
        "messages": messages,
        "temperature": 0.7,          # 0.7 = توازن بين الإبداع والدقة
        "max_tokens": 1024,
        "top_p": 0.9
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"].strip()

        # أضف رد الـ AI للسياق
        conversation_history[sender_id].append({"role": "assistant", "content": reply})

        return reply

    except requests.exceptions.RequestException as e:
        print(f"خطأ في طلب Groq: {e}")
        if 'response' in locals():
            print("تفاصيل الخطأ:", response.text)
        return "⚠️ آسف، في مشكلة في الاتصال بالذكاء الاصطناعي... جرب تاني بعد شوية 😅"

# ====================== Webhook لفيسبوك ======================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        # التحقق من Facebook
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook تم التحقق منه بنجاح!")
            return challenge, 200
        return "فشل التحقق", 403

    if request.method == "POST":
        try:
            data = request.get_json()
            if not data:
                return "No data", 400

            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    if "sender" not in event or "message" not in event:
                        continue

                    sender_id = event["sender"]["id"]

                    # تجاهل الرسائل بدون نص (مثل صور أو reactions)
                    if "message" in event and "text" in event["message"]:
                        user_text = event["message"]["text"].strip()
                        print(f"[{datetime.now()}] رسالة من {sender_id}: {user_text}")

                        # احصل على الرد
                        reply_text = get_ai_reply(sender_id, user_text)

                        # أرسل الرد
                        send_message(sender_id, reply_text)

            return "EVENT_RECEIVED", 200

        except Exception as e:
            print(f"خطأ عام في webhook: {e}")
            return "Server error", 500

# تشغيل السيرفر
if __name__ == "__main__":
    print("🚀 البوت شغال...")
    print("استخدم ngrok http 5000 لعمل URL عام لفيسبوك webhook")
    app.run(host="0.0.0.0", port=5000, debug=True)
