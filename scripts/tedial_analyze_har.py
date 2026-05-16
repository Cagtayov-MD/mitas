import json
import sys
import re
import html
import collections
import urllib.parse


INPUT_FILE = "tedial_capture.har"
OUTPUT_FILE = "faz0_har_ozet.txt"

INTERESTING_URL_PARTS = [
    "login",
    "j_security_check",
    "doNewSearch",
    "refreshPlaybackToken",
    "loadDefaultSearch",
    "loadCategoriesTree",
    "checkEnabledSworkActions",
    ".mpd",
    "cache_lowres",
    "KeyframeService",
]

SECRET_KEY_RE = re.compile(r"pass|pwd|password|token|secret|credential", re.I)
SECRET_URL_KEY_RE = re.compile(r"pass|pwd|password|token|secret|credential|ticket|authorization", re.I)


def shorten(value, limit=80):
    text = "" if value is None else str(value)
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def is_secret_key(key):
    return bool(SECRET_KEY_RE.search(str(key)))


def mask_url(url):
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return mask_text(url)
    if not parts.query:
        return url
    masked_pairs = []
    changed = False
    for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True):
        if SECRET_URL_KEY_RE.search(key):
            masked_pairs.append((key, "<MASKED>"))
            changed = True
        else:
            masked_pairs.append((key, value))
    if not changed:
        return url
    query = urllib.parse.urlencode(masked_pairs, doseq=True)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def mask_text(text):
    if text is None:
        return ""
    masked = str(text)
    masked = re.sub(r"(?i)(JSESSIONID=)[^;\s&<>'\"]+", r"\1<MASKED>", masked)
    masked = re.sub(r"(?i)(Authorization\s*[:=]\s*(?:Bearer\s+)?)['\"]?[^;\s&<>'\"]+", r"\1<MASKED>", masked)
    masked = re.sub(
        r"(?i)(['\"]?[A-Za-z0-9_.-]*(?:pass|pwd|password|token|secret|credential)[A-Za-z0-9_.-]*['\"]?\s*[:=]\s*)['\"]?[^&\s<>'\",}]+['\"]?",
        r"\1<MASKED>",
        masked,
    )
    return masked


def content_type_from_headers(headers):
    for header in headers or []:
        if header.get("name", "").lower() == "content-type":
            return header.get("value", "")
    return ""


def request_headers_summary(headers):
    items = []
    for header in headers or []:
        name = header.get("name", "")
        if name.lower() in ("cookie", "authorization"):
            items.append(name + ": <MASKED>")
        else:
            items.append(name)
    return ", ".join(items) if items else "(none)"


def response_headers_summary(headers):
    names = []
    cookies = []
    for header in headers or []:
        name = header.get("name", "")
        value = header.get("value", "")
        names.append(name)
        if name.lower() == "set-cookie":
            cookie_name = value.split("=", 1)[0].strip() if value else "(unknown)"
            cookies.append(cookie_name + "=<MASKED>")
    lines = ["Response headers: " + (", ".join(names) if names else "(none)")]
    if cookies:
        lines.append("Set-Cookie names: " + ", ".join(cookies))
    else:
        lines.append("Set-Cookie names: (none)")
    return lines


def json_scalar(value, secret):
    if secret:
        return "<MASKED>"
    if isinstance(value, str):
        return '"' + shorten(mask_text(value)) + '"'
    if value is None:
        return "null"
    return shorten(value)


def render_json_tree(value, lines, label="root", indent="", depth=0, secret=False):
    if depth > 8:
        lines.append(indent + label + ": ...")
        return
    if isinstance(value, dict):
        lines.append(indent + label + ": object{" + str(len(value)) + "}")
        for index, key in enumerate(value):
            if index >= 80:
                lines.append(indent + "  ... (" + str(len(value) - index) + " more keys)")
                break
            render_json_tree(value[key], lines, str(key), indent + "  ", depth + 1, secret or is_secret_key(key))
        return
    if isinstance(value, list):
        lines.append(indent + label + ": array[" + str(len(value)) + "]")
        for index, item in enumerate(value[:40]):
            render_json_tree(item, lines, "[" + str(index) + "]", indent + "  ", depth + 1, secret)
        if len(value) > 40:
            lines.append(indent + "  ... (" + str(len(value) - 40) + " more items)")
        return
    lines.append(indent + label + ": " + json_scalar(value, secret))


