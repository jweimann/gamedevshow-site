"""
Generates the static Game Dev Show site from data/episodes.json and data/tags.json.

    python tools/build_site.py        # writes site/

Output is plain files with no build step and no runtime dependency: site/index.html is
the catalogue, site/e/<id>.html is one page per episode. Any static host serves it, and
it opens correctly from the filesystem, so the preview is the same thing that ships.

DESIGN NOTE, so the next person does not "tidy" the thing that makes it work.

The bones are a BROADCAST RUNDOWN - the sheet a live show is actually run from: dense
rows, hairline rules, monospace timings, a running order down the left. Not cards.

What is worn over them is the ENGINE EDITOR everyone on this show has open all day. Chrome
greys cooled toward blue, and one selection orange that only ever marks what is live,
selected or hovered - the colour an engine outlines a clicked object in. Hovering a row
paints the selection bar down its left edge. The evidence disclosures were always
foldouts, so they now carry an inspector's triangle. The masthead sits over a scene-view
grid, the figures read as the stats overlay, and the panel are portraits in frames.

The one flourish is the evidence disclosure itself: a tag opens to the timestamps where
the topic was really discussed, which is a thing this catalogue can do and a generic
podcast template cannot.
"""

import html
import json
import os
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")

SHOW = {
    "name": "The Game Dev Show",
    "spotify": "https://open.spotify.com/show/2aVmqZDsjGOQjC7gR44u1F",
    "apple": "https://podcasts.apple.com/us/podcast/the-game-dev-show/id1727884433",
    "rss": "https://anchor.fm/s/e4e835e8/podcast/rss",
    "youtube": "https://www.youtube.com/@Unity3dCollege",
    "contact": "jasonweimann@gmail.com",
}


def e(text):
    return html.escape(str(text if text is not None else ""), quote=True)


def hms(seconds):
    seconds = int(seconds or 0)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return "%d:%02d:%02d" % (h, m, s) if h else "%d:%02d" % (m, s)


def runtime(seconds):
    seconds = int(seconds or 0)
    h, m = seconds // 3600, (seconds % 3600) // 60
    return "%dh %02dm" % (h, m) if h else "%dm" % m


def thousands(n):
    return "{:,}".format(int(n or 0))


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Chakra+Petch:wght@600;700&'
         'family=IBM+Plex+Sans:wght@400;500;600&'
         'family=JetBrains+Mono:wght@400;500;700&'
         'family=Silkscreen:wght@400;700&display=swap">')

