# Kobe kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Her iş biriminden sonra güncellenir ve commit'lenir.
> Plan: `docs/superpowers/plans/2026-08-12-allstar-kobe-kulesi.md`
> Spec: `docs/superpowers/specs/2026-08-12-allstar-kobe-kulesi-design.md`

**Son güncelleme:** 2026-08-13 — **ÇIKIŞ TAMAM, GİRİŞ TASARLANDI.**
Üç ölçüm kapısı sapma sıfır geçti, testler 61/61. Giriş bloğu için karar
alındı ama HENÜZ YAZILMADI — aşağıdaki 'SIRADAKİ İŞ' bölümü.

---

## Değişmez kurallar (her oturumda geçerli)

- **`ollama.service` DURDURULMUŞ kalır.** Ölçüm kapıları buna bağlı; açılırsa
  skor ~%93.6'ya iner ve kapı sahte alarm verir. Her ölçümden önce
  `systemctl is-active ollama` → `inactive` doğrula.
- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Ağaçta
  bu işe ait olmayan 9 değişik + 68 silinmiş (`mutfak/`) dosya var. Yalnız adı
  geçen yolları sahnele.
- **Üretim durmuş.** Hiçbir toplu koşu başlatma.
- **`gereksinimler.txt`'ten paket çıkarma.** Kobe'nin çıktısı, kodunun hiç
  import etmediği paketlere bağlı (aşağıdaki ders). Çıkarmadan önce 110 filmlik
  ölçümü koş ve sapma sıfır olduğunu gör.
- Ölçüm referansı: **kapsam 110, doğru 104, genel %94.5, üretim %97.3,
  kredi-var 75/81, kredi-yok 29/29, eksik 5**.
- Ölçüm komutu (~140 sn):
  `cd /opt/mitas/Allstar/kobe/olcum && ../venv/bin/python olc_pool.py --paralel 8`
