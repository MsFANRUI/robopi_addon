#!/bin/sh
set -eu

service=${USBCAN_CAPTURE_SERVICE:-usbcan-capture.service}
source_dir=${USBCAN_CAPTURE_DIR:-/run/usbcan}
snapshot_root=${USBCAN_SNAPSHOT_DIR:-/var/log/usbcan-snapshots}
lock_file=${USBCAN_SNAPSHOT_LOCK:-/run/lock/usbcan-debug-snapshot.lock}
timestamp=$(date +%Y%m%d-%H%M%S)
destination=$snapshot_root/$timestamp
was_active=no

if [ "${USBCAN_ALLOW_NON_ROOT:-no}" != yes ] && [ "$(id -u)" -ne 0 ]; then
    echo "usbcan-debug-snapshot: run as root" >&2
    exit 1
fi

exec 9>"$lock_file"
flock -n 9 || {
    echo "usbcan-debug-snapshot: another snapshot is running" >&2
    exit 1
}

if systemctl is-active --quiet "$service"; then
    was_active=yes
    systemctl stop "$service"
fi

restart_capture()
{
    if [ "$was_active" = yes ]; then
        systemctl start "$service" || true
    fi
}
trap restart_capture EXIT HUP INT TERM

[ -d "$source_dir" ] || {
    echo "usbcan-debug-snapshot: capture directory not found: $source_dir" >&2
    exit 1
}
set -- "$source_dir"/usbcan.pcap*
[ -e "$1" ] || {
    echo "usbcan-debug-snapshot: no usbcan.pcap files in $source_dir" >&2
    exit 1
}

[ ! -e "$destination" ] || {
    echo "usbcan-debug-snapshot: destination already exists: $destination" >&2
    exit 1
}
install -d -m 0750 "$destination"
cp -a "$source_dir"/usbcan.pcap* "$destination"/

lsusb > "$destination/lsusb.txt" 2>&1 || true
lsusb -t > "$destination/lsusb-tree.txt" 2>&1 || true
ip -details -statistics link show type can \
    > "$destination/can-interfaces.txt" 2>&1 || true
journalctl -u "$service" -b --no-pager \
    > "$destination/usbcan-capture-journal.txt" 2>&1 || true
dmesg --ctime > "$destination/dmesg.txt" 2>&1 || true

restart_capture
was_active=no
trap - EXIT HUP INT TERM

echo "$destination"