# The page is dressed as an engine editor, because that is the window everyone on this
# show has open. Chrome greys cooled toward blue exactly as editor chrome is, and one
# selection orange - the colour an engine outlines the thing you have clicked in - which
# is why it only ever marks what is live, selected or being pointed at. A second gizmo
# green carries counts and never competes.
CSS = r"""
:root{
  --paper:#e7eaec; --surface:#f7f8f9; --sunken:#dde1e4; --ink:#141a1e; --muted:#5d6a72;
  --rule:#c5ccd1; --accent:#c2540b; --accent-ink:#ffffff; --gizmo:#256b4e;
  --gizmo-soft:#dfeee7; --grid:rgba(20,26,30,.07);
  --f-display:"Chakra Petch","Helvetica Neue",Arial,sans-serif;
  --f-body:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;
  --f-mono:"JetBrains Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;
  --f-pixel:"Silkscreen",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#1b1f22; --surface:#252a2e; --sunken:#15181b; --ink:#e2e7ea; --muted:#94a1a9;
    --rule:#333a40; --accent:#ff8b3d; --accent-ink:#1b1f22; --gizmo:#79cfa4;
    --gizmo-soft:#1d2a26; --grid:rgba(226,231,234,.06);
  }
}
:root[data-theme="dark"]{
  --paper:#1b1f22; --surface:#252a2e; --sunken:#15181b; --ink:#e2e7ea; --muted:#94a1a9;
  --rule:#333a40; --accent:#ff8b3d; --accent-ink:#1b1f22; --gizmo:#79cfa4;
  --gizmo-soft:#1d2a26; --grid:rgba(226,231,234,.06);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-body);
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}

/* ---------- masthead: a title card over the scene grid ---------- */
.mast{position:relative;border-bottom:2px solid var(--ink);padding:40px 0 0;overflow:hidden}
/* The scene view's grid, fading out before it reaches the reading. */
.mast::before{content:"";position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(var(--grid) 1px,transparent 1px),
    linear-gradient(90deg,var(--grid) 1px,transparent 1px);
  background-size:58px 58px;
  -webkit-mask-image:linear-gradient(to bottom,#000,transparent 74%);
  mask-image:linear-gradient(to bottom,#000,transparent 74%)}
.mast .wrap{position:relative}
.tally{display:inline-flex;align-items:center;gap:8px;font-family:var(--f-pixel);
  font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent)}
.tally::before{content:"";width:8px;height:8px;background:var(--accent);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 22%,transparent)}
h1{font-family:var(--f-display);font-weight:700;font-size:clamp(2.6rem,7.4vw,5.4rem);
  line-height:.94;letter-spacing:-.005em;margin:16px 0 0;text-wrap:balance}
.standfirst{max-width:60ch;color:var(--muted);font-size:1.06rem;margin:16px 0 0}
/* The figures read as the Stats overlay an engine puts over the game view. */
.figures{display:flex;flex-wrap:wrap;gap:0;margin:32px 0 0;border:1px solid var(--rule);
  border-bottom:0;background:var(--surface)}
.figure{flex:1 1 150px;padding:13px 18px 16px;border-right:1px solid var(--rule)}
.figure:last-child{border-right:0}
.figure b{display:block;font-family:var(--f-mono);font-weight:700;font-size:1.65rem;
  letter-spacing:-.03em;font-variant-numeric:tabular-nums}
.figure span{display:block;font-family:var(--f-pixel);font-size:.62rem;letter-spacing:.02em;
  text-transform:uppercase;color:var(--muted);margin-top:4px}
.listen{display:flex;flex-wrap:wrap;gap:8px;padding:16px 0 22px;position:relative}
.listen a{font-family:var(--f-mono);font-size:.78rem;text-decoration:none;padding:7px 13px;
  border:1px solid var(--rule);background:var(--surface);border-radius:3px}
.listen a:hover{border-color:var(--accent);color:var(--accent)}

/* ---------- the panel, in portrait frames ---------- */
.people{padding:24px 0 20px;border-bottom:1px solid var(--rule)}
.phead{font-family:var(--f-pixel);font-size:.66rem;letter-spacing:.02em;text-transform:uppercase;
  color:var(--muted);margin:0 0 14px;font-weight:400}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px 28px;
  margin:0;padding:0;list-style:none}
.pcard{display:flex;gap:11px;align-items:center;min-width:0}
/* Square-ish frames, not circles: a roster of portraits, the way a party screen shows one. */
.face{width:46px;height:46px;border-radius:5px;flex:0 0 auto;border:1px solid var(--rule);
  object-fit:cover;background:var(--sunken);display:block}
.pcard:hover .face{border-color:var(--accent)}
.face.mono{display:grid;place-items:center;font-family:var(--f-mono);font-size:.84rem;
  font-weight:700;color:var(--muted)}
.pwho{min-width:0;display:flex;flex-direction:column;line-height:1.32}
.pwho b{font-family:var(--f-display);font-weight:600;font-size:1rem}
.plinks{display:flex;flex-wrap:wrap;gap:2px 10px;font-family:var(--f-mono);font-size:.72rem}
.plinks a{color:var(--gizmo);text-decoration:none}
.plinks a:hover{text-decoration:underline}
.plinks .nolink{color:var(--muted)}
.pnote{font-family:var(--f-mono);font-size:.72rem;color:var(--muted);margin:16px 0 0}

/* ---------- controls: the editor toolbar ---------- */
.controls{position:sticky;top:0;z-index:20;background:var(--paper);
  border-bottom:1px solid var(--rule);padding:14px 0 12px}
.searchrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
input[type=search]{flex:1 1 260px;min-width:0;font:inherit;padding:9px 12px;
  border:1px solid var(--rule);background:var(--sunken);color:var(--ink);border-radius:3px}
input[type=search]:focus-visible,select:focus-visible,button:focus-visible,
summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
select{font:inherit;padding:9px 10px;border:1px solid var(--rule);background:var(--surface);
  color:var(--ink);border-radius:3px}
.count{font-family:var(--f-mono);font-size:.8rem;color:var(--muted);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px;align-items:center}
.chip{font-family:var(--f-mono);font-size:.75rem;padding:5px 10px;border:1px solid var(--rule);
  background:var(--surface);color:var(--ink);border-radius:3px;cursor:pointer;
  display:inline-flex;align-items:center;gap:6px}
.chip .n{color:var(--muted);font-variant-numeric:tabular-nums}
.chip:hover{border-color:var(--accent)}
/* Selected changes SHAPE as well as colour: a square toolbar toggle becomes a pill with a
   cross, so the state survives a glance, a greyscale screen and a colour-blind reader. */
.chip[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);
  color:var(--accent-ink);border-radius:999px;padding-left:12px}
.chip[aria-pressed="true"] .n{color:color-mix(in srgb,var(--accent-ink) 75%,transparent)}
.chip[aria-pressed="true"]::after{content:"×";font-size:1.05em;line-height:1;opacity:.9}

/* The row of topics people actually use, then everything else behind one disclosure. */
.topline{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:12px}
.morebtn{font-family:var(--f-mono);font-size:.75rem;padding:5px 10px;cursor:pointer;
  border:1px dashed var(--rule);background:none;color:var(--muted);border-radius:3px}
.morebtn:hover{border-color:var(--accent);color:var(--accent)}
.alltopics{margin-top:10px}
.alltopics[hidden]{display:none}
.tgroup{margin:0 0 14px}
.tgroup h4{font-family:var(--f-pixel);font-size:.64rem;letter-spacing:.02em;text-transform:uppercase;
  color:var(--muted);margin:0 0 7px;font-weight:400}
.tgroup .chips{margin-top:0}

/* What is selected, said in words rather than left to be inferred from tint. */
.showing{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px;
  padding:9px 12px;border-left:3px solid var(--accent);background:var(--surface)}
.showing[hidden]{display:none}
.showing .lead{font-size:.84rem;color:var(--muted)}
.showing .lead b{color:var(--ink)}
.grouplabel{font-family:var(--f-mono);font-size:.7rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);align-self:center;margin-right:2px}
@media (max-width:640px){
  .topline{flex-wrap:nowrap;overflow-x:auto;padding-bottom:4px;
    scrollbar-width:thin;-webkit-overflow-scrolling:touch}
  .topline .chip{flex:0 0 auto}
}
.clear{background:none;border:0;color:var(--accent);font:inherit;font-size:.82rem;
  cursor:pointer;padding:4px 2px;text-decoration:underline}

/* ---------- the rundown, read as a hierarchy ---------- */
.rundown{margin:0;padding:26px 0 0}
.row{display:grid;grid-template-columns:88px 52px 1fr 78px;gap:16px;align-items:baseline;
  padding:13px 0 13px 10px;border-bottom:1px solid var(--rule);
  box-shadow:inset 3px 0 0 transparent}
/* Hover paints the selection bar an engine paints down the side of a selected object. */
.row:hover{background:var(--surface);box-shadow:inset 3px 0 0 var(--accent)}
.cell-date,.cell-no,.cell-run{font-family:var(--f-mono);font-size:.78rem;
  font-variant-numeric:tabular-nums;color:var(--muted)}
.cell-no{color:var(--accent);font-weight:700}
.cell-run{text-align:right}
.cell-main a.t{font-family:var(--f-display);font-weight:600;font-size:1.1rem;
  line-height:1.26;text-decoration:none;display:inline-block}
.cell-main a.t:hover{text-decoration:underline;text-decoration-color:var(--accent);
  text-underline-offset:3px}
.meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:6px}
.tg{font-family:var(--f-mono);font-size:.7rem;color:var(--gizmo);background:var(--gizmo-soft);
  padding:2px 7px;border-radius:3px;border:0;cursor:pointer}
.tg:hover{text-decoration:underline}
.audioflag{color:var(--accent);background:none;border:1px solid var(--accent);cursor:default}
.audioflag:hover{text-decoration:none}
audio{width:100%;margin-top:4px}
.guest{font-family:var(--f-mono);font-size:.7rem;color:var(--muted)}
.guest b{color:var(--ink);font-weight:500}
.empty{padding:60px 0;text-align:center;color:var(--muted)}

/* ---------- what the catalogue covers, closing the page ---------- */
.closing{margin:64px 0 0;border-top:2px solid var(--ink);padding:34px 0 70px}
.closing h2{font-family:var(--f-display);font-weight:700;font-size:2.1rem;margin:0 0 6px}
.closing .note{color:var(--muted);max-width:62ch}
.srcnote{font-family:var(--f-mono);font-size:.73rem;color:var(--muted);
  border-left:2px solid var(--rule);padding-left:10px;margin:22px 0 0}
.topics{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:0 26px;
  margin:22px 0 0;padding:0;list-style:none}
/* The rule under each topic fills to how much of the catalogue's watch time it carries,
   so the list is also the chart. */
.topics li{position:relative;display:flex;justify-content:space-between;gap:12px;padding:7px 0;
  border-bottom:1px solid var(--rule);font-size:.9rem}
.topics li::after{content:"";position:absolute;left:0;bottom:-1px;height:2px;
  width:var(--w,0);background:var(--accent)}
.topics .v{font-family:var(--f-mono);font-size:.76rem;color:var(--muted);
  font-variant-numeric:tabular-nums;white-space:nowrap}
footer{border-top:1px solid var(--rule);padding:22px 0 40px;color:var(--muted);font-size:.84rem}

/* ---------- episode page ---------- */
.back{font-family:var(--f-mono);font-size:.77rem;text-decoration:none;color:var(--muted)}
.back:hover{color:var(--accent)}
.ep h1{font-size:clamp(1.9rem,4.4vw,3rem);margin-top:10px}
.epmeta{display:flex;flex-wrap:wrap;gap:18px;font-family:var(--f-mono);font-size:.8rem;
  color:var(--muted);margin:14px 0 0;font-variant-numeric:tabular-nums}
.epgrid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(240px,.85fr);gap:44px;
  margin:34px 0 0}
@media (max-width:860px){.epgrid{grid-template-columns:1fr;gap:28px}
  .row{grid-template-columns:74px 1fr;gap:6px 12px}
  .cell-run{text-align:left;grid-column:1}
  .cell-main{grid-column:1 / -1}}
.player{width:100%;aspect-ratio:16/9;border:1px solid var(--rule);background:#000}
/* These were always foldouts. Now they look like the foldouts in an inspector, triangle
   on the left, so it reads as something to open rather than a heading. */
.evtag{border-bottom:1px solid var(--rule)}
.evtag summary{cursor:pointer;padding:11px 0;display:flex;justify-content:space-between;
  gap:10px;align-items:baseline;list-style:none}
.evtag summary::-webkit-details-marker{display:none}
.evtag summary::before{content:"\25B8";font-size:.8em;color:var(--muted);
  margin-right:2px;flex:0 0 auto}
.evtag[open] summary::before{content:"\25BE";color:var(--accent)}
.evtag .name{font-weight:600;margin-right:auto}
.evtag .hits{font-family:var(--f-mono);font-size:.74rem;color:var(--muted)}
.stamps{display:flex;flex-wrap:wrap;gap:6px;padding:0 0 14px 16px}
.stamps a{font-family:var(--f-mono);font-size:.75rem;text-decoration:none;padding:3px 8px;
  border:1px solid var(--rule);border-radius:3px;background:var(--surface)}
.stamps a:hover{border-color:var(--accent);color:var(--accent)}
.stamps a.peak{border-color:var(--accent);color:var(--accent)}
.aside h3{font-family:var(--f-pixel);font-size:.64rem;letter-spacing:.02em;text-transform:uppercase;
  color:var(--muted);margin:0 0 9px;font-weight:400}
.aside section{margin:0 0 26px}
.aside ul{margin:0;padding:0;list-style:none}
.aside li{padding:4px 0;font-size:.92rem}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{animation:none!important;
  transition:none!important}}
"""


