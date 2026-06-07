# Reboot survival with systemd

Running ricet on a lab machine that occasionally reboots? Install the
user-level systemd units so `ricet up` comes back for every adopted
project without manual `screen -dmS` rituals.

---

## What you get

Two units, installed under `~/.config/systemd/user/`:

| Unit | Scope | Purpose |
| --- | --- | --- |
| `ricet-mobile.service` | One per machine | Runs `ricet mobile serve` on port `8858` |
| `ricet-up@<project>.service` | One per adopted project | Runs `ricet up --screen <project>` in `~/projects/<project>` |

Both are **user units**, so they don't need root. Both set
`Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin` so that a
pipx-installed `ricet` resolves without a login shell.

---

## Install

Adopt your projects first so they show up in `~/.ricet/projects.json`:

```bash
cd ~/projects/research-automation && ricet adopt
cd ~/projects/mitochondria       && ricet adopt
```

Then install and enable:

```bash
ricet systemd install
```

This copies both templates in, runs `systemctl --user daemon-reload`,
and enables `ricet-mobile.service` plus one `ricet-up@<project>.service`
for every registered project.

### Let units start before you log in

User units only run while you have an active session **unless** you
enable linger:

```bash
sudo loginctl enable-linger $USER
```

With linger on, the units come up at boot, even before SSH login.

### Custom mobile port

```bash
ricet systemd install --mobile-port 9090
```

---

## Directory layout

The project template expects the checkout at `~/projects/<name>`. If
your code lives elsewhere, just symlink:

```bash
mkdir -p ~/projects
ln -s ~/code/research-automation ~/projects/research-automation
```

The instance name (`%i` in `ricet-up@%i.service`) is the project name
exactly as it appears in `~/.ricet/projects.json`.

---

## Verify

```bash
systemctl --user status ricet-mobile
systemctl --user status ricet-up@research-automation
systemctl --user list-units 'ricet-*'
journalctl --user -u ricet-up@research-automation -f
```

Attach to the live screen session the unit started:

```bash
screen -r research-automation
```

---

## Uninstall

```bash
ricet systemd uninstall
```

Disables and removes both units (plus any stale per-project instances).
Linger is left alone; run `sudo loginctl disable-linger $USER` manually
if you want to turn it off.

---

## Troubleshooting

- **`ricet: command not found` in the journal.** pipx installs ricet to
  `~/.local/bin`. The units already put that on `PATH`; if your install
  lives elsewhere, edit `~/.config/systemd/user/ricet-mobile.service`
  and `ricet-up@.service`, then `systemctl --user daemon-reload`.
- **`ricet up` can't find the project directory.** Symlink it under
  `~/projects/<name>` as shown above, or edit `WorkingDirectory` in the
  installed unit file.
- **Docker errors on boot.** The project unit has `After=docker.service`
  but that's the system unit; if your Docker is rootless user-mode,
  add `After=docker.service` under `[Unit]` for the matching user
  service instead.
