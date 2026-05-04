import os
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from database import get_db
from models import (
    MessageRequest, UserCreate, UserLogin, Token, TokenData, UserInDB,
    CreateSessionRequest
)
from agent import process_user_message
from auth import verify_password, get_password_hash, create_access_token, ALGORITHM, SECRET_KEY
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Define allowed origins
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "https://ai-virtual-assistant-gold.vercel.app",
]

frontend_url = os.getenv("FRONTEND_URL")
if frontend_url:
    url = frontend_url.rstrip("/")
    if url not in origins:
        origins.append(url)
    if f"{url}/" not in origins:
        origins.append(f"{url}/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    
    user_dict = await db.users.find_one({"email": token_data.email})
    if user_dict is None:
        raise credentials_exception
    user_dict["_id"] = str(user_dict["_id"])
    return user_dict

@app.get("/")
async def read_root(db = Depends(get_db)):
    try:
        # Check if we can ping the database
        await db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "message": "AI Virtual Assistant API is running (v5-manual-loop).",
        "database": db_status,
        "frontend_url": os.getenv("FRONTEND_URL", "not set"),
        "version": "5.0.0"
    }

@app.post("/signup")
async def signup(user: UserCreate, db = Depends(get_db)):
    try:
        print(f"Signup attempt for email: {user.email}")
        existing_user = await db.users.find_one({"email": user.email})
        if existing_user:
            print(f"Signup failed: Email {user.email} already registered")
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user.password)
        user_data = {
            "email": user.email,
            "hashed_password": hashed_password,
            "created_at": datetime.utcnow()
        }
        result = await db.users.insert_one(user_data)
        print(f"User created successfully: {user.email}")
        return {"message": "User created successfully", "id": str(result.inserted_id)}
    except Exception as e:
        print(f"CRITICAL ERROR during signup: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/login")
async def login(user_data: UserLogin, db = Depends(get_db)):
    user = await db.users.find_one({"email": user_data.email})
    if not user or not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
async def read_users_me(current_user = Depends(get_current_user)):
    return {"email": current_user["email"], "id": current_user["_id"]}