def page(title, description, body, extra_head=""):
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            "<title>%s</title>\n<meta name=\"description\" content=\"%s\">\n%s\n"
            "<style>%s</style>\n%s</head>\n<body>\n%s\n</body>\n</html>\n"
            % (e(title), e(description), FONTS, CSS, extra_head, body))


def masthead(stats):
    return """<header class="mast"><div class="wrap">
<p class="tally">Live, with a rotating table of developers</p>
<h1>The Game&nbsp;Dev Show</h1>
<p class="standfirst">A working game developer's podcast: engines, code, the industry and the
week's news, recorded live with a rotating table of developers. %(episodes)s episodes%(current)s.</p>
<div class="figures">
  <div class="figure"><b>%(episodes)s</b><span>episodes</span></div>
  <div class="figure"><b>%(hours)s</b><span>hours recorded</span></div>
  <div class="figure"><b>%(views)s</b><span>YouTube views</span></div>
  <div class="figure"><b>%(median)s</b><span>median run time</span></div>
  <div class="figure"><b>%(years)s</b><span>years running</span></div>
</div>
<nav class="listen">
  <a href="%(youtube)s">YouTube</a><a href="%(spotify)s">Spotify</a>
  <a href="%(apple)s">Apple Podcasts</a><a href="%(rss)s">RSS</a>
  <a href="#covers">What it covers</a>
</nav>
</div></header>""" % stats


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def canonical_names(people):
    """Every form a person is written in, mapped to the one name the site uses.

    The description credits call him "Warped Imagination" and the stream tile calls him
    "David"; without this the filter offers both and each finds half his episodes.
    """
    out = {}
    for person in people:
        forms = [person["name"], person.get("channel")] + list(person.get("aliases") or [])
        for form in forms:
            if form:
                out[form.strip().lower()] = person["name"]
    return out


