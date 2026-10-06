# Calendar Face

A real-time AI avatar that reads (and can create/reschedule) Google Calendar events and holds you accountable.

Built on [LiveKit Agents](https://docs.livekit.io/agents/) + [Synthesia Interactive Avatars](https://www.synthesia.io/features/avatars/interactive-avatars). Inspired by [this tutorial](https://youtu.be/xQoJA9_1EXA).

**Powered by [Naga Codex](https://www.nagacodex.cloud/).**

## Bring your own keys (BYOK)

This project is meant to be **self-hosted by each user**.  
You do **not** put your LiveKit / Synthesia / Google keys in the public app.

| Who | Pays for |
|-----|----------|
| Each end user | Their own LiveKit project, Synthesia Interactive Avatars, Google Cloud (free tier is usually enough) |
| You (repo author) | Nothing — as long as you never ship a hosted demo wired to *your* `.env` |

Do **not** deploy one shared Cloud agent with your API keys and let strangers use it. That bills **you**.

## What each user needs

1. **LiveKit Cloud** project → URL + API key + secret ([cloud.livekit.io](https://cloud.livekit.io))
2. **Synthesia** API key with **Interactive Avatars** scope ([docs](https://docs.synthesia.io/docs/developers))
3. **Google Cloud** OAuth Desktop client + Calendar API enabled → save as `credentials.json`

## Setup

```bash
git clone <your-repo-url>
cd avatar-face-for-google-calendar-main   # or your folder name
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with **their** keys. Put Google’s downloaded OAuth JSON here as `credentials.json` (never commit it).

## Run locally

Terminal 1 — agent worker:

```bash
source .venv/bin/activate
python agent.py dev
```

First run opens Google login and writes `token.json` (local only).

Terminal 2 — branded viewer (optional, good for demos):

```bash
source .venv/bin/activate
python view_avatar.py
```

Open http://127.0.0.1:8765 → **Connect once** (Synthesia plans often allow only 1 concurrent avatar session).

Or use LiveKit Cloud → Agents → select the agent named like `LIVEKIT_AGENT_NAME` → Launch Console.

## Env vars

See [`.env.example`](.env.example):

- `SYNTHESIA_API_KEY` — required  
- `SYNTHESIA_AVATAR_ID` — optional gallery id  
- `LIVEKIT_URL` / `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` — required  
- `LIVEKIT_AGENT_NAME` — must match the agent name used in LiveKit dispatch/Console  

## Deploy options (still BYOK)

| Option | Use when | Your keys exposed? |
|--------|----------|--------------------|
| **Local run** (above) | Friends, open-source users, demos on their machine | No |
| **User deploys to their LiveKit Cloud** | They want it always-on | No — they use `lk agent` + their secrets |
| **Your hosted multi-tenant SaaS** | Product with accounts + billing | Would use *your* keys unless you add per-user key vault + billing — don’t do this casually |

Recommended for GitHub: ship the code + README; users clone and run with their own `.env`.

## Security checklist before `git push`

- [ ] `.env`, `credentials.json`, `token.json`, `client_secret*.json` are gitignored  
- [ ] `.env.example` has empty placeholders only  
- [ ] No real keys in README, commits, or screenshots  
- [ ] If keys were ever pasted into chat/files that were shared, **rotate** them in LiveKit + Synthesia  

## License / credit

Demo UI branding includes a local `logo.png`.  
Powered by [Naga Codex](https://www.nagacodex.cloud/).
