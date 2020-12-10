"""

"""
import gc
import json
import math
import os
import sys
from copy import deepcopy

import numpy
import pandas
import tensorflow
from tensorflow.keras import (
    callbacks,
    losses,
    Sequential,
    metrics,
    optimizers,
    )
from tensorflow.python.keras.models import Model

from command_line_tools import (
    command_line_config,
    run_tools,
    )
from dmp.data.pmlb import pmlb_loader
from dmp.data.pmlb.pmlb_loader import load_dataset


def count_trainable_parameters(model: Model) -> int:
    count = 0
    for var in model.trainable_variables:
        print('ctp {}'.format(var.get_shape()))
        acc = 1
        for dim in var.get_shape():
            acc *= int(dim)
        print('ctp acc {}'.format(acc))
        count += acc
    print('ctp total {}'.format(count))
    return count


class NpEncoder(json.JSONEncoder):
    
    def default(self, obj):
        if isinstance(obj, numpy.integer):
            return int(obj)
        elif isinstance(obj, numpy.floating):
            return float(obj)
        elif isinstance(obj, numpy.ndarray):
            return obj.tolist()
        else:
            return super(NpEncoder, self).default(obj)


def test_network(
        config: {},
        dataset,
        inputs: numpy.ndarray,
        outputs: numpy.ndarray,
        prefix,
        width: int,
        depth: int,
        ) -> None:
    config = deepcopy(config)
    name = '{}_{}_{}_b_{}_w_{}_d_{}'.format(
        dataset['Task'],
        dataset['Endpoint'],
        dataset['Dataset'],
        prefix,
        width,
        depth)
    
    config['name'] = name
    config['depth'] = depth
    config['num_hidden'] = max(0, depth - 2)
    config['width'] = width
    
    # pprint(config)
    run_name = run_tools.get_run_name(config)
    config['run_name'] = run_name
    
    num_observations = inputs.shape[0]
    num_inputs = inputs.shape[1]
    num_outputs = outputs.shape[1]
    
    log_data = {'config': config}
    run_config = config['run_config']
    
    run_optimizer = optimizers.Adam(0.001)
    run_metrics = [
        # metrics.CategoricalAccuracy(),
        'accuracy',
        metrics.CosineSimilarity(),
        metrics.Hinge(),
        metrics.KLDivergence(),
        metrics.MeanAbsoluteError(),
        metrics.MeanSquaredError(),
        metrics.MeanSquaredLogarithmicError(),
        metrics.RootMeanSquaredError(),
        metrics.SquaredHinge(),
        ]
    
    print('input shape {} output shape {}'.format(inputs.shape, outputs.shape))
    # print(inputs[0, :])
    # print(outputs[0, :])
    runLoss = losses.mean_squared_error
    outputActivation = tensorflow.nn.relu
    runTask = dataset['Task']
    if runTask == 'regression':
        runLoss = losses.mean_squared_error
        outputActivation = tensorflow.nn.sigmoid
        print('mean_squared_error')
    elif runTask == 'classification':
        outputActivation = tensorflow.nn.softmax
        if num_outputs == 1:
            runLoss = losses.binary_crossentropy
            print('binary_crossentropy')
        else:
            runLoss = losses.categorical_crossentropy
            print('categorical_crossentropy')
    else:
        raise Exception('Unknown task "{}"'.format(runTask))
    
    layers = []
    for d in range(depth):
        
        if d == depth - 1:
            # output layer
            layerWidth = num_outputs
            activation = outputActivation
        else:
            layerWidth = width
            activation = tensorflow.nn.relu
        
        layer = None
        if d == 0:
            # input layer
            layer = tensorflow.keras.layers.Dense(
                layerWidth,
                activation=activation,
                input_shape=(num_inputs,))
        else:
            layer = tensorflow.keras.layers.Dense(
                layerWidth,
                activation=activation,
                )
        print('d {} w {} in {}'.format(d, layerWidth, num_inputs))
        layers.append(layer)
    
    model = Sequential(layers)
    model.compile(
        # loss='binary_crossentropy', # binary classification
        # loss='categorical_crossentropy', # categorical classification (one hot)
        loss=runLoss,  # regression
        optimizer=run_optimizer,
        # optimizer='rmsprop',
        # metrics=['accuracy'],
        metrics=run_metrics,
        )
    
    log_data['num_weights'] = count_trainable_parameters(model)
    log_data['num_inputs'] = num_inputs
    log_data['num_features'] = dataset['n_features']
    log_data['num_classes'] = dataset['n_classes']
    log_data['num_outputs'] = num_outputs
    log_data['num_observations'] = num_observations
    log_data['task'] = dataset['Task']
    log_data['endpoint'] = dataset['Endpoint']
    
    run_callbacks = [
        callbacks.EarlyStopping(**config['early_stopping']),
        ]
    
    gc.collect()
    
    history_callback = model.fit(
        x=inputs,
        y=outputs,
        callbacks=run_callbacks,
        **run_config,
        )
    
    history = history_callback.history
    log_data['history'] = history
    
    validation_losses = numpy.array(history['val_loss'])
    best_index = numpy.argmin(validation_losses)
    
    log_data['iterations'] = best_index + 1
    log_data['val_loss'] = validation_losses[best_index]
    log_data['loss'] = history['loss'][best_index]
    
    log_path = config['log_path']
    run_tools.makedir_if_not_exists(log_path)
    log_file = os.path.join(log_path, '{}.json'.format(run_name))
    print('log file: {}'.format(log_file))
    
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2, sort_keys=True, cls=NpEncoder)


