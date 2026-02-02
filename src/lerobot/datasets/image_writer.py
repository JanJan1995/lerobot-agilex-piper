#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
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
import multiprocessing
import queue
import threading
from pathlib import Path

import numpy as np
import PIL.Image
import torch


def safe_stop_image_writer(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            dataset = kwargs.get("dataset")
            image_writer = getattr(dataset, "image_writer", None) if dataset else None
            if image_writer is not None:
                print("Waiting for image writer to terminate...")
                image_writer.stop()
            raise e

    return wrapper


def image_array_to_pil_image(image_array: np.ndarray, range_check: bool = True, is_depth: bool = False) -> PIL.Image.Image:
    """Convert numpy array to PIL Image, handling 2D (grayscale/depth) and 3D (RGB) arrays.
    
    Args:
        image_array: Input numpy array
        range_check: Whether to check value ranges
        is_depth: If True, save as 16-bit PNG without compression (preserves depth values)
    """
    original_shape = image_array.shape
    original_dtype = image_array.dtype
    
    # Handle 2D arrays (grayscale/depth images)
    if image_array.ndim == 2:
        # For depth images, preserve 16-bit values without compression
        if is_depth:
            # Convert to uint16 if needed, preserving original values
            if image_array.dtype == np.float32 or image_array.dtype == np.float64:
                # For float depth values, convert to uint16 (0-65535 range)
                # Assume depth values are in reasonable range (e.g., millimeters)
                max_val = image_array.max().item()
                if max_val > 65535.0:
                    # If values exceed uint16 range, scale down but preserve relative values
                    image_array = (image_array / (max_val / 65535.0)).astype(np.uint16)
                elif max_val > 1.0:
                    # Values are likely in millimeters or similar units
                    image_array = image_array.astype(np.uint16)
                else:
                    # Values in [0, 1] range, scale to uint16
                    image_array = (image_array * 65535.0).astype(np.uint16)
            elif image_array.dtype != np.uint16:
                # Convert other integer types to uint16
                image_array = image_array.astype(np.uint16)
            # Use 'I;16' mode for 16-bit grayscale PNG
            return PIL.Image.fromarray(image_array, mode='I;16')
        
        # For regular grayscale images, normalize to uint8
        if image_array.dtype != np.uint8:
            if range_check:
                max_ = image_array.max().item()
                min_ = image_array.min().item()
                # For grayscale images, normalize to 0-255 range
                if max_ > 255.0 or min_ < 0.0:
                    # Normalize to [0, 1] first if values are outside uint8 range
                    if max_ > 1.0:
                        image_array = (image_array - min_) / (max_ - min_ + 1e-8)
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)
            else:
                if image_array.dtype == np.float32 or image_array.dtype == np.float64:
                    # Assume float values are in [0, 1] range
                    image_array = (image_array * 255).astype(np.uint8)
                else:
                    image_array = image_array.astype(np.uint8)
        return PIL.Image.fromarray(image_array, mode='L')
    
    # Handle 3D arrays
    if image_array.ndim != 3:
        raise ValueError(f"The array has {image_array.ndim} dimensions, but 2 or 3 is expected for an image.")

    # Handle (C, H, W) format - transpose to (H, W, C)
    if image_array.shape[0] == 1 or image_array.shape[0] == 3 or image_array.shape[0] == 4:
        # Transpose from pytorch convention (C, H, W) to (H, W, C)
        image_array = image_array.transpose(1, 2, 0)

    # Handle single channel 3D arrays (shape becomes (H, W, 1) after transpose)
    if image_array.shape[-1] == 1:
        # Squeeze to 2D and use grayscale mode
        image_array = image_array.squeeze(-1)
        if image_array.dtype != np.uint8:
            if range_check:
                max_ = image_array.max().item()
                min_ = image_array.min().item()
                if max_ > 1.0 or min_ < 0.0:
                    raise ValueError(
                        "The image data type is float, which requires values in the range [0.0, 1.0]. "
                        f"However, the provided range is [{min_}, {max_}]. Please adjust the range or "
                        "provide a uint8 image with values in the range [0, 255]."
                    )
            image_array = (image_array * 255).astype(np.uint8)
        return PIL.Image.fromarray(image_array, mode='L')
    
    # Handle RGB images (3 channels)
    if image_array.shape[-1] == 3:
        if image_array.dtype != np.uint8:
            if range_check:
                max_ = image_array.max().item()
                min_ = image_array.min().item()
                if max_ > 1.0 or min_ < 0.0:
                    raise ValueError(
                        "The image data type is float, which requires values in the range [0.0, 1.0]. "
                        f"However, the provided range is [{min_}, {max_}]. Please adjust the range or "
                        "provide a uint8 image with values in the range [0, 255]."
                    )
            image_array = (image_array * 255).astype(np.uint8)
        return PIL.Image.fromarray(image_array, mode='RGB')
    
    # Handle RGBA images (4 channels)
    if image_array.shape[-1] == 4:
        if image_array.dtype != np.uint8:
            if range_check:
                max_ = image_array.max().item()
                min_ = image_array.min().item()
                if max_ > 1.0 or min_ < 0.0:
                    raise ValueError(
                        "The image data type is float, which requires values in the range [0.0, 1.0]. "
                        f"However, the provided range is [{min_}, {max_}]. Please adjust the range or "
                        "provide a uint8 image with values in the range [0, 255]."
                    )
            image_array = (image_array * 255).astype(np.uint8)
        return PIL.Image.fromarray(image_array, mode='RGBA')
    
    raise NotImplementedError(
        f"The image has {image_array.shape[-1]} channels, but 1, 3, or 4 channels are supported."
    )


