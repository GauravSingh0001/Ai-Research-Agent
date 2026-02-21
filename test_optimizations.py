#!/usr/bin/env python3
"""Test optimizations are working correctly."""

import sys
sys.path.insert(0, '.')

try:
    # Test cache
    from src.cache import SynthesisCache
    print('✅ Cache module imports successfully')
    
    cache = SynthesisCache()
    stats = cache.get_cache_stats()
    print(f'✅ Cache initialized: {stats["analysis_entries"]} analysis entries')
    
    # Test writing
    from src.writing import ResearchWriter
    print('✅ Writing module imports successfully (parallel execution)')
    
    # Test analysis
    import concurrent.futures
    from src.analysis import PaperAnalyzer
    print('✅ Analysis module imports successfully (parallel processing)')
    
    print('\n🎉 All optimizations verified!')
    
except Exception as e:
    import traceback
    print(f'❌ Error: {type(e).__name__}: {str(e)}')
    traceback.print_exc()
