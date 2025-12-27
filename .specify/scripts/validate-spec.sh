#!/bin/bash
set -e

SPEC_DIR="$1"

if [ -z "$SPEC_DIR" ]; then
    echo "Usage: $0 <spec-directory>"
    exit 1
fi

echo "Validating spec: $SPEC_DIR"
echo "---"

# Check required files exist
for file in spec.md plan.md tasks.md; do
    if [ ! -f "$SPEC_DIR/$file" ]; then
        echo "❌ Missing required file: $file"
        exit 1
    fi
    echo "✓ Found: $file"
done

# Check spec.md has required sections
echo ""
echo "Checking spec.md structure..."

for section in "User Stories" "Requirements" "Success Criteria"; do
    if ! grep -q "^## $section" "$SPEC_DIR/spec.md"; then
        echo "❌ Missing section in spec.md: $section"
        exit 1
    fi
    echo "✓ Found section: $section"
done

# Check plan.md has constitution compliance
echo ""
echo "Checking plan.md constitution compliance..."
if ! grep -q "Constitution Compliance Check" "$SPEC_DIR/plan.md"; then
    echo "❌ Missing constitution compliance in plan.md"
    exit 1
fi
echo "✓ Constitution compliance section present"

# Check for UNCERTAINTY markers
echo ""
echo "Checking for unresolved questions..."
UNCERTAIN_COUNT=$(grep -c "\[NEEDS CLARIFICATION\]" "$SPEC_DIR/spec.md" || true)
if [ "$UNCERTAIN_COUNT" -gt 0 ]; then
    echo "⚠️  Found $UNCERTAIN_COUNT unresolved question(s)"
    grep "\[NEEDS CLARIFICATION\]" "$SPEC_DIR/spec.md"
else
    echo "✓ No unresolved questions"
fi

echo ""
echo "✅ Spec validation complete!"