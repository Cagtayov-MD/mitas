#!/usr/bin/env python3
"""YÖNETMEN KURTARMA — künyede etiket VAR ama alan BOŞ kalan filmleri kurtarır.

ÖLÇÜLEN SORUN (2026-08-01, garble_trigger_olcum düzeltildikten sonra):
    292 künyeli filmin 145'inde yönetmen etiketi var; bunların **35'inde (%24)**
    etiket künyede duruyor ama yönetmen alanı BOŞ → QC1 RED → KONTROL.

CANLI KANIT — KUTSAL HAZİNE 1998-0325:
    giriş karesi g_0244.png ekranda "Directed by / JOHN CONNICK" gösteriyor;
    hibrit okuyucu DOĞRU okudu, hakem piksel kanıtı verdi (kutu_n=2),
    kunye.txt:252-253'e YAZILDI. Sonra gemma (rol çıkarımı) 18 oyuncuyu buldu
    ama yönetmeni atladı; VL yedeği de koştu ve o da bulamadı. İKİ LLM YOLU DA
    kaçırdı. Kayıp okuma değil, hatırlama hatası.

BU MODÜLÜN DURUŞU: LLM'i DÜZELTMEZ, yalnız BOŞLUĞU doldurur.
  • Yalnız yonetmen BOŞ iken çağrılır → dolu alanı ASLA ezmez → sıfır regresyon.
  • Deterministik: model yok, ağ yok, aynı girdi aynı çıktı.
  • Kanıt döndürür (etiket, satır no) → karar izlenebilir, sessiz tahmin yok.
  • Bulamazsa None döner; uydurmaz (Çağatay: "halüsinasyon olmasın").
"""
from __future__ import annotations

import re
import unicodedata

# Yönetmen etiketi — çok dilli. Kelime sınırı ŞART: 'DIRECTORS SOUND' eşleşmesin.
#
# ÇIPLAK "DIRECTOR" BİLEREK YOK (kuru koşu bulgusu 2026-08-01): 28 adayın 20'si
# çıplak DIRECTOR'dan geldi ve HEPSİ çöptü — çünkü OCR "DIRECTOR OF PHOTOGRAPHY"yi
# bozunca ('OF PHOROGRAPHY', 'OH PHOBOGRAGN', 'DE FOTOGRAFIA') _DEGIL süzgeci
# tutmuyor, geriye çıplak DIRECTOR kalıyor. Yalnız KENDİ BAŞINA yönetmen anlamına
# gelen kalıplar kabul edilir. Kapsam kaybı bilinçli: yanlış yönetmen yazmak boş
# bırakmaktan BETERDİR (Çağatay: "halüsinasyon olmasın").
_ETIKET = re.compile(
    r"\b("
    r"y[oö]netmen|y[oö]neten|"
    # "Directed and Edited by" / "Directed, Produced and Written by" gibi\n    # BÖLÜNMÜŞ bileşik etiketler: directed ile by arasına rol sözcüğü girebilir.
    r"directed(\s*[,&]?\s*(and|written|produced|edited|photographed))*\s+by|"
    r"r[eé]alisation|r[eé]alis[eé]\s+par|mise\s+en\s+sc[eè]ne|un\s+film\s+de|"
    r"ein\s+film\s+von|a\s+film\s+by|"
    r"regia|regie|regi|"
    r"re[zj]iss[oö]r|regisseur|"
    # ÖLÇÜLEREK eklendi (2026-08-01, tüm künye korpusu tarandı — tahmin değil):
    # regisseur 10 film · direccion 4 · regi 2 · rendezte 1 · کارگردان 1.
    # KOŞUCU 2025-1047 (yönetmeni bulunamayanlardan) Farsça etiketi taşıyor.
    r"direcci[oó]n|dirigida?\s+por|"
    r"dire[cç][aã]o|realiza[cç][aã]o|"
    r"re[zż]yseria|re[zž]ie|rendezte|"
    r"σκηνοθεσ[ιί]α"
    r")\b"
    # Latin-dışı yazılar: \b Unicode sözcük sınırı bu yazılarda güvenilmez, ayrı tutulur.
    r"|کارگردان|إخراج|監督|감督|导演|導演|בימוי"
    # KİRİL AYRI (ANNA KARENINA 1988-0520 bulgusu 2026-08-01): künyede 'РЕЖИССЕРЫ'
    # (çoğul) vardı ama \b sonlandırması Rusça ÇEKİM EKİNİ kesiyordu (-ы/-а/-ом/-ов)
    # → etiket hiç görülmedi. Kiril için ek serbest bırakılır; 'ПОСТАНОВЩИК' (sanat
    # yönetmeni) BİLEREK yok — o _DEGIL sınıfı.
    r"|режисс[ёе]р\w*|постановка\b",
    re.IGNORECASE,
)

