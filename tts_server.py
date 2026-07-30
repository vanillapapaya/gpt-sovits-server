#!/usr/bin/env python3
"""
GPT-SoVITS TTS API 서버
모델을 미리 로드해두고 HTTP API로 빠르게 음성 생성

설정 파일: tts_config.yaml (FRIDAY 폴더)

사용법:
    python tts_server.py                    # 기본 실행
    python tts_server.py --voice paimon     # 특정 음성으로 시작
    python tts_server.py --port 9880        # 포트 변경

API:
    POST /tts
    {
        "text": "안녕하세요!",
        "voice": "paimon"  (선택)
    }
    → WAV 오디오 파일 반환
"""

import os
import sys
import io
import argparse
import time
from pathlib import Path
from typing import Dict, Any, Optional

import yaml

# .env 로드
from dotenv import load_dotenv

FRIDAY_PATH = Path(__file__).parent
load_dotenv(FRIDAY_PATH / ".env")

# GPT-SoVITS 경로. .env 의 SOVITS_PATH 로 지정한다.
# 기본값은 이 파일이 놓인 자리 — GPT-SoVITS 체크아웃 안에 두면 그대로 맞는다.
SOVITS_PATH = Path(os.getenv("SOVITS_PATH", str(Path(__file__).parent)))

# 경로 존재 확인
if not SOVITS_PATH.exists():
    print(f"⚠️  GPT-SoVITS 경로를 찾을 수 없습니다: {SOVITS_PATH}")
    print(f"   .env 파일에서 SOVITS_PATH를 설정해주세요.")

# 환경변수 설정 (임포트 전에!)
os.environ["version"] = "v4"
os.environ["is_half"] = "False"
# transformers 보안 체크 우회 (PyTorch 2.6 미만에서 torch.load 사용 허용)
os.environ["TRANSFORMERS_ALLOW_UNSAFE_TORCH_LOAD"] = "1"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn


# ========== TTS 설정 파일 로드 ==========

def load_tts_config() -> Dict[str, Any]:
    """tts_config.yaml 로드"""
    config_path = FRIDAY_PATH / "tts_config.yaml"

    if not config_path.exists():
        print(f"⚠️  TTS 설정 파일 없음: {config_path}")
        print("   기본 설정을 사용합니다.")
        return {
            "default_voice": "paimon",
            "voices": {},
            "inference": {},
            "paths": {
                "gpt_weights": "GPT_weights_v2",
                "sovits_weights": "SoVITS_weights_v2",
                "reference_audio": "reference_audio"
            }
        }

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    print(f"✅ TTS 설정 로드: {config_path}")
    return config


TTS_CONFIG = load_tts_config()


# ========== easy_tts 동적 임포트 ==========

EasyTTS = None
EasyTTSConfig = None

def load_easy_tts():
    global EasyTTS, EasyTTSConfig
    if EasyTTS is not None:
        return

    # GPT-SoVITS 경로를 Python path에 추가
    sovits_path_str = str(SOVITS_PATH)
    if sovits_path_str not in sys.path:
        sys.path.insert(0, sovits_path_str)
    gpt_sovits_path = str(SOVITS_PATH / "GPT_SoVITS")
    if gpt_sovits_path not in sys.path:
        sys.path.insert(0, gpt_sovits_path)

    # 작업 디렉토리를 GPT-SoVITS로 변경 (모델 경로 문제 해결)
    original_cwd = os.getcwd()
    os.chdir(SOVITS_PATH)

    try:
        from easy_tts import EasyTTS as _EasyTTS, TTSConfig as _TTSConfig
        EasyTTS = _EasyTTS
        EasyTTSConfig = _TTSConfig
    finally:
        os.chdir(original_cwd)


# ========== API 모델 ==========

class TTSRequest(BaseModel):
    language: str = None
    text: str
    voice: str = None


# ========== TTS 서버 클래스 ==========

