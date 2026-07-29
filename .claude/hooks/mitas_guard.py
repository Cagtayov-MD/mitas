#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MITAS Guard Hook (PreToolUse)
------------------------------
Uc koruma:
1. KILITLI DOSYA -> "ask": yuk-tasiyan dosyalara (mitas_roots.py vb.) yazmadan
   once kullanici onayi istenir.
2. ENV OKUMA -> "deny": .env dosyalari API anahtari icerir; Read ile acilirsa
   anahtar transcript'e sizer. Anahtar ISIMLERI gerekiyorsa grep -oE '^[A-Z_]+='
3. URETIM VERISI -> "deny": Database/, Mitas Output/ gibi geri-getirilemez
   koklerde rm/shred/-delete engellenir. Gerekiyorsa Cagatay kendi
   terminalinden calistirir.
4. SUPURGE KOMUTU -> "deny": git clean -x/-X ve git gc/repack tum agaci
   vurur; yol eslesmesi aranmaz. Kuru kosu (--dry-run / -n) serbesttir.

Sessiz gecis = izin (cikti yok, exit 0).
"""

import json
import os
import re
import sys


def out(decision, reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # girdi bozuksa engelleme, sessiz gec

tool = data.get("tool_name", "")
ti = data.get("tool_input") or {}
cwd = data.get("cwd") or "/opt/mitas"

LOCKED = {
    "/opt/mitas/scripts/mitas_roots.py":
        "yük-taşıyan kök tanımı — 46+ yerde hard-code referanslı",
    "/opt/mitas/model_manifest.yaml":
        "benchmark politikası (no_engine_selection_before_benchmark)",
    "/opt/mitas/MITAS_KUNYE_KURALLARI.md":
        "künye kural dosyası — üretim çıktı formatını belirler",
    "/opt/mitas/CLAUDE.md":
        "kural defteri — yönetim modeli",
}

PROD_ROOTS = [
    "/opt/mitas/Database",
    "/opt/mitas/Mitas Output",
    "/opt/mitas/Mitas_Files",
    "/opt/mitas/models",
    "/opt/mitas/venvs",
    "/opt/mitas/testklipler",
    "/opt/mitas/KARANTINA_2026-07-29",
    "/opt/mitas/arsiv",
]


def norm(p):
    if not p:
        return ""
    p = os.path.expanduser(p)
    if not os.path.isabs(p):
        p = os.path.join(cwd, p)
    return os.path.realpath(p)


if tool in ("Edit", "Write", "NotebookEdit"):
    p = norm(ti.get("file_path") or ti.get("notebook_path"))
    if p in LOCKED:
        out("ask",
            f"🔒 KİLİTLİ DOSYA: {os.path.basename(p)} — {LOCKED[p]}. "
            "Bilinçli bir değişiklikse onaylayın; değilse reddedin.")
    sys.exit(0)

if tool == "Read":
    p = norm(ti.get("file_path"))
    base = os.path.basename(p)
    is_env = (base == ".env" or base.endswith(".env")
              or re.match(r"^\.env\.", base) is not None)
    if is_env and not base.endswith(".example"):
        out("deny",
            "🔑 ENV KORUMASI: bu dosya API anahtarı içerebilir; içeriği "
            "okumak anahtarı transcript'e sızdırır. Anahtar İSİMLERİ "
            f"gerekiyorsa: grep -oE '^[A-Z_]+=' {ti.get('file_path', '')}")
    sys.exit(0)

# Tüm ağacı süpüren komutlar: yol eşleşmesi ARAMAZ, cwd'den itibaren her şeyi vururlar.
# git clean -x/-X: .gitignore'lu HER ŞEYİ siler. /opt/mitas'ta bu 1.1 TB demek —
#   models/ 587G, Mitas_Files/ 157G, Database/ 119G, venvs/ 105G, mitas.env, CLAUDE.md.
#   (2026-07-29 ölçümü: `git clean -ndx` 1429 giriş listeliyor.)
# git gc/repack: erişilemez ama BENZERSİZ commit'leri yeniden paketlerken atar.
#   2026-07-29'da 3 yetim commit'te başka hiçbir yerde olmayan test dosyaları bulundu;
#   kurtarma/* dalları o yüzden açıldı. gc bu dallar olmadan onları yok ederdi.
SUPURGE = [
    (re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+clean\b(?=.*(?:-\w*[xX]|--force.*-\w*[xX]))"),
     "git clean -x/-X: .gitignore'lu HER ŞEYİ siler — burada ~1.1 TB "
     "(models/, Mitas_Files/, Database/, venvs/, mitas.env). Kuru koşu için "
     "`git clean -ndx` kullanın."),
    (re.compile(r"\bgit\b(?:\s+-C\s+\S+)?\s+(?:gc|repack)\b"),
     "git gc/repack: erişilemez ama benzersiz commit'leri yok eder. Bu repoda "
     "kurtarma/* dallarıyla korunan 3 yetim commit var. Gerekiyorsa önce "
     "`git fsck --unreachable` ile inceleyin."),
]

if tool == "Bash":
    cmd = ti.get("command", "") or ""
    kuru = ("--dry-run" in cmd) or re.search(r"\bclean\b[^|;&]*\s-\w*n", cmd)
    if not kuru:
        for desen, mesaj in SUPURGE:
            if desen.search(cmd):
                out("deny", f"🛑 SÜPÜRGE KOMUTU: {mesaj}")
    if re.search(r"\b(rm|rmdir|shred)\b", cmd) or "-delete" in cmd:
        for root in PROD_ROOTS:
            rel = os.path.basename(root)
            hit = (root in cmd
                   or root.replace(" ", "\\ ") in cmd
                   or re.search(rf"""(^|[\s"'=]){re.escape(rel)}/""", cmd))
            if hit:
                out("deny",
                    f"🛑 ÜRETİM VERİSİ KORUMASI: komut '{root}' üzerinde "
                    "silme içeriyor — bu geri getirilemez arşiv/model "
                    "verisine dokunur. Gerçekten gerekiyorsa Çağatay kendi "
                    "terminalinden çalıştırsın.")
    sys.exit(0)

sys.exit(0)
