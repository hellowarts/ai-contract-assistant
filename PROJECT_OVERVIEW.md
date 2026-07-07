# AI Contract Assistant 프로젝트 개요

## 1. 프로젝트 목적
이 프로젝트는 공공기관 계약 업무를 지원하기 위한 AI 기반 보조 도구다. 사용자가 계약 내용을 입력하면 계약 분석, 규정 판단, 제출서류 확인, 체크리스트 정리, 최종 보고서 생성을 한 번에 수행한다.

## 2. 주요 기능
- 계약 문장에서 계약유형, 계약상대자, 계약금액, 계약기간, 계약방식, 사업명, 위험요소를 추출한다.
- 규정 지식베이스를 조회해 계약 내용과 관련 조항을 연결하고 판단 근거를 정리한다.
- 제출서류 지식베이스를 검색해 필요한 문서를 도출한다.
- 체크리스트를 생성해 필수 확인 항목과 추가 확인 항목을 구분한다.
- 최종 응답은 AI가 작성하며, 실무 보고서 형식으로 출력한다.

## 3. 실행 흐름
1. `app/cli.py`에서 사용자의 계약 입력을 받는다.
2. `WorkflowEngine`가 전체 워크플로우를 실행한다.
3. `ContractAnalyzer`가 계약 정보를 구조화한다.
4. `RegulationAgent`가 KB-001을 기준으로 규정 판단과 근거를 만든다.
5. `DocumentAgent`가 KB-002~KB-005를 바탕으로 제출서류를 찾는다.
6. `ChecklistAgent`가 확인 항목을 생성한다.
7. `OutputFormatter`와 최종 프롬프트를 사용해 AI 최종 보고서를 만든다.

## 4. 핵심 구성 요소

### 진입점
- `app/cli.py`: 콘솔에서 계약 내용을 입력받고 최종 결과를 출력한다.

### 워크플로우
- `app/core/workflow_engine.py`: 전체 순서를 조율하고 최종 응답을 생성한다.
- `app/core/workflow_state.py`: 계약, 규정, 문서, 체크리스트, 근거, 로그를 저장하는 상태 객체다.
- `app/agents/supervisor.py`: 현재 어떤 단계가 완료되었는지 추적한다.

### 계약 분석
- `app/agents/contract_analyzer.py`: LLM과 정규식을 함께 사용해 계약 정보를 추출한다.
- 추출 항목에는 `contract_type`, `vendor`, `amount`, `title`, `business_name`, `task_scope`, `task_content`, `risk_factors`, `contract_start`, `contract_end`, `contract_method`가 포함된다.

### 규정 판단
- `app/agents/regulation_agent.py`: KB-001 문서를 조회해 규정 판단을 만든다.
- 위험요소와 계약 정보를 키워드로 변환해 관련 조항의 근거를 찾는다.
- `state.regulation`, `state.evidence`, `state.logs`를 갱신한다.

### 제출서류 검색
- `app/agents/document_agent.py`: KB-002~KB-005에서 제출서류 관련 내용을 찾는다.
- 벡터 검색이 가능하면 Chroma 기반 검색을 사용하고, 실패하면 대체 검색을 수행한다.

### 체크리스트
- `app/agents/checklist_agent.py`: 계약 정보와 규정 판단, 제출서류 결과를 바탕으로 점검 항목을 만든다.

### 출력 형식
- `app/agents/output_formatter.py`: 계약 분석, 규정 판단, 근거, 제출서류, 체크리스트, 최종 검토를 보기 좋게 정리한다.
- `prompts/final_response_prompt.md`: AI가 최종 보고서를 작성할 때 사용하는 템플릿이다.

## 5. 지식베이스와 데이터
- `app/kb/KB-001.pdf`~`KB-005.xlsx`를 기준 지식으로 사용한다.
- `KB-001`은 규정 판단용, `KB-002`~`KB-005`는 제출서류 확인용으로 사용된다.
- 벡터 저장소는 `data/chroma`에 생성된다.

## 6. 환경과 의존성
필수 라이브러리는 `requirements.txt`에 정의되어 있다.

- `langchain`, `langchain-community`, `langchain-openai`, `langchain-chroma`
- `chromadb`
- `openai`
- `python-dotenv`
- `pypdf`
- `pandas`, `openpyxl`
- `rich`

## 7. 실행 조건
- `OPENAI_API_KEY`가 설정되어 있어야 한다.
- `app/core/llm_client.py`는 OpenAI API 키 형식을 검사하고, `gpt-5` 모델을 사용한다.
- API 키가 없거나 유효하지 않으면 워크플로우 실행이 중단된다.

## 8. 출력 결과의 특징
- 최종 출력은 실무 보고서 스타일의 한국어 문서 형식이다.
- 계약 내용과 규정 판단을 직접 연결해 설명한다.
- Evidence에는 핵심 근거만 포함한다.
- 제출서류와 체크리스트는 가능한 한 누락 없이 정리한다.

## 9. 참고 메모
- 현재 코드 구조는 `app/` 아래 모듈들이 `agents.*`, `core.*`처럼 최상위 패키지로 import되는 형태다.
- 콘솔 입력 기반 CLI이므로 별도 웹 UI는 없다.