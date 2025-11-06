# Project Overview – VocBench Knowledge Chat

## Objective
Enable a conversational AI (powered by Anthropic SDK) to answer questions and engage with knowledge derived from the VocBench Google Group discussions.

## Functional Goals
1. Extract and index all public discussions from the VocBench user group.
2. Provide a semantic retrieval pipeline over this content.
3. Integrate the retrieval with a conversational interface via Anthropic SDK.
4. Support scheduled data refresh and incremental updates.

## System Architecture
- **Data Source:** Public archive of the VocBench Google Group (`https://groups.google.com/g/vocbench-user`).
- **Ingestion Layer:** Scraping of group threads → parsing → normalization → JSON output.
- **Processing Layer:** Text cleaning, chunking, embeddings generation, vector database storage.
- **Retrieval Layer:** Semantic retrieval and ranking from vector DB.
- **Conversation Layer:** Anthropic SDK–based assistant with retrieval augmentation.
- **Monitoring:** Scheduled scraping updates and error logging.

## Design Choices
- Use **Anthropic SDK** directly for RAG-style prompts and context injection.
- Keep infrastructure modular: scraping, indexing, and retrieval as separate services.
- Ensure reproducibility and maintainability (Dockerized pipelines, config files).

## Success Criteria
- Fully automated extraction and refresh pipeline.
- Fast retrieval (<1s per query).
- Accurate answers grounded in source material.
- Scalable to other Google Groups or similar forums.
