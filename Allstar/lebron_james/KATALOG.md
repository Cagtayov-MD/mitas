# KATALOG — master PNG'ye ait her şey nerede

> **Amaç:** *"aradığımda bulabileyim"* (Çağatay, 2026-08-15). Master PNG'yle
> ilgili kod, test, deneme, rapor ve ölçüm bu kule altında toplandı. Bu dosya
> haritadır — ne nerede, ne çalışıyor, ne çalışmıyor.

## Bir bakışta

| Dizin | İçinde ne var | Koşuyor mu? |
|---|---|---|
| `src/` | Kulenin ÇALIŞAN kodu | ✅ evet |
| `aday/` | Henüz devrede olmayan motor(lar) | ❌ hayır — kasıtlı |
| `olcum/` | Ölçüm yatağı: kapı, sağlık, sadakat, atlas | ⚙️ elle çağrılır |
| `olcum/testler/` | Ölçüm kümesinin kendi testleri | ⚙️ elle |
| `arac/` | Master'ı dilimleyen / okuyan yan scriptler | ⚙️ referans |
| `arsiv/` | Eski denemeler, terk edilmiş sürümler | ❌ referans |
| `raporlar/` | Rapor ve kök-sebep belgeleri | 📄 okunur |
| `tests/` | Kulenin kendi testleri | ✅ `pytest tests` |

---

## `src/` — çalışan kod

| Dosya | Ne yapar |
|---|---|
| `derleyici.py` | **BİRİNCİL kompozitör.** Kareleri master PNG'ye bağlar (AI flashlight + phase correlate). `harness/master_dup/lebron_james.py`'den birebir taşındı |
| `yukleyici.py` | Kare listeleme / doğal sıralama / unicode-güvenli okuma-yazma |
| `kural.py` | Kulenin kendi çıktısı hakkındaki hükümleri: boy tavanı, çöküş dedektörü |
| `okuyucu.py` | Master → satırlar. Bantlama + süzgeçler + piksel kalkanı. **Modeli bilmez** |
| `model.py` | DeepSeek-OCR. transformers'a dokunan TEK yer |

## `aday/` — bekleme odası

| Dosya | Ne | Durum |
|---|---|---|
| `ibrahimovic.py` | Eski birincil kompozitör (740 satır). Lebron 2026-08-04'te yerine geçti | **Kör taşındı — tek satır dokunulmadı.** Hiçbir yerden çağrılmıyor |
| `magic.py` | **Birleşik aday:** lebron iskeleti + ibrahimovic'in dört mekanizması (plato v4 + dissolve bekçisi, token-kimlik, Sobel yedek yolu, token ızgara sondajı) | **Ölçüldü (2026-08-17), kararı bekliyor** — `raporlar/kompozitor_secim_karari_2026-08-17.md` |

