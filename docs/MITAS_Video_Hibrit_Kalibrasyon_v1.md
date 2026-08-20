# MITAS Video-Hibrit Router — §4-adım-1 Kalibrasyon Raporu

**Tarih:** 2026-07-20 · **Girdi:** `candidate_runs/vllm_bench_20260718/HYBRID_DEVIR_NOTU.md`
**Durum:** Kalibrasyon tamamlandı. **Adım-2 (router modülü) DURDURULDU** — gerekçe §4.

---

## 1. Yapılan iş

Devir notunun §4-adım-1'i istendiği gibi yürütüldü: 28 bench-filminin jenerik
manifest sinyalleri (`strict_scroll_frac`, blok/kare sayısı, yükseklik) çekildi,
ölçülmüş video-recall ile korele edildi, eşik arandı.

Üretilen araçlar (hepsi `candidate_runs/vllm_bench_20260718/`):

| dosya | iş |
|---|---|
| `router_kalibrasyon.py` | manifest sinyalleri + film-bazlı video recall |
| `router_kiyas.py` | **video vs master-PNG** film-bazlı karşılaştırma |
| `router_sinyal_v2.py` | Spearman + tek/çift sinyal eşik taraması |
| `router_loocv.py` | leave-one-out ile aşırı-uydurma sınaması |
| `router_kos_sonra_devret.py` | alternatif tasarımın süre ekonomisi |
| `gt_yanlilik_denetimi.py` | **zemin-gerçek geçerlilik denetimi** |

Manifestler `candidate_runs/kunye51_20260714/Database/<film>/` altında bulundu
(28/28 eşleşti). 24 filmde GT var; MAVZER GT'si 2 isim olduğu için (§5 uyarısı)
dışlandı → **n=23**.

---

## 2. Devir notunun ana hipotezi çürüdü

§2'nin önerdiği kural "`strict_scroll_frac` düşük → video-uygun" **ayrıştırmıyor**:

- GÜZEL_BİR_ÖLÜM `scroll_frac=0.881` (çok kayan) → video **1.000**
- FRANNY `scroll_frac=0.063` (en statik) → video **0.720**

Spearman (sinyal ↔ Δrecall): `kare_x_scroll` −0.445, `scroll_frac_w` −0.432,
`scroll_frac_max` −0.329, `h_toplam` −0.013. Hiçbiri karar verdirecek güçte değil.
Notun "isim sayısı belirleyici" varsayımı da zayıf çıktı (GT-isim ↔ Δrecall = −0.304).

En iyi iki-sinyal kuralı `blok ≤ 80.5 AND kare_x_scroll ≤ 189.5` eğitim setinde
TP=7 FP=0 verdi; ama bu 23 noktada ~128.000 hipotez taranarak bulundu.
**LOOCV: %74 doğruluk (TP=5 FP=1 FN=5 TN=12).** Kural 23 fold'un 21'inde aynı
çıktı — yani gürültü değil, ama karar-vermeye yetecek güçte de değil.

### Strateji kıyası (23 film)

| strateji | Δrecall | ort. hız | toplam süre |
|---|---|---|---|
| hep-master (mevcut üretim) | +0.000 | 1.0× | 5658 sn |
| hep-video | −2.337 | 5.7× | 1488 sn |
| LOOCV a-priori router | **+0.663** | 2.0× | — |
| koş-sonra-devret | — | — | 3718 sn (1.52×) |
| oracle (kusursuz router) | +1.311 | 4.8× | 2618 sn (2.16×) |

---

## 3. ASIL BULGU — ölçüm dairesel, "uydurma" metriği güvenilmez

Kalibrasyon sırasında zemin-gerçeğin kendisi denetlendi. **`claude_gt/*.json`'un
313 slice'ının tamamı `*_reading_master_runaware_p*.png` kaynaklı** — yani GT,
master-PNG okunarak üretilmiş. Sonuç: GT, master-PNG'nin görebildiğiyle sınırlı.
Video gerçek kareleri gördüğü için master-PNG'nin kaybettiği metni okuyabiliyor,
ama GT'de olmadığı için metrik bunu **"uydurma" sayıyor**.

### Kanıt — KULÜBE (Rancho Notorious, 1952)

GT'nin ilk master-PNG dilimi ile video okuması satır-hizasında:

