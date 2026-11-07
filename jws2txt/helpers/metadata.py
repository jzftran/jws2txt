# %%
from __future__ import annotations

import datetime
import re
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from olefile import OleFileIO

OLE_EPOCH = datetime.datetime(1899, 12, 30, tzinfo=datetime.timezone.utc)


def parse_ole_date(days: float) -> str | None:
    """Convert an OLE Automation DATE to an ISO 8601 date-time string.

    Args:
        days: Number of days since December 30, 1899, including a fractional
            part representing the time of day.

    Returns:
        The date and time formatted as ``YYYY-MM-DD HH:MM:SS``, or ``None``
        if the input is less than or equal to zero or conversion fails.

    """
    dt = OLE_EPOCH + datetime.timedelta(days=days)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# %%
def parse_base_info(data: bytes) -> dict[str, Any]:
    """Parse BaseInfo stream containing original file path and timestamps."""
    if len(data) < 25:
        return {}
    res = {}
    str_len = struct.unpack("<I", data[21:25])[0]
    if 25 + str_len <= len(data):
        orig_path = (
            data[25 : 25 + str_len]
            .decode("utf-16le", errors="ignore")
            .rstrip("\x00")
        )
        if orig_path:
            res["original_file"] = orig_path
        offset = 25 + str_len
        if offset + 16 <= len(data):
            created_d, modified_d = struct.unpack(
                "<dd",
                data[offset : offset + 16],
            )
            created_dt = parse_ole_date(created_d)
            modified_dt = parse_ole_date(modified_d)
            if created_dt:
                res["created"] = created_dt
            if modified_dt:
                res["modified"] = modified_dt
    return res


def parse_header(data: bytes) -> dict[str, Any]:
    """Parse Header stream containing software name, version, and platform."""
    if len(data) < 120:
        return {}
    res = {}
    prog = (
        data[8:40].decode("utf-16le", errors="ignore").split("\x00")[0].strip()
    )
    ver = (
        data[56:88]
        .decode("utf-16le", errors="ignore")
        .split("\x00")[0]
        .strip()
    )
    plat = (
        data[88:120]
        .decode("utf-16le", errors="ignore")
        .split("\x00")[0]
        .strip()
    )
    comp = (
        data[120:152]
        .decode("utf-16le", errors="ignore")
        .split("\x00")[0]
        .strip()
        if len(data) >= 152
        else ""
    )
    if prog:
        res["software"] = f"{prog} {ver}".strip() if ver else prog
    if plat:
        res["platform"] = plat
    if comp:
        res["compiler"] = comp
    return res


def parse_user_info(data: bytes) -> dict[str, Any]:
    """Parse UserInfo stream containing operator and institution."""
    if len(data) < 52:
        return {}
    slen = struct.unpack("<I", data[48:52])[0]
    if slen > 0 and 52 + slen <= len(data):
        inst = (
            data[52 : 52 + slen]
            .decode("utf-16le", errors="ignore")
            .rstrip("\x00")
            .strip()
        )
        if inst:
            return {"institution": inst}
    return {}


