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

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig

from ..config import RobotConfig


@RobotConfig.register_subclass("piper_follower")
@dataclass
class PiperFollowerConfig(RobotConfig):
    """Configuration for Piper Follower (slave) arm."""

    # CAN interface name.
    # In official Piper single-CAN master/slave mode, both arms share the same
    # CAN bus (e.g. "can0"). In legacy dual-CAN mode, follower uses "can0".
    can_name: str = "can0"

    # Disable torque on disconnect for safety
    disable_torque_on_disconnect: bool = True

    # Optional safety limit on relative positional target (radians)
    max_relative_target: float | None = None

    # When True, send_action() will manually write JointCtrl() to the slave arm.
    # When False (default for teleop), the slave arm follows the master automatically
    # via hardware master/slave linkage on the shared CAN bus.
    manual_control: bool = False

    # Cameras attached to the follower setup
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
