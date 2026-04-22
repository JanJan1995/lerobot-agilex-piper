#!/bin/bash

# =============================================================================
# Piper Master/Slave Mode Setup Script
# =============================================================================
# This script sets the master/slave mode for two Piper arms connected to
# the same CAN bus. Since MasterSlaveConfig is a broadcast command (CAN ID 0x470),
# you must set each arm individually — only one arm should be connected to the
# CAN bus at a time during setup.
#
# Prerequisites:
#   1. CAN interface is activated (e.g. can0)
#   2. python-can and piper_sdk are installed in the conda environment
#
# Usage:
#   bash piper_scripts/setup_piper_master_slave.sh
# =============================================================================

set -e

CAN_NAME="${1:-can0}"
CONDA_ENV="piper_lerobot"

echo "========================================================================"
echo "  Piper Master/Slave Mode Setup"
echo "========================================================================"
echo ""
echo "  CAN interface: $CAN_NAME"
echo ""
echo "  IMPORTANT: MasterSlaveConfig is a BROADCAST command. Both arms on the"
echo "  same bus will receive it. You MUST set them one at a time."
echo ""
echo "========================================================================"
echo ""

# Check CAN is up
if ! ip link show "$CAN_NAME" &>/dev/null; then
    echo "ERROR: CAN interface '$CAN_NAME' does not exist."
    echo "       Run the CAN activation script first:"
    echo "         sudo bash \$CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh"
    exit 1
fi

if ! ip link show "$CAN_NAME" | grep -q "UP"; then
    echo "ERROR: CAN interface '$CAN_NAME' is DOWN."
    echo "       Bring it up with: sudo ip link set $CAN_NAME up"
    exit 1
fi

echo "✓ CAN interface '$CAN_NAME' is UP"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Set MASTER arm
# ---------------------------------------------------------------------------
echo "------------------------------------------------------------------------"
echo "STEP 1: Set MASTER arm (teaching input)"
echo "------------------------------------------------------------------------"
echo ""
echo "  1. Make sure ONLY the MASTER arm is connected to the CAN bus."
echo "  2. Disconnect the SLAVE arm (unplug its CAN cable or power it off)."
echo ""
read -p "Press ENTER when only the MASTER arm is connected..."
echo ""

conda run -n "$CONDA_ENV" python -c "
from piper_sdk import C_PiperInterface_V2
import time

print('Connecting to $CAN_NAME ...')
piper = C_PiperInterface_V2('$CAN_NAME')
piper.ConnectPort()
time.sleep(0.5)

print('Setting MASTER mode (0xFA, teaching input) ...')
piper.MasterSlaveConfig(0xFA, 0, 0, 0)
time.sleep(0.5)

print('Done. Master arm configured.')
piper.DisconnectPort()
"

echo ""
echo "✓ Master arm set to 0xFA (teaching input)"
echo ""

# ---------------------------------------------------------------------------
# Step 2: Set SLAVE arm
# ---------------------------------------------------------------------------
echo "------------------------------------------------------------------------"
echo "STEP 2: Set SLAVE arm (motion output)"
echo "------------------------------------------------------------------------"
echo ""
echo "  1. Disconnect the MASTER arm (unplug its CAN cable or power it off)."
echo "  2. Connect ONLY the SLAVE arm to the CAN bus."
echo ""
read -p "Press ENTER when only the SLAVE arm is connected..."
echo ""

conda run -n "$CONDA_ENV" python -c "
from piper_sdk import C_PiperInterface_V2
import time

print('Connecting to $CAN_NAME ...')
piper = C_PiperInterface_V2('$CAN_NAME')
piper.ConnectPort()
time.sleep(0.5)

print('Setting SLAVE mode (0xFC, motion output) ...')
piper.MasterSlaveConfig(0xFC, 0, 0, 0)
time.sleep(0.5)

print('Done. Slave arm configured.')
piper.DisconnectPort()
"

echo ""
echo "✓ Slave arm set to 0xFC (motion output)"
echo ""

# ---------------------------------------------------------------------------
# Step 3: Power-on sequence
# ---------------------------------------------------------------------------
echo "------------------------------------------------------------------------"
echo "STEP 3: Power-on sequence for teleoperation"
echo "------------------------------------------------------------------------"
echo ""
echo "  1. Connect BOTH arms to the same CAN bus ($CAN_NAME)."
echo "  2. Power on the SLAVE arm FIRST."
echo "  3. Wait 3-5 seconds."
echo "  4. Power on the MASTER arm."
echo "  5. Wait 3-5 seconds for arms to stabilise."
echo ""
read -p "Press ENTER when both arms are powered on (slave first, then master)..."
echo ""

echo "========================================================================"
echo "  Setup complete!"
echo "========================================================================"
echo ""
echo "  You can now run teleoperation:"
echo ""
echo "    bash piper_scripts/teleop_piper.sh"
echo ""
echo "========================================================================"