def try_json(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def summarize_post_data(post_data):
    if not post_data:
        return ["Request body: (none)"]
    mime = post_data.get("mimeType", "")
    text = post_data.get("text", "")
    lines = ["Request body mimeType: " + (mime or "(unknown)")]
    parsed = try_json(text)
    if parsed is not None:
        tree = []
        render_json_tree(parsed, tree)
        lines.append("Request body JSON tree:")
        lines.extend(tree)
        return lines

    if "x-www-form-urlencoded" in mime.lower():
        pairs = urllib.parse.parse_qsl(text, keep_blank_values=True)
        lines.append("Request body form fields:")
        if not pairs:
            lines.append("  (none)")
        for key, value in pairs:
            shown = "<MASKED>" if is_secret_key(key) else shorten(mask_text(value))
            lines.append("  " + key + ": " + shown)
        return lines

    lines.append("Request body text length: " + str(len(text or "")))
    lines.append(mask_text(shorten(text, 3000)))
    return lines


def normalize_tag(tag):
    tag = re.sub(r"\s+", " ", tag.strip())
    return shorten(mask_text(tag), 240)


def summarize_html(text):
    safe_text = mask_text(text or "")
    unescaped = html.unescape(safe_text)
    lines = ["Response HTML length: " + str(len(text or ""))]
    lines.append("Response HTML first 3000 chars:")
    lines.append(unescaped[:3000])
    tags = []
    for pattern in (r"<li\b[^>]*>", r"<tr\b[^>]*>", r"<div\b[^>]*class=[\"'][^\"']+[\"'][^>]*>"):
        for match in re.finditer(pattern, safe_text, re.I):
            tags.append(normalize_tag(match.group(0)))
    counter = collections.Counter(tags)
    lines.append("Repeated HTML opening tag patterns (top 15):")
    if not counter:
        lines.append("  (none)")
    for tag, count in counter.most_common(15):
        lines.append("  " + str(count) + "x " + tag)
    return lines


def summarize_response_body(response):
    content = response.get("content") or {}
    headers = response.get("headers") or []
    mime = content.get("mimeType") or content_type_from_headers(headers)
    text = content.get("text")
    encoding = content.get("encoding", "")
    size = content.get("size", 0)
    lines = ["Response body mimeType: " + (mime or "(unknown)")]
    if encoding:
        lines.append("Response content encoding: " + encoding)
    if text is None:
        lines.append("Response body: no text captured; size=" + str(size))
        return lines
    if encoding and encoding.lower() == "base64":
        lines.append("Response body: base64/binary text omitted; encoded length=" + str(len(text)) + ", size=" + str(size))
        return lines
    lower_mime = mime.lower()
    parsed = None
    if "json" in lower_mime or text.lstrip().startswith("{") or text.lstrip().startswith("["):
        parsed = try_json(text)
    if parsed is not None:
        tree = []
        render_json_tree(parsed, tree)
        lines.append("Response JSON tree:")
        lines.extend(tree)
        return lines
    if "text/html" in lower_mime or "<html" in text[:1000].lower() or "<div" in text[:1000].lower():
        lines.extend(summarize_html(text))
        return lines
    lines.append("Response body: type=" + (mime or "(unknown)") + ", text length=" + str(len(text or "")) + ", size=" + str(size))
    lines.append(mask_text(shorten(text, 1200)))
    return lines


def has_jsessionid_set_cookie(entry):
    for header in entry.get("response", {}).get("headers", []) or []:
        if header.get("name", "").lower() == "set-cookie" and "JSESSIONID" in header.get("value", ""):
            return True
    return False


def interesting_entry(entry, login_entry_index, index):
    url = entry.get("request", {}).get("url", "")
    lower_url = url.lower()
    if any(part.lower() in lower_url for part in INTERESTING_URL_PARTS):
        return True
    return login_entry_index == index


def first_login_cookie_index(entries):
    for index, entry in enumerate(entries):
        if has_jsessionid_set_cookie(entry):
            return index
    return None


def list_first_urls(entries):
    seen = []
    for entry in entries:
        url = mask_url(entry.get("request", {}).get("url", ""))
        if url not in seen:
            seen.append(url)
        if len(seen) >= 30:
            break
    return seen


def summarize_entry(entry, display_index, login_cookie_index, actual_index):
    request = entry.get("request") or {}
    response = entry.get("response") or {}
    method = request.get("method", "")
    url = mask_url(request.get("url", ""))
    lines = ["=== [" + str(display_index) + "] " + method + " " + url + " ==="]
    if login_cookie_index == actual_index:
        lines.append("NOTE: possible login response (first Set-Cookie containing JSESSIONID)")
    lines.append("Request headers: " + request_headers_summary(request.get("headers") or []))
    lines.extend(summarize_post_data(request.get("postData")))
    lines.append("Response status: " + str(response.get("status", "")))
    lines.append("Response Content-Type: " + (content_type_from_headers(response.get("headers") or []) or response.get("content", {}).get("mimeType", "") or "(unknown)"))
    lines.extend(response_headers_summary(response.get("headers") or []))
    lines.extend(summarize_response_body(response))
    lines.append("")
    return lines


def main():
    try:
        with open(INPUT_FILE, "r", encoding="utf-8-sig") as handle:
            har = json.load(handle)
    except Exception as exc:
        print("ERROR: could not read " + INPUT_FILE + ": " + str(exc), file=sys.stderr)
        return 2

    entries = har.get("log", {}).get("entries", [])
    login_cookie_index = first_login_cookie_index(entries)
    matching = []
    for index, entry in enumerate(entries):
        if interesting_entry(entry, login_cookie_index, index):
            matching.append((index, entry))

    output = []
    output.append("Tedial HAR masked summary")
    output.append("Total HAR entries: " + str(len(entries)))
    output.append("Matched entries: " + str(len(matching)))
    output.append("")

    if not matching:
        output.append("ERROR: no matching Tedial entries found.")
        output.append("First 30 URLs in HAR:")
        for url in list_first_urls(entries):
            output.append("- " + url)
    else:
        for display_index, item in enumerate(matching, start=1):
            actual_index, entry = item
            output.extend(summarize_entry(entry, display_index, login_cookie_index, actual_index))

    result = "\n".join(output)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as handle:
        handle.write(result)
        handle.write("\n")
    print(result)
    if not matching:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
