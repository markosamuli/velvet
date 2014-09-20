from fabric.api import env

import boto.ec2
from fabric.colors import red, green, yellow

import velvet.config
import velvet.cloudformation

from velvet.aws.config import region
from velvet.decorators import deprecated


class StackOutputValueError(Exception):
    pass

def get_security_group_from_resource(stack, resource_name):
    security_group_id = velvet.cloudformation.get_stack_output_value(stack, resource_name)
    if security_group_id is None:
        raise StackOutputValueError('Security group resource not found')
    return get_security_group(security_group_id)

@deprecated
def authorize_database_access_from_resouce(stack, resource_name, target_security_group):
    if authorize_database_access_from_resource(stack, resource_name, target_security_group):
        return True
    raise Exception('Failed to authorize database access')

def authorize_database_access_from_resource(stack, resource_name, target_security_group):

    try:
        source_sg = get_security_group_from_resource(stack, resource_name)
    except StackOutputValueError as e:
        print red("*** " + str(e))
        return False

    target_sg = get_security_group(target_security_group)

    if has_database_access_from_group(target_sg, source_sg):
        print yellow("*** Rule already exists")
        return True
    else:
        print green("*** Allow RDS access: " + str(source_sg.name) + " -> " + str(target_sg.name))
        target_sg.authorize('tcp', 3306, 3306, src_group=source_sg)
        return True

@deprecated
def revoke_database_access_from_resouce(stack, resource_name, target_security_group):
    if revoke_database_access_from_resource(stack, resource_name, target_security_group):
        return True
    raise Exception('Failed to authorize database access')

def revoke_database_access_from_resource(stack, resource_name, target_security_group):

    try:
        source_sg = get_security_group_from_resource(stack, resource_name)
    except StackOutputValueError as e:
        print red(str(e))
        return False

    target_sg = get_security_group(target_security_group)

    if has_database_access_from_group(target_sg, source_sg):
        print green("*** Revoke RDS access: " + str(source_sg.name) + " -> " + str(target_sg.name))
        target_sg.revoke('tcp', 3306, 3306, src_group=source_sg)
        return True
    else:
        print red("*** Database access rule does not exist")
        return False


def has_database_access_from_group(target_sg, source_sg):
    """
    Check if source group can access target group
    :type target_sg: boto.ec2.securitygroup.SecurityGroup
    :type source_sg: boto.ec2.securitygroup.SecurityGroup
    :rtype: bool
    """
    existing = []
    for rule in target_sg.rules:
        for grant in rule.grants:
            if not grant.cidr_ip:
                existing.append(str(grant))

    source_group = source_sg.id + "-" + source_sg.owner_id
    if source_sg.id + "-" + source_sg.owner_id in existing:
        return True

    return False


def get_security_group(security_group):
    """
    Find security group by name or id
    :type security_group: str
    :rtype: boto.ec2.securitygroup.SecurityGroup
    """
    ec2 = boto.ec2.connect_to_region(region)
    rs = ec2.get_all_security_groups()
    for sg in rs:
        if sg.name == security_group:
            return sg
        if sg.id == security_group:
            return sg
    return None

