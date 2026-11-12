"""Extract and format metadata from JASCO JWS/JWB (OLE) files."""

from __future__ import annotations

import datetime
import re
import struct
from typing import TYPE_CHECKING, Any, Callable, Sequence

if TYPE_CHECKING:
    from olefile import OleFileIO

OLE_EPOCH = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)

WAVELENGTH_CODE = 268435715  # DataInfo code for a wavelength axis
_INSTRUMENT_PREFIXES = ("J-", "V-", "FP-")

_KNOWN_PREFIXES = (
    *_INSTRUMENT_PREFIXES,
    "PM-",
    "RSC-",
    "CDF-",
    "PAC-",
    "ETCS-",
    "SCE-",
    "V700",
)
_VARIANT_FORMATS = {2: "<h", 3: "<i", 5: "<d", 7: "<d", 11: "<h", 19: "<I"}

# parameter name -> property IDs to try, in order (all must be non-empty text)
_TEXT_PARAMS = {
    "sensitivity": (20, 88),
    "pathlength": (25,),
    "sample_description": (42,),
    "start_time": (203, 92),
    "end_time": (204, 190, 93, 90),
}

# ramp field -> property IDs to try, in order (all must be numeric)
_RAMP_FIELDS = {
    "start_temperature": (404,),
    "end_temperature": (405,),
    "temperature_step": (402,),
    "heating_rate": (410,),
    "temperature_tolerance": (861, 662),
    "stabilization_time": (803, 603),
    "post_run_temperature": (401,),
}


_FILE_FIELDS = (
    ("original_file", "Original File"),
    ("created", "Created"),
    ("modified", "Modified"),
)
_OPERATOR_FIELDS = (("institution", "Institution / Operator"),)
_SOFTWARE_FIELDS = (("software", "Software"),)
_SAMPLE_FIELDS = (
    ("name", "Sample Name"),
    ("comment", "Sample Comment"),
    ("description", "Sample Description"),
)
_PARAM_FIELDS = (
    ("photometric_mode", "Photometric Mode"),
    ("scanning_mode", "Scanning Mode"),
    ("scanning_speed", "Scanning Speed"),
    ("response", "D.I.T. (Response)"),
    ("bandwidth", "Bandwidth"),
    ("excitation_wavelength", "Excitation Wavelength"),
    ("sensitivity", "Sensitivity"),
    ("pathlength", "Pathlength"),
    ("accumulations", "Accumulations"),
    ("baseline_correction", "Baseline Correction"),
)


# --------------------------------------------------------------------------
# Low-level helpers
# --------------------------------------------------------------------------


def parse_ole_date(days: float) -> str | None:
    """Convert an OLE Automation DATE to ``YYYY-MM-DD HH:MM:SS``.

    Args:
        days: Days since December 30, 1899, with the time of day as the
            fractional part.

    Returns:
        The formatted date-time, or ``None`` if ``days`` is not positive or
        cannot be converted.

    """
    if days <= 0:
        return None
    try:
        dt = OLE_EPOCH + datetime.timedelta(days=days)
    except (OverflowError, ValueError):
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _decode(chunk: bytes) -> str:
    """Decode a UTF-16LE length-prefixed string, dropping trailing NULs."""
    return chunk.decode("utf-16le", errors="ignore").rstrip("\x00")


def _fixed_field(data: bytes, start: int, length: int = 32) -> str:
    """Decode a fixed-width UTF-16LE field, stopping at the first NUL."""
    chunk = data[start : start + length]
    return chunk.decode("utf-16le", errors="ignore").split("\x00")[0].strip()


def _is_text(value: Any) -> bool:  # noqa: ANN401
    return isinstance(value, str) and bool(value.strip())


def _is_number(v: Any) -> bool:  # noqa: ANN401
    return isinstance(v, (int, float))


def _is_positive_int(v: Any) -> bool:  # noqa: ANN401
    return isinstance(v, int) and v > 0


