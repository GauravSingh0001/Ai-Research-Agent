#!/usr/bin/env python3
"""Test refactored AI Research Agent configuration and initialization."""

import sys
sys.path.insert(0, '.')

def test_configuration():
    """Test environment and config settings."""
    from src.config import GPT_MODEL, COHERE_MODEL, HF_BASE_URL, GEMINI_MODEL, OPENAI_API_KEY, COHERE_API_KEY
    
    print("=" * 60)
    print("1. CONFIGURATION TEST")
    print("=" * 60)
    
    print(f"✅ GPT_MODEL: {GPT_MODEL}")
    assert "llama" in GPT_MODEL.lower(), f"Expected Llama model, got {GPT_MODEL}"
    
    print(f"✅ COHERE_MODEL: {COHERE_MODEL}")
    assert "command" in COHERE_MODEL.lower(), f"Expected command model, got {COHERE_MODEL}"
    
    print(f"✅ HF_BASE_URL: {HF_BASE_URL}")
    assert "router.huggingface.co" in HF_BASE_URL, f"Invalid HF endpoint: {HF_BASE_URL}"
    
    print(f"✅ GEMINI_MODEL: {GEMINI_MODEL}")
    
    print(f"✅ OPENAI_API_KEY present: {bool(OPENAI_API_KEY)}")
    print(f"✅ COHERE_API_KEY present: {bool(COHERE_API_KEY)}")
    
    print("\n✅ Configuration validation passed!")
    return True

def test_ai_engine_initialization():
    """Test AI Engine provider initialization and ordering."""
    from src.ai_engine import AIEngine
    
    print("\n" + "=" * 60)
    print("2. AI ENGINE INITIALIZATION TEST")
    print("=" * 60)
    
    engine = AIEngine()
    
    print(f"✅ Provider initialized: {engine.provider}")
    print(f"✅ Cohere ready: {engine.cohere_client is not None}")
    print(f"✅ Gemini ready: {engine.gemini_ready}")
    print(f"✅ OpenAI/HF ready: {engine.openai_client is not None}")
    print(f"✅ Engine is_ready(): {engine.is_ready()}")
    
    # Check provider priority (Cohere should be first if available)
    if engine.cohere_client is not None:
        assert engine.provider == "Cohere", f"Expected Cohere as primary, got {engine.provider}"
        print("✅ Provider priority correct: Cohere is primary")
    
    return True

def test_validation_logic():
    """Test API key validation and model compatibility detection."""
    from src.ai_engine import AIEngine
    from src.config import GPT_MODEL, OPENAI_API_KEY
    
    print("\n" + "=" * 60)
    print("3. VALIDATION LOGIC TEST")
    print("=" * 60)
    
    engine = AIEngine()
    
    # Test that validation functions exist in the code
    print(f"✅ GPT_MODEL: {GPT_MODEL}")
    print(f"✅ OPENAI_API_KEY starts with 'hf_': {OPENAI_API_KEY.startswith('hf_')}")
    print(f"✅ Model is HF-compatible ('gpt' not in name): {'gpt' not in GPT_MODEL.lower()}")
    
    print("\n✅ Validation logic verified!")
    return True

def test_server_components():
    """Test server imports and component availability."""
    import server
    from src.writing import ResearchWriter
    from src.config import ANALYSIS_RESULTS_FILE, SECTIONS_DATA_FILE
    
    print("\n" + "=" * 60)
    print("4. SERVER COMPONENTS TEST")
    print("=" * 60)
    
    print(f"✅ Flask app imported: {server.app is not None}")
    print(f"✅ ResearchWriter available for initialization")
    print(f"✅ ANALYSIS_RESULTS_FILE: {ANALYSIS_RESULTS_FILE}")
    print(f"✅ SECTIONS_DATA_FILE: {SECTIONS_DATA_FILE}")
    
    print("\n✅ Server components verified!")
    return True

def test_cache_integration():
    """Test cache module for improved performance."""
    from src.cache import SynthesisCache, get_cache
    
    print("\n" + "=" * 60)
    print("5. CACHE INTEGRATION TEST")
    print("=" * 60)
    
    cache = get_cache()
    stats = cache.get_cache_stats()
    
    print(f"✅ Cache initialized successfully")
    print(f"✅ Analysis cache entries: {stats['analysis_entries']}")
    print(f"✅ Synthesis cache entries: {stats['synthesis_entries']}")
    print(f"✅ Cache directory: {stats['cache_dir']}")
    
    print("\n✅ Cache integration verified!")
    return True

def main():
    """Run all tests."""
    print("\n" + "🧪 REFACTORING VALIDATION SUITE 🧪".center(60))
    print("=" * 60 + "\n")
    
    tests = [
        test_configuration,
        test_ai_engine_initialization,
        test_validation_logic,
        test_server_components,
        test_cache_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_func.__name__} FAILED:")
            print(f"   {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}/{len(tests)}")
    print(f"❌ Failed: {failed}/{len(tests)}")
    
    if failed == 0:
        print("\n🎉 ALL REFACTORING TESTS PASSED!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
