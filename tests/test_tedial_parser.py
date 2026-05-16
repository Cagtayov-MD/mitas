from __future__ import annotations

from core.api.tedial.parser import parse_search_results


def test_parse_search_result_box_fragment() -> None:
    html = """
    <ul id="block-grid">
      <li class="block-section-box dragSearchElement not-draggable-result" id="box-1">
        <div id="box-4A66886E-C51A-01EF-8A7B-001000200100" class="large-12 columns">
          <h3><div>TRT ID:&nbsp;2024-0504-2-0100-90-1-YOK_IS_BIRLIGI_PROTOKOLU</div><div>ARSIV YER NO:&nbsp;-</div></h3>
          <img class="ar-content keyframeImg" src="https://evo.int.trt.net.tr:8181/MamService/KeyframeService/B10B9B06-5171-01F1-8C5E-0010007FFF00/asset/49880000?height=150&amp;quality=95">
          <input type="hidden" id="titleHidden" name="titleHidden" value="YOK IS BIRLIGI PROTOKOLU">
          <input type="hidden" id="sequenceIdHidden" name="sequenceIdHidden" value="4A66886E-C51A-01EF-8A7B-001000200100">
          <input type="hidden" id="assetIdIdHidden" name="assetIdIdHidden" value="4A5CC964-C51A-01EF-8A74-001000100100">
          <input type="hidden" name="fps" value="25.0">
          <input type="hidden" name="tcIn" value="0.0">
          <input type="hidden" name="tcOut" value="122280.0">
          <input type="hidden" name="imageTcIn" value="https://evo.int.trt.net.tr:8181/MamService/KeyframeService/repo/asset/0/floor">
          <input type="hidden" name="imageTcOut" value="https://evo.int.trt.net.tr:8181/MamService/KeyframeService/repo/asset/122280000/floor">
          <input type="hidden" name="assetType" value="VIDEO">
          <ul><li class="large-3 columns">nested icon row</li></ul>
        </div>
      </li>
    </ul>
    """

    results = parse_search_results(html)

    assert len(results) == 1
    result = results[0]
    assert result.box_id == "box-4A66886E-C51A-01EF-8A7B-001000200100"
    assert result.title == "YOK IS BIRLIGI PROTOKOLU"
    assert result.trt_id == "2024-0504-2-0100-90-1-YOK_IS_BIRLIGI_PROTOKOLU"
    assert result.repository_id == "B10B9B06-5171-01F1-8C5E-0010007FFF00"
    assert result.sequence_id == "4A66886E-C51A-01EF-8A7B-001000200100"
    assert result.asset_id == "4A5CC964-C51A-01EF-8A74-001000100100"
    assert result.asset_type == "VIDEO"
    assert result.fps == 25.0
    assert result.duration_units == 122280.0
    assert result.keyframe_url.endswith("quality=95")
