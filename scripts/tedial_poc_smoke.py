"""Offline smoke check for the Tedial Phase 1 POC primitives.

This does not call Tedial. It verifies that the session broker can attach a
cookie header, the proxy service can plan safe upstream calls, the HTML parser
can extract an asset row, and MPD BaseURL rewrite keeps media behind MITAS.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.api.tedial import TedialConfig, TedialProxyService, TedialSessionBroker, parse_search_results, rewrite_mpd_base_urls


SAMPLE_HTML = """
<ul id="block-grid">
  <li class="block-section-box dragSearchElement not-draggable-result" id="box-1">
    <div id="box-4A66886E-C51A-01EF-8A7B-001000200100" class="large-12 columns">
      <img class="ar-content keyframeImg" src="https://evo.int.trt.net.tr:8181/MamService/KeyframeService/B10B9B06-5171-01F1-8C5E-0010007FFF00/4A5CC964-C51A-01EF-8A74-001000100100/49880000?height=150&amp;quality=95">
      <input type="hidden" id="titleHidden" name="titleHidden" value="YOK IS BIRLIGI PROTOKOLU">
      <input type="hidden" id="sequenceIdHidden" name="sequenceIdHidden" value="4A66886E-C51A-01EF-8A7B-001000200100">
      <input type="hidden" id="assetIdIdHidden" name="assetIdIdHidden" value="4A5CC964-C51A-01EF-8A74-001000100100">
      <input type="hidden" name="fps" value="25.0">
      <input type="hidden" name="tcIn" value="0.0">
      <input type="hidden" name="tcOut" value="122280.0">
      <input type="hidden" name="assetType" value="VIDEO">
    </div>
  </li>
</ul>
"""

SAMPLE_MPD = """
<MPD>
  <BaseURL>https://evo.int.trt.net.tr/cache_lowres/445/925/video.mp4</BaseURL>
</MPD>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default="dev-local")
    parser.add_argument("--cookie", default="JSESSIONID=offline-smoke")
    parser.add_argument("--search", default="tr-*")
    args = parser.parse_args()

    broker = TedialSessionBroker()
    broker.attach_cookie_header(args.user_id, args.cookie)
    service = TedialProxyService(broker=broker, config=TedialConfig())

    search_plan = service.plan_search(args.user_id, args.search)
    results = parse_search_results(SAMPLE_HTML)
    rewritten_mpd = rewrite_mpd_base_urls(SAMPLE_MPD, service.config)

    report = {
        "session": service.session_status(args.user_id).to_dict(),
        "search_plan": {
            "method": search_plan.method,
            "url": search_plan.url,
            "headers": {k: "<MASKED>" if k.lower() == "cookie" else v for k, v in search_plan.headers.items()},
            "body_len": len(search_plan.body or b""),
        },
        "parsed_results": [asdict(item) for item in results],
        "rewritten_mpd": rewritten_mpd.strip(),
        "note": "This smoke is offline: it covers broker/parser/proxy primitives and does not call Tedial.",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
