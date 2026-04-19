"""
TruthShield — Test Pipeline
Pytest tests for each module with mock responses (no real API keys needed).
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ═══════════════════════════════════════════════
# Test: Text Processor
# ═══════════════════════════════════════════════

class TestTextProcessor:
    def test_clean_text(self):
        from backend.preprocessor.text_processor import TextProcessor
        processor = TextProcessor()
        result = processor.clean_text("  Hello   World  \n\n  Test  ")
        assert "Hello World Test" == result

    def test_process_english(self):
        from backend.preprocessor.text_processor import TextProcessor
        processor = TextProcessor()
        packet = processor.process("This is a test article about politics.", "en")
        assert packet.content_type.value == "text"
        assert packet.lang.value == "en"
        assert packet.text is not None
        assert len(packet.text) > 0

    def test_process_with_lang_hint(self):
        from backend.preprocessor.text_processor import TextProcessor
        processor = TextProcessor()
        packet = processor.process("Some text", "hi")
        assert packet.lang.value == "hi"

    def test_detect_language(self):
        from backend.preprocessor.text_processor import TextProcessor
        lang = TextProcessor.detect_language("This is English text for testing.")
        assert lang.value == "en"


# ═══════════════════════════════════════════════
# Test: URL Scraper
# ═══════════════════════════════════════════════

class TestURLScraper:
    @patch("backend.preprocessor.url_scraper.requests")
    def test_scrape_success(self, mock_requests):
        from backend.preprocessor.url_scraper import URLScraper

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
        <head><title>Test Article</title>
        <meta property="og:title" content="Test Article Title" />
        <meta property="og:image" content="https://example.com/image.jpg" />
        </head>
        <body><article><p>This is a test article with enough text to be extracted properly by the scraper.</p></article></body>
        </html>
        """
        mock_requests.get.return_value = mock_response

        scraper = URLScraper()
        result = scraper.scrape("https://example.com/article")
        assert result["title"] == "Test Article Title"
        assert result["og_image"] == "https://example.com/image.jpg"


# ═══════════════════════════════════════════════
# Test: Text Classifier
# ═══════════════════════════════════════════════

class TestTextClassifier:
    def test_fallback_classify_fake(self):
        from backend.detectors.text_classifier import TextClassifier
        classifier = TextClassifier()
        text = "BREAKING!!! Share before deleted! They don't want you to know this shocking truth!"
        result = classifier._fallback_classify(text)
        assert result.label in ("fake", "misleading")
        assert result.confidence > 0

    def test_fallback_classify_real(self):
        from backend.detectors.text_classifier import TextClassifier
        classifier = TextClassifier()
        text = "According to the official press release, the government data shows that reported figures indicate a modest change."
        result = classifier._fallback_classify(text)
        assert result.label in ("real", "misleading")

    def test_short_text(self):
        from backend.detectors.text_classifier import TextClassifier
        classifier = TextClassifier()
        result = classifier.classify("Hi")
        assert result.label == "unknown"


# ═══════════════════════════════════════════════
# Test: AI Content Detector
# ═══════════════════════════════════════════════

class TestAIContentDetector:
    def test_heuristic_detect_ai_phrases(self):
        from backend.detectors.ai_content_detector import AIContentDetector
        detector = AIContentDetector()
        text = "It's important to note that this comprehensive analysis delves into the subject. It is worth noting that it's crucial to understand."
        prob = detector._heuristic_detect(text)
        assert prob > 0.3  # Should detect AI-like patterns

    def test_heuristic_detect_human(self):
        from backend.detectors.ai_content_detector import AIContentDetector
        detector = AIContentDetector()
        text = "The match was fantastic yesterday. Kohli scored a brilliant century and the crowd went absolutely wild with joy."
        prob = detector._heuristic_detect(text)
        assert prob < 0.3  # Should detect human-like patterns

    def test_insufficient_text(self):
        from backend.detectors.ai_content_detector import AIContentDetector
        detector = AIContentDetector()
        result = detector.analyze("short")
        assert result.ai_generated_probability == 0.0
        assert result.method == "insufficient_text"


# ═══════════════════════════════════════════════
# Test: Credibility Scorer
# ═══════════════════════════════════════════════

