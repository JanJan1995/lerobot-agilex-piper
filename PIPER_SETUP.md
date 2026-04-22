# Piper 主从臂遥操 × LeRobot 数据集录制完整指南（单 CAN 方案）

本文档介绍如何在 **lerobot-agilex** 项目中使用 **两台 Agilex Piper 机械臂**（一台主臂 / Leader，一台从臂 / Follower）完成主从遥操作和数据集录制。

> **硬件要求**
> - 2 × Agilex Piper 机械臂
> - 1 × CAN-USB 适配器（gs_usb 芯片，如广成科技、周立功等）
> - 1+ 摄像头（Intel RealSense D435I 或 USB 摄像头）
> - Ubuntu 20.04/22.04 主机

**核心要点**：两台 Piper 的 CAN 线并联到**同一个** USB-to-CAN 适配器，共享一条 CAN 总线。

---

## 一、环境配置

### 1.1 激活 Conda 环境

项目使用已创建好的 `piper_lerobot` 环境：

```bash
conda activate piper_lerobot
```

### 1.2 安装 Piper SDK

```bash
pip install piper_sdk python-can
```

### 1.3 安装系统依赖

```bash
sudo apt update
sudo apt install -y can-utils ethtool ffmpeg
```

### 1.4 安装 LeRobot（可编辑模式）

如果尚未安装：

```bash
cd /path/to/lerobot-agilex
pip install -e ".[feetech]"
```

> **注意**：lerobot-agilex 支持 Feetech/Dynamixel 舵机，但我们为 Piper 额外编写了独立驱动，不需要这些舵机依赖也能运行 Piper。

---

## 二、硬件接线（关键！）

### 2.1 CAN 总线并联接线

将两台 Piper 的 CAN 线并联到**同一个** USB-to-CAN 适配器：

```
          USB-to-CAN Adapter
                |
    +-----------+-----------+
    |                       |
 Piper #1 (Master)      Piper #2 (Slave)
  CAN_H + CAN_L           CAN_H + CAN_L
```

- CAN_H 接 CAN_H，CAN_L 接 CAN_L
- 确保 CAN 总线两端有 **120Ω 终端电阻**（通常 USB-to-CAN 适配器自带，另一台 Piper 也可能自带）

### 2.2 设置主从模式

Piper 官方提供两种方式设置主从模式：

#### 方式 A：通过 Piper 上位机软件（推荐）

使用 Agilex 官方工具将一台 Piper 设为**主臂 (Master/Teaching Input)**，另一台设为**从臂 (Slave/Motion Output)**。

#### 方式 B：通过 SDK 脚本设置

项目提供了自动设置脚本（无需上位机软件）：

```bash
bash piper_scripts/setup_piper_master_slave.sh
```

脚本会引导你：
1. 先只连接 **Master** 臂 → 发送 `MasterSlaveConfig(0xFA)`
2. 再只连接 **Slave** 臂 → 发送 `MasterSlaveConfig(0xFC)`

> **注意**：`0xFA` = 主臂 (Teaching Input)，`0xFC` = 从臂 (Motion Output)
>
> `MasterSlaveConfig` 是广播命令，两根臂同时在总线上时会互相干扰，因此必须**一个一个连**。

---

## 三、CAN 总线激活

插入 USB-to-CAN 适配器后，执行：

### 使用 Piper SDK 官方脚本（推荐）

Piper SDK 安装后自带官方 CAN 激活脚本，路径为：

```bash
# 通过 pip 安装的 piper_sdk，脚本位置
$CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh
```

执行方式：

```bash
bash $CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh
```

官方脚本会自动：
- 检查 `ethtool` 和 `can-utils` 是否已安装
- 检测 CAN 接口数量和 USB 硬件地址
- 设置波特率为 **1 Mbps**
- 命名为 `can0`
- 如果接口已激活且波特率正确，**智能跳过**重复配置

#### 参数说明

