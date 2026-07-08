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

    if not args.topic and not args.script:
        sys.exit("Provide either --topic (LLM writes it) or --script (your own text file).")

    os.makedirs(args.out, exist_ok=True)
    audio_dir = os.path.join(args.out, "audio")
    footage_cache = os.path.join(args.out, "footage_cache")

    # 1. Script
    if args.script:
        data = script_writer.load_manual_script(args.script, language=args.language)
    else:
        print("Writing script...")
        data = script_writer.generate_script(
            args.topic, language=args.language, num_sentences=args.num_sentences
        )
    sentences = data["sentences"]
    print(f"Script: '{data['title']}' -- {len(sentences)} lines")

    # 2. Voice (per-sentence, so each has an exact known duration)
    voice = voice_generator.resolve_voice(args.language, args.gender, args.voice)
    print(f"Synthesizing voice with {voice}...")
    sentences = voice_generator.generate_sentence_audio(sentences, voice, audio_dir, args.rate)

    # 3. Footage (local first, Pexels fallback), sized per-sentence later
    pexels_key = os.environ.get("PEXELS_API_KEY")
    print("Finding footage for each line...")
    for s in sentences:
        s["clip_path"] = footage_finder.find_clip_for_sentence(
            s["keywords"], args.clips_dir, footage_cache, pexels_key
        )

    # 4. Assemble -- sync guaranteed because each segment's picture length
    #    is derived from that same segment's own audio duration
    out_video = os.path.join(args.out, "final_video.mp4")
    print("Assembling final video (this can take a few minutes)...")
    video_assembler.build_video(sentences, out_video, font_path=args.font)

    # 5. Also write a standalone .srt, useful for platforms that want
    #    a separate subtitle upload alongside burned-in captions
    out_srt = os.path.join(args.out, "final_video.srt")
    srt_writer.write_srt(sentences, out_srt)

    print(f"\nDone.\n  Video: {out_video}\n  Subtitles: {out_srt}")


if __name__ == "__main__":
    main()
