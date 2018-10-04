#!/usr/bin/env python

from datetime import datetime, timedelta

import pandas as pd
import pendulum

from airflow import DAG
from airflow.operators.mssql_operator import MsSqlOperator
from airflow.operators.sensors import ExternalTaskSensor

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

conn_id = 'ebi_datamart'
pool_id = 'ebi_etl_pool'

df = pd.read_csv('/var/lib/etl_deps/ebi_etl_diagram.csv', na_filter=False)
unique_procs = df.proc_name.unique()

# get tables that have no dependency
no_dep_procs = df[(df.dependency_name == '') & (df.num_dependencies == 0)][['proc_name']]

# get tables that have at least one dependency
dep_procs = df[(df.dependency_name != '') & (df.num_dependencies != 0)][['proc_name', 'dependency_name']]

# create grouping of procs with tables they rely on
proc_map = dep_procs.groupby('proc_name')['dependency_name'].apply(list)

# create series of procs that have dependencies to loop over and set downstream
unique_dep_procs = dep_procs.proc_name.unique()

# create a sqloperator for each procedure
sql_operators = {}
for p in unique_procs:
    o = MsSqlOperator(
            sql='exec {};'.format(p),
            task_id='exec_{}'.format(p),
            mssql_conn_id=conn_id,
            pool=pool_id,
            dag=dag
            )
    sql_operators[p] = o

# set procedures downstream from all their dependencies
for p in unique_dep_procs:
    for t in proc_map[p]:
        sql_operators[t + '_logic'] >> sql_operators[p]
# [sql_operators[t + '_logic'] >> sql_operators[p] for p in unique_dep_procs for t in proc_map[p]]

# create sensor to wait for db_access_daemon so we know we can log in to db
access = ExternalTaskSensor(
        external_dag_id='probe_db_access',
        external_task_id='attempt_to_connect',
        task_id='wait_for_access',
        dag=dag
        )

# create sensor to wait for etl dependencies to be in csv
deps = ExternalTaskSensor(
        external_dag_id='get_etl_deps',
        external_task_id='query_and_save_deps',
        task_id='wait_for_dependencies_file',
        dag=dag
        )

access >> deps

for p in no_dep_procs.proc_name:
    deps >> sql_operators[p]
