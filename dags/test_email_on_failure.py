from datetime import datetime, timedelta

import pendulum

from airflow import DAG
from airflow.operators.python_operator import PythonOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 9, 12, tzinfo=pendulum.timezone('America/Los_Angeles')),
    'email': ['sbliefnick@coh.org'],
    'email_on_failure': True,
    'email_on_retry': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=1)
    }

dag = DAG('test_email_on_failure', default_args=default_args, catchup=False, schedule_interval='@daily')


def throw_error(**context):
    raise ValueError('Intentionally throwing an error to send an email')


t1 = PythonOperator(task_id='first_task',
                    python_callable=throw_error,
                    provide_context=True,
                    email_on_failure=True,
                    email_on_retry=True,
                    email='sbliefnick@coh.org',
                    dag=dag)
