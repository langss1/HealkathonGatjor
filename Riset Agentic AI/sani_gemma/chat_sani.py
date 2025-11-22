import json
import re
from typing import Dict, Any, List

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# ===================== KONFIGURASI MODEL ===================== #

BASE_MODEL = "Qwen/Qwen2-1.5B-Instruct"
ADAPTER_DIR = "sani-qwen2-1_5b-sani-lora-v3"

print(">> [SANI] Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

print(">> [SANI] Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    device_map="auto",
    torch_dtype=torch.float16,
)

print(">> [SANI] Loading LoRA adapter (v3)...")
model = PeftModel.from_pretrained(
    base_model,
    ADAPTER_DIR,
    device_map="auto",
    torch_dtype=torch.float16,
)
model.eval()
DEVICE = next(model.parameters()).device
print(">> [SANI] Siap. Device:", DEVICE)

# ===================== PROMPT CHATBOT ===================== #

SYSTEM_PROMPT_CHAT = """
Kamu adalah SANI (Sahabat JKN Indonesia), asisten virtual pendamping aplikasi Mobile JKN
yang dibuat untuk lomba Healkathon (bukan chatbot resmi BPJS).

Peranmu:
1. Mengobrol santai dan ramah dengan peserta JKN.
2. Menjelaskan apa itu JKN, BPJS Kesehatan, dan fitur-fitur umum Mobile JKN
   (antrian, kepesertaan, iuran, perubahan data, dsb).
3. Memberikan tips kesehatan ringan dan edukasi (bukan diagnosis, bukan pengganti dokter).
   Sertakan pengingat singkat: "kalau keluhan berat atau tidak membaik, segera periksa ke dokter".
4. Kalau perlu tindakan di aplikasi, cukup jelaskan langkah-langkahnya secara singkat
   dengan bahasa natural (misalnya: "Buka menu Kartu Peserta, lalu pilih ...").
   JANGAN menuliskan format teknis.

PENTING (WAJIB PATUH):
- JANGAN menuliskan kata atau label seperti:
  INTENT:, ACTION:, FOTO_MENU:, BOT_INTEGRATION, [BLOCK], [ACTION], [RESPONSE],
  atau struktur JSON apa pun.
- Jangan bilang bahwa kamu hanya memberikan "contoh pertanyaan".
  Kalau pengguna bertanya sesuatu, langsung jawab isi pertanyaannya.
- Jawaban harus berupa paragraf atau poin kalimat biasa yang enak dibaca pengguna.

Gaya bahasa:
- Sopan, hangat, dan mudah dimengerti.
- Gunakan bahasa Indonesia santai tapi tetap sopan.
- Jawaban ringkas, fokus membantu kebutuhan pengguna.
""".strip()

# ===================== PROMPT NLU (INTENT JSON) ===================== #

SYSTEM_PROMPT_NLU = """
Kamu adalah engine NLU untuk SANI (Sahabat JKN Indonesia).
Tugasmu: baca kalimat pengguna dan kembalikan JSON VALID dengan format:

{
  "intent": "<daftar_rs | pindah_faskes | other>",
  "slots": {
    "nama": "<nama peserta atau kosong>",
    "rs": "<nama rumah sakit atau kosong>",
    "faskes": "<nama faskes tingkat pertama atau kosong>",
    "kota": "<kota/kabupaten atau kosong>",
    "tanggal": "<tanggal atau token seperti 'besok', 'lusa', 'hari ini', atau kosong>",
    "field": "<nama field yang diubah, mis. 'faskes', 'no_hp', 'alamat', atau kosong>"
  }
}

- intent:
  - "daftar_rs" kalau user mau daftar berobat / ambil antrean ke rumah sakit rujukan.
  - "pindah_faskes" kalau user mau daftar/pindah faskes tingkat pertama (puskesmas/klinik).
  - "other" kalau tidak termasuk dua itu.

- Jangan pakai intent lain selain tiga di atas.
- HANYA kembalikan JSON, tanpa penjelasan tambahan, tanpa markdown.
""".strip()

# ===================== FUNGSI GENERATE UMUM ===================== #

def _generate(messages: List[Dict[str, str]],
              max_new_tokens: int = 256,
              temperature: float = 0.6) -> str:
    """Fungsi umum generate teks dari model Qwen + LoRA."""
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=0.9,
        )

    output_ids = outputs[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(output_ids, skip_special_tokens=True)
    return text.strip()

# ===================== CLEAN OUTPUT CHAT ===================== #

def _clean_chat_output(raw: str) -> str:
    """
    Bersihkan output model dari artefak agentic:
    - blok [ACTION] / [RESPONSE] (termasuk variasi [^RESPONSE])
    - tag-tag [XXXXX] lain
    - baris INTENT:, ACTION:, MENU_KATEGORI:, MENU_ITEM:, CONTENT:, FOTO_MENU:, BOT_INTEGRATION:
    - potongan JSON / code block setelah teks utama
    - merapikan list bernomor agar tiap nomor di baris baru
    """
    if not raw:
        return ""

    text = raw

    # 1) buang blok [ACTION] ... [/ACTION] dan [RESPONSE] ... [/RESPONSE] (termasuk yang pakai '^')
    text = re.sub(
        r"\[\^?ACTION\].*?\[\^?/ACTION\]",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(
        r"\[\^?RESPONSE\].*?\[\^?/RESPONSE\]",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2) buang marker satuan di dalam [] (mis. [RESPONSE], [^RESPONSE], [ACTION], dll)
    text = re.sub(r"\[[^\]]+\]", "", text)

    # 3) buang baris metadata teknis
    meta_keys = [
        r"INTENT:",
        r"ACTION:",
        r"FOTO_MENU:",
        r"BOT_INTEGRATION:",
        r"MENU_KATEGORI:",
        r"MENU_ITEM:",
        r"CONTENT:",
    ]
    for key in meta_keys:
        text = re.sub(rf"^.*{key}.*$", "", text,
                      flags=re.MULTILINE | re.IGNORECASE)

    # 4) potong kalau ada ``` (code block) – sisanya dianggap sampah teknis
    text = text.split("```")[0]

    # 5) potong kalau ada garis '---' diikuti struktur { ... }
    text = re.split(r"\n\s*[-–—]{3,}", text)[0]

    # 6) potong kalau ada '{' di baris baru (indikasi JSON)
    text = re.split(r"\n\s*\{", text)[0]

    # 7) pecah list bernomor yang nempel di satu baris
    #    contoh: ".... hari ini? 1. Buka menu ... 2. Pilih ..." -> tiap "n." mulai di baris baru
    text = re.sub(
        r"(?<!\n)\s*(\d+\.)",
        lambda m: "\n" + m.group(1),
        text
    )

    # 8) rapikan spasi & baris kosong berlebih
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)  # max 2 baris kosong
    text = text.strip()

    return text


# ===================== CHATBOT API ===================== #

def generate_chat_reply(history: List[Dict[str, str]],
                        message: str) -> str:
    """
    history: list of {"role": "user"/"assistant", "content": str}
    message: pesan user terbaru

    return: reply string yang sudah dibersihkan dari artefak teknis
    """
    msgs: List[Dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT_CHAT}
    ]

    # tambahkan riwayat (kalau ada)
    for turn in history or []:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})

    # pesan user terbaru
    msgs.append({"role": "user", "content": message})

    raw = _generate(msgs, max_new_tokens=320, temperature=0.7)
    cleaned = _clean_chat_output(raw)

    if not cleaned.strip():
        cleaned = (
            "Maaf, SANI sedikit bingung dengan pertanyaan tadi. "
            "Bisa diulang dengan kalimat lain?"
        )

    return cleaned

