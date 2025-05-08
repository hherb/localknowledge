#!/bin/bash
# Script to kill the current embedding process and start a new one with safer parameters

# Find and kill the current process
pkill -f "python update_embeddings_for_abstracts.py"

# Wait a moment for the process to terminate
sleep 2

# Run the safer script with minimal logging
./run_pubmedbert_quiet.sh
