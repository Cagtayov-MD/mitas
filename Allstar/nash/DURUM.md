# Nash kulesi — canlı durum

> **Bu dosya bağlam sigortasıdır.** Oturum kesilirse yeni oturum BURADAN devam
> eder. Her iş biriminden sonra güncellenir ve commit'lenir.
> Spec: `docs/superpowers/specs/2026-08-14-allstar-nash-kulesi-design.md`

**Son güncelleme:** 2026-08-14 — **FAZ 0′ + FAZ 2 TAMAM. KULE UÇTAN UCA ÇALIŞIYOR.**
Ham kare dizini girer, **yazı çıkar**. KAPI 1 29/29 sapma sıfır · KAPI 0′
veto sonrası %92.8 birebir / %97.6 bulanık · testler 104/104.
**SIRADAKİ: Faz 3 — üretim geçişi + sökme (ayrı tasarım gerekir).**

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

## BULGU → ONARILDI (2026-08-15) — `film_esigi` Otsu araması

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

### ÖLÇÜLDÜ (2026-08-14) — `olcum/otsu_ayrisma.py`, `olcum/onarim_adayi.py`

**Kusur, ikilem değil.** Ayrışan tek yüzeyde (MOBY DICK/çıkış, 241 fark)
mekanizma şu:

| | aday argmax | bölme | ayrım | sonuç |
|---|---|---|---|---|
| Eski | **28** | 238 / 3 | 6.05 | `28` (Otsu) |
| Yeni | **29** | 239 / **2** | 8.39 | ≥3 kapısı → **`p25+2 = 13`** |

İki sürüm **verideki aynı yapıyı buluyor** — 28 ile 29 bir kutu yan yana.
Yeni sürüm cevabı buluyor, sonra kendi son-denetimiyle **çöpe atıp** yerine
bimodalliğe hiç bakmayan bir geri-düşüş koyuyor. 13, medyanın (16) *altında*:
ardışık farkların ~%25'i "yeni grup" sayılıyor → gruplama çöküyor
(242 kare → 165 grup). `birikim_esigi` de 84→39 düşüp etkiyi katlıyor.

**Hız ikilemi yok.** `≥3` kuralı O(n) histogram döngüsünün *içine* arama
kısıtı olarak konursa (`onarim_adayi.film_esigi_onarilmis`):

* **29/29 yüzeyde eski cevabın birebir aynısı** (MOBY DICK dahil: 28)
* eskiden **5.5× hızlı**, bugünkü üretim sürümünden de hızlı
  (49.2 ms → 8.9 ms; üretim 12.0 ms)

Yani commit'in vaat ettiği hız, cevabı bozmadan zaten alınabiliyordu.

**Yaygınlık.** Kusur, kısıtsız argmax'ın küçük yanı <3 olunca tetikleniyor.
Yatakta dağılım: `<3 → 1` · `3–6 → 3` · `>6 → 25`. Yani 29 yüzeyin 4'ü
sınıra yakın — 1825 filmlik koşuda bu tekrar eden bir mod, tek seferlik
tuhaflık değil. Üstelik **sessiz**: hata vermiyor, yalnız 4× fazla sayfa okuyor.

**Yön: her zaman "fazla okuma" değil — çürütme turunun bulgusu.** İlk okumada
kusur bir *maliyet* kusuru gibi görünüyor (eşik düşer, sayfa artar). Ama
geri-düşüş `p25+2` doğru eşiğin **üstüne** de çıkabiliyor: yatakta 3/29 yüzeyde
öyle (KERMİT/çıkış `21 → 31`, DONÖR/çıkış `14 → 17`, KERMİT/giriş `40 → 41`).
O yüzeylerde kusur tetiklense **daha AZ sayfa** okunurdu — yani sessiz **içerik
kaybı**. Kusurun işareti veriye bağlı: 25/29 fazla-okuma, 3/29 az-okuma.
Bu, kusuru "pahalı ama güvenli"den çıkarıp "yönü öngörülemez"e taşıyor.