def _first(
    props: dict[int, Any],
    pids: Sequence[int],
    test: Callable[[Any], bool] = lambda _: True,
) -> Any:  # noqa: ANN401
    """Return the value of the first property in ``pids`` that passes ``test``."""  # noqa: E501
    for pid in pids:
        v = props.get(pid)
        if v is not None and test(v):
            return v
    return None


# --------------------------------------------------------------------------
# Simple stream parsers
# --------------------------------------------------------------------------


def parse_base_info(data: bytes) -> dict[str, Any]:
    """Parse BaseInfo stream containing original file path and timestamps."""
    if len(data) < 25:
        return {}
    (str_len,) = struct.unpack_from("<I", data, 21)
    end = 25 + str_len
    if end > len(data):
        return {}

    res: dict[str, Any] = {}
    if orig_path := _decode(data[25:end]):
        res["original_file"] = orig_path
    if end + 16 <= len(data):
        created, modified = struct.unpack_from("<dd", data, end)
        if created_dt := parse_ole_date(created):
            res["created"] = created_dt
        if modified_dt := parse_ole_date(modified):
            res["modified"] = modified_dt
    return res


def parse_header(data: bytes) -> dict[str, Any]:
    """Parse Header stream containing software name, version, and platform."""
    if len(data) < 120:
        return {}
    prog, ver, plat = (_fixed_field(data, o) for o in (8, 56, 88))
    comp = _fixed_field(data, 120) if len(data) >= 152 else ""

    res: dict[str, Any] = {}
    if prog:
        res["software"] = f"{prog} {ver}".strip()
    if plat:
        res["platform"] = plat
    if comp:
        res["compiler"] = comp
    return res


def parse_user_info(data: bytes) -> dict[str, Any]:
    """Parse UserInfo stream containing operator and institution."""
    if len(data) < 52:
        return {}
    (slen,) = struct.unpack_from("<I", data, 48)
    if (
        slen > 0
        and 52 + slen <= len(data)
        and (inst := _decode(data[52 : 52 + slen]).strip())
    ):
        return {"institution": inst}
    return {}


def parse_sample_info(data: bytes) -> dict[str, str]:
    """Parse SampleInfo stream to extract sample name and comment."""
    result = {"name": "", "comment": ""}
    if len(data) < 8:
        return result

    (name_len,) = struct.unpack_from("<I", data, 4)
    pos = 8
    result["name"] = _decode(data[pos : pos + name_len])
    pos += name_len
    if pos + 4 <= len(data):
        (comment_len,) = struct.unpack_from("<I", data, pos)
        pos += 4
        result["comment"] = _decode(data[pos : pos + comment_len])
    return result


# --------------------------------------------------------------------------
# ModuleInfo (heuristic: guesses model/serial pairs from string patterns)
# --------------------------------------------------------------------------


def _extract_module_strings(data: bytes) -> list[str]:
    """Scan for length-prefixed, NUL-terminated printable UTF-16LE strings."""
    strings: list[str] = []
    idx = 4
    while idx < len(data) - 4:
        (slen,) = struct.unpack_from("<I", data, idx)
        if 2 < slen <= 64 and slen % 2 == 0 and idx + 4 + slen <= len(data):
            try:
                s = data[idx + 4 : idx + 4 + slen].decode("utf-16le")
            except UnicodeDecodeError:
                s = ""
            if s.endswith("\x00"):
                clean = s.rstrip("\x00").strip()
                if clean and all(32 <= ord(c) < 127 for c in clean):
                    strings.append(clean)
                    idx += 4 + slen
                    continue
        idx += 1
    return strings


