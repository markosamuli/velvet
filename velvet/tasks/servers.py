from fabric.api import env, sudo, put, run, settings
import fabric.contrib.files


def get_instance_type():
    return run('curl http://169.254.169.254/latest/meta-data/instance-type')


def reload_phpfpm():
    """ Reload PHP-FPM config """
    if not fabric.contrib.files.exists('/etc/php5/fpm', use_sudo=True):
        print "*** PHP-FPM not installed, skip reload"
        return
    sudo("service php5-fpm reload")    


def reload_nginx():
    """ Reload nginx config """
    if not fabric.contrib.files.exists('/etc/nginx', use_sudo=True):
        print "*** nginx not installed, skip reload"
        return
    sudo("service nginx reload")    


def restart_nginx():
    """ Restart nginx server """
    if not fabric.contrib.files.exists('/etc/nginx', use_sudo=True):
        print "*** nginx not installed, skip restart"
        return
    sudo("service nginx restart")    


def clear_nginx_cache():
    sudo("find /var/run/nginx-cache -type f -delete")    


def upload_nginx_config(config_path):

    path = '/etc/nginx/'
    files = ['nginx.conf']
    sites = []
    for f in glob.glob(config_path + path + 'sites-available/*'):
        site = os.path.basename(f)
        sites.append(site)
        files.append('sites-available/' + site) 

    for filename in files:
        fullpath = path + filename
        put(config_path + fullpath, fullpath, use_sudo=True)
        sudo('chown root:root ' + fullpath)

    sudo('[ -e /etc/nginx/sites-enabled/default ] && rm /etc/nginx/sites-enabled/default || exit 0')
    for site in sites:
        symlink('/etc/nginx/sites-available/' + site, '/etc/nginx/sites-enabled/' + site, use_sudo=True)


def set_phpfpm_instance_config():   

    if not fabric.contrib.files.exists('/etc/php5/fpm', use_sudo=True):
        print "*** PHP-FPM not installed, skip configuration"
        return       

    print "*** Update PHP-FPM config"
    instance_type = get_instance_type()
    if instance_type:
        print "*** Instance type: " + instance_type
        params = {
            "config_root" : '/etc/php5/fpm/pool.d',
            "instance_type" : instance_type
        }
        if fabric.contrib.files.exists("%(config_root)s/pm.conf-%(instance_type)s" % params, use_sudo=True):
            print "*** Use instance type specific PHP-FPM config"
            sudo("ln -nfs %(config_root)s/pm.conf-%(instance_type)s %(config_root)s/pm.conf" % params)
        else:
            print "*** Use default PHP-FPM config"
            sudo("ln -nfs %(config_root)s/pm.conf-default %(config_root)s/pm.conf" % params)

    else:
        raise Exception('Unknown instance type')  


def upload_phpfpm_config(config_path):

    path = '/etc/php5/fpm/'
    files = ['php.ini', 'php-fpm.conf']
    for filename in files:
        fullpath = path + filename
        put(config_path + fullpath, fullpath, use_sudo=True)
        sudo('chown root:root ' + fullpath)

    path = '/etc/php5/fpm/pool.d/'
    files = ['errors.conf', 'ping.conf', 'socket.conf', 'status.conf', 'www.conf', 'socket.conf']
    for filename in files:
        fullpath = path + filename
        put(config_path + fullpath, fullpath, use_sudo=True)
        sudo('chown root:root ' + fullpath)    

    for sourcefile in glob.glob(config_path + path + 'pm.conf-*'):
        fullpath = sourcefile.replace(config_path, '')
        put(sourcefile, fullpath, use_sudo=True)
        sudo('chown root:root ' + fullpath)            