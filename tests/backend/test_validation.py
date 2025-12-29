"""Input validation tests for API models."""

import pytest
from app.models.alert import AlertItemCreate, AlertItemUpdate
from app.models.common import MetricType
from app.models.stock import MetricFilter, OperatorType, ScreenRequest
from app.models.watchlist import WatchlistItemCreate
from pydantic import ValidationError


class TestMetricValidation:
    """Test metric field validation (whitelist)."""

    def test_valid_metric_enum(self):
        """Valid metric Enum should pass."""
        filter = MetricFilter(
            metric=MetricType.PE_RATIO,
            operator=OperatorType.LT,
            value=15.0,
        )
        assert filter.metric == MetricType.PE_RATIO

    def test_valid_metric_string(self):
        """Valid metric string should be converted to Enum."""
        filter = MetricFilter(
            metric="pe_ratio",
            operator=OperatorType.LT,
            value=15.0,
        )
        assert filter.metric == MetricType.PE_RATIO

    def test_invalid_metric_rejected(self):
        """Invalid metric should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MetricFilter(
                metric="invalid_column",
                operator=OperatorType.LT,
                value=15.0,
            )
        assert "metric" in str(exc_info.value).lower()

    def test_sql_injection_attempt_blocked(self):
        """SQL injection attempt should be blocked."""
        with pytest.raises(ValidationError):
            MetricFilter(
                metric="pe_ratio; DROP TABLE companies;--",
                operator=OperatorType.LT,
                value=15.0,
            )

    def test_all_valid_metrics(self):
        """All defined metrics should be valid."""
        for metric in MetricType:
            filter = MetricFilter(
                metric=metric,
                operator=OperatorType.EQ,
                value=0.0,
            )
            assert filter.metric == metric


class TestValueRangeValidation:
    """Test numeric value range validation."""

    def test_value_within_bounds(self):
        """Value within bounds should pass."""
        filter = MetricFilter(
            metric=MetricType.PE_RATIO,
            operator=OperatorType.LT,
            value=15.0,
        )
        assert filter.value == 15.0

    def test_negative_value_allowed(self):
        """Negative values should be allowed (within bounds)."""
        filter = MetricFilter(
            metric=MetricType.PE_RATIO,
            operator=OperatorType.GT,
            value=-100.0,
        )
        assert filter.value == -100.0

    def test_value_exceeds_max(self):
        """Value exceeding max should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MetricFilter(
                metric=MetricType.PE_RATIO,
                operator=OperatorType.LT,
                value=1e15,  # Too large (max is 1e12)
            )
        assert "value" in str(exc_info.value).lower()

    def test_value_below_min(self):
        """Value below min should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MetricFilter(
                metric=MetricType.PE_RATIO,
                operator=OperatorType.LT,
                value=-1e15,  # Too small (min is -1e12)
            )
        assert "value" in str(exc_info.value).lower()


class TestUUIDValidation:
    """Test UUID format validation."""

    def test_valid_uuid_v4(self):
        """Valid UUID v4 should pass."""
        item = WatchlistItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
        )
        assert item.company_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_invalid_uuid_rejected(self):
        """Invalid UUID should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WatchlistItemCreate(
                company_id="not-a-valid-uuid",
            )
        assert "company_id" in str(exc_info.value).lower()

    def test_uuid_v1_rejected(self):
        """UUID v1 should be rejected (only v4 allowed)."""
        with pytest.raises(ValidationError):
            WatchlistItemCreate(
                company_id="550e8400-e29b-11d4-a716-446655440000",  # v1 (has 1 in third group)
            )

    def test_uppercase_uuid_rejected(self):
        """Uppercase UUID should be rejected (pattern expects lowercase)."""
        with pytest.raises(ValidationError):
            WatchlistItemCreate(
                company_id="550E8400-E29B-41D4-A716-446655440000",
            )


