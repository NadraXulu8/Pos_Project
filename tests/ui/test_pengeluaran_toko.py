from unittest.mock import patch

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

from src.ui.pengeluaran_toko import PengeluaranTokoWindow


class TestPengeluaranTokoWindow:
    def test_simpan_nonaktif_saat_form_kosong(self, qtbot):
        widget = PengeluaranTokoWindow()
        qtbot.addWidget(widget)
        assert not widget.save_button.isEnabled()

    def test_tambah_data_pengeluaran(self, qtbot):
        widget = PengeluaranTokoWindow()
        qtbot.addWidget(widget)

        widget.date_input.setDate(QDate(2026, 4, 24))
        widget.category_input.setCurrentText("Operasional")
        widget.amount_input.setText("25000")
        widget.method_input.setCurrentText("Cash")
        widget.note_input.setPlainText("Beli alat tulis")
        widget._on_save()

        assert len(widget.expense_data) == 1
        assert widget.table.rowCount() == 1
        assert widget.expense_data[0]["amount"] == 25000

    def test_edit_dan_hapus_data_pengeluaran(self, qtbot):
        widget = PengeluaranTokoWindow()
        qtbot.addWidget(widget)
        widget.expense_data = [{
            "date": "2026-04-24",
            "category": "Operasional",
            "amount": 10000,
            "method": "Cash",
            "note": "Awal"
        }]
        widget._apply_search_filter_sort()

        widget._on_edit(0)
        widget.amount_input.setText("15000")
        widget._on_save()
        assert widget.expense_data[0]["amount"] == 15000

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            widget._on_delete(0)
        assert widget.expense_data == []