| GT (master-PNG'den) | VİDEO |
|---|---|
| FIDELITY PICTURES, INC. | FIDELITY PICTURES, INC. |
| PRESENTS | PRESENTS |
| `[okunamadı] (kesik satır alt-silueti, IN'in üstünde)` | **MARLENE DIETRICH** |
| — | **ARTHUR KENNEDY** |
| `[okunamadı] (kesik satır silueti, IN'in altında)` | **MEL FERRER** |
| IN | IN |
| RANCHO / NOTORIOUS | RANCHO NOTORIOUS |
| with … (aynı 11 isim) | with … (aynı 11 isim) |

Bu üçü Rancho Notorious'un gerçek başrolleridir (video jeneriğin sonunda
yönetmen FRITZ LANG'ı da okumuş). Puanlayıcı bu üçünü **"uydurma"** saydı.

Aynı desen YARI_SERT'te (Semi-Tough, 1977): 36 "uydurma"nın içinde
KRIS KRISTOFFERSON, JILL CLAYBURGH, LOTTE LENYA, GENE AUTRY, JERRY FIELDING —
filmin gerçek künyesi.

Tüm "uydurma" havuzunun **%98.7'si isim-formunda**; yalnızca %1.3'ü gerçek
teknik gürültü (`CH2 STEREO MIX RIGHT`, `ANAMORPHIC 16 9` — FRANNY'de bir
teknik slate). Yani devir notunun §1'deki "video tüm-kareyi görüyor →
altyazı/dekor karışıyor" teşhisi de **veriyle desteklenmiyor**.

> Not: `[okunamadı]` sayısı ile uydurma sayısı arasında korelasyon çıkmadı
> (+0.057). Mekanizma yalnız "işaretli okunamadı" değil; master-PNG bazı
> jenerik bloklarını **hiç üretmemiş** olabilir — o zaman GT'de iz de kalmaz.
> Bu, aşağıdaki §5'in birinci maddesinin sebebi.

### Bunun üç sonucu

1. **Video'nun recall'ı düşük ölçülmüş** — GT'de olmayan doğru okumalar
   paydaya girmiyor, üstelik ceza yazılıyor.
2. **Master-PNG'nin recall'ı yapay yüksek** — kendi ürettiği kaynağa karşı
   ölçülüyor (dairesellik).
3. **Router kalibrasyonu bu GT üzerinde sonuçlandırılamaz.** Hedef değişken
   ("video mu master mı kazandı") sistematik olarak master lehine kaymış.

---

## 4. Karar — adım-2 neden durduruldu

Prensip 1 (*gerçek bağlama hizmet ediyor mu*) gereği: bozuk bir ölçüme eşik
uydurmak, sorunu değil sorun-görünenini çözer. Router'ı bu GT ile kalibre edip
üretime almak, master-PNG lehine yanlı bir kapıyı kalıcılaştırırdı.

Ayrıca bulgu, router'dan **daha değerli** bir şeye işaret ediyor: eğer
master-PNG jenerik bloklarını sessizce kaybediyorsa, bu mevcut **üretim
yolunda bir kusurdur** ve 2.000 filmin tamamını etkiler. Router en iyi
ihtimalle 2× hız verecekti; bu ise doğrudan künye doğruluğu.

## 5. Dış konsey turu (2026-07-20)

Kırmızı-takım brifingi gönderildi. **Yalnız GLM cevapladı** (Qwen: HTTP 401
anahtar hatası — bilinen Alibaba hesap sorunu; Kimi: HTTP 429 bakiye bitmiş).
GLM üç merceği de kendi içinde canlandırdı, yani tek ses — buna göre tartıldı.

GLM'in hükmü: *a-priori router'ı kurma, "koş-sonra-devret"e geç; %14 uydurma
OCR-otorite kanununu ihlal eder.*

**Tartı:** GLM'in a-priori router'a itirazı ve koş-sonra-devret tercihi
doğrulandı — süre ekonomisi iddiası da sayısal olarak tutuyor (1.52×).
Post-hoc sinyaller a-priori olanlardan gerçekten daha ayırt edici
(`video_sn` ↔ Δrecall = −0.664, en iyi a-priori −0.445).

**Ama GLM'in temel dayanağı yanlıştı:** "%14 uydurma"yı veri olarak kabul edip
üzerine hüküm kurdu, metriğin geçerliliğini sorgulamadı. Uydurmayı "temporal
birleştirme kaynaklı yapısal halüsinasyon" diye açıkladı — KULÜBE kanıtı bunu
çürütüyor: video doğru okudu, GT yanlış saydı. GLM ayrıca Δ=0 olan
KIZGIN/SON_METRO'yu "anlamsız kazanım" saydı; oysa aynı kalitede 4.4× ve 24×
hız en temiz kazanç türüdür.

---

## 6. Öneri — sıradaki iş

**Router'ı kurmadan önce ölçümü düzelt.** Sıra:

1. **Bağımsız GT** — 6-8 filmde zemin-gerçek master-PNG'den DEĞİL, ham video
   karelerinden üretilsin. Böylece iki yol da aynı, yansız kaynağa karşı
   ölçülür. Bu olmadan hiçbir router eşiği güvenilir değil.
2. **Master-PNG kayıp denetimi** — video'nun okuyup master-PNG'nin hiç
   üretmediği jenerik blokları var mı? Varsa üretim yolunda kusur demektir
   (§4). Bu, router'dan öncelikli.
3. **Sonra** router: yeni GT ile kalibrasyon tekrarlanır. Mevcut kanıt
   **koş-sonra-devret**'i işaret ediyor (a-priori sinyaller zayıf, post-hoc
   sinyaller güçlü, mevcut yol bozulmuyor).

