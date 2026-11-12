"""Read and export spectral data from JASCO JWS and JWB files.

This module provides functionality for parsing JASCO binary data files
(JWS and JWB), extracting spectral measurements
and exporting the resulting data to delimited text or JSON (metadata) files.

The parser reads the OLE file structure using olefile and
extracts the following streams:

DataInfo: Contains information about the spectral data, including
the number of data points, axis boundaries, axis increment, scan count,
and signal definitions.

Y-Data: Contains the spectral measurements stored as 32-bit
floating-point values.

The extracted measurements are converted into a structured representation
consisting of an independent X-axis and one or more corresponding
spectral datasets.

For multi-scan JWB files, the module generates individual column names
for each signal and scan. Signal names are resolved using
CHANNELS_DEFINITIONS where possible.

Sample information and additional file metadata are extracted through
the metadata utilities provided by the metadata module.

"""

from __future__ import annotations

import csv
import json
from contextlib import contextmanager
from pathlib import Path
from struct import unpack
from typing import (
    TYPE_CHECKING,
    Any,
    Generator,
    Iterator,
    Literal,
    Optional,
    Sequence,
    TextIO,
)

import olefile as ofio

from .metadata import extract_metadata, format_metadata_header

if TYPE_CHECKING:
    from os import PathLike

DATAINFO_FMT = "<LLLLLLdddLLLLdddd"

CHANNELS_DEFINITIONS = {
    536871427: "TIME",
    268435715: "WAVELENGTH",
    4097: "CD",
    8193: "HT VOLTAGE",
    3: "ABSORBANCE",
    14: "FLUORESCENCE",
}

MINIMUM_DATA_SIZE = 96
MetadataMode = Optional[Literal["header", "json", "both"]]


@contextmanager
def _open_text(
    target: str | PathLike[str] | TextIO,
) -> Generator[TextIO, None, None]:
    """Yield a writable text stream, opening paths exclusively."""
    if isinstance(
        target,
        TextIO,
    ):
        yield target
        return

    with Path(target).open(mode="a", newline="", encoding="utf-8") as stream:
        yield stream


class InvalidJascoDataError(Exception):
    """Raised when a JASCO file contains invalid or incomplete data."""

    def __init__(
        self,
        stream_name: str,
        actual_size: int,
        minimum_size: int,
    ) -> None:
        """Initialize the exception with stream size details."""
        super().__init__(
            f"{stream_name} must be at least {minimum_size} bytes, "
            f"but contains only {actual_size} bytes.",
        )


class InvalidXIncrementError(ValueError):
    """Raised when x_increment cannot be computed from the DataInfo header."""

    def __init__(self) -> None:
        """Initialize the exception with a fixed message."""
        super().__init__(
            "Cannot compute x_increment: identical first/last points.",
        )


class InvalidNPointsError(ValueError):
    """Raised when DataInfo declares an unusable number of points."""

    def __init__(self, npoints: object) -> None:
        """Initialize the exception with the offending value."""
        super().__init__(
            f"Invalid npoints: {npoints!r} (expected an integer >= 2).",
        )


class InvalidYDataLengthError(ValueError):
    """Raised when Y-Data size is not a whole number of float32 spectra."""

    def __init__(self, data_size: int, npoints: int) -> None:
        """Initialize the exception with the stream and spectrum sizes."""
        super().__init__(
            f"Invalid Y-Data length for float32 spectra: {data_size} bytes "
            f"is not a multiple of {npoints * 4} bytes "
            f"({npoints} points x 4 bytes).",
        )


class InvalidSpectraCountError(ValueError):
    """Raised when stored spectra do not match the DataInfo declaration."""

    def __init__(
        self,
        stored_spectra: int,
        scan_count: int,
        signal_count: int,
    ) -> None:
        """Initialize the exception with the declared and stored counts."""
        super().__init__(
            f"Y-Data contains {stored_spectra} spectra, but DataInfo "
            f"declares {scan_count} scans and {signal_count} signals",
        )


