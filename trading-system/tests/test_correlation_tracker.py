#!/usr/bin/env python3
"""
Comprehensive tests for correlation_tracker.py module
Tests correlation ID tracking, persistence, parent-child chains, and statistics
"""

import pytest
import tempfile
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.correlation_tracker import (
    CorrelationRecord,
    CorrelationTracker,
    get_global_tracker
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    yield temp_file.name
    # Cleanup
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


@pytest.fixture
def tracker(temp_db):
    """Create CorrelationTracker instance with temp database"""
    return CorrelationTracker(db_path=temp_db)


# ============================================================================
# CorrelationRecord Tests
# ============================================================================

class TestCorrelationRecord:
    """Test CorrelationRecord dataclass"""

    def test_duration_ms_completed_operation(self):
        """Test duration calculation for completed operation"""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 0, 150000)  # 150ms later

        record = CorrelationRecord(
            correlation_id="test-123",
            operation="test_op",
            start_time=start,
            end_time=end
        )

        duration = record.duration_ms()
        assert duration == 150.0

    def test_duration_ms_pending_operation(self):
        """Test duration is None for pending operation"""
        record = CorrelationRecord(
            correlation_id="test-123",
            operation="test_op",
            start_time=datetime.now()
        )

        assert record.duration_ms() is None

    def test_to_dict_conversion(self):
        """Test converting record to dictionary"""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 1)

        record = CorrelationRecord(
            correlation_id="test-123",
            operation="test_op",
            start_time=start,
            end_time=end,
            status="success",
            metadata={"key": "value"}
        )

        data = record.to_dict()

        assert data["correlation_id"] == "test-123"
        assert data["operation"] == "test_op"
        assert data["status"] == "success"
        assert data["start_time"] == start.isoformat()
        assert data["end_time"] == end.isoformat()
        assert data["metadata"] == {"key": "value"}

    def test_to_dict_with_none_end_time(self):
        """Test to_dict with pending operation (no end time)"""
        start = datetime(2025, 1, 1, 10, 0, 0)

        record = CorrelationRecord(
            correlation_id="test-123",
            operation="test_op",
            start_time=start
        )

        data = record.to_dict()

        assert data["end_time"] is None


# ============================================================================
# Tracker Initialization Tests
# ============================================================================

class TestTrackerInitialization:
    """Test CorrelationTracker initialization"""

    def test_initialization_creates_database(self, temp_db):
        """Test that initialization creates database file"""
        tracker = CorrelationTracker(db_path=temp_db)

        assert os.path.exists(temp_db)

    def test_initialization_creates_parent_directory(self):
        """Test that initialization creates parent directories"""
        import shutil
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "subdir", "test.db")

        tracker = CorrelationTracker(db_path=db_path)

        assert os.path.exists(db_path)

        # Cleanup
        shutil.rmtree(temp_dir)

    def test_database_schema_created(self, tracker, temp_db):
        """Test that database schema is properly created"""
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='correlations'"
        )

        tables = cursor.fetchall()
        assert len(tables) == 1
        assert tables[0][0] == "correlations"

        conn.close()

    def test_database_indices_created(self, tracker, temp_db):
        """Test that database indices are created"""
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )

        indices = [row[0] for row in cursor.fetchall()]

        # Check expected indices exist
        assert any('idx_correlations_operation' in idx for idx in indices)
        assert any('idx_correlations_status' in idx for idx in indices)
        assert any('idx_correlations_start_time' in idx for idx in indices)

        conn.close()


# ============================================================================
# Start/End Operation Tests
# ============================================================================

class TestStartEndOperations:
    """Test starting and ending operations"""

    def test_start_operation_generates_correlation_id(self, tracker):
        """Test that start_operation generates a correlation ID"""
        corr_id = tracker.start_operation("test_operation")

        assert corr_id is not None
        assert len(corr_id) > 0

    def test_start_operation_with_existing_id(self, tracker):
        """Test start_operation with provided correlation ID"""
        provided_id = "custom-correlation-123"

        corr_id = tracker.start_operation("test_operation", correlation_id=provided_id)

        assert corr_id == provided_id

    def test_start_operation_with_metadata(self, tracker):
        """Test start_operation with metadata"""
        metadata = {"user": "test_user", "action": "buy"}

        corr_id = tracker.start_operation("trade", metadata=metadata)

        record = tracker.get_correlation(corr_id)
        assert record.metadata == metadata

    def test_start_operation_with_parent(self, tracker):
        """Test start_operation with parent correlation ID"""
        parent_id = tracker.start_operation("parent_operation")
        child_id = tracker.start_operation("child_operation", parent_correlation_id=parent_id)

        child_record = tracker.get_correlation(child_id)
        assert child_record.parent_correlation_id == parent_id

    def test_end_operation_success(self, tracker):
        """Test ending operation with success"""
        corr_id = tracker.start_operation("test_operation")
        time.sleep(0.01)  # Small delay to ensure duration > 0
        tracker.end_operation(corr_id, status='success')

        record = tracker.get_correlation(corr_id)

        assert record.status == 'success'
        assert record.end_time is not None
        assert record.duration_ms() > 0

    def test_end_operation_failure(self, tracker):
        """Test ending operation with failure"""
        corr_id = tracker.start_operation("test_operation")
        tracker.end_operation(corr_id, status='failure', error_message="Test error")

        record = tracker.get_correlation(corr_id)

        assert record.status == 'failure'
        assert record.error_message == "Test error"

    def test_end_operation_removes_from_active(self, tracker):
        """Test that ending operation removes it from active correlations"""
        corr_id = tracker.start_operation("test_operation")

        # Should be in active correlations
        assert corr_id in tracker._active_correlations

        tracker.end_operation(corr_id)

        # Should be removed from active correlations
        assert corr_id not in tracker._active_correlations

    def test_end_operation_nonexistent_id(self, tracker):
        """Test ending operation with nonexistent correlation ID"""
        # Should not raise exception, just log warning
        tracker.end_operation("nonexistent-id")


