from typing import Any, Dict, Sequence, Tuple, Callable, TypeVar, List, Union
from dmp.layer.convolutional_layer import ConvolutionalLayer
from dmp.layer.layer import Layer, empty_config, empty_inputs, LayerConfig

class DenseConv(ConvolutionalLayer):

    @staticmethod
    def make(
        filters: int,
        kernel_size: List[int],
        strides: List[int],
        config: LayerConfig = empty_config,
        inputs: List[Layer] = empty_inputs,
    ) -> 'DenseConv':
        return ConvolutionalLayer.make(DenseConv, filters, kernel_size,
                                       strides, config, inputs)

    @staticmethod
    def make_NxN(n: int,
                inputs: List[Layer] = empty_inputs) -> 'DenseConv':
        return DenseConv.make(-1, [n, n], [1, 1], {}, inputs)

def conv_1x1(inputs: List[Layer] = empty_inputs) -> DenseConv:
    return DenseConv.make_NxN(1, inputs)

def conv_3x3(inputs: List[Layer] = empty_inputs) -> DenseConv:
    return DenseConv.make_NxN(3, inputs)

def conv_5x5(inputs: List[Layer] = empty_inputs) -> DenseConv:
    return DenseConv.make_NxN(5, inputs)


