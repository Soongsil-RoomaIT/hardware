"""핀 배치 (BCM 번호). 배선을 바꾸면 여기와 README 배선표를 같이 고친다."""

# I2C (SHT31, SCD41) - GPIO2 = SDA, GPIO3 = SCL  (raspi-config 에서 I2C 활성화)
# UART (PMS7003)    - GPIO14 = TX, GPIO15 = RX  -> /dev/serial0
PMS_SERIAL_PORT = "/dev/serial0"

# --- 버튼 서보 구성 (현재 시연 구성) ------------------------------------------
# 서보 하나가 창문/공기청정기/제습기 버튼을 모두 누른다. 누르는 동안 그 기기의 LED 가 켜진다.
# 두 서보는 하드웨어 PWM 채널이 다른 핀(18 = PWM0, 13 = PWM1)에 둔다.
BUTTON_SERVO = 18
LED_WINDOW = 17
LED_DEHUMIDIFIER = 27
LED_PURIFIER = 22

# 문 닫기 서보 (하드웨어 PWM 채널이 있는 GPIO13)
DOOR_SERVO = 13

# 문 열림 감지 터치센서 (DFR0030/TTP223, 출력 HIGH = 터치됨)
DOOR_TOUCH = 23

# 온습도 (DHT11/DHT22)
DHT11_DATA = 4

# --- 모터 창문 구성 (버튼 서보 구성과 같이 쓸 수 없음: GPIO17/27/22 가 LED 와 겹침) ----
# 창문: L298N 모터 드라이버
WINDOW_MOTOR_IN1 = 17  # 정회전 = 열기
WINDOW_MOTOR_IN2 = 27  # 역회전 = 닫기
WINDOW_MOTOR_ENA = 22  # 속도(PWM)

# 창문 리밋 스위치 (GND 와 연결, 내부 풀업 사용)
WINDOW_LIMIT_OPEN = 5
WINDOW_LIMIT_CLOSED = 6

# 가전마다 서보를 따로 둘 때 (버튼 서보 구성에서는 쓰지 않음)
PURIFIER_SERVO = 18
DEHUMIDIFIER_SERVO = 12

# 창문 터치센서 실습 (examples/read_dht11_window_touch.py)
WINDOW_TOUCH = 24