def frange(
    start: float,
    stop: float = 0,
    step: float = 1.0,
) -> Iterator[float]:
    """Return evenly spaced number over specified range.

    Args:
        start (float): The starting value of the sequence.
        stop (float): The last value of the sequence.
        step (float): The step for which the sequence is generated.

    """
    count = 0
    while True:
        float_range = start + count * step
        if (step > 0 and float_range >= stop) or (
            step < 0 and float_range <= stop
        ):
            break
        yield float_range
        count += 1


class MissingYDataError(Exception):
    """Raised when a JASCO file has no Y-Data stream."""

    def __init__(self, path: str) -> None:
        """Initialize the exception with the file path."""
        super().__init__(f"Y-Data stream not found in {path}.")


def _unique_codes(codes: Sequence[int]) -> tuple[int, ...]:
    """Return codes in order, dropping repeats."""
    return tuple(dict.fromkeys(codes))


def _multi_scan_header_names(
    codes: Sequence[int],
    scan_count: int,
    signal_count: int,
) -> list[str]:
    """Build neutral column labels for multi-scan JWB files.

    DataInfo does not establish whether the independent variable is
    temperature, concentration, or something else, so labels stay neutral.
    """
    names = ["WAVELENGTH"]
    for i in range(signal_count):
        signal = CHANNELS_DEFINITIONS.get(int(codes[i]), f"Signal_{i + 1}")
        names.extend(f"{signal}_scan{scan + 1}" for scan in range(scan_count))
    return names


