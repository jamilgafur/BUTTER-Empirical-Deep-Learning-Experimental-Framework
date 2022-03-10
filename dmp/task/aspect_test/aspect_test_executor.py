from dataclasses import dataclass
import os

from dmp.data.pmlb import pmlb_loader


from .aspect_test_task import AspectTestTask
import tensorflow.keras.metrics as metrics
import tensorflow.keras.callbacks as callbacks
from .aspect_test_utils import *
from dmp.task.task import Parameter

import pandas
import numpy

# from keras_buoy.models import ResumableModel

_datasets = pmlb_loader.load_dataset_index()


@dataclass
class AspectTestExecutor(AspectTestTask):
    '''
    '''

    output_activation: Optional[str] = None
    tensorflow_strategy: Optional[tensorflow.distribute.Strategy] = None
    keras_model: Optional[tensorflow.keras.Model] = None
    run_loss: Optional[tensorflow.keras.losses] = None
    network_module: Optional[NetworkModule] = None
    dataset: Optional[pandas.Series] = None
    inputs: Optional[numpy.ndarray] = None
    outputs: Optional[numpy.ndarray] = None

    def __call__(self) -> Tuple[Dict[str, Parameter], Dict[str, any]]:
        # Configure hardware
        if self.tensorflow_strategy is None:
            self.tensorflow_strategy = tensorflow.distribute.get_strategy()

        # Set random seeds
        self.seed = set_random_seeds(self.seed)

        # Load dataset
        self.dataset, self.inputs, self.outputs =  \
            pmlb_loader.load_dataset(_datasets, self.dataset)

        # prepare dataset shuffle, split, and label noise:
        prepared_config = prepare_dataset(
            self.validation_split_method,
            self.label_noise,
            self.run_config,
            self.dataset['Task'],
            self.inputs,
            self.outputs,
        )

        # Generate neural network architecture
        num_outputs = self.outputs.shape[1]
        self.output_activation, self.run_loss = \
            compute_network_configuration(num_outputs, self.dataset)

        # TODO: make it so we don't need this hack
        shape = self.shape
        residual_mode = None
        residual_suffix = '_residual'
        if shape.endswith(residual_suffix):
            residual_mode = 'full'
            shape = shape[0:-len(residual_suffix)]

        # Build NetworkModule network
        delta, widths, self.network_module = find_best_layout_for_budget_and_depth(
            self.inputs,
            residual_mode,
            self.input_activation,
            self.activation,
            self.output_activation,
            self.size,
            widths_factory(shape)(num_outputs, self.depth),
            self.depth,
            shape
        )

        print('begin reps: size: {}, depth: {}, widths: {}, rep: {}'.format(self.size, self.depth, self.widths,
                                                                            self.rep))

        # Create and execute network using Keras
        with self.tensorflow_strategy.scope():
            # Build Keras model
            self.keras_model = make_keras_network_from_network_module(
                self.network_module)
            assert len(
                self.keras_model.inputs) == 1, 'Wrong number of keras inputs generated'

            # Compile Keras Model
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

            run_optimizer = tensorflow.keras.optimizers.get(self.optimizer)

            self.keras_model.compile(
                # loss='binary_crossentropy', # binary classification
                # loss='categorical_crossentropy', # categorical classification (one hot)
                loss=self.run_loss,  # regression
                optimizer=run_optimizer,
                # optimizer='rmsprop',
                # metrics=['accuracy'],
                metrics=run_metrics,
            )

            assert count_num_free_parameters(self.network_module) == count_trainable_parameters_in_keras_model(self.keras_model), \
                'Wrong number of trainable parameters'

            # Configure Keras Callbacks
            run_callbacks = []
            if self.early_stopping is not None:
                run_callbacks.append(
                    callbacks.EarlyStopping(**self.early_stopping))

            # # optionally enable checkpoints
            # if self.save_every_epochs is not None and self.save_every_epochs > 0:
            #     DMP_CHECKPOINT_DIR = os.getenv(
            #         'DMP_CHECKPOINT_DIR', default='checkpoints')
            #     if not os.path.exists(DMP_CHECKPOINT_DIR):
            #         os.makedirs(DMP_CHECKPOINT_DIR)

            #     save_path = os.path.join(
            #         DMP_CHECKPOINT_DIR, self.job_id + '.h5')

            #     self.keras_model = ResumableModel(
            #         self.keras_model,
            #         save_every_epochs=self.save_every_epochs,
            #         to_path=save_path)

            # fit / train model
            history = self.keras_model.fit(
                callbacks=run_callbacks,
                **prepared_config,
            )

            # Tensorflow models return a History object from their fit function,
            # but ResumableModel objects returns History.history. This smooths
            # out that incompatibility.
            if self.save_every_epochs is None or self.save_every_epochs == 0:
                history = history.history

            # Direct method of saving the model (or just weights). This is automatically done by the ResumableModel interface if you enable checkpointing.
            # Using the older H5 format because it's one single file instead of multiple files, and this should be easier on Lustre.
            # model.save_weights(f'./log/weights/{run_name}.h5', save_format='h5')
            # model.save(f'./log/models/{run_name}.h5', save_format='h5')

            run_parameters = {
                'tensorflow_version': tensorflow.__version__,
            }

            # return the result record
            return run_parameters, history