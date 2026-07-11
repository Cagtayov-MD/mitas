# DİZİ MODU — SİSTEM SÖZLEŞMESİ (v1, 2026-07-09)

Bu belge dizi-modu modüllerinin ORTAK sözleşmesidir. Tüm modüller buradaki şemalara UYAR;
şema değişikliği önce burada yapılır. Onaylı plan: `C:\Users\TRT03\.claude\plans\mitasta-art-k-yavas-yavas-lovely-rabbit.md`

## İlkeler
- **SIFIR-DOKUNUŞ:** `mitas_pipeline.py`, `tek_film_kunye.py`, `_make_pdf.py`, `credit_parse.py`,
  `credit_role_lexicon.py` DEĞİŞMEZ. Dizi katmanı yalnız yeni dosyalar ekler, hub artefaktlarını salt-okur.
- **"Okunamadı > yanlış oku":** emin olunmayan alan BOŞ kalır, asla tahmin basılmaz.
- **"Bölümde yok" ALARM DEĞİLDİR:** dizi jeneriği o bölümde oynayanı basar; eksik isim kanondan basılır.
- Master güncellemesi (kalıcı değişim) tek motor kanıtıyla YAPILMAZ — OneOCR deterministiktir,
  aynı garble her bölümde aynı okunur. VL çapraz-tanık şart; yoksa `MASTER_ADAY` + KONTROL.

## Modüller (scripts/)
| Modül | Rol | Saf mı? |
|---|---|---|
| `seri_kayit.py` | Seri deposu IO: yükle/kaydet/kilitle/versiyonla | IO burada, mantık minimal |
| `dizi_credit_parse.py` | Hub → normalize BolumOkuma; konuk_ayikla; stop-kart | IO=hub salt-okuma |
| `seri_konsensus.py` | İlk-N okuma → master gövdesi | SAF (IO yok) |
| `seri_diff.py` | LOCKED master vs BolumOkuma → diff + uygula | SAF (IO yok) |
| `seri_bolum_kunye.py` | master+diff+meta → d-sözlüğü + PDF | birlesik_kunye SAF; CLI IO |
| `dizi_isle.py` | Orkestratör CLI (klasör → bölümler) | IO/subprocess |

## Depo düzeni
```
Database/_SERILER/<seri_anahtar>/
    seri_master.json      # kanonik durum (atomik: tmp + os.replace)
    gecmis.jsonl          # append-only olay günlüğü
    bolumler/bolum_0014.json   # bölüm-başına BolumOkuma anlık görüntüsü
```
Kök env ile taşınabilir: `MITAS_SERILER_ROOT` (test: tmp_path).

## Seri anahtarı
`seri_anahtar(klasor_adi)`: addan TRT_RE eşleşmeleri silinir → Türkçe-fold + upper +
alfasayısal-dışı `_` → 80 karaktere kırp → `_` + `sha1(ham_ad.encode('utf-8')).hexdigest()[:8]` soneki.
Örn `"BİZİM EVİN HALLERİ"` → `BIZIM_EVIN_HALLERI_<8hex>`.
`trt_seri_on_ek("1900-0138-0-0009-00-1")` → `"1900-0138-0"` (ilk 3 parsel; bölüm parseli maskelenir).
Farklı ön-ek görülürse `trt_on_ekler`e eklenir + `COKLU_SERI` uyarısı; seri BÖLÜNMEZ (klasör otorite).

