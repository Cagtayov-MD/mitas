#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""credit_text_read.py — OneOCR+GLM HAM METNİNDEN rol-eşleme (VLM-okuma YERİNE).

KURAL (Çağatay 2026-06-08): Okuma OneOCR+GLM ile yapılır; isimler OCR METNİNDEN gelir.
LLM yalnız ROL-EŞLEME yapar (pikselden OKUMAZ) → halüsinasyon imkânsız: her çıktı ismi
OCR metninde token olarak bulunmazsa ATILIR (anti-halüsinasyon kalkanı).

read_credits_from_text(lines, title, model) -> {"yonetmen":[...],"yapimci":[...],"cast":[...],"guven":...,"ham":...}

Akış: ham OCR satırları → LLM (rol-eşleme JSON, isim-metinden) → KALKAN (token-doğrulama)
      → GARBLE KAPISI (looks_garble) → KB ROL-FİLTRESİ (crew-oyuncu ayırt) → çıktı.

2026-06-08 F1/F2/F3 düzeltmeleri:
  F1 — ENSEMBLE: read_credits_auto artık tüm zinciri koşar, ilk-doluda durmaz;
       credit_video_read.fuse() mantığıyla yönetmen mutabakatı/KB-seçimi.
  F2 — KB ROL-FİLTRESİ: credit_video_read.KB ile crew→cast sızıntısını keser.
  F3 — GARBLE KAPISI: outputs/garble_audit.looks_garble ile garble isimler atılır.
