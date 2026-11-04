#!/usr/bin/env python3
"""Inspect a PMIC and explicitly trial the right-layout serial OTA protocol."""

import argparse
import hashlib
import json
import re
import struct
import sys
import time
import zlib
from pathlib import Path


APP_START = 0x08001000
APP_END = 0x0800FC00
UID_RE = re.compile(r"^[0-9A-F]{24}$")


def load_bundle(path):
    manifest_path = Path(path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != 1 or manifest.get("board") != "stm32f103_pmic":
        raise ValueError("unsupported PMIC bundle")
    if manifest.get("layout") not in ("left", "right"):
        raise ValueError("missing or invalid board layout")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-" + manifest["layout"],
                        manifest.get("version", "")):
        raise ValueError("bundle version does not match board layout")

    images = {}
    for name, address in (("boot", 0x08000000), ("app", APP_START)):
        item = manifest["images"][name]
        filename = item["file"]
        if filename != name + ".bin" and not (name == "app" and filename == "ChargeBAT.bin"):
            raise ValueError("unexpected image filename")
        if int(item["load_address"], 16) != address:
            raise ValueError("unexpected image load address")
        image = manifest_path.parent / filename
        data = image.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != item["sha256"]:
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


def ota_command(port, command, expected, timeout):
    port.reset_input_buffer()
    port.write(command.encode("ascii"))
    port.flush()
    reply = read_field(port, "OTA_", timeout)
    if reply != expected:
        raise RuntimeError(f"expected {expected!r}, received {reply!r}")


def transfer(port, app, timeout):
    crc = zlib.crc32(app) & 0xFFFFFFFF
    try:
        ota_command(port, f"OTA_BEGIN:{len(app)},{crc};", "OTA_READY;", timeout)
        for offset in range(0, len(app), 64):
            block = app[offset:offset + 64]
            ota_command(port, f"OTA_DATA:{offset},{block.hex()};",
                        f"OTA_ACK:{offset + len(block)};", timeout)
        ota_command(port, "OTA_END:1;", "OTA_DONE;", timeout)
    except (RuntimeError, TimeoutError):
        port.write(b"OTA_ABORT:1;")
        port.flush()
        raise


def verify_reboot(port, uid, version, wait):
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        time.sleep(1)
        try:
            current_uid, current_version = identity(port, 1)
        except (TimeoutError, ValueError):
            continue
        if current_uid != uid:
            raise RuntimeError("device UID changed after OTA")
        if current_version == version:
            return
    raise TimeoutError("PMIC did not return with the expected version")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "trial-ota"))
    parser.add_argument("--port", required=True, help="PMIC USART3 serial device")
    parser.add_argument("--bundle", help="path to the board-layout manifest.json")
    parser.add_argument("--confirm-uid", help="24-digit UID required for trial-ota")
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--reboot-wait", type=float, default=30)
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.reboot_wait <= 0:
        parser.error("timeouts must be positive")
    if args.command == "trial-ota" and (not args.bundle or not args.confirm_uid):
        parser.error("trial-ota requires --bundle and --confirm-uid")

    try:
        import serial
    except ImportError as exc:
        parser.error(f"python3-serial is required: {exc}")

    try:
        bundle = load_bundle(args.bundle) if args.bundle else None
        if args.command == "trial-ota" and bundle[0]["layout"] != "right":
            raise ValueError("left-layout PMIC has no external Flash and rejects serial OTA")
        with serial.Serial(args.port, 115200, timeout=0.05, write_timeout=args.timeout) as port:
            uid, current = identity(port, args.timeout)
            print(f"UID={uid} FW_VER={current}")
            if args.command == "inspect":
                return 0
            manifest, images = bundle
            if uid != args.confirm_uid.upper():
                raise ValueError("UID confirmation does not match connected PMIC")
            if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+-right", current):
                raise ValueError("connected PMIC is not a right-layout firmware")
            if current == manifest["version"]:
                raise ValueError("target version equals current version; post-OTA version check would be inconclusive")
            print(f"trial OTA: {len(images['app'])} bytes, target {manifest['version']}")
            transfer(port, images["app"], args.timeout)
            verify_reboot(port, uid, manifest["version"], args.reboot_wait)
            print("PMIC rebooted with expected UID and version; flash readback is unavailable")
    except (OSError, ValueError, RuntimeError, TimeoutError, serial.SerialException) as exc:
        print(f"PMIC OTA failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
