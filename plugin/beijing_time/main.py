from datetime import datetime, timezone, timedelta


def tool_main(arg):
    """
    获取当前北京时间
    
    Returns:
        str: 当前北京时间，格式为 YYYY-MM-DD HH:MM:SS
    """
    # 北京时间 = UTC + 8 小时
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    
    # 格式化为字符串
    return now.strftime("%Y-%m-%d %H:%M:%S")
