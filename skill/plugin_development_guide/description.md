# 插件开发完整指南

## 概述
本指南基于py-legnachat框架的插件系统，总结了插件开发的最佳实践、核心要点和常见模式。通过分析现有插件（hello、beijing_time、system_info、tavily）和框架文档，提供全面的插件开发指导。

## 插件系统架构

### 1. 基本结构
```
plugin/[插件名]/
├── main.py              # 插件主逻辑（必需）
├── description.yaml     # 插件描述（必需）
├── requirements.txt     # 依赖文件（可选）
└── apikey.txt          # API密钥文件（可选，如tavily插件）
```

### 2. 核心文件详解

#### main.py - 插件主逻辑
```python
def tool_main(arg):
    """
    插件主函数
    
    Args:
        arg: dict类型，包含调用时传入的参数
        
    Returns:
        str: 返回字符串结果，建议使用JSON格式返回结构化数据
    """
    # 插件逻辑实现
    return "插件执行结果"
```

**关键要点：**
- 必须有且仅有一个`tool_main`函数
- 参数`arg`是字典类型，包含调用时传入的JSON参数
- 返回值必须是字符串类型

#### description.yaml - 插件描述
```yaml
display_name: 插件简短描述
description: |
  插件详细说明，包含：
  1. 功能介绍
  2. 调用方式（JSON格式）
  3. 参数说明
  4. 返回值格式
  5. 示例
```

**关键要点：**
- `display_name`：简洁明了，<20字
- `description`：详细准确，包含调用方式和示例
- 调用方式必须明确说明JSON格式
- 示例要具体可执行

## 插件开发流程

### 1. 需求分析阶段
1. **明确功能**：插件要解决什么问题？
2. **确定输入输出**：需要什么参数？返回什么数据？
3. **评估复杂度**：是否需要外部依赖？是否需要API密钥？
4. **安全评估**：是否有安全风险？如何防范？

### 2. 开发实现阶段
1. **创建插件目录**：`plugin/插件名`
2. **编写description.yaml**：先定义接口，再实现功能
3. **编写main.py**：实现核心逻辑
4. **添加依赖**：如有需要，创建requirements.txt
5. **配置API密钥**：如有需要，创建apikey.txt

### 3. 测试验证阶段
1. **单元测试**：测试各种输入情况
2. **异常处理**：测试错误输入和网络异常
3. **性能测试**：确保响应时间合理
4. **安全测试**：验证无安全隐患

## 插件设计模式

### 1. 无参数插件（如beijing_time）
```python
def tool_main(arg):
    # 无需参数，直接返回结果
    return "固定格式的结果"
```

**description.yaml示例：**
```yaml
display_name: 获取北京时间
description: 获取当前北京时间。调用方式：{}（无需参数，直接调用即可）。返回当前日期和时间，格式为 YYYY-MM-DD HH:MM:SS，例如：2026-03-11 01:00:00
```

### 2. 简单参数插件（如hello）
```python
def tool_main(arg):
    name = arg.get("name", "World")
    return f"Hello, {name}!"
```

**description.yaml示例：**
```yaml
display_name: 测试插件，返回 Hello 消息
description: 这是一个测试插件，返回 Hello 消息。具体调用方式：参数使用json传入，格式为 {"name":"用户的名字"}。其中"用户的名字"你可以随便写，程序会返回"hello 用户的名字"
```

### 3. 复杂功能插件（如system_info）
```python
def tool_main(arg):
    # 收集多种系统信息
    result = {
        "os_info": {...},
        "cpu_info": {...},
        "memory_info": {...},
        "disk_info": [...],
        "python_info": {...}
    }
    return json.dumps(result, indent=2, ensure_ascii=False)
```

**关键要点：**
- 返回结构化数据，使用JSON格式
- 包含详细的错误处理
- 使用标准库（platform、psutil等）

### 4. API调用插件（如tavily）
```python
def tool_main(arg):
    # 读取本地API密钥
    api_key = _get_apikey()
    if not api_key:
        return "Error: 未找到apikey.txt文件"
    
    # 调用外部API
    response = requests.post(url, json=data, headers=headers)
    # 处理返回结果
    return formatted_result
```

**关键要点：**
- API密钥存储在本地文件（apikey.txt）
- 完整的网络异常处理
- 结果格式化，便于AI阅读

## 最佳实践

### 1. 错误处理
```python
def tool_main(arg):
    try:
        # 主逻辑
        result = do_something(arg)
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        # 返回错误信息，而不是抛出异常
        return json.dumps({"error": str(e)}, indent=2, ensure_ascii=False)
```

### 2. 参数验证
```python
def tool_main(arg):
    # 验证必需参数
    required_params = ["query", "limit"]
    for param in required_params:
        if param not in arg:
            return f"Error: 缺少必需参数 '{param}'"
    
    # 验证参数类型
    if not isinstance(arg.get("limit"), int):
        return "Error: 参数'limit'必须是整数"
    
    # 验证参数范围
    if arg["limit"] <= 0 or arg["limit"] > 100:
        return "Error: 参数'limit'必须在1-100之间"
```

