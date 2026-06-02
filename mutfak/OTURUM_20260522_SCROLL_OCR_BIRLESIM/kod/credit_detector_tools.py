"""credit_detector.py — Jenerik bölgesi tespiti ve sınıflandırması.

Bir video dosyasında akan veya statik jenerik segmentini otomatik bulur;
başlangıç/bitiş saniyesi ve scroll hızı döndürür.

Kullanım:
    from tools.credit_detector import CreditDetector
    det = CreditDetector()
    r = det.detect("film.mp4")
    # r = {
    #     'found': True,
    #     'type': 'scroll',        # 'scroll' | 'static' | 'none'
    #     'start_sec': 5820.0,
    #     'end_sec': 6290.0,
    #     'scroll_speed': -2.35,   # px/frame; scroll değilse 0.0
    #     'confidence': 0.87,      # 0-1
    # }
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path


# ── Probe sonucu ───────────────────────────────────────────────────────────────

@dataclass
class ProbeResult:
    t: float          # saniye — bu probe'un video zamanı
    dark_ratio: float # kare piksellerinin karanlık fraksiyonu [0-1]
    text_ratio: float # kare piksellerinin parlak-metin fraksiyonu [0-1]
    avg_dy: float     # ortalama dikey kayma (px/frame)
    dy_std: float     # dikey kayma standart sapması
    n_good: int       # geçerli LK vektör sayısı

    @property
    def scroll_score(self) -> float:
        """0-1: bu probe'un akan jenerik olma skoru.

        SNR = |avg_dy| / max(0.5, dy_std) — sabit bir std eşiği yerine
        sinyal/gürültü oranına bakılır. Yavaş ama tutarlı scroll da yakalanır.
        """
        dark_s = min(1.0, self.dark_ratio / 0.50)
        text_s = min(1.0, self.text_ratio / 0.015)
        if self.n_good >= 3 and abs(self.avg_dy) > 0.8:
            snr = abs(self.avg_dy) / max(0.5, self.dy_std)
            motion_s = min(1.0, snr / 2.5)
        else:
            motion_s = 0.0
        return 0.25 * dark_s + 0.25 * text_s + 0.50 * motion_s

    @property
    def static_score(self) -> float:
        """0-1: bu probe'un statik jenerik olma skoru.

        Karanlık arka plan (dark_ratio > 0.35) ZORUNLU — bu olmadan film
        sahnelerindeki text overlay'ler yanlış pozitif verir.
        """
        if self.dark_ratio < 0.35:
            return 0.0          # siyah zemin yoksa statik jenerik değil
        dark_s  = min(1.0, self.dark_ratio / 0.60)
        text_s  = min(1.0, self.text_ratio / 0.015)
        still_s = 1.0 if abs(self.avg_dy) < 0.5 else max(0.0, 1.0 - abs(self.avg_dy) / 3.0)
        return 0.30 * dark_s + 0.40 * text_s + 0.30 * still_s

    @property
    def is_credit(self) -> bool:
        return self.scroll_score >= 0.55 or self.static_score >= 0.60

    @property
    def credit_type(self) -> str:
        if self.scroll_score >= 0.55 and self.scroll_score >= self.static_score:
            return "scroll"
        if self.static_score >= 0.60:
            return "static"
        return "none"


# ── Dedektör ──────────────────────────────────────────────────────────────────

class CreditDetector:
    """
    Geniş tarama (10s aralıklı probe) + sınır rafine (2s aralıklı)
    ile jenerik segmentini bulur.
    """

    # ── Parametreler ────────────────────────────────────────────────────────
    DARK_THRESH  = 30     # "karanlık piksel" eşiği (0-255)
    PROBE_SEC    = 10     # geniş taramada probe aralığı (saniye)
    REFINE_SEC   = 2      # sınır rafine aralığı (saniye)
    MOTION_DT    = 0.4    # motion ölçümü için frame arası zaman (saniye)
    MOTION_N     = 5      # motion ölçümü için frame sayısı
    MIN_CREDIT   = 20     # geçerli segment için minimum süre (saniye)
    MERGE_GAP    = 30     # bu kadar saniyeye kadar olan boşlukları birleştir
    SEARCH_END   = 15     # önce son N dakikayı tara (dk)

    _FEAT = dict(maxCorners=40, qualityLevel=0.2, minDistance=10, blockSize=7)
    _LK   = dict(winSize=(21, 21), maxLevel=2,
                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.05))

    # ── Public API ──────────────────────────────────────────────────────────

    def detect(
        self,
        video_path: str | Path,
        search_end_min: float | None = None,
        verbose: bool = True,
    ) -> dict:
        """
        Videodaki jenerik segmentini bul.

        Args:
            video_path:     Video dosyası.
            search_end_min: İlk önce son bu kadar dakikayı tara.
                            None → SEARCH_END sabitini kullan.
            verbose:        Ara adımları yazdır.

        Returns:
            found, type, start_sec, end_sec, scroll_speed, confidence
        """
        path = Path(video_path)
        cap  = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return self._no_result()

        fps   = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur   = total / fps
        end_m = search_end_min if search_end_min is not None else self.SEARCH_END

        if verbose:
            print(f"[CreditDetector] {path.name}  dur={dur/60:.1f}m  fps={fps:.2f}")

        # Faz 1: son N dakikayı geniş tara
        search_start = max(0.0, dur - end_m * 60)
        probes = self._broad_scan(cap, fps, search_start, dur, verbose)
        segment = self._find_segment(probes)

        # Faz 1b: bulunamazsa tüm videoyu tara
        if segment is None and search_start > 0:
            if verbose:
                print("[CreditDetector] Son bölümde bulunamadı, tüm video taranıyor...")
            probes = self._broad_scan(cap, fps, 0.0, dur, verbose)
            segment = self._find_segment(probes)

        if segment is None:
            cap.release()
            if verbose:
                print("[CreditDetector] Jenerik bulunamadı.")
            return self._no_result()

        raw_start, raw_end, ctype, speed, conf = segment
        if verbose:
            print(f"[CreditDetector] Ham segment: {raw_start:.0f}s–{raw_end:.0f}s  "
                  f"tip={ctype}  hız={speed:.2f}  güven={conf:.2f}")

        # Faz 2: sınırları 2s hassasiyetle rafine et
        t_start = self._refine(cap, fps, raw_start - self.PROBE_SEC,
                               raw_start + self.PROBE_SEC, "start", ctype, verbose)
        t_end   = self._refine(cap, fps, raw_end   - self.PROBE_SEC,
                               raw_end   + self.PROBE_SEC, "end",   ctype, verbose)

        # Faz 3: rafine bölgede gerçek scroll hızını ölç
        # Fallback: _measure_speed text bulamazsa probe ortalamasını kullan
        if ctype == "scroll":
            measured = self._measure_speed(cap, fps, t_start, t_end, verbose)
            speed = measured if abs(measured) > 0.3 else speed

        cap.release()

        if verbose:
            print(f"[CreditDetector] Sonuç: {t_start:.0f}s–{t_end:.0f}s  "
                  f"({(t_end-t_start)/60:.1f}m)  tip={ctype}  hız={speed:.3f}  güven={conf:.2f}")

        return {
            "found":       True,
            "type":        ctype,
            "start_sec":   t_start,
            "end_sec":     t_end,
            "scroll_speed": round(speed, 3),
            "confidence":  round(conf, 3),
        }

    # ── Geniş tarama ───────────────────────────────────────────────────────

    def _broad_scan(
        self, cap, fps: float, t0: float, t1: float, verbose: bool
    ) -> list[ProbeResult]:
        """[t0, t1] aralığını PROBE_SEC adımlarla ölç."""
        probes: list[ProbeResult] = []
        t = t0
        while t <= t1:
            p = self._probe_at(cap, fps, t)
            probes.append(p)
            if verbose:
                print(f"  t={t:7.1f}s  dark={p.dark_ratio:.2f}  text={p.text_ratio:.3f}  "
                      f"dy={p.avg_dy:+.2f}±{p.dy_std:.2f}  scroll={p.scroll_score:.2f}  "
                      f"static={p.static_score:.2f}  -> {p.credit_type}")
            t += self.PROBE_SEC
        return probes

    # ── Segment bulma ───────────────────────────────────────────────────────

    def _find_segment(
        self, probes: list[ProbeResult]
    ) -> tuple[float, float, str, float, float] | None:
        """
        Probe listesinden en uzun geçerli jenerik segmentini bul.

        Returns (start_sec, end_sec, type, avg_speed, confidence) veya None.
        """
        if not probes:
            return None

        # Her probe'u credit/non-credit olarak işaretle
        credit_flags = [p.is_credit for p in probes]

        # Boşlukları birleştir (MERGE_GAP sn'ye kadar)
        gap_probes = int(np.ceil(self.MERGE_GAP / self.PROBE_SEC))
        merged = list(credit_flags)
        for i in range(len(merged)):
            if not merged[i]:
                # Sağa bak: gap_probes içinde True var mı?
                ahead = merged[i + 1: i + 1 + gap_probes]
                if any(ahead):
                    merged[i] = True  # boşluğu köprüle

        # Ardışık True bloklarını bul
        runs: list[tuple[int, int]] = []
        start = None
        for i, v in enumerate(merged):
            if v and start is None:
                start = i
            elif not v and start is not None:
                runs.append((start, i - 1))
                start = None
        if start is not None:
            runs.append((start, len(merged) - 1))

        # Minimum süreyi karşılayan uzun segmentleri filtrele
        min_probes = max(2, int(np.ceil(self.MIN_CREDIT / self.PROBE_SEC)))
        valid = [(s, e) for s, e in runs if e - s + 1 >= min_probes]
        if not valid:
            return None

        # Segment skoru: uzunluk × video sonu yakınlığı × scroll kalitesi
        # Video sonu yakınlığı kritik — end credits neredeyse her zaman sonda.
        last_t = probes[-1].t if probes else 1.0

        def seg_score(se_pair):
            s, e = se_pair
            length_w = (e - s + 1) / max(1, len(probes))
            pos_w    = probes[e].t / max(1.0, last_t)   # geç = yüksek puan
            seg_ps   = [probes[i] for i in range(s, e + 1) if probes[i].is_credit]
            quality  = float(np.mean([max(p.scroll_score, p.static_score) for p in seg_ps])) if seg_ps else 0.0
            return length_w * 0.20 + pos_w * 0.60 + quality * 0.20

        s, e = max(valid, key=seg_score)
        seg_probes = [probes[i] for i in range(s, e + 1) if probes[i].is_credit]

        t_start = probes[s].t
        t_end   = probes[e].t

        # Tip: herhangi bir probe açıkça scroll'sa (>=0.65) → scroll.
        # Aksi hâlde çoğunluk oylaması.
        scroll_votes  = sum(1 for p in seg_probes if p.credit_type == "scroll")
        clear_scrolls = sum(1 for p in seg_probes if p.scroll_score >= 0.65)
        if clear_scrolls >= 2 or scroll_votes > len(seg_probes) / 2:
            ctype = "scroll"
        else:
            ctype = "static"

        avg_speed = float(np.median([p.avg_dy for p in seg_probes
                                     if abs(p.avg_dy) > 0.5])) if ctype == "scroll" else 0.0
        conf = float(np.mean([p.scroll_score if ctype == "scroll"
                               else p.static_score for p in seg_probes]))

        return t_start, t_end, ctype, avg_speed, conf

    # ── Sınır rafine ───────────────────────────────────────────────────────

    def _refine(
        self, cap, fps: float,
        t_lo: float, t_hi: float,
        direction: str,
        ctype: str,
        verbose: bool,
    ) -> float:
        """REFINE_SEC adımlarla sınırı daralt."""
        t_lo = max(0.0, t_lo)
        t = t_lo
        results: list[tuple[float, bool]] = []
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur = total_frames / (fps or 25)

        while t <= min(t_hi, dur):
            p = self._probe_at(cap, fps, t)
            is_c = (p.scroll_score >= 0.55 if ctype == "scroll"
                    else p.static_score >= 0.55)
            results.append((t, is_c))
            t += self.REFINE_SEC

        if not results:
            return t_lo

        if direction == "start":
            # İlk True → credit başladı
            for tv, is_c in results:
                if is_c:
                    return tv
            return t_lo
        else:
            # Son True → credit bitti
            last_t = t_lo
            for tv, is_c in results:
                if is_c:
                    last_t = tv
            return last_t + self.REFINE_SEC

    # ── Hız ölçümü ─────────────────────────────────────────────────────────

    def _measure_speed(
        self, cap, fps: float, t_start: float, t_end: float, verbose: bool
    ) -> float:
        """Jenerik segmentinin birden fazla noktasında scroll hızını ölç.

        Segment ortasında tek ölçüm yapmak logo/durak anlarına denk gelebilir.
        %25, %50, %75 üç noktada ölçüp medyan alınır.
        """
        dt_frames = max(1, int(round(0.2 * fps)))   # dt=0.2s, normalize için
        total = max(1.0, t_end - t_start)
        candidates: list[float] = []

        for frac in (0.25, 0.50, 0.75):
            t = t_start + frac * total
            frames = self._read_frames(cap, fps, t, n=12, dt=0.2)
            if len(frames) < 3:
                continue
            avg_dy, _, n_good = self._motion_signals(frames, dt_frames)
            if n_good >= 3 and abs(avg_dy) > 0.3:
                candidates.append(avg_dy)

        if not candidates:
            return 0.0
        # En tutarlı (en büyük mutlak değerli) ölçümü al
        return float(sorted(candidates, key=abs)[-1])

    # ── Tek probe ──────────────────────────────────────────────────────────

    def _probe_at(self, cap, fps: float, t: float) -> ProbeResult:
        """t saniyesinde tek probe: statik + motion sinyalleri."""
        frames = self._read_frames(cap, fps, t, n=self.MOTION_N, dt=self.MOTION_DT)
        if not frames:
            return ProbeResult(t=t, dark_ratio=0, text_ratio=0,
                               avg_dy=0, dy_std=0, n_good=0)

        # Statik sinyaller: ilk frame üzerinde
        dark_ratio, text_ratio = self._frame_signals(frames[0])

        # Motion sinyalleri: px/video-frame cinsinden
        dt_frames = max(1, int(round(self.MOTION_DT * fps)))
        avg_dy, dy_std, n_good = self._motion_signals(frames, dt_frames)

        return ProbeResult(
            t=t,
            dark_ratio=dark_ratio,
            text_ratio=text_ratio,
            avg_dy=avg_dy,
            dy_std=dy_std,
            n_good=n_good,
        )

    # ── Frame okuma ────────────────────────────────────────────────────────

    def _read_frames(
        self, cap, fps: float, t: float, n: int, dt: float
    ) -> list:
        """t saniyesinden başlayarak n frame oku (dt saniyelik adımlarla)."""
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        for i in range(n):
            f_idx = int((t + i * dt) * fps)
            if f_idx >= total_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, float(f_idx))
            ok, frame = cap.read()
            if ok:
                frames.append(frame)
        return frames

    # ── Sinyal hesaplamaları ───────────────────────────────────────────────

    @staticmethod
    def _frame_signals(frame: np.ndarray) -> tuple[float, float]:
        """Bir frame'in karanlık ve metin piksel oranlarını hesapla."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        n = gray.size
        dark_ratio = float((gray < 30).sum()) / n
        thr = max(50.0, float(gray.mean()) + 1.5 * float(gray.std()))
        text_ratio = float((gray > thr).sum()) / n
        return dark_ratio, text_ratio

    @staticmethod
    def _text_mask_for_detection(gray: np.ndarray) -> np.ndarray | None:
        """Parlak piksel maskesi — feature detection'ı metinle sınırlar.

        Arka plan feature'larını eleyerek scroll_reconstructor ile aynı
        mantıkta hız ölçümü yapılır. Maske boşsa None döner (fallback).
        """
        thr = max(45.0, float(gray.mean()) + float(gray.std()))
        _, m = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
        m = cv2.dilate(m, np.ones((11, 11), np.uint8))
        return m if m.any() else None

    def _motion_signals(
        self, frames: list, dt_frames: int = 1
    ) -> tuple[float, float, int]:
        """Ardışık frame çiftleri arasında LK ile dy ölç.

        Args:
            frames:    Eşit aralıklı frame listesi.
            dt_frames: Her çift arası video frame sayısı (normalleştirme için).

        Returns:
            (avg_dy, dy_std, n_good) — birim: px/video-frame.
        """
        if len(frames) < 2:
            return 0.0, 0.0, 0

        dy_vals: list[float] = []
        prev = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        mask = self._text_mask_for_detection(prev)
        pts  = cv2.goodFeaturesToTrack(prev, mask=mask, **self._FEAT)

        for frm in frames[1:]:
            gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
            if pts is None or len(pts) < 4:
                mask = self._text_mask_for_detection(prev)
                pts  = cv2.goodFeaturesToTrack(prev, mask=mask, **self._FEAT)
            if pts is None:
                prev = gray
                continue
            nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None, **self._LK)
            ok = st.ravel().astype(bool)
            if ok.sum() >= 4:
                raw_dy = float(np.median(nxt[ok, 0, 1] - pts[ok, 0, 1]))
                dy_vals.append(raw_dy / dt_frames)   # px/video-frame'e normalize
                pts = nxt[ok].reshape(-1, 1, 2)
            prev = gray

        if not dy_vals:
            return 0.0, 0.0, 0
        return (float(np.mean(dy_vals)),
                float(np.std(dy_vals)) if len(dy_vals) > 1 else 0.0,
                len(dy_vals))

    # ── Yardımcı ──────────────────────────────────────────────────────────

    @staticmethod
    def _no_result() -> dict:
        return {"found": False, "type": "none", "start_sec": 0.0,
                "end_sec": 0.0, "scroll_speed": 0.0, "confidence": 0.0}
