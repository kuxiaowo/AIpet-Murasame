from __future__ import annotations

import getpass

import paramiko


HOST = "connect.weste.seetacloud.com"
PORT = 32475
USERNAME = "root"


def run(
    client: paramiko.SSHClient,
    title: str,
    command: str,
    *,
    timeout: int = 60,
) -> None:
    print(f"\n===== {title} =====", flush=True)
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    print(stdout.read().decode("utf-8", errors="replace"), end="")
    error = stderr.read().decode("utf-8", errors="replace")
    if error:
        print(error, end="")
    print(f"[exit={stdout.channel.recv_exit_status()}]", flush=True)


password = getpass.getpass("AutoDL password: ")
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    HOST,
    port=PORT,
    username=USERNAME,
    password=password,
    timeout=15,
    banner_timeout=15,
    auth_timeout=15,
    allow_agent=False,
    look_for_keys=False,
)
try:
    run(
        client,
        "install Linux CU128 dependencies",
        "set -e; "
        "export DEBIAN_FRONTEND=noninteractive; "
        "apt-get update -qq; "
        "apt-get install -y ffmpeg cmake make unzip build-essential; "
        "apt-get clean; "
        "source /root/miniconda3/etc/profile.d/conda.sh; "
        "conda activate GPTSoVits; "
        "cd /root/GPT-SoVITS; "
        "python -m pip install --no-cache-dir "
        "torch torchaudio torchcodec "
        "--index-url https://download.pytorch.org/whl/cu128; "
        "python -m pip install --no-cache-dir "
        "-r extra-req.txt --no-deps; "
        "python -m pip install --no-cache-dir -r requirements.txt; "
        "python -c \"import torch; "
        "print('torch=', torch.__version__); "
        "print('torch_cuda=', torch.version.cuda); "
        "print('cuda_available=', torch.cuda.is_available())\"; "
        "df -h /root",
        timeout=7200,
    )
finally:
    client.close()
