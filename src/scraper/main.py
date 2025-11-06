"""
Main entry point for the scraper module
"""
import argparse
import logging
from pathlib import Path

from config.settings import settings
from src.scraper.google_groups_scraper import GoogleGroupsScraper


def setup_logging():
    """Configure logging"""
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'scraper.log'),
            logging.StreamHandler()
        ]
    )


def main():
    """Main scraper execution"""
    parser = argparse.ArgumentParser(description='Scrape VocBench Google Group')
    parser.add_argument(
        '--max-threads',
        type=int,
        default=None,
        help='Maximum number of threads to scrape'
    )
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Maximum number of thread list pages to fetch'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='scraped_data.json',
        help='Output filename'
    )

    args = parser.parse_args()
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting VocBench scraper")

    # Initialize scraper
    scraper = GoogleGroupsScraper(
        group_url=settings.google_group_url,
        user_agent=settings.scraper_user_agent,
        output_dir='./data/raw'
    )

    # Scrape threads
    threads = scraper.scrape_all(
        max_threads=args.max_threads,
        max_pages=args.max_pages
    )

    # Save results
    scraper.save_threads(threads, filename=args.output)

    # Print statistics
    logger.info("=" * 60)
    logger.info(f"Scraping Statistics:")
    logger.info(f"  Total threads processed: {scraper.stats.total_threads}")
    logger.info(f"  Successful threads: {scraper.stats.successful_threads}")
    logger.info(f"  Failed threads: {scraper.stats.failed_threads}")
    logger.info(f"  Total messages: {scraper.stats.total_messages}")
    logger.info(f"  Duration: {scraper.stats.duration_seconds:.2f} seconds")
    if scraper.stats.errors:
        logger.info(f"  Errors encountered: {len(scraper.stats.errors)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
