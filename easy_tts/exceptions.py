"""TTS 관련 예외 클래스"""


class TTSError(Exception):
    """TTS 관련 기본 예외"""
    pass


class VoiceNotFoundError(TTSError):
    """음성 모델을 찾을 수 없을 때"""
    pass


class ModelLoadError(TTSError):
    """모델 로드 실패"""
    pass


class AudioGenerationError(TTSError):
    """오디오 생성 실패"""
    pass
