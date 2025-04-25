"""
Login dialog for the LocalKnowledge application.

This module provides a login dialog that allows users to log in or register.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QTabWidget, QWidget, QMessageBox,
    QFormLayout, QDialogButtonBox, QGroupBox, QSpacerItem,
    QSizePolicy
)

from localknowledge.db.user import UserDatabaseManager
from localknowledge.context import set_context, CURRENT_USER


class LoginDialog(QDialog):
    """Dialog for user login and registration."""

    # Signal emitted when user successfully logs in
    loginSuccessful = Signal(dict)

    def __init__(self, parent=None):
        """Initialize the login dialog."""
        super().__init__(parent)

        self.db_manager = UserDatabaseManager()
        self.current_user = None

        self.setWindowTitle("Login")
        self.setMinimumWidth(400)

        # Set window icon and store path for later use
        self.icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "enthusiasticrobo_medium.png")
        self.setWindowIcon(QIcon(self.icon_path))

        self.setup_ui()

        # Try to load saved login info
        self.load_saved_login()

    def setup_ui(self):
        """Set up the user interface."""
        # Main layout
        main_layout = QVBoxLayout(self)

        # Create tab widget for login/register tabs
        self.tab_widget = QTabWidget()

        # Login tab
        login_widget = QWidget()
        login_layout = QVBoxLayout(login_widget)

        # Logo/header
        logo_label = QLabel()
        # Use the same icon path that was set in __init__
        logo_pixmap = QPixmap(self.icon_path).scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo_label.setPixmap(logo_pixmap)
        logo_label.setAlignment(Qt.AlignCenter)
        login_layout.addWidget(logo_label)

        # Login form
        login_form = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username or Email")
        login_form.addRow("Username:", self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        login_form.addRow("Password:", self.password_input)

        login_layout.addLayout(login_form)

        # Remember me checkbox
        self.remember_checkbox = QCheckBox("Remember me")
        login_layout.addWidget(self.remember_checkbox)

        # Add some spacing
        login_layout.addSpacing(10)

        # Login button
        login_button = QPushButton("Login")
        login_button.setDefault(True)
        login_button.clicked.connect(self.login)
        login_layout.addWidget(login_button)

        # Add login tab
        self.tab_widget.addTab(login_widget, "Login")

        # Register tab
        register_widget = QWidget()
        register_layout = QVBoxLayout(register_widget)

        # Logo/header for register tab
        register_logo_label = QLabel()
        register_logo_label.setPixmap(logo_pixmap)  # Reuse the same pixmap from login tab
        register_logo_label.setAlignment(Qt.AlignCenter)
        register_layout.addWidget(register_logo_label)

        # Registration form
        register_form = QFormLayout()

        self.reg_username = QLineEdit()
        self.reg_username.setPlaceholderText("Choose a username")
        register_form.addRow("Username:", self.reg_username)

        self.reg_firstname = QLineEdit()
        self.reg_firstname.setPlaceholderText("First name")
        register_form.addRow("First name:", self.reg_firstname)

        self.reg_surname = QLineEdit()
        self.reg_surname.setPlaceholderText("Last name")
        register_form.addRow("Last name:", self.reg_surname)

        self.reg_email = QLineEdit()
        self.reg_email.setPlaceholderText("Email address")
        register_form.addRow("Email:", self.reg_email)

        self.reg_password = QLineEdit()
        self.reg_password.setPlaceholderText("Choose a password")
        self.reg_password.setEchoMode(QLineEdit.Password)
        register_form.addRow("Password:", self.reg_password)

        self.reg_confirm_password = QLineEdit()
        self.reg_confirm_password.setPlaceholderText("Confirm password")
        self.reg_confirm_password.setEchoMode(QLineEdit.Password)
        register_form.addRow("Confirm:", self.reg_confirm_password)

        register_layout.addLayout(register_form)

        # Add some spacing
        register_layout.addSpacing(10)

        # Register button
        register_button = QPushButton("Register")
        register_button.clicked.connect(self.register_user)
        register_layout.addWidget(register_button)

        # Add register tab
        self.tab_widget.addTab(register_widget, "Register")

        # Add tab widget to main layout
        main_layout.addWidget(self.tab_widget)

        # Button box for Cancel
        button_box = QDialogButtonBox(QDialogButtonBox.Cancel)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def login(self):
        """Attempt to log in the user."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Login Error", "Please enter both username and password.")
            return

        # Attempt authentication
        user = self.db_manager.authenticate_user(username, password)

        if user:
            # Save login info if remember checkbox is checked
            if self.remember_checkbox.isChecked():
                self.save_login_info(username)

            # Store the current user
            self.current_user = user

            # Store user in the global context
            set_context(CURRENT_USER, user)

            # Emit signal with user data
            self.loginSuccessful.emit(user)

            # Close dialog with success
            self.accept()
        else:
            QMessageBox.critical(self, "Login Failed", "Invalid username or password.")

    def register_user(self):
        """Register a new user."""
        # Get input values
        username = self.reg_username.text().strip()
        firstname = self.reg_firstname.text().strip()
        surname = self.reg_surname.text().strip()
        email = self.reg_email.text().strip()
        password = self.reg_password.text()
        confirm_password = self.reg_confirm_password.text()

        # Validate input
        if not username or not firstname or not surname or not email or not password:
            QMessageBox.warning(self, "Registration Error", "Please fill in all fields.")
            return

        if password != confirm_password:
            QMessageBox.warning(self, "Registration Error", "Passwords do not match.")
            return

        if '@' not in email or '.' not in email:
            QMessageBox.warning(self, "Registration Error", "Please enter a valid email address.")
            return

        # Attempt to create the user
        try:
            user_id = self.db_manager.create_user(username, firstname, surname, email, password)

            if user_id:
                # Show success message
                QMessageBox.information(self, "Registration Successful",
                                       f"Welcome, {firstname}! You can now log in.")

                # Switch to login tab and pre-fill username
                self.tab_widget.setCurrentIndex(0)
                self.username_input.setText(username)
                self.password_input.setText("")
                self.password_input.setFocus()
            else:
                QMessageBox.critical(self, "Registration Failed",
                                    "Could not create user due to an unknown error.")
        except ValueError as e:
            # Handle specific constraint violations
            QMessageBox.warning(self, "Registration Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Registration Error", f"An error occurred: {str(e)}")

    def save_login_info(self, username):
        """Save login information for auto-login next time."""
        try:
            # Get the settings directory
            settings_dir = Path.home() / ".localknowledge"
            settings_dir.mkdir(exist_ok=True)

            # Save username to file
            with open(settings_dir / "autologin", "w") as f:
                f.write(username)
        except Exception as e:
            print(f"Error saving login info: {e}")

    def load_saved_login(self):
        """Load saved login information if available."""
        try:
            settings_dir = Path.home() / ".localknowledge"
            autologin_file = settings_dir / "autologin"

            if autologin_file.exists():
                with open(autologin_file, "r") as f:
                    username = f.read().strip()
                    if username:
                        self.username_input.setText(username)
                        self.remember_checkbox.setChecked(True)
                        self.password_input.setFocus()
        except Exception as e:
            print(f"Error loading saved login: {e}")

    def clear_saved_login(self):
        """Clear saved login information."""
        try:
            settings_dir = Path.home() / ".localknowledge"
            autologin_file = settings_dir / "autologin"

            if autologin_file.exists():
                autologin_file.unlink()
        except Exception as e:
            print(f"Error clearing saved login: {e}")

    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get the currently logged in user.

        Returns:
            Dictionary with user data or None if no user is logged in
        """
        return self.current_user


# Example standalone usage
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    dialog = LoginDialog()

    # Connect to test slot
    @Slot(dict)
    def handle_login(user_data):
        print(f"User logged in: {user_data['username']}")

    dialog.loginSuccessful.connect(handle_login)

    if dialog.exec() == QDialog.Accepted:
        print("Login successful")
    else:
        print("Login cancelled")

    sys.exit(0)
