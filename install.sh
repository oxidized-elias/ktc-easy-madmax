#!/bin/bash

KLIPPER_PATH="${HOME}/klipper"
KLIPPY_ENV_PATH="${HOME}/klippy-env"
# Install this checkout, including forks and clones with a different directory name.
INSTALL_PATH="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_PATH="${HOME}/printer_data/config"

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

function install_requirements {
    if [ -f "${INSTALL_PATH}/requirements.txt" ]; then
        echo "[REQUIREMENTS] Installing Python requirements..."
        
        # Use Klipper's Python environment
        if [ -f "${KLIPPY_ENV_PATH}/bin/pip" ]; then
            "${KLIPPY_ENV_PATH}/bin/pip" install -r "${INSTALL_PATH}/requirements.txt"
            printf "[REQUIREMENTS] Requirements installed successfully!\n\n"
        else
            echo "[ERROR] Klipper Python environment not found at ${KLIPPY_ENV_PATH}"
            exit -1
        fi
    else
        printf "[REQUIREMENTS] No requirements.txt found, skipping...\n\n"
    fi
}

function use_tap_per_tool {
    echo "[INSTALL] Tap Per Tool"

    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/tool_detection.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs/
    cp -n "${INSTALL_PATH}"/examples/easy-additions/user-configs/tools/tap_per_tool/* "${CONFIG_PATH}"/toolchanger/tools
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/user-configs/toolchanger-include.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs/toolchanger-include.cfg
}

function z_probe_on_shuttle {
    echo "[INSTALL] Z Probe on Shuttle"

    cp -n "${INSTALL_PATH}"/examples/easy-additions/user-configs/tools/probe_on_shuttle/* "${CONFIG_PATH}"/toolchanger/tools
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/user-configs/toolchanger-include_scanner.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs/toolchanger-include.cfg
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper..."
    for file in "${INSTALL_PATH}"/klipper/extras/*.py; do ln -sfn "${file}" "${KLIPPER_PATH}/klippy/extras/"; done
}

function do_shared_config {

    mkdir -p "${CONFIG_PATH}"/toolchanger
    mkdir -p "${CONFIG_PATH}"/toolchanger/tools
    mkdir -p "${CONFIG_PATH}"/toolchanger/readonly-configs

    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/toolchanger.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/homing.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/calibrate-offsets.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/toolchanger-macros.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs
    ln -sfn "${INSTALL_PATH}"/examples/easy-additions/crash-detection.cfg "${CONFIG_PATH}"/toolchanger/readonly-configs

    cp -n "${INSTALL_PATH}"/examples/easy-additions/user-configs/toolchanger-config.cfg "${CONFIG_PATH}"/toolchanger
}

function z_probe_option {
    echo -e "\n\n\nHow will you Z probe?"
    echo "1. I will use the TAP sensor as my Z probe on each tool"
    echo "2. I will use a shuttle mounted Beacon/Cartographer/Eddy/etc as my Z probe"
    read -rp "Select an option [1-2]: " z_probe_choice

    case $z_probe_choice in
        1)
            use_tap_per_tool
            ;;
        2)
            z_probe_on_shuttle
            ;;
        *)
            echo "[ERROR] Invalid option selected!"
            exit -1
            ;;
    esac
}

function restart_klipper {
    echo "[POST-INSTALL] Restarting Klipper..."
    sudo systemctl restart klipper
}

function toolchanger_option {
    echo "Which toolchanger do you use?"
    echo "1. StealthChanger (existing Easy Install paths)"
    echo "2. MadMax (experimental XY docking, per-tool coupling probes)"
    read -rp "Select an option [1-2]: " toolchanger_choice
    case "$toolchanger_choice" in
        1|2) ;;
        *) echo "[ERROR] Invalid toolchanger option selected!"; return 1 ;;
    esac
}

function use_madmax {
    echo "[INSTALL] MadMax: using per-tool Maxwell coupling probes"
    use_tap_per_tool
    ln -sfn "${INSTALL_PATH}/examples/madmax/toolchanger.cfg" "${CONFIG_PATH}/toolchanger/readonly-configs/madmax.cfg"
    ln -sfn "${INSTALL_PATH}/examples/madmax/toolchanger-include.cfg" "${CONFIG_PATH}/toolchanger/readonly-configs/toolchanger-include.cfg"
    # Never overwrite measured coordinates on a subsequent installation.
    if [ ! -e "${CONFIG_PATH}/toolchanger/madmax-user.cfg" ]; then
        cp "${INSTALL_PATH}/examples/madmax/madmax-user.cfg" "${CONFIG_PATH}/toolchanger/madmax-user.cfg"
    fi
    echo "[MADMAX] Profile installed. Configure tools and toolchanger/madmax-user.cfg."
    echo "[MADMAX] Use only [include toolchanger/readonly-configs/toolchanger-include.cfg] in printer.cfg."
    echo "[MADMAX] Remove any older manual MadMax includes to avoid duplicate sections."
    echo "[MADMAX] Docking is blocked until each tool is marked calibrated."
    echo "[MADMAX] Klipper was not restarted. Review homing and configs, then restart manually."
}

function main {
    printf "\n- Klipper toolchanger install script -\n\n"
    preflight_checks
    # Choose before changing any installed configuration.
    toolchanger_option
    install_requirements
    do_shared_config
    link_extension
    if [ "$toolchanger_choice" = 2 ]; then
        use_madmax
    else
        z_probe_option
        restart_klipper
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
