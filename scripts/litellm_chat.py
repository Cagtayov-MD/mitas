#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""litellm_chat.py — LiteLLM proxy üzerinden terminal sohbet istemcisi.

Kullanım:
    python3 litellm_chat.py <model_adı> [--api-key KEY] [--url URL]

Örnek:
    python3 litellm_chat.py qwen-max
    python3 litellm_chat.py nemotron
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

DEFAULT_URL = "http://127.0.0.1:4000/v1"
DEFAULT_KEY = os.environ.get("LITELLM_MASTER_KEY", "948473*Mitas")

def chat(model: str, api_base: str, api_key: str) -> None:
    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║  MITAS LiteLLM Chat                              ║")
    print(f"║  Model : {model:<40s} ║")
    print(f"║  Proxy : {api_base:<40s} ║")
    print(f"╚══════════════════════════════════════════════════╝")
    print(f"Çıkış: 'exit', 'quit' veya Ctrl+C\n")

    messages = []
    while True:
        try:
            user_input = input("\033[1;36msen > \033[0m").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGörüşmek üzere!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q", "çık", "çıkış"):
            print("Görüşmek üzere!")
            break

        messages.append({"role": "user", "content": user_input})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "stream": False,
            "temperature": 0.7,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{api_base}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assistant_msg = data["choices"][0]["message"]["content"]
            messages.append({"role": "assistant", "content": assistant_msg})

            usage = data.get("usage", {})
            usage_str = ""
            if usage:
                usage_str = f"  [{usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out]"

            print(f"\033[1;32m{model}\033[0m > {assistant_msg}{usage_str}\n")

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            print(f"\033[1;31mHATA ({e.code}):\033[0m {body}\n")
        except Exception as e:
            print(f"\033[1;31mHATA:\033[0m {e}\n")

def main():
    parser = argparse.ArgumentParser(description="Mitas LiteLLM terminal sohbeti")
    parser.add_argument("model", help="LiteLLM'deki model adı (örn: qwen-max, nemotron)")
    parser.add_argument("--url", default=DEFAULT_URL, help="LiteLLM proxy URL")
    parser.add_argument("--api-key", default=DEFAULT_KEY, dest="api_key", help="Master key")
    args = parser.parse_args()
    chat(args.model, args.url.rstrip("/"), args.api_key)

if __name__ == "__main__":
    main()