## seri_master.json şeması (surum_sema=1)
```jsonc
{
  "surum_sema": 1,
  "seri_anahtar": "BIZIM_EVIN_HALLERI_a3f81c2d",
  "seri_adi": "BİZİM EVİN HALLERİ",
  "kaynak_klasor": "D:\\GELEN\\BİZİM EVİN HALLERİ",
  "trt_on_ekler": ["1900-0138-0"],
  "durum": "BUILDING",                    // BUILDING | LOCKED
  "master_surum": 1,
  "kilit_bolumler": [1, 2, 3],            // tohum bölümleri
  "surum_gecmisi": [                      // olay: kilit | kalici_degisim | terfi | ayrilma | format_kopusu
    {"surum": 1, "olay": "kilit", "bolumler": [1,2,3], "ts": "2026-07-09T12:00:00"}
  ],
  "alanlar": {                            // TEKİL alanlar — bkz. TEKIL_ALANLAR
    "Yönetmen": {
      "kanonik": ["SAMET POLAT"],         // liste: eş-yönetmen mümkün
      "guven": "KESIN",                   // KESIN | COKLU | ZAYIF | TEK_TANIK
      "kb_teyit": false,
      "tanik": {"SAMET POLAT": {"bolumler": [1,2,3], "yazimlar": {"SAMET POLAT": 2, "SAMET P0LAT": 1}}}
    }
  },
  "oyuncular": {                          // anahtar = KANONİK yazım
    "POLAT ALEMDAR": {
      "yazimlar": {"POLAT ALEMDAR": 2, "P0LAT ALEMDAR": 1},
      "bolumler": [1,2,3], "sira": 0,     // ilk-görünme sırası → PDF cast sırası
      "kb_teyit": false,
      "durum": "AKTIF",                   // AKTIF | ZAYIF_UYE | AYRILDI
      "son_gorulme": 3, "ardisik_yok": 0, "ayrilma_bolumu": null
    }
  },
  "teknik_ekip": {                        // TEKİL olmayan crew rolleri: rol → isim → kayıt
    "Müzik Yönetmeni": {"CAN ATİLLA": {"yazimlar": {"CAN ATİLLA": 3}, "bolumler": [1,2,3]}}
  },
  "aday_havuzu": {                        // tohumda 1-tanıklı kalanlar (alan bilgisiyle)
    "ALTAN ALKAN": {"alan": "oyuncular", "bolumler": [2], "yazimlar": {"ALTAN ALKAN": 1}}
  },
  "konuk_gecmisi": {                      // terfi takibi (KONUK_ADAYI görülme geçmişi)
    "OKTAY DENER": {"bolumler": [5, 9], "yazimlar": {"OKTAY DENER": 2}}
  },
  "bekleyen_degisimler": [                // kalıcı-değişim adayları (2-ardışık + VL-teyit bekler)
    {"tip": "alan_degisim", "alan": "Yönetmen", "yeni": ["CEM DENIZ"],
     "gorulen_bolumler": [13], "vl_teyit_bolumler": [], "ilk_bolum": 13}
  ],
  "format_kopusu": {"ardisik": 0, "ilk_bolum": null},   // toplu-kopuş sayacı
  "tanik_kayitlari": {                    // idempotency: bölüm-TRT-id → içerik
    "1900-0138-0-0014-00-1": {"bolum_no": 14, "content_hash": "sha256hex", "ts": "..."}
  },
  "guncelleme": {"ts": "...", "modul": "seri_diff", "bolum": 14}
}
```
`ts` değerleri çağıran tarafından `datetime.now().isoformat(timespec="seconds")` ile verilir.

## TEKİL alanlar
```python
TEKIL_ALANLAR = ("Yönetmen", "Yapımcı", "Senaryo", "Müzik", "Görüntü Yönetmeni", "Kurgu")
```
Geri kalan crew rolleri (CANON_OUT kalanları + "Diğer" + bilinmeyenler) → `teknik_ekip` (liste-alan).
CAST → `oyuncular`.

