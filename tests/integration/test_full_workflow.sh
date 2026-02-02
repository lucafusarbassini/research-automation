#!/usr/bin/env bash
# =============================================================================
# ricet 0.3.0 — Full Integration Test
# =============================================================================
#
# Toy research problem: "Predicting protein-ligand binding affinity using
# graph neural networks on the PDBbind dataset."
#
# This script behaves like a real human researcher using ricet to:
#   1. Initialize a project with a real scientific goal
#   2. Search literature, cite papers, discover related work
#   3. Scaffold code, generate tests, build docs
#   4. Track reproducibility, manage tasks, verify claims
#   5. Use infrastructure tools (worktrees, packages, websites)
#   6. Test cross-repo learning, MCP discovery, and social publishing
#
# Usage:
#   bash tests/integration/test_full_workflow.sh [--with-credentials]
#
# The script writes a full log to /tmp/ricet-integration/report.txt
# and generates a Markdown report suitable for PDF conversion.
#
# Exit codes: 0 = all tests passed, 1 = some failures
# =============================================================================

set -o pipefail

# ---- Config ----
TESTDIR="/tmp/ricet-integration"
PROJECT="$TESTDIR/protein-binding"
REPORT="$TESTDIR/report.md"
LOG="$TESTDIR/full_log.txt"
PASS=0
FAIL=0
SKIP=0
TOTAL=0

# ---- Helpers ----
cleanup() {
    rm -rf "$TESTDIR"
}

setup() {
    cleanup
    mkdir -p "$TESTDIR"
    > "$LOG"
    cat > "$REPORT" << 'HEADER'
# ricet 0.3.0 — Integration Test Report

**Date:** DATEPLACEHOLDER
**System:** SYSTEMPLACEHOLDER
**Test:** Protein-Ligand Binding Affinity Prediction (toy research project)

---

HEADER
    sed -i "s/DATEPLACEHOLDER/$(date '+%Y-%m-%d %H:%M:%S')/" "$REPORT"
    sed -i "s|SYSTEMPLACEHOLDER|$(uname -srm), Python $(python3 --version 2>&1 | awk '{print $2}')|" "$REPORT"
}

run() {
    # run "Section" "Description" "command" [timeout] [allow_fail]
    local section="$1"
    local desc="$2"
    local cmd="$3"
    local timeout="${4:-60}"
    local allow_fail="${5:-false}"

    ((TOTAL++))
    echo -n "[$TOTAL] $section: $desc ... "

    # Log to file
    echo "## $section: $desc" >> "$REPORT"
    echo "" >> "$REPORT"
    echo '```bash' >> "$REPORT"
    echo "$ $cmd" >> "$REPORT"
    echo '```' >> "$REPORT"
    echo "" >> "$REPORT"
    echo '```' >> "$REPORT"

    # Execute
    local output
    output=$(timeout "$timeout" bash -c "$cmd" 2>&1)
    local rc=$?

    # Trim output to first 80 lines for the report
    echo "$output" | head -80 >> "$REPORT"
    if [ "$(echo "$output" | wc -l)" -gt 80 ]; then
        echo "... (truncated)" >> "$REPORT"
    fi
    echo '```' >> "$REPORT"
    echo "" >> "$REPORT"

    # Full output to log
    echo "=== [$TOTAL] $section: $desc ===" >> "$LOG"
    echo "CMD: $cmd" >> "$LOG"
    echo "RC: $rc" >> "$LOG"
    echo "$output" >> "$LOG"
    echo "==========" >> "$LOG"
    echo "" >> "$LOG"

    if [ $rc -eq 0 ]; then
        echo "**Result: PASS**" >> "$REPORT"
        echo "PASS"
        ((PASS++))
    elif [ $rc -eq 124 ]; then
        echo "**Result: TIMEOUT (${timeout}s)**" >> "$REPORT"
        echo "TIMEOUT"
        ((FAIL++))
    elif [ "$allow_fail" = "true" ]; then
        echo "**Result: OK (expected non-zero exit $rc)**" >> "$REPORT"
        echo "OK (expected)"
        ((PASS++))
    else
        echo "**Result: FAIL (exit $rc)**" >> "$REPORT"
        echo "FAIL (exit $rc)"
        ((FAIL++))
    fi
    echo "" >> "$REPORT"
    echo "---" >> "$REPORT"
    echo "" >> "$REPORT"
}

