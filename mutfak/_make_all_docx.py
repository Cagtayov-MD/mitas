# -*- coding: utf-8 -*-
"""MITAS: 3 Word belgesi. (1) kompakt model envanteri 2 sutun, (2) profiller, (3) detayli jenerik raporu."""
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.table import WD_TABLE_ALIGNMENT

NAVY  = RGBColor(0x16,0x31,0x5C)
BLUE  = RGBColor(0x1F,0x4A,0x7A)
WHITE = RGBColor(0xFF,0xFF,0xFF)
LABEL = RGBColor(0x33,0x44,0x5E)
EXCLR = RGBColor(0x4A,0x55,0x68)
BODY  = RGBColor(0x22,0x2B,0x36)
SOFT  = RGBColor(0x4D,0x58,0x68)
GREY  = RGBColor(0x6B,0x7A,0x92)
PLAN  = RGBColor(0x9A,0x57,0x12)
FONT  = "Segoe UI"

def shade(par, fill):
    pPr = par._p.get_or_add_pPr()
    shd = OxmlElement('w:shd'); shd.set(qn('w:val'),'clear'); shd.set(qn('w:fill'),fill)
    pPr.append(shd)

def bborder(par, color, sz=10):
    pPr = par._p.get_or_add_pPr()
    pbdr = OxmlElement('w:pBdr'); b = OxmlElement('w:bottom')
    b.set(qn('w:val'),'single'); b.set(qn('w:sz'),str(sz)); b.set(qn('w:space'),'2'); b.set(qn('w:color'),color)
    pbdr.append(b); pPr.append(pbdr)

def two_cols(doc, space=340):
    sectPr = doc.sections[0]._sectPr
    cols = sectPr.find(qn('w:cols'))
    if cols is None:
        cols = OxmlElement('w:cols'); sectPr.append(cols)
    cols.set(qn('w:num'),'2'); cols.set(qn('w:space'),str(space))

def setup(doc, margin=1.3):
    s = doc.sections[0]
    s.page_width = Cm(21.0); s.page_height = Cm(29.7)
    s.top_margin = Cm(margin); s.bottom_margin = Cm(margin); s.left_margin = Cm(margin+0.2); s.right_margin = Cm(margin+0.2)
    nrm = doc.styles['Normal']; nrm.font.name = FONT; nrm.font.size = Pt(9.5); nrm.font.color.rgb = BODY
    pf = nrm.paragraph_format; pf.space_before = Pt(0); pf.space_after = Pt(1); pf.line_spacing = 1.0

def run(p, text, size, color=BODY, bold=False, italic=False, mono=False):
    r = p.add_run(text); r.font.size = Pt(size); r.font.color.rgb = color
    r.font.bold = bold; r.font.italic = italic; r.font.name = "Consolas" if mono else FONT
    return r

