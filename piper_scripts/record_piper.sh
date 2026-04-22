#!/bin/bash

# =============================================================================
# Piper Master/Slave Dataset Recording Script (Single CAN, Dual Camera)
# =============================================================================
# Both arms share the same CAN bus (can0 by default).
# Two cameras: wrist (arm-mounted) + up (global overhead, from stereo depth cam).
#
# Prerequisites:
#   1. Activate CAN: bash $CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh
#   2. Set master/slave modes: bash piper_scripts/setup_piper_master_slave.sh
#   3. Power on the SLAVE arm first, then the MASTER arm.
#
# Usage:
#   bash piper_scripts/record_piper.sh [task_name] [num_episodes]
#
# Defaults:
#   task_name     = "piper_task"
#   num_episodes  = 50
#   dataset_root  = /home/mc509/Workspace/VLA/Piper/datasets
# =============================================================================

set -e

TASK_NAME="${1:-piper_task}"
NUM_EPISODES="${2:-50}"

# HuggingFace repo_id cannot contain spaces; replace with underscores
SAFE_TASK_NAME="${TASK_NAME// /_}"

HF_USER="${HF_USER:-$USER}"
REPO_ID="${HF_USER}/${SAFE_TASK_NAME}"
DATASET_ROOT="/home/mc509/Workspace/VLA/Piper/datasets/${SAFE_TASK_NAME}"

echo "========================================"
echo "Piper Dataset Recording (Single CAN)"
echo "========================================"
echo "Task:        $TASK_NAME"
echo "Episodes:    $NUM_EPISODES"
echo "Repo ID:     $REPO_ID"
echo "Dataset:     $DATASET_ROOT"
echo "Shared CAN:  can0"
echo "Cameras:     wrist (/dev/video4) + up (/dev/video10)"
echo ""

lerobot-record \
    --robot.type=piper_follower \
    --robot.can_name=can0 \
    --robot.id=piper_slave \
    --robot.cameras='{
        wrist: {type: opencv, index_or_path: "/dev/video4", width: 640, height: 480, fps: 30, color_mode: rgb},
        up:    {type: opencv, index_or_path: "/dev/video10", width: 640, height: 480, fps: 30, color_mode: rgb}
    }' \
    --teleop.type=piper_leader \
    --teleop.can_name=can0 \
    --teleop.id=piper_master \
    --dataset.repo_id="$REPO_ID" \
    --dataset.root="$DATASET_ROOT" \
    --dataset.num_episodes="$NUM_EPISODES" \
    --dataset.single_task="$TASK_NAME" \
    --dataset.fps=30 \
    --dataset.episode_time_s=60 \
    --dataset.reset_time_s=30 \
    --dataset.push_to_hub=false \
    --dataset.video=true \
    --display_data=true \
    --resume=false

echo ""
echo "Recording complete. Dataset saved to: $DATASET_ROOT"
