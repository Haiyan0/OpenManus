# web_run.py — OpenManus Web 聊天界面启动入口
"""启动 OpenManus Web 聊天服务器。

Usage:
    python web_run.py
    # 访问 http://localhost:8080
"""

import uvicorn


def main():
    uvicorn.run(
        "app.web.server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
