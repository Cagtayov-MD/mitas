# MITAS Tedial Session Broker Tasarımı v1

## Amaç

Tedial için kullanıcı adı/parola toplayan bir entegrasyon yazmak yerine, kullanıcının kendi Tedial oturumunu MITAS'a güvenli şekilde bağlamak.

Bu tasarımda MITAS:

- Tedial parolasını bilmez.
- Kullanıcının yetkilerini aşmaz.
- Arama, manifest ve player çağrılarını kullanıcının Tedial session'ı ile yapar.
- `cache_lowres` segmentlerini mümkünse cookie olmadan, byte-range destekli şekilde proxy eder.

## Karar

Faz 1 için önerilen yaklaşım: **kullanıcı kontrollü Tedial login + backend session broker + kullanıcı bazlı cookie jar**.

UI'da "Tedial'a Bağlan" butonu veya Tedial sekmesi olacak. Kullanıcı bu akışta Tedial login ekranına yönlenecek, girişini kendi yapacak, sonra MITAS backend bu kullanıcının Tedial session durumunu kullanarak proxy çağrılarını yürütecek.

## Neden Bu Yol

- Tedial login akışı HAR'da hâlâ doğrulanmadı; SSO/CAPTCHA olabilir.
- SSO/CAPTCHA varsa backend'in programatik login yapması kırılgan olur.
- Kullanıcı kendi oturumunu kullandığında yetki modeli Tedial ile aynı kalır.
- MITAS hiçbir zaman kullanıcı parolasını saklamak zorunda kalmaz.
- Kurumsal kullanımda audit ve sorumluluk daha temiz olur: herkes kendi Tedial hesabıyla işlem yapar.

## Temel Akış

1. Kullanıcı MITAS UI'da Tedial sekmesini açar.
2. UI, Tedial bağlantı durumunu backend'den sorar.
3. Oturum yoksa "Tedial'a Bağlan" eylemi gösterilir.
4. Kullanıcı bağlantı eylemini başlatır.
5. MITAS, Tedial login ekranını ayrı pencere/WebView/popup içinde açar.
6. Kullanıcı Tedial'a kendi hesabıyla giriş yapar.
7. Login başarılı olunca session cookie'leri backend tarafındaki kullanıcıya ait cookie jar'a alınır.
8. UI "Bağlandı" durumuna geçer.
9. Arama ve player istekleri backend proxy üzerinden, o kullanıcıya ait Tedial session ile yapılır.
10. Session süresi dolarsa UI kullanıcıya tekrar bağlanma ister.

## Önerilen UI Davranışı

Tedial sekmesinde üç durum yeterli:

- `Bağlı değil`: "Tedial'a Bağlan" butonu.
- `Bağlı`: kullanıcı adı bilinirse gösterilir, "Bağlantıyı Kes" ve "Beni Hatırla" kontrolü.
- `Süresi doldu`: "Yeniden Bağlan" butonu.

"Beni Hatırla" seçeneği:

- Kapalıysa session sadece çalışma süresince tutulur.
- Açıksa cookie jar şifreli şekilde saklanır.
- Session geçersizleşirse sessizce hata vermek yerine kullanıcıya yeniden login akışı açılır.

## Teknik Seçenekler

### Seçenek A - Backend Kontrollü WebView

MITAS masaüstü uygulaması veya yerel servis, Tedial login penceresini kontrol eder ve cookie jar'a doğrudan erişir.

Artıları:

- `HttpOnly` cookie sorunu aşılır, çünkü cookie tarayıcı motorunun cookie store'undan alınır.
- Backend proxy ile aynı süreç cookie jar'ı yönetebilir.
- Kullanıcı parolası görülmez.

Eksileri:

- WebView/embedded browser entegrasyonu gerekir.
- Tedial CSP/X-Frame-Options nedeniyle iframe yerine ayrı pencere gerekebilir.

### Seçenek B - Sistem Tarayıcısı + Yerel Callback

Tedial sistem tarayıcısında açılır. Başarılı girişten sonra kullanıcı MITAS'a döner.

Artıları:

- Kullanıcı alıştığı tarayıcı ile login olur.
- SSO daha doğal çalışabilir.

Eksileri:

- Browser cookie'lerini backend'e güvenli şekilde aktarmak zordur.
- `HttpOnly` cookie'ler JavaScript ile okunamaz.
- Ek browser extension veya local proxy gerekebilir.

### Seçenek C - Local Reverse Proxy ile Login

MITAS yerelde `http://127.0.0.1:<port>/tedial/...` gibi bir proxy açar. Kullanıcı Tedial'a bu proxy üzerinden girer, proxy `Set-Cookie` header'larını kendi jar'ına kaydeder.

Artıları:

- Backend cookie jar doğal şekilde oluşur.
- Programatik login gerekmez.
- `HttpOnly` cookie backend tarafından görülebilir, çünkü response header proxy üzerinden geçer.

Eksileri:

- Tedial origin, CORS, absolute URL, redirect ve mixed path rewrite işleri dikkat ister.
- Güvenlik sınırı çok net çizilmeli; sadece Tedial host'larına proxy yapılmalı.

## Önerilen Faz 1 Yolu

İlk uygulanabilir tasarım için **Seçenek C** en uygun aday:

1. MITAS backend sadece Tedial host'larına izin veren local login proxy başlatır.
2. UI "Tedial'a Bağlan" dediğinde popup şu URL'yi açar:

   `http://127.0.0.1:<mitas-port>/tedial/login`

