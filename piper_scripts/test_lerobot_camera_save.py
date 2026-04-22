#!/usr/bin/env python
"""Simulate LeRobot camera read + save pipeline to find color bug."""

import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

sys.path.insert(0, "/home/mc509/Workspace/VLA/Piper/lerobot-agilex/src")

from lerobot.cameras.opencv.camera_opencv import OpenCVCamera
from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig, ColorMode

output_dir = Path("/tmp/lerobot_color_test")
output_dir.mkdir(exist_ok=True)

def test_camera(name, dev, color_mode=ColorMode.RGB):
    print(f"\n=== Testing {name} ({dev}) with color_mode={color_mode.value} ===")
    cfg = OpenCVCameraConfig(
        index_or_path=dev,
        fps=30,
        width=640,
        height=480,
        color_mode=color_mode,
    )
    cam = OpenCVCamera(cfg)
    cam.connect()
    time.sleep(0.5)

    # Simulate async_read (what get_observation() uses)
    frame = cam.async_read()
    print(f"  async_read shape={frame.shape}, dtype={frame.dtype}")
    print(f"  pixel[100,100] = {frame[100, 100].tolist()}")

    # Save via PIL (same as dataset.add_frame -> write_image)
    pil_path = output_dir / f"{name}_{color_mode.value}_pil_save.png"
    Image.fromarray(frame, mode="RGB").save(pil_path)
    print(f"  PIL save -> {pil_path}")

    # Also save raw OpenCV frame for reference
    cap = cv2.VideoCapture(dev)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    for _ in range(5):
        cap.read()
    ret, raw = cap.read()
    cap.release()
    if ret:
        cv2.imwrite(str(output_dir / f"{name}_raw_opencv.png"), raw)
        print(f"  Raw OpenCV save -> {output_dir / f'{name}_raw_opencv.png'}")

    cam.disconnect()
    return frame

# Test both cameras with RGB (LeRobot default)
for name, dev in [("wrist", "/dev/video4"), ("up", "/dev/video10")]:
    try:
        test_camera(name, dev, color_mode=ColorMode.RGB)
    except Exception as e:
        print(f"  FAILED: {e}")

print(f"\n\nNow inspect images in: {output_dir}")
print("If 'xxx_rgb_pil_save.png' looks wrong (blue/red swapped), try BGR mode.")
