import re
from typing import List, Tuple, Dict, Optional


class MarkdownChunker:
    """
    A tool for chunking markdown text into sections based on headings and size constraints.
    
    Chunks text such that:
    - Chunks are based on markdown heading structure
    - No chunk exceeds max_size
    - Chunks are not smaller than min_size unless unavoidable
    - When expanding a small chunk, it starts at a sentence boundary
    - Headings are always kept with their content
    """
    
    def __init__(self, min_size: int = 200, max_size: int = 1000):
        """
        Initialize the chunker with size constraints.
        
        Args:
            min_size: Minimum size of chunks in characters
            max_size: Maximum size of chunks in characters
        """
        self.min_size = min_size
        self.max_size = max_size
        
        # Regex patterns - allowing for indentation in markdown headers
        self.heading_pattern = re.compile(r'^(\s*)(#{1,6})\s+(.*?)(?:\s+\{#.*\})?\s*$', re.MULTILINE)
        self.sentence_pattern = re.compile(r'(?<=[.!?])\s+')
    
    def _get_heading_level(self, match) -> int:
        """Get the level of a heading from a regex match."""
        return len(match.group(2))
    
    def _split_text_by_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs (separated by blank lines)."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p for p in paragraphs if p.strip()]
    
    def _split_paragraph_by_sentences(self, paragraph: str) -> List[str]:
        """Split a paragraph into sentences."""
        sentences = self.sentence_pattern.split(paragraph)
        
        # Reconstruct sentences with proper endings
        result = []
        start_idx = 0
        for sentence in sentences:
            # Find where this sentence appears in the original paragraph
            sentence_start = paragraph.find(sentence, start_idx)
            if sentence_start == -1:
                result.append(sentence)  # Fallback
                continue
                
            # Find the end of this sentence (including punctuation)
            sentence_end = sentence_start + len(sentence)
            while sentence_end < len(paragraph) and paragraph[sentence_end] in ".!?":
                sentence_end += 1
            
            # Extract the complete sentence with punctuation
            complete_sentence = paragraph[sentence_start:sentence_end]
            if sentence_end < len(paragraph) and paragraph[sentence_end].isspace():
                complete_sentence += " "  # Add space if it exists
                
            result.append(complete_sentence)
            start_idx = sentence_end
            
        return result
    
    def _build_markdown_tree(self, text: str) -> Dict:
        """
        Build a tree representation of the markdown structure.
        
        Returns:
            Dictionary representing the markdown hierarchy
        """
        lines = text.split('\n')
        
        root = {
            'level': 0, 
            'heading': None,
            'content': [],
            'children': []
        }
        
        current_node = root
        parent_stack = []
        
        for line in lines:
            match = self.heading_pattern.match(line)
            
            if match:
                # Found a heading
                indent = match.group(1)
                level = self._get_heading_level(match)
                heading_text = match.group(3)
                
                # If this heading is a child of current node, we go deeper
                if not parent_stack or level > parent_stack[-1]['level']:
                    parent_stack.append(current_node)
                    
                # If this heading is at same level or higher, we go up
                else:
                    while parent_stack and level <= parent_stack[-1]['level']:
                        parent_stack.pop()
                        
                    if not parent_stack:
                        parent_stack.append(root)
                
                # Create new node for this heading
                new_node = {
                    'level': level,
                    'heading': indent + match.group(2) + ' ' + heading_text,
                    'content': [],
                    'children': []
                }
                
                parent_stack[-1]['children'].append(new_node)
                current_node = new_node
            else:
                # Content line, add to current node
                if current_node:
                    current_node['content'].append(line)
        
        return root
    
    def _node_to_text(self, node: Dict) -> str:
        """Convert a node to text with its heading and content."""
        result = []
        
        if node['heading']:
            result.append(node['heading'])
            
        if node['content']:
            result.extend(node['content'])
            
        return '\n'.join(result)
    
    def _node_size(self, node: Dict) -> int:
        """Calculate the size of a node's text."""
        return len(self._node_to_text(node))
    
    def _combine_node_texts(self, nodes: List[Dict]) -> str:
        """Combine multiple nodes into a single text."""
        result = []
        
        for node in nodes:
            node_text = self._node_to_text(node)
            if node_text:
                result.append(node_text)
                
        return '\n\n'.join(result)
    
    def _is_too_small(self, text: str) -> bool:
        """Determine if a text is too small."""
        return len(text) < self.min_size
    
    def _can_fit_in_chunk(self, current_text: str, new_text: str) -> bool:
        """Check if adding new_text to current_text exceeds max size."""
        separator = '\n\n' if current_text and new_text else ''
        return len(current_text) + len(separator) + len(new_text) <= self.max_size
    
    def _create_chunks_from_tree(self, node: Dict) -> List[str]:
        """
        Recursively create chunks from the markdown tree.
        Ensures headings always stay with content.
        """
        chunks = []
        current_chunk = ""
        
        # Process this node's heading and content first
        node_text = self._node_to_text(node)
        
        # If this node alone exceeds max_size, we need special handling
        if len(node_text) > self.max_size:
            # Always include the heading in our chunk if it exists
            heading = node['heading'] if node['heading'] else ""
            
            # Split content into paragraphs
            paragraphs = node['content']
            
            # Initialize the first chunk with the heading
            current_chunk = heading
            
            # Track if we've added at least some content after heading
            content_added = False
            
            for paragraph in paragraphs:
                # Skip empty paragraphs
                if not paragraph.strip():
                    current_chunk += '\n' if current_chunk else ''
                    continue
                
                # Check if this paragraph would fit in current chunk
                separator = '\n' if current_chunk else ''
                if len(current_chunk) + len(separator) + len(paragraph) <= self.max_size:
                    # Add to current chunk
                    current_chunk += separator + paragraph
                    content_added = True
                else:
                    # If we've added content already, finalize current chunk
                    if content_added:
                        chunks.append(current_chunk)
                        current_chunk = heading + '\n' + paragraph  # Start new chunk with heading
                        content_added = True
                    else:
                        # Need to split this paragraph itself (it's too big even with just the heading)
                        sentences = self._split_paragraph_by_sentences(paragraph)
                        
                        for sentence in sentences:
                            if len(current_chunk) + len(sentence) <= self.max_size:
                                separator = '\n' if current_chunk else ''
                                current_chunk += separator + sentence
                                content_added = True
                            else:
                                if content_added:
                                    chunks.append(current_chunk)
                                    current_chunk = heading + '\n' + sentence
                                    content_added = True
                                else:
                                    # Even a single sentence won't fit with heading, we have to exceed max_size
                                    chunks.append(current_chunk + sentence)
                                    current_chunk = heading
                                    content_added = False
            
            # Add the final chunk if it has content
            if content_added:
                chunks.append(current_chunk)
                current_chunk = ""
        else:
            current_chunk = node_text
        
        # Process children recursively
        for child in node['children']:
            child_chunks = self._create_chunks_from_tree(child)
            
            # If we have an existing chunk, try to combine with first child chunk
            if current_chunk and child_chunks:
                combined = current_chunk + '\n\n' + child_chunks[0]
                
                if len(combined) <= self.max_size:
                    current_chunk = combined
                    child_chunks = child_chunks[1:]
                else:
                    # Can't combine, add current chunk to results
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = ""
            
            # Add any remaining child chunks
            if child_chunks:
                if not current_chunk:
                    current_chunk = child_chunks[0]
                    child_chunks = child_chunks[1:]
                    
                chunks.extend(child_chunks)
        
        # Add final chunk if not empty
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _expand_small_chunks(self, chunks: List[str]) -> List[str]:
        """
        Perform a pass to try to expand chunks that are below min_size.
        Will try to merge small chunks with previous or next chunk if possible.
        """
        if not chunks:
            return []
            
        result = [chunks[0]]
        
        for i in range(1, len(chunks)):
            current = chunks[i]
            
            # If current chunk is too small, try to merge with previous
            if self._is_too_small(current) and result:
                combined = result[-1] + '\n\n' + current
                
                if len(combined) <= self.max_size:
                    result[-1] = combined
                else:
                    # Couldn't merge, add as is
                    result.append(current)
            else:
                result.append(current)
        
        return result
    
    def chunk_markdown(self, text: str) -> List[str]:
        """
        Chunk the markdown text according to the rules.
        
        Returns:
            List of text chunks
        """
        # Build markdown tree structure
        tree = self._build_markdown_tree(text)
        
        # Create initial chunks from tree
        chunks = self._create_chunks_from_tree(tree)
        
        # Expand small chunks where possible
        chunks = self._expand_small_chunks(chunks)
        
        return chunks


