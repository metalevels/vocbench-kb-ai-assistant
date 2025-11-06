# Scraper Management System Guide

## Overview

The VocBench scraper now includes a **full-featured management system** with:

✅ **Start/Stop/Pause/Resume controls**
✅ **Incremental crawling** (only fetch new content)
✅ **Queue-based architecture** with state persistence
✅ **Progress monitoring** with real-time status
✅ **Web-based console** for visual management
✅ **Session management** with resume capability
✅ **Automatic checkpointing** and recovery
✅ **Failed thread retry** mechanism

## Quick Start

### 1. Start the API Server

```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Access the Web Console

Open your browser and navigate to:

```
http://localhost:8080/console
```

You'll see a beautiful, interactive dashboard where you can:
- Start/stop/pause/resume scraping
- Monitor progress in real-time
- View statistics (threads scraped, messages, failures)
- Retry failed threads
- Configure scraping parameters

## Architecture

### Components

```
┌─────────────────────────────────────────────────────┐
│           ScraperManager (Orchestrator)              │
├─────────────────────────────────────────────────────┤
│  - Queue Management                                  │
│  - Worker Thread Pool                                │
│  - State Persistence                                 │
│  - Checkpoint Management                             │
└─────────────────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
   ┌────▼────┐            ┌───────▼──────┐
   │  State  │            │  URL Queue   │
   │ Manager │            │              │
   └─────────┘            └──────────────┘
        │                         │
        │                         ▼
        │                 ┌──────────────┐
        │                 │   Workers    │
        │                 │ (Threading)  │
        │                 └──────────────┘
        │                         │
        ▼                         ▼
┌──────────────┐          ┌──────────────┐
│ Checkpoint   │          │   Scraper    │
│   Files      │          │  (executor)  │
└──────────────┘          └──────────────┘
```

### Key Features

#### 1. State Persistence

All scraping state is saved to `./data/scraper_state/{session_id}.json`:

```json
{
  "session_id": "abc-123",
  "status": "running",
  "started_at": "2024-01-20T10:00:00",
  "total_threads_discovered": 100,
  "threads_scraped": 45,
  "threads_failed": 2,
  "messages_scraped": 234,
  "scraped_thread_ids": ["thread_1", "thread_2", ...],
  "pending_thread_urls": ["url3", "url4", ...],
  "last_scraped_date": "2024-01-15T14:30:00",
  "is_incremental": true
}
```

#### 2. Incremental Crawling

When enabled, the scraper:
- Tracks the most recent message date
- Only fetches threads created/updated after this date
- Skips already-scraped thread IDs
- Significantly reduces redundant scraping

#### 3. Queue-Based Architecture

- Thread URLs are queued for processing
- Worker threads pull from queue
- Failures don't block the queue
- Can pause/resume without losing state

#### 4. Automatic Checkpointing

- State saved every N threads (configurable, default: 10)
- Can resume from last checkpoint after crash
- Manual checkpoint creation supported

## API Endpoints

### Start Scraping

```bash
curl -X POST "http://localhost:8080/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{
    "max_threads": 50,
    "max_pages": 5,
    "incremental": true,
    "auto_process": false
  }'
```

**Response:**
```json
{
  "session_id": "abc-def-123",
  "status": "running",
  "message": "Scraping started with session ID: abc-def-123"
}
```

### Get Status

```bash
curl "http://localhost:8080/scraper/status"
```

**Response:**
```json
{
  "session_id": "abc-def-123",
  "status": "running",
  "started_at": "2024-01-20T10:00:00",
  "progress": {
    "percentage": 45.5,
    "threads_scraped": 45,
    "threads_failed": 2,
    "total_threads": 100,
    "messages_scraped": 234,
    "pending": 53
  },
  "is_incremental": true,
  "last_error": null,
  "errors_count": 2
}
```

### Pause Scraping

```bash
curl -X POST "http://localhost:8080/scraper/pause"
```

### Resume Scraping

```bash
curl -X POST "http://localhost:8080/scraper/resume"
```

### Stop Scraping

```bash
curl -X POST "http://localhost:8080/scraper/stop"
```

### Retry Failed Threads

```bash
curl -X POST "http://localhost:8080/scraper/retry-failed"
```

### List All Sessions

```bash
curl "http://localhost:8080/scraper/sessions"
```

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "abc-123",
      "status": "completed",
      "started_at": "2024-01-20T10:00:00",
      "threads_scraped": 100,
      "total_threads": 100,
      "is_incremental": false
    },
    {
      "session_id": "def-456",
      "status": "paused",
      "started_at": "2024-01-21T14:30:00",
      "threads_scraped": 45,
      "total_threads": 150,
      "is_incremental": true
    }
  ],
  "total": 2
}
```