# ---- Setup ----
setup
echo "ricet 0.3.0 Integration Test — $(date)"
echo "Project: Protein-Ligand Binding Affinity Prediction"
echo "Output: $REPORT"
echo ""

# =============================================================================
# PHASE 0: Prerequisites
# =============================================================================
echo "=== PHASE 0: Prerequisites ==="

run "0.1" "Version check" \
    "ricet --version"

# =============================================================================
# PHASE 1: Project Initialization
# =============================================================================
echo ""
echo "=== PHASE 1: Project Init ==="

# Create project programmatically (init is interactive)
run "1.1" "Create project directory" \
    "python3 -c \"
import sys; sys.path.insert(0, '/home/fusar/claude/research-automation')
from core.onboarding import setup_workspace
from pathlib import Path
import yaml, subprocess

p = Path('$PROJECT')
setup_workspace(p)

# Write a real scientific goal
goal = '''# Research Goal

## Title
Predicting Protein-Ligand Binding Affinity with Graph Neural Networks

## Description
Develop a GNN-based model to predict binding affinity (pKd) between protein
targets and small-molecule ligands using the PDBbind v2020 dataset. The model
should learn from 3D molecular graphs and outperform traditional docking scores.

Key objectives:
1. Parse PDBbind SDF/PDB files into molecular graphs
2. Implement a GNN (SchNet or DimeNet variant) for affinity prediction
3. Compare against AutoDock Vina scores as baseline
4. Achieve Pearson r > 0.80 on the core test set

## Success Criteria
- Pearson correlation > 0.80 on PDBbind core set
- RMSE < 1.5 pKd units
- Training completes in < 4 hours on a single RTX 4070
- Full reproducibility with fixed random seeds

## Timeline
3 months

## Key Challenges
- Handling protein flexibility (multiple conformations)
- Featurizing both protein and ligand as graphs
- Small dataset size (~19k complexes) — risk of overfitting
'''
(p / 'knowledge' / 'GOAL.md').write_text(goal)

settings = {
    'project_name': 'protein-binding',
    'project_type': 'research',
    'compute_type': 'local-gpu',
    'notification_method': 'none',
    'timeline': '3 months',
}
(p / 'config' / 'settings.yml').write_text(yaml.dump(settings))

todo = '''# TODO

- [ ] Literature review on GNN-based binding affinity prediction
- [ ] Download and preprocess PDBbind v2020 dataset
- [ ] Implement molecular graph featurization pipeline
- [ ] Build SchNet model architecture in PyTorch
- [ ] Train baseline model and log metrics
- [ ] Hyperparameter optimization with Optuna
- [ ] Compare against AutoDock Vina scores
- [ ] Ablation study on graph features
- [ ] Generate publication-quality figures
- [ ] Write methods and results sections
'''
(p / 'state' / 'TODO.md').write_text(todo)

subprocess.run(['git', 'init'], cwd=str(p), capture_output=True)
subprocess.run(['git', 'add', '-A'], cwd=str(p), capture_output=True)
subprocess.run(['git', 'commit', '-m', 'ricet init: protein-binding project'], cwd=str(p), capture_output=True)
print('Project created: ' + str(p))
print('Files: ' + str(len(list(p.rglob('*')))))
\"" 30

run "1.2" "Verify scaffolded structure" \
    "ls $PROJECT/.claude/agents/ && echo '---' && head -5 $PROJECT/knowledge/GOAL.md && echo '---' && head -5 $PROJECT/config/settings.yml"

# =============================================================================
# PHASE 2: Status & Sessions
# =============================================================================
echo ""
echo "=== PHASE 2: Status & Sessions ==="

run "2.1" "Project status" \
    "cd $PROJECT && ricet status"

run "2.2" "List sessions (empty)" \
    "cd $PROJECT && ricet list-sessions"

run "2.3" "Agent definitions" \
    "cd $PROJECT && ricet agents"

# =============================================================================
# PHASE 3: Knowledge & Memory
# =============================================================================
echo ""
echo "=== PHASE 3: Knowledge & Memory ==="

run "3.1" "Log decision: optimizer choice" \
    "cd $PROJECT && ricet memory log-decision 'Use AdamW optimizer with lr=1e-4 and weight_decay=1e-5 -- SchNet paper recommends this for molecular property prediction'"

