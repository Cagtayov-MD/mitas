# Council MCP Server

VİTOS/MİTAS teknik kararları için Claude Code'dan birden fazla modele
(Gemini, Qwen, GLM, GPT) aynı anda danışmanı sağlayan yerel MCP server.

Şu an sadece **Gemini 3.5 Flash** aktif. Diğer üçü kodda hazır, key
eklediğinde otomatik devreye girer - kod değişikliği gerekmez.

## 1. Kurulum

```bash
cd council_mcp
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## 2. Key'i tanımla

```bash
copy .env.example .env
```

`.env` dosyasını aç, `GEMINI_API_KEY=` satırının sağına kendi key'ini
yapıştır. Bu dosya asla git'e gitmez (`.gitignore`'da tanımlı).

## 3. Claude Code'a bağla

Council klasörünün tam yolunu kullanarak:

```bash
claude mcp add council -- python "C:\tam\yol\council_mcp\server.py"
```

Bağlantıyı doğrulamak için Claude Code içinde:

```
/mcp
```

`council` listede görünmeli ve bağlı (connected) durumda olmalı.

## 4. Kullanım

Claude Code'da normal konuşurken:

> "VİTOS'ta face clustering için HDBSCAN yerine başka bir yöntem
> düşünmeli miyiz, council'a sor."

Claude otomatik olarak `ask_council` aracını çağırır, şu an sadece
Gemini'den cevap gelir. Yanıtın başında hangi üyelerin cevap verdiği
yazar - key eklemediğin modeller listede görünmez, hata da vermez.

## 5. Yeni bir council üyesini aktif etme (örn. Qwen)

1. Alibaba Cloud Model Studio'dan Qwen API key'ini al.
2. `providers/qwen.py` içindeki `DEFAULT_BASE_URL`'in senin hesabının
   bölgesiyle (uluslararası/Çin) uyuştuğunu kontrol et - uyuşmuyorsa
   `.env`'e `QWEN_BASE_URL=...` ekleyerek override et.
3. `.env` dosyasına `QWEN_API_KEY=...` yaz.
4. Başka bir şey yapmana gerek yok - `server.py` içindeki
   `COUNCIL_MEMBERS` sözlüğü zaten Qwen'i içeriyor, `is_configured()`
   key'i görünce otomatik devreye girer.

GLM-5.2 için aynı adımlar, sadece `providers/glm.py`'deki
`DEFAULT_BASE_URL` notunu oku - o da doğrulama istiyor.

GPT-5.5 için doğrulama gerekmiyor, endpoint sabit ve resmi - sadece
`OPENAI_API_KEY`'i `.env`'e ekle, yeter.

## 6. Davranış kuralları (kilitli - VİTOS proje kararlarıyla tutarlı)

- Bir model timeout/hata verirse: 2 kez otomatik tekrar dener (üstel
  bekleme ile), üçü de başarısız olursa net bir hata mesajı döner.
- Key'i tanımlı olmayan üyeler sessizce atlanır, hata üretmez.
- `ask_council` bilinçli/manuel bir araç - Claude her teknik soruda
  otomatik çağırmaz, sen ne zaman ikinci bir görüş istediğini
  belirtmelisin.

## 7. Notlar / ileride yapılacaklar

- GLM-5.2 MIT lisanslı açık ağırlıklı - istersen ileride RTX Pro 6000
  üzerinde yerel olarak (vLLM ile) barındırıp `GLM_BASE_URL`'i yerel
  endpoint'e çevirebilirsin, API maliyetinden tamamen kurtulursun.
- Qwen ve GLM'in base URL'leri bu dosyaların yazıldığı tarihte
  (Temmuz 2026) doğrulanmış genel adresler - sağlayıcı tarafında
  değişmiş olabilir, key eklemeden önce güncel dokümantasyonlarından
  teyit et.
