from datetime import datetime, timedelta

import pendulum

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.email_operator import EmailOperator

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

dag = DAG('test_email_operator', default_args=default_args, catchup=False, schedule_interval='@daily')


def do_something(**context):
    print("This is the first task :)")


t1 = PythonOperator(task_id='do_something',
                    python_callable=do_something,
                    provide_context=True,
                    dag=dag)

t2 = EmailOperator(task_id='email_something',
                   to='sbliefnick@coh.org',
                   subject='{{ task_instance_key_str }} information',
                   html_content="""
DAG {{ dag }} has some information for you.<br>

task: {{ task }}<br>

task_instance: {{ task_instance }}<br>

ds: {{ ds }}<br>

some html:<br>

<table style="width:50%">
  <tr>
    <th>Firstname</th>
    <th>Lastname</th> 
    <th>Age</th>
  </tr>
  <tr>
    <td>Jill</td>
    <td>Smith</td> 
    <td>50</td>
  </tr>
  <tr>
    <td>Eve</td>
    <td>Jackson</td> 
    <td>94</td>
  </tr>
</table>

""",
                   provide_context=True,
                   dag=dag)

t1 >> t2
