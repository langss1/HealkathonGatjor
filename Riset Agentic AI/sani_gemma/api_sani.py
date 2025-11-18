from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import re

from chat_sani import chat_once  # pastikan file chat_sani.py ada di folder yg sama


# --------- FastAPI app + CORS ---------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # boleh dari mana saja (dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


# --------- Parser output SANI ---------
def parse_sani_output(text: str) -> dict:
    """
    Parsing format:
    [RESPONSE] ... [/RESPONSE]

    [ACTION]
    INTENT: ...
    NAVIGATE: "..."
    FILL_FORM: { ... }
    ASK_CONFIRM: "..."
    [/ACTION]

    Fallback:
    - Kalau tidak ada [RESPONSE], seluruh text dianggap jawaban.
    - Kalau tidak ada [ACTION], INTENT/NAVIGATE/FILL_FORM/ASK_CONFIRM dikosongkan.
    """

    # Default nilai
    response_text = None
    intent = None
    navigate = None
    fill_form = None
    ask_confirm = None

    # Cari [RESPONSE]
    resp_match = re.search(r"\[RESPONSE\](.*?)\[/RESPONSE\]", text, re.S | re.I)
    if resp_match:
        response_text = resp_match.group(1).strip()
    else:
        # fallback: pakai seluruh text sebagai jawaban
        response_text = text.strip()

    # Cari [ACTION] (kalau ada)
    action_match = re.search(r"\[ACTION\](.*?)\[/ACTION\]", text, re.S | re.I)
    if action_match:
        action_text = action_match.group(1).strip()

        # INTENT
        intent_match = re.search(r"INTENT:\s*([A-Z0-9_]+)", action_text)
        if intent_match:
            intent = intent_match.group(1).strip()

        # NAVIGATE
        nav_match = re.search(r'NAVIGATE:\s*"([^"]+)"', action_text)
        if nav_match:
            navigate = nav_match.group(1).strip()

        # FILL_FORM (ambil sebagai string mentah)
        fill_match = re.search(r"FILL_FORM:\s*{(.*?)}", action_text, re.S)
        if fill_match:
            inner = fill_match.group(1).strip()
            fill_form = "{\n" + inner + "\n}"

        # ASK_CONFIRM
        ask_match = re.search(r'ASK_CONFIRM:\s*"([^"]+)"', action_text)
        if ask_match:
            ask_confirm = ask_match.group(1).strip()

    return {
        "raw": text,
        "response_text": response_text,
        "intent": intent,
        "navigate": navigate,
        "fill_form": fill_form,
        "ask_confirm": ask_confirm,
    }


# --------- Endpoint utama ---------
@app.post("/sani/chat")
def sani_chat(req: ChatRequest):
    raw_output = chat_once(req.message)
    parsed = parse_sani_output(raw_output)
    return parsed


if __name__ == "__main__":
    # Jalankan dengan reload untuk dev
    uvicorn.run("api_sani:app", host="0.0.0.0", port=8000, reload=True)
