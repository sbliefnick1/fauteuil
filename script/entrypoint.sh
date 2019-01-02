#!/usr/bin/env bash 

TRY_LOOP="20"

cat /run/secrets/freetds.conf >> /etc/freetds/freetds.conf
cat /run/secrets/odbc.ini >> /etc/odbc.ini

AIRFLOW_HOME="/usr/local/airflow"
SECRETS="/run/secrets"

REDIS_HOST="redis"
REDIS_PORT="6379"
REDIS_PASSWORD=""
REDIS_PREFIX=""

if [[ -n "$REDIS_PASSWORD" ]]; then
    REDIS_PREFIX=:${REDIS_PASSWORD}@
else
    REDIS_PREFIX=
fi

POSTGRES_HOST="postgres"
POSTGRES_PORT="5432"
POSTGRES_USER="$(cat ${SECRETS}/pg_user)"
POSTGRES_PASSWORD="$(cat ${SECRETS}/pg_password)"
POSTGRES_DB="$(cat ${SECRETS}/pg_db)"

AIRFLOW__CORE__EXECUTOR="CeleryExecutor"
AIRFLOW__CORE__SQL_ALCHEMY_CONN="postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
AIRFLOW__CORE__LOAD_EXAMPLES="False"
AIRFLOW__CORE__FERNET_KEY="$(cat ${SECRETS}/fernet_key)"
AIRFLOW__WEBSERVER__SECRET_KEY="$(cat ${SECRETS}/flask_secret_key)"
AIRFLOW__CELERY__BROKER_URL="redis://${REDIS_PREFIX}${REDIS_HOST}:${REDIS_PORT}/1"
AIRFLOW__CELERY__RESULT_BACKEND="db+postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}"
AIRFLOW__LDAP__URI="$(jq -r '.ldap.coh.uri' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__USER_FILTER="$(jq -r '.ldap.coh.user_filter' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__USER_NAME_ATTR="$(jq -r '.ldap.coh.user_name_attr' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__GROUP_MEMBER_ATTR="$(jq -r '.ldap.coh.group_member_attr' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__SUPERUSER_FILTER="$(jq -r '.ldap.coh.superuser_filter' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__DATA_PROFILER_FILTER="$(jq -r '.ldap.coh.data_profiler_filter' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__BIND_USER="$(jq -r '.ldap.coh.bind_user' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__BIND_PASSWORD="$(jq -r '.ldap.coh.bind_password' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__BASEDN="$(jq -r '.ldap.coh.basedn' ${SECRETS}/ebi_db_conn)"
AIRFLOW__LDAP__SEARCH_SCOPE="$(jq -r '.ldap.coh.search_scope' ${SECRETS}/ebi_db_conn)"

export \
  AIRFLOW__CORE__EXECUTOR \
  AIRFLOW__CORE__SQL_ALCHEMY_CONN \
  AIRFLOW__CORE__LOAD_EXAMPLES \
  AIRFLOW__CORE__FERNET_KEY \
  AIRFLOW__WEBSERVER__SECRET_KEY \
  AIRFLOW__CELERY__BROKER_URL \
  AIRFLOW__CELERY__RESULT_BACKEND \
  AIRFLOW__LDAP__URI \
  AIRFLOW__LDAP__USER_FILTER \
  AIRFLOW__LDAP__USER_NAME_ATTR \
  AIRFLOW__LDAP__GROUP_MEMBER_ATTR \
  AIRFLOW__LDAP__SUPERUSER_FILTER \
  AIRFLOW__LDAP__DATA_PROFILER_FILTER \
  AIRFLOW__LDAP__BIND_USER \
  AIRFLOW__LDAP__BIND_PASSWORD \
  AIRFLOW__LDAP__BASEDN \
  AIRFLOW__LDAP__SEARCH_SCOPE \


# Install custom python package if requirements.txt is present
if [[ -e "/requirements.txt" ]]; then
    $(which pip) install --user -r /requirements.txt
fi

wait_for_port() {
  local name="$1" host="$2" port="$3"
  local j=0
  while ! nc -z "$host" "$port" >/dev/null 2>&1 < /dev/null; do
    j=$((j+1))
    if [[ ${j} -ge ${TRY_LOOP} ]]; then
      echo >&2 "$(date) - $host:$port still not reachable, giving up"
      exit 1
    fi
    echo "$(date) - waiting for $name... $j/$TRY_LOOP"
    sleep 5
  done
}

wait_for_redis() {
  # Wait for Redis if we are using it
  if [[ "$AIRFLOW__CORE__EXECUTOR" = "CeleryExecutor" ]]; then
    wait_for_port "Redis" "$REDIS_HOST" "$REDIS_PORT"
  fi
}


case "$1" in
  webserver)
    wait_for_port "Postgres" "$POSTGRES_HOST" "$POSTGRES_PORT"
    wait_for_redis
    airflow initdb
    exec airflow webserver
    ;;
  worker|scheduler)
    wait_for_port "Postgres" "$POSTGRES_HOST" "$POSTGRES_PORT"
    wait_for_redis
    # To give the webserver time to run initdb.
    sleep 10
    exec airflow "$@"
    ;;
  flower)
    wait_for_redis
    exec airflow "$@"
    ;;
  version)
    exec airflow "$@"
    ;;
  *)
    # The command is something like bash, not an airflow subcommand. Just run it in the right environment.
    exec "$@"
    ;;
esac