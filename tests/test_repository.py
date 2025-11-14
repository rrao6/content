from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from exceptions import ContentNotFoundError
from repository import ContentRepository


@pytest.fixture
def mock_config():
    class DummyConfig:
        fully_qualified_table = "catalog.schema.content_info"

    return DummyConfig()


def test_get_by_id_success(mock_config):
    repo = ContentRepository(config=mock_config)
    fake_row = SimpleNamespace(
        content_id=1,
        content_name="Title",
        is_episode=False,
        program_name="Program",
        program_id=10,
        content_type="movie",
        parent_id=None,
        import_id="imp",
        publisher_id="pub",
        active=True,
        policy=None,
        content_partner_id=None,
        gracenote_id="grace",
        program_gracenote_id="pgrace",
        duration=3600.0,
        cue_points=None,
        credit_cue_point=None,
        rating="PG",
        mpaa_rating="PG",
        tvpg_rating="PG",
        poster_img_url="https://example/1.jpg",
    )

    with patch("repository.get_cursor") as mock_cursor_ctx:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [fake_row]
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        records = repo.get_by_id("1")
        assert len(records) == 1
        assert records[0].content_id == 1


def test_get_by_id_not_found(mock_config):
    repo = ContentRepository(config=mock_config)

    with patch("repository.get_cursor") as mock_cursor_ctx:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        with pytest.raises(ContentNotFoundError):
            repo.get_by_id("missing")


def test_get_batch(mock_config):
    repo = ContentRepository(config=mock_config)
    fake_rows = [
        SimpleNamespace(content_id=1),
        SimpleNamespace(content_id=2),
        SimpleNamespace(content_id=1),
    ]

    with patch("repository.get_cursor") as mock_cursor_ctx:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = fake_rows
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        results = repo.get_batch(["1", "2"])
        assert set(results.keys()) == {1, 2}
        assert len(results[1]) == 2


def test_iter_poster_images(mock_config):
    repo = ContentRepository(config=mock_config)
    rows = [
        SimpleNamespace(content_id=1, poster_img_url="https://a"),
        SimpleNamespace(content_id=2, poster_img_url=None),
    ]

    with patch("repository.get_cursor") as mock_cursor_ctx:
        mock_cursor = MagicMock()
        mock_cursor.fetchall.side_effect = AssertionError("fetchall not expected")
        mock_cursor.fetchmany.side_effect = [rows, []]
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        posters = list(
            repo.iter_poster_images(
                batch_size=2, only_active=False, require_url=False
            )
        )
        assert len(posters) == 2
        assert posters[0].poster_img_url == "https://a"


def test_iter_poster_images_limit(mock_config):
    repo = ContentRepository(config=mock_config)
    rows = [
        SimpleNamespace(content_id=1, poster_img_url="https://a"),
        SimpleNamespace(content_id=2, poster_img_url="https://b"),
    ]

    with patch("repository.get_cursor") as mock_cursor_ctx:
        mock_cursor = MagicMock()
        mock_cursor.fetchmany.side_effect = [rows, []]
        mock_cursor_ctx.return_value.__enter__.return_value = mock_cursor

        posters = list(
            repo.iter_poster_images(
                batch_size=2, only_active=False, require_url=False, max_items=1
            )
        )
        assert len(posters) == 1
        assert posters[0].poster_img_url == "https://a"