def tile_credits():
    """Who was read off the stream's own name tags, per episode.

    This is the source that works. The captions were tried four ways and each one put a
    name on an episode the name was not on - see the note at the top of people.toml.
    """
    path = os.path.join(DATA, "tile_people.json")
    if not os.path.exists(path):
        return {}
    rows = json.load(open(path, encoding="utf-8"))["episodes"]
    return {vid: [r["name"] for r in entries] for vid, entries in rows.items()}


def merge_people(episodes, people):
    """Fold the tile credits into each episode, under one name per person.

    Before this, nine episodes of a hundred and forty-seven said who was on them. The
    tiles carry a hundred, which is the difference between a filter worth using and a
    decoration.
    """
    canon = canonical_names(people)
    tiles = tile_credits()
    for ep in episodes:
        merged = {}
        for p in ep.get("people") or []:
            merged.setdefault(canon.get(p["name"].strip().lower(), p["name"]), None)
        for name in tiles.get(ep["id"], []):
            merged.setdefault(name, None)
        ep["people"] = [{"name": name} for name in sorted(merged)]


def people_strip(people):
    """The panel up top, each name pointing at where they actually publish.

    A channel picture where the channel is known, initials where it is not, so the row
    stays even and an unlinked person reads as a gap to fill rather than a mistake. The
    asset-store links carry Jason's affiliate id.
    """
    cards = []
    for p in people:
        slug = slugify(p["name"])
        if os.path.exists(os.path.join(SITE, "img", slug + ".jpg")):
            face = ('<img class="face" src="img/%s.jpg" alt="" loading="lazy" '
                    'width="44" height="44">' % e(slug))
        else:
            initials = "".join(w[0] for w in p["name"].split()[:2]).upper()
            face = '<span class="face mono" aria-hidden="true">%s</span>' % e(initials)
        links = []
        channel = p.get("channel") or ""
        if channel.strip().lower() == p["name"].strip().lower():
            channel = ""
        if p.get("link"):
            links.append('<a href="%s">%s</a>' % (e(p["link"]), e(channel or "YouTube")))
        if p.get("store"):
            links.append('<a href="%s">Asset Store</a>' % e(p["store"]))
        if p.get("site"):
            links.append('<a href="%s">Site</a>' % e(p["site"]))
        if not links:
            links.append('<span class="nolink">channel not on record</span>')
        cards.append('<li class="pcard">%s<span class="pwho"><b>%s</b>'
                     '<span class="plinks">%s</span></span></li>'
                     % (face, e(p["name"]), "".join(links)))
    return "".join(cards)


def roster():
    """The panel, as stated in people.toml. Read here rather than in build_data because
    it is a display fact, not a derived one - which also means editing the roster costs a
    two-second site rebuild instead of a three-minute retag."""
    import tomllib
    path = os.path.join(ROOT, "people.toml")
    if not os.path.exists(path):
        return [], []
    with open(path, "rb") as handle:
        people = tomllib.load(handle).get("person", [])
    shown = [p for p in people if p.get("confirmed", True)]
    return (shown,
            [p for p in shown if p.get("role") == "regular"],
            [p for p in shown if p.get("role") == "guest"])


