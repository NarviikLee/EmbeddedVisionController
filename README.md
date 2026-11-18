# EmbeddedVisionController

OpenCV로 카메라 영상의 밝기를 분석하고, 밝기 상태가 바뀌면 시리얼 포트로 외부 장치에 전달하는 Python 프로젝트입니다. 중앙 영역의 평균 밝기에 이동평균과 히스테리시스를 적용해 `BRIGHT` 또는 `DARK` 상태를 판단합니다.

현재는 VMware Ubuntu 20.04에서 UVC 카메라의 사람 검출 결과를 UART로 NUCLEO-F401RE에 전달하고, PCA9685와 SG90 서보를 통해 PAN 좌우 추적을 수행합니다. 밝기 분석 기능도 별도 실행 경로로 유지합니다.

## 최근 업데이트 (2026-11-18)

- Raspberry Pi 4B 문제로 VMware Ubuntu 20.04 환경으로 전환
- Innomaker U20CAM-720P 연결 및 OpenCV 입력 `(480, 640, 3)` 확인
- Windows 보드 COM 포트 → VMware Serial Port → `/dev/ttyS0` 경로로 UART 송수신 확인
- 사람 검출 → 방향 판단 → UART → STM32 → PCA9685 → PAN 서보 전체 경로의 실제 추적 동작 확인
- 팬틸트 장착 방향에 맞춰 `cv2.flip(frame, -1)`로 영상 상하·좌우 보정
- 로컬 전용 `tests/`의 자동화 테스트 9개 통과 및 Git 추적 제외

하드웨어 확인 결과는 사용자가 직접 수행한 테스트를 기준으로 합니다. PAN 좌우 진동 안정화가 다음 우선순위이며, 영상 기반 TILT 추적은 아직 구현하지 않았습니다. 구성, 연결 문제 해결, 서보 보정값과 다음 작업은 [2026-11-18 작업 기록](docs/2026-11-18-pan-tracking.md)에 정리했습니다.

## 구현된 기능

- 카메라 프레임 읽기 및 중앙 ROI의 회색조 평균 밝기 계산
- 최근 최대 5개 밝기 값의 이동평균
- 이전 상태와 임계값을 이용한 히스테리시스 상태 판단
- 최초 판단 및 상태 변경 시 `STATE` 메시지 전송
- 시리얼 응답 한 줄 수신, 패킷 형식 검사 및 콘솔 출력
- 카메라 화면 표시, `q` 키 종료 및 자원 정리
- 영상 처리, 시리얼 통신, 패킷 파싱의 모듈별 수동 확인 코드
- EfficientDet Lite0 객체 검출, 결과 시각화, 사람 위치 기반 방향 판단 및 시리얼 전송

## 프로젝트 구조

```text
EmbeddedVisionController/
├── app/
│   └── main.py                 # 영상 처리와 통신을 연결하는 실행 코드
├── vision/
│   ├── camera_test.py          # 밝기 계산, 상태 판단, 카메라 단독 확인
│   └── detector.py             # 객체 검출 처리 및 좌우·중앙 방향 판단
├── communication/
│   ├── protocol.py             # UTF-8 패킷 생성과 파싱
│   └── serial_comm.py          # 시리얼 연결 및 송수신
├── models/
│   ├── efficientdet_lite0.tflite # 객체 검출 모델
│   └── coco_labels.txt          # COCO 클래스 라벨
├── scripts/
│   ├── inspect_model.py         # 모델 입력 텐서 정보 확인
│   └── test_input.py            # 사람 검출 및 TRACK 시리얼 전송
├── docs/
│   └── 2026-11-18-pan-tracking.md # 환경 변경 및 PAN 실동작 기록
├── firmware/                   # 현재 비어 있음
├── .gitignore
├── requirements.txt            # 기본 영상 처리 및 시리얼 통신 의존성
├── requirements-vision.txt     # 기본 의존성 + 객체 검출 의존성
└── README.md
```

빈 `firmware/` 디렉터리와 로컬 전용 `tests/`는 clone한 저장소에 포함되지 않습니다.

## 데이터 흐름

```text
카메라 프레임
    → 중앙 ROI 추출
    → 회색조 변환 및 평균 밝기 계산
    → 최근 최대 5개 값의 이동평균
    → BRIGHT / DARK 상태 판단
    → 최초 판단 또는 상태 변경 시 STATE 패킷 전송
    → 응답 한 줄 수신 및 콘솔 출력
    → 카메라 화면 표시 및 다음 프레임 처리
```

