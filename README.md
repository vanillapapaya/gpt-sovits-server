# GPT-SoVITS TTS Server

GPT-SoVITS 에 얇은 HTTP 껍데기를 씌운다. **음색을 이름 하나로 고른다**. 그게
stock `api_v2.py` 와 다른 전부다.

```
POST /tts   {"text": "こんにちは", "language": "Japanese", "voice": "anon-jp"}
            → WAV 바이트
GET  /voices → 설정에 적어 둔 목소리 목록
```

가중치·참조 음성·참조 텍스트를 YAML 한 장에 적어 두면 요청은 이름만 보낸다.
`api_v2.py` 는 요청마다 `ref_audio_path` 와 `prompt_text` 를 들려 보내야 하고
`/voices` 도 없다. 클라이언트가 모델 사정을 알아야 하는 구조라서 껍데기를 씌웠다.

모델은 **기동 때 한 번 올려 두고 재사용한다.** 요청마다 올리면 첫 문장이 수십 초다.

[Manga Live Reader](https://github.com/vanillapapaya/MangaLiveReader) 가 이 계약을
쓴다. 확장 옵션 화면에 이 서버 주소를 넣으면 만화 원문을 이 목소리로 읽는다.

**음색 모델은 이 저장소에 없다.** 각자 학습하거나 구해서 넣는다.

---

# 쓰기

**여기까지만 읽으면 띄울 수 있다.**

## 필요한 것

- **NVIDIA 그래픽카드.** CPU 로도 돌지만 실시간이 안 된다
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 체크아웃과 그 사전학습 모델
- **음색 하나에 파일 둘**: SoVITS 가중치(`.ckpt`)와 참조 음성(`.wav` 3-10초)

이 서버는 독립 패키지가 아니다. **GPT-SoVITS 의 venv 안에서 도는 껍데기**라
추론 의존성(torch, librosa, transformers …)은 그쪽이 이미 깔아 준다.

## 설치 — 네 단계

### 1. GPT-SoVITS (이미 있으면 건너뛴다)

```bash
git clone https://github.com/RVC-Boss/GPT-SoVITS
cd GPT-SoVITS
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

사전학습 모델은 그쪽 README 를 따라 받는다 (`GPT_SoVITS/pretrained_models/` 에
들어간다).

### 2. 이 서버 얹기

```bash
cd ~/GPT-SoVITS
git clone https://github.com/vanillapapaya/gpt-sovits-server tmp && \
  mv tmp/tts_server.py tmp/easy_tts tmp/requirements.txt \
     tmp/TtsServer.cmd tmp/tts_launcher.ps1 \
     tmp/*.example* tmp/.env.example . && rm -rf tmp

.venv/bin/pip install -r requirements.txt
```

`requirements.txt` 에는 **서버가 추가로 쓰는 것만** 있다. 추론 의존성은 GPT-SoVITS
쪽이 이미 깔아 두었으므로 다시 깔지 않는다.

체크아웃 **밖에** 두고 싶을 때만 `cp .env.example .env` 하고 `SOVITS_PATH` 를 적는다.

### 3. 음색 넣기

`models/` 아래에 **`분류/음색` 두 단계**로 넣으면 알아서 찾는다:

```
models/                          ← GPT-SoVITS 체크아웃 옆
  mygo/                          ← 분류 (아무 이름이나)
    anon_jp/                     ← 음색 하나 = 폴더 하나
      anon-e8.ckpt               ← SoVITS 가중치
      reference.wav              ← 참조 음성 3-10초
      reference_text.txt         ← 그 음성에서 실제로 말하는 내용 (UTF-8)
```

폴더 이름 끝의 `_jp`·`_cn`·`_en` 으로 언어를 알아낸다 (그 밖은 한국어).

**참조 텍스트가 실제 발화와 다르면 품질이 눈에 띄게 나빠진다.** 받아쓰기를 정확히
할 것. 이름과 설명을 직접 정하고 싶으면 [아래](#음색을-yaml-로-직접-적기).

### 4. 띄우기

```bash
cp tts_config.example.yaml tts_config.yaml   # 자동 감지만 쓸 거면 voices 를 비워 둔다
.venv/bin/python tts_server.py
```

윈도우면 **`TtsServer.cmd` 를 더블클릭**해도 된다. 무엇이 없는지 짚어 주고, 서버
의존성 설치와 `tts_config.yaml` 초안 복사는 알아서 한다. **설치를 대신해 주지는
않는다**. GPT-SoVITS 본체·음색 가중치·참조 음성은 자동으로 구할 수 있는 것이
하나도 없어서, 무엇을 해야 하는지 적어 주는 데까지가 전부다.

**기동에 1-3분 걸린다** (모델 로드). 그 뒤로는 상주한다.

## 확인

```bash
curl -s localhost:9880/voices          # 음색이 목록에 뜨는가
curl -s -X POST localhost:9880/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"테스트입니다"}' -o test.wav && ls -l test.wav
```

`test.wav` 가 재생되면 끝이다.

## 안 될 때

| 증상 | 원인 |
|---|---|
| `/voices` 가 비었다 | `models_dir` 경로가 틀렸거나 `분류/음색` 두 단계가 아니다 |
| 음색이 하나만 안 뜬다 | 그 폴더에 `*.ckpt` 가 없거나 참조 `.wav` 를 못 찾았다 (둘 다 있어야 등록된다) |
| 목소리는 나오는데 안 닮았다 | 참조 음성이 너무 짧거나 잡음이 섞였다. 3-10초 깨끗한 한 문장으로 |
| 발음이 뭉개진다 | `ref_text` 가 참조 음성과 다르다 |
| 음색 바꾼 첫 요청이 느리다 | 정상이다. 가중치를 다시 올린다 (두 번째부터 정상 속도) |
| 기동이 1-3분 걸린다 | 정상이다 (모델 로드) |

`curl -s localhost:9880/config` 로 서버가 실제로 물고 있는 경로를 볼 수 있다.
기동 로그에도 설정된 음색 이름이 그대로 찍힌다.

## 상시 띄우기

`tts.service.example` 을 `~/.config/systemd/user/tts.service` 로 복사해 경로를 고친다.

```bash
systemctl --user enable --now tts
loginctl enable-linger $USER      # 이걸 빠뜨리면 재부팅 후 안 뜬다
journalctl --user -u tts -f
```

## 열어 둘 때 주의

**인증이 없다.** 그리고 CORS 가 `allow_origins=["*"]` 라 브라우저에서 아무 페이지나
부를 수 있다. 그래서 기본 바인딩을 **루프백**으로 두었다.

다른 기기에서 쓰려면 주소를 좁혀서 연다:

```bash
python tts_server.py --host 100.x.y.z      # 예: Tailscale 주소
```

`0.0.0.0` 은 집 LAN 에까지 열린다는 뜻이다. 인증이 없는 서버에는 권하지 않는다.
인터넷에 열 것이면 앞단에 인증 프록시를 둔다.

---

# 더 하기

## 음색을 YAML 로 직접 적기

`/voices` 목록에 보일 이름과 설명을 통제하려면 이쪽이다:

```yaml
default_voice: "anon-jp"

voices:
  anon-jp:
    sovits_model: "mygo/anon_jp/anon-e8.ckpt"     # models_dir 기준 상대 경로
    ref_audio: "mygo/anon_jp/reference.wav"
    ref_text: "参考音声で実際に話している内容をそのまま書く"
    language: "Japanese"
    description: "확장 옵션 화면에 보일 설명"

paths:
  models_dir: "../models"
  pretrained_gpt: "GPT_SoVITS/pretrained_models/s1v3.ckpt"
```

`voices` 를 하나라도 적으면 자동 감지는 **쓰지 않는다**. 전부 적어야 한다.

<details>
<summary>자동 감지가 파일을 찾는 규칙</summary>

이름은 폴더 이름에서 `_ko`·`_kr` 을 뗀 것이고, 언어는 폴더 이름으로 추론한다:

| 폴더 이름에 | 언어 |
|---|---|
| `_jp` · `_ja` | Japanese |
| `_cn` · `_zh` | Chinese |
| `_en` | English |
| 그 밖 | Korean |

참조 음성은 이 순서로 찾는다 (`config.py:106`):

```
reference_audios/**/default_reference.wav
reference_audios/**/*.wav
references/**/*.wav
*.wav
```

참조 텍스트는 `reference_text.txt` 를 읽고, 없으면 참조 음성 **파일 이름**에서 뽑는다
(5자 이하면 `"레퍼런스 텍스트"` 로 떨어진다. 품질이 나빠지니 파일을 넣는 편이 낫다).

가중치는 `*.ckpt` 중 첫 번째를 집는다 (`config.py:71`). `.ckpt` 와 `.pth` 가
헷갈리기 쉬운데, 이 서버는 `sovits_model` 에 적은 파일을
`change_sovits_weights()` 에 그대로 넘긴다. 학습 산출물의 이름이 다르면 YAML 에
경로를 직접 적는다.

</details>

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

**RTF 0.25**: 재생이 합성보다 4배 느리다. 그래서 지금 것을 재생하는 동안 다음 것을
미리 합성해 두면 문장 사이가 끊기지 않는다 (한 칸만 앞서면 충분하다).

첫 요청은 모델 로드 때문에 느리다. 음색을 **바꿀 때도** 가중치를 다시 올린다.

---

# 안쪽

## 가중치를 다루는 방식

**GPT 가중치는 하나를 전부 공유하고, 음색마다 바꾸는 것은 SoVITS 가중치뿐이다.**

```
change_gpt_weights(paths.pretrained_gpt)   # 기동 때 한 번        engine.py:54
change_sovits_weights(voice.sovits_model)  # 음색을 고를 때마다   engine.py:72
```

그래서 음색 하나에 필요한 파일이 둘이다.

> `voices.*.gpt_model` 을 적어도 **지금 코드는 읽지 않는다** (`tts_server.py` 의
> `_build_voices_config` 가 `sovits_model`·`ref_audio`·`ref_text`·`description`·
> `language` 만 본다). 음색마다 GPT 가중치를 따로 쓰려면 코드를 고쳐야 한다.

## 무엇이 들어 있나

```
tts_server.py             FastAPI 서버. 설정 로드·캐시·음색 전환
easy_tts/                 GPT-SoVITS 추론 래퍼
  engine.py               합성 본체
  config.py               음색 설정 · models_dir 자동 감지
  emotions.py, parser.py  문장 분해와 감정 태그
tts_config.example.yaml   음색 설정 예시
tts.service.example       systemd 유닛 예시
TtsServer.cmd             윈도우 더블클릭 런처 (ASCII 전용 — cmd 가 cp949 로 읽는다)
tts_launcher.ps1          그 실제 내용. 전제 검사 · 의존성 설치 · 기동 (UTF-8 BOM)
```

## 라이선스

코드는 **MIT** (`LICENSE`). GPT-SoVITS 본체와 사전학습 모델, 그리고 각자 넣는 음색
가중치는 **각자의 라이선스를 따른다**. 이 저장소는 그중 어느 것도 재배포하지 않는다.

목소리를 학습해 쓰는 일에는 원 화자의 권리가 걸린다. 판단은 쓰는 사람 몫이다.
