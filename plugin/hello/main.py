def tool_main(arg):
    """Hello 插件主函数"""
    name = arg.get("name", "World")
    return f"Hello, {name}!"