class TestCredibilityScorer:
    def test_high_trust(self):
        from backend.detectors.credibility_scorer import CredibilityScorer
        from backend.models.schemas import TextClassificationResult, AIContentResult

        scorer = CredibilityScorer()
        result = scorer.score(
            text_result=TextClassificationResult(label="real", confidence=0.9),
            ai_content_result=AIContentResult(ai_generated_probability=0.1),
        )
        assert result.trust_score >= 70
        assert "AUTHENTIC" in result.verdict or "UNCERTAIN" in result.verdict

    def test_low_trust(self):
        from backend.detectors.credibility_scorer import CredibilityScorer
        from backend.models.schemas import TextClassificationResult, AIContentResult

        scorer = CredibilityScorer()
        result = scorer.score(
            text_result=TextClassificationResult(label="fake", confidence=0.95),
            ai_content_result=AIContentResult(ai_generated_probability=0.9),
        )
        assert result.trust_score <= 30
        assert "FALSE" in result.verdict or "MISLEADING" in result.verdict

    def test_no_inputs(self):
        from backend.detectors.credibility_scorer import CredibilityScorer
        scorer = CredibilityScorer()
        result = scorer.score()
        assert result.trust_score == 50  # Neutral default


# ═══════════════════════════════════════════════
# Test: Claim Extractor
# ═══════════════════════════════════════════════

class TestClaimExtractor:
    def test_rule_based_extraction(self):
        from backend.factcheck.claim_extractor import ClaimExtractor
        extractor = ClaimExtractor()
        text = (
            "The government announced that GDP grew by 15% last quarter. "
            "A study shows that 80% of citizens support the new policy. "
            "According to experts, the economy will improve."
        )
        claims = extractor._rule_based_extract(text)
        assert len(claims) >= 1

    def test_empty_text(self):
        from backend.factcheck.claim_extractor import ClaimExtractor
        extractor = ClaimExtractor()
        claims = extractor._rule_based_extract("")
        assert len(claims) == 0


# ═══════════════════════════════════════════════
# Test: Source Ranker
# ═══════════════════════════════════════════════

class TestSourceRanker:
    def test_government_source(self):
        from backend.factcheck.source_ranker import SourceRanker
        ranker = SourceRanker()
        score = ranker.score_source("https://pib.gov.in/article/12345")
        assert score >= 0.85

    def test_disinfo_source(self):
        from backend.factcheck.source_ranker import SourceRanker
        ranker = SourceRanker()
        score = ranker.score_source("https://infowars.com/fake-story")
        assert score == 0.0

    def test_unknown_source(self):
        from backend.factcheck.source_ranker import SourceRanker
        ranker = SourceRanker()
        score = ranker.score_source("https://randomsite.xyz/article")
        assert score == 0.3

    def test_news_source(self):
        from backend.factcheck.source_ranker import SourceRanker
        ranker = SourceRanker()
        score = ranker.score_source("https://www.bbc.com/news/article")
        assert score >= 0.7

    def test_rank_evidence(self):
        from backend.factcheck.source_ranker import SourceRanker
        from backend.models.schemas import Evidence
        ranker = SourceRanker()
        evidence = [
            Evidence(title="A", url="https://randomsite.xyz/a", snippet="", source_score=0),
            Evidence(title="B", url="https://pib.gov.in/b", snippet="", source_score=0),
            Evidence(title="C", url="https://bbc.com/c", snippet="", source_score=0),
        ]
        ranked = ranker.rank_evidence(evidence)
        assert ranked[0].url == "https://pib.gov.in/b"  # Highest score first


# ═══════════════════════════════════════════════
# Test: Verdict Engine (Mocked)
# ═══════════════════════════════════════════════

class TestVerdictEngine:
    def test_fallback_with_evidence(self):
        from backend.factcheck.verdict_engine import VerdictEngine
        from backend.models.schemas import Claim, Evidence

        engine = VerdictEngine()
        claim = Claim(text="GDP grew by 8%", entity="India")
        evidence = [
            Evidence(title="Official stats", url="https://gov.in/gdp", snippet="GDP growth 8.2%", source_score=0.9),
        ]
        result = engine._fallback_evaluate(claim, evidence)
        assert result.verdict.value == "TRUE"

    def test_fallback_no_evidence(self):
        from backend.factcheck.verdict_engine import VerdictEngine
        from backend.models.schemas import Claim

        engine = VerdictEngine()
        claim = Claim(text="Some unverifiable claim")
        result = engine._fallback_evaluate(claim, [])
        assert result.verdict.value == "UNVERIFIED"


# ═══════════════════════════════════════════════
# Test: Multilingual Explainer (Fallbacks)
# ═══════════════════════════════════════════════

class TestMultilingualExplainer:
    def test_fallback_english(self):
        from backend.counter.multilingual_explainer import MultilingualExplainer
        explainer = MultilingualExplainer()
        text = explainer._fallback_explanation("FALSE", "en")
        assert "false" in text.lower() or "contradict" in text.lower()

    def test_fallback_hindi(self):
        from backend.counter.multilingual_explainer import MultilingualExplainer
        explainer = MultilingualExplainer()
        text = explainer._fallback_explanation("FALSE", "hi")
        assert len(text) > 0  # Hindi text should be non-empty

    def test_fallback_tamil(self):
        from backend.counter.multilingual_explainer import MultilingualExplainer
        explainer = MultilingualExplainer()
        text = explainer._fallback_explanation("MISLEADING", "ta")
        assert len(text) > 0