**Kapsama (ölçüldü, ama sonucu belirleyici DEĞİL).** Yeni seçim eskinin
üst-kümesi değil: tarihî koşuda okunan 26 karenin 13'ü, 100 tavanı stride ile
kırpıldıktan sonra yeni seçimde yok (233 satır taşıyorlardı). Ama bunların
yalnız **1'i** gerçekten farklı bir kart (imza mesafesi 86); kalan 12'sinin
mesafesi 6–23 — kayan jenerikte "kısmi örtüşme", temiz kayıp değil.

### ONARILDI (2026-08-15) — Çağatay kararı: "önce veri kalitesi, hız sonra"

`≥3` kuralı O(n) döngüsünün içine arama kısıtı olarak geri kondu.
Dokunulan: `harness/track_kunye/steve_nash.py` + birebir kopyası
`Allstar/nash/src/havuz.py` (ikisi hâlâ yalnız docstring başlığında ayrılıyor).

Doğrulama zinciri:

| denetim | sonuç |
|---|---|
| `harness/track_kunye` havuz testleri | 50 geçti, 2 atlandı |
| Nash kule testleri | 105 geçti, 1 atlandı |
| 29 yüzeyde onarım == naif arama | **29/29 birebir** |
| **KAPI 1** (taze referansa karşı) | **29 kıyas, 0 sapma — GEÇTİ** |
| Onarım sonrası üretim vs **2026-07-31 doğrulanmış** çıktı | **14/14 aynı, 0 sapma** |
| Eşik hesabı hızı | naif 35.8 ms → **6.4 ms (5.6×)** |

Son satır kapanışın kanıtı: üretim, beş ay önce ölçülmüş ve QC'den geçmiş
davranışa **bit düzeyinde** döndü — üstelik naif aramadan hızlı. MOBY DICK/çıkış
yeniden `esik=28, grup=15, sayfa=15 (+11) = 26 sayfa`.

`olcum/*_onarim_oncesi.json` kusurun kanıtı olarak saklandı (onarımdan sonra
yeniden üretilemez).

**Hâlâ ÖLÇÜLMEDİ (açık borç):** 26 seyrek sayfa mı, 100 sıkı sayfa mı jeneriği
daha iyi okuyor? Onarım bunu *cevaplamıyor* — doğrulanmış hale döndürüyor.
Eğer daha sıkı okuma kaliteyi artırıyorsa bu **kasıtlı ve tek biçimli** bir
politika olarak ölçülüp konmalı (eşik/tavan ayarı), 15 filmde 1'inde rastgele
tetiklenen bir kusur olarak değil. Cevaplamak ollama + ~100 deepseek sayfası
ister (~15–30 dk).

## TAMAMLANAN — Faz 0′ sadakat sondajı + Faz 2 okuyucu

**Sonuç: TAŞIMA GÜVENLİ.** 4 farklı dönemden film (1955/1985/2002/2018) ×
4 kare = 16 kare, iki motorda okundu ve kıyaslandı.

| | birebir | bulanık (≥0.92) |
|---|---|---|
| Ham model çıktısı | %89.2 | %93.5 |
| **Veto sonrası (kulenin gerçek çıktısı)** | **%92.8** | **%97.6** |

Kalan 6+4 satırlık fark **içerik kaybı değil**, aynı künyenin harf düzeyinde
varyantları: `Abduumannob`/`Abdumannob`, `Ra'no Qasimova`/`Qosimova`,
`Judge Sullivan`/`Stillman`, `Vivamus at nunc`/`Vivus and music by`.
Kaybolan veya uydurulan isim YOK.

Sapma **metin içermeyen** karelerde toplanıyor; orada iki motor da uyduruyor
ve birbirine çok yakın uyduruyor (`cikis_0576`: "woman's arm" / "woman's hand").
O satırlar zaten veto katmanında eleniyor.

### Yığın gerçekleri (ölçüldü, tahmin değil)

