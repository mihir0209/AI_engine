"""
Advanced chat features module
Provides conversation summarization, context compression, and topic extraction
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
from dataclasses import dataclass


@dataclass
class ConversationSummary:
    """Summary of a conversation"""
    chat_id: int
    summary: str
    key_topics: List[str]
    sentiment: str  # positive, neutral, negative
    message_count: int
    word_count: int


@dataclass
class CompressedContext:
    """Compressed conversation context"""
    messages: List[Dict]
    original_count: int
    compressed_count: int
    compression_ratio: float
    key_points: List[str]


class ChatIntelligence:
    """Advanced chat intelligence features"""

    def __init__(self):
        self.stop_words = {
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your',
            'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her',
            'hers', 'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs',
            'themselves', 'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those',
            'am', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'having', 'do', 'does', 'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if',
            'or', 'because', 'as', 'until', 'while', 'of', 'at', 'by', 'for', 'with',
            'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after',
            'above', 'below', 'to', 'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over',
            'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when', 'where',
            'why', 'how', 'all', 'both', 'each', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
            's', 't', 'can', 'will', 'just', 'don', 'should', 'now', 'd', 'll', 'm', 'o',
            're', 've', 'y', 'ain', 'aren', 'couldn', 'didn', 'doesn', 'hadn', 'hasn',
            'haven', 'isn', 'ma', 'mightn', 'mustn', 'needn', 'shan', 'shouldn', 'wasn',
            'weren', 'won', 'wouldn'
        }

    def summarize_conversation(self, messages: List[Dict], max_length: int = 200) -> ConversationSummary:
        """Generate a summary of the conversation"""
        if not messages:
            return ConversationSummary(
                chat_id=0, summary="Empty conversation", key_topics=[],
                sentiment="neutral", message_count=0, word_count=0
            )

        # Combine all messages
        all_text = " ".join(m.get("content", "") for m in messages)
        words = all_text.split()

        # Extract key topics
        key_topics = self._extract_topics(all_text)

        # Analyze sentiment
        sentiment = self._analyze_sentiment(all_text)

        # Generate summary (simple extractive approach)
        summary = self._generate_summary(messages, max_length)

        return ConversationSummary(
            chat_id=messages[0].get("chat_id", 0),
            summary=summary,
            key_topics=key_topics[:5],
            sentiment=sentiment,
            message_count=len(messages),
            word_count=len(words)
        )

    def compress_context(self, messages: List[Dict], max_tokens: int = 4000) -> CompressedContext:
        """Compress conversation context to fit within token limit"""
        if not messages:
            return CompressedContext(messages=[], original_count=0, compressed_count=0,
                                   compression_ratio=1.0, key_points=[])

        original_count = len(messages)

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        total_chars = sum(len(m.get("content", "")) for m in messages)
        estimated_tokens = total_chars // 4

        if estimated_tokens <= max_tokens:
            return CompressedContext(
                messages=messages,
                original_count=original_count,
                compressed_count=original_count,
                compression_ratio=1.0,
                key_points=[]
            )

        # Strategy 1: Keep system message and last N messages
        system_messages = [m for m in messages if m.get("role") == "system"]
        non_system_messages = [m for m in messages if m.get("role") != "system"]

        # Calculate how many messages we can keep
        chars_per_token = 4
        max_chars = max_tokens * chars_per_token

        # Keep system messages (they're important)
        kept_messages = list(system_messages)
        kept_chars = sum(len(m.get("content", "")) for m in kept_messages)

        # Add messages from the end until we hit the limit
        for msg in reversed(non_system_messages):
            msg_chars = len(msg.get("content", ""))
            if kept_chars + msg_chars <= max_chars:
                kept_messages.insert(len(system_messages), msg)
                kept_chars += msg_chars
            else:
                break

        # Extract key points from dropped messages
        dropped_messages = [m for m in non_system_messages if m not in kept_messages]
        key_points = self._extract_key_points(dropped_messages)

        # Sort kept messages by original order
        kept_messages.sort(key=lambda m: messages.index(m) if m in messages else 0)

        return CompressedContext(
            messages=kept_messages,
            original_count=original_count,
            compressed_count=len(kept_messages),
            compression_ratio=len(kept_messages) / original_count if original_count > 0 else 1.0,
            key_points=key_points
        )

    def extract_topics(self, text: str) -> List[str]:
        """Extract main topics from text"""
        return self._extract_topics(text)

    def _extract_topics(self, text: str) -> List[str]:
        """Internal topic extraction using TF-IDF-like approach"""
        # Tokenize and clean
        words = re.findall(r'\b\w+\b', text.lower())
        words = [w for w in words if w not in self.stop_words and len(w) > 3]

        # Count word frequencies
        word_counts = Counter(words)

        # Get top keywords
        top_words = word_counts.most_common(10)

        # Extract bigrams for better topic detection
        bigrams = []
        for i in range(len(words) - 1):
            if words[i] not in self.stop_words and words[i+1] not in self.stop_words:
                bigrams.append(f"{words[i]} {words[i+1]}")

        bigram_counts = Counter(bigrams)
        top_bigrams = [b for b, _ in bigram_counts.most_common(5)]

        # Combine single words and bigrams
        topics = top_bigrams + [w for w, _ in top_words[:5]]

        return topics[:10]

    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis"""
        positive_words = {'good', 'great', 'excellent', 'awesome', 'fantastic', 'wonderful',
                         'love', 'like', 'happy', 'pleased', 'thank', 'thanks', 'perfect',
                         'amazing', 'best', 'helpful', 'useful', 'beautiful', 'nice'}
        negative_words = {'bad', 'terrible', 'awful', 'horrible', 'hate', 'dislike', 'sad',
                         'angry', 'frustrated', 'annoying', 'broken', 'wrong', 'error',
                         'fail', 'failed', 'problem', 'issue', 'bug', 'crash', 'worst'}

        words = set(text.lower().split())

        positive_count = len(words & positive_words)
        negative_count = len(words & negative_words)

        if positive_count > negative_count * 2:
            return "positive"
        elif negative_count > positive_count * 2:
            return "negative"
        return "neutral"

    def _generate_summary(self, messages: List[Dict], max_length: int) -> str:
        """Generate extractive summary"""
        if not messages:
            return ""

        # Simple approach: take first message, last few messages, and longest messages
        important_messages = []

        # First message (usually sets context)
        if messages:
            important_messages.append(messages[0])

        # Last 2-3 messages (most recent context)
        important_messages.extend(messages[-3:])

        # Longest messages (likely most informative)
        sorted_by_length = sorted(messages, key=lambda m: len(m.get("content", "")), reverse=True)
        important_messages.extend(sorted_by_length[:2])

        # Remove duplicates while preserving order
        seen = set()
        unique_messages = []
        for msg in important_messages:
            content = msg.get("content", "")
            if content and content not in seen:
                seen.add(content)
                unique_messages.append(content)

        # Combine and truncate
        summary = " ".join(unique_messages)
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."

        return summary

    def _extract_key_points(self, messages: List[Dict]) -> List[str]:
        """Extract key points from messages"""
        key_points = []

        for msg in messages:
            content = msg.get("content", "")
            if not content:
                continue

            # Look for sentences with important patterns
            sentences = re.split(r'[.!?]+', content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 10:
                    continue

                # Check for important patterns
                if any(keyword in sentence.lower() for keyword in ['important', 'note', 'remember', 'key', 'main', 'summary']):
                    key_points.append(sentence)
                elif len(sentence) > 50:  # Longer sentences often contain key info
                    key_points.append(sentence[:100] + "..." if len(sentence) > 100 else sentence)

        return key_points[:5]  # Return top 5 key points

    def detect_intent(self, message: str) -> str:
        """Detect user intent from message"""
        message_lower = message.lower()

        # Question patterns
        if re.match(r'^(what|how|why|when|where|who|which|can|could|would|should|is|are|do|does|did)', message_lower):
            return "question"

        # Request patterns
        if any(word in message_lower for word in ['please', 'help', 'need', 'want', 'can you', 'could you']):
            return "request"

        # Command patterns
        if any(word in message_lower for word in ['create', 'make', 'build', 'generate', 'write', 'add', 'remove', 'delete']):
            return "command"

        # Information sharing
        if any(word in message_lower for word in ['here is', 'this is', 'the following', 'note that']):
            return "information"

        # Greeting
        if any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']):
            return "greeting"

        return "statement"


# Global instance
chat_intelligence = ChatIntelligence()
