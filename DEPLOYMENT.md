# Visioret — Free Deployment Guide

Getting Visioret onto a public HTTPS URL, **at zero cost**, so it can be
demonstrated from any device with a browser — a borrowed laptop, the venue's
PC, or a phone.

> **Status (2026-10-02): LIVE at <https://visioret.eastasia.cloudapp.azure.com>.**
> Phases 0–4 done. VM: East Asia, `Standard_B2als_v2` (2 vCPU, 4 GiB),
> Ubuntu 24.04, key `C:\Users\User\.ssh\visioret_key2.pem`. Verified live:
> Let's Encrypt HTTPS with HTTP→HTTPS redirect, OCT prediction (~4 s),
> non-OCT rejection (422), scan images served, and recovery to healthy
> **61 s after a reboot** with no manual steps. Remaining: Phase 5 accounts
> (register, then promote to admin), Phase 6 backup dry run.
>
> To manage the running server, jump to **Managing the live server**.

---

## Why this setup

**Primary: one Azure virtual machine, paid for by Azure for Students credit.**
**Backup: GitHub Codespaces, started on demand.** Both are free and neither
needs a credit card.

| Option considered | Verdict | Reason (checked 2026-09-30) |
|---|---|---|
| **Azure for Students VM** | ✅ **Chosen** | $100 credit for 12 months, **no credit card**, verified with a university email. A 4 GB VM runs the existing Docker Compose stack almost unchanged, on a real disk, so accounts, scans *and images* all persist. |
| **GitHub Codespaces** | ✅ **Backup** | 120 core-hours/month free, no payment method needed. Only online while you have it running — good for a demo, not a permanent URL. |
| Hugging Face Docker Space | ❌ | The earlier plan. Docker Spaces now require a paid plan (PRO, $9/mo) to create. Its disk is also wiped on every restart, which would lose uploaded scan images. |
| Render / Koyeb free tiers | ❌ | ~512 MB RAM. The backend peaks at ~686 MB (R8 in `REVIEW_CHECKPOINTS.md`). |
| Oracle Always Free, Google Cloud Run | ❌ | Both require a credit card to sign up. |

Free-tier terms change. Re-check them as you sign up.

### What the live system looks like

```
Visitor's browser
   │  https://visioret-xxxx.<region>.cloudapp.azure.com
   ▼
Azure VM (Ubuntu) ── only ports 22, 80, 443 open
   └─ Docker Compose (docker-compose.prod.yml)
        caddy     :80/:443  HTTPS (free Let's Encrypt cert, auto-renewed)
          ├─ /api/*, /media/*, /docs  ──►  backend  (FastAPI, not public)
          └─ everything else          ──►  frontend (nginx, not public)
        db        Postgres 16, not public, data in a Docker volume
```

**One URL, one origin.** The browser only ever talks to Caddy, so the
frontend uses relative `/api/...` calls. That removes the CORS configuration,
the CSP `connect-src` entry, and the build-time `VITE_API_BASE_URL` problem
in one move — the same reasoning as the old plan, now without a paid host.

---

## Phase 0 — Code changes ✅ done (verified locally, pushed in `ba7d116`)

Verified against the production stack running locally with
`SITE_ADDRESS=http://localhost`: only Caddy publishes ports; `/`, `/history`,
`/scans/1`, `/metrics` all resolve; the built bundle contains no
`localhost:8000`; an OCT sample predicts (200) and a chart is rejected (422);
both scan images load from `/media`; register → login → viewer gets 403 on
metrics → promoted to reviewer gets 200 with both seeded metric rows;
feedback saves; the UI renders the full analysis with no CSP errors. The
backend logged the real client address rather than Caddy's, and ignored a
spoofed `X-Forwarded-For` header. Cold start to healthy: ~85 s with empty
caches.

Everything the local setup assumes about `localhost` has to become
configuration. Nothing here changes how the app behaves locally with the
existing `docker-compose.yml`.

- [x] **`docker-compose.prod.yml`** — a separate production compose file:
      - adds a **Caddy** service as the only thing listening publicly;
      - builds the frontend with an **empty** `VITE_API_BASE_URL`, so every
        call is relative (`/api/...`) — same origin;
      - **no published ports** for `db`, `backend` or `frontend`;
      - Postgres password read from `.env` instead of the hardcoded
        `visioret`;
      - `restart: unless-stopped` on every service, so the stack comes back by
        itself after a crash or a VM reboot.
