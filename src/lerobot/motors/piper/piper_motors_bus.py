#!/usr/bin/env python

# Copyright 2025 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Piper Motors Bus driver for LeRobot — Single-CAN Master/Slave Mode.

This module supports Piper's official dual-arm setup where both the master
(leader) and slave (follower) arms are connected to the SAME CAN bus.

In this mode:
  - Master arm sends control frames (CAN IDs: 0x155, 0x156, 0x157, 0x159, 0x151)
  - Slave arm executes them and sends feedback frames

All external positions are in **radians**.
"""

import logging
from dataclasses import dataclass
from typing import Dict

from lerobot.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

logger = logging.getLogger(__name__)


@dataclass
class PiperMotorsBusConfig:
    """Configuration for PiperMotorsBus."""

    can_name: str
    motors: dict[str, tuple[int, str]]


class PiperMotorsBus:
    """
    Low-level driver for Agilex Piper arm via CAN bus.

    Supports both single-arm and dual-arm (master/slave) setups.
    When used in dual-arm mode, the same CAN interface is shared.
    """

    def __init__(self, config: PiperMotorsBusConfig):
        try:
            from piper_sdk import C_PiperInterface_V2
        except ImportError as e:
            raise ImportError(
                "piper_sdk is not installed. Please install it with:\n"
                "  pip install piper_sdk\n"
                "Also ensure CAN interface is up (e.g. can0)."
            ) from e

        self.can_name = config.can_name
        # piper_sdk internally prevents duplicate instances for the same can_port
        self.piper = C_PiperInterface_V2(config.can_name)
        # Avoid calling ConnectPort() multiple times on the same instance,
        # which would start duplicate reader threads and cause CAN state corruption.
        if not self.piper.get_connect_status():
            self.piper.ConnectPort()
        self.motors = config.motors

        # Conversion factor: 0.001 deg -> rad
        self.joint_factor = 57324.840764  # 1000 * 180 / pi

        # Conversion factor: µm -> meters (gripper unit is µm per SDK doc)
        self.gripper_factor = 1_000_000.0

        self._is_connected = False

    @property
    def motor_names(self) -> list[str]:
        return list(self.motors.keys())

    @property
    def motor_models(self) -> list[str]:
        return [model for _, model in self.motors.values()]

    @property
    def motor_indices(self) -> list[int]:
        return [idx for idx, _ in self.motors.values()]

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def connect(self) -> None:
        """Enable the Piper arm."""
        if self._is_connected:
            raise DeviceAlreadyConnectedError(
                f"PiperMotorsBus('{self.can_name}') is already connected."
            )

        self.piper.EnableArm(7)
        self.piper.GripperCtrl(0, 1000, 0x01, 0)
        self._is_connected = True
        logger.info(f"PiperMotorsBus('{self.can_name}') connected and enabled.")

    def disconnect(self) -> None:
        """Mark the bus as disconnected without sending any hardware commands.

        NOTE: We intentionally do NOT call DisableArm() or ModeCtrl(Standby)
        here. Cutting torque causes the arm to free-fall under gravity.
        Sending ModeCtrl(Standby) breaks the MasterSlaveConfig setup,
        destroying the master/slave linkage. Instead, we simply stop the
        Python control loop and leave the hardware in its current state.
        """
        if not self._is_connected:
            raise DeviceNotConnectedError(
                f"PiperMotorsBus('{self.can_name}') is not connected."
            )

        self._is_connected = False
        logger.info(
            f"PiperMotorsBus('{self.can_name}') disconnected. "
            f"Hardware left in current state (master/slave linkage preserved)."
        )

    def read(self) -> Dict[str, float]:
        """
        Read current joint positions from the connected Piper (feedback).
        Returns dict mapping motor name to position in **radians**.
        """
        if not self._is_connected:
            raise DeviceNotConnectedError(
                f"PiperMotorsBus('{self.can_name}') is not connected."
            )

        joint_msg = self.piper.GetArmJointMsgs()
        joint_state = joint_msg.joint_state

        gripper_msg = self.piper.GetArmGripperMsgs()
        gripper_state = gripper_msg.gripper_state

        return {
            "joint_1": joint_state.joint_1 / self.joint_factor,
            "joint_2": joint_state.joint_2 / self.joint_factor,
            "joint_3": joint_state.joint_3 / self.joint_factor,
            "joint_4": joint_state.joint_4 / self.joint_factor,
            "joint_5": joint_state.joint_5 / self.joint_factor,
            "joint_6": joint_state.joint_6 / self.joint_factor,
            "gripper": gripper_state.grippers_angle / self.gripper_factor,
        }

    def read_ctrl(self) -> Dict[str, float]:
        """
        Read the master arm's control commands from the CAN bus.
        Returns dict mapping motor name to target position in **radians**.
        """
        if not self._is_connected:
            raise DeviceNotConnectedError(
                f"PiperMotorsBus('{self.can_name}') is not connected."
            )

        joint_ctrl = self.piper.GetArmJointCtrl()
        joint_data = joint_ctrl.joint_ctrl

        gripper_ctrl = self.piper.GetArmGripperCtrl()
        gripper_data = gripper_ctrl.gripper_ctrl

        return {
            "joint_1": joint_data.joint_1 / self.joint_factor,
            "joint_2": joint_data.joint_2 / self.joint_factor,
            "joint_3": joint_data.joint_3 / self.joint_factor,
            "joint_4": joint_data.joint_4 / self.joint_factor,
            "joint_5": joint_data.joint_5 / self.joint_factor,
            "joint_6": joint_data.joint_6 / self.joint_factor,
            "gripper": gripper_data.grippers_angle / self.gripper_factor,
        }

    def write(self, target_joints: list[float]) -> None:
        """
        Write target joint positions to Piper.
        Args: list of 7 float values in **radians**:
              [joint_1, joint_2, joint_3, joint_4, joint_5, joint_6, gripper]
        """
        if not self._is_connected:
            raise DeviceNotConnectedError(
                f"PiperMotorsBus('{self.can_name}') is not connected."
            )

        if len(target_joints) != 7:
            raise ValueError(
                f"Expected 7 joint values, got {len(target_joints)}. "
                "Order: [joint_1, joint_2, joint_3, joint_4, joint_5, joint_6, gripper]"
            )

        joints = [round(j * self.joint_factor) for j in target_joints[:6]]
        gripper = round(target_joints[6] * self.gripper_factor)

        self.piper.MotionCtrl_2(0x01, 0x01, 100, 0x00)
        self.piper.JointCtrl(
            joints[0], joints[1], joints[2], joints[3], joints[4], joints[5]
        )
        self.piper.GripperCtrl(abs(gripper), 1000, 0x01, 0)