def parse_module_info(data: bytes) -> dict[str, Any]:
    """Parse ModuleInfo stream to extract hardware model, serial, and accessories."""
    if len(data) < 8:
        return {}
    strings: list[str] = []
    idx = 4
    while idx < len(data) - 4:
        slen = struct.unpack("<I", data[idx : idx + 4])[0]
        if 2 < slen <= 64 and slen % 2 == 0 and idx + 4 + slen <= len(data):
            raw = data[idx + 4 : idx + 4 + slen]
            s = raw.decode("utf-16le")
            if s.endswith("\x00"):
                clean = s.rstrip("\x00").strip()
                if clean and all(32 <= ord(c) < 127 for c in clean):
                    strings.append(clean)
                    idx += 4 + slen
                    continue
        idx += 1

    if not strings:
        return {}

    # Deduplicate consecutive identical names
    dedup: list[str] = []
    for s in strings:
        if not dedup or s != dedup[-1]:
            dedup.append(s)

    res: dict[str, Any] = {}
    accessories: list[dict[str, str]] = []
    main_model: str | None = None
    main_serial: str | None = None

    known_prefixes = (
        "J-",
        "V-",
        "FP-",
        "PM-",
        "RSC-",
        "CDF-",
        "PAC-",
        "ETCS-",
        "SCE-",
        "V700",
    )

    i = 0
    while i < len(dedup):
        item = dedup[i]
        has_next = i + 1 < len(dedup)
        next_item = dedup[i + 1] if has_next else ""
        next_is_serial = (
            has_next
            and any(c.isdigit() for c in next_item)
            and not any(next_item.startswith(p) for p in known_prefixes)
        )

        if next_is_serial:
            model_candidate = item
            serial_candidate = next_item
            if main_model is None:
                # E.g. "Biochemistry CD" followed by "J-815"
                if i + 2 < len(dedup) and any(
                    next_item.startswith(p) for p in ("J-", "V-", "FP-")
                ):
                    res["system_name"] = item
                    i += 1
                    continue
                main_model = model_candidate
                main_serial = serial_candidate
            else:
                accessories.append(
                    {
                        "model": model_candidate,
                        "serial_number": serial_candidate,
                    },
                )
            i += 2
        else:
            if main_model is None and any(
                item.startswith(p) for p in ("J-", "V-", "FP-")
            ):
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


