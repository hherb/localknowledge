"""
Hypothesis widget for displaying and editing hypotheses.

This module provides a widget for displaying and editing hypotheses and
counterhypotheses for a research project.
"""
from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QFrame, QSizePolicy, QMessageBox
)
from PySide6.QtGui import QColor

from localknowledge.db.hypotheses import HypothesesDatabaseManager


class HypothesisWidget(QWidget):
    """Widget for displaying and editing hypotheses."""

    # Signal emitted when a hypothesis is updated
    hypothesisUpdated = Signal(int)

    def __init__(self, parent=None):
        """Initialize the hypothesis widget."""
        super().__init__(parent)

        # Set up database manager
        self.db_manager = HypothesesDatabaseManager()

        # Current project ID and hypothesis data
        self.project_id = None
        self.hypothesis_id = None
        self.hypothesis_data = None

        # Set up the UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

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

        # Horizontal layout for hypothesis and counterhypothesis side by side
        hypothesis_container = QHBoxLayout()

        # Left side - Hypothesis section
        hypothesis_layout = QVBoxLayout()

        # Hypothesis label
        hypothesis_label = QLabel("My hypothesis:")
        hypothesis_label.setStyleSheet("font-weight: bold;")
        hypothesis_layout.addWidget(hypothesis_label)

        # Hypothesis text edit
        self.hypothesis_edit = QTextEdit()
        self.hypothesis_edit.setPlaceholderText("A paragraph of text.\nA second row of text.")
        self.hypothesis_edit.setMinimumHeight(60)  # Reduced height for ~3 lines
        # Allow vertical stretching
        self.hypothesis_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        hypothesis_layout.addWidget(self.hypothesis_edit)

        # Add hypothesis section to container
        hypothesis_container.addLayout(hypothesis_layout)

        # Right side - Counterhypothesis section
        counterhypothesis_layout = QVBoxLayout()

        # Counterhypothesis label
        counterhypothesis_label = QLabel("Counterhypothesis:")
        counterhypothesis_label.setStyleSheet("font-weight: bold;")
        counterhypothesis_layout.addWidget(counterhypothesis_label)

        # Counterhypothesis text edit
        self.counterhypothesis_edit = QTextEdit()
        self.counterhypothesis_edit.setPlaceholderText("A paragraph of text.\nA second row of text.")
        self.counterhypothesis_edit.setMinimumHeight(60)  # Reduced height for ~3 lines
        # Allow vertical stretching
        self.counterhypothesis_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        counterhypothesis_layout.addWidget(self.counterhypothesis_edit)

        # Add counterhypothesis section to container
        hypothesis_container.addLayout(counterhypothesis_layout)

        # Add the container to the main layout
        layout.addLayout(hypothesis_container)

        # Buttons layout at the bottom
        buttons_layout = QHBoxLayout()

        # Add stretch to push buttons to the right
        buttons_layout.addStretch(1)

        # Hypothesis save button
        self.hypothesis_save_button = QPushButton("Save Hypothesis")
        self.hypothesis_save_button.clicked.connect(self._on_save_hypothesis)
        buttons_layout.addWidget(self.hypothesis_save_button)

        # Counterhypothesis save button
        self.counterhypothesis_save_button = QPushButton("Save Counterhypothesis")
        self.counterhypothesis_save_button.clicked.connect(self._on_save_counterhypothesis)
        buttons_layout.addWidget(self.counterhypothesis_save_button)

        # Add buttons layout to main layout
        layout.addLayout(buttons_layout)

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
        Load hypotheses for a project.

        Args:
            project_id: Project ID
        """
        self.project_id = project_id

        # Get hypotheses for this project
        hypotheses = self.db_manager.get_project_hypotheses(project_id)

        if hypotheses and len(hypotheses) > 0:
            # Use the first hypothesis
            self.hypothesis_data = hypotheses[0]
            self.hypothesis_id = self.hypothesis_data['id']

            # Update UI with hypothesis data
            self.hypothesis_edit.setText(self.hypothesis_data['hypothesis'])
            self.counterhypothesis_edit.setText(self.hypothesis_data['counterhypothesis'] or "")
        else:
            # No hypothesis found, clear the UI
            self.hypothesis_id = None
            self.hypothesis_data = None
            self.hypothesis_edit.clear()
            self.counterhypothesis_edit.clear()

    def _on_save_hypothesis(self):
        """Handle save hypothesis button click."""
        hypothesis_text = self.hypothesis_edit.toPlainText().strip()

        if not hypothesis_text:
            self.show_status_message("Hypothesis text is required", success=False)
            return

        if self.hypothesis_id:
            # Update existing hypothesis
            success = self.db_manager.update_hypothesis(
                self.hypothesis_id,
                {'hypothesis': hypothesis_text}
            )

            if success:
                self.show_status_message("Hypothesis updated successfully", success=True)
                self.hypothesisUpdated.emit(self.hypothesis_id)
            else:
                self.show_status_message("Failed to update hypothesis", success=False)
        else:
            # Create new hypothesis
            counterhypothesis_text = self.counterhypothesis_edit.toPlainText().strip()
            counterhypothesis = counterhypothesis_text if counterhypothesis_text else None

            hypothesis_id = self.db_manager.create_hypothesis(
                hypothesis=hypothesis_text,
                counterhypothesis=counterhypothesis
            )

            if hypothesis_id:
                # Associate with project
                self.db_manager.associate_with_project(hypothesis_id, self.project_id)

                # Update UI
                self.hypothesis_id = hypothesis_id
                self.load_project(self.project_id)

                self.show_status_message("Hypothesis created successfully", success=True)
                self.hypothesisUpdated.emit(hypothesis_id)
            else:
                self.show_status_message("Failed to create hypothesis", success=False)

    def _on_save_counterhypothesis(self):
        """Handle save counterhypothesis button click."""
        counterhypothesis_text = self.counterhypothesis_edit.toPlainText().strip()

        if not self.hypothesis_id:
            # Need to save the hypothesis first
            self.show_status_message("Please save the hypothesis first", success=False)
            return

        # Update existing hypothesis with counterhypothesis
        success = self.db_manager.update_hypothesis(
            self.hypothesis_id,
            {'counterhypothesis': counterhypothesis_text}
        )

        if success:
            self.show_status_message("Counterhypothesis updated successfully", success=True)
            self.hypothesisUpdated.emit(self.hypothesis_id)
        else:
            self.show_status_message("Failed to update counterhypothesis", success=False)


# For testing
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create a test window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Create the hypothesis widget
    hypothesis_widget = HypothesisWidget()
    layout.addWidget(hypothesis_widget)

    # Set a test project ID
    hypothesis_widget.load_project(1)  # Assuming project ID 1 exists

    # Show the window
    window.setGeometry(100, 100, 600, 400)
    window.show()

    sys.exit(app.exec())
