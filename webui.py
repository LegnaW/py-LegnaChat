#!/usr/bin/env python3
"""
Web UI - 使用 Gradio 提供网页界面
参考官方 Agent 工具调用文档重写
"""

import json
import requests
import os
import yaml
import traceback
import platform
import datetime
from pathlib import Path
import gradio as gr
from gradio import ChatMessage

# 获取当前目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 导入工具模块
import sys
sys.path.insert(0, SCRIPT_DIR)
import tools_builtin_webui as tools_builtin
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
TOOL_OUTPUT_LENGTH = config.get("tool_output_length", 10000)
TEMPERATURE = config.get("temperature", 0.7)
SERVER_PORT = config.get("server_port", 9600)
OPEN_BROWSER = config.get("open_browser", True)

# ========== 路径初始化 ==========
MEMORY_DIR = os.path.join(SCRIPT_DIR, "memory")
LOG_DIR = os.path.join(SCRIPT_DIR, "log")
SHORT_MEMORY_PATH = os.path.join(MEMORY_DIR, "short.md")
LONG_MEMORY_PATH = os.path.join(MEMORY_DIR, "long.md")
CURRENT_SESSION_LOG = None
SKILL_DIR = os.path.join(SCRIPT_DIR, "skill")
AI_PROGRAM_DIR = os.path.join(SCRIPT_DIR, "ai-programs")

SAFE_PATH_DEFAULT = [MEMORY_DIR,SKILL_DIR,AI_PROGRAM_DIR]
SAFE_PATH = config.get("safe_path", SAFE_PATH_DEFAULT)
if SAFE_PATH == []:
    SAFE_PATH = SAFE_PATH_DEFAULT

# 全局变量：默认不允许危险操作
ALLOW_DANGEROUS_OPERATION = False
RESET_AND_SUMMERY = False

def register_env_variables():
    """将配置变量注册为环境变量，方便插件读取"""
    global ALLOW_DANGEROUS_OPERATION
    
    # API 配置
    os.environ["LEGNA_API_KEY"] = API_KEY
    os.environ["LEGNA_BASE_URL"] = BASE_URL
    os.environ["LEGNA_MODEL"] = MODEL
    
    # 功能配置
    os.environ["LEGNA_TOOL_OUTPUT_LENGTH"] = str(TOOL_OUTPUT_LENGTH)
    os.environ["LEGNA_TEMPERATURE"] = str(TEMPERATURE)
    os.environ["LEGNA_SERVER_PORT"] = str(SERVER_PORT)
    os.environ["LEGNA_OPEN_BROWSER"] = str(OPEN_BROWSER)
    
    # 安全配置
    os.environ["LEGNA_ALLOW_DANGEROUS_OPERATION"] = str(ALLOW_DANGEROUS_OPERATION).lower()
    os.environ["LEGNA_SAFE_PATH"] = str(SAFE_PATH)
    
    # 目录配置
    os.environ["LEGNA_SCRIPT_DIR"] = SCRIPT_DIR
    os.environ["LEGNA_MEMORY_DIR"] = MEMORY_DIR
    os.environ["LEGNA_LOG_DIR"] = LOG_DIR
    os.environ["LEGNA_SKILL_DIR"] = SKILL_DIR

# 注册环境变量
register_env_variables()

def get_current_session_log_path():
    """获取当前会话的历史日志文件路径"""
    global CURRENT_SESSION_LOG
    if CURRENT_SESSION_LOG is None:
        # 首次调用，创建一个新文件
        filename = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        CURRENT_SESSION_LOG = os.path.join(LOG_DIR, filename)
    return CURRENT_SESSION_LOG

