"""
Writes a .srt file from the sentence list's own known durations --
no Whisper transcription involved, so there's no risk of mistranscribed
Indian-language audio throwing off subtitle timing.
"""


def _format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


import os

def write_srt(sentences_with_durations: list[dict], out_path: str):
    parent_dir = os.path.dirname(out_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    lines = []
    t = 0.0
    for i, s in enumerate(sentences_with_durations, start=1):
        start = t
        end = t + s["duration"]
        lines.append(str(i))
        lines.append(f"{_format_timestamp(start)} --> {_format_timestamp(end)}")
        lines.append(s["text"])
        lines.append("")
        t = end

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return out_path
