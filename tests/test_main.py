"""Tests for jws2txt main module."""

from argparse import ArgumentTypeError

import pytest

from jws2txt.jws2txt import parse_metadata_mode, str2bool


class TestStr2Bool:
    """Tests for str2bool function."""

    @pytest.mark.parametrize(
        "value",
        ["y", "yes", "true", "t", "1", "Y", "YES", "TRUE", "T"],
    )
    def test_str2bool_true(self, value) -> None:
        """Test str2bool returns True for truthy values."""
        assert str2bool(value) is True

    @pytest.mark.parametrize(
        "value",
        ["n", "no", "false", "f", "0", "N", "NO", "FALSE", "F"],
    )
    def test_str2bool_false(self, value) -> None:
        """Test str2bool returns False for falsy values."""
        assert str2bool(value) is False

    def test_str2bool_bool_passthrough(self) -> None:
        """Test str2bool passes through bool values."""
        assert str2bool(True) is True
        assert str2bool(False) is False

    def test_str2bool_invalid(self) -> None:
        """Test str2bool raises ArgumentTypeError for invalid values."""
        with pytest.raises(ArgumentTypeError):
            str2bool("blurb")
        with pytest.raises(ArgumentTypeError):
            str2bool("maybe")
        with pytest.raises(ArgumentTypeError):
            str2bool("")


class TestParseMetadataMode:
    """Tests for parse_metadata_mode function."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("none", "none"),
            ("NONE", "none"),
            ("None", "none"),
            ("false", "none"),
            ("FALSE", "none"),
            ("0", "none"),
            ("no", "none"),
            ("f", "none"),
        ],
    )
    def test_parse_metadata_mode_none(self, value, expected) -> None:
        """Test parse_metadata_mode returns 'none' for none values."""
        assert parse_metadata_mode(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("header", "header"),
            ("HEADER", "header"),
            ("Header", "header"),
            ("head", "header"),
        ],
    )
    def test_parse_metadata_mode_header(self, value, expected) -> None:
        """Test parse_metadata_mode returns 'header' for header values."""
        assert parse_metadata_mode(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("json", "json"),
            ("JSON", "json"),
            ("Json", "json"),
            ("sidecar", "json"),
        ],
    )
    def test_parse_metadata_mode_json(self, value, expected) -> None:
        """Test parse_metadata_mode returns 'json' for json values."""
        assert parse_metadata_mode(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("both", "both"),
            ("BOTH", "both"),
            ("Both", "both"),
            ("all", "both"),
            ("true", "both"),
            ("TRUE", "both"),
            ("yes", "both"),
            ("1", "both"),
            ("t", "both"),
        ],
    )
    def test_parse_metadata_mode_both(self, value, expected) -> None:
        """Test parse_metadata_mode returns 'both' for both values."""
        assert parse_metadata_mode(value) == expected

    def test_parse_metadata_mode_invalid(self) -> None:
        """Test parse_metadata_mode raises ArgumentTypeError for invalid values."""  # noqa: E501
        with pytest.raises(ArgumentTypeError):
            parse_metadata_mode("invalid_mode")
        with pytest.raises(ArgumentTypeError):
            parse_metadata_mode("")
        with pytest.raises(ArgumentTypeError):
            parse_metadata_mode("header_only")