def parse_meas_param(data: bytes) -> dict[str, Any]:
    """Parse MeasParam stream containing instrument parameters as typed OLE Variants."""
    if len(data) < 12:
        return {}
    pos = 12
    raw_props: dict[int, Any] = {}

    while pos + 6 <= len(data):
        prop_id, vtype = struct.unpack("<IH", data[pos : pos + 6])
        pos += 6
        if vtype == 3:  # VT_I4 (int32)
            if pos + 4 > len(data):
                break
            val = struct.unpack("<i", data[pos : pos + 4])[0]
            pos += 4
        elif vtype == 5:  # VT_R8 (double)
            if pos + 8 > len(data):
                break
            val = struct.unpack("<d", data[pos : pos + 8])[0]
            pos += 8
        elif vtype == 7:  # VT_DATE (double date)
            if pos + 8 > len(data):
                break
            val_d = struct.unpack("<d", data[pos : pos + 8])[0]
            val = parse_ole_date(val_d)
            pos += 8
        elif vtype == 8:  # VT_BSTR (length-prefixed UTF-16LE)
            if pos + 4 > len(data):
                break
            slen = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
            if pos + slen > len(data):
                break
            val = (
                data[pos : pos + slen]
                .decode("utf-16le", errors="ignore")
                .rstrip("\x00")
                .strip()
            )
            pos += slen
        elif vtype == 11:  # VT_BOOL (int16 boolean)
            if pos + 2 > len(data):
                break
            val = struct.unpack("<h", data[pos : pos + 2])[0] != 0
            pos += 2
        elif vtype == 2:  # VT_I2 (int16)
            if pos + 2 > len(data):
                break
            val = struct.unpack("<h", data[pos : pos + 2])[0]
            pos += 2
        elif vtype == 19:  # VT_UI4 (uint32)
            if pos + 4 > len(data):
                break
            val = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
        else:
            break
        raw_props[prop_id] = val

    params: dict[str, Any] = {}

    # Sensitivity
    for pid in (20, 88):
        if (
            pid in raw_props
            and isinstance(raw_props[pid], str)
            and raw_props[pid]
        ):
            params["sensitivity"] = raw_props[pid]
            break

    # Response time
    for pid in (21, 9, 7):
        if (
            pid in raw_props
            and isinstance(raw_props[pid], str)
            and "sec" in raw_props[pid]
        ):
            params["response"] = raw_props[pid]
            break

    # Bandwidth (dual EX/EM for spectrofluorometers, or single bandwidth)
    if (
        2 in raw_props
        and 4 in raw_props
        and isinstance(raw_props[2], str)
        and isinstance(raw_props[4], str)
        and "nm" in raw_props[2]
        and "nm" in raw_props[4]
    ):
        params["ex_bandwidth"] = raw_props[2]
        params["em_bandwidth"] = raw_props[4]
        params["bandwidth"] = f"EX {raw_props[2]}, EM {raw_props[4]}"
    else:
        for pid in (24, 7, 8, 2):
            if (
                pid in raw_props
                and isinstance(raw_props[pid], str)
                and "nm" in raw_props[pid]
            ):
                params["bandwidth"] = raw_props[pid]
                break

    # Fixed excitation wavelength (for 2D fluorescence emission scans)
    if raw_props.get(1) == 1 and 9 in raw_props:
        v9 = raw_props[9]
        if isinstance(v9, (int, float)) and v9 > 0:
            params["excitation_wavelength"] = f"{float(v9):g} nm"

    # Scanning speed
    if (
        28 in raw_props
        and isinstance(raw_props[28], int)
        and raw_props[28] > 0
    ):
        params["scanning_speed"] = f"{raw_props[28]} nm/min"
    elif (
        6 in raw_props
        and isinstance(raw_props[6], int)
        and raw_props[6] in (500, 1000, 2000)
    ):
        params["scanning_speed"] = f"{raw_props[6]} nm/min"

    # Pathlength
    if 25 in raw_props and isinstance(raw_props[25], str) and raw_props[25]:
        params["pathlength"] = raw_props[25]

    # Accumulations (Prop 202 is true measurement count, 80 and 1 are fallback flags)
    for pid in (202, 80, 1):
        if (
            pid in raw_props
            and isinstance(raw_props[pid], int)
            and raw_props[pid] > 0
        ):
            params["accumulations"] = raw_props[pid]
            break

    # Scanning mode (0: Continuous, 1: Step)
    if 26 in raw_props and isinstance(raw_props[26], int):
        params["scanning_mode"] = (
            "Step" if raw_props[26] == 1 else "Continuous"
        )

    # Baseline correction
    if raw_props.get(120) == 2 or raw_props.get(121) == 1:
        params["baseline_correction"] = "Baseline"

    # CD detector and PMT voltage
    if raw_props.get(122) == 5:
        params["cd_detector"] = "PMT"
    if raw_props.get(103) == 20:
        params["pmt_voltage"] = "Auto"

    # Buffer / sample notes
    if 42 in raw_props and isinstance(raw_props[42], str) and raw_props[42]:
        params["sample_description"] = raw_props[42]

    # Start / end measurement timestamps
    for pid in (203, 92):
        if (
            pid in raw_props
            and isinstance(raw_props[pid], str)
            and raw_props[pid]
        ):
            params["start_time"] = raw_props[pid]
            break

    for pid in (204, 190, 93, 90):
        if (
            pid in raw_props
            and isinstance(raw_props[pid], str)
            and raw_props[pid]
        ):
            params["end_time"] = raw_props[pid]
            break

    # Multi-scan temperature / thermal control
    if (
        403 in raw_props
        and isinstance(raw_props[403], int)
        and raw_props[403] > 1
    ):
        ramp: dict[str, Any] = {"scans": raw_props[403]}
        if 404 in raw_props and isinstance(raw_props[404], (int, float)):
            ramp["start_temperature"] = float(raw_props[404])
        if 405 in raw_props and isinstance(raw_props[405], (int, float)):
            ramp["end_temperature"] = float(raw_props[405])
        if 402 in raw_props and isinstance(raw_props[402], (int, float)):
            ramp["temperature_step"] = float(raw_props[402])
        if 410 in raw_props and isinstance(raw_props[410], (int, float)):
            ramp["heating_rate"] = float(raw_props[410])
        for t_pid in (861, 662):
            if t_pid in raw_props and isinstance(
                raw_props[t_pid],
                (int, float),
            ):
                ramp["temperature_tolerance"] = float(raw_props[t_pid])
                break
        for w_pid in (803, 603):
            if w_pid in raw_props and isinstance(
                raw_props[w_pid],
                (int, float),
            ):
                ramp["stabilization_time"] = float(raw_props[w_pid])
                break
        if 401 in raw_props and isinstance(raw_props[401], (int, float)):
            ramp["post_run_temperature"] = float(raw_props[401])
        params["temperature_control"] = ramp

    return params


