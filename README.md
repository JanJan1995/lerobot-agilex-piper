# LeRobot
Referencing https://github.com/huggingface/lerobot.git, For more details, please refer to this link.
Data collection method reference: https://github.com/agilexrobotics/data_tools
## Installation

LeRobot works with Python 3.10+ and PyTorch 2.2+.

### Environment Setup

Create a virtual environment with Python 3.10 and activate it, e.g. with [`miniconda`](https://docs.anaconda.com/free/miniconda/index.html):

```bash
conda create -y -n lerobot python=3.10
conda activate lerobot
```

When using `miniconda`, install `ffmpeg` in your environment:

```bash
conda install ffmpeg -c conda-forge
```

> **NOTE:** This usually installs `ffmpeg 7.X` for your platform compiled with the `libsvtav1` encoder. If `libsvtav1` is not supported (check supported encoders with `ffmpeg -encoders`), you can:
>
> - _[On any platform]_ Explicitly install `ffmpeg 7.X` using:
>
> ```bash
> conda install ffmpeg=7.1.1 -c conda-forge
> ```
>
> - _[On Linux only]_ Install [ffmpeg build dependencies](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu#GettheDependencies) and [compile ffmpeg from source with libsvtav1](https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu#libsvtav1), and make sure you use the corresponding ffmpeg binary to your install with `which ffmpeg`.

### Install LeRobot 🤗

#### From Source

First, clone the repository and navigate into the directory:

```bash
git clone https://github.com/agilexrobotics/lerobot-agilex.git lerobot
cd lerobot
```

Then, install the library in editable mode. This is useful if you plan to contribute to the code.

```bash
pip install -e .
```
## Train
```bash
conda activate lerobot && cd ~/lerobot && python src/lerobot/scripts/train.py --dataset.repo_id=data --policy.type=act --output_dir=/home/agilex/checkpoint_lerobot --job_name=data --policy.device=cuda --wandb.enable=false --dataset.root=/home/agilex/data_lerobot/ --policy.repo_id=data --batch_size 1 --eval.batch_size 1
```

## inference
```bash
conda activate lerobot && cd ~/lerobot/scripts && python lerobot_inference-ros2.py --policy act --pretrained_model_name_or_path ~/checkpoint_lerobot/checkpoints/100000/pretrained_model/
```
