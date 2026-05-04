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
        
        system_instruction_proxy = f"{system_instruction}\n\nCRITICAL RULE: You MUST include a tag for EVERY action. \n- To add a task: [ADD_TASK: Task Name]\n- To set a reminder: [SET_REMINDER: Name | Time | ISO]\n\nIf the user asks for MULTIPLE actions (e.g. a task AND a reminder), you MUST output MULTIPLE tags in your response. DO NOT FORGET ANY TAGS."
        
        proxy_messages = [{"role": "system", "content": system_instruction_proxy}]
        for doc in history_docs[-5:]:
            if doc.get("user_message"):
                proxy_messages.append({"role": "user", "content": doc["user_message"]})
            if doc.get("bot_response"):
                proxy_messages.append({"role": "assistant", "content": doc["bot_response"] or "..."})
        proxy_messages.append({"role": "user", "content": user_message})

        async with httpx.AsyncClient() as client:
            import random
            resp = await client.post(
                "https://text.pollinations.ai/",
                json={
                    "messages": proxy_messages, 
                    "model": "gpt-4o",
                    "seed": random.randint(1, 1000000)
                },
                timeout=30.0
            )
            
            if resp.status_code == 200:
                text = resp.text or ""
                
                # Robust extraction
                if text.strip().startswith("{"):
                    try:
                        data = json.loads(text)
                        text = data.get("content") or data.get("reasoning_content") or data.get("reasoning") or text
                    except: pass
                
                # ── CLEANUP REASONING (Safe) ──────────────────
                # ── CLEANUP REASONING (Safe Dynamic) ──────────────────
                # Safely remove sentences where the AI thinks out loud (e.g., "User wants... Need to call...")
                text = re.sub(r"(?i)(User wants.*?\. |The user wants.*?\. |Need to call.*?\. |We need to call.*?\. |Use tool.*?\. )", "", text)
                
                phrases_to_remove = [
                    "User wants a reminder set. Use tool.",
                    "User wants status: list status.",
                    "The command: Tasks:",
                    "Use tool.",
                    "Therefore:",
                    "Protocols updated.",
                    "Protocols updated"
                ]
                for phrase in phrases_to_remove:
                    text = text.replace(phrase, "")
                text = text.strip()                
                
                # ── FUZZY INTENT PARSER (Backup Safety Net) ──────────────
                # Catch cases where AI says "Reminder set for X at Y" without brackets
                if "Reminder set for" in text and "[" not in text:
                    fuzzy_rem = re.search(r"Reminder set for \"(.*?)\" at (.*?) on (.*)", text)
                    if fuzzy_rem:
                        await set_reminder_tool(fuzzy_rem.group(1), fuzzy_rem.group(2), fuzzy_rem.group(3))
                
                if "Task" in text and "added" in text and "[" not in text:
                    fuzzy_task = re.search(r"Task \"(.*?)\" added", text)
                    if fuzzy_task:
                        await add_task_tool(fuzzy_task.group(1))

                # Fuzzy trigger for GET_STATUS
                is_status_request = False
                if any(phrase in text.lower() for phrase in ["list_status", "status tool", "list status", "list of their reminders", "tasks:", "reminders:", "tasks and reminders"]):
                    is_status_request = True

                # ── PRIMARY INTENT PARSING (Support Multiple) ───────────
                added_tasks = []
                for match in re.finditer(r"\[ADD_TASK:\s*(.*?)\]", text):
                    await add_task_tool(match.group(1))
                    added_tasks.append(match.group(1))
                
                added_rems = []
                for match in re.finditer(r"\[SET_REMINDER:\s*(.*?)\|\s*(.*?)\|\s*(.*?)\]", text):
                    await set_reminder_tool(match.group(1), match.group(2), match.group(3))
                    added_rems.append(f"'{match.group(1)}' at {match.group(2)}")
                
                if "[GET_STATUS]" in text or is_status_request:
                    # Bypass all AI text completely for status checks
                    return await get_status_tool()
                
                # If any action was taken, completely ignore the AI's generated text (which might contain reasoning)
                # and return a clean, hardcoded success message.
                if added_tasks or added_rems:
                    resp_parts = []
                    if added_tasks:
                        resp_parts.append(f"Task(s) added: {', '.join(added_tasks)}.")
                    if added_rems:
                        resp_parts.append(f"Reminder(s) set: {', '.join(added_rems)}.")
                    return " ".join(resp_parts)
                
                # If no actions or status, return the cleaned AI text
                clean_text = re.sub(r"\[ADD_TASK:.*?\]|\[SET_REMINDER:.*?\]|\[GET_STATUS\]", "", text).strip()
                clean_text = re.sub(r"^[:.,\s]+", "", clean_text)
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
