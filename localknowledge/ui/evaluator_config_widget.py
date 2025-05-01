"""
Evaluator configuration widget for managing evaluators.

This module provides a widget for configuring evaluators, including selecting models,
setting parameters, and creating custom prompts.
"""

import logging
import json
from typing import Dict, Any, Optional, List

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QTextEdit, QPushButton,
    QDoubleSpinBox, QSpinBox, QListWidget, QListWidgetItem,
    QMessageBox, QSplitter, QFrame
)

from localknowledge.db.models import ModelsDatabaseManager
from localknowledge.db.reading_suggestions import ReadingSuggestionsManager

# Configure logging
logger = logging.getLogger(__name__)


class EvaluatorConfigWidget(QWidget):
    """Widget for configuring evaluators."""

    # Signal emitted when evaluators are updated
    evaluatorsUpdated = Signal()

    def __init__(self, parent=None):
        """Initialize the evaluator configuration widget."""
        super().__init__(parent)

        # Initialize database managers
        self.models_db = ModelsDatabaseManager()
        self.suggestions_db = ReadingSuggestionsManager()

        # Initialize UI
        self._init_ui()

        # Load initial data
        self._load_evaluators()
        self._load_models()

    def _init_ui(self):
        """Initialize the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # Title
        title_label = QLabel("<h3>Evaluator Configuration</h3>")
        main_layout.addWidget(title_label)

        # Splitter for evaluator list and editor
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Evaluator list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Evaluator list
        list_label = QLabel("<b>Available Evaluators:</b>")
        left_layout.addWidget(list_label)

        self.evaluator_list = QListWidget()
        self.evaluator_list.setMinimumWidth(200)
        self.evaluator_list.currentItemChanged.connect(self._on_evaluator_selected)
        left_layout.addWidget(self.evaluator_list)

        # Buttons for list management
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("New")
        self.add_btn.clicked.connect(self._on_add_clicked)
        button_layout.addWidget(self.add_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setEnabled(False)  # Disabled until an evaluator is selected
        button_layout.addWidget(self.delete_btn)

        left_layout.addLayout(button_layout)

        # Right panel - Evaluator editor
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Editor form
        editor_label = QLabel("<b>Evaluator Details:</b>")
        right_layout.addWidget(editor_label)

        editor_form = QGroupBox()
        form_layout = QFormLayout(editor_form)

        # Name field
        self.name_edit = QLineEdit()
        form_layout.addRow("Name:", self.name_edit)

        # Model selector
        self.model_combo = QComboBox()
        form_layout.addRow("Model:", self.model_combo)

        # Parameters group
        params_group = QGroupBox("Model Parameters")
        params_layout = QFormLayout(params_group)

        # Temperature with slider
        temp_layout = QHBoxLayout()

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        self.temperature_spin.setFixedWidth(70)
        temp_layout.addWidget(self.temperature_spin)

        self.temperature_slider = QSlider(Qt.Horizontal)
        self.temperature_slider.setRange(0, 200)  # 0.0 to 2.0 with 100 steps per unit
        self.temperature_slider.setValue(70)      # 0.7 default
        self.temperature_slider.setTickPosition(QSlider.TicksBelow)
        self.temperature_slider.setTickInterval(10)
        temp_layout.addWidget(self.temperature_slider)

        # Connect slider and spin box
        self.temperature_slider.valueChanged.connect(self._on_temp_slider_changed)
        self.temperature_spin.valueChanged.connect(self._on_temp_spin_changed)

        params_layout.addRow("Temperature:", temp_layout)

        # Top-K with integer input
        top_k_layout = QHBoxLayout()

        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(0, 100)
        self.top_k_spin.setValue(40)
        self.top_k_spin.setFixedWidth(70)
        top_k_layout.addWidget(self.top_k_spin)

        # Add a label explaining Top-K
        top_k_label = QLabel("(Higher = more diverse)")
        top_k_label.setStyleSheet("color: gray; font-style: italic;")
        top_k_layout.addWidget(top_k_label)
        top_k_layout.addStretch()

        params_layout.addRow("Top-K:", top_k_layout)

        # Top-P with integer input and slider
        top_p_layout = QHBoxLayout()

        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(0.9)
        self.top_p_spin.setFixedWidth(70)
        top_p_layout.addWidget(self.top_p_spin)

        self.top_p_slider = QSlider(Qt.Horizontal)
        self.top_p_slider.setRange(0, 100)  # 0.0 to 1.0 with 100 steps
        self.top_p_slider.setValue(90)      # 0.9 default
        self.top_p_slider.setTickPosition(QSlider.TicksBelow)
        self.top_p_slider.setTickInterval(10)
        top_p_layout.addWidget(self.top_p_slider)

        # Connect slider and spin box
        self.top_p_slider.valueChanged.connect(self._on_top_p_slider_changed)
        self.top_p_spin.valueChanged.connect(self._on_top_p_spin_changed)

        params_layout.addRow("Top-P:", top_p_layout)

        form_layout.addRow("", params_group)

        # Prompt field
        prompt_label = QLabel("Custom Prompt:")
        form_layout.addRow(prompt_label)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(150)
        self.prompt_edit.setPlaceholderText("Enter a custom prompt for the evaluator...")
        form_layout.addRow(self.prompt_edit)

        right_layout.addWidget(editor_form)

        # Save button
        self.save_btn = QPushButton("Save Evaluator")
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.save_btn.setEnabled(False)  # Disabled until an evaluator is selected or new is clicked
        right_layout.addWidget(self.save_btn)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)

        # Set initial splitter sizes (40% list, 60% editor)
        splitter.setSizes([400, 600])

        # Add splitter to main layout
        main_layout.addWidget(splitter)

        # Set initial state
        self._clear_editor()

    def _load_evaluators(self):
        """Load evaluators from the database into the list widget."""
        try:
            # Clear existing items
            self.evaluator_list.clear()

            # Get all evaluators
            evaluators = self.suggestions_db.get_evaluators()

            # Add evaluators to list
            for evaluator in evaluators:
                item = QListWidgetItem(evaluator.get('name', 'Unknown Evaluator'))
                item.setData(Qt.UserRole, evaluator)
                self.evaluator_list.addItem(item)

            logger.info(f"Loaded {len(evaluators)} evaluators")
        except Exception as e:
            logger.error(f"Error loading evaluators: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load evaluators: {str(e)}")

    def _load_models(self):
        """Load models from the database into the model combo box."""
        try:
            # Clear existing items
            self.model_combo.clear()

            # Get completion models (models that can be used for chat/completion)
            models = self.models_db.get_completion_models()

            # Add models to combo box
            for model in models:
                model_name = model.get('name', 'Unknown Model')
                provider_name = model.get('provider_name', 'Unknown Provider')
                display_name = f"{model_name} ({provider_name})"
                self.model_combo.addItem(display_name, model)

            logger.info(f"Loaded {len(models)} models")
        except Exception as e:
            logger.error(f"Error loading models: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load models: {str(e)}")

    def _clear_editor(self):
        """Clear the editor form."""
        self.name_edit.clear()
        self.model_combo.setCurrentIndex(-1)

        # Reset temperature controls
        self.temperature_spin.setValue(0.7)
        self.temperature_slider.setValue(70)

        # Reset top-k control
        self.top_k_spin.setValue(40)

        # Reset top-p controls
        self.top_p_spin.setValue(0.9)
        self.top_p_slider.setValue(90)

        self.prompt_edit.clear()

        # Set default prompt
        default_prompt = """
