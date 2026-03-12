#!/usr/bin/env python3
"""
基础 AI Agent
使用 OpenAI 标准 API，支持上下文对话和工具调用
"""

import json
import requests
import os
import yaml
import traceback
import platform
import datetime
import shutil
import tools_builtin

# 获取当前目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 设置工具函数的脚本目录
tools_builtin.set_script_dir(SCRIPT_DIR)

# 读取配置文件
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.yaml")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
else:
    config = {}

# 从配置中读取 API 配置
API_KEY = config.get("api", {}).get("key", "your-api-key")
BASE_URL = config.get("api", {}).get("base_url", "https://api.deepseek.com/v1")
MODEL = config.get("api", {}).get("model", "deepseek-chat")
TEMPERATURE = config.get("temperature", 0.7)

# ========== 记忆系统初始化 ==========
MEMORY_DIR = os.path.join(SCRIPT_DIR, "memory")
LOG_DIR = os.path.join(SCRIPT_DIR, "log")
SHORT_MEMORY_PATH = os.path.join(MEMORY_DIR, "short.md")
LONG_MEMORY_PATH = os.path.join(MEMORY_DIR, "long.md")

# 当前会话的历史日志文件路径
CURRENT_SESSION_LOG = None

def init_memory():
    """初始化记忆系统目录和文件"""
    # 创建目录
    os.makedirs(MEMORY_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 创建短期记忆文件（如果不存在）
    if not os.path.exists(SHORT_MEMORY_PATH):
        with open(SHORT_MEMORY_PATH, "w", encoding="utf-8") as f:
            f.write("")
    
    # 创建长期记忆文件（如果不存在）
    if not os.path.exists(LONG_MEMORY_PATH):
        with open(LONG_MEMORY_PATH, "w", encoding="utf-8") as f:
            f.write("")
def init_session():
    """初始化会话：创建日志文件并总结短期记忆"""
    # 预先创建当前会话的历史日志文件
    session_path = get_current_session_log_path()
    open(session_path, "w", encoding="utf-8").close()
    
    # 读取现有内容
    latest_log = read_latest_log()
    short_memory = read_short_memory()
    
    # 如果有内容，进行总结
    if latest_log.strip() or short_memory.strip():
        print("\n正在总结短期记忆...")
        new_summary = summarize_short_memory(latest_log, short_memory)
        write_short_memory(new_summary)
        print("短期记忆已更新")
    
    # 清空 latest.txt（开始新会话）
    latest_path = get_latest_log_path()
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write("")
def get_latest_log_path():
    """获取 latest.txt 路径"""
    return os.path.join(LOG_DIR, "latest.txt")

def get_current_session_log_path():
    """获取当前会话的历史日志文件路径"""
    global CURRENT_SESSION_LOG
    if CURRENT_SESSION_LOG is None:
        # 首次调用，创建一个新文件
        filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        CURRENT_SESSION_LOG = os.path.join(LOG_DIR, filename)
    return CURRENT_SESSION_LOG

def save_log(user_msg, ai_msg):
    """保存对话到日志文件"""
    log_entry = f"User: {user_msg}\nAI: {ai_msg}\n"
    
    # 追加到 latest.txt
    latest_path = get_latest_log_path()
    with open(latest_path, "a", encoding="utf-8") as f:
        f.write(log_entry)
    
    # 追加到当前会话历史文件
    session_path = get_current_session_log_path()
    with open(session_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def read_latest_log():
    """读取 latest.txt 内容"""
    latest_path = get_latest_log_path()
    if os.path.exists(latest_path):
        with open(latest_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def read_short_memory():
    """读取短期记忆"""
    if os.path.exists(SHORT_MEMORY_PATH):
        with open(SHORT_MEMORY_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def write_short_memory(content):
    """写入短期记忆"""
    with open(SHORT_MEMORY_PATH, "w", encoding="utf-8") as f:
        f.write(content)

def summarize_short_memory(latest_log, short_memory):
    """调用 AI 总结短期记忆"""
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """你是一个专业的聊天记录总结程序。用户会为你提供两段内容：
1. 之前的聊天内容总结
2. 新的聊天记录

你需要合并这两份信息，整合为一份新的总结。要求：
- 简明扼要，准确提炼关键信息
- 前半段总结是之前的内容，后半段是新的内容，二者各占一半
- 300字以内，越精炼越好
- 只输出总结内容，不要有其他任何文字"""

    user_prompt = f"""之前的内容总结：
{short_memory if short_memory.strip() else "（无）"}
新的聊天记录：
{latest_log if latest_log.strip() else "（无）"}"""

    data = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        result = response.json()
        
        if "choices" in result and len(result["choices"]) > 0:
            return result["choices"][0]["message"].get("content", "")
        else:
            return short_memory  # 如果失败，保留原内容
    except Exception as e:
        print(f"总结短期记忆失败: {e}")
        return short_memory



# 加载插件
print("正在加载插件...")
tools_builtin.load_plugins()

# 获取所有插件的名称和显示名称
extra_plugin_list = tools_builtin.get_all_plugins_list()

SKILLS_LIST = tools_builtin.list_skills()
# 获取当前系统名称
SYSTEM_NAME = platform.system().lower()  # Windows / Linux / Darwin(macOS)

# 读取系统提示词并进行占位符替换
SYSTEM_PROMPT_PATH = os.path.join(SCRIPT_DIR, "system_prompt.md")
if os.path.exists(SYSTEM_PROMPT_PATH):
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
    # 替换 {extra_plugin_list} 占位符
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{extra_plugin_list}", extra_plugin_list)
    # 替换 {system} 占位符
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{system}", SYSTEM_NAME)
    # 替换 {program_path} 占位符
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{program_path}", SCRIPT_DIR)
    # 替换 {skills_list} 占位符
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{skills_list}", SKILLS_LIST)
else:
    SYSTEM_PROMPT = "你是一个有用的AI助手。"

# 读取工具定义
TOOLS_PATH = os.path.join(SCRIPT_DIR, "tools.json")
if os.path.exists(TOOLS_PATH):
    with open(TOOLS_PATH, "r", encoding="utf-8") as f:
        TOOLS = json.load(f)
else:
    TOOLS = []

# 加载插件
'''
print("正在加载插件...")
tools_builtin.load_plugins()
print("插件加载完成")
'''
# 对话历史
messages = []

def chat(user_input):
    """发送对话请求"""
    global messages
    
    # 添加用户消息
    messages.append({
        "role": "user",
        "content": user_input
    })
    
    # 构建请求（包含系统提示词和工具）
    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    
    # 构建请求
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": MODEL,
        "messages": all_messages,
        "tools": TOOLS,
        "temperature": TEMPERATURE
    }
    
    # 发送请求
    response = requests.post(url, headers=headers, json=data)
    result = response.json()
    
    # 检查 API 错误
    if "error" in result:
        traceback.print_exc()
        return f"API Error: {result['error']}"
    
    # 检查是否有工具调用（循环处理多次工具调用）
    while True:
        if "choices" in result and len(result["choices"]) > 0:
            message = result["choices"][0]["message"]
            
            # 如果有工具调用
            if "tool_calls" in message and message["tool_calls"]:
                for tool_call in message["tool_calls"]:
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]
                    
                    # 解析 arguments（可能是 str 或 dict）
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    
                    # 执行工具
                    tool_result = tools_builtin.call_tool(tool_name, arguments)
                    
                    # 将工具结果添加到对话
                    messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result
                    })
                
                # 再次请求获取最终回复（AI 可能还会调用工具）
                url2 = f"{BASE_URL}/chat/completions"
                data2 = {
                    "model": MODEL,
                    "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                    "tools": TOOLS,
                    "temperature": TEMPERATURE
                }
                response2 = requests.post(url2, headers=headers, json=data2)
                result = response2.json()
                
                # 检查 API 错误
                if "error" in result:
                    traceback.print_exc()
                    return f"API Error: {result['error']}"
                
                # 继续循环，检查是否还有工具调用
                continue
        
        # 没有工具调用，返回最终回复
        break
    
    # 返回 AI 的最终回复
    if "choices" in result and len(result["choices"]) > 0:
        assistant_message = result["choices"][0]["message"]
        messages.append(assistant_message)
        ai_content = assistant_message.get("content", "")
        
        # 保存对话到日志
        save_log(user_input, ai_content)
        
        return ai_content
    else:
        return f"Error: {result}"

def main():
    print(f"系统提示词: {SYSTEM_PROMPT}")
    # 初始化记忆系统
    print("正在初始化记忆系统...")
    init_memory()
    init_session()
    print("记忆系统初始化完成")
    print("=" * 50)
    print("AI Agent 已启动")
    print("输入 'quit' 或 'exit' 退出")
    print("输入 'summary' 总结压缩对话到短期记忆")
    print("=" * 50)
    print()
    
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ["quit", "exit"]:
            print("再见！")
            break
        
        if user_input.lower() == "summary":
            init_session()
            messages.clear()
            print("对话历史已清空")
            continue
        
        if not user_input:
            continue
        
        try:
            response = chat(user_input)
            print(f"AI: {response}")
            print()
        except Exception as e:
            traceback.print_exc()
            print(f"Error: {e}")

if __name__ == "__main__":
    main()