def build_index(episodes, tags, stats):
    groups = {}
    for tag in tags:
        if tag["episodes"]:
            groups.setdefault(tag["group"], []).append(tag)

    def chip(tag):
        return ('<button class="chip" type="button" aria-pressed="false" data-tag="%s">'
                '<span>%s</span><span class="n">%d</span></button>'
                % (e(tag["id"]), e(tag["label"]), tag["episodes"]))

    # The eight topics that actually carry the catalogue lead; everything else is one
    # click away. Thirty chips in a single wrapping block was the complaint.
    used = sorted([t for t in tags if t["episodes"]], key=lambda t: -t["episodes"])
    top_chips = "".join(chip(t) for t in used[:8])
    group_blocks = []
    for group, items in groups.items():
        group_blocks.append('<div class="tgroup"><h4>%s</h4><div class="chips">%s</div></div>'
                            % (e(group), "".join(chip(t) for t in items)))
    all_groups = "".join(group_blocks)

    people = sorted({p["name"] for ep in episodes for p in ep.get("people") or []})
    guest_options = "".join('<option value="%s">%s</option>' % (e(p), e(p)) for p in people)

    payload = [{
        "i": ep["id"], "n": ep["number"], "d": ep["date"], "t": ep["title"],
        "r": ep["duration"], "v": ep["views"],
        "g": [p["name"] for p in ep.get("people") or []],
        # Filters and row chips carry only what the episode is about, not every topic
        # that came up in two hours.
        "T": sorted(t for t, d in ep["tags"].items() if d.get("primary")),
        "a": 1 if ep.get("audio_only") else 0,
    } for ep in episodes]
    labels = {t["id"]: t["label"] for t in tags}

    # Every number here is computed from public YouTube data, and the note under it says
    # so. Nothing about listeners or demographics is claimed, because nobody has given us
    # any. This closes the page as a description of the catalogue rather than a pitch: the
    # same figures do the same work for a sponsor without the page having to sell at them.
    # Episode count and views, not the demand proxy. Ranking a phrase against its own
    # prefix saturates - six topics scored 100 and Godot's twelve episodes sat beside
    # Unity's on the same number, which tells a sponsor nothing and invites the question
    # of what the score even is. Both figures here are public and neither saturates.
    # Demand survives only as the internal order of the chip bar.
    top_topics = sorted([t for t in tags if t["episodes"]],
                        key=lambda t: -t["views"])[:12]
    peak_views = max([t["views"] for t in top_topics] or [1]) or 1
    topics_html = "".join(
        '<li style="--w:%d%%"><span>%s</span>'
        '<span class="v">%d eps &middot; %s views</span></li>'
        % (round(100 * t["views"] / peak_views), e(t["label"]),
           t["episodes"], thousands(t["views"]))
        for t in top_topics)

    _all, regulars, _guests = roster()
    # The strip is the regular panel. A one-off guest with no channel would be a face-less
    # card linking nowhere, so guests live in the "Who's on" filter instead - which is
    # what Jason asked for.
    strip_html = people_strip(regulars)
    missing = [p["name"] for p in regulars
               if not (p.get("link") or p.get("store") or p.get("site"))]
    if missing:
        print("no channel on record, shown as initials: %s" % ", ".join(missing))

    body = """%(mast)s
<main class="wrap">
  <section class="people" aria-label="The regular panel">
    <h2 class="phead">The regular panel</h2>
    <ul class="pgrid">%(strip)s</ul>
  </section>
  <section class="controls" aria-label="Filter episodes">
    <div class="searchrow">
      <input type="search" id="q" placeholder="Search titles, guests and topics" aria-label="Search episodes">
      <select id="guest" aria-label="Filter by who is on the episode"><option value="">Who's on &mdash; anyone</option>%(guests)s</select>
      <select id="sort" aria-label="Sort order">
        <option value="old">Release order</option>
        <option value="new">Newest first</option>
        <option value="views">Most watched</option>
        <option value="long">Longest</option>
      </select>
      <span class="count" id="count"></span>
      <button class="clear" id="clear" type="button" hidden>Reset</button>
    </div>
    <div class="showing" id="showing" hidden></div>
    <div class="topline" id="topline">%(topchips)s<button class="morebtn" type="button"
      id="morebtn" aria-expanded="false" aria-controls="alltopics">All %(tagcount)d topics</button></div>
    <div class="alltopics" id="alltopics" hidden>%(allgroups)s</div>
    <p class="srcnote" style="margin:10px 0 0;border:0;padding:0">"Who's on" reads the
    name tags shown on screen during the stream, so it finds the table as it actually sat
    that night rather than whoever the title happened to credit. %(covered)d of the
    %(episodes)s episodes carry readable tags; the rest are filtered by their title
    credits alone.</p>
  </section>
  <section class="rundown" id="rundown" aria-live="polite"></section>

  <section class="closing" id="covers">
    <h2>What the show covers</h2>
    <p class="note">Five years of a working developer's podcast, counted by subject. An
    episode is tagged with everything it really goes into, so the counts overlap; the bar
    is each topic's views measured against the most watched.</p>
    <ul class="topics">%(topics)s</ul>
    <p class="srcnote">Every figure on this page is public YouTube data for the %(episodes)s
    episodes listed, counted on %(built)s. The channel's non-episode uploads are not
    counted here, so these are the show's own numbers rather than the channel's. Listener
    and download figures are not public and are not shown.</p>
    <p class="note" style="margin-top:22px">Get in touch: <a href="mailto:%(contact)s">%(contact)s</a></p>
  </section>
</main>
<footer class="wrap">The Game Dev Show &middot; hosted by Jason Weimann with a rotating
table of game developers.</footer>
<script id="data" type="application/json">%(payload)s</script>
<script id="labels" type="application/json">%(labels)s</script>
<script>%(js)s</script>""" % {
        "mast": masthead(stats),
        "topchips": top_chips,
        "allgroups": all_groups,
        "tagcount": len(used),
        "guests": guest_options,
        "strip": strip_html,
        "covered": sum(1 for ep in episodes if ep.get("people")),
        "topics": topics_html,
        "built": stats["built"], "episodes": stats["episodes"],
        "contact": SHOW["contact"],
        "payload": json.dumps(payload, separators=(",", ":")),
        "labels": json.dumps(labels, separators=(",", ":")),
        "js": INDEX_JS,
    }
    return page("The Game Dev Show",
                "Every episode of The Game Dev Show, in release order, searchable and "
                "filterable by topic and guest.", body)


