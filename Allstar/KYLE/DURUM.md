# KYLE durum

**Faz 1 çalışan deterministik kule.**

Kurulan parçalar:

- dizi bazlı kalıcı/geçici profile (`kyle.series/v1`)
- manuel ilk cast/crew seed'i
- 2–3 bağımsız saf metin girişi
- source-preserving observation ID
- fuzzy known-person eşleştirme
- rol başlığı canonicalization
- aynı kaynağı tek oy sayma
- unknown cross-source clustering
- minimum 2 bağımsız kaynak kapısı
- sadece değişiklik çıktısı
- `COUNT_INCREASE`
- `ROLE_HOLDER_CHANGED`
- `NEW_MEMBER`
- `NEW_GUEST`
- `NEW_EPISODE_MEMBER`
- review kuyruğu (tek kaynak / rol belirsiz)
- JSON kanıt
- PDF değişiklik raporu
- otomatik profile zehirlenmesini önleyen `memory_patch` + açık `uygula`
- atomik JSON ve `_TAMAM` bitiş işareti

KYLE'ın hedefi "her bölümün kusursuz tam jeneriğini yeniden yazmak" değildir. Hedef, doğrulanmış dizi hafızasına göre **yalnız yeni/değişen şeyleri yüksek hassasiyetle bulmaktır**.
