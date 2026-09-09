"""
Measures how much developers actually search for each tag topic.

    python tools/demand.py

WHAT THIS IS AND IS NOT. There is no free source of true YouTube search volume, so this
does not claim one. It uses the public autocomplete endpoint, which ranks completions by
how often people search them, and asks one question per tag:

    typing the first few characters of the topic, does YouTube offer the whole phrase
    back, and how near the top?

A phrase offered first is searched more than one offered eighth, and one never offered is
searched little enough that YouTube would rather suggest something else. That ordering is
the signal. It is a PROXY FOR DEMAND, NOT A VOLUME, and the site says so wherever the
number appears.

Writes data/demand.json: for every tag, the rank, the suggestion list it came from (the
evidence), and a 0-100 score. Any tag the endpoint has nothing to say about scores 0 and
is marked `measured = false`, so it can be told apart from one that scored 0 on merit.
"""

import json
import os
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENDPOINT = "https://suggestqueries.google.com/complete/search"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def load_tags():
    import tomllib
    with open(os.path.join(ROOT, "tags.toml"), "rb") as handle:
        return tomllib.load(handle)["tag"]


def suggest(prefix, timeout=15):
    url = ENDPOINT + "?" + urllib.parse.urlencode({"client": "firefox", "ds": "yt", "q": prefix})
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    data = json.loads(body)
    return [s.lower() for s in (data[1] if len(data) > 1 else [])]


def measure(phrase):
    """Rank of the full phrase among the completions of its own prefix."""
    phrase = phrase.lower().strip()
    # Long enough to be unambiguous, short enough that the rest is YouTube's opinion.
    cut = max(4, min(len(phrase) - 3, int(len(phrase) * 0.55)))
    prefix = phrase[:cut]
    suggestions = suggest(prefix)
    rank = None
    for i, s in enumerate(suggestions):
        if s == phrase or s.startswith(phrase):
            rank = i
            break
    if rank is None:
        # Not offered at all: fall back to whether the phrase has completions of its own,
        # which at least separates "a thing people search" from "a thing nobody types".
        own = suggest(phrase + " ")
        return {"measured": True, "prefix": prefix, "rank": None,
                "suggestions": suggestions[:10], "own_completions": len(own),
                "score": min(25, len(own) * 2)}
    score = round(100.0 * (1.0 - (rank / max(len(suggestions), 1))), 1)
    return {"measured": True, "prefix": prefix, "rank": rank,
            "suggestions": suggestions[:10], "own_completions": None, "score": score}


def main():
    out = {}
    tags = load_tags()
    for n, tag in enumerate(tags, 1):
        phrase = tag.get("query") or tag["label"]
        try:
            result = measure(phrase)
        except Exception as error:  # a proxy that fails is reported, never guessed
            result = {"measured": False, "error": str(error)[:200], "score": 0}
        result["phrase"] = phrase
        out[tag["id"]] = result
        print("[%2d/%d] %-16s %-34s rank=%s score=%s"
              % (n, len(tags), tag["id"], phrase, result.get("rank"), result.get("score")),
              flush=True)
        time.sleep(1.2)

    path = os.path.join(ROOT, "data", "demand.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(out, handle, indent=2)
    measured = sum(1 for v in out.values() if v.get("measured"))
    print("WROTE %s (%d of %d measured)" % (path, measured, len(out)))


if __name__ == "__main__":
    main()