**Neden `src/` değil:** `src/` yalnız koşan kodu tutar. İbrahimovic bağlanmadan
önce iki borcu var (ikisi de `tests/test_izolasyon.py`'de yazılı):
gömülü mutlak yol (`/home/cagatay/Ex_Frame`) ve `olcum/saglik`'e bağımlılık.
Ölçüm kazanınca `src/`'nin tam vatandaşı olur.

> Çağatay: *"ilerde onu lebron ile destekleyeceğim, ikisini birleştireceğim."*
> Magic o birleşmenin adıdır: derleyici.py'ye DOKUNMADAN, aday olarak kuruldu.
> Token'ları kulenin İÇindeki Paddle'dan alır — ibrahimovic'in `saglik` yan
> kapısı (bilinen borç) magic'e GEÇMEDİ. İki test korur: dosyalar
> **silinmesin**, ve **sessizce devreye girmesin**.

## `olcum/` — ölçüm yatağı

| Dosya | Ne ölçer |
|---|---|
| **`kapi_sadakat.py`** | **Kule çıktısı ↔ üretim çıktısı, SHA-256.** Taşımanın doğruluğu bununla kanıtlandı |
| **`kompozitor_kiyas.py`** | **Kompozitör kıyası:** lebron ↔ ibrahimovic ↔ magic (+ablasyon) aynı karelerde; saglik+sadakat+dup+çöküş tablosu → `raporlar/kompozitor_kiyas_*.json/.md` |
| `saglik.py` | Üretim OK · dup_oran ≤ 0.10 · boy 300–45000 · doku kapsamı ≥ 0.05 |
| `sadakat.py` | **Metin-recall:** ham karelerdeki metnin master'da ne kadarı hayatta kaldı |
| `dup_metrik.py` | Master'ın kendi içindeki tekrar oranı |
| `uret.py` / `uret_ex.py` | Üretim kompozisyonunu havuzda yeniden koşturur |
| `atlas.py` / `atlas_tanik.py` / `kalan91_atlas.py` | Kusur atlası — hangi film hangi sınıfta |
| `mod_denetim.py` | Mod hatası: kayan jenerik statik sayfa olarak mı derlendi |
| `skip_audit.py` · `dikis_tekrar_tara.py` · `hizli_silah_iz.py` · `fix_dogrula.py` · `k3_recall_testi.py` · `kapanis_kaniti.py` | Nokta denetimleri |
| `kalibrasyon_k1.py` · `kalibrasyon_f3c_ncc.py` | Eşik kalibrasyonu |
| `lebron_james.py` | Kaynak motorun kopyası — kapının kıyas tarafı |

**`sadakat.py` neden kritik:** `dup_metrik` master'ı yalnız *kendi içinde*
ölçüyor. "Kayan jenerik statik sayfa olarak derlendi" tipi mod hatalarında
`dup_oran ≈ 0` çıkıp defekt tamamen gözden kaçıyordu (`acemiler-cetesi` /
`benimle-dans-et` vakaları).

**Ölçüm yatağı üretimi çağırabilir** — kıyaslanacak şey zaten dışarıda. Kule
kuralı çalışma zamanı içindir; muafiyet tek yönlü ve testle kilitli.

## `arac/` — yan araçlar

| Dosya | Ne |
|---|---|
| `master_png_dilimle.py` | Master'ı `master_dilim/*.png` parçalarına böler |
| `master_dilim_oku.py` | O parçaları **OneOCR** ile okur → VL hayalet-kalkanı korpusu |
| `master_saglik_olcum.py` | Toplu sağlık ölçümü |
| `_jenerik_dense.py` | Adaptif-yoğun kardeş havuz üretici (1.5 fps'te scroll'un "kesme" sanılması sorununa karşı) |

## `raporlar/`

| Dosya | Ne |
|---|---|
| `kapi_sadakat*.json` | Kapı koşularının sonuçları (kule vs üretim, SHA-256) |
| `kompozitor_kiyas_*.json/.md` | Kompozitör kıyas koşuları (lebron ↔ ibrahimovic ↔ magic) |
| `kompozitor_secim_karari_2026-08-17.md` | **Faz 4 ölçülmüş kararı** — no_engine_selection_before_benchmark kuralının işletilmesi |
| `master_dup/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` | Dup sorununun kök-sebep planı — M1…M10 görevleri |
| `master_dup/dup_dokumu.md` · `dup_dokumu_v2.md` | Dup dökümü |
| `master_dup/ex_dup_siniflandirma.md` | Sınıflandırma + Sınıf B yanlış-pozitif analizi |
| `master_dup/sadakat_raporu.md` | Metin-recall raporu |
| `master_dup/kalan91_atlasi.md` | Kalan 91 filmin atlası |
| `master_dup/MASTER_DB_COMPOSE_FINAL_2026-06-20.md` | db_compose_master final notu |
| `master_dup/frame_vs_master_raporu.md` | Frame kolu ↔ master kolu kıyası |
| `master_dup/masterpnghkhersey.md` | Master PNG toplu notlar |

## `arsiv/_deneme_arsivi/`

Terk edilmiş sürümler: `lebron_james_v2.py`, `lebron_james_step1.py`,
`lebron_james.py.backup_step1`, `benchmark_iyilestirmeler.py`.
**Koşturulmaz** — biri sözdizimi olarak bozuk (orijinalinde de bozuktu).

---

## Kulede OLMAYANLAR (bilerek)

| Ne | Nerede kaldı | Neden |
|---|---|---|
| `master_png_monitor.py` | `OCR-worktree/` | Orkestratör: havuz seçer, Database'e yazar, symlink kurar. MITAS'ın işi |
| `db_compose_master.py` | `OCR-worktree/` | 3796 satır; giriş run-aware motoru burada. Taşınması ayrı faz |
| `_pipe_hibrit_okuma.py` | `scripts/` | Üretimin okuma kolu; kule kendi okuyucusunu taşıyor |
| Orijinal `harness/master_dup/*` | yerinde | **Silinmedi**: üretim hâlâ oradan çağırıyor ve sadakat kapısı orayı kıyas için okuyor. Faz 5'te (üretim devri) silinecek — Nash'in izlediği sıra |

---

## Sık aranan sorular

**"Master nasıl üretiliyor?"** → `src/derleyici.py`, `README.md` §Sadakat kapısı

**"Master nasıl okunuyor?"** → `src/okuyucu.py` + `src/model.py`, `README.md` §Okuyucu

**"Bu master iyi mi?"** → `olcum/saglik.py` (kendi içinde) + `olcum/sadakat.py`
(kaynağa sadık mı)

**"Taşırken bozuldu mu?"** → `olcum/kapi_sadakat.py`, sonuçlar
`raporlar/kapi_sadakat*.json`

**"İbrahimovic nerede?"** → `aday/ibrahimovic.py`, kör kopya, bağlı değil

**"Neler denendi, ne başarısız oldu?"** → `raporlar/master_dup/` +
`arsiv/_deneme_arsivi/`

**"Bugün ne durumdayız?"** → `DURUM.md`
