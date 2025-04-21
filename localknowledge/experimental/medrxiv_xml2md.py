import xml.etree.ElementTree as ET
import re
import os
import argparse


class MedRxivXmlToMarkdown:
    """
    Converts medRxiv XML files to Markdown format, preserving the structure
    of scientific publications.
    """
    
    def __init__(self):
        # JATS XML namespace
        self.ns = {'jats': 'http://www.ncbi.nlm.nih.gov/JATS1'}
        self.output = []
    
    def convert_file(self, xml_path, output_path=None):
        """Convert an XML file to Markdown and save to file."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            self.output = []
            self.process_article(root)
            
            markdown_content = '\n\n'.join(self.output)
            
            if output_path is None:
                # Create output filename based on input filename
                base_name = os.path.splitext(xml_path)[0]
                output_path = f"{base_name}.md"
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            return output_path
            
        except Exception as e:
            print(f"Error converting file: {e}")
            return None
    
    def convert_string(self, xml_string):
        """Convert XML string to Markdown and return the result."""
        try:
            root = ET.fromstring(xml_string)
            
            self.output = []
            self.process_article(root)
            
            return '\n\n'.join(self.output)
            
        except Exception as e:
            print(f"Error converting string: {e}")
            return None
    
    def process_article(self, root):
        """Process the entire article structure."""
        # Process front matter (title, authors, abstract)
        front = root.find('.//jats:front', self.ns)
        if front is not None:
            self.process_front(front)
        
        # Process body (main content)
        body = root.find('.//jats:body', self.ns)
        if body is not None:
            self.process_body(body)
        
        # Process back matter (references, appendices)
        back = root.find('.//jats:back', self.ns)
        if back is not None:
            self.process_back(back)
    
    def process_front(self, front):
        """Process the front matter of the article."""
        # Article title
        title = front.find('.//jats:article-title', self.ns)
        if title is not None and title.text:
            self.output.append(f"# {title.text.strip()}")
        
        # Article metadata
        journal_meta = front.find('.//jats:journal-meta', self.ns)
        if journal_meta is not None:
            journal_title = journal_meta.find('.//jats:journal-title', self.ns)
            if journal_title is not None and journal_title.text:
                self.output.append(f"*{journal_title.text.strip()}*")
        
        # Article IDs (DOI, etc.)
        article_ids = front.findall('.//jats:article-id', self.ns)
        if article_ids:
            id_info = []
            for id_elem in article_ids:
                id_type = id_elem.get('pub-id-type', '')
                if id_type and id_elem.text:
                    id_info.append(f"{id_type.upper()}: {id_elem.text.strip()}")
            if id_info:
                self.output.append("**Article IDs:** " + ", ".join(id_info))
        
        # Authors
        contrib_group = front.find('.//jats:contrib-group', self.ns)
        if contrib_group is not None:
            authors = []
            for contrib in contrib_group.findall('.//jats:contrib[@contrib-type="author"]', self.ns):
                surname = contrib.find('.//jats:surname', self.ns)
                surname_text = surname.text.strip() if surname is not None and surname.text else ""
                
                given_names = contrib.find('.//jats:given-names', self.ns)
                given_text = given_names.text.strip() if given_names is not None and given_names.text else ""
                
                if surname_text or given_text:
                    author_name = f"{given_text} {surname_text}".strip()
                    
                    # Get author affiliations
                    xrefs = contrib.findall('.//jats:xref[@ref-type="aff"]', self.ns)
                    if xrefs:
                        author_affiliations = [xref.get('rid', '') for xref in xrefs]
                        author_name += "^" + ",".join(author_affiliations) + "^"
                    
                    authors.append(author_name)
            
            if authors:
                self.output.append("**Authors:** " + ", ".join(authors))
        
        # Affiliations
        affiliations = front.findall('.//jats:aff', self.ns)
        if affiliations:
            aff_list = []
            for aff in affiliations:
                aff_id = aff.get('id', '')
                aff_text = " ".join(aff.itertext()).strip()
                if aff_id and aff_text:
                    aff_list.append(f"^{aff_id}^{aff_text}")
            
            if aff_list:
                self.output.append("\n".join(aff_list))
        
        # Abstract
        abstract = front.find('.//jats:abstract', self.ns)
        if abstract is not None:
            self.output.append("## Abstract")
            self.process_abstract(abstract)
    
    def process_abstract(self, abstract):
        """Process the abstract section."""
        for elem in abstract:
            tag = self._strip_namespace(elem.tag)
            
            if tag == 'title' and elem.text:
                self.output.append(f"**{elem.text.strip()}**")
            elif tag == 'p':
                text = self._get_paragraph_text(elem)
                if text:
                    self.output.append(text)
            elif tag == 'sec':
                self.process_section(elem, 3)  # Abstract sections start at ### level
    
    def process_body(self, body):
        """Process the main body of the article."""
        for section in body.findall('.//jats:sec', self.ns):
            self.process_section(section, 2)  # Main sections start at ## level
    
    def process_section(self, section, level):
        """Process a section of the article with the given heading level."""
        # Section title
        title = section.find('.//jats:title', self.ns)
        if title is not None:
            title_text = self._get_element_text(title)
            if title_text:
                heading = '#' * level
                self.output.append(f"{heading} {title_text}")
        
        # Process paragraphs and other direct children of the section
        for elem in section:
            tag = self._strip_namespace(elem.tag)
            
            if tag == 'p':
                text = self._get_paragraph_text(elem)
                if text:
                    self.output.append(text)
            elif tag == 'fig':
                self.process_figure(elem)
            elif tag == 'table-wrap':
                self.process_table(elem)
            elif tag == 'list':
                self.process_list(elem)
            elif tag == 'sec':
                # Process subsections recursively with increased heading level
                self.process_section(elem, level + 1)
    
    def process_figure(self, fig_elem):
        """Process a figure element."""
        fig_id = fig_elem.get('id', '')
        
        caption = fig_elem.find('.//jats:caption', self.ns)
        caption_text = ""
        if caption is not None:
            title = caption.find('.//jats:title', self.ns)
            if title is not None and title.text:
                caption_text = title.text.strip()
            
            # Add caption paragraphs
            for p in caption.findall('.//jats:p', self.ns):
                p_text = self._get_paragraph_text(p)
                if p_text and p_text != caption_text:
                    caption_text += f" {p_text}"
        
        # In Markdown we would reference the figure file here
        # but for medRxiv XML we may not have direct access to the image files
        self.output.append(f"**Figure {fig_id}:** {caption_text}")
    
    def process_table(self, table_wrap):
        """Process a table element."""
        table_id = table_wrap.get('id', '')
        
        # Table caption
        caption = table_wrap.find('.//jats:caption', self.ns)
        caption_text = ""
        if caption is not None:
            caption_text = " ".join(caption.itertext()).strip()
        
        self.output.append(f"**Table {table_id}:** {caption_text}")
        
        # Process the actual table
        table = table_wrap.find('.//jats:table', self.ns)
        if table is not None:
            markdown_table = []
            
            # Process header row
            header_row = table.find('.//jats:tr', self.ns)
            if header_row is not None:
                headers = [self._get_element_text(th) for th in header_row.findall('.//jats:th', self.ns)]
                if headers:
                    markdown_table.append('| ' + ' | '.join(headers) + ' |')
                    markdown_table.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
            
            # Process data rows
            for row in table.findall('.//jats:tr', self.ns)[1:]:  # Skip header row
                cells = [self._get_element_text(td) for td in row.findall('.//jats:td', self.ns)]
                if cells:
                    markdown_table.append('| ' + ' | '.join(cells) + ' |')
            
            if markdown_table:
                self.output.append('\n'.join(markdown_table))
    
    def process_list(self, list_elem):
        """Process a list element."""
        list_type = list_elem.get('list-type', 'bullet')
        
        for i, item in enumerate(list_elem.findall('.//jats:list-item', self.ns), 1):
            item_text = " ".join(item.itertext()).strip()
            
            if list_type == 'ordered':
                self.output.append(f"{i}. {item_text}")
            else:
                self.output.append(f"* {item_text}")
    
    def process_back(self, back):
        """Process the back matter of the article."""
        # References
        ref_list = back.find('.//jats:ref-list', self.ns)
        if ref_list is not None:
            self.output.append("## References")
            for i, ref in enumerate(ref_list.findall('.//jats:ref', self.ns), 1):
                ref_text = " ".join(ref.itertext()).strip()
                if ref_text:
                    self.output.append(f"{i}. {ref_text}")
        
        # Appendices
        for app in back.findall('.//jats:app', self.ns):
            app_title = app.find('.//jats:title', self.ns)
            if app_title is not None and app_title.text:
                self.output.append(f"## Appendix: {app_title.text.strip()}")
            
            for elem in app:
                tag = self._strip_namespace(elem.tag)
                if tag == 'p':
                    text = self._get_paragraph_text(elem)
                    if text:
                        self.output.append(text)
    
    def _strip_namespace(self, tag):
        """Remove namespace from tag name."""
        if tag and '}' in tag:
            return tag.split('}', 1)[1]
        return tag
    
    def _get_element_text(self, elem):
        """Get text from an element, handling formatting tags."""
        if elem is None:
            return ""
        
        if not list(elem):
            return elem.text or ""
        
        text = elem.text or ""
        for child in elem:
            child_tag = self._strip_namespace(child.tag)
            
            if child_tag == 'italic':
                child_text = self._get_element_text(child)
                text += f"*{child_text}*"
            elif child_tag == 'bold':
                child_text = self._get_element_text(child)
                text += f"**{child_text}**"
            elif child_tag == 'sup':
                child_text = self._get_element_text(child)
                text += f"^{child_text}^"
            elif child_tag == 'sub':
                child_text = self._get_element_text(child)
                text += f"~{child_text}~"
            elif child_tag == 'xref':
                child_text = self._get_element_text(child)
                ref_type = child.get('ref-type', '')
                rid = child.get('rid', '')
                if ref_type == 'bibr':
                    text += f"[{child_text}]"
                elif ref_type in ('fig', 'table'):
                    text += f"[{child_text}]"
                else:
                    text += child_text
            else:
                child_text = self._get_element_text(child)
                text += child_text
            
            if child.tail:
                text += child.tail
        
        return text
    
    def _get_paragraph_text(self, p_elem):
        """Get formatted text from a paragraph element."""
        if p_elem is None:
            return ""
        
        return self._get_element_text(p_elem)


def main():
    parser = argparse.ArgumentParser(description='Convert medRxiv XML files to Markdown')
    parser.add_argument('input', help='Input XML file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory (optional)')
    parser.add_argument('-r', '--recursive', action='store_true', help='Process directories recursively')
    
    args = parser.parse_args()
    
    converter = MedRxivXmlToMarkdown()
    
    if os.path.isdir(args.input):
        # Process directory
        if args.output and not os.path.isdir(args.output):
            os.makedirs(args.output, exist_ok=True)
        
        for root, dirs, files in os.walk(args.input):
            for file in files:
                if file.lower().endswith('.xml'):
                    input_path = os.path.join(root, file)
                    
                    if args.output:
                        rel_path = os.path.relpath(input_path, args.input)
                        output_path = os.path.join(args.output, os.path.splitext(rel_path)[0] + '.md')
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    else:
                        output_path = None
                    
                    result = converter.convert_file(input_path, output_path)
                    if result:
                        print(f"Converted: {input_path} -> {result}")
            
            if not args.recursive:
                break
    else:
        # Process single file
        result = converter.convert_file(args.input, args.output)
        if result:
            print(f"Converted: {args.input} -> {result}")


if __name__ == "__main__":
    main()
