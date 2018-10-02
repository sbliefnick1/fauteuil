# VERSION
# AUTHOR Soren Bliefnick 
# DESCRIPTION Airflow container for Swarm
# BUILD docker build --rm -t sbliefnick/fauteuil .
# SOURCE https://github.com/sbliefnick/fauteuil
# Based on puckel/docker-airflow https://github.com/puckel/docker-airflow

FROM python:3.5-slim

# Never prompts the user for choices on installation/configuration of packages
ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Airflow
ARG AIRFLOW_VERSION=1.10.0
ARG AIRFLOW_HOME=/usr/local/airflow
ENV SLUGIFY_USES_TEXT_UNIDECODE=yes

# Define en_US.
ENV LANGUAGE en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
ENV LC_MESSAGES en_US.UTF-8

RUN set -ex \
    && buildDeps=' \
        python3-dev \
        libkrb5-dev \
        libsasl2-dev \
        libssl-dev \
        libffi-dev \
        build-essential \
        libblas-dev \
        liblapack-dev \
        libpq-dev \
        git \
    ' \
    && apt-get update -yqq \
    && apt-get upgrade -yqq \
    && apt-get install -yqq --no-install-recommends \
        $buildDeps \
        python3-pip \
        python3-requests \
        apt-utils \
        curl \
		unixodbc \
		unixodbc-dev \
		freetds-dev \
		freetds-bin \
		tdsodbc \
        rsync \
        netcat \
        locales \
    && sed -i 's/^# en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/g' /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 \
    && useradd -ms /bin/bash -d ${AIRFLOW_HOME} airflow \
    && pip install -U pip setuptools wheel \
    && pip install Cython==0.28.5 \
    && pip install pytz==2018.5 \
    && pip install pyOpenSSL==18.0.0 \
    && pip install ndg-httpsclient==0.5.1 \
    && pip install pyasn1==0.4.4 \
    && pip install click==6.7 \
    && pip install apache-airflow[celery,crypto,ldap,mssql,password,postgres]==$AIRFLOW_VERSION \
    && pip install celery[redis]==4.1.1 \
    && pip install gevent==1.3.6 \
	&& pip install pandas==0.23.4 \
	&& pip install psycopg2==2.7.5 \
	&& pip install pyodbc==4.0.24 \
	&& pip install SQLAlchemy==1.1.18 \
	&& pip install tableauserverclient==0.7 \
    && apt-get purge --auto-remove -yqq $buildDeps \
    && apt-get clean \
    && rm -rf \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/* \
        /usr/share/man \
        /usr/share/doc \
        /usr/share/doc-base

COPY script/entrypoint.sh /entrypoint.sh
COPY config/airflow.cfg ${AIRFLOW_HOME}/airflow.cfg
COPY config/odbcinst.ini /etc/odbcinst.ini
COPY dags ${AIRFLOW_HOME}/dags/ 
COPY auxiliary ${AIRFLOW_HOME}/auxiliary/

ENV PYTHONPATH ${AIRFLOW_HOME} 

RUN chown -R airflow: ${AIRFLOW_HOME}
RUN chmod +x /entrypoint.sh
RUN chmod 776 /etc/freetds/freetds.conf
RUN chmod 776 /etc/odbc.ini

EXPOSE 8080 5555 8793 6379 5432 9090

USER airflow
WORKDIR ${AIRFLOW_HOME}
ENTRYPOINT ["/entrypoint.sh"]