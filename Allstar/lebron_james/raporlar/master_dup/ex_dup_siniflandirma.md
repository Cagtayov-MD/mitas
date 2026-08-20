# Ex_Frame 427 — dup-135 Mekanizma Sınıflandırması (M7 teşhis)

> Bağlam: `docs/MITAS_Master_Dup_Kok_Sebep_Plani_v1.md` (M7 + M4b). Taban koşusu
> sağlık %62.8 (268/427); ana ihlal `dup_oran>0.10` olan **135 film**. Bu doküman
> o 135'in MEKANİZMA dağılımını görsel kanıtla çıkarır: hangi düzeltme kaç film
> kazandırır. SALT-ANALİZ — hiçbir üretim/harness dosyası değişmedi.

## Yöntem

- Örneklem: dup-sıralı ilk 20 + `[0.10,0.30)` bandından `random.seed(42)` ile
  rastgele 10 = **30 film** (tam liste, projeksiyon tabanı bu 30).
- Ek çapraz-kontrol (projeksiyona DAHIL DEĞİL, sadece doğrulama): `imha_imzasi`
  ihlali alan 10 filmden 6'sı (sampiyon, duello, maudie, ozgurluge-kacis,
  dogu-ekspresinde-cinayet, don-kisot) + `boy_anormal` alan 18 filmden 3'ü
  (ben-hur, solaris, + genel örüntü) ayrıca görsel incelendi.
- Her film için: `metrik.json`'daki `bloklar` listesinden en büyük+en dokulu 2-3
  tekrar çifti otomatik seçildi (`benzerlik×0.2 + alan×0.5 + doku×0.3` skoru),
  `reading_master.png`'den KAYNAK/TEKRAR kırpımı yan yana üretilip PNG'ye
  yazıldı (`data/master_ex/_siniflandirma/<slug>_witness.png`), sonra GÖZLE
  bakıldı. Otomatik seçim düz/dokusuz bant seçtiğinde (2 filmde oldu) tam
  master PNG'ye bakıldı.
- Manifest çapraz-okuma: `blocks[].skip`, `blocks[].rec_kanit.karar_yolu`,
  `strict_scroll_frac`, `blocks[].kind` (`static_page` vs `scroll_slit`) her
  filmde okunup F1/F1b/F1c'nin o filmde İZ bırakıp bırakmadığı ayrıca kaydedildi.

## Sınıf dağılımı — 30-örneklem

| Sınıf | Film sayısı | Oran |
|---|---|---|
| A — DONUK-TEKRAR-KORUNAN | 23 | %76.7 |
| B — OVERLAY-İMHA-DUP | 0 | %0 |
| C — MEŞRU-FARKLI-METİN | 6 | %20.0 |
| D — DİĞER/BELİRSİZ | 1 | %3.3 |

**A'nın iç ayrımı** (kanıt: `manifest.strict_scroll_frac` ve `blocks[].kind`):

