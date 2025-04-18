"""
Example usage of the localknowledge library.
"""
from localknowledge.pubmed import PubMedClient
from localknowledge.medrxiv import MedRxivClient

def main():
    print("LocalKnowledge Library Demo")
    
    # Example PubMed usage
    pubmed = PubMedClient()
    print("Searching PubMed for 'covid'...")
    results = pubmed.search("covid", max_results=5)
    print(f"Found {len(results)} results")

    # Example medRxiv usage
    medrxiv = MedRxivClient()
    print("Searching medRxiv for 'covid'...")
    results = medrxiv.search("covid", max_results=5)
    print(f"Found {len(results)} results")

if __name__ == "__main__":
    main()
