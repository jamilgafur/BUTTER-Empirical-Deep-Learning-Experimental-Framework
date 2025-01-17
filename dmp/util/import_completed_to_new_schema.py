from math import ceil
import ujson
from psycopg import sql
import psycopg.extras as extras
import psycopg
import jobqueue.connect as connect
from pprint import pprint
import sys
from jobqueue.cursor_manager import CursorManager
from dmp.logging.postgres_result_logger import PostgresResultLogger
from dmp.layer.visitor.network_json_deserializer import NetworkJSONDeserializer

from dmp.task.aspect_test.aspect_test_task import AspectTestTask

from dmp.postgres_interface.postgres_attr_map import PostgresAttrMap
from dmp.jobqueue_interface import jobqueue_marshal

sys.path.append("../../")

psycopg.extras.register_uuid()

class SchemaUpdate:

    def __init__(self, credentials, logger, ids) -> None:
        print('init SchemaUpdate')
        with CursorManager(credentials) as cursor:
            self.cursor = cursor
            self.logger = logger
            # self._experiment_table = sql.Identifier("experiment")
            # self._run_table = sql.Identifier("run")
            # self._run_settings_table = sql.Identifier("run_settings")
            # self._run_columns = [
            #     "seed",
            #     "save_every_epochs",
            # ]

            """
            + run results:
                + update experiment parameters if not already updated
                + copy run data and new parameters into a new table 
                    with updated parameters
                or

                + update experiment table parameters
                + create new run_settings entry
                + for new runs:
                    + create run table entry
                        + use dummy data for other columns
                + for old runs:
                    + update run parameters
                
                + update materialized table
                
            """

            cursor.execute(sql.SQL("""
    SELECT
        j.uuid,
        j.config,
        l.doc,
        j.username,
        j.groupname,
        j.host,
        j.status,
        j.worker,
        j.creation_time,
        j.priority,
        j.start_time,
        j.update_time,
        j.end_time,
        j.depth,
        j.wall_time,
        j.retry_count,
        l."timestamp"
    FROM jobqueue j, log l
    WHERE 
        l.job = j.uuid
        AND j.uuid IN %s
;"""), (ids,))
            rows = list(cursor.fetchall())
            values = [self.convert_row(row) for row in rows]
            self.logger.log(values)
            # pprint(values)

    def convert_row(self, row):
        # print(f'{row}')
        # print(ujson.dumps(row[2], sort_keys=True, indent=2))

        job_id = row[0]
        config = row[1]
        doc = row[2]

        task = self.make_task(config)

        result = task.parameters

        config = doc['config']
        environment = doc['environment']

        result['task_version'] = 0
        result['tensorflow_version'] = environment.get('tensorflow_version', None)
        result['python_version'] = environment.get('python_version', None)
        result['platform'] = environment.get('platform', None)
        result['git_hash'] = environment.get('git_hash', None)
        result['hostname'] = environment.get('hostname', None)
        result['slurm_job_id'] = environment.get('SLURM_JOB_ID', None)
        result['widths'] = config.get('widths', None)
        result['num_free_parameters'] = doc.get('num_weights', None)
        
        network_structure = None
        if 'network_structure' in config:
            network_structure = jobqueue_marshal.marshal(
                NetworkJSONDeserializer(config['network_structure'])())
        result['network_structure'] =  network_structure
        # pprint(result)
        result.update(doc['history'])

        # + job_id: UUID,
        # + experiment_parameters: Dict,
        # 1/2 run_parameters: Dict,
        # + run_values: Dict,
        # result: Dict,

        # print(job_id)
        # pprint(experiment_parameters)
        # pprint(run_parameters)
        # pprint(run_values)

        return (job_id,
                job_id,
                result,
                )

    def make_task(self, config):
        kwargs = {
            'seed': config['seed'],
            'dataset': config['dataset'],
            'input_activation': config['activation'],
            'activation': config['activation'],
            'optimizer': config['optimizer'],
            'shape': config['topology'],
            'size': config['budget'],
            'depth': config['depth'],
            'validation_split': config['run_config']['validation_split'],
            'validation_split_method': config['validation_split_method'],
            'run_config': config['run_config'],
            'label_noise': config['label_noise'],
            'early_stopping': config.get('early_stopping', None),
            'save_every_epochs': None,
        }

        kwargs['batch'] = 'fixed_3k_1'

        if not isinstance(kwargs['early_stopping'], dict):
            kwargs['early_stopping'] = None

        if config.get('residual_mode', None) == 'full':
            kwargs['shape'] = kwargs['shape'] + '_' + 'residual'

        if kwargs['label_noise'] == 'none':
            kwargs['label_noise'] = 0.0

        return AspectTestTask(**kwargs)


if __name__ == "__main__":
    credentials = connect.load_credentials('dmp')

    import simplejson
    # extras.register_default_json(loads=ujson.loads, globally=True)
    # extras.register_default_jsonb(loads=ujson.loads, globally=True)
    extras.register_default_json(loads=simplejson.loads, globally=True)
    extras.register_default_jsonb(loads=simplejson.loads, globally=True)
    psycopg.extensions.register_adapter(dict, psycopg.extras.Json)
    
    # pd.io.json._json.loads = lambda s, *a, **kw: simplejson.loads(s)

    # parameter_map = None
    logger = PostgresResultLogger(credentials)
    ids = None
    with CursorManager(credentials) as cursor:
        # parameter_map = PostgresParameterMap(cursor)

        cursor.execute(sql.SQL("""
    SELECT 
        j.uuid
    FROM jobqueue j
    WHERE j.groupname = 'fixed_3k_1'
    AND j.status = 'done'
    AND EXISTS (SELECT job FROM log WHERE log.job = j.uuid)
    AND NOT EXISTS (SELECT job_id from run_ r where r.job_id = j.uuid)
    ORDER BY j.config->'dataset', j.config->'label_noise', j.config->'optimizer'->'config'->'learning_rate', j.config->'topology', j.config->'budget', j.config->'depth', j.uuid
;"""))
        ids = [row[0] for row in cursor.fetchall()]

    print(f'loaded {len(ids)}.')

    num_readers = 64
    chunk_size = 4
    chunks = [
        tuple(ids[c*chunk_size: min(len(ids), (c+1)*chunk_size)])
        for c in range(int(ceil(len(ids)/chunk_size)))]

    from pathos.multiprocessing import Pool

    print(f'created {len(chunks)} chunks')
    # SchemaUpdate(credentials, logger, chunks[0])

    def func(c):
        SchemaUpdate(credentials, logger, c)
        return None

    with Pool(num_readers) as p:
        p.map(func, chunks)
