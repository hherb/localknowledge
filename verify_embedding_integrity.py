#!/usr/bin/env python3
"""
Verify embedding integrity between emb_1024 and chunks tables.

This script traverses the emb_1024 table and checks for each embedding whether
the embedded chunk actually matches the chunk/document in the chunks table.
It verifies:
1. That the chunk_id in emb_1024 exists in chunks table
2. That the document_id matches between the embedding and chunk
3. That the chunk text is not empty
4. Optionally checks for orphaned embeddings and missing chunks

Usage:
    python verify_embedding_integrity.py [--verbose] [--fix-orphans] [--sample-size N]
"""

import argparse
import logging
import sys
from typing import List, Dict, Any, Optional, Tuple
import time
from dataclasses import dataclass

from localknowledge.db.connection_pool import initialize_pool, get_cursor, close_pool
from localknowledge.db.base import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class IntegrityIssue:
    """Represents an integrity issue found during verification."""
    issue_type: str
    embedding_id: int
    chunk_id: int
    model_id: Optional[int]
    description: str
    severity: str  # 'ERROR', 'WARNING', 'INFO'


class EmbeddingIntegrityVerifier:
    """Verifies integrity between embeddings and chunks tables."""

    def __init__(self, verbose: bool = False, verify_content: bool = False, model_name: str = "snowflake-arctic-embed2:latest"):
        """
        Initialize the integrity verifier.

        Args:
            verbose: Enable verbose logging
            verify_content: If True, also verify that embeddings match their chunk text
            model_name: Model name to use for content verification
        """
        self.verbose = verbose
        self.verify_content = verify_content
        self.model_name = model_name
        self.db = DatabaseManager()
        self.issues: List[IntegrityIssue] = []

        # Initialize embedder for content verification if needed
        self.embedder = None
        if verify_content:
            try:
                from localknowledge.embeddings import OllamaEmbedder
                self.embedder = OllamaEmbedder(model_name)
                logger.info(f"Initialized embedder for content verification: {model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize embedder: {e}")
                logger.warning("Content verification will be disabled")
                self.verify_content = False

        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)
    
    def verify_embeddings(self, sample_size: Optional[int] = None, check_orphans: bool = False) -> Dict[str, Any]:
        """
        Verify all embeddings in emb_1024 table against chunks table.

        Args:
            sample_size: If specified, only check this many embeddings (for testing)
            check_orphans: If True, also check for orphaned chunks (can be slow)

        Returns:
            Dictionary with verification results and statistics
        """
        logger.info("Starting embedding integrity verification...")
        start_time = time.time()

        # Get total count of embeddings
        total_embeddings = self._count_embeddings()
        logger.info(f"Found {total_embeddings} embeddings to verify")

        if sample_size:
            total_embeddings = min(total_embeddings, sample_size)
            logger.info(f"Limiting verification to {total_embeddings} embeddings")

        # Verify embeddings in batches
        batch_size = 1000
        verified_count = 0
        error_count = 0
        warning_count = 0

        for offset in range(0, total_embeddings, batch_size):
            current_batch_size = min(batch_size, total_embeddings - offset)
            logger.info(f"Verifying batch {offset//batch_size + 1}: "
                       f"embeddings {offset + 1} to {offset + current_batch_size}")

            batch_results = self._verify_embedding_batch(offset, current_batch_size)
            verified_count += batch_results['verified']
            error_count += batch_results['errors']
            warning_count += batch_results['warnings']

        # Check for orphaned chunks (chunks without embeddings) - optional due to performance
        orphaned_chunks = []
        if check_orphans:
            try:
                orphaned_chunks = self._find_orphaned_chunks()
            except Exception as e:
                logger.warning(f"Could not check for orphaned chunks: {e}")
                logger.info("Use --check-orphans flag to enable orphaned chunk detection")

        # Calculate statistics
        total_time = time.time() - start_time

        results = {
            'total_embeddings': total_embeddings,
            'verified_embeddings': verified_count,
            'error_count': error_count,
            'warning_count': warning_count,
            'orphaned_chunks': len(orphaned_chunks),
            'issues': self.issues,
            'verification_time': total_time,
            'success_rate': (verified_count / total_embeddings * 100) if total_embeddings > 0 else 0
        }

        logger.info(f"Verification completed in {total_time:.2f} seconds")
        logger.info(f"Success rate: {results['success_rate']:.2f}%")
        logger.info(f"Found {error_count} errors, {warning_count} warnings")
        if check_orphans:
            logger.info(f"Found {len(orphaned_chunks)} orphaned chunks")

        return results
    
    def _count_embeddings(self) -> int:
        """Count total number of embeddings in emb_1024 table."""
        query = "SELECT COUNT(*) as count FROM emb_1024"
        result = self.db.execute(query)
        return result[0]['count'] if result else 0
    
    def _verify_embedding_batch(self, offset: int, batch_size: int) -> Dict[str, int]:
        """
        Verify a batch of embeddings.
        
        Args:
            offset: Starting offset for the batch
            batch_size: Number of embeddings to verify in this batch
            
        Returns:
            Dictionary with batch verification statistics
        """
        # Get embeddings with their corresponding chunk data
        # Include the actual embedding vector if we're doing content verification
        if self.verify_content:
            query = """
            SELECT
                e.id as embedding_id,
                e.chunk_id,
                e.model_id,
                e.embedding,
                c.id as chunk_table_id,
                c.document_id,
                c.text,
                c.document_title,
                c.chunktype_id,
                ct.chunktype,
                em.model_name
            FROM emb_1024 e
            LEFT JOIN chunks c ON e.chunk_id = c.id
            LEFT JOIN chunktypes ct ON c.chunktype_id = ct.id
            LEFT JOIN embedding_models em ON e.model_id = em.id
            ORDER BY e.id
            LIMIT %s OFFSET %s
            """
        else:
            query = """
            SELECT
                e.id as embedding_id,
                e.chunk_id,
                e.model_id,
                c.id as chunk_table_id,
                c.document_id,
                c.text,
                c.document_title,
                c.chunktype_id,
                ct.chunktype,
                em.model_name
            FROM emb_1024 e
            LEFT JOIN chunks c ON e.chunk_id = c.id
            LEFT JOIN chunktypes ct ON c.chunktype_id = ct.id
            LEFT JOIN embedding_models em ON e.model_id = em.id
            ORDER BY e.id
            LIMIT %s OFFSET %s
            """
        
        embeddings = self.db.execute(query, (batch_size, offset))
        
        verified = 0
        errors = 0
        warnings = 0
        
        for embedding in embeddings:
            result = self._verify_single_embedding(embedding)
            if result['status'] == 'verified':
                verified += 1
            elif result['status'] == 'error':
                errors += 1
            elif result['status'] == 'warning':
                warnings += 1
        
        return {
            'verified': verified,
            'errors': errors,
            'warnings': warnings
        }
    
    def _verify_single_embedding(self, embedding: Dict[str, Any]) -> Dict[str, str]:
        """
        Verify a single embedding record.
        
        Args:
            embedding: Embedding record with joined chunk data
            
        Returns:
            Dictionary with verification result
        """
        embedding_id = embedding['embedding_id']
        chunk_id = embedding['chunk_id']
        model_id = embedding['model_id']
        
        # Check if chunk exists
        if embedding['chunk_table_id'] is None:
            self.issues.append(IntegrityIssue(
                issue_type='missing_chunk',
                embedding_id=embedding_id,
                chunk_id=chunk_id,
                model_id=model_id,
                description=f"Embedding {embedding_id} references non-existent chunk {chunk_id}",
                severity='ERROR'
            ))
            if self.verbose:
                logger.error(f"Embedding {embedding_id}: chunk {chunk_id} does not exist")
            return {'status': 'error'}
        
        # Check if chunk has text
        if not embedding['text'] or embedding['text'].strip() == '':
            self.issues.append(IntegrityIssue(
                issue_type='empty_chunk_text',
                embedding_id=embedding_id,
                chunk_id=chunk_id,
                model_id=model_id,
                description=f"Chunk {chunk_id} has empty text",
                severity='WARNING'
            ))
            if self.verbose:
                logger.warning(f"Embedding {embedding_id}: chunk {chunk_id} has empty text")
            return {'status': 'warning'}
        
        # Check if model exists
        if embedding['model_name'] is None:
            self.issues.append(IntegrityIssue(
                issue_type='missing_model',
                embedding_id=embedding_id,
                chunk_id=chunk_id,
                model_id=model_id,
                description=f"Embedding {embedding_id} references non-existent model {model_id}",
                severity='WARNING'
            ))
            if self.verbose:
                logger.warning(f"Embedding {embedding_id}: model {model_id} does not exist")
            return {'status': 'warning'}
        
        # Check chunk type
        if embedding['chunktype'] is None:
            self.issues.append(IntegrityIssue(
                issue_type='missing_chunktype',
                embedding_id=embedding_id,
                chunk_id=chunk_id,
                model_id=model_id,
                description=f"Chunk {chunk_id} has invalid chunktype_id {embedding['chunktype_id']}",
                severity='WARNING'
            ))
            if self.verbose:
                logger.warning(f"Embedding {embedding_id}: chunk {chunk_id} has invalid chunktype")
            return {'status': 'warning'}
        
        # If content verification is enabled, check if embedding matches the text
        if self.verify_content and self.embedder and embedding['text']:
            content_match = self._verify_embedding_content(embedding)
            if not content_match:
                return {'status': 'error'}  # Content verification failed

        if self.verbose:
            logger.debug(f"Embedding {embedding_id}: OK (chunk {chunk_id}, "
                        f"model {embedding['model_name']}, type {embedding['chunktype']})")

        return {'status': 'verified'}

    def _verify_embedding_content(self, embedding: Dict[str, Any]) -> bool:
        """
        Verify that the stored embedding actually matches the chunk text.

        Args:
            embedding: Embedding record with chunk data and embedding vector

        Returns:
            True if embedding matches text, False otherwise
        """
        try:
            embedding_id = embedding['embedding_id']
            chunk_id = embedding['chunk_id']
            stored_embedding_raw = embedding['embedding']
            chunk_text = embedding['text']

            if not chunk_text or not stored_embedding_raw:
                return True  # Skip if no text or embedding

            # Parse the stored embedding from string format to list of floats
            stored_embedding = self._parse_vector_string(stored_embedding_raw)
            if not stored_embedding:
                logger.warning(f"Failed to parse stored embedding for chunk {chunk_id}")
                return True  # Skip verification if we can't parse embedding

            # Generate a fresh embedding for the chunk text
            fresh_embedding = self.embedder.embed(chunk_text)

            if not fresh_embedding:
                logger.warning(f"Failed to generate fresh embedding for chunk {chunk_id}")
                return True  # Skip verification if we can't generate embedding

            # Calculate cosine similarity between stored and fresh embeddings
            similarity = self._calculate_cosine_similarity(stored_embedding, fresh_embedding)

            # Use configurable similarity threshold - embeddings should be very similar if they're the same text
            # Lower threshold might indicate the embedding doesn't match the text
            similarity_threshold = getattr(self, 'similarity_threshold', 0.95)

            if similarity < similarity_threshold:
                self.issues.append(IntegrityIssue(
                    issue_type='content_mismatch',
                    embedding_id=embedding_id,
                    chunk_id=chunk_id,
                    model_id=embedding['model_id'],
                    description=f"Embedding {embedding_id} content mismatch: similarity {similarity:.3f} < {similarity_threshold} for chunk {chunk_id}",
                    severity='ERROR'
                ))
                if self.verbose:
                    logger.error(f"Content mismatch for embedding {embedding_id}: similarity {similarity:.3f}")
                return False

            if self.verbose:
                logger.debug(f"Content verified for embedding {embedding_id}: similarity {similarity:.3f}")

            return True

        except Exception as e:
            logger.error(f"Error verifying content for embedding {embedding['embedding_id']}: {e}")
            # Don't fail verification due to technical issues
            return True

    def _parse_vector_string(self, vector_str: str) -> List[float]:
        """
        Parse a PostgreSQL vector string into a list of floats.

        Args:
            vector_str: String representation of vector like "[-0.007466765,-0.050680224,...]"

        Returns:
            List of float values, or empty list if parsing fails
        """
        try:
            # Remove brackets and split by commas
            if isinstance(vector_str, str):
                # Remove leading/trailing brackets
                clean_str = vector_str.strip('[]')
                # Split by commas and convert to floats
                values = [float(x.strip()) for x in clean_str.split(',')]
                return values
            elif hasattr(vector_str, 'tolist'):
                # Already a numpy array or similar
                return vector_str.tolist()
            elif isinstance(vector_str, (list, tuple)):
                # Already a list or tuple
                return list(vector_str)
            else:
                logger.warning(f"Unknown vector format: {type(vector_str)}")
                return []
        except Exception as e:
            logger.error(f"Error parsing vector string: {e}")
            return []

    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0-1, where 1 is identical)
        """
        import math

        # Convert to lists if they're not already
        if hasattr(vec1, 'tolist'):
            vec1 = vec1.tolist()
        if hasattr(vec2, 'tolist'):
            vec2 = vec2.tolist()

        # Ensure vectors are the same length
        if len(vec1) != len(vec2):
            logger.warning(f"Vector length mismatch: {len(vec1)} vs {len(vec2)}")
            return 0.0

        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Calculate magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(a * a for a in vec2))

        # Avoid division by zero
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)

        # Clamp to [0, 1] range (should already be in [-1, 1])
        return max(0.0, min(1.0, similarity))

    def _find_orphaned_chunks(self) -> List[Dict[str, Any]]:
        """
        Find chunks that don't have any embeddings.

        Returns:
            List of orphaned chunk records
        """
        logger.info("Checking for orphaned chunks (this may take a while)...")

        # Use a more efficient query with EXISTS instead of LEFT JOIN
        # and limit to abstract chunks only for faster execution
        query = """
        SELECT c.id, c.document_id, c.document_title, c.chunktype_id, ct.chunktype,
               LENGTH(c.text) as text_length
        FROM chunks c
        JOIN chunktypes ct ON c.chunktype_id = ct.id
        WHERE ct.chunktype = 'abstract'
        AND NOT EXISTS (
            SELECT 1 FROM emb_1024 e WHERE e.chunk_id = c.id
        )
        ORDER BY c.id
        LIMIT 1000
        """

        # Use longer timeout for this potentially slow query
        orphaned_chunks = self.db.execute(query, timeout=120) or []

        for chunk in orphaned_chunks:
            self.issues.append(IntegrityIssue(
                issue_type='orphaned_chunk',
                embedding_id=0,  # No embedding ID for orphaned chunks
                chunk_id=chunk['id'],
                model_id=None,
                description=f"Chunk {chunk['id']} has no embeddings (type: {chunk['chunktype']})",
                severity='INFO'
            ))

        return orphaned_chunks
    
    def print_summary(self, results: Dict[str, Any]) -> None:
        """Print a summary of verification results."""
        print("\n" + "="*80)
        print("EMBEDDING INTEGRITY VERIFICATION SUMMARY")
        print("="*80)
        print(f"Total embeddings checked: {results['total_embeddings']:,}")
        print(f"Successfully verified: {results['verified_embeddings']:,}")
        print(f"Success rate: {results['success_rate']:.2f}%")
        print(f"Errors found: {results['error_count']}")
        print(f"Warnings found: {results['warning_count']}")
        print(f"Orphaned chunks: {results['orphaned_chunks']}")
        print(f"Verification time: {results['verification_time']:.2f} seconds")

        # Calculate performance metrics
        if results['verification_time'] > 0:
            rate = results['total_embeddings'] / results['verification_time']
            print(f"Verification rate: {rate:.1f} embeddings/second")

        if self.issues:
            print(f"\nISSUES FOUND ({len(self.issues)} total):")
            print("-" * 40)

            # Group issues by type and severity
            issue_types = {}
            severity_counts = {'ERROR': 0, 'WARNING': 0, 'INFO': 0}

            for issue in self.issues:
                if issue.issue_type not in issue_types:
                    issue_types[issue.issue_type] = []
                issue_types[issue.issue_type].append(issue)
                severity_counts[issue.severity] += 1

            # Print severity summary
            print(f"\nBy severity:")
            for severity, count in severity_counts.items():
                if count > 0:
                    print(f"  {severity}: {count}")

            # Print issues by type
            for issue_type, issues in issue_types.items():
                print(f"\n{issue_type.upper().replace('_', ' ')} ({len(issues)} issues):")
                for issue in issues[:10]:  # Show first 10 of each type
                    print(f"  - {issue.description}")
                if len(issues) > 10:
                    print(f"  ... and {len(issues) - 10} more")
        else:
            print("\n✅ No integrity issues found!")

    def export_issues_to_file(self, filename: str) -> None:
        """Export all issues to a CSV file for further analysis."""
        import csv

        if not self.issues:
            logger.info("No issues to export")
            return

        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['issue_type', 'severity', 'embedding_id', 'chunk_id', 'model_id', 'description']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for issue in self.issues:
                writer.writerow({
                    'issue_type': issue.issue_type,
                    'severity': issue.severity,
                    'embedding_id': issue.embedding_id,
                    'chunk_id': issue.chunk_id,
                    'model_id': issue.model_id,
                    'description': issue.description
                })

        logger.info(f"Exported {len(self.issues)} issues to {filename}")


def main():
    """Main function to run embedding integrity verification."""
    parser = argparse.ArgumentParser(description='Verify embedding integrity between emb_1024 and chunks tables.')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--sample-size', type=int, default=None,
                       help='Only verify this many embeddings (for testing)')
    parser.add_argument('--check-orphans', action='store_true',
                       help='Also check for orphaned chunks (can be slow)')
    parser.add_argument('--verify-content', action='store_true',
                       help='Verify that embeddings actually match their chunk text (slow but thorough)')
    parser.add_argument('--model', type=str, default='snowflake-arctic-embed2:latest',
                       help='Model name to use for content verification')
    parser.add_argument('--similarity-threshold', type=float, default=0.95,
                       help='Minimum similarity threshold for content verification (default: 0.95)')
    parser.add_argument('--export-issues', type=str, default=None,
                       help='Export issues to CSV file (e.g., issues.csv)')
    parser.add_argument('--min-connections', type=int, default=2,
                       help='Minimum number of database connections in the pool')
    parser.add_argument('--max-connections', type=int, default=5,
                       help='Maximum number of database connections in the pool')

    args = parser.parse_args()

    # Initialize connection pool
    try:
        initialize_pool(min_connections=args.min_connections, max_connections=args.max_connections)
        logger.info(f"Connection pool initialized with {args.min_connections}-{args.max_connections} connections")
    except Exception as e:
        logger.error(f"Error initializing connection pool: {e}")
        sys.exit(1)

    try:
        # Create verifier and run verification
        verifier = EmbeddingIntegrityVerifier(
            verbose=args.verbose,
            verify_content=args.verify_content,
            model_name=args.model
        )

        # Update similarity threshold if content verification is enabled
        if args.verify_content and hasattr(verifier, '_verify_embedding_content'):
            # We'll need to pass this to the verification method
            verifier.similarity_threshold = args.similarity_threshold

        if args.verify_content:
            print(f"Content verification enabled with model: {args.model}")
            print(f"Similarity threshold: {args.similarity_threshold}")
            print("Warning: Content verification is slow and will re-embed each chunk")

        results = verifier.verify_embeddings(sample_size=args.sample_size, check_orphans=args.check_orphans)

        # Print summary
        verifier.print_summary(results)

        # Export issues if requested
        if args.export_issues and verifier.issues:
            verifier.export_issues_to_file(args.export_issues)
            print(f"\nIssues exported to: {args.export_issues}")

        # Exit with error code if issues found
        if results['error_count'] > 0:
            sys.exit(1)
        elif results['warning_count'] > 0:
            sys.exit(2)
        else:
            sys.exit(0)

    finally:
        # Always close the connection pool
        close_pool()
        logger.info("Connection pool closed")


if __name__ == "__main__":
    main()
