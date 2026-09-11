#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

mkdir -p "$tmpdir/bin" "$tmpdir/sys/class/net/can0" \
    "$tmpdir/devices/usb3/3-1/3-1:1.0" "$tmpdir/capture"
printf '003\n' > "$tmpdir/devices/usb3/3-1/busnum"
ln -s "$tmpdir/devices/usb3/3-1/3-1:1.0" \
    "$tmpdir/sys/class/net/can0/device"

cat > "$tmpdir/bin/modprobe" <<'EOF'
#!/bin/sh
printf 'modprobe:%s\n' "$*"
EOF
cat > "$tmpdir/bin/tcpdump" <<'EOF'
#!/bin/sh
printf 'tcpdump:%s\n' "$*"
EOF
chmod +x "$tmpdir/bin/modprobe" "$tmpdir/bin/tcpdump"

run_capture()
{
    USBCAN_SYS_CLASS_NET="$tmpdir/sys/class/net" \
    USBCAN_MODPROBE_BIN="$tmpdir/bin/modprobe" \
    USBCAN_TCPDUMP_BIN="$tmpdir/bin/tcpdump" \
    USBCAN_ALLOW_NON_RUN_CAPTURE_DIR=yes \
    CAPTURE_DIR="$tmpdir/capture" \
    "$@" scripts/usbcan-capture.sh
}

output=$(run_capture env USBMON_IFACE=auto CAN_INTERFACE=can0 \
    FILE_SIZE_MB=64 FILE_COUNT=8)
[[ $output == *'modprobe:usbmon'* ]]
[[ $output == *'recording usbmon3'* ]]
[[ $output == *"tcpdump:-Z root -i usbmon3 -s 0 -B 16384 -U -C 64 -W 8"* ]]

output=$(run_capture env USBMON_IFACE=usbmon6 FILE_SIZE_MB=32 FILE_COUNT=4)
[[ $output == *'recording usbmon6'* ]]
[[ $output == *'-C 32 -W 4'* ]]

if run_capture env USBMON_IFACE=usbmon3oops >/dev/null 2>&1; then
    echo 'invalid USBMON_IFACE was accepted' >&2
    exit 1
fi
if run_capture env FILE_SIZE_MB=0 >/dev/null 2>&1; then
    echo 'invalid FILE_SIZE_MB was accepted' >&2
    exit 1
fi

echo 'PASS: automatic bus resolution, explicit interface, arguments and validation'
