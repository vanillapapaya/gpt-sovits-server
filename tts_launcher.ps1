#Requires -Version 5.1
<#
    GPT-SoVITS TTS 서버 런처. `TtsServer.cmd` 가 이 파일을 부른다.

    **이 런처는 설치를 대신해 주지 않는다.** MangaLiveReader 쪽 런처는 필요한 것을
    전부 받아 올 수 있지만 여기는 못 한다 — GPT-SoVITS 본체는 그쪽 설치 절차를
    따라야 하고, 음색 가중치는 각자 학습한 것이며, `tts_config.yaml` 은 참조 음성과
    그 음성의 정확한 받아쓰기가 있어야 채울 수 있다. 자동으로 구할 수 있는 것이
    하나도 없다.

    그래서 하는 일은 셋이다:

      1. 무엇이 없는지 짚어 주고 무엇을 해야 하는지 정확히 적어 준다
      2. 자동으로 할 수 있는 것만 한다 (서버 의존성 설치, 설정 파일 초안 복사)
      3. 다 갖춰졌으면 띄운다

    **이 파일은 UTF-8 BOM 으로 저장한다.** PowerShell 5.1 은 BOM 이 없으면 한글을
    cp949 로 읽어 깨진다.

    놓이는 자리는 GPT-SoVITS 체크아웃 안, `tts_server.py` 옆이다.
#>

param(
    # tts_server.py 로 그대로 넘긴다 (--host, --port, --voice).
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Passthrough
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = 'GPT-SoVITS TTS Server'

$Py         = Join-Path $Root '.venv\Scripts\python.exe'
$Server     = Join-Path $Root 'tts_server.py'
$Config     = Join-Path $Root 'tts_config.yaml'
$ConfigEx   = Join-Path $Root 'tts_config.example.yaml'
$Reqs       = Join-Path $Root 'requirements.txt'
$Pretrained = Join-Path $Root 'GPT_SoVITS\pretrained_models'

$script:StepNo = 0

function Step($text) {
    $script:StepNo++
    Write-Host ''
    Write-Host ("[{0}/4] {1}" -f $script:StepNo, $text) -ForegroundColor Cyan
}
function Ok($text)   { Write-Host "      $text" -ForegroundColor DarkGray }
function Warn($text) { Write-Host "  !   $text" -ForegroundColor Yellow }

function Die($text) {
    Write-Host ''
    Write-Host "  X   $text" -ForegroundColor Red
    Write-Host ''
    Read-Host '  엔터를 누르면 창이 닫힙니다' | Out-Null
    exit 1
}

Write-Host ''
Write-Host '  GPT-SoVITS TTS Server' -ForegroundColor White
Write-Host '  ─────────────────────' -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# 1. GPT-SoVITS
#
# 이 서버는 독립 패키지가 아니라 GPT-SoVITS 의 venv 안에서 도는 껍데기다.
# 추론 의존성(torch, librosa, transformers …)은 그쪽이 이미 깔아 두었다는 전제다.
# ---------------------------------------------------------------------------
Step 'GPT-SoVITS 확인'

if (-not (Test-Path $Server)) {
    Die @"
같은 폴더에 tts_server.py 가 없습니다.

이 런처는 GPT-SoVITS 체크아웃 안에 tts_server.py 와 나란히 놓여야 합니다.
지금 자리: $Root
"@
}

if (-not (Test-Path $Py)) {
    Die @"
GPT-SoVITS 의 파이썬 환경이 없습니다: .venv\Scripts\python.exe

이 서버는 GPT-SoVITS 안에서 도는 껍데기라 본체를 먼저 깔아야 합니다.
런처가 대신 해 줄 수 없는 부분입니다:

  1. https://github.com/RVC-Boss/GPT-SoVITS 를 받아서 그쪽 안내대로 설치
  2. 사전학습 모델을 GPT_SoVITS\pretrained_models\ 에 넣기
  3. 이 파일들을 그 폴더로 옮기고 다시 실행

자세한 것은 README 의 「설치 — 네 단계」.
"@
}
Ok "파이썬 환경 있음"

if (-not (Test-Path $Pretrained)) {
    Warn 'GPT_SoVITS\pretrained_models\ 가 안 보입니다.'
    Ok '사전학습 모델이 없으면 기동 중에 실패합니다 (GPT-SoVITS README 참조).'
} else {
    Ok '사전학습 모델 폴더 있음'
}

# ---------------------------------------------------------------------------
# 2. 서버 의존성 — 여기는 자동으로 할 수 있다
# ---------------------------------------------------------------------------
Step '서버 의존성'

& $Py -c "import fastapi, uvicorn, yaml, dotenv, soundfile, scipy" 2>$null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path $Reqs)) {
        Die @"
서버 의존성이 없는데 requirements.txt 도 없습니다.

파일을 옮길 때 requirements.txt 를 빠뜨린 것 같습니다. 저장소에서 다시 받아
이 폴더에 놓고 실행하세요.
"@
    }
    Ok '없음 → 받습니다 (작습니다. 추론 의존성은 GPT-SoVITS 것을 그대로 씁니다)'
    & $Py -m pip install -r $Reqs
    if ($LASTEXITCODE -ne 0) { Die "의존성 설치에 실패했습니다 (종료 코드 $LASTEXITCODE)." }
} else {
    Ok '있음'
}

