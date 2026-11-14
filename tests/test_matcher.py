from app.triggers.matcher import is_reminder
from app.memos.models import Memo

from unittest.mock import Mock


def test_none_memo():
    assert is_reminder(None) is False


def test_empty_content_memo():
    assert is_reminder(Mock(spec=Memo, content="")) is False


def test_whitespace_content_memo():
    assert is_reminder(Mock(spec=Memo, content="   ")) is False


def test_reminder():
    assert is_reminder(Mock(spec=Memo, content="напомни завтра")) is True


def test_not_reminder():
    assert is_reminder(Mock(spec=Memo, content="обычная заметка")) is False


def test_custom_phrases():
    memo = Mock(spec=Memo, content="купи хлеб")
    assert is_reminder(memo, ["купи"]) is True


def test_empty_phrases():
    memo = Mock(spec=Memo, content="напомни завтра")
    assert is_reminder(memo, []) is False
