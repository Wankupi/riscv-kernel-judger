from dataclasses import dataclass
from serial import Serial


class USBRelay(Serial):
    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1):
        super().__init__(port, baudrate, timeout=timeout)

    def run_cmd(self, addrs: int | list[int], cmd: int):
        if isinstance(addrs, int):
            addrs = [addrs]
        resp: list[bytes] = []
        for addr in addrs:
            frame = [0xA0, addr & 0xFF, cmd & 0xFF]
            checksum = sum(frame) & 0xFF
            frame.append(checksum)
            self.write(bytes(frame))
            if cmd > 1:  # have response
                resp.append(self.read(4))
        return resp

    def on(self, addrs: int | list[int]):
        self.run_cmd(addrs, 1)

    def off(self, addrs: int | list[int]):
        self.run_cmd(addrs, 0)


@dataclass
class PowerManager:
    dev: USBRelay
    addrs: list[int] | int

    def __enter__(self):
        self.dev.on(self.addrs)

    def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: type | None):
        self.dev.off(self.addrs)
        return False


if __name__ == "__main__":
    import typer

    def main(cmd: int, port: str = "/dev/ttyUSB0", baudrate: int = 9600, timeout: int = 1):
        dev = USBRelay(port, baudrate, timeout=timeout)
        dev.run_cmd([1, 2], cmd)

    typer.run(main)
