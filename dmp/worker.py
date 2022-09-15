from typing import Dict, List, Optional
import uuid
from jobqueue.job import Job
from jobqueue.job_queue import JobQueue
from dmp.logging.result_logger import ResultLogger
from dmp.task.task import Task

from dmp.jobqueue_interface.common import jobqueue_marshal
from lmarshal.src.marshal import Marshal


class Worker:
    _job_queue: JobQueue
    _result_logger: ResultLogger
    _worker_info : Dict

    def __init__(self,
                 job_queue: JobQueue,
                 result_logger: ResultLogger,
                 worker_info: Dict,
                 ) -> None:
        self._job_queue = job_queue
        self._result_logger = result_logger
        self._worker_info = worker_info

    @property
    def worker_info(self) -> Dict:
        return self._worker_info

    def __call__(self):
        self._job_queue.work_loop(
            lambda worker_id, job: self._handler(worker_id, job))

    def _handler(self, worker_id: uuid.UUID, job: Job):

        # demarshal task from job.command
        task: Task = jobqueue_marshal.demarshal(job.command)

        # run task
        result = task(self)

        # log task run

        self._result_logger.log(
            [
                (
                    job.id,
                    job.id,
                    result
                )
            ]
        )