# ═══════════════════════════════════════════════
# Test: Inconsistency Highlighter (Fallbacks)
# ═══════════════════════════════════════════════

class TestInconsistencyHighlighter:
    def test_fallback_highlight_detects_patterns(self):
        from backend.counter.inconsistency_highlighter import InconsistencyHighlighter
        highlighter = InconsistencyHighlighter()
        text = "This is 100% true! Share before they delete it! They don't want you to know!"
        results = highlighter._fallback_highlight(text)
        assert len(results) >= 2  # Should detect multiple patterns

    def test_fallback_clean_text(self):
        from backend.counter.inconsistency_highlighter import InconsistencyHighlighter
        highlighter = InconsistencyHighlighter()
        text = "The government announced new economic policies for the next fiscal year."
        results = highlighter._fallback_highlight(text)
        assert len(results) == 0


# ═══════════════════════════════════════════════
# Test: Pydantic Schemas
# ═══════════════════════════════════════════════

class TestSchemas:
    def test_content_packet_creation(self):
        from backend.models.schemas import ContentPacket, ContentType, Language
        packet = ContentPacket(content_type=ContentType.TEXT, text="test", lang=Language.EN)
        assert packet.id is not None
        assert packet.content_type == ContentType.TEXT

    def test_analysis_report_creation(self):
        from backend.models.schemas import AnalysisReport
        report = AnalysisReport()
        assert report.id is not None
        assert report.credibility.trust_score == 50

    def test_claim_verdict_serialization(self):
        from backend.models.schemas import Claim, ClaimVerdict, Verdict
        cv = ClaimVerdict(
            claim=Claim(text="Test claim"),
            verdict=Verdict.TRUE,
            reasoning="Verified",
            confidence=0.95,
        )
        data = cv.model_dump()
        assert data["verdict"] == "TRUE"
        assert data["confidence"] == 0.95


# ═══════════════════════════════════════════════
# Test: Config
# ═══════════════════════════════════════════════

class TestConfig:
    def test_settings_load(self):
        from backend.config import get_settings
        settings = get_settings()
        assert settings.APP_PORT == 8000
        assert settings.JWT_ALGORITHM == "HS256"

    def test_credibility_weights(self):
        from backend.config import CREDIBILITY_WEIGHTS
        total = sum(CREDIBILITY_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01  # Weights should sum to 1.0

    def test_supported_languages(self):
        from backend.config import SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES
        assert "hi" in SUPPORTED_LANGUAGES
        assert "ta" in SUPPORTED_LANGUAGES


# ═══════════════════════════════════════════════
# Test: Full Pipeline (Integration, Mocked)
# ═══════════════════════════════════════════════

class TestFullPipeline:
    def test_sample_fake_hindi_article(self):
        """Test the full pipeline on the fake Hindi article sample."""
        from backend.preprocessor.text_processor import TextProcessor
        from backend.detectors.text_classifier import TextClassifier
        from backend.detectors.credibility_scorer import CredibilityScorer

        sample_path = Path(__file__).parent / "sample_data" / "fake_hindi_article.txt"
        if not sample_path.exists():
            pytest.skip("Sample data not found")

        text = sample_path.read_text(encoding="utf-8")

        # Preprocess
        processor = TextProcessor()
        packet = processor.process(text)
        assert packet.lang.value == "hi"

        # Classify
        classifier = TextClassifier()
        text_result = classifier.classify(packet.text, packet.lang.value)
        assert text_result.label in ("fake", "misleading", "real", "unknown")

        # Score
        scorer = CredibilityScorer()
        score = scorer.score(text_result=text_result)
        assert 0 <= score.trust_score <= 100

    def test_sample_real_english_article(self):
        """Test the full pipeline on the real English article sample."""
        from backend.preprocessor.text_processor import TextProcessor
        from backend.detectors.text_classifier import TextClassifier
        from backend.detectors.credibility_scorer import CredibilityScorer

        sample_path = Path(__file__).parent / "sample_data" / "real_english_article.txt"
        if not sample_path.exists():
            pytest.skip("Sample data not found")

        text = sample_path.read_text(encoding="utf-8")

        processor = TextProcessor()
        packet = processor.process(text)
        assert packet.lang.value == "en"

        classifier = TextClassifier()
        text_result = classifier.classify(packet.text, packet.lang.value)

        scorer = CredibilityScorer()
        score = scorer.score(text_result=text_result)
        assert 0 <= score.trust_score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
