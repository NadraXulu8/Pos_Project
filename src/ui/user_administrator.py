"""
user_administrator.py — Frontend UI untuk halaman User Management.

Halaman ini menampilkan daftar user dalam tabel dengan fitur:
- Filter berdasarkan role (Super_user, Admin, dll.)
- Tombol aksi global: Tambah, Edit, Hapus User
- Kolom password di-mask dengan karakter bulat (••••••••)
- Kolom aksi berisi tombol Edit & Hapus per-baris

"""

from PySide6.QtCore import (
    Qt, QRect, QSize, QPoint, QModelIndex, QPersistentModelIndex, QEvent, Signal, QObject
)
from PySide6.QtGui import (
    QFont, QShortcut, QKeySequence, QIcon, QPainter, QPen,
    QColor, QCursor, QPixmap, QMouseEvent
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QComboBox,
    QStackedWidget, QStyledItemDelegate, QStyle,
    QStyleOptionViewItem, QApplication, QToolTip,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QTableWidget
)
from shiboken6 import isValid

import math
from src.database.database import DatabaseManager

from config import asset_path, asset_uri
from src.ui.ui_base import BaseTableWidget, BaseDataPage
from src.utils.message import CustomMessageBox
from src.ui.register import RegisterDialog

class UserFormDialog(QDialog):
    def __init__(self, parent=None, user_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit User" if user_data else "Tambah User")
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #ffffff; font-family: "Segoe UI"; }
            QLabel { color: #ffffff; font-size: 14px; }
            QLineEdit, QComboBox { 
                background-color: #333333; color: #ffffff; 
                border: 1px solid #555555; padding: 5px; border-radius: 4px; font-size: 14px;
            }
            QPushButton { background-color: #0d47a1; color: #ffffff; padding: 6px 12px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #1565c0; }
        """)
        
        self.nama_input, self.kunci_input, self.role_input = QLineEdit(), QLineEdit(), QComboBox()
        self.kunci_input.setPlaceholderText("Kosongkan jika tidak diubah" if user_data else "Harus 10 digit angka")
        self.kunci_input.setMaxLength(10)
        self.role_input.addItems(["Admin", "Super_user"])
        
        self.id_user = user_data.get('id') if user_data else None
        if user_data:
            self.nama_input.setText(user_data.get('nama', ''))
            if (idx := self.role_input.findText(user_data.get('role', 'Admin'))) >= 0: self.role_input.setCurrentIndex(idx)
            
        layout = QFormLayout(self)
        layout.addRow("Nama User:", self.nama_input)
        layout.addRow("Kunci Akses:", self.kunci_input)
        layout.addRow("Role:", self.role_input)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        
    def get_data(self):
        return {"id": self.id_user, "nama": self.nama_input.text().strip(), "kunci": self.kunci_input.text().strip(), "role": self.role_input.currentText()}

_PASSWORD_CHAR = "●"
_ACTION_ICON_SIZE = 20 
_ACTION_BUTTON_GAP = 12
_ACTION_BUTTON_PADDING = 14

COL_ID = 0
COL_NAMA = 1
COL_ROLE = 2
COL_PASSWORD = 3
COL_AKSI = 4

class PasswordDelegate(QStyledItemDelegate):
    """
    Menampilkan teks pada kolom password sebagai karakter bulat (●●●●●●●●).
    Teks asli tetap tersimpan di model, hanya rendering yang di-mask.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mask_font = QFont("Segoe UI", 12)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        raw_text = index.data(Qt.ItemDataRole.DisplayRole)
        masked = _PASSWORD_CHAR * min(len(str(raw_text)), 12) if raw_text else ""

        painter.save()
        painter.setFont(self._mask_font)
        painter.setPen(QPen(QColor("#ffffff")))
        painter.drawText(option.rect.adjusted(12, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, masked)
        painter.restore()


class ActionDelegate(QStyledItemDelegate):
    """
    Render dua ikon (Edit & Hapus) secara berdampingan di dalam cell kolom AKSI.

    Fitur UX:
    - Hover effect: ikon memudar (opacity) saat cursor di atas area tombol.
    - Cursor berubah menjadi PointingHandCursor saat di area ikon.
    - Tooltip "Edit User" / "Hapus User".
    """

    def __init__(self, table_widget: QTableWidget, parent=None):
        super().__init__(parent)
        self._table: QTableWidget | None = table_widget

        self._icon_edit = QIcon(asset_path("edit_button.svg"))
        self._icon_delete = QIcon(asset_path("remove_button.svg"))

        self._hover_row = -1
        self._hover_zone = ""

        table_widget.viewport().installEventFilter(self)
        table_widget.viewport().setMouseTracking(True)
        table_widget.destroyed.connect(self._on_table_destroyed)

    def _on_table_destroyed(self, *_):
        self._table, self._hover_row, self._hover_zone = None, -1, ""

    @staticmethod
    def _is_object_valid(obj: QObject | None) -> bool:
        try: return obj is not None and isValid(obj)
        except RuntimeError: return False

    def _get_table_and_viewport(self) -> tuple[QTableWidget | None, QWidget | None]:
        if self._table is None or not self._is_object_valid(self._table): return None, None
        try: vp = self._table.viewport()
        except RuntimeError: return None, None
        return (self._table, vp) if self._is_object_valid(vp) else (None, None)

    def _icon_rects(self, cell_rect: QRect):
        y = cell_rect.center().y() - _ACTION_ICON_SIZE // 2
        x = cell_rect.center().x() - (_ACTION_ICON_SIZE * 2 + _ACTION_BUTTON_GAP) // 2
        return QRect(x, y, _ACTION_ICON_SIZE, _ACTION_ICON_SIZE), QRect(x + _ACTION_ICON_SIZE + _ACTION_BUTTON_GAP, y, _ACTION_ICON_SIZE, _ACTION_ICON_SIZE)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, option, painter, option.widget)

        e_rect, d_rect = self._icon_rects(option.rect)
        painter.save()
        is_hover = (index.row() == self._hover_row)
        
        painter.setOpacity(1.0 if is_hover and self._hover_zone == "edit" else 0.55)
        self._icon_edit.paint(painter, e_rect)
        
        painter.setOpacity(1.0 if is_hover and self._hover_zone == "delete" else 0.55)
        self._icon_delete.paint(painter, d_rect)
        painter.restore()

    def eventFilter(self, obj, event: QEvent):
        table, vp = self._get_table_and_viewport()
        if not table or not vp: return False
        if obj is not vp: return super().eventFilter(obj, event)

        evt_type = event.type()
        if evt_type == QEvent.Type.MouseMove:
            mouse_evt: QMouseEvent = event  # type: ignore[assignment]
            pos = mouse_evt.position().toPoint()
            idx = table.indexAt(pos)
            if idx.isValid() and idx.column() == COL_AKSI:
                e_rect, d_rect = self._icon_rects(table.visualRect(idx))
                old_row, old_zone = self._hover_row, self._hover_zone
                
                if e_rect.contains(pos): self._hover_row, self._hover_zone = idx.row(), "edit"
                elif d_rect.contains(pos): self._hover_row, self._hover_zone = idx.row(), "delete"
                else: self._hover_row, self._hover_zone = -1, ""

                if self._hover_row != -1:
                    vp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    QToolTip.showText(vp.mapToGlobal(pos), "Edit User" if self._hover_zone == "edit" else "Hapus User")
                else:
                    vp.unsetCursor()
                    QToolTip.hideText()

                if (old_row, old_zone) != (self._hover_row, self._hover_zone): vp.update()
            elif self._hover_row != -1:
                self._hover_row, self._hover_zone = -1, ""
                vp.unsetCursor()
                vp.update()

        elif evt_type == QEvent.Type.MouseButtonRelease:
            mouse_evt_rel: QMouseEvent = event  # type: ignore[assignment]
            pos = mouse_evt_rel.position().toPoint()
            idx = table.indexAt(pos)
            if idx.isValid() and idx.column() == COL_AKSI:
                e_rect, d_rect = self._icon_rects(table.visualRect(idx))
                if e_rect.contains(pos): self._on_edit_clicked(idx.row())
                elif d_rect.contains(pos): self._on_delete_clicked(idx.row())

        elif evt_type == QEvent.Type.Leave and self._hover_row != -1:
            self._hover_row, self._hover_zone = -1, ""
            vp.update()

        return super().eventFilter(obj, event)

    def _on_edit_clicked(self, row: int):
        if (ut := self._resolve_user_table()) and hasattr(ut, "edit_requested"): getattr(ut, "edit_requested").emit(row)

    def _on_delete_clicked(self, row: int):
        if (ut := self._resolve_user_table()) and hasattr(ut, "delete_requested"): getattr(ut, "delete_requested").emit(row)

    def _resolve_user_table(self) -> QObject | None:
        w = self.parent() if self._is_object_valid(self.parent()) else (self._table if self._is_object_valid(self._table) else None)
        while w:
            if hasattr(w, 'edit_requested') and hasattr(w, 'delete_requested'): return w
            w = w.parent()
        return None


class UserTable(BaseTableWidget):
    """
    Tabel daftar user dengan kolom: ID, NAMA, ROLE, KUNCI/PASSWORD, AKSI.
    Menggunakan delegate khusus pada kolom PASSWORD dan AKSI.
    """

    edit_requested = Signal(int)
    delete_requested = Signal(int)

    TABLE_WIDTH = 800
    TABLE_ROW_COUNT = 3
    ROW_HEIGHT = 45
    COLUMN_WIDTHS = [60, 0, 120, 0, 120]
    HEADERS = ["ID", "NAMA", "ROLE", "KUNCI/PASSWORD", "AKSI"]
    FIELDS = ["id", "nama", "role", "password", "aksi"]
    LEFT_ALIGN_FIELDS = ["nama"]

    def __init__(self):
        super().__init__()
        self._apply_styling()
        self._apply_delegates()

    def _apply_styling(self):
        """Override default styling tabel agar sesuai dark theme."""
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #1a1a1a;
                alternate-background-color: #232323;
                gridline-color: #333333;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 6px;
                font-family: "Segoe UI";
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #0d47a1;
                color: #ffffff;
            }
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #ffffff;
                padding: 8px 5px;
                border: none;
                border-bottom: 2px solid #00aaff;
                font-family: "Segoe UI";
                font-weight: bold;
                font-size: 13px;
            }
            QTableCornerButton::section {
                background-color: #2a2a2a;
                border: none;
            }
            /* Scrollbar */
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #555555;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #777777;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)

    def _apply_delegates(self):
        """Pasang delegate khusus pada kolom Password dan Aksi."""
        self._password_delegate = PasswordDelegate(self.table)
        self.table.setItemDelegateForColumn(COL_PASSWORD, self._password_delegate)

        self._action_delegate = ActionDelegate(self.table, parent=self.table)
        self.table.setItemDelegateForColumn(COL_AKSI, self._action_delegate)

    def set_data(self, rows: list[dict]):
        """Override: atur data dan pastikan row height konsisten."""
        super().set_data(rows)
        self.table.setRowCount(len(rows))
        self.table.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)


