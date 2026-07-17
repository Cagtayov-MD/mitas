# ŞEF (CONDUCTOR) — künye-okuma orkestra mimarisi (2026-07-06)

Çağatay: "Elimizde 3 model var (OneOCR/GLM/VL), üçü de bir şekilde doğru okuyor. Önemli olan doğru
YÖNLENDİRME yaparak doğru yazıyı doğru modele okutmak. Bütün orkestra parçaları var, sadece şarkıyı
çalamıyoruz." → Eksik parça: modelleri HİYERARŞİ (patron+yedek) değil ENSEMBLE (uzmanlar) olarak
kullanan bir ŞEF.

## KUZEY-YILDIZI
Frame'de bir isim VARSA → doğru şekilde PDF'e. Aktaramazsak başarısızlık. (Sayı değil, aktarım.)

## ENSTRÜMAN PROFİLLERİ (kanıtlı)
| Model | Güçlü | Zayıf | Maliyet |
|---|---|---|---|
| OneOCR | temiz düz metin, yoğun-liste, HIZLI | italik/dekoratif/SD tek-kart (varyans: Minnelli 4-okuma) | ~0 (CPU) |
| GLM-OCR | tek-net-isim/etiket, tertemiz, HIZLI | yoğun-ufak-TR liste (bozar/loop), ara-sıra CJK-çöp | 5-19 sn (GPU) |
| VL (gemma) | bağlam (etiket+isim), tek-kart | yavaş, VRAM-ağır, liste-loop | 10-30 sn (GPU) |

## ŞEFİN ÜÇ İŞİ

### 1) YÖNLENDİRME (routing) — hangi yazı hangi enstrümana
- **HER film**: OneOCR birincil geçer (bedava, hızlı) → ham okuma + GÜVEN-SİNYALİ üretir.
- **GÜVEN-SİNYALİ** (bir alanın "zor/şüpheli" olduğunu söyler):
  - case-garble (kelime-içi büyük harf: VincenTe/SouthonBst) → KESİN şüphe
  - kareler-arası tutarsızlık (aynı yuva 2+ farklı okundu) → OCR sallandı
  - alan-BOŞ ama frame'de rol-etiketi VAR (DIRECTED BY altı okunamadı) → kayıp
  - fuzzy-yakın-ama-tam-değil (yalnız DESTEK, tek başına değil)
- **Şüpheli alan** → o alanın KARESİ uzman-modele yönlendirilir:
  - YÖNETMEN / tekil-kart → **GLM birincil, VL ikincil** (GLM bu işte usta+hızlı)
  - CAST-LİSTESİ → **OneOCR kalır** (GLM liste-zaafı); yalnız tek-tek garble-oyuncu için GLM/VL
- **Temiz alan** (sinyal yok) → OneOCR sonucu AYNEN (uzman-model çağrılmaz — GPU-zaman israfı yok)

### 2) UZLAŞTIRMA (reconciliation) — çıkanları hakemle
Bir alan için elde N okuma (OneOCR + [GLM] + [VL]):
- **HEPSİ AYNI** (fold-eş) → GÜVEN TAM → yaz.
- **2 AYNI 1 farklı** → çoğunluk + KB-teyit → yaz (Minnelli: GLM=VL, OneOCR garble → GLM/VL kazanır).
- **HEPSİ FARKLI** → KB/kimlik HAKEM: hangi okuma KB-rol-teyitli (fuzzy-kanonik ≥0.90+marj) → o.
- **Hiçbiri KB/kimlik-teyitli değil AMA çift-ekran-imza var** (kunye+dilim aynı) → yaz (ekran-otorite).
- **Hiçbir teyit yok** → alan OLDUĞU GİBİ kalmaz, BOŞ → film Kontrol'e ("okunamadı>yanlış-oku").

### 3) TEYİT (verification) — her yazılan bir kanıta dayanır
Yazılan isim ≥1 çapaya bağlı olmalı: model-mutabakatı (2+), VEYA KB-rol-teyit, VEYA çift-ekran-imza,
VEYA XML/kimlik. Çıplak tek-model-tek-okuma ASLA yazılmaz (fabrikasyon-freni).

## NEDEN ŞİMDİYE KADAR ÇALINAMADI (borç teşhisi)
Modeller farklı zamanlarda YEDEK olarak eklendi: OneOCR patron, VL yalnız QC1-RED'de, GLM consensus-
kapalı. Garble-ama-makul isim QC1'i GEÇTİĞİ için uzman hiç çağrılmadı. Yani hiyerarşi uzmanı "çökünce"
çağırıyordu; oysa uzman "zor yazıda" çağrılmalı. Şef bu tetikleyiciyi (çökme değil, GÜVEN-SİNYALİ) kurar.

## KADEMELİ İNŞA (kanıt-kapılı)
1. **GÜVEN-SİNYALİ katmanı** (salt-ölçüm, karar-etkisiz): her alana case-garble/tutarsızlık/etiket-boş
   skorunu işle → kaç alan "şüpheli" görülüyor ölç. KAPI: sinyal temiz-alanı yanlış-işaretleme oranı <%5.
2. **ŞEF-YÖNLENDİRME (yalnız YÖNETMEN)**: şüpheli-yönetmen → GLM-kare-oku → uzlaştır → KB-teyit.
   Golden 28/28 + garble-15-vaka kıyasıyla A/B. KAPI: garble-yön kurtarma ≥%60, temiz-yön regresyon=0.
3. **UZLAŞTIRMA motoru** (mutabakat+KB-hakem) → yönetmende ölç, cast'e genişlet.
4. **CAST tek-tek garble** → GLM/VL yalnız garble-imzalı oyuncuya (liste-toptan DEĞİL).
5. Master-PNG-first (konsey kararına göre) YÖNETMEN-kartı için birincil-girdi olarak şefe eklenebilir.

## KİLL-SWITCH + KORUMA
- MITAS_SEF=0 → şef kapalı, bugünkü davranış.
- Her katman ayrı bayrak; golden-regresyon her adımda; byte-nötr A/B.
- Tek-GPU: uzman yalnız ŞÜPHELİ-alanda çağrılır (her isme değil) → maliyet kontrollü (Çağatay kalite>hız
  dedi ama israf değil — temiz alan bedava OneOCR'da kalır).

## ÖLÇÜLEBİLİR BAŞARI ("frame'de varsa doğru PDF'e")
Garble-kıyas seti (18 vaka, genişletilebilir) = ALTIN. Her vaka için: frame'de-gerçek-isim (insan-teyitli)
vs PDF-çıktısı. Başarı = frame'de-var-ve-PDF'te-doğru / frame'de-var. Şef öncesi vs sonrası bu oranla ölçülür.
