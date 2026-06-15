from __future__ import annotations
import json, urllib.request

def mask_key(key: str | None) -> str | None:
    if not key:
        return None
    return "sk-***" + key[-4:] if len(key) >= 8 else "***"

def chat_completion(base_url: str, api_key: str, model: str, messages: list[dict], timeout: int = 60) -> dict:
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "messages": messages, "temperature": 0.2}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
