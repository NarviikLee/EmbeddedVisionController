# 2026-11-18 PAN 추적 통합 작업 기록

이 기록의 실제 하드웨어 동작과 설정값은 사용자가 수행한 테스트 및 제공한 작업 정리를 기준으로 합니다. 저장소에는 STM32 펌웨어가 포함되어 있지 않으며, 아래 값의 단위와 펌웨어 구현은 코드로 확인하지 않았습니다.

## 실행 환경 및 전체 경로

Raspberry Pi 4B 문제로 VMware Ubuntu 20.04 환경으로 전환했습니다.

```text
Innomaker U20CAM-720P (USB 2.0 UVC)
→ OpenCV → EfficientDet-Lite0 → person 검출
→ center_x / direction → UART
→ NUCLEO-F401RE → PCA9685 → SG90 PAN/TILT
```

현재 PAN 좌우 사람 추적까지 실제 동작을 확인했습니다. TILT 서보 보정은 완료했으나 영상 기반 상하 추적은 아직 구현하지 않았습니다.

## 카메라 연결 및 검출

VMware USB passthrough에서 `Microdia Innomaker-U20CAM-720P`의 `Driver error`가 발생했고 Ubuntu의 `lsusb` 및 `/dev/video*`에 카메라가 나타나지 않았습니다. VMware USB 컨트롤러를 USB 3.0 방식으로 설정하고 다시 연결한 뒤 인식됐습니다. 카메라 자체는 USB 2.0 제품입니다.

- USB 확인: `0c45:6367 Microdia Innomaker-U20CAM-720P` (당시 Bus 003 Device 005)
- 생성된 장치: `/dev/video0`, `/dev/video1`
- `cv2.VideoCapture(0)`: 열기 및 프레임 읽기 성공
- 확인한 프레임 형태: `(480, 640, 3)`

```bash
python -m scripts.test_input --verbose
```

GUI에서 person 검출, bbox, center_x, error_x 및 LEFT/CENTER/RIGHT 판단을 확인했습니다.

## VMware 시리얼 연결

```text
NUCLEO-F401RE → Windows COM Port
→ VMware Serial Port → Ubuntu /dev/ttyS0
```

VMware 설정에서 Serial Port를 추가하고 Windows의 보드 COM 포트를 연결했습니다. USB passthrough로 보드를 직접 넘기는 구성 대신 이 경로를 사용합니다.

Python 설정은 `/dev/ttyS0`, 115200 baud, 읽기 타임아웃 1초입니다. UART 송수신과 Vision → UART → STM32 → PCA9685 → PAN 서보의 통합 동작을 사용자가 확인했습니다. `TRACK:CENTER`는 PAN을 중앙 보정값 320으로 복귀시키는 명령이 아니라 현재 위치를 유지하는 명령입니다.

## 장착 방향 보정

팬틸트에 카메라를 장착하면 영상의 상하·좌우 보정이 모두 필요합니다. `cv2.flip(frame, -1)`을 한 번 적용해 180도 회전시키며, 이후 검출·방향 판단도 보정된 좌표계를 사용합니다.

권장 처리 순서:

```python
ret, frame = cap.read()
if not ret:
    print("Frame read failed")
    break
frame = cv2.flip(frame, -1)
```

`flip(frame, 0)`과 `flip(frame, -1)`을 연속 적용하면 최종적으로 좌우 반전만 남으므로 두 번 적용하지 않습니다. 문서 작성 시점의 실행 코드는 `ret` 검사 전에 `flip(frame, -1)`을 호출하고 있습니다. 이번 문서 업데이트에서는 실행 코드를 수정하지 않았습니다.

## 현재 설정과 PAN 진동

| 항목 | 현재 값 |
|---|---|
| enter_dead_zone | 50픽셀 |
| exit_dead_zone | 70픽셀 |
| MOVE_INTERVAL | 0.2초 |
| PAN_RIGHT / CENTER / LEFT | 215 / 320 / 425 |
| PAN_STEP | 10 |
| TILT_DOWN / CENTER / UP | 280 / 320 / 350 |
| TILT_STEP | 5 |

PAN은 사람을 따라 움직이지만 중앙 부근에서 좌우 진동이 관찰됐습니다. 프레임·추론 처리 지연과 고정 이동량 때문에 중앙에 가까워진 뒤에도 이전 프레임 기준 명령으로 더 이동하고 반대 방향으로 보정하는 상황을 원인 후보로 보고 있습니다. 지연 및 원인별 영향은 아직 측정으로 확정하지 않았습니다.

## 다음 작업

1. center_x, error_x, direction과 프레임 처리·송수신 시간을 측정해 진동 분석
2. 사용자 제공 사양인 120° FOV와 실제 오차 분포를 고려해 dead zone / hysteresis 조정
3. 추론 지연과 서보 이동량을 고려해 MOVE_INTERVAL 조정
4. 부족하면 raw center_x → EMA → error_x → direction 필터링 검토
5. 고정 PAN_STEP 안정화 후 오차에 따른 proportional control 검토
6. PAN 안정화 후 center_y → 수직 오차 → UP/CENTER/DOWN → TILT 추적 구현

## 검증 범위

- 사용자 실측: 카메라 입력, 사람 검출, 방향 판단, UART 송수신, PAN 실제 추적 및 영상 방향 보정
- 로컬 자동화: 합성 이미지 모델 추론, 전처리·후처리, 방향 경계, 반복 전송, GUI/headless 모의 흐름, 패킷 및 밝기 판단의 9개 테스트
- 미완료: PAN 진동 안정화, 정확도·지연 정량 측정, 영상 기반 TILT 추적

`tests/`는 로컬 전용으로 Git 추적에서 제외합니다. 다른 컴퓨터에서 clone해도 테스트 파일은 제공되지 않습니다.
