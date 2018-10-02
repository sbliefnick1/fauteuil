import json


def get_secret(secret_name):
    try:
        with open('/run/secrets/{}'.format(secret_name), 'r') as secret_file:
            return json.load(secret_file)
    except IOError:
        return None
