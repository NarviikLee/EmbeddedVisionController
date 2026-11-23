# EmbeddedVisionController

OpenCV로 카메라 영상의 밝기를 분석하고, 밝기 상태가 바뀌면 시리얼 포트로 외부 장치에 전달하는 Python 프로젝트입니다. 중앙 영역의 평균 밝기에 이동평균과 히스테리시스를 적용해 `BRIGHT` 또는 `DARK` 상태를 판단합니다.

현재는 VMware Ubuntu 20.04에서 UVC 카메라의 사람 검출 결과를 UART로 NUCLEO-F401RE에 전달하고, PCA9685와 SG90 서보를 통해 PAN 좌우 추적을 수행합니다. 밝기 분석 기능도 별도 실행 경로로 유지합니다.

## 최근 업데이트 (2026-11-23)

- PAN 중심값에 EMA (`alpha_x = 0.4`)를 적용하고 실행 루프의 히스테리시스 기준을 복귀 60 / 이탈 85픽셀로 확대
- 가로 오차 크기에 따라 반복 명령 간격을 0.20~0.50초로 조절해 중앙 부근의 과이동·좌우 왕복 감소
- 추적 루프의 UART echo/ACK 대기를 제거해 명령 전송 중에도 사용자 측정 약 4~5 FPS 유지
- VMware Serial Port의 Connected 설정 문제를 해결해 `/dev/ttyS0` 통신 복구
- TILT 전용 UART 송신과 독립 전송 상태 추가: UP/DOWN 반복 간격 0.4초, CENTER 진입 시 한 번 전송
- 사용자 STM32 파서·물리 방향 매핑 수정 후 PAN/TILT 실제 동시 추적 확인
- `scripts/test_tilt.py` 추가: UP/DOWN 각 4회 반복 전송으로 하드웨어 이동 확인
- 프레임 읽기 성공 확인 후 영상 180도 보정을 수행하도록 순서 수정

PAN과 TILT 모두 Vision 기반 실제 서보 추적을 확인했습니다. 다음 단계는 PAN 설정을 유지하며 TILT STEP·dead zone·필터·반복 간격을 튜닝하는 것입니다. 하드웨어 관찰과 성능 수치는 사용자 제공 결과입니다. [PAN 안정화 기록](docs/2026-11-23-tracking-stability.md), [PAN/TILT 통합 기록](docs/2026-11-23-pan-tilt-integration.md)과 [이전 구성 기록](docs/2026-11-18-pan-tracking.md)을 참고하세요.

## 구현된 기능

- 카메라 프레임 읽기 및 중앙 ROI의 회색조 평균 밝기 계산
- 최근 최대 5개 밝기 값의 이동평균
- 이전 상태와 임계값을 이용한 히스테리시스 상태 판단
- 최초 판단 및 상태 변경 시 `STATE` 메시지 전송
- 시리얼 응답 한 줄 수신, 패킷 형식 검사 및 콘솔 출력
- 카메라 화면 표시, `q` 키 종료 및 자원 정리
- 영상 처리, 시리얼 통신, 패킷 파싱의 모듈별 수동 확인 코드
- EfficientDet Lite0 객체 검출, 결과 시각화, PAN EMA·히스테리시스·가변 전송 주기 및 실제 서보 추적
- TILT center_y·error_y 판단, 전용 UART 전송 및 실제 상하 서보 추적
- PAN/TILT 독립 명령 상태 관리 및 실제 동시 추적

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
│   ├── test_input.py            # 사람 검출 및 PAN/TILT 시리얼 전송
│   └── test_tilt.py             # 실제 TILT 서보 UP/DOWN 반복 전송
├── docs/
│   ├── 2026-11-18-pan-tracking.md # 환경 변경 및 PAN 실동작 기록
│   ├── 2026-11-23-tracking-stability.md # PAN 안정화 및 TILT 방향 판단
│   └── 2026-11-23-pan-tilt-integration.md # TILT 연동 및 동시 추적
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
6. 영상에 박스·라벨·점수를 표시하고 결과에 `label`, `score`, `center_x`, `center_y`, `bbox` 저장
7. 첫 번째 `person`의 가로 중심에 EMA를 적용한 뒤 PAN 방향 판단, 세로 중심으로 TILT 방향 판단
8. 각 축의 독립 전송 조건에 따라 TILT 및 PAN TRACK 명령을 같은 UART로 순차 전송 (echo 응답 대기 없음)

PAN 필터는 첫 검출의 중심값으로 초기화하며 이후 `filtered_center_x = 0.4 * center_x + 0.6 * filtered_center_x`로 갱신합니다. 사용자 튜닝에서 alpha 0.3은 반응이 느리고 0.5는 일부 좌우 왕복이 있어 0.4를 기준값으로 선택했습니다.