⚠ **Uyarı:** §3'ün "devret tetikleyicisi" taramasındaki `uydurma_oran` GT'ye
karşı ölçülüyor — **üretimde GT yok**. Uygulanabilir bir devret kuralı için
GT'siz bir uydurma-vekili gerekir; bu henüz tasarlanmadı.

---

# EK — Master-PNG Kayıp Denetimi (§6-madde-2 yürütüldü)

**Araç:** `masterpng_kayip_denetimi.py` → `masterpng_kayip.json` (salt-okuma).

**Ayraç:** aynı master-PNG'yi 22 bağımsız model okudu (12 filmde; kalan 16 filmde
2 model). Video'nun okuduğu bir isim HİÇBİR model tarafından bulunamamışsa o metin
PNG'de yoktur — 22 modelin aynı ismi birlikte kaçırması gerçekçi değil.

**Sonuç:** video'nun okuduğu 2096 ismin **680'i (%32.4) hiçbir master-PNG
modelinde yok.** Ayracın en güvenilir olduğu 12 filmde (≥10 model): 266/965 (%27.6).

## E1. Üç ayrı popülasyon var — tek hüküm yanlış olur

Örnekler incelendiğinde PNG-dışı adaylar üç farklı şeye ayrılıyor:

### (a) GERÇEK KAYIP — master-PNG'nin kaybettiği doğru künye

**BEYAZ_BİZON (The White Buffalo, 1977) — kanıtlanmış vaka.** Master-PNG'nin
tamamı yalnızca EKİP bloğu: `film editor / MICHAEL F ANDERSON`, `production
designer / TAMBI LARSEN`, `music / JOHN BARRY`, `director of photography /
PAUL LOHMANN`, `screenplay by / RICHARD SALE`, `produced by / PANCHO KOHNER`,
`directed by / J. LEE THOMPSON`. Qwen3-VL ve GLM-OCR **birebir aynısını** okudu —
demek ki PNG'de gerçekten bu kadar var.

Video ise ayrıca DINO DE LAURENTIIS, JACK WARDEN, CLINT WALKER, SLIM PICKENS,
STUART WHITMAN, ED LAUTER, MARTIN KOVE okudu — filmin gerçek oyuncu kadrosu.
**Master-PNG açılış oyuncu kartını komple kaybetmiş.** Bu film GT'si olmayan
4 filmden biri olduğu için kayıp benchmark'a hiç yansımamıştı.

Aynı desen MAKSİM'İN_KAPICISI'nda: MICHEL GALABRU, JEAN LEFEBVRE,
FRANCIS PERRIN, ALFRED ADAM, ALAIN POIRÉ, ROBERT DALBAN — gerçek Fransız kadro.
Ve KULÜBE'de (§3'teki Marlene Dietrich vakası).

