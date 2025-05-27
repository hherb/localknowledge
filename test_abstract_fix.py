#!/usr/bin/env python3
"""
Test script to verify the abstract truncation fix.

This script tests the get_element_text function with various XML structures
that contain mixed content (text + child elements) to ensure abstracts
are no longer truncated when encountering special characters.

It also tests with a real-world PubMed article (PMID 28675679) that contains
special characters in the abstract.
"""

import xml.etree.ElementTree as ET
import sys
import os
import requests
import json

# Add the localknowledge module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from localknowledge.pubmed.import_downloads import get_element_text, process_article


def fetch_pubmed_xml(pmid):
    """
    Fetch PubMed article XML from NCBI E-utilities API.

    Args:
        pmid: PubMed ID

    Returns:
        XML string or None if failed
    """
    try:
        # Use NCBI E-utilities to fetch the article
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'xml',
            'rettype': 'abstract'
        }

        response = requests.get(base_url, params=params)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Failed to fetch PMID {pmid}: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching PMID {pmid}: {e}")
        return None


def test_real_pubmed_article():
    """Test with the real PubMed article PMID 28675679."""

    print("Testing with real PubMed article PMID 28675679...")

    # Fetch the article XML
    xml_content = fetch_pubmed_xml("28675679")

    if not xml_content:
        print("Failed to fetch the article. Skipping real-world test.")
        return

    try:
        # Parse the XML
        root = ET.fromstring(xml_content)

        # Find the PubmedArticle element
        article_elem = root.find('.//PubmedArticle')
        if article_elem is None:
            print("No PubmedArticle found in the XML")
            return

        # Process the article using our fixed function
        result = process_article(article_elem)

        if result:
            print("Successfully processed real PubMed article!")
            print(f"PMID: {result['pmid']}")
            print(f"Title: {result['title']}")
            print(f"Abstract length: {len(result['abstract'])} characters")
            print(f"Full abstract: {result['abstract']}")
            print()

            # Check if the abstract contains expected content that would be truncated
            # This article should contain chemical formulas and special characters
            if len(result['abstract']) > 100:  # Should be a substantial abstract
                print("✓ Abstract appears to be complete (not truncated)")
            else:
                print("⚠ Abstract seems short - might still be truncated")

            # Look for signs of truncation at special characters
            if result['abstract'].endswith('('):
                print("⚠ Abstract ends with '(' - likely truncated")
            else:
                print("✓ Abstract doesn't end with truncation pattern")

        else:
            print("Failed to process the real PubMed article")

    except Exception as e:
        print(f"Error processing real article: {e}")


def test_get_element_text():
    """Test the get_element_text function with various XML structures."""

    print("Testing get_element_text function...")

    # Test 1: Simple text without child elements
    xml1 = '<AbstractText>Simple text without any formatting.</AbstractText>'
    elem1 = ET.fromstring(xml1)
    result1 = get_element_text(elem1)
    expected1 = "Simple text without any formatting."
    print(f"Test 1 - Simple text:")
    print(f"  Expected: {expected1}")
    print(f"  Got:      {result1}")
    print(f"  Pass:     {result1 == expected1}")
    print()

    # Test 2: Text with subscript (the reported bug case)
    xml2 = '<AbstractText>We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n<sub>5</sub>) that can be activated by light.</AbstractText>'
    elem2 = ET.fromstring(xml2)
    result2 = get_element_text(elem2)
    expected2 = "We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n5) that can be activated by light."
    print(f"Test 2 - Text with subscript:")
    print(f"  Expected: {expected2}")
    print(f"  Got:      {result2}")
    print(f"  Pass:     {result2 == expected2}")
    print()

    # Test 3: Text with superscript
    xml3 = '<AbstractText>The concentration was 10<sup>-6</sup> M in the solution.</AbstractText>'
    elem3 = ET.fromstring(xml3)
    result3 = get_element_text(elem3)
    expected3 = "The concentration was 10-6 M in the solution."
    print(f"Test 3 - Text with superscript:")
    print(f"  Expected: {expected3}")
    print(f"  Got:      {result3}")
    print(f"  Pass:     {result3 == expected3}")
    print()

    # Test 4: Text with italic formatting
    xml4 = '<AbstractText>The study examined <i>Escherichia coli</i> bacteria in various conditions.</AbstractText>'
    elem4 = ET.fromstring(xml4)
    result4 = get_element_text(elem4)
    expected4 = "The study examined Escherichia coli bacteria in various conditions."
    print(f"Test 4 - Text with italic:")
    print(f"  Expected: {expected4}")
    print(f"  Got:      {result4}")
    print(f"  Pass:     {result4 == expected4}")
    print()

    # Test 5: Text with multiple formatting elements
    xml5 = '<AbstractText>Results showed a <b>significant</b> increase of 2<sup>3</sup> fold in <i>gene<sub>x</sub></i> expression.</AbstractText>'
    elem5 = ET.fromstring(xml5)
    result5 = get_element_text(elem5)
    expected5 = "Results showed a significant increase of 23 fold in genex expression."
    print(f"Test 5 - Text with multiple formatting:")
    print(f"  Expected: {expected5}")
    print(f"  Got:      {result5}")
    print(f"  Pass:     {result5 == expected5}")
    print()

    # Test 6: Empty element
    xml6 = '<AbstractText></AbstractText>'
    elem6 = ET.fromstring(xml6)
    result6 = get_element_text(elem6)
    expected6 = ""
    print(f"Test 6 - Empty element:")
    print(f"  Expected: '{expected6}'")
    print(f"  Got:      '{result6}'")
    print(f"  Pass:     {result6 == expected6}")
    print()

    # Test 7: None element
    result7 = get_element_text(None)
    expected7 = ""
    print(f"Test 7 - None element:")
    print(f"  Expected: '{expected7}'")
    print(f"  Got:      '{result7}'")
    print(f"  Pass:     {result7 == expected7}")
    print()


