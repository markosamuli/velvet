import functools
from fabric.api import run, env, settings
 
import imp
import importlib

import velvet.aws.config

def find_executable(cmd):
    result = run('command -v %s' % cmd, quiet=True)
    if result.return_code == 0: 
        if len(result) == 0:
            return None
        return result
    return None


def dir_exists(dir):
    return run('[ -d %s ] && echo 1 || echo 0' % dir) == '1'


def file_exists(dir):
    return run('[ -e %s ] && echo 1 || echo 0' % dir) == '1'


def list_files(dir):
    return sorted(run('ls -x %(dir)s' % { 'dir': dir }).split())  


def with_aws(func):
    """A decorator that loads AWS configuration."""

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        """ Path to the configuration file containing the AWS IAM user credentials """
        env.setdefault('aws_config', 'config/aws.yml')

        """ Run AWS configuration """
        velvet.aws.config.load()

        return func(*args, **kwargs)

    return decorated


def with_build_defaults(func):

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        """ By default, include the whole project root in the build """
        env.setdefault('build_root', '.')

        """ Temporary directory for building """
        env.setdefault('build_tmp', 'tmp')

        """ Path to the file containing the list of files to exclude in the build """
        env.setdefault('build_exclude_file', 'config/build-exclude.txt')

        return func(*args, **kwargs)

    return decorated


def with_defaults(func):
    """A decorator that sets all defaults for a task."""

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        """ Python binary name """
        env.setdefault('python_bin', 'python')

        """ Deployment username and group """
        env.setdefault('user', 'ubuntu')
        env.setdefault('group', 'ubuntu')

        """ Base directory where the applications are deployed to """
        env.setdefault('base_dir', '/srv/www')

        """ Web server username and group """
        env.setdefault('www_owner', 'www-data')
        env.setdefault('www_group', 'www-data')

        """ S3 deployment bucket and package name """
        env.setdefault('deploy_package', env.app_name)
        env.setdefault('deploy_bucket', env.app_name + '-deploy')
        env.setdefault('deploy_package_path', '')

        """ Path to look deployment hook scripts for, relative to the project root """
        env.setdefault('deploy_hook_path', 'build/deploy')

        """ 
        The path where to deploy the application to within the deployment base directory.
        By default, deploy application to the path after it's name. This can be changed in the
        config, if there is a need for example to deploy multiple environments on the same server.
        """
        env.setdefault('app_path', "%(app_name)s" % { 'app_name': env.app_name })

        """ Full path where to deploy the application to """
        env.setdefault('domain_path', "%(base_dir)s/%(app_path)s" % \
                                  { 'base_dir':env.base_dir,
                                    'app_path':env.app_path })

        """ Symlink to the current release """
        env.setdefault('current_path', "%(domain_path)s/current" % \
                                       { 'domain_path':env.domain_path })

        """ Path to the releases directory """
        env.setdefault('releases_path', "%(domain_path)s/releases" % \
                                        { 'domain_path':env.domain_path })

        """ Path to the shared directory maintained between releases """
        env.setdefault('shared_path', "%(domain_path)s/shared" % \
                                      { 'domain_path':env.domain_path })

        """ Keep application s3cmd configuration in the application root """
        env.setdefault('s3cfg', "%(domain_path)s/.s3cfg" % \
                                { 'domain_path':env.domain_path })

        return func(*args, **kwargs)

    return decorated


def with_releases(func):
    """A decorator that loads release data from the server."""

    @functools.wraps(func)
    def decorated(*args, **kwargs):

        """ Do not run this if the list of releases has already been set """
        if not env.has_key('releases'):
            if dir_exists(env.releases_path):
                env.releases = filter(lambda a: a != 'dummy', sorted(run('ls -x %(releases_path)s' % { 'releases_path':env.releases_path }).split()))

                if len(env.releases) >= 1:
                    env.current_revision = env.releases[-1]
                    env.current_release = "%(releases_path)s/%(current_revision)s" % \
                                                { 'releases_path':env.releases_path, 
                                                  'current_revision':env.current_revision }
                if len(env.releases) > 1:
                    env.previous_revision = env.releases[-2]
                    env.previous_release = "%(releases_path)s/%(previous_revision)s" % \
                                                { 'releases_path':env.releases_path, 
                                                  'previous_revision':env.previous_revision }

        return func(*args, **kwargs)
    return decorated


