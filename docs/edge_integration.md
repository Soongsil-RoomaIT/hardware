# A 담당과 연결하는 방법

2026-10-02에 확인한 `edge_agent/src/edge_agent/devices.py`, `agent.py`, `config.py`의
공개 인터페이스를 기준으로 합니다. 다른 저장소를 자동 변경하지 않습니다.

## 1. 기존 계약 유지

`Reading`의 다섯 필드/단위와 `read()` 및 `set(on)`은 유지합니다.
`CachedSensorReader(RoomSensorReader(...))`를 사용해 UART/I2C가 A의 0.5초 통신 점검을 막지 않게 합니다.
전체 센서용은 정상 수치가 모두 모였을 때만 반환합니다.
하나가 실패하면 `OSError`이므로 기존 Edge의 센서 오류 처리로 전달됩니다.

`measured_at`은 합쳐진 수치 중 가장 오래된 획득 시각입니다.
CO₂가 새 값이 아니면 이전 timestamp를 유지합니다. 이 시각은 라이브러리가 값을 가져온 시각이며
센서 내부 측정 시작 시각과 같다고 보장할 수 없습니다.
캐시는 기본 4초보다 오래된 값을 반환하지 않습니다. 수집 타이밍에 따라 새 CO₂ 값이
나오기 전 일시적으로 stale 오류가 발생할 수 있으며, 이때 이전 값을 새 값처럼 발행하지 않습니다.
SCD41은 자체 주기가 약 5초이므로 예열·수집·발행 주기를 포함해 NFR-01을 실측해야 합니다.

## 2. 제공된 실행 진입점

라즈베리파이에 두 저장소를 형제 폴더로 복제한 상태를 가정합니다.
`hardware`에서 만든 가상환경을 활성화한 다음 같은 환경에 Edge 패키지를 설치합니다.

```bash
cd hardware
source .venv/bin/activate
python -m pip install -e '.[hardware]'
python -m pip install -e ../edge_agent

# 실제 전체 센서만 연결. actuator는 생성하지 않음
python examples/edge_agent_hardware.py --config ../edge_agent/config/config.toml

# 기구 검증 후 창문 모터/공기청정기를 함께 연결
python examples/edge_agent_hardware.py --config ../edge_agent/config/config.toml --enable-control --purifier-current off
```

`--purifier-current off`는 실제 전원이 꺼진 것을 확인했을 때만 지정합니다.
SHT31 대신 DHT11을 계속 쓰려면 `--temperature-model DHT11`을 붙입니다.
CO₂와 PM 센서는 이 실행에서 여전히 필수입니다.
설정의 MQTT 주소·인증·TLS는 A/D가 준비한 값을 사용합니다. 이 저장소가 인증을 설정하지는 않습니다.
이 진입점은 `build_agent()`의 미구현 경로 대신 `EdgeAgent` 생성자를 사용합니다.

## 3. 조합 API

```python
from roomcare_hw.bundle import HardwareBundle

with HardwareBundle(
    temperature_model="DHT11",
    window_touch=True,
    touch_verified=True,  # 실제 창문 설치 검증 완료 때만
    window_motor=True,
    purifier=True,
    purifier_initial=False,  # 실제 전원 상태 확인
    dehumidifier=True,
    dehumidifier_initial=False,
    door_sensor=True,
    door_verified=True,
    door_closer=True,
) as hw:
    # hw.sensor -> EdgeAgent의 sensor
    # hw.actuators -> EdgeAgent의 actuators
    # hw.door_sensor -> EdgeAgent의 door_sensor
    # read()는 첫 측정 전 OSError, 호출부에서 재시도
    print(hw.status())
```

초기화 중 하나가 실패해도 이미 생성된 자원을 정리합니다.
종료 순서는 액추에이터 → 위치 센서 → 수집 스레드/환경 센서입니다.
`HardwareBundle`은 자동제어 정책을 시작하지 않으며, 모든 액추에이터는 기본 비활성입니다.
`starter=True, temperature_model="DHT11"`은 실습 전용 `PartialReading`입니다.

## 4. A/C/E에서 이어서 반영할 항목

1. `hw.status()`의 창문 상세 상태·장치 fault를 telemetry/event에 추가합니다.
   현재 Edge payload에는 환경 수치만 있고 창문 상세 위치가 없습니다.
2. `set()` 성공은 **명령 수락**입니다. 이후 `position`, `is_moving`, `fault`를 확인하여
   완료/실패 알림을 분리합니다. background timeout은 set 호출 시 예외로 돌아오지 않습니다.
3. bool `is_on=False`는 창문의 완전 닫힘과 같지 않습니다.
   기존 Edge의 “이미 False면 닫기 생략” 최적화는 unknown/중간 위치에서 맞지 않을 수 있습니다.
   창문은 `position == 'closed'`로 도달을 판단하고 필요하면 멱등적인 `set(False)`를 호출하세요.
4. 가전 `is_on`은 알 수 없거나 움직이는 동안 `HardwareFault`를 냅니다.
   버튼을 누르기 전 상태 확인을 요구하는 의도된 동작입니다.
5. 기존 코드에는 DoorAutoCloser가 로컬 정책을 소유한다는 설명이 있으나 역할표에는 C 자동화가 있습니다.
   최종 운영에서는 한쪽만 소유하도록 정하고 승인/재시도/알림을 합의합니다.
   B의 `DoorAutoCloser`는 시험용이며 bundle/통합 진입점에서는 자동 시작하지 않습니다.
6. `dehumidifier` 장치 등록과 습도 제어 규칙, MQTT/UI 처리는 A/C/E가 추가합니다.
7. 실제 모델에 맞는 정지/장애물 피드백을 A 제어 허용 조건에 포함합니다.
8. NFR-01/02/03은 네트워크와 웹까지 포함한 통합 시간 로그로 판정합니다.

현재 보유한 DHT/터치만으로 완성 시스템의 전체 센서 수집이나 CO₂ 기반 자동 환기를 구현했다고
표시하면 안 됩니다. 해당 모드는 학습·배선 검증 단계입니다.