# Adayın İLK kelimesi bunlardan biriyse isim değildir (edat/bağlaç/etiket başı).
# 'OF PHOROGRAPHY', 'DE FOTOGRAFIA', 'BY JOHN', 'AND EDITED' vakaları.
_ADAY_BAS_YASAK = {
    "OF", "DE", "DI", "DA", "DU", "DES", "DEL", "BY", "AND", "THE", "A", "AN",
    "VE", "ILE", "ZND", "2ND", "3RD", "1ST", "FIRST", "SECOND", "THIRD",
    "PRODUCED", "WRITTEN", "EDITED", "MUSIC", "SOUND", "CAMERA", "UNIT",
    "EXECUTIVE", "ASSOCIATE", "LINE", "CO",
}

# Aday içinde bu kelimelerden biri geçerse isim değildir (bozuk OCR'a dayanıklı:
# PHO*RAPH*, FOTOGRAF* gibi kökler harf hatalarını da yakalasın diye gevşek).
_ADAY_ICI_YASAK = re.compile(
    r"ph[o0]?[tr8b][o0]?[gq]r?a?[pf]h?|f[o0]t[o0][gq]raf|"      # photography / fotografia bozulmaları
    r"\bunit\b|\bsound\b|\bcamera\b|\bmusic\b|\bproduc|\bedit|"
    r"\bpresent|\bstudio|\bpictures?\b|\bfilms?\b|"
    r"\bdirect|\bwrit|\bdesign|\bsupervis",                      # 'DIRECTOR OF' vakası (CAZCI)
    re.IGNORECASE,
)

# Düzyazı imzası: bu işlev sözcükleri bir İSİMDE bulunmaz — cümle parçasıdır.
# ('EXPLODED THROUGHOUT AN UNSUSPECTING…' / 'YOU CANT …' vakaları)
_PROSA = re.compile(
    r"\b(the|an|and|with|that|this|from|into|through|throughout|when|while|"
    r"his|her|their|its|you|they|was|were|has|have|had|been|being|"
    r"cant|cannot|dont|wont|isnt|about|after|before|during|over|under|"
    # 2026-08-01 kuru koşu: _DEGIL genişletmesinden sonra iki çöp sızdı —
    # '6. GÜN → DEDIE A' (Fr. ithaf) ve 'ANGOLA → ALL ANIMAL CATCHING SCENES'.
    r"all|every|some|any|each|both|d[eé]di[eé]|dedicat|"
    r"scene|scenes|sequence|footage|sahne|g[oö]r[uü]nt[uü]ler)\b|"
    r"\w+ing\b",          # ulaç/-ing (CATCHING, SHOOTING) — isimde bulunmaz
    re.IGNORECASE,
)

