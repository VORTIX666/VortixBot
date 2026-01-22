from flask import Flask, request
import requests
import random
import subprocess
import threading
import time
from bs4 import BeautifulSoup
import yt_dlp

app = Flask(__name__)

# ================== المفاتيح ==================
PAGE_ACCESS_TOKEN = "EAANedrFZCBBsBQh3qIsUXcBsifSTCGojo4mlRXg7DGJ2p8S6iPveMzXLoZB74qnTL0eG9F2EUQNSE2aRQz7DtB4b15HBEEl5eJxo4tCbVZAhSJHivawFahPOFZCbt9aeaTR5LnCtIYEpm3yG4Y1NdinRY0T02BeZAkehzDiJFe2yYyIC0OdIj3pkkSuQihV9O3x4B"
VERIFY_TOKEN = "verify123"
GROK_API_KEY = "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"

# ================== الحالات ==================
user_mode = {}  # menu | ai | quiz | select_difficulty | imgd | videod | fb
conversation_history = {}
quiz_state = {}  # {user_id: {"questions": [...], "current_index": int, "score": int, "difficulty": str}}
current_process = None  # للبث المباشر

# ================== إرسال رسالة ==================
def send_message(user_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    data = {"recipient": {"id": user_id}, "message": {"text": text}}
    try:
        requests.post(url, params=params, json=data, timeout=10)
    except:
        pass

# ================== AI ==================
def ai_reply(user_id, text, prompt_type="chat"):
    if user_id not in conversation_history:
        system_content = "أنت VortixBot، مساعد ذكي يجيب بالعربية وباختصار."
        if prompt_type == "programming":
            system_content = "أنت VortixBot، مساعد برمجي يكتب أكواد نظيفة بالعربية والإنجليزية."
        conversation_history[user_id] = [{"role": "system", "content": system_content}]

    conversation_history[user_id].append({"role": "user", "content": text})
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": conversation_history[user_id][-10:],
        "max_tokens": 700,
        "temperature": 0.7
    }
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        reply = response.json()["choices"][0]["message"]["content"]
        conversation_history[user_id].append({"role": "assistant", "content": reply})
        return reply
    except:
        return "⚠️ حدث خطأ في الذكاء الاصطناعي."

# ================== Trivia ==================
questions_bank = {
    "easy": [
        {"question": "عاصمة المغرب؟", "answer": "الرباط", "options": ["مراكش", "الرباط", "الدار البيضاء"]},
        {"question": "أكبر كوكب في المجموعة الشمسية؟", "answer": "المشتري", "options": ["المشتري", "الأرض", "الزهرة"]},
        {"question": "اللون الذي يرمز للسلام؟", "answer": "الأبيض", "options": ["الأبيض", "الأحمر", "الأزرق"]},
        {"question": "ما هو الحيوان الذي يسمى ملك الغابة؟", "answer": "الأسد", "options": ["الأسد", "النمر", "الفهد"]},
        {"question": "كم عدد أيام الأسبوع؟", "answer": "7", "options": ["5", "6", "7"]}
    ],
    "medium": [
        {"question": "من اكتشف أمريكا؟", "answer": "كريستوفر كولومبوس", "options": ["كريستوفر كولومبوس", "فاسكو دا غاما", "ماركو بولو"]},
        {"question": "ما هي أصغر قارة؟", "answer": "أستراليا", "options": ["أستراليا", "أوروبا", "أفريقيا"]},
        {"question": "من كتب رواية البؤساء؟", "answer": "فيكتور هوغو", "options": ["فيكتور هوغو", "تولستوي", "تشارلز ديكنز"]},
        {"question": "أي غاز يشكل 78٪ من الهواء؟", "answer": "النيتروجين", "options": ["النيتروجين", "الأكسجين", "الهيدروجين"]},
        {"question": "كم عدد الحروف في الأبجدية العربية؟", "answer": "28", "options": ["28", "26", "30"]}
    ],
    "hard": [
        {"question": "ما هو أطول نهر في العالم؟", "answer": "النيل", "options": ["النيل", "الأمازون", "اليانغتسي"]},
        {"question": "ما هو العنصر الأكثر وفرة في الكون؟", "answer": "الهيدروجين", "options": ["الهيدروجين", "الأكسجين", "الهيليوم"]},
        {"question": "من هو مؤسس بازل؟", "answer": "يوسف جوتش", "options": ["يوسف جوتش", "ماركوس أوريليوس", "ليوناردو دا فينشي"]},
        {"question": "كم عدد كواكب المجموعة الشمسية؟", "answer": "8", "options": ["7", "8", "9"]},
        {"question": "ما اسم أسرع حيوان بري؟", "answer": "الفهد", "options": ["الفهد", "الأسد", "النمر"]}
    ]
}

