"""Tests for jws2txt metadata extraction and writing."""

import argparse
import json

import pytest

from jws2txt.jws2txt import parse_metadata_mode


class TestMetadataStructure:
    """Tests for metadata structure and content."""

    def test_metadata_structure(self, hg_file) -> None:
        """Test metadata has expected top-level structure."""
        meta = hg_file.metadata
        assert "file_info" in meta
        assert "instrument" in meta
        assert "software" in meta
        assert "operator" in meta
        assert "sample" in meta
        assert "parameters" in meta

    def test_metadata_instrument_info(self, hg_file) -> None:
        """Test instrument metadata is correctly extracted."""
        meta = hg_file.metadata
        assert meta["instrument"]["model"] == "J-1500"
        assert meta["instrument"]["serial_number"] == "A005461638"

    def test_metadata_operator_info(self, hg_file) -> None:
        """Test operator metadata is correctly extracted."""
        meta = hg_file.metadata
        assert meta["operator"]["institution"] == "Uniwersytet Wroclawski"

    def test_metadata_sample_info(self, hg_file) -> None:
        """Test sample metadata is correctly extracted."""
        meta = hg_file.metadata
        assert meta["sample"]["name"] == "HK14_CN"
        assert meta["sample"]["comment"] == "1mm"
        assert meta["sample"]["description"] == "TRIS 10mM NaF 5mM CN 50uM Hk14"

    def test_metadata_parameters(self, hg_file) -> None:
        """Test measurement parameters are correctly extracted."""
        meta = hg_file.metadata
        params = meta["parameters"]
        assert params["sensitivity"] == "200 mdeg/1.0 dOD"
        assert params["bandwidth"] == "2.00 nm"
        assert params["response"] == "2 sec"
        assert params["scanning_speed"] == "200 nm/min"
        assert params["accumulations"] == 3
        assert params["pathlength"] == "100 um"
        assert params["scanning_mode"] == "Continuous"

    def test_sample_names_populated_from_metadata(
        self,
        hg_file,
        fl_file,
        cd_file,
        jwb_file,
    ) -> None:
        """Test sample_name and comment are populated from metadata."""
        assert hg_file.sample_name == "HK14_CN"
        assert hg_file.comment == "1mm"
        assert fl_file.sample_name == "photonic wire"
        assert fl_file.comment == ""
        assert cd_file.sample_name == "1A"
        assert cd_file.comment == ""
        assert jwb_file.sample_name == ""
        assert jwb_file.comment == ""


class TestFluorescenceMetadata:
    """Tests for fluorescence-specific metadata."""

    def test_fluorescence_metadata(self, fl_file) -> None:
        """Test fluorescence metadata extraction."""
        meta = fl_file.metadata
        params = meta["parameters"]
        assert params["bandwidth"] == "EX 10 nm, EM 1 nm"
        assert params["ex_bandwidth"] == "10 nm"
        assert params["em_bandwidth"] == "1 nm"
        assert params["excitation_wavelength"] == "380 nm"
        assert params["response"] == "0.1 sec"
        assert params["photometric_mode"] == "FLUORESCENCE"


class TestJWBMultiScanMetadata:
    """Tests for JWB multi-scan metadata."""

    def test_jwb_multi_scan_metadata(self, jwb_file) -> None:
        """Test JWB multi-scan metadata extraction."""
        meta = jwb_file.metadata
        assert meta["instrument"]["model"] == "V-730"
        assert meta["instrument"]["serial_number"] == "B184861798"
        assert meta["operator"]["institution"] == "北海道大学"

        temp_ctrl = meta["parameters"].get("temperature_control", {})
        assert temp_ctrl.get("scans") == 8
        assert temp_ctrl.get("start_temperature") == 25.0
        assert temp_ctrl.get("end_temperature") == 60.0
        assert temp_ctrl.get("temperature_step") == 5.0
        assert temp_ctrl.get("heating_rate") == 1.0
        assert temp_ctrl.get("temperature_tolerance") == 0.1
        assert temp_ctrl.get("stabilization_time") == 20.0
        assert temp_ctrl.get("post_run_temperature") == 300.0
        assert len(temp_ctrl.get("scan_temperatures", [])) == 8
        assert temp_ctrl["scan_temperatures"][0] == pytest.approx(
            24.98,
            abs=0.1,
        )
        assert temp_ctrl["scan_temperatures"][-1] == pytest.approx(
            60.01,
            abs=0.1,
        )


class TestParseMetadataMode:
    """Tests for parse_metadata_mode function (integration test)."""

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
            ("header", "header"),
            ("HEADER", "header"),
            ("Header", "header"),
            ("head", "header"),
            ("json", "json"),
            ("JSON", "json"),
            ("Json", "json"),
            ("sidecar", "json"),
            ("both", "both"),
            ("BOTH", "both"),
            ("Both", "both"),
            ("all", "both"),
            ("true", "both"),
            ("TRUE", "both"),
            ("yes", "both"),
            ("1", "both"),
        ],
    )
    def test_parse_metadata_mode_values(self, value, expected) -> None:
        """Test parse_metadata_mode handles all valid values."""
        assert parse_metadata_mode(value) == expected

    def test_parse_metadata_mode_invalid(self) -> None:
        """Test parse_metadata_mode raises for invalid values."""
        with pytest.raises(argparse.ArgumentTypeError):
            parse_metadata_mode("invalid_mode")


