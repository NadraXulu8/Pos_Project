from PySide6.QtCore import QSize, QStringListModel, QTimer
from PySide6.QtGui import QFont, Qt, QIcon, QShortcut, QKeySequence
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QAbstractItemView, QHeaderView, QGridLayout,
    QTextEdit, QCompleter, QTableWidgetItem, QSpinBox, QAbstractSpinBox, QScrollArea, QCheckBox, QDialog
)

from config import asset_path, asset_uri

from src.database.database import DatabaseManager
from src.ui.discount import DiscountPopup
from src.ui.nota_printer import NotaPrinter
from src.ui.printer_selection import PrinterSelectionDialog
from src.utils.fungsi import MacroSpinBox


class PenjualanWindow(QWidget):
    SEARCH_LIMIT = 12
    MAX_QTY = 9999

    def __init__(self, user_data=None, db_manager=None):
        super().__init__()
        self.user_data = user_data or {}
        self.db_manager = db_manager or DatabaseManager()
        self.diskon_nominal = 0
        self.diskon_nominal_input = 0
        self.diskon_persen = 0
        self.discount_mode = None
        self.is_rounding_active = False
        self.pembulatan_nominal = 0
        self.cart_items = []
        self.search_suggestions = []
        self.search_lookup = {}
        self._pending_search_add_signature = None
        self.discount_popup = None

        self.setup_ui()
        self._setup_search_completer()
        self._setup_customer_completer()
        self._setup_payment_actions()
        self._refresh_search_suggestions()
        self._refresh_customer_suggestions()
        self._update_cart_summary()
        self._rebuild_tab_order()

    def setup_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        container = QFrame()
        container.setStyleSheet("background-color: #050505;")
        root_layout.addWidget(container)

        content_layout = QHBoxLayout(container)
        content_layout.setContentsMargins(24, 24, 24, 24)
        content_layout.setSpacing(20)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        content_layout.addWidget(left_panel, 7)
        content_layout.addWidget(right_panel, 3)

        self.setStyleSheet(self._get_stylesheet())

    def _create_left_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        header = self._create_header_card()
        search_card = self._create_search_card()
        cart_card = self._create_cart_card()

        layout.addWidget(header)
        layout.addWidget(search_card)
        layout.addWidget(cart_card, 1)
        return widget

    def _create_right_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        payment_card = self._create_payment_summary_card()
        input_card = self._create_payment_input_card()
        quick_action_card = self._create_quick_actions_card()

        layout.addWidget(payment_card)
        layout.addWidget(input_card)
        layout.addWidget(quick_action_card)
        layout.addStretch()

        return widget

    def _create_header_card(self) -> QWidget:
        card = self._build_card()
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        icon = QSvgWidget(asset_path("kasir_100.svg"))
        icon.setFixedSize(QSize(50, 50))

        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_layout.setSpacing(4)

        title = QLabel("TRANSAKSI PENJUALAN")
        title.setFont(QFont("Times New Roman", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #ffffff;")

        badge_layout = QHBoxLayout()
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(4)

        username = str(self.user_data.get("username") or "Guest").upper()
        badge_nama = QLabel(f"NAMA KASIR : {username}")
        badge_nama.setObjectName("smallBadge")

        role = self._format_role(self.user_data.get("role"))
        badge_role = QLabel(role)
        badge_role.setObjectName("smallBadge")

        badge_layout.addWidget(badge_nama)
        badge_layout.addWidget(badge_role)
        badge_layout.addStretch()

        header_layout.addWidget(title)
        header_layout.addLayout(badge_layout)

        layout.addWidget(icon)
        layout.addLayout(header_layout)
        return card

    def _create_search_card(self) -> QWidget:
        card = self._build_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 10, 24, 10)
        layout.setSpacing(16)

        search_row = QHBoxLayout()
        search_row.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ketik nama produk / SKU lalu tekan Enter...")
        self.search_input.textChanged.connect(self._handle_search_text_changed)
        self.search_input.returnPressed.connect(self._add_product_from_search)
        search_row.addWidget(self.search_input, 1)

        self.product_filter = QComboBox()
        self.product_filter.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.product_filter.addItems(["Semua Produk", "Produk Satuan", "Produk Paket"])
        self.product_filter.setFixedWidth(170)
        self.product_filter.currentIndexChanged.connect(self._handle_search_filter_changed)
        search_row.addWidget(self.product_filter)

        self.button_add_product = QPushButton("Tambah ke Keranjang")
        self.button_add_product.clicked.connect(self._add_product_from_search)
        self.button_add_product.setObjectName("primaryButton")
        self.button_add_product.setStyleSheet("""
            QPushButton {
                background-color: #00c853;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #ffffff;
                color: #00c853;
            }
        """)
        search_row.addWidget(self.button_add_product)

        self.search_hint_label = QLabel("Cari produk berdasarkan SKU atau nama produk.")
        self.search_hint_label.setStyleSheet("color: #98a3af; font-size: 12px;")

        layout.addLayout(search_row)
        layout.addWidget(self.search_hint_label)
        return card

    def _create_cart_card(self) -> QWidget:
        card = self._build_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        self.cart_table = QTableWidget(0, 7)
        self.cart_table.setHorizontalHeaderLabels([
            "SKU", "Produk", "Tipe", "Harga", "Qty", "Subtotal", "Aksi"
        ])
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.cart_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.verticalHeader().setDefaultSectionSize(50)
        self.cart_table.setStyleSheet("""
            QTableWidget::item { padding: 0px; }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(100, 100, 100, 150);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(150, 150, 150, 255);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cart_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.cart_table.setColumnWidth(4, 100)
        self.cart_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cart_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.cart_table.setMinimumHeight(100)

        table_scroll = QScrollArea()
        table_scroll.setWidgetResizable(True)
        table_scroll.setFrameShape(QFrame.Shape.NoFrame)
        table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        table_wrapper = QWidget()
        table_wrapper_layout = QVBoxLayout(table_wrapper)
        table_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        table_wrapper_layout.addWidget(self.cart_table)
        table_scroll.setWidget(table_wrapper)

        layout.addWidget(table_scroll, 1)

        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.cart_info_label = QLabel("Keranjang masih kosong.")
        self.cart_info_label.setStyleSheet("color: #98a3af; font-size: 12px;")
        footer.addWidget(self.cart_info_label)
        footer.addStretch()

        clear_button = QPushButton("Kosongkan Keranjang")
        clear_button.setObjectName("ghostButton")
        clear_button.setStyleSheet("""
            QPushButton { 
                background-color: #17202a;
                color: #dbe8f4;
                border: 2px solid #2a3745;
            }
            QPushButton:hover { 
                background-color: #dbe8f4;
                color: #17202a;
            }
        """)
        clear_button.clicked.connect(self._clear_cart)
        footer.addWidget(clear_button)

        layout.addLayout(footer)
        return card

    def _create_payment_summary_card(self) -> QWidget:
        card = self._build_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        self.summary_subtotal = self._create_summary_row(layout, "Subtotal", "Rp 0")
        self.summary_discount = self._create_summary_row(layout, "Diskon", "Rp 0")
        self.summary_rounding = self._create_summary_row(layout, "Pembulatan", "Rp 0")

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #2e3945;")
        layout.addWidget(divider)

        total_label = QLabel("Total Tagihan")
        total_label.setStyleSheet("color: #b8c4d0; font-size: 13px; font-weight: 600;")
        layout.addWidget(total_label)

        self.summary_total = QLabel("Rp 0")
        self.summary_total.setStyleSheet(
            "color: #00ff85; font-size: 28px; font-weight: 800;"
        )
        layout.addWidget(self.summary_total)

        return card

    def _create_payment_input_card(self) -> QWidget:
        card = self._build_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(5)

        metode_label = QLabel("Metode Bayar")
        metode_label.setObjectName("formLabel")
        self.payment_method = QComboBox()
        self.payment_method.addItems(["Tunai", "QRIS", "Transfer"])
        self.payment_method.setFixedHeight(33)
        self.payment_method.setStyleSheet("""
            QComboBox {
                padding: 0px 12px;
            }
        """
        )
        form_layout.addWidget(metode_label, 0, 0)
        form_layout.addWidget(self.payment_method, 0, 1)

        bayar_label = QLabel("Nominal Bayar")
        bayar_label.setObjectName("formLabel")

        payment_layout = QHBoxLayout()
        payment_layout.setContentsMargins(0, 0, 0, 0)
        rp = QLabel("Rp. ")
        payment_layout.addWidget(rp)
        self.payment_input = QLineEdit()
        self.payment_input.setFixedHeight(33)
        self.payment_input.setStyleSheet("""
            padding: 0px 12px;
        """
        )
        self.payment_input.textChanged.connect(self._format_payment_input)
        payment_layout.addWidget(self.payment_input)

        form_layout.addWidget(bayar_label, 1, 0)
        form_layout.addLayout(payment_layout, 1, 1)

        pelanggan_label = QLabel("Nama Customer")
        pelanggan_label.setObjectName("formLabel")
        self.customer_input = QLineEdit()
        self.customer_input.setPlaceholderText("Opsional, misal: Pelanggan Umum")
        self.customer_input.setFixedHeight(33)
        self.customer_input.setStyleSheet("""
            QLineEdit {
                padding: 0px 12px;
            }
        """
        )
        self.customer_input.textChanged.connect(self._handle_customer_text_changed)
        form_layout.addWidget(pelanggan_label, 2, 0)
        form_layout.addWidget(self.customer_input, 2, 1)

        layout.addLayout(form_layout)

        notes_label = QLabel("Catatan Kasir")
        notes_label.setObjectName("formLabel")
        layout.addWidget(notes_label)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("tulis informasi disini")
        self.notes_input.setFixedHeight(50)
        layout.addWidget(self.notes_input)

        self.change_label = QLabel("Kembalian: Rp 0")
        self.change_label.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")
        layout.addWidget(self.change_label)

        self.print_checkbox = QCheckBox(" Cetak Nota Transaksi")
        self.print_checkbox.setChecked(False)
        self.print_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.print_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: #b8c4d0;
                font-size: 13px;
                margin-top: 10px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #263241;
                background-color: #111827;
            }}
            QCheckBox::indicator:hover {{
                border: 2px solid #00c2ff;
            }}
            QCheckBox::indicator:checked {{
                background-color: #00ff85;
                border: 2px solid #00ff85;
                image: url({asset_uri("check.svg")});
            }}
        """)
        layout.addWidget(self.print_checkbox)

        return card

    def _create_quick_actions_card(self) -> QWidget:
        card = self._build_card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        self.button_discount = QPushButton("Diskon")
        self.button_discount.setObjectName("warningButton")
        self.button_discount.setStyleSheet("""
            QPushButton#warningButton {
                background-color: #ffb020;
                color: #1f1300;
            }
            QPushButton#warningButton:hover {
                background-color: #ffd27a;
            }
        """)

        self.button_rounding = QPushButton("Pembulatan")
        self.button_rounding.setObjectName("secondaryButton")
        self.button_rounding.setStyleSheet("""
            QPushButton#secondaryButton {
                background-color: #00c2ff;
                color: #02131a;
            }
            QPushButton#secondaryButton:hover {
                background-color: #86e8ff;
            }
        """)

        self.button_cancel = QPushButton("Cancel")
        self.button_cancel.setObjectName("ghostDangerButton")
        self.button_cancel.setStyleSheet("""
            QPushButton#ghostDangerButton:hover {
                background-color: #243342;
            }
            QPushButton#ghostDangerButton {
                background-color: #241316;
                color: #ff8f98;
                border: 1px solid #59242a;
            }
        """)
        self.button_cancel.clicked.connect(self._clear_cart)

        self.button_pay = QPushButton("Bayar")
        self.button_pay.setObjectName("successButton")
        self.button_pay.setStyleSheet("""
            QPushButton#successButton:hover {
                background-color: #7dffb1;
            }
            QPushButton#successButton {
                background-color: #00ff85;
                color: #02140a;
            }
        """)

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(10)
        button_grid.setVerticalSpacing(10)
        button_grid.addWidget(self.button_discount, 0, 0)
        button_grid.addWidget(self.button_rounding, 0, 1)
        button_grid.addWidget(self.button_cancel, 1, 0)
        button_grid.addWidget(self.button_pay, 1, 1)

        layout.addLayout(button_grid)
        return card

    def _setup_payment_actions(self):
        self.button_discount.clicked.connect(self._show_discount_popup)
        self.button_rounding.clicked.connect(self._apply_rounding)
        self.button_pay.clicked.connect(self._process_payment)

        shortcut_pay = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut_pay.activated.connect(self._process_payment)

        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_search.activated.connect(self._focus_search)

        shortcut_nominal = QShortcut(QKeySequence("Ctrl+S"), self)
        shortcut_nominal.activated.connect(self._fokus_nominal)

        self.payment_method.currentIndexChanged.connect(self._handle_payment_method_changed)

    def _fokus_nominal(self):
        self.payment_input.setFocus()

    def _handle_payment_method_changed(self, index: int):
        if index in (1, 2):
            total_tagihan = self._calculate_final_total()
            self.payment_input.setText(str(total_tagihan))
        elif index == 0:
            self.payment_input.setText("")

    def _setup_search_completer(self):
        self.search_model = QStringListModel(self)
        self.search_completer = QCompleter(self.search_model, self)
        self.search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search_completer.activated.connect(self._handle_completer_activated)
        self.search_input.setCompleter(self.search_completer)

    def _setup_customer_completer(self):
        self.customer_model = QStringListModel(self)
        self.customer_completer = QCompleter(self.customer_model, self)
        self.customer_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.customer_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.customer_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def _handle_search_text_changed(self, text: str):
        if text in self.search_lookup:
            return

        if not text:
            self.search_model.setStringList([])
            self.search_lookup.clear()
            self.search_hint_label.setText("Cari produk berdasarkan SKU atau nama produk.")

            if (p := self.search_completer.popup()):
                p.hide()
            return

        self._refresh_search_suggestions(text)
        text = text.strip()
        if text:
            jumlah = len(self.search_suggestions)
            self.search_hint_label.setText(f"{jumlah} saran produk ditemukan.")
        else:
            self.search_hint_label.setText("Cari produk berdasarkan SKU atau nama produk.")

    def _handle_search_filter_changed(self):
        self._refresh_search_suggestions(self.search_input.text())

    def _handle_completer_activated(self, selected_text: str):
        product = self.search_lookup.get(selected_text)
        if not product:
            return

        self._add_product_to_cart_once_per_event_cycle(product)
        self.search_hint_label.setText(f"Produk {product['nama_barang']} ditambahkan ke keranjang.")
        QTimer.singleShot(0, self.search_input.clear)

    def _refresh_search_suggestions(self, keyword: str = ""):
        keyword = keyword.strip()
        self.search_suggestions = self.db_manager.search_products(
            keyword=keyword,
            limit=self.SEARCH_LIMIT,
            filter_index=self.product_filter.currentIndex(),
        )
        self.search_lookup = {
            self._build_suggestion_text(item): item
            for item in self.search_suggestions
        }
        self.search_model.setStringList(list(self.search_lookup.keys()))

        if keyword and self.search_suggestions:
            self.search_completer.complete()

    def _refresh_customer_suggestions(self):
        customers = self.db_manager.get_all_customer_names()
        self.customer_model.setStringList(customers)
        self.customer_input.setCompleter(self.customer_completer)

    def _handle_customer_text_changed(self, text: str):
        if text.strip():
            self.customer_completer.complete()

    def _find_exact_product(self, keyword: str):
        keyword = keyword.strip().casefold()
        if not keyword:
            return None

        for item in self.db_manager.search_products(
            keyword=keyword,
            limit=self.SEARCH_LIMIT,
            filter_index=self.product_filter.currentIndex(),
        ):
            sku = str(item["sku"]).strip().casefold()
            nama = str(item["nama_barang"]).strip().casefold()
            if keyword in {sku, nama}:
                return item

        for item in self.search_suggestions:
            sku = str(item["sku"]).strip().casefold()
            nama = str(item["nama_barang"]).strip().casefold()
            if keyword in {sku, nama}:
                return item

        return self.search_suggestions[0] if self.search_suggestions else None

    def _get_product_from_completer_selection(self):
        popup = self.search_completer.popup()
        if popup is None or not popup.isVisible():
            return None

        index = popup.currentIndex()
        if index.isValid():
            selected_text = index.data(Qt.ItemDataRole.DisplayRole)
        else:
            selected_text = self.search_completer.currentCompletion()
        if not selected_text:
            return None

        return self.search_lookup.get(str(selected_text))

    def _add_product_from_search(self):
        product = self._get_product_from_completer_selection()
        if not product:
            keyword = self.search_input.text().strip().lower()
            if not keyword:
                self.search_hint_label.setText("Masukkan SKU atau nama produk terlebih dahulu")
                return
            product = self._find_exact_product(keyword)
        
        if not product:
            self.search_hint_label.setText("Produk tidak ditemukan untuk kata kunci tersebut.")
            return

        if product["tipe"] == "satuan" and int(product.get("stok") or 0) <= 0:
            self.search_hint_label.setText(f"Stok produk {product['nama_barang']} sedang habis.")
            return

        self._add_product_to_cart_once_per_event_cycle(product)
        QTimer.singleShot(0, self.search_input.clear)
        self._refresh_search_suggestions()
        self.search_hint_label.setText(f"Produk {product['nama_barang']} ditambahkan ke keranjang.")

    def _clear_pending_search_add_signature(self):
        self._pending_search_add_signature = None

    def _get_product_signature(self, product: dict):
        return (
            str(product.get("id", "")),
            str(product.get("sku", "")),
            str(product.get("tipe", "")).casefold(),
        )

    def _add_product_to_cart_once_per_event_cycle(self, product: dict):
        signature = self._get_product_signature(product)
        if signature == self._pending_search_add_signature:
            return

        self._pending_search_add_signature = signature
        QTimer.singleShot(0, self._clear_pending_search_add_signature)
        self._add_product_to_cart(product)

    def _add_product_to_cart(self, product: dict):
        existing_index = self._get_cart_index(product["sku"], product["tipe"])
        if existing_index is not None:
            item = self.cart_items[existing_index]
            next_qty = item["qty"] + 1
            max_qty = item.get("max_qty", self.MAX_QTY)
            if next_qty > max_qty:
                self.search_hint_label.setText(
                    f"Qty maksimum untuk {item['nama_barang']} adalah {max_qty}."
                )
                return

            item["qty"] = next_qty
            qty_widget = self.cart_table.cellWidget(existing_index, 4)
            if isinstance(qty_widget, QSpinBox):
                qty_widget.blockSignals(True)
                qty_widget.setValue(next_qty)
                qty_widget.blockSignals(False)
            self._refresh_row(existing_index)
            self._update_cart_summary()
            return

        max_qty = int(product.get("stok") or self.MAX_QTY)
        cart_item = {
            "product_id": product["id"],
            "sku": product["sku"],
            "nama_barang": product["nama_barang"],
            "tipe": str(product["tipe"]).title(),
            "harga_jual": int(product["harga_jual"] or 0),
            "qty": 1,
            "max_qty": max(1, max_qty),
        }
        self.cart_items.append(cart_item)
        self._append_cart_row(cart_item)
        self._update_cart_summary()

    def _get_cart_index(self, sku: str, tipe: str):
        tipe_title = str(tipe).title()
        for index, item in enumerate(self.cart_items):
            if item["sku"] == sku and item["tipe"] == tipe_title:
                return index
        return None

    def _append_cart_row(self, item: dict):
        row = self.cart_table.rowCount()
        self.cart_table.insertRow(row)
        self._set_table_label(row, 0, item["sku"])
        self._set_table_label(row, 1, item["nama_barang"])
        self._set_table_label(row, 2, item["tipe"])
        self._set_table_label(row, 3, self._format_currency(item["harga_jual"]))
        self.cart_table.setCellWidget(row, 4, self._create_qty_editor(row, item))
        self._set_table_label(row, 5, self._format_currency(item["harga_jual"] * item["qty"]))
        self.cart_table.setCellWidget(row, 6, self._create_delete_button(row, item["nama_barang"]))
        self._rebuild_tab_order()

    def _refresh_row(self, row: int):
        if row >= len(self.cart_items):
            return
        item = self.cart_items[row]
        subtotal = item["harga_jual"] * item["qty"]
        self._set_table_label(row, 5, self._format_currency(subtotal))

    def _create_qty_editor(self, row: int, item: dict) -> QSpinBox:
        spinbox = MacroSpinBox()
        spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.UpDownArrows)
        spinbox.setRange(1, item.get("max_qty", self.MAX_QTY))
        spinbox.setValue(item["qty"])
        spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spinbox.setStyleSheet("QSpinBox { padding: 0px 6px; }")
        spinbox.valueChanged.connect(lambda value, current_row=row: self._update_cart_qty(current_row, value))
        return spinbox

    def _create_delete_button(self, row: int, product_name: str) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        button = QPushButton()
        button.setToolTip(f"Hapus {product_name}")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(34, 34)
        button.setIcon(QIcon(asset_path("tong_sampah_putih.svg")))
        button.setIconSize(QSize(18, 18))
        button.setObjectName("deleteCartButton")
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(lambda _=False, current_row=row: self._remove_cart_item(current_row))

        layout.addWidget(button)
        return wrapper

    def _update_cart_qty(self, row: int, value: int):
        if row >= len(self.cart_items):
            return

        item = self.cart_items[row]
        max_qty = item.get("max_qty", self.MAX_QTY)
        qty = max(1, min(value, max_qty))
        item["qty"] = qty
        self._refresh_row(row)
        self._update_cart_summary()
        self.search_hint_label.setText(f"Qty {item['nama_barang']} diperbarui menjadi {qty}.")

    def _remove_cart_item(self, row: int):
        if row >= len(self.cart_items):
            return

        nama_barang = self.cart_items[row]["nama_barang"]
        self.cart_items.pop(row)
        self.cart_table.removeRow(row)
        self._rebuild_cart_actions()
        self._rebuild_tab_order()
        self._update_cart_summary()
        self.search_hint_label.setText(f"Produk {nama_barang} dihapus dari keranjang.")

    def _rebuild_cart_actions(self):
        for row, item in enumerate(self.cart_items):
            qty_widget = self.cart_table.cellWidget(row, 4)
            if isinstance(qty_widget, QSpinBox):
                try:
                    qty_widget.valueChanged.disconnect()
                except (RuntimeError, TypeError):
                    pass
                qty_widget.valueChanged.connect(
                    lambda value, current_row=row: self._update_cart_qty(current_row, value)
                )

            action_widget = self.cart_table.cellWidget(row, 6)
            if action_widget is not None:
                button = action_widget.findChild(QPushButton)
                if button is not None:
                    try:
                        button.clicked.disconnect()
                    except RuntimeError:
                        pass
                    except TypeError:
                        pass
                    button.clicked.connect(
                        lambda _=False, current_row=row: self._remove_cart_item(current_row)
                    )

    def _rebuild_tab_order(self):
        """
        Rebuild TAB order setiap kali baris cart berubah.

        Aturan fokus:
        - Hanya QSpinBox (kolom Qty) yang boleh menerima TAB fokus di dalam tabel.
        - Delete button (kolom Aksi) diberi NoFocus agar tidak masuk TAB chain.
        - Setelah spinbox terakhir, TAB langsung menuju payment_method (input card),
          sehingga fokus tidak terjebak berputar di dalam tabel.
        """
        spinboxes: list[QSpinBox] = []
        for row in range(self.cart_table.rowCount()):
            widget = self.cart_table.cellWidget(row, 4)
            if isinstance(widget, QSpinBox):
                spinboxes.append(widget)

        if not spinboxes:
            QWidget.setTabOrder(self.search_input, self.search_input)
            return

        for sb in spinboxes:
            if isinstance(sb, MacroSpinBox):
                sb.is_last_spinbox = False
        last_sb = spinboxes[-1]
        if isinstance(last_sb, MacroSpinBox):
            last_sb.is_last_spinbox = True

        QWidget.setTabOrder(self.search_input, spinboxes[0])
        QWidget.setTabOrder(self.payment_input, self.payment_method)

    def _focus_search(self):
        """Fokus ke search input dan select semua teks (untuk Ctrl+F shortcut)."""
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _set_table_label(self, row: int, column: int, value: str):
        item = self.cart_table.item(row, column)
        if item is None:
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cart_table.setItem(row, column, item)
        else:
            item.setText(value)

    def _calculate_rounding_amount(self, current_total: int) -> int:
        remainder = current_total % 1000
        if remainder == 0:
            return 0
        if 1 <= remainder <= 250:
            return -remainder
        elif 251 <= remainder <= 750:
            return 500 - remainder
        elif 751 <= remainder <= 999:
            return 1000 - remainder
        return 0

    def _apply_rounding(self):
        if not self.cart_items:
            self.search_hint_label.setText("Keranjang kosong, tidak dapat melakukan pembulatan.")
            return

        self.is_rounding_active = not getattr(self, "is_rounding_active", False)
        self._update_cart_summary()

        if self.is_rounding_active:
            status = "penambahan biaya" if self.pembulatan_nominal > 0 else "pengurangan biaya"
            self.search_hint_label.setText(
                f"Pembulatan aktif ({status}): {self._format_currency(abs(self.pembulatan_nominal))}"
            )
        else:
            self.search_hint_label.setText("Pembulatan dinonaktifkan.")

    def _update_cart_summary(self):
        subtotal = self._get_cart_subtotal()
        self.diskon_nominal = self._calculate_discount_amount(subtotal)
        
        current_total = max(0, subtotal - self.diskon_nominal)
        if getattr(self, "is_rounding_active", False):
            self.pembulatan_nominal = self._calculate_rounding_amount(current_total)
        else:
            self.pembulatan_nominal = 0
            
        total = self._calculate_final_total(subtotal)

        self.summary_subtotal.setText(self._format_currency(subtotal))
        self.summary_discount.setText(self._format_discount_summary())
        self.summary_rounding.setText(self._format_currency(self.pembulatan_nominal))
        self.summary_total.setText(self._format_currency(total))

        total_item = sum(item["qty"] for item in self.cart_items)
        if total_item:
            self.cart_info_label.setText(
                f"{len(self.cart_items)} produk • {total_item} item di keranjang."
            )
        else:
            self.cart_info_label.setText("Keranjang masih kosong.")

        self._update_change_display()

    def _update_change_display(self):
        total = self._calculate_final_total()
        bayar = self._parse_currency_input(self.payment_input.text())
        kembali = bayar - total
        self.change_label.setText(f"Kembalian: {self._format_currency(kembali)}")

    @staticmethod
    def _parse_currency_input(value: str) -> int:
        digits = "".join(ch for ch in value if ch.isdigit())
        return int(digits) if digits else 0

    def _format_payment_input(self, text: str):
        digits = "".join(ch for ch in text if ch.isdigit())

        if not digits:
            self.payment_input.blockSignals(True)
            self.payment_input.clear()
            self.payment_input.blockSignals(False)
            self._update_change_display()
            return

        formatted_text = f"{int(digits):,}".replace(",", ".")

        if formatted_text != text:
            cursor_pos_from_right = len(text) - self.payment_input.cursorPosition()

            self.payment_input.blockSignals(True)
            self.payment_input.setText(formatted_text)
            self.payment_input.blockSignals(False)

            new_cursor_pos = max(0, len(formatted_text) - cursor_pos_from_right)
            self.payment_input.setCursorPosition(new_cursor_pos)

        self._update_change_display()

    @staticmethod
    def _build_card() -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        return card

    def _clear_cart(self):
        self.cart_items.clear()
        self.cart_table.setRowCount(0)
        self.discount_mode = None
        self.diskon_nominal = 0
        self.diskon_nominal_input = 0
        self.diskon_persen = 0
        self.is_rounding_active = False
        self.pembulatan_nominal = 0
        self.summary_discount.setText(self._format_discount_summary())
        self.summary_rounding.setText(self._format_currency(0))
        self._update_cart_summary()
        self.payment_input.clear()
        self.customer_input.clear()
        self.notes_input.clear()
        self.search_hint_label.setText("Keranjang dikosongkan.")

    def _show_discount_popup(self):
        if not self.cart_items:
            self.search_hint_label.setText("Tambahkan produk ke keranjang sebelum memberi diskon.")
            return

        if self.discount_popup is not None:
            self.discount_popup.close()

        state = {
            "mode": self.discount_mode,
            "percent": self.diskon_persen,
            "nominal_input": self.diskon_nominal_input,
        }
        self.discount_popup = DiscountPopup(self, state, self._apply_discount_value)
        popup_size = self.discount_popup.sizeHint()
        origin = self.mapToGlobal(self.rect().topLeft())
        target_x = max(0, (self.width() - popup_size.width()) // 2)
        target_y = max(0, (self.height() - popup_size.height()) // 2)
        self.discount_popup.move(origin.x() + target_x, origin.y() + target_y)
        self.discount_popup.show()

    def _apply_discount_value(self, payload: dict):
        mode = payload.get("mode")
        percent_value = int(payload.get("percent") or 0)
        nominal_value = int(payload.get("nominal") or 0)

        if mode == "percent":
            self.discount_mode = "percent"
            self.diskon_persen = max(0, min(percent_value, 100))
            self.diskon_nominal_input = 0
        elif mode == "nominal":
            self.discount_mode = "nominal"
            self.diskon_persen = 0
            self.diskon_nominal_input = max(0, nominal_value)
        else:
            self.discount_mode = None
            self.diskon_persen = 0
            self.diskon_nominal_input = 0

        self._update_cart_summary()

        if self.discount_mode == "percent":
            self.search_hint_label.setText(f"Diskon {self.diskon_persen}% diterapkan ke transaksi.")
        elif self.discount_mode == "nominal":
            self.search_hint_label.setText(
                f"Diskon nominal {self._format_currency(self.diskon_nominal)} diterapkan ke transaksi."
            )
        else:
            self.search_hint_label.setText("Diskon transaksi dihapus.")

    def _get_cart_subtotal(self) -> int:
        return sum(item["harga_jual"] * item["qty"] for item in self.cart_items)

    def _calculate_discount_amount(self, subtotal: int | None = None) -> int:
        subtotal = self._get_cart_subtotal() if subtotal is None else max(0, int(subtotal))
        if subtotal <= 0:
            return 0

        if self.discount_mode == "percent" and self.diskon_persen > 0:
            nominal = int(round(subtotal * (self.diskon_persen / 100)))
            return min(subtotal, nominal)

        if self.discount_mode == "nominal" and self.diskon_nominal_input > 0:
            return min(subtotal, self.diskon_nominal_input)

        return 0

    def _calculate_final_total(self, subtotal: int | None = None) -> int:
        subtotal = self._get_cart_subtotal() if subtotal is None else max(0, int(subtotal))
        discount_amount = self._calculate_discount_amount(subtotal)
        return max(0, subtotal - discount_amount + self.pembulatan_nominal)

    def _format_discount_summary(self) -> str:
        if self.discount_mode == "percent" and self.diskon_persen > 0 and self.diskon_nominal > 0:
            return f"{self._format_currency(self.diskon_nominal)} ({self.diskon_persen}%)"

        if self.discount_mode == "nominal" and self.diskon_nominal > 0:
            return self._format_currency(self.diskon_nominal)

        return self._format_currency(0)

    def _build_sale_payload(self) -> dict:
        subtotal = self._get_cart_subtotal()
        discount_nominal = self._calculate_discount_amount(subtotal)
        total = self._calculate_final_total(subtotal)
        amount_paid = self._parse_currency_input(self.payment_input.text())
        payment_method = self.payment_method.currentText().strip()

        if payment_method in {"QRIS", "Transfer"} and amount_paid <= 0:
            amount_paid = total

        return {
            "subtotal": subtotal,
            "discount_nominal": discount_nominal,
            "discount_percent": self.diskon_persen if self.discount_mode == "percent" else 0,
            "rounding": self.pembulatan_nominal,
            "total": total,
            "payment_method": payment_method,
            "amount_paid": amount_paid,
            "change_amount": amount_paid - total,
            "customer_name": self.customer_input.text().strip(),
            "notes": self.notes_input.toPlainText().strip(),
        }

    def _process_payment(self):
        if not self.cart_items:
            self.search_hint_label.setText("Keranjang masih kosong. Tidak ada transaksi untuk dibayar.")
            return

        sale_payload = self._build_sale_payload()
        if sale_payload["amount_paid"] < sale_payload["total"]:
            self.search_hint_label.setText("Nominal bayar masih kurang dari total tagihan.")
            return

        result = self.db_manager.create_sale_transaction(
            self.cart_items,
            sale_payload,
            self.user_data,
        )

        if not result.get("success"):
            self.search_hint_label.setText(f"Gagal menyimpan transaksi: {result.get('message', '-')}")
            return

        transaction_id = result.get("transaction_id")
        customer_name = result.get("customer_name", "Pelanggan Umum")

        if self.print_checkbox.isChecked():
            transaction_data = self.db_manager.get_transaction_detail_with_items(transaction_id)
            if transaction_data:
                dialog = PrinterSelectionDialog(self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    selected_printer = dialog.get_selected_printer()
                    printer = NotaPrinter(printer_name=selected_printer)
                    printer.print_receipt(transaction_data)

        self._clear_cart()
        self.search_hint_label.setText(
            f"Transaksi #{transaction_id} berhasil disimpan untuk {customer_name}."
        )


    @staticmethod
    def _create_summary_row(parent_layout: QVBoxLayout, label_text: str, value_text: str) -> QLabel:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(label_text)
        label.setStyleSheet("color: #b7c2cc; font-size: 13px;")
        value = QLabel(value_text)
        value.setStyleSheet("color: #ffffff; font-size: 14px; font-weight: 700;")

        layout.addWidget(label)
        layout.addStretch()
        layout.addWidget(value)
        parent_layout.addWidget(row)
        return value

    @staticmethod
    def _format_currency(value: int) -> str:
        prefix = "-" if value < 0 else ""
        nominal = f"{abs(int(value)):,}".replace(",", ".")
        return f"{prefix}Rp {nominal}"

    @staticmethod
    def _format_role(role_value) -> str:
        role_text = str(role_value or "User").replace("_", " ").strip()
        return role_text.upper()

    @staticmethod
    def _build_suggestion_text(item: dict) -> str:
        return f"{item['nama_barang']} • {item['sku']} • {str(item['tipe']).title()}"

    @staticmethod
    def _get_stylesheet() -> str:
        return f"""
                QWidget {{
                    background-color: transparent;
                    color: #ffffff;
                    font-family: "Segoe UI";
                }}
                QFrame#card {{
                    background-color: #0d1117;
                    border: 2px solid #1d2630;
                    border-radius: 18px;
                }}
                QLabel#smallBadge {{
                    background-color: rgba(0, 255, 133, 0.12);
                    color: #7dfcc4;
                    border: 2px solid rgba(0, 255, 133, 0.4);
                    border-radius: 10px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QLineEdit, QComboBox, QDoubleSpinBox, QTextEdit, QSpinBox {{
                    background-color: #111827;
                    border: 2px solid #263241;
                    border-radius: 12px;
                    color: #ffffff;
                    padding: 10px 12px;
                    font-size: 13px;
                }}
                QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QSpinBox:focus {{
                    border: 2px solid #00c2ff;
                }}
                QSpinBox::up-button {{
                    subcontrol-origin: border;
                    subcontrol-position: top right;
                    width: 20px;
                    border-left: 1px solid #2a3745;
                }}
                QSpinBox::down-button {{
                    subcontrol-origin: border;
                    subcontrol-position: bottom right;
                    width: 20px;
                    border-left: 1px solid #2a3745;
                }}
                QSpinBox::up-arrow {{
                    image: url({asset_uri("icon_up.svg")});
                    width: 10px;
                    height: 10px;
                }}
                QSpinBox::down-arrow {{
                    image: url({asset_uri("icon_down.svg")});
                    width: 10px;
                    height: 10px;
                }}
                QComboBox::drop-down {{
                    border: none;
                    width: 26px;
                }}
                QPushButton {{
                    min-height: 44px;
                    border-radius: 12px;
                    border: none;
                    font-size: 13px;
                    font-weight: 700;
                    padding: 0 16px;
                }}
                QPushButton#deleteCartButton {{
                    min-height: 34px;
                    max-height: 34px;
                    background-color: #241316;
                    border: 2px solid #59242a;
                    padding: 0;
                }}
                QPushButton#deleteCartButton:hover {{
                    background-color: #3b1c20;
                }}

                QTableWidget {{
                    background-color: #0a0f14;
                    border: 1px solid #202a35;
                    border-radius: 14px;
                    gridline-color: #1d2630;
                    color: #ffffff;
                    padding: 6px;
                    selection-background-color: transparent;
                }}
                QHeaderView::section {{
                    background-color: #121a24;
                    color: #93a1af;
                    padding: 10px;
                    border: none;
                    border-bottom: 1px solid #263241;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QTableWidget::item {{
                    padding: 10px;
                    border-bottom: 1px solid #18212b;
                }}
        """
