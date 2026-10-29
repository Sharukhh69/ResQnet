#!/bin/bash
# ResQ-Mesh Gateway Setup Script for Raspberry Pi OS (Bookworm / Bullseye)
set -e

echo "=========================================================="
echo "  ResQnet / ResQ-Mesh Gateway Environment Setup"
echo "=========================================================="

# 1. Check & Enable SPI interface
echo "[1/4] Checking hardware SPI interface..."
if ! ls /dev/spidev0.* > /dev/null 2>&1; then
    echo "Enabling SPI via raspi-config..."
    sudo raspi-config nonint do_spi 0
    echo "SPI enabled. If /dev/spidev0.0 does not appear, reboot may be required."
else
    echo "SPI is already active (/dev/spidev0.0 detected)."
fi

# 2. Install apt system dependencies
echo "[2/4] Installing system packages..."
sudo apt-get update
sudo apt-get install -y python3-pip python3-spidev git

# 3. Setup pySX127x driver
echo "[3/4] Setting up pySX127x LoRa driver..."
if [ ! -d "$HOME/pySX127x" ]; then
    echo "Cloning pySX127x into $HOME/pySX127x..."
    git clone https://github.com/rpsreal/pySX127x.git "$HOME/pySX127x"
else
    echo "pySX127x already present in $HOME/pySX127x."
fi

# 4. Install python requirements
echo "[4/4] Installing Python requirements..."
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

echo "=========================================================="
echo "  Setup Complete! Launch Gateway with:"
echo "  sudo python3 base_station.py"
echo "=========================================================="
