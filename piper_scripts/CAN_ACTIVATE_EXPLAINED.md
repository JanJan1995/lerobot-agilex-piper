# can_activate.sh 逐行命令详解

> 本文档基于 Piper SDK 官方 `can_activate.sh` 脚本，逐行解释每条命令的含义。
>
> 官方源码：https://github.com/agilexrobotics/piper_sdk/blob/master/piper_sdk/can_activate.sh

---

## 脚本头部：参数定义

```bash
#!/bin/bash
```
> **Shebang**：声明使用 `/bin/bash` 作为解释器执行此脚本。

```bash
DEFAULT_CAN_NAME="${1:-can0}"
```
> **接收第 1 个参数**：用户传入的目标 CAN 接口名。
> - 如果用户执行 `bash can_activate.sh can1`，则 `DEFAULT_CAN_NAME = can1`
> - 如果用户没传参数，默认值为 `can0`

```bash
DEFAULT_BITRATE="${2:-1000000}"
```
> **接收第 2 个参数**：用户传入的波特率。
> - 如果用户执行 `bash can_activate.sh can0 500000`，则波特率为 500Kbps
> - 如果没传，默认值为 `1000000`（1 Mbps，Piper 固定用这个速率）

```bash
USB_ADDRESS="${3}"
```
> **接收第 3 个参数（可选）**：USB 硬件地址。
> - 当电脑插了**多个** USB-to-CAN 适配器时，用这个参数指定具体要配置哪一个
> - 格式如 `1-2:1.0`，可通过 `ethtool -i can0 | grep bus-info` 查看

---

## 第一部分：检查系统依赖

```bash
if ! dpkg -l | grep -q "ethtool"; then
    echo "Error: ethtool not detected in the system."
    echo "Please use the following command to install ethtool:"
    echo "sudo apt update && sudo apt install ethtool"
    exit 1
fi
```

| 命令 | 作用 |
|------|------|
| `dpkg -l` | 列出系统中所有已安装的 Debian 软件包 |
| `grep -q "ethtool"` | 在列表中静默搜索 `ethtool`，找到返回 0，没找到返回 1 |
| `!` | 取反：如果没找到 ethtool，就执行 then 分支 |

> **ethtool** 是一个用于查询和配置网卡参数的工具。这里用它来获取 USB-to-CAN 适配器的硬件地址（bus-info）。
> 如果没有安装 ethtool，脚本会提示安装方法并退出。

```bash
if ! dpkg -l | grep -q "can-utils"; then
    echo "Error: can-utils not detected in the system."
    ...
    exit 1
fi
```
> 同理，检查 `can-utils` 是否已安装。
>
> **can-utils** 是 Linux CAN 工具集，包含 `candump`、`cansend` 等常用命令，是操作 CAN 总线的基础工具。

```bash
echo "Both ethtool and can-utils are installed."
```
> 依赖检查通过，继续执行。

---

## 第二部分：检测 CAN 接口数量

```bash
CURRENT_CAN_COUNT=$(ip link show type can | grep -c "link/can")
```

| 命令 | 作用 |
|------|------|
| `ip link show type can` | 列出系统中所有 CAN 类型的网络接口 |
| `grep -c "link/can"` | 统计包含 `"link/can"` 的行数，即 CAN 接口的数量 |

> 示例：如果插了 1 个 USB-to-CAN，返回 `1`；插了 2 个，返回 `2`。

```bash
if [ "$CURRENT_CAN_COUNT" -ne "1" ]; then
```
> **判断是否恰好只有 1 个 CAN 接口**。
> - `-ne` = not equal（不等于）
> - 官方脚本**默认假设只配置 1 个 CAN 模块**
> - 如果检测到 0 个或多个，进入特殊处理逻辑

### 多 CAN 模块的处理逻辑

```bash
if [ -z "$USB_ADDRESS" ]; then
```
> **检查用户是否传了 USB 硬件地址**。
> - `-z` = 判断字符串是否为空
> - 如果没传 USB_ADDRESS，说明用户没指定用哪个适配器，此时脚本**无法确定要配置哪一个**，进入报错分支

