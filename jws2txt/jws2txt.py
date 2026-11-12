"""Provide a command-line interface for converting JASCO spectral files."""

from __future__ import annotations

import argparse
import csv
import logging
from enum import Enum
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .helpers.helpers import JWSFile

if TYPE_CHECKING:
    from collections.abc import Iterator
logger = logging.getLogger(__name__)

_TRUE_VALUES = frozenset({"yes", "true", "t", "y", "1"})
_FALSE_VALUES = frozenset({"no", "false", "f", "n", "0"})


class MetadataMode(str, Enum):
    """Define supported metadata export modes.

    Attributes:
        NONE: Disable metadata export.
        HEADER: Include metadata as comment lines in the text output.
        JSON: Export metadata to a separate JSON file.
        BOTH: Enable both header and JSON metadata exports.

    """

    NONE = "none"
    HEADER = "header"
    JSON = "json"
    BOTH = "both"

    def __str__(self) -> str:
        """Return the string value of the metadata mode."""
        return self.value

    @property
    def writes_header(self) -> bool:
        """Indicate whether metadata should be included in the text header.

        Returns:
            True for HEADER and BOTH modes; otherwise False.

        """
        return self in (MetadataMode.HEADER, MetadataMode.BOTH)

    @property
    def writes_json(self) -> bool:
        """Indicate whether metadata should be exported as JSON.

        Returns:
            True for JSON and BOTH modes; otherwise False.

        """
        return self in (MetadataMode.JSON, MetadataMode.BOTH)


_METADATA_ALIASES: dict[str, MetadataMode] = {
    "none": MetadataMode.NONE,
    "false": MetadataMode.NONE,
    "f": MetadataMode.NONE,
    "no": MetadataMode.NONE,
    "0": MetadataMode.NONE,
    "header": MetadataMode.HEADER,
    "head": MetadataMode.HEADER,
    "json": MetadataMode.JSON,
    "sidecar": MetadataMode.JSON,
    "both": MetadataMode.BOTH,
    "all": MetadataMode.BOTH,
    "true": MetadataMode.BOTH,
    "t": MetadataMode.BOTH,
    "yes": MetadataMode.BOTH,
    "1": MetadataMode.BOTH,
}

SUPPORTED_EXTENSIONS = frozenset({".jws", ".jwb"})


def iter_input_files(in_path: Path) -> Iterator[Path]:
    """Yield files eligible for conversion from a file or directory.

    If ``in_path`` is a file, yield it directly regardless of its
    extension. If it is a directory, recursively discover files with
    supported JASCO extensions. Discovered files are yielded in
    sorted path order.

    Args:
        in_path: Path to an input file or directory.

    Yields:
        Path: Path to an input file eligible for conversion.

    """
    if in_path.is_file():
        yield in_path
        return
    for path in sorted(in_path.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def str2bool(value: str | bool) -> bool:
    """Convert a string representation of a boolean into a bool."""
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()

    if normalized in _TRUE_VALUES:
        return True

    if normalized in _FALSE_VALUES:
        return False

    msg = f"Boolean value expected, got {value!r}."
    raise argparse.ArgumentTypeError(
        msg,
    )


def parse_metadata_mode(value: str) -> MetadataMode:
    """Parse metadata output mode, accepting case-insensitive aliases."""
    normalized = value.strip().lower()

    try:
        return _METADATA_ALIASES[normalized]
    except KeyError:
        choices = ", ".join(mode.value for mode in MetadataMode)
        msg = f"Invalid metadata mode: {value!r}. Choose from: {choices}."
        raise argparse.ArgumentTypeError(
            msg,
        ) from None


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert .jws and .jwb files into\
                    human-readable text files.",
    )

    parser.add_argument(
        "--in-path",
        type=Path,
        required=True,
        metavar="PATH",
        help="Path to a file or directory containing files to convert.",
    )

    parser.add_argument(
        "--out-dir",
        type=Path,
        metavar="DIR",
        help="Output directory. Defaults to the input file's parent "
        "or the input directory.",
    )

    parser.add_argument(
        "--delimiter",
        default="\t",
        help="Delimiter used in generated text files.",
    )

    parser.add_argument(
        "--comments",
        type=str2bool,
        choices=(True, False),
        default=True,
        metavar="BOOL",
        help="Write sample information (default: true).",
    )

    parser.add_argument(
        "--header",
        type=str2bool,
        choices=(True, False),
        default=True,
        metavar="BOOL",
        help="Write column headers (default: true).",
    )

    parser.add_argument(
        "--metadata",
        type=parse_metadata_mode,
        choices=list(MetadataMode),
        default=MetadataMode.NONE,
        metavar="MODE",
        help="Metadata export mode: none, header, json, or both.",
    )

    return parser


def convert_file(src: Path, out_dir: Path, args: argparse.Namespace) -> None:
    """Convert a JASCO file into delimited text and optional JSON output.

    Parse the source file and export its spectral data to a text file.
    Depending on the provided options, the output may also include
    sample information, column headers, and metadata.

    Metadata can additionally be exported to a separate JSON file.

    The output directory is created if it does not exist. Existing
    output text files are not overwritten.

    Args:
        src: Path to the source JWS or JWB file.
        out_dir: Directory where the converted files will be saved.
        args: Parsed command-line arguments controlling the export:
            metadata: Metadata export mode.
            comments: Whether to include sample information.
            header: Whether to include column headers.
            delimiter: Delimiter used between data columns.

    Raises:
        FileExistsError: If the output text file already exists.
        OSError: If the output directory cannot be created or an output
            file cannot be written.
        InvalidJascoDataError: If the source file contains invalid data.
        MissingYDataError: If the source file does not contain Y-Data.

    """
    out_dir.mkdir(parents=True, exist_ok=True)
    out_txt = out_dir / f"{src.stem}.txt"
    jws = JWSFile(src)

    with out_txt.open("x", newline="", encoding="utf-8") as f:
        if args.metadata.writes_header:
            f.writelines(f"{line}\n" for line in jws.iter_metadata_rows())

        rows = chain(
            jws.iter_comment_rows() if args.comments else (),
            jws.iter_header_rows() if args.header else (),
            jws.iter_data_rows(),
        )
        csv.writer(f, delimiter=args.delimiter).writerows(rows)

    if args.metadata.writes_json:
        jws.write_metadata_json(out_txt.with_suffix(".json"))


def main() -> Literal[0, 1]:
    """Run the file conversion CLI.

    Validates the input path, determines the output directory, and
    converts all discovered input files. Individual conversion failures
    are logged without interrupting the remaining conversions.

    Returns:
        0 if all conversions succeed, 1 if any conversion fails.

    """
    parser = create_argument_parser()
    args = parser.parse_args()
    in_path: Path = args.in_path

    if not in_path.exists():
        parser.error(f"{in_path} does not exist.")

    base_out = args.out_dir or (
        in_path.parent if in_path.is_file() else in_path
    )

    failures: list[Path] = []

    for src in iter_input_files(in_path):
        rel = Path() if in_path.is_file() else src.parent.relative_to(in_path)

        try:
            convert_file(src, base_out / rel, args)
        except Exception:
            logger.exception("Failed to convert '%s'", src)
            failures.append(src)

    if failures:
        logger.error(
            "Conversion finished with %d failure(s): %s",
            len(failures),
            ", ".join(str(path) for path in failures),
        )
        return 1

    return 0


if __name__ == "__main__":
    main()
