#!/bin/bash

# Test script for locus lockscreen

echo "=== Locus Lockscreen Test ==="
echo ""

# Check if config exists
if [ ! -f ~/.config/locus/config.toml ]; then
    echo "❌ Config not found at ~/.config/locus/config.toml"
    echo "Creating default config..."
    mkdir -p ~/.config/locus
    cat > ~/.config/locus/config.toml << 'EOF'
[lock_screen]
password = "admin"
max_attempts = 3
enabled = true
EOF
    echo "✅ Config created with default password: 'admin'"
else
    echo "✅ Config found"
    if grep -q "\[lock_screen\]" ~/.config/locus/config.toml; then
        echo "✅ Lockscreen config exists"
        password=$(grep "^password" ~/.config/locus/config.toml | cut -d'"' -f2)
        echo "   Password configured: ${password:0:3}*** (hidden)"
    else
        echo "⚠️  Lockscreen config not found in config file"
        echo "Adding lockscreen config..."
        cat >> ~/.config/locus/config.toml << 'EOF'

[lock_screen]
password = "admin"
max_attempts = 3
enabled = true
EOF
        echo "✅ Lockscreen config added"
    fi
fi

echo ""

# Check if locus is running
if pgrep -x "locus" > /dev/null; then
    echo "✅ Locus is running"
    echo ""
    echo "Triggering lockscreen..."
    echo "Password: admin"
    echo ""

    # Trigger lockscreen via IPC
    echo 'lock' | nc -U /tmp/locus_socket

    if [ $? -eq 0 ]; then
        echo "✅ Lock command sent successfully"
        echo ""
        echo "The lockscreen should now be visible on all monitors."
        echo "Type 'admin' and press Enter to unlock."
        echo ""
        echo "Press Ctrl+C in this terminal to exit"
    else
        echo "❌ Failed to send lock command"
        echo "   Check if socket exists at /tmp/locus_socket"
    fi
else
    echo "❌ Locus is not running"
    echo ""
    echo "Start Locus first:"
    echo "  ./locus"
    echo ""
    echo "Or run in background:"
    echo "  ./locus &"
    echo ""
    echo "Then run this script again."
fi