# ===================== BELGE 1: KOMPAKT ENVANTER (2 SUTUN) =====================
def build_envanter():
    doc = Document(); setup(doc, 1.1)
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(1)
    run(p, "MITAS — Model Envanteri", 15, NAVY, bold=True)
    p2 = doc.add_paragraph(); p2.paragraph_format.space_after = Pt(4)
    run(p2, "Tüm modeller tek bakışta · 3 Haziran 2026 · planlı modüller (Müzik / Yüz / Sahne) sonda", 8, GREY, italic=True)
    two_cols(doc, 360)

    def csec(t):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(5); p.paragraph_format.space_after = Pt(1); p.paragraph_format.keep_with_next = True
        run(p, t, 10, NAVY, bold=True); bborder(p, '2A6EA3', 6)
    def cmodel(name, desc):
        p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(2); p.paragraph_format.space_after = Pt(3); p.paragraph_format.keep_together = True
        run(p, name, 9.5, NAVY, bold=True); p.add_run().add_break()
        run(p, desc, 7.7, SOFT)

    GROUPS = [
     ("1 · ASR — Konuşmayı Yazıya", [
      ("faster-whisper large-v3-turbo", "Ana konuşma tanıma motoru; sesi hızlıca metne çevirir (gerçek zamanın ~25 katı)."),
      ("faster-whisper large-v3", "Kalite öncelikli ağır model; sadece riskli parçaları yeniden çözen seçici onarım."),
      ("Silero VAD", "Seste konuşmanın nerede olduğunu bulur; sessiz ve müzikli bölgeleri ayıklar."),
      ("WhisperX", "Her kelimenin tam kaçıncı saniyede söylendiğini bulur (kelime düzeyi zaman damgası)."),
      ("pyannote-audio", "Konuşmacı ayrımı: kim, ne zaman konuştu (SPEAKER_00/01…)."),
      ("SpeechBrain dil tanıma", "Sesin hangi dilde olduğunu tespit eder (tr/ar/az/ku… 107 dil)."),
      ("DeepFilterNet", "Arka plan gürültüsünü/müziğini konuşmadan ayırır. (planlı/kısmi)"),
      ("Özel İsim Düzeltme", "ASR'ın yanlış yazdığı bilinen özel adları kural tabanlı düzeltir."),
      ("Tahmini Kelime Zamanlama", "WhisperX başarısızsa kelime zamanını tahminle üretir (yedek)."),
     ]),
     ("2 · Çeviri — Yabancı Dili Türkçeye", [
      ("OPUS-MT (EN→TR)", "İngilizceden Türkçeye hızlı ve kaliteli çeviri uzmanı."),
      ("NLLB-200-3.3B", "200 dilden Türkçeye çeviren çok dilli ana model (özellikle Arapça)."),
      ("Arapça Lehçe Normalizasyonu", "Lehçeleri standart Arapçaya çevirip çeviri kalitesini yükseltir."),
      ("NLLB-200-1.3B", "3.3B modelin küçük ve hızlı versiyonu (yedek, rotaya bağlı değil)."),
     ]),
     ("3 · OCR & Görsel-Dil — Ekran Yazısı", [
      ("PaddleOCR", "Ana OCR motoru; karelerden metin kutusu bulup içini okur."),
      ("OneOCR", "Windows'un OCR motoru; birincil motor bozulunca devreye giren yedek."),
      ("qwen2.5vl — Bekçi / GÖZ", "OCR yapmaz, karar verir: jenerik mi film mi? Yanlış kareyi OCR'a sokmaz."),
      ("GLM-OCR", "Hızlı görsel-dil OCR; kırpılmış metni temiz okur (kıyaslama kazananı)."),
      ("InternVL3-8B", "Zor Türkçe jenerikleri en iyi okuyan görsel-dil modeli."),
      ("LocateAnything-3B", "Metnin yerini (kutu) bulur; GLM-OCR ile okutulur."),
      ("MiniCPM-V 2.6", "Görüntüden Türkçe metin çıkaran görsel-dil modeli (3. sıra)."),
      ("Tesseract", "Klasik, kütüphanesiz OCR; karşılaştırma adayı. (planlı)"),
     ]),
     ("4 · Üst Denetim & Özet — LLM", [
      ("Claude (Sonnet)", "Transcript'ten özet ve film/dizi künye metni üretir (özet motoru)."),
      ("Kimi-K2.6", "En güçlü denetim adayı; özel isim/bağlam hatalarını yakalar."),
      ("Gemma-4-26b", "Varsayılan denetim modeli; hata/şüphe için aksiyon önerir, metni ezmez."),
      ("Qwen3.6-27b", "En dengeli bağlam ayrımı; ikinci görüş / hakem."),
      ("Qwen3-30b-a3b", "Qwen 27B'nin daha hızlı alternatifi."),
      ("Llama-3.3-70b", "Yüksek riskli kararların temkinli son hakemi."),
      ("Nemotron-3-nano-omni", "Kare/künye kanıtını okuyan çok modlu model. (planlı)"),
      ("qwen3-vl", "Videoya soru sorup cevap almak için görsel-dil modeli."),
     ]),
     ("5 · Müzik Tanıma (planlı)", [
      ("Repertuvar Bankası", "Eser/sanatçı sözlüğü — TRT Müzik Kütüphanesi'nin temeli."),
      ("ASR Anons Parser", "Sunucu anonsundan eser+sanatçı çıkarır."),
      ("PANNs CNN14", "Sesi konuşma/müzik/alkış olarak ayırır; şarkı sınırını bulur."),
      ("Demucs", "Vokali ayırıp şarkı sözünden eseri bulur (ileri aşama)."),
      ("Chromaprint + AcoustID", "Akustik parmak izi; birincil değil doğrulayıcı katman."),
     ]),
     ("6 · Altyapı Araçları", [
      ("ffmpeg", "Videodan ses/kare çıkarır, format çevirir — her modülün giriş kapısı."),
      ("ffprobe", "Medya künyesini okur: süre, kanal sayısı, codec."),
      ("PyTorch + CUDA", "GPU üzerinde derin öğrenme hesabının temel altyapısı."),
      ("CTranslate2", "ASR/çeviri modellerini düşük bellekte hızlı çalıştıran motor."),
      ("ONNX Runtime", "ONNX modellerini GPU'da çalıştırır (yüz tanıma motoru)."),
      ("OpenCV", "Görüntü işleme tabanı: hız ölçümü, hareket takibi, keskinlik."),
      ("Venv izolasyonu", "Her modül ayrı ortamda çalışır; biri diğerini bozmaz."),
     ]),
     ("7 · Yüz Tanıma (planlı)", [
      ("InsightFace / buffalo_l", "Tek pakette yüz tespiti + 512 boyutlu kimlik vektörü."),
      ("SCRFD", "Karelerde yüzleri hızla tespit eder."),
      ("ArcFace", "Hizalanmış yüzü kimlik vektörüne çevirir."),
      ("ByteTrack", "Aynı yüzü ardışık karelerde tek kimlikle takip eder."),
      ("HDBSCAN", "Yüz izlerini kişi bazlı gruplara ayırır (kümeleme)."),
      ("pgvector", "Kimlik vektörlerini saklayıp hızlı arar (kişi bankası)."),
     ]),
     ("8 · Sahne / Cisim Tanıma (planlı)", [
      ("YOLO-World", "Serbest sözlükle nesne/ortam tespiti (kürsü, mikrofon, bayrak)."),
      ("SigLIP", "Sahne atmosferini skorlar (stüdyo / açık alan / gece)."),
      ("PySceneDetect", "Videoyu sahnelere böler; anahtar kare üretir."),
      ("GroundingDINO + RAM", "Yedek nesne dedektörü + etiket sözlüğü keşfi."),
     ]),
    ]
    for st, models in GROUPS:
        csec(st)
        for n, d in models:
            cmodel(n, d)
    csec("9 · Denendi ve Elendi")
    for n, why in [
        ("EasyOCR", "PaddleOCR'a göre net kazanç yok; sürücü/DLL riski."),
        ("deepseek-ocr", "Tam başarısız; yazı yerine \"/\" döndürdü."),
        ("LLaVA-NeXT-Video", "Kıyaslamada yetersiz."),
        ("granite-3.2-8b", "Bağlam tuzaklarına düştü."),
        ("glm-4.7-flash", "Uzun düşünme, eksik çıktı."),
        ("qwq-32b", "Format sorunu, agresif değiştirme."),
        ("gpt-oss-20b", "Bu görevde zayıf."),
        ("mistral-nemo", "Politika tutarsız."),
        ("Qwen3-14B", "Değiştirme çok agresif."),
        ("qwen3.6:35b (yerel)", "Özet formatını tutmadı → Claude'a geçildi."),
        ("qwen2.5-vl (metin)", "Metin testinde döngü; görsel/bekçi rolünde başarılı."),
    ]:
        cmodel(n, why)
    doc.save(r"E:\MITAS\mutfak\MITAS_Model_Envanteri.docx")
    print("OK envanter")

