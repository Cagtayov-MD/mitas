# MITAS Karar Denetim Checklist v1

## Amaç

Bu doküman, MITAS’ta her önemli karar, sprint kapanışı, master plan güncellemesi, modül seçimi ve profil/pipeline değişikliği öncesinde çalıştırılacak kontrol listesidir.

Amaç:

- kritik açıkları erken yakalamak
- owner boşluklarını görmek
- benchmark yapılmadan model seçimini engellemek
- performans/VRAM etkisini unutmamak
- schema ve migration problemlerini erken görmek
- UI / review akışı çelişkilerini yakalamak
- profil defaultları ile runtime override davranışını karıştırmamak

## Checklist

1. Bu kararın owner’ı var mı?
2. Test seti / ground truth gerektiriyor mu?
3. Benchmark görmeden ana motor ilan ediyor muyuz?
4. Performans hedefi ölçülmüş mü, yoksa niyet mi?
5. VRAM/runtime etkisi var mı?
6. Başka modüle bağımlı mı?
7. P1 kapısı ise sırası belli mi?
8. Schema değiştiriyorsa schema_version var mı?
9. Eski veriye migration gerekiyor mu?
10. Review UI / kullanıcı akışıyla çelişiyor mu?
11. Runtime override ile profil default’ları karışıyor mu?
12. Bu karar master’a mı, ara karar dokümanına mı girmeli?

## Ne Zaman Çalıştırılır?

- Yeni sprint kapatırken
- Yeni karar dokümanı oluştururken
- Master plana karar taşırken
- Model seçimi yaparken
- Profil/pipeline kararı değiştirirken
- UI/review akışı değiştirirken
- Benchmark sonucu yorumlarken
- “Bunu sabitleyelim” denilen her noktada

## Kullanım Kuralı

Bir karar bu checklist’ten geçmeden “sabit” kabul edilmez.

Her madde için cevaplardan biri yazılır:

- OK
- Eksik
- Bu karar için geçerli değil
- Sonra değerlendirilecek

Eksik çıkan maddeler ya kapatılır ya da açık risk olarak dokümana yazılır.

## Son Karar

Bu checklist MITAS karar alma sürecinin zorunlu denetim filtresidir.
