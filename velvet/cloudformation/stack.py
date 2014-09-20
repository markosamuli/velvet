import boto.cloudformation

from boto.cloudformation.stack import Stack
import re

from velvet.decorators import deprecated

import velvet.ec2
from velvet.aws.config import region

import boto.exception

# import logging
# logging.basicConfig(level=logging.INFO)

from fabric.colors import red, green, yellow

from time import sleep
from datetime import datetime

STACK_COMPLETE_STATUSES = [
    # Successful creation of one or more stacks.
    'CREATE_COMPLETE',
    # Successful update of one or more stacks.
    'UPDATE_COMPLETE',
    # Successful return of one or more stacks to a previous working state after a failed stack update.
    'UPDATE_ROLLBACK_COMPLETE',
    # Ongoing removal of new resources for one or more stacks after a failed stack update. In this state, the stack has been rolled back to its previous working state and is usable, but AWS CloudFormation is still deleting any new resources it created during the stack update.,
    # 'UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS',
    # Ongoing removal of old resources for one or more stacks after a successful stack update. For stack updates that require resources to be replaced, AWS CloudFormation creates the new resources first and then deletes the old resources to help reduce any interruptions with your stack. In this state, the stack has been updated and is, usable, but AWS CloudFormation is still deleting the old resources.
    'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS'
]

class CloudFormationResult(object):

    def __init__(self):
        self.failed = None
        self.succeeded = None

    def __nonzero__(self):
        return self.succeeded and not self.failed

class StackNotReadyException(Exception):
    pass

class ValidationErrorException(Exception):
    pass

def get_stack(stack_id):
    """
    Find stack with the given name or id
    :type stack_id: str
    :rtype: boto.cloudformation.stack.Stack
    """
    cf = boto.cloudformation.connect_to_region(region)

    stacks = cf.describe_stacks()
    for stack in stacks:
        if stack.stack_name == stack_id:
            return stack
        if stack.stack_id == stack_id:
            return stack

    # no stacks found matching the name or id
    return None


def get_stack_resource(stack, name):
    """
    :type stack: boto.cloudformation.stack.Stack
    :type name: str
    """
    resource = stack.describe_resource(name)
    return resource['DescribeStackResourceResponse']['DescribeStackResourceResult']['StackResourceDetail']


def validate_stack(stack):
    """
    :type stack: boto.cloudformation.stack.Stack
    """

    if not isinstance(stack, Stack):
        raise ValueError("Stack must be instance of boto.cloudformation.stack.Stack")

    if stack.stack_status in STACK_COMPLETE_STATUSES:
        return True

    raise StackNotReadyException("Stack %(stack_name)s provisioning is not complete - stack_status: %(stack_status)s" % {
        'stack_name': stack.stack_name,
        'stack_status': stack.stack_status
    })


def get_stack_autoscaling_group(stack, resource_name):
    resource = get_stack_resource(stack, resource_name)
    return velvet.ec2.get_autoscaling_group(resource['PhysicalResourceId'])


def get_stack_autoscaling_group_instances(stack, resource_name):

    validate_stack(stack)

    as_group = get_stack_autoscaling_group(stack, resource_name)

    instance_ids = velvet.ec2.get_autoscaling_group_instance_ids(as_group)
    if instance_ids is not None and len(instance_ids) > 0:
        return velvet.ec2.get_instances(instance_ids)

    return None


def get_stack_autoscaling_group_hosts(stack, resource_name):

    hosts = []
    instances = get_stack_autoscaling_group_instances(stack, resource_name)
    if instances is not None and len(instances) > 0:
        for i in instances:
            hostname = i.__dict__['public_dns_name']
            if hostname is not '':
                hosts.append(hostname)

    return hosts


def get_stack_static_hostnames(stack, match):

    hosts = []

    validate_stack(stack)

    for output in stack.outputs:
        m = re.match(match, output.key)
        if m:
            hosts.append(output.value)
    return hosts


def get_stack_outputs(stack):

    validate_stack(stack)

    outputs = {}
    for output in stack.outputs:
        outputs[output.key] = output.value
    return outputs


