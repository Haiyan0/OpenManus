# web_run.py — OpenManus Web 聊天界面启动入口
"""启动 OpenManus Web 聊天服务器。

Usage:
    python web_run.py
    # 访问 http://localhost:8080
"""

import entry

entry.apply_env(entry.parse_env())  # 必须先于 uvicorn.run：app.web.server 在 run 时加载

import uvicorn  # noqa: E402


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
