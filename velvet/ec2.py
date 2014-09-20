import boto.ec2
import boto.ec2.autoscale
import boto.ec2.elb

from velvet.aws.config import region

def get_autoscaling_group(group_id):
    autoscale = boto.ec2.autoscale.connect_to_region(region)
    groups = autoscale.get_all_groups()
    for group in groups:
        if group.name == group_id:
            return group
    return None


def get_autoscaling_group_instance_ids(group):
    return [i.instance_id for i in group.instances]


def get_instances(instance_ids):
    ec2 = boto.ec2.connect_to_region(region)
    return ec2.get_only_instances(instance_ids)

# Deprecated methods for backwards compatibility

from velvet.decorators import deprecated

@deprecated
def enable_elb_crosszone(stack, resource_name):
	import velvet.elb
	return velvet.elb.enable_elb_crosszone(stack, resource_name)
