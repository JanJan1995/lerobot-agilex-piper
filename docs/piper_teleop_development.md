# Piper 遥操代码开发记录

> 记录将 Agilex Piper 机械臂集成到 LeRobot 框架中进行遥操作（teleoperation）的完整开发过程。
>
> 硬件：2x Piper 臂（master/slave），单 CAN 总线（can0），piper_sdk V2

---

## 一、项目背景与目标

**目标**：在 LeRobot 框架中实现 Piper 双臂遥操，用于数据集录制和后续策略训练。

**硬件拓扑**：
- 1x USB-to-CAN 适配器（gs_usb 驱动）
- 2x Piper 机械臂通过 CAN 总线并联
- 共享同一个 CAN 接口 `can0`（bitrate 1 Mbps）

**Piper 官方主从模式**：
- Master 臂移动时，固件**自动**发送控制帧（CAN ID 0x155-0x157）到总线
- Slave 臂接收控制帧后**自动**执行动作
- **Python 代码不需要（也不应该）手动发送控制命令给 Slave**

---

## 二、软件架构设计

### 2.1 仿照 SO101 的模式

LeRobot 中已有成熟的 SO101 遥操实现：

```
SO101Leader (Teleoperator)          SO101Follower (Robot)
    └── FeetechMotorsBus                └── FeetechMotorsBus
        └── 串口读取 Leader 位置              └── 串口写入 Follower 目标位置
```

SO101 是**纯软件遥操**：Python 负责从 Leader 读取位置，再写给 Follower。

### 2.2 Piper 的不同之处

Piper 是**硬件自动联动**：Master 固件 → CAN 总线 → Slave 固件，Python 不干预运动。

因此 Piper 的架构是：

```
PiperLeader (Teleoperator)          PiperFollower (Robot)
    └── PiperMotorsBus                  └── PiperMotorsBus
        └── 读 Master 控制帧                  └── 读 Slave 反馈帧
        └── (不发送任何控制命令)               └── (遥操时不发送控制命令)
```

### 2.3 核心设计决策

| 决策 | 说明 |
|------|------|
| 各自创建 PiperMotorsBus 实例 | Leader 和 Follower 各自管理连接状态，符合 LeRobot 架构 |
| 底层共享 C_PiperInterface_V2 | SDK 内部是单例（通过 `__new__` 实现），实际只有一个 CAN socket |
| 遥操时不 `write()` | 避免双重控制导致抖动 |
| 保留 `manual_control` 参数 | 推理模式时手动控制 Slave（需断开 Master） |

---

## 三、关键实现

### 3.1 PiperMotorsBus — 底层驱动

```python
class PiperMotorsBus:
    def __init__(self, config):
        # SDK 单例：相同 can_name 返回同一个实例
        self.piper = C_PiperInterface_V2(config.can_name)
        # 避免重复调用 ConnectPort()（见问题 5）
        if not self.piper.get_connect_status():
            self.piper.ConnectPort()

    def connect(self):
        # 只使能，不验证状态（避免 Master 臂不需要使能的问题）
        self.piper.EnableArm(7)
        self.piper.GripperCtrl(0, 1000, 0x01, 0)

    def disconnect(self):
        # 见问题 6：不能发 ModeCtrl(Standby)，会破坏主从配置
        # 也不能 DisableArm()，会导致下坠
        # 最终方案：什么都不发，只是标记断开
        self._is_connected = False

    def read(self):
        # 读 Slave 反馈：GetArmJointMsgs / GetArmGripperMsgs
        ...

    def read_ctrl(self):
        # 读 Master 控制帧：GetArmJointCtrl / GetArmGripperCtrl
        ...

    def write(self, target_joints):
        # 手动控制：MotionCtrl_2 + JointCtrl + GripperCtrl
        # 只在推理模式（manual_control=True）时调用
        ...
```

### 3.2 PiperLeader

```python
class PiperLeader(Teleoperator):
    def get_action(self):
        # 读取 Master 的控制帧（CAN ID 0x155-0x157）
        action_raw = self.bus.read_ctrl()
        return {f"{motor}.pos": val for motor, val in action_raw.items()}
```

### 3.3 PiperFollower

