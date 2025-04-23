#!/usr/bin/env python3
"""
Settings widget for the Knowledge Browser.

This module provides a configuration widget for the Knowledge Browser,
allowing users to configure search sources and search strategies.
"""

from typing import Dict, List, Any, Optional
import logging

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, 
    QComboBox, QLabel, QSlider, QSpinBox, QFormLayout, QScrollArea,
    QFrame, QPushButton
)

# Configure logging
logger = logging.getLogger(__name__)

# Try to import rerankers module
try:
    from localknowledge.ai.rerankers import get_available_rerankers
    RERANKERS_AVAILABLE = True
except ImportError:
    logger.warning("Rerankers module not available")
    RERANKERS_AVAILABLE = False

# Try to import embedding models
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    logger.warning("Ollama not available")
    OLLAMA_AVAILABLE = False


class KnowledgeBrowserSettings(QWidget):
    """Settings widget for the Knowledge Browser."""
    
    # Signal emitted when settings are changed
    settingsChanged = Signal(dict)
    
    def __init__(self, parent=None, current_settings=None):
        """
        Initialize the settings widget.
        
        Args:
            parent: Parent widget
            current_settings: Current settings dictionary
        """
        super().__init__(parent)
        
        # Default settings
        self.settings = {
            'sources': {
                'pubmed': True,
                'medrxiv': True
            },
            'search_strategies': {
                'keyword': True,
                'semantic': True,
                'hybrid': True,
                'bm25': False
            },
            'semantic_settings': {
                'embedding_model': 'snowflake-arctic-embed2:latest',
                'similarity_threshold': 0.3,
                'max_results': 20,
                'use_hyde': False,
                'hyde_model': 'gemma3:4b',
                'use_reranker': False,
                'reranker_model': 'BAAI/bge-reranker-base'
            },
            'hybrid_settings': {
                'semantic_weight': 0.5
            }
        }
        
        # Update with current settings if provided
        if current_settings:
            self._update_settings(current_settings)
        
        # Available embedding models
        self.embedding_models = self._get_available_embedding_models()
        
        # Available rerankers
        self.rerankers = self._get_available_rerankers()
        
        # Set up UI
        self.setup_ui()
    
    def _update_settings(self, current_settings: Dict[str, Any]) -> None:
        """
        Update settings with current values.
        
        Args:
            current_settings: Current settings dictionary
        """
        # Update each section if it exists
        if 'sources' in current_settings:
            self.settings['sources'].update(current_settings['sources'])
        
        if 'search_strategies' in current_settings:
            self.settings['search_strategies'].update(current_settings['search_strategies'])
        
        if 'semantic_settings' in current_settings:
            self.settings['semantic_settings'].update(current_settings['semantic_settings'])
        
        if 'hybrid_settings' in current_settings:
            self.settings['hybrid_settings'].update(current_settings['hybrid_settings'])
    
    def _get_available_embedding_models(self) -> List[Dict[str, str]]:
        """
        Get a list of available embedding models.
        
        Returns:
            List of dictionaries with model information
        """
        default_models = [
            {
                'id': 'snowflake-arctic-embed2:latest',
                'name': 'Snowflake Arctic Embed2',
                'description': 'Default embedding model'
            },
            {
                'id': 'nomic-embed-text:latest',
                'name': 'Nomic Embed Text',
                'description': 'Alternative embedding model'
            }
        ]
        
        if OLLAMA_AVAILABLE:
            try:
                # Get models from Ollama
                ollama_models = ollama.list()
                
                # Filter for embedding models
                embedding_models = []
                model_names = [model['model'] for model in ollama_models.get('models', [])]
                
                # Add known embedding models if available
                for model_id in model_names:
                    if any(keyword in model_id.lower() for keyword in ['embed', 'bge', 'jina']):
                        name_parts = model_id.split(':')[0].split('/')[-1].split('-')
                        name = ' '.join(part.capitalize() for part in name_parts)
                        embedding_models.append({
                            'id': model_id,
                            'name': name,
                            'description': 'Ollama embedding model'
                        })
                
                if embedding_models:
                    return embedding_models
            except Exception as e:
                logger.warning(f"Error getting Ollama models: {e}")
        
        return default_models
    
    def _get_available_rerankers(self) -> List[Dict[str, str]]:
        """
        Get a list of available rerankers.
        
        Returns:
            List of dictionaries with reranker information
        """
        if RERANKERS_AVAILABLE:
            try:
                return get_available_rerankers()
            except Exception as e:
                logger.warning(f"Error getting rerankers: {e}")
        
        # Default rerankers if module not available
        return [
            {
                'id': 'BAAI/bge-reranker-base',
                'name': 'BGE Reranker Base',
                'description': 'Good general purpose reranker'
            },
            {
                'id': 'cross-encoder/ms-marco-MiniLM-L-6-v2',
                'name': 'MS MARCO MiniLM',
                'description': 'Fast and efficient reranker'
            },
            {
                'id': 'cross-encoder/ms-marco-TinyBERT-L-2-v2',
                'name': 'MS MARCO TinyBERT',
                'description': 'Very lightweight reranker'
            }
        ]
    
    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create a scroll area for the settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Create a widget to hold all settings
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Add settings groups
        scroll_layout.addWidget(self._create_sources_group())
        scroll_layout.addWidget(self._create_search_strategies_group())
        scroll_layout.addWidget(self._create_semantic_settings_group())
        scroll_layout.addWidget(self._create_hybrid_settings_group())
        
        # Add stretch to push everything to the top
        scroll_layout.addStretch(1)
        
        # Set the scroll content
        scroll_area.setWidget(scroll_content)
        
        # Add the scroll area to the main layout
        main_layout.addWidget(scroll_area)
        
        # Add apply button
        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self._apply_settings)
        main_layout.addWidget(apply_button)
    
    def _create_sources_group(self) -> QGroupBox:
        """
        Create the sources group box.
        
        Returns:
            QGroupBox: Sources group box
        """
        group = QGroupBox("Search Sources")
        layout = QVBoxLayout(group)
        
        # Create checkboxes for each source
        self.pubmed_checkbox = QCheckBox("PubMed")
        self.pubmed_checkbox.setChecked(self.settings['sources'].get('pubmed', True))
        layout.addWidget(self.pubmed_checkbox)
        
        self.medrxiv_checkbox = QCheckBox("medRxiv")
        self.medrxiv_checkbox.setChecked(self.settings['sources'].get('medrxiv', True))
        layout.addWidget(self.medrxiv_checkbox)
        
        return group
    
    def _create_search_strategies_group(self) -> QGroupBox:
        """
        Create the search strategies group box.
        
        Returns:
            QGroupBox: Search strategies group box
        """
        group = QGroupBox("Search Strategies")
        layout = QVBoxLayout(group)
        
        # Create checkboxes for each strategy
        self.keyword_checkbox = QCheckBox("Keyword Search")
        self.keyword_checkbox.setChecked(self.settings['search_strategies'].get('keyword', True))
        layout.addWidget(self.keyword_checkbox)
        
        self.semantic_checkbox = QCheckBox("Semantic Search")
        self.semantic_checkbox.setChecked(self.settings['search_strategies'].get('semantic', True))
        self.semantic_checkbox.toggled.connect(self._on_semantic_toggled)
        layout.addWidget(self.semantic_checkbox)
        
        self.hybrid_checkbox = QCheckBox("Hybrid Search (Keyword + Semantic)")
        self.hybrid_checkbox.setChecked(self.settings['search_strategies'].get('hybrid', True))
        self.hybrid_checkbox.toggled.connect(self._on_hybrid_toggled)
        layout.addWidget(self.hybrid_checkbox)
        
        self.bm25_checkbox = QCheckBox("BM25 Search")
        self.bm25_checkbox.setChecked(self.settings['search_strategies'].get('bm25', False))
        layout.addWidget(self.bm25_checkbox)
        
        return group
    
    def _create_semantic_settings_group(self) -> QGroupBox:
        """
        Create the semantic settings group box.
        
        Returns:
            QGroupBox: Semantic settings group box
        """
        group = QGroupBox("Semantic Search Settings")
        layout = QFormLayout(group)
        
        # Embedding model selector
        self.embedding_model_combo = QComboBox()
        for model in self.embedding_models:
            self.embedding_model_combo.addItem(model['name'], model['id'])
        
        # Set current model
        current_model = self.settings['semantic_settings'].get('embedding_model', 'snowflake-arctic-embed2:latest')
        index = self.embedding_model_combo.findData(current_model)
        if index >= 0:
            self.embedding_model_combo.setCurrentIndex(index)
        
        layout.addRow("Embedding Model:", self.embedding_model_combo)
        
        # Similarity threshold slider
        self.similarity_label = QLabel(f"Similarity Threshold: {self.settings['semantic_settings'].get('similarity_threshold', 0.3):.2f}")
        self.similarity_slider = QSlider(Qt.Horizontal)
        self.similarity_slider.setRange(0, 100)
        self.similarity_slider.setValue(int(self.settings['semantic_settings'].get('similarity_threshold', 0.3) * 100))
        self.similarity_slider.setTickPosition(QSlider.TicksBelow)
        self.similarity_slider.setTickInterval(10)
        self.similarity_slider.valueChanged.connect(self._update_similarity_label)
        
        layout.addRow(self.similarity_label, self.similarity_slider)
        
        # Max results spinner
        self.max_results_spinner = QSpinBox()
        self.max_results_spinner.setRange(5, 100)
        self.max_results_spinner.setValue(self.settings['semantic_settings'].get('max_results', 20))
        self.max_results_spinner.setSingleStep(5)
        
        layout.addRow("Max Results:", self.max_results_spinner)
        
        # HyDE checkbox and model selector
        self.hyde_checkbox = QCheckBox("Use HyDE (Hypothetical Document Embeddings)")
        self.hyde_checkbox.setChecked(self.settings['semantic_settings'].get('use_hyde', False))
        self.hyde_checkbox.toggled.connect(self._on_hyde_toggled)
        
        layout.addRow("", self.hyde_checkbox)
        
        # HyDE model selector
        self.hyde_model_combo = QComboBox()
        self.hyde_model_combo.addItem("Gemma 3 (4B)", "gemma3:4b")
        self.hyde_model_combo.addItem("Llama 3 (8B)", "llama3:8b")
        self.hyde_model_combo.addItem("Mistral (7B)", "mistral:7b")
        
        # Set current model
        current_hyde_model = self.settings['semantic_settings'].get('hyde_model', 'gemma3:4b')
        index = self.hyde_model_combo.findData(current_hyde_model)
        if index >= 0:
            self.hyde_model_combo.setCurrentIndex(index)
        
        self.hyde_model_combo.setEnabled(self.hyde_checkbox.isChecked())
        layout.addRow("HyDE Model:", self.hyde_model_combo)
        
        # Reranker checkbox and model selector
        self.reranker_checkbox = QCheckBox("Use Reranker")
        self.reranker_checkbox.setChecked(self.settings['semantic_settings'].get('use_reranker', False))
        self.reranker_checkbox.toggled.connect(self._on_reranker_toggled)
        
        layout.addRow("", self.reranker_checkbox)
        
        # Reranker model selector
        self.reranker_model_combo = QComboBox()
        for reranker in self.rerankers:
            self.reranker_model_combo.addItem(reranker['name'], reranker['id'])
        
        # Set current model
        current_reranker = self.settings['semantic_settings'].get('reranker_model', 'BAAI/bge-reranker-base')
        index = self.reranker_model_combo.findData(current_reranker)
        if index >= 0:
            self.reranker_model_combo.setCurrentIndex(index)
        
        self.reranker_model_combo.setEnabled(self.reranker_checkbox.isChecked())
        layout.addRow("Reranker Model:", self.reranker_model_combo)
        
        return group
    
    def _create_hybrid_settings_group(self) -> QGroupBox:
        """
        Create the hybrid settings group box.
        
        Returns:
            QGroupBox: Hybrid settings group box
        """
        group = QGroupBox("Hybrid Search Settings")
        layout = QFormLayout(group)
        
        # Semantic weight slider
        semantic_weight = self.settings['hybrid_settings'].get('semantic_weight', 0.5)
        self.semantic_weight_label = QLabel(f"Semantic Weight: {semantic_weight:.2f}")
        self.semantic_weight_slider = QSlider(Qt.Horizontal)
        self.semantic_weight_slider.setRange(0, 100)
        self.semantic_weight_slider.setValue(int(semantic_weight * 100))
        self.semantic_weight_slider.setTickPosition(QSlider.TicksBelow)
        self.semantic_weight_slider.setTickInterval(10)
        self.semantic_weight_slider.valueChanged.connect(self._update_semantic_weight_label)
        
        layout.addRow(self.semantic_weight_label, self.semantic_weight_slider)
        
        # Enable/disable based on hybrid checkbox
        group.setEnabled(self.settings['search_strategies'].get('hybrid', True))
        
        return group
    
    @Slot(int)
    def _update_similarity_label(self, value: int) -> None:
        """
        Update the similarity threshold label.
        
        Args:
            value: Slider value (0-100)
        """
        threshold = value / 100.0
        self.similarity_label.setText(f"Similarity Threshold: {threshold:.2f}")
    
    @Slot(int)
    def _update_semantic_weight_label(self, value: int) -> None:
        """
        Update the semantic weight label.
        
        Args:
            value: Slider value (0-100)
        """
        weight = value / 100.0
        self.semantic_weight_label.setText(f"Semantic Weight: {weight:.2f}")
    
    @Slot(bool)
    def _on_semantic_toggled(self, checked: bool) -> None:
        """
        Handle semantic search checkbox toggle.
        
        Args:
            checked: Whether the checkbox is checked
        """
        # If semantic is disabled, also disable hybrid
        if not checked and self.hybrid_checkbox.isChecked():
            self.hybrid_checkbox.setChecked(False)
    
    @Slot(bool)
    def _on_hybrid_toggled(self, checked: bool) -> None:
        """
        Handle hybrid search checkbox toggle.
        
        Args:
            checked: Whether the checkbox is checked
        """
        # If hybrid is enabled, also enable semantic and keyword
        if checked:
            self.semantic_checkbox.setChecked(True)
            self.keyword_checkbox.setChecked(True)
    
    @Slot(bool)
    def _on_hyde_toggled(self, checked: bool) -> None:
        """
        Handle HyDE checkbox toggle.
        
        Args:
            checked: Whether the checkbox is checked
        """
        self.hyde_model_combo.setEnabled(checked)
    
    @Slot(bool)
    def _on_reranker_toggled(self, checked: bool) -> None:
        """
        Handle reranker checkbox toggle.
        
        Args:
            checked: Whether the checkbox is checked
        """
        self.reranker_model_combo.setEnabled(checked)
    
    @Slot()
    def _apply_settings(self) -> None:
        """Apply the current settings and emit the settingsChanged signal."""
        # Update settings from UI
        self.settings['sources'] = {
            'pubmed': self.pubmed_checkbox.isChecked(),
            'medrxiv': self.medrxiv_checkbox.isChecked()
        }
        
        self.settings['search_strategies'] = {
            'keyword': self.keyword_checkbox.isChecked(),
            'semantic': self.semantic_checkbox.isChecked(),
            'hybrid': self.hybrid_checkbox.isChecked(),
            'bm25': self.bm25_checkbox.isChecked()
        }
        
        self.settings['semantic_settings'] = {
            'embedding_model': self.embedding_model_combo.currentData(),
            'similarity_threshold': self.similarity_slider.value() / 100.0,
            'max_results': self.max_results_spinner.value(),
            'use_hyde': self.hyde_checkbox.isChecked(),
            'hyde_model': self.hyde_model_combo.currentData(),
            'use_reranker': self.reranker_checkbox.isChecked(),
            'reranker_model': self.reranker_model_combo.currentData()
        }
        
        self.settings['hybrid_settings'] = {
            'semantic_weight': self.semantic_weight_slider.value() / 100.0
        }
        
        # Emit signal with updated settings
        self.settingsChanged.emit(self.settings)
        
        logger.info("Knowledge Browser settings applied")
    
    def get_settings(self) -> Dict[str, Any]:
        """
        Get the current settings.
        
        Returns:
            Dict: Current settings
        """
        return self.settings