| A alt-tipi | Film sayısı (23 içinde) | Oran | Mekanizma |
|---|---|---|---|
| A1 — statik kart tekrarı (`scroll_frac=0`, yalnız `static_page`) | 14 | %60.9 | Aynı sahne birden fazla "kart"a bölünmüş (grain dHash'i kandırıyor), F1/F1b/F1c hiç tetiklenmiyor ya da yetersiz kalıyor |
| A2 — kayan-yazı/slit tekrarı (`scroll_frac>0`, `scroll_slit` bloklar mevcut) | 9 | %39.1 | H1: slit dy tahmini/karışık-mod sınırı satırları birden fazla dilimde tekrar ettiriyor |

## Projeksiyon — 135 filme

| Sınıf | 30-örneklem oranı | 135'e projeksiyon (yaklaşık) |
|---|---|---|
| A (toplam) | %76.7 | **~104 film** |
| — A1 statik | %46.7 (14/30) | ~63 film |
| — A2 kayan-yazı | %30.0 (9/30) | ~41 film |
| B | %0 | **~0 film** (bkz. F1c bulgusu — üst güven sınırı birkaç film olabilir ama 34 filmlik birleşik örneklemde SIFIR gerçek vaka) |
| C | %20.0 | **~27 film** |
| D | %3.3 | **~4-5 film** |

## F1c-aktiflik bulgusu (kritik)

F1c (hayalet-kutu/rec tabanlı distant-dup skip) **ÖLÜ DEĞİL** — 427-filmlik
tüm Ex_Frame korpusunda 28 filmde toplam 74 kez `rec_kanit.karar_yolu="rec"`
izine rastlandı; global skip-tipi dağılımı: `no-text-band` 612, `consecutive-dup`
172, **`distant-dup-scene` 121**, `empty` 38, `no-text` 16, `dup` 8,
`distant-dup-text` 3, `distant-dup` 3, `distant-dup-rec` 3.

Ancak **135 dup>0.10 alt-kümesinde F1c'nin kapsamı ÇOK SINIRLI**:

| Ölçü (135 içinde) | Film sayısı | Oran |
|---|---|---|
| Hiç `skip` izi YOK (F1/F1b/F1c hiç tetiklenmedi) | 51 | %37.8 |
| En az 1 `skip` izi VAR | 84 | %62.2 |
| `consecutive-dup` (F1, orijinal ardışık dHash) tetiklendi | 38 | %28.1 |
| Herhangi `distant-dup*` (F1b/F1c uzak-eşleşme) tetiklendi | 21 | %15.6 |
| F1c'nin `rec_kanit` (OCR-rec/hayalet-kutu) değerlendirmesi ÇALIŞTI | 13 | %9.6 |

Somut kanıt (`don-juan-in-maceralari`): F1c run[0,58] içinde kart 1/2/3'ü
`es_blok_indeksi=0`'a (yani run'ın İLK kartına) karşı test edip `distant-dup-scene`
ile SKIP etti (`rec_kanit.karar_yolu="rec"`, `hayalet_kutular` skorları
0.0-0.55, hepsi eşik altı → hayalet). Ama AYNI filmin master'ında y=144-312 ile
y=1044-1212 arasında (muhtemelen farklı bir run/sahne) HÂLÂ birebir aynı çatı
manzarası tekrarlıyor (dup=0.6053) — yani F1c bir run içinde KISMEN çalışıyor
ama global/run-arası kapsamı yok; H2'nin öngördüğü "yeni kart ÖNCEKİ TÜM
kartlarla karşılaştırılır" davranışı henüz devrede değil.

`hizli-silah` (dup=0.9277, örneklemin en kötüsü) tersi ucu gösteriyor: run[9,23]
içindeki 4 kart (h=402/480/417/348, hepsi "Cast of Characters" listesinin
BİREBİR aynı metnini taşıyor) için `skip` alanı hiç yok (`no-text-band` dışında
iz yok) — yani F1'in ardışık dHash'i bile tetiklenmedi (F1b bulgu-1'in
öngördüğü "gren ham≤4'ü aşıyor, 0 aday" durumu burada da doğrulandı). F1c'nin
piksel ön-filtresi (`global_fark<0.06 VE max_band_fark<0.10`) muhtemelen bu
yüksek-kontrastlı/grenlı sayfalarda hiç açılmıyor, yani F1c'ye aday bile
gitmiyor.

**Sonuç:** F1c bir mekanizma olarak İZ BIRAKIYOR (ölü değil) ama 135'in
%90'ında (122 film) hiçbir aday üretip değerlendirmemiş; kapsam sorunu —
parametre ince ayarından çok, ön-filtre eşiği ve karşılaştırma kapsamı
(yalnız 1 referans karta karşı, run-içi/run-arası TÜM çiftlere değil) darlığı.

## Sınıf C ve D — bunlar "bug" değil, ölçüt sorunu

**C (6/30):** Tipik desen: dondurulmuş/az-değişen bir arkaplan görüntüsü
(yakın-plan oyuncu ikilisi, at-araba sahnesi, kar manzarası, Flintstones
mağara kapısı) üzerine SAYFA SAYFA FARKLI prodüksiyon kredisi/isim metni
biniyor. `dup_metrik.py` şerit-NCC'si arkaplanın baskın piksel kütlesini
yakalayıp "duplike" diyor, ama metin farklı → içerik kaybı YOK. Reçete kod
fix'i değil: health/dup tanımına "metin-farklılığı istisnası" (F1c'nin zaten
yaptığı OCR-rec eşitlik testinin dup_oran hesaplamasına da uygulanması, ya da
health kriterinde `dup_oran` payına yalnız metin-özdeş blokların sayılması).

