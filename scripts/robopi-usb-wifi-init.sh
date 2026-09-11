#!/bin/sh
# Install-time and boot-time preparation; never changes NetworkManager profiles.
set -eu
kver=$(uname -r)
# Load only when aic8800_fdrv exists for the running kernel.
if ! modinfo -k "$kver" aic8800_fdrv >/dev/null 2>&1; then
    echo "robopi-usb-wifi: aic8800_fdrv not found for $kver; skip" >&2
    exit 0
fi
modprobe aic_load_fw
modprobe aic8800_fdrv
udevadm control --reload-rules
# Handle an adapter already plugged in before package installation. Future
# hotplug events use aic.rules. Never issue a global udev trigger.
for disk in /sys/class/block/*; do
    [ -e "$disk" ] || continue
    [ ! -e "$disk/partition" ] || continue
    props=$(udevadm info --query=property --path="$disk") || continue
    printf '%s\n' "$props" | grep -qx 'ID_VENDOR_ID=a69c' || continue
    printf '%s\n' "$props" | grep -Eq '^ID_MODEL_ID=(5721|5722|572a)$' || continue
    eject "/dev/${disk##*/}" || echo "robopi-usb-wifi: eject returned an error for ${disk##*/}; check lsusb for re-enumeration" >&2
done
echo "robopi-usb-wifi: preparation complete; check iw dev for the wireless interface"
