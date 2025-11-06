# Developer Guide – VocBench Knowledge Chat

## Tech Stack
- **Language:** Python 3.10+
- **LLM Client:** Anthropic SDK
- **Scraper:** Based on open-source projects (see below)
- **Storage:** JSON + Vector Database (Weaviate, Milvus, or pgvector)
- **Infrastructure:** Docker, systemd cron for scheduled refresh

## Data Pipeline
1. **Scraping**
   - Crawl all threads and posts from the VocBench Google Group.
   - Normalize to structured JSON: {thread_id, message_id, subject, author, date, body}.
   - Use OSS crawlers (prioritized below) to bootstrap:
     1. `henryk/gggd` – actively maintained, exports to mbox.
     2. `google-group-crawler` – Python-based, handles pagination and HTML parsing.
     3. `ggarchive` – Node.js variant, supports incremental fetch.

2. **Processing**
   - Clean text, remove HTML noise, signatures, duplicates.
   - Split long posts into semantic chunks (~500–800 tokens).
   - Generate embeddings (Anthropic or local transformer model).

3. **Indexing**
   - Store embeddings and metadata in a vector database.
   - Maintain a simple metadata collection for full-text fallback search.

4. **Retrieval + Conversation**
   - User query → retrieve relevant posts → send to Anthropic SDK as context.
   - Use Anthropic’s `answer_with_results()` or equivalent retrieval call pattern.
   - Return concise, grounded responses with reference to discussion threads.

5. **Scheduling**
   - Weekly data refresh (cron).
   - Incremental scraping: fetch only new threads/posts since last run.

## Security & Compliance
- Only process public content.
- Respect robots.txt and Google TOS for scraping.
- Sanitize personal data before indexing.
- Keep Anthropic API keys in secure vault or environment variable manager.

## Deployment
- Containerize the system for local and cloud environments.
- Use `docker-compose` for modular deployment (scraper, processor, retriever, LLM client).
- Provide REST or gRPC interface for user queries.

## Deliverables
- Fully automated ingestion and RAG backend.
- Command-line tool for local testing.
- Optional simple chat frontend (CLI or web).