**D (1/30, `tehlikeli-yolculuk-kentucky-guzeli`):** `kept_blocks=1` — masterda
GERÇEKTEN TEK sayfa var ("THE END / A Howco Production", H=480px), kompozisyonda
hiçbir tekrar yok. `dup_metrik.py` yine de dup_oran=0.1282 ölçtü çünkü görüntünün
düz/gradyanlı gökyüzü bandı kendi içinde başka bir düz banda NCC≥0.92 ile
eşleşti (metrik yanlış-pozitifi, doku_kapsami düşük bölgede). Reçete: composer
değil, `dup_metrik.py`'de tek-kept-block durumunda (ya da genel olarak) düşük
dokulu/düz-gradyan bantlar için ek bir güvenlik filtresi.

## Sınıf B — bu 135 popülasyonunda pratikte YOK

30-örneklemde 0/30 B çıktı. Ayrıca `imha_imzasi` ihlali alan 10 filmden 4'ü
zaten `dup_oran>0.10` (135) kümesiyle kesişiyor (duello, maudie,
ozgurluge-kacis, sampiyon) — bunların HEPSİ görsel incelemede **A veya C**
çıktı, metin HER YERDE tam okunaklı (BAŞKAN tipi "13px'e ezik" deseni YOK).
İmha-10 havuzundan ek 2 film (don-kisot, dogu-ekspresinde-cinayet — ikisi de
dup≤0.10, 135 dışı) incelendiğinde: don-kisot yine A (okunaklı tekrar metin),
dogu-ekspresinde-cinayet KISMEN B paternine benziyor (mor kayan yazı kar
manzarası üzerinde, bazı bölümlerde okunaklı bazılarında ince/düşük-kontrast)
ama net bir "silinmiş" örnek değil.

**Çıkarım:** `imha_imzasi` kriteri (statik-sayfa alanı>%70 VE ≥2 cılız blok)
muhtemelen YANLIŞ-POZİTİF üretiyor — sıradan kayan-yazı kredilerinde tek
satırlık (h<25px) bloklar zaten yaygın, bu tek başına "imha" kanıtı değil.
M4b'nin B-fix'i (kutu-hasadı fallback) bu 135-havuz için düşük öncelik olmalı;
gerçek B-vakaları (varsa) muhtemelen `imha_imzasi`nin DAHA SIKI bir versiyonuyla
(gerçek okunabilirlik testi, örn. OCR-rec confidence eşiği) ayrıca taranmalı.

## Fix → kazanım tablosu

| Reçete | Hedef sınıf | Tahmini film (135 içinden) | Not |
|---|---|---|---|
| F1c ön-filtre gevşetme + run-içi TÜM kart çiftlerini karşılaştırma (yalnız 1 referansa değil) | A1 (statik kart tekrarı) | ~63 | En büyük tekil kazanım adayı; %38'i (51 film) zaten hiç aday üretmiyor |
| H1 slit-birleştirme dy-doğrulamalı örtüşme kırpma | A2 (kayan-yazı/slit tekrarı) | ~41 | F1c bu blokları KAPSAMAZ (yalnız `static_page` inceliyor) — ayrı fix şart |
| Health/dup tanımına metin-farklılığı istisnası | C | ~27 | Kod fix değil — üretim/composer dokunulmaz, ölçüt güncellemesi |
| `dup_metrik.py` düz-gradyan/tek-blok güvenlik filtresi | D | ~4-5 | Metrik-katmanı, composer dokunulmaz |
| M4b kutu-hasadı fallback (B) | B | ~0 | Bu 135-havuzda hedef neredeyse yok; öncelik düşürülmeli |

Toplam potansiyel: A1+A2 fix'leri gerçekten dup_oran'ı 0.10 altına indirirse
~104 film sağlıklı hale gelebilir (mevcut 268/427 → ~372/427, sağlık
%62.8→%87.1); C+D'nin ölçüt düzeltmesiyle "hasta" sayılmaktan çıkması ek
~31-32 film daha katar (~%94.5) — M7 hedefi %91'in üzerinde. (Bu üst-sınır bir
tahmin; A1/A2 fix'lerinin HER filmde dup_oran'ı tam eşiğin altına indireceği
garanti değil, gerçek etki ancak fix uygulanıp yeniden ölçülünce netleşir.)

## En çarpıcı 5 vaka (tanık kırpım yolları)

1. **hizli-silah** (dup=0.9277, örneklemin en kötüsü) — "Cast of Characters"
   listesi run[9,23] içinde 4 kart olarak BİREBİR tekrarlanmış, hiçbir skip izi
   yok (F1 bile tetiklenmemiş).
   `data/master_ex/_siniflandirma/hizli-silah_witness.png`
