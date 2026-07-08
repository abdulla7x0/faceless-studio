"""
Faceless Video Studio -- end to end: topic -> synced vertical video.

Usage:
    python main.py --topic "5 gold trading mistakes beginners make" \\
                    --language hi --gender female \\
                    --clips_dir ./my_clips --out ./output

    python main.py --script my_script.txt --language ta --out ./output
        (uses your own script text instead of an LLM)

See .env.example for API keys -- copy it to .env and fill in what you need.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

import script_writer
import voice_generator
import footage_finder
import video_assembler
import srt_writer


def run_pipeline(
    topic: str | None = None,
    script_path: str | None = None,
    language: str = "hi",
    gender: str = "female",
    voice: str | None = None,
    rate: str = "+0%",
    num_sentences: int = 8,
    clips_dir: str | None = None,
    out_dir: str = "./output",
    font_path: str | None = None,
    progress_callback = None
):
    if not topic and not script_path:
        raise ValueError("Provide either topic or script_path.")

    os.makedirs(out_dir, exist_ok=True)
    audio_dir = os.path.join(out_dir, "audio")
    footage_cache = os.path.join(out_dir, "footage_cache")

    # 1. Script
    if progress_callback:
        progress_callback("Writing script...", 10)
    if script_path:
        data = script_writer.load_manual_script(script_path, language=language)
    else:
        print("Writing script...")
        data = script_writer.generate_script(
            topic, language=language, num_sentences=num_sentences
        )
    sentences = data["sentences"]
    print(f"Script: '{data['title']}' -- {len(sentences)} lines")

    # 2. Voice (per-sentence, so each has an exact known duration)
    if progress_callback:
        progress_callback("Synthesizing voice audio...", 30)
    voice_name = voice_generator.resolve_voice(language, gender, voice)
    print(f"Synthesizing voice with {voice_name}...")
    sentences = voice_generator.generate_sentence_audio(sentences, voice_name, audio_dir, rate)

    # 3. Footage (local first, Pexels fallback), sized per-sentence later
    if progress_callback:
        progress_callback("Finding visual footage...", 50)
    pexels_key = os.environ.get("PEXELS_API_KEY")
    print("Finding footage for each line...")
    for s in sentences:
        s["clip_path"] = footage_finder.find_clip_for_sentence(
            s["keywords"], clips_dir, footage_cache, pexels_key
        )

    # 4. Assemble -- sync guaranteed because each segment's picture length
    #    is derived from that same segment's own audio duration
    if progress_callback:
        progress_callback("Assembling final video (rendering frames)...", 70)
    out_video = os.path.join(out_dir, "final_video.mp4")
    print("Assembling final video (this can take a few minutes)...")
    video_assembler.build_video(sentences, out_video, font_path=font_path)

    # 5. Also write a standalone .srt
    if progress_callback:
        progress_callback("Generating subtitle files...", 90)
    out_srt = os.path.join(out_dir, "final_video.srt")
    srt_writer.write_srt(sentences, out_srt)

    if progress_callback:
        progress_callback("Video successfully generated!", 100)
    print(f"\nDone.\n  Video: {out_video}\n  Subtitles: {out_srt}")
    return out_video, out_srt


def main():
    load_dotenv()

    p = argparse.ArgumentParser(description="Generate a synced faceless video from a topic or script.")
    p.add_argument("--topic", help="Topic for the LLM to write a script about")
    p.add_argument("--script", help="Path to a .txt file with your own script (one line per sentence)")
    p.add_argument("--language", default="hi", help="hi, ta, te, mr, bn, en (default: hi)")
    p.add_argument("--gender", default="female", choices=["male", "female"])
    p.add_argument("--voice", default=None, help="Override: exact edge-tts voice name")
    p.add_argument("--rate", default="+0%", help="Speech rate, e.g. +10%% or -10%%")
    p.add_argument("--num_sentences", type=int, default=8)
    p.add_argument("--clips_dir", default=None, help="Folder with your own video clips")
    p.add_argument("--out", default="./output", help="Output folder")
    p.add_argument("--font", default=None, help="Path to a .ttf font for subtitles (needed for non-Latin scripts!)")
    args = p.parse_args()

    run_pipeline(
        topic=args.topic,
        script_path=args.script,
        language=args.language,
        gender=args.gender,
        voice=args.voice,
        rate=args.rate,
        num_sentences=args.num_sentences,
        clips_dir=args.clips_dir,
        out_dir=args.out,
        font_path=args.font
    )


if __name__ == "__main__":
    main()
