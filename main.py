"""Auto YouTube Shorts: script (Gemini) -> images (Pollinations) -> voice (edge-tts)
-> video (FFmpeg) -> upload (YouTube Data API). Designed to run on GitHub Actions."""
import asyncio
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.parse

import edge_tts
import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

W, H = 1080, 1920
FPS = 30
WORK = pathlib.Path("work")
HISTORY = pathlib.Path("history.json")

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
NICHE = os.getenv("VIDEO_NICHE", "gaming facts, secrets, and short stories about popular video games")
VOICE = os.getenv("VOICE", "en-US-GuyNeural")
PRIVACY = os.getenv("PRIVACY", "public")  # public | unlisted | private


def load_history():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return []


def make_script(history):
    recent = "; ".join(history[-30:]) or "none yet"
    prompt = f"""You write scripts for YouTube Shorts in this niche: {NICHE}.
Write ONE new video. Do not repeat these recent titles: {recent}.
Rules:
- Total narration 90-120 words (about 45 seconds spoken), English, punchy hook in the first sentence.
- Split into 6 scenes. Each scene has one short narration line and one image_prompt.
- image_prompt: a vivid, detailed visual description for an AI image generator. Original fantasy/game-style
  art only. No real people, no logos, no text in the image, no copyrighted character names.
Return JSON only, exactly this shape:
{{"title": "...(max 70 chars, no hashtags)", "description": "...(2-3 sentences)", "tags": ["..."],
  "scenes": [{{"narration": "...", "image_prompt": "..."}}]}}"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    r = requests.post(
        url,
        params={"key": GEMINI_KEY},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
        },
        timeout=120,
    )
    r.raise_for_status()
    text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(text)
    if not data.get("scenes"):
        raise RuntimeError("Gemini returned no scenes")
    return data


def make_image(prompt, path, seed):
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt + ", cinematic, vertical, high detail")
    last = None
    for attempt in range(4):
        try:
            r = requests.get(
                url,
                params={"width": W, "height": H, "nologo": "true", "seed": seed},
                timeout=180,
            )
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                path.write_bytes(r.content)
                return
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Image generation failed: {last}")


async def _edge_voice(text, path):
    await edge_tts.Communicate(text, VOICE).save(str(path))


def make_voice(text, path):
    # 1) edge-tts, retried because Microsoft's free service fails randomly
    for attempt in range(4):
        try:
            asyncio.run(_edge_voice(text, path))
            if path.exists() and path.stat().st_size > 1000:
                return
        except Exception as e:
            print(f"edge-tts attempt {attempt + 1} failed: {e}")
        time.sleep(5 * (attempt + 1))
    # 2) backup voice: Google gTTS
    from gtts import gTTS
    print("Falling back to gTTS")
    gTTS(text=text, lang="en").save(str(path))


def duration(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out.decode().strip())


def make_clip(img, audio, out):
    dur = duration(audio) + 0.3
    frames = int(dur * FPS) + 1
    vf = (
        f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
        f"zoompan=z='min(zoom+0.0007,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={W}x{H}:fps={FPS},format=yuv420p"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(img), "-i", str(audio),
            "-vf", vf, "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-ar", "44100", "-ac", "2",
            "-af", "apad", "-shortest", str(out),
        ],
        check=True,
    )


def build_video(scenes):
    WORK.mkdir(exist_ok=True)
    clips = []
    for i, s in enumerate(scenes):
        img = WORK / f"s{i}.jpg"
        aud = WORK / f"s{i}.mp3"
        clip = WORK / f"c{i}.mp4"
        print(f"Scene {i + 1}/{len(scenes)}")
        make_image(s["image_prompt"], img, seed=int(time.time()) + i)
        make_voice(s["narration"], aud)
        make_clip(img, aud, clip)
        clips.append(clip)
    listing = WORK / "list.txt"
    listing.write_text("".join(f"file '{c.name}'\n" for c in clips))
    final = WORK / "final.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(final)],
        check=True,
    )
    print(f"Final video length: {duration(final):.1f}s")
    return final


def upload(video, meta):
    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds)
    title = meta["title"][:90]
    if "#shorts" not in title.lower():
        title = (title[:80] + " #Shorts").strip()
    body = {
        "snippet": {
            "title": title,
            "description": meta.get("description", "") + "\n\n#Shorts #Gaming",
            "tags": meta.get("tags", [])[:15],
            "categoryId": "20",  # Gaming
        },
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"Upload {int(status.progress() * 100)}%")
    print("Uploaded video id:", resp["id"])
    return resp["id"]


def main():
    history = load_history()
    meta = make_script(history)
    print("Title:", meta["title"])
    video = build_video(meta["scenes"])
    upload(video, meta)
    history.append(meta["title"])
    HISTORY.write_text(json.dumps(history[-100:], indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FAILED:", e, file=sys.stderr)
        raise
