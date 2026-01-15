from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY", "sk_e86d5c0fb7b75e625006b86dc78cf05cca0e52b1a905bb0d")
VOICE_ID = os.getenv("VOICE_ID", "9v8bxagMX43JiaF92sqe")

class GenerateRequest(BaseModel):
    guest_name: str
    birthday_kid: str

@app.post("/api/generate-audio")
async def generate_audio(req: GenerateRequest):
    text = f"Привет, {req.guest_name}! Я Лис Рокки из Hello Park. {req.birthday_kid} приглашает тебя на свой день рождения, чтобы спасти космическую вечеринку! Я жду тебя, и у меня есть для тебя секретное задание!"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
            headers={
                "Content-Type": "application/json",
                "xi-api-key": ELEVEN_LABS_API_KEY
            },
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            },
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="ElevenLabs API error")
        
        return Response(content=response.content, media_type="audio/mpeg")

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_CONTENT

HTML_CONTENT = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Приглашение от Рокки</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px;
        }
        .container {
            max-width: 400px;
            margin: 0 auto;
        }
        .card {
            background: rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 24px;
            backdrop-filter: blur(10px);
            margin-bottom: 16px;
        }
        .header { text-align: center; margin-bottom: 24px; }
        .emoji { font-size: 48px; margin-bottom: 8px; }
        .emoji-large { font-size: 64px; margin-bottom: 16px; }
        h1 { color: #fff; font-size: 22px; }
        h2 { color: #fff; font-size: 18px; margin-bottom: 16px; }
        p { color: rgba(255,255,255,0.7); font-size: 14px; margin-top: 8px; line-height: 1.5; }
        label { color: rgba(255,255,255,0.9); font-size: 14px; display: block; margin-bottom: 8px; }
        input {
            width: 100%;
            padding: 12px 16px;
            border-radius: 12px;
            border: none;
            font-size: 16px;
            background: rgba(255,255,255,0.9);
        }
        .input-row { display: flex; gap: 8px; }
        .input-row input { flex: 1; }
        .btn {
            padding: 16px;
            border-radius: 12px;
            border: none;
            font-size: 16px;
            cursor: pointer;
            width: 100%;
            font-weight: 600;
        }
        .btn-primary {
            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
            color: #fff;
        }
        .btn-add {
            padding: 12px 20px;
            width: auto;
            background: #ff6b35;
            color: #fff;
        }
        .btn-secondary {
            background: rgba(255,107,53,0.1);
            border: 2px solid rgba(255,107,53,0.5);
            color: #fff;
        }
        .btn-play {
            padding: 16px 32px;
            border-radius: 50px;
            width: auto;
            margin: 20px auto 0;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 18px;
        }
        .btn-back {
            background: transparent;
            color: rgba(255,255,255,0.5);
            font-size: 14px;
            padding: 12px;
        }
        .btn:disabled {
            background: rgba(255,255,255,0.2);
            cursor: not-allowed;
        }
        .guests { margin: 20px 0; }
        .guests-label { color: rgba(255,255,255,0.7); font-size: 13px; margin-bottom: 8px; }
        .guest-tags { display: flex; flex-wrap: wrap; gap: 8px; }
        .guest-tag {
            background: rgba(255,107,53,0.3);
            color: #fff;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .guest-tag span { cursor: pointer; opacity: 0.7; }
        .guest-btn {
            padding: 16px 20px;
            margin-bottom: 12px;
            font-size: 18px;
        }
        .field { margin-bottom: 20px; }
        .task-placeholder {
            background: linear-gradient(135deg, #2a2a4a 0%, #1a1a3a 100%);
            border-radius: 12px;
            padding: 40px 20px;
            text-align: center;
            margin-bottom: 16px;
        }
        .loading { opacity: 0.7; pointer-events: none; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <!-- Экран 1: Настройка -->
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
                
                <button class="btn btn-primary" id="create-btn" onclick="createInvites()" disabled>
                    Создать приглашения 🎉
                </button>
            </div>
        </div>
        
        <!-- Экран 2: Выбор имени -->
        <div id="screen-select" class="hidden">
            <div class="card">
                <div class="header">
                    <div class="emoji">🦊✉️</div>
                    <h1 id="select-title"></h1>
                    <p>Выбери своё имя, чтобы получить персональное приглашение от Лиса Рокки</p>
                </div>
                <div id="guest-buttons"></div>
                <button class="btn btn-back" onclick="showScreen('setup')">← Назад к настройке</button>
            </div>
        </div>
        
        <!-- Экран 3: Приглашение -->
        <div id="screen-invite" class="hidden">
            <div class="card" style="text-align: center;">
                <div class="emoji-large">🦊</div>
                <h1 id="invite-title"></h1>
                <p>У тебя голосовое сообщение от Лиса Рокки</p>
                <audio id="audio-player"></audio>
                <button class="btn btn-primary btn-play" onclick="playAudio()">▶️ Послушать</button>
            </div>
            
            <button class="btn btn-secondary" id="task-btn" onclick="showTask()">
                🎯 Посмотреть секретное задание
            </button>
            
            <div class="card hidden" id="task-card">
                <h2>🎯 Секретное задание от Рокки</h2>
                <div class="task-placeholder">
                    <div class="emoji">🚀🎮🦊</div>
                    <p>[Здесь будет видео-задание от Рокки]</p>
                </div>
                <p style="color: rgba(255,255,255,0.8);">
                    Выполни задание и покажи Рокки в парке, чтобы получить специальный приз! 🎁
                </p>
            </div>
            
            <button class="btn btn-back" onclick="backToSelect()">← Выбрать другое имя</button>
        </div>
    </div>

    <script>
        let guests = [];
        let birthdayKid = '';
        let selectedGuest = '';
        
        document.getElementById('new-guest').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addGuest();
        });
        
        function addGuest() {
            const input = document.getElementById('new-guest');
            const name = input.value.trim();
            if (name && !guests.includes(name)) {
                guests.push(name);
                input.value = '';
                renderGuests();
            }
        }
        
        function removeGuest(name) {
            guests = guests.filter(g => g !== name);
            renderGuests();
        }
        
        function renderGuests() {
            const container = document.getElementById('guests-container');
            const list = document.getElementById('guests-list');
            const count = document.getElementById('guests-count');
            const btn = document.getElementById('create-btn');
            const kid = document.getElementById('birthday-kid').value.trim();
            
            if (guests.length > 0) {
                container.classList.remove('hidden');
                count.textContent = guests.length;
                list.innerHTML = guests.map(g => 
                    `<div class="guest-tag">${g}<span onclick="removeGuest('${g}')">✕</span></div>`
                ).join('');
            } else {
                container.classList.add('hidden');
            }
            
            btn.disabled = !(guests.length > 0 && kid);
        }
        
        document.getElementById('birthday-kid').addEventListener('input', renderGuests);
        
        function createInvites() {
            birthdayKid = document.getElementById('birthday-kid').value.trim();
            document.getElementById('select-title').textContent = 
                `${birthdayKid} приглашает тебя на День Рождения!`;
            
            const btns = document.getElementById('guest-buttons');
            btns.innerHTML = guests.map(g => 
                `<button class="btn btn-secondary guest-btn" onclick="selectGuest('${g}')">${g}</button>`
            ).join('');
            
            showScreen('select');
        }
        
        async function selectGuest(name) {
            selectedGuest = name;
            const btns = document.querySelectorAll('.guest-btn');
            btns.forEach(b => {
                if (b.textContent === name) {
                    b.textContent = '⏳ Рокки готовит приглашение...';
                    b.classList.add('loading');
                }
            });
            
            try {
                const response = await fetch('/api/generate-audio', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ guest_name: name, birthday_kid: birthdayKid })
                });
                
                if (response.ok) {
                    const blob = await response.blob();
                    const url = URL.createObjectURL(blob);
                    document.getElementById('audio-player').src = url;
                    document.getElementById('invite-title').textContent = `Привет, ${name}!`;
                    showScreen('invite');
                } else {
                    alert('Ошибка генерации аудио');
                }
            } catch (error) {
                alert('Ошибка: ' + error.message);
            }
            
            btns.forEach(b => {
                if (b.textContent.includes('⏳')) {
                    b.textContent = name;
                    b.classList.remove('loading');
                }
            });
        }
        
        function playAudio() {
            document.getElementById('audio-player').play();
        }
        
        function showTask() {
            document.getElementById('task-btn').classList.add('hidden');
            document.getElementById('task-card').classList.remove('hidden');
        }
        
        function backToSelect() {
            document.getElementById('task-btn').classList.remove('hidden');
            document.getElementById('task-card').classList.add('hidden');
            showScreen('select');
        }
        
        function showScreen(name) {
            ['setup', 'select', 'invite'].forEach(s => {
                document.getElementById(`screen-${s}`).classList.add('hidden');
            });
            document.getElementById(`screen-${name}`).classList.remove('hidden');
        }
    </script>
</body>
</html>
'''