상태가 유지되면 송수신하지 않습니다. 메인 화면은 원본 프레임을 표시하며, 카메라 단독 실행에서는 상태와 필터링된 밝기도 영상 위에 표시합니다.

## Vision 처리

`calculate_brightness()`는 프레임의 가로·세로 각각 `1/4`부터 `3/4`까지의 중앙 영역을 선택합니다. 전체 면적의 약 25%인 ROI를 회색조로 변환하고 픽셀 값의 평균을 구합니다.

이 평균 밝기를 최근 최대 5개 프레임에 걸쳐 평균합니다. 시작 시 값이 5개 미만이면 확보된 값만 사용합니다. `determine_state()`는 필터링된 밝기에 다음 기준을 적용합니다.

| 판단 시점 | 밝기 조건 | 상태 |
|---|---|---|
| 최초 판단 | 100 이상 | `BRIGHT` |
| 최초 판단 | 100 미만 | `DARK` |
| 이후 판단 | 110 이상 | `BRIGHT` |
| 이후 판단 | 90 이하 | `DARK` |
| 이후 판단 | 90 초과, 110 미만 | 이전 상태 유지 |

이동평균과 상태 유지 구간은 작은 밝기 변화로 상태가 반복 전환되는 것을 줄이기 위한 처리입니다. 안정화 효과와 반응 시간에 대한 측정 결과는 포함되어 있지 않습니다.

## 객체 검출 모델

프로젝트에 포함된 `models/efficientdet_lite0.tflite`는 카메라 영상에서 여러 객체의 위치와 클래스를 검출하는 데 사용하는 TensorFlow Lite 모델입니다. 파일 크기는 약 4.4 MiB이며, `vision/detector.py`는 CPU에서 `tflite_runtime.Interpreter`로 실행하며, 해당 모듈 import가 실패하면 `ai_edge_litert.interpreter.Interpreter`를 사용합니다.

로컬 모델 파일에서 확인한 텐서 정보는 다음과 같습니다.

| 구분 | 형태 / 타입 | 현재 코드의 사용 방식 |
|---|---|---|
| 입력 이미지 | `[1, 320, 320, 3]`, `uint8` | RGB 이미지 한 장 |
| 출력 0 | `[1, 25, 4]`, `float32` | 박스 좌표 (`y_min, x_min, y_max, x_max`) |
| 출력 1 | `[1, 25]`, `float32` | 클래스 ID |
| 출력 2 | `[1, 25]`, `float32` | 검출 점수 |
| 출력 3 | `[1]`, `float32` | 검출 개수 |

입력 텐서의 양자화 scale은 `0.0078125`, zero point는 `127`입니다. 현재 코드는 별도 실수 정규화 없이 RGB `uint8` 픽셀을 전달합니다. 출력 배열은 최대 25개 검출을 담으며, 점수 `0.5` 이상인 결과만 후처리하고 프레임에 표시 정보를 그립니다. `--headless` 실행에서는 창을 표시하지 않습니다.

`models/coco_labels.txt`는 클래스 ID를 사람이 읽을 수 있는 이름으로 변환합니다. 사람(`person`), 자전거(`bicycle`), 자동차(`car`) 등의 라벨이 있으며, 90줄 중 일부는 `n/a` 자리 표시자입니다. 코드에서는 클래스 ID를 목록 인덱스로 직접 사용하므로 모델과 라벨 순서가 일치해야 합니다.

모델 다운로드 출처, 학습 설정 및 라이선스 정보는 현재 저장소에 기록되어 있지 않습니다. 이 설명은 포함된 파일과 현재 코드에서 확인한 내용을 기준으로 하며, 모델 정확도나 학습 이력을 의미하지 않습니다.

## 객체 검출 처리

`scripts/test_input.py`는 카메라 인덱스 `0`에서 프레임을 읽고 다음 처리를 반복합니다.

1. 장착 방향을 보정하도록 영상을 `cv2.flip(frame, -1)`로 180도 회전한 뒤 모델 입력 텐서 형태에 맞게 프레임을 리사이즈하고 BGR에서 RGB로 변환 (현재 모델은 `320 × 320`)
2. 배치 차원을 추가해 입력 텐서를 만들고 모델에 전달 (별도 정규화 없음)
3. `interpreter.invoke()`로 모델 추론 실행
4. 출력 텐서를 박스, 클래스, 점수, 검출 개수 순으로 읽기
5. 점수 `0.5` 이상인 검출의 좌표를 원본 프레임 크기로 변환하고 화면 범위로 제한
6. 원본 영상에 박스·라벨·점수를 표시하고, 검출 결과에 `label`, `score`, `center_x`, `bbox` 저장 (`direction` 필드 없음)
7. `find_target()`으로 첫 번째 `person`을 선택하고 이전 방향을 이용해 방향·중심 오차 계산
8. 전송 조건을 만족하면 `TRACK` 전송 및 응답 한 줄 수신

