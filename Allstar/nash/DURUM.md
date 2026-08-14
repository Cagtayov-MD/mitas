# Nash kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Her iş biriminden sonra güncellenir ve commit'lenir.
> Spec: `docs/superpowers/specs/2026-08-14-allstar-nash-kulesi-design.md`

**Son güncelleme:** 2026-08-14 — **FAZ 1 TAMAM.** Havuz yarısı çalışıyor,
KAPI 1 geçildi (29/29 birebir, sapma sıfır), testler 99/99.
**SIRADAKİ: Faz 0′ sadakat sondajı — Çağatay onayı bekliyor** (aşağıda).

---

## Değişmez kurallar (her oturumda geçerli)

- **`src/havuz.py` DEĞİŞTİRİLMEZ.** `harness/track_kunye/steve_nash.py`'nin
  birebir kopyası (yalnız docstring başlığı farklı). Sadeleştirme,
  "iyileştirme", yeniden yazım YASAK — KAPI 1 bunu ölçer.
- **Üretime dokunulmaz.** Faz 1-2 boyunca `_pipe_hibrit_okuma.py`,
  `_pipe_track_kunye.py`, `olcum_yatagi_faz2.py`, `pilot_hat.py`,
  `steve_nash.py`, `messi.py` **salt-okunur**. Sökme yalnız Faz 3'te.
- **`git add -A`, `git add .`, `git reset --hard`, `git stash` YASAK.** Ağaçta
  bu işe ait olmayan çok sayıda değişik + silinmiş dosya var. Yalnız adı geçen
  yolları sahnele.
- **Üretim durmuş** (2026-07-31, Çağatay talimatı). Hiçbir toplu koşu başlatma.
- **venv python 3.12.13 olmalı** — sistem python'u 3.14, referans ortam 3.12.13.
- **Ollama açıkken Kobe ölçümü koşturulmaz** (%94.5 → %93.6).

---

## Tamamlanan — Faz 1

| # | İş | Kanıt |
|---|---|---|
| 1 | Kule iskeleti + `sozlesme.py` (3 durum, 5 arıza sınıfı) | 19 test |
| 2 | `src/havuz.py` — `steve_nash.py` birebir taşındı | `diff` = yalnız docstring |
| 3 | `src/secim.py` — dizin→seçim + iki üretim sigortası tek yerde | 18 test |
| 4 | `src/okuyucu.py` — dedup + gevezelik süzgeci + sağlık (modelsiz) | 22 test |
| 5 | `main.py` + `nash` + `config.yaml` — CLI, toplu kuyruk | 15 test |
| 6 | Havuz testleri taşındı (`test_messi.py` → `tests/test_havuz.py`) | 25 test |
| 7 | **KAPI 1** — kule vs bugünkü üretim kodu | **29/29 birebir, SAPAN 0** |
| 8 | Uçtan uca gerçek koşu (BOZGUNCULAR) | `ARIZA(MODEL)` + havuz kanıtı doğru |

Toplam **99 test**, GPU gerektirmez, 1.5 sn.

```bash
./nash tek --kareler <ham-kare-dizini> --film-id <id>
# → out/<id>/cikis/nash.json + _TAMAM
```

## Uygulama sırasında alınan iki karar (spec'e ek)

**1. Sağlık bayraktır, hüküm değil.** İlk yazımda `deepseek_saglik`'in her
olumsuz sonucu `ARIZA(CIKTI_BOZUK)` üretiyordu. Testler yakaladı: **150
karakterlik gerçek bir kısa jenerik ARIZA olup içeriği çöpe gidiyordu** —
sözleşmenin yasakladığı şeyin aynası. Şimdi yalnız `garble_yuksek` arıza üretir
(metin YANLIŞ, aşağı akışı zehirler); `cok_kisa` yalnız kanıta yazılır.
Üretimde de bayrak zaten hüküm değil (`_pipe_track_kunye` manifest'e yazıp
içeriği korur).

**2. `nash.txt` yalnız `OKUNDU`'da yazılır.** Gerçek koşuda görüldü: ARIZA'da
da boş `nash.txt` yazılıyordu; `_TAMAM` var + dosya boş = yalnız metni okuyan
tüketiciye "yazı bulunamadı" gibi görünür ve ARIZA/METIN_YOK ayrımını yutar.
Dosya yoksa tüketici `nash.json`'a bakmak zorunda kalır.

## BULGU — ölçülmemiş algoritma değişikliği (Nash'in dışında, ama Nash'in kalbi)

