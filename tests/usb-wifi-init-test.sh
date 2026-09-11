#!/bin/bash
# Non-mutating tests: mock all commands that can touch hardware.
set -eu
cd "$(dirname "$0")/.."
uname() { printf '%s\n' "$mock_kernel"; }
modinfo() {
    # modinfo -k <kver> aic8800_fdrv
    if [ "${mock_modinfo_rc:-0}" -eq 0 ]; then
        printf '%s\n' 'filename: mock/aic8800_fdrv.ko'
        return 0
    fi
    return 1
}
modprobe() { printf 'MODPROBE:%s\n' "$1"; return "${mock_modprobe_rc:-0}"; }
udevadm() { printf '%s\n' 'ID_VENDOR_ID=0000'; }
eject() { echo 'ERROR: unrelated disk ejected'; return 1; }

mock_kernel=unrelated-kernel
mock_modinfo_rc=1
out=$( . scripts/robopi-usb-wifi-init.sh 2>&1 )
[[ "$out" == *'aic8800_fdrv not found'* && "$out" != *MODPROBE* ]]

mock_kernel=6.18.51-current-rockchip64
mock_modinfo_rc=0
out=$( . scripts/robopi-usb-wifi-init.sh )
[[ "$out" == *MODPROBE:aic_load_fw* && "$out" == *MODPROBE:aic8800_fdrv* ]]
[[ "$out" == *'preparation complete'* && "$out" != *ERROR* ]]

echo 'PASS: missing modules skipped; present modules loaded; unrelated disks untouched'
