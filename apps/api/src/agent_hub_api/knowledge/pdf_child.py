from __future__ import annotations

import json
import os
import sys
import unicodedata
from pathlib import Path


def _apply_posix_limits(cpu_seconds: int, memory_bytes: int, output_bytes: int) -> None:
    import resource

    resource.setrlimit(  # type: ignore[attr-defined]
        resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds)  # type: ignore[attr-defined]
    )
    resource.setrlimit(  # type: ignore[attr-defined]
        resource.RLIMIT_AS, (memory_bytes, memory_bytes)  # type: ignore[attr-defined]
    )
    resource.setrlimit(  # type: ignore[attr-defined]
        resource.RLIMIT_FSIZE, (output_bytes, output_bytes)  # type: ignore[attr-defined]
    )
    resource.setrlimit(  # type: ignore[attr-defined]
        resource.RLIMIT_NOFILE, (32, 32)  # type: ignore[attr-defined]
    )


def _apply_windows_limits(cpu_seconds: int, memory_bytes: int) -> object:
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class BASIC_LIMITS(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class EXTENDED_LIMITS(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BASIC_LIMITS),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
    limits = EXTENDED_LIMITS()
    limits.BasicLimitInformation.PerProcessUserTimeLimit = cpu_seconds * 10_000_000
    limits.BasicLimitInformation.LimitFlags = 0x2 | 0x100 | 0x2000
    limits.ProcessMemoryLimit = memory_bytes
    if not kernel32.SetInformationJobObject(
        job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
    ):
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
    if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")
    return job


def _apply_limits(cpu_seconds: int, memory_bytes: int, output_bytes: int) -> object | None:
    if os.name == "nt":
        return _apply_windows_limits(cpu_seconds, memory_bytes)
    _apply_posix_limits(cpu_seconds, memory_bytes, output_bytes)
    return None


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        character
        for character in normalized
        if character in {"\n", "\t"} or ord(character) >= 32
    ).strip()


def _write_result(path: Path, payload: dict[str, object], max_bytes: int) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > max_bytes:
        encoded = b'{"ok":false,"error_code":"PDF_OUTPUT_LIMIT_EXCEEDED"}'
    path.write_bytes(encoded)


def main() -> int:
    if len(sys.argv) != 8:
        return 2
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    max_pages, max_chars, cpu_seconds, memory_bytes, output_bytes = map(int, sys.argv[3:])
    try:
        limit_handle = _apply_limits(cpu_seconds, memory_bytes, output_bytes)
    except (ImportError, OSError, ValueError):
        return 3
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(input_path), strict=True)
        if reader.is_encrypted:
            _write_result(
                output_path, {"ok": False, "error_code": "PDF_ENCRYPTED_UNSUPPORTED"}, output_bytes
            )
            return 0
        page_count = len(reader.pages)
        if page_count > max_pages:
            _write_result(
                output_path, {"ok": False, "error_code": "PDF_PAGE_LIMIT_EXCEEDED"}, output_bytes
            )
            return 0
        pages: list[str] = []
        total = 0
        for page in reader.pages:
            extracted = page.extract_text() or ""
            total += len(extracted)
            if total > max_chars:
                _write_result(
                    output_path,
                    {"ok": False, "error_code": "DOCUMENT_TEXT_LIMIT_EXCEEDED"},
                    output_bytes,
                )
                return 0
            pages.append(extracted)
        text = _normalize("\n\n".join(pages))
        if not text:
            _write_result(
                output_path, {"ok": False, "error_code": "PDF_TEXT_NOT_FOUND"}, output_bytes
            )
            return 0
        _write_result(
            output_path,
            {"ok": True, "text": text, "page_count": page_count},
            output_bytes,
        )
        del limit_handle
        return 0
    except MemoryError:
        return 4
    except BaseException:
        _write_result(output_path, {"ok": False, "error_code": "PDF_INVALID"}, output_bytes)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
