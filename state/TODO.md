# TODO

## Under development
- [ ] Reproducibility pipeline (`/reproduce` skill): largely a placeholder — needs real-world testing
      with multi-seed runs, split variation, and subsample sensitivity on actual experiments
- [ ] Manual curation of MD skills: all 8 skills written but need human review and field-testing
      before they can be considered production-quality

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
- [ ] [voice] what is the current status of my project?
- [ ] [voice] Let's test implementing a new function
- [ ] [voice] write an ordinary differential equation system and an integration and make a plot
- [ ] [mobile] update the website
- [ ] [voice] check progress
- [ ] [mobile:proj] run experiments