## BolumOkuma şeması (dizi_credit_parse.okuma_topla çıktısı)
```jsonc
{
  "bolum_no": 14,
  "trt_id": "1900-0138-0-0014-00-1",
  "cast": ["OKTAY DENER", "..."],          // parse_credits(dizi=True) cast — konuk_acik DÜŞÜLMÜŞ
  "crew": {"Yönetmen": ["SAMET POLAT"], "Müzik": ["CAN ATİLLA"]},   // rol → isimler
  "konuk_acik": ["ALTAN ALKAN"],           // jenerikte açık KONUK/BÖLÜM OYUNCULARI başlığı altındakiler
  "kb_hatti": {"yonetmen": [], "yapimci": [], "cast": []},   // v4 raporundan (varsa; yüksek güven)
  "vl": {"yonetmen": [], "oyuncular": [], "diger_roller": []},  // gemma_kunye.json (varsa)
  "stop_kart_bolum_no": 617,               // "617. Bölüm Sonu" kartından okunan no (yoksa null)
  "kaynak": "master_dilim",                // master_dilim | kare | yok
  "uyarilar": ["BOLUM_NO_CELISKI: kart=617 dosya=14"]
}
```
- Dilim kaynağı: `<clip>/master_dilim/dilim_oneocr.txt` + `dilim_oneocr.meta.json`;
  `meta["ocr_job"]` en yeni `ocr/<job>/` ile eşleşmeli (bkz. `_pipe_credit_text._dilim_lines` deseni),
  `### DILIM-SINIRI` satırları atılır. Dilim yoksa `kaynak="kare"`: en yeni `ocr/*/kunye.txt` satırları.
  O da yoksa `kaynak="yok"`, cast/crew boş.
- KONUK başlıkları (fold ile karşılaştır): `konuk oyuncular, konuk oyuncu, konuk sanatci,
  konuklar, bolum oyunculari, bu bolumun konuklari, guest starring, guest stars, special guest`.
  Başlık satırından sonraki isimler, bir sonraki rol başlığına (`credit_parse.role_of(l) != None`)
  kadar konuk sayılır; bu isimler `cast`ten `name_match` ile düşülür.
