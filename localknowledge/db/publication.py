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
    doi : Optional[str] = None
    pmid: Optional[str] = None
    source: str   #one of ['medrxiv', 'pubmed', 'url', 'localfile', 'other']
    title: str
    abstract: Optional[str] = None
    authors: List[str]
    publication: str
    publication_date: datetime
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    pdf_filename: Optional[str] = None
    full_text: Optional[str] = None

    keywords: List[str] = Field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the publication object to a dictionary.
        
        Returns:
            Dictionary representation of the publication object.
        """
        return self.dict(by_alias=True)