### 3. 结果格式化
```python
def tool_main(arg):
    # 对于AI友好的格式
    if isinstance(result, dict) or isinstance(result, list):
        # 结构化数据使用JSON
        return json.dumps(result, indent=2, ensure_ascii=False)
    else:
        # 简单文本直接返回
        return str(result)
```

### 4. 依赖管理
```python
# requirements.txt示例
requests>=2.25.1
beautifulsoup4>=4.9.3
psutil>=5.8.0
```

**注意事项：**
- 尽量使用标准库，减少外部依赖
- 如有依赖，必须在requirements.txt中明确指定版本
- 考虑依赖的安装难度和兼容性

## 安全规范

### 1. 绝对禁止
- ❌ 执行未授权的系统命令
- ❌ 访问用户隐私数据
- ❌ 修改用户文件系统
- ❌ 建立网络连接（除非明确需要）
- ❌ 包含恶意代码

### 2. 必须做到
- ✅ 所有操作透明可追溯
- ✅ 用户数据本地处理
- ✅ 异常安全处理
- ✅ 最小权限原则
- ✅ 代码开源可审查

### 3. API密钥安全
```python
# 正确做法：从本地文件读取
def _get_apikey():
    """从插件目录下的apikey.txt读取API密钥"""
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    apikey_file = os.path.join(plugin_dir, "apikey.txt")
    
    if not os.path.exists(apikey_file):
        return None
    
    with open(apikey_file, "r", encoding="utf-8") as f:
        return f.read().strip()
```

## 插件示例模板

### 模板1：简单功能插件
```python
# main.py
def tool_main(arg):
    """
    简单功能插件示例
    
    Args:
        arg: dict，包含插件参数
        
    Returns:
        str: 执行结果
    """
    # 获取参数，设置默认值
    param1 = arg.get("param1", "default_value")
    
    # 执行功能
    result = f"处理结果: {param1}"
    
    return result
```

```yaml
# description.yaml
display_name: 简单功能插件
description: |
  这是一个简单功能插件示例。
  
  调用方式：
  ```json
  {"param1": "参数值"}
  ```
  
  参数说明：
  - param1: 字符串参数，可选，默认值为"default_value"
  
  返回值：
  字符串格式的处理结果
  
  示例：
  ```json
  {"param1": "测试数据"}
  ```

  返回：
  ```
  "处理结果: 测试数据"
  ```

### 模板2：API调用插件
```python
# main.py
import os
import requests
import json

def _get_apikey():
    """读取API密钥"""
    plugin_dir = os.path.dirname(os.path.abspath(__file__))
    apikey_file = os.path.join(plugin_dir, "apikey.txt")
    
    if not os.path.exists(apikey_file):
        return None
    
    with open(apikey_file, "r", encoding="utf-8") as f:
        return f.read().strip()

def tool_main(arg):
    """
    API调用插件示例
    
    Args:
        arg: dict，包含query参数
        
    Returns:
        str: 搜索结果
    """
    # 验证参数
    query = arg.get("query", "")
    if not query:
        return "Error: 请提供搜索关键词 (query)"
    
    # 获取API密钥
    api_key = _get_apikey()
    if not api_key:
        return "Error: 未配置API密钥，请在插件目录下创建apikey.txt并填入密钥"
    
    try:
        # 调用API
        response = requests.post(
            "https://api.example.com/search",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query},
            timeout=30
        )
        
        if response.status_code != 200:
            return f"Error: API返回错误 {response.status_code}"
        
        # 处理结果
        data = response.json()
        # 格式化结果
        return json.dumps(data, indent=2, ensure_ascii=False)
        
    except requests.exceptions.Timeout:
        return "Error: 请求超时"
    except Exception as e:
        return f"Error: {str(e)}"
```

## 常见问题解决

### 1. 插件未加载
- 检查插件目录结构是否正确
- 检查description.yaml格式是否正确
- 重启Agent程序

### 2. 参数传递错误
- 确保description.yaml中调用方式描述准确
- 验证JSON参数格式
- 检查参数名称大小写

### 3. 依赖安装失败
- 检查requirements.txt格式
- 确认依赖包名称正确
- 考虑依赖兼容性

## 文档编写要点

### 1. description.yaml编写
- 功能描述清晰准确
- 调用方式具体可执行
- 参数说明完整
- 示例真实有效

### 2. 代码注释
- 函数说明包含参数和返回值
- 复杂逻辑添加注释
- 关键算法说明原理
- 外部依赖注明来源

## 总结

插件开发的核心是**简单、安全、可靠**：
1. **简单**：功能单一，接口清晰
2. **安全**：不危害用户系统，保护隐私
3. **可靠**：稳定运行，良好错误处理

通过遵循本指南，你可以开发出高质量的py-legnachat插件，为AI助手提供强大的功能扩展能力。