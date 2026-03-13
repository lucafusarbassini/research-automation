# TODO

## Future integrations
- [ ] Integrate context-hub (https://github.com/andrewyng/context-hub) for structured context management
      Generates .context files from repos, docs, URLs — could feed Encyclopedia and cross-project RAG
- [ ] Add notte.cc bridge (https://www.notte.cc/) for browser automation sessions
      Would enable ricet agents to interact with web UIs (Overleaf, dashboards, etc.)
- [ ] Slack file uploads: need SLACK_BOT_TOKEN with files:write scope for automated plot delivery
      Claude connector can send text to #claude_plots but cannot upload images/PDFs
- [ ] Google Drive integration: rclone mount or gdrive CLI for figure export to shared folders
- [ ] Overleaf git sync: `ricet overleaf pull/push` commands for dual-remote workflow

## Paper template
- [ ] Fix supplementary.tex tocloft+authblk conflict (Missing number at \maketitle under tectonic)
      Pre-existing bug in manuscript_lipiddevatlas; main.tex compiles fine.
- [ ] supplementary_figs_tables.tex uses \hl (soul package) but soul is never loaded

- [ ] [voice] what's your name
- [ ] [mobile] what's 3+2?
- [ ] [mobile] what's 3**2?
- [ ] [voice] Joe community
- [ ] [mobile] Implementa una nuova figura
- [ ] [mobile:adopted-math] mmmmm
- [ ] [voice] what's the weather like
- [ ] [mobile] update the website
- [ ] [voice] check progress
- [ ] [mobile:proj] run experiments
- [ ] [mobile] update the website
- [ ] [voice] check progress
- [ ] [mobile:proj] run experiments
- [ ] [mobile] update the website
- [ ] [voice] check progress
- [ ] [mobile:proj] run experiments
