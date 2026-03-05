# BuildableRegionGenrator

정북사선 기준의 기준선/건축가능영역 계산 및 SHP 배치 처리를 위한 프로젝트입니다.

## 코드 컨벤션

### 1) 함수 설명 주석(필수)
- 모든 함수/메서드는 본문 시작에 **한 줄 설명 도큐스트링**을 작성합니다.
- 형식 예시:
  - `"""주어진 높이에서 buildable boundary를 계산한다."""`

### 2) 타입 표기 방식(통일)
- 프로젝트의 타입 표기는 **`# type:` 주석 방식**으로 통일합니다.
- 함수 시그니처에 인라인 타입힌트(`def f(x: int) -> str`)를 새로 추가하지 않습니다.
- 형식 예시:
  - `def func(x):`
  - `    # type: (int) -> str`

### 3) 상수 관리
- 정책/법규/기본값 상수는 **`src/constants.py`에서만 관리**합니다.
- 다른 파일에서는 상수를 직접 정의하지 않고 `constants.상수명`으로 참조합니다.

### 4) 입력 검증 원칙
- 필수 입력 누락 시 자동 보정하지 않고 즉시 `ValueError`를 발생시킵니다.
- 우회 로직(`hasattr` fallback, 임의 default 주입)은 지양합니다.

## 실행 개요
- Grasshopper 엔트리: `src/main.py`
- 정북사선 계산기: `src/northsky.py`
- SHP 배치 처리: `src/shp_northsky_batch.py`
- SHP 로딩/선택: `src/shp_to_lot.py`
- 공통 유틸: `src/utils.py`
- 공통 상수: `src/constants.py`
