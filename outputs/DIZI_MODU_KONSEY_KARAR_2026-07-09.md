# DİZİ MODU — NİHAİ DEĞERLENDİRME VE KARAR DOKÜMANI
2026-07-09 · Kaynaklar: 5-hakem paneli (max-effort, satır-referanslı) · 4-rol konsey (Yaratıcı/Muhafazakâr/Eleştirmen/Sentezci) · GLM (tur-1) · qwen3.7-max (tur-1 + tur-2) · Fable sentezi
Değerlendirilen: Faz-1 (commit 3de8d716) — `scripts/dizi_SISTEM.md` + 6 modül + 109 test

## 0. ÜST-KARAR (tek paragraf)

**Yakınsak hibrit:** Streaming omurga pilot için KALIR ama "veri-toplama + teslim-dışı" statüsünde koşar (konsey); nihai **karar otoritesi** pilot verisiyle kalibre edilecek **retrospektif yeniden-mühürleme motoruna** (= İki-Düzlem Faz-B: tüm-seri varlık matrisi + segment tespiti + üç-tanık kanonik) geçer (Fable/GLM/qwen/Yaratıcı) ve teslim **epoch-versiyonlu** saf-render olur (qwen). Streaming'in cırcır makinesi (ardışıklık sayaçları, bekleyen-değişim zinciri) derinlemesine TAMIR EDİLMEZ — pilotu güvenle bitirecek asgari yamalar yapılır, sonra otorite Faz-B'ye devredilir. Böylece: pilot körü körüne yazılmış batch parametrelerini değil gerçek davranışı ölçer; panelin A-2/A-4/A-5/A-6 sınıfı yapısal buglarının çoğu otorite devriyle kendiliğinden anlamsızlaşır; kod tabanının ~%70'i (okuma adaptörü, depo/ledger, kümeleme çekirdeği, PDF birleştirici) her iki fazda da aynen yaşar.

## 1. KİM NE DEDİ — YAKINSAMA HARİTASI

