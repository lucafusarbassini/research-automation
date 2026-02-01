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
