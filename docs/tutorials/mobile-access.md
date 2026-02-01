# Tutorial 7: Mobile Access

This tutorial shows you how to set up mobile phone access to your ricet
projects. You can submit tasks, check status, review progress, and
send voice commands -- all from your phone's browser.

**Time:** ~15 minutes

**Prerequisites:**
- A project created with `ricet init` ([Tutorial 3](first-project.md))
- Your computer and phone on the same network (for local access), or a public
  server/tunneling setup (for remote access)

---

## Table of Contents

1. [How Mobile Access Works](#1-how-mobile-access-works)
2. [Start the Mobile Server](#2-start-the-mobile-server)
3. [Connect from Your Phone](#3-connect-from-your-phone)
4. [API Endpoints](#4-api-endpoints)
5. [Authentication](#5-authentication)
6. [Remote Access via Tunnel](#6-remote-access-via-tunnel)
7. [Using a Bookmarklet or Shortcut](#7-using-a-bookmarklet-or-shortcut)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. How Mobile Access Works

The mobile module (`core/mobile.py`) runs a lightweight HTTP API server on port
8777. It uses only Python standard library modules (no Flask, no Django) so
there are no extra dependencies.

The server provides five endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/task` | Submit a new task |
| GET | `/status` | Get project status |
| GET | `/sessions` | List sessions |
| POST | `/voice` | Submit voice-transcribed text as a task |
| GET | `/progress` | View recent task progress |

All responses are JSON, formatted for compact mobile display (strings truncated
to 280 characters).

---

## 2. Start the Mobile Server

### From Python

```python
from core.mobile import start_server, MobileAuth

# Without authentication (local network only)
start_server(host="0.0.0.0", port=8777)

# With authentication (recommended)
auth = MobileAuth()
token = auth.generate_token()
print(f"Your access token: {token}")
start_server(host="0.0.0.0", port=8777, auth=auth)
```

### From a script

Create a quick startup script:

```bash
$ cat > start_mobile.py << 'EOF'
#!/usr/bin/env python3
from core.mobile import start_server, generate_mobile_url, MobileAuth
import time

auth = MobileAuth()
url = generate_mobile_url(port=8777, auth=auth)
print(f"Mobile access URL: {url}")
print("Share this URL with your phone (copy or scan QR code)")
print("Press Ctrl+C to stop")

thread = start_server(host="0.0.0.0", port=8777, auth=auth)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    from core.mobile import stop_server
    stop_server()
    print("Server stopped.")
EOF

$ python3 start_mobile.py
Mobile access URL: http://0.0.0.0:8777?token=abc123...
```

### Alongside overnight mode

You can run the mobile server in the background while overnight mode runs:

```bash
# Terminal 1: Start mobile server
$ python3 start_mobile.py &

# Terminal 2: Start overnight mode
$ ricet overnight --iterations 20
```

---

## 3. Connect from Your Phone

### Step 1: Find your computer's local IP

```bash
$ hostname -I | awk '{print $1}'
192.168.1.100
```

### Step 2: Open the URL on your phone

Open your phone's browser and navigate to:

```
http://192.168.1.100:8777?token=YOUR_TOKEN
```

> **Screenshot:** Phone browser showing the JSON response from the /status
> endpoint with project status information displayed.

### Step 3: Test with a status check

Navigate to:
```
http://192.168.1.100:8777/status
```

You should see:
```json
{
  "ok": true,
  "status": "running",
  "tasks_queued": 2,
  "tasks_total": 5,
  "_ts": "2026-02-01T23:15:00+00:00"
}
```

---

## 4. API Endpoints

### Submit a task

```bash
# From phone browser or using a REST client app:
POST http://192.168.1.100:8777/task
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{"prompt": "Generate a confusion matrix figure for the test results"}
```

Response:
```json
{
  "ok": true,
  "task_id": "a1b2c3d4e5f6",
  "status": "queued",
  "_ts": "2026-02-01T23:15:00+00:00"
}
```

### Check status

```bash
GET http://192.168.1.100:8777/status
Authorization: Bearer YOUR_TOKEN
```

### View progress

```bash
GET http://192.168.1.100:8777/progress
Authorization: Bearer YOUR_TOKEN
```

Response:
```json
{
  "ok": true,
  "entries": [
    {"task_id": "a1b2c3d4e5f6", "prompt": "Generate a confusion...", "status": "queued"},
    {"task_id": "f6e5d4c3b2a1", "prompt": "Run training...", "status": "queued"}
  ],
  "_ts": "2026-02-01T23:16:00+00:00"
}
```

### Submit voice command

```bash
POST http://192.168.1.100:8777/voice
Content-Type: application/json
Authorization: Bearer YOUR_TOKEN

{"text": "check how many epochs have completed"}
```

> **Screenshot:** Phone showing a simple interface (or REST client app) with
> a text field for entering tasks and a "Submit" button.

---

## 5. Authentication

The mobile server uses bearer token authentication. Tokens are generated
randomly (48 characters, URL-safe).

### Generate a token

```python
from core.mobile import MobileAuth

auth = MobileAuth()
token = auth.generate_token()
print(token)  # e.g., "kF3x9Qm2-vB7_nL1pR8..."
```

### Use the token in requests

Add the `Authorization` header to every request:

```
Authorization: Bearer kF3x9Qm2-vB7_nL1pR8...
```

Or pass it as a URL parameter (less secure, but convenient for bookmarks):

```
http://192.168.1.100:8777/status?token=kF3x9Qm2-vB7_nL1pR8...
```

### Revoke a token

```python
auth.revoke("kF3x9Qm2-vB7_nL1pR8...")
```

### Security notes

- Tokens are stored in memory only. Restarting the server invalidates all tokens.
- For local network access, the token prevents others on your network from
  controlling your research.
- For internet-facing deployments, always use HTTPS (see tunnel section below).

---

## 6. Remote Access via Tunnel

If you want to access your research from outside your local network (e.g., from
your phone on cellular data), use an SSH tunnel or a tunneling service.

### Option A: SSH tunnel (if you have a server with a public IP)

On your local machine:

```bash
$ ssh -R 8777:localhost:8777 user@your-server.com
```

Then access `http://your-server.com:8777` from your phone.

### Option B: Cloudflare Tunnel (free)

```bash
# Install cloudflared
$ curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
$ chmod +x /usr/local/bin/cloudflared

# Start tunnel
$ cloudflared tunnel --url http://localhost:8777
```

Cloudflared gives you a public URL like `https://random-words.trycloudflare.com`.
Open this on your phone.

### Option C: ngrok

```bash
$ ngrok http 8777
```

Ngrok provides a public URL like `https://abc123.ngrok-free.app`.

> **Important:** When using a tunnel, always enable authentication (bearer
> token) to prevent unauthorized access.

---

## 7. Using a Bookmarklet or Shortcut

### iOS Shortcut

Create a Shortcut that sends a POST request:

1. Open the **Shortcuts** app.
2. Create a new shortcut.
3. Add action: **Get Contents of URL**.
4. Set URL to `http://192.168.1.100:8777/status`.
5. Set Method to `GET`.
6. Add Header: `Authorization: Bearer YOUR_TOKEN`.
7. Add action: **Show Result**.
8. Name it "Research Status" and add it to your home screen.

### Android quick action

Use an app like **HTTP Shortcuts** (free, open source):

1. Install HTTP Shortcuts from the Play Store.
2. Create a new shortcut.
3. Set the URL and method.
4. Add the Authorization header.
5. Place the widget on your home screen.

> **Screenshot:** Phone home screen showing a "Research Status" shortcut widget
> that can be tapped to quickly check project status.

---

## 8. Troubleshooting

### Cannot connect from phone

- Verify your computer and phone are on the same Wi-Fi network
- Check your computer's firewall allows port 8777:
  ```bash
  $ sudo ufw allow 8777/tcp        # Ubuntu
  $ sudo firewall-cmd --add-port=8777/tcp --permanent  # Fedora
  ```
- Verify the server is running: `curl http://localhost:8777/status`

### "unauthorized" response

- Check that you are sending the `Authorization: Bearer TOKEN` header
- Tokens are case-sensitive; copy the exact token
- If the server was restarted, generate a new token

### Slow responses

- The mobile server is single-threaded for simplicity
- If an overnight task is consuming heavy CPU, API responses may be delayed
- The server itself is lightweight; delays usually come from the research tasks

### Phone shows raw JSON

The mobile API returns JSON, not a web page. Options:

1. Use a JSON viewer browser extension on mobile
2. Use a REST client app (e.g., HTTPBot on iOS, REST Client on Android)
3. Build a simple HTML dashboard that fetches from the API (ask Claude to
   generate one)

### Token in URL is not secure

URL parameters can be logged by proxies and appear in browser history. For
better security:

- Use the `Authorization` header instead of URL parameters
- Use HTTPS via a tunnel (Cloudflare/ngrok)
- Revoke tokens when no longer needed

---

**That completes the tutorial series.** You now have all the tools to:

1. Set up credentials and Docker environments
2. Create and manage research projects
3. Write papers with LaTeX, citations, and style analysis
4. Deploy academic websites
5. Run overnight autonomous sessions
6. Monitor everything from your phone

Return to the [Tutorial Index](README.md) at any time.
