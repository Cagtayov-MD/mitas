# SLİTSCAN HİBRİT HIZ-KESTİRİMİ — KONTROLLÜ GEÇİŞ ŞARTNAMESİ
2026-07-09 · Kaynaklar: ölçüm (Yedi Numara 121-kare R-run) · 4-rol konsey (kod-doğrulamalı) · qwen3.7-max · Fable
GLM: 2 denemede uzun-soru cevabı alınamadı (kısa sorularda çalışıyor — council altyapı notu).
Durum: **ÇAĞATAY ONAYI BEKLİYOR — onaysız koda dokunulmaz.**

## 0. İKİ SORUNUN CEVABI

**"Çalışan sistemi bozar mı?"** — HAYIR, tasarım gereği: film hattı bayrak-`0`'da **bit-identik** kod yolunda kalır (yeni fonksiyonlar hiç çağrılmaz); gölge fazı 54-film korpusunda PNG+manifest **SHA256 birebirliğini** şart koşar (gölge kaydı ayrı sidecar dosyada); aktivasyonda bile sağlıklı run'lar MASKED-statüko yolundan aynen geçer. Tek risk (dedektör yanlış-pozitifi) kanaatle değil gölge fire-sayımıyla ölçülür.

**"Daha sağlıklı mı çalışır?"** — Dizi hattında ölçülebilir EVET beklentisi: FIRE hükmü Yedi Numara'da 105/120 kare-atlamayı ~6'ya, travel-oranını ~0.24'ten ~1.0'a çeker ("SEDEF PEHLİVANOĞLU" düz okunur = turnusol); DEMOTE hükmü kısmi-çökme baypasını kapatır. Ama "daha sağlıklı" damgası tek örnekle değil, 12+ segment OCR-isim-doğruluğu + sağlık-metrik kabulüyle basılır.

## 1. ÖLÇÜLMÜŞ ZEMİN (2026-07-09)

Yedi Numara çıkış jeneriği, run [74,194] "R", donmuş-kare arka plan + kayan yazı:
- TAM-KARE dy: medyan 31.63, p10-p90 [31.58, 31.67], sıfır spike — kusursuz.
- MASKELİ dy (mevcut slitscan yolu): medyan 0.07, **105/120 kare vmin-altı atlandı**, 18 spike (hepsi 31.6 platosuna oturuyor = "kesişme tanığı").
- Maske kapsaması %54.5-61.5 — text_mask renkli donmuş sahneyi metin sanmış; maskeli görüntü statik arka planla dolu → korelasyon 0'a çapalı.
- Master'da travel çöküklüğü birinci elden teyit: scroll_slit blok 928px ≈ beklenen 3796px'in ~0.24'ü.
- TERS YÖN (tarihsel): hareketli-footage + duran-yazı vakasında tam-kare 15.81 ölçüp scroll sanmış, maskeli 0.02 ile doğruyu vermiş. → İki yönde de tek-metrik batar; **içerik-koşullu hibrit şart.**
- qwen'in response-tuzağı teyidi: phaseCorrelate statik-statik eşleşmede "yüksek güven + 0 hız" döner → response v1 kararına giremez (yalnız gölge-log).

## 2. MEKANİZMA (kod-düzeyi; tek dosya: OCR-worktree/db_compose_master.py)

`split_runs`/`split_runs_reading`/`text_mask`/`Params` DOKUNULMAZ. Toplam ~100-120 yeni satır + ~10 satır gövde dokunuşu + ~15 satır sağlık-ölçer + ~120 satır test.

