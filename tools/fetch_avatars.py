"""
Fetch each panellist's channel picture so the people strip has faces rather than text.

    python tools/fetch_avatars.py

Saves site/img/<slug>.jpg for every person in people.toml with a channel link, and
records the slug so build_site.py can use it. Files are cached: a rerun only fetches what
is missing.

The pictures are each person's own channel avatar, shown next to their name and linked
to their channel - the same use the credit line in every episode description already
makes. Anyone without a channel gets a monogram drawn from their initials instead, so the
strip stays even and nothing is invented.
"""

import io
import json
import os
import re
import tomllib
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "site", "img")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126 Safari/537.36"}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def avatar_url(channel_url):
    request = urllib.request.Request(channel_url, headers=UA)
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")
    block = re.search(r'"avatar":\{"thumbnails":\[(.*?)\]', html)
    if not block:
        return None
    urls = re.findall(r'"url":"(https://yt3[^"]+)"', block.group(1))
    return urls[-1] if urls else None


def main():
    os.makedirs(IMG, exist_ok=True)
    with open(os.path.join(ROOT, "people.toml"), "rb") as handle:
        people = tomllib.load(handle)["person"]

    got, missing = [], []
    for person in people:
        link = person.get("link")
        name = person["name"]
        path = os.path.join(IMG, slug(name) + ".jpg")
        if not link:
            missing.append(name)
            continue
        if os.path.exists(path):
            got.append(name)
            continue
        try:
            url = avatar_url(link)
            if not url:
                missing.append(name)
                continue
            request = urllib.request.Request(url.replace("\\u003d", "="), headers=UA)
            with urllib.request.urlopen(request, timeout=40) as response:
                data = response.read()
            with open(path, "wb") as out:
                out.write(data)
            got.append(name)
            print("  %-18s %5.0f KB" % (name, len(data) / 1024), flush=True)
        except Exception as error:
            print("  %-18s FAILED %s" % (name, type(error).__name__), flush=True)
            missing.append(name)

    print("\navatars on disk: %d" % len(got))
    print("no channel, monogram instead: %s" % (", ".join(missing) or "none"))


if __name__ == "__main__":
    main()
