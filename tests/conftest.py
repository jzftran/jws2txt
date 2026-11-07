"""Shared pytest fixtures for jws2txt tests."""

import pytest

import jws2txt


@pytest.fixture(scope="session")
def sample_files_dir() -> str:
    """Path to the test files directory."""
    return "tests/files"


@pytest.fixture(scope="session")
def hg_file(sample_files_dir):
    """JWSFile for 001Hg.jws (3 channels: WAVELENGTH, CD, HT VOLTAGE, ABSORBANCE)."""
    return jws2txt.JWSFile(f"{sample_files_dir}/001Hg.jws")


@pytest.fixture(scope="session")
def jwb_file(sample_files_dir):
    """JWSFile for 2022_05_14-1.jwb (multi-scan JWB file, 8 channels)."""
    return jws2txt.JWSFile(f"{sample_files_dir}/2022_05_14-1.jwb")


@pytest.fixture(scope="session")
def fl_file(sample_files_dir):
    """JWSFile for sample_fluorescence.jws (single channel fluorescence)."""
    return jws2txt.JWSFile(f"{sample_files_dir}/sample_fluorescence.jws")


@pytest.fixture(scope="session")
def cd_file(sample_files_dir):
    """JWSFile for sample_CD_HT_Abs.jws (CD with HT and Abs)."""
    return jws2txt.JWSFile(f"{sample_files_dir}/sample_CD_HT_Abs.jws")
