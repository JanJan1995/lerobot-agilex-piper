#!/usr/bin/env python
"""Test camera color channel order for /dev/video4 and /dev/video10."""

import cv2
import numpy as np
from pathlib import Path

output_dir = Path("/tmp/camera_color_test")
output_dir.mkdir(exist_ok=True)

devices = {
    "wrist": "/dev/video4",
    "up": "/dev/video10",
}

for name, dev in devices.items():
    cap = cv2.VideoCapture(dev)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    # Warmup
    for _ in range(10):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print(f"[{name}] FAILED to read from {dev}")
        continue

    # frame from OpenCV is supposedly BGR
    # Save three versions for comparison
    cv2.imwrite(str(output_dir / f"{name}_opencv_bgr.png"), frame)
    cv2.imwrite(str(output_dir / f"{name}_cvt_rgb.png"), cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    # Also save with PIL (RGB) to see if channel order is correct
    from PIL import Image
    Image.fromarray(frame[:, :, ::-1], mode="RGB").save(output_dir / f"{name}_pil_from_bgr.png")
    Image.fromarray(frame, mode="RGB").save(output_dir / f"{name}_pil_from_raw.png")

    print(f"[{name}] Read OK from {dev}, shape={frame.shape}")
    print(f"  Pixel[100,100] BGR={frame[100,100].tolist()}")

print(f"\nTest images saved to: {output_dir}")
print("Compare these files:")
print("  - opencv_bgr.png   : OpenCV imwrite (expects BGR input)")
print("  - cvt_rgb.png      : After COLOR_BGR2RGB, then cv2.imwrite")
print("  - pil_from_bgr.png : PIL fromarray(frame[:,:,::-1], RGB)")
print("  - pil_from_raw.png : PIL fromarray(frame, RGB)")
print("\nIf 'opencv_bgr.png' looks correct, your camera outputs BGR (normal).")
print("If 'pil_from_raw.png' looks correct, your camera outputs RGB (unusual).")
