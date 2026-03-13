import requests
from bs4 import BeautifulSoup

# 伪装浏览器请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def tool_main(arg):
    """
    网页内容阅读器插件
    
    使用 bs4 解析网页内容
    
    Args:
        arg: dict，包含：
            - url: 网页 URL（必填）
            - selector: CSS 选择器（可选，默认提取正文）
            - max_length: 最大字符数（可选，默认 2000）
    
    Returns:
        str: 网页内容
    """
    url = arg.get("url", "")
    selector = arg.get("selector", "")
    max_length = arg.get("max_length", 2000)
    
    if not url:
        return "Error: 请提供网页 URL (url)"
    
    # 简单校验
    if not url.startswith(("http://", "https://")):
        return "Error: 请提供完整的 URL（以 http:// 或 https:// 开头）"
    
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")
        
        if selector:
            elements = soup.select(selector)
            if not elements:
                return f"Error: 未找到匹配 CSS 选择器 '{selector}' 的内容"
            content = "\n".join([e.get_text(strip=True) for e in elements])
        else:
            # 默认提取 body 文本
            body = soup.find("body")
            content = body.get_text(separator="\n", strip=True) if body else soup.get_text()
        
        # 截断
        if len(content) > max_length:
            content = content[:max_length] + f"\n... (共 {len(content)} 字符)"
        
        return content
        
    except requests.exceptions.Timeout:
        return "Error: 请求超时"
    except Exception as e:
        return f"Error: {str(e)}"