# Bu kelimelerden biri geçiyorsa o etiket FİLM yönetmeni DEĞİL.
# (KUTSAL HAZİNE'de '2nd Unit Director' ve 'DIRECTORS SOUND' bu yüzden elenir;
#  CİNAYET'te 'Director of Photography', OKYANUSUN'da 'Seslendirme Yönetmen'.)
_DEGIL = re.compile(
    r"yard[iı]mc|asist|assistan|assisten|ayudante|assistente|"   # NL/DE 'ASSISTENT', ES 'AYUDANTE'
    r"associate|"
    r"photograph|d\.?o\.?p\.?|g[oö]r[uü]nt[uü]|"
    r"sanat|art\s+direct|"
    r"casting|cast\s+direct|"
    r"dublaj|seslendirme|sound|audio|ses\b|"
    r"m[uü]zik|music|"
    r"2nd\s+unit|second\s+unit|ikinci\s+birim|"
    # PRODUCTION/DESIGN aileleri (2026-08-01, hakem 3. tur bulgusu): hakem
    # 'Production Designer'ı YÖNETMEN kabul etti. 'production manager' varken
    # 'production designer' yoktu; design/dekor/kostüm/sanat da eksikti.
    r"post|teknik|prod[uü]ksiyon|production\s+(manager|designer|supervis|coordinat)|"
    r"designer|design[eé]?\b|dekor|kost[uü]m|costume|"
    r"executive|line\s+produc|co.?produc|"
    r"stunt|d[oö]v[uü][sş]|"
    # SENARYO/HİKÂYE etiketleri (2026-08-01, KARA GÜNLER kanıtı): model
    # "NACH EINER GESCHICHTE VON" (= hikâyesinden) altındaki ismi yönetmen
    # yazmıştı. Hikâye/senaryo yazarı yönetmen DEĞİL.
    r"geschichte\s+von|based\s+on\s+a\s+story|d.?apr[eè]s|"
    r"senaryo|screenplay|written\s+by|drehbuch|sc[eé]nario|soggetto|"
    r"hik[aâ]ye|uyarlama|adaptation|adapt[eé]\s+par",
    re.IGNORECASE,
)

# İsim OLMAYAN satırlar (şirket/rol/teknik). isim_mi() bunları eler.
_SIRKET = {
    "FILM", "FILMS", "FILMI", "PRODUCTION", "PRODUCTIONS", "PICTURES", "PICTURE",
    "STUDIO", "STUDIOS", "ENTERTAINMENT", "MEDIA", "INC", "LLC", "LTD", "LIMITED",
    "COMPANY", "CO", "TV", "INTERNATIONAL", "GROUP", "CORP", "CORPORATION",
    "ASSOCIATES", "YAPIM", "YAPIMCILIK", "SUNAR", "PRESENTS", "PRODUCTIONS",
    "AS", "A.S", "SANAYI", "TICARET", "REKLAM", "AJANS",
}

# Yönetmen etiketinin ÖNÜNE gelebilen MEŞRU bileşik önekler.
# Önek YALNIZ izinli rol sözcükleri + ayraç + 'and' içeriyorsa bileşik etikettir.
# 'Written, Produced and' / 'Written and' / 'Produced and' hepsini kapsar;
# 'Bu film 1998 yılında' gibi serbest cümle KAPSAM DIŞI (izinsiz sözcük var).
_BILESIK_ON = re.compile(
    r"[\s,]*((written|produced|edited|photographed|conceived|created|adapted|and|&)[\s,]*)+",
    re.IGNORECASE)

_MAX_ILERI = 3            # etiketten sonra en fazla kaç satır ileri bakılır
_MAX_ISIM_TOKEN = 5       # 'JOHN RONALD REUEL TOLKIEN JR' sınırı


def _kats(s: str) -> str:
    s = (s or "").replace("ı", "i").replace("İ", "i")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def isim_mi(satir: str) -> bool:
    """Bu satır bir KİŞİ adı olabilir mi? Muhafazakâr: şüphede HAYIR."""
    s = (satir or "").strip(" .:-–—\t")
    if not (3 <= len(s) <= 48):
        return False
    if _ETIKET.search(s) or _DEGIL.search(s):
        return False                       # başka bir rol etiketi
    if any(ch.isdigit() for ch in s):
        return False
    if _ADAY_ICI_YASAK.search(s):
        return False                       # görüntü yön./ekip/şirket kökü (OCR bozulmasına dayanıklı)
    if _PROSA.search(s):
        return False                       # cümle parçası, isim değil
    tok = [t for t in re.split(r"[\s'’.\-]+", s) if t]
    if not (2 <= len(tok) <= _MAX_ISIM_TOKEN):
        return False                       # tek kelime isim sayılmaz (Çağatay kuralı)
    if _kats(tok[0]) in _ADAY_BAS_YASAK:
        return False                       # edat/etiket başı: 'OF ...', 'PRODUCED BY'
    if any(_kats(t) in _SIRKET for t in tok):
        return False
    if not all(re.fullmatch(r"[^\W\d_]+", t, re.UNICODE) for t in tok):
        return False                       # her token SAF harf olmalı
    harf = [c for c in s if c.isalpha()]
    if len(harf) < len(s.replace(" ", "")) * 0.8:
        return False                       # noktalama ağırlıklı → çöp
    return True


