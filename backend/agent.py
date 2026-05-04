import os
import json
import asyncio
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime
from bson import ObjectId

load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Clients
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

openai_client = None
if OPENAI_API_KEY:
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def process_user_message(user_message: str, history_docs: list, db=None, user_id=None, user_local_time: str = None) -> str:
    current_time_str = user_local_time or datetime.utcnow().isoformat()
    system_instruction = f"""System Time: {current_time_str}. 
You are Aura, an elite AI life management assistant. 
CRITICAL: You MUST use the provided tools for adding tasks, setting reminders, or listing status. 
Never tell the user you have done something (like adding a task or setting a reminder) unless you have successfully called the corresponding tool.
Professional, concise, and proactive style."""

    # ── TOOLS CONFIGURATION ──────────────────────────────────────────────────
    async def add_task_tool(task: str) -> str:
        if db is not None and user_id:
            try:
                await db.tasks.insert_one({
                    "task": task, "user_id": str(user_id), "completed": False, "created_at": datetime.utcnow()
                })
                return f"SUCCESS: Added task '{task}'"
            except: return "ERROR: DB"
        return "ERROR: Context"

    async def set_reminder_tool(task: str, time: str, structured_time: str = None) -> str:
        if db is not None and user_id:
            try:
                await db.reminders.insert_one({
                    "task": task, "time": time, "scheduled_time": structured_time or time,
                    "user_id": str(user_id), "completed": False, "created_at": datetime.utcnow()
                })
                return f"SUCCESS: Set reminder for '{task}' at {time}"
            except: return "ERROR: DB"
        return "ERROR: Context"

    async def get_status_tool() -> str:
        if db is not None and user_id:
            tasks = await db.tasks.find({"user_id": str(user_id), "completed": False}).to_list(length=10)
            rems = await db.reminders.find({"user_id": str(user_id), "completed": False}).to_list(length=10)
            res = "Tasks:\n" + "\n".join([f"- {t['task']}" for t in tasks]) if tasks else "No tasks."
            res += "\n\nReminders:\n" + "\n".join([f"- {r['task']} at {r['time']}" for r in rems]) if rems else "\nNo reminders."
            return res
        return "Context error."

    # ── PRIMARY ENGINE: REGION-SAFE (Pollinations Smart) ─────────────────
    # This engine works EVERYWHERE and is not restricted by region.
    try:
        import httpx
        import re
        
        system_instruction_proxy = system_instruction + """
        To use tools, you MUST include these tags:
        - [ADD_TASK: Task description]
        - [SET_REMINDER: Task description | Time | ISO Time]
        - [GET_STATUS]
        """
        
        proxy_messages = [{"role": "system", "content": system_instruction_proxy}]
        for doc in history_docs[-5:]:
            if doc.get("user_message"):
                proxy_messages.append({"role": "user", "content": doc["user_message"]})
            if doc.get("bot_response"):
                proxy_messages.append({"role": "assistant", "content": doc["bot_response"] or "..."})
        proxy_messages.append({"role": "user", "content": user_message})

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://text.pollinations.ai/",
                json={"messages": proxy_messages, "model": "openai", "seed": 42},
                timeout=30.0
            )
            
            if resp.status_code == 200:
                text = resp.text or ""
                
                # Intent Parsing
                task_match = re.search(r"\[ADD_TASK:\s*(.*?)\]", text)
                if task_match: await add_task_tool(task_match.group(1))
                
                rem_match = re.search(r"\[SET_REMINDER:\s*(.*?)\|\s*(.*?)\|\s*(.*?)\]", text)
                if rem_match: await set_reminder_tool(rem_match.group(1), rem_match.group(2), rem_match.group(3))
                
                if "[GET_STATUS]" in text:
                    text = text.replace("[GET_STATUS]", await get_status_tool())
                
                clean_text = re.sub(r"\[ADD_TASK:.*?\]|\[SET_REMINDER:.*?\]|\[GET_STATUS\]", "", text).strip()
                return clean_text or "Protocols updated."
                
    except Exception as e:
        print(f"DEBUG: Proxy Error: {e}")

    # ── FALLBACK ENGINE: GEMINI (v1 Stable) ─────────────────────────────
    if GEMINI_API_KEY:
        try:
            import httpx
            for model in ["gemini-1.5-flash", "gemini-pro"]:
                url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={GEMINI_API_KEY}"
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json={
                        "contents": [{"role": "user", "parts": [{"text": user_message}]}],
                        "systemInstruction": {"parts": [{"text": system_instruction}]}
                    }, timeout=15.0)
                    if resp.status_code == 200:
                        return resp.json()['candidates'][0]['content']['parts'][0]['text']
        except: pass

    # ── FINAL FALLBACK ───────────────────────────────────────────────────
    return "I'm currently unable to process your request. Please try again in a moment."
