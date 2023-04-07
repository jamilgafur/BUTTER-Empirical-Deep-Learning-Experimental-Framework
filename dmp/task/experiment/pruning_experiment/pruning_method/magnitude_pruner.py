from copy import copy
from dataclasses import dataclass
from functools import singledispatchmethod
from math import ceil
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)

import numpy

from dmp import common

from dmp.layer import *
from dmp.model.keras_layer_info import KerasLayerInfo
from dmp.task.experiment.pruning_experiment.pruning_method.pruning_method import (
    PruningMethod,
)
from dmp.task.experiment.pruning_experiment.weight_mask import WeightMask
import dmp.keras_interface.keras_keys as keras_keys


@dataclass
class MagnitudePruner(PruningMethod):
    prune_percent: float

    def prune(
        self,
        root: Layer,
        layer_to_keras_map: Dict[Layer, KerasLayerInfo],
    ) -> int:
        import tensorflow

        def is_prunable(
            layer: Layer,
        ) -> bool:
            keras_layer = layer_to_keras_map[layer].keras_layer
            return hasattr(keras_layer, keras_keys.kernel_constraint) \
                and isinstance(keras_layer.kernel_constraint, WeightMask)

        def get_weights_and_mask(
            layer: Layer,
        ) -> Tuple[numpy.ndarray, tensorflow.Variable]:
            keras_layer = layer_to_keras_map[layer].keras_layer
            return (
                keras_layer.get_weights()[0],  # type: ignore
                keras_layer.kernel_constraint.mask,  # type: ignore
            )

        def get_prunable_weights_from_layer(
            layer: Layer,
        ) -> numpy.ndarray:
            weights, mask = get_weights_and_mask(layer)
            return (weights[mask]).flatten()  # type: ignore

        prunable_layers = [
            layer for layer in root.all_descendants if is_prunable(layer)
        ]

        prunable_weights = numpy.concatenate(
            [
                l
                for l in (
                    get_prunable_weights_from_layer(layer) for layer in prunable_layers
                )
                if l is not None
            ]
        )

        pruning_threshold = numpy.quantile(
            prunable_weights,
            self.prune_percent,
        )
        del prunable_weights

        # prune at selected level
        total_pruned = 0
        for layer in prunable_layers:
            weights, mask = get_weights_and_mask(layer)
            new_mask = numpy.logical_and(
                mask,   # type: ignore
                weights > pruning_threshold,
            )
            total_pruned += new_mask.size - new_mask.sum()
            mask.assign(new_mask)

        return total_pruned
