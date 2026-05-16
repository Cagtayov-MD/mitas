# CODEX GÖREV TALİMATI — Tedial Faz 0 Doğrulama

> Bu döküman bir coding agent (Codex) için yazılmıştır. Görevleri **sırayla** yap.
> Her görevin sonunda **Kabul Kriteri** vardır; sağlanmadan sonraki göreve geçme.
> Türkçe yorum/çıktı kabul; kod İngilizce. **Sıfır pip kurulumu** — yalnızca Python
> standart kütüphanesi kullan.

---

## 0. Bağlam (neden bu iş)

TRT'nin arşivi **Tedial** (iTClient, host `evo.int.trt.net.tr`). Programatik API
yok; biz kendi UI'mıza bir **backend vekil (proxy)** ile arama + low-res video
getireceğiz. Kod yazmadan önce **5 teknik gerçeği** canlı sistemden doğrulamamız
gerekiyor. Bu görev sadece **doğrulama + raporlama**; entegrasyon kodu YAZMA.

Doğrulanacak 5 gerçek:

| # | Soru |
|---|------|
| 1 | Login akışı: hangi endpoint'e, hangi alanlarla POST? SSO/CAPTCHA var mı? Hangi `Set-Cookie`'ler dönüyor? |
| 2 | `doNewSearch.html`: istek JSON gövdesinin alanları + **yanıt HTML yapısı** (asset satırı CSS seçici/`id`'leri, asset ID / süre / keyframe URL nerede gömülü) |
| 3 | `refreshPlaybackToken.html`: istek + yanıt (JSON) — token formatı, `file.mpd`/`cache_lowres` ile ilişkisi, ömrü |
| 4 | `file.mpd` hangi endpoint'ten elde ediliyor (asset ID → manifest)? `.mpd` isteğinden hemen önce hangi istek var? |
| 5 | `cache_lowres` host'u (port 443) `JSESSIONID` istiyor mu, public mi, imzalı/süreli URL mi? `Range` isteğine nasıl yanıt veriyor? |

---

## ÖN KOŞUL — İnsandan gelecek girdi: `tedial_capture.har`

Bu dosyayı **insan** sağlayacak. Yoksa İNSAN'a şu talimatı ver ve bekle:

> 1. Chrome'da Tedial'a giriş yapılacak ekrana gel (henüz login OLMA).
> 2. F12 → **Network** sekmesi → **Preserve log** işaretle → filtre **All**.
> 3. Tedial'a **login ol**.
> 4. Bir **arama** yap.
> 5. Sonuçlardan bir asset aç, **videoyu oynat**, biraz **ileri sar**.
> 6. Network panelinde sağ tık → **"Save all as HAR with content"** →
>    dosyayı bu klasöre `tedial_capture.har` adıyla kaydet.
> ⚠️ HAR ham hali oturum cookie'leri / parola içerebilir. Aşağıdaki betik
>    bunları maskeler; ham HAR'ı rapora KOPYALAMA.

`tedial_capture.har` bu klasörde mevcut olduğunda görevlere başla.

---

## GÖREV 1 — `analyze_har.py` yaz ve çalıştır

**Amaç:** HAR'ı parse edip 1–4. soruların ham kanıtını maskeli şekilde çıkar.

**Spesifikasyon:**

- Girdi: aynı klasördeki `tedial_capture.har` (HAR = JSON).
- Yalnızca standart kütüphane: `json, sys, re, html, collections, urllib.parse`.
- `log.entries` üzerinde dön. Şu URL parçalarından **birini** içeren entry'lerle
  ilgilen (case-insensitive):
  `login`, `j_security_check`, `doNewSearch`, `refreshPlaybackToken`,
  `loadDefaultSearch`, `loadCategoriesTree`, `checkEnabledSworkActions`,
  `.mpd`, `cache_lowres`, `KeyframeService`.
- Ayrıca: `Set-Cookie` içinde `JSESSIONID` bulunan **ilk** entry'yi "olası login
  yanıtı" olarak işaretle (heuristik).
- Her ilgili entry için şunları çıkar:
  - `method`, tam `url`
  - **request headers**: isim listesi; `Cookie`, `Authorization` değerleri →
    `<MASKED>` (sadece isim göster)
  - **request body** (`postData`): `mimeType` + içerik. JSON parse edilebiliyorsa
    **anahtar ağacını** yazdır; değerleri kısalt (>80 karakter ise `…`).
    Anahtar adı `pass|pwd|password|token|secret|credential` regex'iyle eşleşen
    alanların **değerini** `<MASKED>` yap.
  - `response.status`, response `Content-Type`
  - **response headers**: `Set-Cookie` adlarını göster, değerleri `<MASKED>`
  - **response body**:
    - `text/html` ise: toplam uzunluk + ilk 3000 karakter + tekrar eden satır
      kalıbı özeti (en sık geçen `<li ...>`, `<tr ...>`, `<div class="...">`
      açılış etiketlerini `collections.Counter` ile ilk 15 tanesini listele —
      asset satırını bulmamıza yarar).
    - JSON ise: anahtar ağacı + kısaltılmış değerler (maskeleme aynı kuralla).
    - diğer/binary ise: sadece tür ve boyut.
- Tüm çıktıyı hem stdout'a yaz hem `faz0_har_ozet.txt` dosyasına kaydet
  (UTF-8). Bölümleri `=== [n] URL ===` başlıklarıyla ayır.
- Hiç eşleşme yoksa net hata bas: hangi URL'lerin HAR'da olduğunu (ilk 30 tane)
  listele ki insan yanlış yakaladıysa görelim.

**Çalıştır:** `python analyze_har.py`

**Kabul Kriteri:**
- [ ] `faz0_har_ozet.txt` oluştu ve içinde en az `doNewSearch` ve `.mpd`
      entry'leri var.
- [ ] Hiçbir gerçek cookie değeri / parola / token düz metin görünmüyor
      (hepsi `<MASKED>`).
- [ ] `doNewSearch` yanıtı için tekrar eden HTML satır kalıbı özeti üretildi.

---

## GÖREV 2 — `test_cache_lowres.py` yaz ve çalıştır

**Amaç:** 5. soruyu (cache_lowres auth) canlı HTTP ile doğrula.

**Spesifikasyon:**

- Yalnızca standart kütüphane: `urllib.request, urllib.error, ssl, os, sys, re`.
- Test edilecek URL'i şu sırayla bul:
  1. Komut satırı argümanı `sys.argv[1]` verilmişse onu kullan.
  2. Yoksa `faz0_har_ozet.txt` içinde `https://evo.int.trt.net.tr/cache_lowres/...`
     ile başlayan ilk URL'i regex'le çek.
- TLS: iç sistem sertifikası olabilir →
  `ctx = ssl._create_unverified_context()` kullan.
- 3 test yap, her biri için **status code + ilgili header'lar** raporla:
  1. `GET`, cookie YOK, `Range` YOK.
  2. `GET`, cookie YOK, `Range: bytes=0-1023` → `status`, `Content-Range`,
     `Accept-Ranges`, `Content-Length`.
  3. `COOKIE` ortam değişkeni doluysa: `GET`, `Cookie: <env>` + `Range` ile.
     (İnsan tarayıcıdaki Cookie header'ını `COOKIE` env'ine koyabilir; yoksa bu
     testi "atlandı" diye işaretle.)
- 401/403 → cookie gerekiyor; 200/206 → erişilebilir; 206 + `Content-Range` →
  byte-range destekli (proxy için ideal). Yorumu açıkça yaz.
- Çıktı: okunur tablo + `faz0_cache_lowres_sonuc.txt`.

**Çalıştır:**
`python test_cache_lowres.py`  (gerekirse `python test_cache_lowres.py "<url>"`)

**Kabul Kriteri:**
- [ ] `faz0_cache_lowres_sonuc.txt` oluştu.
- [ ] 3 testin her biri için status code kaydedildi (veya "atlandı" gerekçesi).
- [ ] "Bu host cookie istiyor mu / byte-range destekli mi" sorusu net cevaplandı.

---

## GÖREV 3 — `FAZ0_BULGULAR.md` raporunu doldur

`faz0_har_ozet.txt` ve `faz0_cache_lowres_sonuc.txt` çıktılarına dayanarak
aşağıdaki şablonu **kanıtla** doldur. Tahmin etme — veride yoksa "HAR'da
görünmüyor, ek yakalama gerek" yaz.

```markdown
# Tedial Faz 0 — Bulgular

## 1. Login akışı
- Endpoint (method + URL):
- İstek alanları (maskeli):
- SSO/CAPTCHA var mı:
- Dönen Set-Cookie adları:
- Sonuç (otomasyon mümkün mü):

## 2. doNewSearch.html sözleşmesi
- İstek Content-Type + JSON alan ağacı:
- Yanıt Content-Type:
- Asset satırının HTML seçicisi (class/id):
- Asset ID / başlık / süre / keyframe URL nerede gömülü:
- Parser stratejisi (hangi seçiciler):

## 3. refreshPlaybackToken.html
- İstek (method/alanlar):
- Yanıt gövdesi (token alanları):
- Token; file.mpd/cache_lowres ile ilişkisi:
- Ömür/yenileme ihtiyacı:

## 4. file.mpd elde etme
- .mpd'yi döndüren/öncesindeki endpoint:
- Asset ID → manifest eşlemesi:

## 5. cache_lowres auth
- Cookie'siz status (testler 1-2):
- Cookie'li status (test 3 / atlandı):
- Byte-range desteği (Content-Range):
- Sonuç (proxy'de cookie passthrough gerekli mi):

## Faz 1 için engel/risk
- (HAR'da eksik kalan, ek yakalama gereken her şey)
```

**Kabul Kriteri:**
- [ ] 5 başlık da ya kanıtla dolu ya da "veri yok + ne gerekiyor" notuyla dolu.
- [ ] Hiçbir maskelenmemiş sır içermiyor.

---

## TESLİM EDİLECEK DOSYALAR (bu klasörde)

1. `analyze_har.py`
2. `test_cache_lowres.py`
3. `faz0_har_ozet.txt`
4. `faz0_cache_lowres_sonuc.txt`
5. `FAZ0_BULGULAR.md`  ← asıl önemli çıktı

## YAPMA / SINIRLAR

- Entegrasyon/proxy kodu YAZMA (bu Faz 1, sonraki adım).
- Tedial'a yazma/değiştirme isteği gönderme — sadece **GET/okuma** ve verilen HAR.
- Ham HAR içeriğini raporlara kopyalama; daima maskeli özetle çalış.
- Bağımlılık kurma; standart kütüphane dışına çıkma.
- Bir şey belirsizse: `FAZ0_BULGULAR.md` → "Faz 1 için engel/risk" altına yaz,
  uydurma.
```