INDEX_JS = r"""
const EPS = JSON.parse(document.getElementById('data').textContent);
const TAGCOUNT = document.querySelectorAll('#alltopics .chip').length;
const LABELS = JSON.parse(document.getElementById('labels').textContent);
const rundown = document.getElementById('rundown');
const q = document.getElementById('q'), guest = document.getElementById('guest');
const sort = document.getElementById('sort'), count = document.getElementById('count');
const clear = document.getElementById('clear');
let active = new Set();

const run = s => { s = s|0; const h = s/3600|0, m = (s%3600)/60|0;
  return h ? h + 'h ' + String(m).padStart(2,'0') + 'm' : m + 'm'; };
const nice = d => d ? new Date(d + 'T00:00:00Z').toLocaleDateString('en-GB',
  {day:'2-digit', month:'short', year:'2-digit', timeZone:'UTC'}) : '';

function matches(ep, terms){
  if (guest.value && !(ep.g||[]).includes(guest.value)) return false;
  for (const t of active) if (!ep.T.includes(t)) return false;
  if (!terms.length) return true;
  const hay = (ep.t + ' ' + (ep.g||[]).join(' ') + ' ' +
    ep.T.map(t => LABELS[t] || t).join(' ')).toLowerCase();
  return terms.every(t => hay.includes(t));
}

function render(){
  const terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
  let list = EPS.filter(ep => matches(ep, terms));
  const by = sort.value;
  list.sort((a,b) =>
    by === 'new'   ? (b.d||'').localeCompare(a.d||'') :
    by === 'views' ? (b.v||0) - (a.v||0) :
    by === 'long'  ? (b.r||0) - (a.r||0) :
                     (a.d||'').localeCompare(b.d||''));

  count.textContent = list.length === EPS.length
    ? EPS.length + ' episodes'
    : list.length + ' of ' + EPS.length + ' episodes';
  clear.hidden = !(active.size || q.value || guest.value);
  renderShowing();

  if (!list.length){
    rundown.innerHTML = '<p class="empty">No episode matches that. Try fewer filters.</p>';
    return;
  }
  const frag = document.createDocumentFragment();
  for (const ep of list){
    const row = document.createElement('article');
    row.className = 'row';
    const tags = ep.T.map(t =>
      '<button class="tg" type="button" data-tag="' + t + '">' + (LABELS[t]||t) + '</button>'
    ).join('');
    const guests = (ep.g||[]).length
      ? '<span class="guest">with <b>' + ep.g.join('</b>, <b>') + '</b></span>' : '';
    const audio = ep.a ? '<span class="tg audioflag">audio only</span>' : '';
    row.innerHTML =
      '<div class="cell-date">' + nice(ep.d) + '</div>' +
      '<div class="cell-no">' + (ep.n != null ? '#' + ep.n : '') + '</div>' +
      '<div class="cell-main"><a class="t" href="e/' + ep.i + '.html">' +
        ep.t.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</a>' +
        '<div class="meta">' + guests + audio + tags + '</div></div>' +
      '<div class="cell-run">' + run(ep.r) + '</div>';
    frag.appendChild(row);
  }
  rundown.replaceChildren(frag);
}

function toggle(id){
  active.has(id) ? active.delete(id) : active.add(id);
  // The same topic can appear in the top row AND in its group, so every copy updates.
  document.querySelectorAll('.chip[data-tag="' + id + '"]').forEach(c =>
    c.setAttribute('aria-pressed', active.has(id) ? 'true' : 'false'));
  render();
}

function renderShowing(){
  const box = document.getElementById('showing');
  if (!active.size){ box.hidden = true; box.innerHTML = ''; return; }
  const names = [...active].map(t =>
    '<button class="chip" type="button" aria-pressed="true" data-tag="' + t + '">' +
    '<span>' + (LABELS[t] || t) + '</span></button>').join('');
  box.innerHTML = '<span class="lead">Showing episodes about <b>' +
    (active.size > 1 ? 'all ' + active.size + ' of these' : 'this') + '</b>:</span>' + names;
  box.hidden = false;
}

document.getElementById('topline').addEventListener('click', ev => {
  const chip = ev.target.closest('.chip'); if (chip) toggle(chip.dataset.tag);
});
document.getElementById('alltopics').addEventListener('click', ev => {
  const chip = ev.target.closest('.chip'); if (chip) toggle(chip.dataset.tag);
});
document.getElementById('showing').addEventListener('click', ev => {
  const chip = ev.target.closest('.chip'); if (chip) toggle(chip.dataset.tag);
});
const moreBtn = document.getElementById('morebtn'), allBox = document.getElementById('alltopics');
moreBtn.addEventListener('click', () => {
  const open = allBox.hidden;
  allBox.hidden = !open;
  moreBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
  moreBtn.textContent = open ? 'Hide topics' : 'All ' + TAGCOUNT + ' topics';
});
rundown.addEventListener('click', ev => {
  const tg = ev.target.closest('.tg');
  if (tg){ toggle(tg.dataset.tag); window.scrollTo({top:0, behavior:'smooth'}); }
});
clear.addEventListener('click', () => {
  active.clear(); q.value = ''; guest.value = '';
  document.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed','false'));
  render();
});
q.addEventListener('input', render);
guest.addEventListener('change', render);
sort.addEventListener('change', render);
render();
"""