def start_quiz(user_id, difficulty):
    selected_questions = random.sample(questions_bank[difficulty], 5)
    quiz_state[user_id] = {"questions": selected_questions, "current_index": 0, "score": 0, "difficulty": difficulty}
    send_next_question(user_id)

def send_next_question(user_id):
    state = quiz_state.get(user_id)
    if not state: return
    if state["current_index"] >= len(state["questions"]):
        send_message(user_id, f"🏁 انتهت الجولة! نتيجتك: {state['score']}/{len(state['questions'])}")
        quiz_state.pop(user_id)
        send_message(user_id, "اكتب `.quiz` للعب مرة أخرى أو `.menu` للخيارات.")
        return
    qdata = state["questions"][state["current_index"]]
    options = qdata["options"].copy()
    random.shuffle(options)
    state["options"] = options
    options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
    send_message(user_id, f"🎲 سؤال ({state['difficulty']}): {qdata['question']}\n{options_text}")

def check_quiz_answer(user_id, text):
    state = quiz_state.get(user_id)
    if not state:
        send_message(user_id, "⚠️ لم يبدأ أي سؤال. اكتب `.menu` للخيارات.")
        return
    try:
        choice = int(text.strip()) - 1
        options = state.get("options", [])
        if 0 <= choice < len(options):
            selected = options[choice]
            correct_answer = state["questions"][state["current_index"]]["answer"]
            if selected == correct_answer:
                send_message(user_id, "✅ إجابة صحيحة!")
                state["score"] += 1
            else:
                send_message(user_id, f"❌ إجابة خاطئة. الإجابة الصحيحة: {correct_answer}")
            state["current_index"] += 1
            send_next_question(user_id)
        else:
            send_message(user_id, "⚠️ اختر رقم من الخيارات فقط.")
    except:
        send_message(user_id, "⚠️ اكتب رقم الإجابة فقط.")

