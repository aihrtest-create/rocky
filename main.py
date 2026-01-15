from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager

# === Config ===
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL", "https://rocky-production-4c4f.up.railway.app")

# === Database ===
def init_db():
    conn = sqlite3.connect('parties.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS parties
                 (id TEXT PRIMARY KEY, birthday_kid TEXT, created_by_tg_id INTEGER,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS guests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, party_id TEXT, name TEXT,
                  claimed_by_tg_id INTEGER, claimed_at TIMESTAMP,
                  FOREIGN KEY (party_id) REFERENCES parties(id))''')
    conn.commit()
    conn.close()

def create_party(party_id: str, birthday_kid: str, guests: list, tg_id: int):
    conn = sqlite3.connect('parties.db')
    c = conn.cursor()
    c.execute("INSERT INTO parties (id, birthday_kid, created_by_tg_id) VALUES (?, ?, ?)",
              (party_id, birthday_kid, tg_id))
    for guest in guests:
        c.execute("INSERT INTO guests (party_id, name) VALUES (?, ?)", (party_id, guest))
    conn.commit()
    conn.close()

def get_party(party_id: str):
    conn = sqlite3.connect('parties.db')
    c = conn.cursor()
    c.execute("SELECT birthday_kid FROM parties WHERE id = ?", (party_id,))
    party = c.fetchone()
    if not party:
        conn.close()
        return None
    c.execute("SELECT name, claimed_by_tg_id FROM guests WHERE party_id = ?", (party_id,))
    guests = [{"name": row[0], "claimed": row[1] is not None} for row in c.fetchall()]
    conn.close()
    return {"birthday_kid": party[0], "guests": guests}

def claim_guest(party_id: str, guest_name: str, tg_id: int):
    conn = sqlite3.connect('parties.db')
    c = conn.cursor()
    c.execute("""UPDATE guests SET claimed_by_tg_id = ?, claimed_at = CURRENT_TIMESTAMP 
                 WHERE party_id = ? AND name = ? AND claimed_by_tg_id IS NULL""",
              (tg_id, party_id, guest_name))
    conn.commit()
    conn.close()

# === Telegram Bot (simple HTTP) ===
async def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None):
    if not BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def handle_telegram_update(update: dict):
    message = update.get("message")
    if not message:
        return
    
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    
    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            # Гость переходит по ссылке
            party_id = parts[1]
            party = get_party(party_id)
            if party:
                webapp_url = f"{APP_URL}?party={party_id}"
                reply_markup = {
                    "inline_keyboard": [[{
                        "text": "🎉 Открыть приглашение",
                        "web_app": {"url": webapp_url}
                    }]]
                }
                await send_telegram_message(
                    chat_id,
                    f"🦊 Привет! <b>{party['birthday_kid']}</b> приглашает тебя на День Рождения!\n\n"
                    "Нажми кнопку, чтобы получить персональное приглашение от Лиса Рокки!",
                    reply_markup
                )
            else:
                await send_telegram_message(chat_id, "Упс, приглашение не найдено 😕")
        else:
            # Мама создаёт новую вечеринку
            user_id = message["from"]["id"]
            webapp_url = f"{APP_URL}?mode=create&tg_id={user_id}"
            reply_markup = {
                "inline_keyboard": [[{
                    "text": "🎈 Создать приглашения",
                    "web_app": {"url": webapp_url}
                }]]
            }
            await send_telegram_message(
                chat_id,
                "🦊 Привет! Я Лис Рокки из Hello Park!\n\n"
                "Я помогу создать персональные приглашения для гостей на День Рождения.\n\n"
                "Нажми кнопку, чтобы начать!",
                reply_markup
            )

# === FastAPI ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === API Models ===
class GenerateRequest(BaseModel):
    guest_name: str
    birthday_kid: str

class CreatePartyRequest(BaseModel):
    birthday_kid: str
    guests: list[str]
    tg_id: int

class ClaimGuestRequest(BaseModel):
    party_id: str
    guest_name: str
    tg_id: int

# === API Endpoints ===
@app.post("/api/generate-audio")
async def generate_audio(req: GenerateRequest):
    text = f"Привет, {req.guest_name}! Я Лис Рокки из Hello Park. {req.birthday_kid} приглашает тебя на свой день рождения, чтобы спасти космическую вечеринку! Я жду тебя, и у меня есть для тебя секретное задание!"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={"Content-Type": "application/json", "xi-api-key": ELEVEN_LABS_API_KEY},
            json={"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            timeout=30.0
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="ElevenLabs API error")
        return Response(content=response.content, media_type="audio/mpeg")

@app.post("/api/party")
async def create_party_endpoint(req: CreatePartyRequest):
    party_id = str(uuid.uuid4())[:8]
    create_party(party_id, req.birthday_kid, req.guests, req.tg_id)
    bot_username = "RockyHelloParkBot"
    return {"party_id": party_id, "share_link": f"https://t.me/{bot_username}?start={party_id}"}

@app.get("/api/party/{party_id}")
async def get_party_endpoint(party_id: str):
    party = get_party(party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    return party

@app.post("/api/claim")
async def claim_guest_endpoint(req: ClaimGuestRequest):
    claim_guest(req.party_id, req.guest_name, req.tg_id)
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    await handle_telegram_update(data)
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_CONTENT

HTML_CONTENT = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Приглашение от Рокки</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: system-ui, sans-serif; min-height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding: 20px; }
        .container { max-width: 400px; margin: 0 auto; }
        .card { background: rgba(255,255,255,0.1); border-radius: 20px; padding: 24px;
            backdrop-filter: blur(10px); margin-bottom: 16px; }
        .header { text-align: center; margin-bottom: 24px; }
        .emoji { font-size: 48px; margin-bottom: 8px; }
        .emoji-large { font-size: 64px; margin-bottom: 16px; }
        h1 { color: #fff; font-size: 22px; }
        h2 { color: #fff; font-size: 18px; margin-bottom: 16px; }
        p { color: rgba(255,255,255,0.7); font-size: 14px; margin-top: 8px; line-height: 1.5; }
        label { color: rgba(255,255,255,0.9); font-size: 14px; display: block; margin-bottom: 8px; }
        input { width: 100%; padding: 12px 16px; border-radius: 12px; border: none;
            font-size: 16px; background: rgba(255,255,255,0.9); }
        .input-row { display: flex; gap: 8px; }
        .input-row input { flex: 1; }
        .btn { padding: 16px; border-radius: 12px; border: none; font-size: 16px;
            cursor: pointer; width: 100%; font-weight: 600; }
        .btn-primary { background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%); color: #fff; }
        .btn-add { padding: 12px 20px; width: auto; background: #ff6b35; color: #fff; }
        .btn-secondary { background: rgba(255,107,53,0.1); border: 2px solid rgba(255,107,53,0.5); color: #fff; }
        .btn-play { padding: 16px 32px; border-radius: 50px; width: auto;
            margin: 20px auto 0; display: flex; align-items: center; gap: 8px; font-size: 18px; }
        .btn-back { background: transparent; color: rgba(255,255,255,0.5); font-size: 14px; padding: 12px; }
        .btn:disabled { background: rgba(255,255,255,0.2); cursor: not-allowed; }
        .guests { margin: 20px 0; }
        .guests-label { color: rgba(255,255,255,0.7); font-size: 13px; margin-bottom: 8px; }
        .guest-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .guest-tag { background: rgba(255,107,53,0.3); color: #fff; padding: 8px 12px;
            border-radius: 20px; font-size: 14px; display: flex; align-items: center; gap: 8px; }
        .guest-tag span { cursor: pointer; opacity: 0.7; }
        .guest-btn { padding: 16px 20px; margin-bottom: 12px; font-size: 18px; }
        .field { margin-bottom: 20px; }
        .task-placeholder { background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%);
            border-radius: 12px; padding: 40px 20px; text-align: center; margin-bottom: 16px; }
        .loading { opacity: 0.7; pointer-events: none; }
        .hidden { display: none; }
        .share-link { background: rgba(255,255,255,0.1); border-radius: 12px; padding: 16px;
            word-break: break-all; color: #fff; font-size: 14px; margin: 16px 0; }
        .btn-copy { background: #4CAF50; margin-top: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <div id="screen-setup">
            <div class="card">
                <div class="header">
                    <div class="emoji">🦊</div>
                    <h1>Приглашения от Рокки</h1>
                    <p>Создайте персональные приглашения для гостей</p>
                </div>
                <div class="field">
                    <label>Имя именинника</label>
                    <input type="text" id="birthday-kid" placeholder="Например: Миша">
                </div>
                <div class="field">
                    <label>Добавить гостей</label>
                    <div class="input-row">
                        <input type="text" id="new-guest" placeholder="Имя гостя">
                        <button class="btn btn-add" onclick="addGuest()">+</button>
                    </div>
                </div>
                <div class="guests hidden" id="guests-container">
                    <div class="guests-label">Гости (<span id="guests-count">0</span>):</div>
                    <div class="guest-tags" id="guests-list"></div>
                </div>
                <button class="btn btn-primary" id="create-btn" onclick="createParty()" disabled>
                    Создать приглашения 🎉
                </button>
            </div>
        </div>
        <div id="screen-share" class="hidden">
            <div class="card">
                <div class="header">
                    <div class="emoji">✅</div>
                    <h1>Приглашения готовы!</h1>
                    <p>Отправьте эту ссылку родителям гостей</p>
                </div>
                <div class="share-link" id="share-link"></div>
                <button class="btn btn-copy" onclick="copyLink()">📋 Скопировать ссылку</button>
                <button class="btn btn-secondary" style="margin-top:12px" onclick="testInvite()">
                    👀 Посмотреть как выглядит</button>
            </div>
        </div>
        <div id="screen-select" class="hidden">
            <div class="card">
                <div class="header">
                    <div class="emoji">🦊✉️</div>
                    <h1 id="select-title"></h1>
                    <p>Выбери своё имя, чтобы получить персональное приглашение от Лиса Рокки</p>
                </div>
                <div id="guest-buttons"></div>
            </div>
        </div>
        <div id="screen-invite" class="hidden">
            <div class="card" style="text-align:center;">
                <div class="emoji-large">🦊</div>
                <h1 id="invite-title"></h1>
                <p>У тебя голосовое сообщение от Лиса Рокки</p>
                <audio id="audio-player"></audio>
                <button class="btn btn-primary btn-play" onclick="playAudio()">▶️ Послушать</button>
            </div>
            <button class="btn btn-secondary" id="task-btn" onclick="showTask()">
                🎯 Посмотреть секретное задание</button>
            <div class="card hidden" id="task-card">
                <h2>🎯 Секретное задание от Рокки</h2>
                <div class="task-placeholder">
                    <div class="emoji">🚀🎮🦊</div>
                    <p>[Здесь будет видео-задание от Рокки]</p>
                </div>
                <p style="color:rgba(255,255,255,0.8);">Выполни задание и покажи Рокки в парке, чтобы получить специальный приз! 🎁</p>
            </div>
        </div>
    </div>
    <script>
        const tg = window.Telegram?.WebApp;
        if (tg) tg.expand();
        const urlParams = new URLSearchParams(window.location.search);
        const partyId = urlParams.get('party');
        const tgId = urlParams.get('tg_id') || tg?.initDataUnsafe?.user?.id || 0;
        let guests = [], birthdayKid = '', currentPartyId = partyId, shareLink = '';
        if (partyId) loadParty(partyId);
        async function loadParty(id) {
            try {
                const r = await fetch(`/api/party/${id}`);
                if (r.ok) {
                    const d = await r.json();
                    birthdayKid = d.birthday_kid;
                    guests = d.guests.map(g => g.name);
                    document.getElementById('select-title').textContent = `${birthdayKid} приглашает тебя на День Рождения!`;
                    renderGuestButtons();
                    showScreen('select');
                }
            } catch (e) { console.error(e); }
        }
        function renderGuestButtons() {
            document.getElementById('guest-buttons').innerHTML = guests.map(g =>
                `<button class="btn btn-secondary guest-btn" onclick="selectGuest('${g}')">${g}</button>`).join('');
        }
        document.getElementById('new-guest')?.addEventListener('keypress', e => { if (e.key === 'Enter') addGuest(); });
        function addGuest() {
            const i = document.getElementById('new-guest'), n = i.value.trim();
            if (n && !guests.includes(n)) { guests.push(n); i.value = ''; renderGuests(); }
        }
        function removeGuest(n) { guests = guests.filter(g => g !== n); renderGuests(); }
        function renderGuests() {
            const c = document.getElementById('guests-container'), l = document.getElementById('guests-list'),
                  cnt = document.getElementById('guests-count'), btn = document.getElementById('create-btn'),
                  kid = document.getElementById('birthday-kid').value.trim();
            if (guests.length > 0) {
                c.classList.remove('hidden'); cnt.textContent = guests.length;
                l.innerHTML = guests.map(g => `<div class="guest-tag">${g}<span onclick="removeGuest('${g}')">✕</span></div>`).join('');
            } else c.classList.add('hidden');
            btn.disabled = !(guests.length > 0 && kid);
        }
        document.getElementById('birthday-kid')?.addEventListener('input', renderGuests);
        async function createParty() {
            birthdayKid = document.getElementById('birthday-kid').value.trim();
            const btn = document.getElementById('create-btn');
            btn.textContent = '⏳ Создаём...'; btn.disabled = true;
            try {
                const r = await fetch('/api/party', { method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ birthday_kid: birthdayKid, guests, tg_id: tgId }) });
                const d = await r.json();
                currentPartyId = d.party_id; shareLink = d.share_link;
                document.getElementById('share-link').textContent = shareLink;
                showScreen('share');
            } catch (e) { alert('Ошибка: ' + e.message); btn.textContent = 'Создать приглашения 🎉'; btn.disabled = false; }
        }
        function copyLink() {
            navigator.clipboard.writeText(shareLink);
            const b = document.querySelector('.btn-copy'); b.textContent = '✅ Скопировано!';
            setTimeout(() => b.textContent = '📋 Скопировать ссылку', 2000);
        }
        function testInvite() {
            document.getElementById('select-title').textContent = `${birthdayKid} приглашает тебя на День Рождения!`;
            renderGuestButtons(); showScreen('select');
        }
        async function selectGuest(name) {
            const btns = document.querySelectorAll('.guest-btn');
            btns.forEach(b => { if (b.textContent === name) { b.textContent = '⏳ Рокки готовит приглашение...'; b.classList.add('loading'); }});
            try {
                if (currentPartyId && tgId) await fetch('/api/claim', { method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ party_id: currentPartyId, guest_name: name, tg_id: tgId }) });
                const r = await fetch('/api/generate-audio', { method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ guest_name: name, birthday_kid: birthdayKid }) });
                if (r.ok) {
                    const blob = await r.blob(), url = URL.createObjectURL(blob);
                    document.getElementById('audio-player').src = url;
                    document.getElementById('invite-title').textContent = `Привет, ${name}!`;
                    showScreen('invite');
                } else alert('Ошибка генерации аудио');
            } catch (e) { alert('Ошибка: ' + e.message); }
            btns.forEach(b => { if (b.textContent.includes('⏳')) { b.textContent = name; b.classList.remove('loading'); }});
        }
        function playAudio() { document.getElementById('audio-player').play(); }
        function showTask() { document.getElementById('task-btn').classList.add('hidden'); document.getElementById('task-card').classList.remove('hidden'); }
        function showScreen(n) { ['setup','share','select','invite'].forEach(s => document.getElementById(`screen-${s}`).classList.add('hidden'));
            document.getElementById(`screen-${n}`).classList.remove('hidden'); }
    </script>
</body>
</html>
'''
