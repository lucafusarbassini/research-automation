"""MCP auto-discovery and loading based on task classification.

When claude-flow is available, it is injected as a tier-0 MCP.
When the pre-configured tiers don't cover a need, Claude searches the
full MCP catalogs (``defaults/MCP_CATALOG.md`` and
``defaults/raggable_mcps.md``) and suggests an install.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Set

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

logger = logging.getLogger(__name__)

MCP_CONFIG = Path(__file__).parent.parent / "templates/config/mcp-nucleus.json"
MCP_CATALOG = Path(__file__).parent.parent / "defaults" / "MCP_CATALOG.md"
RAGGABLE_CATALOG = Path(__file__).parent.parent / "defaults" / "raggable_mcps.md"


def load_mcp_config() -> dict:
    """Load MCP configuration."""
    with open(MCP_CONFIG) as f:
        return json.load(f)


def get_claude_flow_mcp_config() -> dict:
    """Return claude-flow as a tier-0 MCP config entry.

    Returns:
        Dict suitable for injection into the MCP config, or empty dict
        if claude-flow is not available.
    """
    try:
        bridge = _get_bridge()
        return {
            "tier0_claude_flow": {
                "description": "Claude-flow swarm orchestration, vector memory, 3-tier routing",
                "mcps": {
                    "claude-flow": {
                        "command": "npx",
                        "args": ["claude-flow@v3alpha", "mcp", "serve"],
                    }
                },
                "trigger_keywords": [],  # Always loaded
            }
        }
    except ClaudeFlowUnavailable:
        return {}


def classify_task(task_description: str) -> Set[str]:
    """Determine which MCP tiers to load based on task keywords."""
    config = load_mcp_config()
    task_lower = task_description.lower()

    tiers_to_load = {"tier1_essential"}  # Always load tier 1

    for tier_name, tier_config in config.items():
        if tier_name == "tier1_essential":
            continue
        keywords = tier_config.get("trigger_keywords", [])
        if any(kw in task_lower for kw in keywords):
            tiers_to_load.add(tier_name)

    return tiers_to_load


def get_mcps_for_task(task_description: str) -> dict:
    """Get all MCPs needed for a task.

    MCPs are registered through LazyMCPLoader so they are tracked but not
    fully loaded until explicitly requested.  The returned dict still
    contains the same MCP configs for backward compatibility.
    """
    from core.lazy_mcp import LazyMCPLoader

    config = load_mcp_config()
    tiers = classify_task(task_description)

    mcps = {}
    for tier in tiers:
        tier_mcps = config.get(tier, {}).get("mcps", {})
        mcps.update(tier_mcps)

    # Register discovered MCPs through LazyMCPLoader for deferred loading.
    # The loader is instantiated per-call; a module-level singleton could be
    # used if cross-call state is needed later.
    lazy = LazyMCPLoader()
    for tier_name in tiers:
        tier_cfg = config.get(tier_name, {})
        tier_num = _tier_name_to_num(tier_name)
        keywords = tier_cfg.get("trigger_keywords", [])
        for mcp_name, mcp_cfg in tier_cfg.get("mcps", {}).items():
            lazy.register_mcp(
                name=mcp_name,
                config=mcp_cfg,
                tier=tier_num,
                trigger_keywords=keywords,
            )

    # Only load MCPs that the lazy loader considers needed for this task.
    needed = lazy.get_needed_mcps(task_description)
    for name in needed:
        lazy.load_mcp(name)

    return mcps


def _tier_name_to_num(tier_name: str) -> int:
    """Convert a tier config key like 'tier2_research' to its numeric tier."""
    import re as _re

    m = _re.match(r"tier(\d+)", tier_name)
    return int(m.group(1)) if m else 1


def get_priority_mcps() -> dict:
    """Return the always-needed (tier-0) MCP servers.

    These are loaded unconditionally regardless of task classification.
    Sequential-thinking is tier-0 because structured reasoning is
    fundamental to every research workflow.
    """
    priority: dict = {
        "sequential-thinking": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
            "purpose": "Structured reasoning chains for complex analysis",
            "tier": 0,
        },
    }

    # Merge claude-flow if available
    cf_config = get_claude_flow_mcp_config()
    if cf_config:
        cf_mcps = cf_config["tier0_claude_flow"]["mcps"]
        for name, entry in cf_mcps.items():
            priority[name] = {**entry, "tier": 0}

    return priority


def install_priority_mcps() -> dict[str, bool]:
    """Install all tier-0 priority MCP servers.

    Returns:
        Mapping of MCP name -> success boolean.
    """
    results: dict[str, bool] = {}
    for name, cfg in get_priority_mcps().items():
        source = cfg.get("source", "")
        if not source:
            # For npx-based MCPs, attempt a dry-run to verify availability
            cmd_parts = cfg.get("args", [])
            pkg = next((a for a in cmd_parts if not a.startswith("-")), None)
            if pkg:
                source = pkg
            else:
                results[name] = True  # nothing to install for npx
                continue
        results[name] = install_mcp(name, source)
    return results


def install_mcp(mcp_name: str, source: str) -> bool:
    """Install an MCP from source."""
    if "github.com" in source or "/" in source:
        cmd = f"npx -y @anthropic-ai/mcp-installer install {source}"
    else:
        cmd = f"npm install -g {source}"

    try:
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


# ---------------------------------------------------------------------------
# Claude-powered MCP catalog discovery
# ---------------------------------------------------------------------------


def search_mcp_catalog(need: str, *, run_cmd=None) -> dict | None:
    """Search the MCP catalogs for a server matching *need* using Claude.

    Reads ``defaults/MCP_CATALOG.md`` (a curated tier list) and
    ``defaults/raggable_mcps.md`` (a comprehensive 1 300+ server catalog)
    and asks Claude to pick the best match, the install command, and what
    API keys (if any) the user must provide.

    Args:
        need: Natural-language description of what the user needs
              (e.g. "access PubMed papers" or "send Slack messages").
        run_cmd: Optional callable for testing.

    Returns:
        Dict with ``name``, ``repo``, ``install_cmd``, ``needs_key``,
        ``key_instructions`` on success; ``None`` when no match is found
        or Claude is unavailable.
    """
    from core.claude_helper import call_claude_json

    # Build combined catalog from both sources.
    catalog_parts: list[str] = []
    if MCP_CATALOG.exists():
        catalog_parts.append(MCP_CATALOG.read_text())
    if RAGGABLE_CATALOG.exists():
        catalog_parts.append(RAGGABLE_CATALOG.read_text())

    if not catalog_parts:
        logger.warning(
            "No MCP catalogs found at %s or %s", MCP_CATALOG, RAGGABLE_CATALOG
        )
        return None

    catalog_text = "\n\n".join(catalog_parts)

    prompt = (
        "You are an MCP server expert. The user needs an MCP server for:\n\n"
        f'  "{need}"\n\n'
        "Below is a catalog of available MCP servers. Pick the BEST match.\n"
        "Reply with a JSON object (no markdown fences):\n"
        '{"name": "server-name", "repo": "owner/repo or npm package", '
        '"install_cmd": "npm install command or npx command", '
        '"needs_key": true/false, '
        '"key_name": "ENV_VAR name if needed", '
        '"key_instructions": "1-2 sentence instructions for getting the key"}\n'
        'If no good match exists, reply: {"name": null}\n\n'
        "--- CATALOG ---\n"
        f"{catalog_text}"
    )

    result = call_claude_json(prompt, run_cmd=run_cmd)
    if result and isinstance(result, dict) and result.get("name"):
        return result

    # Fallback: if Claude is unavailable, use MCPIndex keyword search
    # over both the hardcoded defaults and the parsed raggable catalog.
    try:
        from core.rag_mcp import DEFAULT_ENTRIES, MCPIndex, parse_raggable_catalog

        entries = list(DEFAULT_ENTRIES)
        entries.extend(parse_raggable_catalog())

        index = MCPIndex()
        index.build_index(entries)
        hits = index.search(need, top_k=1)
        if hits:
            entry = hits[0]
            return {
                "name": entry.name,
                "repo": entry.url,
                "install_cmd": entry.install_command,
                "needs_key": bool(entry.config_template.get("env")),
                "key_name": next(iter(entry.config_template.get("env", {})), ""),
                "key_instructions": "",
            }
    except Exception:
        logger.debug("rag_mcp fallback failed", exc_info=True)

    return None


def suggest_and_install_mcp(
    need: str,
    *,
    auto_install: bool = False,
    prompt_fn=None,
    print_fn=None,
    run_cmd=None,
) -> bool:
    """Search the catalog, suggest an MCP, optionally install it.

    This is the main entry point for "I need an MCP but don't know which".
    Claude searches the catalog, explains the match, and if API keys are
    required, tells the user exactly how to obtain them.

    Args:
        need: What the user needs (natural language).
        auto_install: If True, install without asking. If False, ask first.
        prompt_fn: Callable(question, default) for user input.
        print_fn: Callable(message) for output.
        run_cmd: Optional callable for testing subprocess calls.

    Returns:
        True if an MCP was installed, False otherwise.
    """
    _print = print_fn or (lambda msg: None)
    _prompt = prompt_fn

    match = search_mcp_catalog(need, run_cmd=run_cmd)
    if not match:
        _print(f"No MCP server found for: {need}")
        return False

    name = match["name"]
    install_cmd = match.get("install_cmd", "")
    needs_key = match.get("needs_key", False)
    key_name = match.get("key_name", "")
    key_instructions = match.get("key_instructions", "")

    _print(f"Found MCP: {name}")
    if match.get("repo"):
        _print(f"  Source: {match['repo']}")
    if install_cmd:
        _print(f"  Install: {install_cmd}")

    if needs_key:
        _print(f"  Requires API key: {key_name}")
        _print(f"  How to get it: {key_instructions}")
        if _prompt:
            key_value = _prompt(f"Enter {key_name} (or press Enter to skip)", "")
            if key_value:
                # Append to .env
                env_path = Path.cwd() / ".env"
                with open(env_path, "a") as f:
                    f.write(f"\n{key_name}={key_value}\n")
                _print(f"  Saved {key_name} to .env")

    if not install_cmd:
        return False

    if not auto_install and _prompt:
        confirm = _prompt(f"Install {name}? (yes/no)", "yes")
        if confirm.lower() not in ("yes", "y"):
            return False

    # Install
    _run = run_cmd or (lambda cmd: subprocess.run(cmd, shell=True, check=True))
    try:
        _run(install_cmd)
        _print(f"  Installed {name}")
        return True
    except (subprocess.CalledProcessError, Exception) as exc:
        _print(f"  Install failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# MCP scaffold generation
# ---------------------------------------------------------------------------


def create_mcp_scaffold(
    name: str,
    description: str,
    tools: list[str],
    output_dir: Path | None = None,
    *,
    run_cmd=None,
) -> Path | None:
    """Generate a new MCP server scaffold using Claude.

    Creates a minimal MCP server with the specified tools.

    Args:
        name: Server name (e.g., "my-data-mcp")
        description: What the MCP does
        tools: List of tool names to implement (e.g., ["search", "fetch", "parse"])
        output_dir: Where to create the scaffold (default: current dir)

    Returns path to created directory, or None on failure.
    """
    from core.claude_helper import call_claude

    if output_dir is None:
        output_dir = Path.cwd()

    mcp_dir = output_dir / name
    mcp_dir.mkdir(parents=True, exist_ok=True)

    tools_str = ", ".join(tools)
    prompt = (
        f"Generate a minimal MCP (Model Context Protocol) server in TypeScript.\n"
        f"Server name: {name}\n"
        f"Description: {description}\n"
        f"Tools to implement: {tools_str}\n\n"
        "Generate the following files:\n"
        "1. package.json with @modelcontextprotocol/sdk dependency\n"
        "2. src/index.ts with the MCP server implementation\n"
        "3. tsconfig.json\n\n"
        "Output ONLY the file contents separated by '=== FILENAME ===' markers.\n"
        "Example:\n"
        "=== package.json ===\n{...}\n"
        "=== src/index.ts ===\n...\n"
        "=== tsconfig.json ===\n...\n"
    )

    result = call_claude(prompt, run_cmd=run_cmd)
    if not result:
        return None

    # Parse the output into files
    current_file = None
    current_content: list[str] = []

    for line in result.splitlines():
        if line.startswith("=== ") and line.endswith(" ==="):
            if current_file and current_content:
                file_path = mcp_dir / current_file
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("\n".join(current_content))
            current_file = line[4:-4].strip()
            current_content = []
        else:
            current_content.append(line)

    # Write last file
    if current_file and current_content:
        file_path = mcp_dir / current_file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("\n".join(current_content))

    return mcp_dir


# ---------------------------------------------------------------------------
# Zapier MCP integration
# ---------------------------------------------------------------------------


def setup_zapier_mcp(*, api_key: str = "", run_cmd=None) -> bool:
    """Configure the Zapier MCP for workflow automation.

    Zapier MCP allows ricet to trigger Zapier zaps (e.g., send to Slack,
    update spreadsheets, trigger webhooks) via the MCP protocol.

    Args:
        api_key: Zapier NLA API key. Falls back to ZAPIER_NLA_API_KEY env var.
        run_cmd: Optional callable for testing.

    Returns:
        True if the Zapier MCP was successfully configured.
    """
    import os

    if not api_key:
        api_key = os.environ.get("ZAPIER_NLA_API_KEY", "")

    if not api_key:
        return False

    # Add Zapier to the project's MCP config
    zapier_config = {
        "zapier-mcp": {
            "command": "npx",
            "args": ["-y", "zapier-mcp-server"],
            "env": {"ZAPIER_NLA_API_KEY": api_key},
            "purpose": "Zapier workflow automation (triggers, webhooks, integrations)",
        }
    }

    # Write to project's .claude/settings.json or mcp config
    settings_path = Path.cwd() / ".claude" / "settings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        if "mcpServers" not in settings:
            settings["mcpServers"] = {}
        settings["mcpServers"].update(zapier_config)
        settings_path.write_text(json.dumps(settings, indent=2))
        return True

    # Fallback: create .claude/settings.json if .claude dir exists
    claude_dir = Path.cwd() / ".claude"
    if claude_dir.is_dir():
        settings = {"mcpServers": zapier_config}
        settings_path.write_text(json.dumps(settings, indent=2))
        return True

    return False