```python
class PiperFollower(Robot):
    def get_observation(self):
        # 读取 Slave 的实际反馈
        obs = self.bus.read()
        ...

    def send_action(self, action):
        # 遥操时：不写！硬件自动联动
        # 推理时：manual_control=True 才调用 bus.write()
        if self.config.manual_control:
            target_joints = [...]
            self.bus.write(target_joints)
        return action
```

### 3.4 draccus 注册

LeRobot 使用 draccus 动态注册 robot/teleop 类型：

```python
# config_piper_follower.py
@RobotConfig.register_subclass("piper_follower")
@dataclass
class PiperFollowerConfig(RobotConfig):
    can_name: str = "can0"
    manual_control: bool = False
```

**关键**：`teleoperate.py` 必须 import `piper_follower` 和 `piper_leader` 模块，否则 draccus 看不到注册。

---

## 四、遇到的问题与解决方案

### 问题 1：draccus 注册失败

**现象**：`lerobot-teleoperate` 报错 `invalid choice: 'piper_follower'`

**原因**：`teleoperate.py` 的导入块里没有 `piper_follower` 和 `piper_leader`，draccus 从未加载这些模块，装饰器未执行。

**解决**：在 `teleoperate.py` 的 import 中添加：

```python
from lerobot.robots import (
    ...
    piper_follower,   # ← 新增
)
from lerobot.teleoperators import (
    ...
    piper_leader,     # ← 新增
)
```

---

### 问题 2：AttributeError — `ArmJointCtrl` 没有 `joint_1`

**现象**：`read_leader()` 报错 `'ArmJointCtrl' object has no attribute 'joint_1'`

**原因**：`GetArmJointCtrl()` 返回的是嵌套结构：

```python
ctrl = piper.GetArmJointCtrl()
ctrl.time_stamp     # 时间戳
ctrl.Hz             # 频率
ctrl.joint_ctrl     # ← 关节数据在这里！
    ctrl.joint_ctrl.joint_1   # 正确的访问路径
```

之前代码直接访问 `ctrl.joint_1`，漏了中间的 `.joint_ctrl` 层。

**解决**：修正为 `ctrl.joint_ctrl.joint_1`。同理 `GetArmGripperCtrl()` → `.gripper_ctrl.grippers_angle`。

---

### 问题 3：Slave 臂剧烈抖动

**现象**：遥操时 Slave 臂剧烈颤抖

**原因**：**双重控制冲突**

```
Master 臂移动
    → 固件自动发控制帧到 CAN（硬件联动）
    → Slave 自动执行

同时 Python 代码：
    → send_action() 又调用 bus.write()
    → 再次发送 JointCtrl 到 CAN

结果：Slave 同时收到两个命令源，冲突 → 抖动
```

**解决**：遥操时 `send_action()` 不调用 `bus.write()`，只返回 action 用于数据集记录。

---

### 问题 4：EnableArm 超时

**现象**：`connect()` 时 `EnableArm` 5 秒超时

**原因**：两个 `PiperMotorsBus` 实例共享同一个 `C_PiperInterface_V2`。`ConnectPort()` 在 `__init__` 中被调用了两次（Leader 一次，Follower 一次），第二次调用可能重置了状态。

**解决**：
1. 去掉 `connect()` 中的 EnableArm 状态验证循环（回到简单 `EnableArm(7)`）
2. `__init__` 中检查 `get_connect_status()`，已连接则跳过 `ConnectPort()`

---

### 问题 5：ConnectPort() 重复调用导致失控

**现象**：第一次遥操正常，结束后再次运行，Master arm 失控自动移动

**原因**：
```
第一次运行：
    Leader.__init__ → ConnectPort()  ✅ 正常
    Follower.__init__ → ConnectPort() ❌ 又调一次（重复启动线程）

第一次结束：
    disconnect() → 没有调用 DisconnectPort()！

第二次运行：
    Leader.__init__ → ConnectPort() ❌ 第三次调用！
    Follower.__init__ → ConnectPort() ❌ 第四次调用！
```

多次 `ConnectPort()` 启动多个读取线程 + 重复执行 `piper_init`，CAN 状态混乱。

**解决**：`__init__` 中检查 `get_connect_status()`：

