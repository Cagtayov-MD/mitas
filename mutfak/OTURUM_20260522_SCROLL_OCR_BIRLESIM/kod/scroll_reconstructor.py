"""scroll_reconstructor.py — DENEYSEL

Akan jenerik frame'lerini tek kompozit görüntüye dönüştürür:
  1. Lucas-Kanade feature tracking ile her frame'in kaç px kaydığını ölç
  2. Frame'leri alt-piksel hizalayarak üst üste yığ (gürültü düşer, ghost olmaz)
  3. Adaptive threshold ile keskin siyah/beyaz görüntü çıkar

Kullanım:
    from tools.scroll_reconstructor import ScrollReconstructor
    rec = ScrollReconstructor()
    composite, sharp = rec.process_video("film.mp4", start_sec=5820, end_sec=5880)
"""

import cv2
import numpy as np
from pathlib import Path


def _png_write(path: Path, img: np.ndarray) -> None:
    """cv2.imwrite Unicode path workaround (Windows'ta sessizce başarısız olur)."""
    _, buf = cv2.imencode(".png", img)
    Path(path).write_bytes(buf.tobytes())


class ScrollReconstructor:

    # ── Adım 1: scroll displacement (Lucas-Kanade, alt-piksel) ─────────────────

    @staticmethod
    def _median_filter(vals: list[float], k: int = 5) -> list[float]:
        """Küçük pencereli medyan filtre — jitter/sıçrama temizliği."""
        if not vals:
            return vals
        half = k // 2
        return [float(np.median(vals[max(0, i - half): i + half + 1]))
                for i in range(len(vals))]

    # Lucas-Kanade + feature parametreleri
    _FEAT = dict(maxCorners=60, qualityLevel=0.15, minDistance=8, blockSize=7)
    _LK = dict(winSize=(21, 21), maxLevel=3,
               criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

    # Displacement düzeltme: hareketli ortalama pencere boyutu.
    # LK jitter'ını bastırır — düşük değer = daha az yumuşatma = daha çok titreme.
    _SMOOTH_K = 25

    @staticmethod
    def _text_mask(gray: np.ndarray) -> np.ndarray:
        """Metin (parlak) piksellerinin maskesi.

        Feature tespiti yalnızca bu maske içinde yapılır — tracker harflere
        kilitlenir, arka plana değil.
        """
        thr = max(45.0, float(gray.mean()) + float(gray.std()))
        _, m = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
        return cv2.dilate(m, np.ones((11, 11), np.uint8))

    @staticmethod
    def _moving_average(vals: list[float], k: int) -> list[float]:
        """Hareketli ortalama — random-walk drift'ini kıran düşük geçiren filtre."""
        if len(vals) < 2 or k < 2:
            return list(vals)
        arr = np.asarray(vals, dtype=np.float64)
        pad = k // 2
        padded = np.pad(arr, pad, mode="edge")
        kernel = np.ones(k) / k
        return np.convolve(padded, kernel, mode="valid")[:len(arr)].tolist()

    @staticmethod
    def _dominant_dy(dy_arr: np.ndarray, dx_arr: np.ndarray) -> float:
        """Hareketli arka plan için baskın dikey hareket hızını bul.

        İki koruma katmanı:
          1. dx filtresi: yatay hareketi > 3px olan vektörleri at
             (kamera yatay panning, çapraz arka plan hareketi)
          2. Histogram tepe tespiti: kalan vektörler arasında en yoğun
             dy değerini seç — arka plan dikey kayıyorsa (kamera tilt),
             metin ve arka plan iki ayrı tepe oluşturur; baskın tepe
             (daha çok feature noktası olan = metin) seçilir.
        """
        # Katman 1: dx filtresi
        keep_dx = np.abs(dx_arr) <= 3.0
        dy_use = dy_arr[keep_dx] if keep_dx.sum() >= 4 else dy_arr

        if len(dy_use) < 4:
            return float(np.median(dy_arr))

        # Katman 2: histogram — ±20px aralığında 41 bin
        hist, edges = np.histogram(dy_use, bins=41, range=(-20.0, 20.0))
        peak = int(np.argmax(hist))
        center = float((edges[peak] + edges[peak + 1]) / 2.0)

        # Tepe etrafında ±2px penceredeki vektörleri kullan
        near_peak = np.abs(dy_use - center) <= 2.0
        if near_peak.sum() >= 3:
            return float(np.median(dy_use[near_peak]))
        return float(np.median(dy_use))

    @staticmethod
    def _detect_active(dy_list: list[float],
                       thresh: float = 0.4,
                       min_stop: int = 8) -> list[bool]:
        """Scroll duraksamalarını tespit et.

        |dy| < thresh olan ve en az min_stop frame süren bölgeler 'stopped'
        sayılır (False döner). Logo kartları, statik ekranlar bunlara girer.
        Kısa takip kayıpları (< min_stop) aktif olarak kalır.
        """
        n = len(dy_list)
        active = [True] * n
        i = 0
        while i < n:
            if abs(dy_list[i]) < thresh:
                j = i
                while j < n and abs(dy_list[j]) < thresh:
                    j += 1
                if j - i >= min_stop:
                    for k in range(i, j):
                        active[k] = False
                i = j
            else:
                i += 1
        return active

    def _estimate_displacements(
        self, frames: list
    ) -> tuple[list[float], list[bool]]:
        """Her frame için kümülatif dikey kayma + aktif frame maskesi.

        Returns:
            cumulative: len(frames) — her frame'in canvas'taki y-ofseti.
            frame_active: len(frames) — True = bu frame scroll'dan geliyor,
                          False = scroll durmuş (logo kartı vb.), stitch'e dahil edilmez.

        Sabit hız hibrit modu (Item 5):
            LK başarısız olduğunda global medyan yerine yerel cruise_speed kullanılır.
            Bootstrap: İlk BOOT_N geçerli ölçüm → cruise_speed = median.
            EMA güncelleme: Her geçerli ölçüm cruise_speed'i yavaşça (α=0.95) günceller.
            Reset: RESET_MIN ardışık sapma (>RESET_DEV) → cruise_speed yeniden hesaplanır.
            Böylece hız değişimi (örn. yavaş başlayıp hızlanan jenerik) yakalanır.

        Hareketli arka plan için dx filtresi:
            Yatay hareketi > 3px olan flow vektörleri atılır. Arka planın
            yatay kaymasından (kamera panning) kaynaklanan sahte dy ölçümleri
            medyana girmiyor — yalnızca dikey hareket eden metin takip ediliyor.
        """
        BOOT_N     = 50    # cruise_speed için gereken minimum ölçüm sayısı
        EMA_ALPHA  = 0.95  # EMA katsayısı — yavaş adaptasyon (≈20 frame yarı-ömür)
        RESET_DEV  = 0.35  # reset için sapma eşiği (cruise_speed'in %35'i)
        RESET_MIN  = 5     # kaç ardışık sapma reset tetikler

        if len(frames) < 2:
            return [0.0] * len(frames), [True] * len(frames)

        prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        pts  = cv2.goodFeaturesToTrack(prev, mask=self._text_mask(prev), **self._FEAT)
        per_frame: list[float | None] = []

        boot_vals:      list[float]       = []
        cruise_speed:   float | None      = None
        deviant_streak: list[float]       = []

        for frame in frames[1:]:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if pts is None or len(pts) < 6:
                pts = cv2.goodFeaturesToTrack(prev, mask=self._text_mask(prev), **self._FEAT)
            if pts is None:
                per_frame.append(None)
                prev = gray
                continue

            nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None, **self._LK)
            status = status.ravel().astype(bool)
            good_prev, good_nxt = pts[status], nxt[status]

            if len(good_nxt) >= 6:
                dy_arr   = good_nxt[:, 0, 1] - good_prev[:, 0, 1]
                dx_arr   = good_nxt[:, 0, 0] - good_prev[:, 0, 0]
                measured = self._dominant_dy(dy_arr, dx_arr)

                if cruise_speed is None:
                    # Bootstrap aşaması
                    boot_vals.append(measured)
                    if len(boot_vals) >= BOOT_N:
                        cruise_speed   = float(np.median(boot_vals))
                        deviant_streak = []
                else:
                    # Cruise aşaması: sapma kontrolü + EMA
                    ref     = max(0.5, abs(cruise_speed))
                    dev_rat = abs(measured - cruise_speed) / ref
                    if dev_rat > RESET_DEV:
                        deviant_streak.append(measured)
                        if len(deviant_streak) >= RESET_MIN:
                            # Hız değişimi tespit edildi → yeniden bootstrap
                            cruise_speed   = float(np.median(deviant_streak))
                            deviant_streak = []
                    else:
                        deviant_streak = []
                        cruise_speed   = EMA_ALPHA * cruise_speed + (1.0 - EMA_ALPHA) * measured

                per_frame.append(measured)
                pts = good_nxt.reshape(-1, 1, 2)
            else:
                per_frame.append(None)
                pts = cv2.goodFeaturesToTrack(gray, mask=self._text_mask(gray), **self._FEAT)
            prev = gray

        # Bootstrap tamamlanmamışsa geçici medyan kullan
        if cruise_speed is None:
            cruise_speed = float(np.median(boot_vals)) if boot_vals else 0.0

        # None'ları cruise_speed ile doldur
        # Bootstrap aşamasındaki boşluklar için causal (o ana kadar) medyanı kullan
        causal_vals: list[float] = []
        filled: list[float] = []
        for d in per_frame:
            if d is not None:
                causal_vals.append(d)
                filled.append(d)
            else:
                if len(causal_vals) >= BOOT_N:
                    filled.append(cruise_speed)
                elif causal_vals:
                    filled.append(float(np.median(causal_vals)))
                else:
                    filled.append(0.0)

        # Felaket sıçramaları reddet (takip kaybında olur) → cruise_speed'e çek
        band   = max(6.0, abs(cruise_speed) * 2.0)
        filled = [d if abs(d - cruise_speed) <= band else cruise_speed for d in filled]

        # Scroll duraksaması tespiti (logo kartları, statik ekranlar)
        trans_active = self._detect_active(filled, thresh=0.4, min_stop=8)

        # Sadece aktif geçişleri düzelt — durmuş bölgeler sınırı kirletmesin
        active_vals = [v for i, v in enumerate(filled) if trans_active[i]]
        if active_vals:
            smoothed_active = self._median_filter(active_vals, k=7)
            smoothed_active = self._moving_average(smoothed_active, k=self._SMOOTH_K)
        else:
            smoothed_active = []

        smoothed: list[float] = []
        j = 0
        for i in range(len(filled)):
            if trans_active[i]:
                smoothed.append(smoothed_active[j])
                j += 1
            else:
                smoothed.append(0.0)  # durmuş frame → aynı pozisyonda kal

        # İlk frame'i her zaman aktif say; sonrakiler geçişe göre
        frame_active = [True] + trans_active   # len = len(frames)

        cumulative = [0.0]
        for dy in smoothed:
            cumulative.append(cumulative[-1] + dy)
        return cumulative, frame_active

    # ── Adım 2: frame yığma (şerit-seçmeli, ghost'suz) ─────────────────────────

    def stitch(self, frames: list) -> np.ndarray | None:
        """Frame listesini kompozit görüntüye dönüştür.

        Ortalama almaz — her frame'den yalnızca *merkez şeridini* alıp yan yana
        döşer. Durmuş frame'ler (logo kartları) atlanır.
        """
        if not frames:
            return None

        displacements, frame_active = self._estimate_displacements(frames)
        h, w = frames[0].shape[:2]
        n = len(frames)

        active_disps = [d for d, a in zip(displacements, frame_active) if a]
        if not active_disps:
            return None

        min_d = min(active_disps)
        max_d = max(active_disps)
        canvas_h = h + int(np.ceil(max_d - min_d)) + 2
        canvas = np.zeros((canvas_h, w, 3), dtype=np.uint8)
        written = np.zeros(canvas_h, dtype=bool)

        offsets = [max_d - d for d in displacements]      # frame üst kenarı
        centers = [off + h / 2.0 for off in offsets]      # frame dikey merkezi

        # Aktif frame indekslerini önceden hesapla (şerit sınırı için)
        active_indices = [i for i in range(n) if frame_active[i]]

        # Her aktif frame için önceki/sonraki aktif komşuyu bul
        prev_active = {}
        nxt_active = {}
        for pos, idx in enumerate(active_indices):
            prev_active[idx] = active_indices[pos - 1] if pos > 0 else None
            nxt_active[idx] = active_indices[pos + 1] if pos + 1 < len(active_indices) else None

        stopped_count = sum(1 for a in frame_active if not a)
        if stopped_count:
            print(f"[ScrollReconstructor] {stopped_count} durmuş frame atlandı "
                  f"(logo/statik bölge)")

        for i, (frame, off) in enumerate(zip(frames, offsets)):
            if not frame_active[i]:
                continue

            io = int(np.floor(off))
            fo = float(off - io)

            # Alt-piksel kaydırma (kesirli kısım) — yuvarlama drift'i olmaz
            M = np.float32([[1, 0, 0], [0, 1, fo]])
            shifted = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE)

            # Bu frame'in şeridi: aktif komşu merkezlerin orta noktaları
            c = io + fo + h / 2.0
            pi = prev_active.get(i)
            ni = nxt_active.get(i)
            top = (centers[pi] + c) / 2.0 if pi is not None else float(io)
            bot = (centers[ni] + c) / 2.0 if ni is not None else float(io + h)
            t = max(int(round(top)), io, 0)
            b = min(int(round(bot)), io + h, canvas_h)
            if b <= t:
                continue

            canvas[t:b] = shifted[t - io: b - io]
            written[t:b] = True

        covered = np.where(written)[0]
        if len(covered):
            composite = canvas[covered[0]: covered[-1] + 1]
        else:
            composite = canvas

        return composite

    # ── Adım 3: sütun ayrıcı tespiti (auto-SPLIT) ─────────────────────────────

    @staticmethod
    def find_column_split(composite: np.ndarray, min_gap_px: int = 8) -> int:
        """Rol/isim ayrım noktasını otomatik bul.

        Jenerikler iki sütundan oluşur: sol=rol, sağ=isim. Aralarında
        metin boşluğu vardır. Algoritma — satır bazlı yaklaşım:

          1. Her satırda metin koşumlarını (parlak piksel dizileri) bul.
          2. En az iki koşum olan satırlarda, en geniş boşluğun orta noktasını
             SPLIT adayı olarak kaydet (sadece %15-%85 arasını ara).
          3. Tüm adayların medyanı = SPLIT.

        Bu yaklaşım sütun yoğunluk profili yerine satır bazlı boşluk tespiti
        yaptığından gürültüye karşı çok daha dayanıklıdır.

        Args:
            composite:   BGR veya gri composite görüntüsü.
            min_gap_px:  Geçerli "sütun boşluğu" sayılmak için minimum px.

        Returns:
            SPLIT piksel x-koordinatı; tespit edilemezse genişliğin ortası.
        """
        if composite is None or composite.size == 0:
            return (composite.shape[1] // 2) if composite is not None else 0

        gray = (cv2.cvtColor(composite, cv2.COLOR_BGR2GRAY)
                if composite.ndim == 3 else composite)
        h, w = gray.shape

        thr = max(50.0, float(gray.mean()) + float(gray.std()))
        binary = (gray > thr)

        # Arama sınırları
        lo = int(w * 0.15)
        hi = int(w * 0.85)

        # Her satırda metin koşumları ara
        # Tüm satırlar yerine eşit aralıklı örnekle (hız için)
        step = max(1, h // 800)
        splits: list[int] = []

        for y in range(0, h, step):
            row = binary[y]
            if not row.any():
                continue

            # Koşumları bul
            runs: list[tuple[int, int]] = []
            in_run = False
            start = 0
            for x in range(w):
                if row[x]:
                    if not in_run:
                        start = x
                        in_run = True
                else:
                    if in_run:
                        runs.append((start, x - 1))
                        in_run = False
            if in_run:
                runs.append((start, w - 1))

            if len(runs) < 2:
                continue

            # En geniş boşluğu %15-%85 arasında ara
            best_gap = min_gap_px - 1
            best_mid: int | None = None
            for i in range(len(runs) - 1):
                gap_l = runs[i][1]      # sol koşumun sağ ucu
                gap_r = runs[i + 1][0]  # sağ koşumun sol ucu
                mid = (gap_l + gap_r) // 2
                gap = gap_r - gap_l
                if gap > best_gap and lo <= mid <= hi:
                    best_gap = gap
                    best_mid = mid

            if best_mid is not None:
                splits.append(best_mid)

        if not splits:
            return w // 2
        return int(np.median(splits))

    # ── Adım 4: kalite skoru ──────────────────────────────────────────────────

    @staticmethod
    def quality_score(composite: np.ndarray) -> dict:
        """Composite kalite skoru (0-1) — HAM composite üzerinde çalışır.

        DİKKAT: Girdi ham composite olmalı, `sharpen()` çıktısı DEĞİL.
        `sharpen()` adaptive threshold uygular ve görüntünün ~%50-80'ini
        beyaza çevirir; bu yüzden onun üzerinde yoğunluk ölçmek anlamsızdır.

        Metrikler:
          sharpness — Laplacian varyansı. Hayalet/yanlış hizalama edge'leri
                      bulanıklaştırır, varyans düşer. İyi reconstruction'da yüksek.
          contrast  — Otsu ile ayrılan metin/zemin parlaklık farkı (0-1).
          text_density — parlak (metin) piksel oranı; sağlıklı bant %2-%25.

        Tipik eşik: score >= 0.65 = kullanılabilir composite.

        Returns:
            {
              "score":        float,  # 0-1 bileşik skor
              "sharpness":    float,  # ham Laplacian varyansı
              "contrast":     float,  # 0-1
              "text_density": float,  # 0-1 oranı
            }
        """
        empty = {"score": 0.0, "sharpness": 0.0, "contrast": 0.0, "text_density": 0.0}
        if composite is None or composite.size == 0:
            return empty

        h, w = composite.shape[:2]
        if h < 10 or w < 10:
            return empty

        gray = cv2.cvtColor(composite, cv2.COLOR_BGR2GRAY) if composite.ndim == 3 else composite

        # 1. Keskinlik — Laplacian varyansı (600+ = net metin kenarları)
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        sharp_s = min(1.0, lap_var / 600.0)

        # 2. Otsu ile metin/zemin ayrımı
        thr, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        bright = gray[gray > thr]
        dark   = gray[gray <= thr]
        if bright.size and dark.size:
            contrast = (float(bright.mean()) - float(dark.mean())) / 255.0
        else:
            contrast = 0.0
        contrast_s = min(1.0, contrast / 0.40)

        # 3. Metin yoğunluğu — sağlıklı bant %2-%25
        density = float(bright.size) / gray.size
        if density < 0.02:
            density_s = density / 0.02
        elif density <= 0.25:
            density_s = 1.0
        else:
            density_s = max(0.0, 1.0 - (density - 0.25) / 0.25)

        score = 0.45 * sharp_s + 0.35 * contrast_s + 0.20 * density_s
        return {
            "score":        round(float(score), 3),
            "sharpness":    round(lap_var, 1),
            "contrast":     round(contrast, 3),
            "text_density": round(density, 4),
        }

    # ── Adım 5: keskinleştirme ─────────────────────────────────────────────────

    def sharpen(self, composite: np.ndarray, block_size: int = 15, c: int = 3) -> np.ndarray:
        """Adaptive threshold -> keskin siyah/beyaz metin."""
        gray = cv2.cvtColor(composite, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block_size, c,
        )
        return binary

    # ── Tam pipeline ───────────────────────────────────────────────────────────

    def process_video(
        self,
        video_path: str | Path,
        start_sec: float = 0,
        end_sec: float | None = None,
        frame_step: int = 1,
        output_dir: str | Path | None = None,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """
        Video dosyasından kompozit + keskin görüntü üret.

        Args:
            video_path:  Video dosyası.
            start_sec:   Başlangıç saniyesi.
            end_sec:     Bitiş saniyesi (None -> dosya sonu).
            frame_step:  Her kaç frame'de bir al (1 = tümü, 2 = atlayarak).
            output_dir:  Belirtilirse composite.png + sharpened.png kaydeder.

        Returns:
            (composite, sharpened) — hata durumunda (None, None).
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"[ScrollReconstructor] Video açılamadı: {video_path}")
            return None, None

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        start_f = int(start_sec * fps)
        end_f = int(end_sec * fps) if end_sec is not None else total

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_f)
        frames = []
        idx = 0

        while cap.get(cv2.CAP_PROP_POS_FRAMES) < end_f:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % frame_step == 0:
                frames.append(frame)
            idx += 1

        cap.release()
        print(f"[ScrollReconstructor] {len(frames)} frame yüklendi ({video_path})")

        if not frames:
            return None, None

        composite = self.stitch(frames)
        if composite is None:
            return None, None

        sharpened = self.sharpen(composite)

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            _png_write(out / "composite.png", composite)
            _png_write(out / "sharpened.png", sharpened)
            print(f"[ScrollReconstructor] Kaydedildi: {out}")

        return composite, sharpened

    def process_frames(
        self,
        frames: list,
        output_dir: str | Path | None = None,
    ) -> tuple[np.ndarray | None, np.ndarray | None]:
        """Frame listesinden doğrudan çalış (video yerine)."""
        composite = self.stitch(frames)
        if composite is None:
            return None, None
        sharpened = self.sharpen(composite)
        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            _png_write(out / "composite.png", composite)
            _png_write(out / "sharpened.png", sharpened)
            print(f"[ScrollReconstructor] Kaydedildi: {out}")
        return composite, sharpened
