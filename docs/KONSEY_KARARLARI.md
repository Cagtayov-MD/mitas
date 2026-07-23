# MITAS Konsey Karar Kayıtları

## 2026-07-23 — testas özet stratejisi portu: v2 prompt kırmızı takım

**Soru:** MITAS ASR-özet promptunu 135-satır aşırı-reçeteli halden testas-türevi yalın hale
(~40 satır, "3-4 cümle / 35-60 kelime") indiriyoruz + kapalı-döngü ekliyoruz (kelime/noktalama/
dolgu kapısı + 3-deneme öz-düzeltme + deterministik onarım). Bu yalınlaştırma gürültülü ASR'de
kilit twist'i kaybettirir mi? Nerede patlar?
**Mod:** kırmızı takım
**Katılan:** glm (qwen: HTTP 401 geçersiz anahtar; kimi: HTTP 429 aşırı yük — TEK üyeli tur)

**Görüşler (GLM, 3 mercek):**
- Twist-kaybı GERÇEK: sıkı kelime limiti altında model yüksek-frekanslı betimlemeye kayıp
  tek-replik twist'i atlar (somut: Sixth Sense — 28 kelime, spoilersız, kapıdan geçer ama YANLIŞ).
- enforce-limit orta cümleleri düşürüyor → twist orta cümlelerde ölebilir.
- Türkçe kelime matematiği: eklemeli dil, 3-4 cümle + 4 isim + spoiler 35-60'a zor sığar → 45-75 öner.

**Benim değerlendirmem:**
- KABUL (twist-priority): v2 prompt'a "frekansı betimlemeyle doldurma, dönümü merkeze koy" eklendi.
- RED (kelime genişletme): kullanıcının asıl şikayeti UZUNLUK; testas'ın 32-65'i zaten Çağatay-onaylı
  çıktı veriyor. GLM kullanıcının derdini bilmiyor — konseyi burada geçtim ("5 dedi, 8 diyorum").
- NOT (enforce orta-cümle): testas'ta da aynı davranış; kapı >65'te yeniden-üretime zorluyor,
  trim son çare. A/B'de izlenecek; gerekirse "ara-kelime kırp" varyantı denenir.

**Karar:** v2 uygulandı (MITAS_OZET_V2 flag'i arkasında, legacy korundu). Nihai promote kararı
A/B eval'e bağlı (Çağatay onayı bekliyor). Qwen anahtarı council_mcp/.env'de düzeltilmeli.

---

## 2026-07-20 — Yerel VLM fine-tune yol haritası: kırmızı takım turu

**Soru:** "Damıtma ile yerel VLM fine-tune" planını yıkın — nerede patlar,
hangi varsayım yanlış?
**Mod:** kırmızı takım
**Katılan:** glm (qwen: Alibaba ödeme sorunu nedeniyle cevapsız; kimi: anahtar
henüz eklenmedi — bu tur TEK üyeli, tam konsey değil)

**Görüşler:**
- GLM: Plan teknik olarak zayıf — (1) N=150-200 örnek gerekli ama üretim
  maliyeti ~15 saat, (2) LoRA vision-encoder'a da uygulanmalı yoksa körlük
  düzelmez, 512×4188 panoramanın tiling sorunu benchmark'sız geçilemez,
  (3) ground-truth döngüsel hata riski gerçek — sentetik veriyle doğrulama
  gerekir, (4) bilinen tuzak: "glyph-blindness" (VLM'ler Türkçe diakritikte
  zayıf) + motion-blur/kesik-yazı sorunu, (5) NİHAİ ÖNERİ: fine-tune yapma,
  400 dosyayı doğrudan Claude batch API ile oku (~43M token, tahmini birkaç
  yüz dolar) — mühendislik süresinden çok daha ucuz/hızlı.

**Anlaşmazlık:** Ölçülemedi — sadece 1 üye cevap verdi, karşılaştıracak
ikinci görüş yok. Bu eksikliği Çağatay'a açıkça bildirildi.

**Benim değerlendirmem:** GLM'in teknik itirazları (vision-encoder LoRA,
tiling, glyph-blindness) sağlam ve daha önce düşünülmemişti — ciddiye
alınmalı. Ama nihai "yapma" önerisi eksik bilgiye dayanıyor: 400 dosyanın
SABİT bir arşiv mi yoksa SÜREKLİ büyüyen bir akış mı olduğunu bilmeden
maliyet/fayda hesabı tamamlanamaz. Bu soruyu Çağatay'a yönelttim.

**Karar:** BEKLEMEDE — Çağatay'ın "sabit mi sürekli mi" cevabına bağlı.
Roadmap dosyası (`docs/MITAS_VLM_Finetuning_Kunye_OCR_Plan_v1.md`) "taslak,
konsey eleştirisi bekliyor" olarak işaretlendi.

**Etki:** DEĞİŞTİRDİ — konsey olmasa muhtemelen doğrudan fine-tune planına
girilecekti; GLM'in itirazı en az bir kritik açık soruyu (tek-seferlik vs
sürekli) gün yüzüne çıkardı ve teknik riskleri (vision-encoder, tiling,
glyph-blindness) önceden işaretledi.

---

## 2026-07-20 — Aynı konu, DÜZELTİLMİŞ ölçekle 2. tur

**Soru:** İlk turda GLM'e YANLIŞ ölçek verilmişti (400 dosya, tek seferlik).
Gerçek: ~2.000 film + 8-10.000 dizi bölümü + belgesel + müzik programı —
sürekli büyüyen, 10.000-15.000+ ögelik hat. Çağatay'ın önerisi: "yerel/ucuz
motor taslak üretsin, Claude hedefli düzeltme yapsın" (tam sıfırdan-Claude
değil, tam otonom-fine-tune de değil — hibrit).
**Mod:** açık tur (düzeltilmiş brifing ile)
**Katılan:** glm (qwen: hâlâ Alibaba ödeme sorunu; kimi: anahtar yok)

