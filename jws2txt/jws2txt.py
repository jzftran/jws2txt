from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Iterator
from enum import Enum
from itertools import chain
from pathlib import Path

from .helpers.helpers import JWSFile

_TRUE_VALUES = frozenset({"yes", "true", "t", "y", "1"})
_FALSE_VALUES = frozenset({"no", "false", "f", "n", "0"})


class MetadataMode(str, Enum):
    NONE = "none"
    HEADER = "header"
    JSON = "json"
    BOTH = "both"

    def __str__(self) -> str:
        return self.value

    @property
    def writes_header(self) -> bool:
        return self in (MetadataMode.HEADER, MetadataMode.BOTH)

    @property
    def writes_json(self) -> bool:
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

    raise argparse.ArgumentTypeError(
        f"Boolean value expected, got {value!r}.",
    )


def parse_metadata_mode(value: str) -> MetadataMode:
    """Parse metadata output mode, accepting case-insensitive aliases."""
    normalized = value.strip().lower()

    try:
        return _METADATA_ALIASES[normalized]
    except KeyError:
        choices = ", ".join(mode.value for mode in MetadataMode)
        raise argparse.ArgumentTypeError(
            f"Invalid metadata mode: {value!r}. Choose from: {choices}.",
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


def main() -> int:
    parser = create_argument_parser()
    args = parser.parse_args()
    in_path: Path = args.in_path

    if not in_path.exists():
        parser.error(f"{in_path} does not exist.")

    base_out = args.out_dir or (
        in_path.parent if in_path.is_file() else in_path
    )

    failures = 0
    for src in iter_input_files(in_path):
        rel = Path() if in_path.is_file() else src.parent.relative_to(in_path)
        try:
            convert_file(src, base_out / rel, args)
        except Exception as exc:  # keep going, report at the end
            failures += 1
            print(f"Failed: {src}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    main()