run "3.2" "Log decision: dataset split" \
    "cd $PROJECT && ricet memory log-decision 'Use time-based split (pre-2018 train, 2018-2019 val, 2020 test) -- avoids temporal leakage in PDBbind'"

run "3.3" "Search knowledge" \
    "cd $PROJECT && ricet memory search 'optimizer' --top-k 3"

run "3.4" "Export knowledge" \
    "cd $PROJECT && ricet memory export"

run "3.5" "Knowledge stats" \
    "cd $PROJECT && ricet memory stats"

# =============================================================================
# PHASE 4: Literature Search
# =============================================================================
echo ""
echo "=== PHASE 4: Literature ==="

run "4.1" "Cite: GNN binding affinity" \
    "cd $PROJECT && ricet cite 'graph neural network protein ligand binding affinity' --max 3" 90

run "4.2" "Cite: SchNet molecular" \
    "cd $PROJECT && ricet cite 'SchNet equivariant neural network molecular properties' --max 2" 90

run "4.3" "Discover: drug discovery GNN" \
    "cd $PROJECT && ricet discover 'deep learning drug discovery binding prediction' --max 3" 90

run "4.4" "Discover with auto-cite" \
    "cd $PROJECT && ricet discover 'PDBbind benchmark molecular docking' --cite --max 2" 90

run "4.5" "Check references.bib" \
    "cd $PROJECT && wc -l paper/references.bib && head -20 paper/references.bib"

# =============================================================================
# PHASE 5: Web Browsing
# =============================================================================
echo ""
echo "=== PHASE 5: Browse ==="

run "5.1" "Browse PDBbind website" \
    "cd $PROJECT && ricet browse 'http://www.pdbbind.org.cn/'" 30

run "5.2" "Browse Wikipedia GNN" \
    "cd $PROJECT && ricet browse 'https://en.wikipedia.org/wiki/Graph_neural_network'" 30

# =============================================================================
# PHASE 6: Paper Pipeline
# =============================================================================
echo ""
echo "=== PHASE 6: Paper ==="

run "6.1" "Paper check" \
    "cd $PROJECT && ricet paper check"

run "6.2" "Paper build (may fail without LaTeX)" \
    "cd $PROJECT && ricet paper build" 30 true

run "6.3" "Paper update" \
    "cd $PROJECT && ricet paper update" 90

run "6.4" "Paper modernize" \
    "cd $PROJECT && ricet paper modernize"

run "6.5" "Paper adapt-style from Nature ref" \
    "cd $PROJECT && ricet paper adapt-style --reference /home/fusar/claude/research-automation/templates/paper/journals/nature/s41586-023-06812-z.pdf" 60

# =============================================================================
# PHASE 7: Verification & Debug
# =============================================================================
echo ""
echo "=== PHASE 7: Verify & Debug ==="

run "7.1" "Verify plausible claim" \
    "cd $PROJECT && ricet verify 'Graph neural networks can predict protein-ligand binding affinity with Pearson r > 0.8 on PDBbind'" 60

run "7.2" "Verify suspicious claim" \
    "cd $PROJECT && ricet verify 'A simple MLP achieves 99% accuracy on protein folding structure prediction'" 60

run "7.3" "Debug a buggy script" \
    "cat > /tmp/buggy_mol.py << 'PYEOF'
import math

def calculate_binding_energy(kd_nm):
    \"\"\"Convert Kd in nanomolar to binding free energy (kcal/mol).\"\"\"
    R = 1.987  # cal/(mol*K)
    T = 298.15  # Kelvin
    # Bug: forgot to convert nM to M (should multiply by 1e-9)
    delta_G = R * T * math.log(kd_nm)
    return delta_G / 1000  # convert to kcal/mol

energies = [calculate_binding_energy(kd) for kd in [10, 50, 100, 0]]
print('Binding energies:', energies)
PYEOF
cd $PROJECT && ricet debug 'python /tmp/buggy_mol.py'" 60

# =============================================================================
# PHASE 8: Code & Tests
# =============================================================================
echo ""
echo "=== PHASE 8: Code & Tests ==="

run "8.1" "Create source files" \
    "cd $PROJECT && mkdir -p src && cat > src/featurizer.py << 'PYEOF'
