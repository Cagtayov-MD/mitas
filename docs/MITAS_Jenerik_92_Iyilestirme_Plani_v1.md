# Jenerik Başlangıç Tespiti %92 İyileştirme Planı (v1)

> **Uygulayıcı ajanlar için:** Bu plan görev-görev uygulanır (subagent-driven).
> Adımlar `- [ ]` checkbox'lıdır. Her görev bağımsız doğrulanabilir bir çıktıyla biter.
> Orkestratör (Fable) görevler arası inceleme yapar.

**Hedef:** `tespit_v5` kapanış-jeneriği dedektörünü büyük-havuz GT'sinde %73.7'den (87/118)
**≥%92**'ye (≥109/118) çıkarmak; kredisiz-film reddi (29/30) GERİLEMEDEN.

**Mimari:** Kutu-koşusu aday üretimi korunur. Değişen: (1) kazanan koşunun BAŞLANGICI
koşu sınırı değil, scroll-tipinde HAREKET, statik-tipte İÇERİK çapasıyla belirlenir;
(2) kaçırılan krediler scroll-kurtarma + kanıt-kapılı gevşetmelerle kazanılır.
Konsey (GLM, 2 tur kırmızı-takım) girdileri işlendi; karar gerekçeleri en altta.

**Teknoloji:** Python 3 (`/opt/mitas/venvs/ocr/bin/python`), PaddleOCR (det+rec),
numpy/PIL. Tüm iş `/opt/mitas/harness/kunye_kiyas/` içinde.

## Küresel Kısıtlar

