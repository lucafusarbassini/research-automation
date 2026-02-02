# Exhaustive Feature Requests — All Chat Sessions

Extracted from **17 chat sessions** (84 user messages, 24 feedback messages read in full without truncation) across `/home/fusar/.claude/projects/` and `archived/`.
Session dates: 2026-02-01 to 2026-02-02

---

## A. Core Application & Architecture (12)

1. Build an app for automating scientific research leveraging Claude Code
2. Build a Visual Studio Code extension for the same
3. Make the tool a pip package for progressive maintenance and distribution
4. Integrate claude-flow library (ruvnet/claude-flow v3) as foundation — replace simpler custom implementations
5. Python bridge wrapping claude-flow CLI calls with graceful fallback to original logic
6. Create cross-repo skeleton files with preconfigured prompts and standardized templates
7. Create a system file containing all technical specifications, prompts, and context-anchoring materials
8. Project configuration template (settings.yml)
9. User constraints template (CONSTRAINTS.md) in knowledge base
10. Self-standing repo: strong README documenting all prerequisites (Docker, GitHub SSH, Claude, etc.)
11. Rename project/package to "ricet" with a hedgehog logo ("supercute face of a hedgehog")
12. README should be user-facing (what to do with the tool) not developer-facing (how to develop it)

## B. Project Initialization & Onboarding (30)

13. Allow users to initialize projects with hyper-detailed descriptions
14. Accept and store API keys during init (GitHub, HuggingFace, W&B, Google/Gemini, Medium, LinkedIn, Slack, SMTP, Google Drive, PubMed, Notion, AWS — all MCPs)
15. Step-by-step API key onboarding guide with how-to URLs, one key at a time
16. Video-based onboarding showing how to obtain each API key end to end
17. Accept GitHub SSH keys only; automate all repo creation under the hood (every project = a repo)
18. Full interactive questionnaire for project onboarding
19. Credential collection and secure storage (secrets/.env and secrets/.env.example)
20. Remove project_type entirely — hardcode to "general", never ask (general-purpose science tool)
21. GOAL.md enforcement: block `ricet start` until GOAL.md has 200+ chars of real content
22. User writes project description in a specific MD file (at least an A4 page, well-detailed)
23. Auto-detect GPU and system hardware — never ask user for GPU name
24. Remove or clarify "success criteria", "target completion date", and "compute resources" prompts
25. Notification method selection during init (email, Slack, none)
26. Target journal or conference selection during init (Nature, Bioinformatics, etc.)
27. Web dashboard option during init
28. Mobile access option during init
29. Guided folder structure with READMEs: reference/papers/, reference/code/, uploads/data/, uploads/personal/
30. Print folder map after init showing where to put things
31. Folder for background knowledge papers with clear upload instructions
32. Folder for useful code to recycle with instructions
33. Folder for personal materials (papers for style impainting, CV, etc.)
34. Comprehensive .gitignore: auto-gitignore heavy files and notify user
35. Doability assessment: check if user prompt is well-defined, ask for more specs only when strictly needed
36. Pre-execution audit: verify uploaded files (papers, code) are in place before proceeding
37. Replace ANTHROPIC_API_KEY with Claude web authentication (`claude auth login`) — no manual API key
38. Remove all "API key required" language from docs; say "authenticate via claude auth login (recommended) or set ANTHROPIC_API_KEY"
39. Automate Claude installation during repo setup; let user connect via web as when first typing "Claude"
40. Automate GitHub CLI (`gh`) installation with under-the-hood checks during setup
41. Automate claude-flow self-install and recognition by ricet
42. Tutorials on how to get all keys so users have a smooth setup experience

## C. Package & Environment Management (10)

43. Create a clean conda environment for each project automatically
44. Discover system specifications and capabilities (OS, Python, GPU, RAM)
45. Generate system.md documentation file with environment details
46. Auto-install required packages at init (typer, rich, pyyaml, python-dotenv)
47. Runtime package auto-install during user work sessions (not just at startup)
48. Autonomous package conflict resolution without bothering the user
49. Goal-aware AI-driven package detection: Claude API call to analyze GOAL.md and infer needed pip packages (e.g., niche domains like spatial metabolomics)
50. Replace ALL hardcoded logic with Claude AI calls (not just packages)
51. Agent should handle install failures automatically
52. Docker sandbox environment setup and configuration

## D. Multi-Model Routing & AI (10)