def build_episode(ep, tags_by_id, neighbours):
    stamps, also = [], []
    for tag_id, detail in sorted(ep["tags"].items(), key=lambda kv: -kv[1]["peak"]):
        tag = tags_by_id.get(tag_id)
        if not tag:
            continue
        if not detail.get("primary"):
            # Real, but incidental: named without a disclosure, and not a filter.
            also.append(e(tag["label"]))
            continue
        # The densest ten minutes is where the topic is actually gone into, so it leads;
        # the scattered mentions follow it. That is the difference between "they said
        # shaders once" and "there is a shader segment at 32 minutes".
        links = []
        if detail.get("peak_at") is not None and detail.get("peak", 0) >= 4:
            links.append('<a href="%s&t=%ds" class="peak"><b>Main run &middot; %s</b></a>'
                         % (e(ep["youtube"]), detail["peak_at"], hms(detail["peak_at"])))
        links += ['<a href="%s&t=%ds">%s</a>' % (e(ep["youtube"]), hit["t"], hms(hit["t"]))
                  for hit in detail["evidence"]]
        stamps.append(
            '<details class="evtag"><summary><span class="name">%s</span>'
            '<span class="hits">%d mentions</span></summary>'
            '<div class="stamps">%s</div></details>'
            % (e(tag["label"]), detail["hits"],
               "".join(links) or "<span class='hits'>&mdash;</span>"))

    guests = ("".join("<li>%s</li>" % e(g) for g in ep["guests"])
              if ep["guests"] else "<li class='hits'>Nobody credited in the title</li>")
    cohosts = "".join('<li><a href="%s">%s</a></li>' % (e(c["link"]), e(c["name"]))
                      for c in ep.get("cohosts") or [])
    # Three episodes went out on the podcast feed and were never uploaded to YouTube, so
    # they get the feed's own audio rather than a video embed, and say what they are.
    if ep.get("audio_only"):
        player = (
            '<div style="border:1px solid var(--rule);background:var(--surface);padding:18px">'
            '<p class="tally" style="margin:0 0 10px">Audio only &middot; never on YouTube</p>'
            '<audio controls preload="none" src="%s"></audio>'
            '<p class="srcnote" style="margin-top:14px">This episode went out on the podcast '
            'feed only, so there is no video and no view count. '
            '<a href="%s">Open it on Spotify</a>.</p></div>'
            % (e(ep.get("audio") or ""), e(ep.get("listen_link") or SHOW["spotify"])))
    else:
        player = ('<iframe class="player" src="https://www.youtube-nocookie.com/embed/%s" '
                  'title="%s" loading="lazy" allowfullscreen '
                  'allow="accelerometer; clipboard-write; encrypted-media; '
                  'picture-in-picture"></iframe>' % (e(ep["id"]), e(ep["title"])))

    prev_ep, next_ep = neighbours
    nav = []
    if prev_ep:
        nav.append('<a class="back" href="%s.html">&larr; %s</a>'
                   % (e(prev_ep["id"]), e(prev_ep["title"][:44])))
    if next_ep:
        nav.append('<a class="back" href="%s.html">%s &rarr;</a>'
                   % (e(next_ep["id"]), e(next_ep["title"][:44])))

    body = """<main class="wrap ep">
<p style="padding-top:28px"><a class="back" href="../index.html">&larr; All episodes</a></p>
<p class="tally">%(no)s%(date)s</p>
<h1>%(title)s</h1>
<div class="epmeta"><span>%(runtime)s</span>%(views)s%(feed)s</div>
<div class="epgrid">
  <div>
    %(player)s
    %(summary)s
    <h3 style="font-family:var(--f-mono);font-size:.72rem;letter-spacing:.1em;
      text-transform:uppercase;color:var(--muted);margin:30px 0 4px">What this episode covers</h3>
    <p class="srcnote" style="margin:0 0 14px">Topics are taken from the episode's own
    captions. Open one to jump to the moments where it comes up.</p>
    %(stamps)s
  </div>
  <aside class="aside">
    <section><h3>Listen</h3><ul>
      %(watch)s
      <li><a href="%(spotify)s">Spotify</a></li>
      <li><a href="%(apple)s">Apple Podcasts</a></li>
    </ul></section>
    %(onthis)s
    <section><h3>Credited in the title</h3><ul>%(guests)s</ul></section>
    %(cohost_block)s
  </aside>
</div>
<p style="display:flex;justify-content:space-between;gap:20px;margin:44px 0 60px">%(nav)s</p>
</main>""" % {
        "no": ("Episode #%d &middot; " % ep["number"]) if ep["number"] else "",
        "date": e(ep["date"] or ""),
        "title": e(ep["title"]),
        "runtime": runtime(ep["duration"]),
        "views": "" if ep.get("audio_only") else "<span>%s views</span>" % thousands(ep["views"]),
        "feed": '<span>Also on the podcast feed</span>' if ep["in_feed"] else "",
        "id": e(ep["id"]),
        "player": player,
        "summary": ('<p style="margin-top:18px">%s</p>' % e(ep["summary"])) if ep.get("summary") else "",
        "stamps": ("".join(stamps) or
                   ("<p class='hits'>Audio-only episodes have no captions to read, so this "
                    "one carries no topics.</p>" if ep.get("audio_only")
                    else "<p class='hits'>No captions were available for this episode.</p>"))
                  + ('<p class="srcnote" style="margin-top:16px">Also mentioned: %s</p>'
                     % ", ".join(also) if also else ""),
        "watch": ('<li><a href="%s">Open on Spotify</a></li>' % e(ep.get("listen_link") or SHOW["spotify"]))
                 if ep.get("audio_only")
                 else '<li><a href="%s">Watch on YouTube</a></li>' % e(ep["youtube"]),
        "spotify": SHOW["spotify"],
        "apple": SHOW["apple"],
        "guests": guests,
        "onthis": ('<section><h3>On this episode</h3><ul>%s</ul>'
                   '<p class="srcnote" style="margin-top:8px">Read from the name tags on '
                   'screen.</p></section>'
                   % "".join("<li>%s</li>" % e(p["name"]) for p in ep["people"]))
                  if ep.get("people") else "",
        "cohost_block": ('<section><h3>Co-hosts</h3><ul>%s</ul></section>' % cohosts) if cohosts else "",
        "nav": "".join(nav),
    }
    return page("%s | The Game Dev Show" % ep["title"],
                "The Game Dev Show, %s. %s" % (ep["date"] or "", ep["title"]), body)