class TestStringLengthValidation:
    """Test string length validation."""

    def test_notes_within_limit(self):
        """Notes within limit should pass."""
        item = WatchlistItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
            notes="Short note",
        )
        assert item.notes == "Short note"

    def test_notes_at_limit(self):
        """Notes at exactly 1000 chars should pass."""
        notes = "x" * 1000
        item = WatchlistItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
            notes=notes,
        )
        assert len(item.notes) == 1000

    def test_notes_exceeds_limit(self):
        """Notes exceeding limit should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WatchlistItemCreate(
                company_id="550e8400-e29b-41d4-a716-446655440000",
                notes="x" * 1001,  # Exceeds 1000 char limit
            )
        assert "notes" in str(exc_info.value).lower()

    def test_notes_empty_allowed(self):
        """Empty notes should be allowed (None)."""
        item = WatchlistItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
            notes=None,
        )
        assert item.notes is None


class TestTargetPriceValidation:
    """Test target price validation."""

    def test_valid_target_price(self):
        """Valid target price should pass."""
        item = WatchlistItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
            target_price=150.50,
        )
        assert item.target_price == 150.50

    def test_zero_target_price_rejected(self):
        """Zero target price should be rejected (gt=0)."""
        with pytest.raises(ValidationError):
            WatchlistItemCreate(
                company_id="550e8400-e29b-41d4-a716-446655440000",
                target_price=0,
            )

    def test_negative_target_price_rejected(self):
        """Negative target price should be rejected."""
        with pytest.raises(ValidationError):
            WatchlistItemCreate(
                company_id="550e8400-e29b-41d4-a716-446655440000",
                target_price=-100,
            )

    def test_target_price_exceeds_max(self):
        """Target price exceeding max should be rejected."""
        with pytest.raises(ValidationError):
            WatchlistItemCreate(
                company_id="550e8400-e29b-41d4-a716-446655440000",
                target_price=2e9,  # Exceeds 1e9 limit
            )


class TestAlertValidation:
    """Test alert creation validation."""

    def test_valid_alert(self):
        """Valid alert should pass all validations."""
        alert = AlertItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
            metric=MetricType.RSI,
            operator="<=",
            value=30.0,
        )
        assert alert.metric == MetricType.RSI
        assert alert.value == 30.0

    def test_alert_with_string_metric(self):
        """Alert with string metric should be converted."""
        alert = AlertItemCreate(
            company_id="550e8400-e29b-41d4-a716-446655440000",
            metric="rsi",
            operator="<=",
            value=30.0,
        )
        assert alert.metric == MetricType.RSI

    def test_alert_invalid_metric(self):
        """Alert with invalid metric should be rejected."""
        with pytest.raises(ValidationError):
            AlertItemCreate(
                company_id="550e8400-e29b-41d4-a716-446655440000",
                metric="invalid_metric",
                operator="<=",
                value=30.0,
            )

    def test_alert_update_partial(self):
        """Partial alert update should pass."""
        update = AlertItemUpdate(
            is_active=False,
        )
        assert update.is_active is False
        assert update.metric is None


class TestScreenRequestValidation:
    """Test screen request validation."""

    def test_valid_screen_request(self):
        """Valid screen request should pass."""
        request = ScreenRequest(
            filters=[
                MetricFilter(
                    metric=MetricType.PE_RATIO,
                    operator=OperatorType.LT,
                    value=15,
                )
            ],
            limit=100,
        )
        assert len(request.filters) == 1

    def test_screen_request_empty_filters(self):
        """Screen request with empty filters should pass (default)."""
        request = ScreenRequest()
        assert request.filters == []

    def test_screen_request_limit_exceeds_max(self):
        """Screen request with limit > 500 should be rejected."""
        with pytest.raises(ValidationError):
            ScreenRequest(
                filters=[],
                limit=1000,  # Exceeds 500 max
            )

    def test_screen_request_negative_offset(self):
        """Screen request with negative offset should be rejected."""
        with pytest.raises(ValidationError):
            ScreenRequest(
                filters=[],
                offset=-1,
            )
