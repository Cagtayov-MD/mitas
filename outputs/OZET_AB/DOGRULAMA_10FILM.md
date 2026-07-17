# 10 Film Özet Doğrulama — Transkripte Karşı (gemma4:26b, sade promt)

Her özet, kendi ASR transkriptine karşı bağımsız bir ajanla denetlendi (kaynak = transkript, dış film bilgisi değil). Tüm hükümler "yüksek güven".

## Hüküm tablosu

| # | Film | Hüküm | En ağır kusur |
|---|------|-------|---------------|
| 1 | X-Men Başlangıç Wolverine | 🟡 KISMEN | Kayla ilişki hatası + Kayla'nın sahte ölüm/ihanet dönümü ATLANDI |
| 2 | Alita | 🟡 KISMEN | **Final yanlış** (Hugo'yu indiriyor, "üst şehre tırmanıyor" değil) + motorball tuzağı & Vector yok |
| 3 | Flashdance | 🟡 KISMEN | Nick rolü TERS (iten↔engelleyen) + torpil/iltimas dönümü atlandı |
| 4 | Cemile | 🔴 HATALI | Ressam/şehre giden Cemile DEĞİL anlatıcı Seyit; Cemile-Daniyar BİRLİKTE kaçar (yalnız kalmaz) |
| 5 | Tarzan Efsanesi | 🟡 KISMEN | "Jane" adı kaynakta yok (Lady Clayton); George'un "belgeleri" ilişki çarpıtması |
| 6 | Polis Akademisi 6 | 🟡 KISMEN | Köstebek yanlış (asıl köstebek Amir Harris hiç anılmıyor; "Hurst" çağrışımı yanlış) |
| 7 | Suçlu Kim | 🟡 KISMEN | Sahneye çıkan/oyuncu Max değil HENRY; final belirsizi "söz/yalnız kalır" diye kesinleştirmiş |
| 8 | Taşıyıcı | 🟡 KISMEN | Taşıyıcı David değil JOSEPH; "kaza" aslında devlet insan-deneyi (en büyük dönüm atlandı) |
| 9 | Sundown'da Karar Günü | 🟡 KISMEN | **"Tate öldürülür" YANLIŞ** — doktor engelliyor, Tate yaşıyor/kasabayı terk ediyor |
| 10 | Misafir | 🔴 HATALI | Arapça diyalogdan çıkarılmamış; ilişkiler ters (İstanbul'a giden Meryem), klişeyle doldurulmuş |

**Skor: 0/10 tam doğru · 8/10 kısmen · 2/10 hatalı.**

## Sistematik kalıplar (kök neden)

**A) ATLANAN KİLİT DÖNÜM — neredeyse her filmde.**
X-Men (Kayla ihaneti+rehin kardeş+Deadpool), Alita (motorball ölüm-tuzağı+Vector), Flashdance (torpil daveti), Tarzan (Şef Mubonga oğul-intikamı), Suçlu Kim (içerideki adam Frank), Taşıyıcı (devlet insan-deneyi), Sundown (Mary'nin intiharı+kasaba ayaklanması). Model olay örgüsünün ekseni olan dönümleri sık atlıyor.
→ **Bu, "daha çok sadeleştir" yönüyle DOĞRUDAN ÇELİŞİYOR.** Sorun fazlalık değil, kilit-dönüm yakalama. Daha agresif sadeleştirme bunu kötüleştirir.

**B) ROL/YÖN TERSİNE ÇEVİRME — "kim ne yaptı" karışıyor.**
Flashdance (Nick iten↔engelleyen), Taşıyıcı (David↔Joseph taşıyıcı), Misafir (Meryem↔Lina), Suçlu Kim (Max↔Henry oyuncu), X-Men (Kayla kimin sevgilisi). Promttaki "belirsiz zamir / kim kimi" kuralı yetmiyor.

**C) FİNAL UYDURMA/ÇARPITMA — spoiler baskısının ters etkisi.**
Alita (yanlış final), Sundown (ölmeyen Tate "öldürülür"), Suçlu Kim (belirsizi kesinleştirme), Cemile/Misafir (yanlış kişi/yön). Promtun "FİNAL somut yaz, belirsiz YASAK" baskısı, kaynakta final net DEĞİLSE modeli UYDURMAYA itiyor.

**D) YABANCI DİL.** Misafir Arapça → model içerik çıkaramayıp dış klişeyle doldurdu (LID/ASR kök, özet-dışı ama özeti çürütüyor).

**E) İSİMLER genelde DOĞRU.** Çoğu filmde kişi adları tutuyor; hata ilişkilerde, dönümlerde ve finalde.

## Stratejik çıkarım
Senin "sade + sadece ana olay" yönün okunabilirlik için iyi, ama bu test gösteriyor ki asıl açık **doğruluk ve kilit-dönüm yakalama**. Öncelik sıralaması: (1) kilit dönüm garantisi, (2) rol/yön netliği, (3) final ancak kaynakta NETSE kesin yaz — net değilse uydurma. Sadeleştirme bunlardan sonra gelmeli.