def extract_scan_temperatures(
    data_info: bytes,
    scan_count: int,
    start_temp: float | None = None,
    end_temp: float | None = None,
) -> list[float]:
    """Find scan temperature array stored in multi-scan DataInfo streams."""
    if scan_count <= 1 or len(data_info) < 96:
        return []
    for offset in range(64, len(data_info) - scan_count * 8 + 1, 4):
        vals = [
            struct.unpack(
                "<d",
                data_info[offset + i * 8 : offset + (i + 1) * 8],
            )[0]
            for i in range(scan_count)
        ]
        if all(-50 <= v <= 350 for v in vals) and len(set(vals)) == scan_count:
            if start_temp is not None and abs(vals[0] - start_temp) > 1.5:
                continue
            if end_temp is not None and abs(vals[-1] - end_temp) > 1.5:
                continue
            return [round(v, 2) for v in vals]
    return []


def parse_sample_info(data: bytes) -> dict[str, str]:
    """Parse SampleInfo stream to extract sample name and comment."""
    if len(data) < 8:
        return {"name": "", "comment": ""}
    try:
        pos = 4
        name_len = struct.unpack("<I", data[pos : pos + 4])[0]
        pos += 4
        sample_name = (
            data[pos : pos + name_len]
            .decode("utf-16le", errors="ignore")
            .rstrip("\x00")
            if name_len
            else ""
        )
        pos += name_len
        if pos + 4 <= len(data):
            comment_len = struct.unpack("<I", data[pos : pos + 4])[0]
            pos += 4
            comment = (
                data[pos : pos + comment_len]
                .decode("utf-16le", errors="ignore")
                .rstrip("\x00")
                if comment_len
                else ""
            )
        else:
            comment = ""
        return {"name": sample_name, "comment": comment}
    except Exception:
        return {"name": "", "comment": ""}


def extract_metadata(
    ole: OleFileIO[str],
    npoints: int = 0,
    x_first: float = 0.0,
    x_last: float = 0.0,
    x_increment: float = 0.0,
    header_names: list[str] | None = None,
    scan_count: int = 1,
) -> dict[str, Any]:
    """Extract available metadata from an OLE."""
    meta: dict[str, Any] = {}

    # File information
    if ole.exists("BaseInfo"):
        base_info = parse_base_info(ole.openstream("BaseInfo").read())
        if base_info:
            meta["file_info"] = base_info

    # Software / platform
    if ole.exists("Header"):
        hdr_info = parse_header(ole.openstream("Header").read())
        if hdr_info:
            meta["software"] = hdr_info

    # Institution / Operator
    if ole.exists("UserInfo"):
        user_info = parse_user_info(ole.openstream("UserInfo").read())
        if user_info:
            meta["operator"] = user_info

    # Instrument and accessories
    if ole.exists("ModuleInfo"):
        mod_info = parse_module_info(ole.openstream("ModuleInfo").read())
        if mod_info:
            meta["instrument"] = mod_info

    # Sample info
    sample_dict: dict[str, Any] = {"name": "", "comment": ""}
    if ole.exists("SampleInfo"):
        sample_dict.update(
            parse_sample_info(ole.openstream("SampleInfo").read()),
        )

    # Measurement parameters
    params: dict[str, Any] = {}
    if ole.exists("MeasParam"):
        params = parse_meas_param(ole.openstream("MeasParam").read())
        if "sample_description" in params:
            sample_dict["description"] = params.pop("sample_description")

    meta["sample"] = sample_dict

    # Spectral parameters
    spectral: dict[str, Any] = {
        "x_initial": x_first,
        "x_final": x_last,
        "x_step": x_increment,
        "points": npoints,
    }
    if header_names:
        raw_channels = [
            h
            for h in header_names
            if not h.startswith("WAVELENGTH") and not h.startswith("TIME")
        ]
        spectral["channels"] = raw_channels
        unique_channels: list[str] = []
        for ch in raw_channels:
            base_ch = re.sub(r"_scan\d+$", "", ch)
            if base_ch not in unique_channels:
                unique_channels.append(base_ch)
        if unique_channels:
            params["photometric_mode"] = ", ".join(unique_channels)

    params["spectral"] = spectral

    # Multi-scan temperature array or 3D spectral scan
    if scan_count > 1 and ole.exists("DataInfo"):
        data_info_bytes = ole.openstream("DataInfo").read()

        # Check for 3D spectral scan (secondary dimension in DataInfo)
        if len(data_info_bytes) >= 92:
            sec_pts = struct.unpack("<I", data_info_bytes[60:64])[0]
            sec_start, sec_end, sec_step = struct.unpack(
                "<ddd",
                data_info_bytes[64:88],
            )
            sec_code = struct.unpack("<I", data_info_bytes[88:92])[0]
            if (
                sec_pts == scan_count
                and sec_code == 268435715
                and sec_step > 0
            ):
                em_wavelengths = [
                    round(sec_start + i * sec_step, 4) for i in range(sec_pts)
                ]
                params["three_dimensional_scan"] = {
                    "dimension": "Emission Wavelength",
                    "scans": sec_pts,
                    "start_wavelength": sec_start,
                    "end_wavelength": sec_end,
                    "wavelength_step": sec_step,
                    "scan_emission_wavelengths": em_wavelengths,
                }
                spectral["secondary_dimension"] = {
                    "name": "Emission Wavelength",
                    "x_initial": sec_start,
                    "x_final": sec_end,
                    "x_step": sec_step,
                    "points": sec_pts,
                }

        temp_ctrl = params.get("temperature_control")
        start_t = temp_ctrl.get("start_temperature") if temp_ctrl else None
        end_t = temp_ctrl.get("end_temperature") if temp_ctrl else None
        temps = extract_scan_temperatures(
            data_info_bytes,
            scan_count,
            start_t,
            end_t,
        )
        if temps:
            if "temperature_control" not in params:
                params["temperature_control"] = {"scans": scan_count}
            params["temperature_control"]["scan_temperatures"] = temps

    meta["parameters"] = params

    return meta


