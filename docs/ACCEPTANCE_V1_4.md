# SAD v1.4 인수시험 및 요구사항 추적 (B)

기준: SAD v1.4 10.1/10.4 및 D 작성 연동 요청 B-1~B-4. 자동 테스트와 실물 시험을 구분한다.
아래 결과는 **전부 미실시**로 시작한다. 실제 결과·증거가 있을 때만 변경한다.

| ID | 시험 절차 | 합격 기준 | 담당 | 결과/증거 |
|---|---|---|---|---|
| HW-01 | 전원 분리 후 핀표, LED 저항, MQ-2 분압/레벨 변환, 별도 서보 전원·GND 검사 | Pi 입력 3.3V 이하 및 정상 논리 레벨, 전원·기구 안전 확인 | B | 미실시 |
| HW-02 | DHT11을 5분 이상 측정하고 실제 측정·오류 기록 | 온습도 갱신, 미장착 CO₂/PM null, 오류 시 허위값 없음 | B | 미실시 |
| HW-03 | 창문 LED 열기/닫기 및 동일 명령 반복 | OPEN에서 계속 점등, CLOSED에서 소등, 중복 명령에 토글되지 않음 | B | 미실시 |
| HW-04a | MC-38 자석 부착·분리 및 모형 20회 개폐·닫힘 지속 10분 | LOW=닫힘, HIGH=열림, 지속 감지 및 극성 확인 | B | 미실시 |
| HW-04b | 모형 서보 1회 닫기, 센서로 도달 확인, 이미 닫힌 상태 및 열기 명령 | 실제 닫힘 확인, 열기 금지, 중복 밀기 없음, 시간 제한·정지 가능 | B | 미실시 |
| HW-04c | A의 600초 타이머와 시연용 30초, 수동 닫기 취소 및 오프라인 | Edge만 타이머를 세고 서보로 닫음, MC-38 확인, 예정 시각 보고 | A+B | 미실시 |
| HW-05 | 각 가전 LED ON/OFF 50회와 동일 명령 반복 | 지속 점등/소등 일치, 상태 COMMANDED | B | 미실시 |
| HW-06 | 정상 종료·동작 중 안전 중단 | LED 소등, GPIO 해제, 정상 서보 동작 후 교정된 rest 위치, 중단 시 추가 밀기 없이 PWM 해제. 기구 안전 별도 확인 | B | 미실시 |
| HW-07 | MQ-2 예열, 안전한 승인 시험 방식으로 감지/해제 | 예열/읽기 오류 None, 감지 True, 해제 False, 논리 극성·전압 확인 | B | 미실시 |
| INT-01 | 온습도 측정→실제 웹 표시 | 5초 이내 | A+B+C+E | 미실시 |
| INT-02 | 웹 명령→LED 또는 서보 동작 시작 | 5초 이내 | A+B+C+E | 미실시 |
| INT-03 | 핫스팟 단절→복구 | 10초 이내 전환·제습기 LED·복구 리포트 | A+B+C+D+E | 미실시 |
| INT-06 | MQ-2 감지→창문 LED, 온라인 알림/오프라인 제어 | 감지 중 열린 상태 유지, 통신 복구 후 이벤트 반영 | A+B+C+D+E | 미실시 |

INT-04/05(AI)는 C/D/E 중심이며 B 드라이버 자체의 합격 기준이 아니다.

## B-1~4 추적

| 연동 요청 | 구현 | 검증 |
|---|---|---|
| B-1 | `sensors/magnetic.py`, `HardwareBundle(door_magnetic=True)` | MC-38 풀업/극성, 기존 콜백, HW-04 |
| B-2 | `actuators/led.py`, `pins.py`, LED bundle 옵션 | 50회/멱등성/고장/종료 Mock, HW-03·05·06 |
| B-4 | `sensors/mq2.py`, gas bundle 옵션 | 예열/극성/전이/오류 Mock, HW-01·07, INT-06 |
| B-3 | 배선·모형 가이드, `examples/demo_v14.py` | HW-01~07 실제 실행 및 기록 필요 |

## 자동 시험

```bash
python -m pip install -e '.[dev]'
python -m ruff check roomcare_hw examples tests
python -m ruff format --check roomcare_hw examples tests
python -m pytest -q
python examples/simulate_hardware.py
```

실제 Pi와 센서의 정확도, 전압, 기구 안전, 전체 MQTT/웹 연결은 Mock 테스트로 합격 처리하지 않는다.

## 실측 기록 양식

- 시험 날짜 / 담당 / Pi 모델 / OS / Python:
- DHT11 모듈, MC-38 접점 및 극성, MQ-2 모듈 모델/DO 극성/예열 시간:
- MQ-2 전압 측정 (DO high/low, 변환 후 high/low, 공급전압):
- 서보 모델 / 별도 전원 정격 / 퓨즈 / rest·push 각도 / hold·return 시간:
- HW 시험 결과 / 오류 / 재시험 조치:
- 배선 사진 / 동영상 / 터미널 로그 / 통합 시험 측정값:
