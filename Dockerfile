# VERSION 0.1
# AUTHOR Soren Bliefnick 
# DESCRIPTION Airflow container for Swarm
# BUILD docker build --rm -t sbliefnick/fauteuil .
# SOURCE https://github.com/sbliefnick/fauteuil
# Based on puckel/docker-airflow https://github.com/puckel/docker-airflow

FROM python:3.6

# do not prompt user for choices on installation of packages
ENV DEBIAN_FRONTEND noninteractive
ENV TERM linux

# airflow
ARG AIRFLOW_VERSION=1.9.0
ARG AIRFLOW_HOME=/usr/local/airflow

ENV LANGUAGE en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV LC_CTYPE en_US.UTF-8
ENV LC_MESSAGES en_US.UTF-8

RUN set -ex \
	&& buildDeps=' \
		build-essential \
		git \
		libblas-dev \
		libffi-dev \
		libkrb5-dev \
		liblapack-dev \
		libpq-dev \
		libsasl2-dev \
		libssl-dev \
		python3-dev \
	' \
	&& apt-get update -yqq \
	&& apt-get upgrade -yqq \
	&& apt-get install -yqq --no-install-recommends \
		apt-utils \
		$buildDeps \
		curl \
		freetds-dev \
		locales \
		netcat \
		python3-pip \
		python3-requests \
	# 	rysnc \
	&& sed -i 's/^# en_US.UTF-8 UTF-8$/en_US.UTF-8 UTF-8/g' /etc/locale.gen \
	&& locale-gen \
	&& update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 \
	&& useradd -ms /bin/bash -d ${AIRFLOW_HOME} airflow \
	&& pip install -U pip setuptools wheel \
	&& pip install Cython \
	&& pip install apache-airflow[celery,crypto,mssql,password,postgres]==$AIRFLOW_VERSION \ 
	&& pip install celery[redis]==4.1.0 \
	&& pip install ndg-httpsclient \
	&& pip install pandas==0.22.0 \
	&& pip install psycopg2 \ 
	&& pip install pyasn1 \
	&& pip install pyOpenSSL \
	&& pip install pytz \
	&& pip install SQLAlchemy==1.2.5 \
	&& pip install tableauserverclient \
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

RUN chown -R airflow: ${AIRFLOW_HOME}

EXPOSE 8080 5555 8793

USER airflow
WORKDIR ${AIRFLOW_HOME}
ENTRYPOINT ["/entrypoint.sh"]
