from fabric.api import env

import yaml
import os
import ConfigParser
import functools
import semantic_version

from velvet import __version__

from velvet.decorators import deprecated

_config = None
environment_config = {}
VELVET_VERSION = semantic_version.Version(__version__)

def save():
    global _config
    if _config is None:
        _config = _read_config_file()
    return _write_config_file(_config)


def load():
    global _config
    if _config is None:
        _config = _read_config_file()
    return _config


def _read_config_file():

    config = ConfigParser.ConfigParser()

    if os.path.exists('.velvet'):
        config.readfp(open('.velvet'))

    return config


def _write_config_file(config):

    if 'config' in env:
        if not config.has_section('velvet'):
            config.add_section('velvet')
        config.set('velvet', 'config', env.config)

    if 'aws_config' in  env:
        if not config.has_section('aws'):
            config.add_section('aws')
        config.set('aws', 'config', env.aws_config)

    with open('.velvet', 'w') as outfile:
        config.write(outfile)

    return config


@deprecated
def init():
    """Initialize default configuration from the environment variables"""
    pass


def find_config_file():
    search = [
        'config/velvet.yml',
        'config/deploy.yml',
    ]
    for file in search:
        if os.path.exists(file):
            return file
    return None


def with_config_defaults(func):
    """A decorator that sets all defaults for a task."""

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        config = load()
        if config.has_option('velvet', 'config'):
            env.setdefault('config', config.get('velvet', 'config'))
        else:
            env.setdefault('config', find_config_file())

        return func(*args, **kwargs)

    return decorated


def _format_ruby_yaml_config(data):

    config = dict()

    for k, v in data:
        if k[0] == ":":
            key = k[1:]
        else:
            key = k
        if isinstance(v, dict):
            v = _format_ruby_yaml_config(v)
        config[key] = v

    return config


def environment(name):
    """Initialize configuration for the given environment from the config file"""

    global environment_config
    config = get_environment_config(name)

    env.environment = name

    if 'deploy_ssh_key' in config:
        env.key_filename = os.environ['HOME'] + '/.ssh/' + config['deploy_ssh_key']

    if 'deploy_s3_bucket' in config:
        config['deploy_bucket'] = config['deploy_s3_bucket']

    if 'assets_s3_bucket' in config:
        config['assets_bucket'] = config['assets_s3_bucket']

    if 'app_package_name' in config:
        config['deploy_package'] = config['app_package_name']

    # list of configuration options that are passed directly into the fabric environment dictionary
    config_options = [
        'app_name',                 # application name

        'deploy_package',           # deployment package file name without extension
        'deploy_bucket',            # deployment S3 bucket name
        'deploy_publish_path',      # path to copy deployment package to on the S3 bucket

        'stack_id',                 # cloudformation stack name
        's3cfg',                    # s3cfg file path on the remote server

        'build_root',               # the folder in which the build will take place (the code you want to go up)
        'build_exclude',
        'app_path',
        'deploy_hook_path',         # path to deploy hooks within the build

        'assets',                   # list of asset files
        'assets_root',              # root directory inside the application for assets
        'assets_bucket',            # assets S3 bucket name
        'gzip_enabled',             # use compressed assets if available when publishing to S3

        'cookbooks_package',        # cookbooks package file name without extension
        'cookbooks_root',           # build root for cookbooks
        'cookbooks_publish_path',   # path to copy deployment package to on the S3 bucket

        'opsworks',                 # OpsWorks configuration

        'cloudformation_path',      # path to cloudformation template files
        'disable_rollback',         # disable cloudformation rollback on failure

        'security',                 # additional options passed for the provisioning scripts
        'roles',                    # non aws/static webserver roles
        'stacks',                   # CloudFormation stacks configuration
    ]

    for key in config_options:
        if key in config:
            env[key] = config[key]

    if 'deploy_user' in config:
        env.user = config['deploy_user']
        if 'deploy_group' in config:
            env.group = config['deploy_group']
        else:
            env.group = env.user

    environment_config = config

    return environment_config
    

def get_config():
    return environment_config


def set_config(config_file):
    if config_file is None:
        raise ValueError('Config file path missing')
    env.config = config_file

class UnsupportedVersion(Exception):
    pass

@with_config_defaults
def get_environment_config(environment):

    if 'config' not in env:
        raise Exception('Config file path not defined')

    if not os.path.exists(env.config):
        raise Exception('Config file missing: ' + env.config)

    f = open(env.config)
    cfg = yaml.safe_load(f)
    f.close()

    # read the version number from the config file if available
    if 'version' in cfg:
        version = semantic_version.Version(str(cfg['version']), partial=True)
    else:
        if ':defaults' in cfg or ':environments' in cfg:
            version = semantic_version.Version('0.2.0')
        else:
            version = semantic_version.Version('0.3.0')

    if version > VELVET_VERSION:
        raise UnsupportedVersion('Configuration file is unsupported by the installed Velvet version ({} > {})'.format(version, VELVET_VERSION))

    # Velvet before version 0.3 used key values compatible with the YAML file shared with Rake tasks
    if version < semantic_version.Version('0.3.0'):
        cfg = _format_ruby_yaml_config(cfg)

    if cfg['environments'][environment] is None:
        raise Exception('Configuration not found for environment "' + environment + '" in ' + env.config)

    return dict(cfg['defaults'].items() + cfg['environments'][environment].items())
    

@deprecated
def aws_config():
    import velvet.aws.config
    velvet.aws.config.load()
