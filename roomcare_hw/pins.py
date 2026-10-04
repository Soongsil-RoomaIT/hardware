"""핀 배치 (BCM 번호). 배선을 바꾸면 여기와 README 배선표를 같이 고친다."""

# I2C (SHT31, SCD41) - GPIO2 = SDA, GPIO3 = SCL  (raspi-config 에서 I2C 활성화)
# UART (PMS7003)    - GPIO14 = TX, GPIO15 = RX  -> /dev/serial0
PMS_SERIAL_PORT = "/dev/serial0"

# 창문: L298N 모터 드라이버
WINDOW_MOTOR_IN1 = 17  # 정회전 = 열기
WINDOW_MOTOR_IN2 = 27  # 역회전 = 닫기
WINDOW_MOTOR_ENA = 22  # 속도(PWM)

# 창문 리밋 스위치 (GND 와 연결, 내부 풀업 사용)
WINDOW_LIMIT_OPEN = 5
WINDOW_LIMIT_CLOSED = 6

# 공기청정기 전원 버튼 누르는 서보
PURIFIER_SERVO = 18

# 문 열림 감지 터치센서 (TTP223, 출력 HIGH = 터치됨)
DOOR_TOUCH = 23

# 문 닫기 서보 (하드웨어 PWM 채널이 있는 GPIO13)
DOOR_SERVO = 13

# 보유 센서로 시작하는 실습 (창문 모터 IN2=27과 충돌하지 않음)
DHT11_DATA = 4
WINDOW_TOUCH = 24
DEHUMIDIFIER_SERVO = 12
