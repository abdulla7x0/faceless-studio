"""
For each sentence's keywords, find a video clip:
  1. First look in your own local clips folder (filename match)
  2. If nothing matches, download a clip from Pexels (needs free API key)

Downloaded clips are cached in out_dir so repeated runs don't re-download.
"""

import os
import re
import requests

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"


def _find_local_clip(keywords: list[str], clips_dir: str | None) -> str | None:
    if not clips_dir or not os.path.isdir(clips_dir):
        return None

    files = [f for f in os.listdir(clips_dir) if f.lower().endswith((".mp4", ".mov", ".mkv"))]
    for kw in keywords:
        kw_norm = re.sub(r"[^a-z0-9]", "", kw.lower())
        for f in files:
            f_norm = re.sub(r"[^a-z0-9]", "", f.lower())
            if kw_norm and kw_norm in f_norm:
                return os.path.join(clips_dir, f)
    return None


def _download_from_pexels(keywords: list[str], cache_dir: str, api_key: str) -> str | None:
    query = " ".join(keywords[:2])
    headers = {"Authorization": api_key}
    params = {"query": query, "orientation": "portrait", "per_page": 5}

    resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    videos = resp.json().get("videos", [])
    if not videos:
        return None

    # pick a reasonably sized HD file, not the huge 4k original
    video_files = sorted(
        videos[0]["video_files"],
        key=lambda vf: abs((vf.get("height") or 0) - 1280),
    )
    best = next((vf for vf in video_files if vf.get("file_type") == "video/mp4"), video_files[0])

    os.makedirs(cache_dir, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_") or "clip"
    out_path = os.path.join(cache_dir, f"{safe_name}_{videos[0]['id']}.mp4")

    if os.path.exists(out_path):
        return out_path

    with requests.get(best["link"], stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)

    return out_path


def find_clip_for_sentence(keywords: list[str], clips_dir: str | None,
                            pexels_cache_dir: str, pexels_api_key: str | None) -> str:
    local = _find_local_clip(keywords, clips_dir)
    if local:
        return local

    if pexels_api_key:
        remote = _download_from_pexels(keywords, pexels_cache_dir, pexels_api_key)
        if remote:
            return remote

    raise FileNotFoundError(
        f"No local clip matched keywords {keywords} in '{clips_dir}', "
        f"and Pexels had nothing (or no API key was set). "
        f"Add a clip to your clips folder whose filename contains one of these words."
    )
