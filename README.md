# 🤖 Aura Pro – AI-Powered Virtual Assistant

A full-stack, intelligent AI assistant built with **FastAPI** (Python) on the backend and **React + Vite** on the frontend. Aura can manage tasks, set reminders, play videos, and hold rich conversations — all with a premium dark UI.

---

## ✨ Features

- 🔐 **Authentication** — Secure JWT-based login & signup
- 💬 **Multi-Session Chat** — Maintain separate conversation histories
- 🎙️ **Voice Input** — Speech-to-text via Web Speech API
- 🔊 **Voice Output** — Text-to-speech with **Stop Aura** button to cancel instantly
- ✅ **Task Management** — AI can add tasks; view, complete & delete from sidebar
- ⏰ **Reminder Management** — AI sets reminders; view & delete from sidebar
- 📺 **YouTube Video Playback** — Ask Aura to play a video and it embeds inline
- 📋 **Copy with Feedback** — Copy any message with a "Copied!" indicator (ChatGPT style)
- ♻️ **Regenerate Response** — Re-run the last query
- 🌙 **Premium Dark UI** — Glassmorphism, smooth animations, framer-motion

---

## 🗂️ Project Structure

```
AI_powered_Virtual_Assistant/
├── backend/               # FastAPI backend
│   ├── main.py            # API routes
│   ├── agent.py           # AI engine (Gemini + OpenAI fallback)
│   ├── auth.py            # JWT auth utilities
│   ├── database.py        # MongoDB connection
│   ├── models.py          # Pydantic models
│   ├── requirements.txt
│   └── .env               # (NOT committed — see below)
│
└── frontend/              # React + Vite frontend
    ├── src/
    │   ├── pages/
    │   │   ├── ChatPage.jsx
    │   │   ├── LoginPage.jsx
    │   │   └── SignupPage.jsx
    │   ├── context/
    │   │   └── AuthContext.jsx
    │   └── components/
    │       └── MessageItem.jsx
    ├── index.html
    └── package.json
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MongoDB Atlas account (or local MongoDB)
- Google Gemini API key (free)

---

### 1. Clone the Repository

```bash
git clone https://github.com/Esha30/AI_Virtual_Assistant.git
cd AI_Virtual_Assistant
```

---

### 2. Backend Setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

Create a `.env` file in `/backend`:

```env
MONGODB_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/virtual_assistant
SECRET_KEY=your-super-secret-jwt-key
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key   # optional fallback
```

Start the backend:

```bash
uvicorn main:app --reload
```

Backend will run at `http://localhost:8000`

---

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at `http://localhost:5173`

---

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `SECRET_KEY` | A random secret for JWT signing |
| `GEMINI_API_KEY` | Google AI Studio API key |
| `OPENAI_API_KEY` | OpenAI API key (optional fallback) |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Vite 6, TailwindCSS 4, Framer Motion |
| Backend | FastAPI, Uvicorn, Motor (async MongoDB) |
| AI Engine | Google Gemini 2.5 Flash → OpenAI GPT-4o-mini fallback → Pollinations Free Provider |
| Database | MongoDB Atlas |
| Auth | JWT (python-jose + passlib) |
| Icons | Lucide React |

---

## 📄 License

MIT License — feel free to use, modify and distribute.

---

> Built with ❤️ by Esha