- STOP-KART (isim-parse'a girmeden düşür): `^\d+\.?\s*BÖLÜM(ÜN)?\s*SONU$`, `^DEVAM EDECEK(TİR)?$`,
  `^SON$` (fold sonrası kontrol). Bölüm-no'lu karttan no çıkarılır → dosya parseliyle çelişirse uyarı.

## Diff çıktı şeması (seri_diff.diffle)
```jsonc
{
  "bolum_no": 14,
  "eslesen": {"oyuncular": [{"master": "POLAT ALEMDAR", "okunan": "P0LAT ALEMDAR"}],
               "alanlar": {"Yönetmen": {"master": ["SAMET POLAT"], "okunan": ["SAMET POLAT"]}}},
  "eksik":   [{"alan": "oyuncular", "isim": "X Y", "ardisik_yok_yeni": 1, "karar": "OCR_KACAK"}],
             // karar: OCR_KACAK | AYRILDI
  "yeni":    [{"alan": "oyuncular", "isim": "A B", "karar": "KONUK_ADAYI", "kaynak": "cast-diff"},
              {"alan": "Yönetmen",  "isim": "C D", "karar": "DEGISIM_ADAYI"}],
  "kalici_degisim": [{"alan": "Yönetmen", "yeni": ["C D"], "kanit_bolumler": [13,14]}],
  "terfi":   [{"isim": "OKTAY DENER", "bolumler": [5,9,14]}],
  "format_kopusu": false,
  "bolum_ozel": {
    "konuk_oyuncular": [{"isim": "A B", "kaynak": "jenerik-basligi", "kesin": true},
                         {"isim": "C D", "kaynak": "cast-diff", "kesin": false}],
    "alan_override": {"Yönetmen": ["C D"]}
  },
  "kontrol_nedenleri": ["Yönetmen master'dan farklı (ilk kez, bölüm 14)"]
}
```

## Diff politikası ve kuralları (seri_diff)
```python
@dataclass
class DiffPolitika:
    eksik_esik: int = 3    # ardışık kaç bölüm yoksa AYRILDI
    kalici_esik: int = 2   # aynı fark kaç ardışık bölümde (VL-teyitli) → master güncelle
    terfi_esik: int = 3    # konuk kaç bölümde görülünce AKTIF kadroya
    konuk_max: int = 12    # bölümde bundan çok yeni isim → OCR patlaması → KONTROL
    kopus_esik: float = 0.40  # eşleşme oranı bunun altındaysa FORMAT_KOPUSU
```
1. Eşleşme YALNIZ `credit_crosscheck.name_match` (sıkı). `name_close` yalnız yazım-önerisi
   (aynı kişi OCR-varyantı) — kümelemede kullanılır, master-diff eşiğinde kullanılMAZ...
   İSTİSNA: master tanık `yazimlar` içinde birebir (fold) geçen yazım da eşleşmedir.
   Aynı bölümde birlikte görülen iki isim ASLA birleştirilmez.
2. master VAR + bölüm VAR → `eslesen`; kanonik yazım master'dan.
3. master VAR + bölüm YOK → `eksik` (`OCR_KACAK`), KONTROL YOK, isim PDF'te yine basılır;
   `uygula`da `ardisik_yok += 1`; `>= eksik_esik` → `AYRILDI` (o bölümden itibaren basılmaz, olay günlüğü).
4. bölüm VAR + master YOK:
   - cast → `KONUK_ADAYI` (KONTROL yok). `konuk_acik` kaynaklılar `kesin: true`.
     Bölümdeki yeni-isim sayısı > `konuk_max` → KONTROL ("yeni-isim patlaması").
     `AYRILDI` üyenin dönüşü konuk DEĞİL → yeniden `AKTIF` + eslesen.
   - TEKİL alan → `DEGISIM_ADAYI`: okuma garble-siz (`_looks_garble is None`) ise
     `alan_override` + KONTROL nedeni; garble ise override YOK (master basılır) + KONTROL nedeni.
5. Kalıcı değişim: `bekleyen_degisimler`de aynı değer (name_match) `kalici_esik` ARDIŞIK bölümde
   görüldü VE her görüldüğü bölümde VL okuması (`vl.yonetmen` / `vl.oyuncular` / diger_roller)
   aynı değeri içeriyorsa (name_match) → `kalici_degisim` → `uygula` `versiyon_atla` çağırır.
   VL teyitsiz → beklemede kalır (`MASTER_ADAY`), her bölüm KONTROL nedeni üretir.
   Araya farkın görülmediği bölüm girerse bekleyen kayıt sıfırlanır.
6. FORMAT_KOPUSU: master `oyuncular(AKTIF)+alanlar` isimlerinin < `kopus_esik` oranı bölümde
   eşleşti → alan-alan diff YAPILMAZ (eksik/yeni üretme), `format_kopusu: true` + tek KONTROL nedeni.
   `uygula`: sayaç artar; 2 ardışıkta olay `format_kopusu` günlüğe → dizi_isle yeni tohum penceresi açar.
7. Konuk terfisi: `konuk_gecmisi` + bu bölüm ile `terfi_esik` FARKLI bölüme ulaşan isim → `terfi`
   → `uygula` AKTIF kadroya ekler (sira = mevcut max+1), olay günlüğe.

## Konsensüs kuralları (seri_konsensus.kur_master)
- Girdi: `okumalar: list[BolumOkuma]` (tohum, bölüm-no sıralı), `seri_adi`, `kb=None` (CreditKB-benzeri
  `wd_find`/`name_close` kullanılabilir nesne; None=KB'siz), `simdi:str` (ts).
- Kümeleme: union-find; kenar = `name_match(a,b) or name_close(a,b)`.
- Kanonik seçim sırası: (1) rakam içeren yazım rakamsıza HER ZAMAN kaybeder;
  (2) çoğunluk (toplam tanık sayısı); (3) beraberlikte KB-yazımı (kb_teyit=True);
  (4) garble-siz olan; (5) ilk bölümdeki.
- TEKİL alan: ≥2 bölüm-tanıklı küme(ler) kanonik. Birden çoksa `guven=COKLU`. Hiç yoksa:
  tek tanık KB-teyitli → `guven=ZAYIF` ile gir; değilse alan HİÇ YAZILMAZ (boş).
- CAST: **3/3** (tohum bölüm sayısı kadar) → `AKTIF`; 2/3 → `ZAYIF_UYE`
  (5 bölümün ≥2'sinde görülmezse diff `uygula` konuğa düşürür); 1/3 → `aday_havuzu`.
- `teknik_ekip`: ≥2 tanık → girer; 1 tanık → `aday_havuzu`.
- Tohumdaki `konuk_acik` isimleri konsensüs havuzuna GİRMEZ → `konuk_gecmisi`ne yazılır.
- N=2 tohum: eşikler 2/2; N=1: her şey girer ama `guven=TEK_TANIK`, durum BUILDING kalır
  (kilidi dizi_isle basar; N<3 kilitte her bölüm "master <3 bölümle kuruldu" KONTROL notu taşır).

## Bölüm PDF birleştirme (seri_bolum_kunye.birlesik_kunye)
- Girdi: `master`, `diff`, `meta` (=`tek_film_kunye.parse_teslim_md` çıktısı + `trt_id`, `bolum`).
- Çıktı: `(d, kaynak_haritasi)`. `d` = `_make_pdf.build` sözlüğü, `tek_film_kunye.py:1174` sözleşmesi:
  `profile="DİZİ"`, `date`, `title`, `subtitle=None`, `specs=[("ÇÖZÜNÜRLÜK",..),("TÜR",..),
  ("TOPLAM SÜRE",..),("TRT KİMLİK",..)]`, `keywords="; ".join(cast)`, `cast`, `crew`,
  `ozet=tek_film_kunye.ozet_v4(meta["ozet"], names=...)`, `ses_kanallari`, `ana_dil`, `altyazi`,
  `poster=None`, `film_notu=[]`, `bolum="14. BÖLÜM"`.
- cast = master AKTIF (+ZAYIF_UYE) oyuncular `sira` düzeninde kanonik yazım, `name_normalize.upper_names`.
- crew = TEKİL alanlar (kanonik; `alan_override` varsa o bölüm için override) + teknik_ekip rolleri
  + EN SONDA `("Konuk Oyuncular", [konuklar])` satırı (varsa). `name_normalize.upper_crew` uygulanır.
- PDF görünümünde kaynak işareti YOK; provenans `pdf/kunye_dizi_kaynak.json`:
  `{"kaynak_haritasi": {...}, "diff_ozet": {...}, "master_surum": n, "kunye_kaynagi": "master|kare|kanon-devir"}`.
- PDF yazımı: `kunye_dizi.pdf` üret → boyut > 10KB ise `os.replace` ile hedefe.

## Yeniden kullanım tablosu (yenisi YAZILMAZ)
| İhtiyaç | Kaynak |
|---|---|
| fold / name_match / name_close / CreditKB | `scripts/credit_crosscheck.py` (:23/:52/:158/:221) |
| parse_credits(dizi=True) / role_of / is_person / is_company / CANON_OUT | `OCR-worktree/pdf-mitas/credit_parse.py` (importlib ile yükle) |
| garble sinyali `_looks_garble(name)->str|None` | `scripts/credit_text_read.py` (:683) |
| dilim satırı + run-scope | `scripts/_pipe_credit_text.py::_dilim_lines` deseni (:34) |
| d-sözlüğü + parse_teslim_md + ozet_v4 | `scripts/tek_film_kunye.py` (:84/:129/:1174) |
| PDF render `mp.build(path, d)` | `OCR-worktree/pdf-mitas/_make_pdf.py` (:83) |
| upper_names/upper_crew/tr_upper | `OCR-worktree/pdf-mitas/name_normalize.py` |
| parse_filename / hash_file / TRT_RE | `scripts/mitas_pipeline.py` (:463/:455/:84) |

`OCR-worktree/pdf-mitas` modülleri `importlib.util.spec_from_file_location` ile yüklenir
(test kalıbı: `tests/test_credit_crew_leak_gate.py`). scripts-içi modüller normal import
(`sys.path.insert(0, scripts_dir)`).

## PİLOT-ÖNCESİ YAMA SÖZLEŞMESİ (2026-07-09, karar: outputs/DIZI_MODU_KONSEY_KARAR_2026-07-09.md)
1. **Tohum-VL kapısı:** kilit anında `kur_master` kanonikleri (alanlar + AKTIF/ZAYIF_UYE oyuncular) tohum
   okumalarının `vl` birleşimiyle `name_match`'lenir; teyitsizler `master["tohum_vl_teyitsiz"]` listesine +
   kilit olayına + her bölümde TEK "tohum VL-teyitsiz: <n> isim" KONTROL nedeni. VETO DEĞİL (basım değişmez).
   `kb=None` BİLİNÇLİ ve KALICI (KB dizi-crew kapsaması ~0; KB asla hakem değil). Otomatik üçüncü-tanık
   eskalasyonu Faz-B (pilotta insan = üçüncü tanık).
2. **Terfi disiplini:** `uygula` terfi bloğu kadro anahtarını `konuk_gecmisi[isim]["yazimlar"]` üzerinde
   `kanonik_sec` ile seçer; `konuk_gecmisi`'ne yeni anahtar açılırken rakamlı yazım anahtar OLAMAZ
   (rakamsız varyant varsa o; yoksa isim aynen).
3. **`seri_kayit.yeniden_tohumla(anahtar, master, bolumler, simdi) -> dict`** (SAF): mevcut LOCKED master'ın
   `surum_gecmisi`'ne {"olay":"yeniden_tohum","eski_kilit":...,"ts":...} ekler, durum=BUILDING'e döndürür,
   `kilit_bolumler`/`format_kopusu` sıfırlar (alan/oyuncu defterleri KORUNUR — tanıklık kaybolmaz).
   `dizi_isle --tohum-yenile B1,B2,B3`: verilen bölümlerin ledger okumalarıyla kur_master+kilitle yeniden.
4. **`dizi_isle --teslim-disi`:** PDF'ler hub'a normal basılır; koşu sonunda export/ONAYLI+KONTROL altındaki
   bu serinin TRT-id'li PDF'leri `outputs/pilot_karantina/<seri_anahtar>/` altına TAŞINIR + rapora yazılır
   (export iki-uç KESİN kuralı korunur — karantina export dışıdır). export_mutabakat taşımaları da karantinaya.
5. **Telemetri:** (a) `uygula` bekleyen-değişim düşüşünde `{"olay":"bekleyen_dustu","alan":...,"gorulen":[...]}`
   olayı üretir; (b) `diffle` eslesen kayıtlarında okunan yazım bölüm `vl`'sinde name_match bulunamıyorsa
   `diff["vl_uyusmazlik"]` sayacı/listesi doldurulur (basımı ETKİLEMEZ); dizi_isle koşu raporuna toplar.
6. **İdempotensi:** `master["uygulanan_bolumler"]: [int]`. Bölüm bu listedeyse `uygula` ATLANIR (diff + PDF
   yine koşar; `--yeniden` bayrağı zorlar). `uygula` başarısında bölüm listeye eklenir (kaydet'ten önce).
7. **BOS_OKUMA:** `diffle`'de havuz (cast+crew+konuk isimleri) < min(8, ceil(0.3×len(beklenen))) VEYA
   okuma["kaynak"]=="yok" → eksik/yeni/kopuş-oranı HESAPLANMAZ; `diff["bos_okuma"]=true` + tek "OKUMA_YOK"
   KONTROL nedeni; kopuş sayacı ARTMAZ; üye sayaçları (ardisik_yok) DEĞİŞMEZ; PDF kanon-devir basılır.
8. **Eş-görünüm vetosu:** `isim_kumele` union adımında iki kümenin `bolumler` kümeleri KESİŞİYORSA
   birleştirme yapılmaz (aynı bölümde birlikte tanıklanan iki farklı yazım = iki kişi kanıtı).
9. **Unvan-strip (yalnız KARŞILAŞTIRMA anında):** kümeleme/name_match öncesi baştaki akademik unvan
   token'ları soyulur: DR, PROF, DOÇ/DOC, YRD, OP, AV, DT (nokta/birleşik varyantlarıyla). Basılan/kaydedilen
   yazıma ASLA uygulanmaz (OCR-otorite). BEY/HANIM/PAŞA LİSTEDE YOK (soyadı riski).
10. **KONUK başlıkları:** listeye `"bolum konuklari"` eklenir.
11. **N<3 kilit notu:** `len(master["kilit_bolumler"]) < 3` ise her bölüm künyesine
    "master <3 bölümle kuruldu (n)" KONTROL nedeni eklenir (seri_bolum_kunye).
12. **VL-dilim fallback (Çağatay 2026-07-09):** kaynak=master_dilim iken stop-kart bulunamadıysa
    VEYA satır sayısı < 8 ise `vl_dilim_oku` master-dilim PNG'lerini VL'e (env `MITAS_DIZI_VL_MODEL`,
    varsayılan glm-ocr) okutur — ADDITIVE: stop-kart no'su VL'den dolabilir (`STOP_KART_VL: n` uyarısı),
    sparse okumaya fold-dedup'lu ek satırlar katılır (`VL_DILIM_EK: n satır`). Kill-switch
    `MITAS_DIZI_VL_DILIM=0`; hata yutulur (`VL_DILIM_HATA`), PNG'siz hub sessiz geçilir.
## PROFİL AYRIMI — FİLM ≠ DİZİ (Çağatay 2026-07-11: "%100 EMİN")
| Eksen | FİLM profili (tip parseli =1) | DİZİ profili (tip parseli =0) |
|---|---|---|
| Hibrit-dy (slitscan kanal seçimi) | **ZORLA '0'** — eski yol bit-identik | **ZORLA '1'** — hibrit aktif |
| Zorlama noktası | `master_png_monitor._profil_dy_kilidi` hub adındaki TRT tipinden — **ortam değişkeni ne derse desin** | aynı kilit + `dizi_isle._pipeline_kos` env=1 (çift güvence) |
| Gölge-VL | pipeline bayrağına tabi | dizi_isle koşusunda ZORUNLU (=1, kalıcı-değişim VL-teyidi için) |
| Kaynak kopyalama | pipeline varsayılanı | `--no-copy-source` (disk) |
| Künye karar katmanı | tek-film v4 akışı (mitas_pipeline) | seri katmanı (konsensüs+diff+kanonik; bu sözleşme) |
| Okuma yüzeyi | kare-kare OneOCR birincil; dilim additive | master-PNG dilim birincil; kare fallback; VL-dilim fallback |
| KB kullanımı | kimlik/cross-check (v4) | kb=None (KB dizi-crew kapsaması ~0; yalnız-pozitif ileride) |
| TRT'siz hub (lab/test) | kilit karar veremez → env/varsayılan geçerli | aynı |
Kanıt-testi: `tests/test_dizi_profil_ayrimi.py` (film-zorla-0, dizi-zorla-1, TRT'siz-dokunma, env-bayrakları).

13. **CAST-ajans kuralı (Çağatay 2026-07-09):** jenerikte `cast` başlığı altında TEK büyük-harf
    girdi = casting AJANSI kredisi ("cast: MAVİ FİL") → oyuncu listesine DEĞİL `crew["Cast"]`
    satırına yazılır + `CAST_AJANS: <isim>` uyarısı. Blok sonu = rol başlığı veya küçük-harf-ağırlıklı
    etiket satırı (dizi kalıbı: etiket küçük, isim BÜYÜK). ≥2 girdili cast bloğuna DOKUNULMAZ.

## Test kuralları
- pytest, mevcut `tests/` kalıbı; her modülün testi kendi dosyasında (`tests/test_<modul>.py`).
- Depo testleri `MITAS_SERILER_ROOT` env + `tmp_path` ile; duckdb/KB MOCK (X:/Y: sürücüleri test ortamında yok sayılır).
- `_make_pdf`/reportlab: monkeypatch sözleşme testi + (reportlab varsa) 1 duman testi.
- Mevcut test paketi DEĞİŞMEDEN yeşil kalmalı.