중심 오차는 `error_x = center_x - (frame_width // 2)`입니다. 초기 방향은 `CENTER`이며, 다음 히스테리시스 기준을 적용합니다.

| 이전 방향 | 조건 | 새 방향 |
|---|---|---|
| CENTER | 오차 < -70 | LEFT |
| CENTER | 오차 > 70 | RIGHT |
| CENTER | -70 ≤ 오차 ≤ 70 | CENTER |
| LEFT | 오차 ≥ -50 | CENTER |
| LEFT | 오차 < -50 | LEFT |
| RIGHT | 오차 ≤ 50 | CENTER |
| RIGHT | 오차 > 50 | RIGHT |

예를 들어 화면 폭 640에서 CENTER 상태는 중심 x=250~390을 유지하고, LEFT 상태는 x=270 이상에서 CENTER로 돌아옵니다. 대상이 왼쪽에서 오른쪽 끝으로 급격히 이동해도 현재 로직은 `LEFT → CENTER → RIGHT`로 프레임마다 전환하므로 중간 CENTER 패킷이 전송될 수 있습니다.

사람을 처음 검출하면 방향을 전송합니다. LEFT/RIGHT로 마지막 전송 방향이 바뀌면 즉시 보내고, 같은 LEFT/RIGHT가 유지되면 마지막 전송 시각부터 0.2초 이상 경과한 프레임에서 다시 보냅니다. CENTER는 마지막 전송 방향이 CENTER가 아닐 때만 보냅니다. 시간은 `time.monotonic()`으로 확인하며, 추론 및 동기식 응답 대기 때문에 정확한 0.2초 주기를 보장하지 않습니다. 기준 시각은 응답 수신 완료 시점이 아니라 전송 전 기록한 시각입니다.

히스테리시스의 이전 방향은 사람을 검출한 매 프레임 갱신하고, 마지막 전송 방향·시각은 응답 패킷 파싱 후 갱신합니다. 응답이 특정 ACK인지 또는 전송 방향과 일치하는지는 검사하지 않습니다.

사람이 검출되지 않으면 메시지를 보내지 않고 방향·전송 기록을 유지합니다. 정지나 대상 소실 패킷도 보내지 않습니다. 같은 LEFT/RIGHT로 다시 나타나면 0.2초 경과 여부에 따라 재전송하며, 마지막 전송이 CENTER이고 다시 CENTER로 나타나면 재전송하지 않습니다. 대상 소실 후 실제 장치의 정지 동작은 STM32 펌웨어에 따라 달라지며, 대상 소실 시 동작은 별도로 검증하지 않았습니다. 여러 사람이 있으면 선택 대상이 바뀔 수 있고, 동일 인물 추적은 구현되어 있지 않습니다.

기본 실행은 GUI 모드이며 `q` 또는 `Ctrl+C`로 종료합니다. GUI 없이 실행하려면 `--headless`를 지정하고 `Ctrl+C`로 종료합니다. 종료 시 카메라와 시리얼 연결을 정리하며, GUI 모드에서는 OpenCV 창도 정리합니다. `--verbose`를 지정하면 검출 결과가 있을 때 첫 번째 결과를 매 프레임 출력합니다. 이 결과는 TRACK 전송 대상으로 선택한 `person`과 다를 수 있습니다. 선택 대상이 있으면 방향과 `error_x`도 출력합니다. 추론 시간이나 FPS는 출력하지 않습니다. 전처리는 모델 입력 크기를 읽어 사용하지만, RGB `uint8` 입력 및 출력 텐서 순서를 가정하므로 다른 모델로 교체하려면 확인이 필요합니다.

## 시리얼 통신 프로토콜

애플리케이션 메시지는 UTF-8 텍스트이며 다음 형식을 사용합니다. `\n`은 실제 LF 줄바꿈을 의미합니다.

```text
COMMAND:PAYLOAD\n
```

`app/main.py`가 보내는 밝기 상태 메시지는 다음 두 종류입니다.

