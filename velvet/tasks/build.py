import pprint
import textwrap
from fabric.api import env, local

import os
import os.path
import sys
from subprocess import check_output, CalledProcessError

import glob2

from boto.s3.connection import S3Connection
from boto.s3.key import Key

from velvet.helpers import with_defaults, with_build_defaults, with_aws
from velvet.aws.config import with_opsworks_defaults

from datetime import datetime, timedelta

def get_build():
    return os.getenv('BUILD_NUMBER', 'latest')

@with_defaults
@with_build_defaults
def config():

    target_build = get_build()
    if target_build is None or target_build == 'latest':
        raise Exception('BUILD_NUMBER environment variable needs to be defined') 

    # target build name or number
    env['target_build'] = target_build

    # application package
    env['build_package_name'] = "%(environment)s-%(target_build)s-%(deploy_package)s" % {
        'environment' : env['environment'],
        'target_build' : target_build,
        'deploy_package' : env['deploy_package']
    }
    env['build_package_file'] = env['build_tmp'] + "/" + env['build_package_name'] + ".tgz"
    env['build_package_path'] = env['build_tmp'] + "/" + env['build_package_name'] + ".tgz"

    if 'deploy_publish_path' in env and len(env['deploy_publish_path']) > 0:
        env['build_publish_root'] = env['environment'] + '/' + env['deploy_publish_path']
    else:
        env['build_publish_root'] = env['environment']

    # assets root directory on S3
    env['assets_publish_root'] = target_build


    env.setdefault('build_config_format', 'php')

    if env['build_config_format'] == 'php':
        env.setdefault('build_config_path', os.path.join(env['build_root'], 'build.php'))


@with_defaults
@with_build_defaults
def config_cookbooks():

    # only used for OpsWorks deployment with custom cookbooks
    env['cookbooks_package_name'] = "%(environment)s-%(target_build)s-%(cookbooks_package)s" % {
        'environment' : env['environment'],
        'target_build' : env['target_build'],
        'cookbooks_package' : env['cookbooks_package'],
    }
    env['cookbooks_package_file'] = env['build_tmp'] + "/" + env['cookbooks_package_name'] + ".tgz"

    if not 'cookbooks_publish_path' in env:
        env['cookbooks_publish_root'] = env['environment'] + '/cookbooks'
    elif len(env['cookbooks_publish_path']) > 0:
        env['cookbooks_publish_root'] = env['environment'] + '/' + env['cookbooks_publish_path']
    else:
        raise Exception("cookbooks_publish_path cannot be empty")


@with_defaults
@with_build_defaults
@with_opsworks_defaults
def display_deployment_paths():

    bucket = env['deploy_bucket']

    print ""
    print "Application:"
    app_paths = _get_app_publish_paths('<BUILD_NUMBER>')
    for name, path in app_paths.iteritems():
        print "{name}: https://{bucket}.s3.amazonaws.com/{path}".format(name=name, bucket=bucket, path=path)

    print ""
    print "Cookbooks:"
    cookbook_paths = _get_cookbooks_publish_paths('<BUILD_NUMBER>')
    for name, path in cookbook_paths.iteritems():
        print "{name}: https://{bucket}.s3.amazonaws.com/{path}".format(name=name, bucket=bucket, path=path)



def _get_app_publish_paths(build_number):

    if 'deploy_publish_path' in env and len(env['deploy_publish_path']) > 0:
        env['build_publish_root'] = env['environment'] + '/' + env['deploy_publish_path']
    else:
        env['build_publish_root'] = env['environment']

    build = {}
    build['build_package'] = env['build_publish_root'] + '/' + build_number + '/' + env['deploy_package'] + '.tgz'
    build['latest_package'] = env['build_publish_root'] + '/latest/' + env['deploy_package'] + '.tgz'
    build['latest_build'] = env['build_publish_root'] + '/latest/build'
    return build


def _get_cookbooks_publish_paths(build_number):

    if len(env['cookbooks_publish_path']) > 0:
        env['cookbooks_publish_root'] = env['environment'] + '/' + env['cookbooks_publish_path']
    else:
        raise Exception("cookbooks_publish_path cannot be empty")

    build = {}
    build['build_package'] = env['cookbooks_publish_root'] + '/' + build_number + '/' + env['cookbooks_package'] + '.tgz'
    build['latest_package'] = env['cookbooks_publish_root'] + '/latest/' + env['cookbooks_package'] + '.tgz'
    build['latest_build'] = env['cookbooks_publish_root'] + '/latest/build'
    return build

