"""OCR-içerik ayırıcı — kredi vs ara-yazı/tabela/sahne-metni.

Konsey (GLM, 2026-07-21): kutu var/yok YETMEZ, metni OKU. Kredi = isim-listesi
(Title Case + BÜYÜK-HARF isimler, rol-keyword), ara-yazı = tek cümle, tabela =
0-birkaç kelime. Test doğruladı: BILLY kredi 11-satır cast, ara-yazı 1-cümle.

PaddleOCR rec sadece ADAY karelerde (birkaç), maliyet düşük.
"""
from __future__ import annotations

import re
import unicodedata

_OCR = None

# rol/görev keyword'leri (EN + TR + İtalyanca/Fransızca/Almanca/İspanyolca/Macarca — T6 2.tur)
# Yabancı-dil kalıpları _ROL_CEKIRDEK ile AYNI (GLM uyarısı: 'distributed/production
# company' türü logo-kuşağı kelimeleri EKLENMEDİ — bkz. _ROL_CEKIRDEK).
#
# PREFIX-GÜVENLİ DÜZELTME (mini-tur 3, alt-adım1): paylaşılan \b(...)\b grubu
# yüzünden KISALTILMIŞ-KÖK niyetli alternatifler (produc, photograph,
# cinematograph, edit, yönet, senaryo, yapım, réalisat, interprét) hiç
# eşleşmiyordu — kapanış \b, kökten sonra gelen ek harfine (producER,
# photographY, yönetMEN, senaryoSU) çarpıp boundary'yi bozuyordu (2. tur
# ajanının kanıtlı bulgusu, ölçüldü: 'Producer'/'photography'/'yönetmen'/
# 'senaryosu'/'yapımcı' hiçbiri tutmuyordu). Köklere `\w*` eklendi — TAM
# KELİME alternatifleri (director/directed/screenplay/written/writer/story/
# music/script/editor/cast/starring/art/costume/sound/camera/design/makeup/
# producer/executive/associate/assistant/görüntü/müzik/kurgu/oyuncu/kostüm/
# montaj/ses ve diğer dil tam-kelimeleri) KASITLI DOKUNULMADI — bunlara `\w*`
# eklemek isim çarpışması riski açardı (örn. 'art'+\w* → 'ARTHUR', 'cast'+\w*
# → 'Castro/Castellano' yanlış-tetikler; ölçüldü, ayırt edici DEĞİL).
_ROL = re.compile(
    r"\b(director|directed|produc\w*|screenplay|written|writer|story|music|script|"
    r"photograph\w*|cinematograph\w*|edit\w*|editor|cast|starring|art|costume|sound|"
    r"camera|design|makeup|make-up|producer|executive|associate|assistant|"
    r"yönet\w*|yapım\w*|senaryo\w*|görüntü|müzik|kurgu|oyuncu|kostüm|montaj|ses|"
    r"regia|produzione|operatore|montaggio|musich|fotografia|scenografia|costumi|interpreti|"
    r"réalisat\w*|scénario|musique|montage|image|décors|interprét\w*|"
    r"regie|drehbuch|kamera|schnitt|musik|darsteller|"
    r"dirección|guión|música|montaje|reparto|"
    r"rendezte|rendező|operatőr|zene|fényképezte|vágó|szereplők|gyártásvezető)\b",
    re.I)

