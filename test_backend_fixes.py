"""
Quick verification test for backend fixes.
Tests that the text classifier and AI detector produce consistent, content-aware results.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_text_classifier():
    """Test that the text classifier correctly identifies content type."""
    from backend.detectors.text_classifier import TextClassifier
    
    classifier = TextClassifier()
    
    # Test 1: Known fake-sounding text
    fake_text = "BREAKING: NASA confirms the Earth is flat! Share before they delete this! You won't believe what they don't want you to know!!!"
    result = classifier.classify(fake_text)
    print(f"\n=== Test 1: Fake-sounding text ===")
    print(f"Text: {fake_text[:80]}...")
    print(f"Label: {result.label}, Confidence: {result.confidence}")
    assert result.label in ("fake", "misleading"), f"Expected fake/misleading, got {result.label}"
    
    # Test 2: Neutral factual text
    factual_text = "The Indian Parliament has two houses: Lok Sabha and Rajya Sabha. The Lok Sabha has 543 members."
    result2 = classifier.classify(factual_text)
    print(f"\n=== Test 2: Factual text ===")
    print(f"Text: {factual_text[:80]}...")
    print(f"Label: {result2.label}, Confidence: {result2.confidence}")
    assert result2.label == "real", f"Expected real, got {result2.label}"
    
    # Test 3: Simple factual statement
    simple_fact = "A rainbow has 7 colors. Water boils at 100 degrees Celsius at sea level."
    result3 = classifier.classify(simple_fact)
    print(f"\n=== Test 3: Simple fact ===")
    print(f"Text: {simple_fact[:80]}...")
    print(f"Label: {result3.label}, Confidence: {result3.confidence}")
    assert result3.label == "real", f"Expected real, got {result3.label}"
    
    # Test 4: Consistency check — run same input 3 times
    for i in range(3):
        r = classifier.classify(fake_text)
        print(f"  Run {i+1}: label={r.label}, conf={r.confidence}")
    
    print("\n✅ Text classifier tests passed!")


def test_ai_content_detector():
    """Test that the AI content detector produces consistent, deterministic results."""
    from backend.detectors.ai_content_detector import AIContentDetector
    
    detector = AIContentDetector()
    
    # Test 1: AI-sounding text
    ai_text = """It's important to note that the landscape of artificial intelligence is multifaceted and nuanced. 
    However, it is essential to delve into the comprehensive aspects of this technology. 
    Furthermore, one could argue that the implications are far-reaching. 
    In conclusion, it is worth noting that AI will play a crucial role in shaping our future."""
    
    result = detector.analyze(ai_text)
    print(f"\n=== AI Detector Test 1: AI-sounding text ===")
    print(f"Probability: {result.ai_generated_probability}")
    print(f"Method: {result.method}")
    assert result.ai_generated_probability > 0.2, "AI text should have higher AI probability"
    
    # Test 2: Human-sounding text  
    human_text = "I went to the store today and bought milk. The weather was really nice! Can't believe how hot it's been lately."
    result2 = detector.analyze(human_text)
    print(f"\n=== AI Detector Test 2: Human-sounding text ===")
    print(f"Probability: {result2.ai_generated_probability}")
    assert result2.ai_generated_probability < 0.3, "Human text should have lower AI probability"
    
    # Test 3: Consistency — same input, same output
    results = [detector.analyze(ai_text).ai_generated_probability for _ in range(3)]
    print(f"\n=== AI Detector Consistency ===")
    print(f"3 runs: {results}")
    assert len(set(results)) == 1, f"Results should be identical: {results}"
    
    print("\n✅ AI content detector tests passed!")


def test_verdict_engine_fallback():
    """Test that the verdict engine fallback properly analyzes evidence."""
    from backend.factcheck.verdict_engine import VerdictEngine
    from backend.models.schemas import Claim, Evidence
    
    engine = VerdictEngine()
    
    # Test 1: Claim with contradicting evidence
    claim = Claim(text="The Earth is flat", entity="Earth")
    evidence = [
        Evidence(
            title="Fact Check: Earth is NOT flat - Debunked",
            url="https://snopes.com/earth-flat-debunked",
            snippet="This claim is rated FALSE. The Earth is an oblate spheroid.",
            source_score=0.9,
        ),
        Evidence(
            title="NASA - Earth Shape",
            url="https://www.nasa.gov/earth-shape",
            snippet="The Earth is roughly spherical, confirmed by satellite imagery.",
            source_score=0.85,
        ),
    ]
    result = engine._fallback_evaluate(claim, evidence)
    print(f"\n=== Verdict Test 1: False claim ===")
    print(f"Verdict: {result.verdict.value}, Confidence: {result.confidence}")
    print(f"Reasoning: {result.reasoning}")
    assert result.verdict.value == "FALSE", f"Expected FALSE, got {result.verdict.value}"
    
    # Test 2: Claim with unrelated evidence (should be UNVERIFIED, not TRUE)
    claim2 = Claim(text="Bananas cure cancer", entity="Bananas")
    evidence2 = [
        Evidence(
            title="Health Benefits of Fruits",
            url="https://example.com/fruits",
            snippet="Fruits contain vitamins and minerals that support general health.",
            source_score=0.5,
        ),
    ]
    result2 = engine._fallback_evaluate(claim2, evidence2)
    print(f"\n=== Verdict Test 2: Unrelated evidence ===")
    print(f"Verdict: {result2.verdict.value}, Confidence: {result2.confidence}")
    assert result2.verdict.value in ("UNVERIFIED", "MISLEADING"), \
        f"Expected UNVERIFIED/MISLEADING, got {result2.verdict.value}"
    
    print("\n✅ Verdict engine fallback tests passed!")


if __name__ == "__main__":
    print("=" * 60)
    print("  TruthShield Backend Fix Verification")
    print("=" * 60)
    
    test_text_classifier()
    test_ai_content_detector()
    test_verdict_engine_fallback()
    
    print("\n" + "=" * 60)
    print("  ALL TESTS PASSED ✅")
    print("=" * 60)
