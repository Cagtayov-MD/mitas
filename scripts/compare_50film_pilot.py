"""50-film V2.1 pilot vs eski 24-film Paddle baseline karşılaştırma.

Çıktı:
- stdout: 3 tablo (eski vs yeni delta / yeni 26 baseline / hata özeti)
- JSON dump: outputs/_ocr_50films_v21_paddle_compare.json

Per-item metrikler (segments opening + closing toplam):
- runtime_sec, total_events, cards_found, scroll_text_line_count,
  fallback_triggered, ocr_error_count, ocr_errors, warnings
"""

from __future__ import annotations

import json
import sys
import io
from pathlib import Path

OLD = Path("outputs/ocr_24films_aaaa_phase4_verify_20260525")
NEW = Path("outputs/ocr_50films_aaaa_v21_paddle_20260525")


def _read_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def aggregate_item(item_dir: Path) -> dict:
    summary = _read_json(item_dir / "item_summary.json")
    if not summary:
        return {"missing": True, "id": item_dir.name}

    total_runtime = 0.0
    total_events = 0
    total_cards = 0
    total_scroll = 0
    fallback_triggered = False
    fallback_reasons: list[str] = []
    fallback_events = 0
    ocr_errors_total = 0
    error_msgs: list[str] = []
    warnings_all: list[str] = []
    bad_status = []

    for seg in summary.get("segments", []) or []:
        total_runtime += float(seg.get("runtime_sec") or 0.0)
        if seg.get("status") and seg["status"] != "done":
            bad_status.append(f"{seg.get('segment_id')}:{seg['status']}")

        # Segment summary'yi oku (cards, scroll, fallback)
        sum_path = seg.get("summary_path")
        if not sum_path:
            continue
        seg_sum = _read_json(Path(sum_path))
        if not seg_sum:
            continue
        total_cards += int(seg_sum.get("cards_found") or 0)
        total_scroll += int(seg_sum.get("scroll_text_line_count") or 0)
        if seg_sum.get("fallback_triggered"):
            fallback_triggered = True
            r = seg_sum.get("fallback_reason")
            if r:
                fallback_reasons.append(f"{seg.get('segment_id')}:{r}")
            fallback_events += int(seg_sum.get("fallback_event_count") or 0)
        ocr_errors_total += int(seg_sum.get("ocr_error_count") or 0)

    # item-level errors/warnings
    for w in summary.get("warnings", []) or []:
        warnings_all.append(str(w))
    for e in summary.get("errors", []) or []:
        error_msgs.append(str(e))

    # Events file'larından total_events
    for seg in summary.get("segments", []) or []:
        ev_path = seg.get("events_path")
        if not ev_path:
            continue
        ev = _read_json(Path(ev_path))
        ev_summary = (ev or {}).get("summary") or {}
        total_events += int(ev_summary.get("total_events") or 0)

    return {
        "id": summary.get("id") or item_dir.name,
        "status": summary.get("status"),
        "runtime_sec": round(total_runtime, 1),
        "total_events": total_events,
        "cards": total_cards,
        "scroll_lines": total_scroll,
        "fallback_triggered": fallback_triggered,
        "fallback_reasons": fallback_reasons,
        "fallback_events": fallback_events,
        "ocr_error_count": ocr_errors_total,
        "errors": error_msgs,
        "warnings": warnings_all,
        "bad_segment_status": bad_status,
    }


def collect(base: Path) -> dict[str, dict]:
    out = {}
    items_dir = base / "items"
    if not items_dir.is_dir():
        return out
    for d in sorted(items_dir.iterdir()):
        if d.is_dir():
            out[d.name] = aggregate_item(d)
    return out


def fmt_delta(o: float | int, n: float | int) -> str:
    if o is None or n is None:
        return "-"
    d = n - o
    if isinstance(o, int) and isinstance(n, int):
        if o == 0:
            pct = "∞" if n > 0 else "—"
        else:
            pct = f"{(d / o * 100):+.0f}%"
        return f"{d:+d} ({pct})"
    if o == 0:
        return f"{d:+.1f}"
    return f"{d:+.1f} ({(d / o * 100):+.1f}%)"


