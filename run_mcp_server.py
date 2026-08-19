# coding: utf-8
# A shortcut to launch OpenManus MCP server, where its introduction also solves other import issues.
import entry

entry.apply_env(entry.parse_env())  # 必须先于 app.* import：config 单例在首次 import 时加载


if __name__ == "__main__":
    from app.mcp.server import MCPServer, parse_args

    args = parse_args()

    # Create and run server (maintaining original flow)
    server = MCPServer()
    server.run(transport=args.transport, host=args.host, port=args.port)
