import boto.ec2.elb
from velvet.cloudformation import stack

def enable_elb_crosszone(stack, resource_name):
	lb = stack.get_stack_resource(stack, resource_name)
	if lb:
		load_balancer_name = lb['PhysicalResourceId']
		print "*** Enable Cross-Zone Load Balancing on " + load_balancer_name
		elb = boto.ec2.elb.connect_to_region(region)
		if elb.modify_lb_attribute(load_balancer_name, 'CrossZoneLoadBalancing', 'true'):
			print "Enabled"
		else:
			print "Failed"
