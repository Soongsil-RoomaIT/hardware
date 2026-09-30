# DHT11 온습도 센서와 DFR0030 창문 터치 입력 실습

자취방 원격 케어 시스템의 **센서 파트 실습 문서 (역할 B)**.
[hardware 저장소](https://github.com/Soongsil-RoomaIT/hardware)의 README 구성에 맞춰 작성했습니다.
참고한 커밋: `b14742f95f16bf373ef5e073e3953f5891ffb65c`.

| 담당 | 내용 |
|---|---|
| 센서 배선 | DHT11 온습도 모듈과 DFR0030 터치센서를 Raspberry Pi에 연결 |
| 구동 드라이버 | 온습도 측정 및 터치 신호 변화 처리 |
| 문서 | 실제 브레드보드 구멍 좌표와 연결 순서 |

> 현재 보유한 센서 기준의 실습용 확장안입니다. 저장소에는 아직 반영하지 않았습니다.
> DFR0030은 정전식 접촉 감지 센서입니다. 터치 신호와 실제 창문 위치가 일치하는지 확인하기 전에는 창문 상태를 시연용 가정으로만 표시합니다.

## 1. edge_agent 와의 약속 (인터페이스)

기존 `Reading`에는 온도, 습도, CO2, PM2.5가 모두 필요합니다. 현재 부품으로는 온도와 습도만 측정할 수 있으므로 기존 `RoomSensorReader`와 `examples/read_sensors.py`를 그대로 사용하지 않습니다.

- 없는 CO2와 미세먼지 측정값을 0으로 채워 실제 측정처럼 전달하지 않습니다.
- 현재 예제는 센서 단독 확인용이며 MQTT와 자동제어는 포함하지 않습니다.
- 추후 엣지 담당 A와 미지원 값의 표현 및 드라이버 인터페이스를 합의합니다.
- 저장소의 `TouchDoorSensor`는 현관문용입니다. 이번 창문 터치 입력을 현관문 상태로 전달하지 않습니다.
- 창문 터치 신호 하나로 완전 열림 위치까지 알 수 없습니다. 기존 모터용 열림·닫힘 리밋 스위치도 대체하지 않습니다.

## 2. 부품 (현재 보유 기준)

| 용도 | 부품 | 인터페이스 | 비고 |
|---|---|---|---|
| 온습도 | 사진 속 DHT11 형태의 3핀 모듈 | GPIO4 | VCC / DAT / GND 표시 기준으로 연결 |
| 창문 상태 시연 입력 | DFRobot DFR0030 Touch Sensor V2 | GPIO24 | 터치 HIGH를 닫힘으로 가정하는 실습 |
| 연결판 | 사진 속 a~j, 1~30 브레드보드 | 내부 연결 | 오른쪽 + / − 줄은 이번 배선에서 사용하지 않음 |
| 연결선 | 암–수 점퍼선 | 2.54mm 핀 | Pi→보드 4개, DHT11→보드 3개 |
| 터치센서 연결선 | DFR0030 호환 PH2.0-3 케이블 | 3핀 | 브레드보드에 연결할 수 단자 또는 어댑터 필요 |

터치센서의 흰색 커넥터에는 일반 점퍼선을 억지로 끼우지 않습니다. 센서 케이블의 VCC / GND / Signal을 표시로 확인해야 합니다. 사진만으로 커넥터 좌우 핀 순서는 확정할 수 없습니다. 선 색깔만으로 전원 극성을 추정하지 않습니다.

## 3. 배선 (BCM 번호와 브레드보드 구멍 좌표)

### 3.1 브레드보드 방향과 구멍 읽기

사진과 같은 방향으로 놓습니다. a~j가 위에 있고 1번 줄이 위, 30번 줄이 아래입니다. `b10`은 b열의 10번 줄 구멍입니다.

| 구멍 묶음 | 내부 연결 |
|---|---|
| a1, b1, c1, d1, e1 | 같은 1번 줄의 왼쪽 다섯 구멍끼리 연결 |
| a2, b2, c2, d2, e2 | 같은 2번 줄의 왼쪽 다섯 구멍끼리 연결 |
| f1, g1, h1, i1, j1 | 같은 1번 줄의 오른쪽 다섯 구멍끼리 연결 |
| e1과 f1 | 가운데 홈을 사이에 두므로 연결되지 않음 |
| a1과 a2 | 서로 다른 줄이므로 연결되지 않음 |

### 3.2 라즈베리파이에서 브레드보드로 연결

전원을 뽑은 상태에서 연결합니다. 40핀 GPIO가 있는 일반 Raspberry Pi 기준입니다. 물리 핀 위치가 불확실하면 보드 모델과 방향부터 확인합니다.

| 순서 | 선의 한쪽 (Pi 물리 핀) | 반대쪽 구멍 | 역할 |
|---|---|---|---|
| 1 | 물리 1번: 3.3V | a1 | 공통 3.3V 전원 |
| 2 | 물리 6번: GND | a2 | 공통 GND |
| 3 | 물리 7번: GPIO4 | a10 | DHT11 데이터 |
| 4 | 물리 18번: GPIO24 | a15 | 창문 터치 입력 |

**물리 18번은 GPIO24입니다. GPIO18과 혼동하지 않습니다.**
앞선 설명의 GPIO27은 저장소에서 창문 모터 IN2에 할당되어 있으므로 이번 구성에서는 사용하지 않습니다. 저장소의 GPIO23은 현관문 터치 입력으로 유지합니다.

### 3.3 온습도 센서에서 브레드보드로 연결

사진 속 센서 핀은 사진 방향에서 위부터 VCC / DAT / GND입니다. 실제 기판 표시를 우선합니다. 암 단자는 센서 핀에 끼우고 수 단자는 아래 구멍에 꽂습니다.

| 센서 핀 | 브레드보드 구멍 | 연결 결과 |
|---|---|---|
| VCC | b1 | a1을 통해 Pi 3.3V |
| DAT | b10 | a10을 통해 GPIO4 |
| GND | b2 | a2를 통해 Pi GND |

### 3.4 터치센서에서 브레드보드로 연결

센서 본체를 브레드보드에 꽂지 않습니다. 흰색 커넥터에 호환 케이블을 연결한 뒤 케이블 반대쪽을 아래 구멍에 연결합니다.

| 케이블 기능 (표시 확인 필수) | 브레드보드 구멍 | 연결 결과 |
|---|---|---|
| VCC / + | c1 | a1을 통해 Pi 3.3V |
| GND / − | c2 | a2를 통해 Pi GND |
| Signal / D / S | c15 | a15를 통해 GPIO24 |

DFR0030은 3.3~5V 전원을 지원합니다. 이번 연결에서는 3.3V를 사용합니다. 터치 케이블의 핀 기능을 확인하기 전에는 전원을 켜지 않습니다.

### 3.5 완성된 구멍 배치

| 줄 | a열 | b열 | c열 | d·e열 |
|---|---|---|---|---|
| 1 | Pi 3.3V | DHT11 VCC | 터치 VCC | 비움 |
| 2 | Pi GND | DHT11 GND | 터치 GND | 비움 |
| 10 | Pi GPIO4 | DHT11 DAT | 비움 | 비움 |
| 15 | Pi GPIO24 | 비움 | 터치 Signal | 비움 |

f~j 구멍과 오른쪽 전원 줄은 비워둡니다. 센서 핀 3개를 b1·c1·d1처럼 같은 줄에 꽂으면 세 핀이 서로 연결되므로 금지합니다.

### 창문 상태 시연 동작

| 입력 | 화면 표시 | 실제로 확인한 내용 |
|---|---|---|
| 터치 HIGH | 닫힘으로 가정 | 터치가 감지됨 |
| 터치 LOW | 열림으로 가정 | 터치가 감지되지 않음 |

창문이 센서를 누른다는 이유만으로 감지가 보장되지는 않습니다. 닫힌 상태에서 손을 뗀 뒤에도 신호가 유지되는지, 창문을 열면 해제되는지 확인해야 합니다. 상시 감지나 설치 재현성이 확보되지 않으면 실제 개폐 판정에 사용하지 않습니다.

## 4. 라즈베리파이 설정

이번 DHT11과 터치센서는 GPIO를 사용하므로 I2C·UART 활성화는 필요하지 않습니다. Raspberry Pi OS의 터미널에서 실행합니다.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-gpiozero python3-lgpio libgpiod-dev python3-libgpiod
```

라즈베리파이 모델과 OS는 아직 확인되지 않았습니다. 설치 오류나 GPIO 접근 오류가 발생하면 오류 메시지와 모델 정보를 확인한 뒤 조정합니다.

## 5. 설치

이미 저장소를 내려받았다면 해당 `hardware` 폴더로 이동합니다. 처음이라면 다음 순서로 진행합니다.

```bash
git clone https://github.com/Soongsil-RoomaIT/hardware.git
cd hardware
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e .
pip install adafruit-circuitpython-dht
```

현재 저장소 의존성에는 DHT 라이브러리가 없으므로 별도 설치합니다. 정식 반영 시 `pyproject.toml`의 dependencies에 `adafruit-circuitpython-dht`를 추가합니다.

## 6. 예제 실행

다음 파일은 새로 만드는 실습 예제입니다. 현재 원격 저장소에는 없습니다.

```bash
nano examples/read_dht11_window_touch.py
```

아래 코드를 붙여 넣습니다. Ctrl+O, Enter로 저장하고 Ctrl+X로 나옵니다.

```python
"""DHT11(GPIO4) + DFR0030 touch(GPIO24) beginner demonstration.
Touch HIGH is mapped to 'closed' for demonstration only.
A capacitive touch sensor does not independently verify window position.
Use 3.3V power for both modules. Verify connector polarity before wiring.
"""
import time
import board
import adafruit_dht
from gpiozero import DigitalInputDevice


def show_window_demo(touched):
    if touched:
        print('[터치 감지] 시연용 창문 상태: 닫힘으로 가정')
    else:
        print('[터치 없음] 시연용 창문 상태: 열림으로 가정')


def main():
    touch = dht = None
    try:
        touch = DigitalInputDevice(24, pull_up=False, bounce_time=0.1)
        dht = adafruit_dht.DHT11(board.D4, use_pulseio=False)
        time.sleep(2)  # 전원 투입 뒤 안정화
        touch.when_activated = lambda: show_window_demo(True)
        touch.when_deactivated = lambda: show_window_demo(False)
        print('측정 시작. Ctrl+C로 종료합니다.')
        print('주의: 아래 창문 상태는 터치 신호를 이용한 시연용 가정입니다.')
        show_window_demo(touch.is_active)

        while True:
            try:
                temperature = dht.temperature
                humidity = dht.humidity
                if temperature is None or humidity is None:
                    print('온습도 값 없음. 다음에 다시 측정합니다.')
                else:
                    print(f'온도 {temperature:.1f}°C / 습도 {humidity:.1f}%')
                    if temperature >= 28:
                        print('[알림] 실습용 온도 기준 28°C 이상입니다.')
                    if humidity >= 70:
                        print('[알림] 실습용 습도 기준 70% 이상입니다.')
            except RuntimeError as error:
                print(f'온습도 읽기 실패. 다음에 재시도: {error}')
            time.sleep(2)
    except KeyboardInterrupt:
        print('\n측정을 종료합니다.')
    finally:
        if touch is not None:
            touch.close()
        if dht is not None:
            dht.exit()


if __name__ == '__main__':
    main()

```

실행:

```bash
python examples/read_dht11_window_touch.py
```

- 온습도는 약 2초마다 출력됩니다.
- 터치 신호가 바뀌면 창문 상태 시연 메시지가 출력됩니다.
- 온도 28°C, 습도 70%는 실습용 알림 기준입니다.
- 실제 모터·창문·가전은 움직이지 않습니다.
- Ctrl+C로 종료합니다.
- DHT 읽기 실패는 다음 주기에 재시도합니다.

## 7. 코드 구조

현재 저장소 구조를 유지하고 실습 예제를 하나 추가하는 제안입니다.

| 경로 | 처리 |
|---|---|
| `examples/read_dht11_window_touch.py` | 위 코드를 새 파일로 추가 |
| `pyproject.toml` | DHT 라이브러리 의존성 추가 |
| `roomcare_hw/pins.py` | 정식 드라이버 반영 시 아래 상수 추가 |
| `docs/dht11_window_touch.md` | 이 문서를 넣을 수 있는 제안 경로 |
| 기존 `sensors/room.py`, `sensors/door.py` | 현재 실습에서는 그대로 유지 |

`pins.py`에 추가할 상수 제안:

```python
DHT11_DATA = 4       # 물리 7번
WINDOW_TOUCH = 24    # 물리 18번, 창문 상태 시연 입력
```

실습 예제는 독립 실행을 위해 GPIO 번호를 직접 지정합니다. 정식 드라이버로 옮길 때는 `pins.py`의 상수를 사용하도록 바꿉니다.

## 8. 할 일

- [ ] 라즈베리파이 모델과 물리 핀 1번 방향 확인
- [ ] 암–수 점퍼선 및 DFR0030 호환 케이블 확인
- [ ] 터치 케이블 VCC / GND / Signal 확인
- [ ] 전원을 뽑고 위 구멍 좌표대로 배선
- [ ] 온습도 값이 정상적으로 출력되는지 확인
- [ ] 손으로 터치하고 뗄 때 HIGH / LOW가 바뀌는지 확인
- [ ] 실제 창문 설치 후 닫힘 신호의 지속성 확인
- [ ] 반복 개폐와 전원 재투입 후에도 같은 판정이 나오는지 확인
- [ ] 창문 감지와 현관문 감지의 의미를 엣지 담당 A와 구분
- [ ] 미지원 CO2 / PM2.5 처리 규격을 엣지 담당 A와 합의
- [ ] 실제 검증 결과 기록 후 드라이버 통합

검증 현황: 예제 코드의 파이썬 문법 확인 완료. 실제 Raspberry Pi와 센서에서의 실행은 미검증입니다. 배선은 커넥터 핀 기능 확인 후 적용해야 합니다.

참고 자료:
- [DFRobot DFR0030 사양](https://wiki.dfrobot.com/dfr0030/)
- [DFR0030 커넥터 및 터치 HIGH 동작 안내](https://wiki.dfrobot.com.cn/_SKU_DFR0030_%E6%95%B0%E5%AD%97%E8%A7%A6%E6%91%B8%E4%BC%A0%E6%84%9F%E5%99%A8/)
- [Adafruit Raspberry Pi 라이브러리 설치](https://learn.adafruit.com/circuitpython-on-raspberrypi-linux/installing-circuitpython-on-raspberry-pi)
