"""Phase 0 discovery tool: replay a DevTools 'Copy as cURL' request and
summarise its shape — without leaking secrets.

The Tedial vendor exposes no documented API, so before we trust any proxy
endpoint we must confirm the real request/response contract for five calls:
login, doNewSearch, refreshPlaybackToken, file.mpd, and a cache_lowres media
range request. Workflow per call:

  1. In Chrome DevTools (Network), right-click the request ->
     Copy -> Copy as cURL (bash). Paste into a file, e.g. search.curl
  2. python scripts/tedial_probe.py search.curl --name doNewSearch
  3. Read the printed summary; share it back (it masks cookie/token values).

This only replays a request you captured yourself against your own
authorised Tedial session. It is a recon aid, not an attack tool.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    import httpx
except ImportError:  # pragma: no cover - environment guard
    sys.exit("httpx gerekli: ilgili venv'i aktive et veya `pip install httpx`")

SENSITIVE_HEADERS = {"cookie", "authorization", "x-csrf-token", "set-cookie"}
SENSITIVE_COOKIES = {"JSESSIONID", "JSESSIONIDVERSION", "JREPLICA"}
MAX_BODY_PREVIEW = 1200


def parse_curl(text: str) -> dict[str, Any]:
    """Parse a bash 'Copy as cURL' blob into method/url/headers/cookies/body."""
    cleaned = text.strip().replace("\\\n", " ").replace("^\n", " ")
    tokens = shlex.split(cleaned)
    if not tokens or tokens[0] != "curl":
        raise ValueError("Girdi 'curl' ile baslamiyor — DevTools 'Copy as cURL (bash)' kullan")

    url = ""
    method = ""
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    body: str | None = None

    i = 1
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-X", "--request"):
            method = tokens[i + 1]
            i += 2
        elif tok in ("-H", "--header"):
            raw = tokens[i + 1]
            if ":" in raw:
                k, _, v = raw.partition(":")
                headers[k.strip().lower()] = v.strip()
            i += 2
        elif tok in ("-b", "--cookie"):
            for pair in tokens[i + 1].split(";"):
                if "=" in pair:
                    k, _, v = pair.strip().partition("=")
                    cookies[k.strip()] = v.strip()
            i += 2
        elif tok in ("-e", "--referer"):
            headers["referer"] = tokens[i + 1]
            i += 2
        elif tok in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode"):
            body = tokens[i + 1] if body is None else f"{body}&{tokens[i + 1]}"
            i += 2
        elif tok in ("--compressed", "-s", "-i", "-k", "--insecure", "-L", "--location"):
            i += 1
        elif tok.startswith("http://") or tok.startswith("https://"):
            url = tok
            i += 1
        else:
            i += 1

    # Cookies may also arrive via a 'cookie:' header.
    if "cookie" in headers and not cookies:
        for pair in headers["cookie"].split(";"):
            if "=" in pair:
                k, _, v = pair.strip().partition("=")
                cookies[k.strip()] = v.strip()

    if not url:
        raise ValueError("cURL icinde URL bulunamadi")
    if not method:
        method = "POST" if body is not None else "GET"
    return {"method": method, "url": url, "headers": headers, "cookies": cookies, "body": body}


def _mask(name: str, value: str) -> str:
    if name in SENSITIVE_COOKIES or name.lower() in SENSITIVE_HEADERS:
        return f"<{len(value)} chars hidden>"
    return value if len(value) <= 80 else value[:77] + "..."


def summarise_json(data: Any, depth: int = 0, max_depth: int = 3) -> Any:
    """Recursively reduce a JSON value to a type/shape skeleton."""
    if depth >= max_depth:
        return f"<{type(data).__name__}>"
    if isinstance(data, dict):
        return {k: summarise_json(v, depth + 1, max_depth) for k, v in list(data.items())[:25]}
    if isinstance(data, list):
        head = summarise_json(data[0], depth + 1, max_depth) if data else "<empty>"
        return f"list[{len(data)}] of {head!r}"
    if isinstance(data, str):
        return f"str(len={len(data)})" if len(data) > 40 else f"str:{data!r}"
    return f"{type(data).__name__}:{data!r}" if not isinstance(data, (dict, list)) else type(data).__name__


def report(name: str, parsed: dict[str, Any], resp: httpx.Response, save_body: Path | None) -> None:
    u = urlsplit(parsed["url"])
    print(f"\n{'=' * 70}\n  PROBE: {name}\n{'=' * 70}")
    print(f"  Request : {parsed['method']} {u.scheme}://{u.netloc}{u.path}")
    if u.query:
        print(f"  Query   : {u.query[:120]}")
    print(f"  Cookies : {', '.join(sorted(parsed['cookies'])) or '(none)'}")
    ctype_req = parsed["headers"].get("content-type", "(none)")
    print(f"  ReqType : {ctype_req}")
    if parsed["body"] is not None:
        b = parsed["body"]
        print(f"  ReqBody : {len(b)} chars | {b[:200]}{'...' if len(b) > 200 else ''}")

    print(f"\n  Status  : {resp.status_code} {resp.reason_phrase}")
    print(f"  RespType: {resp.headers.get('content-type', '(none)')}")
    print(f"  Server  : {resp.headers.get('server', '(none)')}")
    print(f"  Size    : {len(resp.content)} bytes")

    set_cookies = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else []
    if set_cookies:
        print("  Set-Cookie (rotation watch):")
        for sc in set_cookies:
            cname = sc.split("=", 1)[0]
            flags = [p.strip() for p in sc.split(";")[1:]]
            print(f"    - {cname}  [{', '.join(flags)}]")

    ctype = resp.headers.get("content-type", "")
    if "json" in ctype:
        try:
            parsed_json = resp.json()
            print("\n  JSON SHAPE (Faz 0 sema cikarimi):")
            print(json.dumps(summarise_json(parsed_json), ensure_ascii=False, indent=2)[:MAX_BODY_PREVIEW])
        except Exception as exc:  # noqa: BLE001
            print(f"  JSON parse hatasi: {exc}")
    elif "xml" in ctype or "dash" in ctype or resp.text.lstrip().startswith("<?xml"):
        text = resp.text
        print("\n  XML/MPD ozeti:")
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("<BaseURL") or s.startswith("<Title") or s.startswith("<Source") or "duration=" in s:
                print(f"    {s[:160]}")
    else:
        print(f"\n  Body preview:\n    {resp.text[:MAX_BODY_PREVIEW]}")

    if save_body:
        save_body.write_bytes(resp.content)
        print(f"\n  Full body saved -> {save_body}")
    print()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tedial Faz 0 cURL-replay kesif araci")
    ap.add_argument("curl_file", type=Path, help="DevTools 'Copy as cURL (bash)' ciktisini iceren dosya")
    ap.add_argument("--name", default="request", help="Rapor etiketi (orn: doNewSearch, login, file.mpd)")
    ap.add_argument("--save-body", type=Path, default=None, help="Tam yaniti bu dosyaya kaydet")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--insecure", action="store_true", help="TLS dogrulamasini kapat (ic ag sertifikasi icin)")
    args = ap.parse_args(argv)

    if not args.curl_file.exists():
        print(f"Dosya yok: {args.curl_file}", file=sys.stderr)
        return 2

    parsed = parse_curl(args.curl_file.read_text(encoding="utf-8"))
    with httpx.Client(timeout=args.timeout, verify=not args.insecure, follow_redirects=False) as client:
        resp = client.request(
            parsed["method"],
            parsed["url"],
            headers={k: v for k, v in parsed["headers"].items() if k != "content-length"},
            cookies=parsed["cookies"],
            content=parsed["body"].encode() if parsed["body"] is not None else None,
        )
    report(args.name, parsed, resp, args.save_body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
