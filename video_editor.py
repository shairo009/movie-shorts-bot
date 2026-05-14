"""
video_editor.py — Edit clips to avoid copyright: speed change, crop, mirror, subs, mux TTS
Uses direct ffmpeg — no Playwright, no HTML rendering.
"""
import os
import random
import subprocess
import json


def run(cmd, desc="ffmpeg"):
    """Run an ffmpeg command, raise on failure."""
    print(f">>> {desc}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"{desc} failed:\n{result.stderr[-1000:]}")
    return result


def get_duration(path):
    """Get video duration in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except:
        return 0


def create_subtitle_overlay(text, lang="en"):
    """Create a subtitle SRT file for text overlay."""
    # Escape text for SRT
    import html
    text = html.escape(text, quote=False)
    srt = f"""1
00:00:00,000 --> 00:00:59,000
{text}

"""
    path = "downloads/subs.srt"
    os.makedirs("downloads", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(srt)
    return path


def edit_clip(input_path, tts_path, script_text, output_path="downloads/final_video.mp4"):
    """
    Full edit pipeline:
    1. Trim to 15-59 sec
    2. Speed change (±25-50%)
    3. Crop to 9:16
    4. Mirror/flip
    5. Add text subtitle overlay
    6. Mux with TTS audio (or silent)
    """
    os.makedirs("downloads", exist_ok=True)

    # Determine final duration target: 30-55 sec (Shorts range)
    orig_dur = get_duration(input_path)
    print(f">>> Original duration: {orig_dur:.1f}s")

    # Target: ~30-55 sec after editing
    target_dur = random.randint(30, 55)
    speed_factor = min(orig_dur / target_dur, 2.0)  # don't exceed 2x

    # Clamp speed factor to avoid detection triggers
    speed_factor = max(1.25, min(speed_factor, 1.75))
    if random.random() < 0.3:
        speed_factor = 1.0  # 0.3 chance: no speed change

    trim_dur = min(orig_dur, target_dur * speed_factor)
    speed_factor = orig_dur / trim_dur

    print(f">>> Speed factor: {speed_factor:.2f}x, trim: {trim_dur:.1f}s")

    work_dir = "downloads"
    tmp_speed = f"{work_dir}/step_speed.mp4"
    tmp_crop = f"{work_dir}/step_crop.mp4"
    tmp_mirror = f"{work_dir}/step_mirror.mp4"

    # === STEP 1: Speed change ===
    run([
        "ffmpeg", "-y", "-ss", "0", "-t", str(trim_dur),
        "-i", input_path,
        "-filter_complex",
        f"[0:v]setpts={1/speed_factor}*PTS[v];[0:a]atempo={speed_factor}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        tmp_speed
    ], "Step 1: Speed change")

    # === STEP 2: Crop to 9:16 ===
    # Detect source resolution
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "json", tmp_speed],
        capture_output=True, text=True,
    )
    try:
        info = json.loads(probe.stdout)
        streams = info.get("streams", [{}])
        w = streams[0].get("width", 1920)
        h = streams[0].get("height", 1080)
    except:
        w, h = 1920, 1080

    target_w = 1080
    target_h = 1920  # 9:16
    if w < 720:
        target_w, target_h = 540, 960

    # Calculate crop from center (vertical strip)
    crop_x = (w - target_w) // 2
    crop_y = 0  # top-aligned crop (most dramatic)
    # Alternatively: center crop
    # crop_y = max(0, (h - target_h * w // target_w) // 2)

    run([
        "ffmpeg", "-y", "-i", tmp_speed,
        "-vf", f"crop={target_w}:{target_h}:{crop_x}:{crop_y},scale={target_w}:{target_h}",
        "-c:a", "copy",
        tmp_crop
    ], "Step 2: Crop to 9:16")

    # === STEP 3: Mirror (50% chance) ===
    mirror = random.random() < 0.5
    if mirror:
        run([
            "ffmpeg", "-y", "-i", tmp_crop,
            "-vf", "hflip",
            "-c:a", "copy",
            tmp_mirror
        ], "Step 3: Mirror flip")
    else:
        import shutil
        shutil.copy(tmp_crop, tmp_mirror)

    # === STEP 4: Text subtitle overlay ===
    # Create a bottom bar with the script text
    sub_path = create_subtitle_overlay(script_text)
    tmp_subs = f"{work_dir}/step_subs.mp4"

    # Use ffmpeg drawtext for burned-in subtitle
    # Font setup — use default font on Ubuntu
    fontfile = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    if not os.path.exists(fontfile):
        fontfile = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
    if not os.path.exists(fontfile):
        fontfile = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

    bar_height = 180
    final_h = target_h + bar_height

    run([
        "ffmpeg", "-y", "-i", tmp_mirror,
        "-f", "lavfi", "-i",
        f"color=black:s={target_w}x{bar_height}:d={trim_dur/speed_factor:.1f}:r=1",
        "-filter_complex",
        f"[0:v]scale={target_w}:{target_h}[top];"
        f"[1:v]scale={target_w}:{bar_height}[bot];"
        f"[top][bot]vstack=inputs=2[outv]",
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        tmp_subs
    ], "Step 4: Add subtitle bar")

    # === STEP 5: Mux with TTS audio ===
    if tts_path and os.path.exists(tts_path):
        final_dur = get_duration(tmp_subs)
        tts_dur = get_duration(tts_path)
        print(f">>> TTS duration: {tts_dur:.1f}s, Video: {final_dur:.1f}s")

        # Trim TTS to fit video duration
        import shutil
        tmp_tts = f"{work_dir}/tts_trim.wav"
        subprocess.run([
            "ffmpeg", "-y", "-i", tts_path,
            "-t", str(min(tts_dur, final_dur)),
            "-ar", "44100", "-ac", "2",
            tmp_tts
        ], capture_output=True)

        run([
            "ffmpeg", "-y", "-i", tmp_subs,
            "-i", tmp_tts,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            output_path
        ], "Step 5: Mux TTS audio")
    else:
        # No TTS — make video silent
        run([
            "ffmpeg", "-y", "-i", tmp_subs,
            "-an",
            "-c:v", "copy",
            output_path
        ], "Step 5: Silent output")

    # Cleanup temp files
    for f in [tmp_speed, tmp_crop, tmp_mirror, tmp_subs]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except: pass

    final_dur = get_duration(output_path)
    print(f">>> Final video: {output_path} ({final_dur:.1f}s)")

    if final_dur < 15:
        raise Exception(f"Video too short: {final_dur:.1f}s (need 15-59s)")

    return output_path