def test_process_article():
    """Test the process_article function with a complete PubMed article."""

    print("Testing process_article function with mixed content...")

    # Create a sample PubMed article XML with mixed content in abstract
    article_xml = '''
    <PubmedArticle>
        <MedlineCitation>
            <PMID>12345678</PMID>
            <Article>
                <ArticleTitle>A Novel Photoswitch for <i>In Vivo</i> Applications</ArticleTitle>
                <Abstract>
                    <AbstractText>We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n<sub>5</sub>) that can be activated by light. The compound showed 10<sup>-6</sup> M binding affinity to <i>target<sub>protein</sub></i> receptors.</AbstractText>
                </Abstract>
                <AuthorList>
                    <Author>
                        <LastName>Smith<sup>1</sup></LastName>
                        <ForeName>John <i>A</i></ForeName>
                    </Author>
                </AuthorList>
                <Journal>
                    <Title>Journal of <i>Advanced</i> Chemistry</Title>
                </Journal>
                <PubDate>
                    <Year>2024</Year>
                </PubDate>
            </Article>
        </MedlineCitation>
        <PubmedData>
            <ArticleIdList>
                <ArticleId IdType="doi">10.1234/example.2024.001</ArticleId>
            </ArticleIdList>
        </PubmedData>
    </PubmedArticle>
    '''

    # Parse the XML
    root = ET.fromstring(article_xml)

    # Process the article
    result = process_article(root)

    if result:
        print("Article processing successful!")
        print(f"PMID: {result['pmid']}")
        print(f"Title: {result['title']}")
        print(f"Abstract: {result['abstract']}")
        print(f"Authors: {result['authors']}")
        print(f"Journal: {result['journal']}")
        print(f"DOI: {result['doi']}")
        print()

        # Check if abstract contains the complete text
        expected_abstract = "We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n5) that can be activated by light. The compound showed 10-6 M binding affinity to targetprotein receptors."
        print(f"Abstract extraction test:")
        print(f"  Expected: {expected_abstract}")
        print(f"  Got:      {result['abstract']}")
        print(f"  Pass:     {expected_abstract in result['abstract']}")

        # Check if the abstract is NOT truncated at the first special character
        truncated_text = "We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n"
        is_not_truncated = not result['abstract'].endswith(truncated_text)
        print(f"  Not truncated: {is_not_truncated}")

    else:
        print("Article processing failed!")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Abstract Truncation Fix")
    print("=" * 60)
    print()

    test_get_element_text()
    print("-" * 60)
    test_process_article()
    print("-" * 60)
    test_real_pubmed_article()

    print("=" * 60)
    print("Test completed!")
