#!/usr/bin/env python 

from airflow import DAG
from airflow.operators.python_operator import BranchPythonOperator
from airflow.operators.bash_operator import BashOperator
from airflow.operators.dummy_operator import DummyOperator

from datetime import datetime, timedelta
import random

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2018, 7, 1),
    'email': ['sbliefnick@coh.org'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)}

dag = DAG('branch_test', default_args=default_args, schedule_interval='@daily')

options = ['branch_a', 'branch_b', 'branch_c', 'branch_d']

run_first = DummyOperator(task_id='run_first', dag=dag)

branching = BranchPythonOperator(
        task_id='decide_branch',
        python_callable=lambda: random.choice(options),
        dag=dag
        )

run_first >> branching

join = DummyOperator(
        task_id='join',
        trigger_rule='one_success',
        dag=dag
        )

for option in options:
    t = BashOperator(
            task_id=option,
            bash_command=f'echo {option} executed at $(date) >> {option}.txt',
            dag=dag)
    branching >> t
    dummy_follow = DummyOperator(task_id='follow_' + option, dag=dag)
    t >> dummy_follow
    dummy_follow >> join