| Konu | Panel | Konsey | GLM | qwen | Fable nihai |
|---|---|---|---|---|---|
| Mimari rota | streaming + 17 fix; rota kararı pilot-sonrası | HİBRİT: streaming kalır, yeniden-mühürleme Faz-2'ye ŞİMDİ yazılır | batch-first | batch-first (omurga onaylı, 3 yama şartlı) | **Konsey sıralaması + batch varışı** |
| Deterministik körlük | tohum 3-okuma ≠ 3 tanık (H2#9) | P0-1: tohum-VL+KB kapısı; "VL üretiliyor, çöpe gidiyor" | statik tohum + körlük | tohum zehirlenmesi | **P0-1 şimdi; kalıcı ilaç Faz-B üç-tanık** |
| Eşikler | çoğu ÖLÇ-SONRA | hepsi KAL/ÖLÇ (tabloda) | 5/3/5/oransal/%70 | 8-10/4/5/15-20/%40 + formül | **Pilot ölçer; dış öneriler çelişik (kanıtsız); qwen formülü Faz-B adayı** |
| AYRILDI mantığı | eksik_esik ÖLÇ | flap-metriği | 3→5 | terminal-yokluk da yanlış (açık-dünya!) → Last_Seen | **qwen haklı: Faz-B'de "dönem kadrosu" modeli; AYRILDI damgası kalkar** |
| Revize-PDF | export tazele (A-1) | teslim-dışı mod (P0-4) | — | ASLA üzerine yazma → EPOCH versiyonlama | **qwen haklı: teslim = epoch'lu; A-1 tam çözümü Faz-B teslim otoritesiyle** |
| Kümeleme | eş-görünüm vetosu eksik (A-7) | 600-tanıkta zincir-birleşme riski (AYLA~AYLIN) | — | unvan-strip (Dr./Bey/Paşa) + karakter-kolon ayrımı | **A-7 + unvan-strip şimdi; zincir-birleşme Faz-B'nin ana test konusu** |
| VL/KB ekonomisi | VL-backfill B-3 | veto değil tanıklık | — | KB (bedava) herkese; VL (pahalı) yalnız KONTROL-kanon + başlıklı-konuk | **qwen'in maliyet ayrımı aynen alınır** |

Çelişki notları: GLM kopuş %70 dedi, qwen %40'ı onayladı, konsey %40 KAL dedi → %40 kalır (2/3 + felaket-dedektörü gerekçesi). GLM/qwen'in eşik sayıları birbiriyle uyuşmuyor → hiçbir dış sayı kanıt değil, pilot ölçer.

## 2. PİLOT-ÖNCESİ İŞ LİSTESİ (10 madde; konsey-P0 ∪ panel-asgari ∪ qwen-küçük)

1. **Tohum-VL mutabakat kapısı** — `kur_master` çıktısındaki her kanonik, tohum VL birleşimiyle name_match'lenir; teyitsizler `tohum_vl_teyitsiz` + KONTROL notu (veto değil). **KB bileşeni ÇIKARILDI (Çağatay düzeltmesi 2026-07-09):** TRT dizi künyesinin ~%90'ı (teknik ekip, ulaştırma, set...) Wikidata/IMDb'de YOKTUR ve olmayacaktır — "KB'de yok" sinyal değildir, KB fuzzy-düzeltmesi gariban isimleri ünlülere çevirme riskidir (film-modu KB-fabrikasyon dersi). `kb=None` bilinçli karardı, KALIR. VL kapısı tek başına yeterli: VL dünyayı değil EKRANI okur (OCR-otorite kanunuyla uyumlu ikinci ekran-tanığı). [konsey P0-1 revize; panel H2#9; GLM körlük]
2. **Terfi kanonik disiplini** — terfi `kanonik_sec` ile yazım seçer; rakamlı ilk-görülme ayrı anahtar açamaz. [konsey P0-2]
3. **`--tohum-yenile B1,B2,B3` CLI** — kopuş duvarından denetimli çıkış (`seri_kayit.yeniden_tohumla`). [konsey P0-3; panel A-4]
4. **`--teslim-disi` mod** — pilot PDF'leri export/ONAYLI'ya sızmaz, karantina klasörüne. [konsey P0-4; 248/250 forensik dersi]
5. **Telemetri olayları** — `bekleyen_dustu` olayı + eşleşen-isim VL-uyuşmazlık sayacı (basımı etkilemez, sadece ölçer). [konsey P0-5]
6. **Sayaç-idempotensi** — `uygulanan_bolumler` defteri; işlenmiş bölümde `uygula` atlanır (`--yeniden` ile zorlanır). Yeniden-mühürlemenin ÖN-ŞARTI: şişmiş yazım sayaçları çoğunluk oylamasını zehirler. [panel A-2; konsey P1-7]
7. **BOS_OKUMA ayrımı** — boş/çok-kısa okuma kopuş sayacına GİRMEZ; kanon-devir + "OKUMA_YOK" KONTROL. 2 ölü bant koşuyu tuğlalayamaz. [panel A-3]
8. **isim_kumele eş-görünüm vetosu** — aynı bölümde birlikte tanıklanan iki yazım birleştirilemez (~10 satır). Hem tohumu hem gelecekteki 600-tanık kümelemesini korur. [panel A-7; konsey çapraz-ateş]
9. **Unvan-strip normalizasyonu** — kümeleme öncesi `Dr./Prof./Av./Bey/Hanım/Paşa` + tire/parantez ayracı temizliği. [qwen tur-2 (b)]
10. **"BÖLÜM KONUKLARI" başlığı** + başlık listesi düzeltmesi (`bu bolumun konuklari` startswith kaçağı). [konsey P1-6]

Panel A-listesinden bilinçli ERTELENENLER: A-1 (export tazeleme/terfi) → Faz-B teslim otoritesi epoch'larla kökten çözer; A-9 (eş-kredi küme-farkı) ve rotasyon (B-1) → Faz-B matriste doğal çözülür (pilot-A verisi tasarım girdisi); A-5/A-6 (VL cırcırı, ardışık tanımları) → telemetriyle ölçülür, tamir edilmez (otorite devriyle emekli).

## 3. PİLOT PROTOKOLÜ (konsey + panel birleşik)

- **Kapsam:** 2 dizi × 30-60 bölüm, kasten farklı profil: (A) dönüşümlü-yönetmenli modern dizi, (B) eski-bantlı analog dizi. `--teslim-disi` zorunlu. 600-bölümlüğe bu fazda girilmez.
- **Metrikler:** tohum_vl_teyitsiz sayısı; eşleşen-isim VL-uyuşmazlık oranı (LLYAS senaryosu); bekleyen_dustu (iğne-deliği); KONTROL kök-neden dağılımı (dönüşümlü-ekip ayrı); ayrilma→geri_donus flap; terfi salınımı; konuk_max alarm doğruluğu; kopuş+tohum-yenile süresi; ikinci-koşu idempotensi diff'i; bölüm-başı duvar-saati.
- **Başarı kriterleri:** 20-isim el-denetiminde garble-kanonik=0 ve isim-kaybı=0; KONTROL-bölüm ≤%25 (yapısal rotasyon hariç-ayrı); kopuş duvarından ≤1 iş-günü çıkış; ONAYLI havuzunda pilot PDF=0.

## 4. FAZ-B ŞARTNAME ÇEKİRDEĞİ (pilot verisiyle inşa edilecek karar otoritesi)

- **Girdi:** birikmiş ledger (BolumOkuma snapshot'ları — bugün zaten yazılıyor, kimse okumuyor).
- **Varlık matrisi:** isim × bölüm; kümeleme = mevcut union-find + eş-görünüm vetosu + unvan-strip; zincir-birleşme riski pilot-verisiyle test edilir (konseyin AYLA~AYLIN uyarısı).
- **Üyelik modeli (qwen açık-dünya düzeltmesi):** AYRILDI damgası YOK; kişi-başı `Last_Seen` + dönem-aktif-kadro. Dönem = eşleşme-serisi değişim-noktası, AMA salt oran-düşüşüyle değil: yeni-dönem ancak GERÇEKTEN yeni (önceki dönemin garble-varyantı olmayan) isimler kümesi girince ilan edilir (qwen'in centroid-kayması kuralı — sahte segment freni).
- **Kanonik = iki EKRAN-tanığı + ihtilaf-eskalasyonu (Çağatay önerisi 2026-07-09):** OneOCR × glm-ocr (mevcut shadow-VL, her bölümde bedava); uyuşmazlıkta ÜÇÜNCÜ ekran-tanığı (gemma-vision / deepseek-ocr — pilotta seçilir) yalnız ihtilaflı ismin KIRPILMIŞ şeridini okur; **2/3 aynı → kanonik, 3'ü farklı → KONTROL**. Maliyet freni: yalnız ihtilaflı isim + yalnız crop + seri-başına BİR kez (karar anında, bölüm-başına değil) ≈ seri başına <1dk. KB'nin rolü DAR ve ASİMETRİK (Çağatay düzeltmesi): yalnız pozitif teyit (hit → güven artar; başrol/ünlü-konuk KB'de olabilir) + yazım-beraberliği bozucu; "KB'de yok" ASLA sinyal/ceza/düzeltme değildir — dizi crew'unun ~%90'ı hiçbir KB'de yoktur (qwen'in "KB herkese" önerisi bu alan-gerçeğiyle KIRPILDI). VL (pahalı) yalnız KONTROL-kanon + başlık-altı konuklara (qwen maliyet ayrımı geçerli).
- **Sınıf formülü (pilot-kalibreli başlangıç, qwen):** ANA KADRO `F > max(4, N×0.15) ∨ C > max(3, N×0.10)`; YARDIMCI/DÖNÜŞÜMLÜ `F > 3` (yeni PDF kategorisi adayı); KONUK `F ≤ 3 ∧ C ≤ 2`. N mümkünse KB'den toplam-yayınlanan bölüm. **Etiket: kanıtsız-varsayılan — pilot kalibre eder.**
- **Teslim = epoch:** üzerine yazma YOK; parti-2 → yeni epoch yan yana (v1/v2), insan onayı epoch-master'a (1 onay → tüm bölümler); erken teslim gerekirse "TASLAK/GEÇİCİ KÜNYE" işaretli proxy (qwen). Panelin A-1 export sorunu bu modelde kökten çözülür.
- **Streaming diff'in emekliliği:** Faz-B otorite olunca akan diff ya tamamen kalkar ya "anomali-nöbetçisi"ne iner (karar yetkisi yok).

## 4b. GERÇEK-KARE OKUMA TESTİ BULGULARI (2026-07-09, D:\master png test — 3 dizi)

Zincir (kare→compose→dilim→OneOCR→parse) üç profilde uçtan uca koştu. Süreler: compose 8-26sn, dilim+OCR ~1sn.
- **Diriliş Ertuğrul (modern, 854×6539, 265 satır):** ekip listesi büyük ölçüde doğru okundu (MEHMET BOZDAĞ, Veda Baycan, atölye/kuaför/ışık kadroları...). SORUN-1: **sponsor-logo sızıntısı** — sol kolon logoları (ÖZAK GLOBAL, DECORiSTAN, PARKELAM, TURMOBiL, www.hanhali.com) isim kovalarına karıştı; is_company bazılarını yakalayamıyor. ÇÖZÜM ADAYI: dilim_oneocr.jsonl'daki kutu-x koordinatıyla kolon ayrımı (veri zaten var) — pilot backlog. SORUN-2: aynı kişinin unvan-varyantları ham okumada çift ("Vrd Doc Hilmi Arie" + "Yrd. Doç. Hilmi Arıç") — yama-9 (unvan-strip) + kümelemenin tam hedefi, konsensüste birleşecek.
- **Yedi Numara (2002 eski, 31 satır):** temiz kartlar doğru (TOLGA TÜREL, ERTAN ERDAL). SORUN-3: **hayalet-bindirme bölgesi** (aynı-yerleşimli kartlar üst üste → "SFAFF PEHI OANAGI U" = SEDEF PEHLİVANOĞLU) — compose'un bilinen zaafı; vl_uyusmazlik telemetrisi bu bölgeleri sayacak. SORUN-4: **"63. Bölüm Sonu" kartı master'da GÖRÜNÜR ama OneOCR düşük-kontrastı okuyamadı** → stop-kart tetiklenmedi; VL'nin bölüm-no tanıklığı değerlendirilmeli (Faz-B). SORUN-5: `cast: MAVİ FİL` — dizi jeneriğinde "cast" başlığı CASTING AJANSI kredisi (şirket); parse oyuncu sanıyor → dizi-özel kural adayı: CAST altında tek-girdi + şirket-benzeri → ajans. SORUN-6: "Bu Dizi TRT / Tarafından FORA FİLM'e / Yaptırılmıştır" kapanış kalıbı parça parça isim sanılıyor → stop-kart/karaliste genişletmesi ("BU DİZİ...YAPTIRILMIŞTIR").
- **Zengin Olsaydın (dublaj yabancı, 4 satır):** zayıf yüzey birebir **BOS_OKUMA** vakası (4 < 8 eşiği) — yama-7 doğru tetiklenecek, kopuş sayacına girmeyecek. "THe END" tipi çöp tek-tanık kaldığı için konsensüse zaten giremez.
SONUÇ: yamaların gerekçeleri gerçek veride doğrulandı; 4 yeni dizi-özel iş pilot-backlog'a (kolon-ayrımı, cast-ajansı kuralı, BU-DİZİ kalıbı, VL-bölüm-no).

## 5. ÖĞRENİLEN SÜREÇ DERSLERİ (bu değerlendirmenin kendisinden)
- Çerçeve-meydan-okuma tasarım aşamasında yapılmalıydı (Fable öz-eleştirisi — feedback_tasarim_cerceve_denetimi_20260709).
- Dış modeller mimari-çerçeve körlüğünü yakalar (çerçevenin dışındalar) ama kod gerçeğini göremez; iç panel kod gerçeğini yakalar ama çerçeveyi miras alır. İkisi birlikte gerekli.
- Eşik önerilerinde dış modeller birbiriyle çelişti (%70 vs %40; 5 vs 8-10) — sayı önerisi kanıt değildir, ölçüm kanıttır.
