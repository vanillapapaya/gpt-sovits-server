# GPT-SoVITS TTS Server

GPT-SoVITS 에 **얇은 HTTP 껍데기**를 씌운다. 목소리를 이름 하나로 고르고, 모델은
미리 올려 둔 채로 재사용한다.

```
POST /tts   {"text": "こんにちは", "language": "Japanese", "voice": "anon-jp"}
            → WAV 바이트
GET  /voices → 설정에 적어 둔 목소리 목록
```

stock GPT-SoVITS 의 `api_v2.py` 와 다른 점은 하나다 — **음색을 이름으로 고른다.**
가중치·참조 음성·참조 텍스트를 YAML 한 장에 적어 두면 요청은 이름만 보낸다.

[Manga Live Reader](https://github.com/vanillapapaya/MangaLiveReader) 가 이 계약을
쓴다. 그 확장 옵션 화면에 이 서버 주소를 넣으면 만화 원문을 이 목소리로 읽는다.

**모델은 이 저장소에 없다.** 음색은 각자 학습하거나 구해서 넣는다.

---

## 빠른 시작

GPT-SoVITS 가 이미 돌고 있다는 전제다 (없으면 아래 「처음부터」).

```bash
# 1. GPT-SoVITS 체크아웃 안에 이 저장소 파일을 둔다
cd ~/GPT-SoVITS
git clone https://github.com/vanillapapaya/gpt-sovits-tts-server tmp && \
  mv tmp/tts_server.py tmp/easy_tts tmp/*.example* . && rm -rf tmp

# 2. GPT-SoVITS 의 venv 안에 서버 의존성만 더 깐다
.venv/bin/pip install fastapi uvicorn pyyaml python-dotenv

# 3. 음색을 적는다
cp tts_config.example.yaml tts_config.yaml && $EDITOR tts_config.yaml

# 4. 띄운다
.venv/bin/python tts_server.py
```

```bash
curl -s localhost:9880/voices | head -c 200
curl -s -X POST localhost:9880/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"테스트입니다"}' -o test.wav && ls -l test.wav
```

`test.wav` 가 재생되면 끝이다.

## 처음부터

### 1. GPT-SoVITS

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS
cd GPT-SoVITS
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

사전학습 모델을 받는다 (그쪽 README 참조 — `GPT_SoVITS/pretrained_models/` 에
들어간다). NVIDIA GPU 를 권한다.

### 2. 음색 준비

음색 하나에 필요한 것은 셋이다:

| | |
|---|---|
| SoVITS 가중치 | 학습 산출물 `.ckpt` |
| GPT 가중치 | 학습 산출물 `.pth`. 없으면 사전학습본을 쓴다 |
| 참조 음성 | **3-10초** 짜리 `.wav` 와 그 안에서 말하는 내용(`ref_text`) |

`ref_text` 가 실제 발화와 다르면 품질이 눈에 띄게 나빠진다 — 받아쓰기를 정확히 할 것.

`tts_config.yaml` 의 `paths.models_dir` 아래에 폴더로 정리한다:

```
models/
  myvoice/
    jp/
      model-e8.ckpt
      model_e10.pth
      reference.wav
```

`voices` 를 아예 비워 두면 `models_dir` 을 훑어 **자동으로 감지**한다
(`easy_tts/config.py`). 이름을 직접 붙이고 설명을 달려면 YAML 에 적는 편이 낫다.

### 3. 서버

```bash
cp .env.example .env      # GPT-SoVITS 체크아웃 밖에 뒀을 때만 필요하다
.venv/bin/python tts_server.py --port 9880
```

## 상시 띄우기

`tts.service.example` 을 `~/.config/systemd/user/tts.service` 로 복사해 경로를 고친다.

```bash
systemctl --user enable --now tts
loginctl enable-linger $USER      # 이걸 빠뜨리면 재부팅 후 안 뜬다
journalctl --user -u tts -f
```

## API

| | | |
|---|---|---|
| `POST /tts` | `{"text": "…", "language": "Japanese"\|"Korean", "voice": "이름"}` | WAV 바이트 |
| `GET /voices` | | `{"voices": [...], "default": "…", "info": {...}}` |
| `GET /health` | | 로드 상태·기본 음색 |
| `GET /config` | | 지금 물고 있는 설정 |

`text` 만 필수다. `voice` 를 빼면 `default_voice`, `language` 를 빼면 그 음색에 적어
둔 언어를 쓴다.

같은 (음색·언어·문장) 조합은 **메모리에 캐시한다** (기본 50개). 같은 대사를 다시
읽을 때 합성을 건너뛴다.

## 성능 (RTX 5080, 일본어 실측)

| 원문 글자 | 합성 | 오디오 길이 |
|---|---|---|
| 8 | 0.6초 | 1.5초 |
| 18 | 0.8초 | 3.1초 |
| 40 | 1.9초 | 7.6초 |

**RTF 0.25** — 재생이 합성보다 4배 느리다. 그래서 지금 것을 재생하는 동안 다음 것을
미리 합성해 두면 문장 사이가 끊기지 않는다 (한 칸만 앞서면 충분하다).

첫 요청은 모델 로드 때문에 느리다. 음색을 **바꿀 때도** 가중치를 다시 올린다.

## 열어 둘 때 주의

**인증이 없다.** 그리고 CORS 가 `allow_origins=["*"]` 라 브라우저에서 아무 페이지나
부를 수 있다. 그래서 기본 바인딩을 **루프백**으로 두었다.

다른 기기에서 쓰려면 주소를 좁혀서 연다:

```bash
python tts_server.py --host 100.x.y.z      # 예: Tailscale 주소
```

`0.0.0.0` 은 집 LAN 에까지 열린다는 뜻이다 — 인증이 없는 서버에는 권하지 않는다.
인터넷에 열 것이면 앞단에 인증 프록시를 둔다.

## 무엇이 들어 있나

```
tts_server.py             FastAPI 서버. 설정 로드·캐시·음색 전환
easy_tts/                 GPT-SoVITS 추론 래퍼
  engine.py               합성 본체
  config.py               음색 설정 · models_dir 자동 감지
  emotions.py, parser.py  문장 분해와 감정 태그
tts_config.example.yaml   음색 설정 예시
tts.service.example       systemd 유닛 예시
```

## 라이선스

코드는 **MIT** (`LICENSE`). GPT-SoVITS 본체와 사전학습 모델, 그리고 각자 넣는 음색
가중치는 **각자의 라이선스를 따른다** — 이 저장소는 그중 어느 것도 재배포하지 않는다.

목소리를 학습해 쓰는 일에는 원 화자의 권리가 걸린다. 판단은 쓰는 사람 몫이다.