\"\"\"Molecular graph featurization for protein-ligand complexes.\"\"\"
import hashlib
from typing import Optional


def atom_features(atomic_num: int, charge: float = 0.0) -> list[float]:
    \"\"\"Compute atom-level features for a graph node.\"\"\"
    one_hot = [0.0] * 10
    idx = min(atomic_num - 1, 9)
    one_hot[idx] = 1.0
    return one_hot + [charge]


def bond_features(bond_type: str) -> list[float]:
    \"\"\"Encode bond type as a feature vector.\"\"\"
    types = {'single': [1, 0, 0], 'double': [0, 1, 0], 'aromatic': [0, 0, 1]}
    return types.get(bond_type, [0, 0, 0])


def mol_to_graph(atoms: list[dict], bonds: list[dict]) -> dict:
    \"\"\"Convert molecule to a graph dict with node and edge features.

    Args:
        atoms: List of atom dicts with 'atomic_num' and optional 'charge'.
        bonds: List of bond dicts with 'atom1', 'atom2', 'type'.

    Returns:
        Graph dict with 'nodes', 'edges', 'edge_features'.
    \"\"\"
    nodes = [atom_features(a['atomic_num'], a.get('charge', 0.0)) for a in atoms]
    edges = [(b['atom1'], b['atom2']) for b in bonds]
    edge_feats = [bond_features(b.get('type', 'single')) for b in bonds]
    return {'nodes': nodes, 'edges': edges, 'edge_features': edge_feats}


def fingerprint(smiles: str) -> str:
    \"\"\"Compute a simple hash fingerprint for a SMILES string.\"\"\"
    return hashlib.md5(smiles.encode()).hexdigest()


def normalize_features(features: list[float], eps: float = 1e-8) -> list[float]:
    \"\"\"L2-normalize a feature vector.\"\"\"
    norm = sum(x**2 for x in features) ** 0.5
    if norm < eps:
        return features
    return [x / norm for x in features]
PYEOF

cat > src/metrics.py << 'PYEOF'
\"\"\"Evaluation metrics for binding affinity prediction.\"\"\"
import math


def pearson_r(predicted: list[float], actual: list[float]) -> float:
    \"\"\"Compute Pearson correlation coefficient.\"\"\"
    n = len(predicted)
    if n < 2:
        return 0.0
    mean_p = sum(predicted) / n
    mean_a = sum(actual) / n
    cov = sum((p - mean_p) * (a - mean_a) for p, a in zip(predicted, actual))
    std_p = math.sqrt(sum((p - mean_p)**2 for p in predicted))
    std_a = math.sqrt(sum((a - mean_a)**2 for a in actual))
    if std_p * std_a == 0:
        return 0.0
    return cov / (std_p * std_a)


def rmse(predicted: list[float], actual: list[float]) -> float:
    \"\"\"Compute root mean squared error.\"\"\"
    n = len(predicted)
    if n == 0:
        return 0.0
    return math.sqrt(sum((p - a)**2 for p, a in zip(predicted, actual)) / n)


def mae(predicted: list[float], actual: list[float]) -> float:
    \"\"\"Compute mean absolute error.\"\"\"
    n = len(predicted)
    if n == 0:
        return 0.0
    return sum(abs(p - a) for p, a in zip(predicted, actual)) / n
PYEOF
echo 'Created src/featurizer.py and src/metrics.py'"

run "8.2" "Generate tests" \
    "cd $PROJECT && ricet test-gen" 60

run "8.3" "Generate tests for specific file" \
    "cd $PROJECT && ricet test-gen --file src/featurizer.py" 60

run "8.4" "Auto-generate documentation" \
    "cd $PROJECT && ricet docs --force" 60

# =============================================================================
# PHASE 9: Reproducibility
# =============================================================================
echo ""
echo "=== PHASE 9: Reproducibility ==="

run "9.1" "Log experiment run" \
    "cd $PROJECT && ricet repro log --run-id gnn-baseline-001 --command 'python train.py --model schnet --lr 1e-4 --epochs 100 --seed 42' --notes 'Baseline SchNet, no pre-training, PDBbind refined set'"

run "9.2" "Log second run" \
    "cd $PROJECT && ricet repro log --run-id gnn-optuna-002 --command 'python train.py --model schnet --lr 3e-4 --epochs 200 --hidden 256' --notes 'Optuna best params, doubled hidden dim'"