def init_memory():
    """初始化记忆系统目录和文件"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    
    if not os.path.exists(SHORT_MEMORY_PATH):
        with open(SHORT_MEMORY_PATH, "w", encoding="utf-8") as f:
            f.write("")
    
    if not os.path.exists(LONG_MEMORY_PATH):
        with open(LONG_MEMORY_PATH, "w", encoding="utf-8") as f:
            f.write("")

def read_latest_log():
    """读取 latest.txt 内容"""
    latest_path = get_latest_log_path()
    if os.path.exists(latest_path):
        with open(latest_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def parse_ai_response(response_text):
    """
    解析AI回复，提取思考片段和回复片段
    
    Args:
        response_text (str): AI的完整回复字符串
        
    Returns:
        list: [思考片段, 回复片段]，如果没有对应片段则为空字符串
    """
    # 初始化结果
    think_content = ""
    reply_content = ""
    
    # 查找思考片段的开始和结束位置
    start_tag = "<think>"
    end_tag = "</think>"
    
    start_pos = response_text.find(start_tag)
    end_pos = response_text.find(end_tag)
    
    # 情况1：有完整的思考片段（同时存在开始和结束标签）
    if start_pos != -1 and end_pos != -1 and end_pos > start_pos:
        # 提取思考内容（不包括标签本身）
        think_content = response_text[start_pos + len(start_tag):end_pos].strip()
        
        # 提取回复内容（思考片段之后的内容）
        reply_content = response_text[end_pos + len(end_tag):].strip()
        
        # 如果思考片段之前还有内容（比如模型先回复再思考的情况，虽然少见，但做兼容处理）
        if start_pos > 0:
            before_think = response_text[:start_pos].strip()
            if before_think:
                # 如果思考前有内容，且思考后也有内容，则需要拼接
                if reply_content:
                    reply_content = before_think + "\n" + reply_content
                else:
                    reply_content = before_think
    
    # 情况2：只有开始标签但没有结束标签
    elif start_pos != -1 and end_pos == -1:
        # 从开始标签后到结尾都是思考内容
        think_content = response_text[start_pos + len(start_tag):].strip()
        # 开始标签前的内容作为回复
        if start_pos > 0:
            reply_content = response_text[:start_pos].strip()
    
    # 情况3：只有结束标签但没有开始标签
    elif start_pos == -1 and end_pos != -1:
        # 结束标签前的内容作为思考内容
        think_content = response_text[:end_pos].strip()
        # 结束标签后的内容作为回复
        reply_content = response_text[end_pos + len(end_tag):].strip()
    
    # 情况4：没有找到任何标签
    else:
        reply_content = response_text.strip()
    
    return [think_content, reply_content]

def init_session():
    """初始化会话：创建日志文件并总结短期记忆"""
    # 预先创建当前会话的历史日志文件
    session_path = get_current_session_log_path()
    open(session_path, "w", encoding="utf-8").close()
    
    # 读取现有内容
    latest_log = read_latest_log()
    short_memory = read_short_memory()
    
    # 如果有内容，进行总结
    if latest_log.strip():
        print("\n正在总结短期记忆...")
        new_summary = summarize_short_memory(latest_log, short_memory)
        write_short_memory(new_summary)
        #print("短期记忆已更新")
    
    # 清空 latest.txt（开始新会话）
    latest_path = get_latest_log_path()
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write("")
def get_latest_log_path():
    return os.path.join(LOG_DIR, "latest.txt")

def save_log(user_msg, ai_msg):
    log_entry = f"User: {user_msg}\nAI: {ai_msg}\n"
    latest_path = get_latest_log_path()
    with open(latest_path, "a", encoding="utf-8") as f:
        f.write(log_entry)

def read_short_memory():
    if os.path.exists(SHORT_MEMORY_PATH):
        with open(SHORT_MEMORY_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def write_short_memory(content):
    with open(SHORT_MEMORY_PATH, "w", encoding="utf-8") as f:
        f.write(content)

def summarize_short_memory(latest_log, short_memory):
    """调用 AI 总结短期记忆"""
    if latest_log.strip() == '':
        print("无新log需要总结")
        return short_memory
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    system_prompt = """你是一个专业的聊天记录总结程序，负责为大语言模型总结记忆。用户会为你提供两段内容：
1. 之前的聊天内容的记忆总结
2. 新的聊天记录

你需要合并这两份信息，整合为一份新的记忆总结。要求：
- 简明扼要，准确提炼关键信息
- 600字以内，越精炼越好
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
        "temperature": 0.7
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=300)
        result = response.json()
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"].get("content", "")
            chat = parse_ai_response(content)[1]
            return chat
        else:
            return short_memory
    except Exception as e:
        print(f"总结短期记忆失败: {e}")
        return short_memory

