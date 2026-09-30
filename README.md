# hardware

자취방 원격 케어 시스템의 **센서·액추에이터** 파트 (역할 BC).

| 담당 | 내용 |
|---|---|
| 센서 배선 | 온습도, CO2, 미세먼지 센서를 Raspberry Pi 에 연결 |
| 액추에이터 제작 | 창문 개폐, 공기청정기 On/Off, 문 자동 닫기 (Retrofit: 기존 창문·가전·문에 부착) |
| 구동 드라이버 | 센서/액추에이터를 Python 으로 제어하는 코드 (이 레포) |
| 문서 | 하드웨어 구성도 (배선도, 전원 구성, 부품 목록) |

> 아래 부품 모델과 핀 배치는 **예시**입니다. 실제로 쓰는 부품에 맞게 바꾸고 이 문서도 같이 갱신하세요.

---

## 1. edge_agent 와의 약속 (인터페이스)

[`edge_agent`](https://github.com/Soongsil-RoomaIT/edge_agent) 가 이 레포의 드라이버를 불러서 씁니다.
아래 형태만 지키면 엣지 쪽은 Mock 을 실제 드라이버로 바꿔 끼우기만 하면 됩니다.
정의: [`roomcare_hw/types.py`](roomcare_hw/types.py)

```python
@dataclass(frozen=True)
class Reading:
    measured_at: float   # unix time
    temperature: float   # C
    humidity: float      # %RH
    co2: float           # ppm
    pm25: float          # ug/m3

class SensorReader:
    def read(self) -> Reading: ...          # 실패 시 IOError

class DoorSensor:
    is_open: bool                           # 문 열림 여부

class Actuator:
    name: str                               # "window" | "air_purifier" | "door"
    is_on: bool                             # 실제 상태 (창문: on = 완전히 열림, 문: on = 열림)
    def set(self, on: bool) -> None: ...    # 동작을 시작하고 바로 반환 (블로킹 금지)
```

- `door` 는 서보가 **닫기만** 할 수 있습니다. `set(False)` = 닫기, `set(True)` 는 무시됩니다.

- **`set()` 은 오래 걸리면 안 됩니다.** 엣지 에이전트는 0.5초마다 통신 상태를 확인해서 10초 안에 오프라인 모드로 전환해야 하므로, 모터가 다 돌 때까지 기다리면 안 됩니다. 동작은 백그라운드에서 끝냅니다.
- `set()` 은 같은 값으로 여러 번 불려도 안전해야 합니다. 자동제어가 측정할 때마다 목표 상태를 다시 보냅니다.
- 필드 이름·단위·액추에이터 이름을 바꿀 때는 **엣지 담당과 같이** 바꿉니다.

---

## 2. 부품 (예시)

| 용도 | 부품 | 인터페이스 | 비고 |
|---|---|---|---|
| 온습도 | SHT31 | I2C (0x44) | DHT22 도 가능하지만 정확도/안정성은 SHT31 이 좋음 |
| CO2 | SCD41 | I2C (0x62) | NDIR 방식. 전원 인가 후 값이 안정되기까지 수 분 |
| 미세먼지 | PMS7003 | UART 9600bps | 5V 전원, 신호는 3.3V |
| 창문 | DC 기어모터 or 리니어 액추에이터 + L298N | GPIO | 리밋 스위치 2개 (열림/닫힘) 필수 |
| 공기청정기 | SG90 / MG90S 서보 | GPIO (PWM) | 전원 버튼을 물리적으로 누름 |
| 문 열림 감지 | TTP223 터치센서 | GPIO (디지털) | 문이 닫히면 문짝(금속 테이프)이 패드에 닿도록 설치 |
| 문 닫기 | MG996R 등 고토크 서보 | GPIO (PWM) | 문을 밀어야 하므로 SG90 은 힘이 부족. 문 무게에 맞게 선정 |
| 전원 | 12V 어댑터 (모터용) + Pi 전용 5V | | **모터 전원을 Pi 5V 핀에서 끌어오지 말 것** |

공기청정기 대안: 스마트 플러그(전원 차단 방식, 기기가 전원 복귀 시 자동 켜짐일 때만), IR 송신기(리모컨 지원 기기).

---

## 3. 배선 (BCM 번호, [`roomcare_hw/pins.py`](roomcare_hw/pins.py))

| 장치 | 장치 핀 | Pi 핀 |
|---|---|---|
| SHT31, SCD41 | SDA / SCL | GPIO2 (핀 3) / GPIO3 (핀 5) — 같은 I2C 버스 공유 |
| SHT31, SCD41 | VCC / GND | 3.3V (핀 1) / GND |
| PMS7003 | TX → | GPIO15 RXD (핀 10) |
| PMS7003 | RX ← | GPIO14 TXD (핀 8) |
| PMS7003 | VCC / GND | 5V (핀 2) / GND |
| L298N | IN1 / IN2 / ENA | GPIO17 / GPIO27 / GPIO22 |
| L298N | 12V / GND | 모터용 어댑터 (+), **GND 는 Pi GND 와 공통** |
| 리밋 스위치 (열림) | 한쪽 → GPIO5, 다른 쪽 → GND | 내부 풀업 사용 |
| 리밋 스위치 (닫힘) | 한쪽 → GPIO6, 다른 쪽 → GND | 내부 풀업 사용 |
| 서보 (공기청정기) | 신호 / VCC / GND | GPIO18 / 외부 5V / GND (공통) |
| TTP223 (문) | OUT / VCC / GND | GPIO23 / 3.3V / GND |
| 서보 (문 닫기) | 신호 / VCC / GND | GPIO13 / 외부 5~6V / GND (공통) |

주의
- Pi GPIO 는 **3.3V** 입니다. 5V 신호를 GPIO 에 직접 넣지 마세요.
- 모터/서보 전원과 Pi 전원은 분리하고 **GND 만 공통**으로 묶습니다.
- 창문은 닫힐 때 손이 끼일 수 있으니, 처음에는 모터를 창문에서 떼고 방향·리밋 스위치부터 확인하세요.
- 고토크 서보(MG996R)는 순간 전류가 1A 이상이라 **반드시 외부 전원**을 씁니다.

### 문 자동 닫기 동작

```
터치센서 떨어짐(문 열림) ─ close_delay(기본 10초) 대기 ─┬─ 그 사이 닫힘 → 취소
                                                      └─ 여전히 열림 → 서보 스윙(밀기 → 복귀)
                                                            └─ 3초 뒤에도 열림 → 재시도 (최대 3회)
```

- 사람이 드나드는 동안 바로 닫지 않도록 지연을 둡니다.
- 스윙 후 서보 신호를 끊어서(detach), 사람이 문을 열 때 서보가 버티지 않습니다.
- 3회 실패하면 포기하고 에러 로그를 남깁니다 (문이 걸렸거나 서보 힘 부족).

구성도(배선도 이미지, 전원 구성도, 부품 목록/가격)는 `docs/` 에 추가합니다.

---

## 4. 라즈베리파이 설정

```bash
sudo raspi-config
#  Interface Options -> I2C -> Enable
#  Interface Options -> Serial Port -> 로그인 셸: No, 시리얼 하드웨어: Yes
sudo reboot

sudo apt install -y i2c-tools python3-lgpio python3-venv
i2cdetect -y 1          # 0x44 (SHT31), 0x62 (SCD41) 가 보이면 배선 OK
```

## 5. 설치

```bash
git clone https://github.com/Soongsil-RoomaIT/hardware.git
cd hardware
python3 -m venv --system-site-packages .venv   # apt 로 설치한 lgpio 를 쓰기 위해
. .venv/bin/activate
pip install -e .
```

## 6. 예제 실행

```bash
python examples/read_sensors.py            # 2초마다 센서값 출력
python examples/test_actuators.py window open
python examples/test_actuators.py window close
python examples/test_actuators.py purifier on
python examples/door_auto_close.py --push        # 서보 한 번 스윙 (각도 조정용)
python examples/door_auto_close.py --delay 3     # 문 열고 3초 뒤 자동 닫기
```

---

## 7. 코드 구조

```
roomcare_hw/
├── types.py              # edge_agent 와 약속한 인터페이스
├── pins.py               # 핀 배치
├── sensors/
│   ├── pms7003.py        # 미세먼지 (UART 프레임 파싱)
│   ├── room.py           # SHT31 + SCD41 + PMS7003 -> RoomSensorReader
│   └── door.py           # TTP223 터치센서 문 열림 감지
└── actuators/
    ├── window.py         # 모터 + 리밋 스위치 (비블로킹, 타임아웃 정지)
    ├── air_purifier.py   # 서보로 전원 버튼 누르기
    └── door_closer.py    # 서보로 문 닫기 + 자동 닫기(지연, 재시도)
examples/
├── read_sensors.py
├── test_actuators.py
└── door_auto_close.py
```

## 8. 할 일

- [ ] 부품 확정 및 구매 (이 문서 부품표 갱신)
- [ ] 센서 하나씩 연결해서 `read_sensors.py` 로 값 확인
- [ ] 창문 개폐 기구 제작 + 리밋 스위치 위치 조정
- [ ] 공기청정기 버튼 누르는 서보 고정 + 각도(`press_angle`) 조정
- [ ] 공기청정기 실제 상태 감지 방법 검토 (지금은 소프트웨어가 기억한 상태만 사용)
- [ ] 터치센서 설치 위치 확정, `touched_means_closed` 방향 확인
- [ ] 문 닫기 서보 고정 + 각도(`rest_angle`, `push_angle`) 조정, 서보 토크가 충분한지 확인
- [ ] edge_agent 와 통합 테스트 (엣지 담당과 같이)
- [ ] 하드웨어 구성도 작성 (`docs/`)
