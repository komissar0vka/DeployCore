import hashlib
import io
import struct
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from deploycore import package_storage as storage
from deploycore.package_schemas import PackageInput, PackagePatch, VersionInput


def test_stream_checks_limit_and_disk_reserve(monkeypatch):
    free = 100
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda _: SimpleNamespace(free=free))
    output = io.BytesIO()
    upload = storage.Upload(output, limit=6, reserve=20)
    upload.append(b"abc")
    free = 21
    with pytest.raises(HTTPException) as caught:
        upload.append(b"de")
    assert caught.value.status_code == 507
    free = 100
    with pytest.raises(HTTPException) as caught:
        upload.append(b"defg")
    assert caught.value.status_code == 413
    upload.append(b"def")
    assert output.getvalue() == b"abcdef"
    assert upload.hash.hexdigest() == hashlib.sha256(output.getvalue()).hexdigest()


def test_pe_input_distinguishes_architecture_and_rejects_library(tmp_path):
    installer = tmp_path / "fixture"
    header = bytearray(90)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 60, 64)
    header[64:68] = b"PE\x00\x00"
    arch = ((0x14C, 0x10B, "x86"), (0x8664, 0x20B, "x64"))
    for machine, magic, name in arch:
        struct.pack_into("<H", header, 68, machine)
        struct.pack_into("<HH", header, 86, 2, magic)
        installer.write_bytes(header)
        assert storage.installer_architecture(installer, "exe") == name
    struct.pack_into("<H", header, 86, 0x2002)
    installer.write_bytes(header)
    with pytest.raises(HTTPException, match="package_invalid_format"):
        storage.installer_architecture(installer, "exe")


def test_catalog_payload_rejects_nulls_and_duplicate_exit_codes():
    with pytest.raises(ValidationError):
        PackageInput(name="Fixture", publisher="Example", description="bad\x00value")
    with pytest.raises(ValidationError):
        PackagePatch(name=None)
    assert PackagePatch().model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError):
        VersionInput(version="1.0", architecture="x64", installer="exe", success_codes=[0, 0],
                     detection={"kind": "registry_software", "display_name": "Fixture", "version": "1.0"})
