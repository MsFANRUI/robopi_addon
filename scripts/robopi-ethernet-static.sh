#!/bin/bash
set -euo pipefail

die() { echo "robopi-ethernet-static: $*" >&2; exit 1; }

uuid=$(nmcli -g connection.uuid connection show id "Wired connection 1")
[[ -n $uuid && $uuid != *$'\n'* ]] || die '有线连接 1 不存在或不唯一，未修改网络。'
connection_type=$(nmcli -g connection.type connection show uuid "$uuid")
[[ $connection_type == 802-3-ethernet ]] || die '目标连接不是有线连接，未修改网络。'
interface=$(nmcli -g connection.interface-name connection show uuid "$uuid")
[[ -n $interface && $interface != -- && $interface != */* ]] || die '目标连接未绑定有效网口，未修改网络。'
device_type=$(nmcli -g GENERAL.TYPE device show "$interface")
[[ $device_type == ethernet ]] || die '目标设备不是有线网口，未修改网络。'

nmcli connection modify uuid "$uuid" \
    connection.autoconnect yes \
    ipv4.method manual ipv4.addresses 192.168.13.1/24 \
    ipv4.gateway "" ipv4.never-default yes ipv4.ignore-auto-dns yes \
    ipv6.gateway "" ipv6.never-default yes ipv6.ignore-auto-dns yes

carrier=$(cat "/sys/class/net/$interface/carrier" 2>/dev/null || true)
if [[ $carrier == 1 ]]; then
    nmcli --wait 30 connection up uuid "$uuid" ifname "$interface"
else
    echo "robopi-ethernet-static: $interface 已保存静态地址，等待网线连接后自动激活。"
fi
