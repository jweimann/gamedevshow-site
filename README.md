# The Game Dev Show — site

A static, sponsor-facing catalogue of every episode of The Game Dev Show, in release
order, filterable by topic and guest, with each topic backed by the timestamps where it
was actually discussed.

Nothing here is hosted yet. `site/` is generated locally and opens straight from disk.

## Run it

```bash
python tools/collect.py      # public metadata + English captions (paced; resumes)
python tools/demand.py       # search-interest proxy per topic
python tools/build_data.py   # merge every source, tag from captions -> data/*.json
python tools/build_site.py   # generate site/
```

Then open `site/index.html`.

`data/raw/` and `data/transcripts/` are deliberately not committed: they are large, they
are re-fetchable, and the captions are YouTube's to serve rather than ours to
redistribute. The derived `data/episodes.json` and `data/tags.json` are committed,
because those are the site's input and they are what a review should be able to read.

## The three things this repo gets right on purpose

**Release order comes from dates, not episode numbers.** Only 100 of 174 titles carry a
`#nnn`, the numbering restarts and repeats across the run, and the podcast feed
contradicts the YouTube titles in at least one place (#156 is one show in the feed and a
different one on YouTube). Sorting by the number would produce an order that is
confidently wrong. The number is kept as a label; the publish date decides the order.

**No single source has the whole show.** The two YouTube playlists that share the show's
name each hold episodes the other lacks (146 and 219 entries, 129 and 173 unique, union
178) and both contain internal duplicates. The RSS feed carries only 14 episodes but
three of those appear on neither playlist. The catalogue is the union, and
`data/episodes.json` records which sources knew about each episode. Anything the feed has
that YouTube does not is kept in `feed_only` rather than dropped.

**A tag is never a guess.** A topic sticks to an episode only when its terms are actually
said, enough times overall *and* densely enough inside one ten-minute window to be a
segment rather than a passing mention. That second test is what makes the tags mean
something: on a catalogue whose median episode is 116 minutes, a flat threshold put
"Audio" on 86% of episodes and "VR & AR" on 72%, which is not what those shows are
about. Every applied tag stores the times it was earned, and the site links them into the
episode, so any tag can be checked in one click.

The evidence stored is a time and a term, never transcript text. Captions are used to
find the topic, not to republish what was said.

## Editing the taxonomy

`tags.toml` is the file to change. Each topic carries the phrases that count as a hit,
optional exclusions, how many hits it needs, and the phrase used to measure search
demand. Add a topic, re-run `build_data.py` and `build_site.py`, and the filter bar picks
it up.

## Search demand

`tools/demand.py` records where YouTube's own autocomplete ranks each topic's phrase
against its own prefix. A phrase offered first is searched more than one offered eighth.
It is a **proxy for demand, not a volume**, there is no free source of true YouTube
search volume, and the site says so wherever the number appears.

## Not done

- Hosting and DNS. No account has been created and nothing has been published.
- Listener and download figures. The sponsor section shows public YouTube counts only,
  and says so on the page.