def main() -> None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    old = collect(OLD)
    new = collect(NEW)
    common = sorted(set(old.keys()) & set(new.keys()))
    new_only = sorted(set(new.keys()) - set(old.keys()))

    # === TABLO 1: ESKI 24 vs YENI 24 (delta) ===
    print("=" * 100)
    print("TABLO 1 — ESKI 24 (eski Paddle baseline) vs YENI 24 (Paddle + V2.1 fallback)")
    print("=" * 100)
    hdr = f"{'film':<50}{'run(s)':>8} {'Δrun':>11} {'card':>5} {'Δ':>5} {'scrl':>5} {'Δscrl':>9} {'ev':>4} {'Δev':>5} {'fb':>3}"
    print(hdr)
    print("-" * len(hdr))
    totals = {"run_o": 0.0, "run_n": 0.0, "card_o": 0, "card_n": 0,
             "scr_o": 0, "scr_n": 0, "ev_o": 0, "ev_n": 0, "fb_count": 0}
    regressions = []
    for key in common:
        o, n = old[key], new[key]
        o_run, n_run = o.get("runtime_sec", 0), n.get("runtime_sec", 0)
        o_card, n_card = o.get("cards", 0), n.get("cards", 0)
        o_scr, n_scr = o.get("scroll_lines", 0), n.get("scroll_lines", 0)
        o_ev, n_ev = o.get("total_events", 0), n.get("total_events", 0)
        fb = "✓" if n.get("fallback_triggered") else ""
        totals["run_o"] += o_run; totals["run_n"] += n_run
        totals["card_o"] += o_card; totals["card_n"] += n_card
        totals["scr_o"] += o_scr; totals["scr_n"] += n_scr
        totals["ev_o"] += o_ev; totals["ev_n"] += n_ev
        if fb:
            totals["fb_count"] += 1
        # Regression: scroll veya card düşmüşse ve event'lar da düşmüşse
        if (n_scr < o_scr - 2 and n_ev < o_ev - 1) or (n_card < o_card - 1 and n_ev < o_ev - 1):
            regressions.append((key, o, n))
        film_short = key.replace("_end_credits", "")[:50]
        print(f"{film_short:<50}{n_run:>8.1f} {fmt_delta(o_run, n_run):>11} "
              f"{n_card:>5} {(n_card - o_card):>+5} "
              f"{n_scr:>5} {fmt_delta(o_scr, n_scr):>9} "
              f"{n_ev:>4} {(n_ev - o_ev):>+5} {fb:>3}")
    print("-" * len(hdr))
    print(f"{'TOPLAM (24 film)':<50}{totals['run_n']:>8.1f} "
          f"{fmt_delta(totals['run_o'], totals['run_n']):>11} "
          f"{totals['card_n']:>5} {(totals['card_n'] - totals['card_o']):>+5} "
          f"{totals['scr_n']:>5} {fmt_delta(totals['scr_o'], totals['scr_n']):>9} "
          f"{totals['ev_n']:>4} {(totals['ev_n'] - totals['ev_o']):>+5} "
          f"{totals['fb_count']:>3}")
    print()
    if regressions:
        print(f"⚠️  REGRESSION ŞÜPHESİ ({len(regressions)} film):")
        for key, o, n in regressions:
            print(f"   - {key}: cards {o['cards']}→{n['cards']}, scroll {o['scroll_lines']}→{n['scroll_lines']}, events {o['total_events']}→{n['total_events']}")
    else:
        print("✅ Regression yok — hiçbir film cards/scroll/events açısından kötüleşmedi.")
    print()

    # === TABLO 2: YENI 26 BASELINE ===
    print("=" * 100)
    print("TABLO 2 — YENI 26 FILM (V2.1 ilk pilot, baseline yok)")
    print("=" * 100)
    hdr2 = f"{'film':<50}{'run(s)':>8} {'card':>5} {'scrl':>5} {'ev':>5} {'fb':>3} {'err':>4}"
    print(hdr2)
    print("-" * len(hdr2))
    nb = {"run": 0.0, "card": 0, "scr": 0, "ev": 0, "fb": 0, "err": 0}
    no_output = []
    for key in new_only:
        n = new[key]
        run, card, scr, ev = n.get("runtime_sec", 0), n.get("cards", 0), n.get("scroll_lines", 0), n.get("total_events", 0)
        err = n.get("ocr_error_count", 0)
        fb = "✓" if n.get("fallback_triggered") else ""
        nb["run"] += run; nb["card"] += card; nb["scr"] += scr; nb["ev"] += ev
        if fb: nb["fb"] += 1
        nb["err"] += err
        if card == 0 and scr == 0:
            no_output.append(key)
        film_short = key.replace("_end_credits", "")[:50]
        print(f"{film_short:<50}{run:>8.1f} {card:>5} {scr:>5} {ev:>5} {fb:>3} {err:>4}")
    print("-" * len(hdr2))
    print(f"{'TOPLAM (26 film)':<50}{nb['run']:>8.1f} {nb['card']:>5} {nb['scr']:>5} {nb['ev']:>5} {nb['fb']:>3} {nb['err']:>4}")
    print()
    if no_output:
        print(f"⚠️  SIFIR ÇIKTI ({len(no_output)} film — Paddle+fallback ikisi de boş):")
        for k in no_output:
            print(f"   - {k}")
    print()

    # === TABLO 3: HATA / WARNING ÖZETİ (50 FILM) ===
    print("=" * 100)
    print("TABLO 3 — HATA + UYARI ÖZETI (50 film tüm)")
    print("=" * 100)
    issues = []
    for key, n in new.items():
        bs = n.get("bad_segment_status") or []
        errs = n.get("errors") or []
        ocr_err = n.get("ocr_error_count", 0)
        warns = n.get("warnings") or []
        if bs or errs or ocr_err or warns:
            issues.append((key, bs, errs, ocr_err, warns))
    if not issues:
        print("✅ Hiçbir filmde hata / uyarı yok.")
    else:
        for key, bs, errs, ocr_err, warns in issues:
            film = key.replace("_end_credits", "")
            parts = []
            if bs: parts.append(f"bad_segments={bs}")
            if errs: parts.append(f"errors={errs[:2]}")
            if ocr_err: parts.append(f"ocr_err={ocr_err}")
            if warns: parts.append(f"warn={warns[:2]}")
            print(f"  - {film}: {', '.join(parts)}")
    print()

    # === FALLBACK TETİKLEME ÖZETİ ===
    print("=" * 100)
    print("V2.1 FALLBACK TETİKLEME — hangi filmlerde OneOCR re-run koştu")
    print("=" * 100)
    fb_items = [(k, v) for k, v in new.items() if v.get("fallback_triggered")]
    if not fb_items:
        print("Hiçbir filmde fallback tetiklenmedi (yani Paddle hep yeterliydi).")
    else:
        for k, v in sorted(fb_items):
            film = k.replace("_end_credits", "")
            print(f"  - {film}: reasons={v.get('fallback_reasons')}, events=+{v.get('fallback_events')}")
    print()

    # JSON dump
    out = {
        "old_base": str(OLD),
        "new_base": str(NEW),
        "old_24": old,
        "new_24_compared": {k: new[k] for k in common},
        "new_26_baseline": {k: new[k] for k in new_only},
        "summary_totals_24": totals,
        "summary_totals_new_26": nb,
        "regressions": [k for k, _, _ in regressions],
        "no_output_new_26": no_output,
        "fallback_triggered_films": [k for k, _ in fb_items],
    }
    Path("outputs/_ocr_50films_v21_paddle_compare.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"JSON dump: outputs/_ocr_50films_v21_paddle_compare.json")


if __name__ == "__main__":
    main()
