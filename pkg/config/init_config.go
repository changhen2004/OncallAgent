package config

import (
	"fmt"
	"strings"

	"github.com/spf13/viper"
)

// Config 应用配置结构
type Config struct {
	Server     ServerConfig     `mapstructure:"server"`
	Embedder   EmbedderConfig   `mapstructure:"embedder"`
	Qdrant     QdrantConfig     `mapstructure:"qdrant"`
	OpenAI     OpenAIConfig     `mapstructure:"openai"`
	Prometheus PrometheusConfig `mapstructure:"prometheus"`
	CLSMcp     CLSMcpConfig     `mapstructure:"cls_mcp"`
}

// ServerConfig 服务器配置
type ServerConfig struct {
	Host string `mapstructure:"host"`
	Port int    `mapstructure:"port"`
}

// EmbedderConfig 嵌入模型配置
type EmbedderConfig struct {
	Host      string `mapstructure:"host"`
	Port      int    `mapstructure:"port"`
	Model     string `mapstructure:"model"`
	Dimension int    `mapstructure:"dimension"`
}

// QdrantConfig Qdrant 向量数据库配置
type QdrantConfig struct {
	Host       string `mapstructure:"host"`
	Port       int    `mapstructure:"port"`
	Collection string `mapstructure:"collection"`
}

// OpenAIConfig OpenAI API 配置
type OpenAIConfig struct {
	APIKey  string `mapstructure:"api_key"`
	Model   string `mapstructure:"model"`
	APIBase string `mapstructure:"api_base"`
}

// PrometheusConfig Prometheus 配置
type PrometheusConfig struct {
	URL string `mapstructure:"url"`
}

// CLSMcpConfig 腾讯云日志服务 CLS MCP 配置
type CLSMcpConfig struct {
	// BaseURL CLS MCP Server 的 SSE 接入地址，例如 http://localhost:3100/sse
	BaseURL string `mapstructure:"base_url"`
	// Enabled 是否启用 CLS 日志 MCP 工具
	Enabled bool `mapstructure:"enabled"`
}

// InitConfig 从配置文件初始化配置
// configFile: 配置文件路径，如 "config/config.json"
func InitConfig(configFile string) (*Config, error) {
	v := viper.New()

	// 设置配置文件
	v.SetConfigFile(configFile)

	// 设置配置文件类型
	if strings.HasSuffix(configFile, ".json") {
		v.SetConfigType("json")
	} else if strings.HasSuffix(configFile, ".yaml") || strings.HasSuffix(configFile, ".yml") {
		v.SetConfigType("yaml")
	}

	// 读取配置文件
	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	// 设置默认值
	setDefaults(v)

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("failed to unmarshal config: %w", err)
	}

	return &cfg, nil
}

// setDefaults 设置默认值
func setDefaults(v *viper.Viper) {
	// Server 默认值
	v.SetDefault("server.host", "localhost")
	v.SetDefault("server.port", 8819)

	// Embedder 默认值
	v.SetDefault("embedder.host", "localhost")
	v.SetDefault("embedder.port", 11434)
	v.SetDefault("embedder.model", "nomic-embed-text")
	v.SetDefault("embedder.dimension", 384)

	// Qdrant 默认值
	v.SetDefault("qdrant.host", "localhost")
	v.SetDefault("qdrant.port", 6334)
	v.SetDefault("qdrant.collection", "oncallagent")

	// OpenAI 默认值
	v.SetDefault("openai.api_key", "")
	v.SetDefault("openai.model", "minimax/minimax-m2.1")
	v.SetDefault("openai.api_base", "https://api.qnaigc.com/v1")

	// Prometheus 默认值
	v.SetDefault("prometheus.url", "http://localhost:9090")

	// CLS MCP 默认值
	v.SetDefault("cls_mcp.base_url", "http://localhost:3100/sse")
	v.SetDefault("cls_mcp.enabled", true)
}

// GetServerAddr 获取服务器完整地址
func (c *Config) GetServerAddr() string {
	return fmt.Sprintf("%s:%d", c.Server.Host, c.Server.Port)
}

// GetEmbedderAddr 获取嵌入模型服务地址
func (c *Config) GetEmbedderAddr() string {
	return fmt.Sprintf("http://%s:%d", c.Embedder.Host, c.Embedder.Port)
}

// GetQdrantAddr 获取 Qdrant 服务地址
func (c *Config) GetQdrantAddr() string {
	return fmt.Sprintf("%s:%d", c.Qdrant.Host, c.Qdrant.Port)
}

// GetPrometheusURL 获取 Prometheus 地址
func (c *Config) GetPrometheusURL() string {
	if c.Prometheus.URL == "" {
		return "http://localhost:9090"
	}
	return c.Prometheus.URL
}

// GetCLSMcpURL 获取 CLS 日志 MCP Server 的 SSE 接入地址
func (c *Config) GetCLSMcpURL() string {
	if c.CLSMcp.BaseURL == "" {
		return "http://localhost:3100/sse"
	}
	return c.CLSMcp.BaseURL
}
