import re
import string
from typing import List, Dict, Set, Tuple
from collections import defaultdict, Counter
import itertools
from functools import lru_cache

# Try importing optional dependencies
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.corpus import wordnet as wn
    from nltk.stem import WordNetLemmatizer
    from nltk.tokenize import word_tokenize
    NLTK_AVAILABLE = True
    
    # Try to download necessary NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        try:
            nltk.download('punkt', quiet=True)
        except:
            pass
    
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        try:
            nltk.download('stopwords', quiet=True)
        except:
            pass
    
    try:
        nltk.data.find('corpora/wordnet')
    except LookupError:
        try:
            nltk.download('wordnet', quiet=True)
        except:
            pass
            
    try:
        nltk.data.find('taggers/averaged_perceptron_tagger')
    except LookupError:
        try:
            nltk.download('averaged_perceptron_tagger', quiet=True)
        except:
            pass
    
    # Initialize WordNet lemmatizer if available
    try:
        lemmatizer = WordNetLemmatizer()
    except:
        lemmatizer = None
        
except ImportError:
    NLTK_AVAILABLE = False


class MedicalQueryProcessor:
    """
    Extract and expand keywords from natural language medical queries.
    Fallback to simple regex-based extraction if advanced NLP libraries aren't available.
    """
    
    def __init__(self, use_umls: bool = False, use_wordnet: bool = True, 
                 umls_api_key: str = None, max_synonyms: int = 3):
        """
        Initialize the query processor with desired expansion sources.
        
        Args:
            use_umls: Whether to use UMLS for medical term expansion
            use_wordnet: Whether to use WordNet for general term expansion
            umls_api_key: API key for UMLS Terminology Services
            max_synonyms: Maximum number of synonyms to add per term
        """
        self.spacy_nlp = None
        
        # Try to load spaCy model if available
        if SPACY_AVAILABLE:
            try:
                # Try loading models in order of preference
                model_names = ["en_core_sci_lg", "en_core_sci_md", "en_core_web_md", "en_core_web_sm", "en"]
                
                for model_name in model_names:
                    try:
                        self.spacy_nlp = spacy.load(model_name)
                        print(f"Loaded spaCy model: {model_name}")
                        break
                    except:
                        continue
                        
            except Exception as e:
                print(f"Error loading spaCy model: {e}")
                self.spacy_nlp = None
        
        # Setup expansion options
        self.use_umls = use_umls and umls_api_key is not None
        self.use_wordnet = use_wordnet and NLTK_AVAILABLE
        self.umls_api_key = umls_api_key
        self.max_synonyms = max_synonyms
        
        # Build stopword list
        self.stopwords = self._build_stopwords()
        
        # Medical stopwords to filter out from results
        self.medical_stopwords = {
            'patient', 'patients', 'disease', 'diseases', 'treatment', 'treatments',
            'symptom', 'symptoms', 'study', 'studies', 'case', 'cases', 'review',
            'research', 'clinical', 'medical', 'medicine', 'doctor', 'hospital',
            'therapy', 'therapeutic', 'diagnosis', 'diagnoses', 'diagnosed', 'effect',
            'effective', 'efficacy', 'outcome', 'outcomes', 'result', 'results'
        }
        
        # Common medical n-grams (these should be preserved during processing)
        self.common_med_ngrams = {
            'heart failure', 'blood pressure', 'diabetes mellitus',
            'covid 19', 'machine learning', 'artificial intelligence',
            'deep learning', 'neural network', 'atrial fibrillation',
            'cancer', 'alzheimer', 'parkinson', 'stroke', 'myocardial infarction',
            'hypertension', 'breast cancer', 'lung cancer'
        }
        
        # Combine all stopwords
        self.all_stopwords = self.stopwords.union(self.medical_stopwords)
        
        # Initialize lemmatizer if available
        self.lemmatizer = lemmatizer if NLTK_AVAILABLE else None
    
    def _build_stopwords(self) -> Set[str]:
        """
        Build a comprehensive stopword list based on available resources
        """
        # Start with a minimal set of common stopwords
        minimal_stopwords = {
            'a', 'an', 'the', 'and', 'or', 'but', 'if', 'because', 'as', 'what', 
            'when', 'where', 'how', 'which', 'who', 'whom', 'this', 'that', 'these', 
            'those', 'then', 'just', 'so', 'than', 'such', 'both', 'through', 'about', 
            'for', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 
            'had', 'having', 'do', 'does', 'did', 'doing', 'to', 'from', 'by', 'on',
            'at', 'in', 'with', 'about', 'against', 'between', 'into', 'through',
            'during', 'before', 'after', 'above', 'below', 'up', 'down', 'of',
            'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here',
            'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
            'than', 'too', 'very'
        }
        
        # Add NLTK stopwords if available
        if NLTK_AVAILABLE:
            try:
                nltk_stopwords = set(stopwords.words('english'))
                return minimal_stopwords.union(nltk_stopwords)
            except:
                pass
        
        return minimal_stopwords
        
    def extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from a natural language query
        
        Args:
            query: Natural language query string
            
        Returns:
            List of extracted keywords
        """
        # Clean the query
        query = self._clean_text(query)
        
        # Check for common medical n-grams first
        preserved_ngrams = []
        query_lower = query.lower()
        for ngram in self.common_med_ngrams:
            if ngram in query_lower:
                preserved_ngrams.append(ngram)
                # Replace with placeholder to prevent splitting
                query_lower = query_lower.replace(ngram, f"PLACEHOLDER_{len(preserved_ngrams)}")
        
        # Use different extraction methods based on available libraries
        if self.spacy_nlp is not None:
            keywords = self._extract_with_spacy(query)
        elif NLTK_AVAILABLE:
            keywords = self._extract_with_nltk(query)
        else:
            keywords = self._extract_with_regex(query)
        
        # Add preserved n-grams back to keywords
        keywords.extend(preserved_ngrams)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_keywords.append(kw)
        
        # Filter out stopwords and very short terms
        filtered_keywords = [kw for kw in unique_keywords 
                           if not self._is_stopword(kw) and len(kw) > 2]
        
        return filtered_keywords
    
    def _extract_with_spacy(self, query: str) -> List[str]:
        """
        Extract keywords using spaCy NLP model
        """
        doc = self.spacy_nlp(query)
        keywords = []
        
        # Extract noun chunks (noun phrases)
        for chunk in doc.noun_chunks:
            clean_chunk = self._clean_text(chunk.text)
            if clean_chunk and len(clean_chunk.split()) <= 3:
                keywords.append(clean_chunk)
        
        # Extract named entities
        for ent in doc.ents:
            clean_ent = self._clean_text(ent.text)
            if clean_ent:
                keywords.append(clean_ent)
        
        # Add important single tokens (mainly for non-entity medical terms)
        for token in doc:
            # Include nouns, adjectives, and verbs with high importance
            if (token.pos_ in ['NOUN', 'PROPN'] or 
                (token.pos_ in ['ADJ', 'VERB'] and not token.is_stop)):
                if (token.is_alpha and len(token.text) > 2):
                    keywords.append(token.text.lower())
        
        return keywords
    
    def _extract_with_nltk(self, query: str) -> List[str]:
        """
        Extract keywords using NLTK
        """
        keywords = []
        
        # Tokenize the query
        tokens = word_tokenize(query)
        
        # Get part-of-speech tags
        pos_tags = nltk.pos_tag(tokens)
        
        # Extract nouns, adjectives, and key verbs
        important_words = []
        for word, tag in pos_tags:
            # Include nouns, adjectives, and some verbs
            if tag.startswith('NN') or tag.startswith('JJ') or tag in ['VB', 'VBG']:
                if len(word) > 2 and word.lower() not in self.all_stopwords:
                    important_words.append(word.lower())
        
        # Add single words
        keywords.extend(important_words)
        
        # Extract potential noun phrases (adjacent noun/adj combinations)
        phrases = []
        i = 0
        while i < len(pos_tags) - 1:
            # Look for adjective + noun or noun + noun patterns
            if ((pos_tags[i][1].startswith('JJ') and pos_tags[i+1][1].startswith('NN')) or
                (pos_tags[i][1].startswith('NN') and pos_tags[i+1][1].startswith('NN'))):
                phrase = pos_tags[i][0] + ' ' + pos_tags[i+1][0]
                if not self._is_stopword(phrase):
                    phrases.append(phrase.lower())
                # Check for 3-word phrases
                if i < len(pos_tags) - 2 and pos_tags[i+2][1].startswith('NN'):
                    phrase3 = phrase + ' ' + pos_tags[i+2][0]
                    if not self._is_stopword(phrase3):
                        phrases.append(phrase3.lower())
            i += 1
        
        keywords.extend(phrases)
        
        return keywords
    
    def _extract_with_regex(self, query: str) -> List[str]:
        """
        Extract keywords using basic regex patterns when no NLP libraries are available
        """
        keywords = []
        
        # Convert to lowercase and tokenize by whitespace
        words = query.lower().split()
        
        # Clean individual words
        words = [self._clean_text(word) for word in words]
        words = [word for word in words if word and not self._is_stopword(word)]
        
        # Add individual words
        keywords.extend([w for w in words if len(w) > 2])
        
        # Try to identify potential phrases (adjacent words)
        for i in range(len(words) - 1):
            phrase = words[i] + ' ' + words[i+1]
            if not self._is_stopword(phrase) and len(phrase) > 5:
                keywords.append(phrase)
            
            # Try triplets too
            if i < len(words) - 2:
                phrase3 = words[i] + ' ' + words[i+1] + ' ' + words[i+2]
                if not self._is_stopword(phrase3) and len(phrase3) > 8:
                    keywords.append(phrase3)
        
        return keywords
    
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
            
            # Get UMLS synonyms for medical terms (if API key provided)
            if self.use_umls and self.umls_api_key:
                umls_synonyms = self._get_umls_synonyms(keyword)
                synonyms.update(umls_synonyms)
            
            # Remove the original keyword from synonyms
            if keyword in synonyms:
                synonyms.remove(keyword)
            
            # Add word form variations even if no synonyms found
            if len(synonyms) == 0 and ' ' not in keyword and self.lemmatizer:
                # Add singular/plural forms
                if keyword.endswith('s'):
                    singular = keyword[:-1]
                    if len(singular) > 2:  # Avoid too short words
                        synonyms.add(singular)
                else:
                    synonyms.add(keyword + 's')
                
                # Add variations using lemmatizer if available
                if self.lemmatizer:
                    lemma = self.lemmatizer.lemmatize(keyword)
                    if lemma != keyword:
                        synonyms.add(lemma)
            
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
        if ' ' in term or not NLTK_AVAILABLE:
            # We don't process multi-word terms with WordNet
            return synonyms
        
        try:
            # Get synsets for the term
            synsets = wn.synsets(term)
            
            # Extract lemma names (synonyms)
            for synset in synsets:
                for lemma in synset.lemmas():
                    synonym = lemma.name().replace('_', ' ')
                    # Only add if it's not too different in length
                    if abs(len(synonym) - len(term)) <= 5:
                        synonyms.add(synonym)
        except:
            pass
                    
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
        # This would be implemented with actual UMLS API calls
        # For this example, return empty set
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
        
        # Simple approach: take evenly spaced samples
        step = max(1, len(combinations) // n_samples)
        return [combinations[i] for i in range(0, len(combinations), step)][:n_samples]
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text by removing punctuation and extra whitespace
        
        Args:
            text: Text to clean
            
        Returns:
            Cleaned text
        """
        # Remove punctuation except hyphens between words
        text = re.sub(r'[^\w\s-]', ' ', text)
        
        # Keep hyphens between words but not at start/end
        text = re.sub(r'(\s)-|-(\s)|^-|-$', r'\1\2', text)
        
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
