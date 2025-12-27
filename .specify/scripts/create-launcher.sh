#!/bin/bash
set -e

# Usage: ./create-launcher.sh <launcher-name> <python-reference-file>

LAUNCHER_NAME="$1"
PYTHON_FILE="$2"

if [ -z "$LAUNCHER_NAME" ]; then
    echo "Usage: $0 <launcher-name> <python-reference-file>"
    exit 1
fi

LAUNCHER_SAFE=$(echo "$LAUNCHER_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')

# Get next feature number
LAST_NUM=$(ls .specify/specs 2>/dev/null | grep -oE '^[0-9]+' | sort -n | tail -1)
NEXT_NUM=$((LAST_NUM + 1))
NUM_PADDED=$(printf "%03d" "$NEXT_NUM")

FEATURE_DIR=".specify/specs/${NUM_PADDED}-${LAUNCHER_SAFE}_launcher"

mkdir -p "$FEATURE_DIR"

# Create spec from launcher template
sed "s/\[LAUNCHER NAME\]/${LAUNCHER_NAME}/g; s/\[XXX\]/${NUM_PADDED}/g" .specify/templates/launcher-template.md > "$FEATURE_DIR/spec.md"

# Create reference.md linking to Python file
if [ -n "$PYTHON_FILE" ]; then
    echo "# Python Reference

File: \`python_backup/${PYTHON_FILE}\`

## Analysis Notes

<!-- Add analysis of the Python implementation here -->
" > "$FEATURE_DIR/reference.md"
fi

# Create plan
sed "s/\[FEATURE NAME\]/${LAUNCHER_NAME} Launcher/g; s/\[XXX\]/${NUM_PADDED}/g" .specify/templates/plan-template.md > "$FEATURE_DIR/plan.md"

# Create branch
git checkout -b "launcher/${NUM_PADDED}-${LAUNCHER_SAFE}" 2>/dev/null || true

echo "✓ Created launcher spec: ${FEATURE_DIR}"
echo "✓ Reference file: $PYTHON_FILE"