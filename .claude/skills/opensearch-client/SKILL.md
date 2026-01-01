---
name: opensearch-client
description: OpenSearch Python client library for hybrid search. Use when writing OpenSearch queries, creating indexes, or implementing text/vector/hybrid search with Korean support.
---

# OpenSearch Client

Python client library for OpenSearch with hybrid search support.

## Installation

```bash
uv add opensearch-client           # Basic
uv add opensearch-client[openai]   # OpenAI embeddings
uv add opensearch-client[local]    # FastEmbed (local)
uv add opensearch-client[all]      # All features
```

## Quick Start

```python
from opensearch_client import OpenSearchClient

client = OpenSearchClient(host="localhost", port=9200, use_ssl=False)
client.ping()
```

## Text Search

```python
from opensearch_client import OpenSearchClient, TextQueryBuilder, IndexManager

client = OpenSearchClient(host="localhost", port=9200, use_ssl=False)

body = IndexManager.create_text_index_body(text_field="content", use_korean_analyzer=True)
client.create_index("docs", body)

client.bulk_index("docs", [{"content": "OpenSearch is a search engine."}])
client.refresh("docs")

query = TextQueryBuilder.multi_match(query="search", fields=["content"])
results = client.search("docs", TextQueryBuilder.build_search_body(query))
```

## Hybrid Search

```python
from opensearch_client import OpenSearchClient, IndexManager
from opensearch_client.semantic_search.embeddings import OpenAIEmbedding

client = OpenSearchClient(host="localhost", port=9200, use_ssl=False)
embedder = OpenAIEmbedding()

body = IndexManager.create_hybrid_index_body(
    vector_dimension=embedder.dimension,
    vector_field="embedding",
    use_korean_analyzer=True
)
client.create_index("hybrid", body)
client.setup_hybrid_pipeline("pipeline", text_weight=0.3, vector_weight=0.7)

text = "OpenSearch supports hybrid search"
client.index_document("hybrid", {"content": text, "embedding": embedder.embed(text)})
client.refresh("hybrid")

results = client.hybrid_search(
    index_name="hybrid", query="search", query_vector=embedder.embed("search"),
    pipeline="pipeline", text_fields=["content"], vector_field="embedding", k=10
)
```

## VectorStore

```python
from opensearch_client import OpenSearchClient, VectorStore
from opensearch_client.semantic_search.embeddings import FastEmbedEmbedding

client = OpenSearchClient(host="localhost", port=9200, use_ssl=False)
store = VectorStore("store", FastEmbedEmbedding(), client)
store.add(["Doc 1", "Doc 2"])
results = store.search("query", k=5)
for r in results:
    print(f"{r.text} (score: {r.score:.4f})")
```

## API Reference

### IndexManager

| Method | Description |
|--------|-------------|
| `create_text_index_body(text_field, use_korean_analyzer)` | Text search index |
| `create_vector_index_body(vector_field, vector_dimension, space_type)` | Vector search index |
| `create_hybrid_index_body(vector_dimension, vector_field, use_korean_analyzer)` | Hybrid search index |

### VectorStore

| Method | Returns |
|--------|---------|
| `add(texts, metadata?, ids?)` | `list[str]` (doc IDs) |
| `add_one(text, metadata?, doc_id?)` | `str` (doc ID) |
| `search(query, k, filter?)` | `list[SearchResult]` |
| `delete(ids)` | None |
| `clear()` | None |
| `count()` | `int` |

### SearchResult (dataclass)

| Attribute | Type |
|-----------|------|
| `text` | str |
| `score` | float |
| `metadata` | dict |
| `id` | str |

## Links

- PyPI: https://pypi.org/project/opensearch-client/
- GitHub: https://github.com/namyoungkim/opensearch-client
