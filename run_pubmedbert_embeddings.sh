#!/bin/bash
# Script to run PubMedBERT embeddings with optimized parameters for performance

# Set environment variables for offline mode
export HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

# Run the embedder with optimized parameters
# Increased batch size and workers for better performance
python update_embeddings_for_abstracts.py \
  --embedder pubmedbert \
  --model "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext" \
  --batch-size 100 \
  --workers 4 \
  --max-batch-size 100 \
  --memory-limit 80.0 \
  --device mps