def parse_module_info(data: bytes) -> dict[str, Any]:
    """Parse ModuleInfo stream: hardware model, serial, and accessories."""
    if len(data) < 8:
        return {}
    strings = _extract_module_strings(data)
    if not strings:
        return {}

    # Deduplicate consecutive identical names
    dedup = [s for i, s in enumerate(strings) if i == 0 or s != strings[i - 1]]

    res: dict[str, Any] = {}
    accessories: list[dict[str, str]] = []
    main_model: str | None = None
    main_serial: str | None = None

    i = 0
    while i < len(dedup):
        item = dedup[i]
        next_item = dedup[i + 1] if i + 1 < len(dedup) else ""
        next_is_serial = (
            bool(next_item)
            and any(c.isdigit() for c in next_item)
            and not next_item.startswith(_KNOWN_PREFIXES)
        )

        if next_is_serial:
            if main_model is None:
                # E.g. "Biochemistry CD" followed by "J-815"
                if i + 2 < len(dedup) and next_item.startswith(
                    _INSTRUMENT_PREFIXES,
                ):
                    res["system_name"] = item
                    i += 1
                    continue
                main_model, main_serial = item, next_item
            else:
                accessories.append(
                    {"model": item, "serial_number": next_item},
                )
            i += 2
        else:
            if main_model is None and item.startswith(_INSTRUMENT_PREFIXES):
                main_model = item
            elif main_model is None and "system_name" not in res:
                res["system_name"] = item
            i += 1

    if main_model:
        res["model"] = main_model
    if main_serial:
        res["serial_number"] = main_serial
    if accessories:
        res["accessories"] = accessories
    return res


# --------------------------------------------------------------------------
# MeasParam
# --------------------------------------------------------------------------


def _read_variant(data: bytes, pos: int, vtype: int) -> tuple[Any, int] | None:
    """Return ``(value, next_pos)``, or ``None`` if unknown or truncated."""
    if vtype == 8:  # VT_BSTR: length-prefixed UTF-16LE
        if pos + 4 > len(data):
            return None
        (n,) = struct.unpack_from("<I", data, pos)
        if pos + 4 + n > len(data):
            return None
        return _decode(data[pos + 4 : pos + 4 + n]).strip(), pos + 4 + n

    fmt = _VARIANT_FORMATS.get(vtype)
    if fmt is None:
        return None
    size = struct.calcsize(fmt)
    if pos + size > len(data):
        return None
    (val,) = struct.unpack_from(fmt, data, pos)
    if vtype == 7:  # VT_DATE
        val = parse_ole_date(val)
    elif vtype == 11:  # VT_BOOL
        val = val != 0
    return val, pos + size


def _read_props(data: bytes) -> dict[int, Any]:
    """Read the typed property list that follows the 12-byte header."""
    props: dict[int, Any] = {}
    pos = 12
    while pos + 6 <= len(data):
        prop_id, vtype = struct.unpack_from("<IH", data, pos)
        result = _read_variant(data, pos + 6, vtype)
        if result is None:
            break
        props[prop_id], pos = result
    return props


def _has_unit(unit: str) -> Callable[[Any], bool]:
    return lambda v: _is_text(v) and unit in v


def _bandwidth(props: dict[int, Any]) -> dict[str, str]:
    """Single bandwidth, or EX/EM pair for spectrofluorometers."""
    has_nm = _has_unit("nm")
    if has_nm(props.get(2)) and has_nm(props.get(4)):
        return {
            "ex_bandwidth": props[2],
            "em_bandwidth": props[4],
            "bandwidth": f"EX {props[2]}, EM {props[4]}",
        }
    if (v := _first(props, (24, 7, 8, 2), has_nm)) is not None:
        return {"bandwidth": v}
    return {}


def _scanning_speed(props: dict[int, Any]) -> str | None:
    if _is_positive_int(props.get(28)):
        return f"{props[28]} nm/min"
    if isinstance(props.get(6), int) and props[6] in (500, 1000, 2000):
        return f"{props[6]} nm/min"
    return None


def _temperature_ramp(props: dict[int, Any]) -> dict[str, Any] | None:
    scans = props.get(403)
    if not (isinstance(scans, int) and scans > 1):
        return None
    ramp: dict[str, Any] = {"scans": scans}
    for name, pids in _RAMP_FIELDS.items():
        if (v := _first(props, pids, _is_number)) is not None:
            ramp[name] = float(v)
    return ramp