# ============================================================================
# Context Manager Tests
# ============================================================================

class TestContextManager:
    """Test track_operation context manager"""

    def test_context_manager_success(self, tracker):
        """Test context manager with successful operation"""
        with tracker.track_operation("test_operation") as corr_id:
            time.sleep(0.01)

        record = tracker.get_correlation(corr_id)

        assert record is not None
        assert record.status == 'success'
        assert record.end_time is not None

    def test_context_manager_failure(self, tracker):
        """Test context manager with failing operation"""
        with pytest.raises(ValueError):
            with tracker.track_operation("test_operation") as corr_id:
                raise ValueError("Test error")

        record = tracker.get_correlation(corr_id)

        assert record is not None
        assert record.status == 'failure'
        assert record.error_message == "Test error"

    def test_context_manager_with_metadata(self, tracker):
        """Test context manager with metadata"""
        metadata = {"key": "value"}

        with tracker.track_operation("test_operation", metadata=metadata) as corr_id:
            pass

        record = tracker.get_correlation(corr_id)
        assert record.metadata == metadata

    def test_context_manager_nested(self, tracker):
        """Test nested context managers (parent-child)"""
        with tracker.track_operation("parent_op") as parent_id:
            with tracker.track_operation("child_op", parent_correlation_id=parent_id) as child_id:
                pass

        child_record = tracker.get_correlation(child_id)
        assert child_record.parent_correlation_id == parent_id


# ============================================================================
# Get Correlation Tests
# ============================================================================

class TestGetCorrelation:
    """Test getting correlation records"""

    def test_get_active_correlation(self, tracker):
        """Test getting correlation from active correlations"""
        corr_id = tracker.start_operation("test_operation")

        record = tracker.get_correlation(corr_id)

        assert record is not None
        assert record.correlation_id == corr_id
        assert record.status == 'pending'

    def test_get_persisted_correlation(self, tracker):
        """Test getting correlation from database"""
        corr_id = tracker.start_operation("test_operation")
        tracker.end_operation(corr_id)

        # Should now be in database, not active
        record = tracker.get_correlation(corr_id)

        assert record is not None
        assert record.correlation_id == corr_id

    def test_get_nonexistent_correlation(self, tracker):
        """Test getting nonexistent correlation"""
        record = tracker.get_correlation("nonexistent-id")

        assert record is None


# ============================================================================
# Operation Chain Tests
# ============================================================================

class TestOperationChain:
    """Test parent-child correlation chains"""

    def test_get_operation_chain_single(self, tracker):
        """Test getting chain with single operation"""
        with tracker.track_operation("single_op") as corr_id:
            pass

        chain = tracker.get_operation_chain(corr_id)

        assert len(chain) == 1
        assert chain[0].operation == "single_op"

    def test_get_operation_chain_parent_child(self, tracker):
        """Test getting chain with parent and child"""
        with tracker.track_operation("parent_op") as parent_id:
            with tracker.track_operation("child_op", parent_correlation_id=parent_id) as child_id:
                pass

        chain = tracker.get_operation_chain(child_id)

        assert len(chain) == 2
        assert chain[0].operation == "parent_op"
        assert chain[1].operation == "child_op"

    def test_get_operation_chain_multiple_children(self, tracker):
        """Test getting chain with multiple children"""
        with tracker.track_operation("parent_op") as parent_id:
            with tracker.track_operation("child_op_1", parent_correlation_id=parent_id):
                pass
            with tracker.track_operation("child_op_2", parent_correlation_id=parent_id):
                pass

        chain = tracker.get_operation_chain(parent_id)

        # Should include parent + 2 children
        assert len(chain) == 3
        assert chain[0].operation == "parent_op"

    def test_get_operation_chain_nonexistent(self, tracker):
        """Test getting chain for nonexistent correlation"""
        chain = tracker.get_operation_chain("nonexistent-id")

        assert len(chain) == 0


