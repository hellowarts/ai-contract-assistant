# AI Contract Assistant

공공기관 계약 업무를 지원하는 CLI 기반 AI 보조 도구입니다. 계약 내용을 입력하면 계약 분석, 규정 판단, 제출서류 확인, 체크리스트, 최종 보고서 생성을 수행합니다.

## 1) 보안 주의사항 (필수)

- 실제 API 키는 절대 GitHub에 커밋하지 마세요.
- 이 저장소는 `.env`를 무시하도록 설정되어 있습니다.
- API 키는 로컬 `.env` 파일에만 넣어 사용하세요.

## 2) 사전 준비

- 운영체제: Windows/macOS/Linux
- Python: 3.10 이상 권장
- OpenAI API Key

## 3) 설치 방법

프로젝트 루트에서 아래 순서로 실행하세요.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

PowerShell에서 아래 오류가 나면 실행 정책 때문에 활성화 스크립트가 차단된 상태입니다.

- 예: `Activate.ps1 : 이 시스템에서 스크립트를 실행할 수 없으므로 ...`

해결 방법 1 (권장, 현재 터미널 세션에만 적용):

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

해결 방법 2 (현재 사용자 범위에 영구 적용):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

활성화 없이도 설치/실행은 가능합니다:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python app/cli.py
```

### macOS / Linux (bash/zsh)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4) API 키 설정 방법

1. `.env.example` 파일을 참고해 `.env` 파일을 만듭니다.
2. `.env`에 본인 키를 입력합니다.

예시:

```env
OPENAI_API_KEY=sk-your-real-key
```

## 5) 프로그램 실행 방법

프로젝트 루트에서 실행:

```bash
python app/cli.py
```

실행 후 콘솔에 계약 내용을 입력하면 결과 보고서가 출력됩니다.