```text
STATE:BRIGHT\n
STATE:DARK\n
```

`scripts/test_input.py`는 사람 방향에 따라 다음 메시지를 보냅니다.

```text
TRACK:LEFT\n
TRACK:CENTER\n
TRACK:RIGHT\n
```

`create_packet()`은 문자열 타입, 빈 값, 콜론 및 줄바꿈 포함 여부를 검사합니다. `parse_packet()`은 UTF-8 디코딩, 끝의 줄바꿈, 콜론 하나, 비어 있지 않은 명령과 데이터를 확인합니다.

| 설정 | 값 |
|---|---|
| 포트 | `/dev/ttyS0` |
| 통신 속도 | 115200 baud |
| 읽기 타임아웃 | 1초 |
| 수신 방식 | STATE 또는 TRACK 전송 직후 `readline()`으로 한 줄 읽기 |

데이터 비트, 패리티, 정지 비트는 코드에서 별도로 지정하지 않습니다. 수신 패킷은 형식만 검사하며, 특정 ACK인지 또는 전송 상태와 일치하는지는 확인하지 않습니다. `protocol.py`의 `TRACK:LEFT`는 파싱 예제이며, 실제 방향 전송은 `scripts/test_input.py`에서 수행합니다.

## STM32 연동 범위

Python 측에는 외부 장치로 상태를 보내고 응답을 읽는 인터페이스가 있습니다. STM32와 연결하려면 장치 측에서 위 메시지를 수신·해석하고, Python이 읽을 수 있는 `COMMAND:PAYLOAD`와 LF 형식으로 응답해야 합니다.

사용자 확인 구성은 NUCLEO-F401RE → PCA9685 → SG90 PAN/TILT입니다. Windows COM 포트를 VMware Serial Port로 연결해 Ubuntu `/dev/ttyS0`에서 통신하며, UART 송수신 및 PAN 사람 추적을 실제로 확인했습니다. `TRACK:CENTER`는 현재 PAN 위치 유지이며 중앙 각도로 복귀하는 명령이 아닙니다.

STM32 펌웨어와 상세 핀·배선은 저장소에 포함되어 있지 않습니다. 보정값과 연결 기록은 [작업 기록](docs/2026-11-18-pan-tracking.md)을 참고하세요. TILT 보정은 완료했으나 영상 기반 TILT 추적은 미구현입니다.

## 설치 및 실행

Python 3와 pip, 카메라가 필요합니다. 밝기 메인 실행, 카메라 단독 확인 및 객체 검출의 기본 실행에는 OpenCV 창을 표시할 수 있는 GUI 환경도 필요합니다. 객체 검출은 `--headless` 옵션으로 GUI 없이 실행할 수 있습니다. 통합 실행에는 `/dev/ttyS0`에 접근할 권한과 프로토콜에 맞게 응답하는 외부 장치도 필요합니다.

프로젝트 루트에서 실행합니다.

```bash
git clone https://github.com/NarviikLee/EmbeddedVisionController.git
cd EmbeddedVisionController
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

`requirements.txt`는 작성 당시 로컬에 설치된 OpenCV `4.9.0.80`과 pyserial `3.5`를 기준으로 작성했습니다. 새 가상환경 설치는 별도로 검증하지 않았습니다. 하드웨어 확인 범위는 아래 작업 기록을 참고하세요. NumPy는 OpenCV의 의존성으로 설치됩니다.

통합 실행:

```bash
python3 -m app.main
```

카메라만 확인:

```bash
python3 -m vision.camera_test
```

카메라 창에서 `q`를 누르면 종료합니다.

시리얼 송수신만 확인 (`BRIGHT`를 한 번 전송하고 응답 수신):

```bash
python3 -m communication.serial_comm
```

하드웨어 없이 샘플 패킷 파싱 확인:

```bash
python3 -m communication.protocol
```

샘플에는 정상 패킷 두 개와 비정상 패킷 하나가 포함되어 있습니다. `INVALID`에 대한 프로토콜 오류 출력은 예제의 예상 동작입니다.

포트와 통신 설정은 `communication/serial_comm.py`에 정의되어 있습니다. 카메라 단독 실행 설정은 `vision/camera_test.py`에 있으며, 메인은 카메라 인덱스 `0`과 평균 창 크기 `5`를 직접 사용합니다. 설정 파일은 없습니다. 객체 검출 스크립트에는 `--headless`, `--verbose` CLI 옵션이 있으며, 포트나 카메라 인덱스를 변경하는 CLI 옵션은 없습니다.

### 객체 검출 스크립트 실행

객체 검출에는 `tflite_runtime` 또는 대체 런타임인 `ai_edge_litert` 모듈이 필요합니다. `requirements-vision.txt`는 기존 Python 3.8 환경을 기준으로 `numpy==1.24.4`와 `tflite-runtime==2.14.0`을 지정하며, `ai-edge-litert`는 포함하지 않습니다. 사용 중인 Python 버전과 플랫폼에 맞는 런타임이 필요합니다.

기존에 모델 로드를 확인한 환경은 Python `3.8.10`, NumPy `1.24.4`, OpenCV `4.9.0.80`, `tflite-runtime` `2.14.0`입니다. 해당 Python 버전과 플랫폼에서 사용할 수 있는 설치 예시는 다음과 같습니다.

```bash
# 프로젝트 루트에서 가상환경 생성 및 활성화 (이미 생성했다면 활성화만 실행)
python3 -m venv .venv
source .venv/bin/activate

