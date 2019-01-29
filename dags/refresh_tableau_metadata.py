from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import requests
import tableauserverclient as TSC
import sqlalchemy as sa
import pendulum

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.sensors import ExternalTaskSensor

from auxiliary.outils import get_json_secret

ebi = get_json_secret('ebi_db_conn')['db_connections']['fi_dm_ebi']
tabuser = get_json_secret('ebi_db_conn')['db_connections']['fi_dm_ebi']['user']
tabpass = get_json_secret('ebi_db_conn')['db_connections']['fi_dm_ebi']['password']

params = quote_plus('DRIVER={driver};'
                    'SERVER={server};'
                    'DATABASE={database};'
                    'UID={user};'
                    'PWD={password};'
                    'PORT={port};'
                    'TDS_Version={tds_version};'
                    .format(**ebi))

engine = sa.create_engine('mssql+pyodbc:///?odbc_connect={}'.format(params))

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 1, 25, tzinfo=pendulum.timezone('America/Los_Angeles')),
    'email': ['sbliefnick@coh.org', 'jharris@coh.org'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=2)
    }

dag = DAG('Refresh_Tableau_Metadata', default_args=default_args, catchup=False, schedule_interval='@daily')


def refreshDSFileds():
    server_url = 'http://COH06550.coh.org'
    tableau_auth = TSC.TableauAuth(tabuser, tabpass)
    server = TSC.Server(server_url, use_server_version=True)
    url = server_url + "/relationship-service-war/graphql"

    jquery = """{
      databases(filter: {name: "FI_DM_EBI"}) {
        tables {
          id
          name
          columns {
            name
            referencedByFields {
              name
              description
              dataCategory
              folderName
              role
              dataType
              defaultFormat
              aggregation
              datasource {
                id
                name
              }
            }
          }
        }
      }
    }
    """

    query = url + '?query=' + jquery

    server.auth.sign_in(tableau_auth)
    auth = server.auth_token
    header = {'X-Tableau-Auth': auth}
    req = requests.get(query, headers=header)
    server.auth.sign_out()

    def getTables():
        data = req.json()
        data = data["data"]["databases"][0]["tables"]
        df = pd.DataFrame()

        for tab in data:
            for col in tab["columns"]:
                field = col["referencedByFields"][0]
                ls = [[tab["id"], tab["name"], col["name"], field["name"], field["datasource"]["id"], field["role"],
                       field["dataType"]]]
                df = df.append(pd.DataFrame(ls, columns=['table_graphql_id', 'table_name', 'column_name', 'field_name',
                                                         'datasource_graphql_id', 'field_role',
                                                         'field_data_type']), ignore_index=True)
                df = df.drop_duplicates()
        return df

    df = getTables()
    engine.execution_options(autocommit=True).execute("TRUNCATE TABLE EBI_TableauServer_Datasource_Fields_New;")
    df.to_sql('EBI_TableauServer_Datasource_Fields_New', engine, index=False, if_exists='append')


load = PythonOperator(
        task_id='Refresh_Tableau_Datasource_Fields',
        python_callable=refreshDSFileds,
        dag=dag
        )

deps = ExternalTaskSensor(
        external_dag_id='get_etl_deps',
        external_task_id='query_and_save_deps',
        task_id='wait_for_dependencies_file',
        dag=dag
        )

deps >> load
