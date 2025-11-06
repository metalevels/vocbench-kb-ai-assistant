#!/usr/bin/env python
"""
Phase 9: Real Data Integration Test Script

This script performs end-to-end testing with real VocBench data:
1. Scrapes real threads from VocBench Google Group
2. Processes the data
3. Indexes into ChromaDB
4. Tests search quality
5. Validates chat (if API key available)
6. Generates performance report
"""
import sys
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper.google_groups_scraper import GoogleGroupsScraper
from src.processor.processor import DataProcessor
from src.retrieval.vector_store import VectorStore, VectorStoreManager
from src.retrieval.retriever import SemanticRetriever
from src.processor.embeddings import EmbeddingGenerator
from config.settings import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./logs/phase9_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Phase9Tester:
    """End-to-end testing with real VocBench data"""

    def __init__(self, max_threads: int = 10):
        """
        Initialize tester

        Args:
            max_threads: Maximum number of threads to scrape for testing
        """
        self.max_threads = max_threads
        self.results = {
            'scraping': {},
            'processing': {},
            'indexing': {},
            'search': {},
            'performance': {},
            'errors': []
        }

        # Output directory
        self.output_dir = Path('./data/phase9_test')
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Phase 9 Tester initialized (max_threads={max_threads})")

    def step1_scrape_real_data(self) -> bool:
        """
        Step 1: Scrape real threads from VocBench Google Group

        Returns:
            Success status
        """
        logger.info("=" * 80)
        logger.info("STEP 1: Scraping Real VocBench Data")
        logger.info("=" * 80)

        try:
            start_time = time.time()

            # Initialize scraper
            scraper = GoogleGroupsScraper(
                group_url=settings.google_group_url,
                user_agent=settings.scraper_user_agent,
                output_dir=str(self.output_dir),
                rate_limit_delay=2.0  # Be polite!
            )

            # Scrape threads
            logger.info(f"Scraping up to {self.max_threads} threads from VocBench...")
            threads = scraper.scrape_all(max_threads=self.max_threads, max_pages=1)

            duration = time.time() - start_time

            # Save results
            scraper.save_threads(threads, filename="real_scraped_data.json")

            # Record metrics
            self.results['scraping'] = {
                'total_threads': len(threads),
                'total_messages': sum(t.message_count for t in threads),
                'successful': scraper.stats.successful_threads,
                'failed': scraper.stats.failed_threads,
                'duration_seconds': duration,
                'threads_per_minute': (len(threads) / duration) * 60 if duration > 0 else 0
            }

            logger.info(f"✓ Scraped {len(threads)} threads with {self.results['scraping']['total_messages']} messages")
            logger.info(f"  Duration: {duration:.2f}s ({self.results['scraping']['threads_per_minute']:.2f} threads/min)")

            if len(threads) == 0:
                logger.error("✗ No threads scraped! Check your internet connection and Google Group URL")
                return False

            return True

        except Exception as e:
            logger.error(f"✗ Scraping failed: {e}", exc_info=True)
            self.results['errors'].append(f"Scraping: {str(e)}")
            return False

    def step2_process_data(self) -> bool:
        """
        Step 2: Process scraped data through pipeline

        Returns:
            Success status
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Processing Scraped Data")
        logger.info("=" * 80)

        try:
            start_time = time.time()

            # Initialize processor
            processor = DataProcessor(output_dir=str(self.output_dir))

            # Process data
            input_file = self.output_dir / "real_scraped_data.json"
            logger.info(f"Processing data from: {input_file}")

            processed_data = processor.process_scraped_data(
                input_file=str(input_file),
                combine_threads=False
            )

            duration = time.time() - start_time

            # Save processed data
            processor.save_processed_data(processed_data, filename="real_processed_data.json")

            # Get statistics
            stats = processor.get_statistics(processed_data)

            self.results['processing'] = {
                'total_chunks': len(processed_data),
                'unique_sources': stats['unique_sources'],
                'avg_chunk_size': stats['avg_chunk_size'],
                'min_chunk_size': stats['min_chunk_size'],
                'max_chunk_size': stats['max_chunk_size'],
                'embedding_dimension': stats['embedding_dimension'],
                'duration_seconds': duration,
                'chunks_per_second': len(processed_data) / duration if duration > 0 else 0
            }

            logger.info(f"✓ Processed into {len(processed_data)} chunks")
            logger.info(f"  Avg chunk size: {stats['avg_chunk_size']:.0f} chars")
            logger.info(f"  Duration: {duration:.2f}s ({self.results['processing']['chunks_per_second']:.2f} chunks/s)")

            if len(processed_data) == 0:
                logger.error("✗ No chunks produced from processing!")
                return False

            return True

        except Exception as e:
            logger.error(f"✗ Processing failed: {e}", exc_info=True)
            self.results['errors'].append(f"Processing: {str(e)}")
            return False

    def step3_index_data(self) -> bool:
        """
        Step 3: Index processed data into ChromaDB

        Returns:
            Success status
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Indexing into Vector Database")
        logger.info("=" * 80)

        try:
            start_time = time.time()

            # Initialize vector store
            vector_store = VectorStore(
                collection_name="phase9_test",
                persist_directory=str(self.output_dir / "chromadb_test")
            )

            # Clear existing data
            vector_store.clear()
            logger.info("Cleared existing test collection")

            # Load processed data
            processor = DataProcessor(output_dir=str(self.output_dir))
            processed_data = processor.load_processed_data("real_processed_data.json")

            # Index data
            manager = VectorStoreManager(vector_store)
            indexed_count = manager.index_processed_data(processed_data, batch_size=50)

            duration = time.time() - start_time

            self.results['indexing'] = {
                'documents_indexed': indexed_count,
                'total_in_collection': vector_store.count(),
                'duration_seconds': duration,
                'docs_per_second': indexed_count / duration if duration > 0 else 0
            }

            logger.info(f"✓ Indexed {indexed_count} documents")
            logger.info(f"  Duration: {duration:.2f}s ({self.results['indexing']['docs_per_second']:.2f} docs/s)")

            # Store vector store for next steps
            self.vector_store = vector_store

            return True

        except Exception as e:
            logger.error(f"✗ Indexing failed: {e}", exc_info=True)
            self.results['errors'].append(f"Indexing: {str(e)}")
            return False

    def step4_test_search(self) -> bool:
        """
        Step 4: Test semantic search with real queries

        Returns:
            Success status
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 4: Testing Semantic Search")
        logger.info("=" * 80)

        try:
            # Initialize retriever
            embedding_generator = EmbeddingGenerator()
            retriever = SemanticRetriever(
                vector_store=self.vector_store,
                embedding_generator=embedding_generator,
                default_top_k=5
            )

            # Test queries (VocBench-specific)
            test_queries = [
                "How do I configure a SPARQL endpoint?",
                "Error importing SKOS vocabulary",
                "Best practices for collaborative editing in VocBench",
                "Custom SPARQL queries",
                "How to export RDF data?",
                "VocBench installation requirements",
                "Creating new concept schemes",
                "User permissions and roles"
            ]

            search_results = []
            total_search_time = 0

            logger.info(f"Testing {len(test_queries)} queries...")

            for i, query in enumerate(test_queries, 1):
                start_time = time.time()
                results = retriever.retrieve(query, top_k=5)
                search_time = time.time() - start_time

                total_search_time += search_time

                search_results.append({
                    'query': query,
                    'num_results': len(results),
                    'top_score': results[0]['score'] if results else 0,
                    'search_time_ms': search_time * 1000
                })

                logger.info(f"\n  Query {i}: '{query}'")
                logger.info(f"  Results: {len(results)}, Top score: {search_results[-1]['top_score']:.3f}, Time: {search_time*1000:.1f}ms")

                if results:
                    logger.info(f"  Top result: {results[0]['content'][:100]}...")

            avg_search_time = (total_search_time / len(test_queries)) * 1000

            self.results['search'] = {
                'total_queries': len(test_queries),
                'avg_search_time_ms': avg_search_time,
                'avg_results_per_query': sum(r['num_results'] for r in search_results) / len(search_results),
                'avg_top_score': sum(r['top_score'] for r in search_results) / len(search_results),
                'queries': search_results
            }

            logger.info(f"\n✓ Search testing complete")
            logger.info(f"  Avg search time: {avg_search_time:.1f}ms")
            logger.info(f"  Avg top score: {self.results['search']['avg_top_score']:.3f}")

            # Store retriever for chat testing
            self.retriever = retriever

            return True

        except Exception as e:
            logger.error(f"✗ Search testing failed: {e}", exc_info=True)
            self.results['errors'].append(f"Search: {str(e)}")
            return False

    def step5_test_chat(self) -> bool:
        """
        Step 5: Test chat responses (if API key available)

        Returns:
            Success status
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 5: Testing Chat Interface")
        logger.info("=" * 80)

        # Check if API key is available
        if not settings.anthropic_api_key or settings.anthropic_api_key.startswith('test_'):
            logger.warning("⚠ Skipping chat test - No valid Anthropic API key configured")
            logger.info("  Set ANTHROPIC_API_KEY in .env to test chat functionality")
            self.results['chat'] = {'skipped': True, 'reason': 'No API key'}
            return True

        try:
            from src.conversation.chat import VocBenchAssistant

            # Initialize assistant
            assistant = VocBenchAssistant(
                retriever=self.retriever,
                api_key=settings.anthropic_api_key
            )

            # Test queries
            test_queries = [
                "What is VocBench?",
                "How do I configure a SPARQL endpoint in VocBench?"
            ]

            chat_results = []

            for query in test_queries:
                logger.info(f"\n  Testing: '{query}'")

                start_time = time.time()
                result = assistant.chat(query, top_k=3)
                chat_time = time.time() - start_time

                chat_results.append({
                    'query': query,
                    'response_length': len(result['response']),
                    'sources_used': len(result.get('sources', [])),
                    'chat_time_ms': chat_time * 1000,
                    'tokens_used': result.get('usage', {})
                })

                logger.info(f"  Response ({len(result['response'])} chars, {chat_time:.2f}s):")
                logger.info(f"  {result['response'][:200]}...")

            self.results['chat'] = {
                'total_queries': len(test_queries),
                'avg_response_time_ms': sum(r['chat_time_ms'] for r in chat_results) / len(chat_results),
                'avg_response_length': sum(r['response_length'] for r in chat_results) / len(chat_results),
                'queries': chat_results
            }

            logger.info(f"\n✓ Chat testing complete")
            logger.info(f"  Avg response time: {self.results['chat']['avg_response_time_ms']:.1f}ms")

            return True

        except Exception as e:
            logger.error(f"✗ Chat testing failed: {e}", exc_info=True)
            self.results['errors'].append(f"Chat: {str(e)}")
            return False

    def step6_generate_report(self):
        """
        Step 6: Generate comprehensive test report

        Returns:
            Success status
        """
        logger.info("\n" + "=" * 80)
        logger.info("STEP 6: Generating Test Report")
        logger.info("=" * 80)

        # Calculate overall performance
        self.results['performance'] = {
            'end_to_end_time': sum([
                self.results.get('scraping', {}).get('duration_seconds', 0),
                self.results.get('processing', {}).get('duration_seconds', 0),
                self.results.get('indexing', {}).get('duration_seconds', 0)
            ]),
            'success': len(self.results['errors']) == 0
        }

        # Save detailed results
        report_file = self.output_dir / "phase9_test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, default=str)

        logger.info(f"✓ Detailed report saved to: {report_file}")

        # Print summary
        self._print_summary()

        return True

    def _print_summary(self):
        """Print test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 9 TEST SUMMARY")
        logger.info("=" * 80)

        # Scraping
        if 'scraping' in self.results:
            s = self.results['scraping']
            logger.info(f"\n📥 SCRAPING:")
            logger.info(f"  Threads: {s.get('total_threads', 0)}")
            logger.info(f"  Messages: {s.get('total_messages', 0)}")
            logger.info(f"  Speed: {s.get('threads_per_minute', 0):.2f} threads/min")

        # Processing
        if 'processing' in self.results:
            p = self.results['processing']
            logger.info(f"\n⚙️  PROCESSING:")
            logger.info(f"  Chunks: {p.get('total_chunks', 0)}")
            logger.info(f"  Avg chunk size: {p.get('avg_chunk_size', 0):.0f} chars")
            logger.info(f"  Speed: {p.get('chunks_per_second', 0):.2f} chunks/s")

        # Indexing
        if 'indexing' in self.results:
            i = self.results['indexing']
            logger.info(f"\n💾 INDEXING:")
            logger.info(f"  Documents: {i.get('documents_indexed', 0)}")
            logger.info(f"  Speed: {i.get('docs_per_second', 0):.2f} docs/s")

        # Search
        if 'search' in self.results:
            s = self.results['search']
            logger.info(f"\n🔍 SEARCH:")
            logger.info(f"  Queries tested: {s.get('total_queries', 0)}")
            logger.info(f"  Avg time: {s.get('avg_search_time_ms', 0):.1f}ms")
            logger.info(f"  Avg top score: {s.get('avg_top_score', 0):.3f}")

        # Chat
        if 'chat' in self.results and not self.results['chat'].get('skipped'):
            c = self.results['chat']
            logger.info(f"\n💬 CHAT:")
            logger.info(f"  Queries tested: {c.get('total_queries', 0)}")
            logger.info(f"  Avg time: {c.get('avg_response_time_ms', 0):.1f}ms")

        # Overall
        logger.info(f"\n⏱️  OVERALL:")
        logger.info(f"  Total time: {self.results['performance']['end_to_end_time']:.2f}s")
        logger.info(f"  Errors: {len(self.results['errors'])}")

        if self.results['errors']:
            logger.info(f"\n❌ ERRORS:")
            for error in self.results['errors']:
                logger.info(f"  - {error}")

        # Success/Failure
        if self.results['performance']['success']:
            logger.info(f"\n✅ PHASE 9 TEST: SUCCESS! 🎉")
            logger.info(f"   All systems validated with real VocBench data!")
        else:
            logger.info(f"\n⚠️  PHASE 9 TEST: COMPLETED WITH ERRORS")
            logger.info(f"   Review errors above and retry failed steps")

        logger.info("=" * 80)

    def run_all(self):
        """Run all test steps"""
        logger.info("🚀 Starting Phase 9: Real Data Integration Test")
        logger.info(f"   Target: {self.max_threads} threads from VocBench Google Group")

        steps = [
            ("Scrape Real Data", self.step1_scrape_real_data),
            ("Process Data", self.step2_process_data),
            ("Index Data", self.step3_index_data),
            ("Test Search", self.step4_test_search),
            ("Test Chat", self.step5_test_chat),
            ("Generate Report", self.step6_generate_report)
        ]

        for step_name, step_func in steps:
            logger.info(f"\n{'='*80}")
            logger.info(f"Starting: {step_name}")
            logger.info(f"{'='*80}")

            success = step_func()

            if not success and step_name != "Test Chat":  # Chat can be skipped
                logger.error(f"Step '{step_name}' failed. Stopping test.")
                break

        return self.results


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Phase 9: Real Data Integration Test')
    parser.add_argument(
        '--max-threads',
        type=int,
        default=10,
        help='Maximum threads to scrape (default: 10)'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='Quick test with only 3 threads'
    )

    args = parser.parse_args()

    max_threads = 3 if args.quick else args.max_threads

    # Create tester
    tester = Phase9Tester(max_threads=max_threads)

    # Run all tests
    results = tester.run_all()

    # Exit code
    exit_code = 0 if results['performance']['success'] else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
