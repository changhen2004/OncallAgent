package tools

import (
	"context"
	"fmt"

	e_mcp "github.com/cloudwego/eino-ext/components/tool/mcp"
	"github.com/cloudwego/eino/components/tool"
	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
)

// GetLogMcpTool 通过 SSE 连接腾讯云日志服务 CLS MCP Server，
// 完成初始化握手后拉取该 Server 暴露的全部工具，供 agent 直接调用。
//
// baseURL 为 CLS MCP Server 的 SSE 接入地址，例如 http://localhost:3100/sse。
func GetLogMcpTool(ctx context.Context, baseURL string) ([]tool.BaseTool, error) {
	// 1. 创建 SSE 客户端
	cli, err := client.NewSSEMCPClient(baseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to create cls mcp sse client: %w", err)
	}

	if err = cli.Start(ctx); err != nil {
		return nil, fmt.Errorf("failed to start cls mcp client: %w", err)
	}

	// 2. 协商协议，完成初始化握手
	initRequest := mcp.InitializeRequest{}
	initRequest.Params.ProtocolVersion = mcp.LATEST_PROTOCOL_VERSION
	initRequest.Params.ClientInfo = mcp.Implementation{
		Name:    "OnCallAgent",
		Version: "1.0.0",
	}
	if _, err = cli.Initialize(ctx, initRequest); err != nil {
		return nil, fmt.Errorf("failed to initialize cls mcp client: %w", err)
	}

	// 3. 获取 CLS MCP Server 暴露的全部工具
	mcpTools, err := e_mcp.GetTools(ctx, &e_mcp.Config{Cli: cli})
	if err != nil {
		return nil, fmt.Errorf("failed to get cls mcp tools: %w", err)
	}

	return mcpTools, nil
}
