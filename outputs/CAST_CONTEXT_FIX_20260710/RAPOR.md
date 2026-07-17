# filter_cast_by_raw_context komşu-dışla fix — kanıt raporu (2026-07-10, task_ebc9425c)

Kaynak: [[project_cast_sessiz_kayip_4mekanizma_20260710]] mekanizma (4) — SANTRAL/"The Operator"
kökü, `E:\MITAS\scripts\credit_text_read.py` `filter_cast_by_raw_context`/`_CREW_CONTEXT_KW`.

## Kök-neden (canlı-veri, doğrudan fonksiyon çağrısıyla — LLM/Ollama gerekmedi)

SANTRAL'in ham OCR'ında (`ocr\ocr-ef563e1b\ocr_raw_all.txt`) iki AYRI sızıntı mekanizması bulundu:

1. **KENDİ-SATIR ÇAKIŞMASI** — JACQUELINE KIM'in ekran-karakteri bizzat "Operator" (santral
   memuresi). OCR kartı "Operator JACQUELINE KIM" diye okuyor; jenerik "operator" crew-kelimesi
   kendi satırında. ~21 ham-tekrar (scroll/çok-kare okuma), OCR bazen "Operator" kelimesini
   kaçırıyor (bare "JACQUELINE KIM" varyantı da var) ama net çoğunluk crew=True → oran 13/21≈0.62
   ≥0.60 → düşüyor.
2. **KOMŞU-KİRLENMESİ** — BRION JAMES'in KENDİ satırında crew-kelimesi YOK, ama kart-düzeninde
   HEMEN ÖNCESİNDE JACQUELINE KIM'in "Operator JACQUELINE KIM" satırı var; geriye-bakan pencere
   (i-2..i) bunu "komşu rol-etiketi" sanıp Brion James'i de crew sayıyor. Ham oran: 18/18=1.0
   (HER tekrar aynı şekilde crew=True — bu, tesadüfi OCR-gürültüsü DEĞİL, kartın gerçek/sabit
   satır-sırası).

## Denenen fix'ler ve 268-film canlı-tarama sonucu

