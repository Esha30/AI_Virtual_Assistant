from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SessionBase(BaseModel):
    title: str
    user_id: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class Session(SessionBase):
    id: str = Field(alias="_id")

class InteractionBase(BaseModel):
    user_message: str
    bot_response: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Interaction(InteractionBase):
    id: str = Field(alias="_id")

class ReminderBase(BaseModel):
    task: str
    time: str
    scheduled_time: Optional[str] = None
    user_id: Optional[str] = None
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Reminder(ReminderBase):
    id: str = Field(alias="_id")

class TaskBase(BaseModel):
    task: str
    user_id: Optional[str] = None
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Task(TaskBase):
    id: str = Field(alias="_id")

class MessageRequest(BaseModel):
    message: str
    local_time: Optional[str] = None
    session_id: Optional[str] = None

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"

class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserInDB(UserBase):
    id: str = Field(alias="_id")
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