# ===================== NLU: INTENT + SLOTS ===================== #

def _generate_nlu(user_msg: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_NLU},
        {"role": "user", "content": user_msg},
    ]
    return _generate(messages, max_new_tokens=256, temperature=0.2)

def _map_to_agentic_intent(user_msg: str,
                           intent_raw: str,
                           slots: Dict[str, Any]):
    """
    Mapping intent NLU menjadi intent agentic:
    REGISTER_FKTP_QUEUE, REGISTER_FRTL_QUEUE, REGISTER_BRANCH_QUEUE,
    UPDATE_PROFILE, REGISTER_ACCOUNT, PAY_BILL, REACTIVATE_BPJS, LOGIN, OTHER
    """
    text = (user_msg or "").lower()
    intent_raw = (intent_raw or "other").lower()

    agentic_intent = "OTHER"
    field = slots.get("field") or ""

    if intent_raw == "daftar_rs":
        # Bisa FKTP / FKRTL -> bedakan pakai kata kunci
        if any(k in text for k in ["puskesmas", "fktp", "klinik",
                                   "faskes tingkat pertama", "faskes tingkat i"]):
            agentic_intent = "REGISTER_FKTP_QUEUE"
        else:
            agentic_intent = "REGISTER_FRTL_QUEUE"
    elif intent_raw == "pindah_faskes":
        agentic_intent = "UPDATE_PROFILE"
        field = field or "faskes"

    # Heuristik tambahan umum
    if "registrasi" in text or "daftar akun" in text or "buat akun" in text:
        agentic_intent = "REGISTER_ACCOUNT"
    elif any(k in text for k in ["antrian", "antre", "antrean", "ambil antrean"]):
        if any(k in text for k in ["faskes", "puskesmas", "klinik", "fktp"]):
            agentic_intent = "REGISTER_FKTP_QUEUE"
        elif any(k in text for k in ["rs ", "rumah sakit"]):
            agentic_intent = "REGISTER_FRTL_QUEUE"
    elif any(k in text for k in ["ubah", "ganti", "pindah"]):
        if "faskes" in text:
            agentic_intent = "UPDATE_PROFILE"
            field = field or "faskes"
    elif any(k in text for k in ["iuran", "tunggakan"]) or (
        "bayar" in text and "iuran" in text
    ):
        agentic_intent = "PAY_BILL"
    elif "aktif" in text and "kembali" in text:
        agentic_intent = "REACTIVATE_BPJS"
    elif "login" in text or "masuk" in text:
        agentic_intent = "LOGIN"

    slots["field"] = field
    return agentic_intent, slots

