import shutil
import time
from common.config import config
from common.redis import RedisTaskQueue
from common.task import Task
from .power import PowerManager, USBRelay


class KernelJudgerRunner:
    def __init__(self) -> None:
        self.queue_client: RedisTaskQueue = RedisTaskQueue()
        self.relay: USBRelay = USBRelay(config.runner.tty_power)
        assert self.relay.is_open, f"cannot open relay device: {config.runner.tty_power}"
        self.relay.off(config.runner.relay_addrs)

    def run_forever(self) -> None:
        print("runner started")
        while True:
            task: Task | None = self.queue_client.dequeue()
            if task is None:
                continue
            try:
                self.run_once(task)
            except Exception as exc:
                print(f"task failed task_id={task.id}: {exc}")

    def run_once(self, task: Task) -> None:
        # 1) boot preparation: copy student kernel into TFTP directory
        shutil.move(task.file_path, config.runner.tftp_kernel_path)
        print(f"kernel deployed task_id={task.id} -> {config.runner.tftp_kernel_path}")

        # 2) power on -> wait -> power off
        timeout: int = task.time_limit or config.runner.default_timeout
        with PowerManager(self.relay, config.runner.relay_addrs):
            time.sleep(timeout)
        print(f"power off task_id={task.id}")


if __name__ == "__main__":
    runner = KernelJudgerRunner()
    try:
        runner.run_forever()
    except KeyboardInterrupt:
        print("runner stopped by user")