def call_tool(tool_name, arguments):
    """调用工具"""
    print("\n" + "=" * 50)
    print(f"调用工具: {tool_name}")
    print(f"参数: {arguments}")
    print("=" * 50)
    
    result = ""
    
    if tool_name == "execute_command":
        if ALLOW_DANGEROUS_OPERATION == True:
            result = tools_builtin.execute_command(arguments.get("command", ""))
        else:
            result = "用户没有给你控制台权限。"
    elif tool_name == "write_file":
        if ALLOW_DANGEROUS_OPERATION == True or is_path_inside_any_safe(arguments.get("path", ""),SAFE_PATH) == True:
            result = tools_builtin.write_file(arguments.get("content", ""), arguments.get("path", ""), arguments.get("mode", "w"))
        else:
            result = f"用户没有给你操作这个目录的权限。你只能操作以下目录的文件：{SAFE_PATH}"
    elif tool_name == "extensions_search":
        result = tools_builtin.extensions_search(arguments.get("query", ""))
    elif tool_name == "extensions":
        tool_name_arg = arguments.get("tool_name", "")
        required_args = arguments.get("required_args", "{}")
        result = tools_builtin.extensions(tool_name_arg, required_args)
    elif tool_name == "list_skills":
        result = tools_builtin.list_skills()
    elif tool_name == "read_memory":
        result = tools_builtin.read_memory()
    elif tool_name == "read_file":
        result = tools_builtin.read_file(arguments.get("path", ""))
    elif tool_name == "extensions_reload":
        result = tools_builtin.extensions_reload()
    else:
        result = f"Error: 未知工具: {tool_name}"
    
    print(f"\n工具返回值:\n{result}")
    print("=" * 50 + "\n")
    
    
    if len(result) > TOOL_OUTPUT_LENGTH:
        result = result[:TOOL_OUTPUT_LENGTH]+f"\n......\n输出太长（>{TOOL_OUTPUT_LENGTH}字符），已省略后续。"
    return result

def format_system_prompt(prompt):
    prompt = prompt.replace("{extra_plugin_list}", extra_plugin_list)
    prompt = prompt.replace("{system}", SYSTEM_NAME)
    prompt = prompt.replace("{program_path}", SCRIPT_DIR)
    prompt = prompt.replace("{skills_list}", SKILLS_LIST)
    prompt = prompt.replace("{safe_path}", str(SAFE_PATH))
# ========== 加载插件和技能 ==========
print("正在加载插件...")
tools_builtin.load_plugins()
extra_plugin_list = tools_builtin.get_all_plugins_list()
SKILLS_LIST = tools_builtin.list_skills()
SYSTEM_NAME = platform.system().lower()

SYSTEM_PROMPT_PATH = os.path.join(SCRIPT_DIR, "system_prompt.md")
if os.path.exists(SYSTEM_PROMPT_PATH):
    with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{extra_plugin_list}", extra_plugin_list)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{system}", SYSTEM_NAME)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{program_path}", SCRIPT_DIR)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{skills_list}", SKILLS_LIST)
    SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{safe_path}", str(SAFE_PATH))
else:
    SYSTEM_PROMPT = "你是一个有用的AI助手。"

TOOLS_PATH = os.path.join(SCRIPT_DIR, "tools.json")
if os.path.exists(TOOLS_PATH):
    with open(TOOLS_PATH, "r", encoding="utf-8") as f:
        TOOLS = json.load(f)
else:
    TOOLS = []

# 全局变量：API 消息存储（完整记录，用于维持上下文）
api_messages = []

# 是否允许危险操作
ALLOW_DANGEROUS_OPERATION = False
ALLOW_DANGEROUS_OPERATION_PATH = os.path.join(SCRIPT_DIR,"allow_dangerous_operation.txt")
if os.path.exists(ALLOW_DANGEROUS_OPERATION_PATH):
    with open(ALLOW_DANGEROUS_OPERATION_PATH, "r", encoding="utf-8") as f:
        if f.read().strip() == 'true':
            ALLOW_DANGEROUS_OPERATION = True
else:
    with open(ALLOW_DANGEROUS_OPERATION_PATH, "w", encoding="utf-8") as f:
        f.write('false')

# 更新环境变量
os.environ["LEGNA_ALLOW_DANGEROUS_OPERATION"] = str(ALLOW_DANGEROUS_OPERATION).lower()


# ========== 工具函数 ==========

def truncate(text, max_len=500):
    """截断过长的文本"""
    if not isinstance(text, str):
        text = str(text)
    if len(text) > max_len:
        return text[:max_len] + f"\n... (共 {len(text)} 字符)"
    return text
def change_allow_dangerous_operation(arg):
    global ALLOW_DANGEROUS_OPERATION
    if arg == True:
        with open(ALLOW_DANGEROUS_OPERATION_PATH, "w", encoding="utf-8") as f:
            f.write('true')
        ALLOW_DANGEROUS_OPERATION = True
    else:
        with open(ALLOW_DANGEROUS_OPERATION_PATH, "w", encoding="utf-8") as f:
            f.write('false')
        ALLOW_DANGEROUS_OPERATION = False
    # 同步更新环境变量
    os.environ["LEGNA_ALLOW_DANGEROUS_OPERATION"] = str(ALLOW_DANGEROUS_OPERATION).lower()
    
