"""Cyberpunk-styled login dialog for desktop auth."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
from PyQt5.QtGui import QColor

from auth_client import AuthClient, AuthError
from auth_config import AuthSettings
from auth_session import AuthSession
from theme import DANGER, TEXT_MUTED, LOGIN_QSS


class LoginDialog(QDialog):
    def __init__(self, settings: AuthSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.session: AuthSession | None = None
        self.setWindowTitle("Automation Hub — Sign In")
        self.setModal(True)
        self.setFixedWidth(420)
        self.setStyleSheet(LOGIN_QSS)

        card = QFrame()
        card.setObjectName("loginCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 12)
        card.setGraphicsEffect(shadow)

        brand = QLabel("AUTOMATION HUB")
        brand.setObjectName("loginBrand")

        title = QLabel("Welcome back")
        title.setObjectName("loginTitle")

        subtitle = QLabel("Sign in to continue to your workspace")
        subtitle.setObjectName("loginSubtitle")
        subtitle.setWordWrap(True)

        user_label = QLabel("USERNAME")
        user_label.setObjectName("fieldLabel")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")

        pass_label = QLabel("PASSWORD")
        pass_label.setObjectName("fieldLabel")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.status_label = QLabel("")
        self.status_label.setObjectName("statusMsg")
        self.status_label.setWordWrap(True)

        self.login_button = QPushButton("Sign In")
        self.login_button.setObjectName("loginBtn")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setMinimumHeight(44)
        self.login_button.clicked.connect(self._attempt_login)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 30, 30, 30)
        card_layout.setSpacing(8)
        card_layout.addWidget(brand)
        card_layout.addSpacing(6)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(16)
        card_layout.addWidget(user_label)
        card_layout.addWidget(self.username_input)
        card_layout.addSpacing(10)
        card_layout.addWidget(pass_label)
        card_layout.addWidget(self.password_input)
        card_layout.addSpacing(6)
        card_layout.addWidget(self.status_label)
        card_layout.addSpacing(10)
        card_layout.addWidget(self.login_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addWidget(card)

        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())
        self.password_input.returnPressed.connect(self._attempt_login)

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            self.status_label.setText("Username and password are required.")
            return

        client = AuthClient(self.settings)
        session = AuthSession(settings=self.settings, client=client)
        self.status_label.setStyleSheet(f"color: {TEXT_MUTED};")
        self.status_label.setText("Authenticating with server...")
        self.login_button.setEnabled(False)

        try:
            result = client.login(
                username,
                password,
                session.device_id,
                session.pc_name,
            )
            session.apply_login(result)
            session.load_payload()
            client.log_activity(
                session.access_token,
                "app_login",
                session.device_id,
                session.pc_name,
            )
            self.session = session
            self.accept()
        except AuthError as exc:
            self.status_label.setStyleSheet(f"color: {DANGER};")
            self.status_label.setText(exc.message)
        except Exception as exc:
            self.status_label.setStyleSheet(f"color: {DANGER};")
            self.status_label.setText(f"Login failed: {exc}")
        finally:
            self.login_button.setEnabled(True)


def require_login(settings: AuthSettings, parent=None) -> AuthSession | None:
    if not settings.api_base:
        QMessageBox.critical(
            parent,
            "Auth Server Not Configured",
            "Set auth.api_base and auth.app_key in config.json before starting.",
        )
        return None

    dialog = LoginDialog(settings, parent=parent)
    if dialog.exec_() != QDialog.Accepted or not dialog.session:
        return None
    return dialog.session

