import subprocess
import threading
import time
import os
import json
import platform
import signal
from datetime import datetime
import locale

class TaskManager:
    """任务管理器"""
    
    def __init__(self):
        self.tasks = {}  # pid -> task_info
        self.lock = threading.Lock()
        self.output_buffer_size = 10000  # 输出缓冲区大小
        self.max_return_output = 5000    # 返回的最大输出长度
        self.encoding = self._get_system_encoding()  # 系统编码
        
    def _get_system_encoding(self):
        """获取系统默认编码"""
        return locale.getpreferredencoding(False)
        
    def _check_permission(self):
        return os.environ.get("LEGNA_ALLOW_DANGEROUS_OPERATION") == "true"
    
    def _get_log_dir(self):
        """获取日志目录"""
        log_dir = "./ai-programs/task_logs"
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    
    
    def _try_decode(self, data):
        """尝试多种编码解码字节数据"""
        if isinstance(data, str):
            return data  # 已经是字符串
        
        encodings = [self.encoding, 'gbk', 'gb2312', 'cp936']
        for enc in encodings:
            try:
                return data.decode(enc)
            except (UnicodeDecodeError, AttributeError):
                continue
        # 所有编码都失败，用 errors='replace'
        return data.decode(self.encoding, errors='replace')
    
    def _read_output_thread(self, pid, process, log_file):
        """后台线程：读取进程输出"""
        try:
            with open(log_file, "a", encoding="utf-8") as log:
                while True:
                    # 读取一行输出（字节模式）
                    line_bytes = process.stdout.readline()
                    if not line_bytes and process.poll() is not None:
                        break  # 进程结束且无输出
                    
                    if line_bytes:
                        # 解码（自动检测编码）
                        line = self._try_decode(line_bytes)
                        
                        # 写入日志文件
                        log.write(line)
                        log.flush()
                        
                        # 更新内存缓冲区
                        with self.lock:
                            if pid in self.tasks:
                                task_info = self.tasks[pid]
                                task_info["buffer"] += line
                                
                                # 限制缓冲区大小
                                if len(task_info["buffer"]) > self.output_buffer_size:
                                    task_info["buffer"] = task_info["buffer"][-self.output_buffer_size:]
        except Exception as e:
            print(f"输出读取线程错误: {e}")
    
    def _format_result(self, pid, task_info, is_finished=False):
        """格式化返回结果"""
        output = task_info.get("buffer", "")
        
        # 限制返回的输出长度
        if len(output) > self.max_return_output:
            output = output[-self.max_return_output:]
        
        result = {
            "pid": pid,
            "status": "finished" if is_finished else "running",
            "output": output,
            "log_file": task_info.get("log_file", ""),
            "created_at": task_info.get("created_at", ""),
            "message": "任务已完成" if is_finished else "任务正在运行中"
        }
        
        # 添加查看建议
        if not is_finished:
            result["view_suggestions"] = self._get_view_suggestions(task_info.get("log_file", ""))
            result["ai_controls"] = {
                "check": json.dumps({"mode": "check", "pid": pid}),
                "send": json.dumps({"mode": "send", "pid": pid, "command": "指令内容"}),
                "kill": json.dumps({"mode": "kill", "pid": pid})
            }
        
        return json.dumps(result, indent=2, ensure_ascii=False)
    
    def _get_view_suggestions(self, log_path):
        """获取日志查看建议"""
        if os.name == 'nt':  # Windows
            return {
                "powershell": f"powershell -Command \"Get-Content '{log_path}' -Wait\"",
                "cmd": f"cmd /c \"type '{log_path}' & pause\"",
                "note": "推荐使用PowerShell查看实时日志"
            }
        else:  # Linux/Mac
            return {
                "tail": f"tail -f '{log_path}'",
                "less": f"less +F '{log_path}'",
                "cat": f"cat '{log_path}'",
                "note": "推荐使用 'tail -f' 查看实时日志"
            }
    
    def _open_terminal(self, log_file, pid):
        """弹出终端窗口显示日志（跨平台）"""
        try:
            system = platform.system().lower()
            
            if system == "windows":
                # Windows: 使用 PowerShell 实时显示，带窗口标题
                title = f"Log Output - PID {pid}"
                subprocess.Popen(
                    f'start "{title}" powershell -Command "Get-Content -Path \\"{log_file}\\" -Wait -Tail 50"',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            elif system == "darwin":
                # macOS: 使用 Terminal
                subprocess.Popen(
                    ["open", "-a", "Terminal", f"tail -f {log_file}"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Linux: 尝试 gnome-terminal 或 xterm，带窗口标题
                try:
                    subprocess.Popen(
                        ["gnome-terminal", "-t", f"Log Output - PID {pid}", "--", "tail", "-f", log_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except FileNotFoundError:
                    try:
                        subprocess.Popen(
                            ["xterm", "-T", f"Log Output - PID {pid}", "-e", f"tail -f {log_file}"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except FileNotFoundError:
                        # 无桌面环境，静默失败
                        pass
        except Exception:
            # 任何错误都静默处理，不影响主任务
            pass
    
    def create_task(self, command):
        """创建新任务"""
        # 1. 权限检查
        if not self._check_permission():
            return json.dumps({
                "error": "未授权执行危险操作",
                "message": "请确保用户已经给你授权了执行危险操作"
            }, ensure_ascii=False)
        
        # 2. 使用 PID 作为标识
        pid = None
        
        # 3. 创建日志文件
        log_dir = self._get_log_dir()
        
        # 写入启动信息（先不指定 PID）
        temp_log = os.path.join(log_dir, "temp.log")
        
        try:
            # 4. 启动进程
            # 根据系统设置进程组，以便 kill 时能杀死所有子进程
            # 注意：不使用 text/encoding 参数，改用二进制模式自行解码
            if platform.system() == "Windows":
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    bufsize=1
                )
            else:
                # Unix: 创建新进程组
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.PIPE,
                    bufsize=1,
                    start_new_session=True
                )
            
            pid = process.pid
            
            # 3. 创建日志文件（使用 PID 命名）
            log_file = os.path.join(log_dir, f"{pid}.log")
            
            # 写入启动信息
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(f"=== 任务启动 ===\n")
                f.write(f"PID: {pid}\n")
                f.write(f"命令: {command}\n")
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 40 + "\n\n")
            
            # 5. 初始化任务信息
            task_info = {
                "process": process,
                "pid": pid,
                "log_file": log_file,
                "buffer": "",
                "created_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "status": "running"
            }
            
            # 6. 启动输出读取线程
            thread = threading.Thread(
                target=self._read_output_thread,
                args=(pid, process, log_file),
                daemon=True
            )
            thread.start()
            
            # 7. ⭐ 立即弹出终端窗口显示日志
            self._open_terminal(log_file, pid)
            
            # 8. 等待30秒或进程结束
            start_time = time.time()
            while time.time() - start_time < 30:  # 30秒超时
                if process.poll() is not None:  # 进程已结束
                    # 等待线程读取最后输出
                    time.sleep(0.5)
                    
                    # 读取最终输出
                    with self.lock:
                        task_info["status"] = "finished"
                        # 从日志文件读取完整输出
                        try:
                            with open(log_file, "r", encoding="utf-8") as f:
                                full_output = f.read()
                                # 跳过开头的元信息
                                lines = full_output.split('\n')
                                content_start = 0
                                for i, line in enumerate(lines):
                                    if "=" * 40 in line:
                                        content_start = i + 1
                                        break
                                task_info["buffer"] = '\n'.join(lines[content_start:])
                        except:
                            pass
                    
                    return self._format_result(pid, task_info, is_finished=True)
                time.sleep(0.1)
            
            # 9. 30秒后仍在运行，保存任务
            with self.lock:
                self.tasks[pid] = task_info
            
            # 10. 返回运行中结果
            return self._format_result(pid, task_info, is_finished=False)
            
        except Exception as e:
            return json.dumps({
                "error": f"创建任务失败: {str(e)}"
            }, ensure_ascii=False)
    
    def check_task(self, pid):
        """查询任务状态"""
        pid = int(pid) if isinstance(pid, str) else pid
        
        with self.lock:
            if pid not in self.tasks:
                return json.dumps({
                    "error": f"任务不存在: PID {pid}",
                    "available_pids": list(self.tasks.keys())
                }, ensure_ascii=False)
            
            task_info = self.tasks[pid]
            
            # 检查进程状态
            process = task_info.get("process")
            if process and process.poll() is not None:
                task_info["status"] = "finished"
                # 从日志文件读取完整输出
                try:
                    with open(task_info["log_file"], "r", encoding="utf-8") as f:
                        full_output = f.read()
                        lines = full_output.split('\n')
                        content_start = 0
                        for i, line in enumerate(lines):
                            if "=" * 40 in line:
                                content_start = i + 1
                                break
                        task_info["buffer"] = '\n'.join(lines[content_start:])
                except:
                    pass
        
        return self._format_result(pid, task_info, is_finished=(task_info.get("status") == "finished"))
    
    def send_command(self, pid, command):
        """向任务发送指令"""
        pid = int(pid) if isinstance(pid, str) else pid
        
        with self.lock:
            if pid not in self.tasks:
                return json.dumps({
                    "error": f"任务不存在: PID {pid}"
                }, ensure_ascii=False)
            
            task_info = self.tasks[pid]
            process = task_info.get("process")
            
            if not process or process.poll() is not None:
                return json.dumps({
                    "error": f"任务已结束: PID {pid}",
                    "status": task_info.get("status", "unknown")
                }, ensure_ascii=False)
        
        try:
            # 发送指令（添加换行符）- 使用 UTF-8 编码
            process.stdin.write((command + "\n").encode(self.encoding))
            process.stdin.flush()
            
            # 记录发送的指令到日志
            with open(task_info["log_file"], "a", encoding="utf-8") as f:
                f.write(f"\n[AI指令] {command}\n")
            
            return json.dumps({
                "success": True,
                "pid": pid,
                "command": command,
                "message": "指令已发送"
            }, ensure_ascii=False)
            
        except Exception as e:
            return json.dumps({
                "error": f"发送指令失败: {str(e)}",
                "pid": pid
            }, ensure_ascii=False)
    
    def kill_task(self, pid):
        """强制终止任务（杀死整个进程树）"""
        pid = int(pid) if isinstance(pid, str) else pid
        
        with self.lock:
            if pid not in self.tasks:
                return json.dumps({
                    "error": f"任务不存在: PID {pid}",
                    "available_pids": list(self.tasks.keys())
                }, ensure_ascii=False)
            
            task_info = self.tasks[pid]
            process = task_info.get("process")
            
            # 检查进程是否已结束
            if process and process.poll() is None:
                # 进程仍在运行，尝试终止
                try:
                    if platform.system() == "Windows":
                        # Windows: 使用 taskkill 杀死进程树
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    else:
                        # Unix: 杀死整个进程组
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        
                        time.sleep(0.3)
                        
                        # 如果还没退出，强制杀死
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    
                    task_info["status"] = "killed"
                    
                    # 记录到日志
                    try:
                        with open(task_info["log_file"], "a", encoding="utf-8") as f:
                            f.write(f"\n=== 任务已被终止 (PID: {pid}) ===\n")
                    except:
                        pass
                    
                    return json.dumps({
                        "success": True,
                        "pid": pid,
                        "status": "killed",
                        "message": "任务已被强制终止（包含子进程）"
                    }, ensure_ascii=False)
                except Exception as e:
                    return json.dumps({
                        "error": f"终止任务失败: {str(e)}",
                        "pid": pid
                    }, ensure_ascii=False)
            else:
                # 进程已结束
                return json.dumps({
                    "error": f"任务已结束，无法终止",
                    "pid": pid,
                    "status": task_info.get("status", "unknown")
                }, ensure_ascii=False)
    
    def list_tasks(self):
        """列出所有任务"""
        with self.lock:
            task_list = []
            for pid, task_info in self.tasks.items():
                process = task_info.get("process")
                status = "running"
                if process and process.poll() is not None:
                    status = "finished"
                
                task_list.append({
                    "pid": pid,
                    "status": status,
                    "created_at": task_info.get("created_at", ""),
                    "log_file": task_info.get("log_file", ""),
                    "buffer_length": len(task_info.get("buffer", ""))
                })
        
        return json.dumps({
            "tasks": task_list,
            "count": len(task_list)
        }, indent=2, ensure_ascii=False)

# 全局任务管理器实例
task_manager = TaskManager()

def tool_main(arg):
    """
    插件主函数
    
    Args:
        arg: dict类型，包含调用参数
        
    Returns:
        str: JSON格式的执行结果
    """
    try:
        mode = arg.get("mode", "").lower()
        
        if mode == "create":
            command = arg.get("command", "")
            if not command:
                return json.dumps({"error": "缺少命令参数"}, ensure_ascii=False)
            return task_manager.create_task(command)
            
        elif mode == "check":
            pid = arg.get("pid", "")
            if not pid:
                return json.dumps({"error": "缺少PID"}, ensure_ascii=False)
            return task_manager.check_task(pid)
            
        elif mode == "send":
            pid = arg.get("pid", "")
            command = arg.get("command", "")
            if not pid or not command:
                return json.dumps({"error": "缺少PID或指令"}, ensure_ascii=False)
            return task_manager.send_command(pid, command)
            
        elif mode == "list":
            return task_manager.list_tasks()
            
        elif mode == "kill":
            pid = arg.get("pid", "")
            if not pid:
                return json.dumps({"error": "缺少PID"}, ensure_ascii=False)
            return task_manager.kill_task(pid)
            
        else:
            return json.dumps({
                "error": "无效的模式",
                "valid_modes": ["create", "check", "send", "list", "kill"],
                "usage": {
                    "create": '{"mode": "create", "command": "要执行的命令"}',
                    "check": '{"mode": "check", "pid": 12345}',
                    "send": '{"mode": "send", "pid": 12345, "command": "要发送的指令"}',
                    "list": '{"mode": "list"}',
                    "kill": '{"mode": "kill", "pid": 12345}'
                }
            }, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({
            "error": f"插件执行错误: {str(e)}"
        }, ensure_ascii=False)
