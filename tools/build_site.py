"""
Generates the static Game Dev Show site from data/episodes.json and data/tags.json.

    python tools/build_site.py        # writes site/

Output is plain files with no build step and no runtime dependency: site/index.html is
the catalogue, site/e/<id>.html is one page per episode. Any static host serves it, and
it opens correctly from the filesystem, so the preview is the same thing that ships.

DESIGN NOTE, so the next person does not "tidy" the thing that makes it work. The page is
laid out as a BROADCAST RUNDOWN - the sheet a live show is actually run from - because
that is this subject's own document: dense rows, hairline rules, monospace timings, a
running order down the left. Not cards. The one flourish is the evidence disclosure: a
tag opens to the timestamps where the topic was actually discussed, which is a thing this
catalogue can do and a generic podcast template cannot.
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
         'family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,800&'
         'family=IBM+Plex+Mono:wght@400;600&'
         'family=IBM+Plex+Sans:wght@400;500;600&display=swap">')

# The palette is a tally light on studio paper: one loud red that only ever marks what is
# live or selected, a deep teal that carries data, and neutrals pulled cool so the red
# stays the only warm thing on the page.
CSS = """
:root{
  --paper:#edf0ef; --surface:#ffffff; --ink:#10171a; --muted:#66767a;
  --rule:#d3dad8; --tally:#c8102e; --signal:#1f6f6b; --signal-soft:#e4efed;
  --shadow:0 1px 2px rgba(16,23,26,.06);
  --f-display:"Bricolage Grotesque","Helvetica Neue",Arial,sans-serif;
  --f-body:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,"Cascadia Mono",Consolas,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0e1416; --surface:#161e21; --ink:#e6ecea; --muted:#8ca0a4;
    --rule:#263134; --tally:#ff6b7a; --signal:#58bdb6; --signal-soft:#152927;
    --shadow:0 1px 2px rgba(0,0,0,.4);
  }
}
:root[data-theme="dark"]{
  --paper:#0e1416; --surface:#161e21; --ink:#e6ecea; --muted:#8ca0a4;
  --rule:#263134; --tally:#ff6b7a; --signal:#58bdb6; --signal-soft:#152927;
  --shadow:0 1px 2px rgba(0,0,0,.4);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-body);
  font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}
a{color:inherit}
.wrap{max-width:1120px;margin:0 auto;padding:0 24px}

/* ---------- masthead: the show's own figures, stated plainly ---------- */
.mast{border-bottom:2px solid var(--ink);padding:40px 0 0}
.tally{display:inline-flex;align-items:center;gap:8px;font-family:var(--f-mono);
  font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--tally)}
.tally::before{content:"";width:9px;height:9px;border-radius:50%;background:var(--tally)}
h1{font-family:var(--f-display);font-weight:800;font-size:clamp(2.6rem,7vw,5.2rem);
  line-height:.95;letter-spacing:-.02em;margin:14px 0 0;text-wrap:balance}