```bash
for iface in $(ip -br link show type can | awk '{print $1}'); do
    BUS_INFO=$(sudo ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')
    echo "Interface $iface is inserted into USB port $BUS_INFO"
done
```

| 命令 | 作用 |
|------|------|
| `ip -br link show type can \| awk '{print $1}'` | 列出所有 CAN 接口的名称 |
| `sudo ethtool -i "$iface"` | 查询指定接口的驱动信息 |
| `grep "bus-info"` | 过滤出 USB 硬件地址行 |
| `awk '{print $2}'` | 提取地址值 |

> 当检测到多个 CAN 接口时，脚本会**遍历所有接口**，打印出每个接口对应的 USB 插槽地址，方便用户选择。

```bash
echo -e " Error: The number of CAN modules detected by the system ($CURRENT_CAN_COUNT) does not match the expected number (1). "
echo -e " Please add the USB hardware address parameter, such as: "
echo -e " bash can_activate.sh can0 1000000 1-2:1.0"
```
> 报错并提示用户：**请加上 USB 硬件地址参数**来指定要配置哪个适配器。

### 如果用户传了 USB_ADDRESS

```bash
if [ -n "$USB_ADDRESS" ]; then
```
> `-n` = 判断字符串**非空**。用户传了 USB 地址，进入精确匹配分支。

```bash
for iface in $(ip -br link show type can | awk '{print $1}'); do
    BUS_INFO=$(sudo ethtool -i "$iface" | grep "bus-info" | awk '{print $2}')
    if [ "$BUS_INFO" = "$USB_ADDRESS" ]; then
        INTERFACE_NAME="$iface"
        break
    fi
done
```
> **遍历所有 CAN 接口**，通过 `ethtool` 获取每个接口的 USB 硬件地址，与用户传入的 `$USB_ADDRESS` 对比。
> - 匹配成功 → 记录接口名到 `INTERFACE_NAME`
> - 匹配失败 → 继续遍历

```bash
if [ -z "$INTERFACE_NAME" ]; then
    echo "Error: Unable to find CAN interface corresponding to USB hardware address $USB_ADDRESS."
    exit 1
```
> 如果遍历完都没找到匹配的，报错退出。

### 如果恰好只有 1 个 CAN 接口

```bash
else
    INTERFACE_NAME=$(ip -br link show type can | awk '{print $1}')
    BUS_INFO=$(sudo ethtool -i "$INTERFACE_NAME" | grep "bus-info" | awk '{print $2}')
    echo "Expected to configure a single CAN module, detected interface $INTERFACE_NAME with corresponding USB address $BUS_INFO."
fi
```
> 直接用唯一的那个 CAN 接口，并打印它的 USB 地址信息。

---

## 第三部分：检查当前接口状态（避免重复配置）

```bash
IS_LINK_UP=$(ip link show "$INTERFACE_NAME" | grep -q "UP" && echo "yes" || echo "no")
```

| 语法 | 作用 |
|------|------|
| `grep -q "UP"` | 检查接口状态是否包含 "UP"（已激活）|
| `&& echo "yes"` | 如果找到，输出 yes |
| `\|\| echo "no"` | 如果没找到，输出 no |

> 把检查结果存到变量 `IS_LINK_UP` 中，值为 `yes` 或 `no`。

```bash
CURRENT_BITRATE=$(ip -details link show "$INTERFACE_NAME" | grep -oP 'bitrate \K\d+')
```

| 语法 | 作用 |
|------|------|
| `ip -details link show` | 显示接口详细信息 |
| `grep -oP 'bitrate \K\d+'` | 用 Perl 正则匹配 `bitrate ` 后面的数字 |

> 提取当前接口的波特率数值，存入 `CURRENT_BITRATE`。

```bash
if [ "$IS_LINK_UP" = "yes" ] && [ "$CURRENT_BITRATE" -eq "$DEFAULT_BITRATE" ]; then
```
> **核心优化**：如果接口**已经激活**（UP）且**波特率已经正确**，则**跳过重新配置**，只做重命名检查。
> - 这样可以避免每次都 down/up，减少设备磨损和等待时间

### 已激活且波特率正确的情况