def create_build_config():

    config()

    data = {
        'ENVIRONMENT' : env['environment'],
        'BUILD_NUMBER' : env['target_build'],
    }

    if env['build_config_format'] == 'php':

        build_config = """
        class BuildConfig {
            const ENVIRONMENT = "%(environment)s";
            const BUILD_NUMBER = %(target_build)s;
        }
        """ % dict(env)

        build_config = "<?php\n" + textwrap.dedent(build_config)

        with open(env['build_config_path'], 'wb') as build_file:
            build_file.write(build_config)


def remove_build_config():

    config()
    os.remove(env['build_config_path'])


@with_defaults
@with_build_defaults
def app_build():

    """ Setup paths """
    config()

    """ Create temporary directory """
    if not os.path.exists(env['build_tmp']):
        local('mkdir ' + env['build_tmp'])

    local('touch ' + env['build_tmp'] + '/BUILD_EXCLUDE_ALL')

    if os.path.exists(env['build_package_file']):
        raise Exception('Build package already exists: ' + env['build_package_file'])

    tar_bin = "tar"

    """ Use GNU tar on OS X (additional options and exclude OSX garbage """
    if sys.platform == 'darwin':
        tar_bin = "gtar"
        try:
            check_output("which gtar", shell=True)
        except CalledProcessError as e:
            print "GNU tar not installed, try following:"
            print "brew install coreutils"
            print "brew install brew tap homebrew/dupes"
            print "brew install gnu-tar"
            return False

    opts = []

    """ Exclude git directories """
    opts.append("--exclude-vcs")

    """ Exclude backup and swap files """
    opts.append("--exclude-backups")

    """ Do not dump the contents of the directory, but dump the directory itself and the file. """
    opts.append("--exclude-tag=BUILD_EXCLUDE")

    """ Omit directories containing file BUILD_EXCLUDE_ALL entirely. """
    opts.append("--exclude-tag-all=BUILD_EXCLUDE_ALL")
    
    """ Exclude development files """
    opts.append("--exclude='.sass-cache'")
    opts.append("--exclude='*.sublime-*'")

    """ Exclude compiled Python files """
    opts.append("--exclude='*.pyc'")

    """ Exclude OSX garbage """
    opts.append("--exclude=.DS_Store")

    if 'build_exclude' in env:
        for exclude in env['build_exclude']:
            opts.append("--exclude=" + exclude)

    if os.path.exists(env['build_exclude_file']):
        opts.append("--exclude-from=" + env['build_exclude_file'])

    args = { 
        'tmp' : env['build_tmp'],
        'tar_bin' : tar_bin,
        'tar_opts' : " ".join(opts),
        'build_root' : env['build_root'],
        'build_package_name' : env['build_package_name']
    }

    def run_command(cmd):
        check_output(cmd % args, shell=True)    

    print "* create tar archive -> %(tmp)s/%(build_package_name)s.tar" % args
    run_command("%(tar_bin)s -c %(tar_opts)s -f %(tmp)s/%(build_package_name)s.tar %(build_root)s")

    print "* compress tar archive with gzip -> %(tmp)s/%(build_package_name)s.tgz" % args
    run_command("gzip -c %(tmp)s/%(build_package_name)s.tar > %(tmp)s/%(build_package_name)s.tgz")
    run_command("rm %(tmp)s/%(build_package_name)s.tar")


@with_defaults
@with_build_defaults
@with_aws
def app_publish():

    """ Setup paths """
    config()

    """ Check that the file actually exists """
    if not os.path.exists(env['build_package_file']):
        raise Exception("Package file %(package_file)s does not exist" % {
            'package_file' : env['build_package_file']
        })

    """ Set S3 file keys we are going to publish """
    app_paths = _get_app_publish_paths(env['target_build'])

    """ get an instance of the S3 interface using the default configuration """
    conn = S3Connection()

    """ create a bucket """
    b = conn.lookup(env['deploy_bucket'])
    if b is None:
        b = conn.create_bucket(env['deploy_bucket'])

    """ upload a file for this build """
    build = Key(b)
    build.key = app_paths['build_package']
    build.set_contents_from_filename(env['build_package_file'])

    """ upload a file for the latest build """
    latest = Key(b)
    latest.key = app_paths['latest_package']
    latest.set_contents_from_filename(env['build_package_file'])

    """ upload a file for the latest build """
    latest_build = Key(b)
    latest_build.key = app_paths['latest_build']
    latest_build.set_contents_from_string(env['target_build'])


