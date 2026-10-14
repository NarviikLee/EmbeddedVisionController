# EmbeddedVisionController

OpenCV로 카메라 영상의 밝기를 분석하고, 밝기 상태가 바뀌면 시리얼 포트로 외부 장치에 전달하는 Python 프로젝트입니다. 중앙 영역의 평균 밝기에 이동평균과 히스테리시스를 적용해 `BRIGHT` 또는 `DARK` 상태를 판단합니다.

Python 측 밝기 분석과 시리얼 송수신 코드가 구현되어 있으며, 별도 스크립트에서 TensorFlow Lite 기반 카메라 객체 검출을 실행할 수 있습니다. STM32 펌웨어와 하드웨어 검증 기록은 포함되어 있지 않아, STM32 연동 및 장치 제어의 성공 여부는 이 저장소만으로 확인할 수 없습니다.

## 최근 업데이트 (2026-10-14)

지난번 푸시한 `82a5e3c`와 현재 작업 트리를 비교한 변경입니다.

- `scripts/test_input.py`: `HEADLESS = True` 상수 대신 `--headless` CLI 옵션 추가. 옵션 없이 실행하면 GUI 모드입니다.
- `--verbose`를 지정했을 때만 첫 번째 검출 결과를 출력합니다. TRACK 송수신 로그는 옵션 없이도 출력합니다.
- 첫 번째 `person`을 선택하는 로직을 `find_target(results, target_label="person")` 함수로 분리했습니다. 선택 기준과 방향 변경 시 전송 동작은 유지됩니다.
- `communication/serial_comm.py`: `/dev/ttyAMA0` 포트 예시를 주석으로 추가했습니다. 실제 설정은 `/dev/ttyACM0`, 115200 baud, 읽기 타임아웃 1초입니다.
- `tests/test_tracking.py`: 하드웨어 없이 실행하는 대상 선택·방향 경계·패킷·CLI 실행 흐름 테스트 추가.

지난 업데이트의 모델 처리 함수 분리, TRACK 전송, `tflite_runtime` import 실패 시 `ai_edge_litert` 대체 처리는 유지됩니다.

`app/main.py`의 밝기 기반 `STATE` 전송은 그대로 유지됩니다. 객체 검출 및 방향 전송은 별도 스크립트로 실행하며, 실제 STM32 동작은 검증하지 않았습니다.

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
├── tests/
│   └── test_tracking.py         # 대상 선택·패킷·CLI 실행 흐름 자동화 테스트
├── docs/                       # 현재 비어 있음
├── firmware/                   # 현재 비어 있음
├── .gitignore
├── requirements.txt            # 기본 영상 처리 및 시리얼 통신 의존성
├── requirements-vision.txt     # 기본 의존성 + 객체 검출 의존성
└── README.md
```

빈 디렉터리는 Git에서 추적하지 않으므로 clone한 저장소에는 `docs/`와 `firmware/`가 없을 수 있습니다.

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

1. 모델 입력 텐서 형태에 맞게 프레임을 리사이즈하고 BGR에서 RGB로 변환 (현재 모델은 `320 × 320`)
2. 배치 차원을 추가해 입력 텐서를 만들고 모델에 전달 (별도 정규화 없음)
3. `interpreter.invoke()`로 모델 추론 실행
4. 출력 텐서를 박스, 클래스, 점수, 검출 개수 순으로 읽기
5. 점수 `0.5` 이상인 검출의 좌표를 원본 프레임 크기로 변환하고 화면 범위로 제한
6. 박스의 가로 중심을 기준으로 방향을 판단하고 원본 영상에 박스, 라벨, 점수 및 방향 표시
7. 검출 목록에서 첫 번째 `person`을 선택하고, 이전 전송 방향과 다르면 `TRACK` 전송 및 응답 한 줄 수신

방향은 화면 중앙보다 60픽셀 넘게 왼쪽이면 `LEFT`, 60픽셀 넘게 오른쪽이면 `RIGHT`, 나머지는 `CENTER`입니다. 사람을 처음 검출했을 때도 전송합니다. 응답 패킷을 파싱한 뒤 이전 방향을 갱신하지만, 응답이 특정 ACK인지 또는 전송 방향과 일치하는지는 검사하지 않습니다.

사람이 검출되지 않으면 메시지를 보내지 않고 이전 방향을 유지합니다. 같은 방향으로 사람이 다시 나타나면 재전송하지 않습니다. 여러 사람이 있는 경우 선택 대상이 프레임마다 바뀔 수 있으며, 동일 인물을 식별하여 유지하는 추적은 구현되어 있지 않습니다.

기본 실행은 GUI 모드이며 `q` 또는 `Ctrl+C`로 종료합니다. GUI 없이 실행하려면 `--headless`를 지정하고 `Ctrl+C`로 종료합니다. 종료 시 카메라와 시리얼 연결을 정리하며, GUI 모드에서는 OpenCV 창도 정리합니다. `--verbose`를 지정하면 검출 결과가 있을 때 첫 번째 결과를 매 프레임 출력합니다. 이 결과는 TRACK 전송 대상으로 선택한 `person`과 다를 수 있습니다. 추론 시간이나 FPS는 출력하지 않습니다. 전처리는 모델 입력 크기를 읽어 사용하지만, RGB `uint8` 입력 및 출력 텐서 순서를 가정하므로 다른 모델로 교체하려면 확인이 필요합니다.

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
| 포트 | `/dev/ttyACM0` |
| 통신 속도 | 115200 baud |
| 읽기 타임아웃 | 1초 |
| 수신 방식 | STATE 또는 TRACK 전송 직후 `readline()`으로 한 줄 읽기 |

데이터 비트, 패리티, 정지 비트는 코드에서 별도로 지정하지 않습니다. 수신 패킷은 형식만 검사하며, 특정 ACK인지 또는 전송 상태와 일치하는지는 확인하지 않습니다. `protocol.py`의 `TRACK:LEFT`는 파싱 예제이며, 실제 방향 전송은 `scripts/test_input.py`에서 수행합니다.

## STM32 연동 범위

Python 측에는 외부 장치로 상태를 보내고 응답을 읽는 인터페이스가 있습니다. STM32와 연결하려면 장치 측에서 위 메시지를 수신·해석하고, Python이 읽을 수 있는 `COMMAND:PAYLOAD`와 LF 형식으로 응답해야 합니다.

현재 저장소에는 STM32 모델, UART 핀·배선, 실제 연결 경로, 수신·응답 펌웨어 및 LED·모터 등의 제어 코드가 없습니다. `/dev/ttyACM0` 경로만으로 USB CDC, ST-LINK 가상 COM 포트 등 실제 연결 방식을 확정할 수 없습니다.

## 설치 및 실행

Python 3와 pip, 카메라가 필요합니다. 밝기 메인 실행, 카메라 단독 확인 및 객체 검출의 기본 실행에는 OpenCV 창을 표시할 수 있는 GUI 환경도 필요합니다. 객체 검출은 `--headless` 옵션으로 GUI 없이 실행할 수 있습니다. 통합 실행에는 `/dev/ttyACM0`에 접근할 권한과 프로토콜에 맞게 응답하는 외부 장치도 필요합니다.

프로젝트 루트에서 실행합니다.

```bash
git clone https://github.com/NarviikLee/EmbeddedVisionController.git
cd EmbeddedVisionController
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

