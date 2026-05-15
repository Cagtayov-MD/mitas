# 12 - Canlı Mutfak Protokolü

**Son güncelleme:** 2026-05-14  
**Son değişen bölüm:** ID'li takip, sabit durum sözlüğü ve tamamlandı kriteri

---

## 1. Temel ilke

`mutfak/` klasörü MITAS'ın canlı takip sistemidir.

Bu dosya `00_BURADAN_BASLA.md` içindeki akış kuralının ayrıntı kılavuzudur. `00` akışı ve organizasyonu söyler; bu dosya canlı takip sisteminin nasıl uygulanacağını açıklar. Çelişki görülürse `00_BURADAN_BASLA.md` bağlayıcı kabul edilir ve bu dosya ona göre düzeltilir.

Kullanıcı "mutfak kaynak", "mutfaktan devam", "nerede kaldık" veya benzer bir ifade kullandığında çalışma şu kabul ile başlar:

```text
Kaynak: E:\MITAS\mutfak
Canonical workspace: E:\MITAS
Canlı pano: mutfak\05_AKTIF_GOREV.md
Karar defteri: mutfak\06_KARARLAR_GUNLUGU.md
Worktree protokolü: mutfak\11_WORKTREE_KOORDINASYON.md
```

Mutfak statik doküman değildir. Her işten sonra nefes alan, güncellenen proje hafızasıdır.

---

## 2. LLM için değişmez çalışma emri

Claude / Opus / Codex / ChatGPT veya başka bir yardımcı MITAS üzerinde çalışıyorsa:

1. Önce `00_BURADAN_BASLA.md` okunur.
2. Canonical workspace `E:\MITAS` kabul edilir.
3. Worktree kontrolü için `11_WORKTREE_KOORDINASYON.md` okunur.
4. Nerede kalındığı `05_AKTIF_GOREV.md` içindeki canlı panodan okunur.
5. Karar verilecekse veya karar değişecekse `06_KARARLAR_GUNLUGU.md` güncellenir.
6. İş bitince mutfak güncellenmeden "tamamlandı" denmez.

Bu görev bir nezaket notu değil, çalışma sözleşmesidir.

---

## 3. "Nerede kaldık?" cevabı nereden verilir?

Kullanıcı "nerede kaldık?" dediğinde cevap şu sırayla hazırlanır:

1. `05_AKTIF_GOREV.md` → canlı pano, açık işler, sonraya bırakılanlar.
2. `03_GUNCEL_DURUM.md` → genel proje durumu.
3. `06_KARARLAR_GUNLUGU.md` → son kararlar.
4. `11_WORKTREE_KOORDINASYON.md` → branch/worktree riski var mı.

Cevap uzun bir tarihçe değil; o an devam etmek için gereken net tablo olmalıdır:

- şu anki odak,
- açık maddeler,
- sonraya bırakılanlar,
- son gerçek testler,
- son kararlar,
- bir sonraki somut adım.

## 3.1 "Şunu yaptık mı?" cevabı nereden verilir?

Kullanıcı "şunu yaptık mı?", "bu kapanmış mı?", "bunu daha önce konuşmuş muyduk?" veya benzer bir soru sorduğunda ilk kaynak yine `05_AKTIF_GOREV.md` canlı panodur.

Sıra:

1. `05_AKTIF_GOREV.md` içindeki "Son yapılanlar / kapananlar" bölümüne bak.
2. Bulunamazsa "Sonraya bırakılanlar / açık park listesi" bölümüne bak.
3. Karar niteliğindeyse `06_KARARLAR_GUNLUGU.md` içinde ara.
4. Dosya/output/araç niteliğindeyse `07_REFERANS_HARITASI.md` veya ilgili `docs/` sprint raporuna bak.

Cevap formatı:

```text
Evet/Hayır/Kısmen.
Kaynak: <dosya ve bölüm>
Durum: Yapıldı / Açık / Ertelendi / Karar bekliyor
Kanıt: <test, artifact, karar veya dosya referansı>
```

Eğer `05_AKTIF_GOREV.md` içinde kayıt yoksa yardımcı "yapılmadı" diye kesin konuşmaz; "canlı panoda kaydı yok, karar günlüğü/referanslarda ayrıca bakıyorum" diyerek doğrular.

---

## 4. Her işlem bitince ne güncellenir?

İşin türüne göre zorunlu kayıt yeri:

| Olay | Güncellenecek yer |
|---|---|
| Kod değişikliği bitti | `05_AKTIF_GOREV.md` canlı pano / yapılanlar |
| Gerçek test koşuldu | `05_AKTIF_GOREV.md` gerçek testler tablosu |
| Yeni karar verildi | `06_KARARLAR_GUNLUGU.md` ve gerekiyorsa `05_AKTIF_GOREV.md` |
| Karar değişti | Eski karar silinmez; `06_KARARLAR_GUNLUGU.md` içinde yeni kayıtla düzeltilir |
| Yeni plan yapıldı | `04_YOL_HARITASI.md` veya `05_AKTIF_GOREV.md` |
| Bir konu ertelendi | `05_AKTIF_GOREV.md` sonraya bırakılanlar |
| Ertelenen konu çözüldü | `05_AKTIF_GOREV.md` içinden yapılanlar/kapananlar bölümüne taşınır |
| Yeni dosya/araç/output oluştu | `07_REFERANS_HARITASI.md` veya ilgili sprint raporu |
| Worktree/branch karışıklığı görüldü | `11_WORKTREE_KOORDINASYON.md` |

---

## 5. Takip ID'leri ve durum sözlüğü

Her izlenebilir madde bir ID alır. ID değişmez; konu kapanınca ID yapılanlar/kapananlar tarafına taşınır.

ID önekleri:

