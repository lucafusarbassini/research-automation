# Mobile Access

ricet lets you control your research from your phone. Submit tasks, send voice
commands, and monitor progress -- all from a mobile-friendly PWA served over
your private Tailscale network.

---

## Quick Start

Three commands, three terminals:

```bash
# Terminal 1: persistent Claude session
screen -S research
claude

# Terminal 2: mobile server + Tailscale tunnel
ricet mobile

# Terminal 3 (optional): desktop remote control
claude /remote-control
```

`ricet mobile` auto-detects the Screen session, starts the API server, and
creates a Tailscale HTTPS tunnel. A QR code and URL are printed -- scan it
with your phone.

---

## Prerequisites

| Requirement | How to get it |
|-------------|--------------|
| Tailscale on your computer | `ricet init` installs it automatically |
| Tailscale on your phone | Free app: [iOS](https://apps.apple.com/app/tailscale/id1470499037) / [Android](https://play.google.com/store/apps/details?id=com.tailscale.ipn) |
| Same Tailscale account | Sign in on both devices with the same account |

---

## How It Works

```
Phone (Tailscale app) ──→ tailscale serve ──→ localhost:8777 (mobile server)
                                                    │
                                                    └── screen -X stuff ──→ Claude session
```

1. The mobile server runs on `localhost:8777`
2. `tailscale serve` proxies it to `https://your-machine.your-tailnet.ts.net`
3. Your phone connects via Tailscale (encrypted, private, no port forwarding)
4. Tasks submitted from the phone are injected directly into the Claude session
   running in GNU Screen

---

## Progressive Web App (PWA)

Open the Tailscale URL on your phone to access the PWA with four tabs:

| Tab | Purpose |
|-----|---------|
| **Dashboard** | Project status, task queue, auto-refresh |
| **Tasks** | Type and submit tasks to Claude |
| **Voice** | Tap microphone, speak a command, submit |
| **Settings** | Connection info, token management |

Install it to your home screen for a native app experience:

- **iOS**: Safari → Share → "Add to Home Screen"
- **Android**: Chrome shows an install banner automatically

---

## Task Injection

When the mobile server detects a Screen session (preferring one named
`research`), submitted tasks are **injected directly** into Claude:

```
POST /task  →  screen -S research -X stuff "your prompt\r"  →  Claude executes it
```

The task status is `"injected"`. If no Screen session is found, tasks fall
back to `"queued"` in `state/TODO.md` for overnight mode to pick up.

Set `RICET_SCREEN_SESSION=name` to target a specific session.

---

## CLI Reference

```bash
# Start tunnel (default action)
ricet mobile                    # = ricet mobile tunnel

# Force Cloudflare tunnel instead of Tailscale
ricet mobile --cf

# Other actions
ricet mobile serve              # Start server without tunnel
ricet mobile stop               # Stop the server
ricet mobile pair               # Generate auth token + QR
ricet mobile tokens             # List active tokens
ricet mobile connect-info       # Show connection methods
ricet mobile cert-regen         # Regenerate TLS certificates
ricet mobile status             # Check server status
```

---

## API Endpoints

All responses are JSON with a `_ts` timestamp.

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| `GET` | `/` | PWA dashboard | No |
| `POST` | `/task` | Submit a task | Yes |
| `POST` | `/voice` | Submit voice command | Yes |
| `GET` | `/status` | Server status | Yes |
| `GET` | `/progress` | Recent tasks | Yes |
| `GET` | `/sessions` | Project sessions | Yes |
| `GET` | `/projects` | All registered projects | Yes |
| `GET` | `/project/status?name=X` | Project-specific status | Yes |
| `POST` | `/project/task?name=X` | Task for specific project | Yes |
| `GET` | `/connect-info` | TLS fingerprint | Yes |

---

## Authentication

Bearer token authentication. Generate a token with `ricet mobile pair`.

```
Authorization: Bearer YOUR_TOKEN
```

Or pass as a URL parameter when first opening the PWA (stored in
`localStorage` for subsequent requests):

```
https://your-machine.ts.net?token=YOUR_TOKEN
```

Tokens are 48-character URL-safe strings. Only SHA-256 hashes are stored on
disk (`~/.ricet/mobile_tokens.json`). Rate limiting: 10 failed attempts from
one IP triggers a 15-minute lockout.

---

## Security Model

- **Tailscale**: End-to-end encrypted WireGuard tunnel between your devices.
  No ports exposed to the internet. Only devices on your tailnet can connect.
- **Bearer tokens**: SHA-256 hashed, stored on disk. Plaintext shown once.
- **Rate limiting**: Per-IP lockout after repeated failures.
- **TLS**: Self-signed certificates for local connections. Tailscale serve
  provides its own trusted HTTPS certificate for phone access.

---

## Troubleshooting

### Phone cannot connect

1. Open Tailscale app on your phone -- is it **ON**?
2. Same account on both devices?
3. Check on computer: `tailscale status` (should show both devices)
4. Check proxy: `tailscale serve status`

### "tailscale serve failed"

```bash
sudo tailscale set --operator=$USER    # run once
```

### Tasks show "queued" not "injected"

The server didn't find a Screen session at startup. Start `screen -S research`
first, then restart `ricet mobile`.

### Voice not working

Requires HTTPS (provided by Tailscale) + Chrome or Safari. Firefox does not
support the Web Speech API.