# ================== .IMGD ==================
def extract_image_url(fb_post_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(fb_post_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", property="og:image")
        if meta and meta.get("content"):
            return meta["content"]
        images = soup.find_all("img")
        for img in images:
            src = img.get("src", "")
            if "scontent" in src and "fbcdn" in src:
                return src
    except:
        pass
    return None

# ================== .VIDEOD ==================
def get_stream_link(video_url):
    ydl_opts = {"quiet": True, "skip_download": True, "format": "best[ext=mp4]/best"}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get("url")
    except:
        return None

# ================== .FB ==================
def start_fb_stream(m3u8_url, stream_key):
    global current_process
    try:
        if current_process and current_process.poll() is None:
            current_process.terminate()
        rtmp_url = f"rtmps://live-api-s.facebook.com:443/rtmp/{stream_key}"
        cmd = ["ffmpeg", "-re", "-i", m3u8_url, "-c", "copy", "-f", "flv", rtmp_url]
        current_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except:
        return False

def stop_fb_stream():
    global current_process
    if current_process and current_process.poll() is None:
        current_process.terminate()
        return True
    return False

# ================== القائمة ==================
def send_menu(user_id):
    text = (
        "🤖 VortixBot\n\n"
        ".AI → الذكاء الاصطناعي\n"
        ".AIP → الذكاء الاصطناعي برمجي\n"
        ".QUIZ → لعبة أسئلة (5 أسئلة)\n"
        ".IMGD → رابط مباشر لصورة فيسبوك\n"
        ".VIDEOD → رابط مباشر لفيديو\n"
        ".FB → بث مباشر على فيسبوك\n"
        ".EXIT → الخروج من أي وضع"
    )
    send_message(user_id, text)

# ================== المسار الجذر (التصحيح الوحيد المضاف) ==================
@app.route('/', methods=['GET'])
def home():
    return "VortixBot شغال! 🚀\nاكتب .menu في الماسنجر", 200

# ================== Webhook ==================
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Error", 403

    data = request.get_json()
    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            if "message" not in event or "text" not in event["message"]:
                continue
            user_id = event["sender"]["id"]
            text = event["message"]["text"].strip()

            if user_id not in user_mode:
                user_mode[user_id] = "menu"

            # القائمة
            if text.lower() == ".menu":
                user_mode[user_id] = "menu"
                send_menu(user_id)
            # AI
            elif text.lower() == ".ai":
                user_mode[user_id] = "ai"
                send_message(user_id, "🤖 دخلت وضع الذكاء الاصطناعي")
            elif text.lower() == ".aip":
                user_mode[user_id] = "ai"
                send_message(user_id, "🤖 دخلت وضع الذكاء الاصطناعي برمجي")
            # Quiz
            elif text.lower() == ".quiz":
                user_mode[user_id] = "select_difficulty"
                send_message(user_id, "🎯 اختر مستوى الصعوبة:\n1️⃣ سهل\n2️⃣ متوسط\n3️⃣ صعب")
            # الخروج
            elif text.lower() == ".exit":
                user_mode[user_id] = "menu"
                send_message(user_id, "✅ خرجت من الوضع الحالي")
            # اختيار مستوى Quiz
            elif user_mode[user_id] == "select_difficulty" and text in ["1","2","3"]:
                difficulty = {"1":"easy","2":"medium","3":"hard"}[text]
                user_mode[user_id] = "quiz"
                start_quiz(user_id, difficulty)
            # IMG
            elif text.lower().startswith(".imgd"):
                fb_url = text[5:].strip()
                send_message(user_id, "⏳ جاري استخراج رابط الصورة...")
                img_url = extract_image_url(fb_url)
                if img_url:
                    send_message(user_id, f"✅ الرابط المباشر للصورة:\n{img_url}")
                else:
                    send_message(user_id, "❌ لم أتمكن من استخراج الصورة")
            # VIDEOD
            elif text.lower().startswith(".videod"):
                video_url = text[7:].strip()
                send_message(user_id, "⏳ جاري استخراج رابط الفيديو...")
                link = get_stream_link(video_url)
                if link:
                    send_message(user_id, f"✅ رابط الفيديو المباشر:\n{link}")
                else:
                    send_message(user_id, "❌ لم أتمكن من استخراج رابط الفيديو")
            # FB بث
            elif text.lower().startswith(".fb"):
                if text.lower().strip() == ".fb stop":
                    stopped = stop_fb_stream()
                    if stopped:
                        send_message(user_id, "🛑 تم إيقاف البث")
                    else:
                        send_message(user_id, "❌ لا يوجد بث جاري")
                else:
                    try:
                        m3u8_url, stream_key = text[3:].split("|")
                        send_message(user_id, "⏳ جاري بدء البث...")
                        time.sleep(5)
                        success = start_fb_stream(m3u8_url.strip(), stream_key.strip())
                        if success:
                            send_message(user_id, "✅ البث بدأ بنجاح!\nلايقاف البث اضغط .FB STOP")
                        else:
                            send_message(user_id, "❌ حدث خطأ أثناء بدء البث")
                    except:
                        send_message(user_id, "⚠️ الصيغة خاطئة! استخدم: `.FB m3u8_url|stream_key`")

            # الرد حسب الوضع
            else:
                if user_mode[user_id] == "ai":
                    prompt_type = "programming" if text.lower().startswith(".aip") else "chat"
                    reply = ai_reply(user_id, text, prompt_type)
                    send_message(user_id, reply)
                elif user_mode[user_id] == "quiz":
                    check_quiz_answer(user_id, text)
                else:
                    send_message(user_id, "📌 اكتب `.menu` لعرض الخيارات")

    return "EVENT_RECEIVED", 200

# ================== تشغيل ==================
if __name__ == "__main__":
    print("🚀 VortixBot شغّال بالكامل")
    app.run(host="0.0.0.0", port=3000)