# 11 - Worktree Koordinasyon ve Canonical Workspace

**Son güncelleme:** 2026-05-14  
**Son değişen bölüm:** Bölüm 5 tablo + Bölüm 6 port listesi tamamlandı işaretlendi (DONE-ASR-001..003 ile)

---

## 1. Opus / Claude icin kopyalanabilir bilgilendirme

> MITAS tarafında worktree karışıklığı tespit edildi. Kullanıcının canonical çalışma alanı `E:\MITAS` olarak kabul edilecek. Senin "uyguladım" dediğin bazı değişiklikler `E:\MITAS\.claude\worktrees\awesome-gould-1ee408` altında görünüyor; ana `E:\MITAS` çalışma ağacına otomatik taşınmamış. Bu yüzden bir bulgu "bu branch'te yok" veya "uygulandı" denmeden önce mutlaka aktif `cwd`, `git worktree list`, `git status --short` ve ana workspace kontrol edilmeli. Eğer `.claude/worktrees/...` altında çalışıyorsan bunu açıkça söyle; ana workspace'e port edilmedikçe kullanıcıya `E:\MITAS` için uygulanmış gibi raporlama.

---

## 2. Kısa durum özeti

2026-05-14 tarihinde ASR audit tartışmasında iki farklı kod görüntüsü birbirine karıştı:

- `E:\MITAS` ana çalışma ağacında ASR v0.1'e ait büyük, uncommitted değişiklikler var.
- Temiz `HEAD` / bazı Claude worktree'leri bu değişiklikleri içermiyor.
- Bu nedenle `_select_fallback_result`, tail-gap detection, `TimelineEvent`, `error_flags`, `channel_merge.py` gibi semboller ana workspace'te varken temiz snapshot'ta yok.
- Opus/Claude tarafının uyguladığını söylediği bazı düzeltmeler ana `E:\MITAS` içinde değil, `.claude/worktrees/awesome-gould-1ee408` worktree'sinde kaldı.

Bu bir mantık kavgası değil; aynı repo ailesi içinde farklı worktree/snapshot okunmasıdır.

---

## 3. Canonical workspace kuralı

Kullanıcı aksi açıkça söylemedikçe MITAS için canonical çalışma alanı:

```text
E:\MITAS
```

Kalıcı kural:

- Kod analizi, audit ve test sonucu öncelikle `E:\MITAS` için raporlanır.
- `.claude/worktrees/...` altındaki değişiklikler izole çalışma kopyasıdır.
- Bir worktree'de yapılan değişiklik ana `E:\MITAS` içine otomatik geçmez.
- Bir düzeltme `.claude/worktrees/...` altında yapıldıysa raporda "ana workspace'e taşındı" denemez.
- Ana workspace'e taşımak gerekiyorsa patch açıkça port edilir, sonra `E:\MITAS` içinde doğrulanır.

---

## 4. Başlamadan önce zorunlu kontrol

Yeni Claude / Opus / Codex oturumu MITAS koduna dokunmadan önce şu kontrolleri yapmalı:

```powershell
Get-Location
git worktree list
git status --short
git -C E:\MITAS status --short
```

ASR audit gibi sembol bazlı bir işte ayrıca:

```powershell
rg -n "def _select_fallback_result|tail_gap_uncovered|error_flags|evidence_ids=\[module_run_id\]|def _segment_confidence|CRITICAL_FALLBACK_DROP_PREFIXES|_MODEL_CACHE_LOCK|multilingual: bool" E:\MITAS\core E:\MITAS\tests
```

Rapor verirken mutlaka şu üç bilgiyi yaz:

```text
cwd:
branch:
degisiklik ana E:\MITAS icinde mi, yoksa .claude/worktrees icinde mi:
```

---

## 5. 2026-05-14 tespit tablosu

