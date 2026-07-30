"""TTS 설정 관리"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class VoiceConfig:
    """음성 모델 설정"""
    name: str
    sovits_path: str
    reference_audio: str
    reference_text: str
    description: str = ""
    language: str = "Korean"  # Korean, Japanese, Chinese, English, auto


@dataclass
class TTSConfig:
    """TTS 전체 설정"""
    # 기본 경로
    base_dir: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir: str = "outputs/easy_tts"
    models_dir: str = "../models"

    # GPT-SoVITS 설정
    pretrained_gpt: str = "GPT_SoVITS/pretrained_models/s1v3.ckpt"

    # 생성 파라미터
    top_k: int = 15
    top_p: float = 1.0
    temperature: float = 1.0

    # ASMR 모드 파라미터
    asmr_top_k: int = 10
    asmr_top_p: float = 0.9
    asmr_temperature: float = 0.6
    asmr_volume: float = 0.35
    asmr_reverb: bool = True

    # 음성 모델들
    voices: Dict[str, VoiceConfig] = field(default_factory=dict)
    default_voice: str = "barbara"

    def __post_init__(self):
        if not self.voices:
            self.voices = self._auto_detect_voices()
        if not self.voices:
            self.voices = self._get_default_voices()
        if self.default_voice not in self.voices and self.voices:
            self.default_voice = list(self.voices.keys())[0]

    def _auto_detect_voices(self) -> Dict[str, VoiceConfig]:
        """models 폴더에서 자동으로 음성 모델을 감지"""
        voices = {}
        models_path = Path(self.base_dir) / self.models_dir

        if not models_path.exists():
            return voices

        for category_dir in models_path.iterdir():
            if not category_dir.is_dir() or category_dir.name.startswith('.'):
                continue

            for voice_dir in category_dir.iterdir():
                if not voice_dir.is_dir() or voice_dir.name.startswith('.'):
                    continue

                ckpt_files = list(voice_dir.glob("*.ckpt"))
                if not ckpt_files:
                    continue

                sovits_path = str(ckpt_files[0])
                ref_audio = self._find_reference_audio(voice_dir)
                if not ref_audio:
                    continue

                ref_text = self._find_reference_text(voice_dir, ref_audio)
                voice_name = voice_dir.name.lower().replace('_ko', '').replace('_kr', '')
                description = f"{voice_dir.name} ({category_dir.name})"

                # 폴더 이름에서 언어 추론 (_jp, _ja -> Japanese, _ko, _kr -> Korean)
                folder_name = voice_dir.name.lower()
                if '_jp' in folder_name or '_ja' in folder_name:
                    language = "Japanese"
                elif '_cn' in folder_name or '_zh' in folder_name:
                    language = "Chinese"
                elif '_en' in folder_name:
                    language = "English"
                else:
                    language = "Korean"

                voices[voice_name] = VoiceConfig(
                    name=voice_name,
                    sovits_path=sovits_path,
                    reference_audio=ref_audio,
                    reference_text=ref_text,
                    description=description,
                    language=language
                )

        return voices

    def _find_reference_audio(self, voice_dir: Path) -> Optional[str]:
        """레퍼런스 오디오 파일 찾기"""
        patterns = [
            "reference_audios/**/default_reference.wav",
            "reference_audios/**/*.wav",
            "references/**/*.wav",
            "*.wav"
        ]
        for pattern in patterns:
            files = list(voice_dir.glob(pattern))
            if files:
                return str(files[0])
        return None

    def _find_reference_text(self, voice_dir: Path, ref_audio: str) -> str:
        """레퍼런스 텍스트 찾기"""
        # voice_dir 루트와 하위 폴더 모두 검색
        text_files = list(voice_dir.glob("reference_text.txt")) or list(voice_dir.glob("**/reference_text.txt"))
        if text_files:
            try:
                return text_files[0].read_text(encoding='utf-8').strip()
            except:
                pass

        audio_name = Path(ref_audio).stem
        if '】' in audio_name:
            audio_name = audio_name.split('】')[-1]
        return audio_name if len(audio_name) > 5 else "레퍼런스 텍스트"

    def _get_default_voices(self) -> Dict[str, VoiceConfig]:
        """기본 음성 모델 설정"""
        return {
            "paimon": VoiceConfig(
                name="paimon",
                sovits_path="../models/genshin/paimon_ko/paimon_ko-e10.ckpt",
                reference_audio="../models/genshin/paimon_ko/reference_audios/korean/emotions/default_reference.wav",
                reference_text="그런 카드가 있는 게임이 있을 리가 분명 우리가 정식 플레이어가 됐으니까 보상을 주려는 걸 거야",
                description="페이몬 (원신)"
            ),
            "barbara": VoiceConfig(
                name="barbara",
                sovits_path="../models/genshin/barbara_ko/barbara_ko-e10.ckpt",
                reference_audio="../models/genshin/barbara_ko/reference_audios/korean/emotions/default_reference.wav",
                reference_text="나중에 기회가 되면 바바라표 매운 음료를 만들어 드릴게요",
                description="바바라 (원신)"
            ),
        }
