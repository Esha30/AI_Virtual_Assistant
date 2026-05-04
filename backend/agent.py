import os
import json
import asyncio
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime
from bson import ObjectId
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

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

# Custom retry condition for Quota Exceeded or High Demand
def is_quota_error(exception):
    err_msg = str(exception).lower()
    return any(term in err_msg for term in ["429", "quota", "exhausted", "503", "demand", "insufficient_quota", "paying", "billing"])

async def process_user_message(user_message: str, history_docs: list, db=None, user_id=None, user_local_time: str = None) -> str:
    current_time_str = user_local_time or datetime.utcnow().isoformat()
    system_instruction = f"""System Time: {current_time_str}. 
You are Aura, an elite AI life management assistant. 
CRITICAL: You MUST use the provided tools for adding tasks, setting reminders, or listing status. 
Never tell the user you have done something (like adding a task or setting a reminder) unless you have successfully called the corresponding tool.
If a user specifies a time like '3pm' and it is currently past that time (e.g., it's 8pm), assume they mean 3pm the NEXT day unless they specify otherwise.
Professional, concise, and proactive style."""

    # ── TOOLS CONFIGURATION ──────────────────────────────────────────────────
    async def add_task_tool(task: str) -> str:
        """Adds a new task to the user's to-do list."""
        print(f"DEBUG: add_task_tool called for task='{task}' and user_id='{user_id}'")
        if db is not None and user_id:
            try:
                res = await db.tasks.insert_one({
                    "task": task, "user_id": str(user_id), "completed": False, "created_at": datetime.utcnow()
                })
                print(f"DEBUG: Task inserted successfully. ID: {res.inserted_id}")
                return f"SUCCESS: I have added the task '{task}' to your to-do list."
            except Exception as e:
                print(f"DEBUG: Error inserting task: {e}")
                return f"ERROR: Database Error: {e}"
        print("DEBUG: Database or user_id missing in tool.")
        return "ERROR: System Context unavailable."

    async def list_tasks_tool() -> str:
        """Lists current pending tasks."""
        if db is not None and user_id:
            cursor = db.tasks.find({
                "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
                "completed": False
            })
            tasks = await cursor.to_list(length=20)
            return "Your Tasks:\n" + "\n".join([f"- {t['task']}" for t in tasks]) if tasks else "No tasks."
        return "DB Error."

    async def set_reminder_tool(task: str, time: str, structured_time: str = None) -> str:
        """Sets a reminder with a specific task and time."""
        print(f"DEBUG: set_reminder_tool called for task='{task}', time='{time}', user_id='{user_id}'")
        if db is not None and user_id:
            try:
                # Ensure structured_time is at least the human readable time if missing
                s_time = structured_time or time
                res = await db.reminders.insert_one({
                    "task": task, "time": time, "scheduled_time": s_time,
                    "user_id": str(user_id), "completed": False, "created_at": datetime.utcnow()
                })
                print(f"DEBUG: Reminder inserted successfully. ID: {res.inserted_id}")
                return f"SUCCESS: I have set a reminder for '{task}' at {time}."
            except Exception as e:
                print(f"DEBUG: Error inserting reminder: {e}")
                return f"ERROR: Database Error: {e}"
        return "ERROR: System Context unavailable."

    async def play_video_tool(query: str) -> str:
        """Plays a YouTube video."""
        import urllib.parse
        return f"Playing: {query}. [PLAY_VIDEO:https://www.youtube.com/embed?listType=search&list={urllib.parse.quote(query)}]"

    async def get_status_tool() -> str:
        """Retrieves a detailed brief of the user's current tasks and reminders."""
        if db is not None and user_id:
            tasks_cursor = db.tasks.find({
                "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
                "completed": False
            })
            tasks = await tasks_cursor.to_list(length=20)
            reminders_cursor = db.reminders.find({
                "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
                "completed": False
            })
            reminders = await reminders_cursor.to_list(length=20)
            
            status_text = "### Quick Briefing\n\n"
            if tasks:
                status_text += "**Pending Tasks:**\n" + "\n".join([f"• {t['task']}" for t in tasks])
            else:
                status_text += "*No pending tasks.*\n"
                
            status_text += "\n\n"
            if reminders:
                status_text += "**Upcoming Reminders:**\n" + "\n".join([f"• {r['task']} (scheduled for {r['time']})" for r in reminders])
            else:
                status_text += "*No active reminders.*"
            
            return status_text
        return "System Context unavailable."

    tools_map = {
        "add_task_tool": add_task_tool,
        "list_tasks_tool": list_tasks_tool,
        "set_reminder_tool": set_reminder_tool,
        "play_video_tool": play_video_tool,
        "get_status_tool": get_status_tool
    }

    # ── STABLE ENGINE: GEMINI v1 ─────────────────────────────────────────
    # This version uses the final 'v1' stable API for maximum reliability.
    gemini_failed = False
    if GEMINI_API_KEY:
        try:
            import httpx
            import re
            
            # 1. Prepare history
            contents_rest = []
            for doc in history_docs[-6:]:
                if doc.get("user_message"):
                    contents_rest.append({"role": "user", "parts": [{"text": doc["user_message"]}]})
                if doc.get("bot_response"):
                    contents_rest.append({"role": "model", "parts": [{"text": doc["bot_response"] or "..."}]})
            contents_rest.append({"role": "user", "parts": [{"text": user_message}]})

            # 2. Try Stable Models in v1
            # Note: We use 'v1' instead of 'v1beta'
            for model_name in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]:
                url = f"https://generativelanguage.googleapis.com/v1/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                
                async with httpx.AsyncClient() as client:
                    try:
                        resp = await client.post(url, json={
                            "contents": contents_rest,
                            "systemInstruction": {"parts": [{"text": system_instruction + "\n\nTo use tools, include these tags: [ADD_TASK: Task], [SET_REMINDER: Task | Time | ISO], [GET_STATUS]"}]}
                        }, timeout=30.0)
                        
                        if resp.status_code == 200:
                            data = resp.json()
                            text = data['candidates'][0]['content']['parts'][0]['text']
                            
                            # Manual tool parsing
                            task_match = re.search(r"\[ADD_TASK:\s*(.*?)\]", text)
                            if task_match: await add_task_tool(task_match.group(1))
                            
                            rem_match = re.search(r"\[SET_REMINDER:\s*(.*?)\|\s*(.*?)\|\s*(.*?)\]", text)
                            if rem_match: await set_reminder_tool(rem_match.group(1), rem_match.group(2), rem_match.group(3))
                            
                            if "[GET_STATUS]" in text:
                                text = text.replace("[GET_STATUS]", await get_status_tool())
                            
                            clean_text = re.sub(r"\[ADD_TASK:.*?\]|\[SET_REMINDER:.*?\]|\[GET_STATUS\]", "", text).strip()
                            return clean_text or "Protocols updated."
                        else:
                            print(f"DEBUG: v1 failed for {model_name}: {resp.status_code}")
                            continue # Try next model
                    except Exception as e:
                        print(f"DEBUG: v1 exception for {model_name}: {e}")
                        continue
            
            # If all v1 models failed, fall back to v1beta as a last resort (sometimes needed for Flash 1.5)
            url_beta = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            async with httpx.AsyncClient() as client:
                resp = await client.post(url_beta, json={
                    "contents": contents_rest,
                    "systemInstruction": {"parts": [{"text": system_instruction}]}
                }, timeout=15.0)
                if resp.status_code == 200:
                    data = resp.json()
                    text = data['candidates'][0]['content']['parts'][0]['text']
                    return re.sub(r"\[.*?\]", "", text).strip() or "Protocols updated."

            gemini_failed = True
        except Exception as e:
            print(f"DEBUG: Gemini Stable Engine Error: {e}")
            gemini_failed = True
    else:
        gemini_failed = True

    # ── FALLBACK ENGINE: OPENAI ───────────────────────────────────────────────

    # ── FALLBACK ENGINE: OPENAI ───────────────────────────────────────────────
    if gemini_failed and openai_client:
        try:
            openai_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "add_task_tool",
                        "description": "Adds a new task to the user's to-do list.",
                        "parameters": {
                            "type": "object",
                            "properties": {"task": {"type": "string"}},
                            "required": ["task"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "list_tasks_tool",
                        "description": "Lists current pending tasks."
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "set_reminder_tool",
                        "description": "Sets a reminder with a specific time.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string"},
                                "time": {"type": "string", "description": "Human readable time"},
                                "structured_time": {"type": "string", "description": "ISO format time"}
                            },
                            "required": ["task", "time", "structured_time"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "play_video_tool",
                        "description": "Plays a YouTube video.",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_status_tool",
                        "description": "Retrieves a detailed brief of the user's current tasks and reminders."
                    }
                }
            ]

            messages = [{"role": "system", "content": system_instruction}]
            for doc in history_docs[-5:]:
                if doc.get("user_message"):
                    messages.append({"role": "user", "content": doc["user_message"]})
                if doc.get("bot_response"):
                    messages.append({"role": "assistant", "content": doc["bot_response"]})
            messages.append({"role": "user", "content": user_message})

            for _ in range(3):
                response = await openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto"
                )
                
                msg = response.choices[0].message
                if not msg.tool_calls:
                    return msg.content or "Protocols updated (OpenAI Turn 1)."
                
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    fn = tools_map.get(fn_name)
                    result = await fn(**fn_args) if fn else f"Error: Tool {fn_name} not found."
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": fn_name,
                        "content": result
                    })
            
            return messages[-1].get("content") or "Processing complete."

        except Exception as e:
            print(f"OpenAI fallback encountered an error: {e}")
            try:
                import requests
                messages_pollin = [{"role": "system", "content": system_instruction}]
                for doc in history_docs[-5:]:
                    if doc.get("user_message"):
                        messages_pollin.append({"role": "user", "content": doc["user_message"]})
                    if doc.get("bot_response"):
                        messages_pollin.append({"role": "assistant", "content": doc["bot_response"]})
                messages_pollin.append({"role": "user", "content": user_message})
                response = requests.post(
                    "https://text.pollinations.ai/openai/",
                    json={"model": "openai", "messages": messages_pollin},
                    timeout=30.0
                )
                if response.status_code != 200:
                    print(f"DEBUG: Pollinations failed with status {response.status_code}: {response.text}")
                    return "I'm having trouble processing that request right now. Please try again in a moment."
                
                msg = response.json()["choices"][0]["message"]
                if not msg.get("tool_calls"):
                    return msg.get("content") or "Protocols updated (Pollinations Turn 1)."
                
                messages_pollin.append(msg)
                for tool_call in msg["tool_calls"]:
                    fn_name = tool_call["function"]["name"]
                    try:
                        fn_args = json.loads(tool_call["function"]["arguments"])
                    except Exception:
                        fn_args = {}
                    fn = tools_map.get(fn_name)
                    result = await fn(**fn_args) if fn else f"Error: Tool {fn_name} not found."
                    
                    messages_pollin.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "name": fn_name,
                        "content": result
                    })
            except Exception as e2:
                print(f"Pollinations fallback also failed: {e2}")
                return "The servers are currently experiencing high demand. Please try again in just a moment!"

    # ── FINAL SAFETY FALLBACK ────────────────────────────────────────────────
    if not gemini_client and not openai_client:
        return "System configuration error: AI API Keys (GEMINI_API_KEY or OPENAI_API_KEY) are missing in the backend environment. Please set them to enable Aura's intelligence."
        
    return "I'm currently unable to process your request due to high server load or quota limits. Please try again in a few minutes."
