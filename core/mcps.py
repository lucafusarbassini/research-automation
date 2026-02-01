"""MCP auto-discovery and loading based on task classification.

When claude-flow is available, it is injected as a tier-0 MCP.
"""

import json
import subprocess
from pathlib import Path
from typing import Set

from core.claude_flow import ClaudeFlowUnavailable, _get_bridge

MCP_CONFIG = Path(__file__).parent.parent / "templates/config/mcp-nucleus.json"


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
    """Get all MCPs needed for a task."""
    config = load_mcp_config()
    tiers = classify_task(task_description)

    mcps = {}
    for tier in tiers:
        tier_mcps = config.get(tier, {}).get("mcps", {})
        mcps.update(tier_mcps)

    return mcps


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
