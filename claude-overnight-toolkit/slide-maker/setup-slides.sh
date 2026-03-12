#!/bin/bash
# =============================================================================
# Set up slide-maker in a project directory
# =============================================================================
# Usage:
#   ./setup-slides.sh /path/to/your/project
#
# This copies the slide-making infrastructure into your project so the Claude
# agent can generate a presentation from your codebase or a website.
# =============================================================================

set -e
TOOLKIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -z "$1" ]; then
    echo "Usage: $0 /path/to/your/project"
    echo ""
    echo "This copies slide-making tools into your project."
    echo "Then edit slides_task.md and run the agent."
    exit 1
fi

PROJECT_DIR="$1"

echo "=== Setting up Slide Maker ==="
echo "Project: ${PROJECT_DIR}"
echo ""

mkdir -p "${PROJECT_DIR}/slides"

# Copy core files
cp "${TOOLKIT_DIR}/slide_utils.py" "${PROJECT_DIR}/slides/"
cp "${TOOLKIT_DIR}/slideprompt.md" "${PROJECT_DIR}/slides/"
cp "${TOOLKIT_DIR}/slides_task.md" "${PROJECT_DIR}/slides/"
cp "${TOOLKIT_DIR}/make_slides_example.py" "${PROJECT_DIR}/slides/"
cp "${TOOLKIT_DIR}/requirements.txt" "${PROJECT_DIR}/slides/"

echo "Files copied to ${PROJECT_DIR}/slides/"
echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit ${PROJECT_DIR}/slides/slides_task.md"
echo "     - Set codebase path OR website URL"
echo "     - Describe audience, key message, schematic ideas"
echo ""
echo "  2. Install dependencies:"
echo "     pip install -r ${PROJECT_DIR}/slides/requirements.txt"
echo ""
echo "  3. Set your Google API key (for Nano Banana Pro):"
echo "     export GOOGLE_API_KEY=your-key-here"
echo ""
echo "  4. Run the agent to create make_slides.py:"
echo "     cd ${PROJECT_DIR}/slides"
echo "     claude -p \"\$(cat slideprompt.md)\""
echo ""
echo "  5. Run the generated script:"
echo "     python make_slides.py"
echo ""
echo "  6. Open slides_output/presentation.pptx"
