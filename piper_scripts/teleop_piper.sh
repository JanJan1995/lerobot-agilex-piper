#!/bin/bash

# =============================================================================
# Piper Master/Slave Teleoperation Script (Single CAN)
# =============================================================================
# Both arms share the same CAN bus (can0 by default).
#
# Prerequisites:
#   1. Activate CAN: bash piper_scripts/can_activate.sh
#   2. Set one Piper as MASTER, the other as SLAVE (via hardware switch or SDK).
#   3. Power on the SLAVE arm first, then the MASTER arm.
#
# Usage:
#   bash piper_scripts/teleop_piper.sh
#
# With camera (uncomment the CAMERA block below and comment out the basic one):
#   bash piper_scripts/teleop_piper.sh
# =============================================================================

set -e

echo "Starting Piper teleoperation (single CAN master/slave)..."
echo "  Shared CAN: can0"
echo "  Make sure SLAVE arm is powered on BEFORE the MASTER arm."
echo "  Press 'q' to quit gracefully."
echo ""

# ---------------------------------------------------------------------------
# Basic teleoperation (no camera)
# ---------------------------------------------------------------------------
# lerobot-teleoperate \
#     --robot.type=piper_follower \
#     --robot.can_name=can0 \
#     --teleop.type=piper_leader \
#     --teleop.can_name=can0 \
#     --fps=30

# ---------------------------------------------------------------------------
# Teleoperation with camera (uncomment below to use)
# ---------------------------------------------------------------------------
# Adjust index_or_path, width, height, fps to match your setup.
# Use 'v4l2-ctl --list-devices' to find the correct camera index.
# 
lerobot-teleoperate \
    --robot.type=piper_follower \
    --robot.can_name=can0 \
    --robot.cameras='{
        wrist: {type: opencv, index_or_path: "/dev/video4", width: 640, height: 480, fps: 30},
        up:    {type: opencv, index_or_path: "/dev/video10", width: 640, height: 480, fps: 30}
    }' \
    --teleop.type=piper_leader \
    --teleop.can_name=can0 \
    --display_data=true \
    --fps=30
