from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_ID = "Qwen/Qwen2-1.5B-Instruct"

print("Loading tokenizer...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

print("Loading model...")
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    device_map="auto",
    torch_dtype="auto"
)

# Contoh chat sederhana pakai chat_template Qwen
messages = [
    {"role": "system", "content": "Kamu adalah asisten bernama SANI, Sahabat JKN Indonesia."},
    {"role": "user", "content": "Apa itu BPJS Kesehatan? Jelaskan singkat pakai bahasa sederhana."}
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True
)

inputs = tokenizer([text], return_tensors="pt").to(model.device)
outputs = model.generate(
    **inputs,
    max_new_tokens=80,
    do_sample=True,
    top_p=0.9,
    temperature=0.7
)

generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
print("\n=== OUTPUT MODEL ===")
print(tokenizer.decode(generated_ids, skip_special_tokens=True))
