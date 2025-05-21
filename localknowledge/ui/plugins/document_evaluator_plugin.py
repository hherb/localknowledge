#!/usr/bin/env python3
"""
Document Evaluator Plugin for RWB

This plugin provides a user interface for evaluating documents against research questions
using AI models and comparing with human evaluations.
"""

import os
import sys
import logging
from typing import Dict, List, Optional, Any

from PySide6.QtCore import Qt, Signal, Slot, QDate, QTimer, QThread, QObject
from PySide6.QtGui import QIcon, QAction, QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QComboBox, QLabel, QSpinBox, QDateEdit, QPushButton,
    QFrame, QMessageBox, QProgressBar, QSizePolicy,
    QRadioButton, QButtonGroup, QCheckBox
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# Set this module's logger to WARNING level to reduce debug output
logger.setLevel(logging.WARNING)
# Also reduce ollama debug output
logging.getLogger('ollama').setLevel(logging.WARNING)

# Get access to the parent package
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the plugin base and registration
from rwb_main import PluginBase
from localknowledge.ui.plugins.plugin_finder import register_plugin

# Import document evaluator will be done in the worker class to avoid circular imports

# Import database managers
from localknowledge.db.document import DocumentDatabaseManager
from localknowledge.db.research_questions import ResearchQuestionsManager
from localknowledge.db.reading_suggestions import ReadingSuggestionsManager
from localknowledge.db.evaluations import EvaluationsDatabaseManager
from localknowledge.db.chunker import ChunkingDatabaseManager, Chunk

# Import UI components
from localknowledge.ui.document_list_widget import DocumentListWidget
from localknowledge.ui.document_display_widget import DocumentDisplayWidget

# Import context management
from localknowledge.context import (
    register_context_listener, get_current_user, get_current_project,
    CURRENT_USER, CURRENT_PROJECT
)

# Worker class for background document evaluation
class EvaluationWorker(QObject):
    """Worker class for evaluating documents in a background thread."""

    # Signals
    document_evaluated = Signal(dict, object)  # document, evaluation
    evaluation_complete = Signal(int)  # number of documents evaluated
    evaluation_error = Signal(str)  # error message
    progress_updated = Signal(int, int)  # current, total

    def __init__(self,
                 documents: List[Dict[str, Any]],
                 question_text: str,
                 model_name: str):
        """
        Initialize the worker.

        Args:
            documents: List of documents to evaluate
            question_text: Research question text
            model_name: Name of the model to use for evaluation
        """
        super().__init__()
        self.documents = documents
        self.question_text = question_text
        self.model_name = model_name
        self.running = False

    def run(self):
        """Run the evaluation process."""
        self.running = True

        try:
            # Create document evaluator
            from localknowledge.ai.document_evaluator import DocumentEvaluator
            # Configure the evaluator's logger to reduce debug output
            import logging
            eval_logger = logging.getLogger('localknowledge.ai.document_evaluator')
            eval_logger.setLevel(logging.WARNING)
            evaluator = DocumentEvaluator(model_name=self.model_name)

            # Evaluate each document
            for i, document in enumerate(self.documents):
                if not self.running:
                    break

                # Emit progress
                self.progress_updated.emit(i + 1, len(self.documents))

                # Evaluate the document
                evaluation = evaluator.evaluate(
                    question=self.question_text,
                    document_id=document['id']
                )

                # Emit result
                self.document_evaluated.emit(document, evaluation)

            # Emit completion signal
            self.evaluation_complete.emit(len(self.documents))

        except Exception as e:
            # Emit error signal
            self.evaluation_error.emit(str(e))

        finally:
            self.running = False

    def stop(self):
        """Stop the evaluation process."""
        self.running = False