Ölçüm yöntemi: `E:\MITAS\Database\` altındaki HER filmin (267-268 film, delivered
`kunye_teslim.md`'si + ham `ocr_raw_all.txt`/`ocr_ham.txt`'i olan) DELIVERED (üretimde zaten
hayatta kalan) cast listesini candidate olarak alıp, ORİJİNAL (fix-öncesi, HEAD'deki) fonksiyon
ile YENİ (fix-sonrası) fonksiyonu aynı ham-bağlam üzerinde karşılaştırdım. Amaç: "üretimde zaten
GÜVENDE olan bir isim yeni-DÜŞÜYOR mu" (regresyon) — LLM'i yeniden çağırmadan, saf fonksiyon
karşılaştırmasıyla.

### Deneme 1: içerik-bazlı dedup + komşu-dışla (İKİSİ BİRDEN) — REDDEDİLDİ

Aynı fiziksel satırın tekrar-OCR'lanan okumalarını TEK oya indirmek (content-dedup) SANTRAL'in
HER İKİ ismini de kurtarıyordu. AMA 268-film taramasında **8 filmde GERÇEK oyuncuları yanlış-crew
sayıp düşürdü**:

| Film | Yanlış-düşen | Neden |
|---|---|---|
| BİR KONUŞABİLSE (Lost in Translation TR) | BILL MURRAY | kendi oyuncu-satırı (8x) + "ASSISTANTS TO BILL MURRAY" (11x, ayrı fiziksel yer) + "Performed by Bill Murray" (9x, ayrı fiziksel yer, müzik). Ham-tekrar sayısı oranı güvenle <0.60 tutuyordu (21/39=0.538); dedup bu payı yok edip ≥0.60'a çıkardı. |
| DEFİNE GEZEGENİ (Treasure Planet) | MARTIN SHORT, MICHAEL WINCOTT | aynı desen (çoklu bağımsız crew-görünümlü satır) |
| JERICO APARTMANI ×2 kayıt | JOHN BOURGEOIS, GENEVIEVE BUJOLD, JOE COBDEN | aynı desen |
| CENNETE GELDİK Mİ | KEVIN BROWN | aynı desen |
| BJ VE AYI | DENNIS FIMPLE | aynı desen |
| ŞEYTAN RUHLU İNSANLAR | JEAN BROCHARD | aynı desen |
| 21.YÜZYIL EŞİĞİNDE TÜRK AİLESİ | ÜMİT KÜL | aynı desen |

Denenen düzeltmeler (dedup'ı kurtarmaya çalışan): "çoğunluk-oy" (majority-vote per distinct-
content-group) — Bill Murray'i YİNE düşürüyor (2/3≥0.60, sadece 1.0'dan 0.667'ye iniyor).
Yakınlık-kümeleme (gap-clustering, ~30 satır eşik) — SANTRAL için gereken eşik Bill Murray'in
"Performed by" kümesini de (13-92 satır aralıklı) parçalayıp AYNI hataya düşüyor. **Kök sorun:
"kaç kez okundu" (ham-tekrar sayısı) tek başına crew/cast ayrımı için güvenilir bir ağırlıklandırma
sinyali değil — bazı filmlerde bu "gürültü" SANTRAL'i düşürüyor, bazı filmlerde bu "gürültü"
(paradoksal biçimde) Bill Murray gibi gerçek oyuncuları YANLIŞLIKLA koruyordu.**

### Deneme 2: SADECE komşu-dışla (dedup YOK) — UYGULANDI

268-film taramasında **SIFIR regresyon**. Tek değişiklik: MAZHAR ALANSON (HERŞEY ÇOK GÜZEL
OLACAK, Cem Yılmaz'ın gerçek co-star'ı, aynı zamanda ünlü müzisyen — kendi adı+"MÜZİK" komşuluğu
benzer bir desen) doğru şekilde kurtarıldı (ek pozitif kanıt, SANTRAL dışı bir filmde).

SANTRAL sonucu (candidates=[JACQUELINE KIM, BRION JAMES, STEPHEN TOBOLOWSKY, MICHAEL LAURENCE,
CHRISTA MILLER]):
- BRION JAMES → KURTARILDI (komşu-kirlenme mekanizması çözüldü).
- JACQUELINE KIM → **HÂLÂ DÜŞÜYOR** (kendi-satır çakışması bilinçli kapsam-dışı bırakıldı —
  yukarıdaki regresyon riski yüzünden).
- STEPHEN TOBOLOWSKY / MICHAEL LAURENCE / CHRISTA MILLER → değişmedi (zaten hayattaydı).

Not: STEPHEN TOBOLOWSKY'nin nihai üründe (kunye_teslim.md) yine de eksik olması bu fonksiyonun
sorunu DEĞİL — trace kanıtı (debug_trace/trace.jsonl) onun bu filtreden GEÇTİĞİNİ, başka bir
pipeline-aşamasında (muhtemelen video_okuma/v4 LLM-çıkarımı, hiç üretilmemiş) kaybolduğunu
gösteriyor — ayrı bir mekanizma, bu görevin kapsamı dışında.

## Test kapsaması (yeni)

`E:\MITAS\tests\test_credit_text_read_cast_context.py` (7 test, hepsi pytest+kendi-koşucusuyla
YEŞİL): komşu-dışla'nın doğru kurtardığı desen, komşu-dışla'nın dokunmaması-gereken gerçek-crew
deseni, cast_seen override'ın bozulmadığı, BOŞ/None girdi fail-safe'i, gerçek SANTRAL verisiyle
uçtan-uca (Brion James kurtarılıyor, kontroller sabit), gerçek SANTRAL verisiyle Jacqueline Kim'in
BİLİNÇLİ olarak hâlâ düştüğünü kilitleyen belge-testi, VE gerçek BİR KONUŞABİLSE verisiyle
dedup'ın Bill Murray'i neden regresyona uğratacağını donduran kanıt-testi (dedup yeniden
denenirse bu test kırılıp fark ettirir).

## Kapsam-dışı bırakılanlar

- **Kendi-satır çakışması** (Jacqueline Kim tipi): yukarıda anlatıldığı gibi güvenli bir mekanik
  fix bulunamadı bu oturumda. Olası gelecek yön: "(in order of appearance)"/"Cast" başlığını
  pozitif sinyal olarak İLERİYE-bakan bir pencereyle yakalamak (görev-talimatının "angle 2"si) —
  ama bu başlık bazı okuma-döngülerinde OCR tarafından okunamaz/bozuk çıkıyor (SANTRAL'de 1
  temiz + 1 bozuk örnek görüldü) — güvenilirliği ayrıca test edilmeli, bu oturumda YAPILMADI.
- **task_33dc2368** (KB crew-yanlış-sınıflama, İKİ SEVGİLİM VAR/Paola Debiasi) — ayrı spawn_task,
  bu oturumda dokunulmadı.
- **task_73abb131** (garble-fuzzy SEIGNER/DESIGNER) — bu oturum SIRASINDA eşzamanlı BAŞKA bir
  session tarafından bağımsız fixlendi (bkz git diff, `_garble_reason_kb_gated`), bu görevle
  ilgisiz.
- **ETHAN HAWKE tipi crew-leak** (test_credit_crew_leak_gate.py'de keşfedilen, ÖNCEDEN VAR OLAN
  ayrı bir başarısız test) — spawn_task task_61e2ea2d'ye bırakıldı, bu fix'in kapsamı dışında
  (farklı mekanizma: komşu satır bir BAŞKA cast-adayının değil, GERÇEK bir crew-etiketinin
  kendisi — mevcut komşu-dışla mantığı bunu yakalayamaz).

## Durum

`E:\MITAS\scripts\credit_text_read.py` içinde COMMIT'SİZ bırakıldı (ana checkout, worktree
DEĞİL), kullanıcı onayı bekliyor. Diff küçük/negatif-yönlü (yalnız komşu-dışla; içerik-dedup
YOK). `E:\MITAS\tests\test_credit_text_read_cast_context.py` yeni dosya, commit'siz.
