from typing import List, Literal, Optional, Dict, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from chat_sani import generate_chat_reply, parse_intent_and_slots

# ===================== MODELS UNTUK API ===================== #

class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatRequest(BaseModel):
    history: List[ChatTurn] = []
    message: str

class ChatResponse(BaseModel):
    reply: str

class ParseRequest(BaseModel):
    message: str
    page: Optional[str] = None  # disediakan kalau nanti mau pakai

class ParseResponse(BaseModel):
    intent: str
    slots: Dict[str, Any]

# ===================== FASTAPI APP ===================== #

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # development, bisa dipersempit kalau perlu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok", "message": "SANI API running"}

@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    # konversi history ke list[dict] buat chat_sani
    history_dicts = [{"role": h.role, "content": h.content} for h in req.history]
    reply = generate_chat_reply(history_dicts, req.message)
    return ChatResponse(reply=reply)

@app.post("/api/parse-intent", response_model=ParseResponse)
async def api_parse_intent(req: ParseRequest):
    result = parse_intent_and_slots(req.message)
    return ParseResponse(intent=result["intent"], slots=result["slots"])
