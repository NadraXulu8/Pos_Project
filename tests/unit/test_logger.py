import logging
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from src.utils.logger import (
    _global_exception_handler,
    _show_crash_dialog,
    get_user_friendly_message,
    get_logger,
    install_global_exception_handler,
    log_critical,
    log_error,
    setup_logging,
)


def test_get_user_friendly_message_for_known_exception():
    message = get_user_friendly_message(ValueError("bad input"))
    assert "Data yang dimasukkan tidak valid" in message


def test_get_user_friendly_message_uses_parent_exception_map():
    class CustomValueError(ValueError):
        pass

    message = get_user_friendly_message(CustomValueError("custom"))
    assert "Data yang dimasukkan tidak valid" in message


def test_get_user_friendly_message_for_unknown_exception_falls_back_to_default():
    class UnknownError(Exception):
        pass

    message = get_user_friendly_message(UnknownError("x"))
    assert "Terjadi kesalahan yang tidak terduga" in message


def test_log_error_logs_and_returns_user_message():
    logger = MagicMock()

    try:
        raise ValueError("invalid data")
    except ValueError as exc:
        message = log_error(exc, context="uji", logger=logger)

    assert "Data yang dimasukkan tidak valid" in message
    logger.error.assert_called_once()
    assert "Exception [uji]" in logger.error.call_args[0][0]


def test_log_critical_logs_and_returns_user_message():
    logger = MagicMock()

    try:
        raise RuntimeError("fatal")
    except RuntimeError as exc:
        message = log_critical(exc, context="fatal flow", logger=logger)

    assert "Terjadi kesalahan saat menjalankan aplikasi" in message
    logger.critical.assert_called_once()
    assert "FATAL Exception [fatal flow]" in logger.critical.call_args[0][0]


def test_install_global_exception_handler_sets_sys_excepthook():
    original_hook = sys.excepthook
    try:
        with patch("src.utils.logger.get_logger", return_value=MagicMock()) as mocked_get_logger:
            install_global_exception_handler()
            assert sys.excepthook == _global_exception_handler
            mocked_get_logger.return_value.info.assert_called_once()
    finally:
        sys.excepthook = original_hook


def test_global_exception_handler_delegates_keyboard_interrupt():
    with patch("sys.__excepthook__") as default_hook:
        _global_exception_handler(KeyboardInterrupt, KeyboardInterrupt(), None)
        default_hook.assert_called_once()


def test_global_exception_handler_logs_and_shows_dialog():
    mock_logger = MagicMock(spec=logging.Logger)

    with patch("src.utils.logger.get_logger", return_value=mock_logger), patch(
        "src.utils.logger._show_crash_dialog"
    ) as show_dialog:
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            _global_exception_handler(RuntimeError, exc, exc.__traceback__)

        mock_logger.critical.assert_called_once()
        show_dialog.assert_called_once()


def test_setup_logging_creates_log_file_and_returns_pos_logger(tmp_path):
    log_dir = tmp_path / "logs"

    root_logger = logging.getLogger()
    old_handlers = root_logger.handlers[:]
    old_level = root_logger.level
    root_logger.handlers = []

    try:
        logger = setup_logging(log_dir=str(log_dir), log_file="unit.log")
        assert logger.name == "POS"
        assert (log_dir / "unit.log").exists()
        assert len(root_logger.handlers) >= 2
    finally:
        for handler in root_logger.handlers:
            try:
                handler.close()
            except Exception:
                pass
        root_logger.handlers = old_handlers
        root_logger.setLevel(old_level)


def test_get_logger_returns_named_logger():
    logger = get_logger("database")
    assert logger.name == "POS.database"


def test_show_crash_dialog_without_qapplication_prints_stderr(capsys):
    with patch("PySide6.QtWidgets.QApplication.instance", return_value=None):
        _show_crash_dialog("RuntimeError", "Pesan user", "detail boom")

    captured = capsys.readouterr()
    assert "[CRITICAL ERROR] RuntimeError: detail boom" in captured.err


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication([])
        created = True
    yield app
    if created:
        app.quit()


def test_show_crash_dialog_prints_to_stderr_when_dialog_raises_exception(capsys, qapp):

    class BrokenMessageBox:
        class Icon:
            Critical = 1

        class StandardButton:
            Ok = 1

        def setIcon(self, *_args, **_kwargs):
            raise RuntimeError("dialog broken")

    with patch("PySide6.QtWidgets.QApplication.instance", return_value=qapp), patch(
        "PySide6.QtWidgets.QMessageBox", BrokenMessageBox
    ), patch("PySide6.QtGui.QIcon"):
        _show_crash_dialog("RuntimeError", "Pesan user", "detail crash")

    captured = capsys.readouterr()
    assert "Gagal menampilkan dialog error" in captured.err
