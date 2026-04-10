import os
import json
import asyncio
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from dotenv import load_dotenv
from datetime import datetime
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
    system_instruction = f"System Time: {current_time_str}. You are Aura, an elite AI assistant. Use tools for life management. Professional and concise style."

    # ── TOOLS CONFIGURATION ──────────────────────────────────────────────────
    async def add_task_tool(task: str) -> str:
        """Adds a new task to the user's to-do list."""
        if db is not None and user_id:
            await db.tasks.insert_one({
                "task": task, "user_id": user_id, "completed": False, "created_at": datetime.utcnow()
            })
            return f"Task added: {task}"
        return "DB Error."

    async def list_tasks_tool() -> str:
        """Lists current pending tasks."""
        if db is not None and user_id:
            cursor = db.tasks.find({"user_id": user_id, "completed": False})
            tasks = await cursor.to_list(length=20)
            return "Your Tasks:\n" + "\n".join([f"- {t['task']}" for t in tasks]) if tasks else "No tasks."
        return "DB Error."

    async def set_reminder_tool(task: str, time: str, structured_time: str) -> str:
        """Sets a reminder with a specific time."""
        if db is not None and user_id:
            await db.reminders.insert_one({
                "task": task, "time": time, "scheduled_time": structured_time,
                "user_id": user_id, "completed": False, "created_at": datetime.utcnow()
            })
            return f"Reminder set for {task} at {time}."
        return "DB Error."

    async def play_video_tool(query: str) -> str:
        """Plays a YouTube video."""
        import urllib.parse
        return f"Playing: {query}. [PLAY_VIDEO:https://www.youtube.com/embed?listType=search&list={urllib.parse.quote(query)}]"

    async def get_status_tool() -> str:
        """Retrieves a detailed brief of the user's current tasks and reminders."""
        if db is not None and user_id:
            tasks_cursor = db.tasks.find({"user_id": user_id, "completed": False})
            tasks = await tasks_cursor.to_list(length=20)
            reminders_cursor = db.reminders.find({"user_id": user_id, "completed": False})
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

    # ── PRIMARY ENGINE: GEMINI ────────────────────────────────────────────────
    gemini_failed = False
    if gemini_client:
        # Prioritize standard models with high free capacity
        AVAILABLE_MODELS = [
            'gemini-2.0-flash',
            'gemini-2.0-flash-lite-preview-02-05'
        ]
        gemini_tools = [add_task_tool, list_tasks_tool, set_reminder_tool, play_video_tool, get_status_tool]
        
        contents = []
        # Use more history to ensure it "never ends after only one message"
        for doc in history_docs[-10:]:
            if doc.get("user_message"):
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=doc["user_message"])]))
            if doc.get("bot_response"):
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=doc["bot_response"] or "...")]))

        config = types.GenerateContentConfig(
            tools=gemini_tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            system_instruction=system_instruction
        )

        for model_name in AVAILABLE_MODELS:
            try:
                current_contents = contents + [types.Content(role="user", parts=[types.Part.from_text(text=user_message)])]
                final_response = None
                for _ in range(3):
                    @retry(
                        stop=stop_after_attempt(3),
                        wait=wait_exponential(multiplier=1, min=2, max=6),
                        retry=retry_if_exception(is_quota_error),
                        reraise=True
                    )
                    async def call_gemini():
                        return await gemini_client.aio.models.generate_content(
                            model=model_name,
                            contents=current_contents,
                            config=config
                        )

                    response = await call_gemini()
                    
                    if not response.function_calls:
                        final_response = response.text or "Protocols updated."
                        break
                    
                    current_contents.append(response.candidates[0].content)
                    tool_parts = []
                    for tool_call in response.function_calls:
                        tool_name = tool_call.name
                        tool_args = tool_call.args
                        tool_fn = tools_map.get(tool_name)
                        if tool_fn:
                            result = await tool_fn(**tool_args)
                        else:
                            result = f"Error: Tool {tool_name} not found."
                        tool_parts.append(types.Part.from_function_response(name=tool_name, response={"result": result}))
                    current_contents.append(types.Content(role="function", parts=tool_parts))
                
                if final_response:
                    return final_response
                
            except Exception as e:
                err_msg = str(e).lower()
                print(f"Gemini error with model {model_name}: {e}")
                # If it's a model-specific error or quota, try next model
                if any(term in err_msg for term in ["429", "quota", "503", "demand", "404", "not found", "400"]):
                    continue
                # If it's a serious error, we might still want to try OpenAI fallback
                break
        
        gemini_failed = True
    else:
        gemini_failed = True

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
                    return msg.content or "Protocols updated."
                
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
                if response.status_code == 200:
                    return response.json()["choices"][0]["message"]["content"]
                return f"Processing complete. (Status: {response.status_code})"
            except Exception as e2:
                print(f"Pollinations fallback also failed: {e2}")
                return "The servers are currently experiencing high demand. Please try again in just a moment!"

    # ── FINAL SAFETY FALLBACK ────────────────────────────────────────────────
    return "I'm currently unable to process your request due to high server load. Please check your internet connection or try again in a few minutes."