2. **belki-bir-gun** (dup=0.5651, H=24768 — dev master) — scroll-slit
   kesişiminde aynı oyuncu-isim satırları birden fazla dilimde tekrarlanmış,
   H1'in en net kanıtı.
   `data/master_ex/_siniflandirma/belki-bir-gun_witness.png`
3. **intikam** (dup=0.7137) — dondurulmuş at-araba sahnesi üzerinde SAYFA SAYFA
   FARKLI kırmızı kredi metni (Class C'nin en net örneği; metin okunaklı,
   içerik kaybı yok).
   `data/master_ex/_siniflandirma/intikam_witness.png`
4. **tas-devri** (dup=0.5882) — Flintstones mağara-kapısı çizimi sabit, her
   sayfada FARKLI seslendirme kadrosu ismi (Class C, çizgi-film örneği).
   `data/master_ex/_siniflandirma/tas-devri_witness.png`
5. **tehlikeli-yolculuk-kentucky-guzeli** (dup=0.1282, `kept_blocks=1`) —
   masterda TEK sayfa var, gerçek tekrar YOK; metrik düz-gökyüzü bandını kendi
   içinde eşleştirmiş (Class D, saf metrik yanlış-pozitifi).
   `data/master_ex/_siniflandirma/tehlikeli-yolculuk-kentucky-guzeli_witness.png`

## Film başına tek satır (30-örneklem)

| Slug | dup_oran | Sınıf | Kanıt |
|---|---|---|---|
| hizli-silah | 0.9277 | A1 | "Cast of Characters" listesi 4 kartta birebir tekrar, sıfır skip izi |
| gelincikler-geri-dondu | 0.7713 | C | Dondurulmuş çift-yakın-plan sahnesi sabit, 3+ sayfada FARKLI prodüksiyon kredisi |
| benim-kalbimi-kirma | 0.7210 | C | Ağaç/gökyüzü footage sabit, sayfalar arası farklı kredi metni (bazı bölümler metinsiz geçiş) |
| boksorun-olumu | 0.7157 | A1 | Dublaj kadrosu isim listesi birebir iki kez (kayan liste çift-yakalama) |
| intikam | 0.7137 | C | At-araba dondurulmuş sahne, her sayfada farklı kırmızı kredi metni |
| uc-kadina-bir-mektup | 0.6961 | A2 | Aynı 6 dublaj ismi 36px kaymayla iki kez (slit-tekrarı, H1) |
| affedilmeyenler | 0.6711 | A1 | "THE END / A James Productions" kartı birebir iki kez |
| kis-gelmeden | 0.6273 | A1 | Aynı oyuncu-isim blokları (~80px kaymayla) tekrar |
| ulysses-in-maceralari | 0.6095 | A1 | "scripts/producer/music composer" satırları birebir tekrar |
| don-juan-in-maceralari | 0.6053 | A1 | Çatı-manzara sahnesi birebir tekrar; F1c run[0,58] içinde KISMEN çalıştı ama run-dışı tekrarı yakalayamadı |
| muthis-gece | 0.6053 | A1 | Dekoratif çerçeveli dağ manzarası, metin yok, birebir tekrar |
| tas-devri | 0.5882 | C | Flintstones mağara kapısı sabit, sayfa başına farklı seslendirme ismi |
| genc-billy-young | 0.5714 | A1 | Batı kasabası sahnesi + BİREBİR aynı 6 kişilik oyuncu listesi iki kez |
| sevgili-james | 0.5714 | A1 | "ERHAN ABİR" ismi iki farklı y-konumunda birebir |
| belki-bir-gun | 0.5651 | A2 | H=24768 dev master; aynı isim satırları slit-dilimlerinde tekrar (H1) |
| amelia-earhart | 0.5069 | A1 | Uçak kanadı yakın-plan sahnesi metinsiz birebir tekrar; F1c bu filmde BAŞKA bir bölümde ateşlendi (rec_kanit var) ama gösterilen çift değil |
| hayat-agaci | 0.5000 | C | Karlı ağaç sahnesi sabit, Farsça kredi isimleri sayfa başına değişiyor |
| cek-postaya-verildi | 0.4933 | A2 | H=11888, `strict_scroll_frac=1.0` (tam slit) — yine de aynı prodüksiyon-ekibi satırları tekrar (H1, saf slit modda bile) |
| aslan-yurekli-cavus | 0.4839 | A1 | "THE END" WB kartı + oyuncu listesi birebir tekrar |
| ask-ruzgari | 0.4667 | A1 | "THE END / A Universal-International Picture" kartı birebir tekrar |
| secenekler | 0.1158 | A1 | Kırmızı-zemin kredi metni birebir iki kez (düşük-dup örneği, aynı mekanizma) |
| hayat-bir-romandir | 0.2588 | A1 | H=11672 dev master, Fransızca kredi satırları birebir tekrar |
| hepsi-benim | 0.2963 | A1 | Heykel/avize sahnesi çoğunlukla metinsiz tekrar (1 sayfada kısa "Courtroom Spectator" metni, örtüşme yok) |
| doberman-cetesi | 0.1875 | A1 | Orman/patika sahnesi metinsiz birebir tekrar |
| gec-gelen-ask | 0.1951 | C | 9 farklı Rusça kredi kartı (yönetmen/kameraman/vs); eşleşen bloklar yalnız sayfa-kenarı düz-gri bandı, gerçek metin farklı |
| ask-sarkisi | 0.2104 | A1 | "Directed by RODNEY BENNETT" kartı köprü/malikane sahnesiyle birebir tekrar |
| batiya-giden-yol | 0.2551 | A1 | "THE END" kartı (dağ manzarası) birebir tekrar |
| kabaran-ofke | 0.2599 | A2 | Saf slit modu (`scroll_frac=1.0`) içinde bile aynı ekip-ismi satırları tekrar |
| alice-harikalar-diyarinda | 0.1081 | A2 | Kart-muhafız animasyon sahnesi birebir tekrar (eşik-sınırı vaka) |
| tehlikeli-yolculuk-kentucky-guzeli | 0.1282 | D | `kept_blocks=1`, gerçek tekrar YOK — metrik düz-gökyüzü öz-benzerliği yanlış-pozitifi |

