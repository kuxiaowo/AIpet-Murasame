from __future__ import annotations

import getpass

import paramiko


password = getpass.getpass("AutoDL password: ")
client = paramiko.SSHClient()
client.load_system_host_keys()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(
    "connect.weste.seetacloud.com",
    port=32475,
    username="root",
    password=password,
    timeout=15,
    banner_timeout=15,
    auth_timeout=15,
    allow_agent=False,
    look_for_keys=False,
)
try:
    command = (
        "ps -eo pid,etime,pcpu,pmem,stat,cmd "
        "| grep -E '[a]pt-get|[p]ip|[i]nstall.sh|[p]ython' "
        "| tail -n 35; "
        "echo LARGE_TEMP_FILES; "
        "find /tmp -type f -size +50M -printf '%s %p\\n' "
        "2>/dev/null | sort -nr | head -n 20; "
        "du -sh /root/miniconda3/envs/GPTSoVits 2>/dev/null || true; "
        "df -h /root"
    )
    _, stdout, stderr = client.exec_command(command, timeout=30)
    print(stdout.read().decode("utf-8", errors="replace"), end="")
    print(stderr.read().decode("utf-8", errors="replace"), end="")
finally:
    client.close()