### (b) GERÇEK UYDURMA — video'nun yoğun/kayan jenerikte halüsinasyonu

BABAM'ın 65 PNG-dışı adayı: NURBA DIOSHINA, DORJANJU MREMETI, PAHISH KANISHI,
DARANIC ASHIL MAIN… 390-isim teşekkür-duvarında video gerçekten uyduruyor.
DAĞ_ADAMLARI'nda CRAN T. HESTON (= CHARLTON HESTON'ın bozulmuşu), HENNY'S ATON,
FON. WHALE — garble + uydurma karışımı.

**Yani devir notunun uydurma endişesi tümüyle yanlış değildi — ama yanlış
filmlerde doğruydu.** Uydurma yoğun/kayan jeneriğe özgü; kart-jenerikte değil.

### (c) METRİK ARTEFAKTI — gerçek ekran metni, "isim" sanılmış

CENNETTE_BULUŞALIM'ın 46 adayının çoğu: `PELÍCULA SUBVENCIONADA POR EL`,
`NOTICIARIO`, `DOCUMENTALES`, `NO DO`, `PRESENTA`, `AÑO X` — İspanyol NO-DO
haber filmi başlıkları ve filmin Türkçe adı (`CENNETTE`, `BULUŞALIM`).
Bunlar ne kayıp ne uydurma; `is_name()` sınıflandırıcısının hatası.

## E2. Yapısal delil — blok düşüyor

Manifestlerde `blocks` vs `kept_blocks` farkı, PNG'ye hiç girmeyen jenerik
bloklarını gösteriyor:

| film | blok | tutulan | **düşen** |
|---|---|---|---|
| DÜNYANIN_EN_MÜTHİŞ_ADAMI | 84 | 68 | **16** |
| CENNETTE_BULUŞALIM | 82 | 70 | **12** |
| JURASSIC_PARK_2 | 75 | 64 | **11** |
| CENNETİN_RENGİ | 146 | 138 | **8** |
| BABAM | 36 | 29 | **7** |
| MAKSİM'İN_KAPICISI | 80 | 74 | **6** |

**Ama tek sebep bu değil:** KULÜBE'de düşen blok YOK (54/54) ve yine de
Marlene Dietrich kayıp. GT o satırı `kesik satır silueti` diye işaretlemiş —
yani blok tutulmuş ama **kırpma satırı kesmiş**. En az iki ayrı kayıp
mekanizması var: (1) blok düşürme, (2) bölge-kırpma taşması.

## E3. Bu denetimin sınırı

- 16 filmde ayraç yalnız 2 modele dayanıyor — orada "PNG-dışı" daha zayıf delil.
  En güçlü kayıp örneklerim (BEYAZ_BİZON, MAKSİM, JURASSIC) ne yazık ki bu
  gruptan; BEYAZ_BİZON'u satır-satır elle doğruladım, diğerleri doğrulanmadı.
- (a)/(b)/(c) ayrımı örneklem üzerinden yapıldı, **otomatik sınıflandırılmadı**.
  680 adayın kaçının gerçek kayıp olduğu sayısal olarak bilinmiyor.
- Kesin ayrım için §6-madde-1'deki bağımsız GT şart.

## E4. Hüküm

1. **Master-PNG'de gerçek bir kayıp kusuru var** — en az bir filmde (BEYAZ_BİZON)
   oyuncu kartının tamamı kaybolmuş, kanıtlanmış. İki mekanizma: blok düşürme
   ve kırpma taşması. Bu, router'dan öncelikli bir üretim-yolu meselesidir.
2. **Video'nun uydurması da gerçek** — ama yoğun/kayan jeneriğe özgü.
   Bu ikisi birlikte hibrit fikrini GÜÇLENDİRİR: iki yolun kusurları farklı
   yerlerde. Kart-jenerikte video kazanıyor, yoğun jenerikte master-PNG.
3. **Ama hiçbiri mevcut GT ile sayısallaştırılamaz.** Bağımsız GT olmadan
   ne kayıp oranı ne uydurma oranı güvenilir.

## 7. Dokunulmayanlar

Bu çalışma yalnız **okuma + yeni analiz scriptleri** üretti. `scripts/`,
`core/`, master-PNG üretim yolu, mevcut çıktılar — hiçbirine dokunulmadı,
hiçbir şey silinmedi.
