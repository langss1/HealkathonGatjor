// Ubah ke alamat server FastAPI kamu kalau perlu
const SANI_API_BASE = "http://127.0.0.1:8000";

// history percakapan untuk endpoint /api/chat
window._saniHistory = window._saniHistory || [];
// state untuk aksi agentic yang butuh konfirmasi
window._saniPendingAction = null;

function initSaniAgentic(pageId) {
  const modal = document.getElementById("chatbotModal");
  if (!modal) return;

  const chatBody = modal.querySelector(".chat-body");
  const form = modal.querySelector("form");
  const input = form ? form.querySelector("input[type='text']") : null;

  if (!chatBody || !form || !input) return;

  // bubble loading SANI (bot)
  let typingBubble = null;

  // ================== STYLE ANIMASI BUBBLE LOADING ==================
  function ensureTypingStyles() {
    if (document.getElementById("sani-typing-style")) return;

    const style = document.createElement("style");
    style.id = "sani-typing-style";
    style.textContent = `
      .sani-typing-bubble {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 4px;
      }
      .sani-typing-dots {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .sani-typing-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        background-color: #cbd5f5;
        animation: sani-typing-bounce 1s infinite ease-in-out;
      }
      .sani-typing-dot:nth-child(2) {
        animation-delay: 0.15s;
      }
      .sani-typing-dot:nth-child(3) {
        animation-delay: 0.3s;
      }
      @keyframes sani-typing-bounce {
        0%, 80%, 100% {
          transform: translateY(0);
          opacity: 0.4;
        }
        40% {
          transform: translateY(-4px);
          opacity: 1;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function addBubble(text, from = "bot") {
    const wrap = document.createElement("div");
    wrap.className =
      "d-flex mb-2" + (from === "user" ? " justify-content-end" : "");

    const bubble = document.createElement("div");
    bubble.className = from === "user" ? "user-bubble" : "bot-bubble";

    const inner = document.createElement("div");
    inner.innerHTML = text;
    bubble.appendChild(inner);

    const time = document.createElement("div");
    time.className =
      "chat-time mt-1" + (from === "user" ? " text-end" : "");
    time.textContent = from === "user" ? "Anda" : "SANI";
    bubble.appendChild(time);

    wrap.appendChild(bubble);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  // ========== BUBBLE LOADING SANI (3 TITIK) ==========
  function showTyping() {
    if (typingBubble) return; // jangan dobel

    ensureTypingStyles();

    const wrap = document.createElement("div");
    wrap.className = "d-flex mb-2";

    const bubble = document.createElement("div");
    bubble.className = "bot-bubble";

    const inner = document.createElement("div");
    inner.className = "sani-typing-bubble";

    const dots = document.createElement("span");
    dots.className = "sani-typing-dots";

    for (let i = 0; i < 3; i++) {
      const dot = document.createElement("span");
      dot.className = "sani-typing-dot";
      dots.appendChild(dot);
    }

    inner.appendChild(dots);
    bubble.appendChild(inner);

    const time = document.createElement("div");
    time.className = "chat-time mt-1";
    time.textContent = "SANI";
    bubble.appendChild(time);

    wrap.appendChild(bubble);
    chatBody.appendChild(wrap);
    chatBody.scrollTop = chatBody.scrollHeight;

    typingBubble = wrap;
  }

  function hideTyping() {
    if (typingBubble && typingBubble.parentNode) {
      typingBubble.parentNode.removeChild(typingBubble);
    }
    typingBubble = null;
  }

  async function routeWithLLM(message) {
    const text = message.trim();
    if (!text) return;

    // tampilkan bubble user
    addBubble(text, "user");
    input.value = "";

    const lower = text.toLowerCase();

    // === MODE 2: user sedang mengisi template (WAITING_TEMPLATE) ===
    if (window._saniPendingAction && window._saniPendingAction.mode === "WAITING_TEMPLATE") {
      const action = window._saniPendingAction;
      window._saniPendingAction = null;

      // simpan isian template (opsional, bisa dipakai di ftp.html)
      try {
        sessionStorage.setItem("sani_last_template", text);
      } catch (e) {
        console.warn("Tidak bisa menyimpan template ke sessionStorage", e);
      }

      addBubble(
        "Terima kasih, datanya sudah saya catat. Sekarang saya arahkan ke halaman yang sesuai. " +
          "Nanti silakan salin isian yang tadi Anda kirim ke form antrean sebelum menekan tombol Simpan.",
        "bot"
      );

      if (action.url) {
        setTimeout(() => {
          window.location.href = action.url;
        }, 1600);
      }
      return;
    }

    // === MODE KONFIRMASI AWAL (YA / TIDAK) ===
    if (window._saniPendingAction) {
      const yesList = ["ya", "iya", "boleh", "ok", "oke", "lanjut"];
      const noList = ["tidak", "ga", "gak", "nggak", "jangan", "no"];

      const action = window._saniPendingAction;

      if (yesList.includes(lower)) {
        window._saniPendingAction = null;
        addBubble("Baik, saya jalankan bantuannya ya. 👌", "bot");
        if (typeof action.runYes === "function") action.runYes();
        return;
      } else if (noList.includes(lower)) {
        window._saniPendingAction = null;
        addBubble(
          "Baik, saya tidak akan mengisi otomatis. Saya arahkan dan jelaskan langkah umumnya saja ya. 🙏",
          "bot"
        );
        if (typeof action.runNo === "function") action.runNo();
        return;
      }
      // kalau bukan jawaban ya/tidak → lanjut diproses sebagai chat biasa
    }


    // tampilkan animasi bubble loading SANI
    showTyping();

    try {
      // === 1) CHAT: jawaban natural dari backend /api/chat ===
      const chatResp = await fetch(SANI_API_BASE + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          history: window._saniHistory,
          message: text,
        }),
      });

      let replyText =
        "Maaf, ada kendala saat menghubungi SANI di backend. Coba beberapa saat lagi ya.";

      if (chatResp.ok) {
        const chatData = await chatResp.json();
        replyText = chatData.reply || replyText;
      }

      hideTyping();
      addBubble(replyText, "bot");

      // update history untuk percakapan selanjutnya
      window._saniHistory.push({ role: "user", content: text });
      window._saniHistory.push({ role: "assistant", content: replyText });

      // === 2) NLU: cek apakah perlu agentic routing via /api/parse-intent ===
      const nluResp = await fetch(SANI_API_BASE + "/api/parse-intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          page: pageId,
        }),
      });

      if (!nluResp.ok) {
        return; // kalau NLU error, cukup chat biasa saja
      }

      const data = await nluResp.json();
      const intent = (data.intent || "OTHER").toUpperCase();
      const slots = data.slots || {};

      // kalau intent OTHER → tidak ada pesan agentic
      if (intent === "OTHER") {
        return;
      }

      handleRoutingWithConfirmation(pageId, intent, slots, addBubble);
    } catch (err) {
      console.error(err);
      hideTyping();
      addBubble(
        "Maaf, terjadi kendala koneksi ke server SANI di backend.",
        "bot"
      );
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const msg = input.value;
    routeWithLLM(msg);
  });
}

/**
 * Agentic routing dengan KONFIRMASI dulu.
 * intent dari backend:
 * REGISTER_FKTP_QUEUE, REGISTER_FRTL_QUEUE, REGISTER_BRANCH_QUEUE,
 * LOGIN, REGISTER_ACCOUNT, UPDATE_PROFILE, PAY_BILL, REACTIVATE_BPJS, OTHER
 */
function handleRoutingWithConfirmation(pageId, intent, slots, addBubble) {
  const nama = slots.nama || "Peserta JKN";

  function delayedGoto(url, ms = 1200) {
    setTimeout(() => {
      window.location.href = url;
    }, ms);
  }

  // ================== ANTRIAN FKTP ==================
  if (intent === "REGISTER_FKTP_QUEUE") {
    window._saniPendingAction = {
      type: "REGISTER_FKTP_QUEUE",
      pageId,
      slots,
      runYes() {
        // Tahap 2: kirim template dan tunggu isi user
        const needRedirect = pageId !== "FKTP";

        addBubble(
          `Oke, saya kirim template isi form antrean FKTP ya.<br><br>` +
            `Silakan balas di chat dengan format seperti ini:<br>` +
            `Nama Peserta: (contoh: Budi Santoso)<br>` +
            `Poli: (contoh: POLI UMUM / POLI ANAK / POLI GIGI & MULUT)<br>` +
            `Tanggal Kunjungan: (contoh: 21-11-2025 atau "besok pagi")<br>` +
            `Keluhan: (contoh: batuk dan demam sejak 3 hari)<br><br>` +
            `Setelah Anda kirim jawaban dengan format di atas, saya akan arahkan ke halaman antrean FKTP.`,
          "bot"
        );

        // sekarang kita masuk mode menunggu template dari user
        window._saniPendingAction = {
          mode: "WAITING_TEMPLATE",
          target: "FKTP",
          url: needRedirect ? "ftp.html" : null,
        };
      },
      runNo() {
        if (pageId !== "FKTP") {
          delayedGoto("ftp.html", 800);
        }
      },
    };


    addBubble(
      `Dari pertanyaan Anda, sepertinya Anda ingin <strong>daftar antrean di Faskes Tingkat Pertama (puskesmas/klinik)</strong> untuk <strong>${nama}</strong>.<br><br>` +
        `Saya bisa membantu <strong>mengarahkan ke halaman antrean FKTP</strong> dan menyiapkan <strong>template pengisian form</strong> sehingga Anda lebih mudah mengisi datanya.<br><br>` +
        `Apakah Anda ingin saya bantu seperti itu?<br>` +
        `Balas <strong>"ya"</strong> jika setuju, atau <strong>"tidak"</strong> jika ingin mengisi sendiri.`,
      "bot"
    );
    return;
  }

  // ================== ANTRIAN FKRTL (RS) ==================
  if (intent === "REGISTER_FRTL_QUEUE") {
    window._saniPendingAction = {
      type: "REGISTER_FRTL_QUEUE",
      pageId,
      slots,
      runYes() {
        const needRedirect = pageId !== "FRTL";

        addBubble(
          `Oke, saya kirim template antrean rumah sakit (FKRTL).<br><br>` +
            `Silakan balas di chat dengan format:<br>` +
            `Nama Peserta: ...<br>` +
            `Nama RS: ... (contoh: RSUD ODSK)<br>` +
            `Poli: ... (contoh: SARAF / JANTUNG / ANAK)<br>` +
            `Tanggal Kunjungan: ... (contoh: 25-11-2025)<br>` +
            `Dokter (jika sudah ditentukan): ...<br><br>` +
            `Setelah Anda kirim jawaban, saya akan arahkan ke halaman antrean FKRTL.`,
          "bot"
        );

        window._saniPendingAction = {
          mode: "WAITING_TEMPLATE",
          target: "FKRTL",
          url: needRedirect ? "ftl.html" : null,
        };
      },
      runNo() {
        if (pageId !== "FRTL") {
          delayedGoto("ftl.html", 800);
        }
      },
    };


    addBubble(
      `Saya memahami Anda ingin <strong>daftar antrean di Rumah Sakit (Faskes Rujukan Tingkat Lanjut)</strong> untuk <strong>${nama}</strong>.<br><br>` +
        `Saya bisa bantu mengarahkan ke halaman antrean RS dan menyiapkan contoh pengisian tanggal dan dokter.<br><br>` +
        `Apakah Anda ingin saya bantu isi secara otomatis dalam bentuk template?<br>` +
        `Balas <strong>"ya"</strong> atau <strong>"tidak"</strong>.`,
      "bot"
    );
    return;
  }

  // ================== UPDATE PROFILE (pindah faskes, ganti hp, dll.) ==================
  if (intent === "UPDATE_PROFILE") {
    const field = (slots.field || "").toLowerCase();

    window._saniPendingAction = {
      type: "UPDATE_PROFILE",
      pageId,
      slots,
      runYes() {
        if (pageId !== "PERUBAHAN_DATA") {
          delayedGoto("perubahandata.html", 800);
        }
        addBubble(
          `Nanti di halaman <strong>Perubahan Data Peserta</strong>, silakan pilih peserta yang datanya ingin diubah, lalu pilih baris data yang sesuai (misalnya Nomor Handphone, Alamat, atau Faskes Tingkat I).<br>` +
            `Ikuti instruksi di layar sampai perubahan tersimpan.`,
          "bot"
        );
      },
      runNo() {
        if (pageId !== "PERUBAHAN_DATA") {
          delayedGoto("perubahandata.html", 800);
        }
      },
    };

    let fieldLabel = "data peserta";
    if (field.includes("faskes")) fieldLabel = "Faskes Tingkat I";
    else if (field.includes("hp") || field.includes("phone"))
      fieldLabel = "Nomor Handphone";
    else if (field.includes("email")) fieldLabel = "Email";
    else if (field.includes("alamat")) fieldLabel = "Alamat";

    addBubble(
      `Anda ingin mengubah <strong>${fieldLabel}</strong> di data peserta JKN.<br><br>` +
        `Saya bisa mengarahkan ke halaman <em>Perubahan Data Peserta</em> dan menyiapkan penjelasan data apa saja yang perlu disiapkan.<br>` +
        `Mau saya bantu? Balas <strong>"ya"</strong> atau <strong>"tidak"</strong>.`,
      "bot"
    );
    return;
  }

  // ================== REGISTRASI AKUN ==================
  if (intent === "REGISTER_ACCOUNT") {
    window._saniPendingAction = {
      type: "REGISTER_ACCOUNT",
      pageId,
      slots,
      runYes() {
        if (pageId !== "REGISTER") {
          delayedGoto("register.html", 800);
        }
        addBubble(
          `Di halaman <strong>Registrasi (register.html)</strong>, siapkan data berikut:<br>` +
            `- NIK sesuai KTP (16 digit).<br>` +
            `- Nama lengkap seperti di KTP.<br>` +
            `- Nomor HP aktif.<br>` +
            `- Email (jika ada).<br>` +
            `- Password yang aman (minimal 6 karakter, ada huruf besar, huruf kecil, dan angka).`,
          "bot"
        );
      },
      runNo() {
        if (pageId !== "REGISTER") delayedGoto("register.html", 800);
      },
    };

    addBubble(
      `Anda ingin <strong>mendaftar akun Mobile JKN</strong>.<br><br>` +
        `Saya bisa mengarahkan ke halaman registrasi dan menjelaskan data apa saja yang perlu Anda siapkan sebelum mengisi form.<br>` +
        `Apakah Anda ingin saya bantu? Balas <strong>"ya"</strong> atau <strong>"tidak"</strong>.`,
      "bot"
    );
    return;
  }

  // ================== INTENT LAIN (tanpa pending action) ==================
  if (intent === "PAY_BILL") {
    addBubble(
      `Anda ingin <strong>melihat atau membayar iuran JKN</strong>.<br>` +
        `Di versi web prototype ini, silakan buka menu <em>Info Riwayat Pembayaran</em> untuk melihat tagihan yang sudah dibayar dan status pembayarannya.`,
      "bot"
    );
    return;
  }

  if (intent === "REACTIVATE_BPJS") {
    addBubble(
      `Anda ingin <strong>mengaktifkan kembali kepesertaan JKN</strong>.<br>` +
        `Biasanya langkahnya: pastikan semua iuran sudah dilunasi, lalu cek status di menu kepesertaan dalam beberapa hari kerja. Jika masih nonaktif, hubungi BPJS atau daftar antrean ke kantor cabang.`,
      "bot"
    );
    return;
  }

  if (intent === "LOGIN") {
    addBubble(
      `Untuk login Mobile JKN, gunakan NIK/Email/No Kepesertaan dan password yang sudah terdaftar. Di prototype web ini, kita mensimulasikan kondisi sudah login, jadi Anda langsung bisa mencoba fitur-fitur demonya.`,
      "bot"
    );
    return;
  }

  // intent OTHER atau yang tidak dikenali: biarkan jawaban chat biasa saja
}
