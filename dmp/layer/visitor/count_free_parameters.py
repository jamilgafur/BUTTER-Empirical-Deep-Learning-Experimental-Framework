from functools import singledispatchmethod
import math
from typing import Any, Callable, Dict, Generic, Iterable, Iterator, List, Optional, Set, Sequence, Tuple, TypeVar, Union
from dmp.layer import *


class CountFreeParametersVisitor:

    def __init__(self, target: Layer) -> None:

        num_free_parameters = 0
        for layer in target.all_descendants:
            num_in_layer = self._visit(layer)
            num_free_parameters += num_in_layer
            layer.free_parameters += num_in_layer
        self._num_free_parameters: int = num_free_parameters

    def __call__(self) -> int:
        return self._num_free_parameters

    def _get_size(self, target: Layer) -> int:
        return sum(target.shape)

    @singledispatchmethod
    def _visit(self, target: Layer, config: Dict[str, Any]) -> int:
        return 0

    @_visit.register
    def _(self, target: Dense, config: Dict[str, Any]) -> int:
        return config['units'] * \
            (sum((self._get_size(i) for i in target.inputs)) +\
                 (1 if target.use_bias else 0))

    @_visit.register
    def _(self, target: AConvolutionalLayer, config: Dict[str, Any]) -> int:
        return self._get_count_for_conv_layer(
            target,
            config,
            math.prod(config['kernel_size']),
        )

    @_visit.register
    def _(self, target: SeparableConv, config: Dict[str, Any]) -> int:
        return self._get_count_for_conv_layer(
            target,
            config,
            sum(config['kernel_size']),
        )

    def _get_count_for_conv_layer(
        self,
        target: ASpatitialLayer,
        config: Dict[str, Any],
        num_nodes_per_filter: int,
    ) -> int:
        num_nodes = num_nodes_per_filter * config['filters']

        input_conv_shape, input_channels = \
            target.to_conv_shape_and_channels(target.input.shape)

        params_per_node = input_channels + (1 if target.use_bias else 0)
        return num_nodes * params_per_node


def count_free_parameters(target: Layer) -> int:
    return CountFreeParametersVisitor(target)()