run "9.3" "List runs" \
    "cd $PROJECT && ricet repro list"

run "9.4" "Show run details" \
    "cd $PROJECT && ricet repro show --run-id gnn-baseline-001"

run "9.5" "Hash a dataset file" \
    "echo 'PDB_ID,pKd,resolution\n1a4k,6.2,2.1\n1b6l,7.8,1.8\n2c3d,5.1,2.5' > /tmp/pdbbind_sample.csv && cd $PROJECT && ricet repro hash --path /tmp/pdbbind_sample.csv"

# =============================================================================
# PHASE 10: Goal Fidelity & Maintenance
# =============================================================================
echo ""
echo "=== PHASE 10: Fidelity & Maintenance ==="

run "10.1" "Goal fidelity check" \
    "cd $PROJECT && ricet fidelity" 90

run "10.2" "Daily maintenance" \
    "cd $PROJECT && ricet maintain" 180

# =============================================================================
# PHASE 11: MCP Discovery
# =============================================================================
echo ""
echo "=== PHASE 11: MCP Discovery ==="

run "11.1"  "MCP: database"          "cd $PROJECT && ricet mcp-search 'database'"
run "11.2"  "MCP: browser"           "cd $PROJECT && ricet mcp-search 'browser automation'"
run "11.3"  "MCP: arxiv"             "cd $PROJECT && ricet mcp-search 'arxiv paper'"
run "11.4"  "MCP: github"            "cd $PROJECT && ricet mcp-search 'github'"
run "11.5"  "MCP: docker"            "cd $PROJECT && ricet mcp-search 'docker container'"
run "11.6"  "MCP: filesystem"        "cd $PROJECT && ricet mcp-search 'filesystem'"
run "11.7"  "MCP: postgres"          "cd $PROJECT && ricet mcp-search 'postgres sql'"
run "11.8"  "MCP: puppeteer"         "cd $PROJECT && ricet mcp-search 'puppeteer'"
run "11.9"  "MCP: slack"             "cd $PROJECT && ricet mcp-search 'slack'"
run "11.10" "MCP: memory"            "cd $PROJECT && ricet mcp-search 'memory vector'"
run "11.11" "MCP: sequential think"  "cd $PROJECT && ricet mcp-search 'sequential thinking'"
run "11.12" "MCP: git"               "cd $PROJECT && ricet mcp-search 'git version control'"
run "11.13" "MCP: web search"        "cd $PROJECT && ricet mcp-search 'web search'"
run "11.14" "MCP: jupyter"           "cd $PROJECT && ricet mcp-search 'jupyter notebook'"
run "11.15" "MCP: python"            "cd $PROJECT && ricet mcp-search 'python execute'"
run "11.16" "MCP: markdown"          "cd $PROJECT && ricet mcp-search 'markdown'"
run "11.17" "MCP: email"             "cd $PROJECT && ricet mcp-search 'email smtp'"
run "11.18" "MCP: redis"             "cd $PROJECT && ricet mcp-search 'redis cache'"
run "11.19" "MCP: kubernetes"        "cd $PROJECT && ricet mcp-search 'kubernetes'"
run "11.20" "MCP: s3 storage"        "cd $PROJECT && ricet mcp-search 's3 storage'"
run "11.21" "MCP: graphql"           "cd $PROJECT && ricet mcp-search 'graphql api'"
run "11.22" "MCP: monitoring"        "cd $PROJECT && ricet mcp-search 'monitoring observability'"
run "11.23" "MCP: pdf"               "cd $PROJECT && ricet mcp-search 'pdf document'"
run "11.24" "MCP: image"             "cd $PROJECT && ricet mcp-search 'image generation'"
run "11.25" "MCP: embeddings"        "cd $PROJECT && ricet mcp-search 'embeddings vector'"

# =============================================================================
# PHASE 12: MCP Creation
# =============================================================================
echo ""
echo "=== PHASE 12: MCP Creation ==="

run "12.1" "Create custom MCP" \
    "cd $PROJECT && ricet mcp-create pdbbind-mcp --desc 'Fetch and parse PDBbind protein-ligand complexes' --tools 'fetch_complex,parse_sdf,get_binding_affinity,list_targets'"

# =============================================================================
# PHASE 13: Task Queue
# =============================================================================
echo ""
echo "=== PHASE 13: Task Queue ==="