def main():
    data = json.load(open(os.path.join(DATA, "episodes.json"), encoding="utf-8"))
    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    episodes = data["episodes"]
    tags_by_id = {t["id"]: t for t in tags}
    merge_people(episodes, roster()[0])

    # "Still going" is a claim, so the page only makes it when the catalogue supports it.
    # After the podcast-only clean-up the newest listed episode is March 2024, and a
    # sponsor-facing page that says "still going" over a fourteen-month gap is telling
    # them something the rundown underneath it contradicts. If the 2025 episodes are
    # brought back, this turns itself on again.
    from datetime import date
    latest = max((ep["date"] for ep in episodes if ep["date"]), default=None)
    months_since = 999
    if latest:
        y, m, _ = (int(p) for p in latest.split("-"))
        today = date.today()
        months_since = (today.year - y) * 12 + (today.month - m)

    total_seconds = sum(ep["duration"] or 0 for ep in episodes)
    durations = sorted(ep["duration"] or 0 for ep in episodes)
    years = sorted(ep["date"][:4] for ep in episodes if ep["date"])
    from datetime import date
    stats = {
        "episodes": len(episodes),
        "hours": thousands(round(total_seconds / 3600)),
        "views": thousands(sum(ep["views"] or 0 for ep in episodes)),
        "median": runtime(durations[len(durations) // 2] if durations else 0),
        "years": (int(years[-1]) - int(years[0]) + 1) if years else 0,
        # No closed year range anywhere: an end year reads as a show that stopped.
        "span": "",
        "current": " and counting" if months_since <= 12 else "",
        "built": date.today().isoformat(),
        "youtube": SHOW["youtube"], "spotify": SHOW["spotify"],
        "apple": SHOW["apple"], "rss": SHOW["rss"],
    }

    os.makedirs(os.path.join(SITE, "e"), exist_ok=True)
    written = set()

    def write(relative, text):
        path = os.path.join(SITE, relative)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        written.add(os.path.normcase(os.path.abspath(path)))

    write("index.html", build_index(episodes, tags, stats))

    for i, ep in enumerate(episodes):
        neighbours = (episodes[i - 1] if i else None,
                      episodes[i + 1] if i + 1 < len(episodes) else None)
        write(os.path.join("e", ep["id"] + ".html"),
              build_episode(ep, tags_by_id, neighbours))

    # GitHub Pages reads the custom domain from a CNAME file in the published output, and
    # it has to be regenerated with the site: a hand-added one would survive today and
    # vanish the first time somebody cleaned site/ before a rebuild, taking the domain
    # with it.
    with open(os.path.join(SITE, "CNAME"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("gamedev.show\n")
    written.add(os.path.normcase(os.path.abspath(os.path.join(SITE, "CNAME"))))

    # PRUNE WHAT THIS RUN DID NOT WRITE. Generating without deleting meant every episode
    # ever dropped from the catalogue kept its page: thirty of them shipped to the live
    # site, including the uploads Jason had just decided were not the show. Unlinked, but
    # publicly reachable and indexable, which is not what "removed from the site" means.
    # site/img holds the panel's channel pictures, fetched by tools/fetch_avatars.py and
    # not written by this build. Without this line the very first rebuild after adding the
    # strip deletes every face on it and leaves fourteen broken images on the live site.
    keep = os.path.normcase(os.path.abspath(os.path.join(SITE, "img")))
    removed = []
    for folder, _dirs, files in os.walk(SITE):
        if os.path.normcase(os.path.abspath(folder)).startswith(keep):
            continue
        for name in files:
            path = os.path.abspath(os.path.join(folder, name))
            if os.path.normcase(path) not in written:
                os.remove(path)
                removed.append(os.path.relpath(path, SITE))
    if removed:
        print("pruned %d file(s) the build no longer produces:" % len(removed))
        for name in sorted(removed)[:8]:
            print("   ", name)
        if len(removed) > 8:
            print("    ... and %d more" % (len(removed) - 8))

    index_kb = os.path.getsize(os.path.join(SITE, "index.html")) / 1024
    print("site/index.html  %.0f KB  (%d episodes, %d tags in the filter bar)"
          % (index_kb, len(episodes), sum(1 for t in tags if t["episodes"])))
    print("site/e/          %d episode pages" % len(episodes))
    print("figures on the page:", {k: stats[k] for k in ("episodes", "hours", "views", "median", "years")})


if __name__ == "__main__":
    main()