def dogrula(isim: str, satirlar, bak_ustu: int = 3) -> dict | None:
    """MODELİN VERDİĞİ yönetmeni künye BAĞLAMINA karşı sına — kusur varsa döner.

    Çağatay kısıtı: "Bu işi modelden ALMAM." Bu yüzden burada çıkarım YOK;
    yalnız modelin cevabı DENETLENİR. Model ana yol kalır, bu katman hakemdir.

    MEKANİZMA: ismin künyedeki yerini bul, HEMEN ÜSTÜNDEKİ satırlara bak.
    Orada yönetmen-DIŞI bir rol etiketi varsa (koreograf, hikâye yazarı,
    asistan, görüntü yön., ses...) o isim O ROLE aittir, yönetmene değil.

    ÖLÇÜLMÜŞ VAKALAR:
      ÇİNGENE 1998-0435 : satır 20 '2ème assistant réalisateur' → 21 FREDERIC PLANCHON
      KARA GÜNLER 1998-0312: satır 12 'NACH EINER GESCHICHTE VON' → 13 DOMINIQUE ROULET
                             (doğru yönetmen NIKOLAUS LEYTNER satır 10'da duruyordu)
    KAPSAM DIŞI (dürüstlük): YAZ TATİLİ'nde ismin üstünde HİÇ etiket yok
    (OCR yapıyı kaybetmiş) → bu kural onu yakalayamaz, yakalamış gibi de yapmaz.

    Döner: kusur varsa {"sebep","etiket","satir","isim"}; temizse None.
    """
    isim = (isim or "").strip()
    if not isim:
        return None
    fold = isim.lower()
    sat = [str(s or "").strip() for s in (satirlar or [])]
    # İKİ DÜZELTME (2026-08-01 konsey turu, 4 üye bağımsız buldu + kodla test edildi):
    # (1) İSİM MASKELEME: _DEGIL, hedef ismin KENDİ İÇİNDEKİ alt-dizeyi yakalıyordu →
    #     'AYŞE POSTACI' → 'POST' eşleşti → DOĞRU yönetmen reddedildi. Artık isim
    #     satırdan ÇIKARILIP sonra rol etiketi aranıyor.
    # (2) TÜM GEÇİŞLERİ TARA: eskiden İLK eşleşmede karar verip dönüyordu →
    #     ['Written by','JANE DOE','Directed by','JANE DOE'] gibi çift-rol (auteur)
    #     vakasında yanlış bağlam seçilip reddediliyordu. Artık ismin TÜM geçişleri
    #     bakılır; BİRİ temiz yönetmen etiketiyle eşleşiyorsa KABUL.
    def _maskele(satir: str) -> str:
        import re as _re
        return _re.sub(_re.escape(isim), " ", satir, flags=_re.IGNORECASE)

    kusurlar = []
    for i, l in enumerate(sat):
        if fold not in l.lower():
            continue
        # (a) AYNI satırda yönetmen-dışı etiket varsa ('Seslendirme Yönetmen X')
        m = _DEGIL.search(_maskele(l))
        if m:
            kusurlar.append({"sebep": "ayni_satirda_rol_etiketi", "etiket": m.group(0),
                             "satir": i, "isim": isim})
            continue
        # (b) ÜSTTEKİ satırlarda; arada başka İSİM yoksa etiket bu isme aittir
        temiz = False
        for j in range(i - 1, max(-1, i - 1 - bak_ustu), -1):
            ust = _maskele(sat[j])
            if not ust.strip():
                continue
            if _ETIKET.search(ust) and not _DEGIL.search(ust):
                temiz = True; break             # gerçek yönetmen etiketi → bu geçiş TEMİZ
            m = _DEGIL.search(ust)
            if m:
                kusurlar.append({"sebep": "ustunde_rol_etiketi", "etiket": m.group(0),
                                 "satir": j, "isim": isim})
                break
            if isim_mi(sat[j]):
                temiz = True; break             # araya başka isim girdi → bağ kopuk, hüküm yok
        if temiz:
            return None                         # EN AZ BİR geçiş temiz → KABUL
    return kusurlar[0] if kusurlar else None


