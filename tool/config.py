import json
def get_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)