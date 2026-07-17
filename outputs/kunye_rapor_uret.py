#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Eksik-künye kök-neden RAPORU üret (markdown). Kaynak: final verdicts + evidence + audit."""
import json, datetime
from collections import Counter, defaultdict

FINAL = r"E:\MITAS\outputs\kunye_rootcause_final.json"
EV    = r"E:\MITAS\outputs\kunye_eksik_evidence.json"
AUDIT = r"E:\MITAS\outputs\kunye_eksik_audit.json"
OUT   = r"E:\MITAS\outputs\KUNYE_EKSIK_KOK_NEDEN_RAPORU_2026-06-14.md"

final = json.load(open(FINAL, encoding="utf-8"))
films = final["filmler"]
ev = {e["folder"]: e for e in json.load(open(EV, encoding="utf-8"))}
audit = json.load(open(AUDIT, encoding="utf-8"))
arows = {r["folder"]: r for r in audit["rows"]}
asum = audit["summary"]

# (açıklama, pipeline-yeri, KATMAN)  Katman: A=mevcut OCR'dan kurtarılabilir, B=yeniden-işleme gerek, C=dış-veri/gerçek-eksik
STEP_INFO = {
    "S2_ROL_ESLEME":     ("İsim filtreli kunye.txt'de VAR ama rol-eşleme adımı final'e yanlış aldı/atladı (cast↔yönetmen↔yapımcı takası, üst-billing'i tanıyamama)", "Aşama 2 (credit_text_read/rol)", "A"),
    "S1_FILTRE_DUSURDU": ("İsim ham OCR'da bitişik VAR ama temizleme/garble filtresi kunye.txt'ye geçirmeden düşürdü", "Aşama 1 (stitch/clean)", "A"),
    "GARBLE_KONTAMINASYON": ("Final alanı garble/şirket-adı/başlık ile dolmuş (filtre+rol garble'ı geçirdi)", "Aşama 1-2", "A"),
    "S5_6_QC_DUSURDU":   ("Değer vardı ama QC kapısı (garble/çelişki/charset) boşa/Kontrol'e düşürdü", "Aşama 5-6 (QC)", "A"),
    "S1_FRAME_KAPSAM":   ("Kare var ama yönetmen/cast kartı yakalanan karelerin dışında / düşük-kontrast diegetik (canlı sahne üstü yazı) jenerik sayılmamış → isim OCR'a hiç girmemiş", "Aşama 1 (kare-seçim/CLIP)", "B"),
    "S1_OCR_OKUYAMADI":  ("Karede yazı var ama OCR motoru okuyamadı/çöp okudu (arşiv/düşük kalite/yabancı alfabe)", "Aşama 1 (OCR motoru)", "B"),
    "S0_CIKTI_YOK":      ("Çıktı yok — pipeline künye/PDF adımına gelmeden kesilmiş (yarım işlem)", "Aşama 0/sonrası", "B"),
    "S1_FRAME_YOK":      ("Jenerik karesi hiç yakalanmamış", "Aşama 1 (kare)", "B"),
    "S4_ROL_AKLI":       ("rol_reconcile/XML/KB adımı değeri yanlış taşıdı/sildi", "Aşama 4 (rol-aklı)", "A"),
    "GERCEKTEN_YABANCI": ("Film gerçekten yabancı; jenerik yabancı-dilde, Türkçe rol etiketi yok → pipeline yabancı şirket metni okudu. Pipeline kusuru DEĞİL; dış-veri/web gerekir", "—", "C"),
    "GERCEKTEN_YOK":     ("İlgili alan jenerikte gerçekten yok (eski film, ayrı yapımcı yok vb.) → gerçek eksiklik, hata değil", "—", "C"),
    "BELIRSIZ":          ("Kanıt yetmedi", "—", "B"),
}
TIER_NAME = {"A": "Mevcut OCR'dan kurtarılabilir (ucuz, yeniden-işleme YOK)",
             "B": "Yeniden-işleme gerek (kare/OCR adımı yeniden koşmalı)",
             "C": "Dış-veri / gerçek-eksik (pipeline kusuru değil)"}

by_step = defaultdict(list)
for f in films:
    by_step[f.get("step","BELIRSIZ")].append(f)