@with_defaults
@with_build_defaults
@with_aws
def assets_publish():

    """ Setup paths """
    config()

    """ get an instance of the S3 interface using the default configuration """
    conn = S3Connection()

    """ create a bucket """
    b = conn.lookup(env['assets_bucket'])
    if b is None:
        b = conn.create_bucket(env['assets_bucket'])

    def list_assets():
        publish_root = env['assets_publish_root']
        assets_root = os.path.join(env['build_root'], env['assets_root'])
        for path in env['assets']:
            for item in glob2.glob(os.path.join(assets_root, path)):
                if os.path.basename(item) == "README.md":
                    continue
                if os.path.isdir(item):
                    continue
                yield (item, item.replace(assets_root, publish_root))


    def find_gzipped_file(source):
        if not env['gzip_enabled']:
            return None
        gzipped_source = source + ".gz"
        if os.path.exists(gzipped_source):
            original_size = os.path.getsize(source)
            gzipped_size = os.path.getsize(gzipped_source)
            if gzipped_size < original_size:
                return gzipped_source
        return None


    for source, target in list_assets():

        o = Key(b)
        o.key = target

        expires = datetime.utcnow() + timedelta(days=(365))
        expires = expires.strftime("%a, %d %b %Y %H:%M:%S GMT")

        gzipped_source = find_gzipped_file(source)
        if gzipped_source:
            o.set_contents_from_filename(gzipped_source, headers={
                'Expires': expires,
                'Content-Encoding': 'gzip',
                'Cache-Control' : 'public, max-age=31557600'
            })
        else:
            o.set_contents_from_filename(source, headers={
                'Expires': expires,
                'Cache-Control' : 'public, max-age=31557600'
            })

        o.set_acl('public-read')

        print target


@with_defaults
@with_build_defaults
def cookbooks_build():

    """ Setup paths """
    config()
    config_cookbooks()

    """ Create temporary directory """
    if not os.path.exists(env['build_tmp']):
        local('mkdir ' + env['build_tmp'])

    tar_bin = "tar"

    """ Use GNU tar on OS X (additional options and exclude OSX garbage """
    if sys.platform == 'darwin':
        tar_bin = "gtar"
        try:
            check_output("which gtar", shell=True)
        except CalledProcessError as e:
            print "GNU tar not installed, try following:"
            print "brew install coreutils"
            print "brew install brew tap homebrew/dupes"
            print "brew install gnu-tar"
            return False

    opts = []

    """ Exclude git directories """
    opts.append("--exclude-vcs")

    """ Exclude backup and swap files """
    opts.append("--exclude-backups")

    args = {
        'tmp' : env['build_tmp'],
        'tar_bin' : tar_bin,
        'tar_opts' : " ".join(opts),
        'cookbooks_root' : env['cookbooks_root'],
        'cookbooks_package_name' : env['cookbooks_package_name'],
    }

    def run_command(cmd):
        check_output(cmd % args, shell=True)

    print "* create tar archive -> %(tmp)s/%(cookbooks_package_name)s.tar" % args
    run_command("%(tar_bin)s -c %(tar_opts)s -f %(tmp)s/%(cookbooks_package_name)s.tar %(cookbooks_root)s")

    print "* compress tar archive with gzip -> %(tmp)s/%(cookbooks_package_name)s.tgz" % args
    run_command("gzip -c %(tmp)s/%(cookbooks_package_name)s.tar > %(tmp)s/%(cookbooks_package_name)s.tgz")
    run_command("rm %(tmp)s/%(cookbooks_package_name)s.tar")


@with_defaults
@with_build_defaults
@with_aws
def cookbooks_publish():

    """ Setup paths """
    config()
    config_cookbooks()

    """ Check that the file actually exists """
    if not os.path.exists(env['cookbooks_package_file']):
        raise Exception("Package file %(package_file)s does not exist" % {
            'package_file' : env['cookbooks_package_file']
        })

    """ Set S3 file keys we are going to publish """
    cookbook_paths = _get_cookbooks_publish_paths(env['target_build'])

    """ get an instance of the S3 interface using the default configuration """
    conn = S3Connection()

    """ create a bucket """
    b = conn.lookup(env['deploy_bucket'])
    if b is None:
        b = conn.create_bucket(env['deploy_bucket'])

    """ upload a file for this build """
    build = Key(b)
    build.key = cookbook_paths['build_package']
    build.set_contents_from_filename(env['cookbooks_package_file'])

    """ upload a file for the latest build """
    latest = Key(b)
    latest.key = cookbook_paths['latest_package']
    latest.set_contents_from_filename(env['cookbooks_package_file'])

    """ upload a file for the latest build """
    latest_build = Key(b)
    latest_build.key = cookbook_paths['latest_build']
    latest_build.set_contents_from_string(env['target_build'])

@with_defaults
@with_build_defaults
def write_build_number():

    """ Setup paths """
    config()

    build_file = os.path.join(env['build_root'], 'BUILD_NUMBER')
    with open(build_file,'w') as f:
        f.write(env['target_build'])

@with_defaults
@with_build_defaults
def clean_build_number():
    build_file = os.path.join(env['build_root'], 'BUILD_NUMBER')
    if os.path.exists(build_file):
        local('rm %(build_file)s' % { 'build_file' : build_file })