# ===================== BELGE 2: PROFILLER =====================
def build_profil():
    doc = Document(); setup(doc, 1.4)
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(1)
    run(p, "MITAS — İçerik Profilleri", 17, NAVY, bold=True)
    p2 = doc.add_paragraph(); p2.paragraph_format.space_after = Pt(6)
    run(p2, "Her içerik türünde hangi soruları soruyoruz, sistem bunları nasıl cevaplıyor · 3 Haziran 2026", 9, GREY, italic=True)
    p3 = doc.add_paragraph(); p3.paragraph_format.space_after = Pt(8)
    run(p3, "Turuncu işaretli satırlar henüz yazılmamış, planlı yeteneklerdir; diğerleri çalışır durumdadır.", 8.5, PLAN, italic=True)

    def psec(t):
        pp = doc.add_paragraph(); pp.paragraph_format.space_before = Pt(10); pp.paragraph_format.space_after = Pt(3); pp.paragraph_format.keep_with_next = True
        run(pp, t, 14, NAVY, bold=True); bborder(pp, '1F4A7A', 10)
    def qa(q, a, plan=False):
        pq = doc.add_paragraph(); pq.paragraph_format.space_before = Pt(4); pq.paragraph_format.space_after = Pt(0); pq.paragraph_format.keep_with_next = True
        run(pq, q, 10, NAVY, bold=True, italic=True)
        pa = doc.add_paragraph(); pa.paragraph_format.space_after = Pt(1); pa.paragraph_format.left_indent = Cm(0.5)
        run(pa, "→ ", 9.3, (PLAN if plan else SOFT), bold=True)
        run(pa, a, 9.3, (PLAN if plan else BODY), italic=plan)

    psec("Film / Dizi")
    qa("1. Film kaç ses kanalından oluşuyor?", "ffprobe dosya künyesini okur: mono / stereo / çok kanal.")
    qa("2. Ses kanalları birbirinden farklı içerik mi taşıyor?", "ASR stereo karşılaştırma katmanı L ve R'yi korelasyon + Mid/Side dB ile ölçer; aynıysa tek kanal işler, farklıysa ikisini ayrı transkript eder.")
    qa("3. Filmin ana dili nedir?", "SpeechBrain dil tanıma 107 dil içinden klibin ana dilini bulur (tr / en / ar / az…).")
    qa("4. Film altyazılı mı (ekrana gömülü altyazı var mı)?", "Planlı: ekrana gömülü altyazı tespiti şu an yok; ileride OCR alt-bant taramasıyla eklenebilir.", True)
    qa("5. Filmin giriş ve çıkış jeneriği nerede başlar, nerede biter?", "Bekçi (görsel-dil modeli) kareye bakıp jenerik mi / film mi ayırır; jenerik aralığının sınırını verir.")
    qa("6. Jenerik tipi nedir?", "Bekçi + hareket ölçümü akan/duran ve sabit/hareketli zemin ayrımını yapıp doğru birleştirme yöntemini seçer.")
    qa("7. Cast'taki isimleri düzgün nasıl okuruz?", "Jenerik tek temiz görüntüye birleştirilir, sonra OCR okur (PaddleOCR; zorlanınca OneOCR / görsel-dil modelleri). İlke: okunamayanı yanlış okumaktansa \"okunamadı\" denir.")
    qa("8. Özet tutarlı mı, dil bilgisine uygun mu?", "Claude/Sonnet özet motoru transcript'ten dilbilgisine uygun, tutarlı Türkçe künye/özet üretir.")
    qa("9. Filmde yabancı dil sahneleri var mı, çeviri gerekiyor mu?", "Dil tanıma yabancı segmenti işaretler, çeviri motoru (OPUS / NLLB) Türkçeye çevirir.")
    qa("10. Filmde yüz tanıma yapıyor muyuz?", "Hayır. Karar gereği filmde kimlik kapalı; sadece \"yüz var\" bilgisi tutulur, isim jenerikten gelir.")

    psec("Stüdyo Programları")
    qa("1. Program kaç ses kanalından oluşuyor?", "ffprobe kanal sayısını okur: mono / stereo / çok kanal.")
    qa("2. Ses kanalları farklı kişilerin konuşmaları mı (transkript için kıymetli)?", "ASR stereo karşılaştırma katmanı kanalların farklı içerik taşıyıp taşımadığını ölçer; farklıysa her kanalı ayrı transkript eder.")
    qa("3. Kim ne zaman konuştu (zaman damgası)?", "pyannote konuşmacı ayrımı (SPEAKER_00/01…) + WhisperX kelime düzeyi zaman damgası.")
    qa("4. Ne zaman sessizlik oldu?", "Silero VAD konuşma aralıklarını verir; aralarda kalan boşluklar sessizlik/müzik olarak işaretlenir.")
    qa("5. Programın giriş ve çıkış jeneriği nerede başlar, nerede biter?", "Bekçi jenerik / program ayrımını yapıp sınırı verir.")
    qa("6. Jenerik tipi nedir?", "Bekçi + hareket ölçümü doğru birleştirme yöntemini seçer.")
    qa("7. Yapım ekibi isimlerini düzgün nasıl okuruz?", "Jenerik birleştirilip OCR ile okunur (PaddleOCR + zor durumda OneOCR / görsel-dil modelleri).")
    qa("8. Konuşmacılar kim, yüz bankasında mevcut mu?", "Planlı (Yüz Tanıma): yüz tespiti + kimlik vektörü; kişi bankasında en yakın kişi aranır, onay olmadan kesin kimlik atanmaz.", True)
    qa("9. Ekranda konuşmacı künyesi (KJ) ne zaman göründü?", "Planlı: alt bant sürekli OCR ile taranır; KJ'nin belirme/kaybolma anları zaman damgalı işaretlenir.", True)
    qa("10. Sürekli (sabit) KJ'lerde neler yazıyor?", "Planlı: alt-bant OCR; program adı, konuşmacı adı-unvanı gibi sabit künye metinleri çıkarılır.", True)
    qa("11. Program boyunca VTR girdi mi?", "Planlı: sahne bölme + içerik değişimiyle stüdyodan hazır video pakete (VTR) geçişler tespit edilir.", True)
    qa("12. VTR'lerde neler mevcut?", "Planlı: VTR segmentine ayrıca ASR + OCR + sahne tanıma uygulanır.", True)

    psec("Müzik Programları")
    qa("1. Program kaç ses kanalından oluşuyor?", "ffprobe kanal sayısını okur.")
    qa("2. Ses kanalları farklı kişilerin konuşmaları mı (transkript için kıymetli)?", "ASR stereo karşılaştırma katmanı kanalların farklı içerik taşıyıp taşımadığını ölçer; farklıysa ayrı transkript eder.")
    qa("3. Sesler ne kadar temiz; gürültülü yerde temiz sesi nasıl transkript ederiz?", "Silero VAD konuşma bölgelerini ayırır; ses temizleme (DeepFilterNet) planlı olarak arka plan müziğini/gürültüyü bastırıp konuşmayı öne çıkaracak.", True)
    qa("4. Programda şarkı blokları ne zaman başladı, ne zaman bitti?", "Planlı (PANNs ses sınıflandırma): sesi konuşma/müzik/alkış/sessizlik olarak ayırıp müzik bloklarının baş/bitiş sınırını verir.", True)
    qa("5. Programda çalan şarkıları kim seslendirdi?", "Planlı: önce ekran künyesi (KJ) ve sunucu anonsu okunur, Repertuvar Bankası ile eşleştirilip seslendiren bulunur; parmak izi doğrulayıcıdır.", True)
    qa("6. Programda çalan şarkıların bestesi kime ait?", "Planlı: Repertuvar Bankası eseri kanonik kaydına bağlar; besteci/söz yazarı bilgisi buradan gelir.", True)
    qa("7. Programın giriş ve çıkış jeneriği nerede başlar, nerede biter?", "Bekçi jenerik / program ayrımını yapıp sınırı verir.")
    qa("8. Jenerik tipi nedir?", "Bekçi + hareket ölçümü doğru birleştirme yöntemini seçer.")
    qa("9. Yapım ekibi isimlerini düzgün nasıl okuruz?", "Jenerik birleştirilip OCR ile okunur (PaddleOCR + zor durumda OneOCR / görsel-dil modelleri).")
    qa("10. Programdakiler kim, yüz bankasında mevcut mu?", "Planlı (Yüz Tanıma): yüz tespiti + kimlik vektörü; kişi bankasında aday eşleşme aranır.", True)
    qa("11. Ekranda künye (KJ) ne zaman göründü?", "Planlı: alt-bant sürekli OCR taraması; KJ belirme/kaybolma anları işaretlenir.", True)
    qa("12. Sürekli (sabit) KJ'lerde neler yazıyor?", "Planlı: alt-bant OCR; \"BESTE / GÜFTE / OKUYAN\" gibi künye alanları çıkarılır.", True)
    qa("13. Program boyunca VTR girdi mi?", "Planlı: sahne bölme + içerik değişimiyle VTR geçişleri tespit edilir.", True)
    qa("14. VTR'lerde neler mevcut?", "Planlı: VTR segmentine ASR + OCR + sahne tanıma uygulanır.", True)

    psec("Spor Yayınları")
    qa("1. Maç kaç ses kanalından oluşuyor?", "ffprobe kanal sayısını okur.")
    qa("2. Spiker sesi hangi kanalda, efekt (saha) sesi hangi kanalda?", "ASR stereo karşılaştırma katmanı kanalların farklı içerik taşıdığını tespit eder; spiker ile saha/efekt kanalı ayrıysa spiker kanalı ayrı ve temiz transkript edilir.")
    qa("3. Sesler ne kadar temiz; saha uğultusu/gürültü içinde nasıl transkript ederiz?", "Silero VAD spikerin konuştuğu anları ayırır; ses temizleme (DeepFilterNet) planlı olarak stadyum uğultusunu bastırıp spiker sesini öne çıkaracak.", True)
    qa("4. Maçta ne zaman KJ (skor/grafik bandı) girdi?", "Planlı: skor/grafik bandı bölgesi sürekli OCR ile taranır; bandın belirdiği anlar işaretlenir.", True)
    qa("5. Maçta grafikten skor takibini en verimli nasıl yaparız?", "Planlı: skor bandının sabit ekran bölgesi (ROI) belirli aralıklarla OCR ile okunur; yalnız skorun değiştiği anlar kaydedilir, böylece tüm kareyi okumadan verimli skor zaman çizelgesi çıkar.", True)

    doc.save(r"E:\MITAS\mutfak\MITAS_Icerik_Profilleri.docx")
    print("OK profil")