def tier_of(step):
    return STEP_INFO.get(step, ("","","B"))[2]

n = len(films)
tier_cnt = Counter(tier_of(f.get("step","BELIRSIZ")) for f in films)
nA, nB, nC = tier_cnt.get("A",0), tier_cnt.get("B",0), tier_cnt.get("C",0)

def short(s, m=180):
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= m else s[:m-1] + "…"

def fields(f):
    fr = f.get("eksik_alanlar") or arows.get(f.get("folder"),{}).get("flag_reasons",[])
    return ", ".join(fr)

L = []
W = L.append
W(f"# MİTAS — Eksik Künye Kök-Neden Raporu")
W(f"*Üretim: {datetime.date.today().isoformat()} · Kaynak: E:\\MITAS\\Database · Orijinal pipeline çıktısı (kunye_teslim.md = kunye.pdf)*\n")

W("## 1. Özet")
W(f"- **Taranan film/klasör:** {asum['toplam_klasor']}")
W(f"- **Eksik (flagli):** {asum['flagli']}  ·  **Temiz:** {asum['temiz']}")
W(f"  - Yönetmen boş: {asum['yonetmen_bos']}  ·  Yapımcı boş: {asum['yapimci_bos']}  ·  Cast ≤ 6: {asum['cast_6_alti']}  ·  Hiç çıktı yok: {asum['no_output']}")
W(f"- **Kök-neden teşhisi:** {n} eksik film, her biri ham OCR'a inilerek pipeline adımına bağlandı; {final['dogrulanan']}'i bağımsız 2. ajanla çapraz-doğrulandı.")
W(f"- **Düzeltilebilirlik katmanı:**")
W(f"  - 🟢 **Katman A — Mevcut OCR'dan kurtarılabilir (yeniden-işleme YOK): {nA} film.** Veri zaten kunye.txt/ham OCR'da; sadece seçim/atama/filtre yanlış.")
W(f"  - 🟡 **Katman B — Yeniden-işleme gerek: {nB} film.** İsim mevcut OCR'da yok; daha sık kare / daha iyi kare-seçim / OCR yeniden koşmalı (veya yarım işlem tamamlanmalı).")
W(f"  - ⚪ **Katman C — Dış-veri/gerçek-eksik (pipeline kusuru değil): {nC} film.** Yabancı jenerik veya alan gerçekten yok → web/KB ile doldurulur ya da olduğu gibi doğrudur.\n")

W("> **Yöntem notu & düzeltme (şeffaflık):** Tespit deterministik yapıldı (438 klasörde hiçbir film atlanmasın + cast sayımı birebir doğru olsun diye, 4 LLM ajanı yerine). Sebep teşhisi 50+ Sonnet ajanı + çapraz-doğrulama ile yapıldı. İlk turda isim-OCR eşleştirmesini ad/soyadı **ayrı token** arayarak yaptım; bu **yanlış-pozitif** üretti (ör. \"Yılmaz Erdoğan\" → grip \"Erdoğan Gündoğdu\"). Kusur bulununca matcher **ad+soyad bitişik** şartına çevrildi (yönetmen isimlerinin %17'si düzeldi), ajan prompt'u sertleştirildi ve tüm teşhis **temiz veriyle baştan** koşuldu. Bu rapor düzeltilmiş veriye dayanır.\n")

W("## 2. Kök-Neden Dağılımı (pipeline adımına göre)\n")
W("| Adım kodu | Katman | Pipeline yeri | Film | Anlamı |")
W("|---|:--:|---|---:|---|")
order = ["S2_ROL_ESLEME","S1_FRAME_KAPSAM","S1_OCR_OKUYAMADI","GARBLE_KONTAMINASYON","S1_FILTRE_DUSURDU","S5_6_QC_DUSURDU","S0_CIKTI_YOK","S1_FRAME_YOK","GERCEKTEN_YABANCI","GERCEKTEN_YOK","BELIRSIZ"]
for s in order:
    if s not in by_step: continue
    desc, loc, tier = STEP_INFO.get(s, ("?","?","B"))
    W(f"| **{s}** | {tier} | {loc} | {len(by_step[s])} | {desc} |")