# ---------------------------------------------------------------------------
# 3. 음색 설정
#
# 초안 복사까지가 자동으로 할 수 있는 전부다. 참조 음성과 그 받아쓰기는 사람이
# 넣어야 하고, 그것이 틀리면 품질이 눈에 띄게 나빠진다.
# ---------------------------------------------------------------------------
Step '음색 설정'

if (-not (Test-Path $Config)) {
    if (-not (Test-Path $ConfigEx)) {
        Die 'tts_config.yaml 도 tts_config.example.yaml 도 없습니다. 저장소에서 다시 받으세요.'
    }
    Copy-Item $ConfigEx $Config
    Write-Host ''
    Warn 'tts_config.yaml 을 예시에서 만들었습니다. 그대로는 못 씁니다.'
    Write-Host ''
    Write-Host '  둘 중 하나를 하세요:' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '    ① 자동 감지 — tts_config.yaml 의 voices 절을 통째로 지우고,'
    Write-Host '       음색을 models\<분류>\<음색>\ 두 단계로 넣습니다:'
    Write-Host ''
    Write-Host '         models\mygo\anon_jp\anon-e8.ckpt        SoVITS 가중치'
    Write-Host '         models\mygo\anon_jp\reference.wav       참조 음성 3-10초'
    Write-Host '         models\mygo\anon_jp\reference_text.txt  그 음성의 받아쓰기'
    Write-Host ''
    Write-Host '    ② 직접 적기 — 예시 그대로 두고 경로·이름을 내 것으로 고칩니다'
    Write-Host ''
    Write-Host "  파일: $Config" -ForegroundColor White
    Write-Host ''
    $ans = Read-Host '  지금 열까요? (Y/n)'
    if (-not ($ans -and $ans.Trim().ToLower().StartsWith('n'))) {
        Start-Process notepad.exe $Config
    }
    Write-Host ''
    Read-Host '  고치고 저장한 뒤 엔터' | Out-Null
} else {
    Ok 'tts_config.yaml 있음'
}

# 예시를 그대로 둔 채 띄우면 없는 파일을 가리켜 기동에서 실패한다. 미리 짚는다.
if ((Get-Content $Config -Raw) -match 'example-jp|example-ko') {
    Warn 'tts_config.yaml 에 예시 음색(example-jp / example-ko)이 그대로 남아 있습니다.'
    Ok '그 경로에 파일이 없으면 기동하다 실패합니다. 자동 감지를 쓰려면 voices 절을 비우세요.'
}

# ---------------------------------------------------------------------------
# 4. 띄우기
# ---------------------------------------------------------------------------
Step '기동'
Ok '모델을 올리는 동안 1-3분 걸립니다. 그 뒤로는 상주합니다.'
Ok '기본 바인딩은 루프백입니다 — 다른 기기에서 쓰려면 --host 로 주소를 좁혀 여세요.'
Write-Host ''

$serverArgs = @('-X', 'utf8', $Server)
if ($Passthrough) { $serverArgs += $Passthrough }
& $Py @serverArgs
$code = $LASTEXITCODE

Write-Host ''
if ($code -ne 0) {
    Write-Host "  서버가 종료됐습니다 (코드 $code)." -ForegroundColor Yellow
} else {
    Write-Host '  서버가 종료됐습니다.' -ForegroundColor DarkGray
}
Read-Host '  엔터를 누르면 창이 닫힙니다' | Out-Null
