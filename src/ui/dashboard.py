from PySide6 import QtCore
from PySide6.QtCore import QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QFrame, QStackedWidget
)
from config import asset_path

from src.database.database import DatabaseManager
from src.ui.manajemen_produk import ManajemenProduk
from src.ui.error import ErrorWindow
from src.ui.welcome import WelcomeWindow
from src.ui.transaksi import PenjualanWindow
from src.ui.sejarah_transaksi import SejarahTransaksiWindow


class Dashboard(QWidget):
    """Dashboard utama aplikasi dengan sidebar navigasi"""

    # Konstanta
    SIDEBAR_LEFT_WIDTH = 50
    SIDEBAR_RIGHT_WIDTH = 250
    BUTTON_SIZE = 30
    ICON_SIZE = 22
    MENU_BUTTON_SIZE = 30
    BUTTON_EXPANDED_WIDTH = 260
    BUTTON_COLLAPSED_WIDTH = 10

    def __init__(self, data):
        super().__init__()

        self.user_data = data
        self.user_role = data.get('role')
        self.manajemen_widget = None
        self.transaksi_widget = None
        self.sejarah_widget = None
        self.pelanggan_widget = None
        self.kas_widget = None
        self.pengeluaran_widget = None
        self.user_widget = None

        self._setup_ui()
        self._setup_connections()
        self._apply_role_permissions()

    def _setup_ui(self):
        """Inisialisasi user interface"""
        # Layout utama
        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Buat sidebar kiri dan kanan
        self.sidebar_left = self._create_left_sidebar()
        self.sidebar_right = self._create_right_sidebar()
        self.sidebar_right.hide()

        # Stack widget untuk konten utama
        self.main_stack = QStackedWidget()

        self.welcome_widget = WelcomeWindow()
        self.main_stack.addWidget(self.welcome_widget)

        self.error_widget = ErrorWindow()
        self.main_stack.addWidget(self.error_widget)

        # Tambahkan widget ke layout
        main_layout.addWidget(self.sidebar_left)
        main_layout.addWidget(self.sidebar_right)
        main_layout.addWidget(self.main_stack)

        # Frame root
        root_frame = QFrame()
        root_frame.setLayout(main_layout)
        root_layout.addWidget(root_frame)

        self.setLayout(root_layout)
        self.setStyleSheet("background-color: #000000;")

    def _create_left_sidebar(self) -> QWidget:
        """Membuat sidebar kiri dengan icon saja"""
        widget = QWidget()
        widget.setFixedWidth(self.SIDEBAR_LEFT_WIDTH)
        widget.setStyleSheet(self._get_sidebar_style())

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Tombol menu
        self.button_menu_left = self._create_menu_button(asset_path("menu putih.png"))
        layout.addWidget(self.button_menu_left)
        layout.addSpacing(25)

        # Tombol navigasi
        self.button_transaksi_left = self._create_nav_button(
            asset_path("Transaksi putih.png"),
            asset_path("Transaksi hijau.png")
        )
        layout.addWidget(self.button_transaksi_left)

        self.button_sejarah_left = self._create_nav_button(
            asset_path("sejarah putih.png"),
            asset_path("sejarah hijau.png")
        )
        layout.addWidget(self.button_sejarah_left)

        self.button_manajemen_left = self._create_nav_button(
            asset_path("manajemen putih.png"),
            asset_path("manajemen hijau.png")
        )
        layout.addWidget(self.button_manajemen_left)

        self.button_pelanggan_left = self._create_nav_button(
            asset_path("pelanggan putih.png"),
            asset_path("pelanggan hijau.png")
        )
        layout.addWidget(self.button_pelanggan_left)

        self.button_kas_left = self._create_nav_button(
            asset_path("kas putih.png"),
            asset_path("kas hijau.png")
        )
        layout.addWidget(self.button_kas_left)

        self.button_buku_left = self._create_nav_button(
            asset_path("buku putih.png"),
            asset_path("buku hijau.png")
        )
        layout.addWidget(self.button_buku_left)

        self.button_user_left = self._create_nav_button(
            asset_path("perisai_putih.png"),
            asset_path("perisai_hijau.png"),
        )
        layout.addWidget(self.button_user_left)

        layout.addStretch()

        # Tombol logout
        self.button_logout_left = self._create_nav_button(
            asset_path("logout putih.png"),
            asset_path("logout hijau.png")
        )
        layout.addWidget(self.button_logout_left)

        return widget

    def _create_right_sidebar(self) -> QWidget:
        """Membuat sidebar kanan dengan icon dan text"""
        widget = QWidget()
        widget.setFixedWidth(self.SIDEBAR_RIGHT_WIDTH)
        widget.setStyleSheet(self._get_sidebar_style(with_text=True))

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Tombol menu
        self.button_menu_right = self._create_menu_button(asset_path("menu putih.png"))
        layout.addWidget(self.button_menu_right)
        layout.addSpacing(25)

        # Tombol navigasi dengan text
        self.button_transaksi_right = self._create_nav_button_with_text(
            asset_path("Transaksi putih.png"),
            asset_path("Transaksi hijau.png"),
            " Input Transaksi"
        )
        layout.addWidget(self.button_transaksi_right)

        self.button_sejarah_right = self._create_nav_button_with_text(
            asset_path("sejarah putih.png"),
            asset_path("sejarah hijau.png"),
            " Sejarah Transaksi"
        )
        layout.addWidget(self.button_sejarah_right)

        self.button_manajemen_right = self._create_nav_button_with_text(
            asset_path("manajemen putih.png"),
            asset_path("manajemen hijau.png"),
            " Manajemen Produk"
        )
        layout.addWidget(self.button_manajemen_right)

        self.button_pelanggan_right = self._create_nav_button_with_text(
            asset_path("pelanggan putih.png"),
            asset_path("pelanggan hijau.png"),
            " Data Customer"
        )
        layout.addWidget(self.button_pelanggan_right)

        self.button_kas_right = self._create_nav_button_with_text(
            asset_path("kas putih.png"),
            asset_path("kas hijau.png"),
            " Laporan Laba"
        )
        layout.addWidget(self.button_kas_right)

        self.button_buku_right = self._create_nav_button_with_text(
            asset_path("buku putih.png"),
            asset_path("buku hijau.png"),
            " Catatan Beban Toko"
        )
        layout.addWidget(self.button_buku_right)

        self.button_user_right = self._create_nav_button_with_text(
            asset_path("perisai_putih.png"),
            asset_path("perisai_hijau.png"),
            " User Administrator"
        )
        layout.addWidget(self.button_user_right)

        layout.addStretch()

        # Tombol logout
        self.button_logout_right = self._create_nav_button_with_text(
            asset_path("logout putih.png"),
            asset_path("logout hijau.png"),
            " Log Out"
        )
        layout.addWidget(self.button_logout_right)

        return widget

    def _create_menu_button(self, icon_path: str) -> QPushButton:
        """Membuat tombol menu"""
        button = QPushButton()
        button.setFixedSize(self.MENU_BUTTON_SIZE, self.MENU_BUTTON_SIZE)

        icon = QIcon()
        icon.addFile(icon_path, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        button.setIcon(icon)
        button.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))

        return button

    def _create_nav_button(self, icon_normal: str, icon_checked: str) -> QPushButton:
        """Membuat tombol navigasi dengan 2 state icon"""
        button = QPushButton()
        button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)

        self._set_button_icon(button, icon_normal, icon_checked)
        button.setCheckable(True)
        button.setAutoExclusive(True)

        return button

    def _create_nav_button_with_text(
            self,
            icon_normal: str,
            icon_checked: str,
            text: str
    ) -> QPushButton:
        """Membuat tombol navigasi dengan icon dan text"""
        button = QPushButton()
        button.setFixedHeight(self.BUTTON_SIZE)

        self._set_button_icon(button, icon_normal, icon_checked)
        button.setText(text)
        button.setFont(QFont("Arial", 15))
        button.setCheckable(True)
        button.setAutoExclusive(True)

        return button

    def _set_button_icon(
            self,
            button: QPushButton,
            icon_normal: str,
            icon_checked: str
    ) -> None:
        """Set icon untuk button dengan 2 state (normal dan checked)"""
        icon = QIcon()
        icon.addFile(icon_normal, QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        icon.addFile(icon_checked, QSize(), QIcon.Mode.Normal, QIcon.State.On)
        button.setIcon(icon)
        button.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))

    @staticmethod
    def _get_sidebar_style(with_text: bool = False) -> str:
        """Mendapatkan stylesheet untuk sidebar"""
        base_style = """
            QWidget {
                background-color: #000000;
                border-right: 2px solid #ffffff;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                background-color: #000000;
            }
            QPushButton:hover {
                background-color: #141414;
            }
            QPushButton:checked {
                background-color: #454545;
            }
        """

        if with_text:
            base_style += """
                QWidget {
                    padding-left: 4px;
                }
                QPushButton {
                    color: #ffffff;
                    text-align: left;
                }
                QPushButton:checked {
                    color: rgb(0, 255, 0);
                    background-color: #000000;
                    font-weight: bold;
                    border: 2px solid #ffffff;
                }
            """

        return base_style

    def _setup_connections(self):
        """Setup semua signal-slot connections"""
        # Toggle sidebar
        self.button_menu_left.clicked.connect(self._show_right_sidebar)
        self.button_menu_right.clicked.connect(self._show_left_sidebar)

        # Sinkronisasi tombol kiri-kanan
        self._sync_buttons(self.button_transaksi_left, self.button_transaksi_right)
        self._sync_buttons(self.button_sejarah_left, self.button_sejarah_right)
        self._sync_buttons(self.button_manajemen_left, self.button_manajemen_right)
        self._sync_buttons(self.button_pelanggan_left, self.button_pelanggan_right)
        self._sync_buttons(self.button_kas_left, self.button_kas_right)
        self._sync_buttons(self.button_buku_left, self.button_buku_right)
        self._sync_buttons(self.button_user_left, self.button_user_right)

        # Handler navigasi
        self.button_transaksi_left.toggled.connect(self._handle_navigation)
        self.button_sejarah_left.toggled.connect(self._handle_navigation)
        self.button_manajemen_left.toggled.connect(self._handle_navigation)
        self.button_pelanggan_left.toggled.connect(self._handle_navigation)
        self.button_kas_left.toggled.connect(self._handle_navigation)
        self.button_buku_left.toggled.connect(self._handle_navigation)
        self.button_user_left.toggled.connect(self._handle_navigation)

        # Logout
        self.button_logout_left.clicked.connect(self._handle_logout)
        self.button_logout_right.clicked.connect(self._handle_logout)

    @staticmethod
    def _sync_buttons(button_left: QPushButton, button_right: QPushButton) -> None:
        """Sinkronisasi state 2 tombol (kiri-kanan)"""
        button_left.toggled.connect(button_right.setChecked)
        button_right.toggled.connect(button_left.setChecked)

    def _show_right_sidebar(self):
        """Tampilkan sidebar kanan, sembunyikan kiri"""
        self.sidebar_right.show()
        self.sidebar_left.hide()

    def _show_left_sidebar(self):
        """Tampilkan sidebar kiri, sembunyikan kanan"""
        self.sidebar_left.show()
        self.sidebar_right.hide()

    def _apply_role_permissions(self):
        """Terapkan permission berdasarkan role user"""
        if self.user_role != "Super_user":
            self.button_kas_left.hide()
            self.button_kas_right.hide()
            self.button_buku_left.hide()
            self.button_buku_right.hide()
            self.button_user_right.hide()
            self.button_user_left.hide()


    def _handle_navigation(self):
        """Handler ketika tombol navigasi diklik"""
        self._reset_all_button_widths()

        if self.button_manajemen_left.isChecked():
            self.button_manajemen_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.manajemen_widget:
                self.manajemen_widget = ManajemenProduk()
                if self.main_stack.indexOf(self.manajemen_widget) == -1:
                    self.main_stack.addWidget(self.manajemen_widget)
            else:
                self.manajemen_widget.refresh_data()
            self.main_stack.setCurrentWidget(self.manajemen_widget)
        elif self.button_transaksi_left.isChecked():
            self.button_transaksi_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.transaksi_widget:
                self.transaksi_widget = PenjualanWindow(self.user_data)
                if self.main_stack.indexOf(self.transaksi_widget) == -1:
                    self.main_stack.addWidget(self.transaksi_widget)
            self.main_stack.setCurrentWidget(self.transaksi_widget)
        elif self.button_sejarah_left.isChecked():
            self.button_sejarah_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.sejarah_widget:
                self.sejarah_widget = SejarahTransaksiWindow(self.user_data)
                if self.main_stack.indexOf(self.sejarah_widget) == -1:
                    self.main_stack.addWidget(self.sejarah_widget)
            else:
                self.sejarah_widget.refresh_data()
            self.main_stack.setCurrentWidget(self.sejarah_widget)
        elif self.button_pelanggan_left.isChecked():
            self.button_pelanggan_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.pelanggan_widget:
                from src.ui.data_pelanggan import DataPelanggan
                self.pelanggan_widget = DataPelanggan()
                if self.main_stack.indexOf(self.pelanggan_widget) == -1:
                    self.main_stack.addWidget(self.pelanggan_widget)
            else:
                self.pelanggan_widget.refresh_data()
            self.main_stack.setCurrentWidget(self.pelanggan_widget)
        elif self.button_kas_left.isChecked():
            self.button_kas_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.kas_widget:
                from src.ui.laporan_kas_flow import LaporanKasFlow
                self.kas_widget = LaporanKasFlow()
                if self.main_stack.indexOf(self.kas_widget) == -1:
                    self.main_stack.addWidget(self.kas_widget)
            self.main_stack.setCurrentWidget(self.kas_widget)
        elif self.button_buku_left.isChecked():
            self.button_buku_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.pengeluaran_widget:
                from src.ui.pengeluaran_toko import PengeluaranTokoWindow
                self.pengeluaran_widget = PengeluaranTokoWindow()
                if self.main_stack.indexOf(self.pengeluaran_widget) == -1:
                    self.main_stack.addWidget(self.pengeluaran_widget)
            self.main_stack.setCurrentWidget(self.pengeluaran_widget)
        elif self.button_user_left.isChecked():
            self.button_user_right.setMinimumWidth(self.BUTTON_EXPANDED_WIDTH)
            if not self.user_widget:
                from src.ui.user_administrator import UserAdministrator
                self.user_widget = UserAdministrator()
                if self.main_stack.indexOf(self.user_widget) == -1:
                    self.main_stack.addWidget(self.user_widget)
            else:
                self.user_widget.refresh_data()
            self.main_stack.setCurrentWidget(self.user_widget)

    def _reset_all_button_widths(self):
        """Reset semua lebar tombol sidebar kanan ke ukuran default"""
        self.button_transaksi_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)
        self.button_sejarah_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)
        self.button_manajemen_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)
        self.button_pelanggan_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)
        self.button_kas_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)
        self.button_buku_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)
        self.button_user_right.setMinimumWidth(self.BUTTON_COLLAPSED_WIDTH)

    def _handle_logout(self):
        """Handler logout: hapus session dan kembali ke login"""
        database_manager = DatabaseManager()
        database_manager.delete_session()

        parent_window = self.window()

        from main import MainWindow
        main_window = MainWindow()
        main_window.show()

        parent_window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, True)
        parent_window.close()