W(f"| **TOPLAM** | | | **{n}** | A={nA} · B={nB} · C={nC} |\n")

W("## 3. En Kritik İki Pipeline Hatası\n")
W(f"**① S2_ROL_ESLEME ({len(by_step.get('S2_ROL_ESLEME',[]))} film) — en büyük tek hata sınıfı.** İsim OCR'da okunmuş, filtreyi geçip `kunye.txt`'ye girmiş, ama final künyeye yanlış alınmış: ya rol takası (oyuncu→yönetmen yazılmış, gerçek yönetmen düşmüş), ya üst-billing oyuncu bloğu (rol-etiketsiz, yabancı-dil karma) tanınmayıp sadece \"ADDITIONAL CAST\" bloğu alınmış. **Kurtarılabilir — veri elimizde, sadece seçim/atama yanlış.**\n")
W(f"**② S1_FRAME_KAPSAM ({len(by_step.get('S1_FRAME_KAPSAM',[]))} film) — ikinci büyük, mimari kör nokta.** Jenerik siyah-karta değil canlı sahne üstüne düşük-kontrastlı biniyor (diegetik) ya da yönetmen kartı yakalanan karelerin dışında kalıyor. Pipeline'ın CLIP kare-seçimi bunları \"jenerik değil\" sayıp atlıyor → isim OCR'a **hiç girmiyor**. KELEBEĞİN RÜYASI tam bu sınıf.\n")

W("## 4. Elle Doğrulanmış Vaka Çalışmaları\n")
W("**KELEBEĞİN RÜYASI (2013-9098)** — *senin örneğin.* Kareler tam (360 giriş + 480 çıkış). Yönetmen **Yılmaz Erdoğan pipeline OCR'ında YOK**; ama kareyi taze OCR'layıp gözle bakınca **g_0103–g_0109'da net** (\"...and YILMAZ ERDOĞAN\", tren penceresi üstü düşük-kontrast diegetik). Cast (Belçim Bilgin, Mert Fırat→\"MO JIRAT\", Farah Zeynep→Yunan-glyph) okunmuş ama final'e ekip-ünvanları yazılmış. → **S1_FRAME_KAPSAM (yönetmen) + S2_ROL_ESLEME (cast).**\n")
W("**GÖZEMLİ GÖZ / The Touch (1973-0220)** — Gerçek yönetmen \"Peter Pau\" hem ham OCR'da hem `kunye.txt`'de **bitişik var**, ama final yönetmen alanına oyuncular (Michelle Yeoh, Ben Chaplin) yazılmış, Peter Pau düşmüş. → **S2_ROL_ESLEME (saf rol-takası).**\n")
W("**ANILAR / Memoria (2022-1196)** — Gerçekten yabancı (İspanyolca/İngilizce jenerik, Tilda Swinton). Pipeline şirket adlarını cast/yönetmen sanmış. → **GERCEKTEN_YABANCI (pipeline-bug değil; web/KB gerek).**\n")
W("**DİNLE NEYDEN (2010-9274)** — Orijinal çıktı: 1 cast, yönetmen/yapımcı boş. Düzeltme verisi gerçek 8 cast + yönetmen Jacques Deschamps + yapımcı Özkul Eren içeriyor → veri kurtarılabilirdi.\n")
W("**13 → 7 ÇIKTI-YOK** — Hepsi son 1-3 günde içe alınmış (bazıları `_2/_3` kopya); OCR var ama künye→PDF adımı henüz koşmamış. **Künye hatası değil, işlem yarım** (canlı batch + Database konsolidasyonu sürüyordu). Batch bitince yeniden bakılmalı.\n")

# adım bazlı film listeleri
def table(step, title):
    fl = sorted(by_step.get(step, []), key=lambda x: x.get("baslik") or "")
    if not fl: return
    W(f"### {title}  ({len(fl)} film)\n")
    W("| Başlık | TRT | Eksik | Güven | Kanıt (özet) |")
    W("|---|---|---|---|---|")
    seen=set()
    for f in fl:
        key=(f.get("trt"),f.get("baslik"))
        if key in seen: continue
        seen.add(key)
        W(f"| {short(f.get('baslik') or arows.get(f.get('folder'),{}).get('baslik',''),40)} | {f.get('trt','')} | {short(fields(f),22)} | {f.get('guven','')} | {short(f.get('kanit') or f.get('step_aciklama'),160)} |")
    W("")

