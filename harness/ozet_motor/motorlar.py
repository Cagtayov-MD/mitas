# -*- coding: utf-8 -*-
"""ozet_motor — arka-uc ve boru-hatti sekilleri.

IKI EKSEN ayri ayri olculur:
  eksen 1  ARKA UC : Ollama (bugun) / VLLM (dogru sablon, sabit baglam, AWQ, toplu is)
  eksen 2  SEKIL   : tek_atis (uretimin bugunku yolu) / cikar_ozetle (hic denenmemis)

Arka uc soyut tutuldu: vLLM'e gecis KOD degil AYAR degisikligi (Cagatay 2026-07-30).
Ikisi de OpenAI-uyumlu olmayan/olan yollari kendi icinde kapatir; cagiran ayni arayuzu gorur.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field

sys.path.insert(0, "/opt/mitas/scripts")

PROMPT_V2 = "/opt/mitas/core/api/prompts/ozet_film_v2.txt"
# Uretimle ayni kirpma esigi (mitas_pipeline.OZET_MAX_SOURCE_CHARS).
MAX_KAYNAK = 60000
_TS = re.compile(r"\[\d\d:\d\d:\d\d\]\s*")


def kaynak_metin(t: str) -> str:
    """Uretimin _ozet_source_text'i ile BIREBIR: damga soy, uzunsa bas/orta/son secki."""
    t = _TS.sub("", t or "")
    if len(t) <= MAX_KAYNAK:
        return t
    bas, orta_bas = t[:25000], max(0, len(t) // 2 - 7500)
    return (f"{bas}\n\n[... orta bolumden secki ...]\n\n{t[orta_bas:orta_bas + 15000]}"
            f"\n\n[... son bolum ...]\n\n{t[-20000:]}")


# ─────────────────────────── arka uclar ───────────────────────────

@dataclass
class Yanit:
    metin: str
    saniye: float
    girdi_token: int | None = None      # prompt_eval_count — MODELE GERCEKTEN giren token
    cikti_token: int | None = None


class Ollama:
    """ollama /api/generate. num_ctx ACIKCA verilir — uretim vermiyor, ollama'nin insafinda."""

    ad = "ollama"

    def __init__(self, model: str, num_ctx: int = 32768,
                 host: str = "http://127.0.0.1:11434", timeout: int = 600):
        self.model, self.num_ctx, self.host, self.timeout = model, num_ctx, host, timeout

    def uret(self, sistem: str, kullanici: str, max_token: int = 1500) -> Yanit:
        govde = json.dumps({
            "model": self.model, "system": sistem, "prompt": kullanici,
            "stream": False, "think": False, "keep_alive": "10m",
            "options": {"temperature": 0.0, "num_predict": max_token, "num_ctx": self.num_ctx},
        }).encode("utf-8")
        t0 = time.perf_counter()
        istek = urllib.request.Request(self.host + "/api/generate", data=govde,
                                       headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(istek, timeout=self.timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        return Yanit((d.get("response") or "").strip(), time.perf_counter() - t0,
                     d.get("prompt_eval_count"), d.get("eval_count"))


class VLLM:
    """vLLM OpenAI-uyumlu uc. think kapatma resmi yoldan (chat_template_kwargs)."""

    ad = "vllm"

    def __init__(self, model: str, host: str = "http://127.0.0.1:8101/v1", timeout: int = 600):
        self.model, self.host, self.timeout = model, host, timeout

    def uret(self, sistem: str, kullanici: str, max_token: int = 1500) -> Yanit:
        govde = json.dumps({
            "model": self.model, "temperature": 0.0, "max_tokens": max_token,
            "messages": [{"role": "system", "content": sistem},
                         {"role": "user", "content": kullanici}],
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode("utf-8")
        t0 = time.perf_counter()
        istek = urllib.request.Request(self.host.rstrip("/") + "/chat/completions", data=govde,
                                       headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(istek, timeout=self.timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        kul = d.get("usage") or {}
        return Yanit((d["choices"][0]["message"]["content"] or "").strip(),
                     time.perf_counter() - t0, kul.get("prompt_tokens"), kul.get("completion_tokens"))


# ─────────────────────────── boru hatti sekilleri ───────────────────────────

@dataclass
class Kosu:
    ozet: str
    saniye: float
    cagri: int
    girdi_token: int = 0
    ara_urun: str = ""
    ayrinti: dict = field(default_factory=dict)


def tek_atis(uc, transcript: str, baslik: str, sure: str = "—") -> Kosu:
    """Uretimin BUGUNKU yolu: tum transkript + v2 promptu → tek cagri."""
    sistem = open(PROMPT_V2, encoding="utf-8").read()
    kullanici = f"Dosya: {baslik}\nSüre: {sure}\n\nTRANSKRİPT:\n{kaynak_metin(transcript)}"
    y = uc.uret(sistem, kullanici)
    return Kosu(y.metin, y.saniye, 1, y.girdi_token or 0)


_PARCA_SORU = (
    "Aşağıdaki metin bir Türkçe filmin transkriptinin {i}/{n} numaralı bölümüdür (ASR çıktısı, "
    "gürültülü, tekrarlı, konuşmacı etiketi YOK).\n"
    "{kisiler}"
    "SADECE bu bölümde GERÇEKTEN geçen somut olayları yaz.\n"
    "Kurallar: kim ne yaptı / kime yaptı AÇIK olsun. 'O', 'adam', 'kadın' gibi belirsiz özne "
    "kullanma — yukarıdaki kişi listesinden hangisi olduğunu yazabiliyorsan adını yaz, "
    "emin değilsen 'kim olduğu net değil' diye belirt. Tahmin, yorum, tema, çıkarım YOK. "
    "Olmayan olayı UYDURMA. Bölümde kayda değer olay yoksa 'kayda değer olay yok' yaz.\n"
    "En fazla {madde} madde, her madde tek satır, madde başına '- ' koy. Türkçe.\n\n"
    "--- BÖLÜM {i}/{n} ---\n{metin}\n\n--- BU BÖLÜMÜN OLAYLARI ---"
)

_FINAL_SORU = (
    "Aşağıdaki metin bir Türkçe filmin SON BÖLÜMÜDÜR (filmin son üçte biri).\n"
    "{kisiler}"
    "Filmin NASIL BİTTİĞİNİ yaz: kim öldü, kim kazandı, kim kavuştu, hangi sır açığa çıktı, "
    "kim nereye gitti.\n"
    "SADECE metinde açıkça geçeni yaz; belirsizse 'net değil' yaz, UYDURMA. Kişileri adıyla yaz.\n"
    "En fazla 5 madde, her madde tek satır, '- ' ile başla. Türkçe.\n\n"
    "--- SON BÖLÜM ---\n{metin}\n\n--- FİLMİN BİTİŞİ ---"
)

_AD_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]{2,})\b")
_AD_DISI = {
    "Bu", "Şu", "Bir", "Ancak", "Fakat", "Ama", "Sonra", "Sonunda", "Finalde", "Böylece",
    "Her", "Kendi", "Onun", "Bunun", "İki", "Üç", "Daha", "Yıllar", "Genç", "Küçük", "Büyük",
    "Yeni", "Eski", "Son", "İlk", "Evet", "Hayır", "Tamam", "Hadi", "Bak", "Gel", "Git",
    "Bölüm", "Filmin", "Film", "Kayda", "Merhaba", "Baba", "Anne", "Abi", "Peki", "Neden",
}


def _adlari_topla(metin: str, sayi: int = 12) -> list[str]:
    """Metinden ozel-ad adaylarini topla (deterministik, LLM cagrisi YOK).

    Konsey bulgusu (GLM + nemotron, 2026-07-30): parcali hattin tek-atistan DAHA KOTU olabilecegi
    tek yer coreference kopugu — parca 4'teki "o" kim, model bilmiyor. Bu liste her parcaya
    tasinir; ucuz panzehir.

    CUMLE-BASI TUZAGI: Turkce'de "Ben/Sen/Bana/Cok" cumle basinda buyuk harfle baslar ve ad
    sanilir. Cozum: bir sozcugu ancak CUMLE ORTASINDA da buyuk harfle gectiginde ad sayariz —
    ozel adin ayirt edici imzasi budur. transcript_plain.txt satir basina bir replik oldugundan
    satir basi = cumle basi.
    """
    orta_sayac: dict[str, int] = {}      # cumle ORTASINDA buyuk harfle gecis (guclu ad sinyali)
    for satir in (metin or "").splitlines():
        # Satiri cumlelere ayir; her cumlenin ILK sozcugunu atla, gerisindeki buyuk harflileri say.
        for cumle in re.split(r"(?<=[.!?])\s+", satir.strip()):
            sozcukler = cumle.split()
            for s in sozcukler[1:]:
                t = s.strip(".,!?:;\"'()…-")
                if len(t) > 2 and _AD_RE.fullmatch(t) and t not in _AD_DISI:
                    orta_sayac[t] = orta_sayac.get(t, 0) + 1
    # En az 2 kez cumle-ortasinda gecmis olsun — tek seferlik ASR gurultusunu eler.
    adaylar = [(a, n) for a, n in orta_sayac.items() if n >= 2]
    return [a for a, _ in sorted(adaylar, key=lambda kv: -kv[1])[:sayi]]


def _satirdan_bol(metin: str, n: int) -> list[str]:
    """Transkripti SATIR sinirindan n parcaya bol (cumle ortasindan kesme YOK).

    transcript_plain.txt zaten satir basina bir replik; karakterden bolmek replikleri ortadan
    kesiyordu (konsey: 'semantik kesen kesisimi')."""
    satir = [s for s in (metin or "").splitlines() if s.strip()]
    if not satir:
        return [""] * n
    adim = len(satir) / n
    return ["\n".join(satir[round(i * adim):round((i + 1) * adim)]) for i in range(n)]


def cikar_ozetle(uc, transcript: str, baslik: str, sure: str = "—", n_parca: int = 6,
                 final_uc=None, topla_uc=None) -> Kosu:
    """Cikar-sonra-ozetle: parca parca OLGU cikar + AYRI final turu → olay-listesi → v2 promptu.

    Neden: bake-off'un A (kilit donum atlama) ve B (kim-kime tersine) kovalari uzun baglamda
    dikkat dagilmasi hatalari; parcalayinca her cagri kisa baglam gorur. C (final uydurma) icin
    son bolume AYRI, adanmis bir tur var. Bake-off'un kendi arastirma notu: extract-then-abstract
    +%15-35 sadakat — ama o turda HIC denenmedi.

    KONSEY DUZELTMELERI (2026-07-30 kirmizi takim, GLM + nemotron):
      1. Satirdan bolme  — karakterden bolme repligi ortadan kesiyordu.
      2. Kisi listesi tasima — parcalar arasi coreference kopugu (parcalamanin EN BUYUK riski).
      3. Final SON IKI parcadan — cerceve-hikayeli filmde final son 1/6'da degil.
      4. Final ONCELIKLI etiketi — son parca hem dongude hem finalde geciyordu, celiski uretiyordu.
      5. Madde/token butcesi parca boyuna gore — sabit 6 madde uzun parcada bilgi kirpiyordu.
    """
    t0 = time.perf_counter()
    metin = _TS.sub("", transcript or "")
    parcalar = _satirdan_bol(metin, n_parca)

    # Kisi listesi TUM transkriptten bir kez cikarilir (deterministik, bedava) — her parca
    # ayni kanonik listeyi gorur, boylece "o" zamirleri ayni kisiye baglanir.
    kisiler = _adlari_topla(metin)
    kisi_satiri = (f"Filmde geçen kişi adları (transkriptin tamamından): {', '.join(kisiler)}.\n"
                   if kisiler else "")

    cagri, girdi = 0, 0
    olaylar = []
    for i, p in enumerate(parcalar, 1):
        # Parca ne kadar uzunsa o kadar madde/token — sabit 6 madde uzun parcayi kirpiyordu.
        kelime = len(p.split())
        madde = min(10, max(5, kelime // 250))
        y = uc.uret("Sen bir film transkriptinden olay çıkaran bir asistansın. Sadece metinde "
                    "açıkça geçeni yazarsın; uydurmazsın.",
                    _PARCA_SORU.format(i=i, n=n_parca, metin=p, kisiler=kisi_satiri, madde=madde),
                    max_token=min(700, 120 + madde * 55))
        cagri += 1
        girdi += y.girdi_token or 0
        olaylar.append(f"[Bölüm {i}/{n_parca}]\n{y.metin}")

    # Final/toplama AYRI motora verilebilir (2026-07-30): olculdu ki 8B cikarabiliyor ama
    # final belirleme ve sikistirma kavrama istiyor. fuc/tuc verilmezse uc'un kendisi kullanilir.
    fuc, tuc = (final_uc or uc), (topla_uc or uc)
    # Final: SON IKI parca (son 1/3). Cerceve-hikayeli/zaman-atlamali filmde bitis son 1/6'da olmaz.
    son_blok = "\n".join(parcalar[-2:]) if n_parca >= 2 else parcalar[-1]
    yf = fuc.uret("Sen bir film transkriptinin son bölümünden filmin bitişini çıkaran bir "
                 "asistansın. Sadece metinde açıkça geçeni yazarsın; uydurmazsın.",
                 _FINAL_SORU.format(metin=son_blok, kisiler=kisi_satiri), max_token=350)
    cagri += 1
    girdi += yf.girdi_token or 0

    tahta = ("\n\n".join(olaylar)
             + "\n\n[FİLMİN BİTİŞİ — son bölümden ayrıca çıkarıldı, ÖNCELİKLİDİR: yukarıdaki "
               "bölüm notlarıyla çelişirse BU doğrudur]\n" + yf.metin)

    sistem = open(PROMPT_V2, encoding="utf-8").read()
    kullanici = (
        f"Dosya: {baslik}\nSüre: {sure}\n\n"
        "Aşağıdaki liste, filmin transkriptinden bölüm bölüm çıkarılmış OLAY NOTLARIDIR "
        "(transkriptin kendisi değil). Bölümler filmin ZAMAN SIRASINA göre dizilidir. "
        "Bu notlara dayanarak özeti yaz. Notlarda olmayan hiçbir şey ekleme. Madde madde "
        "değil, akıcı tek paragraf yaz.\n\nOLAY NOTLARI:\n" + tahta
    )
    y = tuc.uret(sistem, kullanici)
    cagri += 1
    girdi += y.girdi_token or 0
    return Kosu(y.metin, time.perf_counter() - t0, cagri, girdi, ara_urun=tahta,
                ayrinti={"n_parca": n_parca, "kisiler": kisiler, "final_turu": yf.metin})


SEKILLER = {"tek_atis": tek_atis, "cikar_ozetle": cikar_ozetle}