```bash
bash can_activate.sh [can_name] [bitrate] [usb_address]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `can_name` | `can0` | 目标 CAN 接口名 |
| `bitrate` | `1000000` | 波特率（Piper 固定 1 Mbps）|
| `usb_address` | （可选）| USB 硬件地址，多适配器时用于精确定位 |

#### 多 CAN 适配器场景

如果你的电脑插了多个 USB-to-CAN 适配器，脚本会报错并列出每个接口的 USB 地址：

```
Interface can0 is inserted into USB port 1-2:1.0
Interface can1 is inserted into USB port 1-3:1.0
Error: The number of CAN modules detected by the system (2) does not match the expected number (1).
Please add the USB hardware address parameter, such as:
bash can_activate.sh can0 1000000 1-2:1.0
```

此时需要指定 USB 地址：

```bash
bash $CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh can0 1000000 1-2:1.0
```

### 手动配置（如果脚本失败）

```bash
sudo ip link set can0 down
sudo ip link set can0 type can bitrate 1000000
sudo ip link set can0 up
```

### 验证 CAN 状态

```bash
ip -details link show can0
```

确认接口是 `UP` 状态，bitrate 为 `1000000`。

---

## 四、启动主从臂

### 上电顺序（官方要求）

1. **先从臂上电**
2. **再主臂上电**
3. 等待几秒，主从模式自动建立

### 4.1 遥操作测试

```bash
bash piper_scripts/teleop_piper.sh
```

或手动调用：

```bash
lerobot-teleoperate \
    --robot.type=piper_follower \
    --robot.can_name=can0 \
    --teleop.type=piper_leader \
    --teleop.can_name=can0 \
    --fps=30
```

此时，移动主臂，从臂会实时跟随。

### 4.2 带摄像头的遥操作

```bash
lerobot-teleoperate \
    --robot.type=piper_follower \
    --robot.can_name=can0 \
    --robot.cameras='{cam1: {type: opencv, camera_index: 0, width: 640, height: 480, fps: 30}}' \
    --teleop.type=piper_leader \
    --teleop.can_name=can0 \
    --display_data=true \
    --fps=30
```

### 4.3 停止遥操

- 按 **`q`** 键优雅退出（推荐）—— 主从配置保持，电机保持使能
- 或按 **`Ctrl+C`** 强制退出

> **注意**：退出脚本后，机械臂**不会**下电或进入 Standby。电机保持使能，主从联控关系保持有效，你可以随时重新运行遥操脚本。
>
> 这是有意的设计：`ModeCtrl(Standby)` 会破坏 `MasterSlaveConfig` 设置，导致主从失联；`DisableArm()` 会导致臂在重力下坠落。

---

## 五、录制 LeRobot 数据集

### 5.1 使用录制脚本

```bash
bash piper_scripts/record_piper.sh "pick_and_place_cube" 50
```

参数说明：
- 第1个参数：任务名称（dataset 的 repo_id 后缀）
- 第2个参数：录制 episode 数量

### 5.2 使用 lerobot-record 命令

```bash
export HF_USER=$USER

lerobot-record \
    --robot.type=piper_follower \
    --robot.can_name=can0 \
    --robot.cameras='{cam1: {type: opencv, camera_index: 0, width: 640, height: 480, fps: 30}}' \
    --teleop.type=piper_leader \
    --teleop.can_name=can0 \
    --dataset.repo_id=${HF_USER}/piper_pick_place \
    --dataset.num_episodes=50 \
    --dataset.single_task="Pick the red cube and place it in the box" \
    --dataset.fps=30 \
    --dataset.episode_time_s=30 \
    --dataset.reset_time_s=10 \
    --dataset.push_to_hub=false \
    --dataset.video=true