def format_metadata_header(metadata: dict[str, Any]) -> list[str]:
    """Format metadata dictionary into human-readable commented lines."""
    lines: list[str] = ["# --- Measurement Information ---"]

    file_info = metadata.get("file_info", {})
    if "original_file" in file_info:
        lines.append(f"# Original File: {file_info['original_file']}")
    if "created" in file_info:
        lines.append(f"# Created: {file_info['created']}")
    if "modified" in file_info:
        lines.append(f"# Modified: {file_info['modified']}")

    operator = metadata.get("operator", {})
    if "institution" in operator:
        lines.append(f"# Institution / Operator: {operator['institution']}")

    instrument = metadata.get("instrument", {})
    if "model" in instrument:
        ser = (
            f" (S/N: {instrument['serial_number']})"
            if "serial_number" in instrument
            else ""
        )
        lines.append(f"# Instrument: {instrument['model']}{ser}")
    if "system_name" in instrument and instrument[
        "system_name"
    ] != instrument.get("model"):
        lines.append(f"# System Name: {instrument['system_name']}")
    if "accessories" in instrument:
        acc_str = ", ".join(
            f"{a['model']} (S/N: {a.get('serial_number', 'N/A')})"
            for a in instrument["accessories"]
        )
        lines.append(f"# Accessories: {acc_str}")

    software = metadata.get("software", {})
    if "software" in software:
        lines.append(f"# Software: {software['software']}")

    sample = metadata.get("sample", {})
    if sample.get("name"):
        lines.append(f"# Sample Name: {sample['name']}")
    if sample.get("comment"):
        lines.append(f"# Sample Comment: {sample['comment']}")
    if sample.get("description"):
        lines.append(f"# Sample Description: {sample['description']}")

    params = metadata.get("parameters", {})
    if "photometric_mode" in params:
        lines.append(f"# Photometric Mode: {params['photometric_mode']}")
    if "scanning_mode" in params:
        lines.append(f"# Scanning Mode: {params['scanning_mode']}")
    if "scanning_speed" in params:
        lines.append(f"# Scanning Speed: {params['scanning_speed']}")
    if "response" in params:
        lines.append(f"# D.I.T. (Response): {params['response']}")
    if "bandwidth" in params:
        lines.append(f"# Bandwidth: {params['bandwidth']}")
    if "excitation_wavelength" in params:
        lines.append(
            f"# Excitation Wavelength: {params['excitation_wavelength']}",
        )
    if "sensitivity" in params:
        lines.append(f"# Sensitivity: {params['sensitivity']}")
    if "pathlength" in params:
        lines.append(f"# Pathlength: {params['pathlength']}")
    if "accumulations" in params:
        lines.append(f"# Accumulations: {params['accumulations']}")
    if "baseline_correction" in params:
        lines.append(f"# Baseline Correction: {params['baseline_correction']}")
    if "cd_detector" in params or "pmt_voltage" in params:
        det = params.get("cd_detector", "")
        volt = (
            f" (PMT Voltage: {params['pmt_voltage']})"
            if "pmt_voltage" in params
            else ""
        )
        lines.append(f"# CD Detector: {det}{volt}".strip())

    spectral = params.get("spectral", {})
    three_d = params.get("three_dimensional_scan", {})
    range_label = "# Range (Excitation)" if three_d else "# Range"
    if "x_initial" in spectral and "x_final" in spectral:
        lines.append(
            f"{range_label}: {spectral['x_initial']} to {spectral['x_final']} "
            f"(Pitch: {spectral.get('x_step', 'N/A')}, Points: {spectral.get('points', 'N/A')})",
        )

    if "start_time" in params or "end_time" in params:
        start_t = params.get("start_time", "Unknown")
        end_t = params.get("end_time", "Unknown")
        lines.append(f"# Measurement Time: {start_t} - {end_t}")

    if three_d:
        scans = three_d.get("scans")
        start_w = three_d.get("start_wavelength")
        end_w = three_d.get("end_wavelength")
        step_w = three_d.get("wavelength_step")
        dim = three_d.get("dimension", "Emission Wavelength")
        summary = f"{scans} scans" if scans else ""
        if start_w is not None and end_w is not None:
            summary += (
                f", {dim} {start_w} nm to {end_w} nm"
                if summary
                else f"{dim} {start_w} nm to {end_w} nm"
            )
        if step_w is not None:
            summary += f" (step {step_w} nm)"
        if summary:
            lines.append(f"# 3D Scan: {summary}")
        em_vals = three_d.get("scan_emission_wavelengths", [])
        if em_vals:
            em_str = ", ".join(f"{w:g} nm" for w in em_vals)
            lines.append(f"# Emission Wavelengths: {em_str}")

    temp_ctrl = params.get("temperature_control", {})
    if temp_ctrl:
        scans = temp_ctrl.get("scans")
        start_t = temp_ctrl.get("start_temperature")
        end_t = temp_ctrl.get("end_temperature")
        step_t = temp_ctrl.get("temperature_step")
        rate_t = temp_ctrl.get("heating_rate")
        tol_t = temp_ctrl.get("temperature_tolerance")
        wait_t = temp_ctrl.get("stabilization_time")
        post_t = temp_ctrl.get("post_run_temperature")

        details = []
        if step_t is not None:
            details.append(f"step {step_t} °C")
        if rate_t is not None:
            details.append(f"rate {rate_t} °C/min")
        if tol_t is not None and wait_t is not None:
            w_disp = (
                int(wait_t)
                if isinstance(wait_t, float) and wait_t.is_integer()
                else wait_t
            )
            details.append(f"tolerance ±{tol_t} °C for {w_disp} s")
        elif tol_t is not None:
            details.append(f"tolerance ±{tol_t} °C")
        elif wait_t is not None:
            w_disp = (
                int(wait_t)
                if isinstance(wait_t, float) and wait_t.is_integer()
                else wait_t
            )
            details.append(f"wait {w_disp} s")
        if post_t is not None:
            details.append(f"post-run {post_t} °C")

        ramp_str = f"{scans} scans" if scans else ""
        if start_t is not None and end_t is not None:
            ramp_str += (
                f", {start_t} °C to {end_t} °C"
                if ramp_str
                else f"{start_t} °C to {end_t} °C"
            )
        if details:
            ramp_str += f" ({', '.join(details)})"
        if ramp_str:
            lines.append(f"# Temperature Ramp: {ramp_str}")
        if "scan_temperatures" in temp_ctrl:
            temps_str = ", ".join(
                f"{t}°C" for t in temp_ctrl["scan_temperatures"]
            )
            lines.append(f"# Scan Temperatures: {temps_str}")

    return lines
