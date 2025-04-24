import numpy as np
import re
from collections import Counter
from typing import List, Dict, Tuple


class BM25OnTheFly:
    """
    Implements BM25 scoring for a small subset of documents without requiring precomputed indexes.
    Designed for "on-the-fly" ranking of < 200 documents from a preliminary keyword search.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 with standard parameters
        
        Args:
            k1: Controls term frequency saturation (default: 1.5)
            b: Controls document length normalization (default: 0.75)
        """
        self.k1 = k1
        self.b = b
        
    def preprocess_text(self, text: str) -> List[str]:
        """
        Basic preprocessing: lowercase, remove punctuation, tokenize
        
        Args:
            text: Raw text to preprocess
            
        Returns:
            List of tokens
        """
        # Convert to lowercase
        text = text.lower()
        # Remove punctuation and split into tokens
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    def compute_document_frequencies(self, documents: List[str]) -> Dict[str, int]:
        """
        Compute document frequencies for each term in the corpus
        
        Args:
            documents: List of document texts
            
        Returns:
            Dictionary mapping terms to their document frequencies
        """
        # Count term occurrences across documents
        doc_freqs = Counter()
        
        for doc in documents:
            # Count each term only once per document
            unique_terms = set(self.preprocess_text(doc))
            doc_freqs.update(unique_terms)
            
        return dict(doc_freqs)
    
    def compute_average_document_length(self, documents: List[str]) -> float:
        """
        Calculate the average document length in the corpus
        
        Args:
            documents: List of document texts
            
        Returns:
            Average document length (in tokens)
        """
        doc_lengths = [len(self.preprocess_text(doc)) for doc in documents]
        return sum(doc_lengths) / len(documents) if documents else 0
    
    def calculate_bm25_scores(self, query: str, documents: List[str]) -> List[float]:
        """
        Calculate BM25 scores for each document relative to the query
        
        Args:
            query: The search query
            documents: List of document texts to rank
            
        Returns:
            List of BM25 scores corresponding to each document
        """
        # Preprocess the query
        query_terms = self.preprocess_text(query)
        
        # Calculate document frequencies and average document length
        doc_freqs = self.compute_document_frequencies(documents)
        avg_doc_length = self.compute_average_document_length(documents)
        
        # Number of documents in the corpus
        N = len(documents)
        
        # Calculate BM25 score for each document
        scores = []
        
        for doc in documents:
            doc_terms = self.preprocess_text(doc)
            doc_length = len(doc_terms)
            
            # Count term frequencies in this document
            term_freqs = Counter(doc_terms)
            
            # Calculate score for this document
            score = 0
            for term in query_terms:
                if term in doc_freqs and doc_freqs[term] > 0:
                    # IDF component
                    idf = np.log((N - doc_freqs[term] + 0.5) / (doc_freqs[term] + 0.5) + 1.0)
                    
                    # TF component with document length normalization
                    tf = term_freqs.get(term, 0)
                    normalized_tf = (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * doc_length / avg_doc_length))
                    
                    score += idf * normalized_tf
            
            scores.append(score)
        
        return scores
    
    def rank_documents(self, query: str, documents: List[str], document_ids: List = None) -> List[Tuple]:
        """
        Rank documents based on BM25 scores
        
        Args:
            query: The search query
            documents: List of document texts to rank
            document_ids: Optional list of document identifiers (defaults to indices)
            
        Returns:
            List of (document_id, score) tuples sorted by decreasing score
        """
        # Calculate BM25 scores
        scores = self.calculate_bm25_scores(query, documents)
        
        # Use document indices as IDs if not provided
        if document_ids is None:
            document_ids = list(range(len(documents)))
        
        # Create (id, score) pairs and sort by score in descending order
        id_score_pairs = list(zip(document_ids, scores))
        ranked_results = sorted(id_score_pairs, key=lambda x: x[1], reverse=True)
        
        return ranked_results


# Example usage
if __name__ == "__main__":
    # Sample documents (abstracts)
    documents = [
        "Artificial intelligence applications in emergency medicine: A systematic review.",
        "Machine learning models for predicting hospital readmission in emergency department patients.",
        "Clinical decision support systems in emergency care: a scoping review of the literature.",
        "Natural language processing for automated extraction of emergency department diagnoses.",
        "Deep learning algorithms for ECG interpretation in the emergency department."
    ]
    
    # Document IDs (e.g., PubMed IDs or other identifiers)
    doc_ids = ["PMC12345", "PMC23456", "PMC34567", "PMC45678", "PMC56789"]
    
    # Create BM25 ranker
    bm25 = BM25OnTheFly()
    
    # Sample query
    query = "machine learning emergency department decision support"
    
    # Rank documents
    ranked_results = bm25.rank_documents(query, documents, doc_ids)
    
    # Print results
    print(f"Query: {query}\n")
    print("Ranked Results:")
    for doc_id, score in ranked_results:
        idx = doc_ids.index(doc_id)
        print(f"Score: {score:.4f} - ID: {doc_id} - {documents[idx]}")