def is_path_inside_any_safe(target_path, base_paths):
    """
    判断路径是否安全
    """
    # 将目标路径转换为绝对路径
    target = Path(target_path).resolve()
    
    for base_path in base_paths:
        base = Path(base_path).resolve()
        
        # 检查目标路径是否在基础路径之内
        try:
            # 使用relative_to检查是否为基础路径的子路径
            target.relative_to(base)
            return True
        except ValueError:
            # 如果不是子路径，继续检查下一个
            continue
    
    return False

def chat_fn(message, history):
    
    """
    处理对话
    - message: str - 用户最新消息
    - history: list[dict] - 前端显示用的历史（可能被清空）
    - 返回: 使用 yield 返回多个 ChatMessage
    
    注意：使用全局 api_messages 维持上下文，不依赖前端 history
    """
    chat_messages = []
    global api_messages
    
    # 使用 api_messages 维持上下文（即使刷新页面也不会丢失）
    # 添加当前用户消息
    api_messages.append({"role": "user", "content": message})
    
    # 构建请求 - 使用 api_messages 而不是 history
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    all_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + api_messages
    
    data = {
        "model": MODEL,
        "messages": all_messages,
        "tools": TOOLS,
        "temperature": TEMPERATURE
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=600)
        result = response.json()
        print(response.json())
    except Exception as e:
        chat_messages.append(ChatMessage(
                        role="assistant",
                        content= f"请求失败: {str(e)}",
                        metadata={}
                    ))
        yield chat_messages
        return chat_messages
    # 检查错误
    if "error" in result:
        chat_messages.append(ChatMessage(
                        role="assistant",
                        content= f"API请求出错: {result['error'].get('message', str(result['error']))}",
                        metadata={}
                    ))
        yield chat_messages
        return chat_messages
    
    # 用于累积显示的消息列表
    
    
    # 处理工具调用（循环直到没有工具调用）
    while True:
        if "choices" in result and len(result["choices"]) > 0:
            message_obj = result["choices"][0]["message"]
            
            if "tool_calls" in message_obj and message_obj["tool_calls"]:
                # 有工具调用 - 先显示用户消息
                #chat_messages.append(ChatMessage(role="user", content=message))
                #yield chat_messages
                if "content" in message_obj and message_obj["content"]:
                    parse_result = parse_ai_response(message_obj["content"])
                    think,chat = parse_result[0],parse_result[1]
                    if think != "":
                        chat_messages.append(ChatMessage(
                            role="assistant",
                            content=think,
                            metadata={"title": f"🤔 思考内容："}
                        ))
                    yield chat_messages
                    chat_messages.append(ChatMessage(
                        role="assistant",
                        content= chat,
                        metadata={}
                    ))
                    yield chat_messages
                # 处理每个工具调用
                for tool_call in message_obj["tool_calls"]:
                    
                    tool_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]
                    
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    
                    # 显示工具调用中
                    args_str = json.dumps(arguments, ensure_ascii=False, indent=2)
                    chat_messages.append(ChatMessage(
                        role="assistant",
                        content=f"📝 调用参数:\n```\n{truncate(args_str)}\n```",
                        metadata={"title": f"🔧 正在调用: {tool_name}"}
                    ))
                    yield chat_messages
                    
                    # 执行工具
                    tool_result = call_tool(tool_name, arguments)
                    
                    # 显示工具返回结果
                    chat_messages.append(ChatMessage(
                        role="assistant",
                        content=f"📥 返回结果:\n```\n{truncate(tool_result)}\n```",
                        metadata={"title": f"🔧 工具返回结果："}
                    ))
                    yield chat_messages
                    
                    # 添加工具结果到 api_messages（保持完整记录）
                    api_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })
                    api_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_result
                    })
                
                # 继续请求获取最终回复
                url2 = f"{BASE_URL}/chat/completions"
                data2 = {
                    "model": MODEL,
                    "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + api_messages,
                    "tools": TOOLS,
                    "temperature": TEMPERATURE
                }
                response2 = requests.post(url2, headers=headers, json=data2)
                result = response2.json()
                
                # 调试：打印 API 返回
                '''print("=" * 50)
                print(f"API 返回 (工具调用后): {json.dumps(result, ensure_ascii=False)[:2000]}")
                print("=" * 50)
                '''
                if "error" in result:
                    return f"API Error: {result['error'].get('message', str(result['error']))}"
                
                continue
        
        break
    
    # 返回最终回复（只有 assistant 消息）
    if "choices" in result and len(result["choices"]) > 0:
        assistant_message = result["choices"][0]["message"]
        api_messages.append(assistant_message)  # 保存到完整记录
        ai_content = assistant_message.get("content", "")
        
        # 保存到日志
        save_log(message, ai_content)
        #print(f"API消息列表：{api_messages}")
        parse_result = parse_ai_response(ai_content)
        think,chat = parse_result[0],parse_result[1]
        if think != "":
            chat_messages.append(ChatMessage(
                role="assistant",
                content=think,
                metadata={"title": f"🤔 思考内容："}
            ))
        yield chat_messages
        chat_messages.append(ChatMessage(
            role="assistant",
            content= chat,
            metadata={}
        ))
        yield chat_messages
        # 只返回 AI 回复（用于显示）
        # chat_messages.append(ChatMessage(role="assistant", content=ai_content))
        
        # 调试：打印返回给 Gradio 的消息
        '''
        print("=" * 50)
        print(f"返回给 Gradio 的 chat_messages: {[str(m) for m in chat_messages]}")
        print("=" * 50)'''
        yield chat_messages
    else:
        return f"Error: {result}"