PAN 오차는 `error_x = filtered_center_x - (frame_width // 2)`입니다. 초기 방향은 CENTER이며 실행 루프는 아래 기준을 명시적으로 전달합니다. `vision/detector.py` 함수 기본값 50/70과는 구분됩니다.

| 이전 방향 | 조건 | 새 방향 |
|---|---|---|
| CENTER | 오차 < -85 | LEFT |
| CENTER | 오차 > 85 | RIGHT |
| CENTER | -85 ≤ 오차 ≤ 85 | CENTER |
| LEFT | 오차 ≥ -60 | CENTER |
| LEFT | 오차 < -60 | LEFT |
| RIGHT | 오차 ≤ 60 | CENTER |
| RIGHT | 오차 > 60 | RIGHT |

폭 640에서 CENTER는 필터 중심 x=235~405를 유지합니다. LEFT는 x≥260, RIGHT는 x≤380에서 CENTER로 돌아옵니다. 반대편으로 급격히 이동하면 중간 CENTER 상태를 거칠 수 있습니다.

처음 검출하거나 LEFT/RIGHT 전송 방향이 바뀌면 즉시 전송합니다. 같은 LEFT/RIGHT는 다음 간격 이상 경과한 프레임에서 반복 전송하며 CENTER는 진입 시 한 번 전송합니다.

| 가로 절대 오차 | 반복 전송 간격 |
|---|---|
| 150 초과 | 0.20초 |
| 100 초과, 150 이하 | 0.30초 |
| 70 초과, 100 이하 | 0.40초 |
| 70 이하 | 0.50초 |

이는 고정 주기를 보장하는 타이머가 아니며 프레임 처리 속도의 영향을 받습니다. 방향은 검출 프레임마다, 마지막 전송 방향·시각은 `send_track()` 반환 후 갱신합니다. STM32 echo는 유지하지만 현재 루프는 읽지 않으며, 실제 처리 성공이나 ACK 의미를 검사하지 않습니다. 응답 대기 제거는 비동기 UART 구현을 의미하지 않으며 `serial.write()`는 동기 호출입니다.

대상이 사라지면 전송하지 않고 필터·방향·전송 기록을 유지합니다. 재등장한 LEFT/RIGHT는 현재 오차의 간격 조건을 따르며 CENTER가 유지되면 재전송하지 않습니다. 대상 소실 패킷은 없고 여러 사람 중 동일 인물을 유지하는 기능도 없습니다.

TILT는 필터링하지 않은 `center_y`로 `error_y = center_y - (frame_height // 2)`를 계산합니다. -60 미만은 UP, 60 초과는 DOWN, 나머지는 CENTER입니다. 높이 480에서 중심 y=180~300은 CENTER입니다. TILT 방향 변경은 즉시 전송하며, 같은 UP/DOWN은 마지막 TILT 전송으로부터 0.4초 이상 지난 프레임에서 반복합니다. CENTER는 마지막 TILT 전송 방향이 CENTER가 아닐 때 한 번 전송합니다. PAN과 별도 방향·시각 상태를 유지하며 두 축의 명령은 같은 UART에 순차적으로 쓰고 응답은 기다리지 않습니다. TILT에는 아직 EMA·히스테리시스·가변 간격을 적용하지 않았습니다.

기본 실행은 GUI 모드이며 `q` 또는 `Ctrl+C`로 종료합니다. GUI 없이 실행하려면 `--headless`를 지정하고 `Ctrl+C`로 종료합니다. 종료 시 카메라와 시리얼 연결을 정리하며, GUI 모드에서는 OpenCV 창도 정리합니다. `--verbose`를 지정하면 검출 결과가 있을 때 첫 번째 결과를 매 프레임 출력합니다. 이 결과는 TRACK 전송 대상으로 선택한 `person`과 다를 수 있습니다. 선택 대상이 있으면 PAN·TILT 방향과 error_x·error_y도 출력합니다. FPS와 Frame Time은 verbose 여부와 무관하게 매 프레임 출력합니다. 측정 구간은 카메라 읽기부터 추론·후처리·전송까지이며 GUI 표시·waitKey·성능 로그 출력은 포함하지 않습니다. 모델 invoke만의 추론 시간이나 전체 실행 FPS와는 구분해야 합니다. 전처리는 모델 입력 크기를 읽어 사용하지만, RGB `uint8` 입력 및 출력 텐서 순서를 가정하므로 다른 모델로 교체하려면 확인이 필요합니다.

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

`scripts/test_input.py`는 PAN 축의 사람 방향에 따라 다음 메시지를 보냅니다.

