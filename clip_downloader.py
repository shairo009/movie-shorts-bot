"""
clip_downloader.py — Download movie clip via Cobalt API + iOS bypass
Multi-engine approach: tries Cobalt first, falls back to iOS TikTok-style bypass
"""
import os
import re
import json
import random
import subprocess
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HISTORY_FILE = "clips_history.txt"

# Cobalt API instances (same as NCS bot)
COBALT_INSTANCES = [
    "https://api.cobalt.tools/",
    "https://cobalt.api.timelessnesses.me/",
    "https://cobalt.catto.space/",
]

# iOS/TikTok bypass instances
YTDLP_MOBILE_HEADERS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

# Movie trailer/clip channels on YouTube (public domain / promotional)
PROMO_CHANNELS = [
    "https://youtube.com/@MGM",
    "https://youtube.com/@WarnerBros",
    "https://youtube.com/@SonyPictures",
    "https://youtube.com/@UniversalPictures",
    "https://youtube.com/@ParamountMovies",
    "https://youtube.com/@Dreamworks",
    "https://youtube.com/@LionsgateMovies",
    "https://youtube.com/@Blumhouse",
]

# Fallback: Internet Archive movie sources (public domain)
ARCHIVE_SOURCES = [
    "https://archive.org/search?query=public+domain+movie",
]


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    return []


def save_to_history(video_id):
    os.makedirs("downloads", exist_ok=True)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{video_id}\n")


def pick_youtube_query():
    """Generate a random movie-related search query for yt-dlp to find clips."""
    queries = [
        "movie scene reaction",
        "best movie scene 2024",
        "cinematic moment",
        "movie climax scene",
        "dramatic movie scene",
        "intense movie moment",
        "emotional movie scene",
        "action movie scene",
        " thriller movie scene",
        "best dialogue scene",
        "movie scene caught on camera",
        "behind the scenes movie",
        "iconic movie moment",
        "movie scene you must see",
        "unreleased movie scene",
    ]
    return random.choice(queries)


def download_with_cobalt(url, output_path, mobile_ios=False):
    """Download video via Cobalt API."""
    api_url = random.choice(COBALT_INSTANCES)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": random.choice(YTDLP_MOBILE_HEADERS) if mobile_ios else random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        ]),
    }
    payload = {
        "url": url,
        "vQuality": "720",
        "aFormat": "mp3",
        "isAudioOnly": False,
    }

    resp = requests.post(
        f"{api_url}api/json",
        json=payload,
        headers=headers,
        timeout=30,
    )

    if resp.status_code != 200:
        raise Exception(f"Cobalt API error: {resp.status_code}")

    data = resp.json()

    if data.get("status") == "redirect" and data.get("url"):
        dl_url = data["url"]
    elif data.get("status") == "success" and data.get("urls"):
        urls = data["urls"]
        dl_url = urls[0].get("url") if isinstance(urls, list) else urls.get("url")
    elif data.get("status") == "picker":
        # Multi-format picker — grab first audio/video option
        items = data.get("items", [])
        dl_url = None
        for item in items:
            if item.get("type") in ("video", "audio"):
                dl_url = item.get("url")
                break
        if not dl_url and items:
            dl_url = items[0].get("url", "")
    else:
        raise Exception(f"Cobalt: unknown status {data.get('status')}")

    if not dl_url:
        raise Exception("Cobalt: no download URL returned")

    print(f">>> Cobalt download URL obtained, fetching...")
    r = requests.get(dl_url, headers={"User-Agent": headers["User-Agent"]}, timeout=120, stream=True)
    r.raise_for_status()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)

    return output_path


def download_with_ytdlp(url, output_path, mobile_ios=False):
    """Fallback: yt-dlp direct download (iOS bypass if mobile_ios=True)."""
    ua = random.choice(YTDLP_MOBILE_HEADERS) if mobile_ios else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    cmd = [
        "yt-dlp",
        "--write-auto-sub", "--skip-unavailable-fragments",
        "-f", "best[height<=720][ext=mp4]/best[ext=mp4]/best",
        "-o", output_path,
        "--no-playlist",
        "--user-agent", ua,
    ]
    if mobile_ios:
        cmd += ["--cookies-from-browser", "chrome"]  # Won't work on GitHub Actions — skip
    cmd.append(url)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise Exception(f"yt-dlp failed: {result.stderr}")
    return output_path


