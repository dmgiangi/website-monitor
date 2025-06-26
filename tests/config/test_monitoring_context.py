"""
Tests for the MonitoringContext class in the website_monitor.config package.

This module contains tests for the MonitoringContext class, which is a NamedTuple
that holds all configuration parameters for the monitoring system.
"""

import pytest

from website_monitor.config.monitoring_context import MonitoringContext


class TestMonitoringContext:
    """Tests for the MonitoringContext class."""

    def test_monitoring_context_should_initialize_with_correct_values(self) -> None:
        """
        Test that MonitoringContext initializes with the correct values.

        This test verifies that when a MonitoringContext is created with specific
        values, those values are correctly stored in the object's attributes.
        """
        # Arrange
        dsn = "postgresql://user:password@localhost:5432/db"
        worker_id = "worker-123"
        logging_type = "dev"
        logging_config_file = "logging.json"
        queue_size = 100
        batch_size = 10
        worker_number = 5
        db_pool_size = 20
        max_timeout = 30
        raise_for_status = True

        # Act
        context = MonitoringContext(
            dsn=dsn,
            worker_id=worker_id,
            logging_type=logging_type,
            logging_config_file=logging_config_file,
            queue_size=queue_size,
            batch_size=batch_size,
            worker_number=worker_number,
            db_pool_size=db_pool_size,
            max_timeout=max_timeout,
            raise_for_status=raise_for_status,
        )

        # Assert
        assert context.dsn == dsn
        assert context.worker_id == worker_id
        assert context.logging_type == logging_type
        assert context.logging_config_file == logging_config_file
        assert context.queue_size == queue_size
        assert context.batch_size == batch_size
        assert context.worker_number == worker_number
        assert context.db_pool_size == db_pool_size
        assert context.max_timeout == max_timeout
        assert context.raise_for_status == raise_for_status

    def test_monitoring_context_should_be_immutable(self) -> None:
        """
        Test that MonitoringContext is immutable.

        This test verifies that once a MonitoringContext is created, its attributes
        cannot be modified, as it is a NamedTuple which is immutable.
        """
        # Arrange
        context = MonitoringContext(
            dsn="postgresql://user:password@localhost:5432/db",
            worker_id="worker-123",
            logging_type="dev",
            logging_config_file="logging.json",
            queue_size=100,
            batch_size=10,
            worker_number=5,
            db_pool_size=20,
            max_timeout=30,
            raise_for_status=True,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            context.dsn = "new-dsn"  # This should raise an AttributeError

    def test_monitoring_context_should_support_equality_comparison(self) -> None:
        """
        Test that MonitoringContext supports equality comparison.

        This test verifies that two MonitoringContext instances with the same
        attribute values are considered equal, and instances with different
        values are considered not equal.
        """
        # Arrange
        context1 = MonitoringContext(
            dsn="postgresql://user:password@localhost:5432/db",
            worker_id="worker-123",
            logging_type="dev",
            logging_config_file="logging.json",
            queue_size=100,
            batch_size=10,
            worker_number=5,
            db_pool_size=20,
            max_timeout=30,
            raise_for_status=True,
        )

        context2 = MonitoringContext(
            dsn="postgresql://user:password@localhost:5432/db",
            worker_id="worker-123",
            logging_type="dev",
            logging_config_file="logging.json",
            queue_size=100,
            batch_size=10,
            worker_number=5,
            db_pool_size=20,
            max_timeout=30,
            raise_for_status=True,
        )

        context3 = MonitoringContext(
            dsn="postgresql://different:password@localhost:5432/db",
            worker_id="worker-123",
            logging_type="dev",
            logging_config_file="logging.json",
            queue_size=100,
            batch_size=10,
            worker_number=5,
            db_pool_size=20,
            max_timeout=30,
            raise_for_status=True,
        )

        # Act & Assert
        assert context1 == context2  # Same values should be equal
        assert context1 != context3  # Different values should not be equal
