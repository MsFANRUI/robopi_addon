#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
mkdir -p "$tmpdir/bin" "$tmpdir/capture" "$tmpdir/snapshots"
printf 'pcap-data\n' > "$tmpdir/capture/usbcan.pcap0"

cat > "$tmpdir/bin/systemctl" <<'EOF'
#!/bin/sh
printf 'systemctl:%s\n' "$*" >> "$USBCAN_TEST_LOG"
case $1 in
    is-active) exit 0 ;;
    stop|start) exit 0 ;;
    *) exit 1 ;;
esac
EOF
for command_name in lsusb ip journalctl dmesg; do
    cat > "$tmpdir/bin/$command_name" <<EOF
#!/bin/sh
printf '$command_name:%s\n' "\$*"
EOF
done
chmod +x "$tmpdir/bin"/*

output=$(
    PATH="$tmpdir/bin:/usr/bin:/bin" \
    USBCAN_ALLOW_NON_ROOT=yes \
    USBCAN_CAPTURE_DIR="$tmpdir/capture" \
    USBCAN_SNAPSHOT_DIR="$tmpdir/snapshots" \
    USBCAN_SNAPSHOT_LOCK="$tmpdir/snapshot.lock" \
    USBCAN_TEST_LOG="$tmpdir/systemctl.log" \
    scripts/usbcan-debug-snapshot.sh
)

[[ -f "$output/usbcan.pcap0" ]]
cmp "$tmpdir/capture/usbcan.pcap0" "$output/usbcan.pcap0"
[[ -f "$output/lsusb.txt" && -f "$output/dmesg.txt" ]]
grep -q '^systemctl:stop usbcan-capture.service$' "$tmpdir/systemctl.log"
grep -q '^systemctl:start usbcan-capture.service$' "$tmpdir/systemctl.log"

echo 'PASS: snapshot copies capture and diagnostics, then restarts active service'
