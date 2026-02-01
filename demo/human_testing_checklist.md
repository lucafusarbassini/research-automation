# Human Testing Checklist

These features require human interaction and cannot be fully automated.
Complete them after the automated demo passes.

## Voice Prompting (Phase 3)

- [ ] **Record voice memo in English** — Use phone's voice recorder. Save as `.wav` or `.m4a`.
- [ ] **Record voice memo in your mother tongue** — Say something like "I want to train a neural network on my dataset and write a paper about the results."
- [ ] **Transcription accuracy** — Run `core.voice.transcribe_audio(path)` if Whisper is installed. Check the transcript matches what you said.
- [ ] **Language detection** — Run `core.voice.detect_language(transcript)`. Verify it returns the correct language code.
- [ ] **Prompt structuring** — Run `core.voice.structure_prompt(transcript)`. Verify the output is a clean, structured English prompt.

## Mobile Access (Phase 3)

- [ ] **Start mobile server** — Run `ricet mobile start` or `python -c "from core.mobile import start_server; start_server()"`.
- [ ] **Connect from phone** — Open `http://<your-ip>:8777/progress` in your phone's browser. Should return JSON.
- [ ] **Submit task from phone** — POST to `http://<your-ip>:8777/task` with `{"task": "check status"}`.
- [ ] **Auth token flow** — Generate a token, add it as `Authorization: Bearer <token>` header, verify it works.
- [ ] **Voice command from phone** — POST to `http://<your-ip>:8777/voice` with `{"text": "run the tests"}`.

## Social Media (Phase 6)

- [ ] **Publish to Medium** — Set `MEDIUM_TOKEN` in `.env`, run `ricet publish medium`. Verify the post appears on Medium.
- [ ] **Publish to LinkedIn** — Set `LINKEDIN_TOKEN` in `.env`, run `ricet publish linkedin`. Verify the post appears.

## Notifications (Phase 6)

- [ ] **Slack notification** — Set `SLACK_WEBHOOK_URL` in `.env`. Trigger a notification. Check Slack channel.
- [ ] **Email notification** — Configure SMTP settings. Trigger. Check inbox.
- [ ] **Desktop notification** — Run on a machine with a desktop. Trigger. See popup.

## Overnight Mode (Phase 4)

- [ ] **Full overnight run** — Set `ANTHROPIC_API_KEY`. Create a TODO.md with 3 tasks. Run `ricet overnight state/TODO.md`. Monitor with `ricet status`. Check results next morning.

## Paper Pipeline (Phase 5)

- [ ] **LaTeX compilation** — Install texlive. Place a paper in `paper/`. Run `ricet paper build`. Check PDF output.
- [ ] **Nature template** — Download Nature LaTeX template files (`.cls`, `.bst`). Place in `templates/paper/journals/nature/`. Run `ricet paper build --journal nature`.

## Docker (Phase 9)

- [ ] **Docker build** — Run `docker compose -f docker/docker-compose.yml build`. Should complete without errors.
- [ ] **Docker web terminal** — Run `docker compose -f docker/docker-compose.yml up`. Open `http://localhost:7681`.
- [ ] **Docker demo** — Run `bash demo/scripts/run_in_docker.sh`. All tests should pass inside container.

## Website (Phase 6)

- [ ] **GitHub Pages** — Push changes. Go to repo Settings > Pages. Enable deploy from Actions. Check `https://lucafusarbassini.github.io/research-automation/`.
- [ ] **Custom domain** — (Optional) Configure CNAME if desired.

## Multi-Project (Phase 7)

- [ ] **Register 2 real projects** — Run `ricet projects register` twice with different paths.
- [ ] **Switch between them** — Run `ricet projects switch <name>`.
- [ ] **Sync knowledge** — After both projects have encyclopedia entries, verify sync works.