53. Multi-model routing: Google (Gemini), Anthropic (Claude), and any other providers
54. Leverage cheaper models where possible (e.g., Gemini for literature review/paper scanning)
55. Use Claude for writing and critical tasks
56. Use fine-tuned models for special tasks
57. 3-tier model routing (haiku/sonnet/opus) via claude-flow
58. Cross-provider fallback when primary model fails
59. Classify task complexity automatically to decide model
60. Token optimization and context management/compaction
61. "Ultrathink / think hard" auto-selection rules by task type
62. Background philosophy: "AI context is like milk; it's best served fresh and condensed!"

## E. Voice Input Pipeline (4)

63. Voice input capability for project descriptions
64. Transcribe audio using Whisper
65. Detect language and translate non-English to English
66. Structure voice-based natural language into formal prompts

## F. Agent Orchestration & Swarm (11)

67. 60+ specialized agents from claude-flow (not simpler custom ones)
68. Swarm orchestration for parallel task execution
69. Intelligent agent spawning (30-40 concurrent agents) with isolation
70. Task dataclass, build task DAG (dependency graph)
71. Execute tasks in parallel where dependencies allow
72. Plan-execute-iterate loop for complex workflows
73. Get active agents status in real-time
74. Dynamic prompt queue: let user queue unlimited prompts, dispatch across subagents dynamically as prompts complete, no memory losses
75. HNSW vector memory for knowledge management (from claude-flow)
76. Session management with persistent sessions and recovery
77. Background philosophy: "Break down large problems into smaller ones" always applied under the hood

## G. Autonomous Execution & Overnight (10)

78. Accept a "start" command and begin autonomous work
79. Allow agent to work while user is away (overnight runs)
80. Maintain awareness of constraints during long overnight runs — never go off track
81. Develop projects iteratively through any number of Claude calls
82. Auto-debug loop: autonomously handle errors, follow protocol, only ask user after repeated failures
83. Automatic error detection in code execution
84. Safe overnight sandbox execution in Docker containers
85. Automate mounting of ~/.claude/ directory into Docker containers (no API key needed in Docker)
86. Overnight result reporting: send Slack/email notifications with summary when overnight completes
87. Write overnight results to state/PROGRESS.md

## H. Reproducibility & Resources (5)

88. RunLog for tracking experiment runs (metadata, parameters)
89. ArtifactRegistry for managing generated files and outputs
90. Compute dataset hash for reproducibility verification
91. Monitor system resources (CPU, memory, disk, GPU)
92. Checkpoint policy: save experiment state, cleanup old checkpoints, resource-based decisions

## I. Literature & Knowledge (3)

93. Web search integration via browser automation
94. Academic paper search functionality
95. Literature review pipeline automation

## J. Two-Repo Structure & Git (5)

96. Two-repo structure: experiments (messy) vs clean (polished)
97. Git worktrees for the two-repo approach
98. Use git worktrees for parallel branch work to avoid subagent collisions
99. Only push working, relevant, polished code to the clean repo
100. Multi-repo synchronization and cross-repo coordination

## K. Dashboard & Monitoring (5)

101. TUI (Text User Interface) dashboard showing agent activity
102. Dashboard with agents panel (active/completed tasks)
103. Dashboard with resource monitoring display
104. Figure gallery for browsing generated visualizations
105. Live status assessment and monitoring (from mobile too)

## L. Prompt & Command System (4)

106. Prompt suggestions / predictive follow-ups when Claude finishes a task
107. Execute markdown files from knowledge folder as instruction sets
108. Task spooler (ts/tsp) integration for job queuing
109. Full session recovery from crashed or completed tasks

## M. MCP Ecosystem (10)

110. Core MCP nucleus with tiered lazy-loading (tier0 always → tier8 marketing)
111. Lazy-load MCP tools to save context
112. Apidog MCP Server integration
113. Sequential Thinking MCP Server integration
114. Puppeteer MCP Server integration
115. Prepare a RAG index of awesome-mcp-servers to discover MCPs based on need
116. Integrate awesome-claude-code (hesreallyhim/awesome-claude-code)
117. Integrate Daft (Eventual-Inc/Daft) for data processing
118. Scrutinize ruvnet repos for extras and embed into workflows
119. Claude Code as a DevOps engineer — DevOps capabilities baked in

## N. GitHub Integration (5)

