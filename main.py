"""
main.py — Movie Shorts Bot orchestrator
Zero-touch: script → clip → edit → render → upload
"""
import os
import sys
import argparse
from script_generator import get_script_and_tts
from clip_downloader import download_movie_clip
from video_editor import edit_clip
from uploader import run_upload


def run_movie_shorts_bot(no_upload=False, video_url=None, no_tts=False):
    print("=" * 50)
    print("  🎬 MOVIE SHORTS BOT — ZERO TOUCH")
    print("=" * 50)

    elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY", "")

    # STEP 1: Pick script + generate TTS
    print("\n>>> STEP 1: Script & TTS...")
    script, tts_path = get_script_and_tts(elevenlabs_key, no_tts=no_tts)
    if not script:
        print("FAILED: No script available.")
        return False

    # STEP 2: Download movie clip
    print("\n>>> STEP 2: Downloading movie clip...")
    try:
        clip_path = download_movie_clip(video_url=video_url)
    except Exception as e:
        print(f"FAILED: Clip download error: {e}")
        return False

    if not clip_path or not os.path.exists(clip_path):
        print("FAILED: No clip downloaded.")
        return False

    # STEP 3: Edit clip + mux with TTS
    print("\n>>> STEP 3: Editing clip...")
    try:
        output_path = edit_clip(clip_path, tts_path, script["text"])
    except Exception as e:
        print(f"FAILED: Video edit error: {e}")
        return False

    if not os.path.exists(output_path):
        print("FAILED: Final video not generated.")
        return False

    if no_upload:
        print(f"\n✅ DRY RUN — Video ready: {output_path}")
        return True

    # STEP 4: Upload to YouTube Shorts
    print("\n>>> STEP 4: Uploading to YouTube...")
    upload_ok = run_upload(output_path, f"🎬 {script['title']}", is_short=True)

    if upload_ok:
        print("\n🎉 PIPELINE COMPLETE!")
    else:
        print("\n❌ Upload failed.")

    return upload_ok


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument("--no-tts", action="store_true")
    parser.add_argument("--url", type=str, default=None, help="Specific YouTube video URL")
    args = parser.parse_args()

    success = run_movie_shorts_bot(
        no_upload=args.no_upload,
        video_url=args.url,
        no_tts=args.no_tts,
    )
    sys.exit(0 if success else 1)
