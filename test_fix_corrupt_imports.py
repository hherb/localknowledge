#!/usr/bin/env python3
"""
Test script for the fix_corrupt_pubmed_imports module.

This script tests the corruption detection and fixing functionality
without actually modifying the database.
"""

import os
import sys
import tempfile
import gzip
import xml.etree.ElementTree as ET

# Add the localknowledge module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from localknowledge.pubmed.fix_corrupt_pubmed_imports import CorruptImportFixer


def create_test_xml_file():
    """Create a test XML file with articles that have mixed content."""
    
    # Sample PubMed XML with mixed content that would be truncated
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
    <PubmedArticle>
        <MedlineCitation>
            <PMID>28675679</PMID>
            <Article>
                <ArticleTitle>Iron-Catalyzed Intramolecular Aminations of C(sp<sup>3</sup>)-H Bonds in Alkylaryl Azides.</ArticleTitle>
                <Abstract>
                    <AbstractText>The nucleophilic iron complex Bu<sub>4</sub>N[Fe(CO)<sub>3</sub>(NO)] (TBA[Fe]) catalyzes the direct intramolecular amination of unactivated C(sp<sup>3</sup>)-H bonds in alkylaryl azides, which results in the formation of substituted indoline and tetrahydroquinoline derivatives.</AbstractText>
                </Abstract>
                <AuthorList>
                    <Author>
                        <LastName>Smith<sup>1</sup></LastName>
                        <ForeName>John <i>A</i></ForeName>
                    </Author>
                    <Author>
                        <LastName>Doe</LastName>
                        <ForeName>Jane</ForeName>
                    </Author>
                </AuthorList>
                <Journal>
                    <Title>Angewandte Chemie <i>International</i> Edition</Title>
                </Journal>
                <PubDate>
                    <Year>2017</Year>
                </PubDate>
                <MeshHeadingList>
                    <MeshHeading>
                        <DescriptorName>Iron<sub>2+</sub> Compounds</DescriptorName>
                    </MeshHeading>
                    <MeshHeading>
                        <DescriptorName>Chemical <i>Synthesis</i></DescriptorName>
                    </MeshHeading>
                </MeshHeadingList>
                <KeywordList>
                    <Keyword>C-H <i>activation</i></Keyword>
                    <Keyword>iron<sub>catalysis</sub></Keyword>
                </KeywordList>
            </Article>
        </MedlineCitation>
        <PubmedData>
            <ArticleIdList>
                <ArticleId IdType="doi">10.1002/anie.201704260</ArticleId>
            </ArticleIdList>
        </PubmedData>
    </PubmedArticle>
    
    <PubmedArticle>
        <MedlineCitation>
            <PMID>12345678</PMID>
            <Article>
                <ArticleTitle>Test Article with <i>Formatting</i> Elements</ArticleTitle>
                <Abstract>
                    <AbstractText>We developed a water-soluble adhesive photoswitch (Gluen-Azo-SA, average n<sub>5</sub>) that can be activated by light. The compound showed 10<sup>-6</sup> M binding affinity to <i>target<sub>protein</sub></i> receptors.</AbstractText>
                </Abstract>
                <AuthorList>
                    <Author>
                        <LastName>Test</LastName>
                        <ForeName>Author</ForeName>
                    </Author>
                </AuthorList>
                <Journal>
                    <Title>Test <i>Journal</i></Title>
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
</PubmedArticleSet>'''
    
    # Create a temporary gzipped XML file
    temp_dir = tempfile.mkdtemp()
    xml_file = os.path.join(temp_dir, 'test_pubmed.xml.gz')
    
    with gzip.open(xml_file, 'wt', encoding='utf-8') as f:
        f.write(xml_content)
    
    return temp_dir, xml_file


def test_xml_processing():
    """Test XML processing with the fixed import function."""
    
    print("Testing XML processing with mixed content...")
    
    # Create test XML file
    temp_dir, xml_file = create_test_xml_file()
    
    try:
        # Create a fixer instance (this will fail if database is not available)
        try:
            fixer = CorruptImportFixer(temp_dir)
            print("✓ CorruptImportFixer initialized successfully")
        except Exception as e:
            print(f"⚠ Could not initialize CorruptImportFixer (database not available): {e}")
            print("Testing XML processing only...")
            
            # Test just the XML processing part
            articles = []
            with gzip.open(xml_file, 'rb') as f:
                context = ET.iterparse(f, events=('end',))
                
                for _, elem in context:
                    if elem.tag == 'PubmedArticle':
                        from localknowledge.pubmed.import_downloads import process_article
                        article_data = process_article(elem)
                        if article_data:
                            articles.append(article_data)
                        elem.clear()
            
            print(f"✓ Processed {len(articles)} articles from XML")
            
            # Check the results
            for i, article in enumerate(articles):
                print(f"\nArticle {i+1}:")
                print(f"  PMID: {article['pmid']}")
                print(f"  Title: {article['title']}")
                print(f"  Abstract: {article['abstract']}")
                print(f"  Authors: {article['authors']}")
                print(f"  Journal: {article['journal']}")
                print(f"  DOI: {article['doi']}")
                
                # Check for truncation patterns
                if article['abstract'].endswith('('):
                    print("  ⚠ Abstract appears to be truncated!")
                else:
                    print("  ✓ Abstract appears complete")
            
            return
        
        # Test XML file processing
        articles = fixer.process_xml_file(xml_file)
        print(f"✓ Processed {len(articles)} articles from XML file")
        
        # Display results
        for i, article in enumerate(articles):
            print(f"\nArticle {i+1}:")
            print(f"  PMID: {article['pmid']}")
            print(f"  Title: {article['title']}")
            print(f"  Abstract: {article['abstract']}")
            print(f"  Authors: {article['authors']}")
            print(f"  Journal: {article['journal']}")
            print(f"  DOI: {article['doi']}")
            
            # Check for truncation patterns
            if article['abstract'].endswith('('):
                print("  ⚠ Abstract appears to be truncated!")
            else:
                print("  ✓ Abstract appears complete")
        
        # Test comparison functionality with mock data
        print("\nTesting comparison functionality...")
        
        if articles:
            article = articles[0]
            
            # Create a "corrupted" version (simulating old truncated import)
            corrupted_article = {
                'id': 1,
                'title': article['title'],
                'abstract': "The nucleophilic iron complex Bu4N[Fe(CO)3(NO)] (TBA[Fe]) catalyzes the direct intramolecular amination of unactivated C(sp",  # Truncated
                'authors': article['authors'].split(', '),
                'publication': article['journal'],
                'mesh_terms': article['mesh_terms'].split(', ') if article['mesh_terms'] else [],
                'keywords': article['keywords'].split(', ') if article['keywords'] else [],
                'doi': article['doi']
            }
            
            # Compare
            differences = fixer.compare_articles(article, corrupted_article)
            print(f"Differences found: {[k for k, v in differences.items() if v]}")
            
            if differences['abstract']:
                print("✓ Abstract truncation detected correctly")
            else:
                print("⚠ Abstract truncation not detected")
        
        fixer.close()
        
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up temporary directory: {temp_dir}")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Fix Corrupt PubMed Imports Module")
    print("=" * 60)
    
    test_xml_processing()
    
    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)
