# NxtWave Workshop — Referral Tracker + WhatsApp Flow (v2)

Working asset for the Growth Challenge. One Flask service that runs the whole registration loop:

| Piece | What it does |
|---|---|
| Landing page `/` | 30-second registration, live seat counter, "invited by X" banner, your own referral count |
| Referral loop | Every registrant gets a code (e.g. `PRIY482`) + one-tap WhatsApp share with pre-filled copy |
| Channel attribution | `?src=wa|li|club|email|qr` on every link → know exactly which channel delivered |
| Admin dashboard `/dashboard?key=…` | Progress to 500, per-day chart, per-channel chart, top colleges, K-factor, CSV export |
| Broadcast generator `/api/messages/<day>` | Day 1–7 WhatsApp copy, auto-filled with live numbers (seats left, referrals so far) |

## Run locally
```bash
pip install -r requirements.txt
python seed_demo.py          # optional: 300+ realistic rows for the demo video
python app.py                # http://localhost:5000  ·  dashboard: /dashboard?key=nxtwave-admin
```

## Deploy on Railway (5 min)
1. Push this folder to GitHub → Railway → New Project → Deploy from repo.
2. Variables: `ADMIN_KEY`, `BASE_URL=https://<your-app>.up.railway.app`, `DB_PATH=/data/tracker.db`.
3. Add a **Volume** mounted at `/data` (otherwise SQLite resets on every redeploy — that was the bug in v1's JSON file).
4. Done. Share links: `BASE_URL/?src=wa` for WhatsApp groups, `?src=li` for LinkedIn, `?src=club`, `?src=email`, `?src=qr`.

The old v1 routes (`/api/register`, `/api/stats`, `/api/referrer/<code>`) still work, so an existing Vercel front-end keeps functioning.

## Tracking links cheat-sheet
| Channel | Link |
|---|---|
| CR / WhatsApp groups | `/?src=wa` |
| Placement-cell email | `/?src=email` |
| Coding club post | `/?src=club` |
| LinkedIn | `/?src=li` |
| Poster QR | `/?src=qr` |
| Student referral | `/?ref=<CODE>` (auto-tagged as Referral) |
