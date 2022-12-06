import copy
import math
from typing import Any, Dict, Optional

import numpy

import dmp.task.growth_experiment.growth_experiment_utils as growth_experiment_utils
from dmp.task.growth_experiment.growth_experiment import GrowthExperiment
from dmp.task.growth_experiment.growth_methods.overlay_growth_method import OverlayGrowthMethod
from dmp.task.task_util import remap_key_prefixes
from dmp.task.training_experiment.training_experiment_utils import *
from dmp.task.training_experiment.training_experiment_executor import TrainingExperimentExecutor
from dmp.task.network import Network


class GrowthExperimentExecutor(TrainingExperimentExecutor):
    '''
    '''

    def __init__(self, task: GrowthExperiment, worker):
        if task.growth_scale <= 1:
            raise RuntimeError(f'Growth scale {task.growth_scale} <= 1.')
        self.task: GrowthExperiment = task
        self.worker = worker

    def __call__(self) -> Dict[str, Any]:
        task = self.task
        self.set_random_seeds()
        dataset = self.load_and_prepare_dataset()


        # get initial_size
        target_final_network = self.make_network(dataset, task.network)
        target_final_network.si


        history: dict = {}
        growth_step: int = 0
        epoch_parameters: int = 0
        epochs: int = 0
        previous_network: Optional[Network] = None
        on_final_iteration: bool = False
        while not on_final_iteration:

            target_size: int = int(
                math.floor(task.initial_size *
                           math.pow(task.growth_scale, growth_step)))

            # if we 'skipped' over a growth step, handle it
            if previous_network is not None and \
                target_size <= previous_network.num_free_parameters:
                growth_step += 1
                continue

            # if we topped out at the maximum size, this is the last iteration
            if target_size >= task.size:
                on_final_iteration = True
                target_size = task.size

            network = self.make_network(dataset, self.task.size)

            max_epochs_at_this_iteration = min(
                epochs - task.max_total_epochs,
                math.floor((task.max_equivalent_epoch_budget * task.size) /
                           network.num_free_parameters))
            if max_epochs_at_this_iteration <= 0:
                break
            fit_config = deepcopy(self.task.run_config)
            fit_config['epochs'] = max_epochs_at_this_iteration

            if previous_network is not None:
                self.grow_network(task, previous_network, network)

            network.compile_model(task.optimizer)
            callbacks = self.make_callbacks(on_final_iteration)
            model_history = self.fit_model(fit_config, dataset, network, callbacks)

            num_epochs = len(model_history['loss'])
            model_history['parameter_count'] = \
                [network.num_free_parameters] * num_epochs
            model_history['growth_points'] = [0] * num_epochs

            # If the growth trigger is EarlyStopping and the
            # 'restore_best_weights' flag is set, indicate growth point at epoch
            # that achieves lowest val_loss else growth occured at final epoch
            if task.growth_trigger.get('restore_best_weights', False):
                model_history['growth_points'][numpy.argmin(
                    model_history['val_loss'])] = 1
            else:
                model_history['growth_points'][-1] = 1

            # Extend histories dictionary
            if len(history.keys()) == 0:
                history = copy.deepcopy(model_history)
            else:
                for k, v in history.items():
                    if type(v) is list:
                        v.extend(model_history[k])

            previous_network = network
            growth_step += 1
            epochs += num_epochs
            epoch_parameters += num_epochs * network.num_free_parameters
            continue  # just put this here for better readability

        if previous_network is None:
            raise RuntimeError(f'No result record generated for task {task}.')

        return self.make_result_record(previous_network, history)

    def grow_network(
        self,
        task: GrowthExperiment,
        source: Network,
        dest: Network,
    ) -> None:
        make_from_typed_config(
            task.growth_method,
            {
                'NetworkOverlayer': OverlayGrowthMethod,
            },
            'growth_method',
            source.network_structure,
            source.layer_to_keras_map,
            dest.network_structure,
            dest.layer_to_keras_map,
        )

    def make_callbacks(self, on_final_iteration:bool) -> List[keras.callbacks.Callback]:
        if on_final_iteration:
            return super().make_callbacks()
        return [make_from_typed_config(
            self.task.growth_trigger, {
                'EarlyStopping': keras.callbacks.EarlyStopping,
            }, 'growth_trigger')]