- [x] **`deploy/Caddyfile`** — routes `/api/*`, `/media/*`, `/docs`,
      `/openapi.json` to the backend and everything else to the frontend.
      The site address comes from `.env`, so the same file works on Azure
      (real domain → automatic HTTPS) and in Codespaces / local testing
      (plain HTTP).
- [x] **Real client IPs behind the proxy.** Uvicorn runs with
      `--proxy-headers`, so the auth rate limiter sees each visitor's address
      instead of Caddy's. Without this, **10 failed logins by anyone would
      lock out everyone for 5 minutes** — see the warning already written in
      `backend/rate_limit.py`. Safe only because the backend is not reachable
      except through Caddy.
- [x] **`.env.production.example`** — the three values the server needs:
      `SITE_ADDRESS`, `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`.
- [x] **Verify locally** — run the production stack on this machine with
      `SITE_ADDRESS=http://localhost` and walk the whole demo: upload, Grad-CAM,
      non-OCT rejection, register/login, roles, metrics, review, History,
      direct navigation to `/history` and `/scans/1`.
- [x] **You commit and push to GitHub.** The VM clones from GitHub, so the
      server only ever gets what has been pushed.

---

## Phase 1 — Azure for Students account (~15 minutes)

- [ ] **Step 1 — Sign up** at <https://azure.microsoft.com/free/students> with
      your **university email address**. No credit card is asked for.
      - If your university email is not accepted, tell Claude before trying
        anything else — do not enter a card anywhere.
- [ ] **Step 2 — Find your allowed regions.** Student subscriptions may only
      deploy to about five regions, and the list differs per account.
      In the portal search bar type **Policy** → left menu **Authoring →
      Assignments** → open **"Allowed resource deployment regions"** →
      **Parameters** (or *View assignment* → Parameters) → note the allowed
      locations. **Do not skip this** — picking any other region in Step 4
      fails the whole deployment with `RequestDisallowedByAzure`. Prefer the one closest to Bangladesh (e.g.
      *Central India*, *South India*, *Southeast Asia*) if it is on your list —
      lower latency for your audience.
- [ ] **Step 3 — Set a budget alert** so the credit can never surprise you.
      Search **Cost Management** → **Budgets** → **Add** → amount `$100`,
      alerts at 50% and 80%, your email. Check the remaining credit any time at
      <https://www.microsoftazuresponsorships.com/balance>.

---

## Phase 2 — Create the VM (~15 minutes)

- [ ] **Step 4 — Portal → Create a resource → Virtual machine.** Fill in:

      | Field | Value |
      |---|---|
      | Subscription | Azure for Students |
      | Resource group | **Create new** → `visioret-rg` |
      | Virtual machine name | `visioret` |
      | Region | one of **your allowed regions** (Step 2) |
      | Availability options | No infrastructure redundancy required |
      | Image | **Ubuntu Server 24.04 LTS – x64 Gen2** |
      | Size | **Standard_B2s** (2 vCPU, 4 GiB). If unavailable in your region, **Standard_B2as_v2** or **Standard_B2als_v2** (also 4 GiB). **Do not pick anything under 4 GiB.** |
      | Authentication type | **SSH public key** |
      | Username | `azureuser` |
      | SSH public key source | Generate new key pair, name `visioret-key` |
      | Public inbound ports | Allow selected ports → **SSH (22), HTTP (80), HTTPS (443)** |

      **Disks tab:** OS disk type *Standard SSD*, default size (30 GiB) is enough.
      **Management tab:** make sure **Enable auto-shutdown is unchecked** —
      otherwise the site switches itself off every evening.

- [ ] **Step 5 — Review + create → Create → "Download private key and create
      resource".** Save the `.pem` file. **It cannot be downloaded again**, and
      it is the only way into the server. Move it to
      `C:\Users\User\.ssh\visioret_key2.pem`. Never commit it.

- [ ] **Step 6 — Give the VM a permanent hostname.** When deployment finishes:
      **Go to resource → Overview → DNS name: Not configured** → set the label
      to something like `visioret-rifat` → **Save**. Your site address is now
      `visioret-rifat.<region>.cloudapp.azure.com` — note it exactly; it goes
      into `.env` in Step 11.

