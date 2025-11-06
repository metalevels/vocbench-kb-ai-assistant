#!/usr/bin/env python
"""
Search Quality Validator

Tests search quality with various query types and provides metrics
"""
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.retrieval.vector_store import VectorStore
from src.retrieval.retriever import SemanticRetriever
from src.processor.embeddings import EmbeddingGenerator


class SearchQualityValidator:
    """Validate search quality with test queries"""

    def __init__(self, collection_name: str = "phase9_test", persist_dir: str = "./data/phase9_test/chromadb_test"):
        """Initialize validator"""
        self.vector_store = VectorStore(
            collection_name=collection_name,
            persist_directory=persist_dir
        )
        self.embedding_generator = EmbeddingGenerator()
        self.retriever = SemanticRetriever(
            self.vector_store,
            self.embedding_generator
        )

    def validate_queries(self, queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a set of queries with expected results

        Args:
            queries: List of dicts with 'query' and optionally 'expected_keywords'

        Returns:
            Validation results
        """
        results = []

        for query_info in queries:
            query = query_info['query']
            expected_keywords = query_info.get('expected_keywords', [])

            # Search
            search_results = self.retriever.retrieve(query, top_k=5)

            # Calculate metrics
            has_results = len(search_results) > 0
            top_score = search_results[0]['score'] if has_results else 0

            # Check if expected keywords are in top results
            keyword_matches = 0
            if expected_keywords and search_results:
                top_content = ' '.join([r['content'].lower() for r in search_results[:3]])
                keyword_matches = sum(1 for kw in expected_keywords if kw.lower() in top_content)

            results.append({
                'query': query,
                'num_results': len(search_results),
                'top_score': top_score,
                'expected_keywords': expected_keywords,
                'keyword_matches': keyword_matches,
                'keyword_match_rate': keyword_matches / len(expected_keywords) if expected_keywords else None,
                'top_result': search_results[0]['content'][:200] if has_results else None
            })

        # Calculate overall metrics
        avg_score = sum(r['top_score'] for r in results) / len(results) if results else 0
        avg_results = sum(r['num_results'] for r in results) / len(results) if results else 0

        queries_with_keywords = [r for r in results if r['expected_keywords']]
        avg_keyword_match = sum(r['keyword_match_rate'] for r in queries_with_keywords) / len(queries_with_keywords) if queries_with_keywords else 0

        return {
            'query_results': results,
            'summary': {
                'total_queries': len(results),
                'avg_top_score': avg_score,
                'avg_results_per_query': avg_results,
                'avg_keyword_match_rate': avg_keyword_match,
                'queries_with_zero_results': sum(1 for r in results if r['num_results'] == 0)
            }
        }


# Test queries for VocBench
VOCBENCH_TEST_QUERIES = [
    {
        'query': 'How to configure SPARQL endpoint?',
        'expected_keywords': ['sparql', 'endpoint', 'configure', 'settings']
    },
    {
        'query': 'Error importing SKOS vocabulary',
        'expected_keywords': ['skos', 'import', 'error', 'vocabulary']
    },
    {
        'query': 'Collaborative editing best practices',
        'expected_keywords': ['collaborative', 'editing', 'workflow', 'validation']
    },
    {
        'query': 'Export RDF data from VocBench',
        'expected_keywords': ['export', 'rdf', 'format', 'turtle']
    },
    {
        'query': 'User permissions and roles',
        'expected_keywords': ['user', 'permissions', 'roles', 'access']
    },
    {
        'query': 'Creating concept schemes in SKOS',
        'expected_keywords': ['concept', 'scheme', 'skos', 'create']
    },
    {
        'query': 'VocBench installation requirements',
        'expected_keywords': ['install', 'requirements', 'system', 'dependencies']
    },
    {
        'query': 'Custom SPARQL queries in VocBench',
        'expected_keywords': ['sparql', 'query', 'custom', 'hierarchies']
    }
]


def main():
    """Main entry point"""
    print("=" * 80)
    print("Search Quality Validation")
    print("=" * 80)

    validator = SearchQualityValidator()

    # Run validation
    results = validator.validate_queries(VOCBENCH_TEST_QUERIES)

    # Print results
    print(f"\n📊 SEARCH QUALITY METRICS:")
    print(f"  Total queries: {results['summary']['total_queries']}")
    print(f"  Avg top score: {results['summary']['avg_top_score']:.3f}")
    print(f"  Avg results/query: {results['summary']['avg_results_per_query']:.1f}")
    print(f"  Avg keyword match: {results['summary']['avg_keyword_match_rate']:.1%}")
    print(f"  Zero results: {results['summary']['queries_with_zero_results']}")

    print(f"\n📋 QUERY DETAILS:")
    for i, r in enumerate(results['query_results'], 1):
        print(f"\n  {i}. '{r['query']}'")
        print(f"     Results: {r['num_results']}, Score: {r['top_score']:.3f}")
        if r['keyword_match_rate'] is not None:
            print(f"     Keyword match: {r['keyword_match_rate']:.1%} ({r['keyword_matches']}/{len(r['expected_keywords'])})")
        if r['top_result']:
            print(f"     Top result: {r['top_result']}...")

    # Quality assessment
    print(f"\n✅ QUALITY ASSESSMENT:")
    if results['summary']['avg_top_score'] > 0.7:
        print("  🟢 Excellent - High relevance scores")
    elif results['summary']['avg_top_score'] > 0.5:
        print("  🟡 Good - Moderate relevance scores")
    else:
        print("  🔴 Poor - Low relevance scores")

    if results['summary']['avg_keyword_match_rate'] > 0.7:
        print("  🟢 Excellent - Keywords found in results")
    elif results['summary']['avg_keyword_match_rate'] > 0.5:
        print("  🟡 Good - Some keywords found")
    else:
        print("  🔴 Poor - Few keywords found")

    print("=" * 80)


if __name__ == "__main__":
    main()
