# Jordan — değişiklik günlüğü

## 2026-08-13 — kule kuruldu

Allstar'ın ikinci kulesi. **mp4 girer, yazı çıkar.** Native video okuma,
Qwen3.5-9B ile. Düzeltme, yorum, router yok.

**Sözleşme.** `OKUNDU` / `METIN_YOK` / `ARIZA` — Kobe'nin üçlü ayrımı devralındı
ve en önemli değişmez korundu: **`ARIZA` asla `METIN_YOK`'a dönüşmez.**
`METIN_YOK` ve `ARIZA` blok/çift taşıyamaz, `OKUNDU` bloksuz olamaz — hepsi
`ValueError` ile zorlanır. Atomik yazım (`os.replace`), `_TAMAM` en son.
Çıktı: `out/<film_id>/<bolum>/` içinde `jordan.json` + `jordan.txt` + `_TAMAM`.

**İki geçiş.** Geçiş 1 videodan ham metin bloklarını okur; geçiş 2 **yalnız o
metni** görerek rol→isim çiftler — görüntüyü görmez. Tek istekte model rolü
tutturmak için metni düzeltmeye başlıyor ve okuma hatasıyla eşleme hatası
ayrılamaz hale geliyordu. **Sızdırmazlık kapısı:** çıkan her rol/isim geçiş 1'in
satırlarında geçmek zorunda; geçmiyorsa atılır ve `kanit.cift_eleme`'ye yazılır.
Geçiş 2 çökerse geçiş 1'in metni korunur (`kanit.cift_ariza`).

**Parçalama — ölçülmüş zorunluluk.** Sandbox ölçümü (2026-08-12): 36 kare/çağrı
→ **39 filmin 39'unda CUDA OOM**; 30 kare → çalıştı. Klip 15 sn'lik, 2 sn
bindirmeli parçalara kesilip her parça ayrı çağrıda okunuyor. Bindirme, parça
sınırında kesilen ismi kurtarıyor; ardışık parçadaki birebir aynı blok düşüyor,
uzak tekrarlar korunuyor. Emniyet freni: `parca.kare_tavani`.

**Düşünme kapatıldı.** Qwen3.5 varsayılan akıl yürütüyor ve muhakemesi
transkripte sızıyordu — sandbox çıktısında modelin *"Wait, looking closely at
the first frame…"* diye yorum yaptığı ve cevabı kaçak bir `</think>` ile iki kez
bastığı gözlendi. `enable_thinking=False` + sızıntı ayıklayıcı: son `</think>`
sonrası alınır ve `kanit.dusunme_sizinti` sayılır; blok kapanmamışsa
`ARIZA(CIKTI_BOZUK)`. Sessizce temizleyip "okundu" denmiyor.

**İki checkpoint kuruldu.**
`model/w8a8` = INT8 W8A8 (`RedHatAI/Qwen3.5-9B-quantized.w8a8`, 14 GB) —
VARSAYILAN. `model/bf16` = orijinal (`Qwen/Qwen3.5-9B`, 19.3 GB) — kıyasın
kontrol kolu. w8a8'de **görüntü kulesi kuantize değil** (`model.visual.*`
`ignore` listesinde, bf16 kalıyor); yalnız dil tarafı 8-bit.

> **FP8 bu kartta yok.** RTX 3090 = Ampere `sm_86`, FP8 çekirdeği `sm_89`+
> ister. "8-bit" istendiğinde bu donanımda doğru cevap INT8'dir.
>
> **Hangisinin daha iyi okuduğu ÖLÇÜLMEDİ.** INT8 varsayılan çünkü bellek
> kısıtı ölçülmüş, kuantizasyon kaybı henüz varsayım. bf16 silinmez.

**Kurulum sırasında çıkan iki gerçek kusur:**
① `Allstar/.gitignore`'a `*/model/` eklendi — 33 GB ağırlık git'e girecekti.
② `torchvision` 0.26 `read_video`'yu kaldırmış; transformers ona düşüp
`AttributeError` veriyordu. `torchcodec` kuruldu. Kule bunu **sessizce
yutmadı** — ilk gerçek koşu `ARIZA(MODEL)` yazdı, hata görünür oldu.

**Uçtan uca gerçek koşu.** KUKLA ADAM açılışı (30 sn): 3 parça, 0 bozuk,
düşünme sızıntısı 0, 3 blok / 7 satır, **23.3 sn** →
`CORI FILMS` · `Quantum Films / in association with / Capital Productions
Limited / presents` · `HUMPTY DUMPTY MAN`. Uydurma yok.

Testler **52/52** (sözleşme 17 · okuyucu 14 · çiftleyici 8 · akış 13), hiçbiri
GPU istemiyor.
