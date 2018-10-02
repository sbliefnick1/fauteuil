#!/usr/bin/env python

from datetime import datetime, timedelta
import json
import os
from urllib.parse import quote_plus

import pandas as pd
import pendulum
import sqlalchemy as sa

from airflow import DAG
from airflow.operators.mssql_operator import MsSqlOperator
from airflow.operators.sensors import ExternalTaskSensor

from auxiliary.outils import get_secret

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

dag = DAG('etl_master_rework', default_args=default_args, catchup=False, schedule_interval='@daily')

initial_sql = '''
select p.name as proc_name
     , case
          when replace(p.name, '_Logic', '') = o.name
              then ''
          else o.name
      end as dependency_name
     , c.num_dependencies
from sys.procedures p
       left join sys.sql_expression_dependencies d on p.object_id = d.referencing_id
       left join sys.objects o on o.object_id = d.referenced_id
       left join (select p2.object_id as proc_id
                       , count(case when o2.name + '_Logic' <> p2.name then 1 end) as num_dependencies
                  from sys.procedures p2
                         left join sys.sql_expression_dependencies d2 on p2.object_id = d2.referencing_id
                         left join sys.objects o2 on o2.object_id = d2.referenced_id
                  where (p2.name like 'EBI[_]Dim[_]%[_]Logic' or p2.name like 'EBI[_]Fact[_]%[_]Logic' or p2.name like 'EBI[_]Bridge[_]%[_]Logic')
                    and p2.name not like '%[_]dev'
                    and (o2.name like 'ebi[_]dim[_]%' or o2.name like 'ebi[_]fact[_]%' or o2.name like 'ebi[_]bridge[_]%')
                  group by p2.object_id) c on c.proc_id = p.object_id
where (p.name like 'EBI[_]Dim[_]%[_]Logic' or p.name like 'EBI[_]Fact[_]%[_]Logic' or p.name like 'EBI[_]Bridge[_]%[_]Logic')
  and p.name not like '%[_]dev'
  and (o.name like 'ebi[_]dim[_]%' or o.name like 'ebi[_]fact[_]%' or o.name like 'ebi[_]bridge[_]%')
  and exists (select 1 from sys.procedures p3 where p3.name = o.name + '_Logic')
order by p.name, o.name;
'''

if os.sys.platform == 'darwin':
    with open('./secrets/ebi_db_conn.json', 'r') as secret_file:
        ebi = json.load(secret_file)['db_connections']['fi_dm_ebi']
elif os.sys.platform == 'linux':
    ebi = get_secret('ebi_db_conn')['db_connections']['fi_dm_ebi']

conn_id = 'ebi_datamart'
params = quote_plus('DRIVER={}'.format(ebi["driver"]) + ';'
                    'SERVER={}'.format(ebi["server"]) + ';'
                    'DATABASE={}'.format(ebi["db"]) + ';'
                    'UID={}'.format(ebi["user"]) + ';'
                    'PWD={}'.format(ebi["password"]) + ';'
                    'PORT={}'.format(ebi["port"]) + ';'
                    'TDS_Version={}'.format(ebi["tds_version"]) + ';'
                    )

# connect to fi_dm_ebi
engine = sa.create_engine('mssql+pyodbc:///?odbc_connect={}'.format(params))
conn = engine.connect()

# get procedure-view relationship
df = pd.read_sql(initial_sql, conn)
df.proc_name = df.proc_name.str.lower()
df.dependency_name = df.dependency_name.str.lower()
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
            dag=dag
            )
    sql_operators[p] = o

# set procedures downstream from all their dependencies
for p in unique_dep_procs:
    tables = proc_map[p]
    for t in tables:
        sql_operators[t + '_logic'] >> sql_operators[p]

# create sensor to wait for db_access_daemon so we know we can log in to db
access = ExternalTaskSensor(
        external_dag_id='db_access_daemon',
        external_task_id='attempt_to_connect',
        task_id='wait_for_access',
        dag=dag
        )

for p in no_dep_procs.proc_name:
    access >> sql_operators[p]
