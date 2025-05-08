#!/bin/bash
# Script to run PubMedBERT embeddings with minimal logging and optimized performance

# Set environment variables for offline mode
export HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

# Run the embedder with optimized parameters and minimal logging
python update_embeddings_for_abstracts.py \
  --embedder pubmedbert \
  --model "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext" \
  --batch-size 50 \
  --workers 4 \
  --max-batch-size 32 \
  --memory-limit 80.0 \
  --device cpu \
  --no-progress
