# 2026-11-27 고정 환경 STEP 튜닝 및 소실·재추적 검증

## 소스 비교와 증거 범위

GitHub fetch 후 main과 origin/main은 99a3a37로 동일했습니다. 문서 작업 전 로컬 변경은 scripts/test_input.py의 로그 개선 14줄 추가·11줄 삭제뿐입니다. communication/serial_comm.py와 vision/detector.py는 원격과 같고, 소실 처리와 MOVE는 기존 11월 25일 구현입니다. 이번에는 실행 코드·제어 설정을 수정하지 않았습니다.

STM32 main.c는 별도 CubeIDE 프로젝트에 있으며 저장소에 없으므로 STEP·PWM·Echo 상태와 실제 동작은 사용자 제공 기록입니다. 자동화 검사나 저장소 diff로 펌웨어 변경을 검증한 것으로 해석하지 않습니다.

## 고정 및 STEP 튜닝 (사용자 하드웨어 시험)

장치를 테이프로 바닥에 고정해 장치 자체 흔들림과 카메라 추적 동작을 구분했습니다. 과거 나무판·3M 듀얼락 고정은 계획이며 이번 설치와 구분합니다.

큰 STEP에서 목표를 지나 반대로 보정하는 왕복이 관찰돼 STM32 PAN_STEP 10→5, TILT_STEP 7→3만 변경했습니다. PWM 범위·중앙, Python EMA·히스테리시스는 유지했습니다. 약 5 FPS와 EMA 지연 조건에서 한 명령의 큰 이동량이 원인 후보지만 오버슈트 각도·크기는 정량 평가하지 않았습니다.

변경 후 왕복 감소, 대상 정지 시 비교적 안정적 정지, 좌우·상하 추적 정확성 개선과 자연스러운 동작을 관찰했습니다. 이동 반응은 느려졌으며 현재는 속도보다 정확성과 정지 안정성을 우선해 STEP 5/3을 유지합니다. 11월 25일의 UART/Echo 문제와 동일 원인으로 단정하지 않습니다.

## 소실·재검출 반복 시험

정면 정상 추적 → 2~3초 이상 시야 이탈 → 1초 소실 로그 → 다른 위치 재등장 → 반대편 재등장까지 반복했습니다. 최종 제공 로그에서 소실 로그는 세 차례였고 짧은 재검출 뒤 다시 소실되는 사례도 있었습니다.

기존 코드는 마지막 검출 후 1초 이상 지나면 target_lost로 중복 로그를 억제하고 양 축 EMA None, 이전 방향 CENTER, 마지막 전송 방향 None으로 초기화합니다. 소실 시 이동 명령을 보내거나 중앙 복귀하지 않으며 마지막 물리 위치를 유지합니다. 재검출은 새 좌표에서 EMA를 시작합니다. 마지막 이동 시각은 남지만 None 방향 때문에 첫 명령 전송은 가능해집니다.

사용자는 소실 중 MOVE 중단, 재검출 후 송신 재개, LEFT/RIGHT 변경·UP/DOWN 생성 및 실제 재추적을 확인했습니다. 대표 로그:

```text
[INFO] Target lost for 1 second
...
TX MOVE -> LEFT,CENTER (17 bytes)
TX MOVE -> LEFT,HOLD (15 bytes)
...
TX MOVE -> CENTER,HOLD (17 bytes)

[INFO] Target lost for 1 second
...
TX MOVE -> RIGHT,DOWN (16 bytes)
TX MOVE -> RIGHT,HOLD (16 bytes)
...
TX MOVE -> CENTER,HOLD (17 bytes)
```

기본 소실·재추적 검증이지 장시간 안정성이나 자동 탐색 완료가 아닙니다. 현재 카메라 시야에 다시 들어와야 재검출할 수 있고, 동일 인물 Target Lock도 없습니다.

## 이번 Python 변경

TX MOVE 출력에서 verbose 조건을 제거해 일반 실행에서도 전송마다 축·바이트 수를 확인합니다. 이것은 serial.write() 실행 기록이며 STM32 수신·PWM 실행 ACK가 아닙니다.

카메라 열기 확인 후 last_fps_log_time을 초기화하고 time.monotonic() 기준 1초 이상 지난 프레임에서 FPS를 출력합니다. 평균 누적 FPS가 아니라 출력 시점의 한 프레임 elapsed와 그 역수입니다. 측정 구간은 카메라 읽기~판단·전송·해당 로그까지이며 이후 GUI·waitKey·FPS 로그 출력 시간은 빠집니다.

사용자 로그 최초 0.97 FPS/1032.5ms 후 일반 구간은 약 4.6~5.0 FPS이며 예시는 4.84/206.6ms, 4.99/200.5ms, 5.04/198.5ms, 4.91/203.8ms입니다. 최초 지연은 워밍업 가능성일 뿐 원인을 확정하지 않았습니다. 해당 시험에서 중단이나 뚜렷한 성능 붕괴는 관찰하지 않았지만 장시간 검증을 대신하지 않습니다.

## 유지 설정 및 불일치

| 항목 | 최신 코드 또는 사용자 확인 |
|---|---|
| PAN/TILT alpha | 0.4 / 0.4 |
| PAN 복귀/이탈 | 60 / 85px |
| TILT 복귀/이탈 | 45 / 70px |
| PAN 목표점 | bbox 중앙 x |
| TILT 목표점 | bbox 상단 35%의 EMA |
| 소실 timeout | 1.0초 |
| 대상 선택 | person 최고 confidence |
| UART | MOVE:PAN,TILT + LF, 115200bps, /dev/ttyS0 |
| PAN 반복 간격 | 절대 오차 >150/100/70/그 외: 0.20/0.30/0.40/0.50초 |
| TILT 최근 시험 기록 | 고정 1.0초 |
| TILT 실제 파일 | 절대 오차 >150/100/70/그 외: 0.30/0.40/0.50/0.60초 |

TILT 파일값과 최근 시험 설정은 여전히 불일치합니다. 0.8초 제안·1초 시험 기록만으로 현재 파일을 덮어쓰지 않았습니다. 정확한 시험 파일 또는 최종값 확인이 필요하며, 방향 변경 즉시 전송과 CENTER 억제는 반복 간격과 별개입니다.

사용자 최신 STM32 설정:

```c
#define PAN_RIGHT       210
#define PAN_CENTER      320
#define PAN_LEFT        431
#define PAN_STEP        5
#define TILT_PWM_MIN    280
#define TILT_CENTER     380
#define TILT_PWM_MAX    480
#define TILT_STEP       3
```

범위·중앙은 11월 25일 제공 값, STEP만 오늘 갱신됐습니다. Echo 비활성화, MovePan/MoveTilt, 미전송 축 HOLD 및 위치 유지 CENTER 의미를 유지합니다.

## 다음 작업

1. 현재 정상 시험에 사용한 Python 파일·CubeIDE 설정 보존 및 TILT 간격 대조
2. 장시간 추적, 양 축 왕복, 반복 소실·재등장, PWM 한계·전원, VMware COM3 재발 여부 확인
3. 사진·시연 영상·주요 로그·STEP 전후 비교·상태 흐름과 한계를 포트폴리오에 정리

Target Lock, UART 인터럽트/DMA·ACK·한계 피드백, 부드러운 목표값 이동, 평균 FPS·추적 오차 정량 평가는 향후 후보이며 현재 구현 완료로 기록하지 않습니다.