```python
self.piper = C_PiperInterface_V2(config.can_name)
if not self.piper.get_connect_status():
    self.piper.ConnectPort()
```

---

### 问题 6（最关键）：disconnect() 破坏主从联控 ⭐

**现象**：第一次遥操结束后，Master 不再控制 Slave。必须断电重置 Master 才能恢复。

**根因分析**：`disconnect()` 最初调用 `ModeCtrl(0x00, 0x01, 50, 0x00)` 进入 Standby 模式：

```python
def disconnect(self):
    self.piper.ModeCtrl(0x00, 0x01, 50, 0x00)  # ← 罪魁祸首！
```

`ModeCtrl` 发到 CAN ID 0x151，是**广播命令**。两个臂都会收到 `ctrl_mode=0x00`（Standby）。

但 `MasterSlaveConfig(0xFA/0xFC)` 发到 CAN ID 0x470，也是广播。Standby 模式会**覆盖/破坏**之前的主从配置，导致 Master 固件不再发送控制帧。

**为什么不能用 DisableArm()**：用户明确禁止。切断电机会导致臂在重力下自由坠落，造成设备损伤。

**最终方案**：`disconnect()` 中**什么都不发**，只是标记断开状态：

```python
def disconnect(self):
    """不发送任何硬件命令，保持主从配置和电机使能状态。"""
    self._is_connected = False
```

这样退出脚本后：
- 电机保持使能（不会下坠）
- 主从配置保持有效（Master 仍然控制 Slave）
- 下次运行脚本时直接 `EnableArm` 即可恢复

---

## 五、单位确认

| 量 | SDK 原始单位 | 代码转换因子 | 外部单位 |
|----|------------|------------|---------|
| 关节角度 | 0.001° | `57324.840764` (= 1000 × 180/π) | 弧度 |
| 夹爪行程 | 0.001mm (= 1µm) | `1_000_000.0` | 米 |

> 注：`GetArmGripperMsgs` 文档中一处写 `0.001°`（笔误），实际应为 `0.001mm`。控制命令 `GripperCtrl` 明确为 `0.001mm`，且 `double_piper.MD` 确认单位为 µm。

---

## 六、文件清单

| 文件 | 说明 |
|------|------|
| `src/lerobot/motors/piper/piper_motors_bus.py` | 底层 CAN 驱动 |
| `src/lerobot/teleoperators/piper_leader/piper_leader.py` | Master 臂遥操器 |
| `src/lerobot/teleoperators/piper_leader/config_piper_leader.py` | Leader 配置 |
| `src/lerobot/robots/piper_follower/piper_follower.py` | Slave 臂机器人 |
| `src/lerobot/robots/piper_follower/config_piper_follower.py` | Follower 配置 |
| `src/lerobot/teleoperate.py` | 遥操入口（新增 'q' 键退出） |
| `piper_scripts/teleop_piper.sh` | 遥操启动脚本 |
| `piper_scripts/setup_piper_master_slave.sh` | 主从模式设置脚本 |

---

## 七、使用流程

```bash
# 1. 激活 CAN
sudo bash $CONDA_PREFIX/lib/python3.10/site-packages/piper_sdk/can_activate.sh

# 2. 设置主从模式（只需一次，除非恢复出厂）
bash piper_scripts/setup_piper_master_slave.sh
#    按提示：先只连 Master → 再只连 Slave

# 3. 启动遥操
bash piper_scripts/teleop_piper.sh
#    按 'q' 优雅退出（主从配置保持）

# 4. 再次启动（无需重新设置主从）
bash piper_scripts/teleop_piper.sh
```

---

## 八、关键经验

1. **Piper 主从模式是硬件自动的**，Python 代码只是旁观者，不要试图手动控制 Slave。
2. **`MasterSlaveConfig` 是广播命令**，无法在一个 CAN 总线上分别设置两个臂，必须一个一个连。
3. **`ModeCtrl(Standby)` 会破坏主从配置**，断开时不能用。
4. **`DisableArm()` 会导致下坠**，断开时不能用。
5. **`ConnectPort()` 不要重复调用**，SDK 是单例但 `ConnectPort` 不是幂等的。
6. **SDK 返回的数据是嵌套的**，`GetArmJointCtrl().joint_ctrl.joint_1`，不要漏中间层。
