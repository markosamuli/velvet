__author__ = 'marko.kirves'

from fabric.colors import red, yellow, green

import velvet.security

def authorize_rds_security_groups(stack, config):
    """
    :type stack: boto.cloudformation.stack.Stack
    :type config: dict
    :rtype: bool
    """

    if 'security_groups' not in config:
        print red('*** Section "security" missing in the config file')
        return False

    if 'rds_security_group' not in config['security_groups']:
        print red('*** RDS security group missing')
        return False

    rds_security_group = config['security_groups']['rds_security_group']

    if 'authorized_db_resources' not in config['security_groups']:
        print yellow('*** No CloudFormation resources (security groups) configured for RDS access')
        return False

    errors = False

    for group_name in config['security_groups']['authorized_db_resources']:
        msg = '*** Authorize ' + group_name + ' -> ' + rds_security_group
        status = velvet.security.authorize_database_access_from_resource(
            stack,
            group_name,
            rds_security_group
        )
        if status:
            print msg + ' [' + green('OK') + ']'
        else:
            print msg + ' [' + red('failed') + ']'
            errors = True

    if errors:
        print red('*** Failed to authorize one or more rules')
        return False

    return True


def revoke_rds_security_groups(stack, config):
    """
    :type stack: boto.cloudformation.stack.Stack
    :type config: dict
    :rtype: bool
    """

    if 'security_groups' not in config:
        print red('*** Section "security" missing in the config file')
        return False

    if 'rds_security_group' not in config['security_groups']:
        print red('*** RDS security group missing')
        return False

    rds_security_group = config['security_groups']['rds_security_group']

    if 'authorized_db_resources' not in config['security_groups']:
        print yellow('*** No CloudFormation resources (security groups) configured for RDS access')
        return False

    errors = False

    for group_name in config['security_groups']['authorized_db_resources']:
        msg = '*** Revoke ' + group_name + ' -> ' + rds_security_group
        status = velvet.security.revoke_database_access_from_resource(
            stack,
            group_name,
            rds_security_group
        )
        if status:
            print msg + ' [' + green('OK') + ']'
        else:
            print msg + ' [' + red('failed') + ']'
            errors = True

    if errors:
        print red('*** Failed to revoke one or more rules')
        return False

    return True