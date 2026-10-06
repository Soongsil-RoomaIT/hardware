# hardware

자취방 원격 케어 시스템의 **B. 하드웨어(센서·액추에이터)** 구현입니다.

**지금 가진 DHT11 온습도 센서와 DFR0030 터치센서부터 시작하려면
[처음 연결하기](docs/dht11_window_touch.md)를 읽으세요.**

이 저장소는 하드웨어 드라이버와 배선·제작·시험 문서를 제공합니다.
실제 장비는 이 개발 환경에 연결되지 않았으므로, 프로그램 시험과 실제 하드웨어 합격을 구분합니다.

## 1. edge_agent와의 약속 (인터페이스)

| API | 동작 |
|---|---|
| `RoomSensorReader.read()` | SHT31 또는 DHT + SCD41 + PMS7003의 `Reading` 반환. 미장착·오류·오래된 값은 `OSError` (`IOError`와 동일) |
| `CachedSensorReader.read()` | 백그라운드에서 수집한 값을 즉시 반환. 초기화 중·고장·유효기간 경과 시 예외 |
| `DHTReader.read()` | 실습용 `PartialReading`. CO₂·PM2.5는 `None`, JSON에서는 `null` |
| `TouchWindowSensor.position` | `unknown/open/closed`. 설치 검증 전에는 `unknown` |
| `WindowActuator.position` | `unknown/open/closed/opening/closing/fault` |
| `Actuator.set(bool)` | 백그라운드 동작 요청. 기구가 끝까지 움직이기를 기다리지 않음 |
| `close()` | 작업 중단·GPIO/버스 해제. 소유자가 반드시 호출 |

`Reading`의 기존 다섯 필드(`measured_at`, `temperature`, `humidity`, `co2`, `pm25`)와
기존 장치 이름 `window`, `air_purifier`, `door`를 유지했습니다.
`dehumidifier`는 신규 장치입니다. 제습기 정책과 클라우드/UI 명령은 A/C/E 연동이 필요합니다.

**실습용 `PartialReading`을 기존 Edge의 숫자 전용 저장·자동제어에 그대로 넣으면 안 됩니다.**
전체 센서로 전환하거나 A 담당이 null/센서 품질 처리를 추가해야 합니다.

가전 토글 버튼은 시작 상태를 모르면 움직이지 않습니다. `initially_on` 또는 상태 피드백을 제공하세요.
`is_on`은 일부 장치의 상태가 불확실하면 `HardwareFault`를 발생시킵니다.
창문 `is_on=False`만으로 완전 닫힘을 판단하지 말고 `position`을 사용하세요.
자세한 연동 예: [A 담당 전달 문서](docs/edge_integration.md).

## 2. 부품

| 상태 | 용도 | 지원 부품 | 설명 |
|---|---|---|---|
| 사용자 보유 | 온습도 | DHT11 3핀 모듈 | 기본 GPIO4. DHT22도 모델 옵션으로 지원 |
| 사용자 보유 | 창문 상태 실습 | DFR0030 터치 | GPIO24. 장시간 창문 감지 실험 필수 |
| 보유했으나 이번 창문 감지에서 미사용 | 거리 | HC-SR04 | 현재 요구에 사용하지 않아 연결하지 않음 |
| 선택/추가 | 정밀 온습도 | SHT31 브레이크아웃 | I2C 0x44 |
| 추가 | CO₂ | SCD41 브레이크아웃 | I2C 0x62, 첫 주기 측정 대기 필요 |
| 추가 | 미세먼지 | PMS7003 + 전용 케이블/어댑터 | UART, atmospheric PM2.5 사용 |
| 추가 | 창문 | DC 기어모터/리니어 액추에이터 + 적합한 드라이버 | 기존 L298N 배선 지원, 리밋 2개 필수 |
| 추가 | 가전 버튼 | SG90/MG90S 등 서보 1개씩 | 공기청정기/제습기 버튼에 탈부착 |
| 추가 | 현관문 모형 | 별도 상태 센서 + 토크 선정한 서보 | 창문 터치센서와 다른 입력(GPIO23) |
| 추가 | 전원/기구 | Pi 전용 전원, 외부 서보/모터 전원, 브래킷·퓨즈·정지 스위치 | 모델/정격을 확인한 뒤 확정 |

모델이 확정되지 않은 기구의 치수·토크·구매 가격을 임의로 확정하지 않았습니다.
실제 현관문은 출입·끼임·대피 문제가 있으므로 먼저 탁상 모형으로 검증합니다.

## 3. 배선 및 하드웨어 구성도