# 기본 기능 및 객체 검출 의존성 설치
python3 -m pip install -r requirements-vision.txt

# 모델 로드 및 입력 텐서 확인
python3 -m scripts.inspect_model

# 카메라 사람 검출 및 시리얼 방향 전송 실행 (외부 장치 필요)
python3 -m scripts.test_input
```

`tflite-runtime`을 설치할 수 없는 환경에서는 기본 의존성과 대체 런타임을 설치할 수 있습니다. 아래 조합은 현재 로컬 Python `3.10.12`에서 확인한 기준이며, 다른 Python 버전과 플랫폼의 호환성은 별도 확인이 필요합니다.

```bash
python3 -m pip install -r requirements.txt "numpy==1.26.4" "ai-edge-litert==2.3.0"
python3 -m scripts.test_input
```

`scripts/inspect_model.py`는 여전히 `tflite_runtime`을 직접 import하므로 대체 런타임만 설치한 환경에서는 실행되지 않습니다. 런타임 대체 처리는 `vision/detector.py`에만 적용되어 있습니다.

실행 옵션 예시 (프로젝트 루트, 가상환경 활성화 후):

```bash
# CLI 도움말: 모델 로드, 카메라 및 시리얼 연결 없이 옵션 확인
python3 -m scripts.test_input --help

# 기본 GUI 모드: q 또는 Ctrl+C로 종료
python3 -m scripts.test_input

# GUI 없는 모드: Ctrl+C로 종료
python3 -m scripts.test_input --headless

