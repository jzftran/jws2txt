"""Tests for jws2txt helpers module."""

import csv

import pytest

from jws2txt.helpers.helpers import frange


class TestJWSFile:
    """Tests for JWSFile class."""

    def test_three_channels_creation(self, hg_file) -> None:
        """Test 3-channel JWS file creation and initialization."""
        assert hg_file.numchanels == 3
        assert hg_file.npoints == 1201
        assert hg_file.x_for_first_point == 320.0
        assert hg_file.x_for_last_point == 200.0
        assert hg_file.x_increment == -0.1
        assert hg_file.header_codes == (268435715, 4097, 8193, 3)
        assert hg_file.header_names == [
            "WAVELENGTH",
            "CD",
            "HT VOLTAGE",
            "ABSORBANCE",
        ]
        assert hg_file.data_list == [
            3,
            1,
            0,
            3,
            1,
            1201,
            320.0,
            200.0,
            -0.1,
            268435715,
            4097,
            8193,
            3,
            8.6939493804496e-311,
            200.0,
            1.0,
            320.0,
        ]
        assert hg_file.sample_name == "HK14_CN"
        assert hg_file.comment == "1mm"
        # test x-axis and 3 channels
        assert hg_file.unpacked_data[0][2] == 319.8
        assert hg_file.unpacked_data[1][2] == pytest.approx(0.1975005567073822)
        assert hg_file.unpacked_data[2][2] == pytest.approx(206.2129669189453)
        assert hg_file.unpacked_data[3][2] == pytest.approx(
            0.11851496249437332,
        )

    def test_single_channel(self, fl_file) -> None:
        """Test single channel JWS file creation and initialization."""
        assert fl_file.numchanels == 1
        assert fl_file.npoints == 301
        assert fl_file.x_for_first_point == 400.0
        assert fl_file.x_for_last_point == 700.0
        assert fl_file.x_increment == 1
        assert fl_file.header_codes == (268435715, 14)
        assert fl_file.header_names == ["WAVELENGTH", "FLUORESCENCE"]
        assert fl_file.data_list == [
            3,
            1,
            0,
            1,
            1,
            301,
            400.0,
            700.0,
            1.0,
            268435715,
            14,
            268435715,
            14,
            400.0,
            700.0,
            700.0,
            0.0,
        ]
        assert fl_file.sample_name == "photonic wire"
        assert fl_file.comment == ""
        # test x-axis and channel
        assert fl_file.unpacked_data[0][2] == 402.0
        assert fl_file.unpacked_data[1][2] == pytest.approx(24.556852340698242)

    def test_jwb_file_creation(self, jwb_file) -> None:
        """Test multi-scan JWB file creation and initialization."""
        assert jwb_file.numchanels == 8
        assert jwb_file.npoints == 1001
        assert jwb_file.x_for_first_point == 900.0
        assert jwb_file.x_for_last_point == 400.0
        assert jwb_file.x_increment == -0.5
        assert jwb_file.header_codes == (268435715, 3, 0, 8)
        assert jwb_file.header_names == ["WAVELENGTH"] + [
            f"ABSORBANCE_scan{i}" for i in range(1, 9)
        ]
        assert jwb_file.data_list == [
            3,
            8,
            1,
            1,
            1,
            1001,
            900.0,
            400.0,
            -0.5,
            268435715,
            3,
            0,
            8,
            24.979999542236328,
            60.0099983215332,
            0.0,
            2.00000035762821,
        ]
        assert jwb_file.sample_name == ""
        assert jwb_file.comment == ""
        # test x-axis and 7th channel
        assert jwb_file.unpacked_data[0][2] == 899.0
        assert jwb_file.unpacked_data[7][2] == pytest.approx(
            0.07367147505283356,
        )

    def test_writing(self, hg_file, tmp_path) -> None:
        """Test writing data to a text file."""
        test_file = tmp_path / "test_output.txt"
        hg_file.write_data(test_file)

        with open(test_file, newline="") as f:
            reader = csv.reader(f, dialect="excel")
            first_row = next(reader)
            # First row should be the data (tab-delimited in a single cell due to csv reader)
            assert len(first_row) == 1
            # Verify the data contains expected values
            data_parts = first_row[0].split("\t")
            assert len(data_parts) == 4
            assert float(data_parts[0]) == pytest.approx(320.0, abs=0.1)
            assert float(data_parts[1]) == pytest.approx(0.196, abs=0.01)
            assert float(data_parts[2]) == pytest.approx(206.18, abs=0.1)
            assert float(data_parts[3]) == pytest.approx(0.118, abs=0.01)


class TestFrange:
    """Tests for frange function."""

    @pytest.mark.parametrize(
        ("start", "stop", "step", "expected"),
        [
            (1, 2, 0.2, (1.0, 1.2, 1.4, 1.6, 1.8)),
            (
                2,
                0.9,
                -0.1,
                (
                    2.0,
                    1.9,
                    1.8,
                    1.7,
                    1.6,
                    1.5,
                    1.4,
                    1.2999999999999998,
                    1.2,
                    1.1,
                    1.0,
                ),
            ),
        ],
    )
    def test_frange(self, start, stop, step, expected) -> None:
        """Test frange with various parameters."""
        assert tuple(frange(start, stop, step)) == expected

    def test_frange_empty(self) -> None:
        """Test frange with empty range."""
        assert tuple(frange(1, 1, 0.1)) == ()
        assert tuple(frange(1, 0, 0.1)) == ()

    def test_frange_single_step(self) -> None:
        """Test frange with single step."""
        assert tuple(frange(0, 1, 1)) == (0.0,)