def _ayni_kare(iz_yolu, etiket_metin: str, isim_metin: str) -> str | None:
    """ADRES TEYİDİ (Çağatay'ın hakem fikri, rol-eşlemeye uygulanmış).

    Etiket ile isim EKRANDA AYNI KAREDE mi? hibrit_iz.jsonl her satırın kaynak
    PNG'sini tutuyor. Aynı kare = kart gerçekten "Directed by / İSİM" kartı.
    Farklı kare = satırlar künyede yan yana düşmüş ama ekranda ilgisiz
    (HOTEL RWANDA vakası: 'A FILM BY' ile oyuncu adı tesadüfen komşu).
    Döner: ortak kare adı, yoksa None. İz dosyası yoksa None (hüküm verme).
    """
    try:
        import json as _json
        et, isim = etiket_metin.strip().lower(), isim_metin.strip().lower()
        et_kare, isim_kare = set(), set()
        with open(iz_yolu, encoding="utf-8") as h:
            for satir in h:
                try:
                    k = _json.loads(satir)
                except Exception:  # noqa: BLE001
                    continue
                t = str(k.get("text", "")).strip().lower()
                kaynak = k.get("kaynak")
                if not kaynak:
                    continue
                if et and et in t:
                    et_kare.add(kaynak)
                if isim and t == isim:
                    isim_kare.add(kaynak)
        ortak = et_kare & isim_kare
        return sorted(ortak)[0] if ortak else None
    except Exception:  # noqa: BLE001 — teyit yoksa hüküm yok
        return None


