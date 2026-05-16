# Tedial Faz 0 — Bulgular

## 1. Login akışı
- Endpoint (method + URL): HAR'da görünmüyor. Yeni HAR'da `login=0`, `j_security_check=0`.
- İstek alanları (maskeli): HAR'da görünmüyor, ek yakalama gerek.
- SSO/CAPTCHA var mı: HAR'da login ekranı/isteği olmadığı için doğrulanamadı.
- Dönen Set-Cookie adları: HAR içinde `Set-Cookie` + `JSESSIONID` heuristiği 0 adet bulundu.
- Sonuç (otomasyon mümkün mü): Bu HAR ile karar verilemez. Sadece login ekranından önce başlatılmış ayrı bir login HAR'ı gerekir.

## 2. doNewSearch.html sözleşmesi
- İstek Content-Type + JSON alan ağacı: `POST https://evo.int.trt.net.tr:8885/iTClient/tarsys/search/ajax/doNewSearch.html`; Content-Type `application/json`; alanlar: `searchType`, `selectedRepositories[]`, `multiRepository`, `searchField`, `placeHolder`, `selectedPresentationTemplate`, `tqlExpression`, `selectedOrderField`, `ascendingSort`, `searchFilterLineList[]`, `selectedItemsPerPage`, `searchScope`.
- Yanıt Content-Type: `text/html;charset=UTF-8`; yanıt HTML uzunluğu `578572`.
- Asset satırının HTML seçicisi (class/id): Sonuçlar `div#block-result-container > ul#block-grid` altında `li.block-section-box.dragSearchElement.not-draggable-result` öğeleri olarak geliyor; örnek satır `li#box-1`, içinde `div#box-4A66886E-C51A-01EF-8A7B-001000200100`.
- Asset ID / başlık / süre / keyframe URL nerede gömülü: Başlık `input#titleHidden[name=titleHidden]`; sequence id `input#sequenceIdHidden`; asset id `input#assetIdIdHidden` (`4A5CC964-C51A-01EF-8A74-001000100100`); süre işareti `input[name=tcIn]`, `input[name=tcOut]` ve MPD `Period duration` alanında; keyframe `img.keyframeImg[src*="/MamService/KeyframeService/"]` ve ayrıca `input[name=imageTcIn]` / `input[name=imageTcOut]`.
- Parser stratejisi (hangi seçiciler): `ul#block-grid > li.block-section-box` üzerinden satırları gez; her satırda `div[id^="box-"]`, `input#titleHidden`, `input#sequenceIdHidden`, `input#assetIdIdHidden`, `input[name=tcOut]`, `img.keyframeImg` ve `input[name^=imageTc]` değerlerini oku.

## 3. refreshPlaybackToken.html
- İstek (method/alanlar): `POST https://evo.int.trt.net.tr:8885/iTClient/player/ajax/refreshPlaybackToken.html`; Content-Type `application/x-www-form-urlencoded; charset=UTF-8`; form alanı `token=<MASKED>`.
- Yanıt gövdesi (token alanları): JSON; `message`, `error`, `sessionError`, `warning`, `data.token=<MASKED>`, `data.generationDate`, `data.validityInterval`.
- Token; file.mpd/cache_lowres ile ilişkisi: HAR'da `refreshPlaybackToken` isteği `.mpd` isteğinden hemen önce geliyor. `.mpd` yanıtı MPD XML'i içeriyor ve `BaseURL` olarak `https://evo.int.trt.net.tr/cache_lowres/...mp4` segmentlerini veriyor. Segment URL'lerinde query token/signature görünmüyor.
- Ömür/yenileme ihtiyacı: Yanıtta `validityInterval: 30`; örnek `generationDate: 1778892830975`. Playback öncesi/akış sırasında yenileme gerekli görünüyor.

## 4. file.mpd elde etme
- .mpd'yi döndüren/öncesindeki endpoint: `.mpd` endpoint'i `GET https://evo.int.trt.net.tr:8181/MamService/PlaylistService/mpd/B10B9B06-5171-01F1-8C5E-0010007FFF00/4A5CC964-C51A-01EF-8A74-001000100100/file.mpd`; hemen önce `POST /iTClient/player/ajax/refreshPlaybackToken.html` var.
- Asset ID → manifest eşlemesi: `doNewSearch` HTML'indeki `input#assetIdIdHidden` değeri `4A5CC964-C51A-01EF-8A74-001000100100`; aynı değer MPD URL path'inde kullanılıyor. İlk path segmenti repository/tenant id gibi görünen `B10B9B06-5171-01F1-8C5E-0010007FFF00`.

## 5. cache_lowres auth
- Cookie'siz status (testler 1-2): Test 1 `GET` cookie yok/Range yok → `200`; Test 2 `GET` cookie yok/`Range: bytes=0-1023` → `206`.
- Cookie'li status (test 3 / atlandı): `COOKIE` ortam değişkeni boş olduğu için atlandı.
- Byte-range desteği (Content-Range): Destekli. Test 2 `Content-Range: bytes 0-1023/10776874`, `Accept-Ranges: bytes`, `Content-Length: 1024` döndürdü.
- Sonuç (proxy'de cookie passthrough gerekli mi): Test edilen `cache_lowres` URL'i cookie olmadan erişilebilir görünüyor; segment proxy için byte-range destekli. Search/player/manifest endpointleri ise Tedial oturumu bağlamında çalışıyor kabul edilmeli.

## Faz 1 için engel/risk
- Login akışı hâlâ yakalanmadı: endpoint, request alanları, SSO/CAPTCHA ve login cookie davranışı için ayrı yakalama gerekiyor.
- `doNewSearch` HTML'inde aynı `id` değerleri (`titleHidden`, `assetIdIdHidden` vb.) her sonuç satırında tekrar ediyor olabilir; parser satır kapsamı içinde arama yapmalı, global `id` seçiciye güvenmemeli.
- `.mpd` yanıtı header'da `application/json;charset=utf-8` görünse de gövde XML MPD; parser Content-Type yerine gövde/XML yapısını dikkate almalı.