- **transformers 5.x KULLANILAMAZ.** DeepSeek-OCR'ın uzak kodu
  `LlamaFlashAttention2` import ediyor; 5.x onu kaldırmış. Model kartının
  dediği sürüm: **4.46.3**. Jordan'ın pini (5.14.1) Nash'e UYMAZ — her kulenin
  kendi venv'i tam da bunun için var.
- **`sdpa` kullanılamaz:** `DeepseekOCRForCausalLM` reddediyor → **eager**.
  Sondaj için doğru seçim: füzyonlu çekirdek sayısal fark katmaz.
- **`infer(..., eval_mode=True)` ZORUNLU** — aksi halde metni stdout'a akıtıp
  `None` döner.
- Uzak kodun ek bağımlılıkları: `addict`, `matplotlib`, `requests`, `easydict`.
- numpy 2.3.5'te **tutuldu**; KAPI 1 kurulum sonrası yeniden koşuldu, geçti.
- Hız: kule-içi eager ~2-4 sn/kare · Ollama ~0.5-1.2 sn/kare (Ollama daha hızlı).

### Ölçümün yakaladığı KENDİ kusurum — madde imi kuralı

Üretimden birebir taşıdığım `madde_imi` vetosu (*"jenerikte madde imi olmaz"*,
ALİE vakasından genellenmiş) **14 GERÇEK İSMİ eliyordu**: KERMİT BATAKLIKTA /
`cikis_0384`, Muppet Workshop künyesi ekranda **gerçekten** madde imli bir isim
listesi (Heather Asch, Rollie Krewson, Polly Smith…). İki motor da doğru
okumuştu; kural ikisinde de kesiyordu.

Düzeltme: **im elenmez, SOYULUR** (`_kirp`); kalan içerik öteki kurallardan
geçer. Veto sonrası birebir %87.2 → **%92.8**.

> **AÇIK BORÇ:** ALİE sınıfı (`- ` + düzyazı ama fiilsiz, örn.
> *"- A river flowing..."*) artık yakalanmıyor. Daha iyi bir ayraç gerekiyor
> ve **ölçülmeden eklenmeyecek.** Kulenin "yok etme, düşür" tasarımı sayesinde
> elenen satırlar `kanit.elenen`'de durur — yanlış eleme görünür kalır.

## SIRADAKİ — Faz 3: üretim geçişi + sökme

**Ayrı tasarım gerekir.** Entegrasyonun şekli (senkron mu asenkron mu) bu
oturumda çözülmedi ve çözülmemeliydi; artık elde gerçek veri var:

- Kule-içi okuma **~2-4 sn/kare** (eager), Ollama ~0.5-1.2 sn/kare.
- Toplu modda model BİR KEZ yükleniyor — "film başına yükleme" korkusu
  gerçek değil (`start` deseni zaten çözüyor).
- VRAM: Kobe(~4 GB) + Nash(6.7 GB) sığar; **Jordan(~18 GB) eklenince
  28.7 GB > 24 GB — üçü aynı anda koşamaz.**

Konseyin bu faza dair uyarıları spec §6'da (asenkronda sessiz bozulma
sınıfları, kuyruk sigortasının kırılması, `frames/` yarış durumu).

Sökülecekler aşağıda.

## Nash'in dışarıda kalan erleri (Faz 3'te sökülecek)

| Yer | Ne | Sınıf |
|---|---|---|
| `scripts/_pipe_hibrit_okuma.py:258,276` | **ANA üretim okuma yolu** | 🔴 canlı |
| `scripts/_pipe_track_kunye.py:176,182` | gölge 3-kol | gölge |
| `scripts/olcum_yatagi_faz2.py:138` | ölçüm yatağı Kol A | ölçüm |
| `harness/track_kunye/{steve_nash,messi,pilot_hat,taze_pilot}.py` | asıl + sarmalayıcı | harness |
| `harness/track_kunye/test_{messi,steve_nash,pilot_hat_uretim}.py` | testler | harness |
| `tests/test_{pipe_track_kunye,track_kunye_giris}.py` | pipeline testleri | repo |
