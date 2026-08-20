vunları varsayılan görevlere gerekrise ek oalrak yaz.
////////
öncelikle istediğim şeyleri anlatayım sana son ekez
öncelikle işlerin tüm tokenleri clauddan gitmemeli.

bu kısım en kritik olan kısım.

modelleri tek tek belirleriz.

proje çıktı üretiyor kontrole düşenleri detaylı bir analiz edecek.
bunları xml dosyasıan raporalyacak.

elimzide şu olacak yani 

titanic filmi yönetmen kontrole düştü. 

neden düştü ?
kimin hatası kodda mı sorun var detaylı bir tespit tamam mı ?
tahmini değil
ocr da şu framede yazı vardı ama biz o yazıyı doğru okumama rağmen şurdaki kod bloğu sebebiyle pdf e aktaramdık. gibi.
her film için kısa bi açıklama.
ve sınıflandırma.
agent kısımımın en önemlisi bu aslında. sistemin kalbi bu.

10 tane film aynı kod bloğunda aynı hataya tamakılıyor. gibi 
25 film yönetmen kontrole takıldı;
bunların 8 i şu sebeple 
6 sı bu sebeple gibi.   bu aşama sadadece raporlama aşamsı işlem yok sadece sebepler.


+++++++++


kod denetcisi kodun performansını denetler tavsiyelerde bulunur. gereksiz zaman harcayan yerleri keşfeder gereksiz beklemeler  gpu boş kaldığı alanlar cpu boş kaldığı alalar ve daha iyi nasıl kullanılabilir önerilerde bulunur. tavsiye. burda temel prensip min sürede max sayıda çıktı üretmek. paralel çalışmak seri çalışmak vs kapsamlı bir öneri tavsiye.. artık neyse.
++++



onaylılar için bir qc verileri internette teğit edip herhangi bir sorun varsa ufak bildirimlerde bulunmak.
aslında buun amacı şu, kontrola düşenler sistem tarafından net hatası bulunanlardır.
ama sistem tarafında birşey bulamayıp hatalı şekilde onaylıya düşenler olabilir. onları kontrol etmek.++++++++++++++
++
Örneğin
1. Kod Denetçisi

Görevi sadece:

Kod kalitesi
SOLID
tekrar eden kod
mimari

Başka hiçbir şeye bakmaz.

2. Performans Uzmanı

Sadece

gereksiz kopyalama
RAM
GPU
darboğaz

ile ilgilenir.



+++

Ana ajan bunların raporlarını okur.

Ve sana

Toplam 17 sorun.

5 performans

3 bug

2 mimari

7 test eksiği

şeklinde tek rapor verir.


+



Mesela

Kod Kalitesi
        │
     Claude
Performans
        │
     DeepSeek
Bug Hunter
        │
      GLM
Kod Yazımı
        │
      Qwen

Çünkü her modelin güçlü olduğu alan farklı.

Secretary

En sevdiğim.

O hiçbir teknik karar vermez.

Sadece bütün raporları okuyup

TOPLAM

Bug

TODO

Risk

Karar

Sonraki adım

çıkarır.

yada 

OCR Reviewer

ASR Reviewer

PDF Reviewer

QC Reviewer

API Reviewer


n çok hoşuma giden şey

Şu ilke:

Gerçek bağlama hizmet ediyor mu?

Çalışan bir şeyi bozuyor mu?

Daha kolay bir yol var mıydı?

Ben olsam bunu bütün ajanların ortak anayasası yaparım.


Eğer gerçekten benim repo üzerinde çalışmamı istiyorsan en temiz yöntem bu.

1. GitHub Connector'ı bağla

ChatGPT'de:

Settings → Connectors → GitHub

GitHub hesabını bağla ve erişim izni ver.

2. Repo erişimi ver

Bağlandıktan sonra bana sadece şunu yaz:

MITAS reposunu incele.

veya

Cagtayov-MD/mitas reposunu kullan.

Ben connector üzerinden dosyaları okuyabilirim.

3. Eğer repo private ise

Sadece MITAS'a izin vermen yeterli.

Tüm GitHub hesabını açmana gerek yok.

4. Ben ne yapacağım?

İlk işim ajan yazmak olmayacak.

Şu raporları çıkaracağım:

📁 Repository haritası
🔄 Import / dependency graph
🧩 Modül sınırları
📊 Kod istatistikleri
🔥 En riskli 20 dosya
📈 En çok değişen dosyalar (commit geçmişinden)
🧪 Test kapsamı
⚡ Performans darboğaz adayları
🏗️ Mimari ihlalleri
📝 AI ajanları için görev dağılımı

Bunlardan sonra sana gerçekten MITAS'a özel bir AI organizasyonu tasarlayabilirim.

Eğer "GitHub" görünmüyorsa

Bazı hesaplarda GitHub Connector henüz açık olmayabiliyor.

O durumda bana söyle. Bu konuşmada GitHub eklentisinin mevcut olup olmadığını birlikte kontrol ederiz ve gerekirse alternatif (ZIP + yerel analiz) üzerinden ilerleriz.

çalışmanı değil detaylı incemenemi ve sorularıma ordan devam ermeni sitiyorm. müdhal etme

Evet, bu yapılabilir ve bence bu senaryo çok daha verimli.

Benim istediğim de aslında bu.

Senin istediğin rol şu:

"Kod yazma. Müdahale etme. Repoyu öğren. Sonraki aylarda bütün sorularıma o bağlamla cevap ver."

Bu tam olarak yapmak istediğim çalışma şekli.

Nasıl olmalı?

Ben repo üzerinde şunları yaparım:

Tüm klasör yapısını öğrenirim.
Her modülün amacını çıkarırım.
Veri akışını anlarım.
Hangi dosya ne iş yapıyor indekslerim.
Mimari kararları öğrenirim.
Commit geçmişini incelerim.
Tasarım felsefesini öğrenirim.

Ama hiçbir dosyayı değiştirmem.

Yani rolüm:

Resident Architect / Technical Reviewer

Kod üretmek değil.

Sonra sen bana şunu dersin:

"credit_text_read.py'ı yeniden yazalım mı?"

Ben cevap veririm:

"Hayır. Çünkü bu modül şu üç pipeline tarafından kullanılıyor. Ayrıca summary_service buna bağımlı. Burayı değiştirmek yerine core/... katmanında çözmek daha doğru."

Bunu ancak repo hafızam olursa söyleyebilirim.

Veya dersin:

"OneOCR'u değiştirelim mi?"

Ben:

"Benchmark kayıtlarına göre henüz yeterli veri yok. Ayrıca OCR modülü şu üç yerde ortak kullanılıyor. Önce benchmark tamamlanmalı."

Benim hedefim

Bir sohbet boyunca değil.

MITAS'ı bilen biri olmak.

Yani sen her seferinde mimariyi tekrar anlatmayacaksın.

Ben de her cevapta genel Python tavsiyesi vermeyeceğim
