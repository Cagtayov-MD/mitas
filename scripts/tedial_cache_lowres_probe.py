import urllib.request
import urllib.error
import ssl
import os
import sys
import re


SUMMARY_FILE = "faz0_har_ozet.txt"
OUTPUT_FILE = "faz0_cache_lowres_sonuc.txt"
URL_RE = re.compile(r"https://evo\.int\.trt\.net\.tr/cache_lowres/[^\s<>'\"]+", re.I)


def find_url():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    try:
        with open(SUMMARY_FILE, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    match = URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip("=)")


def selected_headers(headers):
    wanted = [
        "Content-Range",
        "Accept-Ranges",
        "Content-Length",
        "Content-Type",
        "Cache-control",
        "Cache-Control",
        "Access-Control-Allow-Origin",
        "Server",
    ]
    result = []
    for name in wanted:
        value = headers.get(name)
        if value is not None:
            result.append((name, value))
    return result


def percent_encode_non_ascii(url):
    parts = []
    for char in url:
        codepoint = ord(char)
        if codepoint < 128:
            parts.append(char)
        else:
            for byte in char.encode("utf-8"):
                parts.append("%" + format(byte, "02X"))
    return "".join(parts)


def run_get(url, range_header=None, cookie=None):
    ctx = ssl._create_unverified_context()
    request = urllib.request.Request(percent_encode_non_ascii(url), method="GET")
    request.add_header("User-Agent", "Tedial-Faz0-CacheLowres-Probe/1.0")
    if range_header:
        request.add_header("Range", range_header)
    if cookie:
        request.add_header("Cookie", cookie)
    try:
        response = urllib.request.urlopen(request, context=ctx, timeout=20)
        try:
            return {
                "status": response.getcode(),
                "headers": selected_headers(response.headers),
                "error": None,
            }
        finally:
            response.close()
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "headers": selected_headers(exc.headers),
            "error": str(exc.reason),
        }
    except urllib.error.URLError as exc:
        return {
            "status": "ERROR",
            "headers": [],
            "error": str(exc.reason),
        }


def render_result(name, description, result):
    lines = []
    lines.append("## " + name)
    lines.append(description)
    lines.append("status: " + str(result.get("status")))
    if result.get("error"):
        lines.append("error: " + str(result.get("error")))
    if result.get("headers"):
        lines.append("headers:")
        for key, value in result.get("headers"):
            lines.append("  " + key + ": " + value)
    else:
        lines.append("headers: (none)")
    lines.append("")
    return lines


def status_value(result):
    status = result.get("status")
    if isinstance(status, int):
        return status
    try:
        return int(status)
    except Exception:
        return None


def header_value(result, name):
    for key, value in result.get("headers", []):
        if key.lower() == name.lower():
            return value
    return None


def interpret(no_cookie_full, no_cookie_range, cookie_range):
    lines = ["## Yorum"]
    statuses = [status_value(no_cookie_full), status_value(no_cookie_range)]
    if any(status in (401, 403) for status in statuses):
        lines.append("Cookie'siz erişimde 401/403 görüldü: cache_lowres host'u cookie/auth istiyor.")
    elif any(status in (200, 206) for status in statuses):
        lines.append("Cookie'siz erişimde 200/206 görüldü: cache_lowres URL'i cookie olmadan erişilebilir görünüyor.")
    else:
        lines.append("Cookie'siz erişim net doğrulanamadı; status değerlerini kontrol et.")

    if status_value(no_cookie_range) == 206 and header_value(no_cookie_range, "Content-Range"):
        lines.append("Range testi 206 + Content-Range döndürdü: byte-range destekli.")
    else:
        lines.append("Range desteği net değil: 206 + Content-Range birlikte görülmedi.")

    if cookie_range is None:
        lines.append("Cookie'li test COOKIE ortam değişkeni olmadığı için atlandı.")
    elif status_value(cookie_range) in (200, 206):
        lines.append("Cookie'li test erişilebilir döndü.")
    elif status_value(cookie_range) in (401, 403):
        lines.append("Cookie'li test 401/403 döndü; verilen cookie geçersiz/eksik olabilir.")
    else:
        lines.append("Cookie'li test net yorumlanamadı.")
    lines.append("")
    return lines


def main():
    url = find_url()
    if not url:
        message = "ERROR: cache_lowres URL bulunamadı. Argüman ver veya faz0_har_ozet.txt üret."
        print(message)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
            handle.write(message + "\n")
        return 1

    cookie = os.environ.get("COOKIE", "")
    lines = []
    lines.append("# cache_lowres canlı test sonucu")
    lines.append("")
    lines.append("URL: " + url)
    lines.append("")

    no_cookie_full = run_get(url)
    no_cookie_range = run_get(url, range_header="bytes=0-1023")
    cookie_range = None
    if cookie:
        cookie_range = run_get(url, range_header="bytes=0-1023", cookie=cookie)

    lines.extend(render_result("Test 1", "GET, cookie YOK, Range YOK", no_cookie_full))
    lines.extend(render_result("Test 2", "GET, cookie YOK, Range: bytes=0-1023", no_cookie_range))
    if cookie:
        lines.extend(render_result("Test 3", "GET, Cookie: <MASKED>, Range: bytes=0-1023", cookie_range))
    else:
        lines.append("## Test 3")
        lines.append("GET, Cookie + Range: atlandı")
        lines.append("status: ATLANDI")
        lines.append("reason: COOKIE ortam değişkeni boş")
        lines.append("")
    lines.extend(interpret(no_cookie_full, no_cookie_range, cookie_range))

    result = "\n".join(lines)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
        handle.write(result)
        handle.write("\n")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
