# 系统配置信息查询

## 概述
通过Windows系统命令查询计算机硬件和系统配置信息，包括CPU、内存、硬盘、网络等详细信息。
这些技巧只能用在Windows下，其它系统是不能用的。

## 使用方法
使用`execute_command`工具执行以下系统命令：

```bash
# 1. 获取系统基本信息
systeminfo

# 2. 获取CPU详细信息
wmic cpu get name,numberofcores,numberoflogicalprocessors,maxclockspeed

# 3. 获取内存详细信息
wmic memorychip get capacity,speed,manufacturer,partnumber

# 4. 获取硬盘信息
wmic diskdrive get model,size,interfaceType

# 5. 获取操作系统信息
wmic os get caption,version,osarchitecture
```

## 示例

### 示例1：完整查询系统配置
```bash
# 执行系统信息查询
systeminfo

# 查询CPU信息
wmic cpu get name,numberofcores,numberoflogicalprocessors,maxclockspeed

# 查询内存信息
wmic memorychip get capacity,speed,manufacturer,partnumber

# 查询硬盘信息
wmic diskdrive get model,size,interfaceType

# 查询操作系统信息
wmic os get caption,version,osarchitecture
```

### 示例2：查询特定硬件信息
```bash
# 只查询CPU和内存
wmic cpu get name,numberofcores,numberoflogicalprocessors
wmic memorychip get capacity,speed
```

### 示例3：格式化输出查询结果
```bash
# 使用更友好的格式查询CPU信息
wmic cpu get name,numberofcores,numberoflogicalprocessors,maxclockspeed /format:list
```

## 注意事项
1. **权限要求**：需要管理员权限才能获取完整的系统信息
2. **命令可用性**：这些命令在Windows系统上可用，其他操作系统可能需要不同的命令
3. **信息准确性**：某些硬件信息可能因驱动或系统版本而显示不完整
4. **执行时间**：`systeminfo`命令可能需要几秒钟才能完成
5. **输出格式**：WMIC命令的输出格式可能需要进一步处理才能获得更易读的结果
6. **替代方案**：对于更详细的硬件信息，可以考虑使用`dxdiag`或第三方工具

## 扩展查询命令
```bash
# 查询显卡信息
wmic path win32_videocontroller get name,adapterram

# 查询主板信息
wmic baseboard get product,manufacturer,version

# 查询BIOS信息
wmic bios get manufacturer,name,version

# 查询网络适配器详细信息
wmic nic get name,netenabled,macaddress,ipaddress
```

## 结果解析提示
1. **内存容量**：WMIC返回的容量单位为字节，需要转换为GB（除以1073741824）
2. **硬盘容量**：同样需要从字节转换为GB
3. **CPU速度**：MaxClockSpeed单位为MHz
4. **网络状态**：需要检查网络适配器的连接状态

## 安全注意事项
1. 这些命令是只读操作，不会修改系统配置
2. 查询结果可能包含系统敏感信息，请注意保护隐私
3. 确保在合法授权的情况下查询系统信息