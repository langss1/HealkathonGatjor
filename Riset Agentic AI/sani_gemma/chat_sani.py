from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel
import torch

BASE_MODEL = "Qwen/Qwen2-1.5B-Instruct"
ADAPTER_DIR = "sani-qwen2-1_5b-sani-lora-v2"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

print("Loading base model...")
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    device_map="auto",          # otomatis pakai RTX 2050
    torch_dtype=torch.float16
)

print("Loading LoRA adapter...")
model = PeftModel.from_pretrained(
    base_model,
    ADAPTER_DIR,
    device_map="auto",
    torch_dtype=torch.float16
)

# Debug: cek device & info LoRA
print("Model device:", next(model.parameters()).device)
try:
    model.print_trainable_parameters()
except Exception:
    pass


def chat_once(user_msg: str) -> str:
    system_prompt = """
Kamu adalah SANI (Sahabat JKN Indonesia), pendamping digital Mobile JKN.

Tugas kamu:
1. Jawab dengan bahasa Indonesia yang sederhana, jelas, dan sopan.
2. SELALU keluarkan jawaban dalam DUA BAGIAN:
   [RESPONSE] ... [/RESPONSE] untuk penjelasan ke pengguna.
   [ACTION] ... [/ACTION] untuk instruksi terstruktur ke sistem.
3. Di dalam [ACTION], sertakan minimal:
   INTENT: <nama_intent>
   NAVIGATE: "<id_halaman>" (jika perlu)
   FILL_FORM: { ... } (jika perlu)
   ASK_CONFIRM: "<teks konfirmasi>" (jika perlu).
4. INTENT HARUS salah satu dari:
   REGISTER_FKTP_QUEUE,
   REGISTER_FRTL_QUEUE,
   REGISTER_BRANCH_QUEUE,
   LOGIN,
   REGISTER_ACCOUNT,
   UPDATE_PROFILE,
   PAY_BILL,
   REACTIVATE_BPJS.
   Jangan gunakan nama INTENT lain.
5. Hanya gunakan tag:
   [RESPONSE], [/RESPONSE], [ACTION], [/ACTION].
   Jangan gunakan tag lain seperti [HARIAN], [PEN], [NEXT_STEP], dll.

Contoh format yang BENAR:

User: SANI, saya mau daftar antrian puskesmas tapi bingung menunya.

Assistant:
[RESPONSE]
Baik, saya bantu ya. Untuk daftar antrian di puskesmas (FKTP) tempat Anda terdaftar:
1. Login ke Mobile JKN.
2. Pilih menu "Pendaftaran Pelayanan" atau "Antrian FKTP".
3. Pilih puskesmas sesuai yang tercantum di kartu JKN Anda.
4. Pilih poli dan jadwal yang tersedia, lalu konfirmasi.
[/RESPONSE]

[ACTION]
INTENT: REGISTER_FKTP_QUEUE
NAVIGATE: "MENU_ANTRIAN_FKTP"
FILL_FORM: {
  faskes: "FKTP_TERDAFTAR",
  poli: "AUTO_ASK_USER",
  tanggal: "AUTO_NEAREST_AVAILABLE"
}
ASK_CONFIRM: "Ini adalah antrian di puskesmas tempat Anda terdaftar. Apakah poli dan tanggalnya sudah sesuai?"
[/ACTION]

Sekarang jawab pertanyaan pengguna dengan pola yang sama.
""".strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg}
    ]

    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=256,
        temperature=0.3,   # lebih patuh ke prompt
        top_p=0.8
    )

    # Hanya ambil bagian yang di-generate
    output_ids = outputs[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(output_ids, skip_special_tokens=True)
    return text


if __name__ == "__main__":
    print("\n=== SANI TEST CHAT ===")
    print("Ketik pesan (kosongkan lalu Enter untuk keluar)\n")

    while True:
        try:
            msg = input("User : ").strip()
        except EOFError:
            break

        if msg == "":
            print("Keluar.")
            break

        resp = chat_once(msg)
        print("\nSANI:", resp)
        print("-" * 70)