```

### 5.3 数据流说明（单 CAN 方案）

在录制过程中，数据从 CAN 总线上读取：

| 数据来源 | SDK API | LeRobot 字段 |
|----------|---------|--------------|
| 主臂控制帧（目标位置） | `GetArmJointCtrl()` / `GetArmGripperCtrl()` | `action` |
| 从臂反馈帧（实际位置） | `GetArmJointMsgs()` / `GetArmGripperMsgs()` | `observation.state` |
| 摄像头 | OpenCV / RealSense | `observation.images.*` |

主臂会自动在 CAN 总线上发送控制帧，从臂自动接收并执行。LeRobot 同时监听总线，收集 action 和 observation。

### 5.4 录制控制快捷键

| 按键 | 功能 |
|------|------|
| `→` (右箭头) | 提前结束当前 episode，进入 reset 阶段 |
| `←` (左箭头) | 取消当前 episode，重新录制 |
| `ESC` | 提前结束整个录制会话 |

### 5.5 查看录制的数据集

```bash
python lerobot/scripts/visualize_dataset.py \
    --repo-id $USER/piper_pick_place \
    --episode-index 0
```

---

## 六、训练策略（Policy）

使用录制的数据集训练 ACT 策略：

```bash
export HF_USER=$USER

python lerobot/scripts/train.py \
  --dataset.repo_id=${HF_USER}/piper_pick_place \
  --policy.type=act \
  --output_dir=outputs/train/act_piper_pick_place \
  --job_name=act_piper_pick_place \
  --device=cuda \
  --wandb.enable=false
```

训练完成后，模型保存在 `outputs/train/act_piper_pick_place/checkpoints/` 下。

---

## 七、推理验证

**重要**：策略推理时，需要断开主臂的航空插头（或关闭主臂电源），否则主臂会持续发送控制命令导致冲突。

> 官方文档原文：
> "When controlling the slave arm, the master arm and the slave arm need to be disconnected."

### 7.1 断开主臂

1. 关闭主臂电源，或拔掉主臂的航空插头
2. 确保只有从臂连接在 CAN 总线上

### 7.2 运行策略

```bash
export HF_USER=$USER

lerobot-record \
    --robot.type=piper_follower \
    --robot.can_name=can0 \
    --robot.cameras='{cam1: {type: opencv, camera_index: 0, width: 640, height: 480, fps: 30}}' \
    --dataset.repo_id=${HF_USER}/eval_piper_pick_place \
    --dataset.num_episodes=10 \
    --dataset.single_task="Pick the red cube and place it in the box" \
    --dataset.fps=30 \
    --dataset.episode_time_s=30 \
    --dataset.push_to_hub=false \
    --policy.path=outputs/train/act_piper_pick_place/checkpoints/latest/pretrained_model