class UserAdministrator(BaseDataPage):
    """
    Halaman utama User Management.
    Menampilkan filter role, tombol aksi, search bar, dan tabel user.
    """

    HEADER_TITLE = "USER MANAGEMENT"
    SEARCH_PLACEHOLDER = "Cari Nama atau ID User ..."
    USERS_PER_PAGE = 3

    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_connections()

        shortcut = QShortcut(QKeySequence("Return"), self)
        shortcut.activated.connect(self.handle_shortcut)

    def _add_custom_widgets(self, layout):
        """Tambahkan filter role dan tombol aksi di atas search bar."""
        controls_widget = self._create_controls_bar()
        layout.addWidget(controls_widget)
        layout.addSpacing(10)

    def _create_controls_bar(self) -> QWidget:
        """
        Susun Tombol Aksi secara horizontal.
        Layout: spacer -- [Tambah] [Edit] [Hapus]
        """
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addStretch()

        self.button_tambah = self._create_action_button("Tambah User", "#00ff00")
        self.button_edit = self._create_action_button("Edit User", "#ff8000")
        self.button_hapus = self._create_action_button("Hapus User", "#ff0000")

        layout.addWidget(self.button_tambah)
        layout.addWidget(self.button_edit)
        layout.addWidget(self.button_hapus)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_data_widget(self) -> QWidget:
        """Buat widget berisi filter, tabel user, dan navigasi halaman."""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 10)
        
        filter_layout.addStretch()
        
        filter_container = QWidget()
        filter_container.setFixedWidth(800)
        fc_layout = QHBoxLayout(filter_container)
        fc_layout.setContentsMargins(0, 0, 0, 0)

        self.filter_role = QComboBox()
        self.filter_role.addItems(["Semua", "Super_user", "Admin"])
        self.filter_role.setFont(QFont("Segoe UI", 14))
        self.filter_role.setFixedSize(180, 35)
        self.filter_role.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_role.setStyleSheet(f"""
            QComboBox {{
                background-color: #1a1a1a;
                color: #ffffff;
                border: 2px solid #444444;
                border-radius: 10px;
                padding-left: 12px;
                font-family: "Segoe UI";
                font-size: 14px;
            }}
            QComboBox:hover {{
                border-color: #00aaff;
            }}
            QComboBox:focus {{
                border-color: #00aaff;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 30px;
                border-left: 1px solid #444444;
                border-top-right-radius: 10px;
                border-bottom-right-radius: 10px;
            }}
            QComboBox::down-arrow {{
                image: url({asset_uri("icon_down.svg")});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1a1a1a;
                color: #ffffff;
                selection-background-color: #0d47a1;
                selection-color: #ffffff;
                border: 1px solid #444444;
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding-left: 10px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #333333;
            }}
        """)
        fc_layout.addWidget(self.filter_role)
        fc_layout.addStretch()
        
        filter_layout.addWidget(filter_container)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)

        self.stack = QStackedWidget()
        self.table_user = UserTable()
        self.table_user.table.setSelectionBehavior(
            self.table_user.table.SelectionBehavior.SelectRows
        )
        self.table_user.table.setSelectionMode(
            self.table_user.table.SelectionMode.SingleSelection
        )
        self.stack.addWidget(self.table_user)
        layout.addWidget(self.stack)

        navigation_widget = self._create_bottom_navigation()
        layout.addWidget(navigation_widget)

        widget.setLayout(layout)
        return widget

    def _setup_connections(self):
        """Hubungkan sinyal tombol ke handler."""
        self.button_tambah.clicked.connect(self._on_tambah_user)
        self.button_edit.clicked.connect(self._on_edit_user)
        self.button_hapus.clicked.connect(self._on_hapus_user)
        self.filter_role.currentIndexChanged.connect(self._on_filter_changed)
        self.table_user.edit_requested.connect(self._on_edit_user_by_row)
        self.table_user.delete_requested.connect(self._on_hapus_user_by_row)
        
        if hasattr(self, 'search_input'):
            self.search_input.returnPressed.connect(self._on_filter_changed)

    def _on_tambah_user(self):
        dialog = RegisterDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.table_data()
            CustomMessageBox.information(self, "Sukses", "User berhasil ditambahkan!")

    def _on_edit_user(self):
        table = self.table_user.table
        current_row = table.currentRow()
        if current_row < 0:
            CustomMessageBox.critical(self, "Error", "Pilih user terlebih dahulu!")
            return
        self._on_edit_user_by_row(current_row)

    def _on_edit_user_by_row(self, row: int):
        user_data = self.table_user._all_rows[row]
        dialog = UserFormDialog(self, user_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            try:
                db = DatabaseManager()
                db.update_user(data['id'], data['nama'], data['kunci'], data['role'])
                self.table_data()
                CustomMessageBox.information(self, "Sukses", "User berhasil diupdate!")
            except ValueError as e:
                CustomMessageBox.critical(self, "Gagal", str(e))

    def _on_hapus_user(self):
        table = self.table_user.table
        current_row = table.currentRow()
        if current_row < 0:
            CustomMessageBox.critical(self, "Error", "Pilih user terlebih dahulu!")
            return
        self._on_hapus_user_by_row(current_row)

    def _on_hapus_user_by_row(self, row: int):
        user_data = self.table_user._all_rows[row]
        confirm = CustomMessageBox.question(
            self, "Konfirmasi Hapus",
            f"Apakah Anda yakin ingin menghapus user {user_data.get('nama')}?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                db = DatabaseManager()
                db.delete_user(user_data['id'])
                self.table_data()
                CustomMessageBox.information(self, "Sukses", "User berhasil dihapus!")
            except ValueError as e:
                CustomMessageBox.critical(self, "Gagal", str(e))


    def _on_filter_changed(self, index=None):
        self.table_data()

    def table_data(self, offset=0):
        db = DatabaseManager()
        role_filter = self.filter_role.currentText()
        search_text = getattr(self, 'search_input', None)
        search_str = search_text.text().strip() if search_text else ""

        data = db.get_users_for_table(role_filter, search_str, limit=self.USERS_PER_PAGE, offset=offset)
        self.table_user.set_data(data)

        total_rows = db.get_users_count(role_filter, search_str)
        pages = math.ceil(total_rows / self.USERS_PER_PAGE) if total_rows > 0 else 1
        self.pages = pages

        if offset == 0:
            self.page_input.setText("1")
        else:
            text_page = int(offset / self.USERS_PER_PAGE) + 1
            self.page_input.setText(str(text_page))

    def custom_page(self):
        p = int(self.page_input.text().strip() or "1")
        if p <= 0:
            self.page_input.setText("1")
            self.table_data()
        elif p >= self.pages:
            self.page_input.setText(str(self.pages))
            self.table_data((self.pages - 1) * self.USERS_PER_PAGE)
        else:
            self.table_data((p - 1) * self.USERS_PER_PAGE)

    def next_page(self):
        p = int(self.page_input.text().strip() or "1")
        if p < getattr(self, 'pages', 1): self.table_data(p * self.USERS_PER_PAGE)

    def prev_page(self):
        p = int(self.page_input.text().strip() or "1")
        if p > 1: self.table_data((p - 2) * self.USERS_PER_PAGE)

    def on_reset_click(self):
        self.filter_role.setCurrentIndex(0)
        if hasattr(self, 'search_input'):
            self.search_input.clear()

    def refresh_data(self):
        if hasattr(self, 'search_input'):
            self.search_input.clear()
        self.filter_role.setCurrentIndex(0)
        self.page_input.setText("1")
        self.table_data()