```text
TRACK:LEFT\n
TRACK:CENTER\n
TRACK:RIGHT\n
```

TILT 축은 별도 명령을 사용합니다.

```text
TILT:UP\n
TILT:DOWN\n
TILT:CENTER\n
```

두 축의 CENTER는 화면 중앙 부근의 타깃을 따라 현재 위치를 유지하는 의미이며, 기계적 중앙 PWM 값 320으로 복귀하는 명령이 아닙니다.

`create_packet()`은 문자열 타입, 빈 값, 콜론 및 줄바꿈 포함 여부를 검사합니다. `parse_packet()`은 UTF-8 디코딩, 끝의 줄바꿈, 콜론 하나, 비어 있지 않은 명령과 데이터를 확인합니다.

| 설정 | 값 |
|---|---|
| 포트 | `/dev/ttyS0` |
| 통신 속도 | 115200 baud |
| 읽기 타임아웃 | 1초 |
| 수신 방식 | STATE 경로는 전송 후 readline(); PAN/TILT 추적 루프는 응답 대기 없음 |

데이터 비트, 패리티, 정지 비트는 코드에서 별도로 지정하지 않습니다. 수신 패킷은 형식만 검사하며, 특정 ACK인지 또는 전송 상태와 일치하는지는 확인하지 않습니다. `protocol.py`의 `TRACK:LEFT`는 파싱 예제이며, 실제 방향 전송은 `scripts/test_input.py`에서 수행합니다.

## STM32 연동 범위

Python 측에는 외부 장치로 상태를 보내고 응답을 읽는 인터페이스가 있습니다. 장치 측에서 위 메시지를 수신·해석해야 합니다. 응답을 읽는 STATE 경로에서는 LF로 끝나는 `COMMAND:PAYLOAD`가 필요하지만, 현재 PAN/TILT 추적 루프는 echo 응답을 기다리지 않습니다.

사용자 확인 구성은 NUCLEO-F401RE → PCA9685 → SG90 PAN/TILT입니다. Windows COM 포트를 VMware Serial Port로 연결해 Ubuntu `/dev/ttyS0`에서 통신하며, UART 송수신 및 PAN/TILT 동시 사람 추적을 실제로 확인했습니다. `TRACK:CENTER`는 현재 PAN 위치 유지이며 중앙 각도로 복귀하는 명령이 아닙니다.

STM32 펌웨어와 상세 핀·배선은 저장소에 포함되어 있지 않습니다. 보정값과 연결 기록은 [작업 기록](docs/2026-11-18-pan-tracking.md)을 참고하세요. 사용자 검증 구성은 PAN 채널 0, TILT 채널 1이며 보드 초기화 시 두 축을 각각 320으로 설정합니다. STM32에서 TILT 물리 방향을 보정해 UP은 실제 위쪽, DOWN은 아래쪽으로 이동합니다. UART·실제 TILT 제어까지 확인했고 안정화 튜닝은 다음 단계입니다.

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

`scripts/test_input.py --headless` 실행에는 카메라와 `/dev/ttyS0`에 연결된 외부 장치와 포트 접근 권한이 필요합니다. 현재 PAN/TILT 추적 루프는 응답을 기다리지 않습니다. 시리얼 연결·쓰기 오류가 발생하면 예외를 출력하고 종료합니다. 별도의 STATE 실행 경로는 여전히 1초 읽기 타임아웃을 사용합니다. `scripts.inspect_model`은 카메라와 시리얼 장치 없이 실행할 수 있습니다. 모델 로드와 라벨 파일 읽기는 카메라 처리의 `try` 블록 이전에 이루어지므로, 의존성이나 파일 경로 오류는 해당 블록에서 처리되지 않습니다.

## Troubleshooting

- UART 응답 타임아웃 시 약 4.5~5.0 FPS / 200~220ms에서 0.82~0.83 FPS / 약 1200ms로 하락했습니다. 사용자가 추적 루프의 blocking receive를 제거한 후 명령 전송 중에도 약 4~5 FPS 유지를 확인했습니다.
- `/dev/ttyS0`이 열려도 echo가 `b''`라면 VMware VM Settings → Serial Port에서 **Connected**와 **Connect at power on**을 확인합니다. 사용자는 Connected 비활성화를 해결해 통신을 복구했습니다.
- PAN 중앙 부근 왕복은 EMA, 히스테리시스 확대 및 오차 기반 가변 전송 간격을 적용한 뒤 감소했습니다.

자세한 관찰값과 튜닝 내용은 [2026-11-23 작업 기록](docs/2026-11-23-tracking-stability.md)을 참고하세요. 기존 USB 허브 연결로 타임아웃이 줄었던 사례는 2026-10-14 사용자 관찰이며, 이번 VMware Connected 문제와 동일 원인으로 확정하지 않았습니다.

