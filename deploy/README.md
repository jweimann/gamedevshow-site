# Publishing gamedev.show

The site is plain static files under `site/`. Nothing here has been run: every command
below needs credentials that only Jason has, and this is where the automation stops.

**The domain.** `gamedev.show` is in Jason's Namecheap account, registered to
2027-02-12, on Namecheap BasicDNS (`dns1.registrar-servers.com`,
`dns2.registrar-servers.com`) with no A or CNAME records today. Nothing is live on it,
so nothing breaks whichever path is picked.

Pick **one** of the two paths below. Path A is simpler; path B matches the other two
podcast sites.

---

## Path A — GitHub Pages  ← CHOSEN

One repo, one push, free certificate.

**A correction to the plan before anything is run: Pages cannot serve from `/site`.**
GitHub's own documentation is explicit that a branch's publishing source is either the
repository root or a `/docs` folder, and nothing else. So the two real options are a
`gh-pages` branch holding the contents of `site/` at its root, or renaming `site/` to
`docs/`.

**Taking the `gh-pages` branch.** It keeps generated output off `main`, so the repo
still shows the four scripts and the two files a human edits rather than 178 generated
pages, and `git subtree push` regenerates the branch from `site/` every time. Renaming
to `docs/` would work equally well for the browser and worse for reading the repo.

**1. Jason: sign in and create the repo.** This machine has no `gh` and no GitHub
session, so this step is his.

```bash
winget install --id GitHub.cli -e
gh auth login
gh repo create gamedevshow-site --public --source . --remote origin --push
```

**2. Point Pages at the `site/` folder.** Either move `site/` to `docs/` and set Pages
to "main /docs", or push `site/` to a `gh-pages` branch:

```bash
git subtree push --prefix site origin gh-pages
```

Then in the repo: Settings → Pages → Source = `gh-pages`, folder = `/`.

**3. Custom domain.** `build_site.py` writes `site/CNAME` containing `gamedev.show`, so
it is regenerated with the site rather than added by hand. A hand-added file would
survive today and disappear the first time anyone cleaned `site/` before a rebuild,
taking the domain with it.

Then Settings → Pages → Custom domain = `gamedev.show`, and tick "Enforce HTTPS" once
the certificate is issued (a few minutes).

**4. DNS at Namecheap** (Domain List → gamedev.show → Advanced DNS). Exactly these
records, and nothing else:

| Type | Host | Value | TTL |
|---|---|---|---|
| A | @ | 185.199.108.153 | Automatic |
| A | @ | 185.199.109.153 | Automatic |
| A | @ | 185.199.110.153 | Automatic |
| A | @ | 185.199.111.153 | Automatic |
| CNAME | www | `<his-github-user>.github.io.` | Automatic |

Checked against GitHub's Pages documentation on 2026-09-08 and unchanged. Four AAAA
records also exist for IPv6 (`2606:50c0:8000::153` through `...8003::153`) and are
optional; add them only if the apex should answer over IPv6.

Re-verify before setting these if any time has passed. The addresses are GitHub's to
change, and a stale apex record is a site that silently serves someone else.

**Set on 2026-09-08**, with `www` pointing at `jweimann.github.io`.

> **Check the www target once the repository exists.** That hostname was taken from the
> Namecheap account name and a stored git credential, not from GitHub itself. If the
> repository ends up under a different account, `www` resolves to a GitHub user who is
> not Jason and the apex works while `www` does not — which looks like a propagation
> delay and is not one.

### One pre-existing record, left alone

The zone already carried a **wildcard URL Redirect, `*` → `https://podcasters.spotify.com/pod/show/gamedevshow`, unmasked**. It predates this work and was
deliberately not touched.

It does not fight the records above: `@` and `www` are both explicit, and an explicit
host beats the wildcard. What it does catch is every *other* name — `blog.gamedev.show`,
a typo, anything — and send it to Spotify.

Two things worth Jason knowing:

- **The target has moved.** `podcasters.spotify.com` now redirects to
  `creators.spotify.com`, so the record sends visitors through an extra hop to a URL
  Spotify has retired. If it is kept, repoint it.
- **It is the first suspect if HTTPS never provisions.** GitHub validates the
  certificate over the apex and `www`. Those are explicit and should be unaffected, but
  a zone mixing URL Redirect entries with A and CNAME records is unusual enough that
  this is where to look before assuming GitHub is slow.

Keeping it is reasonable if he wants stray subdomains to land somewhere. Dropping it is
also reasonable now that the domain has a real site.

---

## Path B — S3 + CloudFront (matches aidevshow.com and theagenticpodcast.com)

More moving parts, but the same shape as the other two sites, so one mental model for
all three.

**1. Jason: credentials.** Nothing below runs without this, and it is his to do. The
key never gets typed into this session.

```bash
winget install --id Amazon.AWSCLI -e
aws configure          # access key, secret, region us-east-1
```

`us-east-1` matters: CloudFront can only use a certificate issued there.

**2. Then `deploy/aws/deploy.sh` does the rest.** It creates the bucket, requests the
certificate, prints the DNS records to add, waits for validation, creates the
distribution and syncs the site. Read it before running it; it is deliberately
step-by-step rather than one opaque command.

```bash
bash deploy/aws/deploy.sh gamedev.show
```

**3. DNS at Namecheap.** Two records, both of which the script prints for you: a CNAME
for the certificate's validation name, and a CNAME `www` plus an ALIAS/`@` record
pointing at the CloudFront domain. Namecheap BasicDNS supports `ALIAS` at the apex,
which is what makes the bare domain work without Route 53.

---

## When a new episode goes out

```bash
python tools/refresh.py        # add --dry-run first to see what it would pick up
```

That is the whole thing. It re-fetches both YouTube playlists and the podcast feed,
collects metadata and captions for anything new, rebuilds the data and the site, and
prints the new episode count and anything waiting on a decision.

**The fetch has to come first, which is why this is a script and not a list of
commands.** `collect.py` takes its list of videos from the playlist dumps in
`data/raw/`, and those are files from the day they were fetched. Running
`collect → build_data → build_site` on its own would find nothing new and faithfully
rebuild yesterday's site, with no error to notice.

### Title the episode so the rule catches it

`refresh.py` never edits `curation.toml`. An episode is picked up automatically when
its title carries **an episode number or the show's name** — `#166`, `Episode 166`, or
anything containing `Game Dev Show`. The feed's last number is **#165**, so the next one
is **#166**.

An upload titled without either — the way "Why I Stopped Using Event Buses in Unity"
was — is not wrong, it just cannot be placed by rule. It will be listed under "NEEDS A
DECISION" and stay off the site until a line is added to `curation.toml`. That is the
design: the alternative is a channel livestream quietly becoming an episode.

### The recency line

The masthead says "and counting" only when the newest episode is less than twelve months
old. It is off today because the newest is 17 May 2025. It turns itself on when a newer
episode lands; nothing needs editing.

## Re-publishing after a content change

```bash
python tools/build_data.py && python tools/build_site.py
# Path A:
git subtree push --prefix site origin gh-pages
# Path B:
aws s3 sync site/ s3://gamedev.show --delete
aws cloudfront create-invalidation --distribution-id <id> --paths '/*'
```

## Before the first publish

The catalogue currently ends on **11 March 2024**, because the podcast-only rule removed
the two May 2025 episodes. A sponsor-facing page whose newest entry is two and a half
years old undercuts the reason for building it. Rescuing those two in `curation.toml`
is a one-line change each and is Jason's call — see the note at the top of that file.
