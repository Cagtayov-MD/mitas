# Sheriff sınır sözleşmesi

1. Bir kuleye yalnız `config.yaml` içindeki executable ve argüman şablonuyla gidilir.
2. Kardeş kule Python import'u yasaktır.
3. `_TAMAM` dosya-yazım bariyeridir; başarı hükmü değildir.
4. Okuyucu teslimi `mitas.okuma/v2` olmalı ve run/task/attempt kimliği eşleşmelidir.
5. Her asset SHA-256 ile doğrulanır; bundle içinde göreli yola çevrilir.
6. BBox yalnız kaynak piksel uzayında `xyxy` tam sayıdır. Tahmin/uydurma yasaktır.
7. Satır proof eksik diye atılmaz; `PARTIAL/NONE` olur.
8. Giriş ve çıkış bağımsız görevlerdir; birinin hatası diğer sonucu silmez.
9. Kule `ARIZA` sonucu process rc=2 verse bile JSON okunur; arıza retry politikasına gider.
10. Sheriff üç-kanal paketi yayımlar; metin uzlaştırmaz ve Shaq'ı başlatmaz.
11. Her kule yalnız kendi `Allstar/<kule>/out/` alanına yazar. Sheriff `--out`
    ile kulenin hedefini değiştirmez; taze `_TAMAM`, kimlik ve asset hash'lerini
    doğruladıktan sonra bölüm dizinini run/attempt'e özel salt-okunur snapshot'a
    alır. Aşağı akış paylaşılan kule `out/`una değil bu snapshot'a bağlanır.
12. `proof=COMPLETE` ancak her satır gerçek frame bbox'ı, pozitif frame sırası
    ve kaynak timecode taşıyorsa geçerlidir.
13. Enqueue anındaki pipeline kimliği aktif kod/registry kimliğiyle uyuşmuyorsa
    görev çalıştırılmaz.
14. Frame havuzu ve Jordan klibi, upstream görevde kaydedilmiş hash ile kule
    öncesi/sonrası ve crash recovery sırasında aynı olmak zorundadır.
15. İlk handoff yayını da cache doğrulamasıyla aynı film/run/task/producer ve
    asset-hash kapılarından `_TAMAM` yazılmadan önce geçer.
16. Layout haritasındaki kaynak frame bağı taşınabilir asset kimliğiyle kurulur;
    mutlak yol yalnız lineage bilgisidir.