class TTSServer:
    def __init__(self, default_voice: str = None, cache_size: int = 50):
        self.default_voice = default_voice or TTS_CONFIG.get("default_voice", "paimon")
        self.tts_engine = None
        self._loaded = False
        self._voices_config = TTS_CONFIG.get("voices", {})

        # 간단한 캐시 (동일 텍스트 재생성 방지)
        self._cache = {}
        self._cache_order = []
        self._cache_size = cache_size

    def load(self):
        """TTS 엔진 로드 (서버 시작 시 한 번만)"""
        if self._loaded:
            return

        print()
        print("=" * 50)
        print("  🚀 TTS 모델 로딩 시작")
        print("=" * 50)
        start = time.time()

        # Step 1: easy_tts 모듈 로드
        print("  [1/3] easy_tts 모듈 로딩 중...")
        try:
            load_easy_tts()
            print("  [1/3] ✅ easy_tts 모듈 로드 완료")
        except Exception as e:
            print(f"  [1/3] ❌ easy_tts 모듈 로드 실패!")
            print(f"        오류: {e}")
            raise

        # Step 2: 설정 구성
        print("  [2/3] 음성 설정 구성 중...")
        try:
            voices_config = self._build_voices_config()
            config = EasyTTSConfig(
                base_dir=str(SOVITS_PATH),
                default_voice=self.default_voice
            )
            if voices_config:
                config.voices = voices_config
            print(f"  [2/3] ✅ 음성 설정 완료 ({len(config.voices)}개 음성)")
        except Exception as e:
            print(f"  [2/3] ❌ 음성 설정 실패!")
            print(f"        오류: {e}")
            raise

        # Step 3: TTS 엔진 초기화 (이 부분이 오래 걸림)
        print("  [3/3] TTS 엔진 초기화 중... (모델 로딩, 1-3분 소요)")
        original_cwd = os.getcwd()
        os.chdir(SOVITS_PATH)

        try:
            self.tts_engine = EasyTTS(config)
            print("  [3/3] ✅ TTS 엔진 초기화 완료")
        except Exception as e:
            print(f"  [3/3] ❌ TTS 엔진 초기화 실패!")
            print(f"        오류: {e}")
            import traceback
            traceback.print_exc()
            raise
        finally:
            os.chdir(original_cwd)

        elapsed = time.time() - start
        self._loaded = True

        print("=" * 50)
        print(f"  ✅ TTS 엔진 초기화 완료! ({elapsed:.1f}초)")
        print(f"  📢 사용 가능한 음성: {list(self.tts_engine.config.voices.keys())}")
        print(f"  🎤 기본 음성: {self.default_voice}")
        print("=" * 50)

        # Step 4: 워밍업 - 첫 생성은 모델 로딩으로 느림
        print("  [4/4] 워밍업 중... (첫 음성 생성)")
        try:
            warmup_start = time.time()
            # 짧은 텍스트로 워밍업
            self._warmup_generate("안녕")
            warmup_elapsed = time.time() - warmup_start
            print(f"  [4/4] ✅ 워밍업 완료! ({warmup_elapsed:.1f}초)")
        except Exception as e:
            print(f"  [4/4] ⚠️  워밍업 실패 (무시): {e}")

        total_elapsed = time.time() - start
        print("=" * 50)
        print(f"  🎉 TTS 서버 준비 완료! (총 {total_elapsed:.1f}초)")
        print("=" * 50)
        print()

    @staticmethod
    def _infer_language(voice_name: str) -> str:
        """voice 이름에서 언어를 추론 (예: anon-jp -> Japanese)"""
        name_lower = voice_name.lower()
        if name_lower.endswith("-jp") or "_jp" in name_lower or name_lower.endswith("-ja") or "_ja" in name_lower:
            return "Japanese"
        if name_lower.endswith("-cn") or "_cn" in name_lower or name_lower.endswith("-zh") or "_zh" in name_lower:
            return "Chinese"
        if name_lower.endswith("-en") or "_en" in name_lower:
            return "English"
        return "Korean"

    def _build_voices_config(self) -> Dict[str, Any]:
        """tts_config.yaml의 voices를 EasyTTS VoiceConfig 형식으로 변환

        EasyTTS VoiceConfig 형식:
        - name: 음성 이름
        - sovits_path: SoVITS 모델 경로 (.ckpt)
        - reference_audio: 레퍼런스 오디오 경로
        - reference_text: 레퍼런스 텍스트
        - description: 설명
        """
        # tts_config.yaml에 voices가 없으면 EasyTTS의 자동 감지 사용
        if not self._voices_config:
            return {}

        paths = TTS_CONFIG.get("paths", {})
        models_dir = paths.get("models_dir", "../models")

        # models_dir은 SOVITS_PATH 기준 상대 경로
        models_path = SOVITS_PATH / models_dir

        # VoiceConfig 임포트 (easy_tts 로드 후에만 가능)
        from easy_tts.config import VoiceConfig

        voices = {}
        for name, cfg in self._voices_config.items():
            # tts_config.yaml의 경로는 models_dir 기준 상대 경로
            sovits_model = cfg.get("sovits_model", "")
            ref_audio = cfg.get("ref_audio", "")

            voices[name] = VoiceConfig(
                name=name,
                sovits_path=str(models_path / sovits_model) if sovits_model else "",
                reference_audio=str(models_path / ref_audio) if ref_audio else "",
                reference_text=cfg.get("ref_text", ""),
                description=cfg.get("description", name),
                language=cfg.get("language") or self._infer_language(name),
            )

        return voices

    def _warmup_generate(self, text: str):
        """워밍업용 음성 생성 (결과 버림)"""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        original_cwd = os.getcwd()
        os.chdir(SOVITS_PATH)

        try:
            self.tts_engine.generate(
                text=text,
                voice=self.default_voice,
                output_path=temp_path,
                verbose=False
            )
        finally:
            os.chdir(original_cwd)
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def generate(self, text: str, voice: str = None, language: str = None) -> bytes:
        """텍스트를 음성으로 변환 (캐시 지원)"""
        if not self._loaded:
            self.load()

        voice = voice or self.default_voice
        cache_key = f"{voice}:{language or 'auto'}:{text}"

        # 캐시 확인
        if cache_key in self._cache:
            print(f"📦 캐시 히트: \"{text[:20]}...\"")
            return self._cache[cache_key]

        start = time.time()

        # 임시 파일에 생성
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        # GPT-SoVITS 작업 디렉토리로 변경 (모델 경로 문제 해결)
        original_cwd = os.getcwd()
        os.chdir(SOVITS_PATH)

        try:
            # 기존 generate 메소드 사용
            output_path = self.tts_engine.generate(
                text=text,
                voice=voice,
                output_path=temp_path,
                language=language,
                verbose=False
            )

            # 파일 읽어서 반환
            with open(output_path, "rb") as f:
                audio_bytes = f.read()

            elapsed = time.time() - start
            print(f"🔊 생성 완료: \"{text[:20]}...\" ({elapsed:.2f}초)")

            # 캐시에 저장
            if len(self._cache) >= self._cache_size:
                # 가장 오래된 항목 제거
                oldest = self._cache_order.pop(0)
                del self._cache[oldest]
            self._cache[cache_key] = audio_bytes
            self._cache_order.append(cache_key)

            return audio_bytes
        finally:
            # 작업 디렉토리 복원
            os.chdir(original_cwd)
            # 임시 파일 삭제
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def list_voices(self):
        """사용 가능한 음성 목록"""
        if not self._loaded:
            self.load()
        return list(self.tts_engine.config.voices.keys())

    def get_voice_info(self, voice: str) -> Optional[Dict]:
        """특정 음성의 설정 정보"""
        return self._voices_config.get(voice)


