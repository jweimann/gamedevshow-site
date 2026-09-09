# The Game Dev Show website — discovery and plan

2026-09-08. Discovery is done; nothing has been built or published. This is the one page
to approve before I build.

## 1. The show exists and is not the AI Dev Show

Both shows are real and separate. **The Game Dev Show** is the one to build:

| | |
|---|---|
| Spotify | https://open.spotify.com/show/2aVmqZDsjGOQjC7gR44u1F |
| Apple | https://podcasts.apple.com/us/podcast/the-game-dev-show/id1727884433 |
| RSS | https://anchor.fm/s/e4e835e8/podcast/rss (Spotify for Creators) |
| YouTube | two playlists on Unity3D College, both titled "The Game Dev Show" |
| Credited hosts | Jason Weimann, Storey, Andrew, Yoriz0r, Salim, Pawel, Corvalis, David, Johnny |

The AI Dev Show (aidevshow.com, co-hosted with Chris Lucian) stays separate. Its sponsor
page is the closest thing to a precedent for the sponsor section here.

## 2. The sources disagree, and neither one is complete

This is the main finding and it shapes the whole build.

- **Two YouTube playlists, same name.** `PLB5_EOMkLx_VH6tYMy6mSw386wE2TeFAl` has 146
  entries but 129 unique; `PLB5_EOMkLx_VdvzNTjlzkqpM04_bDm7wz` has 219 entries but 173
  unique. Both contain internal duplicates. Neither is a superset: 5 videos are only in
  the first, 49 only in the second. **Union: 178 unique, of which 174 are watchable and
  4 are private or deleted.**
- **RSS carries only 14 episodes** against 174 on YouTube — but it holds #163, #164 and
  #165, which are on neither playlist. So the catalogue is the union of both sources,
  not either one.
- **Episode numbers cannot be trusted as order.** Only 100 of 174 titles carry a number
  at all, the range is #1 to #162, and the RSS numbering contradicts the YouTube titles
  in at least one place (#156 is "AI Ban Removed from Steam" in RSS and "LIVE" on
  YouTube). **Release order will come from actual publish dates**, with the number kept
  as a display label where one exists.
- **Captions are available** in English on every episode sampled, so transcript tagging
  is viable.

Scale, from the playlist data: **341 hours** of episodes, median length 116 minutes,
about **1.7 million views** across them.

## 3. What I will build

**Repo:** `D:/Projects/gamedevshow-site` (its own git repo, nothing in the game repo).

1. **Collect.** A per-video metadata pass over all 174 (yt-dlp, public data) for real
   publish dates, durations, descriptions and view counts, plus the 14 RSS items; merge
   into one record per episode keyed by YouTube id, carrying the Spotify/Apple link where
   the RSS matches. Private/deleted videos are recorded and excluded from the site.
2. **Transcribe and tag.** Pull English captions, match against a taxonomy of about 25
   game-dev topics kept in one editable file (`tags.yml`): Unity, Unreal, Godot,
   rendering, shaders, navigation and AI, netcode and multiplayer, performance, tooling,
   animation, audio, VR and AR, procedural generation, ECS and DOTS, source control,
   testing, architecture and patterns, careers and hiring, marketing and launch, game
   design, art pipeline, monetisation, and so on. A tag sticks only above a hit
   threshold, and every tag stores its **evidence**: the timestamps where the topic is
   discussed. No tag is a guess, and the site shows the evidence.
3. **Generate.** A static site: episodes in release order, filter by tag and by guest,
   a search box, an episode page each with description, guests, tags, evidence
   timestamps and both players. Plus a sponsor section built only from public numbers
   and whatever you give me.
4. **Preview to you before anything goes live.**

On transcripts: they are used to *derive* tags and timestamps. The site will not
republish transcript text beyond a few words of context per tag hit.

## 4. Three things I need from you

1. **The domain.** I could not check Namecheap: it is behind a Cloudflare "verify you are
   human" checkbox, which I will not complete, and the URL bounced to the login page, so
   Chrome may not be signed in. Meanwhile `gamedevshow.com` is **live and belongs to
   someone else** (it serves a site titled "GameDevShow'25") and `thegamedevshow.com` is
   a parked GoDaddy page. So please check your Namecheap domain list and tell me what is
   in it, or approve a name to register yourself.
2. **The hosting account.** I found none on this machine: no GitHub CLI, and GitHub is
   signed out in Chrome; no Netlify, Vercel or Cloudflare CLI. Which do you have? My
   recommendation is **Cloudflare Pages** with the domain's DNS pointed there, because it
   is free, fast, and the DNS and the host end up in one place. GitHub Pages is the
   equal-simplest if you would rather the source sat in a public repo.
3. **Sponsor numbers.** I will invent nothing. I can publish the public YouTube view
   counts and the episode cadence from the dates. If you want downloads, unique
   listeners or demographics on the page, send them and I will use exactly those.

## 5. Not in scope tonight

The Meshy reply is on hold at your word. Your Facebook group (unity3d.group) and the
Spotify show link are collected and waiting for it. Nothing has been sent to Meshy since
the opener you approved on the 7th.
