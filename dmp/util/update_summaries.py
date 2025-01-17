import os

from jobqueue.job import Job
from dmp.postgres_interface.schema.postgres_schema import PostgresSchema
from dmp.postgres_interface.update_experiment_summary import UpdateExperimentSummary
from dmp.postgres_interface.update_experiment_summary_result import UpdateExperimentSummaryResult

from dmp.worker import Worker

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

from jobqueue.connection_manager import ConnectionManager
import argparse
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple
import pandas
import traceback
import json

from pprint import pprint
import uuid
from psycopg import sql

from jobqueue import load_credentials
from jobqueue.cursor_manager import CursorManager
from dmp.dataset.dataset_spec import DatasetSpec
from dmp.dataset.ml_task import MLTask
from dmp.layer.dense import Dense
from dmp.postgres_interface.postgres_compressed_result_logger import PostgresCompressedResultLogger

from dmp.logging.postgres_parameter_map_v1 import PostgresParameterMapV1
from dmp.model.dense_by_size import DenseBySize

from dmp.task.experiment.training_experiment.training_experiment import TrainingExperiment

from dmp.marshaling import marshal

import pathos.multiprocessing as multiprocessing


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('num_workers', type=int)
    # parser.add_argument('block_size', type=int)
    args = parser.parse_args()

    num_workers = args.num_workers
    # block_size = args.block_size

    pool = multiprocessing.ProcessPool(num_workers)
    results = pool.uimap(do_work, ((i, ) for i in range(num_workers)))
    total_updated = sum(results)
    print(f'Done. Summarized {total_updated} experiments.')
    pool.close()
    pool.join()
    print('Complete.')
    do_work((0, 0))


def do_work(args):
    worker_number = args[0]

    credentials = load_credentials('dmp')

    worker = Worker(
        None,
        PostgresSchema(credentials),
        None,
        None,
        {},
    )

    total_updated = 0
    num_tries = 0
    while num_tries < 256:
        job = Job()

        task = UpdateExperimentSummary()

        result: UpdateExperimentSummaryResult = task(worker,
                                                     job)  # type: ignore
        num_updated = result.num_experiments_updated
        total_updated += num_updated
        print(f'Updated {num_updated}.')
        if num_updated == 0:
            num_tries += 1
        else:
            num_tries = 0

    return total_updated


if __name__ == "__main__":
    main()
