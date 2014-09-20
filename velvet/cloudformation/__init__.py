from velvet.decorators import deprecated
from velvet.cloudformation import stack as cf_stack

# autoscale.py

@deprecated
def validate_stack(stack):
	return cf_stack.validate_stack(stack)

@deprecated
def get_stack_autoscaling_group(stack, resource_name):
	return cf_stack.get_stack_autoscaling_group(stack, resource_name)	

@deprecated
def get_stack_autoscaling_group_instances(stack, resource_name):
	return cf_stack.get_stack_autoscaling_group_instances(stack, resource_name)	

# ec2.py

@deprecated
def get_stack_resource(stack, name):
	return cf_stack.get_stack_resource(stack, name)

# route53.py, security.py

@deprecated
def get_stack_output_value(stack, key):
	return cf_stack.get_stack_output_value(stack, key)	

# tasks/stack.py

@deprecated
def provision_stack(stack_name, environment, project):
	return cf_stack.provision_stack(stack_name, environment, project)	

@deprecated
def delete_stack(stack_name, environment, project):
	return cf_stack.delete_stack(stack_name, environment, project)

@deprecated
def get_stack(stack_id):
    return cf_stack.get_stack(stack_id)