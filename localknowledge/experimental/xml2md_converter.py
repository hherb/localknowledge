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
        # JATS XML namespaces to try (in order)
        self.ns = {'jats': 'http://www.ncbi.nlm.nih.gov/JATS1'}
        # Alternative namespaces to try
        self.alt_namespaces = [
            {'jats': 'http://jats.nlm.nih.gov/ns/archiving/1.0/'},
            {'jats': 'http://dtd.nlm.nih.gov/publishing/2.3/'},
            {'jats': 'http://www.niso.org/standards/z39-96/ns/1.0/'},
            {}  # Empty namespace as fallback
        ]
        
        # HighWire Press / medRxiv specific namespaces
        self.hwp_namespaces = {
            'hwp': 'http://schema.highwire.org/Journal',
            'hw': 'org.highwire.hpp',
            'hpp': 'http://schema.highwire.org/Publishing'
        }
        
        self.output = []
        self.debug = True  # Set to False in production
        
        # Flag to indicate if we're processing a HighWire Press / medRxiv XML
        self.is_hwp_xml = False
    
    def convert_file(self, xml_path, output_path=None):
        """
        Convert an XML file to Markdown.
        
        Args:
            xml_path: Path to the XML file to convert
            output_path: If provided, save output to this file path; 
                         if None, just return the markdown text
                         
        Returns:
            If output_path is None: the markdown text as a string
            If output_path is provided: the path to the saved file
        """
        try:
            if self.debug:
                print(f"Reading file: {xml_path}")
            
            # First try to identify the XML format
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                
            # Check for medRxiv or HighWire Press format
            if "xmlns:hwp=" in xml_content or "xmlns:hw=" in xml_content:
                if self.debug:
                    print("Detected HighWire Press / medRxiv XML format")
                self.is_hwp_xml = True
            else:
                self.is_hwp_xml = False
                
            # Check for DTD or namespace declarations
            doctype_match = re.search(r'<!DOCTYPE\s+[^>]*>\s*', xml_content)
            if doctype_match and self.debug:
                print(f"Found DOCTYPE: {doctype_match.group(0)}")
                
            # Extract all namespaces for debugging
            ns_matches = re.findall(r'xmlns(?:\:[a-zA-Z0-9]+)?="([^"]+)"', xml_content)
            if ns_matches and self.debug:
                print(f"Found namespaces: {ns_matches}")
                
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            if self.debug:
                print(f"Root tag: {root.tag}")
            
            self.output = []
            
            # Process based on detected format
            if self.is_hwp_xml:
                self._process_hwp_article(root)
            else:
                # Try with the default namespace first
                self.process_article(root)
                
                # If nothing was extracted, try with alternative namespaces
                if not self.output:
                    if self.debug:
                        print("Default namespace didn't work, trying alternatives")
                    
                    for ns in self.alt_namespaces:
                        if self.debug:
                            print(f"Trying namespace: {ns}")
                        
                        self.ns = ns
                        self.process_article(root)
                        
                        if self.output:
                            if self.debug:
                                print(f"Successfully extracted content with namespace: {ns}")
                            break
            
            # If we still have no output, try a completely generic approach
            if not self.output:
                if self.debug:
                    print("All namespace approaches failed, using completely generic extraction")
                self._extract_text_generic(root)
            
            markdown_content = '\n\n'.join(self.output) if self.output else "No content could be extracted from the XML file."
            
            if output_path is not None:
                # Save to file if output path is specified
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                return output_path
            else:
                # Return the markdown content as string
                return markdown_content
            
        except Exception as e:
            if self.debug:
                import traceback
                print(f"Error converting file: {e}")
                print(traceback.format_exc())
            else:
                print(f"Error converting file: {e}")
            return f"Error converting file: {str(e)}"
    
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
        # Print root tag to help with debugging
        if self.debug:
            print(f"Root tag: {root.tag}")
            print(f"Available namespaces: {root.nsmap if hasattr(root, 'nsmap') else 'N/A'}")
        
        # Try both with and without namespace
        front_with_ns = root.find('.//jats:front', self.ns)
        front_without_ns = root.find('.//front')
        
        # Process front matter (title, authors, abstract)
        if front_with_ns is not None:
            if self.debug:
                print("Found front matter with namespace")
            self.process_front(front_with_ns)
        elif front_without_ns is not None:
            if self.debug:
                print("Found front matter without namespace")
            # Temporarily remove namespace requirement
            old_ns = self.ns
            self.ns = {}
            self.process_front(front_without_ns)
            self.ns = old_ns
        else:
            if self.debug:
                print("No front matter found - trying direct child elements")
            # Try to extract basic information directly
            title = root.find('.//article-title') or root.find('.//jats:article-title', self.ns)
            if title is not None and title.text:
                self.output.append(f"# {title.text.strip()}")
        
        # Process body (main content)
        body_with_ns = root.find('.//jats:body', self.ns)
        body_without_ns = root.find('.//body')
        
        if body_with_ns is not None:
            if self.debug:
                print("Found body with namespace")
            self.process_body(body_with_ns)
        elif body_without_ns is not None:
            if self.debug:
                print("Found body without namespace")
            # Temporarily remove namespace requirement
            old_ns = self.ns
            self.ns = {}
            self.process_body(body_without_ns)
            self.ns = old_ns
        else:
            if self.debug:
                print("No body found")
        
        # Process back matter (references, appendices)
        back_with_ns = root.find('.//jats:back', self.ns)
        back_without_ns = root.find('.//back')
        
        if back_with_ns is not None:
            if self.debug:
                print("Found back matter with namespace")
            self.process_back(back_with_ns)
        elif back_without_ns is not None:
            if self.debug:
                print("Found back matter without namespace")
            # Temporarily remove namespace requirement
            old_ns = self.ns
            self.ns = {}
            self.process_back(back_without_ns)
            self.ns = old_ns
        else:
            if self.debug:
                print("No back matter found")
            
        # If no content was processed, try a generic approach
        if not self.output:
            if self.debug:
                print("No content processed with standard approach, trying generic approach")
            self._extract_text_generic(root)
            
    def _process_hwp_article(self, root):
        """Process a HighWire Press / medRxiv article structure."""
        if self.debug:
            print("Processing HighWire Press / medRxiv XML format")
        
        # Front matter (title, authors, abstract)
        front = root.find('.//front')
        if front is not None:
            if self.debug:
                print("Found front matter in HWP format")
            self._process_hwp_front(front)
        
        # Body (main content)
        body = root.find('.//body')
        if body is not None:
            if self.debug:
                print("Found body in HWP format")
            self._process_hwp_body(body)
        
        # Back matter (references, appendices)
        back = root.find('.//back')
        if back is not None:
            if self.debug:
                print("Found back matter in HWP format")
            self._process_hwp_back(back)
            
    def _process_hwp_body(self, body):
        """Process the body of a HighWire Press / medRxiv article."""
        # Process sections
        for sec in body.findall('.//sec'):
            self._process_hwp_section(sec, 2)  # Start at level 2 (##)
    
    def _process_hwp_section(self, sec, level):
        """Process a section in a HighWire Press / medRxiv article."""
        # Get section title
        sec_id = sec.get('id', '')
        title = sec.find('.//title')
        if title is not None:
            title_text = self._get_element_text(title)
            if title_text:
                heading = '#' * level
                self.output.append(f"{heading} {title_text}")
        
        # Process paragraphs
        for p in sec.findall('.//p'):
            p_text = self._get_element_text(p)
            if p_text:
                self.output.append(p_text)
        
        # Process tables
        for table_wrap in sec.findall('.//table-wrap'):
            self._process_hwp_table(table_wrap)
        
        # Process figures
        for fig in sec.findall('.//fig'):
            self._process_hwp_figure(fig)
        
        # Process subsections recursively
        for subsec in sec.findall('.//sec'):
            if subsec != sec:  # Avoid processing the same section again
                self._process_hwp_section(subsec, level + 1)
    
    def _process_hwp_table(self, table_wrap):
        """Process a table in a HighWire Press / medRxiv article."""
        # Get table ID and caption
        table_id = table_wrap.get('id', '')
        
        caption = table_wrap.find('.//caption')
        caption_text = ""
        if caption is not None:
            title = caption.find('.//title')
            if title is not None:
                caption_text = self._get_element_text(title)
        
        if table_id or caption_text:
            if table_id and caption_text:
                self.output.append(f"**Table {table_id}:** {caption_text}")
            elif table_id:
                self.output.append(f"**Table {table_id}**")
            else:
                self.output.append(f"**Table:** {caption_text}")
        
        # Process table content
        table = table_wrap.find('.//table') or table_wrap.find('.//alternative-form/table')
        if table is not None:
            markdown_table = []
            
            # Process header row
            tr_elements = table.findall('.//tr')
            if tr_elements:
                header_row = tr_elements[0]
                headers = []
                for th in header_row.findall('.//th'):
                    th_text = self._get_element_text(th)
                    headers.append(th_text if th_text else "")
                
                if not headers:
                    # Try td if th not found
                    for td in header_row.findall('.//td'):
                        td_text = self._get_element_text(td)
                        headers.append(td_text if td_text else "")
                
                if headers:
                    markdown_table.append('| ' + ' | '.join(headers) + ' |')
                    markdown_table.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                
                # Process data rows
                for tr in tr_elements[1:]:
                    cells = []
                    for td in tr.findall('.//td'):
                        td_text = self._get_element_text(td)
                        cells.append(td_text if td_text else "")
                    
                    if cells:
                        markdown_table.append('| ' + ' | '.join(cells) + ' |')
            
            if markdown_table:
                self.output.append('\n'.join(markdown_table))
        else:
            # Handle graphic tables
            graphic = table_wrap.find('.//graphic')
            if graphic is not None:
                self.output.append("*[Table content is a graphic - not rendered in markdown]*")
    
    def _process_hwp_figure(self, fig):
        """Process a figure in a HighWire Press / medRxiv article."""
        # Get figure ID
        fig_id = fig.get('id', '')
        
        # Get caption
        caption = fig.find('.//caption')
        caption_text = ""
        if caption is not None:
            title = caption.find('.//title')
            if title is not None:
                caption_text = self._get_element_text(title)
            
            # Add any additional caption paragraphs
            for p in caption.findall('.//p'):
                p_text = self._get_element_text(p)
                if p_text and p_text != caption_text:
                    caption_text += f" {p_text}"
        
        # Output figure reference
        if fig_id or caption_text:
            if fig_id and caption_text:
                self.output.append(f"**Figure {fig_id}:** {caption_text}")
            elif fig_id:
                self.output.append(f"**Figure {fig_id}**")
            else:
                self.output.append(f"**Figure:** {caption_text}")
        
        # Note about figure graphic
        graphic = fig.find('.//graphic')
        if graphic is not None:
            self.output.append("*[Figure image not included in markdown]*")
            
    def _process_hwp_back(self, back):
        """Process the back matter of a HighWire Press / medRxiv article."""
        # Process acknowledgments
        ack = back.find('.//ack')
        if ack is not None:
            self.output.append("## Acknowledgements")
            
            # Process title if present
            title = ack.find('.//title')
            if title is not None and title.text and title.text.strip().lower() != "acknowledgements":
                self.output.append(f"### {title.text.strip()}")
            
            # Process paragraphs
            for p in ack.findall('.//p'):
                p_text = self._get_element_text(p)
                if p_text:
                    self.output.append(p_text)
        
        # Process references
        ref_list = back.find('.//ref-list')
        if ref_list is not None:
            self.output.append("## References")
            
            # Process individual references
            for ref in ref_list.findall('.//ref'):
                ref_id = ref.get('id', '')
                
                # Try different reference formats
                citation = ref.find('.//citation') or ref.find('.//element-citation') or ref.find('.//mixed-citation')
                if citation is not None:
                    ref_text = self._get_element_text(citation)
                    if ref_text:
                        if ref_id:
                            self.output.append(f"{ref_id}. {ref_text}")
                        else:
                            self.output.append(f"- {ref_text}")
                else:
                    # Fallback: get all text from reference
                    ref_text = " ".join(ref.itertext()).strip()
                    if ref_text:
                        if ref_id:
                            self.output.append(f"{ref_id}. {ref_text}")
                        else:
                            self.output.append(f"- {ref_text}")
        
        # Process appendices
        app_group = back.find('.//app-group') or back
        for app in app_group.findall('.//app'):
            app_id = app.get('id', '')
            title = app.find('.//title')
            
            # Output appendix title
            if title is not None and title.text:
                self.output.append(f"## Appendix: {title.text.strip()}")
            elif app_id:
                self.output.append(f"## Appendix {app_id}")
            else:
                self.output.append("## Appendix")
            
            # Process appendix content
            for sec in app.findall('.//sec'):
                self._process_hwp_section(sec, 3)
            
            # Process paragraphs directly in the appendix
            for p in app.findall('.//p'):
                # Check if p is a direct child of app (since standard ElementTree doesn't have getparent())
                is_direct_child = False
                for child in app:
                    if child == p:
                        is_direct_child = True
                        break
                
                if is_direct_child:
                    p_text = self._get_element_text(p)
                    if p_text:
                        self.output.append(p_text)
        
        # Process supplementary material
        for supp_material in back.findall('.//supplementary-material'):
            supp_id = supp_material.get('id', '')
            label = supp_material.find('.//label')
            caption = supp_material.find('.//caption')
            
            # Output supplementary material title
            if label is not None and label.text:
                title_text = label.text.strip()
                if caption is not None:
                    caption_text = self._get_element_text(caption)
                    if caption_text:
                        self.output.append(f"### {title_text}: {caption_text}")
                    else:
                        self.output.append(f"### {title_text}")
                else:
                    self.output.append(f"### {title_text}")
            elif supp_id:
                self.output.append(f"### Supplementary Material {supp_id}")
            else:
                self.output.append("### Supplementary Material")
            
            # Reference to media or file
            media = supp_material.find('.//media')
            if media is not None:
                href = media.get('{http://www.w3.org/1999/xlink}href', '')
                if href:
                    self.output.append(f"*Supplementary file: {href}*")
                else:
                    self.output.append("*Supplementary file available with the original article*")
            
    def _process_hwp_front(self, front):
        """Process the front matter of a HighWire Press / medRxiv article."""
        # Article title
        title_group = front.find('.//title-group')
        if title_group is not None:
            article_title = title_group.find('.//article-title')
            if article_title is not None:
                title_text = self._get_element_text(article_title)
                self.output.append(f"# {title_text}")
        
        # Journal info
        journal_meta = front.find('.//journal-meta')
        if journal_meta is not None:
            journal_title = journal_meta.find('.//journal-title')
            if journal_title is not None and journal_title.text:
                self.output.append(f"*{journal_title.text.strip()}*")
                
            publisher = journal_meta.find('.//publisher-name')
            if publisher is not None and publisher.text:
                self.output.append(f"Publisher: {publisher.text.strip()}")
        
        # Article metadata
        article_meta = front.find('.//article-meta')
        if article_meta is not None:
            # DOI and other IDs
            doi = None
            ids = []
            for article_id in article_meta.findall('.//article-id'):
                id_type = article_id.get('pub-id-type', '')
                if id_type == 'doi':
                    doi = article_id.text.strip()
                elif article_id.text:
                    ids.append(f"{id_type.upper()}: {article_id.text.strip()}")
            
            if doi:
                self.output.append(f"DOI: {doi}")
            if ids:
                self.output.append("IDs: " + ", ".join(ids))
        
            # History/Dates
            history = article_meta.find('.//history')
            if history is not None:
                dates = []
                for date in history.findall('.//date'):
                    date_type = date.get('date-type', '')
                    day = date.find('.//day')
                    month = date.find('.//month')
                    year = date.find('.//year')
                    
                    if date_type and year is not None and year.text:
                        date_str = year.text
                        if month is not None and month.text:
                            date_str = f"{month.text}/{date_str}"
                            if day is not None and day.text:
                                date_str = f"{day.text}/{date_str}"
                        dates.append(f"{date_type.capitalize()}: {date_str}")
                
                if dates:
                    self.output.append("**Dates:** " + ", ".join(dates))
        
        # Contributors/Authors
        contrib_group = front.find('.//contrib-group')
        if contrib_group is not None:
            authors = []
            for contrib in contrib_group.findall('.//contrib[@contrib-type="author"]'):
                name = contrib.find('.//name')
                if name is not None:
                    surname = name.find('.//surname')
                    given_names = name.find('.//given-names')
                    if surname is not None and given_names is not None:
                        author_name = f"{given_names.text} {surname.text}"
                        authors.append(author_name)
            
            if authors:
                self.output.append("**Authors:** " + ", ".join(authors))
        
        # Affiliations
        affiliations = front.findall('.//aff')
        if affiliations:
            aff_list = []
            for aff in affiliations:
                aff_id = aff.get('id', '')
                institution = aff.find('.//institution')
                if institution is not None and institution.text:
                    aff_text = f"{aff_id}. {institution.text.strip()}"
                    aff_list.append(aff_text)
            
            if aff_list:
                self.output.append("**Affiliations:**")
                self.output.append("\n".join(aff_list))
        
        # Abstract
        abstract = front.find('.//abstract')
        if abstract is not None:
            self.output.append("## Abstract")
            
            # Check if abstract has sections
            abstract_secs = abstract.findall('.//sec')
            if abstract_secs:
                for sec in abstract_secs:
                    title = sec.find('.//title')
                    if title is not None and title.text:
                        self.output.append(f"### {title.text.strip()}")
                    
                    for p in sec.findall('.//p'):
                        p_text = self._get_element_text(p)
                        if p_text:
                            self.output.append(p_text)
            else:
                # Process paragraphs directly
                for p in abstract.findall('.//p'):
                    p_text = self._get_element_text(p)
                    if p_text:
                        self.output.append(p_text)
    
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
        
    def _extract_text_generic(self, element, current_depth=0):
        """
        Extract text from any XML element structure in a generic way.
        This is a fallback method when the standard extraction fails.
        
        Args:
            element: The XML element to process
            current_depth: Current nesting depth (for heading levels)
        """
        if element is None:
            return
            
        # Process this element
        tag = self._strip_namespace(element.tag)
        
        # Skip certain elements
        if tag in ['xref', 'ref-list', 'table-wrap', 'fig']:
            return
            
        # Handle potential heading elements
        if tag in ['title', 'sec-title', 'heading', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            heading_text = element.text or ""
            heading_text += "".join([child.tail or "" for child in element if child.tail])
            heading_text = heading_text.strip()
            
            if heading_text:
                # Use appropriate heading level based on depth or explicit heading tag
                depth = current_depth
                if tag[0] == 'h' and len(tag) == 2 and tag[1].isdigit():
                    # For explicit h1, h2, etc tags
                    depth = int(tag[1])
                
                # Cap heading depth at 6 (markdown limit)
                depth = min(depth, 6)
                heading_prefix = '#' * max(1, depth)
                self.output.append(f"{heading_prefix} {heading_text}")
            return
        
        # Handle paragraph-like elements
        if tag in ['p', 'par', 'paragraph']:
            full_text = element.text or ""
            for child in element:
                child_text = self._get_element_text(child)
                full_text += child_text
                if child.tail:
                    full_text += child.tail
            
            if full_text.strip():
                self.output.append(full_text.strip())
            return
                
        # Get direct text content if any
        if element.text and element.text.strip():
            # Special case for single text elements that look important
            text = element.text.strip()
            if tag in ['article-title', 'article_title', 'articleTitle']:
                self.output.append(f"# {text}")
            elif tag in ['abstract']:
                self.output.append(f"## Abstract\n\n{text}")
            elif tag in ['author', 'contrib']:
                self.output.append(f"**Author:** {text}")
            elif current_depth == 0 and len(text) > 20:
                # This might be important direct text at the root level
                self.output.append(text)
        
        # Process tail text if significant
        if element.tail and element.tail.strip() and len(element.tail.strip()) > 20:
            self.output.append(element.tail.strip())
            
        # Process children recursively
        if tag in ['sec', 'section', 'div']:
            # Increment depth for hierarchical sections
            next_depth = current_depth + 1
        else:
            next_depth = current_depth
            
        for child in element:
            self._extract_text_generic(child, next_depth)


def main():
    parser = argparse.ArgumentParser(description='Convert medRxiv XML files to Markdown')
    parser.add_argument('input', help='Input XML file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory (optional)')
    parser.add_argument('-r', '--recursive', action='store_true', help='Process directories recursively')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug output')
    parser.add_argument('-p', '--print', action='store_true', help='Print output to console instead of saving to file')
    
    args = parser.parse_args()
    
    converter = MedRxivXmlToMarkdown()
    converter.debug = args.debug
    
    if os.path.isdir(args.input):
        # Process directory
        if args.output and not os.path.isdir(args.output):
            os.makedirs(args.output, exist_ok=True)
        
        for root, dirs, files in os.walk(args.input):
            for file in files:
                if file.lower().endswith('.xml'):
                    input_path = os.path.join(root, file)
                    
                    if args.print:
                        # Just print to console
                        output_path = None
                    elif args.output:
                        rel_path = os.path.relpath(input_path, args.input)
                        output_path = os.path.join(args.output, os.path.splitext(rel_path)[0] + '.md')
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    else:
                        # Default to same directory with .md extension
                        output_path = os.path.splitext(input_path)[0] + '.md'
                    
                    result = converter.convert_file(input_path, output_path)
                    
                    if args.print:
                        print("\n" + "="*40 + f" {file} " + "="*40)
                        print(result)
                    elif result:
                        print(f"Converted: {input_path} -> {result if isinstance(result, str) and os.path.exists(result) else 'output generated'}")
            
            if not args.recursive:
                break
    else:
        # Process single file
        if args.print:
            result = converter.convert_file(args.input, None)
            print(result)
        else:
            output_path = args.output if args.output else os.path.splitext(args.input)[0] + '.md'
            result = converter.convert_file(args.input, output_path)
            if result:
                print(f"Converted: {args.input} -> {result if isinstance(result, str) and os.path.exists(result) else 'output generated'}")


if __name__ == "__main__":
    main()
