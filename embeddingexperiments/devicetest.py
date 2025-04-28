from sentence_transformers import SentenceTransformer
import torch
from .pubmedbert import PubMedBERT

MODEL = "microsoft/BiomedNLP-PubMedBERT-base-uncased-abstract-fulltext" 

# Automatically detect device
device = 'mps' if torch.backends.mps.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')
print(f"Using device: {device}")

# Load model on detected device
model = SentenceTransformer(MODEL, device=device)

bert =PubMedBERT()