# ===================== BELGE 3: DETAYLI JENERIK RAPORU =====================
def build_jenerik():
    doc = Document(); setup(doc, 1.5)
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(1)
    run(p, "MITAS — Jenerik Okuma Stratejisi", 18, NAVY, bold=True)
    p2 = doc.add_paragraph(); p2.paragraph_format.space_after = Pt(8)
    run(p2, "Akan ve duran jeneriği okunabilir tek görüntüye dönüştürme: yöntemler, modeller, kanıtlar · 3 Haziran 2026", 9.5, GREY, italic=True)

    def H(t):
        pp = doc.add_paragraph(); pp.paragraph_format.space_before = Pt(11); pp.paragraph_format.space_after = Pt(3); pp.paragraph_format.keep_with_next = True
        run(pp, t, 14, NAVY, bold=True); bborder(pp, '1F4A7A', 10)
    def band(t):
        pp = doc.add_paragraph(); pp.paragraph_format.space_before = Pt(7); pp.paragraph_format.space_after = Pt(2); pp.paragraph_format.keep_with_next = True
        shade(pp, '16315C'); run(pp, "  " + t + "  ", 11.5, WHITE, bold=True)
    def para(text):
        pp = doc.add_paragraph(); pp.paragraph_format.space_after = Pt(3)
        run(pp, text, 9.6, BODY)
    def field(label, text):
        pp = doc.add_paragraph(); pp.paragraph_format.space_after = Pt(1); pp.paragraph_format.left_indent = Cm(0.2); pp.paragraph_format.keep_with_next = True
        run(pp, label + " ", 9.3, LABEL, bold=True); run(pp, text, 9.4, BODY)
    def bullet(text):
        pp = doc.add_paragraph(style="List Bullet"); pp.paragraph_format.space_after = Pt(0); pp.paragraph_format.left_indent = Cm(0.7)
        run(pp, text, 9.2, BODY)

    H("1 · Asıl Problem — Jenerik mi, Film mi?")
    para("Jenerikteki yazıyı OCR'a vermeden önce, kareler arasına dağılmış metni tek bir temiz görüntüye toplamak gerekir. Bunun için jeneriğin biçimini bilmek şarttır: yazı akıyor mu yoksa duruyor mu, arka plan sabit mi yoksa oynayan film mi? Reconstruction (görüntü kurma) tarafı çözüldü. Asıl çözülmesi gereken sorun şudur: bir segment gerçekten JENERİK mi, yoksa FİLM GÖRÜNTÜSÜ mü?")
    para("60 filmin tüm scroll segmentleri tarandığında ortaya çıktı ki: kamera/özne hareketi, sahte bir \"kayma hızı\" üretip yazısız film görüntüsünü \"akan jenerik\" gibi gösteriyor. Bakılan 5 düşük-parlaklık segmentin 5'i de aslında yazısız footage'dı. Üstelik karanlık oranı (dark_ratio) bu ayrımı yapmaya yetmiyor — gerçek jenerik de footage da aynı parlaklıkta olabiliyor. Sonuç: doğru segmenti doğru yönteme yollayan bir \"bekçi\" olmadan, en iyi birleştirme yöntemi bile footage'da çöp üretmeye mahkûm.")

    H("2 · Karar Matrisi")
    tbl = doc.add_table(rows=3, cols=3)
    tbl.alignment = WD_TABLE_ALIGNMENT.LEFT
    cells = [
        ["Jenerik biçimi", "Arka plan sabit (siyah/düz)", "Arka plan hareketli (oynayan film)"],
        ["Akan (scroll)", "KARAR 1 — Slit-Scan", "KARAR 3 — Satır-Yeniden-İnşa"],
        ["Duran kart", "KARAR 2 — Durağan Kart", "KARAR 2 (metin dedektörlü)"],
    ]
    widths = [Cm(4.2), Cm(6.4), Cm(6.4)]
    for ri, rowvals in enumerate(cells):
        for ci, val in enumerate(rowvals):
            c = tbl.rows[ri].cells[ci]; c.width = widths[ci]
            pp = c.paragraphs[0]; pp.paragraph_format.space_after = Pt(0)
            head = (ri == 0) or (ci == 0)
            r = run(pp, val, 8.8, (WHITE if ri==0 else NAVY) if head else BODY, bold=head)
            if ri == 0:
                shd = OxmlElement('w:shd'); shd.set(qn('w:val'),'clear'); shd.set(qn('w:fill'),'16315C'); c._tc.get_or_add_tcPr().append(shd)
            elif ci == 0:
                shd = OxmlElement('w:shd'); shd.set(qn('w:val'),'clear'); shd.set(qn('w:fill'),'EEF3F9'); c._tc.get_or_add_tcPr().append(shd)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)

    H("3 · Bekçi — Görsel-Dil Modeli (qwen2.5vl:7b)")
    para("Doğru yöntemi seçen katman, tek kareye bakıp \"bu jenerik mi, film mi?\" diyen yerel bir görsel-dil modelidir (Ollama üzerinde qwen2.5vl:7b). OCR yapmaz; sınıflandırır.")
    field("İş bölümü:", "GÖZ (model, 1 kare) görünümü yorumlar — yazı parlak mı, jenerik/film mi, kaç sütun, hangi dil, zemin tipi. MATEMATİK (2 kare arası dy) hareketi ölçer — bir model tek kareden hareketi bilemez, bu fizik. KOD ikisini birleştirip doğru motoru seçer.")
    field("Çıktı:", "Yapılandırılmış JSON — is_credits, motion_guess (scrolling/static_card), background (moving_scene/black_plain), columns, language, recommended_method. Sıcaklık 0; düşünme modu kapalı (/no_think — açıkken tekrar döngüsüne giriyor).")
    field("Kanıt:", "ANJELIK frame 750 (akan jenerik) → bright, columns=2, French, moving_scene; frame 60 (kadın yüzü) → is_credits=false. Bekçinin yapması gereken işi tam yaptı: testte 5/5 doğru ayırdı ve 3 ayrı dizide genelledi.")
    field("Kritik tasarım notu:", "Bekçi TÜM segmente değil, KARE-ARALIĞINA karar vermeli. Tek bir segment caption + cast-scroll + footage'ı iç içe taşıyabilir (Anjelik açılışı gibi).")

    H("4 · KARAR 1 — Slit-Scan (Photo-finish)")
    field("Kapsam:", "Akan (scroll) jenerik + sabit/siyah/düz-renk arka plan. Arşivde en sık görülen kapanış scroll'u.")
    field("Yöntem:", "Ardışık iki kare arasındaki dikey kaymayı cv2.phaseCorrelate ile ölç (Hann pencereli). v = round(|dy|). v < 1 ise akış durmuş, atla. v > 40 ise kesme/sıçrama, atla. Aksi halde sabit bir yatay çizgiden (ref = 0.55 × kare yüksekliği) v piksel yükseklikte bir şerit kes ve alt alta diz (np.vstack).")
    field("Neden çalışır:", "Sabit hızda her içerik satırı çizgiden tam bir kez geçer. Ortalama/harman yok — gerçek piksel kopyalanır, bu yüzden her satır master'da tam bir kez ve keskin görünür; bulanıklık olmaz.")
    field("Doğrulanmış parametreler:", "SLIT_FRAC = 0.55; maskesiz tam-kare phaseCorrelate; v<1 atla; v>40 atla; harman / OCR / dedup YOK.")
    field("Kanıt:", "X-MEN (2000) kapanışı: 3240 kare → 2328 şerit, medyan hız 8.4 piksel/kare → 854 × 19.846 piksel master. İki sütun (rol + isim) hizalı, her satır TEK, keskin, hayalet yok.")
    para("Bu kutuda denenip elenen yöntemler aşağıdaki 9. bölümde listelenmiştir (NCC overlap-template, OCR satır-dedup, optik akış harmanı, sabit şerit yüksekliği).")

    H("5 · KARAR 2 — Durağan Kart Yakalama")
    field("Kapsam:", "Akmayan, ekranda birkaç saniye duran isim kartları (açılış cast kartları gibi).")
    field("Yöntem A (ham kareden):", "Top-hat morfolojiyle (cv2.morphologyEx, MORPH_TOPHAT) yazı maskesi çıkar → kayma yoksa (|dy| < 1.5) \"kart tutuluyor\" (held-run). Held-run'ın en keskin karesini seç (max cv2.Laplacian varyansı). Yazı bölgesi farkı sıçradığında yeni kart (swap). Bitişik kartları yazı bandı NCC ≥ 0.97 ile tekille.")
    field("Yöntem B (pipeline):", "PaddleOCR metin dedektörü her karedeki kutuları bulur → box_tracker kümeler → her benzersiz kart için en iyi kare + dikey aralık (y_range) render edilir. Gerçek metin dedektörü kullandığı için arka-plan bağımsızdır.")
    field("Doğrulanmış parametreler:", "STATIC_DY = 1.5; TB_SWAP = 22 (yazı-bölgesi fark eşiği); MIN_HOLD = 5 kare; DOMINANT_BG_MIN = 0.42; dedup yazı bandı NCC ≥ 0.97.")
    field("Kanıt:", "SON METRO açılışı (kırmızı kartlar): Yöntem A → 28 kart, cast + ekip tam; Yöntem B → 29 parça, temiz. İkisi de iyi. ANJELIK açılışı (hareketli zemin): A top-hat → giriş metni 7× tekrar; A metin-dedektörlü → cast kayboldu; B (pipeline) → cast + ekip ayrı ayrı temiz.")
    field("Karar:", "Sabit arka plan → A veya B (ikisi de net). Hareketli arka plan → SADECE B; çünkü hareketli zeminde \"bu yazı mı?\" ayrımı gerçek metin dedektörü ister, A'nın kare-bazlı held-run'ı flicker'da kırılıyor.")

    H("6 · KARAR 3 — Hareketli Zemin Üzerinde Akan Jenerik")
    para("En zor kutu: yazı akıyor AMA arka plan siyah değil, oynayan film (yüz, manzara, sahne). İki bağımsız yol da çalışıyor.")
    band("YOL 1 — Pipeline Satır-Yeniden-İnşa (row_composite)")
    field("Nasıl:", "Kümülatif optik akış (Lucas-Kanade; cv2.goodFeaturesToTrack + cv2.calcOpticalFlowPyrLK) ile yazının kayma miktarı ölçülür. Cruise-speed bootstrap (ilk karelerin medyan hızı), EMA stabilizasyon ve band-clamp ile aykırı değerler kırpılır. Yazı metin olarak takip edildiği için şeritler temiz oturur; arka plandaki film tutarsız olduğu için birikemez, zararsız dikey bulanıklığa dönüşüp silinir.")
    field("Kanıt:", "2014 \"Duck You Sucker\" (Leone) kapanışı: dark 0.753, dy −26.2, 126 satır, hayalet cezası 0.0 → TEMİZ (tüm cast her isim bir kez, footage bulanıklaştı). 2016 Marie Curie kapanışı: dark 0.797, dy −5.6, 41 satır, kalite 0.94.")
    band("YOL 2 — Ham Kareden Maskeli-Hız Slit-Scan")
    field("Nasıl:", "Pipeline'sız, ham kareden çalışır. Top-hat maskeyle SADECE yazı pikselleri seçilir, hız maskeli cv2.phaseCorrelate ile yalnız yazıdan ölçülür (oynayan zemin yok sayılır). Sabit çizgiden v-yükseklik şerit alınıp dizilir. Master üstünde top-hat + parlaklık eşiğiyle yazı saf siyaha taşınarak temiz-zemin katmanı üretilir.")
    field("Neden çalışır (fizik):", "Yazı kendi hızında hizalanır → ardışık şeritler yazıda tam örtüşür → her satır tek ve keskin. Aynı şeritlerde deniz/zemin hizasız → ortalanıp bulanık washa döner → silinir. Doğru hızda tarama yazıyı odakta, zemini defokus yapar.")
    field("Kanıt:", "ANJELIK end_credits 600–900 (301 kare, oynayan deniz + yelkenli üstünde Fransızca iki sütun, ~9 px/kare): 293 şerit → 600 × 2773 master, tüm kadro her satır bir kez keskin, oynayan deniz kendiliğinden silindi.")
    field("Sınır:", "Parlak-yazı varsayımı (koyu yazıda temiz-zemin katmanı çöker; o zaman yalnız slit-scan master'ı kullanılır). Zemin yazıyla aynı hız+yönde hareket ederse (nadir) ayrım düşer. Yazısız footage konursa yine çöp → bekçi şart.")

    H("7 · Kullanılan Görüntü İşleme Teknikleri (OpenCV)")
    bullet("cv2.phaseCorrelate — iki kare arasındaki kayma/scroll hızını (dy) ölçer; slit-scan'in kalbi.")
    bullet("cv2.calcOpticalFlowPyrLK + cv2.goodFeaturesToTrack — Lucas-Kanade seyrek optik akış; hareketli zeminde yazının kümülatif kaymasını takip eder.")
    bullet("cv2.morphologyEx (MORPH_TOPHAT) — ince parlak yazı strokelarını arka plandan ayıran yazı maskesi.")
    bullet("cv2.connectedComponentsWithStats — geniş+kısa blobları (yazı satırlarını) film bloblarından ayırır.")
    bullet("cv2.Laplacian varyansı — en keskin kareyi seçer (durağan kart için).")
    bullet("Hann penceresi — phaseCorrelate öncesi kenar etkisini bastırır.")
    bullet("cv2.imencode / np.fromfile — Türkçe-İ içeren Windows yollarında okuma/yazma tuzağını aşar.")

    H("8 · OCR Motor Zinciri (birleştirilmiş görüntü okunurken)")
    field("Birincil:", "PaddleOCR (PP-OCRv5) — tespit + tanıma; çok uzun master'lar dikey dilimlere bölünerek okunur.")
    field("Yedek:", "OneOCR (Windows) — PaddleOCR \"garble\" (anlamsız) ürettiğinde devreye girer.")
    field("Görsel-dil okuyucular:", "GLM-OCR (hızlı, kırpıntı okur, kıyaslama kazananı) + InternVL3-8B (zor Türkçe karakterleri en iyi okuyan). LocateAnything-3B metin kutularını bulup GLM-OCR'a okutur. MiniCPM-V 2.6 üçüncü sırada.")
    field("İlke:", "Okunamayan yeri yanlış okumaktansa \"okunamadı\" denir; stroke kalınlığı/parlaklık eşiğinin altındaki metin OCR'a sokulmaz, kimlik-teyit yoluna düşer.")

    H("9 · Denenip Elenen Birleştirme Yöntemleri")
    bullet("Overlap-Template (NCC, motor A): yoğun iki sütunlu küçük metinde eşleşme belirsizleşir → hayalet/çift satır.")
    bullet("OCR Satır-Dedup (motor D): iki sütunda rol (sol) ve ismi (sağ) ayrı satır sanıp her satırı 2× basar (ghosting); ayrıca yavaş.")
    bullet("Optik-Akış + Medyan Harman (motor B): ortalama küçük metni bulanıklaştırır; parlaklık kapısı beyaz-siyah scroll'da boş bırakır.")
    bullet("Sabit şerit yüksekliği (eski slit-scan, SLIT_H=8): gerçek hız 8 değilse dikey ölçek bozulur → ölçülen gerçek v kullanılmalı.")
    bullet("cv2.Stitcher (SCANS): %99 siyah dejenere dev tuval üretir; tekrar eden zeminde sahte özellik eşleşmesi.")

    H("10 · Açık Problem ve Sonraki İş")
    bullet("Bekçi gerçek-ölçek doğrulaması: şu an 3 karelik PoC; çok sayıda filmde doğruluk ve hız ölçülmeli.")
    bullet("YOL 1 ile YOL 2'nin büyük bir film grubunda yan yana yarışı (kapsama, hayalet cezası, okunabilirlik, footage'a dayanıklılık).")
    bullet("Bekçinin segment değil kare-aralığı düzeyinde çalışması (karışık segmentler için tasarım sorusu).")
    bullet("Ön şart: girdiye gerçek scroll segmentleri verilmeli (footage ayıklanmalı); yoksa her iki yol da haksız yere çöp üretir.")

    note = doc.add_paragraph(); note.paragraph_format.space_before = Pt(10)
    run(note, "Bu rapor MITAS OCR çalışma dosyalarındaki (ocr-opus-final.md) kanıtlanmış kararlardan derlenmiştir; tüm sayısal değerler gerçek test koşumlarından alınmıştır.", 8.4, GREY, italic=True)

    doc.save(r"E:\MITAS\mutfak\MITAS_Jenerik_Okuma_Stratejisi.docx")
    print("OK jenerik")

build_envanter()
build_profil()
build_jenerik()
print("DONE")