# GUI 없이 첫 검출 결과도 출력
python3 -m scripts.test_input --headless --verbose
```

모델과 라벨 파일은 `models/`에 포함되어 있으므로 별도로 다운로드할 필요는 없습니다.

`No matching distribution found`가 나오면 사용 중인 Python 버전 또는 플랫폼에 맞는 패키지가 없는지 확인해야 합니다. 위 버전 조합은 현재 로컬 환경에서 모델 로드를 확인한 기준이며, 다른 환경에서의 설치 성공은 검증하지 않았습니다. 현재 로컬 `.venv`에는 `pyserial` `3.5`도 설치되어 있으며, 모듈 import를 확인했습니다. 2026-11-18 사용자가 VMware `/dev/ttyS0` 경로의 실제 송수신을 확인했습니다.

모델과 라벨 경로는 현재 작업 디렉터리를 기준으로 하므로 프로젝트 루트에서 실행합니다.

`scripts.inspect_model`은 출력 텐서 정보도 조회하지만 콘솔에는 입력 텐서 정보만 출력합니다. 2026-10-06 로컬 `.venv`에서 모델 로드·텐서 할당 및 합성 이미지 추론을 확인했습니다. Python 소스 문법과 `STATE` 패킷 생성·파싱 왕복 검사도 통과했습니다. 카메라 객체 검출 및 실제 시리얼 통신 실행은 이번 확인에 포함되지 않았습니다.

`scripts/test_input.py --headless` 실행에는 카메라와 `/dev/ttyS0`에 연결된 외부 장치와 포트 접근 권한이 필요합니다. 장치는 TRACK 전송 후 1초 타임아웃 안에 LF로 끝나는 `COMMAND:PAYLOAD` 형식의 응답을 보내야 합니다. 시리얼 연결 실패나 응답 타임아웃이 발생하면 실행이 종료됩니다. `scripts.inspect_model`은 카메라와 시리얼 장치 없이 실행할 수 있습니다. 모델 로드와 라벨 파일 읽기는 카메라 처리의 `try` 블록 이전에 이루어지므로, 의존성이나 파일 경로 오류는 해당 블록에서 처리되지 않습니다.

## Troubleshooting

### STM32 응답 타임아웃이 자주 발생하는 경우

사용자 확인 사례 (2026-10-14): STM32 연결 시 응답 타임아웃이 자주 발생했으나, USB 허브를 통해 STM32를 연결한 뒤에는 타임아웃 없이 정상 동작했습니다. 같은 증상이 발생하면 USB 허브를 통한 연결을 시도하고 응답 수신 여부를 확인할 수 있습니다.

이 내용은 사용자가 실제 연결에서 관찰한 결과입니다. 타임아웃의 원인과 USB 허브의 전원 방식·모델은 확인하지 않았으며, 모든 환경에서 같은 결과를 보장하지 않습니다. 이번 자동화 테스트에는 실제 USB 연결 검증이 포함되지 않았습니다.

## 검증 범위 및 현재 한계

모듈별 수동 확인 코드와 Git에서 제외한 로컬 `tests/`가 있습니다. 2026-11-18 사용자가 카메라·UART·STM32·PAN 서보 통합 동작을 확인했으며, [작업 기록](docs/2026-11-18-pan-tracking.md)에 결과를 남겼습니다. 처리 지연과 검출 정확도의 정량 측정은 아직 없습니다.

- 통신은 동기식이며 응답을 기다리는 동안 영상 처리가 대기합니다.
- 타임아웃이나 패킷 오류가 발생하면 통합 실행은 예외를 출력하고 종료합니다.
- 상태 전송 직후 이전 상태를 갱신하며, 상대 장치의 처리 성공을 확인하지 않습니다.
- LEFT/RIGHT의 주기적 반복 전송은 있지만, 통신 실패에 대한 재시도, 상시 수신, 자동 재연결, 체크섬은 구현되어 있지 않습니다.
- 객체 검출과 딥러닝 추론은 별도 스크립트에 구현되어 있으며, 방향 판단 및 시리얼 전송도 연결되어 있습니다. 밝기 메인과의 통합 및 동일 인물 추적은 구현되어 있지 않습니다.
- PAN 추적에서 좌우 진동이 관찰되어 안정화가 필요하며, 영상 기반 TILT 추적은 미구현입니다.
- 객체 검출 정확도와 추론 시간의 정량 측정 결과는 아직 없습니다.
- `app/main.py`는 import 시에도 실행 로직이 시작됩니다.

### 2026-10-13 확인 결과

변경된 Python 소스 문법, 합성 이미지 모델 추론·후처리, 방향 판단 경계값 및 모의 시리얼의 `TRACK:LEFT` 패킷 생성을 확인했습니다. 실제 카메라 검출, 외부 장치 응답 및 장치 제어는 이번 검사에 포함되지 않았습니다.

추가 변경 확인: Python `3.10.12`, NumPy `1.26.4`, OpenCV `4.9.0`, `ai-edge-litert` `2.3.0` 환경에서 변경된 두 Python 파일의 문법과 합성 이미지 추론·후처리를 확인했습니다. 대체 런타임이 실제로 선택되었으며, 카메라·GUI·시리얼 통신 및 `Ctrl+C` 자원 정리는 실행 검증하지 않았습니다.


### 현재 로컬 자동화 테스트

로컬 `tests/`를 최신 함수 인자와 검출 결과 형식에 맞춰 갱신했으며, 2026-11-18 재실행 결과 9개 테스트가 모두 통과했습니다. 이전 2026-10-19의 테스트 불일치는 로컬 테스트에서 해소했습니다.

```bash
python3 -m unittest discover -s tests -v
```

검사 범위는 실제 모델의 합성 이미지 추론, RGB 전처리, 검출 필터·좌표 제한, 방향 히스테리시스 경계, 대상 선택, 반복 전송·CENTER 억제, GUI/headless 및 종료 정리의 모의 실행, 시리얼 패킷·응답 예외, 밝기 판단입니다. 이 자동화 검사는 실제 카메라·STM32를 제어하지 않습니다.

`tests/`는 사용자 요청에 따라 `.gitignore`에 등록하고 기존 파일의 Git 추적도 해제했습니다. 테스트 파일은 로컬에만 존재하므로 clone한 저장소에서는 별도로 준비해야 합니다.
