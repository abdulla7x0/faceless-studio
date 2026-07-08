"""
Generates ONE audio file PER SENTENCE (not one big file for the whole script).

This is the key architectural decision that fixes the sync problem:
because we know the exact duration of each sentence's own audio, we can
size each sentence's video clip to match it exactly. There's no need to
reverse-engineer timing later with Whisper -- the timing is known by
construction.
"""

import asyncio
import os
import edge_tts
from mutagen.mp3 import MP3

# A few solid Indian-language voices to pick from.
# Run `edge-tts --list-voices | grep IN` for the full list.
INDIAN_VOICES = {
    "hi": {"male": "hi-IN-MadhurNeural", "female": "hi-IN-SwaraNeural"},
    "ta": {"male": "ta-IN-ValluvarNeural", "female": "ta-IN-PallaviNeural"},
    "te": {"male": "te-IN-MohanNeural", "female": "te-IN-ShrutiNeural"},
    "mr": {"male": "mr-IN-ManoharNeural", "female": "mr-IN-AarohiNeural"},
    "bn": {"male": "bn-IN-BashkarNeural", "female": "bn-IN-TanishaaNeural"},
    "en": {"male": "en-IN-PrabhatNeural", "female": "en-IN-NeerjaNeural"},
}


def resolve_voice(language: str, gender: str = "female", voice_override: str | None = None) -> str:
    if voice_override:
        return voice_override
    lang_voices = INDIAN_VOICES.get(language)
    if not lang_voices:
        raise ValueError(f"No built-in voice for language '{language}'. Pass voice_override explicitly.")
    return lang_voices.get(gender, list(lang_voices.values())[0])


async def _synthesize(text: str, voice: str, out_path: str, rate: str = "+0%"):
    retries = 3
    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(out_path)
            return  # Success!
        except Exception as e:
            if attempt == retries - 1:
                print(f"[TTS ERROR] Failed to synthesize text after {retries} attempts: '{text}' with voice '{voice}' and rate '{rate}'. Error: {e}")
                raise
            else:
                backoff = 2 ** attempt
                print(f"[TTS WARNING] Attempt {attempt + 1} failed for text '{text}'. Retrying in {backoff}s... Error: {e}")
                await asyncio.sleep(backoff)


def get_mp3_duration(path: str) -> float:
    return MP3(path).info.length


def generate_sentence_audio(sentences: list[dict], voice: str, out_dir: str,
                             rate: str = "+0%") -> list[dict]:
    """
    Takes the sentence list from script_writer.generate_script(), synthesizes
    one mp3 per sentence, and returns the SAME list with two new keys added
    to each sentence dict: "audio_path" and "duration" (seconds).
    """
    os.makedirs(out_dir, exist_ok=True)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for i, sentence in enumerate(sentences):
        out_path = os.path.join(out_dir, f"line_{i:03d}.mp3")
        loop.run_until_complete(_synthesize(sentence["text"], voice, out_path, rate))
        sentence["audio_path"] = out_path
        sentence["duration"] = get_mp3_duration(out_path)

    loop.close()
    return sentences