# ÇEKİRDEK-ROL beyaz listesi (T6, plan Görev6/Adım1) — SON_ERISIM gevşetmesi/
# scroll-kurtarma/seyrek-yol gibi RİSKLİ gevşetmeleri SADECE bunlar tetikler.
# "distributed/production/copyright" türü logo-kuşağı kelimeleri KASITLI DIŞARIDA
# (GLM tur-2 uyarısı: film-ortası şirket logosu/kredi-dışı insert yanlış tetikler).
# Macarca eklendi (T6 2.tur, alt-adım1a — konsey kırmızı-takım): DOĞUM_GÜNÜN gibi
# Macar yapımlarında kredi kartları yalnız Macarca rol adları taşıyor.
#
# PREFIX-GÜVENLİ DÜZELTME (mini-tur 3, alt-adım1): _ROL'deki aynı \b(...)\b
# kapanış-sınırı bozukluğu burada da var — 'photograph'/'cinematograph'/
# 'yönet'/'senaryo'/'réalisat'/'interprét' köklerine `\w*` eklendi (aynı
# gerekçe: photographY/cinematographER/yönetMEN/senaryoSU/réalisateur/
# interprétation hiç tutmuyordu). 'produc'/'yapım' (producer/yapımcı analogu)
# BİLEREK EKLENMEDİ — bu liste zaten "produc"sız tasarlandı (logo-kuşağı
# riski, yukarıdaki gerekçe); prefix-düzeltmesi bu kasıtlı dışlamayı
# GENİŞLETMEZ, yalnız zaten listede olan köklerin kendi bozukluğunu giderir.
_ROL_CEKIRDEK = re.compile(
    r"\b(director|directed|screenplay|written|writer|cinematograph\w*|photograph\w*|"
    r"editor|edited|music|starring|cast|script|"
    r"yönet\w*|senaryo\w*|görüntü|kurgu|müzik|oyuncu|"
    r"regia|produzione|operatore|montaggio|musich|fotografia|scenografia|costumi|interpreti|"
    r"réalisat\w*|scénario|musique|montage|image|décors|interprét\w*|"
    r"regie|drehbuch|kamera|schnitt|musik|darsteller|"
    r"dirección|guión|música|montaje|reparto|"
    r"rendezte|rendező|operatőr|zene|fényképezte|vágó|szereplők|gyártásvezető)\b",
    re.I)