# ========== FastAPI 앱 ==========

app = FastAPI(title="GPT-SoVITS TTS Server")

# CORS 설정 (웹 프론트엔드에서 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 origin 허용 (개발용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

server = TTSServer()


@app.on_event("startup")
async def startup():
    """서버 시작 시 모델 미리 로드"""
    server.load()


@app.post("/tts")
async def tts(request: TTSRequest):
    """텍스트를 음성으로 변환"""
    try:
        audio_bytes = server.generate(request.text, request.voice, language=request.language)
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"}
        )
    except Exception as e:
        import traceback
        print(f"❌ TTS 에러: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices")
async def voices():
    """사용 가능한 음성 목록"""
    voice_list = server.list_voices()
    voice_info = {v: server.get_voice_info(v) for v in voice_list}
    return {
        "voices": voice_list,
        "default": server.default_voice,
        "info": voice_info
    }


@app.get("/health")
async def health():
    """서버 상태 확인"""
    return {
        "status": "ok",
        "loaded": server._loaded,
        "default_voice": server.default_voice,
        "config_path": str(FRIDAY_PATH / "tts_config.yaml")
    }


@app.get("/config")
async def get_config():
    """현재 TTS 설정 반환"""
    return {
        "sovits_path": str(SOVITS_PATH),
        "config": TTS_CONFIG
    }


# ========== 메인 ==========

def main():
    parser = argparse.ArgumentParser(description="GPT-SoVITS TTS Server")
    # **기본은 루프백이다.** 0.0.0.0 은 집 LAN 에까지 열린다 — 이 서버에는 인증이
    # 없으므로 밖에서 붙일 때는 주소를 명시해서 좁힌다 (예: Tailscale 주소).
    parser.add_argument("--host", default="127.0.0.1", help="바인딩 주소 (기본: 루프백)")
    parser.add_argument("--port", type=int, default=9880, help="포트")
    parser.add_argument("--voice", default=None, help="기본 음성 (tts_config.yaml 우선)")
    args = parser.parse_args()

    if args.voice:
        server.default_voice = args.voice

    print("=" * 50)
    print("  GPT-SoVITS TTS Server for FRIDAY")
    print("=" * 50)
    print(f"  주소: http://{args.host}:{args.port}")
    print(f"  기본 음성: {server.default_voice}")
    print(f"  SoVITS 경로: {SOVITS_PATH}")
    print(f"  설정 파일: {FRIDAY_PATH / 'tts_config.yaml'}")
    print("=" * 50)

    # 설정된 음성 목록
    if TTS_CONFIG.get("voices"):
        print("  📢 설정된 음성:")
        for name in TTS_CONFIG["voices"]:
            print(f"      - {name}")
        print("=" * 50)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
