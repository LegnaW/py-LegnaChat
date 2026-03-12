import os
import requests

# 获取插件目录路径
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
APIKEY_FILE = os.path.join(PLUGIN_DIR, "apikey.txt")


def _get_apikey():
    """从 apikey.txt 读取 API Key"""
    if not os.path.exists(APIKEY_FILE):
        return None
    
    with open(APIKEY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def tool_main(arg):
    """
    Tavily 搜索插件
    
    Args:
        arg: dict，包含 query（搜索关键词）和可选的 search_depth
        
    Returns:
        str: 搜索结果
    """
    query = arg.get("query", "")
    search_depth = arg.get("search_depth", "basic")
    
    if not query:
        return "Error: 请提供搜索关键词 (query)"
    
    # 读取 API Key
    api_key = _get_apikey()
    if not api_key:
        return "Error: 未找到 apikey.txt 文件，请先在本插件目录下的apikey.txt创建并填入 Tavily API Key"
    
    # 发送搜索请求
    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "query": query,
        "search_depth": search_depth
    }
    
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code != 200:
            return f"Error: API 返回错误 {response.status_code}: {response.text}"
        
        result = response.json()
        
        # 解析结果
        if "results" in result and result["results"]:
            answers = []
            for i, r in enumerate(result["results"][:5], 1):  # 最多返回 5 条
                title = r.get("title", "无标题")
                url = r.get("url", "")
                content = r.get("content", "")
                
                # 截取内容前 200 字
                if len(content) > 200:
                    content = content[:200] + "..."
                
                answers.append(f"{i}. {title}\n   {content}\n   来源: {url}")
            
            return "\n\n".join(answers)
        elif "answer" in result:
            # advanced 模式可能有 answer 字段
            return result["answer"]
        else:
            return f"未找到相关结果: {result}"
            
    except requests.exceptions.Timeout:
        return "Error: 请求超时，请稍后重试"
    except requests.exceptions.RequestException as e:
        return f"Error: 网络请求失败 - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"
