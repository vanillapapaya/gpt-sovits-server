"""TTS 엔진 코어"""

import os
import sys
import re
from typing import Optional, List

import numpy as np
import soundfile as sf
from scipy import signal

from .config import TTSConfig, VoiceConfig
from .emotions import EmotionAnalyzer
from .parser import TextParser
from .exceptions import VoiceNotFoundError, ModelLoadError, AudioGenerationError

# GPT-SoVITS 환경 설정
os.environ.setdefault("version", "v4")
os.environ.setdefault("is_half", "False")
os.environ.setdefault("INFERENCE_WEBUI_SKIP_UI", "1")

# GPT_SoVITS 경로 추가
_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_base_dir, "GPT_SoVITS"))


class EasyTTS:
    """간편한 TTS 생성 엔진"""

    SAMPLE_RATE = 32000

    def __init__(self, config: Optional[TTSConfig] = None):
        self.config = config or TTSConfig()
        self.emotion_analyzer = EmotionAnalyzer()
        self._model_loaded = False
        self._current_voice = None
        os.makedirs(self.config.output_dir, exist_ok=True)

    def _load_model(self):
        """GPT-SoVITS 모델 로드"""
        if self._model_loaded:
            return

        print("Loading GPT-SoVITS modules...")
        try:
            from GPT_SoVITS.inference_webui import (
                change_gpt_weights,
                change_sovits_weights,
                get_tts_wav,
            )
            self._change_gpt_weights = change_gpt_weights
            self._change_sovits_weights = change_sovits_weights
            self._get_tts_wav = get_tts_wav
            change_gpt_weights(self.config.pretrained_gpt)
            self._model_loaded = True
            print("Model loaded successfully!")
        except ImportError as e:
            raise ModelLoadError(f"GPT-SoVITS 모듈 로드 실패: {e}")
        except Exception as e:
            raise ModelLoadError(f"모델 로드 실패: {e}")

    def _load_voice(self, voice_name: str):
        """음성 모델 로드"""
        if self._current_voice == voice_name:
            return

        if voice_name not in self.config.voices:
            raise VoiceNotFoundError(f"Unknown voice: {voice_name}")

        voice = self.config.voices[voice_name]
        print(f"Loading voice: {voice_name}")
        self._change_sovits_weights(voice.sovits_path)
        self._current_voice = voice_name

    def list_voices(self) -> List[str]:
        """사용 가능한 음성 목록"""
        return list(self.config.voices.keys())

    def _get_unique_path(self, path: str) -> str:
        """고유한 파일 경로 생성"""
        if not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1
        return f"{base}_{counter}{ext}"

    def _generate_silence(self, duration: float, sample_rate: int) -> np.ndarray:
        """무음 생성"""
        return np.zeros(int(duration * sample_rate), dtype=np.float32)

    def _apply_asmr_effect(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """ASMR 후처리"""
        # 저역 통과 필터
        nyquist = sample_rate / 2
        cutoff = 7000 / nyquist
        b, a = signal.butter(2, cutoff, btype='low')
        audio_filtered = signal.filtfilt(b, a, audio)
        audio = audio * 0.6 + audio_filtered * 0.4

        # 리버브
        if self.config.asmr_reverb:
            delay = int(0.04 * sample_rate)
            reverb = np.zeros_like(audio)
            reverb[delay:] = audio[:-delay] * 0.25
            reverb[delay*2:] += audio[:-delay*2] * 0.12
            audio = audio + reverb

        # 볼륨 조정
        audio = audio * self.config.asmr_volume
        max_val = np.max(np.abs(audio))
        if max_val > 0.5:
            audio = audio * (0.5 / max_val)

        return audio.astype(np.float32)

    def _generate_speech(
        self,
        text: str,
        voice_config: VoiceConfig,
        asmr: bool = False,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: Optional[str] = None
    ) -> tuple:
        """단일 텍스트 음성 생성"""
        if asmr:
            top_k, top_p, temp = self.config.asmr_top_k, self.config.asmr_top_p, self.config.asmr_temperature
        else:
            top_k, top_p, temp = self.config.top_k, self.config.top_p, self.config.temperature

        actual_ref_audio = ref_audio or voice_config.reference_audio
        actual_ref_text = ref_text or voice_config.reference_text

        try:
            lang = language or voice_config.language
            result = self._get_tts_wav(
                ref_wav_path=actual_ref_audio,
                prompt_text=actual_ref_text,
                prompt_language=lang,
                text=text,
                text_language=lang,
                how_to_cut="不切",
                top_k=top_k,
                top_p=top_p,
                temperature=temp,
                ref_free=False,
            )
            return next(result)
        except StopIteration:
            raise AudioGenerationError("음성 생성 결과 없음")
        except Exception as e:
            raise AudioGenerationError(f"음성 생성 실패: {e}")

    def generate(
        self,
        text: str,
        voice: Optional[str] = None,
        output_path: Optional[str] = None,
        asmr: bool = False,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: Optional[str] = None,
        verbose: bool = True
    ) -> str:
        """텍스트에서 음성 생성"""
        self._load_model()

        voice_name = voice or self.config.default_voice
        self._load_voice(voice_name)
        voice_config = self.config.voices[voice_name]

        # 텍스트 파싱
        segments = TextParser.parse(text)

        # 출력 경로
        if output_path is None:
            clean_text = TextParser.clean(text)
            safe_text = re.sub(r'[^\w\s가-힣]', '', clean_text)[:20].strip().replace(' ', '_')
            suffix = "_asmr" if asmr else ""
            output_path = os.path.join(self.config.output_dir, f"{voice_name}_{safe_text}{suffix}.wav")

        output_path = self._get_unique_path(output_path)

        if verbose:
            print(f"  Generating: {text[:50]}{'...' if len(text) > 50 else ''}")

        # 세그먼트별 오디오 생성
        audio_segments = []
        sample_rate = None

        for seg in segments:
            if seg["type"] == "pause":
                sr = sample_rate or self.SAMPLE_RATE
                audio_segments.append(self._generate_silence(seg["duration"], sr))
            else:
                sr, audio = self._generate_speech(
                    seg["content"], voice_config, asmr=asmr,
                    ref_audio=ref_audio, ref_text=ref_text, language=language
                )
                sample_rate = sr
                audio_segments.append(audio)

        # 합치기 및 후처리
        if audio_segments:
            final_audio = np.concatenate(audio_segments)
            if asmr:
                final_audio = self._apply_asmr_effect(final_audio, sample_rate)
            else:
                max_val = np.max(np.abs(final_audio))
                if max_val > 0.95:
                    final_audio = final_audio * (0.95 / max_val)
        else:
            final_audio = np.array([], dtype=np.float32)

        sf.write(output_path, final_audio, sample_rate or self.SAMPLE_RATE)

        if verbose:
            duration = len(final_audio) / (sample_rate or self.SAMPLE_RATE)
            print(f"  Saved: {output_path} ({duration:.1f}s)")

        return output_path

    def generate_from_file(
        self,
        input_file: str,
        voice: Optional[str] = None,
        output_dir: Optional[str] = None,
        merge: bool = True,
        asmr: bool = False,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: Optional[str] = None
    ) -> List[str]:
        """텍스트 파일에서 음성 생성"""
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        output_dir = output_dir or self.config.output_dir
        os.makedirs(output_dir, exist_ok=True)
        voice_name = voice or self.config.default_voice

        print(f"\n{'='*50}")
        print(f"TTS: {input_file} ({len(lines)} lines)")
        print(f"Voice: {voice_name}" + (" [ASMR]" if asmr else ""))
        print(f"{'='*50}\n")

        if merge:
            full_text = "\n".join(lines)
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            suffix = "_asmr" if asmr else ""
            output_path = self._get_unique_path(
                os.path.join(output_dir, f"{base_name}_{voice_name}{suffix}.wav")
            )
            try:
                path = self.generate(full_text, voice=voice, output_path=output_path,
                                    asmr=asmr, ref_audio=ref_audio, ref_text=ref_text, language=language)
                return [path]
            except Exception as e:
                print(f"Error: {e}")
                return []
        else:
            generated = []
            idx = 1
            for i, line in enumerate(lines, 1):
                if not TextParser.clean(line):
                    continue
                print(f"[{i}/{len(lines)}]")
                suffix = "_asmr" if asmr else ""
                output_path = self._get_unique_path(
                    os.path.join(output_dir, f"{idx:03d}_{voice_name}{suffix}.wav")
                )
                try:
                    path = self.generate(line, voice=voice, output_path=output_path,
                                        asmr=asmr, ref_audio=ref_audio, ref_text=ref_text, language=language)
                    generated.append(path)
                    idx += 1
                except Exception as e:
                    print(f"  Error: {e}")
            return generated