Rough cost: a B2s-class VM plus disk and IP is on the order of $35–45/month
(check Azure's pricing calculator for your region), so $100 lasts about two
to three months — well past the presentation.

---

## Phase 3 — Connect and prepare the server (~15 minutes)

- [ ] **Step 7 — SSH in from this PC** (PowerShell):

      ssh -i $HOME\.ssh\visioret_key2.pem azureuser@visioret.eastasia.cloudapp.azure.com

      Type `yes` to the fingerprint prompt the first time. If ssh refuses with
      *"UNPROTECTED PRIVATE KEY FILE"*, restrict the file to your user:

      icacls $HOME\.ssh\visioret_key2.pem /inheritance:r /grant:r "$($env:USERNAME):R"

      Everything from here to Phase 5 runs **on the server**, inside that
      SSH session.

- [ ] **Step 8 — Add 2 GB of swap** (insurance against running out of memory
      during the first image build):

      sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
      echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

- [ ] **Step 9 — Install Docker** (official install script; also enables it
      to start on boot):

      curl -fsSL https://get.docker.com | sudo sh
      sudo usermod -aG docker $USER

      Then `exit`, and SSH back in (Step 7) so the group change applies.
      Check with `docker run --rm hello-world`.

---

## Phase 4 — Deploy (~30 minutes, mostly waiting)

Only after Phase 0 is pushed to GitHub.

- [ ] **Step 10 — Clone the repo:**

      git clone https://github.com/Tusher3584/visioret.git
      cd visioret

- [ ] **Step 11 — Create the server's `.env`:**

      cp .env.production.example .env
      nano .env

      | Variable | Value |
      |---|---|
      | `SITE_ADDRESS` | your hostname from Step 6, **no** `https://` — e.g. `visioret.eastasia.cloudapp.azure.com` |
      | `JWT_SECRET_KEY` | output of `openssl rand -hex 32` |
      | `POSTGRES_PASSWORD` | output of `openssl rand -hex 24` (a *different* value) |

      Generate each value in the terminal first, then paste it in. Save with
      `Ctrl+O`, `Enter`, exit with `Ctrl+X`. These values live only on the
      server — never in git, never in chat.

- [ ] **Step 12 — Start it:**

      docker compose -f docker-compose.prod.yml up -d --build

      The first build installs PyTorch and builds the frontend: **expect
      10–20 minutes.** Watch the backend come up:

      docker compose -f docker-compose.prod.yml logs -f backend

      Wait for Uvicorn's "Application startup complete", then `Ctrl+C` (this
      only stops *watching* the logs, not the app).

- [ ] **Step 13 — Open `https://<your hostname>`.** Caddy obtains the HTTPS
      certificate automatically on the first request — it can take ~30 s the
      very first time. If the browser shows a certificate error, wait a
      minute and reload.

---

## Phase 5 — Bring it to life (~15 minutes)

- [ ] **Step 14 — Register your account** in the UI. Use a real-looking email
      domain — `.test`, `.local` and `localhost` are correctly rejected as
      reserved domains.
- [ ] **Step 15 — Make yourself admin** (on the server):

      docker compose -f docker-compose.prod.yml exec backend python -m backend.grant_role your@email.com admin

      This is the *only* way to create an admin, by design.
- [ ] **Step 16 — Create a reviewer account for the demo** — register a
      second account, then promote it to reviewer from the in-app Admin page.
      The Metrics page is reviewer-only.
- [ ] **Step 17 — Verify live**, from your **phone on mobile data** (proves it
      works from outside your home network):
      - upload a real OCT scan → prediction, Grad-CAM overlay, interpretation
      - upload a non-OCT photo → rejected, **no diagnosis shown**
      - History lists the scan; open it; images load
      - Metrics → both result tables and confusion matrices
      - record a review on a scan → attribution and timestamp appear
- [ ] **Step 18 — Prove it survives a reboot:**

      sudo reboot

      Wait ~2 minutes, reload the site. Everything — including your
      accounts and old scans — should be back without you doing anything.

---

## Phase 6 — Backup: GitHub Codespaces (do one dry run before the day)

