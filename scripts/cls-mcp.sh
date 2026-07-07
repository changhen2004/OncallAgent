#!/usr/bin/env bash
# 腾讯云日志服务 CLS MCP Server 管理脚本
# 用法: ./scripts/cls-mcp.sh {start|stop|restart|status|logs}
set -euo pipefail

# 切到项目根目录（脚本在 scripts/ 下）
cd "$(dirname "$0")/.."

ENV_FILE=".env"
LOG_FILE="log/cls-mcp-server.log"
PID_FILE="log/cls-mcp-server.pid"

# 从 .env 读取端口，默认 3100
PORT="$(grep -E '^PORT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || true)"
PORT="${PORT:-3100}"

# 返回监听该端口的进程 PID（若有）
listening_pid() {
  lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true
}

start() {
  local pid
  pid="$(listening_pid)"
  if [ -n "$pid" ]; then
    echo "已在运行 (port $PORT, pid $pid)"
    return 0
  fi
  if [ ! -f "$ENV_FILE" ]; then
    echo "错误: 缺少 $ENV_FILE（需含 TENCENTCLOUD_SECRET_ID/KEY、TRANSPORT=sse、PORT）" >&2
    exit 1
  fi
  mkdir -p log
  # 加载 .env 后以独立进程方式启动，脱离当前 shell
  set -a; . "./$ENV_FILE"; set +a
  nohup npx -y cls-mcp-server@latest > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"
  echo "启动中... (pid $(cat "$PID_FILE"), port $PORT)"
  sleep 2
  status
}

stop() {
  local pid
  pid="$(listening_pid)"
  if [ -z "$pid" ]; then
    echo "未在运行 (port $PORT)"
    rm -f "$PID_FILE"
    return 0
  fi
  echo "停止 pid $pid ..."
  kill "$pid" 2>/dev/null || true
  sleep 1
  # 仍存活则强制
  pid="$(listening_pid)"
  [ -n "$pid" ] && kill -9 "$pid" 2>/dev/null || true
  rm -f "$PID_FILE"
  echo "已停止"
}

status() {
  local pid
  pid="$(listening_pid)"
  if [ -n "$pid" ]; then
    echo "运行中: port $PORT, pid $pid, SSE=http://localhost:$PORT/sse"
  else
    echo "未运行 (port $PORT)"
  fi
}

logs() {
  tail -f "$LOG_FILE"
}

case "${1:-}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  logs)    logs ;;
  *) echo "用法: $0 {start|stop|restart|status|logs}" >&2; exit 1 ;;
esac