def parse_meas_param(data: bytes) -> dict[str, Any]:
    """Parse MeasParam stream containing instrument parameters."""
    if len(data) < 12:
        return {}
    props = _read_props(data)
    params: dict[str, Any] = {}

    for name, pids in _TEXT_PARAMS.items():
        if (v := _first(props, pids, _is_text)) is not None:
            params[name] = v

    if (v := _first(props, (21, 9, 7), _has_unit("sec"))) is not None:
        params["response"] = v

    params.update(_bandwidth(props))

    # Fixed excitation wavelength (2D fluorescence emission scans)
    v9 = props.get(9, 0)
    if props.get(1) == 1 and _is_number(v9) and v9 > 0:
        params["excitation_wavelength"] = f"{float(v9):g} nm"

    if speed := _scanning_speed(props):
        params["scanning_speed"] = speed

    # 202 is the true measurement count; 80 and 1 are fallbacks
    if (v := _first(props, (202, 80, 1), _is_positive_int)) is not None:
        params["accumulations"] = v

    if isinstance(props.get(26), int):  # 0: Continuous, 1: Step
        params["scanning_mode"] = "Step" if props[26] == 1 else "Continuous"

    if props.get(120) == 2 or props.get(121) == 1:
        params["baseline_correction"] = "Baseline"

    if props.get(122) == 5:
        params["cd_detector"] = "PMT"
    if props.get(103) == 20:
        params["pmt_voltage"] = "Auto"

    if ramp := _temperature_ramp(props):
        params["temperature_control"] = ramp

    return params


# --------------------------------------------------------------------------
# DataInfo extras
# --------------------------------------------------------------------------


def extract_scan_temperatures(
    data_info: bytes,
    scan_count: int,
    start_temp: float | None = None,
    end_temp: float | None = None,
) -> list[float]:
    """Find the scan temperature array stored in multi-scan DataInfo."""
    if scan_count <= 1 or len(data_info) < 96:
        return []
    fmt = f"<{scan_count}d"
    size = struct.calcsize(fmt)
    for offset in range(64, len(data_info) - size + 1, 4):
        vals = struct.unpack_from(fmt, data_info, offset)
        if not all(-50 <= v <= 350 for v in vals):
            continue
        if len(set(vals)) != scan_count:
            continue
        if start_temp is not None and abs(vals[0] - start_temp) > 1.5:
            continue
        if end_temp is not None and abs(vals[-1] - end_temp) > 1.5:
            continue
        return [round(v, 2) for v in vals]
    return []


def _parse_3d_scan(data_info: bytes, scan_count: int) -> dict[str, Any] | None:
    """Detect a 3D spectral scan (secondary wavelength axis) in DataInfo."""
    if len(data_info) < 92:
        return None
    (sec_pts,) = struct.unpack_from("<I", data_info, 60)
    sec_start, sec_end, sec_step = struct.unpack_from("<ddd", data_info, 64)
    (sec_code,) = struct.unpack_from("<I", data_info, 88)
    if not (
        sec_pts == scan_count and sec_code == WAVELENGTH_CODE and sec_step > 0
    ):
        return None
    return {
        "dimension": "Emission Wavelength",
        "scans": sec_pts,
        "start_wavelength": sec_start,
        "end_wavelength": sec_end,
        "wavelength_step": sec_step,
        "scan_emission_wavelengths": [
            round(sec_start + i * sec_step, 4) for i in range(sec_pts)
        ],
    }


# --------------------------------------------------------------------------
# Top-level extraction
# --------------------------------------------------------------------------

_STREAM_PARSERS = (
    # (metadata key, stream name, parser)
    ("file_info", "BaseInfo", parse_base_info),
    ("software", "Header", parse_header),
    ("operator", "UserInfo", parse_user_info),
    ("instrument", "ModuleInfo", parse_module_info),
)