@register_plugin
class DocumentEvaluatorPlugin(PluginBase):
    """Document evaluator plugin for RWB that allows evaluating documents against research questions."""

    plugin_name = "Document Evaluator"
    plugin_description = "Evaluate documents against research questions and compare AI with human evaluations"
    plugin_icon = ":/icons/evaluate.png"  # Replace with actual icon path

    def __init__(self, parent=None):
        """Initialize the plugin."""
        super().__init__(parent)

        # Initialize database managers
        self.db_manager = DocumentDatabaseManager()
        self.questions_manager = ResearchQuestionsManager()
        self.suggestions_manager = ReadingSuggestionsManager()
        self.evaluations_manager = EvaluationsDatabaseManager()
        self.chunking_manager = ChunkingDatabaseManager()

        # Initialize document evaluator
        self.document_evaluator = None  # Will be created when needed with the selected model

        # Initialize current document
        self.current_document = None

        # Initialize thread-related variables
        self.worker = None
        self.thread = None
        self.evaluated_count = 0

        # Get current user and project from context
        user = get_current_user()
        self.user_id = user.get('id') if user else None

        project = get_current_project()
        self.project_id = project.get('id') if project else None

        # Register context listeners
        register_context_listener(CURRENT_USER, self._on_user_changed)
        register_context_listener(CURRENT_PROJECT, self._on_project_changed)

        # Set up UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Status banner (initially hidden)
        self.status_banner = QFrame()
        self.status_banner.setFrameShape(QFrame.StyledPanel)
        self.status_banner.setFrameShadow(QFrame.Raised)
        self.status_banner.setStyleSheet("background-color: #f8f9fa;")
        self.status_banner.setMaximumHeight(40)
        self.status_banner.setVisible(False)

        status_layout = QHBoxLayout(self.status_banner)
        status_layout.setContentsMargins(10, 5, 10, 5)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)

        # Progress bar (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)

        # Close button for the banner
        close_btn = QPushButton("×")
        close_btn.setMaximumWidth(20)
        close_btn.setFlat(True)
        close_btn.clicked.connect(lambda: self.status_banner.setVisible(False))
        status_layout.addWidget(close_btn)

        main_layout.addWidget(self.status_banner)

        # Control panel at the top
        control_panel = QFrame()
        control_panel.setFrameShape(QFrame.StyledPanel)
        control_panel.setFrameShadow(QFrame.Raised)
        control_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        control_layout = QHBoxLayout(control_panel)

        # Research question selector
        question_label = QLabel("Research Question:")
        control_layout.addWidget(question_label)

        self.question_combo = QComboBox()
        self.question_combo.setMinimumWidth(300)
        control_layout.addWidget(self.question_combo)

        # Evaluator model selector
        model_label = QLabel("Evaluator Model:")
        control_layout.addWidget(model_label)

        self.model_combo = QComboBox()
        control_layout.addWidget(self.model_combo)

        # Number of records input
        records_label = QLabel("Records:")
        control_layout.addWidget(records_label)

        self.records_spin = QSpinBox()
        self.records_spin.setMinimum(1)
        self.records_spin.setMaximum(100)
        self.records_spin.setValue(10)
        control_layout.addWidget(self.records_spin)

        # Start date selector
        date_label = QLabel("From Date:")
        control_layout.addWidget(date_label)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate().addMonths(-1))  # Default to 1 month ago
        control_layout.addWidget(self.date_edit)

        # Skip evaluated checkbox
        self.skip_evaluated_cb = QCheckBox("Skip Evaluated")
        self.skip_evaluated_cb.setChecked(True)
        self.skip_evaluated_cb.setToolTip("Skip documents already evaluated by the selected evaluator")
        control_layout.addWidget(self.skip_evaluated_cb)

        # Pending human review checkbox
        self.pending_review_cb = QCheckBox("Pending Human Review")
        self.pending_review_cb.setChecked(False)
        self.pending_review_cb.setToolTip("Show only documents that need human review for the selected research question")
        self.pending_review_cb.stateChanged.connect(self._on_pending_review_changed)
        control_layout.addWidget(self.pending_review_cb)

        # Evaluate button
        self.evaluate_btn = QPushButton("Evaluate")
        self.evaluate_btn.clicked.connect(self._on_evaluate_clicked)
        control_layout.addWidget(self.evaluate_btn)

        # Add control panel to main layout
        main_layout.addWidget(control_panel)

        # Main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Main horizontal splitter for document list and right panel
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Document list on the left
        self.document_list = DocumentListWidget()
        self.document_list.documentSelected.connect(self._on_document_selected)
        self.main_splitter.addWidget(self.document_list)

        # Right panel with vertical splitter for document display and evaluations
        self.right_splitter = QSplitter(Qt.Vertical)

        # Document display on top
        # Get PDF base directory from context
        from localknowledge.context import get_pdf_base_dir
        pdf_base_dir = get_pdf_base_dir()

        self.document_display = DocumentDisplayWidget(
            parent=self,
            status_bar=None,  # We'll handle status messages ourselves
            db_manager=self.db_manager,
            pdf_base_dir=str(pdf_base_dir)
        )

        # Connect to document display signals
        self.document_display.documentBookmarked.connect(self._on_document_bookmarked)
        self.right_splitter.addWidget(self.document_display)

        # Evaluations panel at the bottom of right splitter
        evaluations_container = QWidget()
        evaluations_container_layout = QVBoxLayout(evaluations_container)
        evaluations_container_layout.setContentsMargins(0, 0, 0, 0)

        # Existing evaluations section
        existing_evaluations_label = QLabel("<b>Evaluations:</b>")
        evaluations_container_layout.addWidget(existing_evaluations_label)

        # Create a scrollable area for evaluations
        from PySide6.QtWidgets import QScrollArea
        self.evaluations_scroll_area = QScrollArea()
        self.evaluations_scroll_area.setWidgetResizable(True)
        self.evaluations_scroll_area.setFrameShape(QFrame.NoFrame)

        # Create the content widget for the scroll area
        self.evaluations_list = QFrame()
        self.evaluations_list.setFrameShape(QFrame.NoFrame)
        self.evaluations_list_layout = QVBoxLayout(self.evaluations_list)
        self.evaluations_list_layout.setContentsMargins(0, 0, 0, 0)
        self.evaluations_list_layout.setSpacing(5)

        # Add a placeholder label
        self.no_evaluations_label = QLabel("No evaluations available for this document")
        self.no_evaluations_label.setStyleSheet("color: gray; font-style: italic;")
        self.evaluations_list_layout.addWidget(self.no_evaluations_label)

        # Add stretch to push content to the top
        self.evaluations_list_layout.addStretch()

        # Set the widget for the scroll area
        self.evaluations_scroll_area.setWidget(self.evaluations_list)

        # Add the scroll area to the container
        evaluations_container_layout.addWidget(self.evaluations_scroll_area)

        # Human rating section
        human_rating_panel = QFrame()
        human_rating_panel.setFrameShape(QFrame.NoFrame)
        human_rating_layout = QHBoxLayout(human_rating_panel)
        human_rating_layout.setContentsMargins(0, 10, 0, 0)

        # Human rating label
        human_rating_layout.addWidget(QLabel("<b>Your Rating:</b>"))

        # Rating radio buttons
        self.rating_buttons = []
        rating_button_group = QButtonGroup(self)

        # Add "n/a" button for not rated yet
        na_btn = QRadioButton("n/a")
        na_btn.setProperty("rating", -1)  # Use -1 to indicate not rated
        na_btn.clicked.connect(self._on_rating_clicked)
        human_rating_layout.addWidget(na_btn)
        self.rating_buttons.append(na_btn)
        rating_button_group.addButton(na_btn, -1)

        for i in range(4):  # 0-3 ratings
            btn = QRadioButton(str(i))
            btn.setProperty("rating", i)
            btn.clicked.connect(self._on_rating_clicked)
            human_rating_layout.addWidget(btn)
            self.rating_buttons.append(btn)
            rating_button_group.addButton(btn, i)

        # Rating explanation
        human_rating_layout.addWidget(QLabel("n/a: Not rated, 0: Not relevant, 1: Somewhat relevant, 2: Very relevant, 3: Essential"))

        # Add human rating panel to evaluations layout
        evaluations_container_layout.addWidget(human_rating_panel)

        # Add evaluations container to right splitter
        self.right_splitter.addWidget(evaluations_container)

        # Set initial right splitter sizes (70% document display, 30% evaluations)
        self.right_splitter.setSizes([700, 300])

        # Add right splitter to main splitter
        self.main_splitter.addWidget(self.right_splitter)

        # Set initial main splitter sizes (40% list, 60% right panel)
        self.main_splitter.setSizes([400, 600])

        # Add main splitter to content layout
        content_layout.addWidget(self.main_splitter)

        # Set content widget to stretch
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(content_widget, 1)  # Add with stretch factor

        # Load initial data
        self._load_research_questions()
        self._load_evaluator_models()

    def _load_research_questions(self):
        """Load research questions into the combo box."""
        try:
            # Clear existing items
            self.question_combo.clear()

            # Get all research questions (not filtered by project)
            # Since there's no direct method to get all questions, we'll use a direct query
            query = """
            SELECT * FROM research_questions
            ORDER BY id
            """
            questions = self.questions_manager.execute(query) or []

            # Add questions to combo box
            for question in questions:
                question_text = question.get('question', 'Unknown Question')
                self.question_combo.addItem(question_text, question.get('id'))

            # Check if we have any questions
            if len(questions) == 0:
                # Add a placeholder item
                self.question_combo.addItem("No research questions available", None)
                self.question_combo.setEnabled(False)
                self.evaluate_btn.setEnabled(False)
                logger.warning("No research questions found in the database")
            else:
                self.question_combo.setEnabled(True)
                self.evaluate_btn.setEnabled(True)
                logger.info(f"Loaded {len(questions)} research questions")
        except Exception as e:
            logger.error(f"Error loading research questions: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load research questions: {str(e)}")

    def _load_evaluator_models(self):
        """Load evaluator models into the combo box."""
        try:
            # Clear existing items
            self.model_combo.clear()

            # Get all evaluators
            evaluators = self.suggestions_manager.get_evaluators()

            # Add evaluators to combo box
            for evaluator in evaluators:
                evaluator_id = evaluator.get('id')
                evaluator_name = evaluator.get('name', 'Unknown Evaluator')

                # Display name is just the evaluator name
                self.model_combo.addItem(evaluator_name, evaluator_id)

            # If no evaluators found, create some default ones
            if len(evaluators) == 0:
                # Create default evaluators in the database
                default_models = ["gemma3:4b", "qwen3:1.7b-q8_0"]
                for model in default_models:
                    # Create a new evaluator in the database
                    evaluator_name = f"Document Evaluator ({model})"
                    evaluator_id = self.suggestions_manager.add_evaluator(
                        name=evaluator_name,
                        user_id=self.user_id,
                        model_id=model,
                        parameters={"type": "document_evaluator"},
                        prompt="Evaluate document relevance to research questions"
                    )

                    if evaluator_id:
                        # Add to combo box
                        self.model_combo.addItem(evaluator_name, evaluator_id)
                        logger.info(f"Created default evaluator: {evaluator_name} (ID: {evaluator_id})")

            logger.info(f"Loaded {self.model_combo.count()} evaluator models")
        except Exception as e:
            logger.error(f"Error loading evaluator models: {e}")
            QMessageBox.warning(self, "Error", f"Failed to load evaluator models: {str(e)}")

    @Slot(int)
    def _on_pending_review_changed(self, state):
        """
        Handle pending human review checkbox state change.

        Args:
            state: Qt.CheckState value
        """
        # If pending review is checked, disable the skip evaluated checkbox
        # as they are mutually exclusive, and change the button text
        if state == Qt.Checked:
            self.skip_evaluated_cb.setEnabled(False)
            self.skip_evaluated_cb.setChecked(False)
            self.evaluate_btn.setText("Load Documents")
        else:
            self.skip_evaluated_cb.setEnabled(True)
            self.evaluate_btn.setText("Evaluate")

    @Slot()
    def _on_evaluate_clicked(self):
        """Handle evaluate button click."""
        logger.debug("Evaluate button clicked")

        # Check if evaluation is already running
        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            # Stop the current evaluation
            if hasattr(self, 'worker') and self.worker:
                self.worker.stop()
            self.thread.quit()
            self.thread.wait()
            if hasattr(self, 'evaluate_btn') and self.evaluate_btn:
                self.evaluate_btn.setText("Evaluate")
            self.show_status_message("Evaluation stopped", success=False)
            return

        # Get selected research question
        try:
            question_idx = self.question_combo.currentIndex()
            if question_idx < 0:
                self.show_status_message("Please select a research question", success=False)
                return

            question_id = self.question_combo.itemData(question_idx)
            if question_id is None:
                self.show_status_message("No valid research question selected", success=False)
                return

            question_text = self.question_combo.itemText(question_idx)
            logger.debug(f"Selected question: {question_text} (ID: {question_id})")

            # Get selected evaluator model
            model_idx = self.model_combo.currentIndex()
            if model_idx < 0:
                self.show_status_message("Please select an evaluator model", success=False)
                return

            evaluator_id = self.model_combo.itemData(model_idx)
            if evaluator_id is None:
                self.show_status_message("No valid evaluator selected", success=False)
                return

            evaluator_name = self.model_combo.itemText(model_idx)
            logger.debug(f"Selected evaluator: {evaluator_name} (ID: {evaluator_id})")

            # Get number of records and start date
            num_records = self.records_spin.value()
            start_date = self.date_edit.date().toString("yyyy-MM-dd")
            logger.debug(f"Records: {num_records}, Start date: {start_date}")

            # Get checkboxes state
            pending_review = self.pending_review_cb.isChecked()
            skip_evaluated = self.skip_evaluated_cb.isChecked()
            logger.debug(f"Pending review: {pending_review}, Skip evaluated: {skip_evaluated}")

        except (RuntimeError, AttributeError) as e:
            logger.error(f"Error accessing UI controls: {e}")
            self.show_status_message("Error accessing UI controls. Please try again.", success=False)
            return

        # Get evaluator details to get the model name
        evaluator = self._get_evaluator_by_id(evaluator_id)
        if not evaluator:
            self.show_status_message(f"Could not find evaluator with ID {evaluator_id}", success=False)
            return

        model_name = evaluator.get('model_id', 'gemma3:4b')  # Default to gemma3:4b if not found
        logger.debug(f"Using model: {model_name}")

        # Show appropriate message based on mode
        if pending_review:
            self.show_status_message(
                f"Loading documents pending human review for question '{question_text}'...",
                success=True,
                duration_ms=0,  # Don't auto-hide
                show_progress=True
            )
        else:
            self.show_status_message(
                f"Starting evaluation of documents from {start_date} using '{evaluator_name}'...",
                success=True,
                duration_ms=0,  # Don't auto-hide
                show_progress=True
            )

        # Get documents from the database based on selected mode
        try:
            documents = self._get_recent_documents(
                start_date=start_date,
                limit=num_records,
                evaluator_id=evaluator_id,
                skip_evaluated=skip_evaluated,
                pending_review=pending_review,
                question_id=question_id
            )

            logger.debug(f"Found {len(documents) if documents else 0} documents")

            if not documents:
                self.show_status_message(f"No documents found from {start_date}", success=False)
                return

            # Clear the document list
            self.document_list.clear()
            # Reset evaluation count
            self.evaluated_count = 0

        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            self.show_status_message(f"Error retrieving documents: {str(e)}", success=False)
            return

        if pending_review:
            # In pending review mode, we just display the documents that need human review
            # without running AI evaluations
            try:
                # Update progress bar for loading documents
                self.progress_bar.setMaximum(len(documents))
                self.progress_bar.setValue(len(documents))

                # Add documents to the list
                for document in documents:
                    # Get existing AI evaluations for this document and question
                    evaluations = self.evaluations_manager.get_evaluations_by_document(
                        document_id=document['id'],
                        research_question_id=question_id,
                        human_only=False  # Get all evaluations, not just human ones
                    )

                    # Filter for AI evaluations only
                    ai_evaluations = [e for e in evaluations if not e.get('is_human_evaluator')]

                    if ai_evaluations:
                        # Use the highest AI rating as the document rating
                        highest_rating = max([e.get('rating', 0) for e in ai_evaluations])
                        document['rating'] = highest_rating

                        # Use the reason from the highest-rated evaluation
                        highest_eval = max(ai_evaluations, key=lambda e: e.get('rating', 0))
                        document['reason'] = highest_eval.get('rating_reason', 'No reason provided')

                        # Add to the list widget
                        is_read = False  # Not read by default
                        evaluator_name = highest_eval.get('evaluator_name', 'Unknown Evaluator')
                        suggestion = {
                            'recommendation_strength': highest_rating,
                            'recommendation_reason': document['reason'],
                            'evaluator_name': f"{evaluator_name} (Needs Human Review)"
                        }

                        self.document_list.add_document(document, is_read, suggestion)

                # Show completion message
                self.show_status_message(
                    f"Loaded {len(documents)} documents pending human review for question '{question_text}'",
                    success=True
                )

            except Exception as e:
                logger.error(f"Error displaying documents for review: {e}")
                self.show_status_message(f"Error displaying documents: {str(e)}", success=False)
                return
        else:
            # In normal mode, run AI evaluations on the documents
            try:
                # Create worker and thread
                self.worker = EvaluationWorker(
                    documents=documents,
                    question_text=question_text,
                    model_name=model_name
                )

                self.thread = QThread()
                self.worker.moveToThread(self.thread)

                # Connect signals
                self.thread.started.connect(self.worker.run)
                self.worker.document_evaluated.connect(self._on_document_evaluated)
                self.worker.evaluation_complete.connect(self._on_evaluation_complete)
                self.worker.evaluation_error.connect(self._on_evaluation_error)
                self.worker.progress_updated.connect(self._on_progress_updated)

                # Change button to "Stop"
                self.evaluate_btn.setText("Stop")

                # Start the thread
                self.thread.start()
                logger.debug("Started evaluation thread")

            except Exception as e:
                logger.error(f"Error starting evaluation thread: {e}")
                self.show_status_message(f"Error starting evaluation: {str(e)}", success=False)
                return

    @Slot(dict, object)
    def _on_document_evaluated(self, document, evaluation):
        """
        Handle document evaluation result from worker.

        Args:
            document: Document that was evaluated
            evaluation: Evaluation result
        """
        # Store the evaluation in the database
        question_id = self.question_combo.itemData(self.question_combo.currentIndex())
        evaluator_id = self.model_combo.itemData(self.model_combo.currentIndex())

        self._store_evaluation(
            document_id=document['id'],
            question_id=question_id,
            evaluator_id=evaluator_id,
            is_human_evaluator=False,
            rating=evaluation.rating,
            reason=evaluation.reason_for_rating,
            confidence=evaluation.similarity
        )

        # Add document to the list with evaluation info
        document['rating'] = evaluation.rating
        document['reason'] = evaluation.reason_for_rating

        # Add to the list widget
        is_read = False  # Not read by default
        evaluator_name = self.model_combo.itemText(self.model_combo.currentIndex())
        suggestion = {
            'recommendation_strength': evaluation.rating,
            'recommendation_reason': evaluation.reason_for_rating,
            'evaluator_name': evaluator_name
        }
        self.document_list.add_document(document, is_read, suggestion)

        # Increment evaluation count
        self.evaluated_count += 1

        # If this is the currently displayed document, refresh the evaluations list
        if self.current_document and self.current_document.get('id') == document['id']:
            self._load_evaluations(document['id'], question_id)

    @Slot(int)
    def _on_evaluation_complete(self, count):
        """
        Handle evaluation completion.

        Args:
            count: Number of documents evaluated
        """
        # Clean up thread
        if self.thread:
            self.thread.quit()
            self.thread.wait()

        # Reset button
        self.evaluate_btn.setText("Evaluate")

        # Show completion message
        self.show_status_message(f"Evaluated {count} documents", success=True)

    @Slot(str)
    def _on_evaluation_error(self, error_message):
        """
        Handle evaluation error.

        Args:
            error_message: Error message
        """
        # Clean up thread
        if self.thread:
            self.thread.quit()
            self.thread.wait()

        # Reset button
        self.evaluate_btn.setText("Evaluate")

        # Show error message
        self.show_status_message(f"Error during evaluation: {error_message}", success=False)

    @Slot(int, int)
    def _on_progress_updated(self, current, total):
        """
        Handle progress update.

        Args:
            current: Current progress
            total: Total items to process
        """
        # Update progress bar
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

        # Update status message
        self.status_label.setText(f"Evaluating document {current} of {total}...")

    @Slot(dict)
    def _on_document_selected(self, document):
        """Handle document selection in the list."""
        if not document:
            return

        # Store the current document
        self.current_document = document

        # Reset all radio buttons when a new document is selected
        for btn in self.rating_buttons:
            btn.setChecked(False)

        # Display the document
        self.document_display.display_document(document)

        # Get the current research question
        question_idx = self.question_combo.currentIndex()
        if question_idx < 0:
            return

        question_id = self.question_combo.itemData(question_idx)
        if question_id is None:
            return

        # Load all evaluations for this document
        self._load_evaluations(document['id'], question_id)

    def _load_evaluations(self, document_id: int, question_id: int):
        """
        Load all evaluations for a document and update UI.

        Args:
            document_id: ID of the document
            question_id: ID of the research question
        """
        try:
            # Clear existing evaluations
            self._clear_evaluations_list()

            # Get all evaluations for this document and question
            evaluations = self.evaluations_manager.get_evaluations_by_document(
                document_id=document_id,
                research_question_id=question_id
            )

            if not evaluations:
                # Show the "no evaluations" label
                self.no_evaluations_label.setVisible(True)
                return

            # Hide the "no evaluations" label
            self.no_evaluations_label.setVisible(False)

            # Group evaluations by evaluator
            evaluations_by_evaluator = {}
            for evaluation in evaluations:
                evaluator_id = evaluation.get('evaluator_id')
                if evaluator_id not in evaluations_by_evaluator:
                    evaluations_by_evaluator[evaluator_id] = []
                evaluations_by_evaluator[evaluator_id].append(evaluation)

            # Get evaluator details
            evaluators = self.suggestions_manager.get_evaluators()
            evaluator_map = {e.get('id'): e for e in evaluators}

            # Add each evaluator's evaluations to the list
            for evaluator_id, evals in evaluations_by_evaluator.items():
                # Get evaluator details
                evaluator = evaluator_map.get(evaluator_id, {})
                evaluator_name = evaluator.get('name', f"Unknown Evaluator (ID: {evaluator_id})")
                is_human = evaluator.get('model_id') is None or evaluator.get('model_id') == 'human'

                # Create a frame for this evaluator's evaluations
                evaluator_frame = QFrame()
                evaluator_frame.setFrameShape(QFrame.StyledPanel)
                evaluator_frame.setStyleSheet("background-color: #f8f9fa;")
                evaluator_layout = QVBoxLayout(evaluator_frame)
                evaluator_layout.setContentsMargins(10, 5, 10, 5)

                # Add evaluator name
                name_label = QLabel(f"<b>{evaluator_name}</b> {'(Human)' if is_human else '(AI)'}")
                evaluator_layout.addWidget(name_label)

                # Add each evaluation
                for eval_data in evals:
                    rating = eval_data.get('rating', 0)
                    reason = eval_data.get('rating_reason', 'No reason provided')
                    confidence = eval_data.get('confidence_level', 0.0)

                    # Create rating display
                    rating_frame = QFrame()
                    rating_layout = QHBoxLayout(rating_frame)
                    rating_layout.setContentsMargins(0, 0, 0, 0)

                    # Rating label
                    rating_label = QLabel(f"Rating: <b>{rating}</b>")
                    rating_layout.addWidget(rating_label)

                    # Confidence label (only for AI evaluators)
                    if not is_human and confidence > 0:
                        confidence_label = QLabel(f"Confidence: {confidence:.2f}")
                        rating_layout.addWidget(confidence_label)

                    rating_layout.addStretch()
                    evaluator_layout.addWidget(rating_frame)

                    # Reason label
                    reason_label = QLabel(reason)
                    reason_label.setWordWrap(True)
                    evaluator_layout.addWidget(reason_label)

                # Add the evaluator frame to the list
                self.evaluations_list_layout.addWidget(evaluator_frame)

            # Load human rating for the current user
            self._load_human_rating(document_id, question_id)

        except Exception as e:
            logger.error(f"Error loading evaluations: {e}")
            self.show_status_message(f"Error loading evaluations: {str(e)}", success=False)

    def _clear_evaluations_list(self):
        """Clear the evaluations list."""
        # Remove all widgets except the "no evaluations" label
        while self.evaluations_list_layout.count() > 1:
            item = self.evaluations_list_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()

        # Reset all radio buttons to ensure none are checked
        for btn in self.rating_buttons:
            btn.setChecked(False)

        # Make sure the "no evaluations" label is visible
        if hasattr(self, 'no_evaluations_label') and self.no_evaluations_label:
            self.no_evaluations_label.setVisible(True)

    def _load_human_rating(self, document_id: int, question_id: int):
        """
        Load existing human rating for the current user and update UI.

        Args:
            document_id: ID of the document
            question_id: ID of the research question
        """
        try:
            # Get current user ID
            user = get_current_user()
            user_id = user.get('id') if user else None

            if not user_id:
                return

            # Get evaluator ID for this user
            evaluator_id = self._get_human_evaluator_id(user_id)

            if not evaluator_id:
                return

            # Reset all radio buttons first
            for btn in self.rating_buttons:
                btn.setChecked(False)

            # Get existing evaluation
            evaluation = self._get_existing_evaluation(document_id, question_id, evaluator_id)

            if not evaluation:
                # No evaluation exists, select the "n/a" button
                logger.info(f"No human rating found for document {document_id}")
                for btn in self.rating_buttons:
                    if btn.property("rating") == -1:  # The "n/a" button
                        btn.blockSignals(True)
                        btn.setChecked(True)
                        btn.blockSignals(False)
                        break
                return

            # Update rating buttons based on the existing evaluation
            rating = evaluation.get('rating', 0)
            for btn in self.rating_buttons:
                btn_rating = btn.property("rating")
                if btn_rating == rating:
                    # Set checked without triggering the clicked signal
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.blockSignals(False)
                    break

            logger.info(f"Loaded human rating {rating} for document {document_id}")

        except Exception as e:
            logger.error(f"Error loading human rating: {e}")
            # Select the "n/a" button in case of error
            for btn in self.rating_buttons:
                btn.setChecked(False)

            # Select the "n/a" button
            for btn in self.rating_buttons:
                if btn.property("rating") == -1:  # The "n/a" button
                    btn.blockSignals(True)
                    btn.setChecked(True)
                    btn.blockSignals(False)
                    break

    def _get_human_evaluator_id(self, user_id: int) -> int:
        """
        Get or create a human evaluator ID for a user.

        Args:
            user_id: ID of the user

        Returns:
            ID of the human evaluator
        """
        # Get evaluators for this user
        evaluators = self.suggestions_manager.get_evaluators(user_id=user_id)

        # Filter for human evaluators
        for evaluator in evaluators:
            if evaluator.get('model_id') is None or evaluator.get('model_id') == 'human':
                return evaluator.get('id')

        # Create a new human evaluator
        evaluator_name = f"Human Evaluator (User {user_id})"
        evaluator_id = self.suggestions_manager.add_evaluator(
            name=evaluator_name,
            user_id=user_id,
            model_id='human',
            parameters={"type": "human_evaluator"},
            prompt=None
        )

        return evaluator_id

    @Slot()
    def _on_rating_clicked(self):
        """Handle rating button click."""
        # Check if we have a current document
        if not hasattr(self, 'current_document') or not self.current_document:
            logger.warning("No current document to rate")
            # Reset all buttons if there's no current document
            for btn in self.rating_buttons:
                btn.setChecked(False)
            return

        # Get the clicked button
        button = self.sender()
        if not button:
            return

        # Get the rating value
        rating = button.property("rating")

        # Ensure the clicked button is checked
        button.setChecked(True)

        # Update button states (only one can be checked)
        for btn in self.rating_buttons:
            if btn != button:
                btn.setChecked(False)

        # If "n/a" is selected, we need to remove any existing rating
        if rating == -1:
            self._remove_human_rating()
        else:
            # Save the human rating to the database
            self._save_human_rating(rating)

    def _remove_human_rating(self):
        """
        Remove existing human rating from the database.
        """
        try:
            # Check if we have a current document
            if not hasattr(self, 'current_document') or not self.current_document:
                logger.warning("No current document to remove rating from")
                return

            document_id = self.current_document.get('id')

            # Get the current research question
            question_idx = self.question_combo.currentIndex()
            if question_idx < 0:
                logger.warning("No research question selected")
                return

            question_id = self.question_combo.itemData(question_idx)
            if question_id is None:
                logger.warning("Invalid research question selected")
                return

            # Get current user ID
            user = get_current_user()
            user_id = user.get('id') if user else None

            if not user_id:
                logger.warning("No current user")
                return

            # Get evaluator ID for this user
            evaluator_id = self._get_human_evaluator_id(user_id)

            if not evaluator_id:
                logger.warning("Could not get human evaluator")
                return

            # Delete the evaluation from the database
            try:
                # Get chunks for this document
                chunks = self._get_or_create_chunks(document_id)

                if not chunks:
                    logger.warning(f"No chunks found for document ID {document_id}")
                    return

                # Delete evaluations for each chunk
                for chunk in chunks:
                    chunk_id = chunk.chunk_id if hasattr(chunk, 'chunk_id') else chunk.get('id')

                    # Delete the evaluation
                    query = """
                    DELETE FROM evaluations
                    WHERE research_question_id = %s
                    AND chunk_id = %s
                    AND evaluator_id = %s
                    """
                    self.evaluations_manager.execute(query, (question_id, chunk_id, evaluator_id))

                logger.info(f"Removed human rating for document {document_id}")
                self.show_status_message("Your rating has been removed", success=True)

                # Refresh the evaluations list
                self._load_evaluations(document_id, question_id)

            except Exception as e:
                logger.error(f"Error removing evaluation from database: {e}")
                self.show_status_message(f"Failed to remove rating: {str(e)}", success=False)

        except Exception as e:
            logger.error(f"Error removing human rating: {e}")
            self.show_status_message(f"Failed to remove rating: {str(e)}", success=False)

    def _save_human_rating(self, rating: int):
        """
        Save human rating to the database.

        Args:
            rating: Rating value (0-3)
        """
        try:
            # Check if we have a current document
            if not hasattr(self, 'current_document') or not self.current_document:
                logger.warning("No current document to rate")
                return

            document_id = self.current_document.get('id')

            # Get the current research question
            question_idx = self.question_combo.currentIndex()
            if question_idx < 0:
                logger.warning("No research question selected")
                return

            question_id = self.question_combo.itemData(question_idx)
            if question_id is None:
                logger.warning("Invalid research question selected")
                return

            # Get current user ID
            user = get_current_user()
            user_id = user.get('id') if user else None

            if not user_id:
                logger.warning("No current user")
                return

            # Get evaluator ID for this user
            evaluator_id = self._get_human_evaluator_id(user_id)

            if not evaluator_id:
                logger.warning("Could not get or create human evaluator")
                return

            # Store the evaluation
            success = self._store_evaluation(
                document_id=document_id,
                question_id=question_id,
                evaluator_id=evaluator_id,
                is_human_evaluator=True,
                rating=rating,
                reason=f"Human rating by user {user_id}",
                confidence=1.0  # Human ratings have full confidence
            )

            if success:
                logger.info(f"Saved human rating {rating} for document {document_id}")
                self.show_status_message(f"Your rating ({rating}) has been saved", success=True)

                # Refresh the evaluations list to show the new rating
                question_id = self.question_combo.itemData(self.question_combo.currentIndex())
                if question_id is not None:
                    self._load_evaluations(document_id, question_id)
            else:
                logger.warning(f"Failed to save human rating for document {document_id}")
                self.show_status_message("Failed to save your rating", success=False)

        except Exception as e:
            logger.error(f"Error saving human rating: {e}")
            self.show_status_message(f"Failed to save rating: {str(e)}", success=False)

    def _on_user_changed(self, user_data):
        """Handle user change from context system."""
        self.user_id = user_data.get('id') if user_data else None
        logger.info(f"User changed to ID: {self.user_id}")

    def _on_project_changed(self, project_data):
        """Handle project change from context system."""
        # Handle both cases: project_data can be an integer (project ID) or a dictionary with an 'id' key
        if isinstance(project_data, dict):
            self.project_id = project_data.get('id')
        else:
            # project_data is already the project ID
            self.project_id = project_data

        logger.info(f"Project changed to ID: {self.project_id}")

        # Reload research questions for the new project
        self._load_research_questions()

    def get_config_widget(self):
        """Get the configuration widget for this plugin."""
        logger.debug("DocumentEvaluatorPlugin.get_config_widget() called")

        # Create a simple configuration widget
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget, QPushButton, QComboBox, QFormLayout, QTextEdit, QDoubleSpinBox, QSpinBox, QSlider, QHBoxLayout, QLineEdit, QSplitter, QSizePolicy
        from PySide6.QtCore import Qt

        # Create a widget that can expand in both directions
        config_widget = QWidget()

        # Store a reference to this widget to prevent premature garbage collection
        self._config_widget = config_widget

        # Set size policy to allow expansion with a high stretch factor
        config_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Set minimum width to ensure it's not too narrow
        config_widget.setMinimumWidth(300)
        # Remove any maximum width constraint
        config_widget.setMaximumWidth(16777215)  # Qt's QWIDGETSIZE_MAX

        # Main layout for the container
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(10, 10, 10, 10)
        config_layout.setSpacing(10)

        # Title at the top
        title_label = QLabel("<h3>Evaluator Configuration</h3>")
        config_layout.addWidget(title_label)

        # Form layout for evaluator settings
        form_widget = QWidget()
        # Store a reference to prevent garbage collection
        self._form_widget = form_widget
        # Make sure the form widget can expand
        form_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        form_layout = QFormLayout(form_widget)
        # Allow form layout to stretch horizontally
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # Name field
        name_label = QLabel("Name:")
        name_edit = QLineEdit()
        # Store a reference to prevent garbage collection
        self._name_edit = name_edit
        form_layout.addRow(name_label, name_edit)

        # Model selector
        model_label = QLabel("Model:")
        model_combo = QComboBox()
        # Store a reference to prevent garbage collection
        self._model_combo = model_combo

        # Load models from database
        try:
            # Import the models database manager
            from localknowledge.db.models import ModelsDatabaseManager
            models_db = ModelsDatabaseManager()

            # Get completion models
            models = models_db.get_completion_models()

            # Add models to combo box
            for model in models:
                model_name = model.get('name', 'Unknown Model')
                provider_name = model.get('provider_name', 'Unknown Provider')
                display_name = f"{model_name} ({provider_name})"
                model_combo.addItem(display_name, model_name)

            # If no models found, add some defaults
            if model_combo.count() == 0:
                model_combo.addItem("gemma3:4b", "gemma3:4b")
                model_combo.addItem("qwen3:1.7b-q8_0", "qwen3:1.7b-q8_0")
        except Exception as e:
            # Add some default models if there's an error
            logger.error(f"Error loading models: {e}")
            model_combo.addItem("gemma3:4b", "gemma3:4b")
            model_combo.addItem("qwen3:1.7b-q8_0", "qwen3:1.7b-q8_0")

        form_layout.addRow(model_label, model_combo)

        # Temperature with slider
        temp_label = QLabel("Temperature:")
        temp_widget = QWidget()
        # Store a reference to prevent garbage collection
        self._temp_widget = temp_widget
        # Make sure the temperature widget can expand
        temp_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        temp_layout = QHBoxLayout(temp_widget)
        temp_layout.setContentsMargins(0, 0, 0, 0)

        temperature_spin = QDoubleSpinBox()
        # Store a reference to prevent garbage collection
        self._temperature_spin = temperature_spin
        temperature_spin.setRange(0.0, 2.0)
        temperature_spin.setSingleStep(0.1)
        temperature_spin.setValue(0.7)
        temperature_spin.setFixedWidth(70)
        temp_layout.addWidget(temperature_spin)

        temperature_slider = QSlider(Qt.Horizontal)
        # Store a reference to prevent garbage collection
        self._temperature_slider = temperature_slider
        # Make sure the slider can expand
        temperature_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        temperature_slider.setRange(0, 200)  # 0.0 to 2.0 with 100 steps per unit
        temperature_slider.setValue(70)      # 0.7 default
        temperature_slider.setTickPosition(QSlider.TicksBelow)
        temperature_slider.setTickInterval(10)
        temp_layout.addWidget(temperature_slider, 1)  # Add with stretch factor

        # Connect slider and spin box
        temperature_slider.valueChanged.connect(lambda value: self._on_temp_slider_changed(value, temperature_spin))
        temperature_spin.valueChanged.connect(lambda value: self._on_temp_spin_changed(value, temperature_slider))

        form_layout.addRow(temp_label, temp_widget)

        # Top-K
        top_k_label = QLabel("Top-K:")
        top_k_spin = QSpinBox()
        # Store a reference to prevent garbage collection
        self._top_k_spin = top_k_spin
        top_k_spin.setRange(0, 100)
        top_k_spin.setValue(40)
        form_layout.addRow(top_k_label, top_k_spin)

        # Top-P with slider
        top_p_label = QLabel("Top-P:")
        top_p_widget = QWidget()
        # Store a reference to prevent garbage collection
        self._top_p_widget = top_p_widget
        # Make sure the top-p widget can expand
        top_p_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        top_p_layout = QHBoxLayout(top_p_widget)
        top_p_layout.setContentsMargins(0, 0, 0, 0)

        top_p_spin = QDoubleSpinBox()
        # Store a reference to prevent garbage collection
        self._top_p_spin = top_p_spin
        top_p_spin.setRange(0.0, 1.0)
        top_p_spin.setSingleStep(0.05)
        top_p_spin.setValue(0.9)
        top_p_spin.setFixedWidth(70)
        top_p_layout.addWidget(top_p_spin)

        top_p_slider = QSlider(Qt.Horizontal)
        # Store a reference to prevent garbage collection
        self._top_p_slider = top_p_slider
        # Make sure the slider can expand
        top_p_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        top_p_slider.setRange(0, 100)  # 0.0 to 1.0 with 100 steps
        top_p_slider.setValue(90)      # 0.9 default
        top_p_slider.setTickPosition(QSlider.TicksBelow)
        top_p_slider.setTickInterval(10)
        top_p_layout.addWidget(top_p_slider, 1)  # Add with stretch factor

        # Connect slider and spin box
        top_p_slider.valueChanged.connect(lambda value: self._on_top_p_slider_changed(value, top_p_spin))
        top_p_spin.valueChanged.connect(lambda value: self._on_top_p_spin_changed(value, top_p_slider))

        form_layout.addRow(top_p_label, top_p_widget)

        # Prompt field
        prompt_label = QLabel("Custom Prompt:")
        form_layout.addRow(prompt_label)

        prompt_edit = QTextEdit()
        # Store a reference to prevent garbage collection
        self._prompt_edit = prompt_edit
        # Make sure the text edit can expand in both directions
        prompt_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        prompt_edit.setMinimumHeight(150)
        prompt_edit.setPlaceholderText("Enter a custom prompt for the evaluator...")

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
        prompt_edit.setPlainText(default_prompt.strip())

        form_layout.addRow(prompt_edit)

        # Add form to main layout
        config_layout.addWidget(form_widget)

        # Save button
        save_btn = QPushButton("Save Evaluator")
        # Store a reference to prevent garbage collection
        self._save_btn = save_btn
        save_btn.clicked.connect(lambda: self._on_save_evaluator_clicked(
            name_edit, model_combo, temperature_spin, top_k_spin, top_p_spin, prompt_edit))
        config_layout.addWidget(save_btn)

        # Add stretch to push content to the top
        config_layout.addStretch()

        logger.debug(f"Created config widget: {config_widget}")

        return config_widget

    def _on_temp_slider_changed(self, value, spin_box):
        """Handle temperature slider value change."""
        # Convert slider value (0-200) to temperature (0.0-2.0)
        temperature = value / 100.0
        # Update spin box without triggering its valueChanged signal
        spin_box.blockSignals(True)
        spin_box.setValue(temperature)
        spin_box.blockSignals(False)

    def _on_temp_spin_changed(self, value, slider):
        """Handle temperature spin box value change."""
        # Convert temperature (0.0-2.0) to slider value (0-200)
        slider_value = int(value * 100)
        # Update slider without triggering its valueChanged signal
        slider.blockSignals(True)
        slider.setValue(slider_value)
        slider.blockSignals(False)

    def _on_top_p_slider_changed(self, value, spin_box):
        """Handle top-p slider value change."""
        # Convert slider value (0-100) to top-p (0.0-1.0)
        top_p = value / 100.0
        # Update spin box without triggering its valueChanged signal
        spin_box.blockSignals(True)
        spin_box.setValue(top_p)
        spin_box.blockSignals(False)

    def _on_top_p_spin_changed(self, value, slider):
        """Handle top-p spin box value change."""
        # Convert top-p (0.0-1.0) to slider value (0-100)
        slider_value = int(value * 100)
        # Update slider without triggering its valueChanged signal
        slider.blockSignals(True)
        slider.setValue(slider_value)
        slider.blockSignals(False)

    def _on_save_evaluator_clicked(self, name_edit, model_combo, temperature_spin, top_k_spin, top_p_spin, prompt_edit):
        """Handle save evaluator button click."""
        try:
            # Get values from form
            name = name_edit.text().strip()
            model_id = model_combo.currentData()
            temperature = temperature_spin.value()
            top_k = top_k_spin.value()
            top_p = top_p_spin.value()
            prompt = prompt_edit.toPlainText().strip()

            # Validate input
            if not name:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Validation Error", "Please enter a name for the evaluator.")
                return

            # Create parameters dictionary
            parameters = {
                "temperature": temperature,
                "top_k": top_k,
                "top_p": top_p,
                "type": "document_evaluator"
            }
        except RuntimeError as e:
            logger.error(f"Qt widget error accessing form values: {e}")
            return

        try:
            # Get current user ID
            from localknowledge.context import get_current_user
            user = get_current_user()
            user_id = user.get('id') if user else None

            # Add evaluator to database
            evaluator_id = self.suggestions_manager.add_evaluator(
                name=name,
                user_id=user_id,
                model_id=model_id,
                parameters=parameters,
                prompt=prompt
            )

            if evaluator_id:
                # Show success message
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "Success", f"Created new evaluator '{name}'.")

                try:
                    # Reload evaluator models
                    self._load_evaluator_models()

                    # Check if widgets are still valid before updating them
                    if hasattr(self, 'name_edit') and self.name_edit:
                        # Clear form
                        self.name_edit.clear()

                    if hasattr(self, 'prompt_edit') and self.prompt_edit:
                        # Reset prompt to default
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

                    # Reset other controls if they still exist
                    if hasattr(self, 'temperature_spin') and self.temperature_spin:
                        self.temperature_spin.setValue(0.7)

                    if hasattr(self, 'temperature_slider') and self.temperature_slider:
                        self.temperature_slider.setValue(70)

                    if hasattr(self, 'top_k_spin') and self.top_k_spin:
                        self.top_k_spin.setValue(40)

                    if hasattr(self, 'top_p_spin') and self.top_p_spin:
                        self.top_p_spin.setValue(0.9)

                    if hasattr(self, 'top_p_slider') and self.top_p_slider:
                        self.top_p_slider.setValue(90)
                except RuntimeError as e:
                    logger.error(f"Qt widget error resetting form: {e}")
            else:
                # Show error message
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", "Failed to create evaluator.")
        except Exception as e:
            # Show error message
            logger.error(f"Error creating evaluator: {e}")
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Error", f"Error creating evaluator: {str(e)}")
            except RuntimeError as e2:
                logger.error(f"Qt widget error showing error message: {e2}")

    def get_actions(self):
        """Get actions for the toolbar."""
        actions = []

        refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        refresh_action.setStatusTip("Refresh data")
        refresh_action.triggered.connect(self._refresh_data)
        actions.append(refresh_action)

        return actions

    def _refresh_data(self):
        """Refresh all data."""
        self._load_research_questions()
        self._load_evaluator_models()

    def _on_document_bookmarked(self, document: dict, bookmark_type: str, is_bookmarked: bool):
        """
        Handle document bookmark event from the document display widget.

        Args:
            document: Document that was bookmarked
            bookmark_type: Type of bookmark ('personal' or 'project')
            is_bookmarked: Whether the document was bookmarked or unbookmarked
        """
        # Log the bookmark action
        action = "Bookmarked" if is_bookmarked else "Unbookmarked"
        logger.info(f"{action} document {document.get('id')} as {bookmark_type}")

        # Show a status message
        self.show_status_message(
            f"{action} document as {bookmark_type}",
            success=True
        )

    def show_status_message(self, message: str, success: bool = True, duration_ms: int = 5000, show_progress: bool = False):
        """
        Show a status message in the banner.

        Args:
            message: Message to display
            success: Whether the message indicates success (green) or error (red)
            duration_ms: How long to display the message (0 for indefinite)
            show_progress: Whether to show the progress bar
        """
        try:
            # Check if widgets are still valid
            if not hasattr(self, 'status_label') or not self.status_label:
                logger.error("Status label is no longer valid")
                return

            if not hasattr(self, 'status_banner') or not self.status_banner:
                logger.error("Status banner is no longer valid")
                return

            if not hasattr(self, 'progress_bar') or not self.progress_bar:
                logger.error("Progress bar is no longer valid")
                return

            # Set message
            self.status_label.setText(message)

            # Set color based on success/error
            if success:
                self.status_banner.setStyleSheet("background-color: #d4edda; color: #155724;")
            else:
                self.status_banner.setStyleSheet("background-color: #f8d7da; color: #721c24;")

            # Show/hide progress bar
            self.progress_bar.setVisible(show_progress)

            # Show the banner
            self.status_banner.setVisible(True)

            # Hide after duration if specified
            if duration_ms > 0:
                QTimer.singleShot(duration_ms, lambda: self._hide_status_banner())
        except RuntimeError as e:
            logger.error(f"Qt widget error showing status message: {e}")

    def _hide_status_banner(self):
        """Safely hide the status banner."""
        try:
            if hasattr(self, 'status_banner') and self.status_banner:
                self.status_banner.setVisible(False)
        except RuntimeError as e:
            logger.error(f"Qt widget error hiding status banner: {e}")

    def _get_evaluator_by_id(self, evaluator_id: int) -> dict:
        """
        Get evaluator details by ID.

        Args:
            evaluator_id: ID of the evaluator

        Returns:
            Evaluator details as a dictionary
        """
        evaluators = self.suggestions_manager.get_evaluators()
        for evaluator in evaluators:
            if evaluator.get('id') == evaluator_id:
                return evaluator
        return None

    def _get_human_evaluator_id(self, user_id: int) -> Optional[int]:
        """
        Get the human evaluator ID for a user.

        Args:
            user_id: ID of the user

        Returns:
            Human evaluator ID or None if not found
        """
        query = """
        SELECT id FROM evaluators
        WHERE user_id = %s AND (model_id IS NULL OR model_id = 'human')
        """
        result = self.db_manager.execute(query, (user_id,))
        return result[0]['id'] if result else None

    def _get_recent_documents(self, start_date: str, limit: int, evaluator_id: int = None, skip_evaluated: bool = True, pending_review: bool = False, question_id: int = None) -> list:
        """
        Get recent documents from the database.

        Args:
            start_date: Start date in YYYY-MM-DD format
            limit: Maximum number of documents to return
            evaluator_id: Optional evaluator ID to check for existing evaluations
            skip_evaluated: If True, skip documents already evaluated by this evaluator
            pending_review: If True, only return documents that need human review
            question_id: ID of the research question (required if pending_review is True)

        Returns:
            List of document dictionaries
        """
        if pending_review and question_id is not None:
            # Get current user ID
            user = get_current_user()
            user_id = user.get('id') if user else None

            if not user_id:
                logger.warning("No current user ID available for pending review query")
                return []

            # Get human evaluator ID for this user
            human_evaluator_id = self._get_human_evaluator_id(user_id)

            if not human_evaluator_id:
                logger.warning("No human evaluator ID available for pending review query")
                return []

            # Get documents that have been evaluated by AI but not by the current human evaluator
            # for the selected research question
            query = """
            WITH ai_evaluated AS (
                -- Documents evaluated by AI for this question
                SELECT DISTINCT ch.document_id
                FROM evaluations e
                JOIN chunks ch ON e.chunk_id = ch.id
                WHERE e.research_question_id = %s
                AND e.is_human_evaluator = FALSE
            ),
            human_evaluated AS (
                -- Documents evaluated by this human evaluator for this question
                SELECT DISTINCT ch.document_id
                FROM evaluations e
                JOIN chunks ch ON e.chunk_id = ch.id
                WHERE e.research_question_id = %s
                AND e.evaluator_id = %s
            )
            SELECT d.*, s.name as source_name, c.name as category_name
            FROM document d
            JOIN sources s ON d.source_id = s.id
            LEFT JOIN categories c ON d.category_id = c.id
            JOIN ai_evaluated ae ON d.id = ae.document_id
            WHERE d.publication_date >= %s
            AND NOT EXISTS (
                -- Exclude documents already evaluated by this human
                SELECT 1 FROM human_evaluated he
                WHERE he.document_id = d.id
            )
            ORDER BY d.publication_date DESC
            LIMIT %s
            """

            return self.db_manager.execute(query, (question_id, question_id, human_evaluator_id, start_date, limit)) or []

        elif skip_evaluated and evaluator_id is not None:
            # Get documents that haven't been evaluated by this evaluator
            query = """
            SELECT d.*, s.name as source_name, c.name as category_name
            FROM document d
            JOIN sources s ON d.source_id = s.id
            LEFT JOIN categories c ON d.category_id = c.id
            WHERE d.publication_date >= %s
            AND NOT EXISTS (
                SELECT 1 FROM evaluations e
                JOIN chunks ch ON e.chunk_id = ch.id
                WHERE ch.document_id = d.id
                AND e.evaluator_id = %s
            )
            ORDER BY d.publication_date DESC
            LIMIT %s
            """

            return self.db_manager.execute(query, (start_date, evaluator_id, limit)) or []
        else:
            # Get all recent documents regardless of evaluation status
            query = """
            SELECT d.*, s.name as source_name, c.name as category_name
            FROM document d
            JOIN sources s ON d.source_id = s.id
            LEFT JOIN categories c ON d.category_id = c.id
            WHERE d.publication_date >= %s
            ORDER BY d.publication_date DESC
            LIMIT %s
            """

            return self.db_manager.execute(query, (start_date, limit)) or []

    def _get_or_create_chunks(self, document_id: int) -> list:
        """
        Get or create chunks for a document.

        Args:
            document_id: ID of the document

        Returns:
            List of chunk dictionaries
        """
        # Try to get existing chunks
        chunks = self.chunking_manager.get_chunks_by_document(document_id)

        if chunks:
            return chunks

        # If no chunks exist, we'll need to create them
        # This is a simplified version - in a real implementation, you'd use a proper chunking strategy
        document = self.db_manager.get_document(document_id)
        if not document:
            return []

        # Get or create a default chunking strategy
        chunking_strategy_id = self.chunking_manager.get_or_create_chunking_strategy(
            strategy_name="default",
            parameters={"chunk_size": 1500, "overlap": 100}
        )

        # Get or create a default chunk type
        chunktype_id = self.chunking_manager.get_or_create_chunktype("abstract")

        # Create a chunk for the abstract
        abstract = document.get('abstract', '')
        if abstract:
            chunk = Chunk(
                chunk_id=0,  # Will be assigned by the database
                document_id=document_id,
                chunking_strategy_id=chunking_strategy_id,
                chunktype_id=chunktype_id,
                document_title=document.get('title', ''),
                text=abstract,
                chunklength=len(abstract),
                chunk_no=1,
                page_start=0,
                page_end=0,
                metadata={}
            )

            # Store the chunk in the database
            self.chunking_manager.get_or_create_chunk(chunk)

            # Get the created chunk
            return self.chunking_manager.get_chunks_by_document(document_id)

        return []

    def _store_evaluation(self, document_id: int, question_id: int, evaluator_id: int,
                         is_human_evaluator: bool, rating: int, reason: str, confidence: float) -> bool:
        """
        Store an evaluation in the database.

        Args:
            document_id: ID of the document
            question_id: ID of the research question
            evaluator_id: ID of the evaluator
            is_human_evaluator: Whether the evaluator is human
            rating: Rating value (0-3)
            reason: Reason for the rating
            confidence: Confidence level (0.0-1.0)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get or create chunks for the document
            chunks = self._get_or_create_chunks(document_id)

            if not chunks:
                logger.warning(f"No chunks found for document ID {document_id}")
                return False

            # Store evaluation for each chunk
            for chunk in chunks:
                chunk_id = chunk.chunk_id if hasattr(chunk, 'chunk_id') else chunk.get('id')

                success = self.evaluations_manager.create_evaluation(
                    research_question_id=question_id,
                    chunk_id=chunk_id,
                    evaluator_id=evaluator_id,
                    document_id=document_id,
                    is_human_evaluator=is_human_evaluator,
                    rating=rating,
                    confidence_level=confidence,
                    rating_reason=reason
                )

                if not success:
                    logger.warning(f"Failed to create evaluation for chunk ID {chunk_id}")

            return True

        except Exception as e:
            logger.error(f"Error storing evaluation: {e}")
            return False

    def _get_existing_evaluation(self, document_id: int, question_id: int, evaluator_id: int) -> dict:
        """
        Get existing evaluation for a document.

        Args:
            document_id: ID of the document
            question_id: ID of the research question
            evaluator_id: ID of the evaluator

        Returns:
            Evaluation data as a dictionary
        """
        try:
            # Get evaluations for the document
            evaluations = self.evaluations_manager.get_evaluations_by_document(
                document_id=document_id,
                research_question_id=question_id
            )

            if not evaluations:
                return None

            # Filter by evaluator ID
            for evaluation in evaluations:
                if evaluation.get('evaluator_id') == evaluator_id:
                    return evaluation

            return None

        except Exception as e:
            logger.error(f"Error getting existing evaluation: {e}")
            return None

    def cleanup(self):
        """Clean up resources before plugin is unloaded."""
        # Stop any running evaluation
        if hasattr(self, 'worker') and self.worker:
            self.worker.stop()

        if hasattr(self, 'thread') and self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait()

        # Close database connections
        if hasattr(self, 'db_manager'):
            self.db_manager.close()

        if hasattr(self, 'questions_manager'):
            self.questions_manager.close()

        if hasattr(self, 'suggestions_manager'):
            self.suggestions_manager.close()

        if hasattr(self, 'evaluations_manager'):
            self.evaluations_manager.close()

        if hasattr(self, 'chunking_manager'):
            self.chunking_manager.close()
