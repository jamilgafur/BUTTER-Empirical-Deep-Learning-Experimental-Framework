from typing import Callable, Dict, Optional, Tuple, Any, List, Sequence, TypeVar, Union
from dmp.layer.pooling_layer import APoolingLayer
from dmp.layer.layer import register_layer_type

class MaxPool(APoolingLayer):

    @staticmethod
    def make(
        pool_size: Sequence[int],
        strides: Sequence[int],
        *args,
        **kwargs,
    ) -> 'MaxPool':
        return APoolingLayer.make(
            MaxPool,
            pool_size,
            strides,
            *args,
            **kwargs,
        )


register_layer_type(MaxPool)