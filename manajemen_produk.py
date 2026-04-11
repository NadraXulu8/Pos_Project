import math
import csv
from datetime import datetime, date
from zoneinfo import ZoneInfo

from PySide6.QtGui import QFont, Qt, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QComboBox, QStackedWidget, QPushButton, QFileDialog
)

from barang_baru import TambahBarangBaru
from database import DatabaseManager
from edit_produk import EditProduk
from hapus_produk import HapusProdukDialog
from message import CustomMessageBox
from ui_base import BaseTableWidget, BaseDataPage


class ManajemenProduk(BaseDataPage):
    """Widget utama untuk manajemen produk"""
    HEADER_TITLE = "MANAJEMEN PRODUK"
    SEARCH_PLACEHOLDER = "Cari Produk atau SKU ..."
    TIMEZONE = "Asia/Jakarta"

    # Konstanta
    SELECTOR_HEIGHT = 35
    NAV_BUTTON_SIZE = 35

    def __init__(self):
        super().__init__()

        self._setup_ui()
        self._setup_connections()

        shortcut = QShortcut(QKeySequence("Return"), self)
        shortcut.activated.connect(self.handle_shortcut)

    def _add_custom_widgets(self, layout):
        # Tombol aksi utama
        action_buttons_widget = self._create_action_buttons()
        layout.addWidget(action_buttons_widget)

        # Tombol aksi sekunder
        secondary_buttons_widget = self._create_secondary_buttons()
        layout.addWidget(secondary_buttons_widget)

        layout.addSpacing(20)

    def _create_action_buttons(self) -> QWidget:
        """Membuat widget dengan tombol aksi utama"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addStretch()

        self.button_tambah = self._create_action_button("Tambah Produk", "#00ff00")
        self.button_hapus = self._create_action_button("Hapus Produk", "#ff0000")
        self.button_return = self._create_action_button("Return Produk", "#00aaff")

        layout.addWidget(self.button_tambah)
        layout.addWidget(self.button_hapus)
        layout.addWidget(self.button_return)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_secondary_buttons(self) -> QWidget:
        """Membuat widget dengan tombol aksi sekunder"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addStretch()

        self.button_edit = self._create_action_button("Edit Produk", "#ff8000")
        self.button_baru = self._create_action_button("Produk Baru", "#00ff00")

        layout.addWidget(self.button_edit)
        layout.addWidget(self.button_baru)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_data_widget(self) -> QWidget:
        """Membuat widget data produk dengan selector dan tabel"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Selector produk
        selector_widget = self._create_product_selector()
        layout.addWidget(selector_widget)

        # Stack widget untuk tabel
        self.stack = QStackedWidget()
        self.table_satuan = ProdukSatuanTable()
        self.stack.addWidget(self.table_satuan)
        self.table_paket = ProdukPaketTable()
        self.stack.addWidget(self.table_paket)
        layout.addWidget(self.stack)

        # Tombol navigasi bawah
        navigation_widget = self._create_bottom_navigation()
        layout.addWidget(navigation_widget)

        widget.setLayout(layout)
        return widget

    def _create_product_selector(self) -> QWidget:
        """Membuat widget selector tipe produk"""
        root_widget = QWidget()
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        content_widget = QWidget()
        content_widget.setFixedSize(self.CONTENT_WIDGET_WIDTH, self.SELECTOR_HEIGHT)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Label
        label = QLabel("Data Produk : ")
        label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        label.setStyleSheet("color: #ffffff;")
        content_layout.addWidget(label)

        # ComboBox selector
        self.product_selector = QComboBox()
        self.product_selector.addItems(["Satuan", "Paket"])
        self.product_selector.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.product_selector.setFixedSize(100, self.SELECTOR_HEIGHT)
        self.product_selector.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.product_selector.setStyleSheet("""
            QComboBox{
                background-color: transparent;
                border: none;
                color: #ffffff;
                padding-left: 5px;
            }
            QComboBox:hover{
                color: #00aaff;
            }
            QComboBox QAbstractItemView{
                color: #ffffff;
            }
        """)
        content_layout.addWidget(self.product_selector)

        content_layout.addStretch()
        content_widget.setLayout(content_layout)
        root_layout.addWidget(content_widget)

        root_widget.setLayout(root_layout)
        return root_widget


    def _setup_connections(self):
        """Setup signal-slot connections"""
        self.product_selector.currentIndexChanged.connect(self._switch_product_view)
        self.button_baru.clicked.connect(self._show_tambah_barang_dialog)
        self.button_edit.clicked.connect(self._show_edit_dialog)
        self.button_hapus.clicked.connect(self._show_hapus_dialog)

    def on_reset_click(self):
        self.table_satuan.reset_width()
        self.table_paket.reset_width()

    def _add_bottom_left_buttons(self, layout):
        self.button_download = QPushButton("Download Data")
        self.button_download.setFixedSize(160, self.BUTTON_HEIGHT)
        self.button_download.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.button_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button_download.setStyleSheet("""
            QPushButton{
                background-color: #00aaff;
                color: white;
                border: 2px solid #00aaff;
                border-radius: 10px;
            }
            QPushButton:hover{
                background-color: #0055ff;
                border: 2px solid #0055ff;
            }
        """)
        self.button_download.clicked.connect(self.download_data_csv)
        layout.addSpacing(10)
        layout.addWidget(self.button_download)

    def download_data_csv(self):
        database = DatabaseManager()
        jumlah_satuan = database.get_rows_produk(0)
        jumlah_paket = database.get_rows_produk(1)

        data_satuan = database.get_produk_satuan(jumlah_satuan, 0) if jumlah_satuan > 0 else []
        data_paket = database.get_produk_paket(jumlah_paket, 0) if jumlah_paket > 0 else []

        headers = [
            "nama", "sku", "jenis", "harga_beli",
            "harga_jual", "stok", "konversi", "nama_barang_satuan"
        ]
        data_export = []

        for item in data_satuan:
            data_export.append({
                "nama": item.get("nama_barang", ""),
                "sku": item.get("sku", ""),
                "jenis": "satuan",
                "harga_beli": item.get("harga_beli", "") or "",
                "harga_jual": item.get("harga_jual", "") or "",
                "stok": item.get("stock", "") or "",
                "konversi": "",
                "nama_barang_satuan": "",
            })

        for item in data_paket:
            data_export.append({
                "nama": item.get("nama_barang", ""),
                "sku": item.get("sku", ""),
                "jenis": "paket",
                "harga_beli": "",
                "harga_jual": item.get("harga_jual", "") or "",
                "stok": "",
                "konversi": item.get("jumlah", "") or "",
                "nama_barang_satuan": item.get("nama", ""),
            })

        default_name = f"produk_{datetime.now(ZoneInfo(self.TIMEZONE)).strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Simpan Data Produk",
            default_name,
            "CSV Files (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            with open(path, mode="w", newline="", encoding="utf-8-sig") as file:
                writer = csv.DictWriter(file, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data_export)
            CustomMessageBox.information(
                self,
                "Berhasil",
                f"Data berhasil disimpan ke:\n{path}\n\nJumlah data: {len(data_export)}"
            )
        except Exception as error:
            CustomMessageBox.critical(
                self,
                "Gagal",
                f"Gagal menyimpan data ke file CSV.\n"
                f"Pastikan lokasi penyimpanan memiliki izin tulis.\n\nDetail: {error}"
            )

    def _switch_product_view(self, index: int):
        """Switch tampilan tabel berdasarkan pilihan selector"""
        self.stack.setCurrentIndex(index)
        self.table_data()

    def _show_tambah_barang_dialog(self):
        """Menampilkan dialog tambah barang"""
        dialog = TambahBarangBaru(self)
        result = dialog.exec()

        if result == TambahBarangBaru.DialogCode.Accepted:
            jenis, data = dialog.get_data()

            if jenis == "satuan":
                barang_baru = DatabaseManager()
                barang_baru.insert_barang_baru_satuan(
                    sku= data["sku"],
                    nama= data["nama_barang"],
                    harga_jual= data["harga_jual"],
                    harga_beli= data["harga_beli"],
                    stok= data["stok"],
                    tanggal= datetime.now(ZoneInfo("Asia/Jakarta"))
                )
                self.table_data()
            else:
                barang_baru = DatabaseManager()
                barang_baru.insert_barang_baru_paket(
                    nama= data["nama_paket"],
                    harga_jual= data["harga_jual"],
                    nama_barang= data["nama_barang"],
                    sku= data["sku"],
                    coversion= data["per_satuan"],
                )
                self.table_data()

    def _show_edit_dialog(self):
        dialog = EditProduk(self)
        result = dialog.exec()
        if result == EditProduk.DialogCode.Accepted:
            self.table_data()

    def _show_hapus_dialog(self):
        dialog = HapusProdukDialog(self)
        result = dialog.exec()
        if result == HapusProdukDialog.DialogCode.Accepted:
            self.table_data()

    def table_data(self, offset=0):
        current = bool(self.search_input.property("active"))
        text = self.search_input.text().strip()
        database = DatabaseManager()
        produk = self.product_selector.currentIndex()
        if current == False or (text == "" and current == True):
            if current:
                self.search_input.setProperty("active", not current)
                self.search_input.style().unpolish(self.search_input)
                self.search_input.style().polish(self.search_input)

            if produk == 0:
                data = database.get_produk_satuan(5, offset)
                self.table_satuan.set_data(data)
            else:
                data = database.get_produk_paket(5, offset)
                self.table_paket.set_data(data)
        elif text != "" and current == True:
            if produk == 0:
                data = database.get_search_produk(produk, text, 5, offset)
                self.table_satuan.set_data(data)
            else:
                data = database.get_search_produk(produk, text, 5, offset)
                self.table_paket.set_data(data)

        if offset == 0:
            self.page_input.setText("1")
        else:
            text = int(offset / 5) + 1
            self.page_input.setText(str(text))


    def custom_page(self):
        text = self.search_input.text().strip()
        current = bool(self.search_input.property("active"))
        index = self.product_selector.currentIndex()
        database = DatabaseManager()

        if current == False or (text == "" and current == True):
            self.pages = math.ceil(database.get_rows_produk(index)/5)
        else:
            self.pages = math.ceil(database.get_search_row(index,text)/5)

        page = int(self.page_input.text().strip())
        if page >= self.pages:
            self.page_input.setText(str(self.pages))
            self.table_data((self.pages - 1) * 5)
        elif page <= 0:
            self.table_data()
        else:
            self.table_data((page - 1) * 5)

    def next_page(self):
        page = int(self.page_input.text().strip())
        database = DatabaseManager()
        text = self.search_input.text().strip()
        current = bool(self.search_input.property("active"))
        index = self.product_selector.currentIndex()

        if current == False or (text == "" and current == True):
            self.pages = math.ceil(database.get_rows_produk(index) / 5)
        else:
            self.pages = math.ceil(database.get_search_row(index,text)/5)

        if page < self.pages:
            page = page + 1
            self.table_data((page - 1) * 5)
        else:
            pass

    def prev_page(self):
        page = int(self.page_input.text().strip())
        if page > 1:
            page -= 1
            self.table_data((page - 1) * 5)
        else:
            pass
    
    def refresh_data(self):
        self.table_data()
        self.search_input.clear()
        self.product_selector.setCurrentIndex(0)
        self.page_input.setText("1")


_ID_MONTHS = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
    5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
    9: "September", 10: "Oktober", 11: "November", 12: "Desember"
}

def format_tanggal(value, in_fmt="%Y-%m-%d"):
    """
    Terima string ISO (contoh: '2025-11-07 19:32:27.262473+07:00'),
    atau 'YYYY-MM-DD', atau datetime/date.
    Kembalikan '7 November 2025' (tanpa ubah zona waktu).
    """
    if not value:
        return ""
    try:
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.strptime(value, in_fmt)
        elif isinstance(value, datetime):
            dt = value
        elif isinstance(value, date):
            dt = datetime(value.year, value.month, value.day)
        else:
            return str(value)

        d = dt.date()
        return f"{d.day} {_ID_MONTHS[d.month]} {d.year}"
    except (ValueError, TypeError):
        return str(value)



class ProdukSatuanTable(BaseTableWidget):
    """Widget tabel untuk produk satuan"""

    TABLE_NAME = "produksatuan"
    TABLE_WIDTH = 800
    TABLE_ROW_COUNT = 5
    COLUMN_WIDTHS = [100, 0, 80, 150, 170]
    HEADERS = ["SKU", "NAMA BARANG", "STOCK", "HARGA JUAL", "TGL MASUK"]
    FIELDS = ["sku", "nama_barang", "stock", "harga_jual", "tgl_masuk"]
    FORMATTERS = {
        "tgl_masuk": format_tanggal,
    }
    LEFT_ALIGN_FIELDS = ["nama_barang"]

class ProdukPaketTable(BaseTableWidget):
    """Widget tabel untuk produk paket"""

    TABLE_NAME = "produkpaket"
    TABLE_WIDTH = 800
    TABLE_ROW_COUNT = 5
    COLUMN_WIDTHS = [100, 300, 200, 200]
    HEADERS = ["SKU", "NAMA BARANG", "HARGA JUAL", "KETERANGAN"]
    FIELDS = ["sku", "nama_barang", "harga_jual", "keterangan"]
    LEFT_ALIGN_FIELDS = ["nama_barang"]
