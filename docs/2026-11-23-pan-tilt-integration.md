# 2026-11-23 PAN/TILT Vision 추적 통합

이 기록은 [PAN 안정화 및 TILT 방향 판단](2026-11-23-tracking-stability.md) 이후 같은 날 진행한 실제 TILT 연동 작업입니다. Python 구현은 현재 코드와 대조했고, STM32 변경 및 실제 하드웨어 결과는 사용자 제공 기록입니다. STM32 펌웨어는 저장소에 포함되어 있지 않습니다.

## 완료한 경로

```text
UVC → OpenCV → EfficientDet-Lite0 → person bbox
  ├─ center_x → EMA_x → PAN hysteresis → 가변 간격 → TRACK:*
  └─ center_y → error_y → TILT 방향 → 고정 반복 간격 → TILT:*
→ UART /dev/ttyS0 → NUCLEO-F401RE → PCA9685 → SG90 PAN/TILT
```

사용자는 PAN 좌우, TILT 상하 및 두 축의 동시 Vision 추적을 확인했습니다.

## Python UART 및 상태 관리

communication/serial_comm.py에 send_tilt(ser, direction)을 추가했습니다. create_packet("TILT", direction)으로 LF로 끝나는 TILT:UP, TILT:DOWN, TILT:CENTER 패킷을 생성합니다. TRACK은 PAN, TILT는 상하 축으로 의미를 구분합니다.

실행 루프는 last_sent_tilt_direction 및 last_tilt_move_time을 PAN 상태와 별도로 유지합니다. 방향 변경 시 즉시 전송하고 같은 UP/DOWN은 0.4초 이상 경과 시 반복합니다. CENTER는 진입 시 한 번만 전송합니다. 두 축 전송은 같은 UART에 순차적으로 쓰며 echo/ACK 대기는 없습니다.

TILT 오차는 raw center_y - frame_height // 2이며 -60 미만 UP, 60 초과 DOWN, 나머지 CENTER입니다. EMA_y, TILT 히스테리시스 및 adaptive interval은 아직 적용하지 않았습니다.

## STM32/PCA9685 변경 (사용자 확인)

| 설정 | PAN | TILT |
|---|---|---|
| PCA9685 채널 | 0 | 1 |
| 부팅 위치 | 320 | 320 |
| 보정 범위 | RIGHT 215, LEFT 425 | DOWN 280, UP 350 |
| STEP | 10 | 5 |

부팅 시 PAN 및 TILT에 PCA9685_SetPWM(channel, 0, center)를 적용했습니다. TILT 현재값도 TILT_CENTER로 초기화합니다. UART 파서는 TILT:UP/DOWN/CENTER를 처리해 현재 위치에서 STEP 단위로 이동합니다.

두 축의 CENTER는 기계적 중앙 복귀가 아니라 현재 위치 유지입니다. 초기 UP→PWM 증가, DOWN→감소 매핑이 실제 기구 방향과 반대로 동작해 STM32 actuator 계층에서 방향을 반전했습니다. 현재는 UP 명령으로 카메라가 위쪽, DOWN으로 아래쪽으로 움직입니다. Python의 방향 의미는 유지했습니다.

## TILT 단독 시험

```bash
python3 -m scripts.test_tilt
```

실제 포트를 열고 UP을 0.3초 간격으로 4회, 1초 대기 후 DOWN을 0.3초 간격으로 4회 전송합니다. 사용자 육안 확인에서 두 방향 모두 이동했습니다. 첫 STEP=5에서 움직임이 거의 보이지 않는 경우는 기능 실패로 단정하지 않고 튜닝 과제로 기록했습니다. 기구 유격·서보 deadband 등 원인은 아직 확정하지 않았습니다.

## PAN 유지 설정과 관찰

PAN alpha_x=0.4, enter_dead_zone=60, exit_dead_zone=85 및 절대 오차별 0.20/0.30/0.40/0.50초 간격은 유지합니다.

사용자 로그에서 error_x는 -94.4 → -85.9 → -69.6 → -63.0에서 LEFT를 유지한 뒤 -57.8 → -51.1에서 CENTER로 전환·유지했습니다. 중앙 부근의 작은 검출 변동에도 불필요한 왕복이 기존보다 크게 감소했습니다.

## 성능 및 다음 단계

PAN/TILT 동시 활성화 상태에서 사용자 관찰은 약 4.5~5.0 FPS, 약 200~220ms/frame입니다. 예시는 4.57/219.0ms, 4.81/207.9ms, 4.95/202.1ms, 5.01/199.8ms입니다. TILT UART 추가로 인한 큰 저하는 관찰하지 않았습니다. 이는 현재 FPS 출력 구간의 측정이며 GUI·waitKey 및 로그 출력 전체나 모델 단독 추론 시간과 동일하지 않습니다.

다음은 PAN 설정을 유지하며 TILT 실제 추적 반복 시험 → STEP·상하 dead zone 튜닝 → 필요 시 EMA_y·adaptive interval → 두 축 동시 안정성 재검증 순서로 진행합니다. 전체 경로의 기능 동작은 확인했지만 TILT 안정화 완료를 의미하지는 않습니다.
