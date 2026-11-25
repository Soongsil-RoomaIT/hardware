# A 담당 전달: SAD v1.4 hardware 연동 계약

B 저장소만 수정한다. 기존 Edge Agent의 최신 main(`88e27829` 확인 시점)은 dht_only와 button_panel은 지원하지만 아래 신규 옵션은 아직 연결해야 한다. 이 문서는 **A가 변경할 사항**이지 A 코드 변경 완료 기록이 아니다.

## 1. HardwareBundle 생성

```python
from roomcare_hw.bundle import HardwareBundle

# 예시: 실제 배선·MC-38·서보 교정·MQ-2 입력전압 및 극성을 검증한 이후에만 enable.
with HardwareBundle(
    starter=True,                # A의 dht_only=true -> 기존 변환 유지
    temperature_model="DHT11",
    window_led=True,
    purifier_led=True,
    dehumidifier_led=True,
    door_sensor=True,
    door_magnetic=True,
    door_verified=True,
    door_closer=True,
    gas_sensor=True,
    gas_active_low=True,          # 실물에서 확인
    gas_warmup_seconds=180.0,     # 실제 모듈 제조사 요구에 맞춰 조정
    door_rest_angle=-60.0,       # 모형 교정 후 변경
    door_push_angle=60.0,
    door_hold_seconds=1.0,
    door_return_seconds=0.8,
) as hw:
    sensor = hw.sensor
    actuators = hw.actuators
    door = hw.door_sensor
    gas = hw.gas_sensor
    # 위 객체를 Edge Agent에 연결. 이 with 예시 자체로 장시간 실행하지는 않음.
```

A의 `HardwareConfig.bundle_kwargs()` 및 config 예시에 신규 옵션을 추가한다. `starter=True`는 이미 연결된 `dht_only`의 결과다. v1.4에서는 `window_motor`, `button_panel`, `window_button`, `purifier`(이전 서보), `dehumidifier`(이전 서보)는 false로 유지한다. `door_verified`는 실제 검증 전 false이며, `door_closer=True`와 같이 쓰려면 true가 필요하다. 설정의 신규 항목을 B와 동일하게 합의한다. HardwareBundle 소유 자원은 기존 `hw.close()`로 일괄 종료된다.

## 2. 저수준 인터페이스

| 대상 | 읽기/제어 | 의미 |
|---|---|---|
| 온습도 | `hw.sensor.read()` | 기존 `measured_at`, `temperature`, `humidity`, `co2`, `pm25`; `pm10`도 None |
| MQ-2 | `hw.gas_sensor.gas_detected` / `hw.gas_detected` | True 감지, False 미감지, None 예열/오류/미설치/만료 |
| MQ-2 | `when_detected`, `when_cleared` | 인자 없는 선택 콜백, 상태 전이 시 호출. 스레드에서 실행되므로 빠르게 큐에 넣는 용도로만 사용 |
| MQ-2 | `warming_up`, `last_error` | 준비/읽기 오류 진단 |
| MC-38 | `is_open`, `position`, `when_opened`, `when_closed`, `magnet_present` | 내부 풀업, LOW=닫힘, 검증 전 위치 unknown |
| 창문 LED | `set(True/False)`, `is_on`, `position` | 켜짐=open, 꺼짐=closed |
| 공기청정기/제습기 LED | `set(True/False)`, `is_on`, `state` | ON/OFF, 직접 제어·멱등 |
| LED 공통 | `state_source = "COMMANDED"`, `is_moving=False`, `fault` | 실제 GPIO 제어 상태(광학 독립 검증 아님), 오류 시 unknown |
| 현관문 서보 | `set(False)`, `is_on`, `is_moving`, `fault` | 닫기 전용; MC-38 실제 닫힘을 확인하고 완료 처리 |

장치 이름은 `window`, `air_purifier`, `dehumidifier`, `door` 그대로다. A의 `devices`·`ack` 송신 경로에서 LED의 상태 출처를 읽어 `stateSource: "COMMANDED"`로 전달하고 문은 `SENSOR`로 보낸다. 단순 LED 점등은 곧 동작 완료이며 별도의 서보 대기는 없다.

## 3. A의 정책 변경 (B에서 구현하지 않음)

- **A-1:** MC-38 open→600초 타이머, 30초 시연 설정, 먼저 닫히거나 원격 닫기 시 취소. 오프라인에서도 실행하고 닫힘 확인. C 규격의 예약 시각 보고. B의 `DoorAutoCloser`를 함께 실행하지 않는다.
- **A-2:** 오프라인에서 습도 >70% 제습기 ON, <60% OFF(기준 사이 유지). 일반 온도/CO₂/외기 규칙으로 창문을 움직이지 않는다.
- **A-4:** MQ-2를 온습도 읽기와 독립적으로 루프에서 확인한다. DHT 오류가 발생해도 가스 감지 경로를 계속 실행한다. True이면 온라인·오프라인 모두 창문 LED를 켜고, 감지 중에는 다른 자동/수동 닫기 명령을 차단하도록 A/C 합의. False이면 일반 규칙으로 복귀하고 자동으로 무조건 닫지는 않는다. None은 정상(false)으로 취급하지 않는다. 콜백은 선택이며 초기 True나 콜백 등록 전 전이를 놓치지 않도록 루프에서 tri-state를 읽는다.
- 이벤트 `gas_detected`/`gas_cleared`는 A가 중복 없이 생성·저장·전송한다. 오류/예열 전환을 cleared로 보고하지 않는다. 가스 감지 중 제어 우선 정책은 A의 책임이다.
- **C-4 완료 후에만** `sensors` MQTT payload의 `gasDetected: true/false/null`을 추가한다. 현재 B는 별도 센서 속성만 제공하므로 기존 센서 payload 형식은 자동으로 바뀌지 않는다. MQTT 통신 자체는 A/C가 합의한 roomait-v1과 ISO timestamp를 사용한다.
- 현관문 예정 시각, 가스 이벤트의 정확한 schema는 D의 v1.4 연동 요청서를 기준으로 A/C가 맞춘다. SAD의 과거 Unix/telemetry 설명과 차이가 있다.

## 4. 인수시험

D에게 VM 기동 요청 후 INT-01/02/03/06, 현관문 예약 및 600초/30초, MQ-2 오프라인 감지 및 복구 후 알림을 함께 시험한다. 실제 시험 결과만 기록한다. VM IP/비밀번호/개인 설정은 Git에 올리지 않는다.
