#!/usr/bin/env python3
"""
Test the final simple chunker with a structured markdown document.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath('.'))

from final_simple_chunker import FinalSimpleChunker

def main():
    """Main function to test the final simple chunker with a structured markdown document."""
    # Create a sample markdown text with clear headings
    markdown_text = """# ONSD Cutoff for Raised ICP

The optic nerve sheath diameter (ONSD) is increasingly recognized as a non-invasive method for estimating intracranial pressure (ICP). A raised ICP can have serious clinical implications, particularly in conditions such as traumatic brain injury and hydrocephalus. Identifying an ONSD cutoff value that reliably indicates elevated ICP would be valuable for clinical practice.

## ONSD Measurement Technique

The ONSD is typically measured using ultrasonography through the closed eyelid, which allows for a relatively easy, non-invasive assessment in various settings, including intensive care units and emergency rooms (Linn et al., 2013; PMID: 23193666).

## Cutoff Values

Several studies have proposed different ONSD cutoff values to indicate elevated ICP:
- A systematic review by Schiavon et al. suggested a mean ONSD of ≥5 mm as indicative of raised ICP, with higher sensitivity and specificity observed when using this threshold (Schiavon et al., 2018; PMID: 29284497).
- Another study indicated that an ONSD value >5.3 mm has high predictive values for elevated ICP in patients with traumatic brain injury (Berg et al., 2014; PMID: 24293349).

## Variability and Limitations

There is variability in the reported cutoffs, which may be influenced by factors such as patient age, ethnicity, and underlying conditions.

The measurement of ONSD can be affected by technical aspects of ultrasound imaging, including probe pressure on the globe, operator experience, and equipment calibration (Linn et al., 2013; PMID: 23193666).

### Technical Factors

Operator experience and training can significantly impact the reliability of ONSD measurements. Standardized protocols for measurement technique are essential for consistent results.

## Clinical Application

Despite these limitations, using ONSD as a surrogate marker for elevated ICP has shown potential benefits in resource-limited settings where invasive monitoring is not feasible or safe. It provides an adjunct tool to clinical assessment and other non-invasive methods like transcranial Doppler.

## Gaps in Evidence

Further research is needed to standardize measurement techniques and establish universally accepted cutoff values.

Longitudinal studies assessing the correlation between changes in ONSD over time and corresponding ICP measurements would enhance clinical applicability.

## Conclusion

While an ONSD of ≥5 mm is commonly used as a threshold for raised ICP, this value should be interpreted with caution considering patient-specific factors. The evidence supports its use as a non-invasive tool for initial assessment, but it should not replace direct ICP monitoring when available and clinically indicated.

## References

- Linn JH, et al., "Ultrasound measurement of the optic nerve sheath diameter in adults." *Eur Radiol*, 2013; PMID: 23193666.
- Schiavon F, et al., "Optic nerve sheath diameter measured by ultrasound as a predictor of intracranial pressure in patients with subarachnoid hemorrhage: A systematic review and meta-analysis." *PLoS One*, 2018; PMID: 29284497.
- Bergsneider M, et al., "The optic nerve sheath diameter is correlated with changes in intracranial pressure after traumatic brain injury." *J Neurotrauma*, 2014; PMID: 24293349.
"""
    
    # Create metadata
    metadata = {
        'file_name': 'structured_example.md',
        'source': 'Test',
        'document_type': 'markdown'
    }
    
    # Create a final simple chunker
    chunker = FinalSimpleChunker(
        chunk_size=1000,
        min_chunk_size=100
    )
    
    # Chunk the markdown text
    chunks = chunker.chunk(markdown_text, metadata=metadata)
    
    # Print the chunks
    print(f"\nFound {len(chunks)} chunks in the markdown text:\n")
    
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}:")
        print(f"  Heading: {chunk.metadata.get('heading_title')}")
        print(f"  Level: {chunk.metadata.get('heading_level')}")
        print(f"  Type: {chunk.metadata.get('chunk_type')}")
        print(f"  Text length: {len(chunk.text)} characters")
        print(f"  Text preview: {chunk.text[:100]}...")
        print(f"  Start line: {chunk.metadata.get('start_line')}")
        print(f"  End line: {chunk.metadata.get('end_line')}")
        print()
        
    # Check for overlapping content
    print("\nChecking for overlapping content...")
    for i in range(len(chunks) - 1):
        chunk1 = chunks[i].text
        chunk2 = chunks[i + 1].text
        
        # Check if chunk2 starts with any significant portion of chunk1
        overlap = False
        for j in range(50, min(len(chunk1), 500), 50):  # Check overlaps of 50, 100, 150, ... characters
            if chunk2.startswith(chunk1[-j:]):
                print(f"WARNING: Chunk {i+2} starts with the last {j} characters of Chunk {i+1}")
                overlap = True
                break
        
        if not overlap:
            print(f"No significant overlap between Chunks {i+1} and {i+2}")

if __name__ == "__main__":
    main()