```

> **注意**：推理时不需要 `--teleop` 参数，因为动作由策略（policy）生成。

---

## 八、项目文件说明

| 文件/目录 | 说明 |
|-----------|------|
| `src/lerobot/motors/piper/piper_motors_bus.py` | Piper CAN 总线底层驱动，支持单 CAN 主从模式 |
| `src/lerobot/robots/piper_follower/` | Piper 从臂（Follower）实现，使用 `read_follower()` 读取从臂反馈 |
| `src/lerobot/teleoperators/piper_leader/` | Piper 主臂（Leader）实现，使用 `read_leader()` 读取主臂控制帧 |
| `$CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh` | Piper SDK 官方 CAN 接口激活脚本（推荐）|
| `piper_scripts/CAN_ACTIVATE_EXPLAINED.md` | `can_activate.sh` 逐行命令详解 |
| `piper_scripts/teleop_piper.sh` | 遥操作启动脚本（单 CAN） |
| `piper_scripts/record_piper.sh` | 数据集录制启动脚本（单 CAN） |
| `piper_scripts/setup_piper_master_slave.sh` | 主从模式设置脚本（无需上位机） |
| `docs/piper_teleop_development.md` | 遥操代码开发记录（问题排查参考） |
| `PIPER_SETUP.md` | 本说明文档 |

---

## 九、常见问题排查

### Q1: `piper_sdk` 导入失败

```bash
pip install piper_sdk
```

确认在 `piper_lerobot` conda 环境中安装。

### Q2: CAN 接口检测不到

- 确认 CAN-USB 适配器已插入且灯亮
- 检查 `dmesg | grep -i can` 看内核是否识别到设备
- 尝试手动加载模块：`sudo modprobe gs_usb`

### Q3: Piper 连接超时（enable timeout）

- 确认 CAN 总线已激活：`ip link show type can`
- 确认波特率正确（必须是 1 Mbps）
- 尝试**断电重启** Piper 机械臂
- 尝试**拔掉 CAN-USB 重新插拔**
- 单独测试：`python -c "from piper_sdk import C_PiperInterface_V2; p=C_PiperInterface_V2('can0'); p.ConnectPort(); print('ok')"`

### Q4: 主从臂不跟随

1. 检查主从模式是否正确设置（一台 0xFA，一台 0xFC）
2. 确认上电顺序：**先从臂，后主臂**
3. 检查 CAN 线是否接触良好
4. 尝试断电后重新上电

> **常见原因**：如果之前运行过遥操脚本后手动按了 `Ctrl+C`，再运行时出现不跟随，可能是因为脚本异常退出导致主从配置被破坏。此时需要重新运行 `setup_piper_master_slave.sh` 设置主从模式。
>
> **根本原因**：`ModeCtrl(Standby)` 会破坏 `MasterSlaveConfig`。我们的脚本已修复此问题（退出时不发送 Standby），但如果是旧版本代码或手动调用 SDK 发送了 Standby，就需要重新设置。

### Q5: 从臂抖动或动作不流畅

**最常见原因：Python 代码在重复发送控制命令**

在 Piper 硬件主从模式下，Master 固件会自动发送控制帧到 CAN 总线，Slave 自动执行。如果 Python 代码在 `send_action()` 中又调用 `bus.write()` 手动发送控制命令，Slave 会同时收到两个命令源，导致冲突和抖动。

**确认**：检查 `piper_follower.py` 的 `send_action()` 中是否有 `self.bus.write()`。遥操时 `manual_control` 必须为 `False`。

其他可能：
- 检查 CAN 总线是否有干扰（缩短 CAN 线长度、确保屏蔽良好）
- 调整 `max_relative_target` 安全限制：`--robot.max_relative_target=0.5`

### Q6: 第一次遥操正常，第二次运行时 Master arm 失控

**原因**：`C_PiperInterface_V2` 是 SDK 内部单例，但 `ConnectPort()` 在每次创建 `PiperMotorsBus` 时都被调用（Leader 和 Follower 各一次）。第一次运行后没有 `DisconnectPort()`，第二次运行时 `ConnectPort()` 被重复调用，启动多个读取线程 + 重复执行 `piper_init`，导致 CAN 状态混乱。

**解决**：在 `PiperMotorsBus.__init__` 中检查 `get_connect_status()`，已连接时跳过 `ConnectPort()`。

### Q7: 策略推理时从臂乱动

- **必须断开主臂**！主臂会持续发送控制帧干扰从臂。
- 关闭主臂电源或拔掉主臂航空插头后再运行推理。

### Q8: 数据集录制没有视频

- 确认摄像头已连接且被正确识别
- 对于 RealSense，检查序列号是否正确
- 对于 OpenCV 摄像头，检查 `camera_index`（可用 `v4l2-ctl --list-devices` 查看）

---

## 十、扩展：双臂 Piper（未来）

如果你有两套主从臂（共 4 台 Piper），需要两条独立的 CAN 总线（can0 和 can1），每对主从臂独占一条总线。代码中只需为第二对指定不同的 `can_name` 即可。

---

如有问题，欢迎查阅：
- [Piper SDK V2 接口文档](https://github.com/agilexrobotics/piper_sdk/blob/master/asserts/V2/INTERFACE_V2.MD)
- [Piper 双机械臂主从模式文档](https://github.com/agilexrobotics/piper_sdk/blob/master/asserts/double_piper.MD)
- LeRobot 官方文档
