from __future__ import annotations

from core.api.tedial import (
    TedialConfig,
    extract_mpd_base_urls,
    keep_mpd_audio_track,
    select_mpd_audio_video_urls,
    select_mpd_media_url,
)


def test_extract_mpd_base_urls_from_namespaced_manifest() -> None:
    mpd = """
    <MPD xmlns="urn:mpeg:dash:schema:mpd:2011">
      <Period>
        <AdaptationSet>
          <Representation>
            <BaseURL>https://evo.int.trt.net.tr/cache_lowres/repo/asset/file.mp4</BaseURL>
          </Representation>
        </AdaptationSet>
      </Period>
    </MPD>
    """

    assert extract_mpd_base_urls(mpd) == ["https://evo.int.trt.net.tr/cache_lowres/repo/asset/file.mp4"]


def test_select_mpd_media_url_accepts_local_proxy_base_url() -> None:
    upstream = "https://evo.int.trt.net.tr/cache_lowres/repo/asset/file.mp4"
    mpd = f"<MPD><BaseURL>/api/tedial/media?url={upstream.replace(':', '%3A').replace('/', '%2F')}</BaseURL></MPD>"

    assert select_mpd_media_url(mpd, TedialConfig()) == upstream


def test_select_mpd_audio_video_urls_prefers_representation_mime_type() -> None:
    video = "https://evo.int.trt.net.tr/cache_lowres/repo/asset/video.mp4"
    audio = "https://evo.int.trt.net.tr/cache_lowres/repo/asset/audio.mp4"
    mpd = f"""
    <MPD xmlns="urn:mpeg:dash:schema:mpd:2011">
      <Period>
        <AdaptationSet>
          <Representation id="VIDEO-0" mimeType="video/mp4">
            <BaseURL>{video}</BaseURL>
          </Representation>
        </AdaptationSet>
        <AdaptationSet>
          <Representation id="AUDIO-0" mimeType="audio/mp4">
            <BaseURL>{audio}</BaseURL>
          </Representation>
        </AdaptationSet>
      </Period>
    </MPD>
    """

    assert select_mpd_audio_video_urls(mpd, TedialConfig()) == (video, audio)


def test_select_mpd_audio_video_urls_can_pick_second_audio_track() -> None:
    video = "https://evo.int.trt.net.tr/cache_lowres/repo/asset/video.mp4"
    audio_1 = "https://evo.int.trt.net.tr/cache_lowres/repo/asset/audio_1.mp4"
    audio_2 = "https://evo.int.trt.net.tr/cache_lowres/repo/asset/audio_2.mp4"
    mpd = f"""
    <MPD xmlns="urn:mpeg:dash:schema:mpd:2011">
      <Period>
        <AdaptationSet>
          <Representation id="VIDEO-0" mimeType="video/mp4">
            <BaseURL>{video}</BaseURL>
          </Representation>
        </AdaptationSet>
        <AdaptationSet>
          <Representation id="AUDIO-0" bandwidth="96000" mimeType="audio/mp4">
            <BaseURL>{audio_1}</BaseURL>
          </Representation>
        </AdaptationSet>
        <AdaptationSet>
          <Representation id="AUDIO-1" bandwidth="96000" mimeType="audio/mp4">
            <BaseURL>{audio_2}</BaseURL>
          </Representation>
        </AdaptationSet>
      </Period>
    </MPD>
    """

    assert select_mpd_audio_video_urls(mpd, TedialConfig(), audio_track_index=1) == (video, audio_2)


def test_keep_mpd_audio_track_removes_unselected_audio_sets() -> None:
    video = "/api/tedial/media?url=https%3A%2F%2Fevo.int.trt.net.tr%2Fcache_lowres%2Frepo%2Fasset%2Fvideo.mp4"
    audio_1 = "/api/tedial/media?url=https%3A%2F%2Fevo.int.trt.net.tr%2Fcache_lowres%2Frepo%2Fasset%2Faudio_1.mp4"
    audio_2 = "/api/tedial/media?url=https%3A%2F%2Fevo.int.trt.net.tr%2Fcache_lowres%2Frepo%2Fasset%2Faudio_2.mp4"
    audio_3 = "/api/tedial/media?url=https%3A%2F%2Fevo.int.trt.net.tr%2Fcache_lowres%2Frepo%2Fasset%2Faudio_3.mp4"
    mpd = f"""
    <MPD xmlns="urn:mpeg:dash:schema:mpd:2011">
      <Period>
        <AdaptationSet>
          <Representation id="VIDEO-0" bandwidth="382899" mimeType="video/mp4">
            <BaseURL>{video}</BaseURL>
          </Representation>
        </AdaptationSet>
        <AdaptationSet>
          <Representation id="AUDIO-0" bandwidth="98272" mimeType="audio/mp4">
            <BaseURL>{audio_1}</BaseURL>
          </Representation>
        </AdaptationSet>
        <AdaptationSet>
          <Representation id="AUDIO-1" bandwidth="2274" mimeType="audio/mp4">
            <BaseURL>{audio_2}</BaseURL>
          </Representation>
        </AdaptationSet>
        <AdaptationSet>
          <Representation id="AUDIO-2" bandwidth="2274" mimeType="audio/mp4">
            <BaseURL>{audio_3}</BaseURL>
          </Representation>
        </AdaptationSet>
      </Period>
    </MPD>
    """

    filtered = keep_mpd_audio_track(mpd, audio_track_index=1)
    urls = extract_mpd_base_urls(filtered)

    assert video in urls
    assert audio_2 in urls
    assert audio_1 not in urls
    assert audio_3 not in urls
