from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QIcon, QIntValidator
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QApplication, QHeaderView,
    QFrame, QLabel
)

from fungsi import NavigationButton

class ActionButton(QPushButton):
    """Tombol aksi standar dengan pengaturan warna"""
    def __init__(self, text: str, color: str, width: int = 200, height: int = 35):
        super().__init__(text)
        self.setFixedSize(width, height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 10px;
                font-family: "Segoe UI";
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover{{
                background-color: #ffffff;
                color: {color};
            }}
        """)


class BaseTableWidget(QWidget):
    """Base class untuk tabel di aplikasi POS"""
    TABLE_WIDTH = 800
    TABLE_ROW_COUNT = 5
    COLUMN_WIDTHS = []
    HEADERS = []
    FIELDS = []
    FORMATTERS = {}
    LEFT_ALIGN_FIELDS = []

    def __init__(self):
        super().__init__()
        self.current_page = 1
        self.per_page = self.TABLE_ROW_COUNT
        self._all_rows = []
        self._setup_ui()

    def _setup_ui(self):
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 5)
        root_layout.addStretch()

        table_widget = QWidget()
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)

        self.table = self._create_table()
        table_layout.addWidget(self.table)

        table_widget.setLayout(table_layout)
        root_layout.addWidget(table_widget)
        root_layout.addStretch()
        self.setLayout(root_layout)

    def _create_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setRowCount(self.TABLE_ROW_COUNT)
        table.setColumnCount(len(self.COLUMN_WIDTHS))
        table.setFixedWidth(self.TABLE_WIDTH)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setHorizontalHeaderLabels(self.HEADERS)

        header = table.horizontalHeader()
        table.verticalHeader().setVisible(False)

        for index, width in enumerate(self.COLUMN_WIDTHS):
            if width == 0:
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
            else:
                table.setColumnWidth(index, width)
                header.setSectionResizeMode(index, QHeaderView.ResizeMode.Fixed)

        table.setAlternatingRowColors(True)
        table.setStyleSheet("""
            QTableWidget{
                background-color: #ffffff;
                gridline-color: #d0d0d0;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 5px;
                border: 1px solid #d0d0d0;
                font-weight: bold;
            }
        """)
        return table

    def reset_width(self):
        pass

    def set_data(self, rows: list[dict]):
        self._all_rows = rows or []
        self.current_page = 1
        self._render_current_page()

    def _render_current_page(self):
        self.table.clearContents()
        for r, row in enumerate(self._all_rows):
            for c, key in enumerate(self.FIELDS):
                val = row.get(key)
                if key in self.FORMATTERS:
                    val = self.FORMATTERS[key](val)
                item = QTableWidgetItem("" if val is None else str(val))
                if key in self.LEFT_ALIGN_FIELDS:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, item)


class BaseDataPage(QWidget):
    """Base class untuk halaman data (seperti produk dan pelanggan)"""
    BUTTON_WIDTH = 200
    BUTTON_HEIGHT = 35
    SEARCH_FIELD_WIDTH = 500
    SEARCH_BUTTON_WIDTH = 100
    CONTENT_WIDGET_WIDTH = 800
    PAGE_INPUT_WIDTH = 30
    PAGE_INPUT_HEIGHT = 30
    RESET_BUTTON_WIDTH = 100

    HEADER_TITLE = ""
    SEARCH_PLACEHOLDER = ""

    def __init__(self):
        super().__init__()
        self.pages = 0

    def _setup_ui(self):
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_widget = QFrame()
        root_widget.setContentsMargins(0, 0, 0, 0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        if self.HEADER_TITLE:
            header_label = self._create_header_label()
            content_layout.addWidget(header_label)
            content_layout.addSpacing(20)

        self._add_custom_widgets(content_layout)

        if self.SEARCH_PLACEHOLDER:
            search_widget = self._create_search_widget(self.SEARCH_PLACEHOLDER)
            content_layout.addWidget(search_widget)

        content_layout.addStretch()

        data_widget = self._create_data_widget()
        if data_widget:
            content_layout.addWidget(data_widget)

        root_widget.setLayout(content_layout)
        root_layout.addWidget(root_widget)
        self.setLayout(root_layout)
        self.setStyleSheet("border: none")
        self.table_data()

    def _create_header_label(self) -> QLabel:
        label = QLabel(self.HEADER_TITLE)
        label.setFont(QFont("Times New Roman", 30, QFont.Weight.Bold))
        label.setStyleSheet("color: #ffffff;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _add_custom_widgets(self, layout):
        pass

    def _create_data_widget(self) -> QWidget | None:
        return None

    def _create_action_button(self, text: str, color: str) -> ActionButton:
        return ActionButton(text, color, self.BUTTON_WIDTH, self.BUTTON_HEIGHT)

    def _create_search_widget(self, placeholder_text: str) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout()
        layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setStyleSheet("""
            QLineEdit{
                border: 2px solid #ffffff;
                border-radius: 10px;
                background-color: #676767;
                color: #ffffff;
                font-family: "Segoe UI";
                padding-left: 10px;
                font-size: 16px;
            }
            QLineEdit:placeholder {
                color: #d3d3d3;
            }
            QLineEdit[active ="true"] {
                border: 2px solid #00aaff;
            }
        """)
        self.search_input.setPlaceholderText(placeholder_text)
        self.search_input.setFixedSize(self.SEARCH_FIELD_WIDTH, self.BUTTON_HEIGHT)
        self.search_input.setProperty("active", False)
        layout.addWidget(self.search_input)

        search_button = QPushButton("   Cari")
        search_button.setFixedSize(self.SEARCH_BUTTON_WIDTH, self.BUTTON_HEIGHT)
        search_button.setIcon(QIcon("data/search.svg"))
        search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        search_button.setStyleSheet("""
            QPushButton{
                background-color: #00aaff;
                color: white;
                border: 2px solid #00aaff;
                border-radius: 10px;
                font-family: "Segoe UI";
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0055ff;
                color: #ffffff;
                border: 2px solid #0055ff;
            }
        """)
        search_button.clicked.connect(self.search_page)
        layout.addWidget(search_button)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def _create_bottom_navigation(self) -> QWidget:
        root_widget = QWidget()
        root_widget.setContentsMargins(0, 0, 0, 0)
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addStretch()

        content_widget = QWidget()
        content_widget.setFixedSize(self.CONTENT_WIDGET_WIDTH, self.BUTTON_HEIGHT)
        content_widget.setContentsMargins(0, 0, 0, 0)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        button_reset = QPushButton(" Reset")
        button_reset.setIcon(QIcon("data/reset.svg"))
        button_reset.setFixedSize(self.RESET_BUTTON_WIDTH, self.BUTTON_HEIGHT)
        button_reset.setIconSize(QSize(20, 20))
        button_reset.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        button_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        button_reset.clicked.connect(self.reset_click)
        button_reset.setStyleSheet("""
            QPushButton{
                background-color: #ff8000;
                color: white;
                border: 2px solid #ff8000;
                border-radius: 10px;
            }
        """)
        content_layout.addWidget(button_reset)
        self._add_bottom_left_buttons(content_layout)
        content_layout.addStretch()

        button_left = NavigationButton("data/arah kiri.svg", "data/kiri-hover.svg")
        button_left.clicked.connect(self.prev_page)
        content_layout.addWidget(button_left)

        self.page_input = QLineEdit()
        self.page_input.setText("1")
        self.page_input.setValidator(QIntValidator(0, 99))
        self.page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_input.setFixedSize(self.PAGE_INPUT_WIDTH, self.PAGE_INPUT_HEIGHT)
        self.page_input.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.page_input.setStyleSheet("""
            QLineEdit{
                border: none;
                background-color: #ffffff;
                color: #000000;
                border-radius: 5px;
            }
        """)
        self.page_input.setMaxLength(2)
        content_layout.addWidget(self.page_input)

        button_right = NavigationButton("data/arah kanan.svg", "data/kanan-hover.svg")
        button_right.clicked.connect(self.next_page)
        content_layout.addWidget(button_right)

        content_widget.setLayout(content_layout)
        root_layout.addWidget(content_widget)
        root_layout.addStretch()

        root_widget.setLayout(root_layout)
        return root_widget

    def search_page(self):
        current = bool(self.search_input.property("active"))
        text = self.search_input.text().strip()
        if (text != "" and current == False) or (text != "" and current == True):
            if not current:
                self.search_input.setProperty("active", not current)
            self.search_input.style().unpolish(self.search_input)
            self.search_input.style().polish(self.search_input)
            self.table_data()
        elif text == "" and current == True:
            self.search_input.setProperty("active", not current)
            self.search_input.style().unpolish(self.search_input)
            self.search_input.style().polish(self.search_input)
            self.table_data()

    def handle_shortcut(self):
        focused = QApplication.focusWidget()
        if hasattr(self, 'search_input') and focused == self.search_input:
            self.search_page()
        elif hasattr(self, 'page_input') and focused == self.page_input:
            self.custom_page()

    # Metode ini harus di-overwrite oleh subclass
    def table_data(self, offset=0):
        pass

    def custom_page(self):
        pass

    def next_page(self):
        pass

    def prev_page(self):
        pass

    def reset_click(self):
        self.search_input.setText("")
        self.search_page()
        self.on_reset_click()

    def on_reset_click(self):
        """Hook for additional reset actions in subclasses"""
        pass

    def _add_bottom_left_buttons(self, layout):
        """Hook for adding extra buttons beside reset in bottom navigation."""
        pass
