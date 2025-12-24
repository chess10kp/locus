#!/bin/bash

# Locus Volume and Brightness Commands
# Source this file in your shell config (e.g., ~/.bashrc) to use the functions

# Volume control functions
locus_volume() {
    if [[ $# -eq 0 ]]; then
        python3 "$(dirname "$0")/locus_client.py" volume get
    else
        python3 "$(dirname "$0")/locus_client.py" volume "$1"
    fi
}

# Brightness control functions
locus_brightness() {
    if [[ $# -eq 0 ]]; then
        python3 "$(dirname "$0")/locus_client.py" brightness get
    else
        python3 "$(dirname "$0")/locus_client.py" brightness "$1"
    fi
}