# Example usage
if __name__ == "__main__":
    # Sample markdown text
    sample_markdown = """
    # Introduction
    
    This is an introduction paragraph. It contains several sentences that describe the document.
    We're adding more text to make it substantial enough for testing. This should help demonstrate how the chunker works.
    
    ## Background
    
    Some background information here. It's quite detailed and contains multiple sentences.
    We'll add more text to ensure it's substantial enough for testing purposes.
    
    ### Historical Context
    
    Detailed historical context with lots of information.
    This section is quite lengthy and contains multiple paragraphs.
    
    This is a second paragraph in the historical context section.
    It adds more details and information about the topic.
    
    ## Methodology
    
    Discussion of methodology used. This section has multiple paragraphs.
    
    This is a second paragraph discussing more methodology details.
    
    ### Data Collection
    
    Details about data collection processes and methods.
    
    ### Analysis Approach
    
    Explanation of how the data was analyzed.
    
    # Results
    
    Presentation of results with lots of details and findings.
    This section is quite lengthy and contains multiple paragraphs.
    
    This is a second paragraph in the results section.
    
    ## Key Findings
    
    Discussion of key findings from the analysis.
    """

    md = sample_markdown

    # Create chunker with min_size=100 and max_size=500 for demonstration
    chunker = MarkdownChunker(min_size=100, max_size=500)

    #check argparse arguments whether we should process a file, else we use the sample text:
    import argparse
    parser = argparse.ArgumentParser(description='Process a markdown file or use a sample text.')
    parser.add_argument('--file', type=str, help='Path to the markdown file to process.')
    args = parser.parse_args()
    if args.file:
        with open(args.file, 'r') as f:
            md = f.read()
            print(f"Processing file: {args.file}")
            print(f"File size: {len(md)} characters")
            print(f"First 100 characters: {md[:100]}...")
            print()
     
    # Chunk the markdown text
    chunks = chunker.chunk_markdown(md)
    
    # Print results
    print(f"Split into {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i+1} (size: {len(chunk)}) ---")
        print(chunk)