- **`_slit_channel_stats(frames,p,args)`** (~40 satır): TEK geçişte kare-başına `dy_M+resp_M` (mevcut :682-693 aynısı), `dy_F+resp_F` (tam-kare; maliyet kare-başına +1 phaseCorrelate — 121-kare run'da <0.5sn), `cov[i]` (bedava). Türetilenler (skip_frac_m, cov_med, med_f, iqr_f, n_coin, n_meas) HEPSİ bu tek geçişin serisinden — ölçüm-hijyeni kuralı (skip+spike=123>120 dersi: ikinci sayım kaynağı YASAK).
- **`_slit_channel_decision(stats,p)`** (~15 satır, SAF → importlib kalıbıyla birim-test): aşağıdaki tablo.
- **`_slit_hybrid_sidecar`** (~12 satır): ham seriler+karar AYRI `*.hybrid_shadow.jsonl`'a — ana manifest/PNG'ye gölgede tek bayt dokunmaz.
- **`slitscan()`**: imza `(frames,p,args,allow_demote=False)` → `(block, hybrid_info|None)`. FULL kararında `dy_override=dy_F` serisi kare-kare akar (rampa serbest) + tek-satır kelepçe `|dy_F−med_f|>3·IQR→med_f` (parlama/interlace sigortası). :695 yuvarlama, :697 vmin/vmax kapısı, seed/tail AYNEN korunur.
- **Çağrı noktaları:** `compose_reading_runaware`:1021 → `allow_demote=True` (DEMOTE→None→MEVCUT statik-sayfa fallthrough'u :1038 — kısmi-çökme baypası da böylece kapanır); `compose_slit`:754 → `allow_demote=False` (DEMOTE statüko-MASKED'e düşer + sidecar; film-ortak koda statik-makine eklenmez).
- **Bayrak:** env `MITAS_SLIT_DY_HYBRID` ∈ {0, golge, 1}, **varsayılan 0**; CLI aynası `--slit-dy-hybrid`. Film profili bayrağa hiç dokunmaz; `dizi_isle.py` aktivasyonda `1` geçer. Kod çatalı yok.

## 3. KARAR TABLOSU (run-başına TEK karar; kare-başına anahtarlama YASAK)

| Hüküm | Koşul | Yedi Numara sağlaması |
|---|---|---|
| **FULL** (maske-şişme) | cov_med≥COV_THR ∧ skip_frac_m≥SKIP_THR ∧ n_coin≥N_COIN_MIN | 0.576✓ 0.875✓ ~18✓ → FIRE |
| **DEMOTE** (duran-yazı) | skip_frac_m≥SKIP_THR ∧ n_coin≤N_COIN_NULL ∧ en-keskin karede has_text | duran-yazı: skip≈1.0, kesişme 0 |
| **MASKED** (statüko) | geri kalan her şey (ara bölge → sidecar `AMBIGUOUS`) | sağlıklı run'lar bit-identik geçer |

- **Kesişme tanığı** `n_coin = #{i: |dy_M[i]−dy_F[i]| ≤ TOL_COIN}` — kare-hizalı (rampa uyumlu). Şişik maske ara ara gerçek hıza kilitlenip itiraf eder (p90=31.63 kanıtı); gerçekten duran yazı asla itiraf etmez (0.02 vs 15.81). İki batma modunu TEK kural ayırır.
- Eşik başlangıçları [hepsi KANITSIZ-VARSAYILAN — gölge korpusundan **ayrılabilirlik kanıtıyla** (sağlam-p99 < eşik < patolojik-min) sabitlenir]: COV_THR=0.40 (qwen alternatifi 0.20 — kalibrasyon karar verir), SKIP_THR=0.5, TOL_COIN=max(2.0, 0.1·med_f), N_COIN_MIN=max(3, ⌈0.05·n_meas⌉), N_COIN_NULL=1. vmin/vmax DEĞİŞMEZ.
- response/koherans/cov serileri karara GİRMEZ — sidecar teşhis tanığı (v2 adayları). qwen ek teşhisleri sidecar'a: velocity-jitter σ, geometrik-yırtık indeksi Σ|v_t−v_{t−1}|.

## 4. GÖLGE-A/B PROTOKOLÜ + KABUL KAPILARI

- **Korpus A (regresyon, film; bayrak=golge):** 54-film koleksiyonu + reading-master'lı tüm hub'lar (envanter: 46 film hub'ı). Kabul: PNG+manifest SHA256 %100 birebir ∧ fire/demote/ambiguous dağılımı raporlu. **Film-fire = hata DEĞİL, İNCELE** (donmuş-arkaplanlı film jeneriğinde doğru-pozitif olabilir; her fire elle sınıflanır).
- **Korpus B (aktivasyon, dizi; bayrak=1):** mevcut dizi hub'ları (YEDİ NUMARA, DİRİLİŞ ERTUĞRUL×2, BENİ BÖYLE SEV, BİZİM EVİN HALLERİ, YALAZA) giriş+çıkış ≥12 segment + qwen önerisi uç-vaka seti (donmuş-arkaplan / hareketli-footage / ağır-VHS sınıflarından el-seçimli) eşik ayarı için.
- **Nöbetçiler:** N-1 Yedi Numara [74,194] FIRE etmek ZORUNDA (travel 0.24→[0.9,1.1]; SEDEF turnusolu). N-2 DEMOTE-yönü: İLK YARIŞ verisi envanterde YOK (doğrulandı) → nöbetçi gölge sidecar'larından imzayla (skip≈1 ∧ n_coin≈0) keşfedilir; bulunamazsa DEMOTE "gölge-kanıt bekliyor" statüsünde (davranışı mevcut tam-çökme fallthrough'uyla aynı — risk asimetrik değil). N-3 sınıflandırıcı-regresyon: SENİN HİKAYEN sahte-S runları S kalmalı. +≥1 passthrough segmenti.
- **Metrikler:** OCR/VL isim-doğruluğu vs ekran; master_saglik_olcum sınıfı; FIRE'lı run'da skip_rate ≤%10; travel_ratio=Σşerit/Σ|dy_seçili| ∈[0.9,1.1]; yeni hayalet/yırtık/garble=0 (görsel QC); fire/demote sayımları.
- **Kapılar:** G1 (golge→dizi-on): Korpus A SHA %100 ∧ eşikler ayrılabilirlik-kanıtlı ∧ her film-fire sınıflanmış. G2 (dizi kalıcı): 12/12 segment temiz ∧ N-1 FIRE+düzelmiş ∧ N-3 regresyonsuz. G3 (film-on): **AYRI karar, bu şartname kapsamı DIŞI** — film 0'da kalır.
- **Süre:** gölge re-compose ≈ 1 gece; kalibrasyon+QC ≈ 1 iş günü; toplam ≈ **2 iş günü** [tahmin].

## 5. ROLLBACK + İZLEME

- Rollback: `MITAS_SLIT_DY_HYBRID=0` — tek env, anında bit-identik; master'lar deterministik yeniden-render. Tetik (üretim): sağlık-sınıf düşüşü ∨ OCR-garble artışı ∨ travel<0.8 blok oranı sıçraması. **Abort (tasarım-iptal):** gölge dağılımları ayrışmıyorsa aktivasyona geçilmez → response-sinyalli v2'ye dönülür.
- İzleme: bayrak=1'de manifest scroll_slit bloğuna dy_source/cov_med/skip_frac/n_coin/travel_ratio (~6 satır); `master_saglik_olcum.py`'ye **TRAVEL-ÇÖKÜK** sınıfı (travel_ratio<0.5) — Yedi Numara vakasını tek sayıyla yakalayan üretim bekçisi.

## 6. BİLİNEN-ÇÖZÜLMEMİŞ (dürüstlük kaydı)

- **Üçüncü mod** (şişik maske + hareketli footage + duran yazı): dy_M≈dy_F → MASKED statüko → mevcut hastalık sürer (yeni regresyon değil); sidecar'a yer-değiştirme tanığı YALNIZ-LOG, v2 adayı.
- compose_slit :761 asimetrisi (R-run None → içerik yutulur): v1'de düzeltilmez, korpusta ölçülür.
- :695 yuvarlama şişmesi (~%1.2 sistematik) + kesirli akümülatör: AYRI iş.
- qwen'in NCC şerit-doğrulaması: CPU %40 maliyetle RED; yalnız bimodal-kararsız bloklarda v2 fallback adayı.

## 7. HAKEM ÖZETİ
Muhafazakâr iskeletiyle kazandı (run-başına tek karar, 3-durumlu bayrak, SHA kapısı, resp v1-dışı, çok-örnekli korpus); Yaratıcı kilit sinyali verdi (kesişme tanığı + çöpe-atılan-tanıklar tespiti); Eleştirmen iki kör nokta buldu (kısmi-çökme fallback-baypası; İLK YARIŞ verisinin yokluğu); qwen response-tuzağını ve blok-medyan/geometri metriklerini ekledi; Yaratıcı'nın sabit-v̂ dayatması, OCR-proxy hakemi ve "%2-3 sapan kabul" önerisi REDDEDİLDİ (Çağatay şartı: mevcut çıktılar bozulmamalı).
