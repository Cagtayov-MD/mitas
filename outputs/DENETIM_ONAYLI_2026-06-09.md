# ONAYLI DENETİMİ — 2026-06-09 (gece koşusu, 27 PDF)
**Yöntem:** 27 paralel agent, her ONAYLI PDF açılıp internet (IMDb/Wikipedia/TMDB) gerçek-zeminine karşı doğrulandı.
**Sonuç:** 19 TEMİZ · 8 SORUNLU (1 kritik + 3 orta + 4 küçük) · yanlış-film/yanlış-yönetmen YOK.

## 🔴 KRİTİK (1)
- **VANINA VANINI** (1961-0011): Yönetmen (Rossellini)/afiş/başlık DOĞRU; ama OYUNCULAR + YAPIMCI ağır bozuk: yapımcı Moris Ergas→cast'e; "DIEGO FABE STENDHAL" (Stendhal=romancı); "LMARTINE CAROLF"=Martine Carol bozulmuş; "LEONARDO SEVERİNİ" uydurma; senaristler (Monique Lange, Antonello Trombadori) cast'te; yapımcı alanı uydurma (Giovagnorio/Negri/Arthuys=besteci). Gerçek başrol Paolo Stoppa eksik.

## 🟠 ORTA (3)
- **GİZLİ TEHLİKE** (1949-0046): AFİŞ yanlış film. Metadata 1991 Dolph Lundgren "Cover-Up" (yön. Manny Coto) doğru; afiş 1949 aynı-isim film noir "Cover Up" (yön. Alfred E. Green). TRT-id 1949 öneki yanıltmış. IMDb tt0099312 (1991) vs tt0041263 (1949).
- **SİLAHŞÖRE DAVET** (1964-0038): cast garble "GEORCE STOAD ALRRDED" (George Segal+Alfred Ryder bozuk birleşim, ikisi zaten ayrıca doğru var) + "CLIFFORD DAVID MIKE KELLIN" (iki oyuncu yapışık). Yön/yapımcı/afiş doğru.
- **HERBIE COŞUYOR** (1974-0204): yapımcı garble "HENY GRAE" (doğrusu Bill Walsh). Yön/cast/afiş/başlık doğru.

## 🟡 KÜÇÜK (4)
- **SON VURGUN** (2004-9120): "MICHAEL PATRICK CUPO" = karakter(Michael)+oyuncu(Patrick Cupo) yapışık (anahtar sözcüklerde de). Charles Durning eksik.
- **V FOR VENDETTA** (2005-9138): özet garble — SADLER→Sutler, EVI→Evey, "ST. EVI KOLU ÇEKER" bozuk cümle. Olay doğru.
- **BATAAN** (1943-0001): özette "BILDEYN"→Bill Dane (ASR fonetik). Olay doğru.
- **ZOR ZAMANLAR** (1975-0186): özette GRETGRIND→Gradgrind, BANDERBY→Bounderby, HARDHOUSE→Harthouse, SISI→Sissy + yapımcı boş (Richard Langridge).

## ✅ TEMİZ (19)
YAZ KAMPI, LUNAPARKTAKİ PANİK, DERİNLİKLERDE (yön Gregg Champion/Alan Smithee doğru dolmuş — downstream çalıştı), EN BÜYÜK KORKU, BABAMIN KABUSU, TRUMP BAŞARININ ÖYKÜSÜ, EDISON, BÜYÜK FİNAL, AMİRAL, ASTERİKS, YILLARIN ARDINDAN, KARDEŞİM İÇİN DER'A, VAY ANAM VAY 3, TUZAK, SUNSET BULVARI, APAÇİ, YUMA KALESİ, YASAK GEZEGEN, BİTMEYEN AŞK.

## DESENLER (kök neden → fix)
1. Cast/yapımcı çok-kelimeli garble (VANINA/SİLAHŞÖRE/HERBIE) → KESİN KURAL P2 zaafı + garble-QC açığı → **film-özel-KB cross-check** (sabah fix).
2. crew→cast karışması (VANINA/SON VURGUN) → film-özel-KB cross-check.
3. Özet isim garble (V/BATAAN/ZOR ZAMANLAR/APAÇİ/BİTMEYEN AŞK küçük) → ASR/OCR artefaktı transcript→özet; ayrı iş (isim düzeltme).
4. Yanlış afiş (GİZLİ TEHLİKE) → afiş yıl/başlık ayrıştırma (TRT-id yılı ≠ film yılı; aynı-isim çakışması).

**Not:** 27/27'de yönetmen DOĞRU, hiç yanlış-film yok; sorunlar ağırlıkla cast-garble + özet-isim artefaktı. ONAYLI kalite ~%70 temiz.