| Konu | `E:\MITAS` ana workspace | Temiz `HEAD` / eski snapshot | `.claude/worktrees/awesome-gould-1ee408` |
|---|---|---|---|
| `_select_fallback_result` (both-unsafe dürüst raporlama) | Var (HIGH-1 fix uygulandı — DONE-ASR-002) | Yok | Yok / eski akış |
| Tail-gap detection (dinamik eşik) | Var (HIGH-3 fix uygulandı — DONE-ASR-002) | Yok | Yok |
| `summary.quality_report.error_flags` (prefix-only) | Var (MED-1 fix uygulandı — DONE-ASR-002) | Yok | Yok |
| `TimelineEvent` üretimi (`evidence_ids=[]`, `source_chunk_index`) | Var (MED-3 + LOW-2 fix uygulandı — DONE-ASR-002) | Yok | Yok |
| `channel_merge.py` (`_union_ratio_bound`) | Var, untracked (MED-6 fix uygulandı — DONE-ASR-002) | Yok | Yok |
| `multilingual=True` düzeltmesi | Uygulandı (DONE-ASR-001) | Yok | Var |
| `_MODEL_CACHE_LOCK` düzeltmesi | Uygulandı (DONE-ASR-001) | Yok | Var |
| fallback prefix genişletme | Uygulandı (DONE-ASR-001) | Yok | Var |
| `speech_seconds` magic clamp temizliği | Uygulandı (DONE-ASR-001) | Yok | Var |
| `condition_on_previous_text=False` (Karar 27) | Uygulandı (DONE-ASR-003) | Yok | Yok |

Bu tablo zamanla değişebilir. Değiştiğinde bu dosya güncellenmeli.

---

## 6. Port edilmesi gereken izole düzeltmeler

> **Durum: Tümü 2026-05-14 ana `E:\MITAS` workspace'e port edildi (DONE-ASR-001). Kayıt arşiv niteliğinde tutulur.**

Opus/Claude tarafında `awesome-gould-1ee408` worktree'sinde görülen ve sonra ana workspace'e port edilen net düzeltmeler:

1. `core/pipelines/asr/models.py` — **port edildi (DONE-ASR-001)**
   - `TranscribeParams.multilingual: False -> True`
   - Karar 14 ile uyumlu.

2. `core/pipelines/asr/models.py` — **port edildi (DONE-ASR-001)**
   - `_MODEL_CACHE_LOCK = Lock()`
   - `load_model()` ve `clear_model_cache()` lock ile korunur.

3. `core/pipelines/asr/transcribe.py` — **port edildi (DONE-ASR-001)**
   - `CRITICAL_FALLBACK_DROP_PREFIXES` içine `very_low_logprob_short_text` ve `multi_signal_low_quality` eklendi.

4. `core/pipelines/asr/transcribe.py` — **port edildi (DONE-ASR-001)**
   - Production `_run_single_pass()` içinde `speech_seconds = max(..., 1.0)` magic clamp kaldırıldı.

Tüm port'lar `cd /e/MITAS && venvs/core/Scripts/python.exe -m pytest tests/ -q` ile 166 passed, 6 skipped olarak doğrulandı (TEST-ASR-AUDIT-001).

---

## 7. Raporlama disiplini

Bir LLM yardımcı şu cümlelerden kaçınmalı:

- "Bu branch'te yok"  
  Önce hangi branch/worktree olduğunu belirt.

- "Uyguladım"  
  Önce hangi dizine uygulandığını belirt.

- "Testler geçti"  
  Testin hangi `cwd` içinde koştuğunu ve ana workspace'e karşı mı yoksa izole worktree'ye karşı mı olduğunu yaz.

Doğru rapor formatı:

```text
Kontrol edilen workspace: E:\MITAS
Branch: master
Durum: dirty/uncommitted
Degisiklik: ana workspace'e uygulandı / sadece izole worktree'de kaldı
Test: <komut>, <sonuc>
```

---

## 8. Ne yapılacak?

Bu dosya, ileride aynı karışıklığı önlemek için kalıcı takip noktasıdır.

Yakın aksiyon:

- Ana `E:\MITAS` workspace'i canonical kabul edilecek. **(Aktif kural — `00_BURADAN_BASLA.md` §0)**
- ~~Opus worktree'sindeki 4 küçük düzeltme gerekiyorsa ana workspace'e port edilecek.~~ **(2026-05-14 tamamlandı, DONE-ASR-001.)**
- ~~Ana workspace'te gerçekten var olan ASR v0.1 bug'ları ayrıca ele alınacak.~~ **(2026-05-14 tamamlandı, DONE-ASR-002 — 9 audit fix + drop-first sırası + 3 test rebalance.)**
- Her agent raporunda `cwd` ve worktree durumu açıkça yazılacak.

Devam eden iş: ASR audit kapanışı sonrası açık takip kalemleri için `mutfak/05_AKTIF_GOREV.md` §0 canlı panosuna bakınız.