class TestMetadataWriting:
    """Tests for metadata writing to text files."""

    def test_metadata_default_off(self, hg_file, tmp_path) -> None:
        """Test default metadata=False writes no # comments."""
        test_txt = tmp_path / "test_out.txt"
        hg_file.write_comments(test_txt)
        hg_file.write_header(test_txt)
        hg_file.write_data(test_txt)
        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()

        assert lines[0] == "HK14_CN"
        assert lines[1] == "1mm"
        assert lines[2].startswith("WAVELENGTH")
        assert not any(l.startswith("# ") for l in lines)

    def test_metadata_header_mode(self, hg_file, tmp_path) -> None:
        """Test metadata='header' writes #-prefixed metadata at top."""
        test_txt = tmp_path / "test_out.txt"
        hg_file.write_metadata(test_txt)
        hg_file.write_comments(test_txt)
        hg_file.write_header(test_txt)
        hg_file.write_data(test_txt)
        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()

        assert lines[0].startswith("# --- Measurement Information ---")
        header_comments = [l for l in lines if l.startswith("# ")]
        assert any("J-1500" in l for l in header_comments)
        assert any("Uniwersytet Wroclawski" in l for l in header_comments)
        assert any("Accumulations: 3" in l for l in header_comments)

        # Sample comments appear after metadata header
        first_non_hash = next(
            i for i, l in enumerate(lines) if not l.startswith("# ")
        )
        assert lines[first_non_hash] == "HK14_CN"
        assert lines[first_non_hash + 1] == "1mm"
        assert lines[first_non_hash + 2].startswith("WAVELENGTH")

    def test_metadata_json_mode(self, hg_file, tmp_path) -> None:
        """Test writing of companion json, no # comments in text."""
        test_txt = tmp_path / "test_out.txt"
        test_json = tmp_path / "test_out.json"

        hg_file.write_comments(test_txt)
        hg_file.write_header(test_txt)
        hg_file.write_data(test_txt)
        hg_file.write_metadata_json(test_json)
        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()

        assert lines[0] == "HK14_CN"
        assert not any(l.startswith("# ") for l in lines)

        assert test_json.exists()
        saved_meta = json.loads(test_json.read_text(encoding="utf-8"))
        assert saved_meta["instrument"]["model"] == "J-1500"

    def test_metadata_both_mode(self, hg_file, tmp_path) -> None:
        """Test metadata='both' writes both # comments and json sidecar."""
        test_txt = tmp_path / "test_out.txt"
        test_json = tmp_path / "test_out.json"
        hg_file.write_metadata(test_txt)
        hg_file.write_comments(test_txt)
        hg_file.write_header(test_txt)
        hg_file.write_data(test_txt)
        hg_file.write_metadata_json(test_json)
        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()

        assert lines[0].startswith("# --- Measurement Information ---")
        assert test_json.exists()

    def test_metadata_boolean_true(self, hg_file, tmp_path) -> None:
        """Test metadata=True writes both header and json."""
        test_txt = tmp_path / "test_out.txt"
        test_json = tmp_path / "test_out.json"
        hg_file.write_metadata(test_txt)
        hg_file.write_comments(test_txt)
        hg_file.write_header(test_txt)
        hg_file.write_data(test_txt)
        hg_file.write_metadata_json(test_json)
        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()

        assert lines[0].startswith("# --- Measurement Information ---")
        assert test_json.exists()

    def test_column_header_flag(self, hg_file, tmp_path) -> None:
        """Test write_header=False suppresses column headers row."""
        test_txt = tmp_path / "test_out.txt"
        hg_file.write_comments(test_txt)
        hg_file.write_data(test_txt)
        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()

        assert lines[0] == "HK14_CN"
        assert lines[1] == "1mm"
        assert not any("WAVELENGTH" in l for l in lines)


class TestMetadataJSONWriting:
    """Tests for dedicated metadata JSON writing."""

    def test_write_metadata_json(self, hg_file, tmp_path) -> None:
        """Test write_metadata_json creates valid JSON file."""
        test_json = tmp_path / "metadata.json"
        hg_file.write_metadata_json(test_json)

        assert test_json.exists()
        saved_meta = json.loads(test_json.read_text(encoding="utf-8"))
        assert saved_meta["instrument"]["model"] == "J-1500"
        assert saved_meta["sample"]["name"] == "HK14_CN"

    def test_write_metadata_json_with_indent(self, hg_file, tmp_path) -> None:
        """Test write_metadata_json respects indent parameter."""
        test_json = tmp_path / "metadata.json"
        hg_file.write_metadata_json(test_json, indent=4)

        content = test_json.read_text(encoding="utf-8")
        assert content.startswith("{\n    ")  # 4-space indent


class TestMetadataHeaderWriting:
    """Tests for dedicated metadata header writing."""

    def test_write_metadata_header(self, hg_file, tmp_path) -> None:
        """Test write_metadata creates comment lines."""
        test_txt = tmp_path / "metadata.txt"
        hg_file.write_metadata(test_txt)

        lines = test_txt.read_text(encoding="utf-8").strip().splitlines()
        assert lines[0] == "# --- Measurement Information ---"
        assert any("J-1500" in l for l in lines)
        assert any("Uniwersytet Wroclawski" in l for l in lines)
