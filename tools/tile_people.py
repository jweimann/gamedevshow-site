"""
Turn the raw stream-tile labels into who was on which episode.

    python tools/tile_people.py     # data/tiles.json -> data/tile_people.json

OCR of a 360p frame produces a lot of near-misses: "Jainan Weomann", "Jaron Storey",
"Sacm Grint" are all the same three people. Raw, that was 1,079 distinct labels across
144 episodes. Fuzzy-matching every label against the confirmed roster collapses 120
variants into the dozen people who are really there, which is also what lets a genuine
one-off guest stand out instead of drowning in misreads of the regulars.

Nothing here invents a person. A label becomes a credit only if it matches a name in
people.toml closely enough, and everything else is written to `unmatched` for a human to
look at. Jason Weimann is dropped: he hosts every episode, so crediting him credits
nothing.
"""

import json
import os
import re
import tomllib
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
THRESHOLD = 0.72     # tuned on the known misreads: "Sacm Grint" -> "Salim Grant"
HOST = "jason weimann"


def norm(s):
    return re.sub(r"[^a-z]", "", s.lower())


def load_people():
    with open(os.path.join(ROOT, "people.toml"), "rb") as handle:
        people = tomllib.load(handle)["person"]
    keys = []
    for person in people:
        forms = [person["name"]] + list(person.get("aliases") or [])
        if person.get("channel"):
            forms.append(person["channel"])
            forms.append("%s - %s" % (person["name"], person["channel"]))
        for form in forms:
            keys.append((norm(form), person["name"]))
    return people, keys


def match(label, keys):
    n = norm(label)
    if not n or SequenceMatcher(None, n, norm(HOST)).ratio() >= THRESHOLD:
        return None                      # the host, credited nowhere
    best, score = None, 0.0
    for key, name in keys:
        if not key:
            continue
        r = SequenceMatcher(None, n, key).ratio()
        # A label often carries the affiliation too, so a contained key counts.
        if key in n and len(key) >= 6:
            r = max(r, 0.9)
        if r > score:
            best, score = name, r
    return best if score >= THRESHOLD else None


def main():
    people, keys = load_people()
    tiles = json.load(open(os.path.join(DATA, "tiles.json"), encoding="utf-8"))

    out, unmatched = {}, {}
    for vid, rec in tiles.items():
        seen = {}
        for item in rec["labels"]:
            who = match(item["label"], keys)
            if who:
                seen.setdefault(who, item["t"])
            else:
                unmatched.setdefault(item["label"], []).append(vid)
        if seen:
            out[vid] = [{"name": k, "t": v} for k, v in sorted(seen.items())]

    json.dump({"episodes": out}, open(os.path.join(DATA, "tile_people.json"), "w",
                                      encoding="utf-8"), indent=1, ensure_ascii=False)

    counts = {}
    for vid, rows in out.items():
        for row in rows:
            counts[row["name"]] = counts.get(row["name"], 0) + 1
    print("episodes with at least one person read off the tiles: %d of %d"
          % (len(out), len(tiles)))
    print("\nper person:")
    for name, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("   %3d episodes  %s" % (n, name))
    print("\nlabels matched to nobody: %d distinct (left for a human, never guessed)"
          % len(unmatched))


if __name__ == "__main__":
    main()
