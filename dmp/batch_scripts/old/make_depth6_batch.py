"""
Enqueues jobs from stdin into the JobQueue
"""

import argparse
import time

import jobqueue.connect as connect
from jobqueue.job import Job
from jobqueue.job_queue import JobQueue
import numpy

from command_line_tools import command_line_config
from dmp.jobqueue_interface import jobqueue_marshal

import sys

from dmp.task.aspect_test.aspect_test_task import AspectTestTask


def do_parameter_sweep(sweep_config, task_handler):

    repetitions = sweep_config['repetitions']
    sweep_values = sweep_config['sweep_values']

    keys = list(sweep_values.keys())
    task_config = {}
    seed = int(time.time())

    def do_sweep(key_index):
        nonlocal task_config, keys, seed
        if key_index < 0:
            for rep in range(repetitions):
                task_config['seed'] = seed
                task = AspectTestTask(**task_config)
                task_handler(task)
                seed += 1
        else:
            key = keys[key_index]
            for v in sweep_values[key]:
                task_config[key] = v
                do_sweep(key_index-1)

    do_sweep(len(keys)-1)


def main():
    default_config = {
        'repetitions': 30,
        'base_priority': 2000000000,
        'queue': 1,
        'sweep_values': {
            'batch': ['fixed_3k_1'],
            'dataset': ['201_pol', '529_pollen', '537_houses', 'adult', 'connect_4', 'mnist', 'nursery', 'sleep', 'wine_quality_white',],
            'input_activation': ['relu'],
            'activation': ['relu'],
            'optimizer': [{'class_name': 'adam', 'config': {'learning_rate': 0.0001}}],
            'shape': ['rectangle', 'trapezoid', 'exponential', 'wide_first_2x', 'wide_first_4x', 'wide_first_16x', 'rectangle_residual'],
            'size': [32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384,
                     32768, 65536, 131072, 262144, 524288, 1048576, 2097152, 4194304,
                     8388608, 16777216, 33554432],
            'depth': [6],
            'test_split': [.2],
            'test_split_method': ['shuffled_train_test_split'],
            'run_config': [{
                'shuffle': True,
                'epochs': 3000,
                'batch_size': 256,
                'verbose': 0,
            }],
            'label_noise': [0.0],
            'kernel_regularizer': [None],
            'bias_regularizer': [None],
            'activity_regularizer': [None],
            'early_stopping': [None],
            'save_every_epochs': [None],
        },
    }

    sweep_config = command_line_config.parse_config_from_args(
        sys.argv[1:], default_config)

    tasks = []

    def handler(task):
        nonlocal tasks
        tasks.append(task)

    do_parameter_sweep(sweep_config, handler)

    tasks = sorted(tasks, key=lambda t: (
        t.depth, t.dataset, numpy.random.randint(10000), t.seed))

    base_priority = sweep_config['base_priority']
    jobs = [Job(
        priority=base_priority+i,
        command=jobqueue_marshal.marshal(t),
    ) for i, t in enumerate(tasks)]

    print(f'Generated {len(jobs)} jobs.')
    credentials = connect.load_credentials('dmp')
    queue_id = int(sweep_config['queue'])
    job_queue = JobQueue(credentials, queue_id, check_table=False)
    job_queue.push(jobs)
    print(f'Enqueued {len(jobs)} jobs.')
    # task = jobqueue_marshal.demarshal(jobs[0].command)
    # print(task)
    # task()
    # job_queue = JobQueue(credentials, queue_id, check_table=False)
    

    # marshaled_task = jobqueue_marshal.marshal(task)
    # print(marshaled_task)


if __name__ == "__main__":
    main()