# ─────────────────────────────────────────────
# SESSION ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/sessions")
async def get_sessions(current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    cursor = db.sessions.find({"user_id": user_id}).sort("last_updated", -1)
    sessions = await cursor.to_list(length=100)
    for s in sessions:
        s["_id"] = str(s["_id"])
    return {"sessions": sessions}

@app.post("/sessions")
async def create_session(
    req: CreateSessionRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    session_data = {
        "title": req.title or "New Chat",
        "user_id": user_id,
        "last_updated": datetime.utcnow()
    }
    result = await db.sessions.insert_one(session_data)
    return {"session_id": str(result.inserted_id), "title": session_data["title"]}

@app.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    await db.interactions.delete_many({"session_id": session_id, "user_id": user_id})
    result = await db.sessions.delete_one({"_id": ObjectId(session_id), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}

@app.put("/sessions/{session_id}")
async def rename_session(
    session_id: str,
    data: dict,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    await db.sessions.update_one(
        {"_id": ObjectId(session_id), "user_id": user_id},
        {"$set": {"title": data.get("title", "New Chat"), "last_updated": datetime.utcnow()}}
    )
    return {"message": "Session renamed"}

@app.delete("/sessions")
async def clear_all_sessions(
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    # Delete all interactions for this user
    await db.interactions.delete_many({"user_id": user_id})
    # Delete all sessions for this user
    result = await db.sessions.delete_many({"user_id": user_id})
    return {"message": f"Deleted {result.deleted_count} sessions and all history"}

# ─────────────────────────────────────────────
# CHAT ENDPOINT (session-aware)
# ─────────────────────────────────────────────

@app.post("/chat")
async def chat_endpoint(req: MessageRequest, current_user = Depends(get_current_user), db = Depends(get_db)):
    user_message = req.message
    user_id = current_user["_id"]
    session_id = req.session_id

    # Auto-create session if none provided
    if not session_id:
        # Generate a smart title from the first user message (first 40 chars)
        title = user_message[:40].strip() + ("..." if len(user_message) > 40 else "")
        session_data = {
            "title": title,
            "user_id": user_id,
            "last_updated": datetime.utcnow()
        }
        result = await db.sessions.insert_one(session_data)
        session_id = str(result.inserted_id)
    else:
        # Update session timestamp
        await db.sessions.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"last_updated": datetime.utcnow()}}
        )

    # Fetch history for THIS session only (last 10 interactions)
    # If this is a regeneration, we don't save the NEW message as an interaction yet, 
    # instead we focus on getting a new response for the last user message.
    
    query = {"user_id": user_id, "session_id": session_id}
    cursor = db.interactions.find(query).sort("timestamp", -1).limit(10)
    history_docs = await cursor.to_list(length=10)
    history_docs.reverse()

    bot_response = await process_user_message(
        user_message,
        history_docs,
        db=db,
        user_id=user_id,
        user_local_time=req.local_time
    )

    # Save interaction
    result = await db.interactions.insert_one({
        "user_message": user_message,
        "bot_response": bot_response,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.utcnow()
    })

    return {"response": bot_response, "session_id": session_id, "interaction_id": str(result.inserted_id)}

# ─────────────────────────────────────────────
# HISTORY ENDPOINT (session-aware)
# ─────────────────────────────────────────────

@app.get("/history")
async def get_history(
    session_id: Optional[str] = None,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    query = {"user_id": user_id}
    if session_id:
        query["session_id"] = session_id
    
    cursor = db.interactions.find(query).sort("timestamp", 1)
    history_docs = await cursor.to_list(length=500)
    for doc in history_docs:
        doc["_id"] = str(doc["_id"])
    return {"history": history_docs}

@app.delete("/history")
async def clear_history(
    session_id: Optional[str] = None,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    query = {"user_id": user_id}
    if session_id:
        query["session_id"] = session_id
    await db.interactions.delete_many(query)
    return {"message": "History cleared"}

@app.delete("/history/{interaction_id}")
async def delete_interaction(interaction_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    result = await db.interactions.delete_one({"_id": ObjectId(interaction_id), "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"message": "Interaction deleted"}

# ─────────────────────────────────────────────
# UNIFIED CONTEXT ENDPOINT
# ─────────────────────────────────────────────

@app.get("/unified-context")
async def get_unified_context(
    session_id: Optional[str] = None,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    user_id = current_user["_id"]
    print(f"DEBUG: get_unified_context called for user_id='{user_id}'")
    
    # 1. Fetch sessions
    sessions_cursor = db.sessions.find({"user_id": str(user_id)}).sort("last_updated", -1)
    sessions = await sessions_cursor.to_list(length=100)
    for s in sessions:
        s["_id"] = str(s["_id"])
        
    # 2. Fetch tasks
    tasks_cursor = db.tasks.find({
        "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
        "completed": False
    }).sort("created_at", -1)
    tasks = await tasks_cursor.to_list(length=50)
    for t in tasks:
        t["_id"] = str(t["_id"])
        
    # 3. Fetch reminders
    reminders_cursor = db.reminders.find({
        "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
        "completed": False
    }).sort("created_at", -1)
    reminders = await reminders_cursor.to_list(length=50)
    for r in reminders:
        r["_id"] = str(r["_id"])
        
    print(f"DEBUG: Found {len(sessions)} sessions, {len(tasks)} tasks, {len(reminders)} reminders.")
    
    # 4. Fetch history if session_id provided
    history = []
    if session_id:
        history_cursor = db.interactions.find({"user_id": user_id, "session_id": session_id}).sort("timestamp", 1)
        history = await history_cursor.to_list(length=100)
        for doc in history:
            doc["_id"] = str(doc["_id"])
            
    from agent import gemini_client, openai_client
    return {
        "sessions": sessions,
        "tasks": tasks,
        "reminders": reminders,
        "history": history,
        "engines": {
            "gemini": gemini_client is not None,
            "openai": openai_client is not None
        }
    }

# ─────────────────────────────────────────────
# TASKS & REMINDERS
# ─────────────────────────────────────────────

@app.get("/tasks")
async def get_tasks(current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    cursor = db.tasks.find({
        "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
        "completed": False
    }).sort("created_at", -1)
    tasks = await cursor.to_list(length=100)
    for t in tasks:
        t["_id"] = str(t["_id"])
    return {"tasks": tasks}

@app.get("/reminders")
async def get_reminders(current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    cursor = db.reminders.find({
        "$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}],
        "completed": False
    }).sort("created_at", -1)
    reminders = await cursor.to_list(length=100)
    for r in reminders:
        r["_id"] = str(r["_id"])
    return {"reminders": reminders}

@app.put("/tasks/{task_id}")
async def update_task(task_id: str, data: dict, current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    await db.tasks.update_one({"_id": ObjectId(task_id), "user_id": user_id}, {"$set": data})
    return {"message": "Task updated"}

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    await db.tasks.delete_one({"_id": ObjectId(task_id), "user_id": user_id})
    return {"message": "Task deleted"}

@app.put("/reminders/{reminder_id}")
async def update_reminder(reminder_id: str, data: dict, current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    await db.reminders.update_one({"_id": ObjectId(reminder_id), "user_id": user_id}, {"$set": data})
    return {"message": "Reminder updated"}

@app.delete("/reminders/{reminder_id}")
async def delete_reminder(reminder_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    user_id = current_user["_id"]
    await db.reminders.delete_one({"_id": ObjectId(reminder_id), "user_id": user_id})
    return {"message": "Reminder deleted"}
