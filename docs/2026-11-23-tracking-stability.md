# 2026-11-23 PAN 안정화 및 TILT 방향 판단

지난 Git 업데이트 a27675b 이후의 작업입니다. 하드웨어 관찰과 튜닝 결과는 사용자가 제공한 작업 기록을 기준으로 하며, 이번 문서 작업에서 실제 장치를 재시험하지 않았습니다. 기존 환경·배선 경로·보정 기록은 [2026-11-18 기록](2026-11-18-pan-tracking.md)을 참고하세요.

## UART 응답 대기와 성능

기존 TRACK 전송 직후 receive_packet()으로 STM32 echo를 기다리면서 1초 읽기 타임아웃이 비전 루프를 막았습니다.

| 관찰 조건 | FPS | 프레임 처리 시간 |
|---|---|---|
| 응답 지연 없는 상태 | 약 4.5~5.0 | 약 200~220ms |
| UART 타임아웃 발생 | 약 0.82~0.83 | 약 1200ms |
| 추적 루프 응답 대기 제거 후 | 약 4.3~5.0 | 약 200~230ms |

약 0.2초의 기존 처리 구간에 약 1초의 응답 대기가 더해진 것으로 분석했습니다. 현재 TRACK 경로는 send_track() 이후 마지막 전송 방향·시간만 갱신합니다. STM32 echo 기능은 유지하지만 추적 루프에서 읽지 않습니다. STATE 경로의 receive_packet()은 유지합니다.

이는 비동기 통신이나 ACK 성공 검증을 구현한 것이 아닙니다. 시리얼 쓰기는 동기식이며, 읽지 않은 echo의 누적·향후 수신 정책은 별도 검토 대상입니다. 현재 FPS 출력은 GUI 표시·waitKey·로그 출력 이전까지의 루프 구간이며 모델 단독 추론 벤치마크가 아닙니다.

## VMware 포트는 열리지만 echo가 빈 경우

/dev/ttyS0을 열고 TRACK:LEFT와 LF를 보냈지만 readline()은 b''를 반환했습니다. VMware Serial Port의 Connected가 꺼져 있었으며 아래 설정 후 사용자 UART 통신·STM32 제어가 복구됐습니다.

```text
VM Settings → Serial Port
→ Connected 체크
→ Connect at power on 체크
```

장치 경로가 존재하거나 포트 열기에 성공하는 것만으로 Windows COM 포트까지의 연결을 보장하지 않습니다.

## PAN 안정화

```text
person → raw center_x → EMA → filtered error_x
→ hysteresis → adaptive command interval
→ TRACK → STM32 → PCA9685 → PAN
```

EMA는 첫 값으로 초기화하고 이후 0.4 * 현재 중심 + 0.6 * 이전 필터값을 사용합니다. 사용자 비교에서 alpha 0.3은 안정적이지만 급격한 이동 반응이 느렸고, 0.5는 빠르지만 일부 왕복이 발생해 현재 0.4를 선택했습니다.

실행 루프의 복귀 기준 enter_dead_zone은 60, 이탈 기준 exit_dead_zone은 85픽셀입니다. CENTER에서 오차가 -85 미만 / 85 초과일 때 LEFT / RIGHT로 진입하고, LEFT에서 -60 이상 / RIGHT에서 60 이하일 때 CENTER로 복귀합니다. 함수 자체 기본값은 여전히 50/70입니다.

| 절대 가로 오차 | 같은 방향 반복 전송 간격 |
|---|---|
| >150 | 0.20초 |
| >100~150 | 0.30초 |
| >70~100 | 0.40초 |
| ≤70 | 0.50초 |

방향 변경은 즉시 전송하며 CENTER는 진입 시 한 번 전송합니다. 사용자는 기존보다 중앙 부근의 과이동·좌우 왕복 감소와 PAN 실제 서보 추적을 확인했습니다. 필터와 이전 상태는 대상 소실 시에도 유지되고, 동일 인물 추적은 없습니다.

프레임 읽기 실패 검사 뒤 flip(frame, -1)을 적용하도록 순서도 수정됐습니다.

## TILT 판단

검출 결과에 center_y = (ymin_pixel + ymax_pixel) // 2를 추가했습니다. 세로 오차는 raw center_y - frame_height // 2입니다. -60 미만은 UP, 60 초과는 DOWN, 그 외는 CENTER로 판단합니다. 높이 480의 기준 중심은 240입니다.

| 사용자 검증 center_y | error_y | 결과 |
|---|---|---|
| 239 | -1 | CENTER |
| 367 | 127 | DOWN |
| 170 | -70 | UP |

verbose 로그는 PAN, error_x, TILT, error_y를 함께 표시합니다. 예: PAN=CENTER, error_x=56.9, TILT=UP, error_y=-70.

TILT는 방향 판단 검증까지만 완료했습니다. 현재 UART에는 PAN TRACK만 전송하고 TILT 명령·파싱·실제 추적은 연결하지 않았습니다. TILT EMA·히스테리시스도 아직 없으며 filtered_center_y 변수는 현재 사용하지 않습니다.

기존 보정값은 TILT_DOWN=280, TILT_CENTER=320, TILT_UP=350, TILT_STEP=5입니다. 이 값의 펌웨어 구현은 현재 저장소에 포함되어 있지 않습니다.

## 다음 작업 및 검증 범위

1. TILT UART 명령 설계
2. STM32 파싱 및 PCA9685 TILT 서보 제어 연결
3. 실제 TILT 추적 시험
4. 필요하면 TILT EMA·히스테리시스·전송 간격 튜닝
5. 로컬 테스트의 center_y, EMA, 가변 간격, 수신 대기 제거 반영 및 하드웨어 테스트 분리

현재 로컬 테스트 결과는 7개 통과, 실행 흐름 2개 실패, 실제 포트 접근 테스트 모듈 로드 오류 1개입니다. 실패한 모의 입력에는 center_y가 없고 포트 오류는 검사 환경에 /dev/ttyS0이 없어서 발생했습니다. 사용자의 하드웨어 실측과 자동화 검사 결과는 별개의 검증 범위입니다.