`requirements.txt`는 작성 당시 로컬에 설치된 OpenCV `4.9.0.80`과 pyserial `3.5`를 기준으로 작성했습니다. 새 가상환경 설치 및 하드웨어 동작은 별도로 검증하지 않았습니다. NumPy는 OpenCV의 의존성으로 설치됩니다.

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

`No matching distribution found`가 나오면 사용 중인 Python 버전 또는 플랫폼에 맞는 패키지가 없는지 확인해야 합니다. 위 버전 조합은 현재 로컬 환경에서 모델 로드를 확인한 기준이며, 다른 환경에서의 설치 성공은 검증하지 않았습니다. 현재 로컬 `.venv`에는 `pyserial` `3.5`도 설치되어 있으며, 모듈 import를 확인했습니다. 실제 시리얼 장치 통신은 별도 검증이 필요합니다.

모델과 라벨 경로는 현재 작업 디렉터리를 기준으로 하므로 프로젝트 루트에서 실행합니다.

`scripts.inspect_model`은 출력 텐서 정보도 조회하지만 콘솔에는 입력 텐서 정보만 출력합니다. 2026-10-06 로컬 `.venv`에서 모델 로드·텐서 할당 및 합성 이미지 추론을 확인했습니다. Python 소스 문법과 `STATE` 패킷 생성·파싱 왕복 검사도 통과했습니다. 카메라 객체 검출 및 실제 시리얼 통신 실행은 이번 확인에 포함되지 않았습니다.

`scripts/test_input.py --headless` 실행에는 카메라와 `/dev/ttyACM0`에 연결된 외부 장치와 포트 접근 권한이 필요합니다. 장치는 TRACK 전송 후 1초 타임아웃 안에 LF로 끝나는 `COMMAND:PAYLOAD` 형식의 응답을 보내야 합니다. 시리얼 연결 실패나 응답 타임아웃이 발생하면 실행이 종료됩니다. `scripts.inspect_model`은 카메라와 시리얼 장치 없이 실행할 수 있습니다. 모델 로드와 라벨 파일 읽기는 카메라 처리의 `try` 블록 이전에 이루어지므로, 의존성이나 파일 경로 오류는 해당 블록에서 처리되지 않습니다.

## Troubleshooting

