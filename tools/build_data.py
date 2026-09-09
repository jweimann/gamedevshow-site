"""
Merges every source into one episode record per episode, and tags each from its captions.

    python tools/build_data.py

Inputs   data/raw/videos/*.info.json   YouTube metadata (public)
         data/raw/feed.xml             the podcast RSS feed
         data/transcripts/*.vtt        English captions
         tags.toml                     the taxonomy Jason edits
         data/demand.json              the search-demand proxy
Output   data/episodes.json            the one file the site is generated from
         data/tags.json                taxonomy + demand + how the catalogue covers it

THREE THINGS THIS FILE EXISTS TO GET RIGHT.

RELEASE ORDER COMES FROM DATES, NOT NUMBERS. Only 100 of 174 titles carry a "#nnn", the
numbering restarts and repeats, and the RSS feed disagrees with the YouTube titles in at
least one place. Sorting on the number would put the catalogue in an order that is
confidently wrong, so the number is kept as a label and `upload_date` decides the order.

NEITHER SOURCE IS COMPLETE. The two YouTube playlists each miss episodes the other has,
and the feed holds three that neither playlist lists. Every source is merged in and an
episode records which sources knew about it.

A TAG IS NEVER A GUESS. A tag sticks only when its terms are actually said, enough times
to clear the tag's own threshold, and every tag carries the timestamps where the terms
were said. The evidence stored is a TIME AND A TERM, not transcript text: enough to check
the claim by clicking into the episode, without republishing what was said.
"""

import glob
import json
import os
import re
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
INFO = os.path.join(DATA, "raw", "videos")
SUBS = os.path.join(DATA, "transcripts")

# "w/ Dan Baker", "with Marc Whitten", "feat. Jason Storey" - the shapes a guest credit
# takes in these titles. Deliberately strict: a false guest is worse than a missing one.
GUEST_PATTERNS = [
    re.compile(r"\bw/\s*(?:a\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"),
    re.compile(r"\bwith\s+([A-Z][a-z]+\s+[A-Z][a-z]+)"),
    re.compile(r"\bfeat\.?\s+([A-Z][a-z]+\s+[A-Z][a-z]+)"),
    re.compile(r"\bQ&A\s+w/\s*([A-Z][a-z]+\s+[A-Z][a-z]+)"),
]
NOT_GUESTS = {"Game Dev", "Dev Show", "The Game", "Live With", "New Game", "Unity Solution"}


def load_tags():
    with open(os.path.join(ROOT, "tags.toml"), "rb") as handle:
        tags = tomllib.load(handle)["tag"]
    for tag in tags:
        tag["_patterns"] = [
            (term, re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.I))
            for term in tag["terms"]
        ]
        # One alternation to ask "does this line matter at all", so the per-term loop only
        # runs on the few lines that do. Without it the pass is every term against every
        # caption line of 174 long episodes, which took minutes.
        tag["_any"] = re.compile(
            r"(?<!\w)(?:" + "|".join(re.escape(t) for t in tag["terms"]) + r")(?!\w)", re.I)
        tag["_exclude"] = [re.compile(re.escape(x), re.I) for x in tag.get("exclude", [])]
    return tags


