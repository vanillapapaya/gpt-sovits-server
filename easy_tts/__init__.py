"""
Easy TTS - GPT-SoVITS v4 기반 간편 TTS 프레임워크
"""

from .config import TTSConfig, VoiceConfig
from .emotions import EmotionAnalyzer
from .parser import TextParser
from .engine import EasyTTS
from .exceptions import TTSError, VoiceNotFoundError, ModelLoadError, AudioGenerationError

__all__ = [
    "EasyTTS",
    "TTSConfig",
    "VoiceConfig",
    "EmotionAnalyzer",
    "TextParser",
    "TTSError",
    "VoiceNotFoundError",
    "ModelLoadError",
    "AudioGenerationError",
]
