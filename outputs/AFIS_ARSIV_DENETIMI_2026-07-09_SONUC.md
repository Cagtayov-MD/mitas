# Afiş Arşiv Denetimi — SONUÇ (2026-07-09)

## Kapsam
`E:\MITAS\Mitas Output\export\ONAYLI` klasöründeki **51 PDF** (233+ değil — gerçek sayı bu),
her birinin gömülü afiş görseli (varsa) çıkarılıp gerçek başlıkla birlikte yerel `qwen3-vl:30b`
modeline (Ollama) "bu afiş bu filme mi ait" diye soruldu (`outputs/afis_arsiv_denetimi.py`).
Otomatik tarama **16/51 filmi** "şüpheli" işaretledi.

## Elle doğrulama (16/16 — hepsi tek tek afiş görseli açılıp gözle kontrol edildi)

**SONUÇ: REKABET/Challengers sınıfı ("tamamen alakasız film") bir vaka BULUNAMADI.**
16 işaretlemenin neredeyse tamamı otomatik-tarama aracının kendi sınırlarından kaynaklı
YANLIŞ-POZİTİF:

| Film | Afişte yazan | Gerçek durum |
|---|---|---|
| İKİ KOCALI KADIN | DOUCEMENT LES BASSES | Doğru — Fransızca orijinal ad (Alain Delon, Jacques Deray) |
| KURUNTULAR | INGANNI | Doğru — İtalyanca orijinal ad (anlamca "Kuruntular/Aldanışlar") |
| SEVİMLİ KÖPEK-... | AIR BUD | Doğru — serinin bilinen İngilizce adı |
| 6. GÜN | THE 6TH DAY | Doğru — Schwarzenegger posteri, tam eşleşme |
| SHERLOCK HOLMES'İN DOĞUŞU | MURDER ROOMS | Doğru — gerçek İngilizce başlık |
| CİNAYET YERİ | MURDER SCENE | Doğru — kendi araç-çıkarımım yanlış "MURDER SEEN" yakalamıştı |
| İSYAN | (üstte oyuncu adları) | Doğru — "İSYAN" posterin kendisinde dev harflerle yazılı, VL yanlış okumuş |
| AYAK TAKIMI | "Rill Rall" (VL yanlış okudu) | Doğru — stilize yazıda "Riff Raff" |
| JOE SHARP | TENNESSEE Stallion | Doğru — filmin bilinen alt-başlığı |
| KIRKSEKİZ SAAT | THE 48-HOUR MILE | Doğru — birebir çeviri eşleşmesi |
| SCHIMANSKI HASRET | SCHIMANSKI | Doğru — franchise-adı posteri (yaygın stil) |
| SCHIMANSKI-CEHENNEM ÇOCUKLARI | SCHIMANSKI (aynı görsel) | Doğru film ama **iki ayrı Schimanski bölümü AYNI jenerik afişi paylaşıyor** — acil değil, küçük veri-hijyeni notu |
| RENE | RENÉ | Doğru — aksan farkı dışında birebir |
| PARDAYYAN | (dönem-kostümlü genç adam, metinsiz) | Muhtemelen doğru (Pardaillan temalı), ama gerçek "afiş" değil, stüdyo fotoğrafı gibi — düşük öncelik |

## Açık kalan 2 nokta (KESIN yanlış-afiş DEĞİL, ama insan gözüyle 1 dakikalık bakış hak ediyor)
1. **DÜŞLER ÜLKESİ (1998-1000)** — PDF'teki "afiş" alanında gerçekte bir **video-oynatıcı ekran-görüntüsü** var ("SCREEN: (play)" yazısı, siyah bar'lı) — gerçek bir afiş DEĞİL. Bu, REKABET bug'ından TAMAMEN FARKLI bir sınıf (yanlış-film değil, "afiş yerine ekran-görüntüsü" — `poster_ok()`'un zaten önlemeye çalıştığı ama bu vakada kaçırdığı türden bir durum). Silinmedi/dokunulmadı.
2. **SON TANIK (1999-0483)** — afişte "CARACARA" yazıyor; bu başlığın "Son Tanık" ile ilişkisini bağımsız doğrulayamadım (RAPOR.md'ye göre bu film daha önce gözle-frame-teyitli olarak zaten promote edilmiş — güçlü ama kesin olmayan bir işaret). Silinmedi/dokunulmadı.

## Sonuç
Şu anki 51 ONAYLI filmde REKABET/VİDEO OYUNU tipi ("tamamen başka bir yapımın afişi") bir
vaka bulunamadı — endişe edilen sistemik yayılma bu arşiv kesitinde DOĞRULANMADI. Otomatik
VL-taraması, orijinal/uluslararası başlık bilgisi olmadan çalıştığında yüksek yanlış-pozitif
oranı üretiyor (aracın kendi kısıtı, MITAS'ın değil) — ileride tekrar kullanılacaksa
`_orig_raw`/XML orijinal-ad alanının PDF'ten daha güvenilir çekilmesi (ya da doğrudan hub
klasöründeki `_DURUM.json`'dan okunması) yanlış-pozitifi büyük ölçüde azaltır.
