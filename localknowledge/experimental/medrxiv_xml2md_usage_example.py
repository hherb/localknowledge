#!/usr/bin/env python3
"""
Example demonstrating how to use the MedRxiv XML to Markdown converter
"""

from xml2md_converter import MedRxivXmlToMarkdown

def simple_example():
    """Convert a single file and print the result"""
    converter = MedRxivXmlToMarkdown()
    
    # Example 1: Convert a file and save output to default location
    result_path = converter.convert_file("sample_paper.xml")
    print(f"File converted and saved to: {result_path}")
    
    # Example 2: Convert a file and specify output location
    result_path = converter.convert_file("sample_paper.xml", "output/paper_converted.md")
    print(f"File converted and saved to: {result_path}")
    
    # Example 3: Convert XML string directly
    xml_string = """
    <article xmlns:jats="http://www.ncbi.nlm.nih.gov/JATS1">
      <front>
        <article-meta>
          <title-group>
            <article-title>Sample medRxiv Paper Title</article-title>
          </title-group>
          <contrib-group>
            <contrib contrib-type="author">
              <name>
                <surname>Smith</surname>
                <given-names>John</given-names>
              </name>
              <xref ref-type="aff" rid="aff1"/>
            </contrib>
          </contrib-group>
          <aff id="aff1">University Medical Center</aff>
          <abstract>
            <p>This is a sample abstract for demonstration purposes.</p>
          </abstract>
        </article-meta>
      </front>
      <body>
        <sec>
          <title>Introduction</title>
          <p>This is an example introduction paragraph.</p>
        </sec>
      </body>
    </article>
    """
    
    markdown_result = converter.convert_string(xml_string)
    print("\nConverted XML string to Markdown:")
    print(markdown_result)

def batch_processing_example():
    """Process multiple files in a directory"""
    import os
    import sys
    
    # Use the command-line interface
    if len(sys.argv) < 2:
        print("Usage: python example.py <xml_directory>")
        return
        
    xml_dir = sys.argv[1]
    output_dir = "converted_markdown"
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Process all XML files in the directory
    for filename in os.listdir(xml_dir):
        if filename.endswith(".xml"):
            input_path = os.path.join(xml_dir, filename)
            output_path = os.path.join(output_dir, filename.replace(".xml", ".md"))
            
            converter = MedRxivXmlToMarkdown()
            result = converter.convert_file(input_path, output_path)
            
            if result:
                print(f"Converted: {input_path} -> {result}")
            else:
                print(f"Failed to convert: {input_path}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        batch_processing_example()
    else:
        simple_example()
