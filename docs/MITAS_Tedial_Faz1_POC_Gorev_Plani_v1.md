# MITAS Tedial Faz 1 POC Görev Planı v1

## Amaç

Faz 0 bulgularını kullanarak Tedial entegrasyonunu güvenli bir POC seviyesine taşımak:

- Kullanıcı Tedial parolasını MITAS'a vermeden oturum bağlayabilsin.
- Backend kullanıcıya ait Tedial session/cookie bilgisini yönetebilsin.
- Search, manifest ve low-res media istekleri güvenli allowlist kurallarıyla planlanabilsin.

## Hazır Olanlar

- `FAZ0_BULGULAR.md`: search HTML, asset alanları, MPD endpoint'i, token refresh ve `cache_lowres` bulguları.
- `docs/MITAS_Tedial_Session_Broker_Tasarimi_v1.md`: kullanıcı kontrollü login + session broker tasarım kararı.
- `core/api/tedial/config.py`: Tedial origin/path konfigürasyonu ve URL allowlist kontrolleri.
- `core/api/tedial/session.py`: kullanıcı bazlı session broker ve maskeli cookie jar.
- `core/api/tedial/proxy.py`: search/token/manifest/media istek planlayıcıları ve MPD BaseURL rewrite helper'ı.
- `core/api/tedial/parser.py`: `doNewSearch.html` HTML sonuç parser iskeleti.
- `core/api/tedial/router.py`: FastAPI router adapter; session/search/token/manifest/media endpoint taslağı.
- `core/api/tedial/router.py` içinde `/api/tedial/login/...`: local reverse login proxy POC; Tedial `Set-Cookie` header'larını broker'a aktarır ve iTClient HTML/redirect referanslarını local proxy altında tutar.
- `core/api/tedial/app.py`: standalone POC FastAPI app factory.
- `scripts/tedial_poc_smoke.py`: canlı Tedial'a dokunmadan broker/parser/proxy plan smoke komutu.
- `tests/test_tedial_session_broker.py`, `tests/test_tedial_parser.py`: POC omurgası için hızlı testler.

## Faz 1 POC Kapsamı

### 1. Login Bağlama POC

Amaç: MITAS backend'in kullanıcı login akışı sırasında Tedial `Set-Cookie` header'larını yakalayabildiğini göstermek.

İlk uygulanan seçenek: local reverse login proxy.

Akış:

1. `POST /api/tedial/session/start`
2. Yanıttaki `login_url` açılır: `/api/tedial/login/`
3. Kullanıcı Tedial login ekranında kendi hesabıyla giriş yapar.
4. Proxy upstream `Set-Cookie` header'larını kullanıcıya ait broker session'a yazar.
5. `GET /api/tedial/session/health` ile session doğrulanır.

Olmazsa sonraki seçenek: WebView kontrollü login.

Kabul kriteri:

- Kullanıcı login sonrası `TedialSessionBroker.attach_set_cookie_headers()` veya eşdeğeriyle `connected` durumuna geçer.
- Cookie değerleri loglarda görünmez.
- `GET /api/tedial/session` benzeri endpoint cookie adlarını döner, değerleri dönmez.

### 2. Session Health Check

Amaç: Bağlanan cookie jar ile session geçerli mi anlaşılabilsin.

Önerilen upstream:

- `GET https://evo.int.trt.net.tr:8885/iTClient/tarsys/search/loadDefaultSearch.html`

Kabul kriteri:

- 200 + Tedial uygulama HTML'i gelirse `connected`.
- 401/403/302 login veya login formu gelirse `expired`.
- Kullanıcıya yeniden bağlanma sinyali verilir.

### 3. Search Proxy + Parser

Amaç: MITAS search formundan Tedial `doNewSearch.html` çağrısı yapılabilsin ve HTML sonuçları modele dönsün.

Faz 0 sözleşmesi:

- Endpoint: `POST /iTClient/tarsys/search/ajax/doNewSearch.html`
- Content-Type: `application/json`
- Önemli alanlar: `searchType`, `selectedRepositories`, `searchField`, `selectedItemsPerPage`, `searchScope`
- Sonuç satırı: `ul#block-grid > li.block-section-box`
- Asset alanları: `titleHidden`, `sequenceIdHidden`, `assetIdIdHidden`, `tcIn`, `tcOut`, `img.keyframeImg`

Kabul kriteri:

- En az 1 gerçek aramada asset listesi döner.
- Parser global duplicate `id` değerlerine güvenmez, her satır içinde arar.
- Asset id, sequence id, başlık, süre ve keyframe URL parse edilir.

### 4. Manifest + Token Akışı

Amaç: Asset id'den MPD alınabilsin.

Faz 0 sözleşmesi:

- Önce `POST /iTClient/player/ajax/refreshPlaybackToken.html`
- Sonra `GET /MamService/PlaylistService/mpd/{repository_id}/{asset_id}/file.mpd`
- MPD gövdesi XML, header bazen `application/json;charset=utf-8`

Kabul kriteri:

- Token değeri loglanmaz.
- MPD parse/rewrite Content-Type'a değil XML gövdeye göre davranır.
- MPD içindeki `BaseURL` değerleri MITAS media proxy rotasına çevrilir.

### 5. Media Proxy

Amaç: `cache_lowres` segmentleri byte-range destekli şekilde servis edilsin.

Faz 0 bulgusu:

- Cookie'siz `GET` 200.
- Cookie'siz `Range: bytes=0-1023` 206.
- `Content-Range` ve `Accept-Ranges` var.

Kabul kriteri:

- Sadece `https://evo.int.trt.net.tr/cache_lowres/...` kabul edilir.
- `Range` header'ı upstream'e taşınır.
- `206`, `Content-Range`, `Accept-Ranges`, `Content-Length`, `Content-Type` korunur.

## API Taslağı

```text
GET  /api/tedial/session
POST /api/tedial/session/start
POST /api/tedial/session/forget
POST /api/tedial/session/remember

POST /api/tedial/search
GET  /api/tedial/assets/{asset_id}/manifest
POST /api/tedial/playback-token/refresh
GET  /api/tedial/media?url=<encoded-cache-lowres-url>
```

## Güvenlik Notları

- Ham HAR commit edilmez.
- Cookie/token değerleri loglanmaz.
- Local proxy genel amaçlı HTTP proxy olmaz; sadece Tedial allowlist.
- Kullanıcı bazlı session izolasyonu korunur.
- "Beni Hatırla" kalıcı saklama gelmeden önce şifreli vault/OS credential store kararı alınır.

## Sıradaki Kodlama Adımı

1. Standalone POC app çalıştırılır:

   ```powershell
   E:\MITAS\venvs\asr\Scripts\python.exe -m uvicorn core.api.tedial.app:create_app --factory --host 127.0.0.1 --port 8765
   ```

2. Offline smoke komutu çalıştırılır:

   ```powershell
   python scripts\tedial_poc_smoke.py
   ```

3. Tarayıcıda `http://127.0.0.1:8765/docs` açılır.
4. `POST /api/tedial/session/start` denenir ve dönen `login_url` yeni sekmede açılır.
5. Tedial login tamamlandıktan sonra `GET /api/tedial/session/health` denenir.
6. Health `connected` olursa `POST /api/tedial/search` ile gerçek arama smoke testi yapılır.
