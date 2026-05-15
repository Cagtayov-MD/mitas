# ASR Gold Probe Review Packets

Bu klasor, gold referans isini bastan transcript yazmaya cevirmeden yapmak icindir.
Her sample icin once `review_candidates/*.txt` aday metnini dinle; sadece hatali kelime/ifadeleri bildir.

Geri bildirim formati:

```text
sample_id:
02:30 "yanlis ifade" degil, "dogru ifade"
```

| Sample | Candidate | Packet | Ref status |
|---|---|---|---|
| gold_h1_news_0000_0100 | outputs\asr_gold_probe_benchmark\review_candidates\gold_h1_news_0000_0100.txt | outputs\asr_gold_probe_benchmark\review_packets\gold_h1_news_0000_0100.md | needs_cleanup |
| gold_neretva_bridge_0340_0440 | outputs\asr_gold_probe_benchmark\review_candidates\gold_neretva_bridge_0340_0440.txt | outputs\asr_gold_probe_benchmark\review_packets\gold_neretva_bridge_0340_0440.md | needs_cleanup |
| gold_merakli_momolar_0000_0100 | outputs\asr_gold_probe_benchmark\review_candidates\gold_merakli_momolar_0000_0100.txt | outputs\asr_gold_probe_benchmark\review_packets\gold_merakli_momolar_0000_0100.md | needs_cleanup |
| gold_baris_manco_children_0140_0340 | outputs\asr_gold_probe_benchmark\review_candidates\gold_baris_manco_children_0140_0340.txt | outputs\asr_gold_probe_benchmark\review_packets\gold_baris_manco_children_0140_0340.md | needs_cleanup |
| gold_kuran_0000_0100 | outputs\asr_gold_probe_benchmark\review_candidates\gold_kuran_0000_0100.txt | outputs\asr_gold_probe_benchmark\review_packets\gold_kuran_0000_0100.md | needs_cleanup |
| gold_mehmed_0000_0100 | outputs\asr_gold_probe_benchmark\review_candidates\gold_mehmed_0000_0100.txt | outputs\asr_gold_probe_benchmark\review_packets\gold_mehmed_0000_0100.md | needs_cleanup |
