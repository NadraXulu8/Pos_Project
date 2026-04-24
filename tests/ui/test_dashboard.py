"""
==============================================================================
test_dashboard.py — Integration Test untuk Dashboard
==============================================================================

Menguji komponen Dashboard (src/ui/dashboard.py).
Fixture `dashboard` tersedia via tests/ui/conftest.py.
==============================================================================
"""

import pytest
from PySide6.QtCore import Qt
from src.ui.pengeluaran_toko import PengeluaranTokoWindow


# ===========================================================================
# SECTION 12: TEST INTEGRASI — Dashboard (init + navigasi sidebar)
# ===========================================================================

class TestDashboard:
    """
    Integration test untuk Dashboard (src/ui/dashboard.py).
    Menguji inisialisasi dan interaksi sidebar navigasi.
    """

    def test_dashboard_terbuat_dengan_sidebar(self, dashboard):
        """
        Memastikan Dashboard berhasil dibuat dengan atribut sidebar kiri,
        sidebar kanan, dan main_stack.
        """
        widget, _ = dashboard
        assert hasattr(widget, "sidebar_left")
        assert hasattr(widget, "sidebar_right")
        assert hasattr(widget, "main_stack")

    def test_sidebar_kanan_tersembunyi_saat_awal(self, dashboard):
        """
        Memastikan sidebar kanan disembunyikan saat Dashboard pertama
        kali dibuat (hanya sidebar kiri yang terlihat).
        """
        widget, _ = dashboard
        widget.show()
        assert not widget.sidebar_right.isVisible(), \
            "Sidebar kanan harus tersembunyi pada awal"
        assert widget.sidebar_left.isVisible(), \
            "Sidebar kiri harus terlihat pada awal"

    def test_klik_menu_menampilkan_sidebar_kanan(self, qtbot, dashboard):
        """
        Memastikan klik button_menu_left menyembunyikan sidebar kiri
        dan menampilkan sidebar kanan (efek toggle sidebar).
        """
        widget, _ = dashboard
        widget.show()
        qtbot.mouseClick(widget.button_menu_left, Qt.MouseButton.LeftButton)
        assert widget.sidebar_right.isVisible()
        assert not widget.sidebar_left.isVisible()

    def test_klik_menu_kanan_mengembalikan_sidebar_kiri(self, qtbot, dashboard):
        """
        Memastikan klik button_menu_right mengembalikan tampilan ke
        sidebar kiri (toggle balik).
        """
        widget, _ = dashboard
        widget.show()
        # Buka sidebar kanan dahulu
        qtbot.mouseClick(widget.button_menu_left, Qt.MouseButton.LeftButton)
        # Lalu klik menu kanan untuk toggle kembali
        qtbot.mouseClick(widget.button_menu_right, Qt.MouseButton.LeftButton)
        assert widget.sidebar_left.isVisible()
        assert not widget.sidebar_right.isVisible()

    def test_role_super_user_memperlihatkan_semua_menu(self, dashboard):
        """
        Memastikan semua tombol menu tersedia untuk role 'Super_user'
        (tidak ada yang disembunyikan karena pembatasan role).
        """
        widget, _ = dashboard
        widget.show()
        # Dengan role Super_user, tombol kas dan user harus terlihat
        assert widget.button_kas_left.isVisible()
        assert widget.button_user_left.isVisible()

    def test_welcome_widget_aktif_saat_awal(self, dashboard):
        """
        Memastikan main_stack menampilkan WelcomeWindow sebagai widget
        aktif pertama saat Dashboard baru dibuka.
        """
        widget, _ = dashboard
        current = widget.main_stack.currentWidget()
        assert current is widget.welcome_widget, \
            "WelcomeWindow harus menjadi widget aktif pertama"

    def test_klik_buku_membuka_halaman_pengeluaran_toko(self, qtbot, dashboard):
        """
        Memastikan klik tombol buku membuka halaman PengeluaranTokoWindow
        dan tidak lagi menampilkan error widget.
        """
        widget, _ = dashboard
        widget.show()
        qtbot.mouseClick(widget.button_buku_left, Qt.MouseButton.LeftButton)
        assert isinstance(widget.main_stack.currentWidget(), PengeluaranTokoWindow)
        assert widget.main_stack.currentWidget() is widget.pengeluaran_widget
