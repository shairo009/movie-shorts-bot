"""
script_generator.py — Picks a random script from pool + ElevenLabs TTS
"""
import os
import json
import random
import requests
from pathlib import Path

HISTORY_FILE = "scripts_history.txt"
POOL_FILE = "scripts_pool.json"
TTS_OUTPUT = "downloads/tts_voiceover.wav"
ELEVENLABS_MODEL = "eleven_monolingual_v1"
# Hindi voice — can swap to any ElevenLabs voice ID
ELEVENLABS_VOICE_ID = "pFZIHFjlDpKmaMWlqHEC"

HUMAN_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]


def load_pool():
    with open(POOL_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def pick_script():
    """Pick a random script from the pool, avoiding recent repeats."""
    pool = load_pool()
    history = load_history()

    # Try to pick something not in recent history
    available = [s for s in pool if str(s["id"]) not in history]
    if not available:
        # Reset history if everything used
        available = pool

    script = random.choice(available)

    # Mark as used (rotate through pool)
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"{script['id']}\n")

    # Keep history manageable (last 30)
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    if len(lines) > 30:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines[-30:]) + "\n")

    return script


def generate_tts(text, api_key, output_path=TTS_OUTPUT, voice_id=ELEVENLABS_VOICE_ID):
    """Generate TTS audio using ElevenLabs API."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "User-Agent": random.choice(HUMAN_USER_AGENTS),
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.5,
            "use_speaker_boost": True,
        },
    }

    print(f">>> ElevenLabs TTS: {len(text)} chars...")
    resp = requests.post(url, json=payload, headers=headers, timeout=60)

    if resp.status_code != 200:
        raise Exception(f"ElevenLabs API error {resp.status_code}: {resp.text}")

    with open(output_path, "wb") as f:
        f.write(resp.content)

    duration = len(resp.content) / (44100 * 2 * 1)
    print(f">>> TTS audio saved: {output_path} (~{duration:.1f}s)")

    return output_path


def get_script_and_tts(api_key, no_tts=False):
    """
    Main entry point: pick a script and generate TTS.
    Returns (script_dict, tts_path)
    """
    script = pick_script()
    print(f">>> Script picked: [{script['id']}] '{script['title']}'")
    print(f">>> Text: {script['text']}")

    tts_path = None
    if api_key and not no_tts:
        try:
            tts_path = generate_tts(script["text"], api_key)
        except Exception as e:
            print(f">>> TTS failed: {e} — continuing without audio")

    return script, tts_path
