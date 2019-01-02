import json
import os
from pathlib import Path

import tableauserverclient as TSC


def get_json_secret(secret_name):
    try:
        if os.sys.platform == 'linux':
            path = Path('/run/secrets/{}'.format(secret_name))
        elif os.sys.platform == 'darwin':
            path = Path('./secrets/{}.json'.format(secret_name))

        secret = json.load(path.open())
    except Exception as e:
        raise e

    return secret


def refresh_tableau_extract(datasource_id):
    ebi = get_json_secret('ebi_db_conn')['db_connections']['fi_dm_ebi']

    server = TSC.Server('https://ebi.coh.org', use_server_version=True)
    tableau_auth = TSC.TableauAuth(ebi['user'].split(sep='\\')[1], ebi['password'])

    server.auth.sign_in(tableau_auth)
    ds = server.datasources.get_by_id(datasource_id)
    server.datasources.refresh(ds)
    server.auth.sign_out()
