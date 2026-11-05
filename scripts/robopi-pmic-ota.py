#!/usr/bin/env python3
"""Inspect the STM32F103C8 PMIC or validate its SWD firmware bundle."""

import argparse
import hashlib
import json
import re
import struct
import sys
import time
from pathlib import Path


APP_START = 0x08001000
APP_END = 0x0800FC00
UID_RE = re.compile(r"^[0-9A-F]{24}$")


def load_bundle(path):
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != 2 or
            manifest.get("board") != "stm32f103_pmic" or
            manifest.get("target") != "stm32f103c8" or
            manifest.get("ota_supported") is not False):
        raise ValueError("unsupported STM32F103C8 PMIC bundle")
    version = manifest.get("version", "")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-[a-z0-9-]+", version):
        raise ValueError("invalid firmware version")

    images = {}
    for name, address in (("boot", 0x08000000), ("app", APP_START)):
        item = manifest["images"][name]
        filename = "boot.bin" if name == "boot" else "ChargeBAT.bin"
        if item["file"] != filename or int(item["load_address"], 16) != address:
            raise ValueError(f"invalid {name} image metadata")
        data = (manifest_path.parent / filename).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"{filename}: SHA-256 mismatch")
        images[name] = data

    app = images["app"]
    if not 8 <= len(app) <= APP_END - APP_START:
        raise ValueError("application is outside the PMIC flash partition")
    stack, reset = struct.unpack_from("<II", app)
    if not 0x20000000 < stack <= 0x20005000:
        raise ValueError("invalid initial stack pointer")
    if not (reset & 1 and APP_START <= (reset & ~1) < APP_START + len(app)):
        raise ValueError("invalid application reset vector")
    if version.encode("ascii") not in app:
        raise ValueError("manifest version is absent from application image")
    if not 8 <= len(images["boot"]) <= APP_START - 0x08000000:
        raise ValueError("bootloader is outside its flash partition")
    return manifest, images


def read_field(port, prefix, timeout):
    deadline = time.monotonic() + timeout
    received = bytearray()
    key = prefix.encode("ascii")
    while time.monotonic() < deadline:
        part = port.read(1)
        if part:
            received.extend(part)
            start = received.find(key)
            if start >= 0:
                end = received.find(b";", start)
                if end >= 0:
                    return received[start:end + 1].decode("ascii")
            if len(received) > 4096:
                del received[:2048]
    raise TimeoutError(f"no {prefix} reply; received {received[-128:]!r}")


def query(port, command, prefix, timeout, attempts=3):
    for attempt in range(attempts):
        port.reset_input_buffer()
        port.write(command.encode("ascii"))
        port.flush()
        try:
            return read_field(port, prefix, timeout)
        except TimeoutError:
            if attempt + 1 == attempts:
                raise


def identity(port, timeout):
    sn = query(port, "SN_GET:1;", "CHRG_SN:", timeout).split(":", 1)[1][:-1]
    version = query(port, "FW_VER:1;", "FW_VER:", timeout).split(":", 1)[1][:-1]
    if not UID_RE.fullmatch(sn):
        raise ValueError(f"invalid chip UID: {sn!r}")
    return sn, version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "verify-bundle"))
    parser.add_argument("--port", help="PMIC USART3 serial device for inspect")
    parser.add_argument("--bundle", help="manifest.json path for verify-bundle")
    parser.add_argument("--timeout", type=float, default=3)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    if args.command == "verify-bundle":
        if not args.bundle:
            parser.error("verify-bundle requires --bundle")
        try:
            manifest, images = load_bundle(args.bundle)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"PMIC bundle invalid: {exc}", file=sys.stderr)
            return 1
        print(f"target={manifest['target']} version={manifest['version']} "
              f"boot={len(images['boot'])} app={len(images['app'])}")
        return 0

    if not args.port:
        parser.error("inspect requires --port")
    try:
        import serial
    except ImportError as exc:
        parser.error(f"python3-serial is required: {exc}")
    try:
        with serial.Serial(args.port, 115200, timeout=0.05, write_timeout=args.timeout) as port:
            uid, version = identity(port, args.timeout)
            print(f"UID={uid} FW_VER={version}")
    except (OSError, ValueError, TimeoutError, serial.SerialException) as exc:
        print(f"PMIC inspect failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