`e1a201d5` (2026-08-05, *"intro-pipeline: … frame pool enhancements"*)
`film_esigi`'nin Otsu aramasını yeniden yazdı. Docstring'i **"Optimize edilmiş
O(n) Otsu"** diyor — ama bu bir hız optimizasyonu değil, **cevabı değiştiren**
bir davranış değişikliği:

| | Eski | Yeni (bugün üretimde) |
|---|---|---|
| Arama uzayı | `t ∈ [min+1, max)` | `t ∈ [0, 256)` |
| ≥3 eleman şartı | aramayı **kısıtlar** (`continue`) | aramadan **sonra** cevabı reddeder |

15 filmlik yatakta **1 film** etkilendi: MOBY DICK 1, eşik 28→13,
sayfa **15→165 (11×)**. Tavan 100 olduğu için o film artık 15 yerine 100 sayfa
okuyacak — model çağrısı ~6.7×.

**Hangisinin doğru olduğu bilinmiyor; ölçüm yok.** Bu Nash kulesinin işi değil
(kule bugünkü davranışı sadık taşıdı), ama açık borç olarak burada duruyor.
Ölçmek için malzeme hazır: `olcum/referans_uret.py` iki sürümle koşturulabilir.

## SIRADAKİ İŞ — Faz 0′ sadakat sondajı (ÇAĞATAY ONAYI GEREKİYOR)

Faz 2'ye (modeli kule içine almak) geçmeden önce ucuz bir ölçüm:
**aynı N kare, iki motor** — Ollama/llama.cpp vs transformers — çıktılar
diff'lenir.

**Neden:** DeepSeek-OCR patch-tabanlı. llama.cpp'nin `deepseekocr` handler'ı ile
transformers `AutoProcessor` farklı normalize eder → patch sınırları farklı
düşer → satır düzeyinde kayma (`YÖNETMEN` → `YÖNETME N`). `dedup_esigi=0.92`
bunu **yeni satır** sayar ve künyeye sızar. (MiniMax, 2026-08-13 konsey turu.)

**Maliyeti (Prensip 2 uzantısı — bu yüzden onay isteniyor):**
- HF ağırlık indirme `deepseek-ai/DeepSeek-OCR` — **~6.7 GB**
- `ollama.service` geçici başlatma (Kobe ölçümü aynı anda koşmamalı)
- torch + transformers kurulumu kulenin venv'ine (~2-3 GB)

**Kapı:** sapma bandı ölçülür ve kayda geçer. Beklenmedik ölçüde büyükse
**Karar 2 (model kule içine) Çağatay'a yeniden açılır** — sessizce devam edilmez.

Not: Ollama'daki model `file_type: F16`, 3.3B, 6.687 GB; HF'deki 3336.1M param.
Birebir aynı ağırlık, kuantizasyon yok. Fark çıkarsa çıkarım yığınından gelir.

## Sonraki fazlar

**Faz 2 — okuyucu kule içine.** `src/model.py` (transformers'a dokunan TEK yer)
+ `model_kur.sh` + pinli torch/transformers. KAPI 2: 15 filmde satır kıyası,
Faz 0′'ın bandı içinde; `kanit.havuz` hâlâ birebir aynı.

**Faz 3 — üretim geçişi + sökme.** `_pipe_hibrit_okuma.py` ve
`_pipe_track_kunye.py` kuleyi kullanır; sonra `steve_nash.py`, `messi.py`,
`test_messi.py`, `test_steve_nash.py` ve `pilot_hat`'ın havuz/okuma katmanları
**silinir.** Ayrı tasarım gerekir — entegrasyonun şekli (senkron/asenkron) Faz
1-2'nin gerçek süre/bellek verisiyle kararlaştırılacak. Konseyin uyarıları
spec §6'da.

## Nash'in dışarıda kalan erleri (Faz 3'te sökülecek)

| Yer | Ne | Sınıf |
|---|---|---|
| `scripts/_pipe_hibrit_okuma.py:258,276` | **ANA üretim okuma yolu** | 🔴 canlı |
| `scripts/_pipe_track_kunye.py:176,182` | gölge 3-kol | gölge |
| `scripts/olcum_yatagi_faz2.py:138` | ölçüm yatağı Kol A | ölçüm |
| `harness/track_kunye/{steve_nash,messi,pilot_hat,taze_pilot}.py` | asıl + sarmalayıcı | harness |
| `harness/track_kunye/test_{messi,steve_nash,pilot_hat_uretim}.py` | testler | harness |
| `tests/test_{pipe_track_kunye,track_kunye_giris}.py` | pipeline testleri | repo |
