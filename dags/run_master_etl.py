#!/usr/bin/env python

from datetime import datetime, timedelta
import logging
import re

import pandas as pd
import pendulum

from airflow import DAG
from airflow.operators.mssql_operator import MsSqlOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.sensors import ExternalTaskSensor

from auxiliary.outils import refresh_tableau_extract

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 9, 12, tzinfo=pendulum.timezone('America/Los_Angeles')),
    'email': ['sbliefnick@coh.org'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)
    }

dag = DAG('run_master_etl', default_args=default_args, catchup=False, schedule_interval='@daily')


def read_json_files(names):
    return [pd.read_json('/var/nfsshare/etl_deps/dev_{}.json'.format(name)) for name in names]


conn_id = 'ebi_datamart'
pool_id = 'ebi_etl_pool'

to_read = ['unique_procs', 'no_dep_procs', 'proc_map', 'unique_dep_procs', 'unique_ds', 'ds_map', 'unique_ds_procs']
unique_procs, no_dep_procs, proc_map, unique_dep_procs, unique_ds, ds_map, unique_ds_procs = read_json_files(to_read)

# create a sql operator for each procedure
sql_ops = {}
for p in unique_procs.procs:
    o = MsSqlOperator(
            sql='exec {};'.format(p),
            task_id='exec_{}'.format(p),
            mssql_conn_id=conn_id,
            pool=pool_id,
            dag=dag
            )
    sql_ops[p] = o

# create a python operator for each tableau datasource
python_ops = {}
for ds in unique_ds.ds_name:
    # TODO account for inappropriately named datasources in get_etl_deps
    if not re.match(r'^[A-Za-z0-9_\-.]+$', ds):
        logging.warning('The key ({}) has to be made of alphanumeric characters, dashes, dots, and underscores '
                        'exclusively'.format(ds))
        continue
    ds_id = unique_ds.loc[unique_ds.ds_name == ds, 'id'].values[0]
    o = PythonOperator(
            task_id='refresh_{}'.format(ds),
            python_callable=refresh_tableau_extract,
            op_kwargs={'datasource_id': ds_id},
            dag=dag
            )
    python_ops[ds] = o

# set procedures downstream from all their dependencies
for p in unique_dep_procs.procs:
    for t in proc_map.loc[proc_map.proc_name == p].dependency_name.values[0]:
        sql_ops[t + '_logic'] >> sql_ops[p]
# [sql_ops[t + '_logic'] >> sql_ops[p] for p in unique_dep_procs.procs for t in proc_map.loc[proc_map.proc_name ==
# p].dependency_name.values[0]]

# set ds refreshes downstream from all their procedure dependencies
for ds in unique_ds.ds_name:
    if not re.match(r'^[A-Za-z0-9_\-.]+$', ds):
        continue
    for p in ds_map.loc[ds_map.ds_name == ds].proc_name.values[0]:
        sql_ops[p] >> python_ops[ds]
# [sql_ops[p] >> python_ops[ds] for ds in unique_ds.ds_name for p in ds_map.loc[ds_map.ds_name == ds].proc_name.values[0]]

# create sensor to wait for etl dependencies to be in json
deps = ExternalTaskSensor(
        external_dag_id='get_etl_deps',
        external_task_id='query_and_save_deps',
        task_id='wait_for_dependencies_file',
        dag=dag
        )

for p in no_dep_procs.proc_name:
    deps >> sql_ops[p]