## Ek çapraz-kontrol: imha-10 ve boy-17 grupları

**imha_imzasi (10 film, ayrı health kriteri) — 6 film incelendi:**
sampiyon (0.2235, A — "CHAMPION" posteri + isim listesi birebir tekrar, metin
tam okunaklı), duello (0.1135, A — altın harfli kredi metni birebir tekrar,
okunaklı), maudie (0.2490, A — beyaz kredi metni birebir tekrar, okunaklı),
ozgurluge-kacis (0.2837, C — dondurulmuş yakın-plan + değişen altyazı metni,
YAKIN_PLAN paterninin ta kendisi), don-kisot (0.0925, A — yel değirmeni
tablosu + kredi metni birebir tekrar, okunaklı), dogu-ekspresinde-cinayet
(0.0667, kısmen B-benzeri — mor kayan yazı kar manzarası üzerinde, bazı
bölümlerde ince/düşük-kontrast ama tam silinmiş değil). **6/6'sında gerçek
"metin ezik/okunaksız" örneği YOK** (dogu hariç, o da sınırda) — `imha_imzasi`
kriteri muhtemelen yanlış-pozitif üretiyor (bkz. yukarı, "Sınıf B" bölümü).

**boy_anormal (18 film, `H<300`) — 3 film incelendi:** ben-hur (H=215, "THE
END / A Metro-Goldwyn-Mayer Picture" — tam ve doğru tek kart, eksik değil),
solaris (H=31, "КОНЕЦ ФИЛЬМА" tek satır — tam ve doğru), + genel örüntüde
diğer 16 film de `dup_oran=0.0` (tekrar YOK). Bu grup A/B/C/D taksonomisine
GİRMİYOR — dup mekanizmasıyla ilgisi yok, sadece basit/kısa jenerik kartlarının
`H_MIN=300` eşiğini net biçimde altında kalması (health tanımı kalibrasyonu
sorunu, muhtemelen `H_MIN` çok agresif — 3 filmin 3'ü de İÇERİK OLARAK
eksiksiz).

## Kısıt ve sonraki adım notu

Bu doküman SALT TEŞHİS — hiçbir fix uygulanmadı. Fix önceliği (orkestratörün
kararı için): F1c ön-filtre gevşetme + kapsam genişletme (A1, en büyük tekil
kazanım) > H1 slit-kırpma (A2) > health/dup-tanımı düzeltmesi (C, kod
dokunmadan hızlı kazanım) > dup_metrik güvenlik filtresi (D) > M4b kutu-hasadı
(B, bu havuzda düşük öncelik — ayrı imha_imzasi kriteri yeniden kalibre
edilmeden B'nin gerçek büyüklüğü bilinemez).
