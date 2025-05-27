#!/usr/bin/env python3
"""
Unit tests for PubMed text extraction fix.

Tests the get_element_text function to ensure it properly handles
mixed content (text + child elements) and doesn't truncate abstracts
when encountering special characters like subscripts, superscripts, etc.
"""

import unittest
import xml.etree.ElementTree as ET
import sys
import os

# Add the parent directory to the path to import localknowledge
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from localknowledge.pubmed.import_downloads import get_element_text, process_article


class TestPubMedTextExtraction(unittest.TestCase):
    """Test cases for PubMed text extraction functions."""

    def test_get_element_text_simple(self):
        """Test get_element_text with simple text content."""
        xml = '<AbstractText>Simple text without any formatting.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        expected = "Simple text without any formatting."
        self.assertEqual(result, expected)

    def test_get_element_text_with_subscript(self):
        """Test get_element_text with subscript elements."""
        xml = '<AbstractText>We developed a compound (average n<sub>5</sub>) that works.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        expected = "We developed a compound (average n5) that works."
        self.assertEqual(result, expected)

    def test_get_element_text_with_superscript(self):
        """Test get_element_text with superscript elements."""
        xml = '<AbstractText>The concentration was 10<sup>-6</sup> M in solution.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        expected = "The concentration was 10-6 M in solution."
        self.assertEqual(result, expected)

    def test_get_element_text_with_italic(self):
        """Test get_element_text with italic elements."""
        xml = '<AbstractText>The study examined <i>Escherichia coli</i> bacteria.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        expected = "The study examined Escherichia coli bacteria."
        self.assertEqual(result, expected)

    def test_get_element_text_with_multiple_formatting(self):
        """Test get_element_text with multiple formatting elements."""
        xml = '<AbstractText>Results showed <b>significant</b> increase of 2<sup>3</sup> fold in <i>gene<sub>x</sub></i> expression.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        expected = "Results showed significant increase of 23 fold in genex expression."
        self.assertEqual(result, expected)

    def test_get_element_text_empty(self):
        """Test get_element_text with empty element."""
        xml = '<AbstractText></AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        self.assertEqual(result, "")

    def test_get_element_text_none(self):
        """Test get_element_text with None input."""
        result = get_element_text(None)
        self.assertEqual(result, "")

    def test_get_element_text_complex_chemistry(self):
        """Test get_element_text with complex chemical formulas."""
        xml = '<AbstractText>The iron complex Bu<sub>4</sub>N[Fe(CO)<sub>3</sub>(NO)] catalyzes C(sp<sup>3</sup>)-H bonds.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        expected = "The iron complex Bu4N[Fe(CO)3(NO)] catalyzes C(sp3)-H bonds."
        self.assertEqual(result, expected)

    def test_process_article_with_mixed_content(self):
        """Test process_article function with mixed content in abstract."""
        article_xml = '''
        <PubmedArticle>
            <MedlineCitation>
                <PMID>12345678</PMID>
                <Article>
                    <ArticleTitle>Test Article with <i>Formatting</i></ArticleTitle>
                    <Abstract>
                        <AbstractText>We developed a compound (Gluen-Azo-SA, average n<sub>5</sub>) with 10<sup>-6</sup> M affinity.</AbstractText>
                    </Abstract>
                    <AuthorList>
                        <Author>
                            <LastName>Smith</LastName>
                            <ForeName>John</ForeName>
                        </Author>
                    </AuthorList>
                    <Journal>
                        <Title>Test Journal</Title>
                    </Journal>
                    <PubDate>
                        <Year>2024</Year>
                    </PubDate>
                </Article>
            </MedlineCitation>
            <PubmedData>
                <ArticleIdList>
                    <ArticleId IdType="doi">10.1234/test.2024.001</ArticleId>
                </ArticleIdList>
            </PubmedData>
        </PubmedArticle>
        '''
        
        root = ET.fromstring(article_xml)
        result = process_article(root)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['pmid'], '12345678')
        self.assertEqual(result['title'], 'Test Article with Formatting')
        
        # Check that the abstract is complete and not truncated
        expected_abstract = "We developed a compound (Gluen-Azo-SA, average n5) with 10-6 M affinity."
        self.assertEqual(result['abstract'], expected_abstract)
        
        # Ensure it's not truncated at the first special character
        self.assertNotEqual(result['abstract'], "We developed a compound (Gluen-Azo-SA, average n")

    def test_abstract_not_truncated_at_parenthesis(self):
        """Test that abstracts are not truncated at opening parentheses."""
        xml = '<AbstractText>We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n<sub>5</sub>) that can be activated by light.</AbstractText>'
        elem = ET.fromstring(xml)
        result = get_element_text(elem)
        
        # Should contain the complete text, not truncated at the opening parenthesis
        self.assertIn("that can be activated by light", result)
        self.assertNotEqual(result, "We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n")


if __name__ == '__main__':
    unittest.main()
