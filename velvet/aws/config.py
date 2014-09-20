import json
import yaml
import boto

import os
import functools
import csv

import velvet.config

from fabric.api import env

from fabric.utils import _AttributeDict

# The current AWS region
region = 'eu-west-1'

def with_aws_defaults(func):
    """A decorator that sets all defaults for a task."""

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        config = velvet.config.load()
        if config.has_option('aws', 'config'):
            env.setdefault('aws_config', config.get('aws', 'config'))
        else:
            env.setdefault('aws_config', 'config/aws.yml')

        return func(*args, **kwargs)

    return decorated


def with_opsworks_defaults(func):

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        env.setdefault('opsworks', False)

        env.setdefault('cookbooks_root', 'cookbooks')
        env.setdefault('cookbooks_package', env.app_name + '-cookbooks')
        env.setdefault('cookbooks_publish_path', 'cookbooks')

        return func(*args, **kwargs)

    return decorated


def import_iam_csv(file):

    def config_value(data):
        return {
            'user_name' : data['user_name'],
            'access_key_id' : data['access_key_id'],
            'secret_access_key' : data['secret_access_key'],
        }

    with open(file, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='"')
        data = [row for row in reader]
        header = data[0]

        if header == ['User Name', 'Access Key Id', 'Secret Access Key']:
            users = []
            for row in data[1:]:
                users.append({
                    'user_name' : row[0],
                    'access_key_id' : row[1],
                    'secret_access_key' : row[2],
                })

            if len(users) == 0:
                return None

            if len(users) == 1:
                return config_value(users[0])

            print 'Found multiple users, select one...'
            for i, user in enumerate(users):
                print "[{0}] {1}".format(str(i), user['user_name'])

            user_id = None
            while user_id == None:
                try:
                    user_id = int(raw_input('> '))
                    if user_id < 0 or user_id >= len(users):
                        raise ValueError('User not found')
                except ValueError:
                    user_id = None

            return config_value(users[user_id])

        else:
            raise ValueError('Failed to read CSV file, invalid formatting')


def import_iam_json(file):

    def config_value(data):

        if not data['AccessKey']:
            raise ValueError('Failed to read JSON file, invalid syntax')

        if data['AccessKey']['Status'] != "Active":
            raise ValueError('Access key is not active')

        return {
            'user_name' : str(data['AccessKey']['UserName']),
            'access_key_id' : str(data['AccessKey']['AccessKeyId']),
            'secret_access_key' : str(data['AccessKey']['SecretAccessKey']),
        }

    with open(file, 'rb') as jsonfile:
        data = json.load(jsonfile)
        return config_value(data)


def config_input(defaults=None):
    """Read AWS config options from user input on the command line"""

    if defaults is None:
        defaults = dict()

    access_key_id = raw_input('AWS Access Key Id [{}]: '.format(defaults.setdefault('access_key_id', '')))
    secret_access_key = raw_input('AWS Secret Access Key [{}]: '.format(defaults.setdefault('secret_access_key', '')))
    region = raw_input('AWS Region [{}]: '.format(defaults.setdefault('region', 'eu-west-1')))

    config = _AttributeDict(defaults)
    if len(access_key_id) > 0:
        config.access_key_id = access_key_id

    if len(secret_access_key) > 0:
        config.secret_access_key = secret_access_key

    if len(region) > 0:
        config.region = region

    return config


@with_aws_defaults
def save(data):
    """Save AWS configuration options into a config file"""

    if not isinstance(data, dict):
        raise ValueError('Invalid value, dictionary expected')

    # Resolve configuration file path
    config_file = os.getenv('DEPLOY_AWS_CONFIG', env.aws_config)

    print "Writing configuration to file {}".format(config_file)

    config_dir = os.path.dirname(config_file)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    # Write data into the file
    with open(config_file, 'w') as outfile:
        outfile.write(yaml.dump(dict(data), default_flow_style=False))


@with_aws_defaults
def load():
    """Load and initialize AWS configuration"""

    # Allow AWS config file outside the workspace
    config_file = os.getenv('DEPLOY_AWS_CONFIG', env.aws_config)
    if not os.path.exists(config_file):
    	raise Exception('AWS config file ' + config_file + ' not found')

    f = open(config_file)
    cfg = yaml.safe_load(f)
    f.close()

    # Use the global region variable
    global region
    if 'region' in cfg:
        region = cfg['region']

    # Update region config for required services
    if not boto.config.has_section('Boto'):
        boto.config.add_section('Boto')
        
    services = ['autoscale', 'cfn', 'ec2']
    for srv in services:
	   boto.config.set('Boto', srv + '_region_name', region)

    if 'access_key_id' in cfg and 'secret_access_key' in cfg:

        if not boto.config.has_section('Credentials'):
            boto.config.add_section('Credentials')

        boto.config.set('Credentials', 'aws_access_key_id', cfg['access_key_id'])
        boto.config.set('Credentials', 'aws_secret_access_key', cfg['secret_access_key'])

    else:

        raise Exception("AWS credentials missing in the config file")