import velvet.cloudformation as cf
import velvet.ec2 as ec2

# from cf import validate_stack, get_stack_autoscaling_group
# from velvet.ec2 import get_autoscaling_group_instance_ids, get_instances

from time import sleep

import datetime
import dateutil.parser

def recycle_instance(instance):
    if instance.state != 'running':
        return False
    print instance.tags['Name'] + " | " + instance.id + " | " + instance.public_dns_name
    instance.stop()
    instance.update()
    while instance.state == 'shutting-down':
        time.sleep(5)
        instance.update()
    print "Instance terminated"
    return True


def recycle_autoscale_instances(stack, resource_name):

	# make sure stack is active
    cf.validate_stack(stack)

    # get autoscaling group from the stack
    webrole_group = cf.get_stack_autoscaling_group(stack, resource_name)

    # get instance ids for the given autoscaling group
    instance_ids = ec2.get_autoscaling_group_instance_ids(webrole_group)
    if instance_ids is not None and len(instance_ids) > 0:

        # get all instances and terminate them
        print "Recycle instances: "
        instances = ec2.get_instances(instance_ids)
        for instance in instances:
            recycle_instance(instance)


def list_autoscaling_instances(stack, resource_name, ssh_key=None, ssh_user=None):

	# make sure stack is active
    cf.validate_stack(stack)

	# get ec2 instances for the given autoscaling group
    instances = cf.get_stack_autoscaling_group_instances(stack, resource_name)
    if instances is not None and len(instances) > 0:

    	# get the current time
        now = datetime.datetime.now(dateutil.tz.tzlocal()).replace(microsecond=0)

        # list details all active instances
        for i in instances:

        	# do not print terminated instances
            if i.state == 'terminated':
                continue

            # display relative runtime
            launch_time = dateutil.parser.parse(i.__dict__['launch_time'])
            launch_delta = now - launch_time

            # print status line
            print '*** %(state)s | %(name)s | %(instance_id)s | %(instance_type)s | Active for %(launch_delta)s'  % {
                'state' : i.state,
                'name' : i.__dict__['tags']['Name'],
                'instance_id' : i.__dict__['id'],
                'instance_type' : i.__dict__['instance_type'],
                'launch_delta' : launch_delta
            }

            # print SSH connection string
            if ssh_key is not None and ssh_user is not None:
                hostname = i.__dict__['public_dns_name']
                if hostname is not '':
                    print "  ssh -i %(ssh_key)s -l %(login)s %(host)s " % {
                        'ssh_key' : ssh_key,
                        'login' : ssh_user,
                        'host' : hostname,
                    }

    else:
        '*** No EC2 instances found in %(resource_name)s!' % {
            'resource_name' : resource_name
        }            