3. Backend bu isteği Tedial giriş sayfasına proxy eder.
4. Proxy, Tedial'dan dönen `Set-Cookie` değerlerini kullanıcıya ait cookie jar'a kaydeder.
5. Kullanıcı login olunca backend `loadDefaultSearch.html` veya benzeri session gerektiren bir endpoint ile health check yapar.
6. Health check başarılıysa popup kapanır veya kullanıcıya "Bağlandı" ekranı gösterilir.

Bu yol çalışmazsa WebView tabanlı Seçenek A ikinci aday olmalı.

## Backend Bileşenleri

### TedialSessionBroker

Sorumluluklar:

- Kullanıcı bazlı Tedial session durumunu tutmak.
- Cookie jar oluşturmak, güncellemek ve silmek.
- "Beni Hatırla" açıksa cookie jar'ı şifreli saklamak.
- Session health check yapmak.

Önerilen durumlar:

- `disconnected`
- `connecting`
- `connected`
- `expired`
- `error`

### TedialProxyClient

Sorumluluklar:

- `doNewSearch.html` isteğini kullanıcının cookie jar'ı ile göndermek.
- Arama HTML'ini parse etmek.
- `refreshPlaybackToken.html` çağrısını yönetmek.
- `file.mpd` manifestini almak ve gerekirse parse etmek.
- Tedial session hatalarını MITAS hata modeline çevirmek.

### TedialMediaProxy

Sorumluluklar:

- `cache_lowres` URL'lerini byte-range destekli proxy etmek.
- `Range`, `Content-Range`, `Accept-Ranges`, `Content-Length`, `Content-Type` header'larını korumak.
- Sadece izinli Tedial media host/path'lerine çıkmak.

Faz 0 bulgusu: test edilen `cache_lowres` URL'i cookie olmadan `200/206` döndü ve byte-range destekli.

## Önerilen MITAS API Taslağı

```text
GET  /api/tedial/session
POST /api/tedial/session/start
POST /api/tedial/session/forget
POST /api/tedial/session/remember

POST /api/tedial/search
GET  /api/tedial/assets/{asset_id}/manifest
GET  /api/tedial/assets/{asset_id}/playback-token
GET  /api/tedial/media?url=<encoded-cache-lowres-url>
```

`GET /api/tedial/session` örnek yanıt:

```json
{
  "status": "connected",
  "remember": false,
  "expires_at": null,
  "last_checked_at": "2026-05-16T00:00:00Z"
}
```

`POST /api/tedial/search` örnek gövde:

```json
{
  "searchField": "tr-*",
  "selectedRepositories": ["TRT1"],
  "selectedItemsPerPage": "100"
}
```

## Güvenlik Kuralları

- Tedial parola hiçbir yerde istenmez, saklanmaz, loglanmaz.
- Cookie değerleri loglara yazılmaz.
- Cookie jar kullanıcı bazlı ayrılır.
- "Beni Hatırla" verisi OS credential store veya proje içi şifreli vault ile saklanır.
- Tedial proxy sadece allowlist host'lara çıkar:
  - `evo.int.trt.net.tr:8885`
  - `evo.int.trt.net.tr:8181`
  - `evo.int.trt.net.tr:443`
- Proxy açık redirect veya genel amaçlı forwarder gibi davranmaz.
- `cache_lowres` proxy'si sadece `https://evo.int.trt.net.tr/cache_lowres/` path'ini kabul eder.
- HAR, cookie ve token içeren ham debug çıktıları asla commit edilmez.

## Faz 0 Bulgularıyla Uyum

Faz 0 raporundaki doğrulanmış noktalar bu tasarımı destekliyor:

- `doNewSearch.html` JSON istek alıyor ve HTML sonuç dönüyor.
- Sonuçlar `ul#block-grid > li.block-section-box` içinde parse edilebilir.
- Asset id `assetIdIdHidden`, sequence id `sequenceIdHidden`, başlık `titleHidden` alanlarında.
- `.mpd` endpoint'i asset id path'iyle çalışıyor.
- `.mpd` öncesinde `refreshPlaybackToken.html` çağrısı var.
- `cache_lowres` cookie olmadan erişilebilir ve byte-range destekli.

Eksik kalan tek kritik parça login akışının kendisi. Bu tasarım programatik login'e bağımlı olmadığı için Faz 1'i bloke etmez; ama session broker implementasyonu için login proxy/WebView davranışı ayrıca smoke test edilmelidir.

## Kabul Kriterleri

- Kullanıcı Tedial parolasını MITAS'a girmeden bağlanabilir.
- MITAS UI bağlantı durumunu doğru gösterir.
- Kullanıcı "Bağlantıyı Kes" dediğinde cookie jar silinir.
- "Beni Hatırla" kapalıyken uygulama kapanınca session kalıcı saklanmaz.
- "Beni Hatırla" açıkken session şifreli saklanır.
- Session süresi dolduğunda search/player istekleri anlaşılır `expired` hatası döndürür.
- Arama sonuçları Tedial HTML'inden parse edilip MITAS modeline çevrilir.
- MPD ve low-res playback, kullanıcının session bağlamı ile çalışır.
- Media proxy `Range` isteklerinde `206` ve `Content-Range` davranışını korur.

## Uygulama Sırası

1. Session broker arayüzü ve durum modeli.
2. Local login proxy veya WebView proof of concept.
3. Cookie jar yakalama ve health check.
4. `doNewSearch` proxy + HTML parser.
5. Asset manifest/token akışı.
6. `cache_lowres` byte-range media proxy.
7. UI Tedial sekmesi: bağlan, durum, beni hatırla, bağlantıyı kes.
8. Hata durumları ve audit-safe loglama.
