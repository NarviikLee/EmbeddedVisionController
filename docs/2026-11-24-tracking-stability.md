# 2026-11-24 최고 confidence 타깃 선택 및 TILT 안정화

현재 Python 코드와 대조한 구현 기록입니다. 실제 하드웨어 결과·성능·설치 계획은 사용자 제공 내용을 구분해 기록합니다. 이전 단계는 [PAN/TILT 통합 기록](2026-11-23-pan-tilt-integration.md)을 참고하세요. 과거 날짜 문서의 미구현 항목은 당시 상태입니다.

## 타깃 선택

find_target()은 감지 목록에서 지정 라벨(기본 person)만 후보로 모아 score가 가장 높은 객체를 반환합니다. 후보가 없으면 None, 동점이면 먼저 나온 후보를 선택합니다. 이전 첫 person 선택보다 confidence를 우선하도록 개선했습니다. 의자·배경 등의 중복 오검출에서 잘못된 선택을 줄이려는 목적이며, 높은 confidence가 실제 사람임을 보장하지는 않습니다. 동일 인물 추적도 아니므로 프레임 사이에 대상이 바뀔 수 있습니다.

## 축별 필터·히스테리시스·전송 상태

| 설정 | PAN | TILT |
|---|---|---|
| EMA alpha | 0.4 | 0.4 |
| 실행 루프 복귀 dead zone | 60px | 45px |
| 실행 루프 이탈 dead zone | 85px | 70px |
| 함수명 | determine_pan_direction | determine_tilt_direction |
| 명령 | TRACK:LEFT/CENTER/RIGHT | TILT:UP/CENTER/DOWN |
| 반복 간격 | 오차별 0.20~0.50초 | 0.4초 |

determine_pan_direction() 함수 기본 dead zone은 50/70이며 실행 루프에서 60/85를 명시합니다. TILT 함수 기본값과 호출값은 모두 45/70입니다. 함수는 (direction, error)를 반환합니다.

두 축 모두 첫 검출 시 raw 중심으로 필터를 초기화하고 이후 filtered = 0.4 * raw + 0.6 * previous_filtered로 갱신합니다. 방향 오차에는 raw가 아닌 필터 중심을 사용합니다. TILT CENTER에서는 -70 미만이 UP, 70 초과가 DOWN이며 경계 ±70은 CENTER입니다. UP에서는 -45 이상, DOWN에서는 45 이하에서 CENTER로 복귀합니다. 반대편으로 급격히 이동하면 CENTER를 거쳐 다음 프레임에 반대 방향으로 전환할 수 있습니다.

previous_pan_direction / previous_tilt_direction, last_sent_pan_direction / last_sent_tilt_direction, last_pan_move_time / last_tilt_move_time 등 축별 상태가 분리됐습니다. 방향은 매 검출 프레임, 전송 방향·시각은 쓰기 반환 후 갱신합니다. 방향 변경은 즉시, 같은 이동 방향은 간격 조건을 만족할 때 반복, CENTER는 진입 시 한 번 전송합니다. 전송 순서는 PAN 다음 TILT이며 echo 대기는 없습니다.

대상이 사라지거나 최고 score 대상이 바뀌어도 필터·상태는 초기화하지 않습니다. 이전 대상 위치의 영향이 남을 수 있으며 이 동작은 이번에 변경하지 않았습니다. TILT_STEP=5는 사용자 STM32 설정으로 유지되며 펌웨어는 저장소에 없습니다.

## detector 모듈 정리

- load_label / load_model: 라벨 및 런타임·텐서 초기화
- preprocess_frame: 입력 크기로 리사이즈, RGB uint8 배치 텐서 생성
- run_inference: invoke 및 출력 텐서 읽기
- postprocess_detections: score 필터, 좌표 제한, class ID 검증, 박스·중심 결과 및 영상 표시
- determine_pan_direction / determine_tilt_direction: 축별 이전 상태 기반 히스테리시스

DEFAULT_SCORE_THRESHOLD=0.5가 후처리 기본값이며 score_threshold 인자로 바꿀 수 있습니다. class_id가 음수이거나 라벨 목록 길이 이상이면 검출을 건너뜁니다. 사용하지 않는 테스트 주석을 정리하고 들여쓰기·변수명을 통일했습니다. 이 포맷 정리가 코드 diff의 줄 수를 늘렸습니다.

## 사용자 실제 시험 결과와 한계

실제 person 추적에서 약 4.9~5.0 FPS, 약 198~205ms/frame을 유지했습니다. raw center_y보다 filtered_center_y가 완만하게 변하고 중앙 부근 TILT가 CENTER를 유지하는 것을 관찰했습니다. PAN도 기존 EMA·히스테리시스·가변 간격으로 동작했습니다.

성능 수치는 현재 코드의 측정 구간(카메라 읽기~전송)의 관찰이며 GUI 표시·waitKey·후속 로그 출력 시간을 포함하지 않습니다. 모델 단독 추론 시간이나 정확도 평가가 아닙니다.

실내 근거리에서는 person bbox가 화면 높이 대부분을 차지해 center_y가 중앙 근처로 형성되는 경우가 있습니다. 따라서 이 결과로 TILT 전체 추적 범위의 안정화를 확정하지 않으며 현재 설정을 유지하고 더 먼 거리에서 추가 평가·튜닝할 예정입니다.

## 설치 계획 및 다음 작업

팬틸트 킷을 나무판 베이스 위에 3M 듀얼락으로 고정해 시험 중 베이스 이동·흔들림을 줄이면서 탈부착은 쉽게 할 계획입니다. 아직 설치 완료 또는 효과 확인 상태는 아닙니다.

다음은 베이스 고정, 더 먼 거리의 TILT 시험, 필요 시 추가 튜닝 및 기존 로컬 테스트의 새 함수명·최고 score 선택·축별 EMA 반영입니다. 현재 설정은 우선 유지합니다.

## 이번 문서 점검에서 수행한 확인

Python 문법, 최고 score 후보 선택 및 후보 없음 처리, TILT 이탈·복귀 경계 8개 사례, PAN 85픽셀 이탈 경계, 음수·범위 초과 class ID 제외와 score 0.5 경계를 하드웨어 없이 검사했고 통과했습니다. 전체 로컬 테스트는 갱신·재실행하지 않았으며 실제 카메라·시리얼·서보 재시험도 하지 않았습니다.
