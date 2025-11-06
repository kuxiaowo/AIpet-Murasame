import io
import os
from datetime import datetime
from typing import List, Dict, Optional

import aiohttp
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from tool.config import get_config


# ============== App ==============
app = FastAPI()


# Upstream service endpoints
OLLAMA_UPSTREAM_URL = os.getenv("OLLAMA_UPSTREAM_URL", "http://localhost:11434/api/generate")


# ============== Local Model (optional) ==============
base_model_path = "./models/Qwen3-14B"
lora_model_path = "./models/Murasame"
model: Optional[AutoModelForCausalLM] = None
tokenizer: Optional[AutoTokenizer] = None


def load_model_and_tokenizer():
    import torch
    from peft import PeftModel
    from pydantic import BaseModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    tok = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    mdl = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        device_map="auto",
        quantization_config=bnb_config,
        trust_remote_code=True,
        offload_buffers=True,
    )
    mdl = PeftModel.from_pretrained(mdl, lora_model_path)
    mdl.eval()
    return mdl, tok


def now_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============== Endpoints ==============
# qwen3-lora (local inference)
class Qwen3LoraRequest(BaseModel):
    history: List[Dict[str, str]]


@app.post("/qwen3-lora")
async def qwen3_lora(req: Qwen3LoraRequest):
    global model, tokenizer
    history = req.history

    # Only available in local mode
    model_type = get_config("./config.json").get("model_type", "deepseek")
    if model_type != "local":
        return {"error": "qwen3-lora 不可用：当前为云端模式"}

    if model is None or tokenizer is None:
        model, tokenizer = load_model_and_tokenizer()

    text = tokenizer.apply_chat_template(
        history,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=True,
            temperature=0.9,
            top_p=0.95,
            top_k=20,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only generated tokens
    gen_ids = outputs[0][inputs["input_ids"].shape[-1]:]
    reply = tokenizer.decode(gen_ids, skip_special_tokens=True).strip()
    return reply


# ollama proxy (async)
class OllamaRequest(BaseModel):
    prompt: dict
    headers: dict


@app.post("/ollama")
async def ollama_qwen3(req: OllamaRequest):
    try:
        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(OLLAMA_UPSTREAM_URL, headers=req.headers, json=req.prompt) as resp:
                data = await resp.json()
                if resp.status != 200:
                    # upstream error; return body to caller
                    return data
                return data
    except Exception as e:
        return {"error": f"upstream request failed: {e}"}


# gpt-sovits tts proxy
class GPTSoVITSTTSRequest(BaseModel):
    params: dict


@app.post("/tts")
async def gpt_sovits_tts(req: GPTSoVITSTTSRequest):
    url = "http://localhost:9880/tts"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=req.params,
                timeout=aiohttp.ClientTimeout(total=300),
            ) as response:
                if response.status == 200:
                    content = await response.read()
                    return StreamingResponse(io.BytesIO(content), media_type="audio/wav")
                else:
                    text = await response.text()
                    return {"error": f"TTS API返回错误: {response.status}"}
    except Exception as e:
        return {"error": f"TTS upstream 请求失败: {e}"}


# deepseek cloud API passthrough
class DeepseekAPIRequest(BaseModel):
    payload: dict
    headers: dict


@app.post("/deepseekAPI")
async def deepseekAPI(req: DeepseekAPIRequest):
    url = "https://api.deepseek.com/chat/completions"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=req.headers,
            json=req.payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                return {"error": f"API返回错误: {response.status}"}


# ============== Entrypoint ==============
if __name__ == "__main__":
    cfg = get_config("./config.json")
    if cfg.get("model_type") == "local":
        # Optional: preload on startup
        model, tokenizer = load_model_and_tokenizer()
    uvicorn.run(app, host="0.0.0.0", port=28565)
