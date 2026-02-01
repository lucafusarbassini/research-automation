"""MCP auto-discovery and loading based on task classification."""

import json
import subprocess
from pathlib import Path
from typing import Set

MCP_CONFIG = Path(__file__).parent.parent / "templates/config/mcp-nucleus.json"


def load_mcp_config() -> dict:
    """Load MCP configuration."""
    with open(MCP_CONFIG) as f:
        return json.load(f)


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
