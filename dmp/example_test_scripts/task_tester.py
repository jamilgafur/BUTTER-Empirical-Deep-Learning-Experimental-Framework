from dmp.task.experiment.growth_experiment.growth_experiment import GrowthExperiment
from dmp.worker import Worker
import pandas as pd
import tensorflow as tf
import pickle

def main():
    task = GrowthExperiment(seed=0,batch='growth_experiment_1',
                          dataset='201_pol',
                          input_activation='relu',
                          activation='relu',
                          optimizer={'class_name': 'adam', 'config': {'learning_rate': 0.01}},
                          shape='rectangle',
                          size=128,
                          depth=3,
                          test_split=0.3,
                          test_split_method='shuffled_train_val_test_split',
                          fit= {'shuffle': True,'epochs': None,'batch_size': 256,'verbose': 0,},
                          label_noise=0.0,
                          kernel_regularizer=None,
                          bias_regularizer=None,
                          activity_regularizer=None,
                          early_stopping=None,
                          save_every_epochs=None,
                          growth_trigger='EarlyStopping',
                          growth_trigger_params={'patience':2},
                          transfer_method='grow_network',
                          growth_method_params=None,
                          growth_scale=2.0,
                          max_size=2**15,
                          val_split=0.1,
                          max_total_epochs=None,
                          max_equivalent_epoch_budget=100)
    
    # print(task.max_size,task.asdf,task.val_split)
    worker = Worker(None,None,tf.distribute.get_strategy(),{})
    
    result = task(worker)
    # print(result)
    # pd.DataFrame(result).to_csv('growth_experiment_dataframe.csv')
    with open('growth_experiment_results.pkl','wb') as f:
        pickle.dump(result,f)

if __name__ == '__main__':
    main() 