W("## 5. Film Listeleri (adım bazlı)\n")
W("### 5A. PIPELINE HATALARI (kurtarılabilir)\n")
table("S2_ROL_ESLEME", "S2_ROL_ESLEME — okundu, filtreyi geçti, final'de yanlış/atlandı")
table("S1_FRAME_KAPSAM", "S1_FRAME_KAPSAM — düşük-kontrast/diegetik jenerik kareden alınamadı")
table("S1_OCR_OKUYAMADI", "S1_OCR_OKUYAMADI — OCR motoru okuyamadı")
table("GARBLE_KONTAMINASYON", "GARBLE_KONTAMINASYON — final garble/şirket-adı ile dolu")
table("S1_FILTRE_DUSURDU", "S1_FILTRE_DUSURDU — ham OCR'da vardı, temizleme filtresi düşürdü")
table("S5_6_QC_DUSURDU", "S5_6_QC_DUSURDU — QC kapısı düşürdü")
table("S0_CIKTI_YOK", "S0_CIKTI_YOK — pipeline künye/PDF adımına gelmeden kesildi")
table("S1_FRAME_YOK", "S1_FRAME_YOK — jenerik karesi hiç yok")
W("### 5B. PIPELINE HATASI DEĞİL (dış-veri gerek / gerçek eksiklik)\n")
table("GERCEKTEN_YABANCI", "GERCEKTEN_YABANCI — yabancı film, yabancı-dil jenerik")
table("GERCEKTEN_YOK", "GERCEKTEN_YOK — alan jenerikte gerçekten yok")
table("BELIRSIZ", "BELIRSIZ — kanıt yetmedi")

W("## 6. Öncelik (en çok film kurtaran düzeltme — bilgi amaçlı, düzeltme istenmedi)\n")
W(f"1. **Aşama 2 rol-eşleme** → ~{len(by_step.get('S2_ROL_ESLEME',[]))} film: üst-billing oyuncu bloğunu tanı, rol-takasını engelle (gerçek yönetmen kunye.txt'de mevcutken oyuncu yazılmasın).")
W(f"2. **Aşama 1 diegetik kare-seçimi** → ~{len(by_step.get('S1_FRAME_KAPSAM',[]))} film: düşük-kontrast/canlı-sahne-üstü jeneriği CLIP eşiğinde jenerik say.")
W(f"3. **Aşama 1 garble/temizleme** → ~{len(by_step.get('S1_FILTRE_DUSURDU',[]))+len(by_step.get('GARBLE_KONTAMINASYON',[]))} film: okunan ismi düşürme + garble'ı final'e geçirme.")
W(f"4. **Yabancı film yolu** → ~{len(by_step.get('GERCEKTEN_YABANCI',[]))} film: web/KB ile doldur (OCR-otorite korunarak).")
W(f"5. **Yarım işlemler** → {len(by_step.get('S0_CIKTI_YOK',[]))} film + 13 ham no-output: batch tamamlanınca künye→PDF adımını koştur.\n")

W("## 7. Uyarılar\n")
W("- Snapshot: tarama sırasında Database **konsolidasyon + canlı gece-batch** altındaydı; `_2/_3` kopyalar ve birkaç in-flight klasör bu yüzden. Bulguların gövdesi (eski/stabil filmler) sağlam; in-flight/no-output set batch bitince yeniden bakılmalı.")
W("- Detay JSON: `outputs/kunye_rootcause_final.json` (film-film, kanıt+güven), `outputs/kunye_eksik_evidence.json` (deterministik kanıt), `outputs/kunye_eksik_audit.json` (ham tespit).")

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("RAPOR ->", OUT)
print("toplam satır:", len(L))
print(f"\nKatman: A={nA} (kurtarılabilir) · B={nB} (yeniden-işle) · C={nC} (dış-veri/gerçek-eksik)")
for s in order:
    if s in by_step:
        print(f"  {len(by_step[s]):3d}  [{tier_of(s)}]  {s}")
