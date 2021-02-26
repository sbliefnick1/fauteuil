# VERSION
# AUTHOR Soren Bliefnick 
# DESCRIPTION Airflow container for Swarm
# BUILD docker build --rm -t sbliefnick/fauteuil .
# SOURCE https://github.com/sbliefnick/fauteuil
# Based on puckel/docker-airflow https://github.com/puckel/docker-airflow

FROM python:3.8-slim

# Never prompts the user for choices on installation/configuration of packages
ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# Airflow
ARG AIRFLOW_VERSION=2.0.1
ARG AIRFLOW_HOME=/usr/local/airflow

# Define en_US.
ENV LANGUAGE en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
ENV LC_MESSAGES en_US.UTF-8

RUN set -ex \
    && buildDeps=' \
        python3-dev \
        python2.7-dev \
        libkrb5-dev \
        libsasl2-dev \
        libssl-dev \
        libffi-dev \
        build-essential \
        libblas-dev \
        liblapack-dev \
        libpq-dev \
        libldap2-dev \
        libsasl2-dev \
        slapd \
        ldap-utils \
      #  python-tox \
        lcov \
        valgrind \
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
        jq \
        gnupg \
    && sed -i 's/^# en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/g' /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 \
    && useradd -ms /bin/bash -d ${AIRFLOW_HOME} airflow \
    && pip install -U pip setuptools wheel \
    && pip install Cython==0.29.21 \
    && pip install pytz==2021.1 \
    && pip install pyOpenSSL==20.0.1 \
    && pip install ndg-httpsclient==0.5.1 \
    && pip install pyasn1==0.4.8 \
    && pip install click==7.1.2 \
    && pip install pymssql==2.1.5 apache-airflow[celery,crypto,ldap,mssql,odbc,password,postgres,ssh,statsd]==$AIRFLOW_VERSION \
    && pip install celery[redis]==4.4.7 \
    && pip install gevent==21.1.2 \
	&& pip install pandas==1.2.2 \
	&& pip install paramiko==2.7.2 \
	&& pip install psycopg2-binary==2.8.6 \
	&& pip install pyodbc==4.0.30 \
	&& pip install python-ldap==3.3.1 \
	&& pip install sshtunnel==0.4.0 \
	&& pip install SQLAlchemy==1.3.23 \
	&& pip install tableauserverclient==0.14.1 \
	&& pip install tableaudocumentapi==0.6 \
	&& pip install tornado==5.1.1 \
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
COPY auxiliary ${AIRFLOW_HOME}/auxiliary/

ENV PYTHONPATH ${AIRFLOW_HOME} 

RUN mkdir -p /var/nfsshare
RUN chown -R airflow: ${AIRFLOW_HOME} && chown airflow:airflow /var/nfsshare
RUN chmod +x /entrypoint.sh
RUN chmod 776 /etc/freetds/freetds.conf
RUN chmod 776 /etc/odbc.ini

EXPOSE 8080 5555 8793 6379 5432 9090 443

USER airflow
WORKDIR ${AIRFLOW_HOME}
ENTRYPOINT ["/entrypoint.sh"]