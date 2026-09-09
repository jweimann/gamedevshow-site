"""
Collects public metadata and English captions for every Game Dev Show episode.

    python tools/collect.py            # resumes; skips anything already on disk
    python tools/collect.py --limit 5  # a short trial run

Reads the two playlist dumps in data/raw/, takes the union of video ids, and for each
one asks yt-dlp for the info JSON and the English subtitle track. Metadata and captions
only: --skip-download means no video or audio is ever fetched.

PACED ON PURPOSE. This runs on the machine somebody is working at, and 174 videos back
to back looks like scraping to YouTube and gets the whole machine throttled. There is a
sleep between videos and a longer one after any failure, and every result is cached to
disk so a rerun costs nothing for what already landed.

Captions are used downstream to DERIVE tags and the timestamps that evidence them. The
site never republishes transcript text beyond a few words of context per hit.
"""

import argparse
import glob
import json
import os
import random
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
INFO = os.path.join(RAW, "videos")
SUBS = os.path.join(ROOT, "data", "transcripts")


def video_ids():
    """Union of the two playlists, in the order the newest playlist lists them."""
    seen = {}
    for path in sorted(glob.glob(os.path.join(RAW, "playlist-*.json"))):
        data = json.load(open(path, encoding="utf-8"))
        for entry in data.get("entries") or []:
            if entry.get("title"):  # private and deleted videos have no title
                seen.setdefault(entry["id"], entry["title"])
    return seen


def have(vid):
    info = os.path.join(INFO, vid + ".info.json")
    subs = glob.glob(os.path.join(SUBS, vid + "*.vtt"))
    return os.path.exists(info), bool(subs)


def fetch(vid, timeout):
    """One yt-dlp call for both the metadata and the captions."""
    cmd = [sys.executable, "-m", "yt_dlp",
           "--skip-download",
           "--write-info-json",
           "--write-subs", "--write-auto-subs",
           "--sub-langs", "en-orig,en,en-US",
           "--sub-format", "vtt",
           "--no-warnings",
           "--retries", "2",
           "-o", os.path.join(INFO, "%(id)s.%(ext)s"),
           "-o", "subtitle:" + os.path.join(SUBS, "%(id)s.%(ext)s"),
           "https://www.youtube.com/watch?v=" + vid]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stderr or "")[-400:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=2.5, help="seconds between videos")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    os.makedirs(INFO, exist_ok=True)
    os.makedirs(SUBS, exist_ok=True)
    ids = video_ids()
    print("catalogue: %d watchable videos" % len(ids), flush=True)

    todo = [v for v in ids if not all(have(v))]
    if args.limit:
        todo = todo[:args.limit]
    print("to fetch: %d (the rest are already on disk)" % len(todo), flush=True)

    failures = []
    for n, vid in enumerate(todo, 1):
        started = time.time()
        try:
            code, err = fetch(vid, args.timeout)
        except subprocess.TimeoutExpired:
            code, err = -1, "timeout"
        info_ok, subs_ok = have(vid)
        print("[%3d/%d] %s exit=%s info=%s subs=%s %.0fs %s"
              % (n, len(todo), vid, code, info_ok, subs_ok, time.time() - started,
                 "" if code == 0 else err.replace("\n", " ")[:160]), flush=True)
        if not info_ok:
            failures.append(vid)
            time.sleep(args.sleep * 4)  # back off harder after a failure
        else:
            time.sleep(args.sleep + random.uniform(0, 1.0))

    print("DONE. info files: %d, caption files: %d, failures: %d"
          % (len(glob.glob(os.path.join(INFO, "*.info.json"))),
             len(glob.glob(os.path.join(SUBS, "*.vtt"))), len(failures)), flush=True)
    if failures:
        print("failed ids:", " ".join(failures), flush=True)


if __name__ == "__main__":
    main()
