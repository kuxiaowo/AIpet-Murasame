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

# ================= 初始化 =================
app = FastAPI()

ollama_url = "http://localhost:11434/api/generate"

#加载模型
base_model_path = "./models/Qwen3-14B"   # 基础模型
lora_model_path = "./models/Murasame"    # LoRA 微调权重
def load_model_and_tokenizer():
    # 加载 tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    #配置量化参数
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,                # 启用 4bit 量化，降低显存占用
        bnb_4bit_use_double_quant=True,   # 启用二次量化，进一步节省显存
        bnb_4bit_quant_type="nf4",        # 使用 nf4 量化算法，比 fp4 更好
        bnb_4bit_compute_dtype=torch.float16  # 推理计算时用半精度 float16
    )
    # 加载基础模型
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,                       # 基础模型路径
        device_map="auto",                # 自动分配 GPU / CPU
        quantization_config=bnb_config,   # 使用上面配置的 4bit 量化
        trust_remote_code=True,           # 同样允许自定义逻辑
        offload_buffers=True  # 把临时 buffer 放到 CPU，减轻 GPU 压力
    )

    # 加载 LoRA adapter
    model = PeftModel.from_pretrained(model, lora_model_path)
    model.eval()

    return model, tokenizer

def now_time():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return now


#本地qwen3-lora端口
class qwen3_lora_request(BaseModel):
    history: List[Dict[str, str]]
@app.post("/qwen3-lora")
async def qwen3_lora(req: qwen3_lora_request):
    history = req.history
    text = tokenizer.apply_chat_template( #apply_chat_template 是 HuggingFace 新 API，用来把 history（对话历史）转成 模型能理解的输入格式
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

    reply = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()#去掉输入部分，只保留生成的新 tokens
    return reply


#本地ollama qwen3端口
class ollama_request(BaseModel):
    prompt: dict
    headers: dict
@app.post("/ollama")
async def ollama_qwen3(req: ollama_request):
    resp = requests.post(ollama_url, headers=req.headers, json=req.prompt)
    return resp.json()


#本地语音合成端口

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
            if response.status == 200:
                content = await response.read()
                return StreamingResponse(io.BytesIO(content), media_type="audio/wav")
            else:
                return {"error": f"TTS API返回错误: {response.status}"}

#deepseek云端API接口
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
                return {"error": f"API返回错误: {response.status}"}

# ================= 启动 =================
if __name__ == "__main__":
    model_type = get_config("./config.json")['model_type']
    if model_type == "local":
        model, tokenizer = load_model_and_tokenizer()
    uvicorn.run(app, host="0.0.0.0", port=28565)
