"""
Read the panellist name labels off each episode's stream tiles.

    python tools/read_tiles.py                 # all episodes, resumes
    python tools/read_tiles.py --limit 3       # a short trial
    python tools/read_tiles.py --only VIDEOID

WHY THIS IS THE GOOD SOURCE. The captions cannot say who was on: the show reads a roll
call of first names, so a person credited on every episode can be spoken on one, and
pairing adjacent capitals invents people. The stream overlay, by contrast, prints each
panellist's name on their own tile - "Corvalis Cohen - Powercore2000", "Greg 'Midnite
Oil' Bradburn" - which is attendance evidence, per episode, in Jason's own words.

THE THREE THINGS THAT MAKE IT WORK, each learned the expensive way:

  * 360p, not 720p. A 3-second section at 360p arrives in about 8 seconds; the same
    section at 720p took over 200. Preprocessing the cheap frame beats fetching a dear
    one.
  * Never --force-keyframes-at-cuts. It re-encodes, and turned an 8-second fetch into a
    4-minute one that had to be killed.
  * Threshold, do not autocontrast. The labels are bright text on a mid-grey pill;
    stretching contrast flattens the two together and the OCR returns noise. Keeping only
    the bright pixels and inverting gives clean dark glyphs on white.

Several samples per episode, because a tile shows who is on camera AT THAT MOMENT: Johnny
was absent from #151 at 3 minutes and present at 45. What comes out is therefore a FLOOR,
never a census, and the site says so.
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
FRAMES = os.path.join(DATA, "frames")
OUT = os.path.join(DATA, "tiles.json")
TESS = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# A label is a person's name, optionally with the outfit they go by. Junk from the video
# behind the strip is short, punctuation-heavy, or full of replacement characters.
GOOD = re.compile(r"^[A-Za-z][A-Za-z0-9'’.&/\- ]{2,44}$")
JUNK = re.compile(r"(?:\ufffd|[|_~^]{2,}|\d{4,})")
STOP = {"the", "and", "for", "you", "live", "new", "off", "sale", "subscribe", "www",
        "com", "http", "https", "game dev show", "gamedevshow"}


def sample_times(duration):
    """Spread the samples: early enough to catch the opening, late enough for arrivals."""
    if not duration or duration < 240:
        return [90]
    marks = [0.03, 0.22, 0.45, 0.70]
    return [max(60, int(duration * m)) for m in marks]


def fetch_frame(vid, second, path, timeout=180):
    clip = path.replace(".jpg", ".mp4")
    span = "*%02d:%02d:%02d-%02d:%02d:%02d" % (
        second // 3600, (second % 3600) // 60, second % 60,
        (second + 2) // 3600, ((second + 2) % 3600) // 60, (second + 2) % 60)
    cmd = [sys.executable, "-m", "yt_dlp", "--quiet", "--no-warnings",
           "--download-sections", span,
           "-f", "worstvideo[height>=360]/worst",
           "-o", clip, "https://www.youtube.com/watch?v=" + vid]
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False
    if not os.path.exists(clip):
        return False
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", clip,
                    "-frames:v", "1", "-q:v", "2", path, "-y"],
                   capture_output=True, timeout=90)
    try:
        os.remove(clip)
    except OSError:
        pass
    return os.path.exists(path)


def read_labels(path, cutoff=190, scale=4):
    """Label strips sit at the foot of each tile, so scan the 1-, 2- and 3-row bands."""
    im = Image.open(path)
    W, H = im.size
    seen, out = set(), []
    for rows in (1, 2, 3):
        for r in range(rows):
            bottom = int(H * (r + 1) / rows)
            top = bottom - int(H * 0.075)
            if top < 0:
                continue
            key = (top, bottom)
            if key in seen:
                continue
            seen.add(key)
            strip = im.crop((0, top, W, bottom)).convert("L")
            strip = strip.resize((strip.width * scale, strip.height * scale), Image.LANCZOS)
            strip = strip.point(lambda v: 0 if v > cutoff else 255)
            tmp = os.path.join(FRAMES, "_strip.png")
            strip.save(tmp)
            res = subprocess.run([TESS, tmp, "-", "--psm", "11"], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=90)
            for line in (res.stdout or "").splitlines():
                line = " ".join(line.split()).strip(" .,:;|-")
                if len(line) < 3 or JUNK.search(line) or not GOOD.match(line):
                    continue
                if line.lower() in STOP or sum(c.isalpha() for c in line) < 3:
                    continue
                out.append(line)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default=None)
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()

    os.makedirs(FRAMES, exist_ok=True)
    episodes = json.load(open(os.path.join(DATA, "episodes.json"), encoding="utf-8"))["episodes"]
    episodes = [e for e in episodes if not e.get("audio_only")]
    if args.only:
        episodes = [e for e in episodes if e["id"] == args.only]

    done = {}
    if os.path.exists(OUT):
        done = json.load(open(OUT, encoding="utf-8"))

    todo = [e for e in episodes if e["id"] not in done]
    if args.limit:
        todo = todo[:args.limit]
    print("episodes: %d, already read: %d, to read: %d" % (len(episodes), len(done), len(todo)),
          flush=True)

    for n, ep in enumerate(todo, 1):
        started = time.time()
        labels = {}
        for second in sample_times(ep.get("duration")):
            path = os.path.join(FRAMES, "%s-%05d.jpg" % (ep["id"], second))
            if not os.path.exists(path) and not fetch_frame(ep["id"], second, path):
                continue
            for name in read_labels(path):
                labels.setdefault(name, second)
            time.sleep(args.sleep + random.uniform(0, 0.8))
        done[ep["id"]] = {"date": ep["date"], "title": ep["title"],
                          "labels": [{"label": k, "t": v} for k, v in sorted(labels.items())]}
        with open(OUT, "w", encoding="utf-8") as handle:
            json.dump(done, handle, indent=1, ensure_ascii=False)
        print("[%3d/%d] %s %-11s %2d labels %3.0fs  %s"
              % (n, len(todo), ep["date"], ep["id"], len(labels), time.time() - started,
                 "; ".join(sorted(labels)[:3])), flush=True)

    print("DONE. %d episodes read -> %s" % (len(done), OUT), flush=True)


if __name__ == "__main__":
    main()
