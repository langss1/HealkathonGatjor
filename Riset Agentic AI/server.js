// server.js
import express from "express";
import cors from "cors";
import bodyParser from "body-parser";
import dotenv from "dotenv";
import OpenAI from "openai";

dotenv.config();

const app = express();
app.use(cors());
app.use(bodyParser.json());

// Pastikan di .env ada: OPENAI_API_KEY=sk-xxxxxxxxxxxx
const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

// Prompt sistem untuk engine NLU SANI
const SYSTEM_PROMPT = `
Kamu adalah engine NLU untuk aplikasi "SANI (Sahabat JKN Indonesia)".
Tugasmu: membaca kalimat pengguna (bahasa Indonesia santai) dan mengembalikan JSON STRICT VALID dengan format:

{
  "intent": "daftar_rs" | "pindah_faskes" | "lainnya",
  "slots": {
    "nama": string | null,
    "rs": string | null,
    "faskes": string | null,
    "kota": string | null,
    "tanggal": string | null
  }
}

Definisi intent:
- "daftar_rs": user ingin daftar/berobat ke rumah sakit (RS, rumah sakit, rawat jalan RS, dll).
- "pindah_faskes": user ingin daftar/pindah/ubah fasilitas kesehatan tingkat pertama (faskes, fktp, puskesmas, klinik).
- "lainnya": di luar dua konteks di atas.

Aturan slot:
- "nama": nama orang jika disebut (contoh: "Nama saya Budi", "Saya bernama Dewi").
- "rs": nama rumah sakit jika disebut (contoh: "RS Mitra", "Rumah Sakit Harapan Sehat").
- "faskes": nama faskes FKTP jika disebut (contoh: "Puskesmas Sukamaju", "Klinik Sehat").
- "kota": kota/kabupaten jika disebut (contoh: "Kota Bandung", "Kabupaten Sleman").
- "tanggal": jika user menyebut "hari ini", "besok", "lusa" pakai string itu apa adanya.
  Kalau menyebut tanggal spesifik (format bebas), tuliskan apa adanya (contoh: "12 Januari 2025").

Output:
- Harus berupa JSON murni tanpa penjelasan lain.
- Jangan tambahkan properti di luar skema.
- Jika suatu slot tidak disebut, isi null.
`;

// Endpoint utama yang dipanggil dari frontend
app.post("/api/parse-intent", async (req, res) => {
  try {
    const { message } = req.body;

    if (!message || typeof message !== "string") {
      return res.status(400).json({ error: "message harus berupa string" });
    }

    // 🔴 DULU: pakai response_format (sekarang ERROR)
    // ✅ SEKARANG: pakai text.format → json_schema
    const response = await client.responses.create({
      model: "gpt-4.1-mini",
      instructions: SYSTEM_PROMPT,
      input: message,
      text: {
        format: {
          type: "json_schema",
          name: "sani_intent_schema",
          schema: {
            type: "object",
            properties: {
              intent: {
                type: "string",
                enum: ["daftar_rs", "pindah_faskes", "lainnya"],
              },
              slots: {
                type: "object",
                properties: {
                  nama: { type: ["string", "null"] },
                  rs: { type: ["string", "null"] },
                  faskes: { type: ["string", "null"] },
                  kota: { type: ["string", "null"] },
                  tanggal: { type: ["string", "null"] },
                },
                required: ["nama", "rs", "faskes", "kota", "tanggal"],
                additionalProperties: false,
              },
            },
            required: ["intent", "slots"],
            additionalProperties: false,
          },
          strict: true,
        },
      },
    });

    // Untuk structured output, JSON-nya dikirim sebagai text
    // Di Node SDK, biasanya ada di output[0].content[0].text
    const rawText = response.output[0].content[0].text;
    const jsonStr = typeof rawText === "string" ? rawText : String(rawText);
    const parsed = JSON.parse(jsonStr);

    res.json(parsed);
  } catch (err) {
    console.error("Error /api/parse-intent:", err);
    res.status(500).json({ error: "Gagal memproses intent" });
  }
});

// Endpoint cek server hidup
app.get("/", (req, res) => {
  res.send("SANI LLM Router API is running");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`SANI LLM router running on http://localhost:${PORT}`);
});