def parse_vtt(path):
    """[(seconds, line)] with the rolling duplicates auto-captions repeat stripped out."""
    cues, start, buffer = [], None, []
    time_re = re.compile(r"(\d\d):(\d\d):(\d\d)[.,](\d\d\d)\s*-->")
    with open(path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            match = time_re.match(line.strip())
            if match:
                if start is not None and buffer:
                    cues.append((start, " ".join(buffer).strip()))
                h, m, s, _ms = (int(g) for g in match.groups())
                start, buffer = h * 3600 + m * 60 + s, []
            elif line.strip() and not line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                text = re.sub(r"<[^>]+>", "", line).strip()
                if text and (not buffer or text != buffer[-1]):
                    buffer.append(text)
    if start is not None and buffer:
        cues.append((start, " ".join(buffer).strip()))

    deduped, seen_recent = [], []
    for seconds, text in cues:
        if text in seen_recent:
            continue
        deduped.append((seconds, text))
        seen_recent = ([text] + seen_recent)[:6]
    return deduped


def transcript_for(vid):
    for suffix in (".en-orig.vtt", ".en.vtt", ".en-US.vtt"):
        path = os.path.join(SUBS, vid + suffix)
        if os.path.exists(path):
            return parse_vtt(path)
    matches = sorted(glob.glob(os.path.join(SUBS, vid + "*.vtt")))
    return parse_vtt(matches[0]) if matches else []


# A topic the show actually COVERED shows up as a burst - a stretch of the episode where
# it keeps coming up - because that is what a segment is. A topic merely MENTIONED is a
# few hits scattered over two hours. Counting total hits cannot tell those apart: on a
# 116-minute median episode, a flat threshold of four put "Audio" on 86% of the catalogue
# and "VR & AR" on 72%, which is not what those shows are about. So a tag has to clear a
# burst inside one window as well as a total, and the window it clears in is the segment
# the evidence links to.
WINDOW = 600  # ten minutes

# How many hits inside that window before a topic counts as covered. Four was still far
# too loose for a two-hour show: it left a median of twelve tags an episode, with
# Multiplayer on 63% and Animation on half the catalogue, and a filter that returns half
# the catalogue does not filter. Measured against the stored densities, ten is where the
# median falls to six and Unity is the only topic left above 60% - which is true of this
# show. A tag can still set its own `min_cluster` in tags.toml.
MIN_CLUSTER = 10

# Even at ten, a wide-ranging episode earns more topics than a reader can use. The densest
# few are what the episode is ABOUT and drive the filters; the rest are real but
# incidental, and appear on the episode page under "also mentioned" instead. Filtering by
# Shaders should return the shader episodes, not every episode where shaders came up.
PRIMARY_TAGS = 5


def tag_episode(cues, tags):
    """Which tags this episode earns, and the times that prove each one."""
    found = {}
    for tag in tags:
        hits = []
        for seconds, text in cues:
            if not tag["_any"].search(text):
                continue
            if any(x.search(text) for x in tag["_exclude"]):
                continue
            for term, pattern in tag["_patterns"]:
                if pattern.search(text):
                    hits.append({"t": seconds, "term": term})
                    break
        if len(hits) < tag["min_hits"]:
            continue

        # Densest ten minutes: a sliding window over the hit times.
        peak, peak_at, start = 0, None, 0
        for end in range(len(hits)):
            while hits[end]["t"] - hits[start]["t"] > WINDOW:
                start += 1
            if end - start + 1 > peak:
                peak, peak_at = end - start + 1, hits[start]["t"]
        if peak < tag.get("min_cluster", MIN_CLUSTER):
            continue

        # Evidence spread across the episode, never six hits from the same minute.
        spread, last = [], -999
        for hit in hits:
            if hit["t"] - last >= 90:
                spread.append(hit)
                last = hit["t"]
        found[tag["id"]] = {"hits": len(hits), "peak": peak, "peak_at": peak_at,
                            "evidence": spread[:8]}

    # The densest few are what the episode is about; the rest are marked incidental.
    ranked = sorted(found.items(), key=lambda kv: -kv[1]["peak"])
    for rank, (tag_id, detail) in enumerate(ranked):
        detail["primary"] = rank < PRIMARY_TAGS
    return found


def guests(title, description):
    """
    One-off guests only, from the title.

    Deliberately NOT the co-hosts. The descriptions credit the same handful of regulars
    on nearly every episode, so folding them in here would give every episode the same
    nine names and a guest filter that filters nothing. Regulars are collected separately
    by cohosts(); this is the person who turned up for one show.
    """
    names = []
    for pattern in GUEST_PATTERNS:
        for name in pattern.findall(title):
            name = name.strip()
            if name not in NOT_GUESTS and name not in names and len(name) > 4:
                names.append(name)
    return names


# The descriptions carry a "CoHosts" block of `https://channel - Name` lines. That is
# where the regulars are credited, and it is the only place their channels appear.
COHOST_LINE = re.compile(r"^\s*(https?://\S+)\s*[-–—]\s*(.+?)\s*$")


def cohosts(description):
    out, inside = [], False
    for raw in (description or "").splitlines():
        line = raw.strip()
        if re.fullmatch(r"co-?hosts:?", line, re.I):
            inside = True
            continue
        if not inside:
            continue
        match = COHOST_LINE.match(line)
        if not match:
            # The block ends at the first line that is not a credit.
            if line and not line.startswith("http"):
                break
            continue
        url, name = match.group(1), match.group(2)
        name = re.sub(r"\s*\((.*?)\)\s*$", "", name).strip()  # drop "(MPG / InfinityPBR)"
        name = re.sub(r"^(subscribe to|follow)\s+", "", name, flags=re.I).strip(" !:-")
        if 2 < len(name) < 40 and not name.lower().startswith("http"):
            if not any(c["name"].lower() == name.lower() for c in out):
                out.append({"name": name, "link": url})
    return out


def summary(description):
    """
    The first line of actual prose, if the description has any.

    These descriptions are mostly affiliate and course links, so showing them raw would
    make the site look like a link farm. Anything that is a URL, or a line whose job is
    to label a URL, is dropped; what survives is a sentence somebody wrote.
    """
    for raw in (description or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("http") or "http" in line:
            continue
        if re.fullmatch(r"co-?hosts:?", line, re.I) or len(line) < 25:
            continue
        return line[:300]
    return None


# An upload whose title carries an episode number or the show's name is an episode; every
# other upload needs a human call, which lives in curation.toml. Without this the
# playlists' strays counted as episodes and carried 58% of the view total, so the three
# most-watched "episodes" on the site were a Mike Rowe commentary, a TV-news clip and an
# AI news short - and "most watched" sorted them to the top for a sponsor to click first.
IS_SHOW = re.compile(r"game\s*dev\s*show|gamedevshow|\bgds\b|#\s*\d", re.I)


def curation():
    path = os.path.join(ROOT, "curation.toml")
    if not os.path.exists(path):
        return {}
    with open(path, "rb") as handle:
        return {c["id"]: c for c in tomllib.load(handle).get("entry", [])}


ITUNES = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}


def _feed_date(pub):
    """RFC-2822 pubDate to an ISO date, so feed episodes sort beside YouTube ones."""
    if not pub:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub).date().isoformat()
    except (TypeError, ValueError):
        return None