def get_clip_from_invidious(channel_url, output_path, invidious_instances):
    """Fallback: use Invidious API to find recent videos from a channel."""
    # Extract channel ID from URL
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"}

    # Pick working Invidious instance
    for inst in invidious_instances:
        try:
            # Get channel info
            resp = requests.get(f"{inst}/@MGM", timeout=10, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                videos = data.get("latestVideos", [])
                if videos:
                    vid = videos[0]
                    vid_url = f"https://www.youtube.com/watch?v={vid['videoId']}"
                    return download_with_cobalt(vid_url, output_path, mobile_ios=True)
        except:
            continue

    raise Exception("All Invidious instances failed")


def download_movie_clip(video_url=None, output_path="downloads/raw_clip.mp4"):
    """
    Main entry point. 
    If video_url is None, searches for a random clip via yt-dlp.
    """
    os.makedirs("downloads", exist_ok=True)
    history = load_history()

    if video_url:
        print(f">>> Downloading clip from: {video_url}")

    # === ENGINE 1: Cobalt API ===
    for i in range(3):  # retry each instance once
        cobalt_url = video_url or pick_youtube_query()
        try:
            if video_url:
                return download_with_cobalt(video_url, output_path, mobile_ios=True)
            else:
                # Search via yt-dlp first to get a URL
                search_q = pick_youtube_query()
                print(f">>> Searching for clip: {search_q}")
                result = subprocess.run(
                    ["yt-dlp", "--flat-playlist", "--get-title", "--no-playlist",
                     "ytsearch5:" + search_q],
                    capture_output=True, text=True, timeout=30,
                )
                videos = [l for l in result.stdout.splitlines() if l.strip()]
                if not videos:
                    raise Exception("No search results")

                # Pick random video not in history
                random.shuffle(videos)
                for vid in videos:
                    vid_id = hash(vid) % 100000
                    if str(vid_id) not in history:
                        print(f">>> Selected: {vid}")
                        save_to_history(str(vid_id))
                        return download_with_cobalt(vid, output_path, mobile_ios=True)
        except Exception as e:
            print(f">>> Cobalt attempt {i+1} failed: {e}")

    # === ENGINE 2: iOS bypass (direct YouTube via yt-dlp mobile UA) ===
    print(">>> Trying iOS bypass engine...")
    for i in range(3):
        try:
            search_q = pick_youtube_query()
            result = subprocess.run(
                ["yt-dlp", "--flat-playlist", "--get-id",
                 "ytsearch3:" + search_q],
                capture_output=True, text=True, timeout=30,
            )
            ids = [l.strip() for l in result.stdout.splitlines() if l.strip()]
            if ids:
                vid_url = f"https://www.youtube.com/watch?v={ids[0]}"
                return download_with_ytdlp(vid_url, output_path, mobile_ios=True)
        except Exception as e:
            print(f">>> iOS bypass attempt {i+1} failed: {e}")

    # === ENGINE 3: Invidious fallback ===
    print(">>> Trying Invidious fallback...")
    INVIDIOUS = [
        "https://invidious.snopyta.org",
        "https://inv.tux.pizza",
        "https://yt.artemislena.eu",
    ]
    for inst in INVIDIOUS:
        try:
            resp = requests.get(f"{inst}/api/v1/search?q=movie+trailer&type=video&limit=3", timeout=10)
            if resp.status_code == 200:
                results = resp.json()
                for vid in results:
                    vid_url = f"https://www.youtube.com/watch?v={vid['videoId']}"
                    return download_with_cobalt(vid_url, output_path, mobile_ios=True)
        except Exception as e:
            print(f">>> Invidious {inst} failed: {e}")

    raise Exception("All download engines exhausted — no clip found")