If Azure is unreachable on the day, this gives you a working copy in ~15
minutes from **any browser**, including the venue's computer. Its database
starts empty — it is a fallback, not a mirror.

- [ ] **Step 19 — Set the idle timeout first:** <https://github.com/settings/codespaces>
      → *Default idle timeout* → **240 minutes** (the default 30 would stop it
      mid-presentation).
- [ ] **Step 20 — Start it:** on the GitHub repo page → **Code** →
      **Codespaces** → **Create codespace on main**. In its terminal:

      cp .env.production.example .env

      Set `SITE_ADDRESS=:80`, and generate the two secrets with
      `openssl rand -hex 32` as in Step 11. Then:

      docker compose -f docker-compose.prod.yml up -d --build

- [ ] **Step 21 — Make it public:** **Ports** tab → port **80** → right-click →
      **Port Visibility → Public** → open the `…app.github.dev` URL.
- [ ] **Step 22 — Stop it when done** (Codespaces menu → *Stop codespace*), and
      delete it after the presentation — stopped codespaces still use the
      15 GB/month free storage.

---

## Presentation-day checklist

- **Day before:** open the site, run the full Step 17 walk-through, check the
  Azure credit balance.
- **Morning of:** open the site once. Confirm it loads on your phone.
- **Have your test images reachable from any computer.** You will not be on
  your own machine. The four sample scans are public in the repo
  (`samples/` on GitHub); also put them plus one **non-OCT photo** in Google
  Drive or on a USB stick.
- **Sign in as the reviewer account** before you start, so Metrics and Review
  are visible.
- **Backup video.** Record a 2–3 minute screen capture of the full flow; keep
  it on your phone and a USB stick. The venue network is the one thing no
  deployment can fix.

---

## Managing the live server

Everything below is run **on the server**. Connect first, from PowerShell on
this PC:

    ssh -i $HOME\.ssh\visioret_key2.pem azureuser@visioret.eastasia.cloudapp.azure.com

then:

    cd ~/visioret

Every command below starts with `docker compose -f docker-compose.prod.yml`
because the production stack lives in that file, not the default
`docker-compose.yml`. Leaving `-f ...` off makes compose look at the *dev*
file and report that nothing is running.

### Where things live on the server

| What | Where | Survives reboot / rebuild? |
|---|---|---|
| Code | `~/visioret` (a git clone of GitHub `main`) | yes |
| Secrets | `~/visioret/.env` (owner-only, never in git) | yes |
| Accounts, scans, reviews | Docker volume `visioret-prod_pgdata` | yes |
| Uploaded scans + Grad-CAM images | `~/visioret/backend/media/scans/` | yes |
| HTTPS certificate | Docker volume `visioret-prod_caddy_data` | yes — renewed automatically |
| ResNet / CLIP weight caches | Docker volumes `..._torch_cache`, `..._hf_cache` | yes |

`docker compose ... down` stops and removes the containers but **keeps** all
of the above. `down -v` would **delete the volumes** — every account and
scan. Never add `-v` on the server.

### Everyday commands

| I want to… | Command |
|---|---|
| See if everything is running | `docker compose -f docker-compose.prod.yml ps` |
| Check health from anywhere | open `https://visioret.eastasia.cloudapp.azure.com/api/health` |
| Watch backend logs live (`Ctrl+C` stops watching, not the app) | `docker compose -f docker-compose.prod.yml logs -f backend` |
| See the last 100 lines of any service | `docker compose -f docker-compose.prod.yml logs --tail 100 caddy` (or `backend`, `frontend`, `db`) |
| Restart just the backend | `docker compose -f docker-compose.prod.yml restart backend` |
| Restart everything | `docker compose -f docker-compose.prod.yml restart` |
| Memory / disk | `free -h` and `df -h /` |
| List accounts and roles | `docker compose -f docker-compose.prod.yml exec backend python -m backend.grant_role --list` |
| Make someone admin | `docker compose -f docker-compose.prod.yml exec backend python -m backend.grant_role someone@example.com admin` |
| Make someone a reviewer (or use the in-app Admin page) | `... grant_role someone@example.com reviewer` |
| Preview deleting anonymous scans | `docker compose -f docker-compose.prod.yml exec backend python -m backend.purge_anonymous --dry-run --all` |
| Delete anonymous scans older than a day | `docker compose -f docker-compose.prod.yml exec backend python -m backend.purge_anonymous --older-than-hours 24` |
| Leave the server | `exit` |