| Önek | Anlam | Örnek |
|---|---|---|
| `PARK-*` | Sonraya bırakılan / açık park maddesi | `PARK-ASR-001` |
| `TASK-*` | Aktif yapılacak iş | `TASK-ASR-001` |
| `DONE-*` | Yapılan / kapanan iş | `DONE-MUTFAK-001` |
| `TEST-*` | Gerçek test veya doğrulama kaydı | `TEST-ASR-001` |
| `DEC-*` | Karar özeti veya karar takibi | `DEC-MUTFAK-001` |

Sabit durum sözlüğü:

| Durum | Anlam |
|---|---|
| `Açık` | Henüz çözülmedi, bekliyor |
| `Ertelendi` | Bilerek sonraya bırakıldı |
| `Karar bekliyor` | Kullanıcı veya karar günlüğü kararı bekleniyor |
| `Devam ediyor` | Üzerinde aktif çalışılıyor |
| `Yapıldı` | İş tamamlandı, test gerekmeyebilir |
| `Test edildi` | Test/doğrulama kaydıyla tamamlandı |
| `Kapatıldı` | Açık listeden düşmüş, yapılanlara taşınmış |
| `İptal edildi` | Bilerek kapsamdan çıkarıldı |

Bu kelimelerin dışına çıkılmaz. Ek durum gerekiyorsa önce `00_BURADAN_BASLA.md` §0 ve bu bölüm güncellenir.

---

## 6. Tamamlandı tanımı

Bir iş ancak aşağıdaki kayıtlar varsa "tamamlandı" sayılır:

1. Workspace/cwd açıkça belli: örn. `E:\MITAS`.
2. Değişen dosyalar veya dokunulan alanlar yazıldı.
3. Test koşulduysa komut ve sonuç yazıldı; koşulmadıysa "test koşulmadı" açıkça yazıldı.
4. `05_AKTIF_GOREV.md` canlı pano güncellendi.
5. Karar niteliği varsa `06_KARARLAR_GUNLUGU.md` güncellendi.
6. Worktree/branch riski varsa `11_WORKTREE_KOORDINASYON.md` ile doğrulandı.

Bu altı maddeden biri eksikse doğru ifade "işin şu kısmı yapıldı, takip kaydı eksik" olmalıdır.

---

## 7. Zorunlu rapor başlığı

Ciddi kod, test, audit veya dokümantasyon işinden sonra yardımcı raporunda şu başlık kısa da olsa yer alır:

```text
Workspace/cwd:
Branch/worktree:
Değişiklik ana E:\MITAS içinde mi:
Test:
Mutfak kaydı:
```

Bu başlık özellikle Claude / Opus / Codex paralel çalışırken yanlış workspace raporlamasını engeller.

---

## 8. "Bunu daha sonra konuşalım" kuralı

Kullanıcı bir konuyu sonraya bırakırsa konu kaybolmaz.

Yapılacak işlem:

1. `05_AKTIF_GOREV.md` içindeki "Sonraya bırakılanlar" bölümüne satır eklenir.
2. Satıra `PARK-*` ID'si verilir.
3. Satırda tarih, konu, neden ertelendiği ve tekrar açma koşulu yazılır.
4. Kullanıcı "daha sonraya ne bırakmıştık?" dediğinde bu liste okunur.
5. Konu çözülünce satır açık listeden kaldırılır veya kapalı olarak işaretlenir; aynı ID referansıyla yapılanlar bölümüne kısa kayıt düşülür.

Örnek:

```markdown
| PARK-ASR-002 | 2026-05-14 | ASR condition_on_previous_text kararı | Kullanıcı kararı bekleniyor | ASR fallback patch'leri sonrası tekrar aç | Karar bekliyor |
```

---

## 9. Gerçek test kaydı nasıl tutulur?

"Test geçti" demek tek başına yeterli değildir.

Gerçek test kaydı şu bilgileri taşımalı:

```text
ID:
Tarih:
Workspace / cwd:
Komut:
Sonuç:
Skipped varsa nedeni:
Artifact / rapor:
```

Örnek:

```markdown
| TEST-ASR-001 | 2026-05-14 | E:\MITAS | `pytest tests/test_asr_quality.py` | passed | Yok | - |
```

Eğer test koşulmadıysa final cevapta açıkça "test koşmadım" denir.

---

## 10. Yapılan iş kaydı

Bir iş bittiğinde `05_AKTIF_GOREV.md` içinde kısa ve izlenebilir kayıt bırakılır:

```markdown
| ID | Tarih | İş | Dosyalar | Kanıt/Test | Durum | Not |
```

Kayıt "ne yaptım" günlükçülüğü değildir; sonraki oturumun kaldığı yerden devam etmesini sağlar.

---

## 11. Mutfak güncellemeden tamamlandı denmez

Bir yardımcı şu cümleyi ancak mutfak güncellendiyse kurabilir:

```text
Tamamlandı.
```

Mutfak güncellenmediyse doğru ifade şudur:

```text
Kod tarafını yaptım; mutfak takibini henüz güncellemedim.
```

Bu ayrım özellikle Claude / Opus / Codex paralel çalışırken zorunludur.

---

## 12. Kısa başlangıç şablonu

Yeni oturumda yardımcı şu kısa kontrolü yapar:

```text
Mutfak kaynak kabul edildi.
Canonical workspace: E:\MITAS
Okunanlar: 00, 11, 12, 05, 03, 06
Nerede kaldık: <05_AKTIF_GOREV.md canlı panodan özet>
Sonraya bırakılanlar: <liste>
ID/durum kontrolü: <açık ID'ler ve durumları>
Bir sonraki somut adım: <tek cümle>
```

Bu şablon konuşmayı yavaşlatmak için değil, aynı yerden devam etmek için vardır.