### STM32 응답 타임아웃이 자주 발생하는 경우

사용자 확인 사례 (2026-10-14): STM32 연결 시 응답 타임아웃이 자주 발생했으나, USB 허브를 통해 STM32를 연결한 뒤에는 타임아웃 없이 정상 동작했습니다. 같은 증상이 발생하면 USB 허브를 통한 연결을 시도하고 응답 수신 여부를 확인할 수 있습니다.

이 내용은 사용자가 실제 연결에서 관찰한 결과입니다. 타임아웃의 원인과 USB 허브의 전원 방식·모델은 확인하지 않았으며, 모든 환경에서 같은 결과를 보장하지 않습니다. 이번 자동화 테스트에는 실제 USB 연결 검증이 포함되지 않았습니다.

## 검증 범위 및 현재 한계

소스에는 모듈별 수동 확인 코드와 `tests/test_tracking.py`의 자동화 테스트가 있습니다. 하드웨어 검증 로그는 없습니다. 카메라 및 STM32 연동 완료, 처리 속도, 판단 정확도에 대한 결과는 아직 문서화되어 있지 않습니다.

- 통신은 동기식이며 응답을 기다리는 동안 영상 처리가 대기합니다.
- 타임아웃이나 패킷 오류가 발생하면 통합 실행은 예외를 출력하고 종료합니다.
- 상태 전송 직후 이전 상태를 갱신하며, 상대 장치의 처리 성공을 확인하지 않습니다.
- 상시 수신, 자동 재연결, 재전송, 체크섬은 구현되어 있지 않습니다.
- 객체 검출과 딥러닝 추론은 별도 스크립트에 구현되어 있으며, 방향 판단 및 시리얼 전송도 연결되어 있습니다. 밝기 메인과의 통합 및 동일 인물 추적은 구현되어 있지 않습니다.
- 객체 검출의 실제 정확도, 추론 시간 측정 결과 및 하드웨어 검증 로그는 아직 문서화되어 있지 않습니다.
- `app/main.py`는 import 시에도 실행 로직이 시작됩니다.

### 2026-10-13 확인 결과

변경된 Python 소스 문법, 합성 이미지 모델 추론·후처리, 방향 판단 경계값 및 모의 시리얼의 `TRACK:LEFT` 패킷 생성을 확인했습니다. 실제 카메라 검출, 외부 장치 응답 및 장치 제어는 이번 검사에 포함되지 않았습니다.

추가 변경 확인: Python `3.10.12`, NumPy `1.26.4`, OpenCV `4.9.0`, `ai-edge-litert` `2.3.0` 환경에서 변경된 두 Python 파일의 문법과 합성 이미지 추론·후처리를 확인했습니다. 대체 런타임이 실제로 선택되었으며, 카메라·GUI·시리얼 통신 및 `Ctrl+C` 자원 정리는 실행 검증하지 않았습니다.


### 재현 가능한 자동화 테스트 (2026-10-14)

프로젝트 루트에서 가상환경을 활성화하고 객체 검출 의존성을 설치한 뒤 실행합니다. 표준 라이브러리 `unittest`를 사용하므로 별도의 테스트 패키지는 필요하지 않습니다. 테스트 모듈 import에는 OpenCV, NumPy, pyserial과 객체 검출 런타임이 필요합니다.

```bash
python3 -m unittest discover -s tests -v
```

`tests/test_tracking.py`의 5개 테스트가 통과했습니다.

| 테스트 | 확인 내용 |
|---|---|
| 대상 선택 | 첫 번째 person 선택, 다른 라벨 지정, 빈 목록 및 대상 없음 |
| 방향 경계 | 폭 640에서 중심 x=259/260/380/381의 LEFT/CENTER/RIGHT |
| 시리얼 패킷 | 세 방향의 TRACK 바이트, 응답 파싱, 타임아웃·잘못된 패킷 예외 |
| Headless + verbose | GUI 함수 미호출, 검출 결과 출력, Ctrl+C 처리 및 자원 정리 |
| 기본 GUI | 프레임 표시와 창 정리 함수 호출, 기본 검출 결과 출력 없음 |

실행 흐름 테스트는 카메라·추론 결과·시리얼·GUI를 모의 객체로 대체합니다. LEFT가 반복되거나 잠시 사람이 사라졌다가 LEFT로 다시 나타나면 추가 전송하지 않고, RIGHT로 변경되면 전송하는 것도 확인합니다. 모의 응답 `ACK:OK`도 수락하므로, 실제 ACK 의미나 방향 일치 검증을 보장하지 않습니다.

추가로 CLI `--help`, Python 소스 문법, 실제 모델의 합성 이미지 추론·후처리를 확인했습니다. 실제 카메라 입력, GUI 창 표시, UART/STM32 응답과 장치 제어는 검증하지 않았습니다.
