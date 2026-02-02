"""PWA HTML/CSS/JS constants for the mobile companion app.

No imports, no logic — just content strings served by the mobile server.
"""

ICON_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192">
  <rect width="192" height="192" rx="32" fill="#1a1a2e"/>
  <path d="M96 32c-22 0-40 18-40 40v8c-8 0-16 8-16 16v48c0 8 8 16 16 16h80
    c8 0 16-8 16-16V96c0-8-8-16-16-16v-8c0-22-18-40-40-40zm0 16
    c13 0 24 11 24 24v8H72v-8c0-13 11-24 24-24z" fill="#e94560"/>
  <circle cx="96" cy="120" r="12" fill="#fff"/>
</svg>"""

MANIFEST_JSON = """\
{
  "name": "ricet Mobile",
  "short_name": "ricet",
  "description": "Mobile companion for ricet research automation",
  "start_url": "/?source=pwa",
  "display": "standalone",
  "background_color": "#0f0f1a",
  "theme_color": "#e94560",
  "icons": [
    {
      "src": "/icon.svg",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}"""

SERVICE_WORKER_JS = """\
const CACHE_NAME = 'ricet-pwa-v1';
const SHELL_URLS = ['/', '/manifest.json', '/icon.svg'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(SHELL_URLS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(names =>
      Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/project') || url.pathname === '/status'
      || url.pathname === '/voice' || url.pathname === '/task'
      || url.pathname === '/projects' || url.pathname === '/connect-info') {
    e.respondWith(fetch(e.request).catch(() =>
      new Response(JSON.stringify({ok: false, error: 'offline'}),
        {headers: {'Content-Type': 'application/json'}})
    ));
  } else {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
  }
});"""

PWA_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#e94560">
<meta name="apple-mobile-web-app-capable" content="yes">
<title>ricet Mobile</title>
<link rel="manifest" href="/manifest.json">
<link rel="icon" href="/icon.svg" type="image/svg+xml">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0f0f1a;color:#e0e0e0;min-height:100vh;overflow-x:hidden}
.header{background:#1a1a2e;padding:12px 16px;display:flex;align-items:center;
  justify-content:space-between;border-bottom:2px solid #e94560;position:sticky;top:0;z-index:10}
.header h1{font-size:18px;color:#e94560}
.offline-badge{background:#ff4444;color:#fff;font-size:11px;padding:2px 8px;
  border-radius:10px;display:none}
.offline-badge.show{display:inline-block}
.tabs{display:flex;background:#1a1a2e;border-bottom:1px solid #333;position:sticky;top:50px;z-index:9}
.tab{flex:1;padding:12px 8px;text-align:center;font-size:13px;cursor:pointer;
  border-bottom:3px solid transparent;color:#888;min-height:48px;
  display:flex;align-items:center;justify-content:center}
.tab.active{color:#e94560;border-bottom-color:#e94560}
.panel{display:none;padding:16px}
.panel.active{display:block}
.card{background:#1a1a2e;border:1px solid #333;border-radius:12px;padding:16px;
  margin-bottom:12px}
.card h3{color:#e94560;font-size:15px;margin-bottom:8px}
.card .meta{font-size:12px;color:#888}
.card .status{display:inline-block;padding:2px 10px;border-radius:10px;
  font-size:12px;margin-top:6px}
.status.running{background:#1b5e20;color:#a5d6a7}
.status.idle{background:#333;color:#999}
.status.error{background:#b71c1c;color:#ef9a9a}
.progress-bar{height:6px;background:#333;border-radius:3px;margin-top:8px;overflow:hidden}
.progress-fill{height:100%;background:#e94560;border-radius:3px;transition:width .3s}
input,textarea,select{width:100%;padding:14px;background:#1a1a2e;border:1px solid #333;
  border-radius:8px;color:#e0e0e0;font-size:16px;margin-bottom:12px;min-height:48px}
textarea{min-height:100px;resize:vertical}
select{appearance:none;-webkit-appearance:none}
.btn{display:block;width:100%;padding:14px;background:#e94560;color:#fff;border:none;
  border-radius:8px;font-size:16px;font-weight:600;cursor:pointer;min-height:48px;
  margin-bottom:8px}
.btn:active{opacity:.8}
.btn.secondary{background:#333}
.voice-area{text-align:center;padding:32px 16px}
.mic-btn{width:80px;height:80px;border-radius:50%;background:#e94560;border:none;
  cursor:pointer;display:inline-flex;align-items:center;justify-content:center;
  font-size:32px;color:#fff;margin-bottom:16px;transition:all .2s}
.mic-btn.listening{background:#ff1744;animation:pulse 1s infinite}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
.transcript{background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;
  min-height:80px;font-size:15px;text-align:left;margin-bottom:16px}
.info-row{display:flex;justify-content:space-between;padding:10px 0;
  border-bottom:1px solid #222;font-size:14px}
.info-row .label{color:#888}
.info-row .value{color:#e0e0e0;word-break:break-all;text-align:right;max-width:60%}
.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);
  background:#333;color:#fff;padding:10px 24px;border-radius:20px;font-size:14px;
  opacity:0;transition:opacity .3s;z-index:100;pointer-events:none}
.toast.show{opacity:1}
</style>
</head>
<body>
<div class="header">
  <h1>ricet</h1>
  <span class="offline-badge" id="offlineBadge">offline</span>
</div>
<div class="tabs">
  <div class="tab active" data-tab="dashboard">Dashboard</div>
  <div class="tab" data-tab="tasks">Tasks</div>
  <div class="tab" data-tab="voice">Voice</div>
  <div class="tab" data-tab="settings">Settings</div>
</div>

<!-- Dashboard -->
<div class="panel active" id="panel-dashboard">
  <div id="projectList"><div class="card"><div class="meta">Loading projects...</div></div></div>
</div>

<!-- Tasks -->
<div class="panel" id="panel-tasks">
  <select id="projectSelect"><option value="">Select project...</option></select>
  <textarea id="taskInput" placeholder="Describe the task..."></textarea>
  <button class="btn" id="submitTask">Submit Task</button>
  <div id="taskResult"></div>
</div>

<!-- Voice -->
<div class="panel" id="panel-voice">
  <div class="voice-area">
    <button class="mic-btn" id="micBtn">&#x1F3A4;</button>
    <div class="meta" id="voiceStatus">Tap to speak</div>
  </div>
  <div class="transcript" id="transcript"></div>
  <button class="btn" id="sendVoice" disabled>Send as Task</button>
  <select id="voiceProject"><option value="">Select project...</option></select>
</div>

<!-- Settings -->
<div class="panel" id="panel-settings">
  <div class="card">
    <h3>Connection</h3>
    <div class="info-row"><span class="label">Server</span><span class="value" id="infoServer">-</span></div>
    <div class="info-row"><span class="label">Fingerprint</span><span class="value" id="infoFingerprint">-</span></div>
    <div class="info-row"><span class="label">TLS</span><span class="value" id="infoTls">-</span></div>
  </div>
  <div class="card">
    <h3>Token</h3>
    <div class="info-row"><span class="label">Stored</span><span class="value" id="infoToken">-</span></div>
    <button class="btn secondary" id="clearToken">Clear Token</button>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
(function(){
  const TOKEN_KEY = 'ricet_token';

  // Extract token from URL on first load
  const params = new URLSearchParams(location.search);
  if (params.get('token')) {
    localStorage.setItem(TOKEN_KEY, params.get('token'));
    history.replaceState(null, '', '/');
  }

  function getToken() { return localStorage.getItem(TOKEN_KEY) || ''; }

  function toast(msg) {
    const el = document.getElementById('toast');
    el.textContent = msg; el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2500);
  }

  async function api(path, opts) {
    const token = getToken();
    const headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'};
    try {
      const r = await fetch(path, {...opts, headers});
      document.getElementById('offlineBadge').classList.remove('show');
      return await r.json();
    } catch(e) {
      document.getElementById('offlineBadge').classList.add('show');
      return {ok: false, error: 'offline'};
    }
  }

  // Tabs
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
      t.classList.add('active');
      document.getElementById('panel-' + t.dataset.tab).classList.add('active');
    });
  });

  // Dashboard
  async function loadDashboard() {
    const data = await api('/projects');
    const el = document.getElementById('projectList');
    if (!data.ok || !data.projects || data.projects.length === 0) {
      el.innerHTML = '<div class="card"><div class="meta">No projects found</div></div>';
      return;
    }
    el.innerHTML = data.projects.map(p => {
      const pct = p.progress || 0;
      const cls = p.status === 'running' ? 'running' : p.status === 'error' ? 'error' : 'idle';
      return '<div class="card"><h3>' + esc(p.name) + '</h3>'
        + '<span class="status ' + cls + '">' + esc(p.status || 'unknown') + '</span>'
        + '<div class="meta" style="margin-top:8px">' + esc(p.description || '') + '</div>'
        + '<div class="progress-bar"><div class="progress-fill" style="width:' + pct + '%"></div></div>'
        + '<div class="meta" style="margin-top:4px">' + pct + '% complete</div></div>';
    }).join('');
    populateSelects(data.projects);
  }

  function populateSelects(projects) {
    ['projectSelect','voiceProject'].forEach(id => {
      const sel = document.getElementById(id);
      sel.innerHTML = '<option value="">Select project...</option>'
        + projects.map(p => '<option value="' + esc(p.name) + '">' + esc(p.name) + '</option>').join('');
    });
  }

  function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // Tasks
  document.getElementById('submitTask').addEventListener('click', async () => {
    const project = document.getElementById('projectSelect').value;
    const prompt = document.getElementById('taskInput').value.trim();
    if (!prompt) { toast('Enter a task description'); return; }
    const path = project ? '/project/task?name=' + encodeURIComponent(project) : '/task';
    const data = await api(path, {method:'POST', body: JSON.stringify({prompt})});
    if (data.ok) {
      toast('Task queued: ' + (data.task_id || ''));
      document.getElementById('taskInput').value = '';
    } else {
      toast('Error: ' + (data.error || 'unknown'));
    }
  });

  // Voice
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const micBtn = document.getElementById('micBtn');
  const voiceStatus = document.getElementById('voiceStatus');
  const transcriptEl = document.getElementById('transcript');
  const sendVoice = document.getElementById('sendVoice');
  let recognition = null;
  let voiceText = '';

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.onresult = e => {
      voiceText = Array.from(e.results).map(r => r[0].transcript).join('');
      transcriptEl.textContent = voiceText;
      sendVoice.disabled = !voiceText.trim();
    };
    recognition.onend = () => { micBtn.classList.remove('listening'); voiceStatus.textContent = 'Tap to speak'; };
    recognition.onerror = () => { micBtn.classList.remove('listening'); voiceStatus.textContent = 'Error - tap to retry'; };
  } else {
    micBtn.style.opacity = '.3';
    voiceStatus.textContent = 'Speech not supported in this browser';
  }

  micBtn.addEventListener('click', () => {
    if (!recognition) return;
    if (micBtn.classList.contains('listening')) { recognition.stop(); return; }
    voiceText = ''; transcriptEl.textContent = '';
    recognition.start();
    micBtn.classList.add('listening');
    voiceStatus.textContent = 'Listening...';
  });

  sendVoice.addEventListener('click', async () => {
    if (!voiceText.trim()) return;
    const project = document.getElementById('voiceProject').value;
    const path = project ? '/project/task?name=' + encodeURIComponent(project) : '/voice';
    const body = project ? {prompt: voiceText} : {text: voiceText};
    const data = await api(path, {method:'POST', body: JSON.stringify(body)});
    if (data.ok) { toast('Voice task sent'); voiceText = ''; transcriptEl.textContent = ''; sendVoice.disabled = true; }
    else toast('Error: ' + (data.error || 'unknown'));
  });

  // Settings
  async function loadSettings() {
    const data = await api('/connect-info');
    if (data.ok) {
      document.getElementById('infoServer').textContent = data.server || '-';
      document.getElementById('infoFingerprint').textContent = data.fingerprint || 'none';
      document.getElementById('infoTls').textContent = data.tls ? 'enabled' : 'disabled';
    }
    const tok = getToken();
    document.getElementById('infoToken').textContent = tok ? tok.substring(0, 8) + '...' : 'none';
  }

  document.getElementById('clearToken').addEventListener('click', () => {
    localStorage.removeItem(TOKEN_KEY);
    document.getElementById('infoToken').textContent = 'none';
    toast('Token cleared');
  });

  // Init + auto-refresh
  loadDashboard(); loadSettings();
  setInterval(loadDashboard, 30000);

  // Service worker
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
})();
</script>
</body>
</html>"""
