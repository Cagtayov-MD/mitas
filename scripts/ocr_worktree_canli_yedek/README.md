# OCR-worktree CANLI dosya yedekleri (izlenebilirlik)

`OCR-worktree/py` .gitignore'lu ama ÜRETİM bu dosyaları çalıştırıyor
(`_pipe_ocr.py` → `PY_OCR_DIR`). Oradaki canlı fix'ler commit'lenemediği için
SHA-izlenebilir kopyaları buraya alınır. **Çalışan kod OCR-worktree'dekidir** —
bu klasör salt yedek/diff kaynağıdır; geri yükleme: kopyala → OCR-worktree/py/.

- 20260601_stitch.py — FIX 2 KOLON-KURTARMA (2026-07-04): co_texts() ikinci-kolon emit,
  MITAS_STITCH_COLRESCUE (default ON). Kanıt: SINIR ÇİZGİSİ cast 10/10 gerçek oyuncu.
- 20260601_clean.py — CJK/Hangul tek-token istisnası (2026-07-03), classify().