### Resume Specific Session

```bash
curl -X POST "http://localhost:8080/scraper/sessions/abc-123/resume"
```

### Delete Session

```bash
curl -X DELETE "http://localhost:8080/scraper/sessions/abc-123"
```

## Programmatic Usage

### Python API

```python
from src.scraper.google_groups_scraper import GoogleGroupsScraper
from src.scraper.manager import ScraperManager
from src.scraper.state import StateManager

# Initialize
scraper = GoogleGroupsScraper(
    group_url="https://groups.google.com/g/vocbench-user",
    output_dir="./data/raw"
)
state_manager = StateManager()
manager = ScraperManager(scraper, state_manager)

# Start scraping
session_id = manager.start_scraping(
    max_threads=100,
    incremental=True
)

print(f"Started session: {session_id}")

# Monitor progress
while manager.current_state.status == "running":
    status = manager.get_status()
    print(f"Progress: {status['progress']['percentage']}%")
    time.sleep(5)

# Pause if needed
manager.pause_scraping()

# Resume
manager.resume_scraping()

# Stop
manager.stop_scraping()
```

### With Callbacks

```python
def on_thread_scraped(thread):
    """Called when a thread is successfully scraped"""
    print(f"Scraped: {thread.subject} ({thread.message_count} messages)")

def on_progress_update(state):
    """Called periodically with state updates"""
    print(f"Progress: {state.threads_scraped}/{state.total_threads_discovered}")

manager.on_thread_scraped = on_thread_scraped
manager.on_progress_update = on_progress_update

manager.start_scraping()
```

## Incremental Scraping Workflow

### First Run (Full Scrape)

```bash
# Start with incremental mode disabled
curl -X POST "http://localhost:8080/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{"incremental": false}'
```

This will:
1. Scrape ALL threads from the Google Group
2. Save all thread IDs to state
3. Track the latest message date

### Subsequent Runs (Incremental)

```bash
# Start with incremental mode enabled
curl -X POST "http://localhost:8080/scraper/start" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true}'
```

This will:
1. Load previous scraping state
2. Skip already-scraped thread IDs
3. Only fetch threads newer than `last_scraped_date`
4. Much faster and more efficient!

### Scheduled Incremental Updates

Set up a cron job for daily incremental scraping:

```bash
# crontab entry
0 2 * * * curl -X POST http://localhost:8080/scraper/start -H "Content-Type: application/json" -d '{"incremental": true}'
```

## Error Handling & Recovery

### Automatic Recovery

If the scraper crashes or is interrupted:

1. **State is Preserved**: Last checkpoint is saved
2. **Resume from Checkpoint**: Load the session and continue
3. **No Data Loss**: Already-scraped threads are tracked

```python
# Resume after crash
manager = ScraperManager(scraper, state_manager)
crashed_session = state_manager.get_active_session()
if crashed_session:
    manager.start_scraping(session_id=crashed_session)
```

### Failed Threads

Failed threads are tracked separately:

```python
# View failed threads
state = manager.current_state
print(f"Failed threads: {len(state.failed_thread_ids)}")

# Retry all failed threads
manager.retry_failed_threads()
```

### Manual Checkpoints

Create named checkpoints for important milestones:

```python
# Create checkpoint
state_manager.create_checkpoint(manager.current_state, "before_risky_operation")

# Restore if needed
restored_state = state_manager.restore_checkpoint(session_id, "before_risky_operation")
```

## Web Console Features

The web console at `/console` provides:

### Real-time Monitoring

- **Progress Bar**: Visual representation of scraping progress
- **Live Statistics**: Threads scraped, messages, failures
- **Status Badge**: Current state (running/paused/stopped/completed)
- **Auto-refresh**: Updates every 2 seconds

