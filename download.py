import json
import os
import re
import shutil

from modelscope.hub.snapshot_download import snapshot_download
from rich.console import Console

from tool.config import get_config

model_type = get_config("./config.json")["model_type"]
console = Console()

MODELS_DIR = "./models"
GS_ROOT = os.path.join(
    os.getcwd(), "GPT-SoVITS"
)
GS_GPT_DIR = os.path.join(GS_ROOT, "GPT_weights")
GS_SOVITS_DIR = os.path.join(GS_ROOT, "SoVITS_weights")
GS_TTS_YAML = os.path.join(
    GS_ROOT, "GPT_SoVITS", "configs", "tts_infer.yaml"
)

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(GS_GPT_DIR, exist_ok=True)
os.makedirs(GS_SOVITS_DIR, exist_ok=True)

console.log("Downloading SoVITS assets...")
local_sovits_dir = os.path.join(MODELS_DIR, "Murasame_SoVITS")
snapshot_download(
    "LemonQu/Murasame_SoVITS", local_dir=local_sovits_dir
)

# Locate the two model files inside the snapshot
gpt_ckpt = None
sovits_pth = None
for name in os.listdir(local_sovits_dir):
    lower = name.lower()
    if (lower.endswith(".ckpt") or lower.endswith(".pth")) and "gpt" in lower:
        gpt_ckpt = os.path.join(local_sovits_dir, name)
    if lower.endswith(".pth") and ("sovits" in lower or re.search(r"s2g", lower)):
        sovits_pth = os.path.join(local_sovits_dir, name)

if not gpt_ckpt or not sovits_pth:
    raise FileNotFoundError(
        "Expected GPT (.ckpt/.pth) and SoVITS (.pth) weights in Murasame_SoVITS"
    )

# Copy into GPT-SoVITS weight folders
gpt_target = os.path.join(GS_GPT_DIR, os.path.basename(gpt_ckpt))
sovits_target = os.path.join(GS_SOVITS_DIR, os.path.basename(sovits_pth))
shutil.copy2(gpt_ckpt, gpt_target)
shutil.copy2(sovits_pth, sovits_target)

console.log(f"Placed GPT weights: {gpt_target}")
console.log(f"Placed SoVITS weights: {sovits_target}")

# Update tts_infer.yaml -> custom.* paths to the new weights
def update_tts_yaml(yaml_path: str, gpt_rel: str, sovits_rel: str) -> None:
    if not os.path.exists(yaml_path):
        console.log(f"[yellow]Config not found: {yaml_path}[/yellow]")
        return

    with open(yaml_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    in_custom = False
    for line in lines:
        if re.match(r"^custom:\s*$", line):
            in_custom = True
            new_lines.append(line)
            continue
        if in_custom and re.match(r"^[^\s]", line):
            in_custom = False

        if in_custom and re.search(r"t2s_weights_path:\s*", line):
            indent = re.match(r"^(\s*)", line).group(1)
            new_lines.append(f"{indent}t2s_weights_path: {gpt_rel}\n")
            continue
        if in_custom and re.search(r"vits_weights_path:\s*", line):
            indent = re.match(r"^(\s*)", line).group(1)
            new_lines.append(f"{indent}vits_weights_path: {sovits_rel}\n")
            continue

        new_lines.append(line)

    with open(yaml_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


# Paths in YAML should be relative to repo root, matching existing style
gpt_rel_path = f"GPT_weights/{os.path.basename(gpt_target)}"
sovits_rel_path = f"SoVITS_weights/{os.path.basename(sovits_target)}"
update_tts_yaml(GS_TTS_YAML, gpt_rel_path, sovits_rel_path)

console.log("Updated tts_infer.yaml custom model paths.")


