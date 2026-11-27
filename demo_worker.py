
import os
from pathlib import Path
from notification_worker import NotificationEngine

HERE = Path(__file__).resolve().parent

class DemoEngine(NotificationEngine):

    def disable_inference(self):
        marker = HERE / "ledger" / "disabled"
        marker.touch(mode=0o600, exist_ok=True)

    def submit(self, assignment, files):
        with self.lock:
            if self.provider.mode != "ollama":
                raise ValueError("Live demonstration mode required")

            marker = self.root / "demo-authorization-consumed"

            try:
                fd = os.open(
                    marker,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600
                )
            except FileExistsError:
                raise ValueError("Demonstration authorization consumed") from None

            with os.fdopen(fd, "w") as stream:
                stream.write("One assignment authorized")
                stream.flush()
                os.fsync(stream.fileno())

            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

            try:
                job = super().submit(assignment, files)
                if self.get(job)["state"] == "FAILED":
                    self.disable_inference()
                return job
            except BaseException:
                self.disable_inference()
                raise

    def run(self, row):
        try:
            super().run(row)
        finally:
            self.disable_inference()

    def cancel(self, job):
        super().cancel(job)
        self.disable_inference()

    def start(self):
        marker = self.root / "demo-authorization-consumed"
        if marker.exists():
            self.disable_inference()
        super().start()
