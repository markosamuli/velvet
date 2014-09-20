from fabric.api import env

import velvet.cloudformation.stack as cf_stack

class CloudFormationResult(object):

    def __init__(self):
        self.failed = None
        self.succeeded = None

    def __nonzero__(self):
        return self.succeeded and not self.failed

def provision_stack():
    """Task to provision a new CloudFormation stack"""

    if 'stack_id' not in env:
        raise Exception('Stack name not defined')

    if 'environment' not in env:
        raise Exception('Environment not defined')

    if 'app_name' not in env:
        raise Exception('Application name not defined')

    if 'cloudformation_path' not in env:
        raise Exception('CloudFormation template path not defined')

    # cloudformation stack name
    stack_name = env.stack_id

     # default template file path
    template_file = "%(path)s/%(environment)s.json" % {
        'path': env.cloudformation_path,
        'environment': env.environment,
    }

    # pass project metadata into the stack as tags
    tags = {}
    tags['Environment'] = env.environment
    tags['Project'] = env.app_name

    disable_rollback = False
    if 'disable_rollback' in env:
        disable_rollback = env.disable_rollback

    return cf_stack.provision_stack_with_template(stack_name, template_file, tags=tags,
                                        disable_rollback=disable_rollback)


def provision_stacks():
    """Task to provision multiple new CloudFormation stacks"""

    if 'stacks' not in env:
        raise Exception('Stacks configuration missing not defined')

    if 'environment' not in env:
        raise Exception('Environment not defined')

    if 'app_name' not in env:
        raise Exception('Application name not defined')

    if 'cloudformation_path' not in env:
        raise Exception('CloudFormation template path not defined')

    # validate all stacks first
    stacks = []
    for stack in env.stacks:

         if 'name' not in stack:
             raise Exception('Stack name not defined')

         if 'template' not in stack:
             raise Exception('Stack template name not defined')

         stacks.append(stack)

    if len(stacks) == 0:
        return False

    stack_parameters = {}

    # cloudformation stack name
    for stack in stacks:

        print "--> Create stack %(name)s" % stack

        template_file = "%(path)s/%(environment)s-%(template)s.json" % {
           'path': env.cloudformation_path,
           'environment': env.environment,
           'template': stack['template'],
        }

        # pass project metadata into the stack as tags
        tags = {}
        tags['Environment'] = env.environment
        tags['Project'] = env.app_name

        disable_rollback = False
        if 'disable_rollback' in env:
            disable_rollback = env.disable_rollback

        parameters = []
        for key, value in stack_parameters.iteritems():
            parameters.append((key, value))

        if 'parameters' in stack:
            for key, value in stack['parameters'].iteritems():
                parameters.append((key, value))

        if 'prompt' in stack:
            for key in stack['prompt']:
                value = raw_input('{0}: '.format(key))
                if value:
                    parameters.append((key, value))

        # print "Parameters:"
        # for item in parameters:
        #     print item[0] + ': ' + item[1]

        result = cf_stack.provision_stack_with_template(stack['name'], template_file, tags=tags,
                                           disable_rollback=disable_rollback,
                                           parameters=parameters)

        if result.failed:
            result = CloudFormationResult()
            result.failed = True
            result.succeeded = not result.failed
            return result

        desired_stack_statuses = [
               "CREATE_COMPLETE",
               "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS",
               "UPDATE_COMPLETE"
        ]

        if result.stack.stack_status in desired_stack_statuses:
            # append output values from the stack to pass on to the next stack
            if 'outputs' in stack:
                stack_outputs = cf_stack.get_stack_outputs(result.stack)
                for key in stack['outputs']:
                    stack_parameters[key] = stack_outputs[key]

        else:
            result = CloudFormationResult()
            result.failed = True
            result.succeeded = not result.failed
            result.error = 'Unexpected stack final status'
            return result

    result = CloudFormationResult()
    result.failed = False
    result.succeeded = not result.failed
    return result


def delete_stack(stack_id=None):
    """Delete a stack"""

    if stack_id is None:
        if 'stack_id' not in env:
            raise Exception('Stack name not defined')
        stack_id = env.stack_id

    delete_failed_stacks = None
    if 'delete_failed_stacks' in env:
        delete_failed_stacks = env.delete_failed_stacks

    return cf_stack.delete_stack(stack_id,
                       delete_failed_stacks=delete_failed_stacks)


def delete_stacks():
    """Delete all stacks"""

    if 'stacks' not in env:
        raise Exception('Stacks configuration missing not defined')

    stacks = env.stacks

    if len(stacks) == 0:
        return False

    # delete stacks in reversed order
    for stack in reversed(stacks):
        success = delete_stack(stack.stack_id)
        if not success:
            result = CloudFormationResult()
            result.failed = True
            result.succeeded = not result.failed
            result.error = 'Failed to delete stack ' + stack.stack_id
            return result

    result = CloudFormationResult()
    result.failed = False
    result.succeeded = not result.failed
    return result