# ========== 启动 Gradio ==========

print("=" * 50)
print("Web UI 启动中...")
print(f"访问地址: http://localhost:{SERVER_PORT}")
print("=" * 50)

# 初始化记忆系统
init_memory()
init_session()
print("记忆系统初始化完成")

# 总结并清空对话的函数
def do_summarize():
    """总结对话"""
    # 1. 读取最新对话
    latest_log = ""
    latest_path = get_latest_log_path()
    if os.path.exists(latest_path):
        with open(latest_path, "r", encoding="utf-8") as f:
            latest_log = f.read()
    
    # 2. 读取短期记忆
    short_memory = read_short_memory()
    
    # 3. 总结
    if latest_log.strip() or short_memory.strip():
        new_summary = summarize_short_memory(latest_log, short_memory)
        write_short_memory(new_summary)
        # 清空 latest.txt
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write("")
        global api_messages
        api_messages = []
        global RESET_AND_SUMMERY
        RESET_AND_SUMMERY = True
        return "✅ 已将历史记录压缩总结到短期记忆以释放上下文"
    else:
        return "没有需要总结的内容"

# 使用 Blocks + ChatInterface 组合
if ALLOW_DANGEROUS_OPERATION == True:
    dangerous_operation_display_init = "✅ 允许危险操作"
else:
    dangerous_operation_display_init = "❌ 不允许危险操作"
with gr.Blocks(title="LegnaChat Web UI") as demo:
    gr.Markdown("# LegnaChat Web UI")
    gr.Markdown("基于 LLM 的智能对话助手")
    gr.Markdown("   ")
    gr.Markdown("**注意，刷新此页面不会重置上下文。上下文保存在程序内部**")
    gr.Markdown("**程序会自动记录log，当你重启程序的时候，程序会根据log和以前的记忆自动更新短期记忆**")
    gr.Markdown("**你也可以点击```📝 总结上下文到短期记忆```主动执行该操作**")
    
    with gr.Row():
        chat_interface = gr.ChatInterface(
            fn=chat_fn,
            chatbot=gr.Chatbot(height=500),
            textbox=gr.Textbox(placeholder="输入您的问题...", label="消息"),
            flagging_mode="manual",
        )
    gr.Markdown("点击下面按钮总结记忆，将把历史对话总结进短期记忆，以保证上下文长度")
    gr.Markdown("该功能在每次程序重启的时候也会执行")
    with gr.Row():
        summarize_btn = gr.Button("📝 总结上下文到短期记忆", variant="secondary")
    status_output = gr.Textbox(label="总结状况", interactive=False)
    gr.Markdown("点击下面按钮允许/拒绝AI助手进行危险操作")
    gr.Markdown("危险操作包括**向运行目录之外的目录写入文件**和**执行控制台指令**。这些权限默认不允许。")
    with gr.Row():
        allow_btn = gr.Button("✅ 允许危险操作")
        deny_btn = gr.Button("❌ 不允许危险操作")
    
    status_output2 = gr.Textbox(label="状态", interactive=False, value=dangerous_operation_display_init)
    
    # 绑定总结按钮
    summarize_btn.click(do_summarize, outputs=status_output)
    # 绑定权限按钮
    def set_allow_true():
        change_allow_dangerous_operation(True)
        return "✅ 允许危险操作"
    
    def set_allow_false():
        change_allow_dangerous_operation(False)
        return "❌ 不允许危险操作"
    
    allow_btn.click(set_allow_true, outputs=status_output2)
    deny_btn.click(set_allow_false, outputs=status_output2)

demo.launch(server_port=SERVER_PORT, server_name="0.0.0.0",inbrowser=OPEN_BROWSER)