"""
from __future__ import annotations
import json
import os
import re
import sys
import unicodedata
import urllib.request

OLLAMA = os.environ.get("MITAS_OLLAMA", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "gemma-4-31b-it-qat-vision:latest")
# FIX 3 (2026-06-22): cast garble-gate'i 8-cap'ten ÖNCE çalıştır — garble'lar 8-slot
# bütçesini doldurup gerçek adları (geç-sırada görünen seslendiren vb.) atmasın.
# Monotonik-güvenli (gate=alt-dizi; non-regresyon audit PASS). AKTİF (default ON).
# MITAS_EXTRACT_GATE_BEFORE_CAP=0 ile eski sıra (cap-sonra-filtre) geri gelir (kill-switch).
_GATE_BEFORE_CAP = os.environ.get("MITAS_EXTRACT_GATE_BEFORE_CAP", "1").strip().lower() in (
    "1", "true", "on", "yes")

# RENDER yanlış-pozitif kalkanı (2026-06-28): detect_script() oransızdır — tek latin-dışı
# karakter bile "latin değil" döndürür. TRT-logo OCR'ı '西' (CJK) / prop-tabela 'ا' (Arap)
# gibi tek-tük gürültü, tamamen Latin bir filmi (SUÇ MEVSİMİ, ŞERİF SHAUGNESSY) "latin-dışı
# kaynak" sanıp haksız KONTROL/RENDER'a yolluyordu. Gerçek latin-dışı jenerik yüksek-oranlıdır;
# gürültü <%2. Oranla ayır. MITAS_NONLATIN_MIN_RATIO=0 ile eski (oransız) davranış geri gelir.
_NONLATIN_MIN_RATIO = float(os.environ.get("MITAS_NONLATIN_MIN_RATIO", "0.02"))


def _nonlatin_ratio(s: str) -> float:
    """Metindeki latin-dışı harflerin TÜM harflere oranı (0..1). Rakam/noktalama sayılmaz."""
    alpha = [c for c in (s or "") if c.isalpha()]
    if not alpha:
        return 0.0
    nonlatin = 0
    for c in alpha:
        try:
            if "LATIN" not in unicodedata.name(c):
                nonlatin += 1
        except ValueError:
            continue
    return nonlatin / len(alpha)

_TR_FOLD = str.maketrans("ışğçöüİIÄ", "isgcouiia")


def _fold(s: str) -> str:
    s = (s or "").casefold().translate(_TR_FOLD)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s)


def _toks(s: str):
    return [t for t in _fold(s).split() if len(t) > 2]


_CREW_CONTEXT_KW = (
    "assistant art director", "art department", "art director", "set designer", "draftsman",
    "art department pa", "storyboard", "construction coordinator", "lead carpenter",
    "carpenter", "gimbal operator", "dolly grip", "key grip", "best boy", "gaffer",
    "production sound mixer", "boom operator", "sound mixer", "sound recordist",
    "camera", "assistant camera", "second unit camera", "director of photography",
    "cast editing assistant", "editing assistant", "extras casting", "casting assistant",
    "casting director", "unit production manager", "production coordinator",
    "production accountant", "assistant director", "modeler", "modelers", "animation",
    "animator", "supervisor", "operator", "buyer", "coordinator", "manager",
    "department", "assistant", "technician", "designer", "editor", "mixer",
    "performed by", "mixed by", "music", "song", "songs", "soundtrack",
    "visual effects", "courtesy of", "records", "licensing", "arrangement",
    # C5c genişletme — yapımcı/teşekkür/yabancı crew unvanları (2026-06-22)
    "producer", "producers", "yapimci", "yapımcı",
    "executive producer", "co producer", "associate producer",
    "line producer", "tesekkur", "teşekkür",
    "special thanks", "thanks to", "wrangler", "redaktion",
    "dialogue coach", "scenario", "scénario",
    # cast/yapımcı doğruluk-denetimi 2026-07-04 — canlı vakalardan crew-etiket ailesi:
    "kamera", "kamera yrd", "isik ekibi", "işık ekibi", "set amiri", "set amiri",  # 21.YÜZYIL
    "collaborateurs", "collaborateur", "yardimci yonetmen",                        # KABAKÇIĞIN (senaryo-ortağı)
    "seslendirme", "seslendirme yonetmeni", "dublaj",                              # AYNADAKİ (dublaj)
    "firearms consultant", "consultant", "danisman", "danışman", "uzman",          # HIZLI VE ÖFKELİ (silah danışmanı)
    "stunt", "dublor", "dublör", "stunts", "wrangler", "trainer",
    "yapim asistan", "yapım asistan", "uygulayici yapimci", "uygulayıcı yapımcı",  # line-producer TR
    "makyaj", "kostum", "kostüm", "montaj", "kurgu", "muzik", "müzik",
    "genel koordinator", "koordinator", "koordinatör", "hazirlayan", "hazırlayan",
)
_CAST_CONTEXT_KW = (
    "starring", "co starring", "cast", "oyuncular", "oynayanlar",
)


def load_raw_context_for_ocr(ocr_path: str | os.PathLike | None) -> list[str]:
    """Load the raw frame OCR next to kunye.txt when available.

    kunye.txt is de-duplicated and may lose role adjacency. The raw files preserve enough
    neighborhood to tell "NAME near crew role" from a real cast block.
    """
    if not ocr_path:
        return []
    base = os.path.dirname(os.fspath(ocr_path))
    for fn in ("ocr_raw_all.txt", "ocr_ham.txt"):
        p = os.path.join(base, fn)
        try:
            if os.path.exists(p):
                lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
                if lines:
                    return lines
        except Exception:
            continue
    return []


def _read_ocr_sidecar_lines(base: str, filename: str) -> list[str]:
    p = os.path.join(base, filename)
    try:
        if os.path.exists(p):
            lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            return [line for line in lines if str(line).strip()]
    except Exception:
        pass
    return []


def _compact_raw_lines_for_llm(lines: list[str], *, max_lines: int = 700) -> list[str]:
    """Keep raw OCR bounded for the LLM while preserving credit-role neighborhoods."""
    cleaned = [str(line).strip() for line in (lines or []) if str(line).strip()]
    if len(cleaned) <= max_lines:
        return cleaned

    hints = re.compile(
        r"\b(CAST|STARRING|IN ORDER OF APPEARANCE|DIRECTED BY|WRITTEN\s*&\s*DIRECTED|"
        r"PRODUCED BY|PRODUCER|YONETMEN|YÖNETMEN|YAPIMCI|OYUNCU|OYUNCULAR)\b",
        re.IGNORECASE,
    )
    keep: set[int] = set()
    for i, line in enumerate(cleaned):
        if hints.search(line):
            keep.update(range(max(0, i - 80), min(len(cleaned), i + 160)))

    if not keep:
        head = max_lines // 2
        tail = max_lines - head
        return cleaned[:head] + cleaned[-tail:]

    # ÖNCELİKLİ KESİM (2026-08-01, KUTSAL HAZİNE 1998-0325 kanıtı).
    # ESKİ DAVRANIŞ: keep bütçeyi aşınca BELGE SIRASINA göre baştan kesiliyordu
    # (`ordered[:max_lines]`). Yönetmen kartı jeneriğin SONUNDA durur → sistem
    # ipucunu doğru bulup koruma listesine ekliyor, sonra pozisyon yüzünden atıyordu.
    # KANIT: ocr_ham 1904 satır, "Directed by"/"JOHN CONNICK" satır 1504-1505'te,
    # 500 sınırından sonra → MODEL YÖNETMENİ HİÇ GÖRMEDİ. "gemma atladı" sanılan
    # vaka aslında girdi kesmesiydi (model A/B'de aynı gemma, kunye.txt verilince
    # ismi BULDU). Ölçek: 500'ü aşan 76 filmin 2'si (KUTSAL HAZİNE, DONÖR).
    # ÇÖZÜM: QC1'in sorduğu alanların (yönetmen + oyuncu) ipucu komşuluğu ÖNCE
    # rezerve edilir, kalan bütçe diğer ipuçlarına belge sırasıyla dağıtılır.
    # Sıra korunur (model satır komşuluğuna güveniyor). Geri dönüş: MITAS_COMPACT_ONCELIK=0.
    if len(keep) > max_lines and os.environ.get(
            "MITAS_COMPACT_ONCELIK", "1").strip().lower() not in ("0", "false", "off"):
        _oncelikli = re.compile(
            r"\b(DIRECTED BY|WRITTEN\s*&\s*DIRECTED|YONETMEN|YÖNETMEN|"
            r"CAST|STARRING|OYUNCU|OYUNCULAR|IN ORDER OF APPEARANCE)\b", re.IGNORECASE)
        birinci: set[int] = set()
        for i, line in enumerate(cleaned):
            if _oncelikli.search(line):
                birinci.update(range(max(0, i - 40), min(len(cleaned), i + 80)))
        birinci &= keep
        if len(birinci) > max_lines:            # tek başına taşıyorsa yine kırp
            birinci = set(sorted(birinci)[:max_lines])
        kalan = max_lines - len(birinci)
        ikinci = [i for i in sorted(keep - birinci)][:max(0, kalan)]
        keep = birinci | set(ikinci)

    ordered = [cleaned[i] for i in sorted(keep)]
    if len(ordered) > max_lines:
        ordered = ordered[:max_lines]
    return ordered


def load_llm_lines_for_ocr(ocr_path: str | os.PathLike | None) -> tuple[list[str], str]:
    """Load the least-lossy OCR text that should be shown to the text model.

    `kunye.txt` is useful as a delivered/normalized artifact, but it can flatten
    credit cards such as `MAURA Sally Hawkins` into `MAURA SALLY HAWKINS`.
    The model should see the rawer OneOCR text first; deterministic cleanup runs
    after the model output.
    """
    if not ocr_path:
        return [], ""
    base = os.path.dirname(os.fspath(ocr_path))

    for filename in ("ocr_ham.txt", "ocr_raw_all.txt"):
        lines = _read_ocr_sidecar_lines(base, filename)
        if lines:
            lines = _compact_raw_lines_for_llm(lines, max_lines=500)  # 260→500: uzun/anahtar-kelimesiz jenerikte kadro-bloğu kaybını azalt (recall güvenliği)
            # YÖNETMEN-KARTI KÖPRÜSÜ (2026-07-04, MÜREKKEP kanıtı): "AN IAIN SOFTLEY FILM" gibi
            # kendinden-etiketli kartlar STITCH-birleşik kunye.txt'de VAR ama ham yan-dosyalarda
            # BÖLÜNMÜŞ (AN / IAIN SOFTLEY / FILM ayrı satırlar) → model+rescue hiç görmüyordu.
            # kunye.txt'nin yönetmen-kartı satırlarını (lexicon is_director_line: A-X-FILM ters-desen
            # + head-isim aynı-satır; stüdyo-bumper dışlanır) girdiye SALT-EKLE (dedup'lu).
            try:
                import credit_role_lexicon as _lexb
                _have = {l.strip().upper() for l in lines}
                _kadd = []
                for _kl in open(ocr_path, encoding="utf-8", errors="ignore").read().splitlines():
                    _kl = _kl.strip()
                    if _kl and _kl.upper() not in _have and _lexb.is_director_line(_kl):
                        _kadd.append(_kl)
                if _kadd:
                    lines = lines + _kadd[:4]
            except Exception:  # noqa: BLE001 — köprü hatası girdiyi ASLA bozmaz
                pass
            return lines, filename

    try:
        lines = open(ocr_path, encoding="utf-8", errors="ignore").read().splitlines()
        return [line for line in lines if str(line).strip()], os.path.basename(os.fspath(ocr_path))
    except Exception:
        return [], ""


def _name_hit_in_raw(name_fold: str, line_fold: str) -> bool:
    if not name_fold or not line_fold:
        return False
    if line_fold == name_fold:
        return True
    return bool(re.search(r"\b" + re.escape(name_fold) + r"\b", line_fold))


def _crew_context(window: str) -> bool:
    return any(k in window for k in _CREW_CONTEXT_KW)


def _cast_context(window: str) -> bool:
    return any(k in window for k in _CAST_CONTEXT_KW) and not _crew_context(window)


def filter_cast_by_raw_context(cast: list[str], raw_context_lines: list[str] | None) -> list[str]:
    """Drop cast candidates that only appear in raw OCR next to crew-role labels.

    This is a negative gate only: it never adds names. If crew-context sightings dominate
    and there is no explicit cast/starring context, the name is removed.

    2026-07-10 KOMŞU-DIŞLA KAPISI (SANTRAL/"The Operator" kökü, canlı-veri kanıtlı — bkz
    tests/test_credit_text_read_cast_context.py): yoğun "in order of appearance" listelerinde
    art arda gelen SATIRLAR farklı cast-adaylarına ait olabilir — pencere geriye-baktığında (i-2..i)
    KOMŞU bir adayın KENDİ satırını "rol-etiketi" sanabiliyordu. Kanıt: BRION JAMES'in kendi satırı
    hiç crew-kelimesi taşımıyor, ama hemen-önceki satır JACQUELINE KIM'in kendi kartı olup jenerik
    "operator" kelimesini içeriyor ("Operator JACQUELINE KIM") — bu, Brion James'in penceresine
    sızıp onu da crew sayıyordu. Fix: pencere yalnız KENDİ satırını (j==i) VE gerçek çevre-metni
    içerir — cast listesindeki HERHANGİ bir adayın kendi kredi-satırı (komşu konumdaysa) asla
    "rol-etiketi" sayılmaz. Negatif-yönlü: isim eklemez, yalnız yanlış-crew-sinyalini azaltır.
    268-film canlı-taramasında SIFIR regresyon (yalnız 2 ek doğru-kurtarma: BRION JAMES/SANTRAL,
    MAZHAR ALANSON/HERŞEY ÇOK GÜZEL OLACAK — bkz outputs/CAST_CONTEXT_FIX_20260710/).

    BİLİNÇLİ KAPSAM-DIŞI (2026-07-10): adayın KENDİ satırının crew-kelimesini taşıdığı "kendi-satır
    çakışması" (SANTRAL'de JACQUELINE KIM — karakter adı bizzat "Operator") bu fix'e DAHİL EDİLMEDİ.
    İçerik-bazlı dedup (aynı fiziksel kartın tekrar-OCR'lanan okumalarını tek oya indirmek) bu
    durumu SANTRAL'de düzeltiyordu AMA 268-film taramasında 8 filmde GERÇEK oyuncuları (BILL MURRAY,
    MARTIN SHORT, MICHAEL WINCOTT, ...) yanlış-crew sayıp düşürdü — çünkü bazı gerçek oyuncuların
    filmde AYRICA bağımsız/meşru crew-görünümlü ek-satırları da var (BILL MURRAY: kendi oyuncu-satırı
    + "Assistants to Bill Murray" + "Performed by Bill Murray" — 3 farklı fiziksel yer, ham-tekrar
    sayısı raw-oran'ı güvenle <0.60 tutuyordu, dedup bu güvenlik payını yok etti). Denenmiş/reddedilmiş
    alternatifler: içerik-dedup + çoğunluk-oy (Bill Murray'i yine düşürüyor), yakınlık-kümeleme
    (SANTRAL için gereken eşik Bill Murray'in "Performed by" kümesini de parçalayıp aynı hataya
    düşüyor). Kök sorun: "kaç kez okundu" tek başına crew/cast ayrımı için güvenilir sinyal değil.

    2026-07-10 BAĞIMSIZ-KANIT KAPISI (ETHAN HAWKE kökü, task_61e2ea2d, canlı-veri kanıtlı — bkz
    tests/test_credit_crew_leak_gate.py::test_raw_context_gate_drops_crew_names_only): i-2 penceresi
    (yukarıdaki KABAKÇIĞIN/"Collaborateurs au scénario" fix'i, b6b0ac8a 2026-07-04) 2026-06-19'da
    yazılmış ÖNCEDEN VAR OLAN bu testi fark edilmeden BOZMUŞTU (o tarihte pencere ±1'di, i-2 hiç
    reach etmiyordu — regresyon 6 gün fark edilmedi çünkü regresyon_golden.py cast'i test etmiyor,
    bkz [[project_cast_sessiz_kayip_4mekanizma_20260710]]). Kanıt: crew-etiketi ("1st Assistant Art
    Director") ETHAN HAWKE'ın 2 satır üstünde, ama ARADAKİ satır ("CAPTAIN AHAB") ne cast listesindeki
    başka bir adayın satırı NE DE crew-bağlamlı — sadece etiketle hiç ilgisi olmayan bir dolgu satırı.
    Pencere yine de etikete "reach" edip Ethan Hawke'ı crew sayıyordu.

    Basit çözüm (i-2 reach'i SADECE i-1 "bağlantılıysa" — cast listesindeki başka bir adayın satırıysa
    VEYA kendisi crew-bağlamlıysa — izin ver) test'i düzeltti AMA 224-film canlı taramasında (delivered
    cast + ham-OCR, aynı SANTRAL yöntemi) KABAKÇIĞIN'in KENDİ motive edici vakasını (MORGAN NAVARRO,
    gerçek "Collaborateurs au scénario" ekran-kanıtlı senaryo-ortağı) REGRESE ETTİ: ham OCR'da 13
    tekrar-okumanın 10'unda etiketle MORGAN NAVARRO arasına komşu "Un film de" kartından taşan bağımsız
    bir isim (CLAUDE BARRAS, yönetmen — cast adayı DEĞİL, crew-bağlamlı da DEĞİL, salt scroll-OCR
    kart-geçiş gürültüsü) giriyor — algoritma açısından CAPTAIN AHAB'la AYIRT EDİLEMEZ şekilde aynı
    şekilli. Basit "i-1 bağlantılı mı" sinyali ARADAKİ satırın kim olduğuna bakıyor, bu yüzden şans
    eseri (MORGAN NAVARRO'nun eş-yazarı GERMANO ZULLO da yanlışlıkla OYUNCU sınıflanmışsa) çalışıyor,
    değilse (PIERRE RICHARD'ın eş-senarist ANDRE RUELLAN'ı gibi crew'a hiç sızmamış biriyse) çalışmıyor.

    UYGULANAN ÇÖZÜM — BAĞIMSIZ-KANIT (2-geçişli): i-2 reach'i i-1 bağlantılıysa (yukarıdaki gibi) VEYA
    bu ADIN KENDİSİNİN ham-bağlamda BAŞKA BİR YERDE (herhangi bir tekrar-okumada) doğrudan ±1 penceresinde
    ŞÜPHESİZ crew-kanıtı VARSA izin ver. Mantık: MORGAN NAVARRO'nun 13 tekrarının 3'ünde etiket doğrudan
    i-1'de (gürültüsüz) — bu doğrudan kanıt, adının TÜM tekrarlarına (gürültülü olanlar dahil) güven
    yayar. ETHAN HAWKE'ın (1 tekrar) ve PIERRE RICHARD'ın (2 tekrar, ikisi de sadece i-2 üzerinden) HİÇBİR
    doğrudan/gürültüsüz kanıtı yok — sadece komşu bir isim üzerinden ZAYIF çıkarım var, tek başına
    yetersiz. 224-film taramasında SIFIR regresyon (KABAKÇIĞIN'in MORGAN NAVARRO'su dahil — artık doğru
    şekilde DÜŞÜYOR); tek kurtarma PIERRE RICHARD (ŞAŞKIN REKLAMCI) — BAĞIMSIZ olarak doğrulandı: ham
    OCR'da AYRI bir "AVEC / P ERRE / RICHARD" (starring-kart, MARIE CHRISTINE BARRAULT'la birlikte)
    kanıtı VAR ama mevcut ad-eşleştirme (_name_hit_in_raw tam-satır eşleşmesi) OCR'ın "PIERRE"yi "P ERRE"
    diye bölmesi yüzünden bunu hiç yakalamıyor (ayrı, bu fix'in kapsamı dışı bir ad-eşleştirme kısıtı) —
    yani kurtarma yanlışlıkla değil, GERÇEK starring-kanıtı (algoritmanın şu an göremediği) sayesinde
    doğru sonuca varıyor. Reddedilen alternatifler: (a) sadece i-1-bağlantılı (MORGAN NAVARRO'yu regrese
    etti), (b) sadece crew-bağlamlı i-1 (aynı regresyon, all_name_idxs şansı da yok), (c) AND-birleşimi
    (daha kısıtlayıcı, MORGAN NAVARRO'yu düzeltmiyor). Detay: outputs/CAST_CONTEXT_FIX_20260710/ (SANTRAL
    yöntemi) + bu oturumun ek 224-film taraması (script kalıcı değil, yöntem burada belgeli).
    """
    if not cast or not raw_context_lines:
        return cast or []
    folded = [_fold(x).strip() for x in raw_context_lines]

    all_hits: dict[str, set[int]] = {}
    for nm in cast:
        nf = _fold(nm).strip()
        all_hits[nm] = {i for i, line in enumerate(folded) if _name_hit_in_raw(nf, line)}
    # cast listesindeki HERHANGİ bir adayın ham-satır index kümesi (komşu-kirlenme testi).
    all_name_idxs: set[int] = set().union(*all_hits.values()) if all_hits else set()

    out: list[str] = []
    for nm in cast:
        hit_idxs = sorted(all_hits[nm])
        if not hit_idxs:
            out.append(nm)
            continue

        def _win_cast_at(i: int) -> str:
            return " ".join(folded[j] for j in range(max(0, i - 1), i + 1)
                             if j == i or j not in all_name_idxs)

        # BAĞIMSIZ-KANIT ön-geçişi: bu ad, ham-bağlamda BAŞKA bir tekrarında gürültüsüz/doğrudan
        # (±1) crew-kanıtı taşıyor mu? Taşıyorsa i-2 reach'i TÜM tekrarlarına güvenilir (bkz docstring).
        has_direct_evidence = any(_crew_context(_win_cast_at(i)) for i in hit_idxs)

        crew_count = 0
        cast_seen = False
        for i in hit_idxs:
            # cast-bağlamı DAR pencere (±1): gerçek oyuncu yanlışlıkla "cast-görüldü" sayılmasın.
            # crew-bağlamı GENİŞ üst-pencere (i-2..i): çok-satıra bölünen etiket ("Collaborateurs au
            # scénario" isimden 2 satır üstte — KABAKÇIĞIN 2026-07-04) yakalansın. 60%-eşik + cast-öncelik
            # yanlış-pozitifi dizginler. KOMŞU-DIŞLA: kendi satırı (j==i) HER ZAMAN kalır; komşu satır
            # (j<i) cast listesindeki HERHANGİ bir adayın kendi satırıysa pencereden düşer.
            #
            # BAĞIMSIZ-KANIT KAPISI: i-2 reach'i yalnız i-1 "bağlantılıysa" (cast listesindeki başka
            # bir adayın satırı VEYA kendisi crew-bağlamlı) YA DA bu ad başka bir tekrarda doğrudan
            # kanıt taşıyorsa (has_direct_evidence) açılır — aksi halde etiketle arasına giren, cast
            # listesiyle ilgisiz bir dolgu satırı (ör. bir karakter adı) i-2'deki etiketi bu ada asla
            # bağlamaz (ETHAN HAWKE/CAPTAIN AHAB deseni).
            win_cast = _win_cast_at(i)
            lo = i - 1
            if i - 1 >= 0:
                i1_connected = (i - 1) in all_name_idxs or _crew_context(folded[i - 1])
                if i1_connected or has_direct_evidence:
                    lo = i - 2
            win_crew = " ".join(folded[j] for j in range(max(0, lo), i + 1)
                                 if j == i or j not in all_name_idxs)
            if _cast_context(win_cast):
                cast_seen = True
            if _crew_context(win_crew):
                crew_count += 1
        if cast_seen or crew_count == 0 or (crew_count / len(hit_idxs)) < 0.60:
            out.append(nm)
    return out


def _name_casing_hits(name: str, raw_lines: list[str]) -> tuple[int, int]:
    """İsmin ham (fold'suz) satırlarda kaç kez TÜMÜ-BÜYÜK-HARF, kaç kez EN-AZ-BİR-KÜÇÜK-HARF
    biçiminde geçtiğini sayar (word-boundary, fold-toleranslı arama, orijinal casing üzerinde ölçüm)."""
    toks = [t for t in _fold(name).split() if t]
    if not toks:
        return (0, 0)
    pat = re.compile(r"\b" + r"\s+".join(re.escape(t) for t in toks) + r"\b", re.IGNORECASE)
    caps = mixed = 0
    for ln in raw_lines:
        s = str(ln or "")
        for m in pat.finditer(s):
            letters = [c for c in m.group(0) if c.isalpha()]
            if len(letters) < 2:
                continue
            if all(c.isupper() for c in letters):
                caps += 1
            else:
                mixed += 1
    return (caps, mixed)


def filter_cast_by_dotleader_casing(cast: list[str], raw_lines: list[str] | None) -> list[str]:
    """NOKTA-DİZİLİ (dot-leader) KARAKTER/OYUNCU KASA-KAPISI (2026-07-09, LAUREL HARDY kökü).

    Klasik-Hollywood "Karakter......OYUNCU" iki-sütunlu kredi kartlarında ekranda karakter adı
    Baş-Harfi-Büyük, oyuncu adı TÜMÜ-BÜYÜK basılır ("Tommy White.......JOHN SHELTON"). OneOCR bu
    satırı bazen TEK parça okur (nokta korunur, sütun belli: "Malcolm Kilgore ... ADDISON
    RICHARDS") ama çoğu zaman çok-kare mozaikte İKİ AYRI satıra böler ("Tommy White" / "JOHN
    SHELTON") — sütun-ipucu kaybolunca PROMPT'un "CASING İPUCU" (kural 2a) talimatı, uzun/gürültülü
    bağlamda küçük modelde güvenilir uygulanmıyor, karakter adı oyuncu sanılabiliyor (kanıt: TOMMY
    WHITE/DOC LAKE/FRANK LUCAS/DARBY MASON/DIXIE BEELER/MALCOLM KILGORE cast'e sızmış, ham OCR'da
    HİÇBİRİ tek kez bile ALL-CAPS görülmüyor — hepsi yalnız Title-Case).

    NEGATİF-KAPI (yalnız düşürür, isim EKLEMEZ — OCR-otorite ihlali yok): aday ham satırlarda
    YALNIZ karışık-kasa (en az bir küçük harf) görülüyorsa, HİÇ ALL-CAPS varyantı yoksa VE aynı
    cast listesinde başka bir isim ALL-CAPS-kanıtlıysa (= bu filmin kredi kartı casing'i GERÇEKTEN
    ayırt edici, rastgele OCR-gürültüsü değil) → karakter-adı say, at. Aksi halde (hiç ALL-CAPS-
    kanıtlı sibling yok = casing bu filmde ayırt edici değil, ör. OCR tüm satırı küçük/karışık
    okumuş) → DOKUNMA (yanlış>boş, fail-safe). Kill-switch: MITAS_CAST_CASING_GATE=0."""
    if os.environ.get("MITAS_CAST_CASING_GATE", "1").strip().lower() in ("0", "false", "off", "no"):
        return cast or []
    if not cast or len(cast) < 2 or not raw_lines:
        return cast or []
    raw = [str(l) for l in raw_lines if str(l).strip()]
    profiles = {nm: _name_casing_hits(nm, raw) for nm in cast}
    if not any(caps > 0 for caps, _mixed in profiles.values()):
        return cast  # bu filmde casing ayırt edici değil — dokunma
    out, dropped = [], []
    for nm in cast:
        caps, mixed = profiles.get(nm, (0, 0))
        if caps == 0 and mixed > 0:
            dropped.append(nm)
        else:
            out.append(nm)
    if dropped:
        sys.stderr.write(
            f"[kasa-kapisi] karakter-adi dustu (yalniz Title-Case, ALL-CAPS kaniti yok): {dropped}\n")
    return out


# DUBLAJ markerları — HER ZAMAN uygula (dublaj-rolü ASLA film-yönetmeni değil, yüksek-isabet).
# "dialogue direct/dialogue writ" (doğruluk-denetimi 2026-07-03, TILSIMLI DÜNYA/anime kanıtı):
# ekranda "Written and Directed by CARL MACEK" (gerçek) YANINDA "Dialogue Written and Directed by
# GREG SNEGOFF" (ADR/dublaj yönetmeni) vardı; sistem dublaj olanı seçmişti. "Dialogue" öneki ayıraç.
_DUB_MARKERS = ("seslendirme", "dublaj", "doblaje", "doublage", "synchron", "voice direct",
                "dialogue direct", "dialogue writ", "adr direct")
# YÖNETMEN-DIŞI diğer rol markerları — yalnız aday ŞÜPHELİYKEN (mutabakat-DIŞI) uygula. Temiz+mutabık
# yönetmene dokunma (3.GÖZ kanıtı: jenerik satır-sırası bozuk olabilir → agresifse gerçek yön'ü öldürür).
_NONFILM_MARKERS = (
    "yardimci", "assistant direct", "asst direct", "aiuto regista",     # asistan yönetmen
    "ayudante", "asistente", "assistente",                             # asistan (ES/IT/PT)
    "music direct", "muzik yon", "art direct", "casting direct", "technical direct",  # X-yönetmeni
    "director of photo", "director de foto", "directeur de la photo", "goruntu yon",
    # DoP-fix (2026-07-03): eksik görüntü-yönetmeni varyantları — EN "cinematography by",
    # IT "direttore della fotografia". ("kamera" tek başına EKLENMEDİ: masum komşulukta
    # gerçek yönetmeni düşürme riski; canlı tarama gerekçe gösterirse ayrıca değerlendirilir.)
    "cinematograph", "della fotografia",
    # TR "FOTO DİREKTÖRÜ" (DİŞİ ŞEYTAN 1964-0002 kökü, 2026-07-07, gözle-teyitli): "goruntu yon"
    # farklı yaygın TR ifadesiydi (Görüntü Yönetmeni), "FOTO DİREKTÖRÜ" (Director of Photography'nin
    # eski-Yeşilçam usulü TR karşılığı) kapsanmıyordu → sinematograf TURGUT ÖREN film-yönetmeni sanıldı.
    "foto direkt", "fotograf direkt",
    # Yaratıcı-etiket ailesi (dolu-yönetmen doğruluk-denetimi 2026-07-03, HALIFAX kanıtı):
    # dizi/franchise kartı "Devised by ROGER SIMPSON" bölüm-yönetmeni sanıldı (gerçek yönetmen
    # Lynn Hegarty ekranda hiç yoktu). "created by/creator" aynı sınıf (seri/karakter yaratıcısı
    # ≠ bölüm yönetmeni). Word-değil substring eşleşme olduğundan "series created by"yi de kapsar.
    "devised by", "created by", "creator",
    "production assistant", "production manager", "asistentes de produc", "ayudante de direc",
    "yapim asistan", "yapim sorumlu", "yapim koordinator",             # yapım rolleri
)

# GERÇEK-YÖNETMEN bağışıklık desenleri (DoP-fix 2026-07-03): adayın KENDİ ya da 2-üst satırında
# bu desenlerden biri varsa aday marker'la DÜŞÜRÜLMEZ (etiket-üstte klasik yerleşim korunur).
# Word-boundary: 'yonetmen' ∌ 'goruntu yonetmeni' ('yonetmeni' eki boundary'yi bozar), 'regie' ∌
# 'regieassistenz'. Liste bilinçli DAR: yalnız tek-anlamlı film-yönetmeni ifadeleri.
_TRUE_DIR_RE = re.compile(
    r"\b(directed by|a film by|film by|un film de|ein film von|film von|realise par|realisateur|"
    r"regia di|dirigido por|yonetmen|yoneten|rejisor|regie|"
    r"mise en scene|realisation|"                                           # FR ana-etiketler (2026-07-06)
    r"written and directed|directed and edited|produced and directed)\b")   # bileşik etiketler (AJAMİ 2026-07-03)


def _name_line_hits(name, folded_lines):
    """İsim kaç satırda TEK-SATIR-BİTİŞİK (word-boundary, sıralı) geçiyor — ekran-kanıt sayacı."""
    toks = _fold(name).split()
    if not toks:
        return 0
    pat = re.compile(r"\b" + r"\s+".join(re.escape(t) for t in toks) + r"\b")
    return sum(1 for l in folded_lines if pat.search(l))


def _collapse_clone_variants(names, raw_lines, kb):
    """KLON-İKİZ ÇÖKERTME (2026-07-04): fuzzy-yakın isim çiftlerinde kanıt-öncelikli eleme.
    (a) tek taraf ekran-kanıtlı → kanıtsız düşer (AJAMİ Rupert/Robert Preston);
    (b) iki taraf kanıtlı + ikisi de KB'de kişi değil → teke çök (BJ tabela-ikizi);
    (c) ikisi de KB-gerçek → dokunma (Brolin/Carradine). Fail-safe: hata → liste AYNEN.
    Kill-switch: MITAS_CLONE_COLLAPSE=0."""
    if os.environ.get("MITAS_CLONE_COLLAPSE", "1").strip().lower() in ("0", "false", "off", "no"):
        return names
    try:
        if not names or len(names) < 2 or not raw_lines:
            return names
        folded_lines = [_fold(str(l)) for l in raw_lines if str(l).strip()]
        import difflib as _dl
        drop = set()
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                fa, fb = _fold(a), _fold(b)
                if len(fa.split()) != len(fb.split()):
                    continue                       # token sayısı farklı (Jr. ekleri vb.) → dokunma
                if _dl.SequenceMatcher(None, fa, fb).ratio() < 0.75:
                    continue
                ha, hb = _name_line_hits(a, folded_lines), _name_line_hits(b, folded_lines)
                if (ha > 0) != (hb > 0):           # (a) yalnız biri kanıtlı → klon-fabrikasyon
                    drop.add(b if ha > 0 else a)
                    continue
                if ha > 0 and hb > 0 and kb is not None:   # (b) ikisi de kanıtlı → KB kişi-varlık
                    try:
                        ka = kb.verify(a, "actor") == "ONAY" or kb.verify(a, "person") == "ONAY"
                        kv = kb.verify(b, "actor") == "ONAY" or kb.verify(b, "person") == "ONAY"
                    except Exception:  # noqa: BLE001 — KB sorgusu patlarsa çift korunur
                        continue
                    if not ka and not kv:          # ikisi de KB'de yok → garble-ikiz, zayıfı at
                        drop.add(b if ha >= hb else a)
        if drop:
            sys.stderr.write(f"[klon-ikiz] düştü: {sorted(drop)}\n")
        return [n for n in names if n not in drop]
    except Exception:  # noqa: BLE001 — çökertme ASLA listeyi bozmaz
        return names


def _drop_dubbing_directors(directors, raw_lines, high_consensus=False):
    """YÖNETMEN-DIŞI ROL DIŞLAMA (Çağatay 2026-06-20): ham OCR'da yönetmen adayının ±2 satır bağlamında
    YÖNETMEN-DIŞI rol etiketi (dublaj/asistan-yön/yapım-asistanı/X-yönetmeni...) varsa → DÜŞ (deterministik,
    LLM-bağımsız). ESRA TANAR=3.GÖZ seslendirme-yön.yard.→düşer; gerçek Sam Raimi KB cast-kilidiyle gelir.
    DUBLAJ markerları HER ZAMAN; diğer roller yalnız high_consensus=False (mutabakat-dışı=şüpheli) iken
    → temiz+mutabık gerçek yönetmeni öldürmez (yanlış>boş; OCR-otorite: isim eklemez/ezmez, yalnız düşürür).
    Döner (kalan, düşenler)."""
    if not directors or not raw_lines:
        return list(directors or []), []
    folded = [_fold(str(l)) for l in raw_lines]
    markers = _DUB_MARKERS if high_consensus else (_DUB_MARKERS + _NONFILM_MARKERS)
    kept, dropped = [], []
    for d in directors:
        df = _fold(d)
        is_nf = False
        if df and len(df) >= 5:
            # B3 FIX (2026-06-20): WORD-BOUNDARY (plain 'df in lf' substring → masum yönetmeni başka
            # satıra rastlantısal eşleştiriyordu) + ±1 bağlam (±2 fazla genişti → uzaktaki crew-etiketi
            # gerçek yönetmeni düşürüyordu). high_consensus guard zaten temiz+mutabık yönü koruyor.
            _df_re = re.compile(r"\b" + re.escape(df) + r"\b")
            _occ = [i for i, lf in enumerate(folded) if _df_re.search(lf)]
            # KOMŞU-KART SINIRI (2026-07-10, Sam Raimi/ardışık-tek-satır-kart koku, test_dubbing_director_drop):
            # dub_ctx ±4-üst-pencere başka bir ADAYIN kendi isim-satırını AŞIP ondan ÖNCEKİ (alakasız)
            # karta ait dublaj-etiketini yakalıyordu — ör. "...SESLENDİRME YÖNETMENİ / ENGİN AYBAKAN /
            # YÖNETMEN / Sam Raimi" dizisinde Engin Aybakan'ın ÜSTÜNDEKİ dublaj-etiketi, Engin Aybakan'ın
            # KENDİ kartını atlayıp Sam Raimi'ye sızıyordu. Diğer adayların kendi isim-satırı kart-sınırı
            # sayılır; pencere o satırı aşamaz. TILSIMLI DÜNYA (2f9ecdcd) etkilenmez: orada marker
            # (Snegoff'un "Dialogue..." etiketi) sınır-adayın (Macek) satırından SONRA/kendi kartında kalır.
            _other_occ = set()
            for _od in directors:
                if _od is d:
                    continue
                _of = _fold(_od)
                if _of and len(_of) >= 5:
                    _other_occ |= {i for i, lf in enumerate(folded) if re.search(r"\b" + re.escape(_of) + r"\b", lf)}
            # GLOBAL-BAĞIŞIKLIK (2026-07-06, KONTROL-MAHKEMESİ FIX-2c — CENNETE GELDİK Mİ kanıtı):
            # adayın HERHANGİ bir geçişinin kendi/2-üst penceresinde GERÇEK-yönetmen etiketi
            # (_TRUE_DIR_RE, "PRODUCED WRITTEN DIRECTED BY" dahil) varsa NONFILM markerları onu
            # DÜŞÜREMEZ — çok-şapkalı kişinin (yön+yapımcı+DoP aynı kişi) diğer kartlarının
            # komşuluğu masum geçişi öldürüyordu. DUBLAJ kuralı DEĞİŞMEZ (geniş-pencere,
            # bağışıklığı bastırır — TILSIMLI dersi aynen korunur).
            _glob_imm = any(_TRUE_DIR_RE.search(" ".join(folded[max(0, _gi - 2):_gi + 1])) for _gi in _occ)
            for i in _occ:
                if True:
                    # DoP-fix (2026-07-03): '±1' niyetli dilim fiilen [i-1, i] idi — SONRAKİ satır hiç
                    # görülmüyordu; "İSİM üstte / DIRECTOR OF PHOTOGRAPHY altta" yerleşimi sızıyordu.
                    # Pencere [i-1, i+1]'e genişletildi. REGRESYON KALKANI: adayın kendi/2-üst satırında
                    # GERÇEK-yönetmen etiketi (_TRUE_DIR_RE) varsa DÜŞÜRME — "DIRECTED BY X" hemen ardından
                    # DoP satırı gelen klasik dizilişte gerçek yönetmen ölmesin (etiket-üstte yerleşim).
                    ctx = " ".join(folded[max(0, i - 1):i + 2])
                    # DUBLAJ GENİŞ-PENCERE (2026-07-03, TILSIMLI DÜNYA): "Dialogue Written and Directed
                    # by GREG SNEGOFF" OCR'da 4 satıra bölünür → dublaj-marker isimden 2-4 satır yukarıda.
                    # Dublaj markerlarına ÖZEL ±4 üst-pencere; bulunursa _TRUE_DIR_RE bağışıklığını BASTIRIR
                    # (o "Directed by" zaten dialogue-directed-by'dır). NONFILM markerları eski dar pencerede.
                    # SADECE ÜST-pencere (i-4..i): dublaj etiketi hep isimden ÖNCE gelir; isim-ALTINDAKİ
                    # sonraki kartın "Dialogue" etiketini yakalayıp masum yönetmeni düşürmeyi önler
                    # (TILSIMLI'de Macek'in ALTINDA Snegoff'un dialogue-kartı var → Macek düşmemeli).
                    _dub_lo = max(0, i - 4)
                    _blockers = [oi for oi in _other_occ if _dub_lo <= oi < i]
                    if _blockers:
                        _dub_lo = max(_blockers) + 1
                    dub_ctx = " ".join(folded[_dub_lo:i + 1])
                    if any(m in dub_ctx for m in _DUB_MARKERS):
                        is_nf = True
                        break
                    if any(m in ctx for m in markers):
                        imm = " ".join(folded[max(0, i - 2):i + 1])
                        if not _glob_imm and not _TRUE_DIR_RE.search(imm):
                            is_nf = True
                            break
        (dropped if is_nf else kept).append(d)
    return kept, dropped


# === _reasoning KALDIRMA (2026-07-11, plan rev.4 İP-3-devamı; Çağatay ONAYI) ===
# ÖLÇÜLMÜŞ GEREKÇE: frames-rerun 289-film koşusunda 13 TECHNICAL_FAILURE'ın HEPSİ >250-satır
# dev-künye (DEFİNE GEZEGENİ 744, YÜZÜKLERİN EFENDİSİ 629, SEVİMLİ KÖPEK 492...) — required-İLK
# _reasoning, num_predict bütçesini yiyip JSON'u yarıda kesiyordu (KARAR KİMİN kanıtı: model
# şema alanlarına hiç ulaşamadan done_reason=length). GERİ-DÖNÜŞ ANAHTARI (şartname):
# MITAS_REASONING=1 eski davranışı aynen geri getirir (rollback; A/B kötü çıkarsa).
SCHEMA_LEAN = {
    "type": "object",
    "properties": {
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["yonetmen", "yapimci", "oyuncular"],
}
SCHEMA_REASONING = {
    "type": "object",
    "properties": {
        "_reasoning": {"type": "string"},
        "yonetmen": {"type": "array", "items": {"type": "string"}},
        "yapimci": {"type": "array", "items": {"type": "string"}},
        "oyuncular": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["_reasoning", "yonetmen", "yapimci", "oyuncular"],
}


def _reasoning_on() -> bool:
    return os.environ.get("MITAS_REASONING", "0").strip().lower() in ("1", "true", "on", "yes")


def _schema():
    return SCHEMA_REASONING if _reasoning_on() else SCHEMA_LEAN


SCHEMA = SCHEMA_LEAN   # geri-uyum adı (statik import edenler için; canlı seçim _schema() ile)

PROMPT = """Aşağıda bir filmin jeneriğinden (künye) OCR ile okunan satırlar var. Satırlar BOZUK/eksik olabilir.
GÖREVİN: bu satırlardan YÖNETMEN, YAPIMCI ve baş OYUNCULARI çıkarmak — YENİDEN OKUMAK ya da bilgiden EKLEMEK DEĞİL.

KESİN KURALLAR:
0. BİÇİM (EN ÖNEMLİ): her isim GERÇEK "Ad Soyad" olmalı — en az İKİ kelime, gerçek bir insan. TEK kelime (yalnız ad VEYA yalnız soyad) YAZMA. Marka/şirket/stüdyo/logo adı (ör. Warner Bros, Lucasfilm, Columbia Pictures), sıfat, rol/etiket sözcüğü İSİM DEĞİLDİR — YAZMA. Emin değilsen o ismi atla.
1. SADECE aşağıdaki satırlarda GEÇEN isimleri kullan. Kendi bilginden/hafızandan İSİM EKLEME, TAHMİN ETME. Bir alan satırlarda yoksa boş liste [] ver.
2. Bir satır "KARAKTER_ADI OYUNCU_ADI" biçimindeyse (ör. "CAL MORSE SAM WATERSTON", "FLETCHER REEDE JIM CARREY", "MARGARET THATCHER MERYL STREEP"), yalnız OYUNCU (gerçek kişi) adını al; KARAKTER adını KOYMA. Tek başına KARAKTER/ROL adı görünüyorsa (ör. yalnız "FLETCHER REEDE" veya "MARGARET THATCHER") onu LİSTEYE KOYMA — sadece gerçek oyuncu adlarını ver.
2a. KARAKTER↔OYUNCU AYRIMI (oyuncu bloğunda ÇOK ÖNEMLİ):
   - AYRI SATIR DÜZENİ: Karakter adı ile oyuncu adı ARDIŞIK ayrı satırlardaysa (ör. üstte "Serebryakov" / altta "OLEG BASILASHVILI"; ya da "Vanya" / "Kirill Lavrov"), OYUNCU olanı al, KARAKTER satırını ATLA.
   - CASING İPUCU: Bir oyuncu bloğunda hem BÜYÜK HARF (ör. "CHARLES BRONSON", "OLEG BASILASHVILI") hem Baş-Harfi-Büyük (ör. "Jeb Maynard", "Carl Richards") isimler KARIŞIK haldeyse → BÜYÜK HARF olanlar genelde OYUNCU, Baş-Harfi-Büyük olanlar KARAKTER adıdır: yalnız BÜYÜK HARF (oyuncu) olanları al, Baş-Harfi-Büyük (karakter) olanları ATLA. AMA blok HOMOJEN ise (hepsi BÜYÜK HARF VEYA hepsi Baş-Harfi-Büyük) bu kural GEÇERSİZ — hepsi oyuncu olabilir, casing'e göre eleme YAPMA.
   - Bu iki alt-kural yalnız OYUNCU alanı içindir; yönetmen/yapımcı için uygulama.
3. Rol etiketleri (DIRECTED BY, PRODUCED BY, YÖNETMEN, YAPIMCI, CAST, STARRING, THE END, MUSIC BY, WRITTEN BY...) ve şirket/kurum adları (FILM, FILMS, PRODUCTION, PICTURES, STUDIO, MEDIA, TV) İSİM DEĞİLDİR — listeye koyma.
4. YÖNETMEN — şu kalıpların birinin YANINDAKİ/ALTINDAKİ GERÇEK kişi adı:
   - "DIRECTED BY <İSİM>", "A FILM BY <İSİM>", "A <İSİM> FILM" (ör. "A JOHN MCTIERNAN FILM" → John McTiernan), "AN <İSİM> FILM"
   - "YÖNETMEN", "YÖNETEN", "REJİSÖR", "UN FILM DE", "EIN FILM VON", "REGIE", "RÉALISÉ PAR"
   - Bileşik etiketler de yönetmen kartıdır: "WRITTEN AND DIRECTED BY", "WRITTEN, DIRECTED AND EDITED BY", "PRODUCED AND DIRECTED BY" — bu kartlardaki kişi(ler) YÖNETMENdir.
   Etiketin yanında BİRDEN FAZLA isim varsa (ör. "Directed by A, B" / "Written, Directed and Edited by Scandar Copti, Yaron Shani") HEPSİNİ yaz — iki eş-yönetmen normaldir, TEKE İNDİRME.
   DİKKAT — DUBLAJ TUZAĞI: "DIALOGUE DIRECTED BY", "DIALOGUE WRITTEN AND DIRECTED BY", "ADR DIRECTOR", "VOICE DIRECTOR" YÖNETMEN DEĞİLDİR (dublaj/seslendirme yönetmeni). Ekranda hem "WRITTEN AND DIRECTED BY <A>" hem "DIALOGUE ... DIRECTED BY <B>" varsa YÖNETMEN <A>'dır, <B> DEĞİL.
   "A <İSİM> FILM" kalıbında "FILM" kelimesi ETİKETtir; içindeki KİŞİ adını AL (kural 3'e takılıp atlama).
   YÖNETMEN DEĞİLDİR — KOYMA: "ASSISTANT DIRECTOR / 1ST / 2ND / FIRST / SECOND ASSISTANT DIRECTOR", "2ème/1er ASSISTANT RÉALISATEUR", "DIRECTOR OF PHOTOGRAPHY", "ART DIRECTOR", "CASTING (BY)", "MUSIC DIRECTOR", yardımcı/görüntü/müzik/yapım yönetmeni.
   HİKÂYE/SENARYO ETİKETİ DE YÖNETMEN DEĞİLDİR — KOYMA: "NACH EINER GESCHICHTE VON", "BASED ON A STORY BY", "D'APRÈS", "SCÉNARIO", "DREHBUCH", "SENARYO", "WRITTEN BY" (yalnız "WRITTEN AND DIRECTED BY" bileşik kartı yönetmendir).
   ETİKETİN ÜSTÜNDEKİ İSİM O ETİKETE AİT DEĞİLDİR: jenerik kartında etiket ÜSTTE, isim ALTTA olur. Bir ismin hemen ALTINDA yönetmen etiketi görüyorsan o isim BAŞKA bir role aittir — yönetmen o etiketin ALTINDAKİ isimdir.
   Bu kalıplardan hiçbiri NET değilse [] ver — ASLA oyuncu adı koyma, ASLA tahmin etme.
5. OYUNCULAR: jenerikte görünen GERÇEK oyuncu adları (gerçek insanlar; karakter/rol adları DEĞİL), en fazla __CAP__, görünme sırasıyla. Besteci/müzik, kurgu, senaryo, görüntü yönetmeni, yapımcı gibi EKİP üyeleri OYUNCU DEĞİLDİR — cast'e koyma.
6. YAPIMCI: "PRODUCED BY / EXECUTIVE PRODUCER / EXEC. PRODUCER / YAPIMCI / PRODUCER / EXECUTIVE YAPIMCI / PRESENTE / PRESENTS / PRESENTED BY / UNA PRODUZIONE" yanındaki GERÇEK KİŞİ adı. Besteci/müzik (COMPOSER/MUSIC BY), kurgu, senaryo YAPIMCI DEĞİLDİR — koyma. "Executive Producer / Yürütücü Yapımcı" GERÇEK YAPIMCI SAYILIR. "Associate Producer / Line Producer / Co-producer / Ortak yapımcı / Yardımcı yapımcı / Uygulayıcı Yapımcı" GERÇEK yapımcı SAYILMAZ — KOYMA.  # fix2-etiket 2026-06-29; Uygulayıcı=AYNADAKİ DÜŞMAN 2026-07-04

__CIKTI__

SATIRLAR:
%s
"""

_CIKTI_LEAN = """ÇIKTI: yalnız JSON (başka hiçbir şey yazma):
{"yonetmen": [...], "yapimci": [...], "oyuncular": [...]}"""

_CIKTI_REASONING = """ÇIKTI: yalnız JSON:
{"_reasoning": "<her satırı kısaca etiketle: YÖNETMEN / YAPIMCI / OYUNCU / EKİP-DİĞER>", "yonetmen": [...], "yapimci": [...], "oyuncular": [...]}
_reasoning bölümünde önce her satırın hangi role ait olduğunu sınıflandır, SONRA alanları doldur."""


def _cast_cap():
    """MITAS_CAST_CAP (default 10, 1-50 geçerli)."""
    try:
        c = int(os.environ.get("MITAS_CAST_CAP", "10") or 10)
        return c if 1 <= c <= 50 else 10
    except ValueError:
        return 10


def _llm_cast_ceiling():
    """PROMPT'a giden OYUNCULAR üst-sınırı — gerçek üretim cap'i (_cast_cap) DEĞİL, ondan kasıtlı
    daha yüksek bir tavan (2026-07-10, KARAR KİMİN/SANTRAL kökü — Opus canlı-yeniden-üretimle
    kanıtlandı). KANIT: _reasoning alanında model isimleri doğru 'OYUNCU' diye sınıflandırıyor
    (ör. KAKI HUNTER/THOMAS CARTER, DREW SNYDER/FRANCES BAY) AMA oyuncular[] dizisi tam
    _cast_cap() uzunluğunda KESİLİYOR — model PROMPT'taki 'en fazla N' talimatını harfiyen
    uygulayıp JSON-array'i N'inci isimde durduruyor; Python'un KENDİ sıra-koruyan cast[:_cap]
    kesimi (aşağıda read_credits_from_text/read_credits_auto) hiç devreye giremiyor çünkü
    girdi zaten eksik geliyor. Gerçek/ürün cap'i YİNE _cast_cap() ile UYGULANIR (bu fonksiyon
    yalnız modele daha az erken-durma payı verir; JSON-parse-fail/num_ctx riskini büyütmemek
    için sabit-büyük değil, cap'e göre ölçekli+sınırlı pay eklenir).
    2026-07-10 RİSK-DÜZELTMESİ: ilk deneme (+30) KARAR KİMİN'de (~90 satırlık _reasoning,
    çoğu EKİP-DİĞER) 3 denemeden 1'inde done_reason=length'e (TAM veri kaybı, num_ctx=8192
    taşması) yol açtı — VE o filmde başarılı denemelerde bile dizi hep AYNI 18 isimde durdu
    (ekstra pay hiç kullanılmadı, çünkü _reasoning zaten bütçenin çoğunu tüketiyor). Yani
    büyük pay o filmde SIFIR fayda + ölçülebilir risk getiriyordu. +8'e düşürüldü: BAŞKAN
    VE MARI/AŞK EVLİLİĞİ tipi 'birkaç aday üst-filtrede düşünce cap[:_cap] yedek bulamıyor'
    senaryosunu hâlâ karşılar, ama modele çok daha büyük bir hedef vermez."""
    return _cast_cap() + 8


def _prompt(text):
    """PROMPT şablonu + cap enjeksiyonu. 117-film taraması fix#1 (2026-07-03): 2026-06-29 cap-fix
    yalnız post-filtre [:8] kesimlerini düzeltmişti; LLM'e giden TALİMATTAKİ sözel 'en fazla 8'
    aynen kalmıştı → ~28 filmde 9.+ oyuncu daha ÇIKARIM aşamasında hiç üretilmiyordu (ADI CARMEN
    'avec' bloğunun 3. satırı, LOTR ana kadrosu vb.). Artık talimat da cap ile senkron.
    2026-07-10 KRİTİK-DÜZELTME: talimattaki sayı artık _cast_cap() (ürün cap'i) DEĞİL,
    _llm_cast_ceiling() (+8 paylı — bkz o fonksiyonun docstring'i, ilk +30 denemesi risk
    taşıdığı için küçültüldü). Gerçek kesim hâlâ _cast_cap() ile Python tarafında,
    sıra-koruyarak yapılır; bu satır yalnız modelin JSON-array üretimini ürün cap'inde
    ERKEN durdurmasını önler.
    2026-07-11 (_reasoning-kaldırma, ölçülmüş): ÇIKTI bloğu __CIKTI__ ile enjekte edilir —
    default LEAN (yalnız 3 alan; taşma-kaynağı satır-etiketleme yok), MITAS_REASONING=1 eskiyi getirir."""
    cikti = _CIKTI_REASONING if _reasoning_on() else _CIKTI_LEAN
    return (PROMPT % text).replace("__CAP__", str(_llm_cast_ceiling())).replace("__CIKTI__", cikti)


def _deepseek_json(model, prompt, timeout=120):
    """DeepSeek (API) JSON yanıtı — model adı 'deepseek*' ise. Anahtar yoksa {} (graceful)."""
    try:
        from _deepseek import deepseek_text
    except Exception:
        return {}
    txt = deepseek_text(prompt=prompt + "\n\nYALNIZ geçerli JSON döndür.",
                        model=model, temperature=0, max_tokens=1200,
                        fmt={"type": "json_object"}, timeout=timeout)
    if not txt:
        return {}
    try:
        return json.loads(txt)
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                return json.JSONDecoder().raw_decode(txt[i:])[0]
            except Exception:
                pass
    return {}


def _ollama_timeout(default=360) -> int:
    try:
        return max(60, int(os.environ.get("MITAS_OLLAMA_TIMEOUT", str(default)) or default))
    except Exception:
        return default


def _ollama_json_ex(model, prompt, schema, timeout=None, num_ctx=None):
    """İP-2 (2026-07-11, plan rev.4 — extraction_status sözleşmesi, 4-yutma-noktasının 1.'si):
    _ollama_json'un DURUM-TAŞIYAN sürümü. Döner: (data, meta).
      meta = {"status": "ok"|"technical_failure",
              "reason": None | "length" | "timeout" | "http" | "invalid_json",
              "done_reason", "prompt_eval_count", "eval_count", "model", "error"?}
    SÖZLEŞME: teknik-kaza (length/timeout/HTTP/parse-fail) ile "model bilinçli boş döndü"
    bir daha AYNI görünmez — KARAR KİMİN sınıfı sessiz veri-kaybının kökü buydu.
    Eski çağıranlar için _ollama_json sarmalayıcısı korunur (yalnız data döner)."""
    timeout = _ollama_timeout() if timeout is None else timeout
    meta = {"status": "technical_failure", "reason": None, "done_reason": None,
            "prompt_eval_count": None, "eval_count": None, "model": model}
    # İP-3 (2026-07-11, plan rev.4): determinizm-hijyeni + çıktı-bütçesi.
    #  • seed: ollama options'ta HİÇ yoktu (temp=0 tek başına GPU non-determinizmini kesmez;
    #    TOPLU GÖSTERİLER "VincenTe Minnati" flap'i bu sınıf). Resmî reproducible-outputs önerisi.
    #  • num_predict: çıktı bütçesi ayrılmadığından üretim ancak num_ctx penceresi dolunca
    #    kesiliyordu (KARAR KİMİN). 2048 rol-JSON'u için bol; aşarsa done_reason=length artık
    #    GÖRÜNÜR kaza (İP-2) + aşağıda tek-retry.
    #  • num_ctx: env'li (ölçüm-bazlı ayar altyapısı — prompt_eval_count telemetrisi birikince
    #    clamp formülü buraya bağlanır). Sabit-16384 konseyce REDDEDİLDİ (VRAM/OOM).
    if num_ctx is None:
        num_ctx = int(os.environ.get("MITAS_OLLAMA_NUM_CTX", "8192") or 8192)
    _opts = {"temperature": 0, "num_ctx": int(num_ctx),
             "seed": int(os.environ.get("MITAS_OLLAMA_SEED", "42") or 42),
             "num_predict": int(os.environ.get("MITAS_OLLAMA_NUM_PREDICT", "2048") or 2048)}
    meta["num_ctx"] = _opts["num_ctx"]
    payload = {
        "model": model, "prompt": prompt, "format": schema, "stream": False,
        "options": _opts,
        # VRAM-hijyeni (hızlandırma planı Faz-0, 2026-07-04): keep_alive env'den. DEFAULT "5m" =
        # ollama'nın ZATEN uyguladığı davranış → BYTE-NÖTR (çıktı değişmez); hız-modunda "15m" ile
        # 31b soğuk-start elenir. Sonnet çakışma-denetimi: GÜVENLİ-PARALEL (K1/kalkan mantığına
        # dokunmaz; _ollama_json salt HTTP-payload).
        "keep_alive": os.environ.get("MITAS_OLLAMA_KEEP_ALIVE", "5m"),
    }
    # Düşünme modeli (qwen3*, gemma-4) → think=False (zorunlu JSON `format` ile over-think çakışmasın).
    # gemma3 düşünme modeli DEĞİL → think gönderme (bazı sürümler 400 verir).
    _m = str(model).lower()
    if _m.startswith("qwen3") or _m.startswith(("gemma-4", "gemma4")):
        payload["think"] = False
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # timeout / bağlantı / HTTP hatası → TEKNİK-KAZA (bilinçli-boş DEĞİL)
        meta["reason"] = "timeout" if "timed out" in str(exc).lower() else "http"
        meta["error"] = f"{type(exc).__name__}: {exc}"
        sys.stderr.write(f"[ollama-json] TEKNIK-KAZA: {model} {meta['reason']}: {exc}\n")
        return {}, meta
    txt = resp.get("response", "")
    meta["done_reason"] = resp.get("done_reason")
    meta["prompt_eval_count"] = resp.get("prompt_eval_count")
    meta["eval_count"] = resp.get("eval_count")
    # done_reason=length, yanit tesadufen parse edilebilir JSON olsa bile TAMAMLANMIS degildir.
    # Parse'tan once reddet ki kesilmis nesne status=ok olamasin ve cagirandaki tek retry calissin.
    if resp.get("done_reason") == "length":
        meta["reason"] = "length"
        sys.stderr.write(
            f"[ollama-json] TEKNIK-KAZA: {model} cevap length ile kesildi "
            f"(JSON parse edilebilir olsa bile gecersiz; prompt_eval={meta['prompt_eval_count']}, "
            f"eval={meta['eval_count']})\n"
        )
        return {}, meta
    try:
        data = json.loads(txt)
        meta["status"] = "ok"
        return data, meta
    except Exception:
        i = txt.find("{")
        if i >= 0:
            try:
                data = json.JSONDecoder().raw_decode(txt[i:])[0]
                meta["status"] = "ok"
                return data, meta
            except Exception:
                pass
    # KRİTİK BULGU #4 (2026-07-09) → İP-2 (2026-07-11) ile KAPANDI: done_reason=="length" → num_ctx
    # prompt+yanıta yetmedi (KARAR KİMİN: _reasoning şema-önceliği bütçeyi yedi), JSON parse-fail.
    # ESKİ davranış: sessizce {} → çağıran boş/rescue sanıyordu (TOM SAWYER, BEYAZ AVUÇLAR — günlerce
    # fark edilmedi). YENİ: meta.status=technical_failure + reason=length/invalid_json TAŞINIR;
    # read_credits_auto → _pipe_credit_text → mitas_pipeline zinciri bunu görür (Hazır'a ASLA gidemez).
    meta["reason"] = "invalid_json"
    sys.stderr.write(
        f"[ollama-json] TEKNIK-KAZA: {model} JSON-parse basarisiz (reason={meta['reason']}, "
        f"done_reason={resp.get('done_reason')!r}, prompt~{len(prompt) if isinstance(prompt, str) else '?'} char, "
        f"yanit~{len(txt)} char, prompt_eval={meta['prompt_eval_count']}, eval={meta['eval_count']})\n"
    )
    return {}, meta


def _ollama_json(model, prompt, schema, timeout=None):
    """Geri-uyum sarmalayıcısı (romanizasyon vb. eski çağıranlar): yalnız data döner.
    YENİ kod _ollama_json_ex kullanmalı — durum bilgisi burada KAYBOLUR (bilinçli, dar kapsam)."""
    data, _meta = _ollama_json_ex(model, prompt, schema, timeout=timeout)
    return data


# ─── LATIN-DIŞI LLM ROMANİZASYON (2026-06-22, NAMUS DÜŞMANI) ─────────────────────────────────
# unidecode Arapça'yı sesli-harfsiz kabaya çevirir ("زكي آلاسيا"→"Zky Alsy") → extraction-LLM gibberish
# sanıp reddeder → cast boş kalır. ÇÖZÜM: çok-dilli qwen HAM non-Latin satırı DOĞRU Latin'e çevirsin
# ("Zeki Alasya"). Bu, OCR-otorite'nin İZİNLİ dönüşümü (kişi aynı, yalnız alfabe; credit_qc_block docstring).
# Sonuç DAİMA KONTROL'e gider (nonlatin_source gate) → human teyit eder (asla auto-ONAYLI). qwen başarısızsa
# çağıran taraf unidecode'a düşer (survival korunur). Fail-safe: hata → None.
_ROMANIZE_SCHEMA = {
    "type": "object",
    "properties": {"satirlar": {"type": "array", "items": {"type": "string"}}},
    "required": ["satirlar"],
}
_ROMANIZE_PROMPT = (
    "Aşağıdaki satırlar bir filmin jeneriğinden Latin-DIŞI alfabeyle (Arap/Kiril/Yunan) yazılmış "
    "metinlerdir; çoğu KİŞİ ADI (oyuncu/yönetmen/yapımcı). Her satırı DOĞRU LATİN-TÜRKÇE yazımına ÇEVİR "
    "(transkripsiyon): kişi/sözcük AYNI kalır, yalnız alfabe değişir. YENİ bilgi EKLEME, isim UYDURMA, "
    "satır ATLAMA, BİRLEŞTİRME. Her girdi satırı için TAM BİR çıktı satırı ver (sayı+sıra KORUNUR). "
    "Çıktı yalnız JSON: {\"satirlar\": [...]}.\n\nSATIRLAR:\n%s"
)


def _romanize_lines_llm(lines, model):
    """HAM non-Latin satırları çok-dilli qwen ile DOĞRU Latin'e çevir. Başarısızsa None (çağıran unidecode'a düşer).
    NOT (adversarial-doğrulama 2026-06-22): satır-sayısı KORUNMASI promptta istenir ama LLM garanti etmez →
    sapma sessiz isim kaybı/uydurma işareti olabilir; stderr'e uyarı yazılır (gözlemlenebilirlik). Romanizasyon
    halüsinasyonu (yanlış-isim ikamesi) içsel guard'larca SÜZÜLMEZ — nonlatin_source→KONTROL ile İNSANA devredilir
    (asla auto-ONAYLI). Çıktı yine de KORUNUR (kısmî > boş; insan teyit eder)."""
    lines = [str(l).strip() for l in (lines or []) if str(l).strip()]
    if not lines:
        return None
    try:
        raw = _ollama_json(model, _ROMANIZE_PROMPT % "\n".join(lines), _ROMANIZE_SCHEMA)
        out = raw.get("satirlar") if isinstance(raw, dict) else None
        if isinstance(out, list):
            out = [str(x).strip() for x in out if str(x).strip()]
            if out and len(out) != len(lines):    # satır-sayısı sapması → sessiz kayıp/uydurma şüphesi (gözlem)
                sys.stderr.write(f"[nonlatin-romanize] UYARI: satır sayısı sapması (girdi={len(lines)} "
                                 f"çıktı={len(out)}) → insan KONTROL teyidi şart\n")
            return out or None
    except Exception as e:  # noqa: BLE001 — fail-safe: romanizasyon başarısız → None → unidecode fallback
        sys.stderr.write(f"[nonlatin-romanize] {model} hata: {type(e).__name__}: {e}\n")
    return None


# Disclaimer/bağlaç/rol-etiketi kelimeleri — bir "isim"de geçiyorsa o cümle parçasıdır, isim DEĞİL.
# Deterministik junk-filtre (çok-dilli): LLM bazen "PELÍCULA SUBVENCİONADA POR EL" gibi disclaimer
# satırını cast'e koyuyor → exact-token eşleşmeyle düşür (alt-dize değil; "connery"≠"con").
_JUNK_WORDS = {
    "por", "the", "del", "della", "con", "apoyo", "subvencionada", "presenta", "presents",
    "presente", "avec", "mit", "und", "von", "par", "fund", "fondo", "support", "courtesy",
    "arrangement", "association", "produced", "directed", "production", "produccion", "pelicula",
    "film", "films", "colaboracion", "gracias", "thanks", "tarafindan", "destek", "katki", "sunar",
    "ile", "tarafından", "yapim", "yapimi", "music", "starring", "cast", "story", "screenplay",
    "written", "based", "company", "pictures", "studio", "media", "entertainment", "all", "rights",
    "performed", "mixed", "visual", "effects", "effect", "licensing", "license", "records",
    # TR rol-etiketi / ajans token'ları (bir "isim"de geçerse o etiket/kurum, kişi DEĞİL):
    "direktoru", "direktor", "yonetmeni", "yonetmen", "menajerlik", "menajer", "ajans", "ajansi",
    "ekibi", "amiri", "sefi", "sorumlusu", "operatoru", "koordinator", "kordinator", "muhendis",
    "teknisyen", "asistani", "yardimcisi", "supervisor", "coordinator", "manager", "designer",
    "casting", "editor", "mixer", "gaffer", "grip",
    # MİRAS (2010-9280) kökü, 2026-07-07: "ÖZEL EFEKT YÖNETMENİ" (Özel Efekt Yönetmeni Sorumlusu)
    # etiketi kesilip yalnız "OZEL EFEKT" kalınca ("yonetmeni" token'ı zaten JUNK'ta ama bu satırda
    # HİÇ okunmamış) _valid_person_name yanlışlıkla True dönüyordu (2 gerçek-token, junk-kontrolsüz).
    # "efekt" (TR "effect" karşılığı — İngilizce "effect/effects" zaten yukarıda vardı, TR eşi eksikti).
    "efekt",
    # YALNIZ TOM (1992-0484) kökü, 2026-07-07: ham OCR "lst Asst. Director" (garbled "1st Assistant
    # Director", isimsiz — bu satırda kimse yok) yönetmen-adayı olarak "LST ASST" (2 gerçek-token,
    # junk-kontrolsüz) çıktı. "asst" eklendi — İngilizce rol-kısaltması, gerçek isim-tokeni DEĞİL.
    "asst",
}


def _guard(names, ocr_fold_tokens, title_f):
    """Anti-halüsinasyon + junk-filtre: her ismin anlamlı tokenlarının TÜMÜ OCR metninde geçmeli;
    1-4 kelime; disclaimer/bağlaç kelimesi içermemeli. Aksi halde uydurma/çöp → atılır."""
    out, seen = [], set()
    for nm in names or []:
        nm = (nm or "").strip()
        if not nm:
            continue
        tk = _toks(nm)
        if not tk:
            continue
        # TÜM anlamlı tokenlar OCR metninde olmalı (halüsinasyon kalkanı)
        if not all(t in ocr_fold_tokens for t in tk):
            continue
        # isim 1-4 anlamlı kelime; daha uzunu cümle/disclaimer
        if len(tk) > 4:
            continue
        # disclaimer/bağlaç/etiket kelimesi içeren "isim" = cümle parçası → düş
        if any(t in _JUNK_WORDS for t in tk):
            continue
        if _fold(nm).strip() == title_f:  # film adının kendisi isim değil
            continue
        k = " ".join(tk)
        if k in seen:
            continue
        seen.add(k)
        out.append(nm)
    return out


# ─── F3: garble_audit.looks_garble import ───────────────────────────────────
# outputs/garble_audit.py script olarak yazılmıştır (if __name__== bloğu var).
# Sadece looks_garble + yardımcılarını yeniden tanımlamak en güvenli yol.
# (sys.path hack ile import etmek o dosyanın DB tarama kodunu çalıştırır → import-time yan etki)

import unicodedata as _uni

def _fold_ga(s: str) -> str:
    """garble_audit.fold() yerel kopyası (import-time yan etki yok)."""
    s = (s or "").replace("ı","i").replace("İ","i").replace("ş","s").replace("Ş","s")
    s = s.replace("ğ","g").replace("Ğ","g").replace("ç","c").replace("Ç","c")
    s = s.replace("ö","o").replace("Ö","o").replace("ü","u").replace("Ü","u")
    s = _uni.normalize("NFKD", s)
    s = "".join(c for c in s if not _uni.combining(c)).upper()
    s = re.sub(r"[^A-Z ]+"," ",s)
    return re.sub(r"\s+"," ",s).strip()

def _lev_ga(a: str, b: str) -> int:
    if a == b: return 0
    if not a: return len(b)
    if not b: return len(a)
    prev = list(range(len(b)+1))
    for i,ca in enumerate(a,1):
        cur=[i]
        for j,cb in enumerate(b,1):
            cur.append(min(prev[j]+1, cur[j-1]+1, prev[j-1]+(ca!=cb)))
        prev=cur
    return prev[-1]

# garble_audit.ROLE_INST — tam eşleşme blocklist (folded)
_GA_ROLE_INST = {
 "KUVVETLERI","SILAHLI","MUSTEREKEN","CEVIRDIGI","CEVIRME","TARAFINDAN","ORDU","ORDUSU",
 "DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","SENATORS","SENATOR","CHORUS","IORUS",
 "MAKEUP","MAKSUP","BASIGNER","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL","THEBAN",
 "PRODUCED","DIRECTED","SCREENPLAY","CAMERA","MUSIC","SOUND","COSTUME","COMPANY","STUDIO",
 "PICTURES","PRESENTS","STARRING",
 # EK (2026-06-20 garble-routing): müzik-kredi / departman / şirket-lisans token'ları (kişi-adı DEĞİL).
 # OCR-okuma gate'i (F3) erken eler + nihai routing sinyalini güçlendirir. Hepsi exact-token (güvenli).
 # NOT: gerçek-oyuncu SOYADIYLA çakışan token'lar KASTEN dışarıda — DRIVER (Adam/Minnie Driver),
 # CRAFT (Christine Craft), FOLEY (Scott/Dave Foley), RUNNER. "CRAFT SERVICES" zaten SERVICES ile yakalanır.
 "PERFORMED","MIXED","ENGINEERED","ARRANGED","RECORDED","MASTERED","COMPOSED","CONDUCTED",
 "ORCHESTRATED","COURTESY","LICENSING","RECORDS","SOUNDTRACK","SERVICES","PRODUCTIONS",
 "ENTERTAINMENT","STUDIOS","RIGHTS","RESERVED","COORDINATOR","SECURITY",
 "CATERING","WRANGLER","GAFFER","TRANSPORTATION","TRANSPORT","DEPARTMENT","FACILITIES",
 "STANDBY","ACCOUNTANT","PUBLICIST","CASTING","WARDROBE","STUNTS","RERECORDING",
 "SUPERVISING","VISUAL","EFFECTS","COLORIST","COLOURIST","DUBBING","DISTRIBUTED","DISTRIBUTION",
}
# Türkçe fiil/cümle eki
_GA_VERB_SUFFIX = ("DIGI","DUGU","DIGINI","ERKEN","EREK","MEKTE","MAKTA","TIGI","TUGU","MISTIR","MUSTUR")
# garbled rol-etiketi fuzzy referansları
_GA_ROLE_REF = ["DESIGNER","DIRECTOR","PRODUCER","EDITOR","OPERATOR","CAMERAMAN","SUPERVISOR","ASSISTANT","COMPOSER"]


def _looks_garble(name: str) -> str | None:
    """garble_audit.looks_garble() yerel kopyası — SADECE YÜKSEK-İSABET sinyaller."""
    f = _fold_ga(name)
    toks = f.split()
    if not toks:
        return None
    # cümle eki
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in _GA_VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    # rol/kurum/çöp token tam eşleşme
    hit = [t for t in toks if t in _GA_ROLE_INST]
    if hit:
        return f"rol/kurum/çöp token ({','.join(hit)})"
    # fuzzy garbled rol etiketi
    for t in toks:
        if len(t)>=6:
            for r in _GA_ROLE_REF:
                if 0 < _lev_ga(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None


def _sim_ga(a: str, b: str) -> float:
    a, b = _fold_ga(a), _fold_ga(b)
    m = max(len(a), len(b)) or 1
    return 1 - _lev_ga(a, b) / m


def _garble_reason_kb_gated(nm: str, kb) -> str | None:
    """_looks_garble() sinyali + KB güvenlik-valfi (2026-07-10, spawn_task task_73abb131 —
    SEIGNER~DESIGNER kökü, Mathilde Seigner AŞK EVLİLİĞİ'nde 2 karede tutarlı okunmuş halde
    fuzzy dala takılıp düşüyordu). SADECE fuzzy Levenshtein dalı ('garbled rol-etiketi (...)':
    distance<=2, 6+ harfli soyadlarla sık çakışır — KB-çapında census: 976 gerçek oyuncu/oyuncu
    tam-adı 9 referans kelimeyle çakışıyor) KB'de TAM AYNI ad gerçek oyuncu/oyuncu profiliyle
    kayıtlıysa None döner (muaf). Diğer iki _looks_garble sinyali (tam-token blocklist, TR
    fiil-eki) çok daha yüksek-isabetli → dokunulmadı. 296-film arşiv taramasında bu dalın
    SEIGNER dışındaki TÜM (310/311) çakışması gerçek rol-kelimesi yazım-hatası/çok-dilli
    varyanttı (KB'de tam-ad eşleşmesi yok) — muafiyet onları etkilemez.
    _apply_garble_gate'in HEM tekil-isim taramasında HEM near-dup tie-break'inde kullanılır —
    aksi halde near-dup adımı, tekil-taramada muaf tutulan bir ismi ham _looks_garble sinyaline
    bakıp geri düşürebilirdi (aynı KB-muafiyeti orada tekrarlanmazsa)."""
    g = _looks_garble(nm)
    if g and g.startswith("garbled rol-etiketi") and kb and _kb_has_actor_prof(nm, kb):
        return None
    return g


def _apply_garble_gate(names: list[str], kb=None) -> list[str]:
    """F3: garble olanı at; garble-varyant near-dup (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ) → garble'ı at temizi tut."""
    # 1. tek-isim garble taraması
    clean = []
    for nm in names:
        if _garble_reason_kb_gated(nm, kb) is None:
            clean.append(nm)
    # 2. near-dup garble-varyant: sim ∈ [0.6, 0.97), aynı token sayısı, her token benzer ama eşit değil
    out = list(clean)
    removed = set()
    for i in range(len(clean)):
        if i in removed:
            continue
        for j in range(i+1, len(clean)):
            if j in removed:
                continue
            fa, fb = _fold_ga(clean[i]), _fold_ga(clean[j])
            if fa == fb:
                # tam dedup — birini kaldır (j)
                removed.add(j)
                continue
            s = _sim_ga(clean[i], clean[j])
            if s < 0.6 or s > 0.97:
                continue
            ta, tb = fa.split(), fb.split()
            # Aynı token sayısı + HER token bound içinde (fa!=fb zaten üstte garanti → ≥1 token farklı).
            # NOT: '0 <' KOYMA — bir token fold'da eşit olabilir (KARAKAŞ/KARAKAÇ→KARAKAC), diğeri garble.
            if (len(ta) == len(tb) and len(ta) >= 1
                    and all(_lev_ga(x, y) <= max(2, len(x)//2) for x, y in zip(ta, tb))):
                ga = _garble_reason_kb_gated(clean[i], kb)
                gb = _garble_reason_kb_gated(clean[j], kb)
                if ga and not gb:
                    removed.add(i)
                elif gb and not ga:
                    removed.add(j)
                else:
                    # İkisi de _looks_garble=None: saf harf-bozulması OCR ÇİFT-OKUMASI
                    # (VAVIZ KARAKAC ≈ YAVUZ KARAKAŞ). Türkçe diakritik SAYISI fazla olanı KORU
                    # (OCR garble diakritiği kaybeder/bozar); eşitse ikisini de tut.
                    # GÜVENLİK: düşülecek isim KB'de gerçek OYUNCU ise DÜŞME (iki ayrı kişi olabilir).
                    _dia = lambda s: sum(c in "şŞıİğĞçÇöÖüÜ" for c in (s or ""))
                    di, dj = _dia(clean[i]), _dia(clean[j])
                    drop = j if di > dj else (i if dj > di else None)
                    if drop is not None and not (kb and _kb_has_actor_prof(clean[drop], kb)):
                        removed.add(drop)
    out = [nm for idx, nm in enumerate(clean) if idx not in removed]
    return out


# ─── F3 YAPIMCI için ROLE_INST ayrımı ────────────────────────────────────────
# Kurumsal yapımcı (TÜRK SİLAHLI KUVVETLERİ) gerçek olabilir → YAPIMCI'da sadece
# fiil-eki ve garble-varyant (near-dup) blocklist'i uygula, kurum-token ile kırma.
_GA_YAPIMCI_GARBLE_ONLY_TOKS = {
    "CEVIRDIGI","CEVIRME","MUSTEREKEN","FILMI","FILMHI","SANAK","PIIMIM","SOMR","ARSUANL",
    "PRODUCED","DIRECTED","PRESENTS","STARRING",
}

def _looks_garble_yapimci(name: str) -> str | None:
    """Yapımcı için özel garble: fiil-eki + üretim-etiketi tokenleri; kurum adı geçerse AT DEĞİL."""
    f = _fold_ga(name)
    toks = f.split()
    if not toks:
        return None
    for t in toks:
        if any(t.endswith(s) and len(t)>5 for s in _GA_VERB_SUFFIX):
            return f"cümle/fiil-eki ({t})"
    hit = [t for t in toks if t in _GA_YAPIMCI_GARBLE_ONLY_TOKS]
    if hit:
        return f"garble üretim-token ({','.join(hit)})"
    # fuzzy garbled rol-etiketi — yapımcıda da uygula
    for t in toks:
        if len(t)>=6:
            for r in _GA_ROLE_REF:
                if 0 < _lev_ga(t,r) <= 2:
                    return f"garbled rol-etiketi ({t}~{r})"
    return None


def _apply_garble_gate_yapimci(names: list[str]) -> list[str]:
    """Yapımcı için garble kapısı — kurum adını korur."""
    clean = []
    for nm in names:
        if _looks_garble_yapimci(nm) is None:
            clean.append(nm)
    # near-dup
    out = list(clean)
    removed = set()
    for i in range(len(clean)):
        if i in removed:
            continue
        for j in range(i+1, len(clean)):
            if j in removed:
                continue
            fa, fb = _fold_ga(clean[i]), _fold_ga(clean[j])
            if fa == fb:
                removed.add(j)
                continue
            s = _sim_ga(clean[i], clean[j])
            if s < 0.6 or s > 0.97:
                continue
            ta, tb = fa.split(), fb.split()
            if (len(ta) == len(tb) and len(ta) >= 1
                    and all(_lev_ga(x, y) <= max(2, len(x)//2) for x, y in zip(ta, tb))):
                ga = _looks_garble_yapimci(clean[i])
                gb = _looks_garble_yapimci(clean[j])
                if ga and not gb:
                    removed.add(i)
                elif gb and not ga:
                    removed.add(j)
                # else: ikisi de None → ikisini de tut (yapımcıda diakritik-tiebreak YOK, temkinli)
    return [nm for idx, nm in enumerate(clean) if idx not in removed]


# ─── F2: KB rol-filtresi (credit_video_read.KB) ──────────────────────────────
# KB'yi lazy import et; hata → filtre no-op (KB() zaten graceful)
_KB_INSTANCE = None

def _get_kb():
    global _KB_INSTANCE
    if _KB_INSTANCE is None:
        try:
            _scripts_dir = os.path.dirname(os.path.abspath(__file__))
            if _scripts_dir not in sys.path:
                sys.path.insert(0, _scripts_dir)
            from credit_video_read import KB
            _KB_INSTANCE = KB()
        except Exception:
            _KB_INSTANCE = _NullKB()
    return _KB_INSTANCE


class _NullKB:
    """KB yoksa graceful no-op: her verify → 'kayit-yok' (filtre geçir)."""
    def verify(self, name, role):
        return "kayit-yok"


# Non-acting meslek kümeleri — KB bu mesleklerden birini dönüyor ve oyunculuk İÇERMİYORSA cast'ten at.
# KB sadece "crew kökeni belli" olanı eler; 0-kayıt = belirsiz → filtre geçir.
_NON_ACTOR_PROFS = frozenset({
    "sound_department", "camera_department", "art_department", "costume_department",
    "editorial_department", "music_department", "visual_effects", "make_up_department",
    "production_manager", "script_and_continuity_department", "transportation_department",
    "electrical_department", "stunts", "special_effects", "set_decorator",
    # Bazen KB'de yönetmen/yapımcı dönebilir; cast'e koyulmuşsa yine de at.
    # (Yönetmen-cast karışıklığı F1'deki edge-case ile ele alınır, burada KB ile de yakalıyoruz.)
})
_ACTOR_PROFS = frozenset({"actor", "actress"})


def _kb_is_crew_not_actor(name: str, kb) -> bool:
    """KB net 'oyunculuk içermeyen ekip üyesi' diyorsa True → cast'ten at.
    0-kayıt / meslek-bos / hata → False (filtre geçir)."""
    try:
        result = kb.verify(name, "actor")
        if result in ("kayit-yok", "meslek-bos", "?", "ONAY"):
            return False
        # result == "RED": KB bu kişiyi "actor" değil dedi.
        # Ancak KB primaryProfession "producer/director" da diyebilir → bu durumda cast'ten at.
        # Ek kontrol: KB'deki professions setini doğrudan kontrol etmeliyiz.
        # credit_video_read.KB.verify() sadece ONAY/RED döndürüyor; profession setini açmıyor.
        # Biz RED gelmesi = "oyunculuk onaylanmadı" → ama KB "director" için RED verebilir.
        # Güvenli strateji: RED + KB üzerinde profession lookup
        if not kb.con:
            return False
        import unicodedata as _unn
        rows = kb.con.execute(
            "SELECT primaryProfession FROM names "
            "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        if not rows:
            return False
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        if not profs:
            return False
        # Oyunculuk var mı?
        if profs & _ACTOR_PROFS:
            return False  # oyuncu → geçir
        # Oyunculuk YOK ve non-actor meslek var → cast'ten at
        if profs & _NON_ACTOR_PROFS:
            return True
        return False
    except Exception:
        return False


def _kb_has_actor_prof(name: str, kb) -> bool:
    """KB primaryProfession actor/actress içeriyor mu? 0-kayıt/hata → False.
    (Başrol-yönetmen ayrımı + garble-varyant güvenliği için.)"""
    try:
        if not getattr(kb, "con", None):
            return False
        rows = kb.con.execute(
            "SELECT primaryProfession FROM names "
            "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [name]).fetchall()
        profs = set()
        for (p,) in rows:
            if p:
                profs.update(x.strip() for x in str(p).split(","))
        return bool(profs & _ACTOR_PROFS)
    except Exception:
        return False


def _apply_kb_cast_filter(cast: list[str], kb) -> list[str]:
    """F2: KB 'oyuncu değil ve ekip-meslekli' diyenleri at; 0-kayıt → geçir."""
    return [nm for nm in cast if not _kb_is_crew_not_actor(nm, kb)]


def _apply_kb_yapimci_filter(yapimci: list[str], kb) -> list[str]:
    """Yapımcı için: KB net 'yapımcı değil' diyorsa düşür; 0-kayıt → geçir."""
    out = []
    for nm in yapimci:
        try:
            r = kb.verify(nm, "producer")
            if r == "RED":
                # Ek kontrol: gerçekten hiç yapımcılık yok mu?
                if kb.con:
                    rows = kb.con.execute(
                        "SELECT primaryProfession FROM names "
                        "WHERE UPPER(strip_accents(primaryName))=UPPER(strip_accents(?))", [nm]).fetchall()
                    profs = set()
                    for (p,) in rows:
                        if p:
                            profs.update(x.strip() for x in str(p).split(","))
                    # Oyuncu olanı yapımcıdan at
                    if "actor" in profs or "actress" in profs:
                        continue
                    # Yapımcılık/yönetmenlik yok ama başka meslek de yok → geçir
                    if "producer" not in profs and "director" not in profs:
                        out.append(nm)  # belirsiz → geçir
                        continue
                    # Net yapımcı değil → at
                    continue
                else:
                    out.append(nm)  # KB yok → geçir
            else:
                out.append(nm)
        except Exception:
            out.append(nm)
    return out


# ─── F1: ENSEMBLE yönetmen fusion (credit_video_read.fuse() mantığı) ─────────

def _dedup_fold(seq: list[str]) -> list[str]:
    out: list[str] = []
    for x in seq:
        if not any(_fold(x) == _fold(y) for y in out):
            out.append(x)
    return out


def _kb_verify_flex(kb, name, role):
    """kb.verify + tek-harf KISALTMA toleransı — İKİ YÖNLÜ.
    (A) İHTİRAS 2026-07-04: query'de tek-harf ara-token varsa ATIP dener ('Bill L. Norton'→'Bill Norton'
        → kb.verify ONAY). Birincil ad AYNEN denenir; ONAY değilse ve tek-harf ara-token varsa (ilk+son
        korunarak) ara-başharfler atılıp yeniden denenir.
    (B) ANGOLA/ESCAPE FROM ANGOLA 2026-07-07 (Çağatay): TERS YÖN. Ekran jeneriği sade ad basar
        ('DIRECTED BY LESLIE MARTINSON') ama KB'de yönetmen tek-harf kısaltmayla kayıtlı
        ('Leslie H. Martinson'=director). Sade ad ise KB'de BAŞKA kişiye ('Leslie Martinson'=
        production dept) çarpıp RED alıyor → doğru okunan yönetmen düşüyordu. ÇÖZÜM: sade ad ONAY
        değilse, tek-harf token'ları (BAŞ veya ORTA — 'A. Manu Ginobili' de dahil) yok sayarak çekirdek
        ad+soyadı EŞİT olan rol-ONAY'lı KB kaydı ara. TEK ve NET aday varsa ONAY; ≥2 farklı kişi
        (belirsiz — 'Leslie H.' + 'Leslie B.') → DOKUNMA (yanlış>boş). Kill-switch: MITAS_KB_INITIAL_TOLERANS=0.
    FAIL-SAFE: her hata → birincil sonuç/'hata'."""
    try:
        r = kb.verify(name, role)
        if r == "ONAY":
            return r
        toks = [t for t in str(name).split() if t.strip()]
        # (A) query'den ara-başharf at (ilk+son korunur)
        if len(toks) >= 3:
            kisa = " ".join([toks[0]] + [t for t in toks[1:-1] if len(t.strip(". ")) > 1] + [toks[-1]])
            if kisa != name and kb.verify(kisa, role) == "ONAY":
                return "ONAY"
        # (B)/(C) KB-tarafı tek-harf kısaltma köprüsü: çekirdek ad+soyad eşit TEK rol-ONAY'lı kayıt → ONAY
        if os.environ.get("MITAS_KB_INITIAL_TOLERANS", "1").strip().lower() not in ("0", "false", "off", "no"):
            _folded = _fold(name).split()
            core = tuple(t for t in _folded if len(t) >= 2)   # çok-harfli token (ad/soyad)
            inits = tuple(t for t in _folded if len(t) == 1)  # tek-harf baş-harfler (sırayla)
            con = getattr(kb, "con", None)
            if con is not None and len(core) == 2:
                # (B) 2-token: sade ad ↔ KB kısaltmalı (Leslie Martinson ↔ Leslie H. Martinson)
                try:
                    like = f"{core[0].upper()}%{core[-1].upper()}"
                    rows = con.execute(
                        "SELECT DISTINCT primaryName FROM names "
                        "WHERE UPPER(strip_accents(primaryName)) LIKE ? LIMIT 400", [like]).fetchall()
                    approved = set()
                    for (pn,) in rows:
                        pn_core = tuple(t for t in _fold(pn).split() if len(t) >= 2)
                        if pn_core == core and kb.verify(pn, role) == "ONAY":
                            approved.add(_fold(pn))
                            if len(approved) >= 2:        # belirsizlik → köprü kurma
                                break
                    if len(approved) == 1:
                        return "ONAY"
                except Exception:  # noqa: BLE001 — köprü ASLA verify'ı bozmaz
                    pass
            elif con is not None and len(core) == 1 and inits and r != "RED":
                # (C) baş-harf-GENİŞLETME (Les Diaboliques/H.G. Clouzot): ekran soyad+baş-harf ("H.G. CLOUZOT")
                # → KB tam-adlı yönetmen ("Henri-Georges Clouzot"). Soyad EŞİT + query baş-harfleri KB ad-kısmı
                # baş-harflerinin PREFIX'i + TEK rol-ONAY'lı kayıt → ONAY. Pseudonym (Clucher, KB'de yok) → köprü YOK.
                # KRİTİK GATE (r != "RED", KOMİSER regresyon-fix 2026-07-07): baş-harf-genişletme İSMİ DEĞİŞTİRİR
                # (V.→Victor). Tam-isim ("V. Grigoryev") KB'de TANINIYORSA (RED=assistant_director) o kişidir →
                # farklı bir "Victor Grigoryev" director'a GENİŞLETME (yanlış>boş ihlali). Yalnız kayit-yok'ta köprü.
                import re as _re_c
                try:
                    surname = core[0]
                    rows = con.execute(
                        "SELECT DISTINCT primaryName FROM names WHERE UPPER(strip_accents(primaryName)) "
                        "LIKE ? AND primaryProfession LIKE '%director%' LIMIT 400", [f"%{surname.upper()}"]).fetchall()
                    approved = set()
                    for (pn,) in rows:
                        _pf = _fold(pn).split()
                        if not _pf or _pf[-1] != surname:          # soyad son-token EŞİT olmalı
                            continue
                        _given = " ".join(pn.split()[:-1])         # ad-kısmı (soyad hariç)
                        _gt = [w for w in _re_c.split(r"[^A-Za-zÀ-ÿ]+", _given) if w]  # tire+boşluk böl: Henri-Georges→[Henri,Georges]
                        _gi = tuple(_fold(w)[0] for w in _gt if _fold(w))
                        if _gi[:len(inits)] == inits and kb.verify(pn, role) == "ONAY":
                            approved.add(_fold(pn))
                            if len(approved) >= 2:
                                break
                    if len(approved) == 1:
                        return "ONAY"
                except Exception:  # noqa: BLE001
                    pass
        return r
    except Exception:  # noqa: BLE001
        return "hata"


_ROL_PROF = {"director": "%director%", "actor": "%act%", "actress": "%act%",
             "producer": "%produc%"}


def _kb_fuzzy_canonical_multi(kb, name, role="director", pool_lines=None):
    """ÇOK-VARYANT + ROL-KISITLI FUZZY KANONİKLEŞTİRME (2026-07-06, Çağatay TOPLU GÖSTERİLER kökü).
    KÖK-BULGU: OneOCR aynı ismi kareden kareye farklı okur ('VincenTe minneti/Minnati/minneLti')
    → stitch YANLIŞ varyantı seçer → tek-varyant fuzzy marjı düşük kalır (Minnati→Minnelli 0.94
    ama 2.'yle marj 0.004). ÇÖZÜM: ekrandan okunan TÜM varyantları topla + KB'yi ROL-KISITLI ara
    → en iyi varyant kazanır ('minneLti'→Vincente Minnelli 0.976 marj 0.05). Böylece "ekranda
    okuduğum PDF'e girer AMA yanlış değil, KB-kanonik + rol-teyitli" (Çağatay kuralı).
    Dönüş: (kanonik_isim, skor) güçlü-hit varsa; yoksa (None, en_iyi_jw).
    """
    con = getattr(kb, "con", None)
    if con is None:
        return (None, 0.0)
    prof = _ROL_PROF.get(role, "%director%")
    # VARYANT HAVUZU (2026-07-06 kök-fix, Çağatay 'Caldana→Judd böyle fuzzy olamaz' kanıtı):
    # KİRLENME BUG'ı — eski havuz "ilk-3-harf aynı" satırları topluyordu → CENNETE'de 'carolyn budd'
    # (BAŞKA kişi) 'carl caldana'nın havuzuna sızdı, Carolyn Judd'a eşlenip yönetmen sanıldı.
    # DOĞRU KURAL: varyant = ADIN KENDİSİNE fuzzy-benzeyen satır (jw≥0.85). Böylece yalnız AYNI
    # ismin OCR-varyantları toplanır ('minneti/Minnati/minneLti' hepsi birbirine ≥0.85); farklı
    # kişi (jw 0.67) HAVUZA GİREMEZ. difflib ile ucuz ön-eleme + jaro_winkler doğrulama.
    import difflib as _dl
    _fn = _fold(name)
    varyantlar = {_fn}
    con0 = con
    for ln in (pool_lines or []):
        lf = _fold(ln)
        toks = lf.split()
        if not (2 <= len(toks) <= 4) or len(lf) < 7 or lf in varyantlar:
            continue
        if _dl.SequenceMatcher(None, _fn, lf).ratio() < 0.72:   # ucuz ön-eleme
            continue
        try:
            jw = con0.execute("SELECT jaro_winkler_similarity(?, ?)", [_fn, lf]).fetchone()[0] or 0
        except Exception:  # noqa: BLE001
            jw = 0
        if jw >= 0.85:                                          # AYNI ismin OCR-varyantı
            varyantlar.add(lf)
    en_iyi = (None, 0.0)
    for q in varyantlar:
        if len(q) < 7 or " " not in q:
            continue
        try:
            rows = con.execute(
                "SELECT primaryName, primaryProfession, "
                "jaro_winkler_similarity(strip_accents(lower(primaryName)), ?) AS jw "
                "FROM names WHERE strip_accents(lower(primaryName)) LIKE ? AND primaryProfession LIKE ? "
                "AND length(primaryName) BETWEEN ? AND ? ORDER BY jw DESC LIMIT 3",
                [q, q[0] + "%", prof, len(q) - 3, len(q) + 3]).fetchall()
        except Exception:  # noqa: BLE001
            continue
        if not rows:
            continue
        top = rows[0][2] or 0.0
        marj = top - (rows[1][2] if len(rows) > 1 else 0)
        if top >= 0.90 and marj >= 0.03 and top > en_iyi[1]:
            en_iyi = (str(rows[0][0]), top)
    if en_iyi[0]:
        return en_iyi
    return (None, en_iyi[1])


def _kb_fuzzy_director_canonical(kb, name, pool_lines=None):
    """Geriye-uyum sarmalayıcı → çok-varyant rol-kısıtlı motora yönlendirir (director)."""
    return _kb_fuzzy_canonical_multi(kb, name, "director", pool_lines)


def _fuse_yonetmen(per_model: dict[str, list[str]], kb,
                   ekran_kunye_f: str = "", ekran_dilim_f: str = "",
                   pool_lines=None) -> tuple[list[str], str]:
    """
    Tüm modellerin yönetmen adaylarını birleştir:
      1. ≥2 modelde aynı → mutabakat (YÜKSEK güven)
      2. Tek model + KB-ONAY → al (ORTA güven)
      3. Çelişki (farklı isimler), KB-ONAY olanı seç; çoklu ONAY → hepsini al
      4. Hiçbiri KB-ONAY değilse tek okuma varsa al (DÜŞÜK güven)
      5. Çelişki + ONAY yok → [] (OKUNAMADI)

    EDGE-CASE — başrolu-yönetmen sanma:
      Bir yönetmen adayı cast listesinde üst sıralarda görünüyorsa ŞÜPHELI.
      Mutabakat yoksa ve sadece tek-model sinyali ise düşür.
      (Ör: Robert Redford başroldür, George Roy Hill yönetmendir.)
    """
    flat = [n for lst in per_model.values() for n in lst]
    if not flat:
        return [], "OKUNAMADI"

    all_flat = _dedup_fold(flat)

    # mutabakat: ≥2 modelde geçen
    agreed = [n for n in all_flat
              if sum(1 for lst in per_model.values()
                     if any(_fold(n) == _fold(x) for x in lst)) >= 2]
    if agreed:
        # KB-RED olanları çıkar
        agreed_ok = [n for n in agreed if _kb_verify_flex(kb, n, "director") != "RED"]
        return (agreed_ok or agreed), "YÜKSEK (mutabakat)"

    # Tek model veya çelişki: KB-ONAY olanı seç
    kb_ok = [n for n in all_flat if _kb_verify_flex(kb, n, "director") == "ONAY"]  # başharf-toleranslı (İHTİRAS 2026-07-04)
    if kb_ok:
        return kb_ok, "ORTA (KB-onay)"

    # ÇOK-VARYANT FUZZY-KANONİK (2026-07-06, Çağatay TOPLU GÖSTERİLER/Minnelli kökü):
    # KB tam-eşleşme yok AMA aday bir KB-YÖNETMENİNİN garble-okuması olabilir. Ekrandan okunan
    # tüm varyantları (pool_lines) + adayları KB'nin ROL-KISITLI kayıtlarına eşle; güçlü tek-kazanan
    # (skor≥0.90, marj≥0.03) varsa KANONİK yazımla al. "Ekranda okuduğum girer AMA yanlış değil,
    # KB-kanonik + rol-teyitli" (Çağatay). Uydurma-freni: rastgele garble KB'de rol-kısıtlı yüksek-
    # skorlu tek-kazanan bulamaz. Kill-switch: MITAS_FUZZY_KANONIK=0.
    if os.environ.get("MITAS_FUZZY_KANONIK", "1").strip().lower() not in ("0", "false", "off", "no"):
        # UYDURMA-FRENİ (2026-07-06 regresyon: 'Carl Caldana'→'Carolyn Judd' fabrikasyonu):
        # fuzzy-kanonik YALNIZ GARBLE-imzalı adaylara uygulanır. TEMİZ bir isim (düzgün Title-Case,
        # garble-yok) ZATEN DOĞRUDUR — KB tanımıyorsa bu KB-dışı gerçek kişidir, EŞLEME YAPMA
        # (aksi halde doğru ismi yanlış KB-komşusuna çevirir). Garble = kelime-içi büyük harf
        # ('minneLti') VEYA _looks_garble. Böylece yalnız BOZUK okumalar kanonikleşir.
        def _garble_imzali(_n):
            for _t in str(_n).split():
                if len(_t) >= 3 and not _t.isupper() and not _t.istitle() and any(c.isupper() for c in _t[1:]):
                    return True
            return _looks_garble(_n) is not None
        _kan_hits = []
        for n in all_flat:
            if not _garble_imzali(n):
                continue
            _k, _s = _kb_fuzzy_canonical_multi(kb, n, "director", pool_lines)
            if _k:
                _kan_hits.append((_k, _s))
        if _kan_hits:
            _kan_hits.sort(key=lambda x: -x[1])
            # tek güçlü kanonik-isim (farklı kanonik-isimler çıkarsa = belirsizlik → girme)
            _uniq = {_fold(h[0]) for h in _kan_hits}
            if len(_uniq) == 1:
                return [_kan_hits[0][0]], "ORTA (fuzzy-kanonik: ekran-garble→KB-yönetmen)"

    # ÇİFT-EKRAN-İMZA (2026-07-06, KONTROL-MAHKEMESİ FIX-2b — Çağatay anayasası: "framede
    # varsa PDF'e girer"): tek-model okuma + KB-kaydı-yok AMA aday İKİ BAĞIMSIZ ekran-okumasında
    # (kunye.txt VE dilim-korpus) harfiyen geçiyorsa bu "tek-okuma" SAYILMAZ — ekran çift-imzası.
    # LLM-uydurması (Asi→"John Platt" dersi) dilim-korpusta GEÇEMEZ → fabrikasyon freni korunur;
    # tek-güçlü-aday şartı (FUZZY-KB 1.5 ilkesi) + KB-RED (yanlış-meslek) yine engeller.
    # KANIT-VAKA: CENNETE GELDİK Mİ — "PRODUCED, WRITTEN & DIRECTED BY / CARL CALDANA" hem
    # kunye hem dilimde; KB tanımıyor diye yönetmen boş kalıyordu.
    if ekran_kunye_f and ekran_dilim_f:
        _cift = []
        for n in all_flat:
            nf = " ".join(_fold(n).split())
            # SAĞLAMLAŞTIRMA-a (2026-07-06 ön-kanıt): İSİM-ŞEKLİ şartı — GLORIA KUŞATMASI'nda
            # küçük-harf cümle-parçası ('exploded throughout an unsuspecting') geçmişti. Gerçek
            # kredi-isimleri Title-Case/CAPS'tir: HER token büyük harfle başlamalı; ayrıca
            # _valid_person_name + _rsc_name_ok (token sayısı/rol-parçası) uygulanır.
            _toks_n = str(n).split()
            if not all(t[:1].isupper() for t in _toks_n):
                continue
            # CASE-GARBLE imzası ('VincenTe Minnati' vakası): kelime-içi büyük harf, kelime ne
            # tam-CAPS ne Title-Case → OCR harf-karışması → GİRME (okunamadı>yanlış-oku; film
            # meşru-okunamadı Kontrol'ünde kalır). Mc/Di/Mac/De/La kalıbı (McDonald, DiCaprio)
            # türetilmiş-Title sayılır ve MUAFTIR.
            _cg_ok = re.compile(r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]{1,2}[A-ZÇĞİÖŞÜ][a-zçğıöşü]+$")
            def _case_garble(_t):
                if _t.isupper() or _t.istitle() or len(_t) < 3:
                    return False
                if _cg_ok.match(_t):
                    return False
                return any(c.isupper() for c in _t[1:])
            if any(_case_garble(t) for t in _toks_n):
                continue
            if not (_valid_person_name(n) and _rsc_name_ok(n)):
                continue
            if (len(nf) >= 7 and f" {nf} " in ekran_kunye_f and f" {nf} " in ekran_dilim_f
                    and _kb_verify_flex(kb, n, "director") != "RED"):
                _cift.append(n)
        if len(_cift) == 1:
            # SAĞLAMLAŞTIRMA-b: FUZZY-KB KANONİKLEŞTİRME — belirsizlik-bandı REDDEDİLDİ (Caldana'nın
            # bile 0.985'lik KB-komşusu var; jw-bandı ayırt edici değil). Yalnız GÜVENLİ kanonik-hit
            # (jw≥0.92+marj≥0.03+director) yazımı düzeltir; garble-eleme yukarıdaki CASE-GARBLE
            # imzasıyla deterministik yapılır.
            try:
                _kan, _topjw = _kb_fuzzy_director_canonical(kb, _cift[0])
                if _kan:
                    return [_kan], "ORTA (ekran-çift-imza: kunye+dilim, KB-kanonik)"
            except Exception:  # noqa: BLE001
                pass
            return _cift, "ORTA (ekran-çift-imza: kunye+dilim)"
    # Tek okuma AMA mutabakat yok + KB onayı yok → GÜVENİLMEZ → ABSTAIN.
    # (Eski "DÜŞÜK tek-okuma" KALDIRILDI: tek-model yanlış yönetmeni ONAYLI'ya koyup
    #  VL-fallback'i engelliyordu — Asi→"John Platt", Sessiz Ölüm→"A.M.Thompson". "yanlış>boş".)
    return [], "OKUNAMADI (tek-okuma, mutabakat/KB yok)"


# ── KESİN KURAL (Çağatay): yönetmen/yapımcı/cast'te YALNIZ gerçek "İsim Soyisim" ──
# ≥2 anlamlı token (isim+soyisim; orta-harf "E." serbest). TEK-TOKEN (sadece isim/soyisim) RED.
# Marka/logo/şirket/kurum/sıfat/rol-etiketi/garble RED. Aksi → liste dışı.
_NONPERSON_TOK = {
    "film", "films", "filmi", "filmleri", "production", "productions", "prod", "pictures", "picture",
    "studio", "studios", "media", "entertainment", "company", "co", "inc", "ltd", "llc", "gmbh", "srl",
    "tv", "yapim", "yapimi", "yapimevi", "yapimlari", "kuvvetleri", "silahli", "ordu", "ordusu",
    "kurumu", "vakfi", "dernegi", "bakanligi", "genel", "mudurlugu", "presents", "present", "sunar",
    "starring", "cast", "the", "and", "ile", "feat", "international", "group", "team", "pictures",
    "bros", "brothers", "sons", "enterprises", "enterprise", "corp", "corporation", "limited",
    "distribution", "releasing", "classics", "animation", "filmworks", "worldwide", "global",
    "networks", "network", "channel", "broadcasting", "partners", "associates",
    # kurum / vakıf / sendika / kuruluş (çok-dilli; gerçek "İsim Soyisim" token'ı değil)
    "foundation", "fondation", "fondazione", "stiftung", "agency", "agence",
    "association", "associazione", "guild", "union", "syndicate", "syndicat",
    "society", "societe", "societa", "institute", "institut", "instituto",
    "federation", "council", "conseil", "committee", "comite", "ministry",
    "ministere", "ministerio", "authority", "government", "gouvernement",
    "cinema", "cinematografica", "filmes", "filmproduktion", "produzione",
    "produktion", "telewizja", "presente", "presenta", "records", "rights", "reserved",
    # rol / sıfat / etiket
    "director", "directed", "producer", "produced", "executive", "associate", "yonetmen", "yapimci",
    "yoneten", "rejisor", "sunan", "anlatan", "music", "performed", "mixed", "visual", "effects",
    "effect", "licensing", "license", "records", "von", "der", "die",
}

# ── KAPI 1 — KARAKTER-ROL / TARİF ÇÖPÜ (2026-06-28) ─────────────────────────────
# Cast'e sızan karakter-tarifini ("GIRL AT DANCE", "SECOND GIRL", "IMMIGRATION OFFICER")
# OCR-otoritesini İHLAL ETMEDEN eler. TASARIM KARARI: token-bazlı rol-kelimesi reddi YASAK —
# birçok rol-kelimesi gerçek SOYADIDIR (Adam DRIVER, Mike JUDGE, Pat PRIEST, Gerard BUTLER).
# Yalnız YAPISAL olarak kesin desenler düşülür → hiçbir gerçek ada denk gelmez:
#   (1) situational edat ("at/in/on/of...") + ambiguous rol-ismi → "GIRL AT DANCE", "VOICE OF GOD"
#   (2) ordinal-önek ("FIRST/SECOND...") + ≥2 token → "SECOND GIRL", "FIRST POLICEMAN"
#   (3) tam-ifade çöp listesi (folded full-string; whack-a-mole ama %100 güvenli) → "FRENCH MAID"
# Flag MITAS_QC_ROLE_FILTER (modül-default OFF; _PROD_DEFAULTS + ps1'de ON). ADDITIVE: yalnız çöp
# düşürür, ad EZMEZ; kapatınca davranış birebir eskisi.
_ROLE_PREP = {"at", "in", "on", "of", "with", "near", "behind", "outside", "inside",
              "aboard", "atop", "beside", "among", "amongst", "to", "from"}
_ROLE_ORDINAL = {"first", "second", "third", "fourth", "fifth", "sixth", "seventh",
                 "eighth", "ninth", "tenth", "1st", "2nd", "3rd", "4th"}
# ambiguous rol-ismi: TEK BAŞINA red ETMEZ (Man Ho / Boy George korunur); yalnız edatla birleşince.
_AMBIG_ROLE_NOUN = {"man", "woman", "boy", "girl", "lady", "guy", "men", "women", "boys",
                    "girls", "kid", "child", "children", "people", "voice", "guard",
                    "officer", "soldier", "cop", "policeman", "policewoman", "maid",
                    "waiter", "waitress", "nurse", "driver", "doctor", "captain", "priest"}
# tam-ifade (folded) çöp: bare rol-etiketleri + kredi-konvansiyonları (exact match → gerçek ada çarpmaz).
_ROLE_PHRASE_EXACT = {
    "immigration officer", "police officer", "prison guard", "french maid",
    "night watchman", "himself", "herself", "themselves", "narrator",
}


def _role_filter_on() -> bool:
    return os.environ.get("MITAS_QC_ROLE_FILTER", "0").strip().lower() in ("1", "true", "on", "yes")


def _looks_character_role(name: str) -> bool:
    """True = karakter-tarifi/çöp (oyuncu ADI değil). Yalnız yapısal-kesin desen; gerçek ad düşürmez."""
    f = " ".join(_fold(name).split())
    if not f:
        return False
    if f in _ROLE_PHRASE_EXACT:                                              # (3) tam-ifade çöp
        return True
    toks = f.split()
    if any(t in _ROLE_PREP for t in toks) and any(t in _AMBIG_ROLE_NOUN for t in toks):  # (1)
        return True
    if toks[0] in _ROLE_ORDINAL and len(toks) >= 2:                          # (2) ordinal-önek
        return True
    return False


_VOWELS_FOLD = set("aeiouy")  # fold sonrası sesli harfler (ı→i zaten fold'da)


def _has_truncation_marker(tok: str) -> bool:
    """Token sesli-harf içermiyorsa VE len<=4 ise eksik/kısaltma belirteci sayılır.
    Örn: 'CHR' (CHRISTINE kırpılmış), 'ST' (STINE kırpılmış). # fix3-B 2026-06-29"""
    t = _fold(tok)
    return len(t) <= 4 and not any(c in _VOWELS_FOLD for c in t)


def _merge_split_names(names: list) -> list:
    """Ardışık iki isim girişinden ilki truncation-marker token içeriyorsa birleştir.

    KURAL (konservatif): names[i] içinde en az bir truncation-marker token VARSA
    VE names[i+1] tek-token ise
    VE birleşik isim _valid_person_name geçerse → birleştir.
    VETO: names[i] zaten tam-geçerli (_valid_person_name=True, toks>=2, hiçbir token
    truncation-marker değil) → birleştirme (ALLEGRO MICHELI + NICHETTI gibi iki ayrı kişiyi korur).
    # fix3-B 2026-06-29"""
    if not names:
        return names
    result = []
    i = 0
    while i < len(names):
        if i + 1 < len(names):
            a = (names[i] or "").strip()
            b = (names[i + 1] or "").strip()
            toks_a = [t for t in _fold(a).split() if t]
            toks_b = [t for t in _fold(b).split() if t]
            # İlk girişin tokenları arasında truncation-marker var mı?
            has_trunc = any(_has_truncation_marker(t) for t in toks_a)
            # İkinci giriş tek-token mi (gerçek bir soyadı parçası)?
            b_single = len(toks_b) == 1
            # VETO: a zaten tam-geçerli (2+ token, hiç truncation yok) → birleştirme
            a_complete = (len(toks_a) >= 2 and not has_trunc)
            if has_trunc and b_single and not a_complete:
                merged = a + " " + b
                # _valid_person_name henüz tanımlanmamış (altında) — direkt _fold+token sayısı
                merged_toks = [t for t in _fold(merged).split() if t]
                if 2 <= len(merged_toks) <= 4:  # sınır: _valid_person_name ile uyumlu
                    result.append(merged)
                    i += 2
                    continue
        result.append(names[i])
        i += 1
    return result


def _valid_person_name(name: str) -> bool:
    nm = (name or "").strip()
    if not nm or any(ch in nm for ch in "<>|/\\@&") or any(c.isdigit() for c in nm):
        return False
    toks = [t for t in _fold(nm).split() if t]
    real = [t for t in toks if len(t) >= 2]            # orta-harf (E.) serbest; ≥2 GERÇEK token şart
    # BAŞ-HARF-ÇOKLU İSİM (2026-07-07, BANA TRINITY DERLER/E.B. Clucher kökü, gözle-teyitli): eski
    # kural yalnız TEK orta-harfi ("John B. Smith") serbest bırakıyordu — "E. B. CLUCHER" (HER iki
    # ön-ad da baş-harfe inmiş, yalnız soyadı açık) real=1'e düşüp RED alıyordu. İSTİSNA: real TAM 1
    # VE geri kalan TÜM token'lar saf tek-harf alfabetik baş-harfse (rakam/junk değil, ≥1 tane) →
    # uzunluk-kapısı atlanır — NONPERSON/JUNK/garble kapıları AŞAĞIDA hâlâ çalışır ("E. B. FILM" gibi
    # junk-soyadlı sahte-adlar yine elenir; çıplak tek-token soyad — baş-harfsiz — hâlâ RED kalır).
    _init_only = [t for t in toks if len(t) == 1]
    _is_initials_name = (len(real) == 1 and bool(_init_only)
                          and len(_init_only) + len(real) == len(toks)
                          and all(t.isalpha() for t in _init_only))
    # 2026-07-06 (BAŞKAN VE MARI kökü): 4-token tavanı 'JEAN-DOMINIQUE DE LA ROCHEFOUCAULD' gibi
    # soylu/bağlaçlı adları RED'liyordu. 5-6 token YALNIZ soy-bağlacı içeriyorsa serbest; cümle-RED korunur.
    _VP_SOYBAG = {"de", "la", "le", "van", "von", "di", "del", "da", "dos", "el", "al", "bin", "der", "den"}
    if len(toks) > 6:
        return False
    if not _is_initials_name and len(real) < 2:        # tek-token RED, uzun-cümle RED
        return False
    if len(toks) > 4 and not _is_initials_name and not any(t in _VP_SOYBAG for t in toks):
        return False                                   # 5-6 token ama bağlaçsız = cümle şüphesi

    if any(t in _NONPERSON_TOK for t in toks) or any(t in _JUNK_WORDS for t in toks):
        return False
    if _looks_garble(nm):
        return False
    if _role_filter_on() and _looks_character_role(nm):     # KAPI 1: karakter-rol/tarif çöpü (flag'li)
        return False
    return True

def _only_persons(names):
    """KESİN KURAL süzgeci: yalnız geçerli 'İsim Soyisim' kalır."""
    return [n for n in (names or []) if _valid_person_name(n)]


_CAST_HEADER_RE = re.compile(r"^\s*(CAST|STARRING|OYUNCULAR|OYUNCU|OYNAYANLAR)\s*$", re.IGNORECASE)
_CAST_SKIP_RE = re.compile(r"^\s*\(?\s*(IN ORDER OF APPEARANCE|ORDER OF APPEARANCE)\s*\)?\s*$", re.IGNORECASE)
_CHARACTER_PREFIX_TOK = {
    "captain", "father", "first", "second", "third", "inn", "landlord", "officer", "doctor",
    "mrs", "mr", "miss", "young", "old", "older", "oldest", "boy", "girl", "man", "woman",
}


def _suffix_actor_from_role_line(line: str) -> str | None:
    """Return actor suffix from `ROLE/CHARACTER Actor Name` mixed-case OCR lines."""
    parts = [p.strip(" ,:;") for p in str(line or "").split() if p.strip(" ,:;")]
    if len(parts) < 3:
        return None
    for i in range(1, len(parts) - 1):
        prefix = parts[:i]
        if any(p and p[0].islower() for p in prefix):
            continue
        suffix = parts[i:]
        if not all(p and p[0].isupper() and any(c.islower() for c in p) for p in suffix):
            continue
        cand = " ".join(suffix)
        if _valid_person_name(cand):
            return cand
    return None


def _cast_block_candidate(line: str) -> str | None:
    line = str(line or "").strip()
    if not line or _CAST_SKIP_RE.match(line):
        return None
    lf = _fold(line)
    if _crew_context(lf):
        return None
    suffix = _suffix_actor_from_role_line(line)
    if suffix:
        return suffix
    toks = [t for t in lf.split() if t]
    if toks and toks[0] in _CHARACTER_PREFIX_TOK:
        return None
    if "." in line or " . " in line or " / " in line:
        return None
    raw_parts = [p.strip(" ,:;") for p in line.split() if p.strip(" ,:;")]
    if any(p and p[0].islower() for p in raw_parts):
        return None
    if _valid_person_name(line):
        return line
    return None


def extract_cast_block_candidates(lines: list[str], *, limit: int = 8) -> list[str]:
    """Deterministic fallback for visible CAST blocks when the LLM times out/abstains."""
    cleaned = [str(line).strip() for line in (lines or []) if str(line).strip()]
    out: list[str] = []
    for i, line in enumerate(cleaned):
        if not _CAST_HEADER_RE.match(line):
            continue
        misses_after_hit = 0
        for nxt in cleaned[i + 1:i + 90]:
            nf = _fold(nxt)
            if _CAST_HEADER_RE.match(nxt) or _CAST_SKIP_RE.match(nxt):
                continue
            if _crew_context(nf) and len(out) >= 3:
                break
            cand = _cast_block_candidate(nxt)
            if cand:
                out.append(cand)
                out = _dedup_fold(out)
                misses_after_hit = 0
                if len(out) >= limit:
                    return out[:limit]
            elif out:
                misses_after_hit += 1
                if misses_after_hit >= 12 and len(out) >= 3:
                    break
        if out:
            return out[:limit]
    return []


# ── QC1 SATIR-ÖN-ELEMESİ (Çağatay 2026-06-15): gürültü PDF'e hiç girmesin ──
# Disclaimer/telif/courtesy/teşekkür/sendika/teknik-marka satırlarını LLM'e GÖNDERMEDEN at.
# Bunlar çok-kelimeli YASAL/TEKNİK kalıp — gerçek "İsim Soyisim" bu kalıplara girmez → SIFIR regresyon.
# (Tek-token marka isimleri DEĞİL; yalnız bariz kalıp-içeren satırlar. İsim satırına dokunmaz.)
_PREFILTER_PHRASES = (
    "COURTESY OF", "IN ASSOCIATION WITH", "EN ASSOCIATION", "AVEC LA PARTICIPATION",
    "WITH THE PARTICIPATION", "IN COLLABORATION WITH", "PROVIDED BY", "STOCK FOOTAGE",
    "ALL RIGHTS RESERVED", "TOUS DROITS", "COPYRIGHT", "SPECIAL THANKS", "THANKS TO",
    "DEDICATED TO", "IN MEMORY OF", "IN LOVING MEMORY", "NO ANIMALS WERE",
    "FILMED ON LOCATION", "SHOT ON LOCATION", "FILMED IN", "RECORDED AT",
    "DOLBY DIGITAL", "DOLBY STEREO", "DTS DIGITAL", "ULTRA STEREO",
    "BASED ON ", "BASED UPON", "MOTION PICTURE ASSOCIATION",  # 2026-07-07 KOVBOY: 'BASED ON THE' dardı,
    # 'BASED ON MY REMINISCENCES...BY FRANK HARRIS' (THE değil MY) kaçıyordu → yazar director-adayı sanıldı.
)
_PREFILTER_MARK = ("©", "®", "™")


def _prefilter_lines(lines):
    """LLM'e girmeden bariz disclaimer/yasal/teknik satırları ele (kişi-adı DEĞİL)."""
    out = []
    for ln in (lines or []):
        u = _fold(ln).upper()
        if any(p in u for p in _PREFILTER_PHRASES):
            continue
        if any(s in ln for s in _PREFILTER_MARK):
            continue
        out.append(ln)
    return out


_RSC_LABELS = {"DIRECTED BY", "YONETMEN", "YONETEN", "REJISOR",
               "UN FILM DE", "EIN FILM VON", "REGIE", "REALISE PAR"}
_RSC_VETO = ("PRODUCED BY", "EXECUTIVE PRODUCER", "ASSOCIATE PRODUCER", "LINE PRODUCER",
             "CO PRODUCER", "COPRODUCER", "ASSISTANT DIRECTOR", "SECOND UNIT", "2ND UNIT",
             "DIRECTOR OF PHOTOGRAPHY", "ART DIRECTOR", "MUSIC DIRECTOR", "CASTING")
_RSC_DIRF = ("DIRECTED BY", "YONETMEN", "YONETEN", "REJISOR", "REALISE PAR", "UN FILM DE", "EIN FILM VON",
             # OKUNAMADI-röntgeni (2026-07-06, BAŞKAN VE MARI kanıtı): FR/DE/IT ana-yönetmen
             # etiketleri sözlükte yoktu → filmler haksız "okunamadı" sayılıyordu.
             "MISE EN SCENE", "REALISATION", "REGIA DI", "REGIE")


_RSC_KOMBINE_VETO = {"SECOND", "2ND", "UNIT", "ASSISTANT", "CASTING", "DIALOGUE", "DUBBING"}

# TEK-KAYNAK BAĞLAMA (2026-07-06, Çağatay "sözlüğü doldur" + BAŞKAN VE MARI kökü): lexicon
# ÇOK-DİLLİ DIRECTOR listesi zengindi ama rescue kendi dar _RSC_DIRF'ini kullanıyordu → FR
# "MISE EN SCENE" gibi kartlar rescue'da görünmezdi. Artık rescue-etiket eşleyicisi lexicon'a
# bağlı (EXCLUDE vetoları dahil). Lexicon import edilemezse eski dar listeyle devam (fail-safe).
try:
    import credit_role_lexicon as _rsc_lex
    _LEX_DIR = tuple(sorted({_rsc_lex.norm(x) for x in _rsc_lex.DIRECTOR if len(_rsc_lex.norm(x)) >= 5},
                            key=len, reverse=True))
    _LEX_EXC = tuple({_rsc_lex.norm(x) for x in _rsc_lex.EXCLUDE})
except Exception:  # noqa: BLE001
    _LEX_DIR, _LEX_EXC = (), ()


def _rsc_label_fuzzy(_f):
    """Bulanık yönetmen-etiketi: tam eşleşme + 'DIRECTED ' öneki (TY/DY/8Y garble) + ratio≥0.85.
    KOMBİNE-ETİKET (2026-07-06, KONTROL-MAHKEMESİ FIX-2): "PRODUCED, WRITTEN & DIRECTED BY" /
    "DIRECTED & PHOTOGRAPHED BY" gibi birleşik kartlar 24-karakter tavanına takılıp KAÇIYORDU
    (CENNETE GELDİK Mİ kanıtı: isim yapımcıya girdi, yönetmen boş kaldı). Ayrık 'DIRECTED'+'BY'
    token'lı ≤48-kr satır yönetmen-etiketi sayılır; yan-ünite/asistan/dublaj VETOLU
    ("DIRECTOR OF PHOTOGRAPHY"/"ASSISTANT DIRECTOR" zaten kalıba girmez)."""
    if not _f:
        return False
    # SİNEMATOGRAF VETO (2026-07-07, BİR BEBEK EVİ/Joseph Losey kökü): docstring "DIRECTOR OF
    # PHOTOGRAPHY zaten kalıba girmez" derken bunu VARSAYIYORDU ama garble ("director of phon",
    # "DIRECTOR OI PHEN", "DIRECTOR E/ PHAH") aşağıdaki fuzzy/lexicon dallarından SIZIYORDU →
    # rescue görüntü-yönetmeni satırını gerçek yönetmen sanıp yanındaki garble'ı (OI PHEN) isim
    # olarak çekiyordu (gerçek yönetmen "director" tek-kelime etiketi daha SONRA geliyordu, hiç
    # bulunmuyordu). Desen: "DIRECTOR" + herhangi bir sonraki token "PH..." ile başlıyor → HER ZAMAN
    # görüntü-yönetmeni garble'ı (gerçek yönetmen etiketi asla "DIRECTOR PH..." biçiminde olmaz).
    _tf0 = _f.split()
    if _tf0 and _tf0[0] == "DIRECTOR" and len(_tf0) >= 2 and any(t.startswith("PH") for t in _tf0[1:]):
        return False
    # ANİMASYON VFX-ÜNVANI VETOSU (2026-07-07, FERDİNAND/"LEAD ENVIRONMENTAL TECHNICAL DIRECTOR"
    # kökü, gözle-teyitli): animasyon jeneriklerinde "DIRECTOR" kelimesi departman-lideri ünvanlarında
    # geçer (film-yönetmeni DEĞİL). Yalnız SOMUT-KANITLI kelimeler eklendi (spekülatif genişletme
    # YOK — açık-uçlu liste riski bilinçle sınırlandı); "DIRECTOR" satırın SONUNDA (etiket ...DIRECTOR
    # biçiminde, isim ayrı satırda) ve satırda bu departman-sıfatlarından biri geçiyorsa veto.
    _VFX_DEPT_ADJ = {"TECHNICAL", "ENVIRONMENTAL"}
    if "DIRECTOR" in _tf0 and (_tf0[-1] == "DIRECTOR" or _tf0[-1] == "DIRECTORS") and (_VFX_DEPT_ADJ & set(_tf0)):
        return False
    if len(_f) <= 48:
        _tf = _f.split()
        if "DIRECTED" in _tf and "BY" in _tf and not (_RSC_KOMBINE_VETO & set(_tf)):
            return True
        # ÇOK-DİLLİ lexicon-eşleşme (2026-07-06): satır bir lexicon-DIRECTOR başlığına eşit ya da
        # onunla başlıyorsa VE alt-rol (EXCLUDE) / yan-ünite vetosu yoksa → yönetmen-etiketi.
        if _LEX_DIR and not (_RSC_KOMBINE_VETO & set(_tf)) and not any(x in _f for x in _LEX_EXC):
            for _L in _LEX_DIR:
                if _f == _L or _f.startswith(_L + " "):
                    return True
    if len(_f) > 24:
        return False
    if _f in _RSC_LABELS or _f.startswith("DIRECTED "):
        return True
    import difflib as _dl
    return any(_dl.SequenceMatcher(None, _f, _L).ratio() >= 0.85 for _L in _RSC_DIRF)


_RSC_BAD_TOK = {"OF", "BY", "THE", "AND", "WITH", "FOR", "IN", "UNIT", "UNITS"}
# APOLLO 11 kökü (2026-07-12, canlı-üretimle: rescue '2ND UNIT DIRECTOR' garble'ından 'ND UNIT'
# üretiyordu — veto 'SECOND UNIT'/'2ND UNIT' vardı ama garble '2' düşünce 'ND UNIT' kalıp sızıyordu,
# LOTR 'directes by' deseninin aynısı). "UNIT" token + "ASSIST/SUPERVIS/COORDINAT/OPERATOR" alt-dize
# (asistan-yönetmen/2.-ünite/koordinatör/operatör rol-parçaları) EKLENDİ → garble-varyantları da kapar.
_RSC_BAD_SUB = ("PHOTOGRAPH", "HOTOGRAPH", "OTOGRAPH", "CASTING", "EDITOR", "PRODUC",
                "DIRECT", "MUSIC", "DESIGN", "SOUND", "COSTUME", "MAKEUP", "EFFECT", "STUNT",
                "ASSIST", "SUPERVIS", "COORDINAT", "OPERATOR")


def _rsc_name_ok(cand):
    """Rescue aday-sağlamlığı (SHERLOCK kanıtı: bölünmüş 'OF P HOTOGRAPHY' kişi-adı sanılmıştı):
    tek-harfli token YOK, bağlaç-token YOK, rol-sözcüğü parçası YOK.
    2026-07-06 (BAŞKAN VE MARI kökü): 4-token tavanı 'JEAN-DOMINIQUE DE LA ROCHEFOUCAULD' gibi
    Fransız/İspanyol soylu adlarını RED'liyordu → tavan 6; 'DE/LA/VAN/VON/DI/DEL' küçük-bağlaçları
    isim-parçası sayılır (BAD_TOK'tan muaf)."""
    toks = (cand or "").split()
    if not (2 <= len(toks) <= 6):
        return False
    _SOY_BAG = {"DE", "LA", "LE", "VAN", "VON", "DI", "DEL", "DA", "DOS", "EL", "AL", "BIN"}
    up_toks = _fold_ga(cand).split()
    if any(len(t) < 2 for t in toks):
        return False
    if any(t in _RSC_BAD_TOK and t not in _SOY_BAG for t in up_toks):
        return False
    up = _fold_ga(cand)
    return not any(b in up.replace(" ", "") for b in _RSC_BAD_SUB)


def _yon_rescue_auto(lines, raw_context_lines, cast, yap, ocr_tokens, title_f):
    """AUTO-yolu deterministik yönetmen-kurtarma (2026-07-04; SHERLOCK/MÜREKKEP kanıtları).
    (A) lexicon A-X-FILM ters-desen — LLM-girdisi + HAM bağlam (kart tek-satır kendinden-etiketli;
        stüdyo-bumper dışlanır). Çift-rol: cast'te → VETO, yalnız yapımcıda → İZİN.
    (B) bulanık DIRECTED-etiketi ±1 satır (İngiliz isim→rol düzeni dahil). Aynı çift-rol kuralı.
    Dönen: kurtarılan [isim] veya []. Her hata → [] (ana akış BOZULMAZ)."""
    try:
        cast_taken = {" ".join(_toks(x)) for x in (cast or [])}
        # (A) kendinden-etiketli kart
        import credit_role_lexicon as _lexr
        for _ln in list(lines or []) + [x for x in (raw_context_lines or []) if x]:
            _cand = _lexr.director_name_from_line(_ln)
            if not _cand or _looks_garble(_cand) is not None or not _valid_person_name(_cand):
                continue
            if not _rsc_name_ok(_cand):
                continue
            if " ".join(_toks(_cand)) in cast_taken:
                continue
            _g = _guard([_cand], ocr_tokens, title_f)
            if _g:
                return _g
        # (B) bulanık etiket ±1
        _ls = [l for l in (lines or []) if l and l.strip()]
        for _i, _ln in enumerate(_ls):
            if not _rsc_label_fuzzy(_fold_ga(_ln)):
                continue
            # LAUREL HARDY yaması (2026-07-05): +1 garble ise ('FLE') +2'yi de dene (tek garble-satır
            # atlama: 'Directed by / FLE / ALFRED WERKER'); -1 en SON çare kalır.
            for _j in (_i + 1, _i + 2, _i - 1):
                if _j < 0 or _j >= len(_ls):
                    continue
                _nb = _ls[_j]
                _nbf = _fold_ga(_nb)
                if any(_v in _nbf for _v in _RSC_VETO) or _rsc_label_fuzzy(_nbf):
                    continue
                # LAUREL HARDY yaması (2026-07-05): aday, HERHANGİ bir rol-etiketinin garble'ı olabilir
                # ('Art Dirg fio' ≈ 'ART DIRECTION' 0.85+) → fuzzy-etiket-vetosu (yalnız DIRECTOR değil).
                import difflib as _dlv
                _ROLE_VETO_F = ("ART DIRECTION", "MUSICAL DIRECTION", "SET DECORATIONS", "FILM EDITOR",
                                "SCREEN PLAY BY", "ORIGINAL STORY BY", "SOUND", "COSTUMES")
                if any(_dlv.SequenceMatcher(None, _nbf, _rv).ratio() >= 0.78 for _rv in _ROLE_VETO_F):
                    continue
                if _looks_garble(_nb) is not None or not _valid_person_name(_nb):
                    continue
                if not _rsc_name_ok(_nb):
                    continue
                if " ".join(_toks(_nb)) in cast_taken:
                    continue
                _g = _guard([_nb], ocr_tokens, title_f)
                if _g:
                    return _g
    except Exception:  # noqa: BLE001 — kurtarma hatası asla akışı bozmaz
        return []
    return []


def read_credits_from_text(lines, title="", model=None, *, dizi=False):
    model = model or DEFAULT_MODEL
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    text = "\n".join(lines)
    ocr_tokens = set(_toks(text))
    title_f = _fold(title).strip()
    out = {"yonetmen": [], "yapimci": [], "cast": [], "guven": "OKUNAMADI", "model": model}
    if not lines:
        out["hata"] = "bos_metin"
        return out
    try:
        if str(model).startswith("deepseek"):
            raw = _deepseek_json(model, _prompt(text))
        else:
            raw = _ollama_json(model, _prompt(text), _schema())
    except Exception as e:
        out["hata"] = f"{type(e).__name__}: {e}"
        return out
    out["ham"] = raw
    yon = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
    yap = _guard(raw.get("yapimci"), ocr_tokens, title_f)
    cast = _guard(_merge_split_names(raw.get("oyuncular") or []), ocr_tokens, title_f)  # fix3-B 2026-06-29

    # C-fix 2026-06-29 — deterministik yönetmen-rescue (LLM boş döndürdüğünde OCR satırından çıkar)
    # KURALLAR: +1-only pencere; 'A FILM BY'/'A * FILM' rescue-setinde YOK (oyuncu/şirket komşuluğu);
    # +1 yapım/yardımcı etiketi içeriyorsa VETO; aday cast/yap'ta varsa VETO (çift-rol engeli).
    # HOTEL RWANDA beklenen davranış: DIRECTED BY(34) +1 = PRODUCED BY → VETO → yon=[] kalır (DOĞRU).
    if not yon and os.environ.get("MITAS_DIRECTOR_RESCUE", "1") != "0":
        _RESCUE_LABELS = {
            "DIRECTED BY", "YONETMEN", "YONETEN", "REJISOR",
            "UN FILM DE", "EIN FILM VON", "REGIE", "REALISE PAR",
        }
        _RESCUE_VETO = (
            "PRODUCED BY", "EXECUTIVE PRODUCER", "ASSOCIATE PRODUCER",
            "LINE PRODUCER", "CO PRODUCER", "COPRODUCER",
            "ASSISTANT DIRECTOR", "SECOND UNIT", "2ND UNIT",
            "DIRECTOR OF PHOTOGRAPHY", "ART DIRECTOR",
            "MUSIC DIRECTOR", "CASTING",
        )
        # cast + yap dedup-veto: normalize → fold (≥3-char token'lar) birleşimi
        _taken = {" ".join(_toks(x)) for x in (cast + yap)}
        for _i, _ln in enumerate(lines):
            if _fold_ga(_ln) not in _RESCUE_LABELS:   # TAM eşleşme (substring DEĞİL)
                continue
            if _i + 1 >= len(lines):
                continue
            _nb = lines[_i + 1]
            _nbf = _fold_ga(_nb)
            if any(_v in _nbf for _v in _RESCUE_VETO):  # +1 yapım/yardımcı etiketi → veto
                continue
            if _looks_garble(_nb) is not None:
                continue
            if not _valid_person_name(_nb):
                continue
            _g = _guard([_nb], ocr_tokens, title_f)
            if not _g:
                continue
            if " ".join(_toks(_nb)) in _taken:          # oyuncu/yapımcı=yönetmen çelişkisi → veto
                continue
            yon = _g
            break

        # RESCUE-2 (2026-07-04, MÜREKKEP YÜREK kanıtı: "AN IAIN SOFTLEY FILM" satırı kunye'de ama LLM
        # yapımcı-bloğu yüzünden kaçırdı): lexicon'un stüdyo-dışlamalı ters-desen çıkarıcısı
        # (A/AN/BIR <İSİM> FILM → isim; A WALT DISNEY FILM → boş). ÇİFT-ROL kuralı: aday CAST'te ise
        # VETO (oyuncu=yönetmen şüphesi KORUNUR); yalnız YAPIMCI'da ise İZİN — yönetmen+yapımcı meşru
        # (Musker/Conli emsali) ve A-X-FILM kartı güçlü yönetmen kanıtıdır.
        if not yon:
            try:
                import credit_role_lexicon as _lex2
                _cast_taken = {" ".join(_toks(x)) for x in cast}
                # ARAMA-UZAYI: LLM-girdisi + HAM-bağlam (ocr_raw+dilim). Neden ham da: girdi-yükleyici
                # ocr_ham.txt'yi tercih edebiliyor ve orada A-X-FILM kartı bölünmüş/yok olabiliyor
                # (MÜREKKEP kanıtı: kart kunye.txt'de VAR, ocr_ham'da YOK → LLM+rescue hiç görmüyordu).
                # Kart tek-satır kendinden-etiketli olduğundan ham'da arama güvenli (stüdyo-dışlama +
                # garble + kişi-adı + cast-veto + _guard korumaları aynen geçerli).
                _space2 = list(lines) + [x for x in (raw_context_lines or []) if x]
                for _ln in _space2:
                    _cand = _lex2.director_name_from_line(_ln)
                    if not _cand:
                        continue
                    if _looks_garble(_cand) is not None or not _valid_person_name(_cand):
                        continue
                    if " ".join(_toks(_cand)) in _cast_taken:   # cast-çelişki → veto (yap-çelişki DEĞİL)
                        continue
                    _g2 = _guard([_cand], ocr_tokens, title_f)
                    if _g2:
                        yon = _g2
                        break
            except Exception:  # noqa: BLE001 — rescue-2 hatası ana akışı ASLA bozmaz
                pass

        # RESCUE-3 (2026-07-04, SHERLOCK kanıtı: "PAUL SEED" ÜSTTE + "DIRECTED TY" garble-etiket ALTTA —
        # İngiliz kapanış-düzeni isim→rol): BULANIK yönetmen-etiketi (DIRECTED TY≈DIRECTED BY ratio≥0.85
        # veya "DIRECTED " öneki) → önce +1, olmazsa -1 satır. -1 penceresi SIKI: aday kişi-adı +
        # garble-değil + cast VE yapımcıda YOK (çift-rol izni RESCUE-2'ye özgü; burada belirsizlik
        # yüksek olduğundan tam-veto).
        if not yon:
            _DIRF = ("DIRECTED BY", "YONETMEN", "YONETEN", "REJISOR", "REALISE PAR", "UN FILM DE", "EIN FILM VON")
            def _dir_label_fuzzy(_f):
                if not _f or len(_f) > 24:
                    return False
                if _f in _RESCUE_LABELS:
                    return True
                if _f.startswith("DIRECTED "):          # DIRECTED TY/DY/8Y garble'ları
                    return True
                import difflib as _dl2
                return any(_dl2.SequenceMatcher(None, _f, _L).ratio() >= 0.85 for _L in _DIRF)
            for _i, _ln in enumerate(lines):
                if not _dir_label_fuzzy(_fold_ga(_ln)):
                    continue
                for _j in (_i + 1, _i - 1):
                    if _j < 0 or _j >= len(lines):
                        continue
                    _nb = lines[_j]
                    _nbf = _fold_ga(_nb)
                    if any(_v in _nbf for _v in _RESCUE_VETO) or _dir_label_fuzzy(_nbf):
                        continue
                    if _looks_garble(_nb) is not None or not _valid_person_name(_nb):
                        continue
                    # ÇİFT-ROL (RESCUE-2 ile tutarlı): cast'te → VETO; yalnız yapımcıda → İZİN
                    # (SHERLOCK kanıtı: PAUL SEED yapımcı-bloğuna gruplanmış ama isminin hemen
                    # altında DIRECTED-BY garble'ı var — ekran onu yönetmen ilan ediyor).
                    if " ".join(_toks(_nb)) in {" ".join(_toks(x)) for x in cast}:
                        continue
                    _g3 = _guard([_nb], ocr_tokens, title_f)
                    if _g3:
                        yon = _g3
                        break
                if yon:
                    break
    # /C-fix 2026-06-29 (+RESCUE-2/3 2026-07-04)

    if not dizi:
        # C-fix-canli 2026-06-29: standalone default 8→10 (Çağatay cap=10 istiyor; env zaten 10 geçiyor).
        _cap = int(os.environ.get("MITAS_CAST_CAP", "10") or 10)
        cast = cast[:_cap]
    # KESİN KURAL: yalnız gerçek "İsim Soyisim"
    out["yonetmen"], out["yapimci"], out["cast"] = _only_persons(yon), _only_persons(yap), _only_persons(cast)
    if out["cast"] or out["yonetmen"]:
        out["guven"] = "OKUNDU (metin-rol-eşleme)"
    return out


def model_chain():
    """Metin model zinciri.
    GEÇİŞ (Çağatay 2026-06-23): TEK MODEL **gemma-4-31b-it-qat-vision + think=False** (MULTIMODAL).
    Ayıklayıcı qwen3.6:35b-a3b → gemma-4-31b-it-qat-vision:latest (yerel GGUF+mmproj). text-only
    çağrıda mmproj girmez → metin text-only gemma ile BİREBİR aynı (aynı blob, +1GB VRAM), vision-hazır
    (paralel-VLM tek modelle). qwen DEVRE DIŞI
    ama silinmedi → MITAS_CREDIT_TEXT_MODEL=qwen3.6:35b-a3b ile anında geri dönülür.
    Tarihçe (2026-06-14, 20-film benchmark): qwen3.6:35b-a3b ayıklamada qwen3:8b'yi her eksende
    yenmişti; gemma'ya geçiş kalite-A/B ile doğrulanır (bkz E:\\QwenModels\\ayikla_bench\\).
    NOT: 31b≈17GB VRAM → CLIP/OCR ile aynı anda GPU'da dikkat; ayıklayıcı aşaması ollama'da paylaşır.
    _ollama_json gemma-4/qwen3* için think=False gönderir (JSON `format` ile over-think çakışmasın).
    Override: MITAS_CREDIT_TEXT_MODEL (virgüllü). DeepSeek opt-in: MITAS_CREDIT_TEXT_MODEL=deepseek-chat."""
    envm = os.environ.get("MITAS_CREDIT_TEXT_MODEL", "").strip()
    if envm:
        return [m.strip() for m in envm.split(",") if m.strip()]
    return ["gemma-4-31b-it-qat-vision:latest"]


def read_credits_auto(lines, title="", *, dizi=False, raw_context_lines=None):
    """F1: TÜM modelleri koş, ilk-doluda DURMA.
    Yönetmen: fuse() ile mutabakat/KB-seçimi.
    Cast: tüm modellerin birleşimi, dedup + F2 KB filtresi + F3 garble kapısı.
    Yapımcı: birleşim + F3 garble (yapımcı-özel) kapısı + F2 KB yapımcı filtresi.
    """
    chain = model_chain()
    lines = [l.strip() for l in (lines or []) if l and l.strip()]
    # CREW-BAĞLAMI DİLİM-KÖPRÜSÜ (2026-07-07, LENI RIEFENSTAHL/Walter A. Franke kökü): dilim-korpus
    # satırları (### MASTER-DILIM OKUMASI ### sonrası, _pipe_credit_text/_dilim_lines tarafından
    # `lines`e eklenir) YALNIZ LLM-girdisine (`lines`) ulaşıyordu; filter_cast_by_raw_context'in
    # kullandığı raw_context_lines'a HİÇ katılmıyordu → Almanca "Kamera/Kameraassistenz" etiketi
    # (zaten _CREW_CONTEXT_KW'de kayıtlı) yalnız dilimde geçince crew-üyesi (Walter A. Franke,
    # Ulrich Jaenchen) cast'ten ATILAMIYORDU (kanıt filtreye hiç ulaşmıyordu). Additive: dilim
    # satırlarını raw_context_lines'a da kat (yalnız EK kanıt; filter_cast_by_raw_context zaten
    # negatif-kapı/isim-eklemez, bu köprü yalnız DAHA FAZLA crew doğru elenmesini sağlar).
    if "### MASTER-DILIM OKUMASI ###" in lines:
        _dil_mi = lines.index("### MASTER-DILIM OKUMASI ###")
        _dil_part = lines[_dil_mi + 1:]
        if _dil_part:
            raw_context_lines = list(raw_context_lines or []) + _dil_part
    # ── LATIN-DIŞI ERKEN ROMANİZASYON (2026-06-22, NAMUS DÜŞMANI) ─────────────────────────────
    # Arap/Kiril/Yunan künyede _fold (re.sub r"[^a-z0-9 ]") TÜM harfleri siler → boş token → guard/
    # _valid_person_name ismi atar → %100 kadro kaybı (OCR mükemmel okusa bile). ÇÖZÜM: extraction'dan
    # ÖNCE Latin'e çevir → isim _fold'da ölmez. ÖNCE çok-dilli qwen (HAM Arapça→"Zeki Alasya" doğru
    # transkripsiyon; OCR-otorite'nin İZİNLİ dönüşümü — kişi aynı, alfabe değişir). qwen başarısızsa
    # unidecode'a düş (kaba "Zky Alsy" ama survival korunur; extraction-LLM reddedebilir). nonlatin_source:
    # romanizasyon OTORİTE DEĞİL → credit_qc_block KONTROL'e yollar (ASLA auto-ONAYLI, human teyit eder).
    # Bayraklar default-ON; Latin filmlerde HİÇ tetiklenmez (detect_script=='latin' → dokunulmaz, 0 regresyon).
    nonlatin_source = False
    translit_method = None
    if os.environ.get("MITAS_NONLATIN_TRANSLIT", "1").strip().lower() not in ("0", "false", "off", "no"):
        try:
            from translit_util import detect_script as _ds, transliterate_mixed as _tlm
        except Exception:  # noqa: BLE001 — translit_util yoksa kalkanı atla (mevcut davranış AYNEN)
            _ds = None
        _full_src = "\n".join(lines + [str(x) for x in (raw_context_lines or [])])
        # Oran kalkanı (bkz _nonlatin_ratio): tek-tük OCR gürültüsü (<%2) RENDER/KONTROL tetiklemesin.
        if _ds is not None and _ds(_full_src) != "latin" and _nonlatin_ratio(_full_src) >= _NONLATIN_MIN_RATIO:
            nonlatin_source = True
            _methods: set[str] = set()

            def _tl_line(s):                            # token-bazlı (kaba unidecode fallback; _fold'dan kurtarır)
                s = str(s or "")
                if not s.strip():
                    return s
                # transliterate_mixed: AZINLIK Latin-dışı token de iner (baskın 'latin' atlamaz),
                # Latin satır → asciify (Türkçe korunur), çevrilemezse HAM koru (sessiz silme yok)
                _o, _m = _tlm(s)
                _methods.update(_m)
                return _o

            # 1) ÖNCE LLM romanizasyon (DOĞRU isim kalitesi). Flag default-ON; kapalıysa direkt unidecode.
            _rmodel = (chain[0] if chain else DEFAULT_MODEL)   # birincil yerel ayıklayıcı modeli
            _rom = None
            if os.environ.get("MITAS_NONLATIN_LLM_ROMANIZE", "1").strip().lower() not in ("0", "false", "off", "no"):
                _rom = _romanize_lines_llm(lines, _rmodel)
            if _rom:
                lines = _rom
                if raw_context_lines:                   # bağlam da romanize (yoksa unidecode'a düş)
                    raw_context_lines = _romanize_lines_llm(
                        [str(x) for x in raw_context_lines], _rmodel) or [_tl_line(x) for x in raw_context_lines]
                translit_method = f"llm:{_rmodel}"
            else:                                       # 2) FALLBACK: unidecode (survival; qwen erişilemez/boş)
                lines = [_tl_line(l) for l in lines]
                if raw_context_lines:
                    raw_context_lines = [_tl_line(l) for l in raw_context_lines]
                translit_method = ",".join(sorted(_methods)) if _methods else "unidecode"
    lines = _prefilter_lines(lines)            # QC1: disclaimer/yasal/teknik satırları ele (LLM görmesin) — codex bunu kaldırmıştı (regresyon)
    text = "\n".join(lines)
    guard_lines = list(lines)
    if raw_context_lines:
        guard_lines.extend(str(l).strip() for l in raw_context_lines if str(l).strip())
    ocr_tokens = set(_toks("\n".join(guard_lines)))
    title_f = _fold(title).strip()

    kb = _get_kb()
    # A-fix-canli 2026-06-29: _cap burada bir kez tanımlanır; aşağıdaki tüm hard-cut'lar buna referans verir.
    # Env zaten 10 geçiyor (mitas_pipeline → os.environ miras); bu satır standalone koşular için de 10 default sağlar.
    _cap = int(os.environ.get("MITAS_CAST_CAP", "10") or 10)
    if not (1 <= _cap <= 50):
        _cap = 10
    pre_cast = extract_cast_block_candidates(lines, limit=(99 if dizi else _cap))
    cast_block_fast = os.environ.get("MITAS_CREDIT_CAST_BLOCK_FAST", "0").strip().lower() in (
        "1", "true", "on", "yes"
    )
    if cast_block_fast and len(pre_cast) >= 3:
        cast_fast = _apply_garble_gate(pre_cast, kb)
        cast_fast = _apply_kb_cast_filter(cast_fast, kb)
        cast_fast = filter_cast_by_raw_context(cast_fast, raw_context_lines)
        if not dizi:
            cast_fast = cast_fast[:_cap]  # A-fix-canli 2026-06-29: hard [:8] → [:_cap]
        if len(cast_fast) >= 3:
            return {
                "yonetmen": [],
                "yapimci": [],
                "cast": _only_persons(cast_fast),
                "guven": "OKUNDU (cast-block fallback; qwen atlandı)",
                "nonlatin_source": nonlatin_source,
                "translit_method": translit_method,
                # İP-2: LLM hiç koşmadı ama deterministik blok-okuma GEÇERLİ bir okumadır → OK.
                "extraction_status": "OK",
                "extraction_detail": {"mode": "cast_block_fast"},
                "degraded": False,
                "degraded_reasons": [],
            }

    per_model_yon: dict[str, list[str]] = {}
    per_model_cast: dict[str, list[str]] = {}
    all_cast: list[str] = []
    all_yap: list[str] = []
    any_success = False
    # İP-2 (2026-07-11): model-başına teknik-durum — aggregate extraction_status'un veri-tabanı.
    model_meta: dict[str, dict] = {}

    for m in chain:
        try:
            if str(m).startswith("deepseek"):
                raw = _deepseek_json(m, _prompt(text))
                model_meta[m] = {"status": "ok", "model": m}
            else:
                raw, _meta = _ollama_json_ex(m, _prompt(text), _schema())
                # İP-3 (2026-07-11): length'te TEK-SEFERLİK num_ctx-yükseltmeli retry (Opus formülü:
                # "length görülürse bir kez yükselt"). Prompt BÖLÜNMEZ — naif bölme VL/OCR bağlam
                # bütünlüğünü kırar (qwen+GLM ortak vetosu); kart-sınırı chunking bilinçli ertelendi
                # (_reasoning kaldırılınca ihtiyaç düşecek). Retry de kaza verirse status TF kalır.
                if _meta.get("status") != "ok" and _meta.get("reason") == "length":
                    _retry_ctx = int(os.environ.get("MITAS_OLLAMA_NUM_CTX_RETRY", "12288") or 12288)
                    sys.stderr.write(f"[credit_text_read] {m} length → tek-retry num_ctx={_retry_ctx}\n")
                    raw, _meta2 = _ollama_json_ex(m, _prompt(text), _schema(), num_ctx=_retry_ctx)
                    _meta2["length_retry"] = True
                    _meta = _meta2
                model_meta[m] = _meta
                if _meta.get("status") != "ok":
                    per_model_yon[m] = []
                    per_model_cast[m] = []
                    continue
        except Exception as e:
            sys.stderr.write(f"[credit_text_read] {m} hata: {type(e).__name__}: {e}\n")
            model_meta[m] = {"status": "technical_failure", "reason": "http",
                             "error": f"{type(e).__name__}: {e}", "model": m}
            per_model_yon[m] = []
            per_model_cast[m] = []
            continue

        yon_raw = _guard(raw.get("yonetmen"), ocr_tokens, title_f)
        yap_raw = _guard(raw.get("yapimci"), ocr_tokens, title_f)
        cast_raw = _guard(_merge_split_names(raw.get("oyuncular") or []), ocr_tokens, title_f)  # fix3-B 2026-06-29

        per_model_yon[m] = yon_raw
        per_model_cast[m] = cast_raw
        all_yap.extend(yap_raw)
        all_cast.extend(cast_raw)
        if yon_raw or cast_raw or yap_raw:
            any_success = True

    # ── F1: Yönetmen fusion ──────────────────────────────────────────────────
    # FIX-2b korpus ayrıştırma: _pipe_credit_text dilim satırlarını '### MASTER-DILIM OKUMASI ###'
    # işaretiyle ekler → işaret ÖNCESİ = kunye-ekranı, SONRASI = dilim-ekranı (iki bağımsız okuma).
    _ekran_kunye_f = _ekran_dilim_f = ""
    try:
        _ls_all = [str(x) for x in (lines or [])]
        if "### MASTER-DILIM OKUMASI ###" in _ls_all:
            _mi = _ls_all.index("### MASTER-DILIM OKUMASI ###")
            _ekran_kunye_f = " " + " ".join(_fold(" ".join(_ls_all[:_mi])).split()) + " "
            _ekran_dilim_f = " " + " ".join(_fold(" ".join(_ls_all[_mi + 1:])).split()) + " "
    except Exception:  # noqa: BLE001 — korpus ayrıştırma füzyonu ASLA bozmaz
        pass
    # pool_lines: fuzzy-kanonik motorun tüm ekran-varyantlarını görebilmesi için ham+dilim satırları
    # (garble-yönetmen aynı kareden kareye farklı okunur → varyant havuzu Minnelli'yi buldurur).
    _pool_lines = [str(x) for x in (lines or [])] + [str(x) for x in (raw_context_lines or [])]
    yon_fused, guven_yon = _fuse_yonetmen(per_model_yon, kb, _ekran_kunye_f, _ekran_dilim_f, _pool_lines)

    # ── F3 + F2: Cast boru hattı ─────────────────────────────────────────────
    cast_merged = _dedup_fold(all_cast)
    if _GATE_BEFORE_CAP:
        # FIX 3: filtre cap'ten ÖNCE — garble'lar gerçek adları 8-slottan atmasın.
        cast_garble = _apply_garble_gate(cast_merged, kb)
        if not dizi:
            cast_garble = cast_garble[:_cap]  # A-fix-canli 2026-06-29: hard [:8] → [:_cap]
    else:
        if not dizi:
            cast_merged = cast_merged[:_cap]  # A-fix-canli 2026-06-29: hard [:8] → [:_cap]
        cast_garble = _apply_garble_gate(cast_merged, kb)

    # F1 edge-case (BAŞROL-YÖNETMEN ayrımı): MUTABAKAT YOKSA, cast'te de görünen yönetmen
    # adayı büyük olasılıkla BAŞROL oyuncudur (ör. Waldo Pepper'da Robert Redford başrol,
    # yönetmen George Roy Hill; Redford KB'de yönetmen olduğu için ONAY alıp sızıyordu).
    # → yönetmenden DÜŞÜR (cast'te kalsın), "yanlış > boş" (okunamadı). Mutabakat (≥2 model)
    # varsa gerçek oyuncu-yönetmen olabilir (Eastwood/Allen) → DOKUNMA.
    # AYRAÇ (KB-bağımsız, self-consistency): bir yönetmen adayını öneren modellerden biri
    # AYNI ismi KENDİ cast'ine de koyduysa → o model kendi içinde çelişiyor → büyük olasılıkla
    # BAŞROL (Redford: qwen hem yönetmen dedi hem cast'ine koydu). Buna karşılık Cimino'yu
    # qwen yönetmen dedi ama KENDİ cast'ine koymadı (cast'e koyan gemma'ydı, o Walken dedi) →
    # çelişki YOK → KORU. Mutabakat (≥2 model) varsa gerçek oyuncu-yönetmen → dokunma.
    if guven_yon != "YÜKSEK (mutabakat)" and yon_fused:
        _kept = []
        for n in yon_fused:
            nf = _fold(n)
            proposers = [m for m, lst in per_model_yon.items() if any(_fold(x) == nf for x in lst)]
            self_contradict = any(
                any(_fold(c) == nf for c in per_model_cast.get(m, [])) for m in proposers)
            if self_contradict:
                continue  # başrol-yönetmen → düş ("yanlış > boş")
            _kept.append(n)
        if _kept != yon_fused:
            yon_fused = _kept
            if not _kept:
                guven_yon = "OKUNAMADI (başrol-yönetmen şüphesi)"
    # DUBLAJ-ROL DIŞLAMA: Türkçe-dublaj "SESLENDİRME/DUBLAJ YÖNETMENİ(+yard.)" film-yönetmeni sanılmasın
    # (3.GÖZ: 'ESRA TANAR' = seslendirme yön. yard. → düşer; gerçek Sam Raimi KB cast-kilidiyle gelir).
    yon_fused, _nf_dropped = _drop_dubbing_directors(
        yon_fused, raw_context_lines or lines,
        high_consensus=(guven_yon == "YÜKSEK (mutabakat)"))
    if _nf_dropped:
        sys.stderr.write(f"[rol-atfı] yönetmenden düştü (yönetmen-dışı rol): {_nf_dropped}\n")
        if not yon_fused:
            guven_yon = "OKUNAMADI (yönetmen-dışı rol — film yönetmeni değil)"
    # Kesin yönetmen cast'te de görünüyorsa cast'ten at (cast↔yönetmen kontaminasyon)
    yon_fold_set = {_fold(n) for n in yon_fused}
    cast_garble = [n for n in cast_garble if _fold(n) not in yon_fold_set]

    cast_kb = _apply_kb_cast_filter(cast_garble, kb)
    cast_kb = filter_cast_by_raw_context(cast_kb, raw_context_lines)
    cast_kb = filter_cast_by_dotleader_casing(cast_kb, guard_lines)
    if len(cast_kb) < 3:
        fallback_cast = extract_cast_block_candidates(lines, limit=(99 if dizi else _cap))  # A-fix-canli 2026-06-29: limit [:8] → [:_cap]
        if fallback_cast:
            fallback_cast = _apply_garble_gate(fallback_cast, kb)
            fallback_cast = _apply_kb_cast_filter(fallback_cast, kb)
            fallback_cast = filter_cast_by_raw_context(fallback_cast, raw_context_lines)
            cast_kb = _dedup_fold(list(cast_kb) + fallback_cast)
            if not dizi:
                cast_kb = cast_kb[:_cap]  # A-fix-canli 2026-06-29: hard [:8] → [:_cap]

    # ── F3 + F2: Yapımcı boru hattı ──────────────────────────────────────────
    yap_merged = _dedup_fold(all_yap)
    yap_garble = _apply_garble_gate_yapimci(yap_merged)
    yap_kb = _apply_kb_yapimci_filter(yap_garble, kb)

    # ── KLON-İKİZ ÇÖKERTME (cast+yapımcı doğruluk-denetimi 2026-07-04) ───────
    # AJAMİ: LLM, OCR'daki 'Rupert Preston'dan hem Rupert hem 'Robert Preston' üretti (klon-
    # fabrikasyon; _guard geçirdi çünkü 'robert' tokeni korpusta başka satırda vardı).
    # BJ VE AYI: kamyon-kapısı rekvizit yazısı iki OCR-varyantıyla ('BILLIE ICE MIKAU' /
    # 'BILLIE JOE MKAY') iki AYRI oyuncu olarak girdi. Kural KANIT-öncelikli (saf benzerlik
    # eşiği YETMEZ: Brolin baba-oğul 0.783 > BJ-çifti 0.774): fuzzy-yakın çiftte
    #   (a) yalnız biri tek-satır-bitişik ekran-kanıtlıysa → kanıtsız DÜŞER;
    #   (b) ikisi de kanıtlı ama ikisi de KB'de kişi DEĞİLSE → garble-ikiz, teke çöker;
    #   (c) ikisi de KB-gerçekse → DOKUNULMAZ (Carradine/Brolin aileleri korunur).
    cast_kb = _collapse_clone_variants(cast_kb, raw_context_lines, kb)
    yap_kb = _collapse_clone_variants(yap_kb, raw_context_lines, kb)

    # ── YÖNETMEN-RESCUE @AUTO (2026-07-04) ───────────────────────────────────
    # from_text içindeki rescue zinciri ÜRETİM yolunda (auto) hiç çalışmıyordu — SHERLOCK kanıtı:
    # 'PAUL SEED' + altında 'directed ty' garble-etiketi girdide bitişik durduğu halde yon boştu.
    # Birleşim + tüm kapılar sonrası yon hâlâ boşsa deterministik kurtarma (kart/etiket kanıtlı).
    if not yon_fused and os.environ.get("MITAS_DIRECTOR_RESCUE", "1") != "0":
        _yr = _yon_rescue_auto(lines, raw_context_lines, cast_kb, yap_kb, ocr_tokens, title_f)
        if _yr:
            # DUBLAJ-SÜZGECİ rescue-sonucuna da (yukarıdaki dublaj-drop rescue'dan ÖNCE koştu;
            # kurtarılan isim süzgeci ATLAYAMAZ — dublaj/seslendirme yönetmeni buradan giremez).
            _yr, _ = _drop_dubbing_directors(_yr, raw_context_lines or lines, high_consensus=False)
        if _yr:
            yon_fused = _yr
            guven_yon = "rescue (deterministik yönetmen-kartı/etiketi)"

    # ── Güven skoru ──────────────────────────────────────────────────────────
    if cast_kb or yon_fused:
        guven = f"OKUNDU (ensemble/fallback; yön:{guven_yon})"
    elif not any_success:
        guven = "OKUNAMADI"
    else:
        guven = "KISMI (sadece yapımcı)"

    # KESİN KURAL (son süzgeç): yönetmen/yapımcı/cast'te yalnız gerçek "İsim Soyisim".
    # İSTİSNA (2026-07-07, Les Diaboliques/H.G. Clouzot): fuse KB-onay/mutabakat/kanonik/çift-imza ile
    # ONAYLADIYSA yönetmen KB-TEYİTLİ gerçek kişidir → _only_persons'ın ≥2-gerçek-token heuristiği
    # (baş-harf-ağırlıklı 'H.G. Clouzot'u eler; gerçek-token sadece 'clouzot'=1) UYGULANMAZ. Teyitsiz
    # (rescue/okunamadı/düşük) yönetmene süzgeç AYNEN kalır (junk-freni; 'PRODUIT ET' vb. sızmaz).
    _yon_kb_teyitli = bool(yon_fused) and any(
        _k in guven_yon for _k in ("mutabakat", "KB-onay", "kanonik", "çift-imza"))
    _final_yon = (yon_fused if _yon_kb_teyitli else _only_persons(yon_fused))
    _final_yap = _only_persons(yap_kb)
    _final_cast = _only_persons(cast_kb)
    # ── İP-2 (2026-07-11): extraction_status aggregate — PRECEDENCE (şartname):
    #   Tüm modeller geçerli-JSON + alanlar dolu → OK
    #   Tüm modeller geçerli-JSON + üç alan da boş → ABSTAIN (bilinçli-boş; DEFERANS uygulanabilir)
    #   Geçerli-JSON + teknik-kaza karışık → DEGRADED (kısmi model kazası görünür)
    #   HİÇ geçerli-JSON yok → TECHNICAL_FAILURE (rescue dolu olsa bile MASKELENMEZ — rescue kanıt
    #   olarak korunur ama koşu insan-kapısını atlayamaz). Romanizasyon unidecode-fallback = DEGRADED.
    _ok_models = [m for m, mt in model_meta.items() if mt.get("status") == "ok"]
    _failed_models = [m for m, mt in model_meta.items() if mt.get("status") != "ok"]
    # Kismi model kazasi, baska bir model basarili oldu diye OK/ABSTAIN icinde maskelenemez.
    # DEGRADED kullanilabilir kaniti korur; hic basarili model yoksa terminal teknik durum TF kalir.
    if _ok_models and _failed_models:
        extraction_status = "DEGRADED"
    elif _ok_models:
        extraction_status = "OK" if (_final_yon or _final_yap or _final_cast) else "ABSTAIN"
    else:
        extraction_status = "TECHNICAL_FAILURE"
    _degraded_reasons = [
        f"model_technical_failure:{m}:{model_meta[m].get('reason') or 'unknown'}"
        for m in _failed_models
    ]
    if nonlatin_source and translit_method and not str(translit_method).startswith("llm:"):
        _degraded_reasons.append("romanize_unidecode_fallback")
    return {
        "yonetmen": _final_yon,
        "yapimci": _final_yap,
        "cast": _final_cast,
        "guven": guven,
        "nonlatin_source": nonlatin_source,
        "translit_method": translit_method,
        "extraction_status": extraction_status,
        "extraction_detail": {
            "models": model_meta,
            "ok_models": _ok_models,
            "failed_models": _failed_models,
            "rescue_filled": bool(_final_yon) and not _ok_models,
        },
        "degraded": bool(_degraded_reasons),
        "degraded_reasons": _degraded_reasons,
    }


def main():
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", required=True, help="OneOCR+GLM kunye.txt yolu")
    ap.add_argument("--title", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--dizi", action="store_true")
    a = ap.parse_args()
    lines = open(a.ocr, encoding="utf-8", errors="ignore").read().splitlines()
    if a.model:
        # tek model modu (eski compat)
        res = read_credits_from_text(lines, a.title, a.model, dizi=a.dizi)
    else:
        res = read_credits_auto(lines, a.title, dizi=a.dizi)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
