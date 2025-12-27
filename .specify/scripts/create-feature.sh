#!/bin/bash
set -e

# Usage: ./create-feature.sh <feature-name> [priority]

FEATURE_NAME="$1"
PRIORITY="${2:-P2}"

if [ -z "$FEATURE_NAME" ]; then
    echo "Usage: $0 <feature-name> [priority]"
    exit 1
fi

# Sanitize feature name
FEATURE_SAFE=$(echo "$FEATURE_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')

# Get next feature number
LAST_NUM=$(ls .specify/specs 2>/dev/null | grep -oE '^[0-9]+' | sort -n | tail -1)
NEXT_NUM=$((LAST_NUM + 1))
NUM_PADDED=$(printf "%03d" "$NEXT_NUM")

FEATURE_DIR=".specify/specs/${NUM_PADDED}-${FEATURE_SAFE}"

# Create directory
mkdir -p "$FEATURE_DIR"

# Copy templates
sed "s/\[FEATURE NAME\]/${FEATURE_NAME}/g" .specify/templates/spec-template.md > "$FEATURE_DIR/spec.md"
sed "s/\[FEATURE NAME\]/${FEATURE_NAME}/g; s/\[XXX\]/${NUM_PADDED}/g" .specify/templates/plan-template.md > "$FEATURE_DIR/plan.md"
sed "s/\[FEATURE NAME\]/${FEATURE_NAME}/g; s/\[XXX\]/${NUM_PADDED}/g" .specify/templates/tasks-template.md > "$FEATURE_DIR/tasks.md"

# Create feature branch
git checkout -b "feature/${NUM_PADDED}-${FEATURE_SAFE}" 2>/dev/null || echo "Branch may already exist"

echo "✓ Created feature: ${FEATURE_DIR}"
echo "✓ Created branch: feature/${NUM_PADDED}-${FEATURE_SAFE}"
echo "✓ Next step: Edit $FEATURE_DIR/spec.md"