# ============================================================================
# Statistics Tests
# ============================================================================

class TestStatistics:
    """Test tracking statistics"""

    def test_get_stats_empty_tracker(self, tracker):
        """Test statistics on empty tracker"""
        stats = tracker.get_stats()

        assert stats['total'] == 0
        assert stats['active'] == 0
        assert stats['by_status'] == {}
        assert stats['by_operation'] == {}

    def test_get_stats_with_operations(self, tracker):
        """Test statistics after operations"""
        # Complete some operations
        with tracker.track_operation("op_1"):
            pass

        with tracker.track_operation("op_2"):
            pass

        # Start active operation
        tracker.start_operation("active_op")

        stats = tracker.get_stats()

        assert stats['total'] == 2  # 2 completed
        assert stats['active'] == 1  # 1 active
        assert 'success' in stats['by_status']
        assert stats['by_status']['success'] == 2

    def test_get_stats_by_operation(self, tracker):
        """Test statistics grouped by operation"""
        # Create multiple operations of same type
        for _ in range(3):
            with tracker.track_operation("repeated_op"):
                pass

        with tracker.track_operation("single_op"):
            pass

        stats = tracker.get_stats()

        assert stats['by_operation']['repeated_op'] == 3
        assert stats['by_operation']['single_op'] == 1

    def test_get_stats_with_failures(self, tracker):
        """Test statistics with failed operations"""
        with tracker.track_operation("success_op"):
            pass

        try:
            with tracker.track_operation("failure_op"):
                raise ValueError("Test error")
        except ValueError:
            pass

        stats = tracker.get_stats()

        assert stats['by_status']['success'] == 1
        assert stats['by_status']['failure'] == 1


# ============================================================================
# Cleanup Tests
# ============================================================================

class TestCleanup:
    """Test cleanup of old records"""

    def test_cleanup_old_records(self, tracker):
        """Test cleaning up old records"""
        # Create some records
        with tracker.track_operation("old_op"):
            pass

        # Delete records older than 0 days (all records)
        deleted = tracker.cleanup_old_records(days=0)

        assert deleted >= 1

    def test_cleanup_keeps_recent_records(self, tracker):
        """Test cleanup keeps recent records"""
        with tracker.track_operation("recent_op") as corr_id:
            pass

        # Delete records older than 30 days (should keep recent)
        deleted = tracker.cleanup_old_records(days=30)

        # Record should still exist
        record = tracker.get_correlation(corr_id)
        assert record is not None

    def test_cleanup_returns_count(self, tracker):
        """Test cleanup returns correct count"""
        # Create 5 records
        for i in range(5):
            with tracker.track_operation(f"op_{i}"):
                pass

        deleted = tracker.cleanup_old_records(days=0)

        assert deleted == 5


# ============================================================================
# Global Tracker Tests
# ============================================================================

class TestGlobalTracker:
    """Test global tracker singleton"""

    def test_get_global_tracker_creates_instance(self):
        """Test that get_global_tracker creates an instance"""
        tracker = get_global_tracker()

        assert tracker is not None
        assert isinstance(tracker, CorrelationTracker)

    def test_get_global_tracker_returns_same_instance(self):
        """Test that get_global_tracker returns same instance"""
        tracker1 = get_global_tracker()
        tracker2 = get_global_tracker()

        assert tracker1 is tracker2


# ============================================================================
# Persistence Tests
# ============================================================================

class TestPersistence:
    """Test database persistence"""

    def test_record_persisted_to_database(self, tracker, temp_db):
        """Test that record is persisted to database"""
        corr_id = tracker.start_operation("test_operation", metadata={"key": "value"})
        tracker.end_operation(corr_id)

        # Query database directly
        import sqlite3
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute(
            "SELECT correlation_id, operation, status, metadata FROM correlations WHERE correlation_id = ?",
            (corr_id,)
        )

        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == corr_id
        assert row[1] == "test_operation"
        assert row[2] == "success"
        assert '{"key": "value"}' in row[3]

    def test_metadata_serialization(self, tracker):
        """Test that complex metadata is properly serialized"""
        metadata = {
            "user": "test_user",
            "nested": {"key": "value"},
            "list": [1, 2, 3]
        }

        corr_id = tracker.start_operation("test_operation", metadata=metadata)
        tracker.end_operation(corr_id)

        # Retrieve and check metadata
        record = tracker.get_correlation(corr_id)

        assert record.metadata == metadata


if __name__ == "__main__":
    # Run tests with: pytest test_correlation_tracker.py -v
    pytest.main([__file__, "-v", "--tb=short"])