def write_image(image: np.ndarray | PIL.Image.Image, fpath: Path, is_depth: bool = False):
    """Write image to file.
    
    Args:
        image: Image array or PIL Image
        fpath: Output file path
        is_depth: If True, save as 16-bit PNG without compression (for depth images)
    """
    try:
        if isinstance(image, np.ndarray):
            img = image_array_to_pil_image(image, is_depth=is_depth)
        elif isinstance(image, PIL.Image.Image):
            img = image
        else:
            raise TypeError(f"Unsupported image type: {type(image)}")
        img.save(fpath)
    except Exception as e:
        print(f"Error writing image {fpath}: {e}")


def worker_thread_loop(queue: queue.Queue):
    while True:
        item = queue.get()
        if item is None:
            queue.task_done()
            break
        # Item can be (image_array, fpath) or (image_array, fpath, is_depth)
        if len(item) == 2:
            image_array, fpath = item
            is_depth = False
        else:
            image_array, fpath, is_depth = item
        write_image(image_array, fpath, is_depth=is_depth)
        queue.task_done()


def worker_process(queue: queue.Queue, num_threads: int):
    threads = []
    for _ in range(num_threads):
        t = threading.Thread(target=worker_thread_loop, args=(queue,))
        t.daemon = True
        t.start()
        threads.append(t)
    for t in threads:
        t.join()


class AsyncImageWriter:
    """
    This class abstract away the initialisation of processes or/and threads to
    save images on disk asynchronously, which is critical to control a robot and record data
    at a high frame rate.

    When `num_processes=0`, it creates a threads pool of size `num_threads`.
    When `num_processes>0`, it creates processes pool of size `num_processes`, where each subprocess starts
    their own threads pool of size `num_threads`.

    The optimal number of processes and threads depends on your computer capabilities.
    We advise to use 4 threads per camera with 0 processes. If the fps is not stable, try to increase or lower
    the number of threads. If it is still not stable, try to use 1 subprocess, or more.
    """

    def __init__(self, num_processes: int = 0, num_threads: int = 1):
        self.num_processes = num_processes
        self.num_threads = num_threads
        self.queue = None
        self.threads = []
        self.processes = []
        self._stopped = False

        if num_threads <= 0 and num_processes <= 0:
            raise ValueError("Number of threads and processes must be greater than zero.")

        if self.num_processes == 0:
            # Use threading
            self.queue = queue.Queue()
            for _ in range(self.num_threads):
                t = threading.Thread(target=worker_thread_loop, args=(self.queue,))
                t.daemon = True
                t.start()
                self.threads.append(t)
        else:
            # Use multiprocessing
            self.queue = multiprocessing.JoinableQueue()
            for _ in range(self.num_processes):
                p = multiprocessing.Process(target=worker_process, args=(self.queue, self.num_threads))
                p.daemon = True
                p.start()
                self.processes.append(p)

    def save_image(self, image: torch.Tensor | np.ndarray | PIL.Image.Image, fpath: Path, is_depth: bool = False):
        """Save image asynchronously.
        
        Args:
            image: Image tensor, array, or PIL Image
            fpath: Output file path
            is_depth: If True, save as 16-bit PNG without compression (for depth images)
        """
        if isinstance(image, torch.Tensor):
            # Convert tensor to numpy array to minimize main process time
            image = image.cpu().numpy()
        self.queue.put((image, fpath, is_depth))

    def wait_until_done(self):
        self.queue.join()

    def stop(self):
        if self._stopped:
            return

        if self.num_processes == 0:
            for _ in self.threads:
                self.queue.put(None)
            for t in self.threads:
                t.join()
        else:
            num_nones = self.num_processes * self.num_threads
            for _ in range(num_nones):
                self.queue.put(None)
            for p in self.processes:
                p.join()
                if p.is_alive():
                    p.terminate()
            self.queue.close()
            self.queue.join_thread()

        self._stopped = True