def _read_stream(ole: OleFileIO[str], name: str) -> bytes:
    return ole.openstream(name).read() if ole.exists(name) else b""


def extract_metadata(
    ole: OleFileIO[str],
    npoints: int = 0,
    x_first: float = 0.0,
    x_last: float = 0.0,
    x_increment: float = 0.0,
    header_names: list[str] | None = None,
    scan_count: int = 1,
) -> dict[str, Any]:
    """Extract available metadata from an OLE file."""
    meta: dict[str, Any] = {}

    for key, stream, parser in _STREAM_PARSERS:
        if info := parser(_read_stream(ole, stream)):
            meta[key] = info

    sample: dict[str, Any] = {"name": "", "comment": ""}
    sample.update(parse_sample_info(_read_stream(ole, "SampleInfo")))

    params = parse_meas_param(_read_stream(ole, "MeasParam"))
    if "sample_description" in params:
        sample["description"] = params.pop("sample_description")
    meta["sample"] = sample

    spectral: dict[str, Any] = {
        "x_initial": x_first,
        "x_final": x_last,
        "x_step": x_increment,
        "points": npoints,
    }
    if header_names:
        channels = [
            h for h in header_names if not h.startswith(("WAVELENGTH", "TIME"))
        ]
        spectral["channels"] = channels
        # Strip "_scanN" suffixes, keep first-seen order
        unique = dict.fromkeys(re.sub(r"_scan\d+$", "", ch) for ch in channels)
        if unique:
            params["photometric_mode"] = ", ".join(unique)
    params["spectral"] = spectral

    if scan_count > 1 and ole.exists("DataInfo"):
        data_info = _read_stream(ole, "DataInfo")

        if three_d := _parse_3d_scan(data_info, scan_count):
            params["three_dimensional_scan"] = three_d
            spectral["secondary_dimension"] = {
                "name": three_d["dimension"],
                "x_initial": three_d["start_wavelength"],
                "x_final": three_d["end_wavelength"],
                "x_step": three_d["wavelength_step"],
                "points": three_d["scans"],
            }

        ramp = params.get("temperature_control") or {}
        temps = extract_scan_temperatures(
            data_info,
            scan_count,
            ramp.get("start_temperature"),
            ramp.get("end_temperature"),
        )
        if temps:
            params.setdefault("temperature_control", {"scans": scan_count})
            params["temperature_control"]["scan_temperatures"] = temps

    meta["parameters"] = params
    return meta


# --------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------


def _add_fields(
    lines: list[str],
    section: dict[str, Any],
    fields: Sequence[tuple[str, str]],
) -> None:
    """Append ``# Label: value`` for each non-empty field in ``section``."""
    for key, label in fields:
        if (value := section.get(key)) not in (None, ""):
            lines.append(f"# {label}: {value}")


def _num(x: float) -> float | int:
    """Show whole floats as ints (30.0 -> 30)."""
    return int(x) if isinstance(x, float) and x.is_integer() else x


