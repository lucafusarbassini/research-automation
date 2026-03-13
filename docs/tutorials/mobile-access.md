# Tutorial 7: Mobile Access

This tutorial shows you how to control your research from your phone using
Tailscale, GNU Screen, and Claude's remote-control feature. You can submit
tasks via voice, check progress, and steer your Claude session -- all from
your phone's browser, from anywhere.

**Time:** ~15 minutes

**Prerequisites:**
- A project created with `ricet init` ([Tutorial 3](first-project.md))
- Tailscale installed on your computer (`ricet init` installs it automatically)
- Tailscale app installed on your phone (free, [iOS](https://apps.apple.com/app/tailscale/id1470499037) / [Android](https://play.google.com/store/apps/details?id=com.tailscale.ipn))
- Both devices signed into the same Tailscale account

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Set Up the Three Components](#2-set-up-the-three-components)
3. [Connect from Your Phone](#3-connect-from-your-phone)
4. [Submitting Tasks and Voice Commands](#4-submitting-tasks-and-voice-commands)
5. [How Task Injection Works](#5-how-task-injection-works)
6. [API Endpoints](#6-api-endpoints)
7. [Authentication](#7-authentication)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Architecture Overview

The mobile access system combines three components that run simultaneously:

| Component | What it does |
|-----------|-------------|
| **GNU Screen** | Keeps your Claude session alive even if you close the terminal |
| **Remote Control** | Lets you send prompts to the running Claude session from another terminal |
| **Tailscale + Mobile Server** | Exposes a PWA and API to your phone via your private Tailscale network |

```
Phone (Tailscale) ──→ Tailscale serve ──→ Mobile server (:8777)
                                              │
                                              ├── PWA dashboard
                                              ├── Voice commands
                                              └── Task injection ──→ Screen session ──→ Claude
```

Tasks submitted from your phone are injected directly into the running Claude
session inside Screen. Claude executes them as if you had typed them yourself.

---

## 2. Set Up the Three Components

### Step 1: Start a Screen session with Claude

```bash
screen -S research
claude
```

Claude is now running inside a persistent Screen session called `research`.
Detach with **Ctrl+A then D** -- the session keeps running.

### Step 2: Start the mobile tunnel

In a **new terminal** (or reattach and open a split):

```bash
ricet mobile
```

This is equivalent to `ricet mobile tunnel` and will:

1. Auto-detect your `research` Screen session
2. Start the mobile API server on `localhost:8777`
3. Run `tailscale serve` to proxy it to your Tailscale network over HTTPS
4. Display a QR code and your Tailscale URL

You should see output like:

```
Screen session: research (tasks will be injected)
Server started on http://127.0.0.1:8777
Starting Tailscale serve → tailnet HTTPS...

Public URL (open on your phone):
  https://your-machine.tail0ece0c.ts.net

█▀▀▀▀▀▀▀█ ▄▄▄ █▀▀▀▀▀▀▀█
█ █▀▀▀█ █ ▄ ▄ █ █▀▀▀█ █
...
```

### Step 3: (Optional) Remote control from another terminal

In yet another terminal:

```bash
claude /remote-control
```

This connects to the same Claude session and lets you send prompts to it
interactively from any terminal. Useful for quick interventions without
touching your phone.

### Summary

| Terminal | Command | Purpose |
|----------|---------|---------|
| 1 (Screen) | `screen -S research` then `claude` | Persistent Claude session |
| 2 | `ricet mobile` | Mobile server + Tailscale tunnel |
| 3 (optional) | `claude /remote-control` | Desktop remote control |

---

## 3. Connect from Your Phone

### Prerequisites

1. Install the **Tailscale app** on your phone
2. Sign in with the **same account** as your computer
3. Toggle Tailscale **ON**

### Open the PWA

Open the URL shown by `ricet mobile` in your phone's browser:

```
https://your-machine.tail0ece0c.ts.net
```

Or scan the QR code displayed in the terminal.

### Install as a home screen app

The server provides a Progressive Web App (PWA) with four tabs (Dashboard,
Tasks, Voice, Settings):

- **iOS**: Open in Safari, tap Share, then "Add to Home Screen"
- **Android**: Chrome shows an "Install" banner automatically, or use the menu

The app works in standalone mode (no browser chrome) and supports offline
graceful degradation.

---

## 4. Submitting Tasks and Voice Commands

### From the PWA

- **Tasks tab**: Type a task description and submit it. The task is injected
  directly into your running Claude session.
- **Voice tab**: Tap the microphone button, speak your command, and it gets
  transcribed and submitted as a task.

### From the command line (curl)

```bash
# Submit a text task
curl -s https://your-machine.ts.net/task \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Generate a confusion matrix for the test set"}'

# Submit a voice-transcribed command
curl -s https://your-machine.ts.net/voice \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "check how many epochs have completed"}'
```

---

## 5. How Task Injection Works

When the mobile server starts, it detects running Screen sessions (preferring
one named `research`). When a task or voice command arrives:

1. The server calls `screen -S research -X stuff "<prompt>\r"`
2. This types the prompt directly into the Claude session running inside Screen
3. Claude receives it as a normal user message and executes it
4. The task status is set to `"injected"` (not `"queued"`)

If no Screen session is found, tasks are queued to `state/TODO.md` instead
and picked up by the next overnight iteration.

You can also set the `RICET_SCREEN_SESSION` environment variable to target
a specific session:

```bash
RICET_SCREEN_SESSION=my-session ricet mobile
```

---

## 6. API Endpoints

All API responses are JSON with a `_ts` timestamp.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | PWA dashboard (installable mobile app) |
| `POST` | `/task` | Submit a new task |
| `GET` | `/status` | Server status and queue size |
| `GET` | `/sessions` | List project sessions |
| `POST` | `/voice` | Submit voice-transcribed text as a task |
| `GET` | `/progress` | Recent task entries |
| `GET` | `/projects` | List all registered ricet projects |
| `GET` | `/project/status?name=X` | Specific project status |
| `POST` | `/project/task?name=X` | Submit task to a specific project |
| `GET` | `/connect-info` | TLS fingerprint and connection methods |

---

## 7. Authentication

The mobile server uses bearer token authentication.

### Generate a token

```bash
ricet mobile pair
```

Tokens are 48-character URL-safe strings. The plaintext is shown once; only
the SHA-256 hash is stored on disk (`~/.ricet/mobile_tokens.json`).

### Use the token

Include in every API request:

```
Authorization: Bearer YOUR_TOKEN
```

Or pass as a URL parameter when first opening the PWA (stored in
`localStorage`):

```
https://your-machine.ts.net?token=YOUR_TOKEN
```

### List and revoke tokens

```bash
ricet mobile tokens
```

### Rate limiting

10 failed authentication attempts from a single IP triggers a 15-minute
lockout.

---

## 8. Troubleshooting

### Phone says "offline" or cannot connect

- Open the **Tailscale app** on your phone and make sure it is **toggled ON**
- Verify both devices are on the same Tailscale account
- Check Tailscale status on your computer: `tailscale status`
- Verify the serve proxy is active: `tailscale serve status`

### "tailscale serve failed" error

Run this once to allow your user to manage Tailscale without sudo:

```bash
sudo tailscale set --operator=$USER
```

### Screen session not detected

- Make sure your Screen session is named `research`: `screen -S research`
- Check running sessions: `screen -ls`
- Or set the environment variable: `RICET_SCREEN_SESSION=research ricet mobile`

### Tasks show "queued" instead of "injected"

This means the mobile server did not find a Screen session at startup.
Restart `ricet mobile` after starting your Screen session.

### Voice tab says "Speech not supported"

The Web Speech API requires HTTPS (provided by Tailscale) and is supported
in Chrome and Safari. Firefox does not support it.

### PWA not installable

- Must be served over HTTPS (Tailscale provides this)
- Try clearing browser cache and reloading
- Use Chrome on Android or Safari on iOS

---

**Next:** Return to the [Tutorial Index](README.md).
