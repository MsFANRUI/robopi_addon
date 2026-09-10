#!/bin/sh
# SPDX-License-Identifier: GPL-3.0

set -eu

GPIO=52                 # GPIO1_C4 = 1 * 32 + 2 * 8 + 4
GPIO_DIR="/sys/class/gpio/gpio${GPIO}"
EXPORT="/sys/class/gpio/export"

usage()
{
    echo "Usage: sudo ~/led.sh {on|off|status}" >&2
    exit 2
}

require_root()
{
    if [ "$(id -u)" -ne 0 ]; then
        echo "led.sh: root privileges are required; run with sudo" >&2
        exit 1
    fi
}

ensure_exported()
{
    if [ ! -d "$GPIO_DIR" ]; then
        if ! printf '%s\n' "$GPIO" > "$EXPORT" 2>/dev/null; then
            echo "led.sh: cannot request GPIO1_C4 (GPIO${GPIO}); it may be owned by another driver" >&2
            exit 1
        fi

        count=0
        while [ ! -e "$GPIO_DIR/direction" ] && [ "$count" -lt 50 ]; do
            sleep 0.01
            count=$((count + 1))
        done
    fi

    if [ ! -e "$GPIO_DIR/direction" ]; then
        echo "led.sh: GPIO${GPIO} sysfs interface did not appear" >&2
        exit 1
    fi
}

set_light()
{
    level=$1
    label=$2

    # set GPIO 
    printf '%s\n' "$level" > "$GPIO_DIR/direction"
    actual=$(cat "$GPIO_DIR/value")
    echo "LIGHT_PWR ${label}: GPIO1_C4=GPIO${GPIO}, value=${actual}"

    # Call WS2812 command according to the level
    if [ "$level" = "high" ]; then
        if command -v robopi-ws2812 >/dev/null 2>&1; then
            robopi-ws2812 solid 30 30 30
        else
            echo "Warning: robopi-ws2812 command not found, skipping LED control" >&2
        fi
    else
        if command -v robopi-ws2812 >/dev/null 2>&1; then
            robopi-ws2812 solid 0 0 0
        else
            echo "Warning: robopi-ws2812 command not found, skipping LED control" >&2
        fi
    fi
}

show_status()
{
    if [ ! -d "$GPIO_DIR" ]; then
        echo "LIGHT_PWR status: unclaimed (light state is controlled by the pin default)"
        return
    fi

    direction=$(cat "$GPIO_DIR/direction")
    value=$(cat "$GPIO_DIR/value")
    if [ "$direction" = "out" ] && [ "$value" = "1" ]; then
        state=on
    elif [ "$direction" = "out" ] && [ "$value" = "0" ]; then
        state=off
    else
        state=unknown
    fi
    echo "LIGHT_PWR status: ${state} (GPIO1_C4=GPIO${GPIO}, direction=${direction}, value=${value})"
}

[ "$#" -eq 1 ] || usage

case "$1" in
    on)
        require_root
        ensure_exported
        set_light high ON
        ;;
    off)
        require_root
        ensure_exported
        set_light low OFF
        ;;
    status)
        show_status
        ;;
    *)
        usage
        ;;
esac