def _instrument_lines(inst: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if "model" in inst:
        serial = (
            f" (S/N: {inst['serial_number']})"
            if "serial_number" in inst
            else ""
        )
        lines.append(f"# Instrument: {inst['model']}{serial}")
    if "system_name" in inst and inst["system_name"] != inst.get("model"):
        lines.append(f"# System Name: {inst['system_name']}")
    if "accessories" in inst:
        acc = ", ".join(
            f"{a['model']} (S/N: {a.get('serial_number', 'N/A')})"
            for a in inst["accessories"]
        )
        lines.append(f"# Accessories: {acc}")
    return lines


def _cd_detector_line(params: dict[str, Any]) -> list[str]:
    if "cd_detector" not in params and "pmt_voltage" not in params:
        return []
    det = params.get("cd_detector", "")
    volt = (
        f" (PMT Voltage: {params['pmt_voltage']})"
        if "pmt_voltage" in params
        else ""
    )
    return [f"# CD Detector: {det}{volt}".strip()]


def _format_3d_scan(three_d: dict[str, Any]) -> str:
    dim = three_d.get("dimension", "Emission Wavelength")
    start, end = three_d.get("start_wavelength"), three_d.get("end_wavelength")
    step = three_d.get("wavelength_step")

    parts = []
    if three_d.get("scans"):
        parts.append(f"{three_d['scans']} scans")
    if start is not None and end is not None:
        parts.append(f"{dim} {start} nm to {end} nm")
    text = ", ".join(parts)
    if step is not None:
        text += f" (step {step} nm)"
    return text.strip()


def _format_ramp(tc: dict[str, Any]) -> str:
    parts = []
    if tc.get("scans"):
        parts.append(f"{tc['scans']} scans")
    if "start_temperature" in tc and "end_temperature" in tc:
        parts.append(
            f"{tc['start_temperature']} °C to {tc['end_temperature']} °C",
        )

    details = []
    if "temperature_step" in tc:
        details.append(f"step {tc['temperature_step']} °C")
    if "heating_rate" in tc:
        details.append(f"rate {tc['heating_rate']} °C/min")
    tol = tc.get("temperature_tolerance")
    wait = tc.get("stabilization_time")
    if tol is not None and wait is not None:
        details.append(f"tolerance ±{tol} °C for {_num(wait)} s")
    elif tol is not None:
        details.append(f"tolerance ±{tol} °C")
    elif wait is not None:
        details.append(f"wait {_num(wait)} s")
    if "post_run_temperature" in tc:
        details.append(f"post-run {tc['post_run_temperature']} °C")

    text = ", ".join(parts)
    if details:
        text += f" ({', '.join(details)})"
    return text.strip()


def format_metadata_header(metadata: dict[str, Any]) -> list[str]:
    """Format metadata dictionary into human-readable commented lines."""
    lines = ["# --- Measurement Information ---"]
    params = metadata.get("parameters", {})

    _add_fields(lines, metadata.get("file_info", {}), _FILE_FIELDS)
    _add_fields(lines, metadata.get("operator", {}), _OPERATOR_FIELDS)
    lines += _instrument_lines(metadata.get("instrument", {}))
    _add_fields(lines, metadata.get("software", {}), _SOFTWARE_FIELDS)
    _add_fields(lines, metadata.get("sample", {}), _SAMPLE_FIELDS)
    _add_fields(lines, params, _PARAM_FIELDS)
    lines += _cd_detector_line(params)

    spectral = params.get("spectral", {})
    three_d = params.get("three_dimensional_scan", {})
    if "x_initial" in spectral and "x_final" in spectral:
        label = "# Range (Excitation)" if three_d else "# Range"
        lines.append(
            f"{label}: {spectral['x_initial']} to {spectral['x_final']} "
            f"(Pitch: {spectral.get('x_step', 'N/A')}, "
            f"Points: {spectral.get('points', 'N/A')})",
        )

    if "start_time" in params or "end_time" in params:
        lines.append(
            f"# Measurement Time: {params.get('start_time', 'Unknown')}"
            f" - {params.get('end_time', 'Unknown')}",
        )

    if three_d:
        if summary := _format_3d_scan(three_d):
            lines.append(f"# 3D Scan: {summary}")
        if em_vals := three_d.get("scan_emission_wavelengths"):
            lines.append(
                "# Emission Wavelengths: "
                + ", ".join(f"{w:g} nm" for w in em_vals),
            )

    if temp_ctrl := params.get("temperature_control"):
        if ramp := _format_ramp(temp_ctrl):
            lines.append(f"# Temperature Ramp: {ramp}")
        if "scan_temperatures" in temp_ctrl:
            temps = ", ".join(f"{t}°C" for t in temp_ctrl["scan_temperatures"])
            lines.append(f"# Scan Temperatures: {temps}")

    return lines
