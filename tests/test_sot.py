"""Tests for SOT (Sources of Truth) functionality."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from sot_query import get_eligible_titles_query, get_eligible_titles_with_content_query
from sot_repository import SOTRepository, EligibleTitle
from service import EligibleTitlesService


class TestSOTQuery:
    """Test SOT query generation."""
    
    def test_eligible_titles_query_default(self):
        """Test default query generation."""
        query = get_eligible_titles_query()
        
        # Check that it includes all SOT types
        assert "imdb" in query
        assert "rt" in query
        assert "award" in query
        assert "vibe" in query
        assert "narrative" in query
        assert "most_liked" in query
        assert "leaving_soon" in query
        assert "just_added" in query
        
        # Check date params
        assert "SELECT" in query
        assert "UNION ALL" in query
    
    def test_eligible_titles_query_with_sot_filter(self):
        """Test query with SOT type filter."""
        query = get_eligible_titles_query(sot_types=["imdb", "rt"])
        
        # Should include specified types
        assert "imdb" in query
        assert "rt" in query
        
        # Should not include others
        assert "award" not in query
        assert "vibe" not in query
    
    def test_eligible_titles_query_with_dates(self):
        """Test query with specific date range."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 1, 7)
        
        query = get_eligible_titles_query(start_date=start, end_date=end)
        
        assert "2025-01-01" in query
        assert "2025-01-07" in query
    
    def test_eligible_titles_with_content_query(self):
        """Test query that joins with content_info."""
        query = get_eligible_titles_with_content_query()
        
        assert "JOIN core_prod.tubidw.content_info" in query
        assert "poster_img_url" in query
        assert "content_name" in query


class TestSOTRepository:
    """Test SOT repository functionality."""
    
    @pytest.fixture
    def mock_cursor(self):
        """Mock database cursor."""
        cursor = MagicMock()
        return cursor
    
    @pytest.fixture
    def repository(self):
        """Create repository instance."""
        return SOTRepository()
    
    def test_get_eligible_titles(self, repository, mock_cursor):
        """Test fetching eligible titles."""
        # Mock data
        mock_rows = [
            MagicMock(program_id=123, sot_name="imdb"),
            MagicMock(program_id=456, sot_name="rt"),
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        with patch("sot_repository.get_cursor", return_value=mock_cursor):
            titles = repository.get_eligible_titles(limit=10)
        
        assert len(titles) == 2
        assert titles[0].program_id == 123
        assert titles[0].sot_name == "imdb"
        assert titles[1].program_id == 456
        assert titles[1].sot_name == "rt"
    
    def test_get_eligible_titles_with_content(self, repository, mock_cursor):
        """Test fetching eligible titles with content info."""
        # Mock data with content details
        mock_rows = [
            MagicMock(
                program_id=123,
                sot_name="imdb",
                content_id=123,
                content_name="Test Movie",
                content_type="MOVIE",
                poster_img_url="http://example.com/poster.jpg"
            ),
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        with patch("sot_repository.get_cursor", return_value=mock_cursor):
            titles = repository.get_eligible_titles_with_content()
        
        assert len(titles) == 1
        assert titles[0].content_name == "Test Movie"
        assert titles[0].poster_img_url == "http://example.com/poster.jpg"
    
    def test_count_eligible_titles_by_sot(self, repository, mock_cursor):
        """Test counting titles by SOT type."""
        # Mock count data
        mock_rows = [
            MagicMock(sot_name="imdb", title_count=150),
            MagicMock(sot_name="rt", title_count=75),
            MagicMock(sot_name="award", title_count=25),
        ]
        mock_cursor.fetchall.return_value = mock_rows
        
        with patch("sot_repository.get_cursor", return_value=mock_cursor):
            counts = repository.count_eligible_titles_by_sot()
        
        assert counts["imdb"] == 150
        assert counts["rt"] == 75
        assert counts["award"] == 25
        assert sum(counts.values()) == 250


class TestEligibleTitlesService:
    """Test eligible titles service."""
    
    @pytest.fixture
    def mock_repository(self):
        """Mock SOT repository."""
        return MagicMock(spec=SOTRepository)
    
    @pytest.fixture
    def service(self, mock_repository):
        """Create service instance with mock repository."""
        return EligibleTitlesService(repository=mock_repository)
    
    def test_fetch_eligible_titles_with_cache(self, service, mock_repository):
        """Test that eligible titles are cached."""
        # Mock data
        mock_titles = [
            EligibleTitle(program_id=123, sot_name="imdb"),
            EligibleTitle(program_id=456, sot_name="rt"),
        ]
        mock_repository.get_eligible_titles.return_value = mock_titles
        
        # First call - should hit repository
        result1 = service.fetch_eligible_titles(days_back=7)
        assert len(result1) == 2
        assert mock_repository.get_eligible_titles.call_count == 1
        
        # Second call with same params - should use cache
        result2 = service.fetch_eligible_titles(days_back=7)
        assert len(result2) == 2
        assert mock_repository.get_eligible_titles.call_count == 1  # No additional call
        
        # Call with different params - should hit repository again
        result3 = service.fetch_eligible_titles(days_back=14)
        assert mock_repository.get_eligible_titles.call_count == 2
    
    def test_get_eligible_poster_images(self, service, mock_repository):
        """Test filtering to only titles with poster URLs."""
        # Mock data with mix of titles with/without posters
        mock_titles = [
            EligibleTitle(
                program_id=123,
                sot_name="imdb",
                poster_img_url="http://example.com/1.jpg"
            ),
            EligibleTitle(
                program_id=456,
                sot_name="rt",
                poster_img_url=None  # No poster
            ),
            EligibleTitle(
                program_id=789,
                sot_name="award",
                poster_img_url="http://example.com/3.jpg"
            ),
        ]
        mock_repository.get_eligible_titles_with_content.return_value = mock_titles
        
        # Get only titles with posters
        result = service.get_eligible_poster_images()
        
        assert len(result) == 2
        assert all(t.poster_img_url for t in result)
        assert result[0].program_id == 123
        assert result[1].program_id == 789
