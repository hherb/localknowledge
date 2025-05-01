"""
Research question widget for displaying and managing research questions.

This module provides a widget for displaying, adding, and removing research
questions for a research project.
"""
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QSize, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QSizePolicy, QMessageBox, QListWidget, QListWidgetItem,
    QLineEdit, QScrollArea, QSplitter
)
from PySide6.QtGui import QIcon, QColor

from localknowledge.db.research_questions import ResearchQuestionsManager


class QuestionCard(QFrame):
    """Card widget for displaying a research question."""

    # Signals
    clicked = Signal(int)  # Signal emitted when the card is clicked
    deleteClicked = Signal(int)  # Signal emitted when the delete button is clicked

    def __init__(self, question_data: Dict[str, Any], parent=None):
        """
        Initialize the question card.

        Args:
            question_data: Research question data dictionary
            parent: Parent widget
        """
        super().__init__(parent)

        # Store the question data
        self.question_data = question_data
        self.question_id = question_data['id']

        # Set up the UI
        self.setup_ui()

        # Make the card clickable
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setCursor(Qt.PointingHandCursor)

        # Set minimum size
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Set stylesheet
        self.setStyleSheet("""
            QuestionCard {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
                margin: 2px;
            }
            QuestionCard:hover {
                background-color: #e0e0e0;
                border: 1px solid #ccc;
            }
        """)

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Question content
        content_layout = QVBoxLayout()
        content_layout.setSpacing(5)

        # Question text
        self.question_label = QLabel(self.question_data['question'])
        self.question_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.question_label.setWordWrap(True)
        content_layout.addWidget(self.question_label)

        # Statistics placeholder (for future implementation)
        stats_text = "No statistics available yet"
        self.stats_label = QLabel(stats_text)
        self.stats_label.setStyleSheet("color: #666; font-size: 10px;")
        content_layout.addWidget(self.stats_label)

        # Add content layout to main layout
        layout.addLayout(content_layout, 1)  # 1 is stretch factor

        # Delete button
        self.delete_button = QPushButton()
        self.delete_button.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setToolTip("Delete this question")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #ddd;
                border-radius: 12px;
            }
        """)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.delete_button)

    def mousePressEvent(self, event):
        """Handle mouse press event to emit clicked signal."""
        super().mousePressEvent(event)
        self.clicked.emit(self.question_id)

    def _on_delete_clicked(self):
        """Handle delete button click."""
        self.deleteClicked.emit(self.question_id)


class ResearchQuestionWidget(QWidget):
    """Widget for displaying and managing research questions."""

    # Signal emitted when a question is added or removed
    questionChanged = Signal(int)

    def __init__(self, parent=None):
        """Initialize the research question widget."""
        super().__init__(parent)

        # Set up database manager
        self.db_manager = ResearchQuestionsManager()

        # Current project ID
        self.project_id = None

        # Set up the UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Status banner for non-intrusive feedback
        self.status_banner = QLabel()
        self.status_banner.setAlignment(Qt.AlignCenter)
        self.status_banner.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                color: white;
                padding: 8px;
                border-radius: 4px;
                margin: 4px;
                font-weight: bold;
            }
        """)
        self.status_banner.setVisible(False)
        layout.addWidget(self.status_banner)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(self.main_splitter)

        # Left side - Questions list
        left_widget = QWidget()
        left_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)
        self.main_splitter.addWidget(left_widget)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.setSpacing(5)

        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search questions...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        left_layout.addLayout(search_layout)

        # Questions list
        questions_layout = QVBoxLayout()
        questions_layout.setSpacing(5)

        # Questions list label
        questions_label = QLabel("Research Questions")
        questions_label.setStyleSheet("font-weight: bold;")
        questions_layout.addWidget(questions_label)

        # Questions list scroll area
        self.questions_scroll = QScrollArea()
        self.questions_scroll.setWidgetResizable(True)
        self.questions_scroll.setFrameShape(QFrame.NoFrame)

        # Questions list container
        self.questions_container = QWidget()
        self.questions_layout = QVBoxLayout(self.questions_container)
        self.questions_layout.setContentsMargins(0, 0, 0, 0)
        self.questions_layout.setSpacing(5)
        self.questions_layout.addStretch(1)  # Push items to the top

        # Set the container as the scroll area widget
        self.questions_scroll.setWidget(self.questions_container)

        # Add scroll area to questions layout
        questions_layout.addWidget(self.questions_scroll)

        # Add questions layout to left layout
        left_layout.addLayout(questions_layout)

        # Right side - Question form
        right_widget = QWidget()
        right_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)
        self.main_splitter.addWidget(right_widget)

        # Add or edit research question section
        # Section label
        add_question_label = QLabel("Add or edit a research question")
        add_question_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(add_question_label)

        # Question input
        question_input_layout = QHBoxLayout()
        question_input_layout.setSpacing(5)

        # Question label
        question_label = QLabel("Question")
        question_label.setFixedWidth(80)
        question_input_layout.addWidget(question_label)

        # Question text input
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("enter your research question ...")
        # Allow horizontal stretching
        self.question_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        question_input_layout.addWidget(self.question_input)

        right_layout.addLayout(question_input_layout)

        # Details input
        details_input_layout = QVBoxLayout()
        details_input_layout.setSpacing(5)

        # Details label
        details_label = QLabel("Details")
        details_input_layout.addWidget(details_label)

        # Details text edit
        self.details_input = QTextEdit()
        self.details_input.setPlaceholderText("A paragraph of text.\nA second row of text.")
        self.details_input.setMinimumHeight(100)
        # Allow vertical stretching
        self.details_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        details_input_layout.addWidget(self.details_input)

        right_layout.addLayout(details_input_layout)

        # Save and new buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(10)

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save_question)
        buttons_layout.addWidget(self.save_button)

        # Add stretch to push the new button to the right
        buttons_layout.addStretch(1)

        # New button
        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self._on_new_question)
        buttons_layout.addWidget(self.new_button)

        right_layout.addLayout(buttons_layout)

        # Add stretch to push everything to the top
        right_layout.addStretch(1)

        # Set splitter sizes (1:2 ratio)
        self.main_splitter.setSizes([1, 2])

        # Store the current question ID being edited
        self.current_question_id = None

    def show_status_message(self, message: str, success: bool = True, duration_ms: int = 3000):
        """
        Show a status message in the banner.

        Args:
            message: Message to display
            success: Whether this is a success message (green) or error message (red)
            duration_ms: How long to display the message in milliseconds
        """
        # Set the message
        self.status_banner.setText(message)

        # Set the color based on success/error
        if success:
            self.status_banner.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    margin: 4px;
                    font-weight: bold;
                }
            """)
        else:
            self.status_banner.setStyleSheet("""
                QLabel {
                    background-color: #F44336;
                    color: white;
                    padding: 8px;
                    border-radius: 4px;
                    margin: 4px;
                    font-weight: bold;
                }
            """)

        # Show the banner
        self.status_banner.setVisible(True)

        # Hide after duration
        QTimer.singleShot(duration_ms, lambda: self.status_banner.setVisible(False))

    def load_project(self, project_id: int):
        """
        Load research questions for a project.

        Args:
            project_id: Project ID
        """
        self.project_id = project_id

        # Clear existing questions
        self._clear_questions()

        # Get questions for this project
        questions = self.db_manager.get_project_questions(project_id)

        if questions:
            # Add questions to the list
            for question in questions:
                self._add_question_item(question)

    def _clear_questions(self):
        """Clear all questions from the list."""
        # Remove all widgets from the questions layout except the stretch at the end
        while self.questions_layout.count() > 1:
            item = self.questions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _add_question_item(self, question_data: Dict[str, Any]):
        """
        Add a question item to the list.

        Args:
            question_data: Research question data dictionary
        """
        # Create question card
        card = QuestionCard(question_data)
        card.deleteClicked.connect(self._on_delete_question)
        card.clicked.connect(self._on_question_selected)

        # Add to layout before the stretch
        self.questions_layout.insertWidget(self.questions_layout.count() - 1, card)

    def _on_save_question(self):
        """Handle save question button click."""
        question_text = self.question_input.text().strip()
        details_text = self.details_input.toPlainText().strip()

        if not question_text:
            self.show_status_message("Question text is required", success=False)
            return

        if self.current_question_id:
            # Update existing question
            success = self.db_manager.update_question(
                question_id=self.current_question_id,
                data={
                    "question": question_text,
                    "details": details_text if details_text else None
                }
            )

            if success:
                # Reload questions
                self.load_project(self.project_id)

                # Clear inputs and reset current question ID
                self.question_input.clear()
                self.details_input.clear()
                self.current_question_id = None

                self.show_status_message("Research question updated successfully", success=True)
                self.questionChanged.emit(self.current_question_id)
            else:
                self.show_status_message("Failed to update research question", success=False)
        else:
            # Create new question
            question_id = self.db_manager.create_question(
                question=question_text,
                details=details_text if details_text else None
            )

            if question_id:
                # Associate with project
                self.db_manager.associate_with_project(question_id, self.project_id)

                # Reload questions
                self.load_project(self.project_id)

                # Clear inputs
                self.question_input.clear()
                self.details_input.clear()

                self.show_status_message("Research question added successfully", success=True)
                self.questionChanged.emit(question_id)
            else:
                self.show_status_message("Failed to add research question", success=False)

    def _on_new_question(self):
        """Handle new question button click."""
        # Clear inputs and reset current question ID
        self.question_input.clear()
        self.details_input.clear()
        self.current_question_id = None
        self.question_input.setFocus()

    def _on_question_selected(self, question_id: int):
        """
        Handle question selection.

        Args:
            question_id: Research question ID
        """
        # Get the question data
        question = self.db_manager.get_question(question_id)
        if not question:
            return

        # Set the current question ID
        self.current_question_id = question_id

        # Update the form
        self.question_input.setText(question['question'])
        self.details_input.setText(question['details'] if question['details'] else "")

    def _on_search_changed(self, search_text: str):
        """
        Handle search text changed.

        Args:
            search_text: Search text
        """
        if not self.project_id:
            return

        # Clear existing questions
        self._clear_questions()

        if not search_text:
            # If search is empty, load all questions
            questions = self.db_manager.get_project_questions(self.project_id)
        else:
            # Search for questions
            questions = self.db_manager.search_questions(search_text, self.project_id)

        if questions:
            # Add questions to the list
            for question in questions:
                self._add_question_item(question)

    def _on_delete_question(self, question_id: int):
        """
        Handle delete question button click.

        Args:
            question_id: Research question ID
        """
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this research question?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Remove from project
            self.db_manager.remove_from_project(question_id, self.project_id)

            # If the deleted question is currently being edited, reset the form
            if self.current_question_id == question_id:
                self.question_input.clear()
                self.details_input.clear()
                self.current_question_id = None

            # Reload questions
            self.load_project(self.project_id)

            self.questionChanged.emit(question_id)


# For testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the research question widget
    question_widget = ResearchQuestionWidget()
    layout.addWidget(question_widget)

    # Set a test project ID
    question_widget.load_project(1)  # Assuming project ID 1 exists

    # Show the window
    window.setGeometry(100, 100, 600, 600)
    window.show()

    sys.exit(app.exec())
