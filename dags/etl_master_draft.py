#!/usr/bin/env python

from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import sqlalchemy as sa

from airflow import DAG
from airflow.operators.sensors import SqlSensor
from airflow.operators.mssql_operator import MsSqlOperator
from airflow.operators.sensors import ExternalTaskSensor

from auxiliary.outils import get_secret

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 7, 11),
    'email': ['sbliefnick@coh.org'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)
    }

dag = DAG('etl_master_draft', default_args=default_args, schedule_interval='@daily')

initial_sql = '''
select distinct p.name as proc_name
  ,             t.name as table_name
from sys.procedures p
  left join sys.sql_dependencies d on p.object_id = d.object_id
  left join sys.tables t on t.object_id = d.referenced_major_id
  right join edw_clarity_load_audit a on a.tablename = t.name
where p.name like '%_clarity_%'
      and p.name not like '%_dev'
      and t.name like 'clarity_%'
      and t.name not like '%_zc_%'

union

select distinct p.name as proc_name
  ,             t.name as table_name
from sys.procedures p
  left join sys.sql_dependencies d on p.object_id = d.object_id
  left join sys.tables t on t.object_id = d.referenced_major_id
where p.name like '%_clarity_%'
      and p.name not like '%_dev'
      and (t.name like 'ebi_dim_%' or t.name like 'ebi_fact_%')
      and replace(p.name, '_Logic', '') <> t.name;
'''
poke_sql = '''
select case
       when LoadType = 'Daily'
            and cast(LastUpdateDatm as date) = 
                cast(getdate() as date)
         then 1
       when LoadType = 'Weekly'
            and cast(LastUpdateDatm as date) = 
                cast(dateadd(day, -1 * ((datepart(weekday, getdate()) % 7) - 1), getdate()) as date) -- sunday
         then 1
       else 0
       end
from EDW_CLARITY_LOAD_AUDIT
where TableName = '{0}';
'''

ebi = get_secret('ebi_db_conn')['db_connections']['fi_dm_ebi']

conn_id = 'ebi_datamart'
params = quote_plus(f'DRIVER={ebi["driver"]};'
                    f'SERVER={ebi["server"]};'
                    f'DATABASE={ebi["db"]};'
                    f'UID={ebi["user"]};'
                    f'PWD={ebi["password"]};'
                    f'PORT={ebi["port"]};'
                    f'TDS_Version={ebi["tds_version"]};'
                    )

# connect to fi_dm_ebi
engine = sa.create_engine(f'mssql+pyodbc:///?odbc_connect={params}')
conn = engine.connect()

# get procedure-table relation and unique dfs thereof
df = pd.read_sql(initial_sql, conn)
df.table_name = df.table_name.str.lower()
df.proc_name = df.proc_name.str.lower()
unique_tables = df.table_name.unique()
unique_procs = df.proc_name.unique()

# remove rows from df where there is no corresponding procedure for an ebi table, e.g., ebi_dim_date
non_proc_tables = []
for t in unique_tables:
    if t.startswith('ebi_') and t + '_logic' not in unique_procs:
        non_proc_tables.append(t)

for t in non_proc_tables:
    df = df[df.table_name != t]

# create grouping of procedures with the tables they rely on
proc_map = df.groupby('proc_name')['table_name'].apply(list)

# create sensors for each of the base tables that starts with 'clarity_'
sensors = {}
for t in unique_tables:
    if t.startswith('ebi_'):
        continue
    s = SqlSensor(
            task_id=f'{t}_sensor',
            conn_id=conn_id,
            poke_interval=300,
            sql=poke_sql.format(t),
            dag=dag
            )
    sensors[t] = s

# create a sqloperator for each procedure
sql_operators = {}
for p in unique_procs:
    tables = proc_map[p]
    o = MsSqlOperator(
            sql=f'exec {p};',
            task_id=f'load_{p}',
            mssql_conn_id=conn_id,
            dag=dag
            )
    sql_operators[p] = o

# set procedure downstream from table sensor if table begins with clarity_,
# and downstream from procedure sqloperator if table begins with ebi_
for p in unique_procs:
    tables = proc_map[p]
    for t in tables:
        if t.startswith('clarity_'):
            sensors[t] >> sql_operators[p]
        elif t.startswith('ebi_'):
            sql_operators[t + '_logic'] >> sql_operators[p]

# create sensor to wait for db_access_daemon to signal that we can log in to database today
access = ExternalTaskSensor(
        external_dag_id='db_access_daemon',
        external_task_id='attempt_to_connect',
        task_id='wait_for_access',
        dag=dag
        )

for t in unique_tables:
    if t.startswith('ebi_'):
        continue
    access >> sensors[t]
