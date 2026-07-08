# Faceless Video Studio

Topic in → synced vertical video out. No camera, no recording your own voice.

## Why this fixes the sync problem

Tools like MoneyPrinterTurbo build one long audio track for the whole
script, stitch clips to roughly match its total length, then run Whisper
on the audio afterward to *guess* subtitle timing. Any mistake in that
chain shows up as visible drift — especially with Indian-language speech,
which Whisper transcribes less reliably than English.

This tool generates **one audio file per sentence**, so each sentence's
exact duration is known upfront. Each video segment is then trimmed or
looped to that exact duration before the two are joined. Sync is
guaranteed by construction — there's nothing to detect or correct
afterward. Subtitles use the same known per-sentence timings, not a
transcription guess.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

You also need **ffmpeg** installed on your system (moviepy depends on it):
- Windows: `winget install ffmpeg` or download from ffmpeg.org
- Mac: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

Edit `.env`:
- Set `LLM_PROVIDER` to `openai`, `anthropic`, or `gemini`, and fill in that one key
- Fill in `PEXELS_API_KEY` (free, from https://www.pexels.com/api/) if you want
  automatic stock footage instead of only using your own clips

## Important: fonts for Hindi/Tamil/Telugu/etc subtitles

The default system font usually can't render Indian scripts, so subtitles
will show as boxes (□□□) if you don't pass a font. Download a free
Noto font for your script and pass it in:

- Hindi/Marathi (Devanagari): [Noto Sans Devanagari](https://fonts.google.com/noto/specimen/Noto+Sans+Devanagari)
- Tamil: [Noto Sans Tamil](https://fonts.google.com/noto/specimen/Noto+Sans+Tamil)
- Telugu: [Noto Sans Telugu](https://fonts.google.com/noto/specimen/Noto+Sans+Telugu)
- Bengali: [Noto Sans Bengali](https://fonts.google.com/noto/specimen/Noto+Sans+Bengali)

Download the `.ttf`, then pass `--font ./NotoSansDevanagari-Regular.ttf`.

## Usage

**LLM writes the script for you:**
```bash
python main.py --topic "5 gold trading mistakes beginners make" \
  --language hi --gender female \
  --clips_dir ./my_clips \
  --font ./NotoSansDevanagari-Regular.ttf \
  --out ./output
```

**You write your own script** (one sentence per line in a .txt file):
```bash
python main.py --script my_script.txt --language ta --out ./output
```

## Options

| Flag | Meaning |
|---|---|
| `--topic` | Topic for the LLM to write about (skip if using `--script`) |
| `--script` | Path to your own script .txt, one sentence per line |
| `--language` | `hi`, `ta`, `te`, `mr`, `bn`, `en` (default `hi`) |
| `--gender` | `male` or `female` voice (default `female`) |
| `--voice` | Override with an exact edge-tts voice name |
| `--rate` | Speech speed, e.g. `+10%` or `-10%` |
| `--num_sentences` | How many lines the LLM writes (default 8) |
| `--clips_dir` | Folder with your own footage — checked before Pexels |
| `--font` | Path to a `.ttf` — **required** for non-Latin subtitles |
| `--out` | Output folder (default `./output`) |

## Output

- `output/final_video.mp4` — 1080x1920 vertical video, burned-in subtitles
- `output/final_video.srt` — standalone subtitle file, in case a platform wants it separately
- `output/audio/` — the individual TTS sentence files, kept in case you want to reuse them
- `output/footage_cache/` — downloaded Pexels clips, cached so re-runs don't re-download

## If footage doesn't match your keywords

`--clips_dir` matching works by checking if a keyword appears in the
filename — e.g. a sentence with keyword "sunset" will match a file named
`beach_sunset_01.mp4`. Name your local clips accordingly, or just rely on
the Pexels fallback.

## Swapping in a paid TTS later

If you outgrow the free voice quality, ElevenLabs is a drop-in swap:
replace the body of `voice_generator.generate_sentence_audio()` with an
ElevenLabs API call instead of `edge_tts.Communicate` — everything else
(duration-matching, sync logic) stays the same since it only cares about
the resulting audio file and its duration.