## 검증 범위 및 현재 한계

모듈별 수동 확인 코드와 Git에서 제외한 로컬 `tests/`가 있습니다. 2026-11-18 사용자가 카메라·UART·STM32·PAN 서보 통합 동작을 확인했으며, [작업 기록](docs/2026-11-18-pan-tracking.md)에 결과를 남겼습니다. 사용자 측정 프레임 처리 시간은 약 200~230ms이며, 검출 정확도와 모델 단독 추론 시간의 정량 평가는 아직 없습니다.

- TRACK 루프는 응답 대기를 제거했지만 시리얼 쓰기는 동기식입니다. STATE 경로는 응답 대기 동안 영상 처리가 대기합니다.
- STATE 경로는 수신 타임아웃·패킷 오류 시 종료합니다. TRACK 루프는 수신하지 않으므로 응답 타임아웃으로 대기하지 않습니다.
- 상태 전송 직후 이전 상태를 갱신하며, 상대 장치의 처리 성공을 확인하지 않습니다.
- LEFT/RIGHT의 주기적 반복 전송은 있지만, 통신 실패에 대한 재시도, 상시 수신, 자동 재연결, 체크섬은 구현되어 있지 않습니다.
- 객체 검출과 딥러닝 추론은 별도 스크립트에 구현되어 있으며, 방향 판단 및 시리얼 전송도 연결되어 있습니다. 밝기 메인과의 통합 및 동일 인물 추적은 구현되어 있지 않습니다.
- PAN 튜닝 후 중앙 부근 왕복·과이동 감소와 PAN/TILT 동시 제어를 사용자가 확인했습니다. TILT 안정화는 다음 단계이며 첫 STEP의 움직임이 미미한 현상은 원인을 확정하지 않았습니다.
- 사용자 관찰 PAN/TILT 동시 루프 성능은 약 4.5~5.0 FPS, 약 200~220ms/frame이며 모델 단독 벤치마크나 검출 정확도 평가는 아닙니다.
- `app/main.py`는 import 시에도 실행 로직이 시작됩니다.

### 2026-10-13 확인 결과

변경된 Python 소스 문법, 합성 이미지 모델 추론·후처리, 방향 판단 경계값 및 모의 시리얼의 `TRACK:LEFT` 패킷 생성을 확인했습니다. 실제 카메라 검출, 외부 장치 응답 및 장치 제어는 이번 검사에 포함되지 않았습니다.

추가 변경 확인: Python `3.10.12`, NumPy `1.26.4`, OpenCV `4.9.0`, `ai-edge-litert` `2.3.0` 환경에서 변경된 두 Python 파일의 문법과 합성 이미지 추론·후처리를 확인했습니다. 대체 런타임이 실제로 선택되었으며, 카메라·GUI·시리얼 통신 및 `Ctrl+C` 자원 정리는 실행 검증하지 않았습니다.


### 현재 로컬 자동화 테스트

2026-11-18에는 로컬 테스트 9개가 통과했습니다. 2026-11-23 현재 실행 결과는 7개 통과, 2개 실패, 테스트 모듈 로드 오류 1개입니다. 실행 흐름 테스트는 모의 결과에 center_y가 없으며 EMA·가변 간격·응답 대기 제거도 반영해야 합니다. test_serial.py는 import 시 실제 /dev/ttyS0을 열어 현재 검사 환경에서 로드에 실패했습니다. 이번에는 테스트 파일을 수정하지 않았습니다.

```bash
python3 -m unittest discover -s tests -v
```

검사 범위는 실제 모델의 합성 이미지 추론, RGB 전처리, 검출 필터·좌표 제한, 방향 히스테리시스 경계, 대상 선택, 반복 전송·CENTER 억제, GUI/headless 및 종료 정리의 모의 실행, 시리얼 패킷·응답 예외, 밝기 판단입니다. 이 자동화 검사는 실제 카메라·STM32를 제어하지 않습니다.

`tests/`는 사용자 요청에 따라 `.gitignore`에 등록하고 기존 파일의 Git 추적도 해제했습니다. 테스트 파일은 로컬에만 존재하므로 clone한 저장소에서는 별도로 준비해야 합니다.

### TILT 단독 하드웨어 확인

```bash
python3 -m scripts.test_tilt
```

이 명령은 실제 서보를 움직입니다. UP을 0.3초 간격으로 4회 보내고 1초 대기 후 DOWN을 0.3초 간격으로 4회 보냅니다. STEP은 사용자 STM32 설정에서 5이며, 테스트는 응답을 읽지 않습니다. 테스트 후 기계적 중앙으로 복귀시키는 명령은 없습니다.
