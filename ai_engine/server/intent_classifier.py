"""
Intent classifier for chat routing.
Classifies user prompts and returns required input/output modalities.
Matches against OpenRouter's cached modality data to select providers.

Flow:
  1. Regex detects keywords → if none match, return text_chat (no provider switch)
  2. If keywords match → classify intent with input/output modalities
  3. Caller matches modalities against OpenRouter cache to find provider/model

Usage:
  result = intent_classifier.classify("draw me a cat", has_images=False)
  # result = {"intent": "image_generation", "confidence": 0.9,
  #           "input_modalities": ["text"], "output_modalities": ["text", "image"]}
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

IMAGE_GEN_PATTERNS = [
    re.compile(r'\b(generate|create|draw|make|produce|render|design|paint|sketch)\b.*\b(image|picture|photo|artwork|illustration|diagram|logo|icon|poster|banner|scene|portrait|landscape|drawing|sketch)', re.I),
    re.compile(r'\b(image|picture|photo|artwork|illustration|diagram|logo|icon|poster|banner)\b.*\b(of|with|showing|featuring|depicting)', re.I),
    re.compile(r'\bgenerate\b.*\bimage', re.I),
    re.compile(r'\bimagine\b', re.I),
    re.compile(r'\btext.to.image\b', re.I),
    re.compile(r'\bpaint\b', re.I),
    re.compile(r'\bsketch\b', re.I),
    re.compile(r'\bdraw\b', re.I),
]

AUDIO_GEN_PATTERNS = [
    re.compile(r'\b(generate|create|produce|make|convert)\b.*\b(audio|speech|voice|sound|music|song|narration|tts|text.to.speech)', re.I),
    re.compile(r'\b(speak|say|read|narrate|pronounce)\b.*\b(this|it|out.loud|aloud)', re.I),
    re.compile(r'\btext.to.speech\b', re.I),
    re.compile(r'\btts\b', re.I),
    re.compile(r'\bgenerate\b.*\b(audio|sound|music|song)\b', re.I),
    re.compile(r'\bvoice\b.*\b(of|clone|synth)', re.I),
]

IMAGE_ANALYSIS_PATTERNS = [
    re.compile(r'\b(what|describe|identify|analyze|read|explain)\b.*\b(image|picture|photo)\b', re.I),
    re.compile(r'\b(what|describe|identify)\b.*\b(this)\b(?!.*\b(code|file|document|text|script|program)\b)', re.I),
    re.compile(r'\b(see|look|show)\b.*\b(this|image|picture)\b', re.I),
    re.compile(r'\bocr\b', re.I),
    re.compile(r'\bwhat.*(color|colour|shape|object|thing)', re.I),
    re.compile(r'\bwhat.*(see|look)', re.I),
]

VIDEO_ANALYSIS_PATTERNS = [
    re.compile(r'\b(analyze|review|summarize|describe)\b.*\b(video|clip|footage|recording)\b', re.I),
    re.compile(r'\bwhat.*(happen|occurring)\b.*\b(video|in.this)', re.I),
    re.compile(r'\bvideo\b.*\b(analysis|review|summarize)', re.I),
]

FILE_ANALYSIS_PATTERNS = [
    re.compile(r'\b(read|parse|analyze|review|summarize|extract)\b.*\b(file|document|pdf|csv|json|code|source)', re.I),
    re.compile(r'\b(what|explain)\b.*\b(this file|this document|this code)', re.I),
]


class IntentClassifier:
    """Classify chat prompts into modality intents"""

    def classify(self, text: str, has_images: bool = False,
                 has_video: bool = False, has_files: bool = False) -> Dict:
        """
        Classify a prompt and return intent with required modalities.

        Returns:
            {
                "intent": "text_chat" | "image_generation" | "audio_generation" |
                          "image_analysis" | "video_analysis" | "file_analysis",
                "confidence": float,
                "input_modalities": ["text", "image", "video", "file"],
                "output_modalities": ["text", "image", "audio"],
                "requires_vision": bool,
                "requires_image_gen": bool,
                "requires_audio": bool,
            }
        """
        if not text:
            return self._result("text_chat", 1.0)

        text_lower = text.lower().strip()

        # Context-based: user uploaded media
        if has_images and not self._has_gen_intent(text_lower):
            return self._result("image_analysis", 0.9,
                                input_modalities=["text", "image"],
                                output_modalities=["text"],
                                requires_vision=True)

        if has_video:
            return self._result("video_analysis", 0.9,
                                input_modalities=["text", "video"],
                                output_modalities=["text"],
                                requires_vision=True)

        if has_files:
            if self._any_match(FILE_ANALYSIS_PATTERNS, text_lower):
                return self._result("file_analysis", 0.85,
                                    input_modalities=["text", "file"],
                                    output_modalities=["text"])
            # File attached but asking about content
            return self._result("file_analysis", 0.7,
                                input_modalities=["text", "file"],
                                output_modalities=["text"])

        # Pattern-based classification
        if self._any_match(IMAGE_GEN_PATTERNS, text_lower):
            return self._result("image_generation", 0.9,
                                input_modalities=["text"],
                                output_modalities=["text", "image"],
                                requires_image_gen=True)

        if self._any_match(AUDIO_GEN_PATTERNS, text_lower):
            return self._result("audio_generation", 0.9,
                                input_modalities=["text"],
                                output_modalities=["text", "audio"],
                                requires_audio=True)

        if self._any_match(IMAGE_ANALYSIS_PATTERNS, text_lower):
            return self._result("image_analysis", 0.85,
                                input_modalities=["text", "image"],
                                output_modalities=["text"],
                                requires_vision=True)

        if self._any_match(VIDEO_ANALYSIS_PATTERNS, text_lower):
            return self._result("video_analysis", 0.85,
                                input_modalities=["text", "video"],
                                output_modalities=["text"],
                                requires_vision=True)

        return self._result("text_chat", 0.8)

    def _any_match(self, patterns, text: str) -> bool:
        return any(p.search(text) for p in patterns)

    def _has_gen_intent(self, text: str) -> bool:
        gen_words = ['generate', 'create', 'draw', 'make', 'produce',
                      'render', 'imagine', 'paint', 'sketch', 'design']
        return any(w in text for w in gen_words)

    def _result(self, intent: str, confidence: float,
                input_modalities=None, output_modalities=None,
                requires_vision=False, requires_image_gen=False,
                requires_audio=False) -> Dict:
        return {
            "intent": intent,
            "confidence": confidence,
            "input_modalities": input_modalities or ["text"],
            "output_modalities": output_modalities or ["text"],
            "requires_vision": requires_vision,
            "requires_image_gen": requires_image_gen,
            "requires_audio": requires_audio,
        }


intent_classifier = IntentClassifier()