def test_aspect_ratio(config, dataset, inputs, outputs, budget, depths):
    config = deepcopy(config)
    config['dataset'] = dataset['Dataset'],
    config['datasetRow'] = list(dataset),
    
    config = command_line_config.parse_config_from_args(sys.argv[1:], default_config)
    # inputs, outputs = PMLBLoader.loadData(dataset)
    gc.collect()
    
    # for width in range(1, 128):
    #     for depth in range(1, 32):
    for depth in depths:
        i = inputs.shape[1]
        h = (depth - 2)
        o = outputs.shape[1]
        
        a = h
        b = i + h + o + 1
        c = o - budget
        
        raw_width = 1
        if h == 0:
            raw_width = -(o - budget) / (i + o + 1)
        else:
            raw_width = (-b + math.sqrt(b ** 2 - 4 * a * c)) / (2 * a)
        width = round(raw_width)
        print('budget {} depth {}, i {} h {} o {}, a {} b {} c {}, raw_width {}, width {}'.format(budget, depth, i, h, o,
                                                                                                 a, b, c, raw_width,
                                                                                                 width))
        test_network(config, dataset, inputs, outputs, '{}'.format(budget), width, depth)
    
    # pprint(logData)
    print('done.')
    gc.collect()


pandas.set_option("display.max_rows", None, "display.max_columns", None)
datasets = pmlb_loader.load_dataset_index()

# core_config = tensorflow.Conf()
# core_config.gpu_options.allow_growth = True
# session = tensorflow.Session(config=core_config)
# tensorflow.keras.backend.set_session(session)


# for index, dataset in datasets.iterrows():
#     print(index)

default_config = {
    'log_path':       '/home/ctripp/log',
    'early_stopping': {
        'patience':             10,
        'monitor':              'val_loss',
        'min_delta':            0,
        'verbose':              0,
        'mode':                 'min',
        'baseline':             None,
        'restore_best_weights': False,
        },
    'run_config':     {
        'validation_split': .2,
        'shuffle':          True,
        'epochs':           10000,
        'batch_size':       256,
        },
    'activation':    'relu',
    }

config = command_line_config.parse_config_from_args(sys.argv[1:], default_config)

# dataset, inputs, outputs = loadDataset(datasets, 'mnist')
# dataset, inputs, outputs = loadDataset(datasets, '537_houses')
# for i in [.125, .25, .5, 1, 2, 4, 8, 16, 32]:
#     budget = int(round(i * 1000))
#     for _ in range(50):
#         testAspectRatio(config, dataset, inputs, outputs, budget, [i for i in range(2, 20)])
  
dataset, inputs, outputs = load_dataset(datasets, 'mnist')
for _ in range(30):
    # for i in [16, 32, 64, 128, 256]:
    for i in [128, 256, 512, 1024, 2048]:
        budget = int(round(i * 1000))
        test_aspect_ratio(config, dataset, inputs, outputs, budget, [i for i in range(2, 20)])
# testAspectRatio(config, dataset, inputs, outputs, 128, [i for i in range(2, 16)])

# pprint(logData)
print('done.')
gc.collect()