def parse_intent_and_slots(user_msg: str) -> Dict[str, Any]:
    """
    Mengembalikan:
    {
      "intent": "<REGISTER_FKTP_QUEUE | REGISTER_FRTL_QUEUE | ... | OTHER>",
      "slots": { ... }
    }

    Agentic HANYA aktif kalau ada kata kunci fungsional, selain itu -> OTHER.
    """
    text = (user_msg or "").lower()

    # ---- GATE: hanya aktifkan agentic kalau ada kata kunci fungsi ----
    functional_keywords = [
        "daftar", "antri", "antre", "antrean", "ambil antrean",
        "puskesmas", "fktp", "faskes", "faskes tingkat pertama",
        "faskes tingkat i", "rumah sakit", "rs ",
        "kantor cabang", "bpjs cabang",
        "pindah faskes", "ubah faskes", "ganti faskes",
        "ubah nomor", "ganti nomor", "nomor hp", "no hp",
        "alamat", "email",
        "bayar iuran", "bayar bpjs", "iuran", "tunggakan",
        "aktifkan kembali", "reaktivasi",
        "login", "masuk aplikasi", "daftar akun", "registrasi"
    ]

    if not any(kw in text for kw in functional_keywords):
        # tidak ada kata kunci → anggap SEKEDAR CHAT,
        # biar agentic tidak muncul sama sekali
        return {"intent": "OTHER", "slots": {}}

    # ---- kalau lolos gate, baru tanya model NLU ----
    raw = _generate_nlu(user_msg)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"intent": "OTHER", "slots": {}}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"intent": "OTHER", "slots": {}}

    intent_raw = (data.get("intent") or "other").strip().lower()
    slots = data.get("slots") or {}

    norm_slots: Dict[str, Any] = {
        "nama": slots.get("nama") or "",
        "rs": slots.get("rs") or "",
        "faskes": slots.get("faskes") or "",
        "kota": slots.get("kota") or "",
        "tanggal": slots.get("tanggal") or "",
        "field": slots.get("field") or "",
    }

    # mapping ke intent agentic
    agentic_intent, norm_slots = _map_to_agentic_intent(
        user_msg, intent_raw, norm_slots
    )

    return {"intent": agentic_intent, "slots": norm_slots}

# ===================== CLI TEST (optional) ===================== #

if __name__ == "__main__":
    print("=== SANI v3 CLI ===")
    hist: List[Dict[str, str]] = []
    while True:
        try:
            msg = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not msg:
            break

        # Chat reply
        reply = generate_chat_reply(hist, msg)
        print("SANI:", reply)

        # Intent parse (debug)
        parsed = parse_intent_and_slots(msg)
        print("NLU:", parsed)

        hist.append({"role": "user", "content": msg})
        hist.append({"role": "assistant", "content": reply})
