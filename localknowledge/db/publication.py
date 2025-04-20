"""This module defines a Base class for publication objects using Pydantic to ensure consistent
data validation and serialization. It also includes a method to convert the object to a dictionary.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from localknowledge.db.base import DatabaseManager

class Publication(BaseModel):
    """
    Base class for publication objects.
    
    This class uses Pydantic for data validation and serialization.
    """
    id: int
    doi : Optional[str] = None  #not every publication has one
    pmid: Optional[str] = None  #only applicable for pubmed records
    source: str   #one of ['medrxiv', 'pubmed', 'url', 'localfile', 'other']
    title: str
    abstract: Optional[str] = None
    authors: str #a list of authors formatted as a string
    publication: str #the journal etc
    publication_date: datetime  #date of publication, could be just the year
    url: Optional[str] = None   #where the publication could be found
    pdf_url: Optional[str] = None  #where the pdf could be found
    pdf_filename: Optional[str] = None #filename of the pdf on our local system, if available
    full_text: Optional[str] = None  #markdown, html, or clear text

    keywords: List[str] = Field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the publication object to a dictionary.
        
        Returns:
            Dictionary representation of the publication object.
        """
        return self.dict(by_alias=True)