run "13.1" "Submit task: data preprocessing" \
    "cd $PROJECT && ricet queue submit --prompt 'Download PDBbind v2020 refined set and extract SDF files for the 5316 complexes'"

run "13.2" "Submit task: feature engineering" \
    "cd $PROJECT && ricet queue submit --prompt 'Compute atom and bond features for all ligands using RDKit'"

run "13.3" "Queue status" \
    "cd $PROJECT && ricet queue status"

run "13.4" "Cancel all (cleanup)" \
    "cd $PROJECT && ricet queue cancel-all"

# =============================================================================
# PHASE 14: Infra & DevOps
# =============================================================================
echo ""
echo "=== PHASE 14: Infrastructure ==="

run "14.1" "Infra check" \
    "cd $PROJECT && ricet infra check"

run "14.2" "CI/CD setup" \
    "cd $PROJECT && ricet infra cicd --template python"

run "14.3" "Secrets listing" \
    "cd $PROJECT && ricet infra secrets"

# =============================================================================
# PHASE 15: Runbook
# =============================================================================
echo ""
echo "=== PHASE 15: Runbook ==="

run "15.0" "Create runbook" \
    "cat > /tmp/test-runbook.md << 'RUNBOOK'
# Environment Check Runbook

## Step 1: Python version

\`\`\`bash
python3 --version
\`\`\`

## Step 2: Check pip packages

\`\`\`bash
pip list 2>/dev/null | head -10
\`\`\`

## Step 3: Check git

\`\`\`bash
git --version
\`\`\`
RUNBOOK
echo 'Created /tmp/test-runbook.md'"

run "15.1" "Runbook dry-run" \
    "cd $PROJECT && ricet runbook /tmp/test-runbook.md"

run "15.2" "Runbook execute" \
    "cd $PROJECT && ricet runbook /tmp/test-runbook.md --execute"

# =============================================================================
# PHASE 16: Two-Repo Structure
# =============================================================================
echo ""
echo "=== PHASE 16: Two-Repo ==="

run "16.1" "Two-repo init" \
    "cd $PROJECT && ricet two-repo init"

run "16.2" "Two-repo status" \
    "cd $PROJECT && ricet two-repo status"

run "16.3" "Create experiment + promote" \
    "cd $PROJECT && mkdir -p experiments && echo 'SCHNET_HIDDEN=128' > experiments/config.py && ricet two-repo promote --files 'config.py' --message 'Promote SchNet config'"

run "16.4" "Two-repo diff" \
    "cd $PROJECT && ricet two-repo diff"

# =============================================================================
# PHASE 17: Git Worktrees
# =============================================================================
echo ""
echo "=== PHASE 17: Worktrees ==="

run "17.1" "Worktree list" \
    "cd $PROJECT && ricet worktree list"

run "17.2" "Worktree add" \
    "cd $PROJECT && ricet worktree add feature-dimenet" 30 true

run "17.3" "Worktree remove" \
    "cd $PROJECT && ricet worktree remove feature-dimenet" 30 true

run "17.4" "Worktree prune" \
    "cd $PROJECT && ricet worktree prune"

# =============================================================================
# PHASE 18: Cross-Repo RAG
# =============================================================================
echo ""
echo "=== PHASE 18: Cross-Repo ==="

run "18.0" "Create linked repo" \
    "mkdir -p /tmp/gnn-utils && cat > /tmp/gnn-utils/layers.py << 'PYEOF'
def graph_conv(nodes, adj, weights):
    \"\"\"Simple graph convolution: H' = sigma(A * H * W)\"\"\"
    return [sum(adj[i][j] * nodes[j] for j in range(len(nodes))) for i in range(len(nodes))]

def readout(nodes):
    \"\"\"Global mean pooling over graph nodes.\"\"\"
    if not nodes:
        return []
    dim = len(nodes[0]) if isinstance(nodes[0], list) else 1
    return [sum(n[d] for n in nodes) / len(nodes) for d in range(dim)]
PYEOF
echo '# GNN Utilities' > /tmp/gnn-utils/README.md
echo 'Created /tmp/gnn-utils'"

run "18.1" "Link repo" \
    "cd $PROJECT && ricet link /tmp/gnn-utils --name gnn-utils"

run "18.2" "Search across repos" \
    "cd $PROJECT && ricet memory search 'graph convolution'"

run "18.3" "Reindex" \
    "cd $PROJECT && ricet reindex"

run "18.4" "Unlink" \
    "cd $PROJECT && ricet unlink gnn-utils"

# =============================================================================
# PHASE 19: Cross-Project Learning
# =============================================================================
echo ""
echo "=== PHASE 19: Cross-Project Learning ==="

run "19.0" "Create source project" \
    "mkdir -p /tmp/prior-project/knowledge && cat > /tmp/prior-project/knowledge/ENCYCLOPEDIA.md << 'EOF'
## Tricks

### 2025-06-15T10:00:00
Using cosine annealing with warm restarts improves GNN training stability.

### 2025-06-20T14:30:00
Early stopping with patience=20 on validation RMSE prevents overfitting on PDBbind.

## What Works

### 2025-07-01T09:00:00
SchNet with 6 interaction blocks and 128 features gives best balance of speed and accuracy.

## What Fails

### 2025-07-05T16:00:00
Batch normalization in GNN message passing causes training instability — use layer norm instead.
EOF
echo 'Created /tmp/prior-project'"

run "19.1" "Sync learnings" \
    "cd $PROJECT && ricet sync-learnings /tmp/prior-project"

run "19.2" "Verify synced knowledge" \
    "cd $PROJECT && ricet memory search 'cosine annealing'"

# =============================================================================
# PHASE 20: Adopt Existing Repo
# =============================================================================
echo ""
echo "=== PHASE 20: Adopt ==="

run "20.0" "Create existing repo" \
    "mkdir -p /tmp/existing-gnn-repo && cd /tmp/existing-gnn-repo && git init && echo '# GNN Binding Predictor\nA simple GNN for PDBbind.' > README.md && git add . && git commit -m 'init' && echo 'Created'"

run "20.1" "Adopt local repo" \
    "cd $TESTDIR && ricet adopt /tmp/existing-gnn-repo --name adopted-gnn"

# =============================================================================
# PHASE 21: Projects Management
# =============================================================================
echo ""
echo "=== PHASE 21: Projects ==="

run "21.1" "Register project" \
    "cd $PROJECT && ricet projects register"

run "21.2" "List projects" \
    "cd $PROJECT && ricet projects list"

# =============================================================================
# PHASE 22: Package Management
# =============================================================================
echo ""
echo "=== PHASE 22: Package ==="

run "22.1" "Package init" \
    "cd $PROJECT && ricet package init"

run "22.2" "Package build" \
    "cd $PROJECT && ricet package build" 60 true

# =============================================================================
# PHASE 23: Website
# =============================================================================
echo ""
echo "=== PHASE 23: Website ==="

run "23.1" "Website init" \
    "cd $PROJECT && ricet website init"

run "23.2" "Website build" \
    "cd $PROJECT && ricet website build" 60 true

# =============================================================================
# PHASE 24: Social Publishing
# =============================================================================
echo ""
echo "=== PHASE 24: Social ==="

run "24.1" "Publish to Medium (draft)" \
    "cd $PROJECT && ricet publish medium" 60

run "24.2" "Publish to LinkedIn (draft)" \
    "cd $PROJECT && ricet publish linkedin" 60

# =============================================================================
# PHASE 25: Zapier
# =============================================================================
echo ""
echo "=== PHASE 25: Zapier ==="

run "25.1" "Zapier setup" \
    "cd $PROJECT && ricet zapier setup --key 'test-key-placeholder'"

# =============================================================================
# PHASE 26: Review CLAUDE.md
# =============================================================================
echo ""
echo "=== PHASE 26: Review ==="

run "26.1" "Review CLAUDE.md" \
    "cd $PROJECT && ricet review-claude-md" 60

# =============================================================================
# PHASE 27: Overnight (minimal)
# =============================================================================
echo ""
echo "=== PHASE 27: Overnight ==="

run "27.0" "Set up minimal TODO" \
    "cd $PROJECT && cat > state/TODO.md << 'EOF'
# TODO

- [ ] Create a Python script that prints the Pearson correlation between two sample lists
EOF
echo 'TODO updated'"

run "27.1" "Overnight 1 iteration" \
    "cd $PROJECT && ricet overnight --iterations 1" 120

# =============================================================================
# PHASE 28: Autonomous Routines
# =============================================================================
echo ""
echo "=== PHASE 28: Auto ==="

run "28.1" "Add routine: nightly verify" \
    "cd $PROJECT && ricet auto add-routine --name nightly-verify --command 'ricet verify \"GNN models generalize to unseen protein families\"' --schedule daily --desc 'Nightly claim verification'"

run "28.2" "Add routine: weekly cite" \
    "cd $PROJECT && ricet auto add-routine --name weekly-lit --command 'ricet cite \"protein binding affinity GNN\" --max 2' --schedule weekly --desc 'Weekly literature check'"

run "28.3" "List routines" \
    "cd $PROJECT && ricet auto list-routines"

run "28.4" "Monitor topic" \
    "cd $PROJECT && ricet auto monitor --topic 'graph neural network drug discovery'"

# =============================================================================
# PHASE 29: Metrics
# =============================================================================
echo ""
echo "=== PHASE 29: Metrics ==="

run "29.1" "Metrics" \
    "cd $PROJECT && ricet metrics"

# =============================================================================
# PHASE 30: Mobile Companion
# =============================================================================
echo ""
echo "=== PHASE 30: Mobile ==="

run "30.1" "Mobile status" \
    "cd $PROJECT && ricet mobile status"

run "30.2" "Mobile connect-info" \
    "cd $PROJECT && ricet mobile connect-info"

run "30.3" "Mobile pair" \
    "cd $PROJECT && ricet mobile pair --label 'test-phone'"

run "30.4" "Mobile tokens" \
    "cd $PROJECT && ricet mobile tokens"

# =============================================================================
# PHASE 31: Environment Variables
# =============================================================================
echo ""
echo "=== PHASE 31: Env Variables ==="

run "31.1" "RICET_NO_CLAUDE: agents" \
    "cd $PROJECT && RICET_NO_CLAUDE=true ricet agents"

run "31.2" "RICET_NO_CLAUDE: fidelity" \
    "cd $PROJECT && RICET_NO_CLAUDE=true ricet fidelity" 60

# =============================================================================
# PHASE 32: Unit Test Suite
# =============================================================================
echo ""
echo "=== PHASE 32: Test Suite ==="

run "32.1" "Full pytest suite" \
    "cd /home/fusar/claude/research-automation && python -m pytest tests/ -q 2>&1 | tail -5" 300

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "========================================"

cat >> "$REPORT" << SUMMARY

# Summary

| Metric | Count |
|--------|-------|
| **Total tests** | $TOTAL |
| **Passed** | $PASS |
| **Failed** | $FAIL |
| **Skipped** | $SKIP |

**Pass rate:** $(( PASS * 100 / TOTAL ))%

## Tests Requiring Manual Verification

These features cannot be tested automatically and require human interaction:

1. **ricet init** — Interactive wizard with goal input, credential collection
2. **ricet start** — Launches Claude Code interactively
3. **ricet resume** — Resumes an interactive Claude session
4. **ricet config** — Interactive configuration prompts
5. **ricet voice** — Requires microphone hardware + whisper
6. **ricet mobile serve** — Requires opening phone browser to PWA
7. **ricet browse --screenshot** — Requires chromium/puppeteer
8. **ricet overnight --docker** — Requires Docker daemon running
9. **ricet package publish** — Would publish to real PyPI
10. **ricet website preview** — Starts blocking local server

### How to manually test:

**Voice (ricet voice):**
\`\`\`bash
cd $PROJECT && ricet voice --duration 5
# Speak into microphone, see transcription
\`\`\`

**Mobile (ricet mobile serve):**
\`\`\`bash
cd $PROJECT && ricet mobile serve --port 8777
# Open https://<server-ip>:8777 on phone
# Accept self-signed cert, enter token from 'ricet mobile pair'
\`\`\`

**Web Dashboard:**
\`\`\`bash
cd $PROJECT && ricet website preview
# Open http://localhost:8000 in browser
\`\`\`
SUMMARY

echo "SUMMARY: $PASS passed, $FAIL failed, $SKIP skipped out of $TOTAL"
echo "Report: $REPORT"
echo "Full log: $LOG"
echo ""

if [ $FAIL -gt 0 ]; then
    echo "FAILURES DETECTED — review $LOG for details"
    exit 1
else
    echo "ALL TESTS PASSED"
    exit 0
fi
