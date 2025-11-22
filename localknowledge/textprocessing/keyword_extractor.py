import spacy
import re
from typing import List, Dict, Set, Tuple
from collections import defaultdict
import itertools
import numpy as np
from nltk.corpus import wordnet as wn
from nltk.corpus import stopwords
import requests
from functools import lru_cache


class MedicalQueryProcessor:
    """
    Extract and expand keywords from natural language medical queries.
    """
    
    def __init__(self, use_umls: bool = True, use_wordnet: bool = True, 
                 umls_api_key: str = None, max_synonyms: int = 3):
        """
        Initialize the query processor with desired expansion sources.
        
        Args:
            use_umls: Whether to use UMLS for medical term expansion
            use_wordnet: Whether to use WordNet for general term expansion
            umls_api_key: API key for UMLS Terminology Services
            max_synonyms: Maximum number of synonyms to add per term
        """
        # Load NLP model
        try:
            # Try to load the larger model with word vectors first
            self.nlp = spacy.load("en_core_sci_lg")
            print("Loaded scientific NLP model")
        except OSError:
            try:
                # Fall back to scientific model without word vectors
                self.nlp = spacy.load("en_core_sci_md")
                print("Loaded medium scientific NLP model")
            except OSError:
                # Fall back to general English model
                self.nlp = spacy.load("en_core_web_md")
                print("Loaded general English NLP model")
        
        # Setup expansion options
        self.use_umls = use_umls
        self.use_wordnet = use_wordnet
        self.umls_api_key = umls_api_key
        self.max_synonyms = max_synonyms
        
        # Load stopwords
        try:
            self.stopwords = set(stopwords.words('english'))
        except LookupError:
            # Fallback minimal stopwords if NLTK data not available
            self.stopwords = {
                'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 
                'when', 'where', 'how', 'which', 'who', 'whom', 'this', 'that', 'these', 
                'those', 'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about', 
                'for', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 
                'had', 'having', 'do', 'does', 'did', 'doing', 'to', 'from', 'by', 'on',
                'at', 'in', 'with', 'about', 'against', 'between', 'into', 'through'
            }
            
        # Medical stopwords to filter out from results
        self.medical_stopwords = {
            'patient', 'patients', 'disease', 'diseases', 'treatment', 'treatments',
            'symptom', 'symptoms', 'study', 'studies', 'case', 'cases', 'review',
            'research', 'clinical', 'medical', 'medicine', 'doctor', 'hospital',
            'therapy', 'therapeutic', 'diagnosis', 'diagnoses', 'diagnosed', 'effect',
            'effective', 'efficacy', 'outcome', 'outcomes', 'result', 'results'
        }
        
        # Combine all stopwords
        self.all_stopwords = self.stopwords.union(self.medical_stopwords)
        
    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from a natural language query
        
        Args:
            query: Natural language query string
            
        Returns:
            List of extracted keywords
        """
        # Process the query with spaCy
        doc = self.nlp(query)
        
        # Initialize keyword candidates
        keyword_candidates = []
        
        # Extract noun chunks (noun phrases)
        for chunk in doc.noun_chunks:
            # Clean the chunk text and check if it's valid
            cleaned_chunk = self._clean_text(chunk.text)
            if cleaned_chunk and len(cleaned_chunk.split()) <= 3:  # Limit to 3-word phrases max
                keyword_candidates.append(cleaned_chunk)
        
        # Extract named entities
        for ent in doc.ents:
            # Only include certain entity types relevant to medical research
            if ent.label_ in ['DISEASE', 'CHEMICAL', 'MEDCOND', 'PROCEDURE', 'ANATOMY', 
                             'PROTEIN', 'GENE', 'PHYS', 'MEDPROC', 'ORG', 'GPE']:
                cleaned_ent = self._clean_text(ent.text)
                if cleaned_ent:
                    keyword_candidates.append(cleaned_ent)
        
        # Add important single tokens (mainly for non-entity medical terms)
        for token in doc:
            # Include nouns, adjectives, and verbs with high importance
            if (token.pos_ in ['NOUN', 'PROPN'] or 
                (token.pos_ in ['ADJ', 'VERB'] and token.is_stop is False)):
                # Check for domain relevance using POS and importance
                if (not self._is_stopword(token.text) and 
                    (token.is_alpha and len(token.text) > 2)):
                    keyword_candidates.append(token.text.lower())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keyword_candidates:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_keywords.append(kw)
        
        # Filter out stopwords and very short terms
        filtered_keywords = [kw for kw in unique_keywords 
                           if not self._is_stopword(kw) and len(kw) > 2]
        
        return filtered_keywords
    
    def expand_keywords(self, keywords: List[str]) -> Dict[str, List[str]]:
        """
        Expand keywords with synonyms from various sources
        
        Args:
            keywords: List of keywords to expand
            
        Returns:
            Dictionary mapping each keyword to its synonyms
        """
        expanded_terms = {}
        
        for keyword in keywords:
            synonyms = set()
            
            # Get WordNet synonyms
            if self.use_wordnet:
                wordnet_synonyms = self._get_wordnet_synonyms(keyword)
                synonyms.update(wordnet_synonyms)
            
            # Get UMLS synonyms for medical terms
            if self.use_umls and self.umls_api_key:
                umls_synonyms = self._get_umls_synonyms(keyword)
                synonyms.update(umls_synonyms)
            
            # Remove the original keyword from synonyms
            if keyword in synonyms:
                synonyms.remove(keyword)
            
            # Limit the number of synonyms
            synonym_list = list(synonyms)[:self.max_synonyms]
            expanded_terms[keyword] = synonym_list
        
        return expanded_terms
    
    def get_expanded_query_terms(self, query: str) -> Dict[str, List[str]]:
        """
        Process a query to extract keywords and their synonyms
        
        Args:
            query: Natural language query
            
        Returns:
            Dictionary of extracted keywords and their synonyms
        """
        # Extract keywords from query
        keywords = self.extract_keywords(query)
        
        # Expand keywords with synonyms
        expanded_terms = self.expand_keywords(keywords)
        
        return expanded_terms
    
    def generate_search_combinations(self, expanded_terms: Dict[str, List[str]], 
                                    max_combinations: int = 8) -> List[List[str]]:
        """
        Generate combinations of original terms and synonyms for search
        
        Args:
            expanded_terms: Dictionary of terms and their synonyms
            max_combinations: Maximum number of combinations to generate
            
        Returns:
            List of term combinations for search
        """
        # Prepare terms for combination generation
        term_options = []
        for original_term, synonyms in expanded_terms.items():
            # Always include the original term as an option
            term_choices = [original_term] + synonyms
            term_options.append(term_choices)
        
        # Generate all possible combinations
        all_combinations = list(itertools.product(*term_options))
        
        # Limit the number of combinations
        if len(all_combinations) > max_combinations:
            # Select a diverse subset of combinations
            # We'll take the first one (all original terms) and sample from the rest
            first_combo = all_combinations[0]  # All original terms
            sampled_combos = self._sample_diverse_combinations(all_combinations[1:], max_combinations-1)
            selected_combinations = [first_combo] + sampled_combos
        else:
            selected_combinations = all_combinations
        
        return [list(combo) for combo in selected_combinations]
    
    @lru_cache(maxsize=1024)
    def _get_wordnet_synonyms(self, term: str) -> Set[str]:
        """
        Get synonyms from WordNet with caching
        
        Args:
            term: Term to find synonyms for
            
        Returns:
            Set of synonyms
        """
        synonyms = set()
        
        # Handle multi-word terms
        if ' ' in term:
            # For multi-word terms, we don't use WordNet directly
            return synonyms
        
        # Get synsets for the term
        synsets = wn.synsets(term)
        
        # Extract lemma names (synonyms)
        for synset in synsets:
            for lemma in synset.lemmas():
                synonym = lemma.name().replace('_', ' ')
                # Only add if it's not too different in length
                if abs(len(synonym) - len(term)) <= 5:
                    synonyms.add(synonym)
                    
        return synonyms
    
    @lru_cache(maxsize=1024)
    def _get_umls_synonyms(self, term: str) -> Set[str]:
        """
        Get medical synonyms from UMLS with caching
        
        Args:
            term: Medical term to find synonyms for
            
        Returns:
            Set of medical synonyms
        """
        # In a real implementation, you would call the UMLS API
        # This is a placeholder that would be replaced with actual API calls
        # Example with requests library:
        '''
        try:
            response = requests.get(
                "https://uts-ws.nlm.nih.gov/rest/search/current",
                params={
                    "string": term,
                    "apiKey": self.umls_api_key,
                    "searchType": "exact"
                }
            )
            if response.status_code == 200:
                data = response.json()
                results = data.get('result', {}).get('results', [])
                synonyms = set()
                for result in results[:5]:  # Limit to top 5 results
                    cui = result.get('ui')
                    if cui:
                        concept_response = requests.get(
                            f"https://uts-ws.nlm.nih.gov/rest/content/current/CUI/{cui}/atoms",
                            params={"apiKey": self.umls_api_key}
                        )
                        if concept_response.status_code == 200:
                            atoms = concept_response.json().get('result', [])
                            for atom in atoms:
                                name = atom.get('name')
                                if name and name.lower() != term.lower():
                                    synonyms.add(name)
                return synonyms
        except Exception as e:
            print(f"UMLS API error: {e}")
        '''
        
        # For this example, return empty set since we don't have actual API access
        return set()
    
    def _sample_diverse_combinations(self, combinations: List[Tuple], 
                                   n_samples: int) -> List[Tuple]:
        """
        Sample a diverse subset of term combinations to ensure variety
        
        Args:
            combinations: List of term combinations
            n_samples: Number of combinations to sample
            
        Returns:
            List of sampled term combinations
        """
        if n_samples >= len(combinations):
            return combinations
        
        # Convert combinations to strings for easier comparison
        combo_strings = [' '.join(combo) for combo in combinations]
        
        # Calculate similarity between combinations
        selected_indices = [0]  # Start with the first combination
        
        while len(selected_indices) < n_samples:
            max_min_distance = -1
            next_index = -1
            
            # Find the combination that is most different from already selected ones
            for i in range(len(combinations)):
                if i in selected_indices:
                    continue
                    
                # Calculate minimum distance to any selected combination
                min_distance = float('inf')
                for j in selected_indices:
                    # Simple distance metric: number of different words
                    distance = sum(1 for a, b in zip(combinations[i], combinations[j]) if a != b)
                    min_distance = min(min_distance, distance)
                
                # Update if this combination is more diverse
                if min_distance > max_min_distance:
                    max_min_distance = min_distance
                    next_index = i
            
            selected_indices.append(next_index)
        
        return [combinations[i] for i in selected_indices]
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing punctuation and extra whitespace
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _is_stopword(self, word: str) -> bool:
        """
        Check if a word is a stopword (common word with little search value)
        
        Args:
            word: Word to check
            
        Returns:
            True if the word is a stopword
        """
        return word.lower() in self.all_stopwords


# Example usage
if __name__ == "__main__":
    # Initialize processor (without actual UMLS API key)
    processor = MedicalQueryProcessor(use_umls=False, use_wordnet=True)
    
    # Example medical queries
    queries = [
        "What are the latest treatments for atrial fibrillation in elderly patients?",
        "Show me studies on COVID-19 and myocarditis in athletes",
        "Find papers discussing machine learning applications for diabetic retinopathy screening"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        
        # Extract keywords
        keywords = processor.extract_keywords(query)
        print(f"Extracted keywords: {keywords}")
        
        # Expand with synonyms
        expanded_terms = processor.expand_keywords(keywords)
        print(f"Expanded terms: {expanded_terms}")
        
        # Generate search combinations
        combinations = processor.generate_search_combinations(expanded_terms, max_combinations=3)
        print(f"Search combinations (limited to 3):")
        for i, combo in enumerate(combinations):
            print(f"  Combination {i+1}: {combo}")