120. GitHub Actions workflows for CI/CD
121. GitHub repo creation for each project (automated)
122. GitHub Pages for documentation (replacing ReadTheDocs)
123. Fix and maintain CI badges and demo badges on homepage
124. PyPI badges on documentation

## O. Publishing & Social Media (7)

125. Create a website ready to be published for each project
126. Create a newsletter for each project
127. Post to LinkedIn automatically with quality check via Claude
128. Post to Medium automatically with quality check via Claude
129. Generate social media content from the project
130. Email notification capability
131. Slack integration capability

## P. Templates & Paper Writing (6)

132. Paper writing core functionality
133. Journal template support (Nature, Bioinformatics, etc.) — professionally looking templates
134. Accept example paper PDFs in templates/paper/journals/
135. LaTeX integration (potentially with Overleaf)
136. Website generation functionality
137. Update website by just asking what you want and let it iterate autonomously

## Q. Mobile & Multi-Project (5)

138. Mobile phone control (/mobile command)
139. Simultaneous multi-project handling
140. Mobile project management and status monitoring
141. Browser integration for web resources
142. Update website from mobile — "I want to be able to update my website by just asking"

## R. Security (3)

143. Enforce repository root validation
144. Scan codebase for secrets and credentials before operations
145. Protect immutable files from accidental modification

## S. Testing & Quality (12)

146. TDD approach: write tests progressively during development
147. Backend should autonomously write tests to keep code checked
148. Complete write-test cycle for all autonomous tasks
149. Comprehensive end-to-end demo/tutorial testing 100% of functions
150. Demo/tutorial should be part of the package and well-documented
151. Test in Docker sandboxes
152. Replace fake README demo with real documented end-to-end scientific workflow
153. Half-baked feature detection: automated check for fragile or trivial implementations
154. Unbiased weakness detection by fresh agents with no context
155. Hardcoded parameter audit (e.g., token maxcap, default values)
156. Automatic "double check everything" verification: every claim verified with a verification table, even when user doesn't ask
157. Keep CLAUDE.md simple and review it periodically (agent should do this) — prevent overcomplication bias

## T. Collaboration & Cross-Repo Awareness (4)

158. Transform existing GitHub repos to Ricet projects with safe backup (fork intact)
159. Support collaborative repos with multiple users
160. Support collaborative research where both users use Ricet
161. Link user's public/private repos for RAG by ricet agents — user-wide code awareness while restricting edits to the active project

## U. UX Philosophy (6)

162. Assume users will read NOTHING — everything must be self-standing and autonomous
163. All complexity under the hood; user experience must be super simple
164. Even very bad voice messages should be deliverable thanks to the system's massive prior
165. Auto-commit and push every operation performed by the ricet machinery
166. Real user testing workflow: "tell me precisely what to run, I run slowly and observe"
167. `ricet start` must leverage the full built system, not just wrap around bare Claude Code

## V. Documentation & Transparency (5)

168. Build log document (Luca/Claude Q&A format) showing how each feature was solved
169. Archive chat transcripts in repo for full transparency on how tool was built
170. Recognize in README the repos used to build the product (claude-flow, ruvnet, etc.)
171. Comprehensive testing guide for all functionalities (API keys, voice, MCPs, etc.)
172. "Features vs reality" audit document: for each feature, honestly report implementation status

## W. Bugs & Fixes Reported During Live Testing (8)

173. `ricet start` session ID format bug: UUID required but timestamp generated
174. `ricet agents` says "claude-flow not available" even after install — fix wiring
175. `ricet verify` returns trivially wrong results — needs real verification logic
176. `ricet memory` returns "no matches" — needs actual knowledge indexing
177. `ricet projects list` shows "no projects registered" after init — fix registration
178. Tests directory not created in user projects — tests should be scaffolded
179. GitHub Pages not deploying despite push — fix deployment workflow
180. GitHub Actions CI failing — fix workflow configuration

---

**Total: 180 unique feature requests across 17 chat sessions**

*Revision 2: Re-read all 24 feedback messages in full (no truncation). Added 33 items previously missed from truncated messages, notably: MCP ecosystem details (Apidog, Sequential Thinking, Puppeteer, awesome-mcp-servers RAG), specific integrations (Daft, awesome-claude-code), branding (hedgehog logo, rename to ricet), quality philosophy (auto-verification, CLAUDE.md simplicity), live testing bugs, and UX refinements.*
