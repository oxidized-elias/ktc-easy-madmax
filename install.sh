#!/bin/bash

KLIPPER_PATH="${HOME}/klipper"
INSTALL_PATH="${HOME}/klipper-toolchanger"
CONFIG_PATH="${HOME}/printer_data/config"
# Use this checkout when run locally; preserve wget | bash download behavior.
if [ -n "${BASH_SOURCE[0]:-}" ]; then
    script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
    if [ -d "${script_dir}/klipper/extras" ]; then
        INSTALL_PATH="$script_dir"
    fi
fi

set -eu
export LC_ALL=C

function preflight_checks {
    if [ "$EUID" -eq 0 ]; then
        echo "[PRE-CHECK] This script must not be run as root!"
        exit -1
    fi

    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F 'klipper.service')" ]; then
        printf "[PRE-CHECK] Klipper service found! Continuing...\n\n"
    else
        echo "[ERROR] Klipper service not found, please install Klipper first!"
        exit -1
    fi
}

function check_download {
    local installdirname installbasename
    installdirname="$(dirname "${INSTALL_PATH}")"
    installbasename="$(basename "${INSTALL_PATH}")"

    if [ ! -d "${INSTALL_PATH}" ]; then
        echo "[DOWNLOAD] Downloading repository..."
        if git -C "${installdirname}" clone https://github.com/contomo/klipper-toolchanger-hard.git "${installbasename}"; then
            chmod +x "${INSTALL_PATH}/install.sh"
            printf "[DOWNLOAD] Download complete!\n\n"
        else
            echo "[ERROR] Download of git repository failed!"
            exit -1
        fi
    else
        printf "[DOWNLOAD] repository already found locally. Continuing...\n\n"
    fi
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper (extras)..."

    local src="${INSTALL_PATH}/klipper/extras"
    local dst="${KLIPPER_PATH}/klippy/extras"

    if [ ! -d "$src" ]; then
        echo "[ERROR] Extras directory not found at: $src"
        exit 1
    fi

    mkdir -p "$dst"
    shopt -s nullglob dotglob
    local found=0
    
    for path in "$src"/*.py "$src"/*/; do # Link top-level .py files and top-level package dirs
        [ -e "$path" ] || continue
        found=1

        if [ -d "$path" ]; then
            path="${path%/}"
            if [ ! -f "$path/__init__.py" ]; then
                continue
            fi
        fi
        base="${path##*/}"
        case "$base" in
            __pycache__|*.dist-info|*.egg-info) continue ;;
        esac
        ln -sfn "$path" "$dst/$base"
        echo "  → $base"
    done
    shopt -u nullglob dotglob
    if [ "$found" -eq 0 ]; then
        echo "[WARN] No .py files or package dirs found under: $src"
    fi
}

function restart_klipper {
    echo "[POST-INSTALL] Restarting Klipper..."
    sudo systemctl restart klipper
}

function profile_option {
    profile=extensions
    case "${1:-}" in
        --madmax) profile=madmax ;;
        --extensions-only) ;;
        --help|-h)
            echo "Usage: install.sh [--madmax|--extensions-only]"
            echo "Without arguments: prompt in a terminal; install extensions only for piped input."
            return 2 ;;
        "")
            if [ -t 0 ]; then
                echo "1. Extensions only (keep your existing toolchanger configuration)"
                echo "2. MadMax (experimental front/side-keyslot XY profile)"
                read -rp "Select an option [1-2]: " profile_choice
                case "$profile_choice" in
                    1) ;;
                    2) profile=madmax ;;
                    *) echo "[ERROR] Invalid profile choice"; return 1 ;;
                esac
            fi ;;
        *) echo "[ERROR] Unknown option: $1"; return 1 ;;
    esac
    if [ "$#" -gt 1 ]; then
        echo "[ERROR] Supply only one profile option"; return 1
    fi
}

function install_madmax {
    local target="${CONFIG_PATH}/toolchanger"
    mkdir -p "$target"
    ln -sfn "${INSTALL_PATH}/examples/madmax/toolchanger.cfg" "$target/madmax.cfg"
    ln -sfn "${INSTALL_PATH}/examples/madmax/madmax-include.cfg" "$target/madmax-include.cfg"
    if [ ! -e "$target/madmax-user.cfg" ]; then
        cp "${INSTALL_PATH}/examples/madmax/madmax-user.cfg" "$target/madmax-user.cfg"
    fi
    echo "[MADMAX] Installed profile; existing madmax-user.cfg was preserved."
    echo "[MADMAX] Configure native detection_pin on every tool and measure dock coordinates."
    echo "[MADMAX] Replace your old dock motion include with:"
    echo "         [include toolchanger/madmax-include.cfg]"
    echo "[MADMAX] Review homing/probing and examples/madmax/README.md before restarting."
    echo "[MADMAX] Klipper was not restarted; docking stays blocked until calibrated."
}

function main {
    local option_status=0
    profile_option "$@" || option_status=$?
    if [ "$option_status" -eq 2 ]; then return 0; fi
    if [ "$option_status" -ne 0 ]; then return "$option_status"; fi
    preflight_checks
    check_download
    link_extension
    if [ "$profile" = madmax ]; then
        install_madmax
    else
        restart_klipper
    fi
}

# BASH_SOURCE is empty when the supported wget | bash installation is used.
if [ "${BASH_SOURCE[0]:-}" = "$0" ] || [ -z "${BASH_SOURCE[0]:-}" ]; then
    main "$@"
fi