### Deploying a change

1. Change code on this PC, test it locally, commit, push to GitHub.
2. On the server:

       cd ~/visioret
       git pull
       docker compose -f docker-compose.prod.yml up -d --build

Only images whose inputs changed are rebuilt, and only their containers are
replaced. A frontend-only change takes about a minute; a change to
`requirements.txt` reinstalls Python packages and takes much longer. The
site is down for a few seconds while the backend container restarts (~60 s
for it to load the models again).

Changes to `model/` (e.g. a retrained checkpoint) need only
`docker compose -f docker-compose.prod.yml restart backend` after the pull,
because `model/` is mounted into the container rather than built into it.

### Backups

Copy the database to a file on the server, then download it to this PC:

    docker compose -f docker-compose.prod.yml exec -T db pg_dump -U visioret visioret > ~/backup.sql

and from PowerShell on **this PC**:

    scp -i $HOME\.ssh\visioret_key2.pem azureuser@visioret.eastasia.cloudapp.azure.com:backup.sql .

### Credit and cost

- Remaining credit: <https://www.microsoftazuresponsorships.com/balance>
- The VM costs about **$1.25/day** while running (B2als_v2 at $0.0526/hr,
  plus a little for disk and IP).
- To stop spending **after the presentation**: Azure portal → VM `visioret`
  → **Stop**. A stopped (deallocated) VM costs only a few cents a day for its
  disk; the site goes offline. **Start** brings everything back exactly as it
  was, since all containers restart on boot. The DNS name stays the same.
- To remove everything permanently: delete the resource group `visioret-rg`.
  This cannot be undone.

### Server maintenance

Ubuntu installs security updates automatically (`unattended-upgrades` is on
by default). Some need a reboot to take effect; rebooting is safe at any time
— the site was measured coming back **61 s** after a reboot with no manual
steps:

    sudo reboot

---

## Troubleshooting

**`ssh: connect ... timed out`.** Port 22 not open — VM → *Networking* →
check an inbound rule allows 22. Or the VM is stopped — *Overview* → *Start*.

**Site doesn't load at all, but SSH works.** Check the containers:
`docker compose -f docker-compose.prod.yml ps`. All should be `Up`. Then check
ports 80/443 are allowed under VM → *Networking*.

**Certificate error that doesn't go away.** `SITE_ADDRESS` in `.env` must be
*exactly* the Azure DNS name, without `https://`. After fixing it:
`docker compose -f docker-compose.prod.yml up -d`. Check
`docker compose -f docker-compose.prod.yml logs caddy`.

**Build killed / "exit code 137".** Out of memory — Step 8 (swap) was skipped,
or the VM has less than 4 GiB.

**"Application startup failed" mentioning JWT.** `JWT_SECRET_KEY` missing from
`.env`.

**Login says "Too many attempts."** The rate limiter is working (10 failed
logins per 5 minutes, per visitor). Wait it out, or restart the backend — its
state is in-process.

**VM creation fails with `InvalidTemplateDeployment` /
`RequestDisallowedByAzure` on every resource** ("This policy maintains a set
of best available regions…"). The region isn't in your subscription's allowed
list — every resource fails because the policy checks each one. Nothing was
created and no credit was spent. Redo Step 2 to get the list, then retry
Step 4 with an allowed region (the resource group's own location does not
matter). On the retry, generate a **new** SSH key pair with a new name and
discard any `.pem` downloaded on the failed attempt.

**Size not available.** Try another allowed region, or one of the alternative
4 GiB sizes listed in Step 4.

---

## Two things to decide knowingly

**Uploaded scan images are served without authentication.** Filenames are
random UUIDs so they cannot be guessed, but anyone holding a link can view
that image indefinitely. For a demo with public sample scans this is fine; it
is documented in `backend/main.py` and `FEATURES.md`. On a public URL it
should be a decision you have actually made.

**Anyone on the internet can use it.** Registration is open and `/api/predict`
is not rate-limited, so a stranger could upload images or create viewer
accounts. Viewers cannot see anyone else's scans or record corrections, so
the exposure is limited to disk usage and CPU time. After the defense you can
stop the VM (VM → *Stop*) to pause all of it.
