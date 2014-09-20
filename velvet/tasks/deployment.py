from fabric.api import env, sudo, put, run, settings
import fabric.contrib.files

from velvet.decorators import deprecated

import glob
import os
import os.path
import json

from velvet.helpers import with_defaults, with_releases, dir_exists, list_files, find_executable, file_exists
import velvet.tasks.servers


def get_build():
    return os.getenv('BUILD_NUMBER', 'latest')


def restart():
    """ Restart web servers """
    print "*** Restart web servers"
    velvet.tasks.servers.reload_nginx()
    velvet.tasks.servers.reload_phpfpm()


@deprecated
def nginx_restart():
    velvet.tasks.servers.restart_nginx()


@deprecated
def clear_cache():
    velvet.tasks.servers.clear_nginx_cache()


@deprecated
def update_nginx_config(config_path):
    velvet.tasks.servers.upload_nginx_config(config_path)
    velvet.tasks.servers.reload_nginx()


def symlink(target_path, link_path, use_sudo=False):
    """ Create a symlink """
    if use_sudo:
        sudo("ln -nfs %(target_path)s %(link_path)s" % { 
            'target_path': target_path, 
            'link_path': link_path 
        }) 
    else:
        run("ln -nfs %(target_path)s %(link_path)s" % { 
            'target_path': target_path, 
            'link_path': link_path 
        })


@with_defaults
def ohai_info():
    if find_executable('ohai') == None:
        raise Exception("Chef client not installed on the remote server")
    ohai_data = sudo('ohai', quiet=True)
    return json.loads(ohai_data)


@with_defaults
def platform():
    data = ohai_info()
    return data['platform']


@with_defaults
def install_chef():
    if fabric.contrib.files.exists('/opt/chef', use_sudo=True):
        """ Chef client already installed on the server """
        return True
    run("sudo curl -L https://www.opscode.com/chef/install.sh | sudo bash")
    return True


@with_defaults
def install_s3cmd():
    """ Install s3cmd on the server if it's not installed already """
    if not find_executable('s3cmd') == None:
        return True

    if platform() in ['ubuntu', 'debian']:
        print "Installing s3cmd on the remote server"
        sudo('apt-get -y -q install s3cmd')
        return True

    return False


@with_defaults
def deploy_php():

    update_s3cmd_config()

    def check_config():

        def assert_in_env(name, err):
            if name not in env:
                raise Exception(err) 

        assert_in_env('releases_path', 'Release root path not defined')
        assert_in_env('deploy_bucket', 'Deployment S3 bucket not defined')
        assert_in_env('deploy_package', 'Deployment package not defined')                    
        assert_in_env('environment', 'Environment not defined')                
        assert_in_env('s3cfg', 's3cmd config file missing')

    def check_dependencies():
        if find_executable('s3cmd') == None:
            raise Exception("s3cmd executable not found on the remote server")

    check_config()
    check_dependencies()

    checkout()

    before_symlink()
    set_current()

    # this should not be done in default deployment because we might be running 
    # a shared environment or not on AWS
    # velvet.tasks.servers.set_phpfpm_instance_config()
    before_restart()
    restart()
    after_restart()


def before_symlink():
    """ Deployment hooks to be run before the current application symlink is updated """
    run_deploy_hook('before_symlink')


def before_restart():
    """ Deployment hooks to be run before any server or application instances are restarted """
    run_deploy_hook('before_restart')


def after_restart():
    """ Deployment hooks to be run after all server or application instances are restarted """
    run_deploy_hook('after_restart')


def run_deploy_hook(name):

    """ This should be called from within the deployment tasks."""

    if 'target_release' not in env:
        raise Exception("Target release path not defined")

    # Test if deploy hooks directory exists on the remote host
    deploy_hook_dir = os.path.join(env['target_release'], env['deploy_hook_path'])
    if not dir_exists(deploy_hook_dir):
        return

    print "Run '%s' deployment hooks" % name    

    script_match = os.path.join(deploy_hook_dir, name + '.sh')
    if file_exists(script_match):
        run(script_match)   
    # for script in list_files(script_match):
    #     run(script)   


@with_defaults
def cleanup_releases():
    """ Remove all releases from the server """
    run("cd %(releases_path)s && rm -rf *" % {
        'releases_path': env.releases_path
    })   


@with_defaults
@with_releases
def set_current():
    """ Sets the current directory to the new release """
    symlink(env.target_release, env.current_path)

    """ Update environment variables, see with_releases helper in the helpers.py file """

    if 'current_revision' in env:
        env.previous_revision = env.current_revision
        env.previous_release = env.current_release

    env.current_revision = env.target_revision
    env.current_release = env.target_release
    
    env.releases.append(env.target_revision)