- Python: HER ZAMAN `/opt/mitas/venvs/ocr/bin/python` (sistem python'u değil).
- PaddleOCR stderr'e gürültü basar → komutlarda `2>/dev/null` kullan (çıktıyı stdout'tan oku).
- Süreç öldürme: `pkill -f` YASAK (kendi shell'ini öldürüyor, exit 144). PID-hedefli:
  `for pid in $(pgrep -f DESEN); do kill $pid; done`.
- Kareler `/opt/mitas/data/jenerik_havuz/pool_frames/<FİLM>/c_%05d.png` — arka planda
  İNDİRİLİYOR (hata filmleri önce; `veri/havuz_kur.log` ilerlemeyi gösterir). Ölçüm
  kapsam-farkındalıklı olmalı: klasörü olmayan/eksik (<50 png) filmi ATLA ve say.
- GT: `harness/kunye_kiyas/veri/dogrulama_sonuc.json` (118 film, `gercek_onset`;
  -1 = kredi yok). Tahmin arşivi: `veri/v5_tahminler.json`. BUNLARI DEĞİŞTİRME.
- Tolerans: |tahmin − gercek_onset| ≤ 20 kare (2fps → 10 sn) = doğru.
- KIRMIZI ÇİZGİ: kredisiz alt-kümede (gercek_onset=-1, 30 film) doğruluk ≥ 29/30.
  Bir değişiklik bunu düşürüyorsa GERİ ALINIR, tartışmasız.
- Aşırı-uyum yasağı: film-adına/karesine özel koşul YOK; her parametre değişikliği
  tek başına ölçülür ve gerekçesi commit mesajına yazılır.
- 🔒 Üretim dosyalarına (`scripts/mitas_pipeline.py`, `scripts/db_compose_master.py` vb.)
  DOKUNMA. Yalnız `harness/kunye_kiyas/*` ve `docs/*`.
- Commit: Türkçe, küçük ve sık. Örn. `feat(jenerik): scroll-onset otoritesi (T4)`.
- `credit_onset.py` içindeki `tespit` (v3) ve `tespit_v4` İMZALARI ve davranışı
  değişmez (42-lab regresyonu onları kullanıyor). Yeni iş `tespit_v5` ve yardımcılarında.

---

### Görev 1: Ölçüm harness'ı `olc_pool.py`

**Dosyalar:**
- Oluştur: `/opt/mitas/harness/kunye_kiyas/olc_pool.py`

**Arayüz:**
- Üretir: CLI `olc_pool.py [--sadece-hatalar] [--film AD_PARCASI]` → stdout raporu +
  `veri/olcum_son.json` (`{"kapsam":n,"dogru":k,"genel":pct,"kredi_var":{...},"kredi_yok":{...},"hatalar":[...]}`).
  Sonraki görevler her iterasyonda bunu koşar.

- [ ] **Adım 1: Kodu yaz** — tam içerik:

```python
#!/usr/bin/env python3
"""Büyük-havuz ölçümü: tespit_v5 vs doğrulanmış 118-film GT.

Kapsam-farkındalıklı: kareleri henüz inmemiş filmleri atlar ve raporlar.
Kullanım:
  olc_pool.py                 # tüm mevcut filmler
  olc_pool.py --sadece-hatalar  # GT'de karar!=dogru olan 31 film
  olc_pool.py --film TAKKELİ    # ad-parçası eşleşen tek film (ayrıntılı)
"""
import glob, json, os, sys, time

BURASI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BURASI)
import credit_onset as co

V = os.path.join(BURASI, "veri")
KOK = "/opt/mitas/data/jenerik_havuz/pool_frames"
TOL = 20


def norm(s: str) -> str:
    return s.replace("’", "'").split(" (")[0].strip()


def main() -> int:
    gt = json.load(open(f"{V}/dogrulama_sonuc.json", encoding="utf-8"))["filmler"]
    klas = {norm(os.path.basename(p.rstrip("/"))): p
            for p in sorted(glob.glob(f"{KOK}/*/"))}
    sadece_hata = "--sadece-hatalar" in sys.argv
    tekil = None
    if "--film" in sys.argv:
        tekil = sys.argv[sys.argv.index("--film") + 1]

    n_kapsam = n_dogru = 0
    kv = {"n": 0, "dogru": 0}   # kredi-var alt-küme
    ky = {"n": 0, "dogru": 0}   # kredi-yok alt-küme (KIRMIZI ÇİZGİ)
    hatalar, eksikler = [], []
    t0 = time.time()
    for x in gt:
        ad = norm(x["film"])
        if sadece_hata and x["karar"] == "dogru":
            continue
        if tekil and tekil not in ad:
            continue
        p = klas.get(ad)
        if not p or len(glob.glob(p + "*.png")) < 50:
            eksikler.append(ad)
            continue
        r = co.tespit_v5(p)
        go, pred = x["gercek_onset"], r.start_frame
        if go == -1:
            ky["n"] += 1
            ok = (pred == -1)
            ky["dogru"] += ok
        else:
            kv["n"] += 1
            ok = (pred != -1 and abs(pred - go) <= TOL)
            kv["dogru"] += ok
        n_kapsam += 1
        n_dogru += ok
        if not ok:
            hatalar.append({"film": ad, "gt": go, "tahmin": pred,
                            "sapma": (pred - go) if (go != -1 and pred != -1) else None,
                            "yontem": r.yontem, "notlar": r.notlar})
        if tekil:
            print(f"{ad}\n  gt={go} tahmin={pred} yöntem={r.yontem}\n  not={r.notlar}")
    hatalar.sort(key=lambda h: -abs(h["sapma"]) if h["sapma"] is not None else 0)
    rapor = {"kapsam": n_kapsam, "dogru": n_dogru,
             "genel": round(100 * n_dogru / max(1, n_kapsam), 1),
             "kredi_var": kv, "kredi_yok": ky,
             "eksik": len(eksikler), "sure_sn": round(time.time() - t0),
             "hatalar": hatalar}
    json.dump(rapor, open(f"{V}/olcum_son.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"\nKAPSAM {n_kapsam} (eksik {len(eksikler)})  "
          f"GENEL {n_dogru}/{n_kapsam} = %{rapor['genel']}")
    print(f"  kredi-var: {kv['dogru']}/{kv['n']}   "
          f"kredi-yok: {ky['dogru']}/{ky['n']}  (kırmızı çizgi ≥29/30)")
    for h in hatalar[:40]:
        s = f"{h['sapma']:+d}" if h["sapma"] is not None else "  - "
        print(f"  {s:>5}  gt={h['gt']:>5} v5={h['tahmin']:>5}  {h['film'][:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Adım 2: Mevcut (kısmi) karelerle koştur, doğrula**

Koş: `cd /opt/mitas/harness/kunye_kiyas && /opt/mitas/venvs/ocr/bin/python olc_pool.py --sadece-hatalar 2>/dev/null`
Beklenen: inmiş hata-filmleri için satırlar; kayıtlı sapmalarla tutarlı (örn.
TAKKELİ_MELEK +317 civarı). Kapsam, o an inmiş klasör sayısına bağlı — sorun değil.

- [ ] **Adım 3: Commit** — `git add harness/kunye_kiyas/olc_pool.py && git commit -m "feat(jenerik): büyük-havuz ölçüm harness'ı olc_pool (T1)"`

---

### Görev 2: `tespit_v5` teşhis enstrümantasyonu (davranış DEĞİŞMEZ)

**Dosyalar:**
- Değiştir: `/opt/mitas/harness/kunye_kiyas/credit_onset.py` (yalnız `tespit_v5`)

**Arayüz:**
- Üretir: `Sonuc.seri["adaylar"]` = aday başına
  `{"a":int,"b":int,"kare_a":int,"kare_b":int,"son_ok":bool,"kb":float|null,"joint":float|null,"roller":[str]}`
  (`kb=null` → SON_ERISIM nedeniyle içerik hiç değerlendirilmedi).
  `kredi_yok` notu artık sebebi ayırır: `"tüm adaylar SON_ERISIM'e takıldı"` /
  `"içerik-eşiği geçilemedi (en iyi kb=X)"` / `"kutu-koşusu yok"`.

- [ ] **Adım 1: Döngüyü yeniden düzenle** — `continue` yerine her aday için kayıt tut.
  SON_ERISIM'e takılan adayın da (ucuz olduğu için) içerik skorunu ÖLÇME — sadece
  `son_ok=False, kb=None` yaz (maliyet artmasın; Görev 3 atlası gerekirse ölçer).
  Rol-keyword listesi için `credit_content._ROL.findall` kullan (küçük-harfe indirip
  benzersizleştir). Dönüşte `seri={"adaylar": kayitlar}` doldur.
- [ ] **Adım 2: Parite testi** — davranış değişmediğinin kanıtı:

Koş: `cd /opt/mitas/harness/kunye_kiyas && /opt/mitas/venvs/ocr/bin/python credit_onset.py --v5 /opt/mitas/data/jenerik_havuz/pool_frames/1925-1185-1-0000-50-0_OPERADAKİ_HAYALET 2>/dev/null`
Beklenen: `start=1161 ... kb=1.00 joint=1.50` (bugünkü değerlerle BİREBİR aynı).
Ek: inmiş 5+ filmde `olc_pool.py --sadece-hatalar` çıktısı Görev 1'dekiyle aynı.

- [ ] **Adım 3: Commit** — `git commit -am "feat(jenerik): v5 aday-kapı teşhisi, davranış değişmedi (T2)"`

---

### Görev 3: Hata atlası — 31 hatanın kanıt-bazlı teşhisi

**Dosyalar:**
- Oluştur: `/opt/mitas/harness/kunye_kiyas/hata_atlasi.py`
- Üret: `/opt/mitas/harness/kunye_kiyas/veri/hata_atlasi.md`

**Arayüz:**
- Tüketir: Görev 2'nin `seri["adaylar"]` çıktısı.
- Üretir: hata filmi başına markdown bölümü. Görev 4–6'nın tasarım kararları
  BU DOSYADAKİ kanıta bağlanır.

- [ ] **Adım 1: `hata_atlasi.py` yaz** — GT'de `karar!="dogru"` ve karesi inmiş her film için:
  (a) `tespit_v5` koş, `seri["adaylar"]`ı listele; (b) gerçek-onset hangi adayın içinde /
  öncesinde / adaysız bölgede, yaz; (c) gerçek-onset civarındaki 3 karede (gt−2, gt, gt+4)
  `credit_content.satirlar` çıktısının ilk 8 satırını yaz; (d) gerçek-onset±10 penceresinde
  scroll istatistiği (dy>3 & corr≥.85 kare oranı; dy medyanı) yaz; (e) otomatik ön-teşhis
  etiketi: `SCROLL_GEC_BASLADI` (kazanan koşu gt'den geç ve gt-penceresi scroll'lu) /
  `SON_ERISIM_KURBANI` (gt bir adayın içinde ama o aday son_ok=False) /
  `ICERIK_REDDI` (gt adayın içinde, kb<0.6) / `KUTU_YOK` (gt hiçbir adayda değil) /
  `ERKEN_METIN` (tahmin<gt: koşu başı kredi-dışı metin) / `DIGER`.
- [ ] **Adım 2: Koştur** — `... hata_atlasi.py 2>/dev/null` → `veri/hata_atlasi.md`.
  O an inmemiş filmler "BEKLIYOR" bölümüne; indirme bitince yeniden koşulur (idempotent).
- [ ] **Adım 3: ÖZET tablosu** — atlas sonuna: etiket → film sayısı → hangi görevin
  (T4/T5/T6) hedefi. Bu tablo orkestratöre raporlanır (görevler arası inceleme noktası).
- [ ] **Adım 4: Commit** — `git add -A harness/kunye_kiyas && git commit -m "feat(jenerik): 31 hatanın kanıt atlası (T3)"`

---

### Görev 4: Scroll-tip onset otoritesi = HAREKET (+geri-genişletme)

Hedef hata sınıfı: büyük POZİTİF sapmalar (+320 MESLEĞE_DÖNÜŞ, +317 TAKKELİ_MELEK,
+176 KARAVAN, +157 DİPTEKİLER, +149 SAKLI_GERÇEKLER*, +123 "6", +83 İNİŞLİ_ÇIKIŞLI, +69
GELECEK_GÜNLER) — atlas etiketleri `SCROLL_GEC_BASLADI` / `SON_ERISIM_KURBANI`.
(*SAKLI_GERÇEKLER kaynakta yok; ölçüm dışı kalabilir.)

**Dosyalar:**
- Değiştir: `credit_onset.py` (`tespit_v5` kazanan-sonrası bölümü + `dy_cift` çağrısı)

- [ ] **Adım 1: Aliasing gardı** — `dy_cift(..., max_shift=60)` (v5 içindeki çağrılarda).
  `dys[i] >= max_shift - 2 and corrs[i] >= 0.85` kareleri de scroll-aktif say
  (hızlı akan jenerik korelasyon sınırına yapışır — GLM tur-2 uyarısı).
- [ ] **Adım 2: Scroll-tip tespiti** — kazanan koşuda scroll-aktif kare oranı ≥ 0.3
  VEYA ardışık scroll ≥ 8 sn (16 örnek-kare) ise koşu SCROLL-tip.
- [ ] **Adım 3: Hareket-otoriteli onset** — SCROLL-tip koşuda onset := kazanan koşuya
  ulaşan en erken scroll+kutu zincirinin başı. Geriye yürüyüş kuralları:
  koşu başından geriye, `scroll[i] and jbayrak[i]` kareler boyunca; araya
  `bosluk_tol` içinde kalan kısa kesintiler (kutu VEYA scroll'dan biri sürüyorsa) atlanır;
  ÖNCEKİ adayların (SON_ERISIM'e takılmış olanlar dahil) içinden geçebilir;
  toplam geri yürüyüş ≤ 120 örnek-kare (60 sn). İçerik-budama scroll-aktif kareye
  ASLA uygulanmaz (bulanık-OCR tuzağı).
- [ ] **Adım 4: Ölç** — `olc_pool.py --sadece-hatalar` → pozitif-sapma filmlerinde düzelme;
  sonra TAM `olc_pool.py` → kredi-yok 29/30 KORUNDU mu? Korunmadıysa geri al, nedenini
  atlasla açıkla.
- [ ] **Adım 5: Commit** — `git commit -am "feat(jenerik): scroll-tip koşuda hareket-otoriteli onset + geri-genişletme (T4)"`

---

### Görev 5: Statik-kart içerik çapası (ileri-budama / geri-genişletme)

Hedef hata sınıfı: NEGATİF sapmalar (−188 YALNIZ_SAVAŞÇI, −124 HARİKA_KÖPEK, −67
İKİ_KAFADAR, −63 KIZIL_HAYAT, −37 TESS, −36 POTEMKİN, −29 KNUTE_ROICKNE, −25
YÜREKTEN_SEVMEK, −21 MEVLANA) — atlas etiketi `ERKEN_METIN` (koşu başı intertitle/epilog).

**Dosyalar:**
- Değiştir: `credit_onset.py` (kazanan-sonrası), `credit_content.py` (yeni yardımcı)

- [ ] **Adım 1: `credit_content.py`'ye kart-sınıfı yardımcı** ekle:

```python
def kredi_karti_mi(satir_listesi: list[str]) -> bool:
    """Tek karenin KREDİ KARTI olup olmadığı (epilog/ara-yazı/ithaf DEĞİL).

    Konsey (GLM tur-2): gerçek ayırıcı yapısal düzen — kredi satırları noktalama
    ile BİTMEZ, rol-keyword veya isim-sütunu taşır; epilog düzyazıdır."""
    if not satir_listesi:
        return False
    isim = sum(1 for s in satir_listesi if _isim_gibi(s))
    rol = any(_ROL.search(s) for s in satir_listesi)
    noktali = sum(1 for s in satir_listesi
                  if s.strip().endswith((".", "!", "?", "...")) and len(s.split()) >= 4)
    if noktali >= 2 and not rol:
        return False              # düzyazı kartı (epilog/mektup/ithaf)
    return rol or isim >= 3
```

- [ ] **Adım 2: İleri-budama (statik-tip koşu)** — kazanan koşu scroll-tip DEĞİLSE:
  koşu başından ileri, örneklenmiş karelerde (her 2 örnek-karede bir, en çok 30 örnek-kare)
  `kredi_karti_mi` False olduğu sürece ilerle; İLK True karesi onset. Guard: budama
  koşu uzunluğunun yarısını geçemez (geçiyorsa dokunma — OCR genel başarısızlığı işareti).
- [ ] **Adım 3: Geri-genişletme (statik-tip)** — koşu başından geriye kare-kare
  (`jbayrak` şart değil — det kaçırabilir): `kredi_karti_mi` True ise onset'i geri çek;
  2 ardışık False'ta dur; toplam ≤ 120 örnek-kare.
- [ ] **Adım 4: Ölç** — önce negatif-sapma filmleri, sonra TAM ölçüm + kırmızı çizgi.
  DİKKAT: Görev 4'ün kazanımları gerilemesin (`olcum_son.json` karşılaştır).
- [ ] **Adım 5: Commit** — `git commit -am "feat(jenerik): statik kartta içerik-çapalı onset, epilog gardı (T5)"`

---

### Görev 6: Kaçırılan kredi kurtarma (11 film) — kanıt-kapılı

Hedef: DERSU_UZALA, DOĞUM_GÜNÜN, VANYA_DAYI, ÖLDÜRME_ZAMANI, MELEKLERİ_GÖRMEK,
SEN_TOM_SAWYER, KÜÇÜK_SİMBA, ROBOCOP, TAKTİKLER_SAVAŞI, KANDAHAR, ARKADAŞIMIN_EVİ.
ÖNCE atlastan gerçek ölüm sebebine bak (SON_ERISIM mi, içerik mi, kutu mu) — aşağıdaki
araçlardan YALNIZ kanıtın gösterdiklerini uygula.

**Dosyalar:**
- Değiştir: `credit_onset.py`, gerekirse `credit_content.py`

- [ ] **Adım 1: ÇEKİRDEK-ROL beyaz listesi** (`credit_content.py`):

```python
# SON_ERISIM/kurtarma gevşetmeleri SADECE çekirdek yapım rolleriyle tetiklenir;
# "distributed/production/copyright" logo-kuşağını tetiklemez (GLM tur-2).
_ROL_CEKIRDEK = re.compile(
    r"\b(director|directed|screenplay|written|writer|cinematograph|photograph|"
    r"editor|edited|music|starring|cast|"
    r"yönet|senaryo|görüntü|kurgu|müzik|oyuncu)\b", re.I)
```

- [ ] **Adım 2: Scroll-kurtarma** — hiçbir aday içerik-eşiğini geçemediyse:
  filmin son %25'inde ≥8 sn sürdürülen scroll koşusu (kutu-bayraklı) ara; koşu
  karelerinde ≥1 `_ROL_CEKIRDEK` eşleşmesi varsa KREDİ KABUL; onset = scroll başı
  (Görev 4 geri-genişletmesi uygulanır). Gerekçe: gazete/tabela/tek-intertitle KAYMAZ.
- [ ] **Adım 3: SON_ERISIM gevşetmesi** — bir aday SON_ERISIM'e takıldıysa VE
  kb≥0.9 VE `_ROL_CEKIRDEK` içeriyor VE filmin SON metin-koşusuysa: eşiği o aday
  için 0.82→0.70'e indir. (0.70'i aşan gevşetme YASAK — film-ortası insert kapısı.)
- [ ] **Adım 4: Statik-seyrek yol** — atlas "seyrek statik kredi" gösterirse:
  `kredi_skoru_coklu(..., yogun_esik=2)` yeniden-değerlendirme, AMA yalnız koşuda
  ≥2 FARKLI `_ROL_CEKIRDEK` rolü varsa (tek "Yönetmen" intertitle'ı YETMEZ — sessiz
  film kırmızı-çizgi senaryosu).
- [ ] **Adım 5: (yalnız atlas kanıtıyla) OCR ön-işleme** — rec düşük kontrastta
  okuyamıyorsa: kareyi 2× büyüt + CLAHE, yalnız içerik-değerlendirme örnek-karelerinde.
- [ ] **Adım 6: Her alt-adımdan sonra TAM ölçüm** — kredi-yok 29/30 HER adımda kontrol.
  Bir gevşetme çizgiyi bozuyorsa gevşetmeyi at, atlasa "denendi-bozdu" notu düş.
- [ ] **Adım 7: Commit** — alt-adım başına ayrı commit.

---

### Görev 7: Nihai tam ölçüm + kabul

- [ ] **Adım 1:** İndirme bitti mi? `tail veri/havuz_kur.log` → "BİTTİ" ve
  `veri/parite_rapor.txt`te FARK'lı film var mı bak (FARK'lıları rapora yaz, ölçümden çıkarma).
- [ ] **Adım 2:** TAM `olc_pool.py` (2 kez üst üste — OCR belirsizliği yoksa sonuç aynı olmalı).
- [ ] **Kabul kriterleri:** (a) genel ≥ %92; (b) kredi-yok alt-küme ≥ 29/30;
  (c) `tespit`/`tespit_v4` imzaları değişmedi; (d) hiçbir film-özel hack yok.
- [ ] **Adım 3:** %92'ye ulaşılamadıysa: kalan hataları atlas formatında belgele,
  orkestratöre eskalasyon (yeni konsey turu kararı orkestratörün).

### Görev 8: Kayıt ve kapanış

- [ ] `docs/MITAS_Jenerik_Baslangic_Tespiti_v1.md`'ye "Büyük-havuz %92 kampanyası" bölümü:
  başlangıç 87/118, hangi görev kaç film kazandırdı, konsey kararları (GLM 2 tur:
  motion-gated onset sentezi; aliasing gardı; epilog yapısal ayırıcı; çekirdek-rol listesi;
  Kimi 429 katılamadı), nihai sayı.
- [ ] `docs/GUNLUK.md`'ye oturum kaydı (en üste).
- [ ] Son commit + `git log --oneline -8` çıktısını rapora ekle.

---

## Konsey karar gerekçeleri (orkestratör hakemliği)

- GLM'in "B/C'yi çöpe at, salt hareket" önerisi KISMEN alındı: hareket otoritesi
  scroll-tip koşularda kesin doğru (bulanık-OCR/budama tuzağını kapatır) — ama statik
  kart jeneriklerde hareket sinyali YOKTUR; orada içerik çapası zorunlu (GLM'in kendi
  adım-2'si de statikte koşu sınırına düşüyordu ki bugünkü hatanın ta kendisi).
  İki tip ayrı otorite: scroll→hareket, statik→içerik.
- GLM tur-2'nin beş somut uyarısı (aliasing/max_shift, epilog yapısal ayırıcı,
  split-screen ROI, logo-kuşağı keyword'leri, arkası-videolu kart) plana işlendi;
  ROI-şeridi YAGNI — atlas split-screen vakası gösterirse eklenir.
- Kimi her iki turda da 429 (Moonshot altyapı) — edge-case merceği eksik kaldı;
  telafi: Görev 3 atlası her düzeltmeyi vaka-kanıtına bağlıyor.