def get_stack_output_value(stack, key):

    validate_stack(stack)

    for output in stack.outputs:
        if key == output.key:
            return output.value

    return None


def _find_stack(stack_id, connection=None, region=None):
    """
    :type stack_id: str
    :type connection: boto.cloudformation.connection.CloudFormationConnection
    :rtype: boto.cloudformation.stack.Stack
    """

    if connection is None:
        connection = boto.cloudformation.connect_to_region(region)

    stacks = None
    try:
        stacks = connection.describe_stacks(stack_id)
        if len(stacks) == 1:
            return stacks[0]
    except boto.exception.BotoServerError as e:
        pass
    return None


def delete_stack(stack_name, delete_failed_stacks=False):
    """
    :param stack_name: Stack name or id to delete
    """

    print ""
    cf = boto.cloudformation.connect_to_region(region)

    def find_stack(stack_name):
        """
        :type stack_name: str
        :rtype: boto.cloudformation.stack.Stack
        """
        return _find_stack(stack_name, connection=cf)

    print "Stack Name:        " + stack_name

    stack = find_stack(stack_name)
    if stack:

        print ""

        status = False

        # Allow deletion of failed stacks?
        if delete_failed_stacks and stack.stack_status in ['CREATE_FAILED', 'DELETE_FAILED']:
            print '*** Delete failed stack %(stack_name)s' % { 'stack_name': stack_name }
            status = cf.delete_stack(stack_name)

        else:

            # Delete only completed stacks
            try:
                validate_stack(stack)
            except StackNotReadyException as e:
                print red("*** " + str(e))
                return False

            print '*** Delete existing stack %(stack_name)s' % { 'stack_name': stack_name }
            status = cf.delete_stack(stack_name)

        events = StackEventStream(stack, cf)

        stack = find_stack(stack_name)
        if not status:
            print '*** Stack deleting failed - stack status: ' + red(stack.stack_status)
            return False

        _print_events(events.new_events())

        # Update stack status while deleting is still in progress
        while stack.stack_status in ['DELETE_IN_PROGRESS']:
            sleep(5)
            stack = find_stack(stack.stack_id)
            _print_events(events.new_events())

        if stack.stack_status == 'DELETE_COMPLETE':
            print '*** Stack deleting complete - stack status: ' + green(stack.stack_status)
            return True
        else:
            print '*** Stack deleting failed - stack status: ' + red(stack.stack_status)
            return False

    else:

        print ""

        print red('*** Stack not found')
        return False


@deprecated
def provision_stack(stack_name, environment, project):

    # default template file path
    template_file = "provisioning/%(environment)s.json" % { 'environment': environment }

    # pass project metadata into the stack as tags
    tags = {}
    tags['Environment'] = environment
    tags['Project'] = project

    return provision_stack_with_template(stack_name, template_file, tags=tags)

class StackEventStream(object):

    def __init__(self, stack, connection=None):
        """
        :type stack: boto.cloudformation.stack.Stack
        :type connection: boto.cloudformation.connection.CloudFormationConnection
        """
        self.connection = connection
        self.stack = stack
        self.events = []
        self.cursor = 0
        self.start_time = datetime.now()

    def new_events(self):
        def filter_old_events(event):
            return True
            # return event.timestamp > self.start_time
        self.events = self.stack.describe_events()
        new = filter(filter_old_events, self.events[:len(self.events) - self.cursor])
        self.cursor = len(self.events)
        return new


def _print_events(events):
    in_progress = re.compile('.*_IN_PROGRESS$')
    complete = re.compile('.*_COMPLETE$')
    failed = re.compile('.*_FAILED$')
    if len(events) > 0:
        for e in reversed(events):
            timestamp = e.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            resource = e.resource_type + " " + e.logical_resource_id

            if in_progress.match(e.resource_status):
                status = yellow(e.resource_status)
            elif failed.match(e.resource_status):
                status = red(e.resource_status)
            elif complete.match(e.resource_status):
                status = green(e.resource_status)
            else:
                status = e.resource_status

            if e.resource_status_reason is not None:
                status += " (" + e.resource_status_reason + ")"

            print timestamp + " - " + resource + " " + status



