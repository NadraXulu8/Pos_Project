import logging
import sys
from unittest.mock import MagicMock, patch

from src.utils.logger import (
    _global_exception_handler,
    get_user_friendly_message,
    install_global_exception_handler,
    log_critical,
    log_error,
)


def test_get_user_friendly_message_for_known_exception():
    message = get_user_friendly_message(ValueError("bad input"))
    assert "Data yang dimasukkan tidak valid" in message


def test_get_user_friendly_message_uses_parent_exception_map():
    class CustomValueError(ValueError):
        pass

    message = get_user_friendly_message(CustomValueError("custom"))
    assert "Data yang dimasukkan tidak valid" in message


def test_get_user_friendly_message_for_unknown_exception_falls_back_default():
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
    original = sys.excepthook
    try:
        with patch("src.utils.logger.get_logger", return_value=MagicMock()) as mocked_get_logger:
            install_global_exception_handler()
            assert sys.excepthook == _global_exception_handler
            mocked_get_logger.return_value.info.assert_called_once()
    finally:
        sys.excepthook = original


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