def update_s3cmd_config():

    if 's3cfg' not in env:
        env['s3cfg'] = '/home/%(deploy_user)s/.s3cfg' % { 
            'deploy_user': env.user
        }

    if not fabric.contrib.files.exists(env['s3cfg']):
        if os.path.exists('config/.s3cfg'):
            print "*** Uploading missing s3cmd config file"
            put('config/.s3cfg', env['s3cfg'], mode=0600)
        else:
            raise Exception("Local s3cmd config file not found") 


@with_defaults
@with_releases
def checkout():

    """ Downloads the files from the repository """

    def set_release_paths():
        """ Set current release paths in env variables """
        from time import time
        env['target_revision'] = "%(target_revision).0f" % {
            'target_revision': time()
        }
        env['target_release'] = "%(releases_path)s/%(target_revision)s" % { 
            'releases_path': env['releases_path'], 
            'target_revision': env['target_revision']
        }

        target_build = get_build()
        env['package_path'] = "s3://" + env['deploy_bucket'] + '/' + env['environment'] + '/' + target_build + '/' + env['deploy_package'] + '.tgz'
        env['package_name'] = os.path.basename(env['target_release']) + ".tgz"


    def download_release_package():
        """Download and extract deployment package"""
        run("cd %(releases_path)s && s3cmd --config %(s3cfg_file)s get %(package_path)s %(package_name)s && mkdir %(target_release)s && tar zxvf %(package_name)s -C %(target_release)s" % { 
            'deploy_user': env.user,
            'releases_path': env.releases_path,
            'package_path': env.package_path,
            'package_name': env.package_name,
            'target_release': env.target_release,
            's3cfg_file' : env['s3cfg']
        })


    def cleanup_release():
        """Remove deployment package"""
        run("cd %(releases_path)s && rm %(package_name)s" % {
            'releases_path': env['releases_path'],
            'package_name': env['package_name']
        })


    print "*** Checkout the latest code into a release"
    set_release_paths()
    download_release_package()
    cleanup_release()       


@deprecated
def update_phpfpm_config(config_path):
    velvet.tasks.servers.upload_phpfpm_config(config_path)
    velvet.tasks.servers.set_phpfpm_instance_config()
    velvet.tasks.servers.reload_phpfpm()


@with_defaults
def set_maintenance():

    """Sets the current directory to the maintenance directory"""
    symlink(env.domain_path + "/maintenance", env.current_path)


def cleanup_autodeploy():

    target = '/home/' + env.user + '/autodeploy/autodeploy.log'
    sudo("rm %(target)s" % { 'target' : target })   


def update_app_autodeploy(config_path):

    # upload init script that gets run on every server reboot
    targetpath = '/etc/init/autodeploy.conf'
    put(config_path + targetpath, targetpath, use_sudo=True)
    sudo('chown root:root ' + targetpath)

    # upload autodeploy script files
    target = '/home/' + env.user + '/autodeploy/'

    # create directories
    sudo('mkdir -p %(target)s' % {
        'target' : target
    })
    
    sudo('chown %(user)s:%(group)s %(target)s' % {
        'user' : env.user,
        'group' : env.group,
        'target' : target
    }) 

    files = ['autodeploy.ini', 'autodeploy.py', 'autodeploy.sh', 'requirements.txt']
    for filename in files:
        targetpath = target + filename
        put(config_path + targetpath, targetpath, use_sudo=True)
        sudo('chown %(user)s:%(group)s %(target)s' % {
            'user' : env.user,
            'group' : env.group,
            'target' : targetpath
        })  

    sudo('chmod u+x ' + target + 'autodeploy.sh')                


def create_app():

    sudo('mkdir -p %(domain_path)s' % {
        'domain_path' : env.domain_path
    })

    sudo('mkdir -p %(releases_path)s' % {
        'releases_path' : env.releases_path
    })

    sudo('chown %(user)s:%(group)s %(domain_path)s' % {
        'domain_path' : env.domain_path,
        'user' : env.user,
        'group' : env.group
    })  

    sudo('chown %(user)s:%(group)s %(releases_path)s' % {
        'releases_path' : env.releases_path,
        'user' : env.user,
        'group' : env.group
    })  


def update_app_static(config_path, path):

    put(config_path + '/' + path, '%(domain_path)s' % {
        'domain_path' : env.domain_path
    }, use_sudo=True)

    sudo('chown -R %(user)s:%(group)s %(domain_path)s/%(path)s' % {
        'path' : path,
        'domain_path' : env.domain_path,
        'user' : env.user,
        'group' : env.group
    })  