### Interactive Controls

- **Start Button**: Opens configuration modal
  - Max threads (optional)
  - Max pages (optional)
  - Incremental mode checkbox
  - Auto-process checkbox
- **Pause Button**: Pause current scraping
- **Resume Button**: Resume paused scraping
- **Stop Button**: Gracefully stop scraping
- **Retry Failed Button**: Re-queue failed threads
- **Refresh Button**: Manual status refresh

### Console Log

- Timestamped log entries
- Success/error notifications
- Auto-scrolling
- Color-coded messages

## Performance & Scalability

### Current Performance

- **Rate Limiting**: 1 request/second (configurable)
- **Checkpointing**: Every 10 threads
- **Worker Threads**: 1 (configurable for future)
- **Memory Usage**: ~100MB for 1000 threads

### Scaling Considerations

For large-scale scraping (>10,000 threads):

1. **Increase Workers**: Modify `max_workers` parameter
2. **Batch Processing**: Process in smaller sessions
3. **Distributed Scraping**: Multiple instances with session management
4. **Rate Limit Adjustment**: Balance speed vs. politeness

## Best Practices

### 1. Use Incremental Mode

Always enable incremental mode for regular updates:

```python
manager.start_scraping(incremental=True)
```

### 2. Monitor for Failures

Check failed threads regularly:

```python
if manager.current_state.threads_failed > 10:
    logger.warning(f"High failure rate: {manager.current_state.threads_failed}")
    manager.retry_failed_threads()
```

### 3. Checkpoint Before Risky Operations

```python
state_manager.create_checkpoint(manager.current_state, "pre_modification")
```

### 4. Clean Up Old Sessions

```python
# Delete sessions older than 30 days
for session_id in state_manager.list_sessions():
    state = state_manager.load_state(session_id)
    if (datetime.now() - state.started_at).days > 30:
        state_manager.delete_state(session_id)
```

### 5. Respect Rate Limits

Don't set rate_limit_delay too low:

```python
scraper = GoogleGroupsScraper(
    group_url="...",
    rate_limit_delay=1.0  # 1 second minimum
)
```

## Troubleshooting

### Scraper Won't Start

**Problem**: "Scraper is already running" error

**Solution**:
```python
manager.stop_scraping()
# Or check and stop active session
active_session = state_manager.get_active_session()
if active_session:
    state = state_manager.load_state(active_session)
    state.status = "stopped"
    state_manager.save_state(state)
```

### High Failure Rate

**Problem**: Many threads failing

**Solution**:
1. Check network connectivity
2. Verify Google Groups URL is accessible
3. Check rate limiting (may be blocked)
4. Review error logs

### State File Corruption

**Problem**: Cannot load session state

**Solution**:
```python
# Delete corrupted state
state_manager.delete_state(session_id)

# Start fresh
manager.start_scraping()
```

### Memory Issues

**Problem**: High memory usage

**Solution**:
- Process in smaller batches
- Reduce checkpoint interval
- Clear old sessions
- Enable auto-processing to persist data

## Advanced Features

### Auto-Processing Integration

Enable automatic data processing as threads are scraped:

```python
def on_thread_scraped(thread):
    # Process immediately
    processor = DataProcessor()
    # ... process and index thread
    pass

manager.on_thread_scraped = on_thread_scraped
manager.start_scraping(auto_process=True)
```

### Custom State Filters

Filter threads based on custom criteria:

```python
def filter_threads(thread_urls):
    # Only scrape threads from last month
    return [url for url in thread_urls if is_recent(url)]

# Apply custom filter
original_discover = manager._discover_threads
def custom_discover():
    original_discover()
    manager.current_state.pending_thread_urls = filter_threads(
        manager.current_state.pending_thread_urls
    )

manager._discover_threads = custom_discover
```

## Summary

The scraper management system provides enterprise-grade crawling capabilities with:

✅ Full control (start/stop/pause/resume)
✅ State persistence and recovery
✅ Incremental scraping for efficiency
✅ Web-based monitoring console
✅ Queue-based architecture
✅ Automatic checkpointing
✅ Failed thread retry
✅ Session management

Perfect for production deployments requiring reliable, resumable, and monitorable web scraping!