def _feed_duration(text):
    if not text:
        return None
    parts = [int(p) for p in text.split(":") if p.isdigit()]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def rss_items():
    path = os.path.join(DATA, "raw", "feed.xml")
    if not os.path.exists(path):
        return []
    channel = ET.parse(path).getroot().find("channel")
    out = []
    for item in channel.findall("item"):
        title = item.findtext("title") or ""
        number = None
        match = re.search(r"#(\d{1,3})", title)
        if match:
            number = int(match.group(1))
        enclosure = item.find("enclosure")
        # The feed still points at podcasters.spotify.com, which now redirects to
        # creators.spotify.com; sending people straight to the live address saves the hop.
        link = (item.findtext("link") or "").replace(
            "podcasters.spotify.com/pod/show/", "creators.spotify.com/pod/profile/")
        out.append({
            "title": title,
            "number": number,
            "date": _feed_date(item.findtext("pubDate")),
            "duration": _feed_duration(item.findtext("itunes:duration", namespaces=ITUNES)),
            "link": link,
            "audio": enclosure.get("url") if enclosure is not None else None,
            "guid": item.findtext("guid"),
        })
    return out


def episode_number(title):
    match = re.search(r"#\s*(\d{1,3})(?!\d)", title)
    return int(match.group(1)) if match else None


