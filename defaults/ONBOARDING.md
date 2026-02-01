# User Onboarding Questions

When a user runs `research init <project-name>`, the tool asks these questions interactively.

---

## REQUIRED (Must Answer)

### 1. Project Goal
**Prompt**: "What is the main goal of this project? (one sentence)"
**Example**: "Predict protein structures from sequence using deep learning"
**Stored in**: `knowledge/GOAL.md`

### 2. Project Type
**Prompt**: "What type of project is this?"
**Options**: 
- `ml-research` (default) - Machine learning/deep learning research
- `data-analysis` - Data analysis and visualization
- `paper-writing` - Writing a scientific paper
- `computational` - Computational science (simulations, etc.)
- `general` - General research

**Effect**: Determines which MCP tiers to pre-load

### 3. GitHub Repository
**Prompt**: "GitHub repository URL (or 'skip' to create later)"
**Example**: "https://github.com/username/project"
**Stored in**: `.git/config`

---

## RECOMMENDED (Can Skip)

### 4. Success Criteria
**Prompt**: "What would make this project successful? (2-3 criteria)"
**Example**: 
- "Achieve >90% accuracy on benchmark"
- "Submit paper to NeurIPS"
**Stored in**: `knowledge/GOAL.md`

### 5. Timeline
**Prompt**: "Target completion date (or 'flexible')"
**Example**: "2024-06-01"
**Stored in**: `knowledge/GOAL.md`

### 6. Compute Resources
**Prompt**: "What compute resources do you have?"
**Options**:
- `local-cpu` - Local CPU only
- `local-gpu` - Local GPU (will ask which)
- `cloud` - Cloud compute (AWS, GCP, etc.)
- `cluster` - HPC cluster
**Stored in**: `knowledge/MACHINES.md`

### 7. Notification Preferences
**Prompt**: "How should I notify you of important events?"
**Options**:
- `email` - Email notifications
- `slack` - Slack messages
- `none` - No notifications (check manually)
**Stored in**: `config/settings.yml`

---

## CREDENTIALS (Asked as needed)

The tool asks for credentials only when needed based on project type and user choices.

### Always Asked
- `GITHUB_TOKEN` - For repository operations

### Asked if ML Research
- `HUGGINGFACE_TOKEN` - For HuggingFace Hub
- `WANDB_API_KEY` or `MLFLOW_TRACKING_URI` - For experiment tracking

### Asked if Notifications Enabled
- `SENDGRID_API_KEY` or `GMAIL_APP_PASSWORD` - For email
- `SLACK_WEBHOOK_URL` - For Slack

### Asked if Cloud Compute
- `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` - For AWS
- `GOOGLE_CLOUD_CREDENTIALS` - For GCP

### Asked for Paper Writing
- `SEMANTIC_SCHOLAR_API_KEY` - For literature search (optional, works without)

---

## POST-INIT UPLOADS

After initialization, the tool prompts:

### Reference Papers
**Prompt**: "Do you have reference papers to upload? (y/n)"
**If yes**: Opens file picker or asks for path
**Stored in**: `reference/papers/`

### Reference Code
**Prompt**: "Do you have existing code to reference? (y/n)"
**If yes**: Opens file picker or asks for path
**Stored in**: `reference/code/`

### Custom Rules
**Prompt**: "Do you have specific rules for this project? (y/n)"
**If yes**: Opens editor for `knowledge/CONSTRAINTS.md`

---

## DEFAULT VALUES

If user skips or presses Enter:

| Question | Default |
|----------|---------|
| Project Type | `ml-research` |
| Timeline | `flexible` |
| Compute | `local-gpu` (if detected) else `local-cpu` |
| Notifications | `none` |

---

## STORED CONFIGURATION

After onboarding, configuration is stored in:

```yaml
# config/settings.yml
project:
  name: "my-project"
  type: "ml-research"
  created: "2024-01-15T10:30:00Z"

compute:
  type: "local-gpu"
  gpu: "NVIDIA RTX 4090"

notifications:
  enabled: true
  method: "email"
  email: "user@example.com"
  
credentials:
  # References to .env file, not actual values
  github: "${GITHUB_TOKEN}"
  huggingface: "${HUGGINGFACE_TOKEN}"
```

---

## RE-CONFIGURATION

Users can re-run onboarding with:
```bash
research config
```

Or edit specific settings:
```bash
research config --notifications
research config --compute
research config --credentials
```