**Görüşler:**
- GLM: **Fikir tam tersine döndü.** Doğru ölçekte hibrit yaklaşım "iki
  dünyanın en iyisi" — yerel taslak Claude'un işini "sıfırdan üretim"den
  "hata ayıklama"ya çevirir (token/maliyet düşer), Claude görselle
  karşılaştırdığı için halüsinasyon riski azalır (tam otonom fine-tune'a
  göre daha güvenli). Yan-ürün veri birikimini "bedava altın-standart veri"
  olarak nitelendirdi — 5-10K çift birikince fine-tune kararını GERÇEK
  rakamlarla vermeyi önerdi, şimdi spekülatif karar vermemeyi.

**Anlaşmazlık:** Yok — tek üye, ama KENDİ ÖNCEKİ GÖRÜŞÜYLE çelişti (doğru
sebeple: yanlış brifing düzeltildi).

**Benim değerlendirmem:** Katılıyorum. Bu aynı zamanda brifing-kalitesi
kuralımızın (CLAUDE.md) neden var olduğunun kanıtı — yanlış ölçek, yanlış
tavsiyeye yol açtı; düzeltince tavsiye tersine döndü. Hibrit yaklaşım zaten
test ettiğimiz OCR agent zincirine (text-comparison-validator,
ocr-quality-assurance) doğrudan oturuyor — yeni bir şey icat etmiyoruz,
var olanı doğru sırayla kullanıyoruz.

**Karar:** Hibrit üretim hattı ONAYLANDI (Çağatay + Claude + GLM mutabık).
Fine-tune kararı ERTELENDİ — üretim yan-ürünü olarak veri birikince (GLM'in
önerisi: ~5-10K çift) gerçek maliyet/hata verisiyle yeniden değerlendirilecek.

**Etki:** DEĞİŞTİRDİ (2. kez) — bu sefer konseyin KENDİ önceki kararını
düzeltmesi yönünde. Sistemin çalıştığının kanıtı: yanlış girdi yanlış çıktı
üretti, düzeltilmiş girdi doğru çıktı üretti.

## 2026-07-23 — Kod-avı turu (GLM; Kimi 429, Qwen 403): jenerik-onset üretim-sertleştirme bulguları

Ölçüm setinde (110 film) görünmeyen, üretimde (2400 film) patlayabilecek 8 bulgu.
Uygulama: T8 sertleştirme görevi (mini-tur-3 bittikten sonra — aynı dosyalar).

1. **[YÜKSEK] T4 geri-birleştirme bütçesi boşluk-sıfır zincirlerde sınırsız** — bütçe yalnız
   boşluklardan düşüyor; bitişik (bosluk=0) altyazı/tabela koşu zincirinde onset ~sınırsız
   geriye kaçabilir. Fix: bütçeden aday-uzunluğu da düş / toplam-mesafe sınırı.
2. **[YÜKSEK] _gecis_icerik_onayi tek rol-kelimesiyle onay** — hardcoded altyazıda "He was
   the director." tüm koşuyu onaylar. Fix: rol + aynı-karede isim-satırı VEYA ≥2 farklı rol.
3. **[YÜKSEK] _isim_gibi_kiril cümle-reddi yok** — Rusça hardcoded altyazı ("Здравствуйте.")
   title-case sayılıp kredisiz Rus filminde FP üretebilir. Fix: satır-sonu noktalama diskalifiyesi
   (Latin eşleniğindeki gard Kiril'e de uygulanmalı).
4. **[ORTA] kart-dizisi 'farklı metin' sayacı OCR gürültüsüne açık** — tek statik kartın 4 farklı
   OCR okuması "4 farklı kart" sayılır. Fix: benzerlik-birleştirme (difflib ≥0.8 aynı say) +
   kare atlamalı örnekleme.
5. **[ORTA] cop_desenli_mi 'y' sesli değil** — CRYSTAL/RHYTHM tipi tokenlar çöp sanılır
   (davranış riski düşük: yalnız gereksiz Kiril-denemesi). Fix: y'yi sesli say.
6. **[ORTA] _scroll_kurtarma pencere-sınırı kırpması** — %75 sınırında başlayan koşunun başı
   sayılmaz, kısa kalır. Fix: sınırdan geriye yürüyüp gerçek koşu başını al.
7. **[ORTA] kart-dizisinde rakam-ağırlıklı kartlar** — "Year 1999" montaj kartları isim sanılır
   (yalnız kazanan-koşulu filmde sapma riski; kredisiz filmde tetiklenemez). Fix: %50+ rakamlı
   satır diskalifiye.
8. **[DÜŞÜK] _scroll_kurtarma orta-ekran crawl** — alt-bant ticker'ı alt_only filtresi zaten
   eliyor (GLM'in senaryosu kısmen örtülü); orta-ekran kayan metin için yükseklik-kapsama
   kontrolü eklenebilir.

Konsey sağlığı: Kimi tekil testte ÇALIŞTI ama tam turda gene 429 (k3 yük-hassas) →
kimi.py'ye k2.6 yedeği eklendi (be99ddf; MCP restart sonrası aktif). Qwen: yeni anahtar
intl-uçta auth GEÇİYOR ama TÜM modeller 403 Unpurchased → Alibaba Model Studio
hesabında model-erişimi/billing AKTİVE EDİLMELİ (konsoldan; anahtar tarafı tamam).
