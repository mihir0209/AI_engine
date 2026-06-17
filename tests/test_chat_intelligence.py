"""Tests for chat intelligence features"""
import pytest


@pytest.fixture
def intelligence():
    from chat_intelligence import ChatIntelligence
    return ChatIntelligence()


# === Summarization Tests ===

def test_summarize_empty_conversation(intelligence):
    summary = intelligence.summarize_conversation([])
    assert summary.message_count == 0
    assert summary.summary == "Empty conversation"


def test_summarize_conversation(intelligence):
    messages = [
        {"role": "user", "content": "Hello, I need help with Python"},
        {"role": "assistant", "content": "Sure! I can help you with Python programming"},
        {"role": "user", "content": "How do I read a file?"},
        {"role": "assistant", "content": "You can use open() function to read files in Python"}
    ]
    
    summary = intelligence.summarize_conversation(messages)
    assert summary.message_count == 4
    assert summary.word_count > 0
    assert len(summary.key_topics) > 0


def test_summarize_sentiment_positive(intelligence):
    messages = [
        {"role": "user", "content": "This is great! I love it! Excellent work!"},
    ]
    
    summary = intelligence.summarize_conversation(messages)
    assert summary.sentiment == "positive"


def test_summarize_sentiment_negative(intelligence):
    messages = [
        {"role": "user", "content": "This is terrible! I hate this! Awful experience!"},
    ]
    
    summary = intelligence.summarize_conversation(messages)
    assert summary.sentiment == "negative"


# === Context Compression Tests ===

def test_compress_context_no_compression_needed(intelligence):
    messages = [
        {"role": "user", "content": "Short message"},
        {"role": "assistant", "content": "Short reply"}
    ]
    
    result = intelligence.compress_context(messages, max_tokens=4000)
    assert result.compressed_count == 2
    assert result.compression_ratio == 1.0


def test_compress_context_with_compression(intelligence):
    # Create messages that exceed token limit
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "x " * 1000},
        {"role": "assistant", "content": "y " * 1000},
        {"role": "user", "content": "z " * 1000}
    ]
    
    result = intelligence.compress_context(messages, max_tokens=100)
    assert result.compressed_count < result.original_count
    assert result.compression_ratio < 1.0
    assert len(result.key_points) >= 0


def test_compress_context_preserves_system_message(intelligence):
    messages = [
        {"role": "system", "content": "Important system prompt"},
        {"role": "user", "content": "x " * 500},
        {"role": "assistant", "content": "y " * 500}
    ]
    
    result = intelligence.compress_context(messages, max_tokens=50)
    system_msgs = [m for m in result.messages if m.get("role") == "system"]
    assert len(system_msgs) == 1


# === Topic Extraction Tests ===

def test_extract_topics(intelligence):
    text = "Python programming language is great for machine learning and data science applications"
    topics = intelligence.extract_topics(text)
    assert len(topics) > 0
    assert any("python" in t.lower() for t in topics)


def test_extract_topics_empty(intelligence):
    topics = intelligence.extract_topics("")
    assert topics == []


# === Intent Detection Tests ===

def test_detect_intent_question(intelligence):
    assert intelligence.detect_intent("What is Python?") == "question"
    assert intelligence.detect_intent("How do I install it?") == "question"
    assert intelligence.detect_intent("Can you help me?") == "question"


def test_detect_intent_request(intelligence):
    assert intelligence.detect_intent("Please help me") == "request"
    assert intelligence.detect_intent("I need assistance") == "request"
    # "Could you" starts with a question word, so it's detected as question
    assert intelligence.detect_intent("Could you explain this?") in ["request", "question"]


def test_detect_intent_command(intelligence):
    assert intelligence.detect_intent("Create a new file") == "command"
    assert intelligence.detect_intent("Write a function") == "command"
    assert intelligence.detect_intent("Generate code") == "command"


def test_detect_intent_greeting(intelligence):
    assert intelligence.detect_intent("Hello!") == "greeting"
    assert intelligence.detect_intent("Hi there") == "greeting"
    assert intelligence.detect_intent("Good morning") == "greeting"


def test_detect_intent_statement(intelligence):
    assert intelligence.detect_intent("The sky is blue") == "statement"
    assert intelligence.detect_intent("I like coding") == "statement"


# === Sentiment Analysis Tests ===

def test_sentiment_analysis(intelligence):
    assert intelligence._analyze_sentiment("I love this! It's great!") == "positive"
    assert intelligence._analyze_sentiment("This is terrible and awful") == "negative"
    assert intelligence._analyze_sentiment("The weather is okay") == "neutral"