- [초보자용 브레드보드 구멍 좌표](docs/dht11_window_touch.md)
- [전체 핀표·전원·구성도·기구 제작](docs/hardware_design.md)
- GPIO27은 창문 모터 IN2입니다. **창문 터치센서는 GPIO24(물리 18번)**입니다.
- 모든 GPIO 신호는 3.3V 기준입니다. 모터·서보는 외부 전원을 사용하고 GND를 공통 연결합니다.
- 창문 터치센서는 전동 창문의 끝점 리밋 스위치 2개를 대체하지 않습니다.

## 4. 라즈베리파이 설정

Windows PC는 코드 편집/모의시험, 실제 센서 코드는 **Raspberry Pi OS**에서 실행합니다.
Python 3.11 이상, 40핀 헤더 기준입니다. Pi 모델/OS에 따라 GPIO·UART 설정은 현물 확인이 필요합니다.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-lgpio i2c-tools
```

전체 센서를 붙일 때만 `sudo raspi-config`에서 I2C를 켜고,
Serial의 로그인 셸은 끄고 시리얼 하드웨어는 켭니다. 변경 후 재부팅하세요.
`i2cdetect -y 1`로 0x44/0x62를 확인하고, PMS의 포트가 `/dev/serial0`인지 확인합니다.
센서 커넥터는 **전원을 끈 상태**에서 연결합니다.

## 5. 설치

```bash
git clone https://github.com/Soongsil-RoomaIT/hardware.git
cd hardware
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -e '.[hardware]'
```

이미 복제한 폴더라면 다시 clone하지 말고 그 안에서 `git pull --ff-only`로 갱신합니다.
실제 Pi용 Adafruit 라이브러리는 `[hardware]` 옵션에 들어 있습니다.

PC 모의시험은 `python -m pip install -e '.[dev]'`만으로 가능합니다.

## 6. 예제 실행

```bash
# 현재 보유 센서. CO2/PM은 null, 창문은 검증 전 unknown
python examples/read_dht11_window_touch.py

# 실제 창문 닫힘/열림과 지속 출력이 일치하는지 검증한 다음에만
python examples/read_dht11_window_touch.py --verified

# 모든 센서가 있을 때. SHT31 대신 DHT11을 유지하려면 아래 옵션
python examples/read_sensors.py --temperature-model DHT11

# 모터/서보를 기구에서 분리한 시험
python examples/test_actuators.py window open --bench-confirmed
python examples/test_actuators.py purifier on --current off --bench-confirmed
python examples/test_actuators.py dehumidifier off --current on --bench-confirmed

# 별도 현관문 모형: 기본 연속 열림 600초, --delay 3은 실험용
python examples/door_auto_close.py --verified

# PC에서 실제 부품 없이 실행
python examples/simulate_hardware.py
python -m pytest -q
```

Ctrl+C로 종료합니다. 프로그램이 강제 종료되거나 Pi가 멈춘 상황까지 소프트웨어만으로
보장할 수는 없습니다. 모터 전원 정지 장치/하드웨어 리밋은 구성도 문서를 따릅니다.

## 7. 코드 구조

| 위치 | 내용 |
|---|---|
| `roomcare_hw/types.py`, `pins.py` | 데이터 계약, 오류, GPIO 배치 |
| `roomcare_hw/sensors/` | DHT, SHT31/SCD41/PMS7003 통합, 터치, 비동기 캐시 |
| `roomcare_hw/actuators/` | 창문 모터, 공기청정기/제습기 버튼, 문 닫기 |
| `roomcare_hw/bundle.py` | 장치 생성·상태 조회·역순 자원 해제 |
| `examples/` | 보유 센서, 전체 센서, 수동 기구 시험, PC 모의시험, Edge 진입점 |
| `tests/` | 실제 하드웨어 없이 오류·시간 초과·동시 명령 검증 |
| `docs/` | 배선, 기구 제작, 요구사항 추적, 인수시험, A 연동 |

## 8. 완료 범위와 남은 실물 작업

- [x] 보유 센서용 실행 코드, 전체 센서 드라이버, 창문·가전·문 드라이버
- [x] 비블로킹 명령, 반복 명령 처리, 시간 초과/모순된 리밋 오류 유지, 종료 처리
- [x] B 하드웨어 구성도·핀표·브레드보드 좌표·기구 제작 순서
- [x] 모의 장치를 이용한 회귀 테스트와 PC 시연
- [ ] 실제 Pi 모델/OS 및 각 부품 모델 확인
- [ ] 실제 배선·신호·온습도/CO₂/PM2.5 교차 확인
- [ ] 창문·가전·현관문 기구 제작과 위치·각도·토크 조정
- [ ] 상태 피드백/끼임 방지/하드웨어 정지 회로 검증
- [ ] A/C/D/E와 MQTT·웹까지 이어지는 5초/10초 요구사항 통합 인수시험

[요구사항 추적표](docs/requirements_traceability.md) · [시험 절차](docs/acceptance.md)
