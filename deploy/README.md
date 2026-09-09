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

## Path A — GitHub Pages (recommended)

One repo, one push, free certificate. Best if the source can be public.

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

**3. Custom domain.** `deploy/github-pages/CNAME` is ready; it must sit at the root of
whatever branch/folder Pages serves. Copy it in before the push:

```bash
cp deploy/github-pages/CNAME site/CNAME
```

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
| CNAME | www | `<username>.github.io.` | Automatic |

Those four apex addresses are GitHub's published Pages set. Verify them against
GitHub's own docs at the time of setup rather than trusting this table; they change
rarely but they do change.

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
