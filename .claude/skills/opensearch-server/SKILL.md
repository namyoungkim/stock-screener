---
name: opensearch-server
description: Start and manage OpenSearch server with Docker. Use when starting OpenSearch locally, setting up development environment, or managing OpenSearch containers.
allowed-tools: Bash
---

# OpenSearch Server

Docker-based OpenSearch server with Korean (Nori) analyzer.

## Quick Start (docker-compose)

```bash
# 1. Copy .env and set PROJECT_NAME
cp .claude/skills/opensearch-server/assets/.env.example .env

# 2. Start server
docker compose -f .claude/skills/opensearch-server/assets/docker-compose.yml up -d

# 3. Verify
curl -s http://localhost:9200
```

## Quick Start (docker run)

```bash
docker run -d --name opensearch \
  -p 9200:9200 -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "plugins.security.disabled=true" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=YourStr0ngP@ss!" \
  -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" \
  -v opensearch-data:/usr/share/opensearch/data \
  a1rtisan/opensearch-nori:latest
```

**Note**: Password requires 8+ chars with upper/lower/digit/special.

## Stop Server

```bash
# docker-compose
docker compose -f .claude/skills/opensearch-server/assets/docker-compose.yml down

# docker run
docker stop opensearch && docker rm opensearch

# Remove data
docker volume rm opensearch-data
```

## Check Status

```bash
# Health check
curl -s http://localhost:9200

# Check Nori plugin
curl -s http://localhost:9200/_cat/plugins | grep nori
```

## Test Korean Analyzer

```bash
curl -X POST "http://localhost:9200/_analyze" \
  -H "Content-Type: application/json" \
  -d '{"tokenizer": "nori_tokenizer", "text": "한국어 형태소 분석"}'
```

## Ports

| Port | Service |
|------|---------|
| 9200 | REST API |
| 9600 | Performance Analyzer |

## Docker Images

| Image | Description |
|-------|-------------|
| `a1rtisan/opensearch-nori:latest` | OpenSearch 3.0 + Nori plugin |
| `opensearchproject/opensearch:latest` | Official (no Nori) |

## Troubleshooting

```bash
# Check container logs
docker logs ${PROJECT_NAME:-opensearch}-dev

# Check process using port 9200
lsof -i :9200

# Reset data (remove volumes)
docker compose -f .claude/skills/opensearch-server/assets/docker-compose.yml down -v
```

## Links

- Docker Hub: https://hub.docker.com/r/a1rtisan/opensearch-nori
- GitHub: https://github.com/namyoungkim/opensearch-client