.standfirst{max-width:60ch;color:var(--muted);font-size:1.06rem;margin:16px 0 0}
.figures{display:flex;flex-wrap:wrap;gap:0;margin:32px 0 0;border-top:1px solid var(--rule)}
.figure{flex:1 1 150px;padding:14px 20px 18px;border-right:1px solid var(--rule)}
.figure:last-child{border-right:0}
.figure b{display:block;font-family:var(--f-mono);font-weight:600;font-size:1.7rem;
  letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.figure span{display:block;font-size:.76rem;letter-spacing:.08em;text-transform:uppercase;
  color:var(--muted);margin-top:2px}
.listen{display:flex;flex-wrap:wrap;gap:8px;padding:16px 0 22px}
.listen a{font-family:var(--f-mono);font-size:.8rem;text-decoration:none;padding:7px 13px;
  border:1px solid var(--rule);background:var(--surface);border-radius:2px}
.listen a:hover{border-color:var(--ink)}

/* ---------- controls ---------- */
.controls{position:sticky;top:0;z-index:20;background:var(--paper);
  border-bottom:1px solid var(--rule);padding:14px 0 12px}
.searchrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
input[type=search]{flex:1 1 260px;min-width:0;font:inherit;padding:9px 12px;
  border:1px solid var(--rule);background:var(--surface);color:var(--ink);border-radius:2px}
input[type=search]:focus-visible,select:focus-visible,button:focus-visible,
summary:focus-visible,a:focus-visible{outline:2px solid var(--tally);outline-offset:2px}
select{font:inherit;padding:9px 10px;border:1px solid var(--rule);background:var(--surface);
  color:var(--ink);border-radius:2px}
.count{font-family:var(--f-mono);font-size:.82rem;color:var(--muted);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.chip{font-family:var(--f-mono);font-size:.76rem;padding:5px 10px;border:1px solid var(--rule);
  background:var(--surface);color:var(--ink);border-radius:2px;cursor:pointer}
.chip .n{color:var(--muted);margin-left:6px;font-variant-numeric:tabular-nums}
.chip:hover{border-color:var(--ink)}
.chip[aria-pressed="true"]{background:var(--tally);border-color:var(--tally);color:#fff}
.chip[aria-pressed="true"] .n{color:rgba(255,255,255,.75)}
.grouplabel{font-family:var(--f-mono);font-size:.7rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);align-self:center;margin-right:2px}
.clear{background:none;border:0;color:var(--tally);font:inherit;font-size:.82rem;
  cursor:pointer;padding:4px 2px;text-decoration:underline}

/* ---------- the rundown ---------- */
.rundown{margin:0;padding:26px 0 0}
.row{display:grid;grid-template-columns:88px 52px 1fr 78px;gap:16px;align-items:baseline;
  padding:13px 0;border-bottom:1px solid var(--rule)}
.row:hover{background:var(--surface)}
.cell-date,.cell-no,.cell-run{font-family:var(--f-mono);font-size:.8rem;
  font-variant-numeric:tabular-nums;color:var(--muted)}
.cell-no{color:var(--tally);font-weight:600}
.cell-run{text-align:right}
.cell-main a.t{font-family:var(--f-display);font-weight:600;font-size:1.06rem;
  line-height:1.28;text-decoration:none;display:inline-block}
.cell-main a.t:hover{text-decoration:underline;text-decoration-color:var(--tally);
  text-underline-offset:3px}
.meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-top:6px}
.tg{font-family:var(--f-mono);font-size:.7rem;color:var(--signal);background:var(--signal-soft);
  padding:2px 7px;border-radius:2px;border:0;cursor:pointer}
.tg:hover{text-decoration:underline}
.guest{font-family:var(--f-mono);font-size:.7rem;color:var(--muted)}
.guest b{color:var(--ink);font-weight:600}
.empty{padding:60px 0;text-align:center;color:var(--muted)}

/* ---------- sponsor block ---------- */
.sponsor{margin:64px 0 0;border-top:2px solid var(--ink);padding:34px 0 70px}
.sponsor h2{font-family:var(--f-display);font-size:2rem;margin:0 0 6px;letter-spacing:-.01em}
.sponsor .note{color:var(--muted);max-width:62ch}
.srcnote{font-family:var(--f-mono);font-size:.74rem;color:var(--muted);
  border-left:2px solid var(--rule);padding-left:10px;margin:22px 0 0}
.topics{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:0 26px;
  margin:22px 0 0;padding:0;list-style:none}
.topics li{display:flex;justify-content:space-between;gap:12px;padding:7px 0;
  border-bottom:1px solid var(--rule);font-size:.9rem}
.topics .v{font-family:var(--f-mono);font-size:.78rem;color:var(--muted);
  font-variant-numeric:tabular-nums;white-space:nowrap}
footer{border-top:1px solid var(--rule);padding:22px 0 40px;color:var(--muted);font-size:.84rem}

/* ---------- episode page ---------- */
.back{font-family:var(--f-mono);font-size:.78rem;text-decoration:none;color:var(--muted)}
.ep h1{font-size:clamp(1.9rem,4.4vw,3rem);margin-top:10px}
.epmeta{display:flex;flex-wrap:wrap;gap:18px;font-family:var(--f-mono);font-size:.82rem;
  color:var(--muted);margin:14px 0 0;font-variant-numeric:tabular-nums}
.epgrid{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(240px,.85fr);gap:44px;
  margin:34px 0 0}
@media (max-width:860px){.epgrid{grid-template-columns:1fr;gap:28px}
  .row{grid-template-columns:74px 1fr;gap:6px 12px}
  .cell-run{text-align:left;grid-column:1}
  .cell-main{grid-column:1 / -1}}
.player{width:100%;aspect-ratio:16/9;border:1px solid var(--rule);background:#000}
.evtag{border-bottom:1px solid var(--rule)}
.evtag summary{cursor:pointer;padding:11px 0;display:flex;justify-content:space-between;
  gap:12px;align-items:baseline;list-style:none}
.evtag summary::-webkit-details-marker{display:none}
.evtag summary::after{content:"+";font-family:var(--f-mono);color:var(--muted)}
.evtag[open] summary::after{content:"\\2212"}
.evtag .name{font-weight:600}
.evtag .hits{font-family:var(--f-mono);font-size:.76rem;color:var(--muted)}
.stamps{display:flex;flex-wrap:wrap;gap:6px;padding:0 0 14px}
.stamps a{font-family:var(--f-mono);font-size:.76rem;text-decoration:none;padding:3px 8px;
  border:1px solid var(--rule);border-radius:2px;background:var(--surface)}
.stamps a:hover{border-color:var(--tally);color:var(--tally)}
.stamps a.peak{border-color:var(--tally);color:var(--tally)}
.aside h3{font-family:var(--f-mono);font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);margin:0 0 8px;font-weight:600}
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
<p class="tally">Live every week &middot; %(span)s</p>
<h1>The Game&nbsp;Dev Show</h1>
<p class="standfirst">A working game developer's podcast: engines, code, the industry and the
week's news, recorded live with a rotating table of developers. %(episodes)s episodes and
still going.</p>
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
  <a href="#sponsor">Sponsor the show</a>
</nav>
</div></header>""" % stats


def build_index(episodes, tags, stats):
    groups = {}
    for tag in tags:
        if tag["episodes"]:
            groups.setdefault(tag["group"], []).append(tag)

    chips = []
    for group, items in groups.items():
        chips.append('<span class="grouplabel">%s</span>' % e(group))
        for tag in items:
            chips.append(
                '<button class="chip" type="button" aria-pressed="false" data-tag="%s">%s'
                '<span class="n">%d</span></button>'
                % (e(tag["id"]), e(tag["label"]), tag["episodes"]))

    guests = sorted({g for ep in episodes for g in ep["guests"]})
    guest_options = "".join('<option value="%s">%s</option>' % (e(g), e(g)) for g in guests)

    payload = [{
        "i": ep["id"], "n": ep["number"], "d": ep["date"], "t": ep["title"],
        "r": ep["duration"], "v": ep["views"], "g": ep["guests"],
        "T": sorted(ep["tags"].keys()),
    } for ep in episodes]
    labels = {t["id"]: t["label"] for t in tags}

    # Sponsor block: every number here is computed from public YouTube data, and the note
    # under it says so. Nothing about listeners or demographics is claimed, because
    # nobody has given us any.
    top_topics = [t for t in tags if t["episodes"]][:12]
    topics_html = "".join(
        '<li><span>%s</span><span class="v">%d eps &middot; demand %s</span></li>'
        % (e(t["label"]), t["episodes"], ("%g" % t["demand_score"]))
        for t in top_topics)

    body = """%(mast)s
<main class="wrap">
  <section class="controls" aria-label="Filter episodes">
    <div class="searchrow">
      <input type="search" id="q" placeholder="Search titles, guests and topics" aria-label="Search episodes">
      <select id="guest" aria-label="Filter by guest"><option value="">Every guest</option>%(guests)s</select>
      <select id="sort" aria-label="Sort order">
        <option value="old">Release order</option>
        <option value="new">Newest first</option>
        <option value="views">Most watched</option>
        <option value="long">Longest</option>
      </select>
      <span class="count" id="count"></span>
      <button class="clear" id="clear" type="button" hidden>Reset</button>
    </div>
    <div class="chips" id="chips">%(chips)s</div>
  </section>
  <section class="rundown" id="rundown" aria-live="polite"></section>

  <section class="sponsor" id="sponsor">
    <h2>Sponsor the show</h2>
    <p class="note">The audience is working game developers: the people who choose the
    engine, buy the tooling and pick the asset store bundle. Episodes run long and get
    watched long, and the back catalogue keeps earning views years after the stream ends.</p>
    <ul class="topics">%(topics)s</ul>
    <p class="srcnote">Every figure on this page is public YouTube data for the episodes
    listed, counted on %(built)s. Demand is a search-interest proxy: where YouTube's own
    autocomplete ranks that topic's phrase. Listener numbers and download figures are not
    shown because they are not public &mdash; ask and we will send them.</p>
    <p class="note" style="margin-top:22px">Talk to us: <a href="mailto:%(contact)s">%(contact)s</a></p>
  </section>
</main>
<footer class="wrap">The Game Dev Show &middot; hosted by Jason Weimann with a rotating
table of game developers.</footer>
<script id="data" type="application/json">%(payload)s</script>
<script id="labels" type="application/json">%(labels)s</script>
<script>%(js)s</script>""" % {
        "mast": masthead(stats),
        "chips": "".join(chips),
        "guests": guest_options,
        "topics": topics_html,
        "built": stats["built"],
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
    row.innerHTML =
      '<div class="cell-date">' + nice(ep.d) + '</div>' +
      '<div class="cell-no">' + (ep.n != null ? '#' + ep.n : '') + '</div>' +
      '<div class="cell-main"><a class="t" href="e/' + ep.i + '.html">' +
        ep.t.replace(/&/g,'&amp;').replace(/</g,'&lt;') + '</a>' +
        '<div class="meta">' + guests + tags + '</div></div>' +
      '<div class="cell-run">' + run(ep.r) + '</div>';
    frag.appendChild(row);
  }
  rundown.replaceChildren(frag);
}

function toggle(id){
  active.has(id) ? active.delete(id) : active.add(id);
  document.querySelectorAll('.chip[data-tag="' + id + '"]').forEach(c =>
    c.setAttribute('aria-pressed', active.has(id) ? 'true' : 'false'));
  render();
}

document.getElementById('chips').addEventListener('click', ev => {
  const chip = ev.target.closest('.chip'); if (chip) toggle(chip.dataset.tag);
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
    stamps = []
    for tag_id, detail in sorted(ep["tags"].items(),
                                 key=lambda kv: -kv[1]["hits"]):
        tag = tags_by_id.get(tag_id)
        if not tag:
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
              if ep["guests"] else "<li class='hits'>No guest credited</li>")
    cohosts = "".join('<li><a href="%s">%s</a></li>' % (e(c["link"]), e(c["name"]))
                      for c in ep.get("cohosts") or [])
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
<div class="epmeta"><span>%(runtime)s</span><span>%(views)s views</span>%(feed)s</div>
<div class="epgrid">
  <div>
    <iframe class="player" src="https://www.youtube-nocookie.com/embed/%(id)s"
      title="%(title)s" loading="lazy" allowfullscreen
      allow="accelerometer; clipboard-write; encrypted-media; picture-in-picture"></iframe>
    %(summary)s
    <h3 style="font-family:var(--f-mono);font-size:.72rem;letter-spacing:.1em;
      text-transform:uppercase;color:var(--muted);margin:30px 0 4px">What this episode covers</h3>
    <p class="srcnote" style="margin:0 0 14px">Topics are taken from the episode's own
    captions. Open one to jump to the moments where it comes up.</p>
    %(stamps)s
  </div>
  <aside class="aside">
    <section><h3>Listen</h3><ul>
      <li><a href="%(youtube)s">Watch on YouTube</a></li>
      <li><a href="%(spotify)s">Spotify</a></li>
      <li><a href="%(apple)s">Apple Podcasts</a></li>
    </ul></section>
    <section><h3>Guests</h3><ul>%(guests)s</ul></section>
    %(cohost_block)s
  </aside>
</div>
<p style="display:flex;justify-content:space-between;gap:20px;margin:44px 0 60px">%(nav)s</p>
</main>""" % {
        "no": ("Episode #%d &middot; " % ep["number"]) if ep["number"] else "",
        "date": e(ep["date"] or ""),
        "title": e(ep["title"]),
        "runtime": runtime(ep["duration"]),
        "views": thousands(ep["views"]),
        "feed": '<span>Also on the podcast feed</span>' if ep["in_feed"] else "",
        "id": e(ep["id"]),
        "summary": ('<p style="margin-top:18px">%s</p>' % e(ep["summary"])) if ep.get("summary") else "",
        "stamps": "".join(stamps) or "<p class='hits'>No captions were available for this episode.</p>",
        "youtube": e(ep["youtube"]),
        "spotify": SHOW["spotify"],
        "apple": SHOW["apple"],
        "guests": guests,
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
        "span": "%s &ndash; %s" % (years[0], years[-1]) if years else "",
        "built": date.today().isoformat(),
        "youtube": SHOW["youtube"], "spotify": SHOW["spotify"],
        "apple": SHOW["apple"], "rss": SHOW["rss"],
    }

    os.makedirs(os.path.join(SITE, "e"), exist_ok=True)
    with open(os.path.join(SITE, "index.html"), "w", encoding="utf-8") as handle:
        handle.write(build_index(episodes, tags, stats))

    for i, ep in enumerate(episodes):
        neighbours = (episodes[i - 1] if i else None,
                      episodes[i + 1] if i + 1 < len(episodes) else None)
        with open(os.path.join(SITE, "e", ep["id"] + ".html"), "w", encoding="utf-8") as handle:
            handle.write(build_episode(ep, tags_by_id, neighbours))

    index_kb = os.path.getsize(os.path.join(SITE, "index.html")) / 1024
    print("site/index.html  %.0f KB  (%d episodes, %d tags in the filter bar)"
          % (index_kb, len(episodes), sum(1 for t in tags if t["episodes"])))
    print("site/e/          %d episode pages" % len(episodes))
    print("figures on the page:", {k: stats[k] for k in ("episodes", "hours", "views", "median", "years")})


if __name__ == "__main__":
    main()
