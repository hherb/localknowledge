"""
Text chunking module for LocalKnowledge.

This module provides various strategies for chunking text into smaller,
semantically meaningful pieces for processing, embedding, or analysis.
"""

from localknowledge.textprocessing.chunking.base import BaseChunker, Chunk
from localknowledge.textprocessing.chunking.text_chunker import TextChunker
from localknowledge.textprocessing.chunking.markdown_chunker import MarkdownChunker
from localknowledge.textprocessing.chunking.AdaptiveTextChunker import AdaptiveTextChunker
from localknowledge.db.chunker import Chunk as DBChunk, ChunkingDatabaseManager

__all__ = [
    'BaseChunker',
    'TextChunker',
    'MarkdownChunker',
    'AdaptiveTextChunker',
    'Chunk',
    'DBChunk',
    'ChunkingDatabaseManager'
]