class JWSFile:
    """Representation of the JASCO JWS or JWB file."""

    def __init__(self, path: str | PathLike[str]) -> None:
        """Initialize the JWSFile class.

        Args:
           path (str): Path to the JWS or JWB file

        """
        with ofio.OleFileIO(str(path)) as file:
            data_tuple = self._read_data_info(file, str(path))
            scan_count, signal_count = data_tuple[1], data_tuple[3]

            y_data = self._read_y_data(file, str(path))
            self.numchanels = self._count_spectra(
                len(y_data),
                scan_count,
                signal_count,
            )
            self.__unpack_y_data(
                y_data,
                datainfo_fmt="<" + "f" * self.npoints,
                num_chanels=self.numchanels,
            )

            # Preserve ordinary JWS header behaviour; only multi-scan JWB
            # files get per-scan labels.
            if scan_count > 1 and self.numchanels == scan_count * signal_count:
                self.header_names = _multi_scan_header_names(
                    data_tuple[10 : 10 + signal_count],
                    scan_count,
                    signal_count,
                )

            self.metadata = extract_metadata(
                ole=file,
                npoints=self.npoints,
                x_first=self.x_for_first_point,
                x_last=self.x_for_last_point,
                x_increment=self.x_increment,
                header_names=self.header_names,
                scan_count=scan_count,
            )

        sample_meta = self.metadata.get("sample", {})
        self.sample_name = sample_meta.get("name", "")
        self.comment = sample_meta.get("comment", "")

    def _read_data_info(
        self,
        file: ofio.OleFileIO,
        path: str,
    ) -> tuple[Any, ...]:
        """Parse the DataInfo stream and set the axis attributes."""
        raw = file.openstream("DataInfo").read()
        if len(raw) < MINIMUM_DATA_SIZE:
            raise InvalidJascoDataError(
                stream_name=path,
                actual_size=len(raw),
                minimum_size=MINIMUM_DATA_SIZE,
            )

        data_tuple = unpack(DATAINFO_FMT, raw[:MINIMUM_DATA_SIZE])
        self.numchanels = data_tuple[3]
        self.npoints = data_tuple[5]
        self.x_for_first_point = data_tuple[6]
        self.x_for_last_point = data_tuple[7]
        self.x_increment = data_tuple[8]

        if self.npoints < 2:
            raise InvalidNPointsError(self.npoints)

        if self.x_increment in (None, 0):
            span = self.x_for_last_point - self.x_for_first_point
            if span == 0:
                raise InvalidXIncrementError
            self.x_increment = span / (self.npoints - 1)

        self.header_codes = _unique_codes(data_tuple[9:13])
        self.header_names = [
            CHANNELS_DEFINITIONS.get(k, "undefined") for k in self.header_codes
        ]
        self.data_list = list(data_tuple)
        return data_tuple

    def _read_y_data(self, file: ofio.OleFileIO, path: str) -> bytes:
        """Read the Y-Data stream and check it holds whole float32 spectra."""
        if not file.exists("Y-Data"):
            raise MissingYDataError(path)

        y_data = file.openstream("Y-Data").read()
        if len(y_data) % (self.npoints * 4):
            raise InvalidYDataLengthError(len(y_data), self.npoints)
        return y_data

    def _count_spectra(
        self,
        y_data_size: int,
        scan_count: int,
        signal_count: int,
    ) -> int:
        """Return the number of stored spectra, validated against DataInfo.

        Some JWB files store scan_count * signal_count spectra
        (signal-major order).
        """
        stored = y_data_size // (self.npoints * 4)
        allowed = {signal_count, scan_count, scan_count * signal_count}
        if stored not in allowed or stored <= 0:
            raise InvalidSpectraCountError(stored, scan_count, signal_count)
        return stored

    def __unpack_y_data(
        self,
        y_data: bytes,
        datainfo_fmt: str,
        num_chanels: int,
    ) -> None:
        """Unpacks the Y-Data from the JWS file."""
        chunk_size = int(len(y_data) / num_chanels)
        data_chunked = [
            y_data[i : i + chunk_size]
            for i in range(0, len(y_data), chunk_size)
        ]
        unpacked_data = [
            unpack(datainfo_fmt, data_chunk) for data_chunk in data_chunked
        ]
        # generate x_data
        x_data = frange(
            self.x_for_first_point,
            self.x_for_last_point + self.x_increment,
            self.x_increment,
        )

        unpacked_data.insert(0, tuple(x_data))
        self.unpacked_data = unpacked_data

    def write_data(
        self,
        out_file: str | PathLike[str] | TextIO,
        *,
        delimiter: str = "\t",
    ) -> None:
        """Write spectral data to a delimited text file.

        Args:
            out_file: Target file path or writable stream.
            delimiter: Column delimiter (default tab).

        Raises:
            FileExistsError: If ``out_file`` is a path that already exists.

        """
        with _open_text(out_file) as f:
            csv.writer(f, delimiter=delimiter).writerows(
                self.iter_data_rows(),
            )

    def iter_comment_rows(self) -> Iterator[Sequence[Any]]:
        """Yield sample name and comment rows."""
        yield [self.sample_name]
        yield [self.comment]

    def iter_header_rows(self) -> Iterator[Sequence[str]]:
        """Yield column header row."""
        yield self._padded_header_names()

    def iter_data_rows(self) -> Iterator[Sequence[Any]]:
        """Yield spectral data rows."""
        yield from zip(*self.unpacked_data, strict=True)

    def write_metadata(
        self,
        out_file: str | PathLike[str] | TextIO,
    ) -> None:
        """Write metadata as comment lines to a text file."""
        with _open_text(out_file) as f:
            csv.writer(f, delimiter="\t").writerows(
                ([line] for line in self.iter_metadata_rows()),
            )

    def write_comments(
        self,
        out_file: str | PathLike[str] | TextIO,
    ) -> None:
        """Write metadata as comment lines to a text file."""
        with _open_text(out_file) as f:
            csv.writer(f, delimiter="\t").writerows(
                (line for line in self.iter_comment_rows()),
            )

    def write_header(
        self,
        out_file: str | PathLike[str] | TextIO,
    ) -> None:
        """Write metadata as comment lines to a text file."""
        with _open_text(out_file) as f:
            csv.writer(f, delimiter="\t").writerows(
                (line for line in self.iter_header_rows()),
            )

    def iter_metadata_rows(self) -> Iterator[str]:
        """Yield metadata as comment rows."""
        yield from format_metadata_header(self.metadata)

    def write_metadata_json(
        self,
        out_file: str | PathLike[str],
        indent: int = 2,
    ) -> None:
        """Write metadata as a JSON file."""
        with Path(out_file).open(mode="w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=indent, ensure_ascii=False)

    def _padded_header_names(self) -> list[str]:
        """Header names, repeating the last one to cover all data columns."""
        missing = len(self.unpacked_data) - len(self.header_names)
        return [*self.header_names, *[self.header_names[-1]] * max(missing, 0)]