```bash
echo "Interface $INTERFACE_NAME is already activated with a bitrate of $DEFAULT_BITRATE."

if [ "$INTERFACE_NAME" != "$DEFAULT_CAN_NAME" ]; then
    echo "Rename interface $INTERFACE_NAME to $DEFAULT_CAN_NAME."
    sudo ip link set "$INTERFACE_NAME" down
    sudo ip link set "$INTERFACE_NAME" name "$DEFAULT_CAN_NAME"
    sudo ip link set "$DEFAULT_CAN_NAME" up
    echo "The interface has been renamed to $DEFAULT_CAN_NAME and reactivated."
else
    echo "The interface name is already $DEFAULT_CAN_NAME."
fi
```
> 只需检查是否需要**重命名**接口，不需要重新配置波特率。

### 未激活或波特率不正确的情况

```bash
else
    if [ "$IS_LINK_UP" = "yes" ]; then
        echo "Interface $INTERFACE_NAME is already activated, but the bitrate is $CURRENT_BITRATE, which does not match the set value of $DEFAULT_BITRATE."
    else
        echo "Interface $INTERFACE_NAME is not activated or bitrate is not set."
    fi
```
> 告诉用户当前是什么状态：
> - 已激活但波特率不对 → 需要重新配置
> - 完全没激活 → 需要全新配置

```bash
    sudo ip link set "$INTERFACE_NAME" down
    sudo ip link set "$INTERFACE_NAME" type can bitrate $DEFAULT_BITRATE
    sudo ip link set "$INTERFACE_NAME" up
    echo "Interface $INTERFACE_NAME has been reset to bitrate $DEFAULT_BITRATE and activated."
```
> 三步走：
> 1. `down` → 关闭接口
> 2. `type can bitrate 1000000` → 配置为 CAN 类型，波特率 1 Mbps
> 3. `up` → 启动接口

```bash
    if [ "$INTERFACE_NAME" != "$DEFAULT_CAN_NAME" ]; then
        echo "Rename interface $INTERFACE_NAME to $DEFAULT_CAN_NAME."
        sudo ip link set "$INTERFACE_NAME" down
        sudo ip link set "$INTERFACE_NAME" name "$DEFAULT_CAN_NAME"
        sudo ip link set "$DEFAULT_CAN_NAME" up
        echo "The interface has been renamed to $DEFAULT_CAN_NAME and reactivated."
    fi
fi
```
> 配置完成后，如果需要，再重命名接口。

---

## 完整流程图

```
开始
  │
  ▼
检查 ethtool ──未安装──→ 报错退出
  │已安装
  ▼
检查 can-utils ──未安装──→ 报错退出
  │已安装
  ▼
检测 CAN 接口数量
  │
  ├─ 0 个 ───→ 报错退出（没插适配器）
  │
  ├─ 1 个 ───→ 直接使用该接口
  │
  └─ 多个 ───→ 用户是否传了 USB_ADDRESS?
       │
       ├─ 没传 ───→ 列出所有接口的 USB 地址，提示用户传参
       │
       └─ 传了 ───→ 通过 ethtool 匹配 USB 地址，定位目标接口
  │
  ▼
检查接口状态
  │
  ├─ 已 UP 且波特率正确 ───→ 只重命名，跳过配置
  │
  └─ 未 UP 或波特率不对 ───→ down → 配置波特率 → up → 重命名
  │
  ▼
完成
```

---

## 对比：官方脚本 vs 我们的脚本

| 场景 | 官方脚本 | 我们的脚本 |
|------|---------|-----------|
| 依赖检查 | ethtool + can-utils | ip 命令 |
| 多次执行 | 智能跳过（已激活则不重配） | 每次都重配 |
| 多 CAN 适配器 | 支持 USB 地址精确定位 | 只取第一个 |
| 驱动加载 | 不处理 | 自动加载 gs_usb |
| 适用场景 | 生产环境，更健壮 | 快速测试，更简洁 |

## 建议

**推荐使用官方脚本**（或基于它做少量修改），因为它：
1. 能避免不必要的重复配置
2. 支持多适配器环境
3. 经过 Piper 官方验证

如果要在官方脚本基础上改进，可以添加：
- 自动加载 `gs_usb` 驱动（我们脚本的优点）
- 更友好的中文输出提示
