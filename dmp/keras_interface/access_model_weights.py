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
import re
import numpy

from dmp.layer import *
from dmp.model.keras_layer_info import KerasLayerInfo
from dmp.task.experiment.pruning_experiment.weight_mask import WeightMask
import tensorflow.keras as keras


def get_weights(
    root: Layer,
    layer_to_keras_map: Dict[Layer, KerasLayerInfo],
    use_mask: bool,
) -> Dict[Layer, List[numpy.ndarray]]:
    weight_map: Dict[Layer, List[numpy.ndarray]] = {}

    def visit_variable(layer, keras_layer, i, variable):
        value = variable.numpy()
        if use_mask:
            constraint = get_mask_constraint(keras_layer, variable)
            if constraint is not None:
                value = numpy.where(constraint.mask.numpy(), value, numpy.nan,)
        weight_map.setdefault(layer, []).append(value)

    visit_weights(
        root,
        layer_to_keras_map,
        visit_variable,
    )
    return weight_map

def set_weights(
    root: Layer,
    layer_to_keras_map: Dict[Layer, KerasLayerInfo],
    weight_map: Dict[Layer, List[numpy.ndarray]],
    restore_mask : bool,
) -> None:
    
    def visit_variable(layer, keras_layer, i, variable):
        value_list = weight_map.get(layer, None)
        if value_list is not None:
            value = value_list[i]
            if restore_mask:
                constraint = get_mask_constraint(keras_layer, variable)
                if constraint is not None:
                    mask = numpy.logical_not(numpy.isnan(value))
                    constraint.mask = mask
                    value = numpy.where(mask, value, 0.0)
                    print(f'set mask {variable.name}')
            print(f'assign {variable.name}')
            variable.assign(value)

    visit_weights(
        root,
        layer_to_keras_map,
        visit_variable,
    )

def visit_weights(
    root: Layer,
    layer_to_keras_map: Dict[Layer, KerasLayerInfo],
    visit_variable: Callable,
) -> None:
    for layer in root.layers:
        layer_info = layer_to_keras_map.get(layer, None)
        if layer_info is None:
            continue
        
        keras_layer = layer_info.keras_layer
        if keras_layer is None or not isinstance(keras_layer, keras.layers.Layer):
            continue

        for i, variable in enumerate(keras_layer.variables): # type: ignore
            visit_variable(layer, keras_layer, i, variable)

def get_mask_constraint(
    keras_layer,
    variable,
) -> Optional[Any]:
    match = re.fullmatch('.*/(bias|kernel):\d+', variable.name)
    if match is not None:
        match_str = match.group(1)
        constraint_member_name =  f'{match_str}_constraint'
        if hasattr(keras_layer, constraint_member_name):
            constraint = getattr(keras_layer, constraint_member_name)
            if isinstance(constraint, WeightMask):
                return constraint
    return None

def lin_iterp_weights(
    weights_a: Dict[Layer, List[numpy.ndarray]],
    alpha: float,
    weights_b: Dict[Layer, List[numpy.ndarray]],
) -> Dict[Layer, List[numpy.ndarray]]:
    results = {}
    for layer, weights in weights_a.items():
        results[layer] = [
            weight_a * alpha + weight_b * (1.0 - alpha)
            for weight_a, weight_b in zip(weights, weights_b[layer])
        ]
    return results