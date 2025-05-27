import requests
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from typing import Dict, Optional, List, Any

from localknowledge.db.document import DocumentDatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Function to retrieve problematic PMIDs from the document database
def get_problematic_pmids(doc_db: DocumentDatabaseManager, limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Retrieve documents with missing details from the database.

    Args:
        doc_db: Document database manager
        limit: Maximum number of records to retrieve

    Returns:
        List of documents with missing details
    """
    query = """
    SELECT d.id, d.external_id as pmid, d.doi, d.title
    FROM document d
    JOIN sources s ON d.source_id = s.id
    WHERE d.missing_details = TRUE AND s.name = 'pubmed'
    LIMIT %s
    """
    return doc_db.execute(query, (limit,))

# 1. Europe PMC API
def fetch_from_europepmc(pmid=None, doi=None) -> Optional[Dict]:
    """Fetch article metadata from Europe PMC API"""
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    if pmid:
        query = f"ext_id:{pmid} AND src:med"
    elif doi:
        query = f"doi:\"{doi}\""
    else:
        return None

    params = {
        "query": query,
        "format": "json",
        "resultType": "core"
    }

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("resultList", {}).get("result") and len(data["resultList"]["result"]) > 0:
                article = data["resultList"]["result"][0]
                return {
                    "source": "europepmc",
                    "abstract": article.get("abstractText"),
                    "doi": article.get("doi"),
                    "pmid": article.get("pmid"),
                    "title": article.get("title")
                }
        return None
    except Exception as e:
        logger.error(f"Europe PMC API error: {e}")
        return None

# 2. Semantic Scholar API
def fetch_from_semanticscholar(pmid=None, doi=None) -> Optional[Dict]:
    """Fetch article metadata from Semantic Scholar API"""
    base_url = "https://api.semanticscholar.org/v1"

    if pmid:
        endpoint = f"{base_url}/paper/pmid:{pmid}"
    elif doi:
        endpoint = f"{base_url}/paper/{doi}"
    else:
        return None

    headers = {"Accept": "application/json"}

    try:
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            article = response.json()
            return {
                "source": "semanticscholar",
                "abstract": article.get("abstract"),
                "doi": article.get("doi"),
                "pmid": article.get("pmid"),
                "title": article.get("title")
            }
        return None
    except Exception as e:
        logger.error(f"Semantic Scholar API error: {e}")
        return None

# 3. Crossref API
def fetch_from_crossref(doi) -> Optional[Dict]:
    """Fetch article metadata from Crossref API"""
    if not doi:
        return None

    base_url = f"https://api.crossref.org/works/{doi}"
    headers = {"Accept": "application/json"}

    try:
        response = requests.get(base_url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            article = data.get("message", {})

            # Crossref doesn't typically include abstract but may have other metadata
            return {
                "source": "crossref",
                "abstract": None,  # Usually None from Crossref
                "doi": article.get("DOI"),
                "pmid": None,  # Crossref doesn't provide PMID
                "title": article.get("title", [None])[0] if article.get("title") else None
            }
        return None
    except Exception as e:
        logger.error(f"Crossref API error: {e}")
        return None

# 4. Unpaywall API
def fetch_from_unpaywall(doi) -> Optional[Dict]:
    """Try to get open access PDFs via Unpaywall which might have abstracts"""
    if not doi:
        return None

    base_url = f"https://api.unpaywall.org/v2/{doi}"
    params = {"email": "your.email@example.com"}  # Required by Unpaywall

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            # Unpaywall doesn't provide abstracts directly but has links to OA versions
            best_oa_url = data.get("best_oa_location", {}).get("url_for_pdf")

            result = {
                "source": "unpaywall",
                "abstract": None,
                "doi": data.get("doi"),
                "pmid": None,
                "title": data.get("title"),
                "oa_url": best_oa_url
            }

            # If we have an OA URL, we could potentially extract the abstract from PDF
            # But that would require additional PDF processing libraries
            return result
        return None
    except Exception as e:
        logger.error(f"Unpaywall API error: {e}")
        return None

# 5. arXiv API (for preprints that might be in PubMed)
def fetch_from_arxiv(title) -> Optional[Dict]:
    """Search arXiv for matching papers by title"""
    if not title:
        return None

    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"ti:\"{title}\"",
        "max_results": 1
    }

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            # Parse XML response
            soup = BeautifulSoup(response.content, "xml")
            entry = soup.find("entry")

            if not entry:
                return None

            abstract = entry.find("summary")
            abstract_text = abstract.text if abstract else None

            return {
                "source": "arxiv",
                "abstract": abstract_text,
                "doi": None,  # arXiv might not have DOI
                "pmid": None,  # arXiv doesn't have PMID
                "title": entry.find("title").text if entry.find("title") else None
            }
        return None
    except Exception as e:
        logger.error(f"arXiv API error: {e}")
        return None

# 6. CORE API (Open access aggregator)
def fetch_from_core(title=None, doi=None) -> Optional[Dict]:
    """Search CORE (core.ac.uk) for papers"""
    if not (title or doi):
        return None

    base_url = "https://core.ac.uk/api/v2/search"
    api_key = "YOUR_CORE_API_KEY"  # Register for free at core.ac.uk

    query = f"doi:{doi}" if doi else f"title:({title})"

    params = {
        "q": query,
        "apiKey": api_key
    }

    try:
        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("data") and len(data["data"]) > 0:
                article = data["data"][0]
                return {
                    "source": "core",
                    "abstract": article.get("description"),
                    "doi": article.get("doi"),
                    "pmid": None,  # CORE doesn't typically provide PMID
                    "title": article.get("title")
                }
        return None
    except Exception as e:
        logger.error(f"CORE API error: {e}")
        return None

# Main function to try all sources for a single article
def fetch_metadata_from_all_sources(pmid=None, doi=None, title=None) -> Dict:
    """Try all sources and return the best result"""
    sources = []

    # Add sources in priority order (first source with good abstract wins)
    if pmid or doi:
        sources.append(fetch_from_europepmc(pmid, doi))
    if pmid or doi:
        sources.append(fetch_from_semanticscholar(pmid, doi))
    if doi:
        sources.append(fetch_from_crossref(doi))
    if doi:
        sources.append(fetch_from_unpaywall(doi))
    if title:
        sources.append(fetch_from_arxiv(title))
    if title or doi:
        sources.append(fetch_from_core(title, doi))

    # Remove None values
    sources = [s for s in sources if s]

    # Return the first source with a non-empty abstract
    for source in sources:
        if source.get("abstract"):
            return source

    # If no source has abstract but we have some metadata, return the first source
    return sources[0] if sources else None

# Update database with the best metadata found
def update_database(doc_db: DocumentDatabaseManager, document_id: int, pmid: str, metadata: Dict[str, Any]) -> bool:
    """
    Update document with metadata from external sources.

    Args:
        doc_db: Document database manager
        document_id: Internal document ID
        pmid: PubMed ID
        metadata: Metadata from external source

    Returns:
        True if update was successful, False otherwise
    """
    if not metadata or not metadata.get("abstract"):
        return False

    try:
        query = """
        UPDATE document
        SET abstract = %s,
            updated_date = CURRENT_TIMESTAMP,
            missing_details = FALSE
        WHERE id = %s
        """
        doc_db.execute(query, (
            metadata["abstract"],
            document_id
        ), commit=True)

        # Log the source of the metadata
        logger.info(f"Updated PMID {pmid} with abstract from {metadata['source']}")
        return True
    except Exception as e:
        logger.error(f"Database update error for PMID {pmid}: {e}")
        return False

# Process a batch of problematic articles
def process_batch(documents: List[Dict[str, Any]], doc_db: DocumentDatabaseManager, max_workers: int = 5) -> int:
    """
    Process a batch of documents with missing details.

    Args:
        documents: List of documents with missing details
        doc_db: Document database manager
        max_workers: Maximum number of concurrent workers

    Returns:
        Number of successfully updated documents
    """
    success_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        for doc in documents:
            document_id = doc["id"]
            pmid = doc["pmid"]
            doi = doc["doi"]
            title = doc["title"]

            # Submit task to executor
            future = executor.submit(
                process_single_document,
                doc_db,
                document_id,
                pmid,
                doi,
                title
            )
            futures.append((future, pmid))

            # Respect rate limits with a small delay
            time.sleep(0.1)

        # Process results as they complete
        for future, pmid in futures:
            try:
                success = future.result()
                if success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error processing PMID {pmid}: {e}")

    return success_count

def process_single_document(doc_db: DocumentDatabaseManager, document_id: int, pmid: str, doi: str, title: str) -> bool:
    """
    Process a single document to update its details.

    Args:
        doc_db: Document database manager
        document_id: Internal document ID
        pmid: PubMed ID
        doi: DOI
        title: Document title

    Returns:
        True if update was successful, False otherwise
    """
    # Try all sources
    metadata = fetch_metadata_from_all_sources(pmid, doi, title)

    if metadata and metadata.get("abstract"):
        if update_database(doc_db, document_id, pmid, metadata):
            logger.info(f"Successfully updated PMID {pmid} from {metadata['source']}")
            return True
    else:
        logger.warning(f"Could not find metadata for PMID {pmid} from any source")

    return False

# Main execution function
def fix_missing_abstracts(batch_size: int = 100, limit: int = 1000) -> int:
    """
    Main function to fix documents with missing details.

    Args:
        batch_size: Number of documents to process in each batch
        limit: Maximum number of documents to process in total

    Returns:
        Number of successfully updated documents
    """
    doc_db = DocumentDatabaseManager()

    try:
        # Get problematic PMIDs
        problematic_docs = get_problematic_pmids(doc_db, limit=limit)

        if not problematic_docs:
            logger.info("No documents with missing details found")
            return 0

        logger.info(f"Found {len(problematic_docs)} documents with missing details")

        # Process in batches
        total_processed = 0

        for i in range(0, len(problematic_docs), batch_size):
            batch_docs = problematic_docs[i:i+batch_size]
            fixed = process_batch(batch_docs, doc_db)
            total_processed += fixed
            logger.info(f"Batch {i//batch_size + 1}: Fixed {fixed}/{len(batch_docs)} documents")

        logger.info(f"Total documents fixed: {total_processed}/{len(problematic_docs)}")
        return total_processed
    except Exception as e:
        logger.error(f"Error fixing missing details: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0
    finally:
        doc_db.close()

def mark_documents_for_update(doc_db: DocumentDatabaseManager, source_name: str = 'pubmed',
                             condition: str = "abstract IS NULL") -> int:
    """
    Mark documents that need updating by setting the missing_details flag.

    Args:
        doc_db: Document database manager
        source_name: Name of the source (e.g., 'pubmed')
        condition: SQL condition to identify documents that need updating

    Returns:
        Number of documents marked for update
    """
    query = f"""
    UPDATE document d
    SET missing_details = TRUE
    FROM sources s
    WHERE d.source_id = s.id
    AND s.name = %s
    AND {condition}
    RETURNING d.id
    """

    try:
        result = doc_db.execute(query, (source_name,), commit=True)
        count = len(result) if result else 0
        logger.info(f"Marked {count} documents for update")
        return count
    except Exception as e:
        logger.error(f"Error marking documents for update: {e}")
        return 0

if __name__ == "__main__":
    # First mark documents that need updating
    doc_db = DocumentDatabaseManager()
    try:
        # Mark documents with missing abstracts
        mark_documents_for_update(doc_db, condition="abstract IS NULL OR abstract = ''")
        # You could add more conditions here if needed
    finally:
        doc_db.close()

    # Then fix the marked documents
    fix_missing_abstracts()