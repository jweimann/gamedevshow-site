"""
Pick up a newly published episode and rebuild the site. One command.

    python tools/refresh.py            # fetch, rebuild, report what changed
    python tools/refresh.py --dry-run  # just say what would be picked up

WHY THIS EXISTS RATHER THAN A LIST OF FOUR COMMANDS. The obvious refresh is
"collect -> build_data -> build_site", and it would have done NOTHING for a new episode.
collect.py reads its list of videos from the playlist dumps in data/raw/, which are
files on disk from the day they were fetched; a video uploaded afterwards is not in
them, so collect has nothing to collect and the rebuild faithfully rebuilds yesterday.
The fetch of the playlists and the feed has to come first, and that is the step this
script exists to stop anyone from forgetting.

It touches nothing a human decides. curation.toml is not written to: an episode whose
title carries a number or the show's name passes by rule, and an unnumbered upload
lands in the review list exactly as it does today, where it is reported rather than
silently counted.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PLAYLISTS = ["PLB5_EOMkLx_VH6tYMy6mSw386wE2TeFAl", "PLB5_EOMkLx_VdvzNTjlzkqpM04_bDm7wz"]
FEED = "https://anchor.fm/s/e4e835e8/podcast/rss"


def run(*args, **kwargs):
    print("  $", " ".join(str(a) for a in args[:4]), "..." if len(args) > 4 else "", flush=True)
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def known_ids():
    ids = set()
    for name in os.listdir(RAW):
        if name.startswith("playlist-") and name.endswith(".json"):
            data = json.load(open(os.path.join(RAW, name), encoding="utf-8"))
            ids |= {e["id"] for e in (data.get("entries") or []) if e.get("title")}
    return ids


def feed_numbers():
    import re
    path = os.path.join(RAW, "feed.xml")
    if not os.path.exists(path):
        return set()
    text = open(path, encoding="utf-8", errors="replace").read()
    return set(re.findall(r"<title>[^<]*?#(\d{1,3})", text))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    before_ids, before_feed = known_ids(), feed_numbers()

    print("1. Re-fetching the playlists (a new upload is invisible until this runs)")
    for playlist in PLAYLISTS:
        out = os.path.join(RAW, "playlist-%s.json" % playlist)
        run(sys.executable, "-m", "yt_dlp", "--flat-playlist", "-J", "--no-warnings",
            "https://www.youtube.com/playlist?list=" + playlist,
            stdout=open(out, "w", encoding="utf-8"))

    print("2. Re-fetching the podcast feed")
    with urllib.request.urlopen(FEED, timeout=60) as response:
        body = response.read()
    with open(os.path.join(RAW, "feed.xml"), "wb") as handle:
        handle.write(body)

    new_ids = known_ids() - before_ids
    new_feed = feed_numbers() - before_feed
    print("\n   new videos in the playlists : %s" % (", ".join(sorted(new_ids)) or "none"))
    print("   new numbered feed episodes  : %s" % (", ".join("#" + n for n in sorted(new_feed)) or "none"))

    if args.dry_run:
        print("\n--dry-run: stopping before the fetch and rebuild.")
        return

    if new_ids:
        print("\n3. Collecting metadata and captions for the new video(s)")
        run(sys.executable, "tools/collect.py")
    else:
        print("\n3. Nothing new to collect; rebuilding anyway so the feed changes land.")

    print("4. Rebuilding the data")
    run(sys.executable, "tools/build_data.py")
    print("5. Rebuilding the site")
    run(sys.executable, "tools/build_site.py")

    data = json.load(open(os.path.join(ROOT, "data", "episodes.json"), encoding="utf-8"))
    episodes = data["episodes"]
    latest = max(e["date"] for e in episodes if e["date"])
    review = [x for x in data["not_episodes"] if x["decision"] == "unreviewed"]

    print("\n%d episodes, newest %s" % (len(episodes), latest))
    if review:
        # The one case a human has to look at: an upload the rule cannot place.
        print("\nNEEDS A DECISION - these are not numbered and not titled as the show, so")
        print("they are NOT on the site until curation.toml says otherwise:")
        for item in review:
            print("   %s  %s  (%s)" % (item["id"], item["title"][:56], item["reason"]))
    else:
        print("Nothing is waiting on a curation decision.")

    print("\nTo publish:  git add -A && git commit && git subtree push --prefix site origin gh-pages")


if __name__ == "__main__":
    main()
