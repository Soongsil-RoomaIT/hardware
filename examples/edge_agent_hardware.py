"""Optional integration entrypoint, executed after installing sibling edge_agent.

All gas sensors required. Default is sensors only; actuation needs --enable-control.
This uses the public EdgeAgent constructor, without editing the A team's repository.
"""

import argparse
import logging
from pathlib import Path

from roomcare_hw.bundle import HardwareBundle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="edge_agent config TOML path")
    parser.add_argument("--temperature-model", choices=["SHT31", "DHT11", "DHT22"], default="SHT31")
    parser.add_argument(
        "--enable-control", action="store_true", help="검증된 창문 모터와 공기청정기 제어 활성화"
    )
    parser.add_argument("--purifier-current", choices=["on", "off"])
    args = parser.parse_args()
    if not Path(args.config).is_file():
        parser.error("config file does not exist")
    if args.enable_control and args.purifier_current is None:
        parser.error("control requires --purifier-current after checking actual power state")
    from edge_agent.agent import EdgeAgent
    from edge_agent.config import load_config
    from edge_agent.storage import LocalStore

    logging.basicConfig(level=logging.INFO)
    cfg = load_config(args.config)
    with HardwareBundle(
        temperature_model=args.temperature_model,
        window_motor=args.enable_control,
        purifier=args.enable_control,
        purifier_initial=args.purifier_current == "on",
    ) as hw:
        store = LocalStore(cfg.db_path)
        try:
            agent = EdgeAgent(cfg, hw.sensor, hw.actuators, store, door_sensor=hw.door_sensor)
        except BaseException:
            store.close()
            raise
        try:
            agent.run()
        except KeyboardInterrupt:
            agent.stop()


if __name__ == "__main__":
    main()
