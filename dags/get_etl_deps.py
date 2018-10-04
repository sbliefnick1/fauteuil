#!/usr/bin/env python

from datetime import datetime, timedelta
import json
import os
from urllib.parse import quote_plus

import pandas as pd
import pendulum
import sqlalchemy as sa

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.sensors import ExternalTaskSensor

from auxiliary.outils import get_secret


def query_and_save(db_engine, sql):
    # connect to fi_dm_ebi
    conn = db_engine.connect()

    # get procedure-view relationship
    df = pd.read_sql(sql, conn)
    df.proc_name = df.proc_name.str.lower()
    df.dependency_name = df.dependency_name.str.lower()

    df.to_csv('/var/lib/etl_deps/ebi_etl_diagram.csv', index=False)


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
        ebi = json.load(secret_file)['db_connections']['qa_db']
elif os.sys.platform == 'linux':
    ebi = get_secret('ebi_db_conn')['db_connections']['qa_db']

params = quote_plus('DRIVER={}'.format(ebi["driver"]) + ';'
                    'SERVER={}'.format(ebi["server"]) + ';'
                    'DATABASE={}'.format(ebi["database"]) + ';'
                    'UID={}'.format(ebi["user"]) + ';'
                    'PWD={}'.format(ebi["password"]) + ';'
                    'PORT={}'.format(ebi["port"]) + ';'
                    'TDS_Version={}'.format(ebi["tds_version"]) + ';'
                    )

engine = sa.create_engine('mssql+pyodbc:///?odbc_connect={}'.format(params))

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 10, 2, tzinfo=pendulum.timezone('America/Los_Angeles')),
    'email': ['sbliefnick@coh.org'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)
    }

dag = DAG('qa_get_etl_deps', default_args=default_args, catchup=False, schedule_interval='@daily')

t1 = ExternalTaskSensor(
        external_dag_id='qa_db_access_daemon',
        external_task_id='attempt_to_connect',
        task_id='wait_for_access',
        dag=dag
        )

t2 = PythonOperator(task_id='query_and_save_deps',
                    python_callable=query_and_save,
                    op_kwargs={'db_engine': engine,
                               'sql': initial_sql},
                    dag=dag)

t1 >> t2
