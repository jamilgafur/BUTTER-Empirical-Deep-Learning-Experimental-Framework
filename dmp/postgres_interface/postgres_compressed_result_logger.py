from itertools import chain
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple, List, Union
import io
from numpy import place
from psycopg.sql import SQL, Composed, Identifier
from psycopg.types.json import Jsonb
from jobqueue.connection_manager import ConnectionManager
from dmp.logging.experiment_result_logger import ExperimentResultLogger
from dmp.postgres_interface.element.column_group import ColumnGroup
from dmp.postgres_interface.schema.postgres_schema import PostgresSchema
from dmp.task.experiment.experiment_result_record import ExperimentResultRecord

from dmp.postgres_interface.postgres_interface_common import sql_comma, sql_placeholder


class PostgresCompressedResultLogger(ExperimentResultLogger):
    _schema: PostgresSchema
    _log_result_record_query: Composed

    def __init__(
        self,
        schema: PostgresSchema,
    ) -> None:
        super().__init__()
        self._schema = schema

        experiment = self._schema.experiment
        run = self._schema.run
        experiment = experiment.all
        run = run.insertion_columns
        self._values_columns = experiment + run
        input_table = Identifier('_input')

        self._log_multiple_query_prefix = SQL("""
WITH {input_table} as (
    SELECT
        {casting_clause}
    FROM
        ( VALUES """).format(
            input_table=input_table,
            casting_clause=self._values_columns.casting_sql,
        )

        self._log_multiple_query_suffix = SQL("""
) AS t (
            {experiment_columns},
            {run_value_columns}
            )
),
{inserted_experiment_table} as (
    INSERT INTO {experiment} AS e (
        {experiment_columns}
    )
    SELECT
        {experiment_columns}
    FROM {input_table}
    ON CONFLICT DO NOTHING
)
INSERT INTO {run} (
    {run_experiment_id},
    {run_value_columns}
    )
SELECT 
    {experiment_id} AS {run_experiment_id},
    {run_value_columns}
FROM {input_table}
ON CONFLICT DO NOTHING
;""").format(
            experiment_columns=experiment.columns_sql,
            run_value_columns=run.columns_sql,
            inserted_experiment_table=Identifier('_inserted'),
            experiment=experiment.identifier,
            run=run.identifier,
            experiment_id=experiment.experiment_id.identifier,
            run_experiment_id=run.experiment_id.identifier,
        )

    def log(self,
            records: Union[Sequence[ExperimentResultRecord],
                           ExperimentResultRecord],
            connection=None) -> None:
        if connection is None:
            with ConnectionManager(self._schema.credentials) as connection:
                return self.log(records, connection)

        if isinstance(records, ExperimentResultRecord):
            return self.log((records, ), connection)

        if not isinstance(records, Sequence):
            raise ValueError(f'Invalid record type {type(records)}.')

        if len(records) <= 0:
            return

        schema = self._schema
        attribute_map = schema.attribute_map
        value_columns = schema.experiment.values
        run_value_columns = schema.run.values
        run_values = []
        for record in records:

            experiment_column_values = value_columns.extract_column_values(
                record.experiment_attrs,
                record.experiment_properties,
            )

            experiment_attrs = attribute_map.to_sorted_attr_ids(
                record.experiment_attrs)

            run_values.append((
                schema.make_experiment_id(experiment_attrs),
                experiment_attrs,
                attribute_map.to_sorted_attr_ids(record.experiment_properties),
                *experiment_column_values,
                *run_value_columns.extract_column_values(record.run_data),
                Jsonb(record.run_data),
                schema.convert_dataframe_to_bytes(record.run_history),
                schema.convert_dataframe_to_bytes(record.run_extended_history),
            ))

        placeholders = sql_comma.join(
            [SQL('({})').format(self._values_columns.placeholders)] *
            len(run_values))

        query = SQL("""{}{}{}""").format(
            self._log_multiple_query_prefix,
            placeholders,
            self._log_multiple_query_suffix,
        )

        connection.execute(
            query,
            list(chain(*run_values)),
            binary=True,
        )