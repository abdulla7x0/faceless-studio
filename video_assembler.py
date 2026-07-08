"""
Core sync fix, explained:

MoneyPrinterTurbo (and most clones) build ONE long audio track, then
separately stitch clips to roughly fill that total length, then run
Whisper on the audio afterwards to guess subtitle timing. Any mismatch
in that chain (whisper mistranscribing, clip lengths not lining up)
shows up as visible desync.

Here, instead: each SENTENCE already has its own audio file with a known
exact duration (from voice_generator.py). For each sentence we:
  1. load a video clip
  2. loop it (if too short) or trim it (if too long) to match THAT
     sentence's audio duration, frame-accurately
  3. attach that sentence's own audio to that segment
Then we concatenate the segments in order. Because each segment's
picture and its audio were sized from the same duration value, sync is
guaranteed by construction -- there's nothing to "detect" or "fix"
after the fact.

Subtitles are burned in from the same known per-sentence start/end
times, not re-derived via transcription.
"""

import os
from moviepy import (
    VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips,
)
from moviepy.video.fx import Loop, Resize, Crop

TARGET_W, TARGET_H = 1080, 1920  # vertical, for Reels/Shorts


def _fit_vertical(clip: VideoFileClip) -> VideoFileClip:
    """Resize+crop a clip to fill a 1080x1920 vertical frame without distortion."""
    scale = max(TARGET_W / clip.w, TARGET_H / clip.h)
    clip = clip.with_effects([Resize(scale)])
    x_center, y_center = clip.w / 2, clip.h / 2
    clip = clip.with_effects([Crop(
        x_center=x_center, y_center=y_center, width=TARGET_W, height=TARGET_H
    )])
    return clip


def _clip_to_duration(path: str, duration: float) -> VideoFileClip:
    clip = VideoFileClip(path)
    clip = _fit_vertical(clip)

    if clip.duration < duration:
        clip = clip.with_effects([Loop(duration=duration)])
    else:
        clip = clip.subclipped(0, duration)

    return clip.with_duration(duration)


def _subtitle_clip(text: str, duration: float, font_path: str | None) -> TextClip:
    kwargs = dict(
        text=text,
        font_size=64,
        color="white",
        stroke_color="black",
        stroke_width=3,
        method="caption",
        size=(int(TARGET_W * 0.9), None),
        text_align="center",
    )
    if font_path:
        kwargs["font"] = font_path
    txt = TextClip(**kwargs)
    txt = txt.with_duration(duration).with_position(("center", int(TARGET_H * 0.78)))
    return txt


def build_video(sentences_with_clips: list[dict], out_path: str,
                 font_path: str | None = None, fps: int = 24):
    """
    sentences_with_clips: list of dicts, each needs:
        "text"        - narration line (used for burned-in subtitle)
        "audio_path"  - mp3 path from voice_generator
        "duration"    - seconds, from voice_generator
        "clip_path"   - video file path, from footage_finder
    """
    segments = []
    for s in sentences_with_clips:
        audio_part = AudioFileClip(s["audio_path"])
        duration = audio_part.duration

        video_part = _clip_to_duration(s["clip_path"], duration)
        video_part = video_part.with_audio(audio_part)

        subtitle = _subtitle_clip(s["text"], duration, font_path)
        segment = CompositeVideoClip([video_part, subtitle], size=(TARGET_W, TARGET_H))
        segment = segment.with_duration(duration)
        segments.append(segment)

    final = concatenate_videoclips(segments, method="compose")
    final.write_videofile(
        out_path, fps=fps, codec="libx264", audio_codec="aac",
        threads=4, preset="ultrafast",
    )

    for seg in segments:
        seg.close()
    final.close()

    return out_path