- Kare havuzu artık kulenin içinde: `Allstar/kobe/havuz/` (git'te değil).

---

## Tamamlanan

| # | İş | Kanıt |
|---|---|---|
| 1 | Ölçüm ÖNCE + geri-dönüş noktası | `raporlar/olcum_ONCE.json`, `d497bdb0` |
| 2 | Kendi çalışma zamanı (`venv/`, paddle 3.3.1+CUDA, 167 pin) | `venv_kur.sh`, `9f24a769` |
| 4 | Dosya taşıma + import yolları + `figo` adının silinmesi | `3577c8b9` |
| 5 | Testler kule içine taşındı | 19/19 |
| 6 | **TAŞIMA KAPISI** — yeni yol + eski venv = %94.5 | `raporlar/olcum_SONRA_tasima.json`, `a875b43d` |
| 7 | `sozlesme.py` — `Girdi`/`Cikti`/`ariza`, atomik yazım + `_TAMAM` | 12/12, `31f9abe7` |
| 8 | `main.py` + `kobe` + `config.yaml` — CLI, toplu kuyruk | 8/8 (toplam 39/39), `b733e85a` |
| 3 | **KULE KAPISI** — kendi venv'iyle %94.5, sapma sıfır | `raporlar/olcum_SONRA.json`, `8bd5b4ad` |
| 8b | Uçtan uca gerçek koşu + `golden/tek_film.json` demiri | POTEMKİN → kare 1133, 21.4 sn |
| 10 | Ölçüm havuzu içeri alındı (`havuz/`, 120 film, 28 GB) | taşıma sonrası ölçüm %94.5, sapma sıfır |

**Kule çalışıyor.** Uçtan uca doğrulandı:

```bash
./Allstar/kobe/kobe tek --kareler <kare-dizini> --film-id <id>
# → out/<id>/kobe.json + _TAMAM, geçici dosya yok, dış dizine dokunulmaz
```

## Çözülen kusur — pahalı ders (kaydedildi)

Kobe kendi venv'iyle önce **%92.7** verdi (%94.5 değil): iki film doğru →
`KREDI_YOK` (`MELEKLERİ`/Kiril, `ARKADAŞIMIN`/Farsça), bir film 2 kare kaydı.

**Kök sebep: eksik paketler.** İlk denemede `venvs/ocr`'dan elle seçilmiş
16 paketlik bir pin listesi kullanılmıştı. Altı kilit paket (paddle 3.3.1,
paddleocr 3.7.0, paddlex 3.7.2, numpy 2.3.5, pillow 12.1.0, opencv 5.0.0.93)
**ikisinde de birebir aynı** olduğu halde sonuç sapıyordu. Eksik 76 paket
kurulunca skor **tam olarak** geri geldi.

> **Ders:** Kobe'nin çıktısı, kodunun **hiç import etmediği** paketlere bağlı.
> `motor.py`/`kutu.py`/`icerik.py` hiçbiri torch, sklearn, easyocr, timm veya
> transformers'a dokunmuyor. "Hangi paket önemli" TAHMİN EDİLMEZ — ortam bütün
> olarak dondurulur.

Elenen şüpheliler (tekrar deneme): Paddle/CUDA yapısı (ikisi de 3.3.1 / CUDA
12.6 / cuDNN 9.5.1 / commit `7688495538f4`), det önbelleği (118 dosya,
değişmemiş), model ağırlıkları (dokunulmamış), ölçüm gürültüsü (`venvs/ocr`
iki koşuda birebir aynı).

## Kalan iş yok — kule teslim edildi

| # | İş | Kanıt |
|---|---|---|
| 9 | `README.md`, `CHANGELOG.md`, `Allstar/MAP.md`, `Players/` silindi | `b4c9e9a7` |
| — | Canlı koddan `FIGO` adı temizlendi | `b357365b` |
| — | `docs/GUNLUK.md` kaydı | `e7f6ebd6` |

## SIRADAKİ İŞ — Kobe giriş bloğu (2026-08-13 kararları)

> Bu bölüm yeni oturum için yazıldı. Kod yazılmadı, kararlar alındı.

### Karar 1 — Kobe = SINIR, Nash = HAVUZ

Giriş+çıkış **aynı kulede** kalır (Çağatay: *"görev tek aslında — filmin giriş
çıkış jenerik tespiti"*). Ama Kobe yalnız **sınır** bulur; kare havuzu kurmak
**Nash'in** işidir.

| Kule | İş |
|---|---|
| **Kobe** | Jenerik nerede **başlıyor/bitiyor** (giriş + çıkış) |
| **Nash** | Kobe'nin sınırından **kare havuzu** ayıklar |

Nash'in stratejisi zaten mevcut: `core/pipelines/ocr/jenerik_frame_pool_detector.py`
(2200+ satır — kare skorlama, Paddle rafine, çok-dilli kredi-rol sözlüğü) +
`scripts/giris_jenerik_havuzu.py` (33 KB, giriş havuzu kurucusu).

**Sonuç: havuz filtreleme Kobe'ye HİÇ girmez.** Kobe tek iş yapar.

### Karar 2 — Kod ayrımı: giriş ve çıkış blokları karışmaz

Çağatay: *"kod olarak Kobe'ye karışmasını istemiyorum, herkesin kendi işi."*
Bu sadece düzen değil **koruma**: giriş yazılırken `src/motor.py`'ye tek satır
dokunulmazsa **%94.5 riske girmez.**

```
src/
├─ cikis/   ← bugünkü motor.py — DONMUŞ, dokunulmaz
├─ giris/   ← yeni blok
└─ ortak/   ← kutu.py + icerik.py (ALET: karar vermez, soru sorar)
```

`main.py` yönlendirici olur: `--bolum`'a göre hangi bloğu çağıracağını bilir,
işin nasıl yapıldığını bilmez.

**Karar mantığı asla paylaşılmaz** — `SON_ERISIM=0.82` çıkış bloğunda kalır,
giriş onu hiç görmez.

### Karar 3 — Giriş (a) ZATEN VAR, yeniden yazılmayacak

Mevcut tasarım (`scripts/mitas_pipeline.py:1982-2002`, Çağatay kuralı 2026-06-15):

```
head = 240 sn                                    ← MITAS_OCR_HEAD varsayılanı
jenerik_detector(prefer="first") → {start_sec, end_sec, confidence}

güven ≥ eşik  →  giris_start = start_sec − 5     ← "0'dan DEĞİL"
                 head       = end_sec + 5        ← tavan 720 (emniyet)
güven < eşik  →  head = 240, start = 0           ← sabit geri düşüş
```

Kod içi gerekçe: *"öncesi logo/cold-open footage → süpürme = gürültü."*
Uyarlanır pencere, hem başlangıç hem bitiş, açık geri düşüş. **Kötü değil.**

> **DİKKAT — düzeltilmiş hata:** Bu belgenin önceki taslağında giriş penceresi
> için 600 sn öneriliyordu. YANLIŞ. Kapanıştaki `TAIL_S=600` ile simetri
> kaygısından uydurulmuştu. Doğru değer **240 sn** — üretimin kendi varsayılanı
> (`MITAS_OCR_HEAD`). Giriş jeneriği 4-5 dakikada biter.

### Karar 4 — Kopyalama değil ÇAĞIRMA (seçenek B)

`jenerik_detector.py` **921 satır** + iki iç bağımlılık (`jenerik_primitifleri`,
`credit_detector`) ve **9 üretim tüketicisi** var:

```
_jenerik_detect · giris_jenerik_havuzu · giris_master_cropstack · jenerik_eval
jenerik_boundary · jenerik_verify_bench · _jenerik_selftest · track_kunye
jenerik_primitifleri
```

Taşınamaz. Kopyalanabilir ama bu **dördüncü kopya borcu** + bağımlılık ağacı
demek. Karar: **Kobe'nin giriş bloğu motoru `_jenerik_detect.py` gibi ÇAĞIRIR**
(repo kökü `sys.path`'te). Kule sınırı bilerek ve **kayıtlı** olarak esnetilir;
okuma kulesi kurulurken `kutu.py`/`icerik.py` borcuyla birlikte kapatılır.

Gerekçe (Çağatay): *"iyi kötü şu an çalışan bir sistem var. Sistemlerin
kalitesi ayrı bir konu. Şu an sistemi ayağa kaldırıyoruz."*

### Karar 5 — Ölçüm ertelendi, ama unutulmadı

Giriş (a) için **GT yok, ölçüm yatağı yok.** Yani kuleye girdiğinde
"Kobe %94.5" cümlesi yalnız ÇIKIŞ için geçerli olacak — giriş hakkında hiçbir
şey söylemiyor. Bu **bilinçli** bir borç, gizli değil.

Ölçüm yatağı kurulacaksa tarif: 15 film (`filmtest/depo_3006/` altındaki TAM
filmler — `test_film_vl/` altındakiler VL deneylerinden kalma **parça**
dosyalar, film değil), ilk **240 sn**, fps 2 → 480 kare/film. GT'yi Çağatay
verir (motorun önerdiği sınırın etrafındaki kareler gösterilir, ~30 sn/film).

### Yapılacaklar (sırayla)

1. `src/cikis/` + `src/ortak/` yeniden düzenlemesi — **ölçüm kapısıyla**
   (taşıma sonrası %94.5 sapma sıfır olmalı)
2. `src/giris/sinir.py` — `jenerik_detector(prefer="first")` çağıran ince sarmalayıcı
3. `main.py` yönlendiricisi: `--bolum giris` → `ARIZA(BOLUM_HAZIR_DEGIL)` yerine giriş bloğu
4. `--uret kare|klip` giriş için: klip `start_sec−10` → `end_sec`, havuz Nash'e devredilir
5. Testler + gerçek koşu doğrulaması

## Diğer kuleler

**Jordan** (`Allstar/jordan/`) — BAŞKA bir oturum tarafından, Çağatay'ın
kontrolünde kuruluyor (MP4'ten doğrudan okuma, Qwen3.5-9B). **DOKUNMA.**
Not: kaynak dosyaları git'te izlenmiyor (`git ls-files Allstar/jordan` → 0).

## Sonraki kule (Çağatay söyleyecek)

Bilinen borç: `src/kutu.py` ve `src/icerik.py`, `harness/kunye_kiyas/`
altındaki asıllarının **kopyası**. Aslını üretim okuyucusu
`scripts/_pipe_hibrit_okuma.py:111` kullanıyor. Okuma kulesi kurulunca o kule
kendi kopyasını alacak ve `harness/kunye_kiyas/` tamamen silinecek.

Ayrıca ertelenen: CPU/GPU kaynak bölüşümü ölçümü (spec §4.7) — Kobe'yi CPU'da
geniş paralel, okuma kulesini GPU'da koşturma hedefi. 110 filmlik yatakta
ölçülmeden kabul edilmez.

## Geri dönüş

Ağaç kirli — `git reset --hard` YASAK. Geri dönmek için:

```
git checkout <SHA> -- harness/kunye_kiyas tests scripts/_jenerik_pool.py
rm -rf Allstar
```

SHA: `raporlar/geri_donus.txt` içinde.
