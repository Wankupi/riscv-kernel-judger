import time
import logging
from serial import Serial
from common.config import config
from common.redis import RedisTaskQueue
from common.task import Task
from .power import PowerManager, USBRelay

logger: logging.Logger = logging.getLogger(__name__)


class KernelJudgerRunner:
    def __init__(self) -> None:
        self.queue_client: RedisTaskQueue = RedisTaskQueue()
        self.relay: USBRelay = USBRelay(config.runner.tty_power)
        assert self.relay.is_open, f"cannot open relay device: {config.runner.tty_power}"
        self.relay.off(config.runner.power_addrs)

    def run_forever(self) -> None:
        logger.info("runner started")
        while True:
            task: Task | None = self.queue_client.dequeue()
            if task is None:
                continue
            logger.info("enter run_task taskid=%s", task.id)
            try:
                self.run_task(task)
            except Exception:
                logger.exception("task failed taskid=%s", task.id)
            finally:
                logger.info("leave run_task taskid=%s", task.id)

    def run_task(self, task: Task) -> None:
        # 1) boot preparation: copy student kernel into TFTP directory
        self.prepare(task)
        # 2) power on -> wait -> power off
        timeout: int = task.time_limit or config.runner.default_time_limit
        config.runner.result_dir.mkdir(parents=True, exist_ok=True)
        result_path = config.runner.result_dir / f"{task.id}.txt"
        # make sure power is off before starting
        self.relay.off(config.runner.power_addrs)
        with (
            Serial(config.runner.tty_board, baudrate=115200) as tty_board,
            open(result_path, "wb") as result,
            PowerManager(self.relay, config.runner.power_addrs),
        ):
            deadline: float = time.monotonic() + float(timeout)
            while True:
                left_time: float = deadline - time.monotonic()
                if left_time <= 0:
                    break
                tty_board.timeout = left_time
                size: int = tty_board.in_waiting or 4096
                data = tty_board.read(size)
                result.write(data)
                result.flush()

    def prepare(self, task: Task) -> None:
        dst_path = config.runner.tftp_kernel_path
        dst_path.unlink(missing_ok=True)
        dst_path.symlink_to(task.file_path.absolute())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    runner = KernelJudgerRunner()
    try:
        runner.run_forever()
    except KeyboardInterrupt:
        logger.info("runner stopped by user")
