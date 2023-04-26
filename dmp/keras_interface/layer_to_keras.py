from functools import singledispatchmethod
from pprint import pprint
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
import tensorflow
from tensorflow import keras
from keras import layers
from dmp.keras_interface.convolutional_keras_layer import ConvolutionalKerasLayer
from dmp.layer.batch_normalization import BatchNormalization
from dmp.layer.flatten import Flatten
from dmp.layer.op_layer import OpLayer
from dmp.model.keras_layer_info import KerasLayer, KerasLayerInfo
from dmp.model.model_info import ModelInfo
from dmp.model.network_info import NetworkInfo
from dmp.model.keras_network_info import KerasNetworkInfo
from dmp.keras_interface.keras_utils import make_keras_instance
import dmp.keras_interface.keras_utils as keras_utils
from dmp.layer import *
import dmp.keras_interface.keras_keys as keras_keys


class LayerToKerasVisitor:
    '''
    Constructs a Keras Model corresponding to a given Layer graph.
    '''

    '''
    Classes that are simple one-to-one mappings between Layer types and keras.layer.Layer types
    '''
    _simple_class_mapping = {
        Dense: layers.Dense,
        Flatten: layers.Flatten,
        BatchNormalization: layers.BatchNormalization,
    }

    _simple_multiple_input_class_map = {
        Add: layers.Add,
        Concatenate: layers.Concatenate,
    }

    def __init__(self, target: Layer) -> None:
        '''
        Runs the visitor on the target, generating a keras network corresponding to target.
        '''
        self._layer_number: int = 0
        self._info: KerasNetworkInfo = KerasNetworkInfo({}, [], [])
        self._info.outputs.append(self._make_keras_network(target).output_tensor)

    def __call__(self) -> KerasNetworkInfo:
        '''
        Retrieves the KerasNetworkInfo generated by the visitor.
        '''
        return self._info

    def _make_keras_network(self, target: Layer) -> KerasLayerInfo:
        '''
        Recursively traverses the layer graph building the keras network.
        '''

        keras_map = self._info.layer_to_keras_map
        if target in keras_map:
            return keras_map[target]

        self._setup_layer_name(target)
        result = self._make_keras_layer_from_layer(
            target,
            target.config.copy(),
            [self._make_keras_network(i).output_tensor for i in target.inputs],
        )

        keras_map[target] = result
        return result

    @singledispatchmethod
    def _make_keras_layer_from_layer(
        self,
        target: Layer,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        keras_class = self._simple_class_mapping.get(type(target), None)  # type: ignore
        if keras_class is not None:
            return self._make_standard_keras_layer(target, keras_class, config, inputs)

        keras_class = self._simple_multiple_input_class_map.get(type(target), None)  # type: ignore
        if keras_class is not None:
            return self._make_multiple_input_keras_layer(
                target, keras_class, config, inputs
            )

        raise NotImplementedError(f'Unknown Layer of type {type(target)}.')

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: Input,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        result = layers.Input(**config)
        self._info.inputs.append(result)  # type: ignore
        return KerasLayerInfo(target, result, result)  # type: ignore

    @_make_keras_layer_from_layer.register
    def visit_DenseConvolutionalLayer(
        self,
        target: DenseConv,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._make_convolutional_layer(
            target,
            config,
            inputs,
            {
                1: layers.Conv1D,
                2: layers.Conv2D,
                3: layers.Conv3D,
            },
        )

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: SeparableConv,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._make_convolutional_layer(
            target,
            config,
            inputs,
            {
                1: layers.SeparableConv1D,
                2: layers.SeparableConv2D,
            },
        )

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: MaxPool,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._make_by_dimension(
            target,
            config,
            inputs,
            {
                1: layers.MaxPool1D,
                2: layers.MaxPool2D,
                3: layers.MaxPool3D,
            },
        )

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: AvgPool,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._make_by_dimension(
            target,
            config,
            inputs,
            {
                1: layers.AvgPool1D,
                2: layers.AvgPool2D,
                3: layers.AvgPool3D,
            },
        )

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: GlobalAveragePooling,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._make_by_dimension(
            target,
            config,
            inputs,
            {
                1: layers.GlobalAveragePooling1D,
                2: layers.GlobalAveragePooling2D,
                3: layers.GlobalAveragePooling3D,
            },
        )

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: GlobalMaxPooling,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._make_by_dimension(
            target,
            config,
            inputs,
            {
                1: layers.GlobalMaxPool1D,
                2: layers.GlobalMaxPool2D,
                3: layers.GlobalMaxPool3D,
            },
        )

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: Identity,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        return self._info.layer_to_keras_map[target.input]

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: Zeroize,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        keras_layer = tensorflow.zeros_like(target.computed_shape)
        return KerasLayerInfo(target, keras_layer, keras_layer)

    @_make_keras_layer_from_layer.register
    def _(
        self,
        target: OpLayer,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        config.pop('name')
        keras_layer = make_keras_instance(config)(*inputs)
        return KerasLayerInfo(target, keras_layer, keras_layer)

    def _setup_layer_name(
        self,
        target: Layer,
    ) -> None:
        '''
        Sets a standardized name for this layer, unless one is already defined.
        Layer names take the form "dmp_layer_{layer_number}" where {layer_number}
        is the in-order traversal index of this layer.
        '''
        if keras_keys.name in target:
            pass  # don't change the name if it's already configured
        layer_number = self._layer_number
        target[keras_keys.name] = f'{keras_keys.dmp_layer_prefix}{layer_number}'
        self._layer_number = layer_number + 1

    def _make_by_dimension(
        self,
        target: Layer,
        config: LayerConfig,
        inputs: List[KerasLayer],
        dimension_to_factory_map: Dict[int, Callable],
    ) -> KerasLayerInfo:
        keras_class = dimension_to_factory_map[target.input.dimension]
        return self._make_standard_keras_layer(target, keras_class, config, inputs)

    def _make_convolutional_layer(
        self,
        target: ConvolutionalLayer,
        config: LayerConfig,
        inputs: List[KerasLayer],
        dimension_to_factory_map: Dict[int, Callable],
    ) -> KerasLayerInfo:
        config[keras_keys.conv_layer_factory] = dimension_to_factory_map[
            target.dimension
        ]
        return self._make_standard_keras_layer(
            target, ConvolutionalKerasLayer, config, inputs
        )

    def _make_standard_keras_layer(
        self,
        layer: Layer,
        target: Callable,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        '''
        Makes a keras layer using the normal configuration parameters (if defined) to
        construct regularizers, constraints, activation functions, batch notrmalizer, initializer, etc.
        '''
        print(f'_make_standard_keras_layer {layer} {inputs}')
        self._setup_standard_layer(config)
        keras_layer = target(**config)
        keras_output = keras_layer(*inputs)
        return KerasLayerInfo(layer, keras_layer, keras_output)  # type: ignore

    def _make_multiple_input_keras_layer(
        self,
        layer: Layer,
        target: Callable,
        config: LayerConfig,
        inputs: List[KerasLayer],
    ) -> KerasLayerInfo:
        print(f'_make_multiple_input_keras_layer {layer} {inputs}')
        self._setup_standard_layer(config)
        keras_layer = target(**config)
        keras_output = keras_layer(inputs)
        return KerasLayerInfo(layer, keras_layer, keras_output)  # type: ignore

    def _setup_standard_layer(
        self,
        config: LayerConfig,
    ) -> None:
        self._setup_regularizers(config)
        self._setup_constraints(config)
        self._setup_activation(config)
        self._make_keras_batch_normalization(config)
        self._setup_initializers(config)

    def _setup_regularizers(self, config: LayerConfig) -> None:
        self.replace_config_key_with_keras_instance(
            config,
            (
                keras_keys.kernel_regularizer,
                keras_keys.bias_regularizer,
                keras_keys.activity_regularizer,
            ),
        )

    def _setup_constraints(self, config: LayerConfig) -> None:
        self.replace_config_key_with_keras_instance(
            config,
            (
                keras_keys.kernel_constraint,
                keras_keys.bias_constraint,
            ),
        )

    def _setup_initializers(self, config: LayerConfig) -> None:
        self.replace_config_key_with_keras_instance(
            config,
            (
                keras_keys.kernel_initializer,
                keras_keys.bias_initializer,
            ),
        )

    def _setup_activation(self, config: LayerConfig) -> None:
        self.replace_config_key_with_keras_instance(config, keras_keys.activation)

    def _make_keras_batch_normalization(self, config: LayerConfig) -> None:
        key = keras_keys.batch_normalization
        if key in config:
            batch_normalization = config[key]
            if batch_normalization is None:
                config[key] = tensorflow.identity
            else:
                batch_normalization_config = batch_normalization.config.copy()
                self._setup_standard_layer(batch_normalization_config)
                keras_layer = layers.BatchNormalization(**batch_normalization_config)
                config[key] = keras_layer

    def replace_config_key_with_keras_instance(
        self,
        config: LayerConfig,
        key: Union[Iterable[str], str],
    ) -> None:
        if isinstance(key, str):
            key_config = config.get(key, None)
            if key_config is not None:
                config[key] = make_keras_instance(key_config)
        else:
            for k in key:
                self.replace_config_key_with_keras_instance(config, k)


def make_keras_network_from_layer(target: Layer) -> KerasNetworkInfo:
    return LayerToKerasVisitor(target)()


def make_keras_model_from_network(network: NetworkInfo) -> ModelInfo:
    keras_network = make_keras_network_from_layer(network.structure)
    keras_model = tensorflow.keras.Model(
        inputs=keras_network.inputs,
        outputs=keras_network.outputs,
    )
    if len(keras_model.inputs) != 1:  # type: ignore
        raise ValueError('Wrong number of keras inputs generated.')

    keras_num_trainable = sum(
        (
            keras_layer_info.keras_layer.count_params()
            for layer, keras_layer_info in keras_network.layer_to_keras_map.items()
            if hasattr(keras_layer_info.keras_layer, 'count_params')
        )
    )

    if keras_num_trainable != network.num_free_parameters:
        raise RuntimeError(
            f'Wrong number of trainable parameters: {keras_num_trainable} vs planned {network.num_free_parameters}'
        )

    return ModelInfo(network, keras_network, keras_model)
