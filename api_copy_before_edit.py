import io
from datetime import datetime
from typing import List, Dict

import aiohttp
import requests
import torch
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from peft import PeftModel
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from tool.config import get_config

# ================= 鍒濆鍖?=================
app = FastAPI()

ollama_url = "http://localhost:11434/api/generate"

#鍔犺浇妯″瀷
base_model_path = "./models/Qwen3-14B"   # 鍩虹妯″瀷
lora_model_path = "./models/Murasame"    # LoRA 寰皟鏉冮噸
def load_model_and_tokenizer():
    # 鍔犺浇 tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    #閰嶇疆閲忓寲鍙傛暟
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,                # 鍚敤 4bit 閲忓寲锛岄檷浣庢樉瀛樺崰鐢?        bnb_4bit_use_double_quant=True,   # 鍚敤浜屾閲忓寲锛岃繘涓€姝ヨ妭鐪佹樉瀛?        bnb_4bit_quant_type="nf4",        # 浣跨敤 nf4 閲忓寲绠楁硶锛屾瘮 fp4 鏇村ソ
        bnb_4bit_compute_dtype=torch.float16  # 鎺ㄧ悊璁＄畻鏃剁敤鍗婄簿搴?float16
    )
    # 鍔犺浇鍩虹妯″瀷
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,                       # 鍩虹妯″瀷璺緞
        device_map="auto",                # 鑷姩鍒嗛厤 GPU / CPU
        quantization_config=bnb_config,   # 浣跨敤涓婇潰閰嶇疆鐨?4bit 閲忓寲
        trust_remote_code=True,           # 鍚屾牱鍏佽鑷畾涔夐€昏緫
        offload_buffers=True  # 鎶婁复鏃?buffer 鏀惧埌 CPU锛屽噺杞?GPU 鍘嬪姏
    )

    # 鍔犺浇 LoRA adapter
    model = PeftModel.from_pretrained(model, lora_model_path)
    model.eval()

    return model, tokenizer

def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now


#鏈湴qwen3-lora绔彛
class qwen3_lora_request(BaseModel):
    history: List[Dict[str, str]]
@app.post("/qwen3-lora")
async def qwen3_lora(req: qwen3_lora_request):
    history = req.history
    text = tokenizer.apply_chat_template( #apply_chat_template 鏄?HuggingFace 鏂?API锛岀敤鏉ユ妸 history锛堝璇濆巻鍙诧級杞垚 妯″瀷鑳界悊瑙ｇ殑杈撳叆鏍煎紡
        history,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=2048,
            do_sample=True,
            temperature=0.9,
            top_p=0.95,
            top_k=20,
            pad_token_id=tokenizer.eos_token_id
        )

    reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()#鍘绘帀杈撳叆閮ㄥ垎锛屽彧淇濈暀鐢熸垚鐨勬柊 tokens
    return reply


#鏈湴ollama qwen3绔彛
class ollama_request(BaseModel):
    prompt: dict
    headers: dict
@app.post("/ollama")
async def ollama_qwen3(req: ollama_request):
    resp = requests.post(ollama_url, headers=req.headers, json=req.prompt)
    return resp.json()


#鏈湴璇煶鍚堟垚绔彛

class gpt_sovits_tts_request(BaseModel):
    params: dict

@app.post("/tts")
async def gpt_sovits_tts(req: gpt_sovits_tts_request):
    url = "http://localhost:9880/tts"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=req.params,
            timeout=aiohttp.ClientTimeout(total=300)
        ) as response:
            #if response.status == 200:
                content = await response.read()
                return StreamingResponse(io.BytesIO(content), media_type="audio/wav")
            #else:
                return {"error": f"TTS API杩斿洖閿欒: {response.status}"}

#deepseek浜戠API鎺ュ彛
class deepseekAPI_request(BaseModel):
    payload: dict
    headers: dict
@app.post("/deepseekAPI")
async def deepseekAPI(req: deepseekAPI_request):
    url = "https://api.deepseek.com/chat/completions"

    async with aiohttp.ClientSession() as session:
        async with session.post(
                url,
                headers=req.headers,
                json=req.payload,
                timeout=aiohttp.ClientTimeout(total=180)
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"API杩斿洖閿欒: {response.status}"}

# ================= 鍚姩 =================
if __name__ == "__main__":
    model_type = get_config("./config.json")['model_type']
    if model_type == "local":
        model, tokenizer = load_model_and_tokenizer()
    uvicorn.run(app, host="0.0.0.0", port=28565)
