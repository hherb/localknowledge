#!/usr/bin/env python3
"""
Test script to confirm the medRxiv XML conversion works properly
"""

from xml2md_converter import MedRxivXmlToMarkdown

def test_medrxiv_conversion():
    """Test conversion of a medRxiv XML file"""
    converter = MedRxivXmlToMarkdown()
    converter.debug = True  # Enable debugging output
    
    # Convert the file and print the output
    markdown_text = converter.convert_file("sample.xml")
    
    print("\n\n" + "="*80)
    print("CONVERSION RESULT:")
    print("="*80)
    print(markdown_text)
    print("="*80)
    
    # Optionally save the output
    with open("medrxiv_converted.md", "w", encoding="utf-8") as f:
        f.write(markdown_text)
    print(f"Markdown saved to medrxiv_converted.md")

if __name__ == "__main__":
    test_medrxiv_conversion()
