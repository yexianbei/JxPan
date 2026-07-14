#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "==> 检查 Cloudflare 登录状态"
if ! npx wrangler whoami >/dev/null 2>&1; then
  echo "未登录，请先运行: npx wrangler login"
  exit 1
fi

echo "==> 创建 D1 数据库（若已存在会提示）"
D1_OUTPUT=$(npx wrangler d1 create jxpan 2>&1 || true)
echo "$D1_OUTPUT"

DB_ID=$(echo "$D1_OUTPUT" | rg -o 'database_id = "[^"]+"' | head -1 | rg -o '[a-f0-9-]{36}' || true)

if [ -z "$DB_ID" ]; then
  echo "==> 尝试从已有 D1 列表获取 database_id"
  DB_ID=$(npx wrangler d1 list 2>/dev/null | rg 'jxpan' | rg -o '[a-f0-9-]{36}' | head -1 || true)
fi

if [ -z "$DB_ID" ]; then
  echo "无法获取 D1 database_id，请手动在 wrangler.jsonc 中填写"
  exit 1
fi

echo "==> 使用 D1 database_id: $DB_ID"
perl -i -pe "s/\"database_id\": \"REPLACE_AFTER_D1_CREATE\"/\"database_id\": \"$DB_ID\"/" wrangler.jsonc

echo "==> 部署 Worker"
npx wrangler deploy --no-bundle

echo ""
echo "部署完成！Worker 地址类似: https://jxpan.<你的子域>.workers.dev"
echo "蓝奏云解析示例:"
echo "  curl 'https://jxpan.<你的子域>.workers.dev/?url=https://lanzoux.com/xxxxxx&type=json'"