def main():
    tags = load_tags()
    demand = {}
    demand_path = os.path.join(DATA, "demand.json")
    if os.path.exists(demand_path):
        demand = json.load(open(demand_path, encoding="utf-8"))

    feed = rss_items()
    by_number = {i["number"]: i for i in feed if i["number"] is not None}

    episodes = []
    for path in sorted(glob.glob(os.path.join(INFO, "*.info.json"))):
        info = json.load(open(path, encoding="utf-8"))
        vid = info["id"]
        title = info.get("title") or ""
        number = episode_number(title)
        cues = transcript_for(vid)
        applied = tag_episode(cues, tags) if cues else {}
        upload = info.get("upload_date")
        iso = None
        if upload:
            iso = datetime.strptime(upload, "%Y%m%d").replace(tzinfo=timezone.utc).date().isoformat()
        matched_feed = by_number.get(number) if number else None
        episodes.append({
            "id": vid,
            "title": title,
            "number": number,
            "date": iso,
            "duration": info.get("duration"),
            "views": info.get("view_count"),
            "summary": summary(info.get("description")),
            "youtube": "https://www.youtube.com/watch?v=" + vid,
            "thumbnail": "https://i.ytimg.com/vi/%s/hqdefault.jpg" % vid,
            "guests": guests(title, info.get("description")),
            "cohosts": cohosts(info.get("description")),
            "tags": applied,
            "has_transcript": bool(cues),
            "transcript_cues": len(cues),
            "in_feed": bool(matched_feed),
            "feed_title": matched_feed["title"] if matched_feed else None,
        })

    episodes.sort(key=lambda e: (e["date"] or "0000-00-00", e["id"]))

    # The same stream is occasionally uploaded twice - once titled properly and once as a
    # bare date - and the catalogue showed both. Same day AND a runtime within half a
    # minute is the same recording; two different shows on one day (which happens ten
    # times here) differ by many minutes, so the window has to be tight or real episodes
    # get swallowed. The copy with fewer views is folded into the one people watched, and
    # it stays in the data marked rather than deleted.
    for i, episode in enumerate(episodes):
        if episode.get("duplicate_of"):
            continue
        for other in episodes[i + 1:]:
            if other["date"] != episode["date"] or other.get("duplicate_of"):
                continue
            if abs((other["duration"] or 0) - (episode["duration"] or 0)) <= 30:
                keep, drop = sorted((episode, other), key=lambda x: -(x["views"] or 0))
                drop["duplicate_of"] = keep["id"]

    curated = curation()
    for episode in episodes:
        entry = curated.get(episode["id"])
        if entry:
            episode["curation"] = entry["decision"]
            episode["curation_reason"] = entry.get("reason")
        elif IS_SHOW.search(episode["title"]):
            episode["curation"] = "include"
            episode["curation_reason"] = "Titled as the show."
        else:
            # New strays default OUT and are reported, so the numbers cannot quietly
            # inflate again the next time the playlists gain something odd.
            episode["curation"] = "unreviewed"
            episode["curation_reason"] = "Not titled as the show and not yet reviewed."

    live = [e for e in episodes
            if not e.get("duplicate_of") and e["curation"] == "include"]
    for i, episode in enumerate(live, 1):
        episode["order"] = i

    # Episodes the feed has and YouTube does not. "Every episode" has to include them, so
    # they join the catalogue as audio-only records rather than sitting in a footnote.
    # They carry no captions, so they earn no tags, and the page says so instead of
    # implying the show did not cover anything that day.
    known = {e["number"] for e in episodes if e["number"]}
    feed_only = [i for i in feed if i["number"] and i["number"] not in known]
    for item in feed_only:
        live.append({
            "id": "feed-%d" % item["number"],
            "title": item["title"],
            "number": item["number"],
            "date": item["date"],
            "duration": item["duration"],
            "views": None,
            "summary": None,
            "youtube": None,
            "thumbnail": None,
            "guests": [],
            "cohosts": [],
            "tags": {},
            "has_transcript": False,
            "transcript_cues": 0,
            "in_feed": True,
            "feed_title": item["title"],
            "audio_only": True,
            "audio": item["audio"],
            "listen_link": item["link"],
            "curation": "include",
            "curation_reason": "Published to the podcast feed only; never uploaded to YouTube.",
        })
    live.sort(key=lambda e: (e["date"] or "0000-00-00", e["id"]))
    for i, episode in enumerate(live, 1):
        episode["order"] = i

    # Chip counts follow the filters, so they count the episodes a topic is ABOUT.
    counts = {}
    for episode in live:
        for tag_id, detail in episode["tags"].items():
            if not detail.get("primary"):
                continue
            entry = counts.setdefault(tag_id, {"episodes": 0, "views": 0})
            entry["episodes"] += 1
            entry["views"] += episode.get("views") or 0

    tag_out = []
    for tag in tags:
        cover = counts.get(tag["id"], {"episodes": 0, "views": 0})
        signal = demand.get(tag["id"], {})
        tag_out.append({
            "id": tag["id"], "label": tag["label"], "group": tag["group"],
            "episodes": cover["episodes"], "views": cover["views"],
            "demand_score": signal.get("score", 0),
            "demand_rank": signal.get("rank"),
            "demand_phrase": signal.get("phrase"),
            "demand_measured": signal.get("measured", False),
        })
    tag_out.sort(key=lambda t: (-t["demand_score"], -t["episodes"]))

    os.makedirs(DATA, exist_ok=True)
    json.dump({"episodes": live,
               "duplicates": [e for e in episodes if e.get("duplicate_of")],
               "not_episodes": [{"id": e["id"], "title": e["title"], "date": e["date"],
                                 "views": e["views"], "duration": e["duration"],
                                 "decision": e["curation"], "reason": e["curation_reason"]}
                                for e in episodes
                                if e["curation"] != "include" and not e.get("duplicate_of")],
               "feed_only": feed_only},
              open(os.path.join(DATA, "episodes.json"), "w", encoding="utf-8"), indent=1)
    json.dump(tag_out, open(os.path.join(DATA, "tags.json"), "w", encoding="utf-8"), indent=1)

    tagged = sum(1 for e in live if e["tags"])
    with_tx = sum(1 for e in live if e["has_transcript"])
    print("episodes: %d  with captions: %d  tagged: %d  feed-only (not on YouTube): %d"
          % (len(live), with_tx, tagged, len(feed_only)))
    print("not episodes: %d excluded, %d unreviewed"
          % (sum(1 for e in episodes if e["curation"] == "exclude"),
             sum(1 for e in episodes if e["curation"] == "unreviewed")))
    print("date range: %s to %s" % (episodes[0]["date"], episodes[-1]["date"]) if episodes else "")
    print("guests on %d episodes; co-hosts credited on %d"
          % (sum(1 for e in episodes if e["guests"]), sum(1 for e in episodes if e["cohosts"])))
    people = {}
    for e in episodes:
        for g in e["guests"]:
            people.setdefault(g, 0); people[g] += 1
    print("distinct guests:", len(people))
    print("\ntop tags by search demand:")
    for tag in tag_out[:10]:
        print("  %-28s demand %5s  episodes %3d" % (tag["label"], tag["demand_score"], tag["episodes"]))


if __name__ == "__main__":
    main()
