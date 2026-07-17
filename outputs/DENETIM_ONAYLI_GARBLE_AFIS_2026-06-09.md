# ONAYLI TARAMA — ÖZEL-İSİM GARBLE + AFİŞ (2026-06-09, 83 PDF)
**Yöntem:** 83 paralel agent, her ONAYLI PDF açılıp SADECE 2 boyutta tarandı: özel-isim garble (özet/cast/yapımcı/yönetmen) + afiş doğruluğu (yanlış-film/eksik). Web-teyitli.
**Sonuç:** 62 temiz · **21 sorunlu** (4 kritik-afiş + 5 afiş-eksik + 12 özet-isim-garble). Bu eksen diğer Opus'un cast/crew düzeltmesinin DIŞINDA (ek değer).

## 🔴 KRİTİK — YANLIŞ AFİŞ (aynı-başlık farklı-versiyon tuzağı) — 4
| Film | TRT | Sorun |
|---|---|---|
| **KIZGIN DAMDAKİ KEDİ** | 1976-0200 | Afiş 1976 "Laurence Olivier Presents" TV uyarlaması; künye 1958 MGM (Elizabeth Taylor/Paul Newman/yön. Richard Brooks). Afişte LAURENCE OLIVIER, kadroda HİÇ yok. |
| **GİZLİ TEHLİKE** | 1949-0046 | Afiş 1949 film-noir "Cover Up" (Bendix/O'Keefe); künye 1991 "Cover-Up" (Dolph Lundgren/yön. Manny Coto). TRT-id 1949 öneki yanıltmış. |
| **PALYAÇO OYUNU** | 1973-0200 | Afiş 1961 Avustralya "Harlequinade" yapımı (John Alden); künye 1973 Anglia TV (Denholm Elliott/yön. Alvin Rakoff). |
| **SİGARA İÇİNCE** | 1993-0508 | Afiş modern bir "Smoking" filmi (sokak/hoodie fotoğraf); künye 1993 Alain Resnais "Smoking/No Smoking" (Azéma/Arditi). |

→ **Kök neden:** poster_fetch aynı İngilizce başlıkta yıl/film ayrıştıramıyor; yanlış dönem filmini çekiyor. Fix: fetch'te yıl + imdb_id zorunlu disambiguation.

## ⬜ AFİŞ EKSİK — 5
HAYALETİ YAKALIYORUZ (1988-1111) · LADY WINDERMERE'İN YELPAZESİ (1988-1568) · HEWITT FARKLI BİRİ (1990-0424) · DOLUNAY (1991-0424) · YILLARIN ARDINDAN (2013-9109, Kore filmi — afiş bulunamamış olabilir)

## 🟡 ÖZET İSİM GARBLE — 12 (küçük; karakter/özel ad OCR/ASR fonetik bozulması, olay doğru)
| Film | Garble → Doğrusu |
|---|---|
| V FOR VENDETTA (orta) | SADLER→Sutler, EVİ→Evey, "ST. EVİ KOLU" bozuk cümle |
| TUZAK | STEFAN NEIL→Stephen Neale, BAYAN BLAINE→Mrs Bellane, LAMBRIDGE→Lembridge, KOST→Cost |
| BATAAN | BİLDEYN→Bill Dane |
| BİTMEYEN AŞK | REISER→Dreiser |
| YUMA KALESİ | MEMBRINO→Mimbreño |
| RIO BRAVO | DUIT→Dude |
| KAN VE SİLAH | KASKARO→Cascorro |
| UYANIŞ | HENNY→Anne |
| KAÇAK | JACK REMSI→Jack Ramsay |
| UZAYDAKİ SIR | POLİKROLİK OTİMAL→Polydichloric Euthimal |
| ENTRİKA | MERMAN→Merriman |
| PİNOKYO'NUN MACERALARI | LEMPİK→Lampwick |

## DESEN / KÖK NEDEN
- **Yanlış afiş (4):** aynı-başlık farklı-dönem; poster_fetch yıl/imdb disambiguation eksik. EN ÖNEMLİ (yanıltıcı, ONAYLI'da durmamalı).
- **Eksik afiş (5):** fetch başarısız/film obscure.
- **Özet garble (12):** transcript (ASR) + OCR'dan gelen karakter/özel ad fonetik bozulması → özet LLM'i sadık aktarıyor. Kozmetik (olay örgüsü doğru); cast/yönetmen/yapımcı temiz.

## NOT
Cast/yönetmen/yapımcı'nın DOĞRU-KİŞİ olması bu taramanın konusu değildi (onu diğer Opus + 27-ONAYLI denetimi kapsıyor). Bu tarama yalnız GARBLE (bozuk yazım) + AFİŞ. 62/83 her iki boyutta tertemiz.
