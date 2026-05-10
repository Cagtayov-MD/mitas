# MITAS Profile Routing Kaba Kararlar v1

## Amaç

Bu doküman, MITAS için profil bazlı kaba routing kararlarını tek yerde toplar.
Detaylı model, eşik, benchmark ve implementation kararları şimdilik bu dokümanın dışında tutulur.

## Profil Listesi

MITAS ilk aşamada 6 içerik profili kullanacaktır:

- film_dizi
- haber
- studio_program
- muzik_eglence
- spor_karsilasma
- belgesel

Demo profili kaldırılmıştır.
Demo ihtiyacı `ASR > streaming_transcription > tracking_overlay` altında yaşar.

## Genel Mimari Karar

Tek ana pipeline engine kullanılacaktır.
Profiller ayrı pipeline kodu değildir.

Profil, ana pipeline engine üzerinde çalışan bir config katmanıdır.
Bu config katmanı hangi modüllerin varsayılan açık/kapalı geleceğini ve açık olan modüllerin nasıl çalışacağını belirler.

Kural:

```text
profile_defaults + runtime_overrides = resolved_config
```

Runtime override global modül davranışını kapatmaz.
Kullanıcının aç/kapa ayarı, seçilen profilin kendi modül davranışını o job için değiştirir.

Örnek:

- `studio_program + visual_tag kapalı` = studio profilindeki hafif/adaptif visual tag kapalı.
- `belgesel + visual_tag kapalı` = belgesel profilindeki daha yoğun/adaptif visual tag kapalı.

UI’da aynı düğme gibi görünebilir; fakat kapatılan çalışma stratejisi profile göre farklıdır.

## film_dizi Kaba Kararları

- ASR sabit açık
- OCR / jenerik okuma sabit açık
- Dil algılama sabit açık
- Transcript algılanan dilde çıkar
- Özet önce orijinal dilde, sonra Türkçe çıktı
- Giriş/çıkış jeneriği okunur
- FilmCreditsParser mantığı sonra detaylandırılır
- Face ID kapalı

## haber Kaba Kararları

- ASR açık
- OCR/KJ açık
- Speaker diarization açık olabilir
- KJ, alt bant, isim, kurum ve görev metinleri önemlidir
- Görsel analiz sınırlı/adaptif olabilir
- Song performance kapalı
- Spor özel mantığı yalnızca spor içeriği tespit edilirse profile/override ile ele alınır

## studio_program Kaba Kararları

- Temiz/stabil stüdyo konuşması varsayılır
- Tam transcript hedeflenir
- Speaker diarization açık
- Kim konuştu bilgisi önemlidir
- OCR/KJ ile konuk, sunucu ve röportaj kişisi yakalanır
- Araya klip girerse hafif/adaptif visual tag çalışabilir
- Song performance kapalı
- Kapanış jeneriği okunur

## muzik_eglence Kaba Kararları

- Kaotik akış varsayılır
- Visual tag varsayılan kapalı
- OCR/KJ açık
- ASR açık; özellikle spiker anonsları önemlidir
- Şarkı başlangıç/bitiş önemli
- Hangi şarkı / kim söyledi önemli
- Face/person match yalnızca destek sinyali olarak kullanılır
- song_performance ana çıktıdır

## spor_karsilasma Kaba Kararları

- `sport_type`: futbol / other
- Futbol için takım, skor, lig, hafta/tur/final, gol atanlar, kırmızı kart takip edilir
- Futbol için sese müdahale/noise-aware ASR önemlidir
- `other`: basketbol, voleybol ve diğer sporlar
- Diğer sporlar için takım, skor, lig, hafta/tur tutulur
- Diğer sporlar için oyuncu detayı varsayılan hedef değildir
- Yellow card kapalı

## belgesel Kaba Kararları

- Geniş analiz profili
- ASR açık
- OCR açık
- Visual tag açık
- Scene detection açık
- Adaptive visual sampling açık
- Speaker diarization açık
- Kapanış jeneriği açık
- Audio activity açık
- Face detection koşullu olabilir
- Otomatik kimlik iddiası yok
- Spor ve song_performance kapalı

## ASR Alt Mod Kararları

- Demo ayrı profil değildir
- STT ayrı ana profil değildir; ASR'nin canlı kullanım biçimidir
- `file_transcription`: kayıtlı dosyadan stabil transcript; görsel işleme yok
- `streaming_transcription`: anlık konuşmayı ekrana verir; partial önce gelir, final düzeltme sonra gelir
- `vad`: konuşma aktivitesi/sessizlik ayrımı
- `diarization`: konuşmacı ayrımı
- `alignment`: timestamp hizalama
- `tracking_overlay`: `streaming_transcription` içinde checkbox ile açılır
- Tracking açılınca küçük pencere çıkar: “Kimi takip edeyim abicim?”
- Kullanıcı ekrandaki kişiyi seçer
- Sistem sadece seçilen kişiyi takip eder
- Tik kapanınca tracking kapanır
- DB’ye yazmaz
- Enrollment yapmaz
- Identity claim yapmaz

## Şimdilik Dışarıda Tutulanlar

- Model seçimi
- Eşikler
- Benchmark metrikleri
- Exact frame sampling değerleri
- UI tasarımı
- Profile YAML dosyaları
- Pipeline implementation

## Son Karar

MITAS tek ana pipeline engine ve profil config yaklaşımıyla ilerleyecektir.
Profil defaults ve runtime overrides birleşerek job bazlı resolved_config üretir.
Demo profili yoktur; demo/showcase ihtiyacı `ASR > streaming_transcription > tracking_overlay` olarak ele alınır.