def _diakritik_kaldir_basit(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# Macarca diyakritik-toleranslı önek (T6 2.tur, alt-adım1a — atlas kanıtı:
# DOĞUM_GÜNÜN'de OCR aksanları düşürüyor: 'operatőr'->'operatori'/'operator',
# 'rendező'->'rendentar'). _ROL_CEKIRDEK'in \b...\b TAM-kelime eşleşmesi bu
# OCR-bozuk biçimleri hiç yakalamıyor (ölçüldü — 36 karenin hiçbirinde tutmadı).
# Kapanış \b KASITLI YOK (Macarca çekimli dil + OCR gürültüsü tam kelimeyi asla
# tutturmuyor). 'vágó' (editör) listeye ALINMADI: diyakritiksiz 3 harfli önek
# ("vag") İngilizce 'vagrancy/vague' ile çakışıyor (kod tabanında zaten bilinen
# bir gazete-insert test vakası — MODERN "WANTED FOR Vagrancy"); risk/kazanç
# dengesi olumsuz, dışarıda bırakıldı. Yalnız cekirdek_rol_bul() içinde
# kullanılır — global _ROL_CEKIRDEK'in davranışı DEĞİŞMEZ.
_ROL_MACAR_ONEK = re.compile(
    r"\b(rendez|operat|fenykepez|szerepl|gyartasvezet)", re.I)


def cekirdek_rol_bul(kare_satirlari: list[list[str]]) -> list[str]:
    """_ROL_CEKIRDEK (tam eşleşme, çok-dilli) + Macarca + Arapça/Kiril toleransı."""
    global AKTIF_DIL
    roller: set[str] = set()
    lang = AKTIF_DIL
    for sl in kare_satirlari:
        for s in sl:
            for m in _ROL_CEKIRDEK.findall(s):
                roller.add(m.lower())
            for m in _ROL_MACAR_ONEK.findall(_diakritik_kaldir_basit(s)):
                roller.add(m.lower())
            if lang == 'ar':
                for m in _ROL_ARAP.findall(_arapca_normalize(s)):
                    roller.add(m.lower())
            elif lang == 'ru':
                for m in _ROL_KIRIL.findall(s):
                    roller.add(m.lower())
    return sorted(roller)


# 'produc' ailesi (producer/production/produced/…) — SADECE seyrek-yol
# genişletme KARARI için (mini-tur3, alt-adım1 fallback). DENENDİ VE
# ÖLÇÜLDÜ: bunu doğrudan _ROL_CEKIRDEK'e eklemek (dolayısıyla cekirdek_rol_bul
# + _gecis_icerik_onayi/_scroll_kurtarma/SON_ERISIM_GEVSEK'in TÜMÜNÜ etkiler)
# kırmızı-çizgiyi BOZDU: DÖNÜŞÜ_OLMAYAN_NEHİR'in şirket-kalıbı satırı
# ("A CINEMASCOPE PRODUCTION" + "Produced and Released by") "production" VE
# "produced" diye İKİ FARKLI yüzey-formu üretiyor — bunlar set'e 2 AYRI rol
# olarak düşüp len(core_roller)>=2'yi TEK BAŞINA (başka HİÇBİR gerçek rol
# olmadan) sağlıyor, seyrek-yolu (yogun_esik=2) yanlış açıyor, kredi_yok
# 29/29→28/29 (ölçüldü). Çözüm: 'produc' ailesi kaç yüzey-formu geçerse
# geçsin TEK kanonik rol ("producer") sayılır — rol-çeşitliliğine EN FAZLA +1
# katkı yapar. KÜÇÜK_SİMBA (gerçek 'Producer'+'Director' — İKİ FARKLI GERÇEK
# rol) hâlâ açılıyor; DÖNÜŞÜ_OLMAYAN_NEHİR (yalnız produc-ailesi, başka rol
# yok → +1'den öteye geçmiyor → hâlâ <2) artık AÇILMIYOR (ölçüldü, 29/29 geri
# geldi). Yalnız cekirdek_rol_bul_genis() içinde kullanılır; ham _ROL_CEKIRDEK
# ve strict cekirdek_rol_bul()'un davranışı DEĞİŞMEZ.
_PRODUC_GENIS = re.compile(r"\b(produc\w*|yapım\w*)\b", re.I)


def cekirdek_rol_bul_genis(kare_satirlari: list[list[str]]) -> list[str]:
    """SADECE tespit_v5'in seyrek-yol GENİŞLETME KARARINDA kullanılır (mini-tur3
    alt-adım1). `_gecis_icerik_onayi` ve `_scroll_kurtarma` kapıları BİLEREK
    ham `_ROL_CEKIRDEK` kullanır (Macarca diyakritik toleransı HARİÇ) — bu
    kapılar sahte-pozitif üreticisi olduğu için `_ROL_MACAR_ONEK`'in kapanış-
    `\\b`-taşımayan öneklerinin `operation`/`render` gibi kelimelere çarpma
    riski oralarda kabul edilmiyor; bu fonksiyon ONLARI etkilemez (kırmızı-
    çizgi güvencesi buradan gelir)."""
    roller = set(cekirdek_rol_bul(kare_satirlari))
    if any(_PRODUC_GENIS.search(s) for sl in kare_satirlari for s in sl):
        roller.add("producer")
    return sorted(roller)


AKTIF_DIL = "en"
_OCR_CACHE = {}

def _ocr():
    global _OCR_CACHE, AKTIF_DIL
    target_lang = AKTIF_DIL
    if target_lang not in _OCR_CACHE:
        from paddleocr import PaddleOCR
        _OCR_CACHE[target_lang] = PaddleOCR(use_textline_orientation=False, lang=target_lang)
    return _OCR_CACHE[target_lang]


def satirlar(frame_path: str) -> list[str]:
    try:
        r = _ocr().predict(frame_path)
        if not r or not r[0]:
            return []
        rr = r[0]
        txt = rr.get("rec_texts", []) if isinstance(rr, dict) else []
        return [t.strip() for t in txt if t and t.strip()]
    except Exception:
        return _qwen_vision_ocr(frame_path, lang=AKTIF_DIL)


# ── İKİNCİ-ŞANS KİRİL REC (T6 2.tur, alt-adım1b) ─────────────────────────
# EN-rec modeli Kiril-script kareyi okuyunca rastgele Latin harf yığınları
# üretir (VANYA_DAYI/MELEKLERİ_GÖRMEK atlas kanıtı: 'ATbA OA', 'OeAHEeUHK').
# Ayrı lazy-init global — yalnız çöp-desenli çıktı veren, içerik-eşiğini
# geçemeyen adaylarda, o adayın birkaç örnek karesinde tetiklenir (det zaten
# var; yalnız rec farklı model, maliyet düşük ve nadir).
_OCR_RU = None


def _ocr_ru():
    global _OCR_RU
    if _OCR_RU is None:
        from paddleocr import PaddleOCR
        _OCR_RU = PaddleOCR(use_textline_orientation=False, lang="ru")
    return _OCR_RU


def satirlar_ru(frame_path: str) -> list[str]:
    try:
        r = _ocr_ru().predict(frame_path)
        if not r or not r[0]:
            return []
        rr = r[0]
        txt = rr.get("rec_texts", []) if isinstance(rr, dict) else []
        return [t.strip() for t in txt if t and t.strip()]
    except Exception:
        return _qwen_vision_ocr(frame_path, lang="ru")


# Rusça+Kazakça rol sözlüğü — kasıtlı olarak SADECE ikinci-şans Kiril yolunda
# kullanılır (global _ROL/_ROL_CEKIRDEK'e KARIŞTIRILMAZ). Rusça/Kazakça çekimli
# dillerdir (режиссёр/режиссёра/режиссёрі...) — kapanış \b YOK, önek eşleşmesi
# kasıtlı (İngilizce _ROL'deki 'produc' önekinin AKSİNE: orada kapanış \b'sinin
# hiç eşleşmediği bir regresyon var — ayrı sorun, bu görev kapsamında DOKUNULMADI).
_ROL_KIRIL = re.compile(
    r"\b(режисс|оператор|композитор|звукооператор|художник|сценари|монтаж|"
    r"актер|актёр|роля|қатысқандар)", re.I)


# T8 Kod-avı #5 (üretim-sertleştirme) — DENENDİ VE GERİ ALINDI: 'y/Y'yi sesli
# saymak CRYSTAL/RHYTHM tipi gerçek kelimeleri "çöp" damgalanmaktan kurtarır
# (amaçlanan düzeltme), AMA MELEKLERİ_GÖRMEK_İSTEDİM'in Kiril-kurtarma yolunu
# BOZAR: o filmin gerçek adayı gercek/len=0.906 (esik=0.92 altında → 'çöp',
# Kiril ikinci-şans tetiklenir, kredi doğru bulunur); 'y' eklenince aynı
# örneklem 0.938'e çıkıp eşiği aşıyor → Kiril denenmiyor → kredi_yok'a düşüyor
# (ölçüldü: 100/110→99/110). Marj o kadar dar ki (0.906 vs 0.92) iki hedefi
# aynı anda karşılayan güvenli bir ayar yok — mevcut kazanım DAHA DEĞERLİ
# (gerçek FP değil, yalnız gereksiz-maliyet riski vardı). 'y' EKLENMEDİ.
_LATIN_SESLI = set("aeiouAEIOU")


def _sesli_orani(tok: str) -> float:
    harfler = [c for c in tok if c.isalpha()]
    if not harfler:
        return 0.0
    return sum(1 for c in harfler if c in _LATIN_SESLI) / len(harfler)


def cop_desenli_mi(kare_satirlari: list[list[str]], esik: float = 0.30) -> bool:
    """EN-rec çıktısı çöp-desenli mi (T6 2.tur, alt-adım1b) — Kiril bir kareyi
    yanlış (lang='en') modelle okuma belirtisi. Gerçek İngilizce/Türkçe kelimeler
    (≥4 harf) sesli-harf-oranı tipik 0.25-0.6 aralığında kalır; Kiril→Latin
    yanlış-okuma rastgele harf yığınları üretir, oran uçlara savrulur. Pragmatik
    eşik (ölçüldü): tokenlerin <%30'u bu aralıkta ise çöp say. Az örnekte (< 3
    token) karar verilemez — çöp DAMGALANMAZ (varsayılan davranış korunur)."""
    tokenler = []
    for satirlar_ in kare_satirlari:
        for s in satirlar_:
            for tok in s.split():
                w = "".join(c for c in tok if c.isalpha())
                if len(w) >= 4:
                    tokenler.append(w)
    if len(tokenler) < 3:
        return False
    gercek = sum(1 for t in tokenler if 0.25 <= _sesli_orani(t) <= 0.6)
    return (gercek / len(tokenler)) < esik


def _isim_gibi_kiril(satir: str) -> bool:
    """Kiril satırın isim/rol-benzeri olup olmadığı — Python'un Unicode-farkında
    isupper()/title-case testleri Kiril'de de doğru çalışır (T6 2.tur kanıtı:
    'РЕЖИССЁР'.isupper()==True); yalnız rol-sözlüğü _ROL_KIRIL'e çevrilir.

    T8 Kod-avı #3 (üretim-sertleştirme): Latin _isim_gibi'deki cümle-gardı
    (satır-sonu noktalama + ≥4 kelime = ara-yazı/altyazı cümlesi) burada
    EKSİKTİ — hardcoded Rusça altyazı ("Здравствуйте, как дела сегодня.")
    title-case sayılıp kredisiz bir Rus filminde yanlış-pozitif üretebilirdi
    (110-filmlik ölçüm setinde görünmez, üretimde risk). Aynı gard buraya da
    uygulandı — Python'un islower()/isupper()'ı Kiril'de de doğru çalışıyor."""
    s = satir.strip().strip('"“”\'')
    if len(s) < 2:
        return False
    if _ROL_KIRIL.search(s):
        return True
    if _NOKTA_LIDER.search(s):
        return True
    kelimeler = s.split()
    if not kelimeler:
        return False
    if s.endswith((".", "?", "!")) and len(kelimeler) >= 4:
        kucuk = sum(1 for w in kelimeler if w and w[0].islower())
        if kucuk >= 2:
            return False
    buyuk = sum(1 for w in kelimeler if len(w) >= 2 and w.isupper())
    title = sum(1 for w in kelimeler if len(w) >= 2 and w[0].isupper() and not w.isupper())
    return buyuk >= 1 or title >= 2


def kredi_skoru_kiril(kare_satirlari: list[list[str]], yogun_esik: int = 2) -> tuple[float, list[str]]:
    """İkinci-şans Kiril rec içerik skoru + bulunan çekirdek-rol listesi.

    kredi_skoru_coklu'nun Kiril-eşleniği: yogun_esik düşük tutulur (2) çünkü
    ikinci-şans yalnız birkaç örnek karede çalışır (dar örneklem, seyrek-kredi
    T6 adım4'teki gerekçeyle aynı: sessiz/az-metinli jenerik kare-başına az
    isim gösterebilir)."""
    if not kare_satirlari:
        return 0.0, []
    yogun = 0
    roller: set[str] = set()
    for sl in kare_satirlari:
        isim_n = sum(1 for s in sl if _isim_gibi_kiril(s))
        if isim_n >= yogun_esik:
            yogun += 1
        for s in sl:
            for m in _ROL_KIRIL.findall(s):
                roller.add(m.lower())
    skor = round(min(1.0, yogun / 3.0), 3)
    return skor, sorted(roller)


# ── İKİNCİ-ŞANS ARAPÇA/FARSÇA REC (alt-adım4, T8 sonrası — Çağatay politikası:
# tespit-yok = cast komple kayıp, artık "opsiyonel" değil) ──────────────────
# Kiril ikinci-şansının farklı bir varyantı: Kiril'de EN-rec metni YANLIŞ
# okuyup rastgele Latin harf yığını üretiyordu (cop_desenli_mi bunu yakalar);
# Arapça/Farsça yazıda ise EN-rec çoğu zaman HİÇBİR ŞEY üretmiyor (glyph'ler
# Latin/Kiril alfabesinden o kadar uzak ki det/rec boş dönüyor — KANDAHAR atlas
# kanıtı: gt-civarı örneklerde credit_content.satirlar() tamamen []). Bu yüzden
# tetikleyici cop_desenli_mi DEĞİL — "EN-rec hiç metin bulamadı" sinyali
# (tespit_v5 tarafında ayrıca kontrol edilir).
_OCR_AR = None


def _qwen_vision_ocr(frame_path: str, lang: str = "ar") -> list[str]:
    """Fallback OCR using local Qwen Vision model when PaddleOCR engine is unavailable."""
    import base64, json, urllib.request
    try:
        with open(frame_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
        prompt = "Transcribe all credit text lines in this image. Return line by line, nothing else."
        payload = {
            'model': 'qwen2.5vl:7b',
            'messages': [{'role': 'user', 'content': prompt, 'images': [img_b64]}],
            'stream': False
        }
        req = urllib.request.Request('http://localhost:11434/api/chat', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        content = json.loads(resp.read())['message']['content'].strip()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        return lines
    except Exception:
        return []


def _ocr_ar():
    global _OCR_AR
    if _OCR_AR is None:
        from paddleocr import PaddleOCR
        _OCR_AR = PaddleOCR(use_textline_orientation=False, lang="ar")
    return _OCR_AR


def satirlar_ar(frame_path: str) -> list[str]:
    try:
        r = _ocr_ar().predict(frame_path)
        if not r or not r[0]:
            return []
        rr = r[0]
        txt = rr.get("rec_texts", []) if isinstance(rr, dict) else []
        return [t.strip() for t in txt if t and t.strip()]
    except Exception:
        return _qwen_vision_ocr(frame_path, lang="ar")


# Farsça/Arapça rol sözlüğü — kasıtlı olarak SADECE ikinci-şans Arapça yolunda
# kullanılır (global _ROL/_ROL_CEKIRDEK'e KARIŞTIRILMAZ, Kiril deseniyle AYNI
# izolasyon ilkesi). کارگردان=yönetmen, تهیه=yapımcı/prodüksiyon,
# فیلمبردار=görüntü yönetmeni, تدوین=kurgu, موسیقی=müzik, بازیگران=oyuncular.
_ROL_ARAP = re.compile(r"(کارگردان|تهیه|فیلمبردار|تدوین|موسیقی|بازیگران)")

# ARAPÇA/FARSÇA HARF-NORMALİZASYONU (KANDAHAR ölçümü, alt-adım4): PaddleOCR'nin
# 'arabic' rec modeli Farsça girdide bile ARAP-standart harf biçimlerini
# üretiyor — Farsça 'ی' (FARSI YEH, U+06CC) yerine Arapça 'ي' (ARABIC YEH,
# U+064A) / 'ى' (ALEF MAKSURA, U+0649), Farsça 'ک' (U+06A9) yerine Arapça 'ك'
# (U+0643). Görsel olarak ayırt edilemez ama farklı Unicode kod noktaları —
# normalize edilmeden _ROL_ARAP (Farsça yazımıyla) HİÇ eşleşmiyordu (ölçüldü:
# KANDAHAR'da 'بازيگران'/'موسيقى' OCR çıktısı gerçek eşleşmeyi kaçırıyordu).
_ARAP_NORMALIZE = str.maketrans({
    "ي": "ی",  # ARABIC YEH -> FARSI YEH
    "ى": "ی",  # ARABIC ALEF MAKSURA -> FARSI YEH
    "ك": "ک",  # ARABIC KAF -> FARSI KEH
})


def _arapca_normalize(s: str) -> str:
    return s.translate(_ARAP_NORMALIZE)


def _isim_gibi_arap(satir: str) -> bool:
    """Arapça/Farsça satırın isim/rol-benzeri olup olmadığı — Arap alfabesinde
    büyük/küçük harf AYRIMI YOK (Kiril/Latin'deki title-case sinyali burada
    KULLANILAMAZ). Ayırt edici: rol-sözlüğü VEYA kısa satır (1-4 kelime —
    isim-listesi düzeni); uzun/çok-kelimeli satırlar ara-yazı/altyazı cümlesi
    sayılır ve reddedilir (Latin/Kiril'deki cümle-gardının kaba eşleniği)."""
    s = satir.strip().strip('"“”\'')
    if len(s) < 2:
        return False
    if _ROL_ARAP.search(_arapca_normalize(s)):
        return True
    kelimeler = s.split()
    return 1 <= len(kelimeler) <= 4


def kredi_skoru_arap(kare_satirlari: list[list[str]], yogun_esik: int = 2) -> tuple[float, list[str]]:
    """İkinci-şans Arapça/Farsça rec içerik skoru + bulunan rol listesi —
    kredi_skoru_kiril'in Arapça/Farsça eşleniği, AYNI güvenlik ilkesiyle:
    salt yoğunluk (kısa-satır sayımı) TEK BAŞINA yetmez — tespit_v5 tarafında
    yalnız `roller` GERÇEKTEN doluysa (bir _ROL_ARAP eşleşmesi varsa) kb
    override edilir."""
    if not kare_satirlari:
        return 0.0, []
    yogun = 0
    roller: set[str] = set()
    for sl in kare_satirlari:
        isim_n = sum(1 for s in sl if _isim_gibi_arap(s))
        if isim_n >= yogun_esik:
            yogun += 1
        for s in sl:
            for m in _ROL_ARAP.findall(_arapca_normalize(s)):
                roller.add(m)
    skor = round(min(1.0, yogun / 3.0), 3)
    return skor, sorted(roller)


# nokta-lider deseni: '..' / '. .' (Avrupa kredi tipografisi — rol . . isim).
# Üç-nokta (ELLIPSIS, ara-yazı/epilogda yaygın) YANLIŞLIKLA tetiklemesin diye
# etraftaki noktalar dışlanır (lookaround) — "..." iki-nokta gibi görünse de
# reddedilir (T6, ÖLDÜRME_ZAMANI atlas kanıtı).
_NOKTA_LIDER = re.compile(r"(?<!\.)\.\s*\.(?!\.)")


# ŞİRKET-KALIBI GARDI (T6 2.tur, alt-adım2 — konsey kırmızı-takım): stüdyo/
# dağıtımcı boilerplate satırları İSİM-SATIRI SAYILMAZ. Atlas kanıtı:
# DÖNÜŞÜ_OLMAYAN_NEHİR'in THE-END/Fox koşusu ("A CINEMASCOPE PRODUCTION",
# "Produced and Released by", "Twentieth Century-Fox Film Corporation")
# Title-Case/CAPS deseniyle _isim_gibi'yi yanlışlıkla geçiyordu (kb=1.0 →
# yanlış-pozitif kredi_var, kırmızı-çizgi ihlali). Gerçek 'produced by JERRY
# BRUCKHEIMER' tipi satırlar bu kalıbı İÇERMEZ (corporation/pictures/studios/
# vb yok) → etkilenmez.
_SIRKET_KALIBI = re.compile(
    r"(corporation|pictures|studios|released by|presents|cinemascope|"
    r"a\s+\w+\s+production\b)", re.I)


def _tum_kucuk_cok_kelime(s: str) -> bool:
    """Tamamı-küçük-harf ≥2 kelimeli satır mı (İtalyanca kredi isim-satırı deseni)."""
    if len(s.split()) < 2:
        return False
    return s.islower()


def _isim_gibi(satir: str, baglam: list[str] | None = None) -> bool:
    """Bir satır kredi-satırı mı (isim/rol) yoksa cümle/gürültü mü."""
    global AKTIF_DIL
    if AKTIF_DIL == "ar":
        return _isim_gibi_arap(satir)
    elif AKTIF_DIL == "ru":
        return _isim_gibi_kiril(satir)
    s = satir.strip().strip('"“”\'')
    if len(s) < 2:
        return False
    # şirket-kalıbı (T6 2.tur) → isim-satırı DEĞİL (bkz. yukarıdaki gerekçe)
    if _SIRKET_KALIBI.search(s):
        return False
    # rol keyword → kredi
    if _ROL.search(s):
        return True
    # nokta-lider deseni (Avrupa kredi tipografisi) → kredi
    if _NOKTA_LIDER.search(s):
        return True
    kelimeler = s.split()
    if not kelimeler:
        return False
    # cümle işareti (ara-yazı: "...cuff." gibi) → kredi DEĞİL
    if s.endswith((".", "?", "!")) and len(kelimeler) >= 4:
        kucuk = sum(1 for w in kelimeler if w and w[0].islower())
        if kucuk >= 2:            # birden fazla küçük-harf başlangıç = cümle
            return False
    # BÜYÜK-HARF isim (PAUL FIX) veya Title Case (Doc Cushman)
    buyuk = sum(1 for w in kelimeler if len(w) >= 2 and w.isupper())
    title = sum(1 for w in kelimeler if len(w) >= 2 and w[0].isupper() and not w.isupper())
    if buyuk >= 1 or title >= 2:
        return True
    # aynı karede rol-keyword'lü başka satır varsa, küçük-harf çok-kelimeli
    # satır da isim say (tek başına küçük-harf cümle gene reddedilir — yukarıdaki
    # cümle-gardı zaten bu satırları erken eledi).
    if baglam is not None and _tum_kucuk_cok_kelime(s) and any(_ROL.search(x) for x in baglam):
        return True
    return False


def kredi_benzeri(satir_listesi: list[str]) -> float:
    """Tek-kare skoru (geriye-uyum). Çoklu-kare için kredi_skoru_coklu kullan."""
    if not satir_listesi:
        return 0.0
    n = len(satir_listesi)
    isim = sum(1 for s in satir_listesi if _isim_gibi(s, satir_listesi))
    return round((isim / n) * min(1.0, n / 3.0), 3)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def isim_sayisi(satir_listesi: list[str]) -> int:
    """Bir karede isim-benzeri satır sayısı."""
    return sum(1 for s in satir_listesi if _isim_gibi(s, satir_listesi))


def _tek_isim_sutunu(satir: str) -> bool:
    """Tek-kelimelik Title-case satır (isim-sütunu üyesi): 'Christine' / 'McTeer'.

    Kart-başına-tek-oyuncu düzeninde her satır TEK kelime olur; _isim_gibi bunu
    kaçırır (≥2 title-kelime ister). BÜYÜK-HARF tek kelime zaten _isim_gibi'de
    sayılır — burada yalnız Title-case tekiller (çifte sayım yok)."""
    p = satir.strip().strip('"“”\'').split()
    if len(p) != 1:
        return False
    w = p[0]
    return len(w) >= 3 and w[0].isupper() and w.isalpha() and not w.isupper()


def kredi_karti_mi(satir_listesi: list[str]) -> bool:
    """Tek karenin KREDİ KARTI olup olmadığı (epilog/ara-yazı/ithaf DEĞİL).

    Konsey (GLM tur-2): gerçek ayırıcı yapısal düzen — kredi satırları noktalama
    ile BİTMEZ, rol-keyword veya isim-sütunu taşır; epilog düzyazıdır.

    isim-sütunu ayarı (T5 ölçümü, BAYAN_JULIE regresyonu): tek-kelime Title-case
    satırlar (kart-başına-tek-oyuncu düzeni) isim sayımına eklenir — film-adı
    değil YAPISAL düzen; _isim_gibi'nin ≥2-kelime şartı bu düzeni kaçırıyordu."""
    if not satir_listesi:
        return False
    isim = sum(1 for s in satir_listesi if _isim_gibi(s, satir_listesi))
    isim += sum(1 for s in satir_listesi
                if not _isim_gibi(s, satir_listesi) and _tek_isim_sutunu(s))
    rol = any(_ROL.search(s) for s in satir_listesi)
    noktali = sum(1 for s in satir_listesi
                  if s.strip().endswith((".", "!", "?", "...")) and len(s.split()) >= 4)
    if noktali >= 2 and not rol:
        return False              # düzyazı kartı (epilog/mektup/ithaf)
    return rol or isim >= 3


def kredi_skoru_coklu(kare_satirlari: list[list[str]], yogun_esik: int = 4) -> float:
    """SÜRDÜRÜLEN yoğunluk skoru — kaç kare ≥yogun_esik isim gösteriyor.

    Kritik ayrım (2026-07-21, doğrulandı): gerçek kredi yoğunluğu SÜRDÜRÜR
    (cast listesi onlarca kare boyunca çok-isimli). Gazete/afiş/arananıyor
    (MODERN "WANTED FOR Vagrancy") TEK-kare yoğun sonra kaybolur; tabela hep
    seyrek. Tek-kare tepe gazeteyi geçiriyordu; sürdürülen-yoğun-kare sayısı
    ayırır. ≥3 yoğun kare → kesin kredi, 1 → gazete insertı."""
    if not kare_satirlari:
        return 0.0
    yogun = sum(1 for s in kare_satirlari if isim_sayisi(s) >= yogun_esik)
    return round(min(1.0, yogun / 3.0), 3)