You are a medical expert. You are evaluating a text for its relevance to a research question.
Consider carefully how likely the provided text will contribute towards answering the question.

The research question is: {question}
The text is: {document}

Please rate the text on a scale of 0 to 3, where:
0 means the document is not relevant at all
1 means the document is somewhat relevant, tangentially related to the question
2 means the document is very likely relevant to answer the question, it should not be missed
3 means the document answers the question, it is essential and must be included in the reading list

Provide a brief reason for your rating in no more than 3 brief sentences. Keep it short.

IMPORTANT: You must respond ONLY with a valid JSON object in the following format:
{"rating": <rating>, "reason": "<reason>"}

Do not include any other text, explanations, or formatting outside of this JSON object.
The rating must be a number (0, 1, 2, or 3) and the reason must be a string.
"""
        self.prompt_edit.setPlainText(default_prompt.strip())

        # Disable save and delete buttons
        self.save_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        # Clear current evaluator
        self.current_evaluator = None

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_evaluator_selected(self, current, previous):
        """Handle evaluator selection in the list."""
        if not current:
            self._clear_editor()
            return

        # Get evaluator data
        evaluator = current.data(Qt.UserRole)
        self.current_evaluator = evaluator

        # Populate editor form
        self.name_edit.setText(evaluator.get('name', ''))

        # Set model
        model_name = evaluator.get('model_id', '')
        for i in range(self.model_combo.count()):
            model_data = self.model_combo.itemData(i)
            if model_data and model_data.get('name') == model_name:
                self.model_combo.setCurrentIndex(i)
                break

        # Set parameters
        parameters = evaluator.get('parameters', {})
        if isinstance(parameters, str):
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}

        # Set temperature controls
        temperature = parameters.get('temperature', 0.7)
        self.temperature_spin.setValue(temperature)
        self.temperature_slider.setValue(int(temperature * 100))

        # Set top-k control
        self.top_k_spin.setValue(parameters.get('top_k', 40))

        # Set top-p controls
        top_p = parameters.get('top_p', 0.9)
        self.top_p_spin.setValue(top_p)
        self.top_p_slider.setValue(int(top_p * 100))

        # Set prompt
        self.prompt_edit.setPlainText(evaluator.get('prompt', ''))

        # Enable save and delete buttons
        self.save_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    @Slot()
    def _on_add_clicked(self):
        """Handle add button click."""
        self._clear_editor()
        self.save_btn.setEnabled(True)
        self.name_edit.setFocus()

    @Slot()
    def _on_delete_clicked(self):
        """Handle delete button click."""
        if not self.current_evaluator:
            return

        # Confirm deletion
        evaluator_name = self.current_evaluator.get('name', 'Unknown Evaluator')
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the evaluator '{evaluator_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Delete evaluator
        evaluator_id = self.current_evaluator.get('id')
        if not evaluator_id:
            logger.warning("No evaluator ID found for deletion")
            return

        try:
            success = self.suggestions_db.delete_evaluator(evaluator_id)

            if success:
                logger.info(f"Deleted evaluator with ID {evaluator_id}")
                QMessageBox.information(
                    self,
                    "Success",
                    f"Deleted evaluator '{evaluator_name}'."
                )
            else:
                logger.warning(f"Failed to delete evaluator with ID {evaluator_id}")
                QMessageBox.warning(
                    self,
                    "Warning",
                    "Could not delete the evaluator. It may be in use by reading suggestions."
                )

            # Reload evaluators
            self._load_evaluators()

            # Clear editor
            self._clear_editor()

            # Emit signal
            self.evaluatorsUpdated.emit()

        except Exception as e:
            logger.error(f"Error deleting evaluator: {e}")
            QMessageBox.warning(self, "Error", f"Failed to delete evaluator: {str(e)}")

    @Slot(int)
    def _on_temp_slider_changed(self, value):
        """Handle temperature slider value change."""
        # Convert slider value (0-200) to temperature (0.0-2.0)
        temperature = value / 100.0
        # Update spin box without triggering its valueChanged signal
        self.temperature_spin.blockSignals(True)
        self.temperature_spin.setValue(temperature)
        self.temperature_spin.blockSignals(False)

    @Slot(float)
    def _on_temp_spin_changed(self, value):
        """Handle temperature spin box value change."""
        # Convert temperature (0.0-2.0) to slider value (0-200)
        slider_value = int(value * 100)
        # Update slider without triggering its valueChanged signal
        self.temperature_slider.blockSignals(True)
        self.temperature_slider.setValue(slider_value)
        self.temperature_slider.blockSignals(False)

    @Slot(int)
    def _on_top_p_slider_changed(self, value):
        """Handle top-p slider value change."""
        # Convert slider value (0-100) to top-p (0.0-1.0)
        top_p = value / 100.0
        # Update spin box without triggering its valueChanged signal
        self.top_p_spin.blockSignals(True)
        self.top_p_spin.setValue(top_p)
        self.top_p_spin.blockSignals(False)

    @Slot(float)
    def _on_top_p_spin_changed(self, value):
        """Handle top-p spin box value change."""
        # Convert top-p (0.0-1.0) to slider value (0-100)
        slider_value = int(value * 100)
        # Update slider without triggering its valueChanged signal
        self.top_p_slider.blockSignals(True)
        self.top_p_slider.setValue(slider_value)
        self.top_p_slider.blockSignals(False)

    @Slot()
    def _on_save_clicked(self):
        """Handle save button click."""
        # Validate input
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a name for the evaluator.")
            self.name_edit.setFocus()
            return

        model_idx = self.model_combo.currentIndex()
        if model_idx < 0:
            QMessageBox.warning(self, "Validation Error", "Please select a model for the evaluator.")
            self.model_combo.setFocus()
            return

        # Get model data
        model_data = self.model_combo.itemData(model_idx)
        model_name = model_data.get('name', '')

        # Get parameters
        parameters = {
            "temperature": self.temperature_spin.value(),
            "top_k": self.top_k_spin.value(),
            "top_p": self.top_p_spin.value(),
            "type": "document_evaluator"
        }

        # Get prompt
        prompt = self.prompt_edit.toPlainText().strip()

        try:
            if self.current_evaluator and self.current_evaluator.get('id'):
                # Update existing evaluator
                success = self.suggestions_db.update_evaluator(
                    evaluator_id=self.current_evaluator.get('id'),
                    name=name,
                    model_id=model_name,
                    parameters=parameters,
                    prompt=prompt
                )

                if success:
                    logger.info(f"Updated evaluator with ID {self.current_evaluator.get('id')}")
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Updated evaluator '{name}'."
                    )
                else:
                    logger.error(f"Failed to update evaluator with ID {self.current_evaluator.get('id')}")
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to update evaluator. Please check the logs for details."
                    )
                    return

            else:
                # Create new evaluator
                from localknowledge.context import get_current_user
                user = get_current_user()
                user_id = user.get('id') if user else None

                evaluator_id = self.suggestions_db.add_evaluator(
                    name=name,
                    user_id=user_id,
                    model_id=model_name,
                    parameters=parameters,
                    prompt=prompt
                )

                if evaluator_id:
                    logger.info(f"Created new evaluator with ID {evaluator_id}")
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Created new evaluator '{name}'."
                    )
                else:
                    logger.error("Failed to create evaluator")
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to create evaluator. Please check the logs for details."
                    )
                    return

            # Reload evaluators
            self._load_evaluators()

            # Clear editor
            self._clear_editor()

            # Emit signal
            self.evaluatorsUpdated.emit()

        except Exception as e:
            logger.error(f"Error saving evaluator: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save evaluator: {str(e)}")
