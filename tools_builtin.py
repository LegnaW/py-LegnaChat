#!/usr/bin/env python3
"""
内置工具函数 + 插件加载
"""

import json
import requests
import os
import importlib.util
import subprocess
import traceback

# 全局变量
SCRIPT_DIR = None
PLUGINS = {}  # 已加载的插件

def set_script_dir(dir_path):
    """设置脚本目录"""
    global SCRIPT_DIR
    SCRIPT_DIR = dir_path

# ========== 插件加载 ==========

def load_plugins():
    """加载所有插件"""
    global PLUGINS
    
    if SCRIPT_DIR is None:
        return
    
    plugin_dir = os.path.join(SCRIPT_DIR, "plugin")
    if not os.path.exists(plugin_dir):
        return
    
    # 遍历 plugin 下的每个文件夹
    for plugin_name in os.listdir(plugin_dir):
        plugin_path = os.path.join(plugin_dir, plugin_name)
        if not os.path.isdir(plugin_path):
            continue
        
        main_file = os.path.join(plugin_path, "main.py")
        desc_file = os.path.join(plugin_path, "description.yaml")
        req_file = os.path.join(plugin_path, "requirements.txt")
        
        if not os.path.exists(main_file):
            continue
        
        # 读取 YAML 描述
        plugin_name_display = plugin_name
        description = ""
        if os.path.exists(desc_file):
            try:
                import yaml
                with open(desc_file, "r", encoding="utf-8") as f:
                    desc_data = yaml.safe_load(f)
                    plugin_name_display = desc_data.get("display_name", plugin_name)
                    description = desc_data.get("description", "")
            except Exception as e:
                print(f"读取插件描述失败: {e}")
        
        # 安装依赖
        if os.path.exists(req_file):
            try:
                subprocess.run(
                    ["pip", "install", "-r", req_file],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
            except Exception as e:
                print(f"安装插件 {plugin_name} 依赖失败: {e}")
        
        # 动态加载模块
        try:
            spec = importlib.util.spec_from_file_location(f"plugin_{plugin_name}", main_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            PLUGINS[plugin_name] = {
                "module": module,
                "display_name": plugin_name_display,
                "description": description,
                "path": plugin_path
            }
            print(f"已加载插件: {plugin_name_display}")
        except Exception as e:
            print(f"加载插件 {plugin_name} 失败: {e}")

# 插件保持独立，不合并到 tools
'''
def call_plugin(plugin_name, arg):
    """调用插件"""
    if plugin_name not in PLUGINS:
        return f"Error: 插件 {plugin_name} 不存在"
    
    try:
        module = PLUGINS[plugin_name]["module"]
        if hasattr(module, "tool_main"):
            # 解析参数
            if isinstance(arg, str):
                import json as json_mod
                arg = json_mod.loads(arg)
            return module.tool_main(arg)
        else:
            return f"Error: 插件 {plugin_name} 没有 tool_main 函数"
    except Exception as e:
        traceback.print_exc()
        return f"Error: {str(e)}"
'''
# ========== 内置工具函数 ==========

def execute_command(command):
    """执行控制台命令，需要用户确认"""
    print("\n" + "=" * 50)
    print("即将执行命令:")
    print(command)
    print("=" * 50)
    confirm = input("确认执行? (输入 y 确认): ").strip().lower()
    
    if confirm != "y":
        return "用户拒绝"
    
    def _try_decode(data, encodings):
        """尝试多种编码解码"""
        for enc in encodings:
            try:
                return data.decode(enc), enc
            except (UnicodeDecodeError, AttributeError):
                continue
        return data.decode("utf-8", errors="replace"), "utf-8(replaced)"
    
    try:
        # 先用 bytes 模式获取原始输出，再尝试多种编码
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=30
        )
        
        # 尝试多种编码：UTF-8 -> GBK -> GB2312
        stdout, _ = _try_decode(result.stdout, ["utf-8", "gbk", "gb2312"])
        stderr, _ = _try_decode(result.stderr, ["utf-8", "gbk", "gb2312"])
        
        output = stdout
        if stderr:
            output += "\nSTDERR: " + stderr
        
        return output if output.strip() else "执行完成（无输出）"
    except subprocess.TimeoutExpired:
        return "Error: 命令执行超时"
    except Exception as e:
        traceback.print_exc()
        return f"Error: {str(e)}"
    
def write_file(content, path, mode):
    """写入文件内容到指定路径"""
    print("\n" + "=" * 50)
    print("即将写进文件:")
    print(path)
    print("=" * 50)
    confirm = input("确认执行? (输入 y 确认): ").strip().lower()
    
    if confirm != "y":
        return "用户拒绝"
    try:
        if mode in ["w","a"]:
            with open(path, mode=mode, encoding="utf-8") as f:
                f.write(content)
            return f"文件已写入: {path}"
        else:
            return "错误的调用方式！"
    except Exception as e:
        traceback.print_exc()
        return f"Error: {str(e)}"
    
def extensions_search(query):
    """查询额外功能列表或插件描述"""
    global PLUGINS
    
    if SCRIPT_DIR is None:
        return "Error: 未设置脚本目录"
    
    # 方式1：查询所有插件
    if query == "all":
        result = []
        for plugin_key, plugin_info in PLUGINS.items():
            result.append({plugin_key: plugin_info.get("display_name", plugin_key)})
        return str(result)
    
    # 方式2：查询指定插件的 description
    if query in PLUGINS:
        desc = PLUGINS[query].get("description", "")
        return desc if desc else "该插件暂无描述"
    '''
    # 查询 extensions.md
    ext_path = os.path.join(SCRIPT_DIR, "extensions.md")
    if os.path.exists(ext_path):
        with open(ext_path, "r", encoding="utf-8") as f:
            return f.read()
    '''
    return "Error: 未找到相关内容"

def extensions(tool_name, required_args):
    """执行额外功能（插件）"""
    global PLUGINS
    
    # 检查插件是否存在
    if tool_name not in PLUGINS:
        return f"Error: 插件 {tool_name} 不存在"
    
    # 解析 required_args 为 JSON 字典
    try:
        if isinstance(required_args, str):
            args = json.loads(required_args)
        else:
            args = required_args
    except json.JSONDecodeError as e:
        return f"json格式不对！错误报告: {str(e)}"
    except Exception as e:
        return f"json格式不对！错误报告: {str(e)}"
    
    # 调用插件的 tool_main 函数
    try:
        module = PLUGINS[tool_name]["module"]
        if hasattr(module, "tool_main"):
            result = module.tool_main(args)
            return result
        else:
            return f"Error: 插件 {tool_name} 没有 tool_main 函数"
    except Exception as e:
        traceback.print_exc()
        return f"执行出错！错误报告: {str(e)}"

def list_skills():
    """列出 skill 文件夹中所有技巧"""
    if SCRIPT_DIR is None:
        return "Error: 未设置脚本目录"
    
    skill_dir = os.path.join(SCRIPT_DIR, "skill")
    if not os.path.exists(skill_dir):
        return "Error: skill 文件夹不存在"
    
    if not os.path.isdir(skill_dir):
        return "Error: skill 不是一个目录"
    
    result = []
    
    # 遍历 skill 文件夹下的所有子目录
    for skill_name in os.listdir(skill_dir):
        skill_path = os.path.join(skill_dir, skill_name)
        if not os.path.isdir(skill_path):
            continue
        
        display_file = os.path.join(skill_path, "display.txt")
        
        # 读取简略描述
        description = ""
        if os.path.exists(display_file):
            try:
                with open(display_file, "r", encoding="utf-8") as f:
                    description = f.read().strip()
            except Exception as e:
                description = ""
        
        # 添加到结果列表
        result.append({description: f"skill/{skill_name}"})
    if result == []:
        return("程序当前似乎没有任何技巧！")
    return str(result)

def read_memory():
    """读取记忆"""
    if SCRIPT_DIR is None:
        return "Error: 未设置脚本目录"
    short_mem = "**短期记忆内容：** 不存在\n"
    short_memory_path = os.path.join(SCRIPT_DIR, "memory", "short.md")
    if os.path.exists(short_memory_path):
        try:
            with open(short_memory_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                short_mem = f"**短期记忆内容：**\n{content}\n"
        except Exception as e:
            return f"Error: 读取失败: {str(e)}"
    long_mem = "**长期记忆内容：** 不存在\n\n"
    long_memory_path = os.path.join(SCRIPT_DIR, "memory", "long.md")
    if os.path.exists(long_memory_path):
        try:
            with open(long_memory_path, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                long_mem = f"**长期记忆内容：**\n{content}\n"
        except Exception as e:
            return f"Error: 读取失败: {str(e)}"
    result = short_mem + long_mem
    return result

def read_file(path):
    """读取指定文件的内容"""
    if not path:
        return "Error: 请提供文件路径"
    
    # 处理绝对路径和相对路径
    if os.path.isabs(path):
        full_path = path
    else:
        # 相对路径基于脚本目录
        full_path = os.path.join(SCRIPT_DIR, path)
    
    if not os.path.exists(full_path):
        return f"Error: 文件不存在: {path}"
    
    if not os.path.isfile(full_path):
        return f"Error: 路径不是文件: {path}"
    
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content if content.strip() else "（文件为空）"
    except Exception as e:
        return f"Error: 读取失败: {str(e)}"
    
    


# ========== 工具调用分发 ==========

def call_tool(tool_name, arguments):
    """调用工具"""
    print("\n" + "=" * 50)
    print(f"调用工具: {tool_name}")
    print(f"参数: {arguments}")
    print("=" * 50)
    
    result = ""
    
    if tool_name == "execute_command":
        result = execute_command(arguments.get("command", ""))
    elif tool_name == "write_file":
        result = write_file(arguments.get("content", ""), arguments.get("path", ""), arguments.get("mode", ""))
    elif tool_name == "extensions_search":
        result = extensions_search(arguments.get("query", ""))
    elif tool_name == "extensions":
        tool_name_arg = arguments.get("tool_name", "")
        required_args = arguments.get("required_args", "{}")
        result = extensions(tool_name_arg, required_args)
    elif tool_name == "list_skills":
        result = list_skills()
    elif tool_name == "read_memory":
        result = read_memory()
    elif tool_name == "read_file":
        result = read_file(arguments.get("path", ""))
    else:
        result = f"Error: 未知工具: {tool_name}"
    
    print(f"\n工具返回值:\n{result}")
    print("=" * 50 + "\n")
    
    return result


def get_all_plugins_list():
    """获取所有插件的名称和显示名称数组"""
    global PLUGINS
    result = []
    for plugin_key, plugin_info in PLUGINS.items():
        result.append({plugin_key: plugin_info.get("display_name", plugin_key)})
    return str(result)


