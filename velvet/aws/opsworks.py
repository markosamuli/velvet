import boto.ec2

from boto.ec2.connection import EC2Connection
from fabric.colors import red, green, yellow
from velvet.aws.config import region, with_opsworks_defaults
import velvet.security

from fabric.api import env

class OpsWorks(object):

    def __init__(self, connection=None, region=None):
        """
        :type connection: boto.ec2.connection.EC2Connection
        """
        self.connection = connection
        self.region = region
        self.src_groups = {}

        # create new connection if needed
        if self.connection is None:
            # only connect if region is defined
            if self.region:
                self.connection = boto.ec2.connect_to_region(self.region)

    def get_default_opsworks_security_groups(self):
        """
        Return default OpsWorks security groups
        :rtype: list of boto.ec2.securitygroup.SecurityGroup
        """

        def filter_opsworks(sg):
            """
            :type sg: boto.ec2.securitygroup.SecurityGroup
            :rtype: bool
            """
            return sg.name.startswith('AWS-OpsWorks-')

        ec2 = boto.ec2.connect_to_region(region)
        return filter(filter_opsworks, ec2.get_all_security_groups())

    def get_security_group(self, group_id, cached=True):
        """
        :type group_id: str
        :rtype: list of boto.ec2.securitygroup.SecurityGroup
        """
        if cached and group_id in self.src_groups:
            src_group = self.src_groups[group_id]
        else:
            src_group = velvet.security.get_security_group(group_id)
            self.src_groups[group_id] = src_group
        return src_group


@with_opsworks_defaults
def is_opsworks_enabled():

    if 'opsworks' not in env:
        return False

    if env['opsworks'] is False:
        return False

    return True


class OpsWorksResult(object):

    def __init__(self):
        self.failed = None
        self.succeeded = None

    def __nonzero__(self):
        return self.succeeded and not self.failed


def cleanup_default_security_groups(dry_run=False):
    """Cleanup default OpsWorks security groups"""

    print "--> Cleanup default OpsWorks security groups" + \
          (" (this is just a dry run...)" if dry_run else "")

    failed = False
    opsworks = OpsWorks(region=region)
    for sg in opsworks.get_default_opsworks_security_groups():

        if len(sg.rules) == 0:
            print "+ Skip security group: " + sg.name
            continue

        print ""
        print "+ Cleanup security group: " + sg.name

        while len(sg.rules) > 0:

            # delete the rules until all are removed
            for rule in sg.rules:
                for grant in rule.grants:
                    status = None
                    if grant.cidr_ip is None:
                        # we have a security group ingress
                        src_group = opsworks.get_security_group(grant.group_id)
                        print ("--> Revoke: %(group_id)s (%(group_name)s) -> %(ip_protocol)s(%(from_port)s-%(to_port)s)" % {
                            'ip_protocol' : rule.ip_protocol,
                            'from_port' : rule.from_port,
                            'to_port' : rule.to_port,
                            'group_id' : src_group.id,
                            'group_name' : src_group.name
                        }),
                        if not dry_run:
                            status = sg.revoke(ip_protocol=rule.ip_protocol,
                                      from_port=rule.from_port, to_port=rule.to_port,
                                      src_group=src_group,
                                      dry_run=dry_run)
                            print (green("[OK]") if status else red("[fail]"))
                            if status is False:
                                failed = True
                        else:
                            print yellow("[dry-run]")

                    else:
                        # we have ip address range
                        if grant.cidr_ip == '0.0.0.0/0':
                            print ("--> Revoke: %(cidr_ip)s -> %(ip_protocol)s(%(from_port)s-%(to_port)s)" % {
                                'ip_protocol' : rule.ip_protocol,
                                'from_port' : rule.from_port,
                                'to_port' : rule.to_port,
                                'cidr_ip' : grant.cidr_ip
                            }),
                            if not dry_run:
                                status = sg.revoke(ip_protocol=rule.ip_protocol,
                                          from_port=rule.from_port, to_port=rule.to_port,
                                          cidr_ip=grant.cidr_ip)
                                print (green("[OK]") if status else red("[fail]"))
                                if status is False:
                                    failed = True
                            else:
                                print yellow("[dry-run]")
                        else:
                            print ("--> Keep: %(cidr_ip)s -> %(ip_protocol)s(%(from_port)s-%(to_port)s)" % {
                                'ip_protocol' : rule.ip_protocol,
                                'from_port' : rule.from_port,
                                'to_port' : rule.to_port,
                                'cidr_ip' : grant.cidr_ip
                            })

    result = OpsWorksResult()
    result.failed = failed
    result.succeeded = not result.failed
    return result