def kurtar(satirlar, iz_yolu=None) -> dict | None:
    """Künye satırlarından yönetmeni ETİKET ÜZERİNDEN çıkar.

    Döner: {"yonetmen": str, "etiket": str, "satir": int, "nasil": "ayni_satir|alt_satir"}
    veya bulunamazsa None. ASLA uydurmaz.
    """
    satirlar = [str(s or "") for s in (satirlar or [])]
    for i, ham in enumerate(satirlar):
        m = _ETIKET.search(ham)
        if not m or _DEGIL.search(ham):
            continue
        # (a) etiketin AYNI satırdaki devamı: 'Directed by JOHN CONNICK'
        kalan = ham[m.end():].strip(" :.-–—\t")
        if isim_mi(kalan):
            return {"yonetmen": kalan, "etiket": m.group(0), "satir": i,
                    "nasil": "ayni_satir", "kare_teyidi": "etiketle_ayni_satir"}
        # (b) ALT satır(lar): 'Directed by' \n 'JOHN CONNICK'
        # BİLEŞİK ETİKET İSTİSNASI (2026-08-01, çok-yönetmen testi yakaladı):
        # 'Written and Directed by' MEŞRU yönetmen kartıdır — promptun kural 4'ü de
        # öyle diyor ("WRITTEN AND DIRECTED BY … bu kartlardaki kişi(ler) YÖNETMENdir").
        # Eski koruma etiketten önce metin görünce serbest cümle sanıp ATLIYORDU.
        _on = ham[:m.start()].strip(" :.-–—\t")
        if _on and not _BILESIK_ON.fullmatch(_on):
            continue                       # gerçekten serbest cümle → atla
        for j in range(i + 1, min(i + 1 + _MAX_ILERI, len(satirlar))):
            aday = satirlar[j].strip()
            if not aday:
                continue
            if _ETIKET.search(aday) or _DEGIL.search(aday):
                break                      # araya başka rol girdi → bu etiket sahipsiz
            if isim_mi(aday):
                # ÇOK-YÖNETMENLİ FİLM (2026-08-01 konsey turu, P0 bulgusu):
                # eskiden İLK isimde return ediliyordu → 'Directed by / JOEL COEN /
                # ETHAN COEN' kartında ETHAN COEN SESSİZCE KAYBOLUYORDU. Bu,
                # Çağatay'ın "isim atlamayalım" kuralının ihlali; eş-yönetmen
                # normaldir (Coen/Taviani kardeşler, Scandar Copti–Yaron Shani).
                # Promptun kural 4'ü de "HEPSİNİ yaz, TEKE İNDİRME" diyor —
                # kurtarıcı o kuralla çelişiyordu.
                # Artık etiketten sonra ARDIŞIK gelen TÜM geçerli isimler toplanır;
                # araya etiket/rol girerse durulur (o başka role aittir).
                # EŞ-YÖNETMEN AYRIMI: komşu her ismi toplamak YENİ hata üretiyor —
                # KUTSAL HAZİNE'de 'Directed by / JOHN CONNICK' sonrası 'Erea Johnson'
                # (karakter adı) eş-yönetmen sanıldı. İki BEDAVA sinyalle ayır:
                #  (a) KASA DESENİ: gerçek kartta eş-yönetmenler AYNI biçimde yazılır
                #      ('JOEL COEN'/'ETHAN COEN' ikisi de BÜYÜK). 'JOHN CONNICK' BÜYÜK
                #      iken 'Erea Johnson' Baş-Harfi-Büyük → aynı kart değil.
                #  (b) ADRES TEYİDİ: aynı kareden mi geldi (iz varsa).
                # Sinyal yoksa MUHAFAZAKÂR davran — tek isim (eski davranış).
                def _kasa(t: str) -> str:
                    harf = [c for c in t if c.isalpha()]
                    if not harf:
                        return "?"
                    if all(c.isupper() for c in harf):
                        return "UST"
                    return "BAS" if t[:1].isupper() else "KUCUK"

                adaylar = [aday]
                _ilk_kasa = _kasa(aday)
                for k2 in range(j + 1, min(j + 1 + _MAX_ILERI, len(satirlar))):
                    s2 = satirlar[k2].strip()
                    if not s2:
                        continue
                    if _ETIKET.search(s2) or _DEGIL.search(s2):
                        break              # yeni rol başladı
                    if not isim_mi(s2):
                        break
                    if _kasa(s2) != _ilk_kasa:
                        break              # farklı yazım biçimi → başka kart/rol
                    if iz_yolu and not _ayni_kare(iz_yolu, m.group(0), s2):
                        break              # adres teyidi tutmadı → eş-yönetmen değil
                    adaylar.append(s2)
                kare = _ayni_kare(iz_yolu, m.group(0), aday) if iz_yolu else None
                return {"yonetmen": adaylar[0], "yonetmenler": adaylar,
                        "etiket": m.group(0), "satir": j,
                        "nasil": "alt_satir",
                        "kare_teyidi": kare or ("iz_yok" if not iz_yolu else "AYRI_KARE")}
            break                          # ilk dolu satır isim değilse zorlama
    return None


if __name__ == "__main__":                 # elle deneme: python3 scripts/yonetmen_kurtar.py <kunye.txt>
    import json
    import sys
    from pathlib import Path
    if len(sys.argv) < 2:
        raise SystemExit("kullanım: yonetmen_kurtar.py <kunye.txt>")
    print(json.dumps(kurtar(Path(sys.argv[1]).read_text(encoding="utf-8",
                                                        errors="ignore").splitlines()),
                     ensure_ascii=False, indent=1))