def validate_template(template, connection=None):

    if connection is None:
        connection = boto.cloudformation.connect_to_region(region)

    try:
        return connection.validate_template(template)
    except boto.exception.BotoServerError as e:

        if not e.error_code == 'ValidationError':
            # unknown error occurred, throw it back
            raise

        raise ValidationErrorException(e.message)


def provision_stack_with_template(stack_name, template_file, tags=None, disable_rollback=False, parameters=None, return_stack=False):
    """
    Provision a new CloudFormation stack with the given name and template file.
    :type stack_name: str
    :type template_file: str
    :type tags: dict
    :type disable_rollback: bool
    """

    print ""
    cf = boto.cloudformation.connect_to_region(region)

    def find_stack(stack_name):
        """
        :type stack_name: str
        :rtype: boto.cloudformation.stack.Stack
        """
        return _find_stack(stack_name, connection=cf)

    # read the template from the file
    template = None
    with open(template_file) as f:
        template = f.read()

    try:
        valid = validate_template(template, connection=cf)
    except ValidationErrorException as e:
        print red("*** Template validation failed: " + str(e))
        result = CloudFormationResult()
        result.failed = True
        result.succeeded = False
        result.error = str(e)
        return result

    print "Stack Name:        " + stack_name
    print "Stack Description: " + valid.description
    print ""

    stack = find_stack(stack_name)
    if stack:

        try:
            validate_stack(stack)
        except StackNotReadyException as e:
            print red("*** " + str(e))
            result = CloudFormationResult()
            result.failed = True
            result.succeeded = False
            result.error = str(e)
            return result

        print "Stack Status: " + stack.stack_status

        print '*** Updating existing stack %(stack_name)s' % { 'stack_name': stack_name }
        try:
            stack_id = cf.update_stack(stack_name, template_body=template, tags=tags, disable_rollback=disable_rollback, parameters=parameters)
        except boto.exception.BotoServerError as e:
            if e.message == "No updates are to be performed.":
                print yellow("*** Update failed: " + e.message)

                if return_stack:
                    return stack

                result = CloudFormationResult()
                result.failed = False
                result.succeeded = not result.failed
                result.stack = stack
                return result

            else:
                print red("*** Update failed: " + e.message)
                result = CloudFormationResult()
                result.failed = True
                result.succeeded = not result.failed
                result.error = str(e.message)
                return result


    else:
        print '*** Creating new stack %(stack_name)s' % { 'stack_name': stack_name }
        stack_id = cf.create_stack(stack_name, template_body=template, tags=tags, disable_rollback=disable_rollback, parameters=parameters)

    # These are the statuses for successful builds
    desired_stack_statuses = ["CREATE_COMPLETE",
                              "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
                              "UPDATE_COMPLETE"]

    if not stack_id:
        # Failed to create new stack
        result = CloudFormationResult()
        result.failed = True
        result.succeeded = not result.failed
        result.error = "Failed to create new stack"
        return result

    stack = find_stack(stack_id)
    events = StackEventStream(stack, cf)

    _print_events(events.new_events())

    # Update stack status while create or update is still in progress
    while stack.stack_status in ['CREATE_IN_PROGRESS', 'UPDATE_IN_PROGRESS']:
        sleep(5)
        stack = find_stack(stack_id)
        _print_events(events.new_events())

    if stack.stack_status in desired_stack_statuses:
        print green('*** Stack provisioning complete - stack status: ' + stack.stack_status)

        if return_stack:
            return stack

        result = CloudFormationResult()
        result.failed = False
        result.succeeded = not result.failed
        result.stack = stack
        return result

    else:

        print red('*** Stack provisioning failed - stack status: ' + stack.stack_status)
        result = CloudFormationResult()
        result.failed = True
        result.succeeded = not result.failed
        result.error = "Stack provisioning failed"
        return result
