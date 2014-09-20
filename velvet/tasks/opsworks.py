from time import sleep
from fabric.api import env
from fabric.colors import red, yellow, green

import velvet.aws.opsworks
import velvet.config
import velvet.tasks.stack
import velvet.cloudformation
import velvet.tasks.security

from velvet.aws.config import region

from velvet.tasks.security import authorize_rds_security_groups as _authorize_rds_security_groups
from velvet.tasks.security import revoke_rds_security_groups as _revoke_rds_security_groups

import boto.opsworks
import boto.opsworks.layer1

class OpsWorksResult(object):

    def __init__(self):
        self.failed = None
        self.succeeded = None

    def __nonzero__(self):
        return self.succeeded and not self.failed

class OpsWorksDeployment(object):

    def __init__(self, connection=None):
        """
        :type connection: boto.opsworks.layer1.OpsWorksConnection
        """
        self.connection = connection

        # create new connection if needed
        if self.connection is None:
            self.connection = boto.opsworks.layer1.OpsWorksConnection()


    def get_stack(self, stack_id):
        stacks = self.connection.describe_stacks(stack_ids=[stack_id])
        if len(stacks['Stacks']) == 1:
            return stacks['Stacks'][0]
        return None

    def get_layer(self, layer_id):
        layers = self.connection.describe_layers(layer_ids=[layer_id])
        if len(layers['Layers']) == 1:
            return layers['Layers'][0]
        return None

    def get_app(self, app_id):
        apps = self.connection.describe_apps(app_ids=[app_id])
        if len(apps['Apps']) == 1:
            return apps['Apps'][0]
        return None

    def get_layer_instances(self, layer_id):
        instances = self.connection.describe_instances(layer_id=layer_id)
        return instances

    def deploy_app(self, stack_id, app_id, instance_ids=None, comment=None):
        deployment = self.connection.create_deployment(stack_id, command={
            'Name' : 'deploy'
        }, app_id=app_id, comment=comment, instance_ids=instance_ids)
        return deployment

    def get_app_deployments(self, app_id):
        """Get all deployments for this application"""

        def _filter(deployment):

            # skip completed deployments
            if deployment['Status'] == "successful":
                return False
            if deployment['Status'] == "failed":
                return False

            # filter out non-app deployments
            if deployment['Command']['Name'] == "deploy":
                return True

            if deployment['Command']['Name'] == "update_custom_cookbooks":
                return True

            return False

        # fetch all deployments for this application
        response = self.connection.describe_deployments(app_id=app_id)
        return filter(_filter, response['Deployments'])

    def get_incomplete_deployments(self, deployments):
        """Get waiting and failed deployments"""

        deployment_ids = [deployment['DeploymentId'] for deployment in deployments]

        def _filter(deployment):
            # skip completed deployments
            if deployment['Status'] == "successful":
                return False
            if deployment['Status'] == "failed":
                return False
            return True

        response = self.connection.describe_deployments(deployment_ids=deployment_ids)
        return filter(_filter,  response['Deployments'])


    def get_deployments(self, deployments):
        """Get waiting and failed deployments"""
        deployment_ids = [deployment['DeploymentId'] for deployment in deployments]
        response = self.connection.describe_deployments(deployment_ids=deployment_ids)
        return response['Deployments']

    def update_cookbooks(self, stack_id, app_id, instance_ids=None, comment=None):
        deployment = self.connection.create_deployment(stack_id, command={
            'Name' : 'update_custom_cookbooks'
        }, app_id=app_id, comment=comment, instance_ids=instance_ids)
        return deployment


def setup_security_groups():
    """
    Setup security groups that can't be created by the CloudFormation scripts
    """

    # Cleanup default OpsWorks security groups
    velvet.aws.opsworks.cleanup_default_security_groups(dry_run=False)

    config = velvet.config.environment_config
    if 'security_groups' not in config:
        print yellow('*** No security groups configuration found')
        result = OpsWorksResult()
        result.succeeded = True
        result.failed = not result.succeeded
        return result

    # Allow application to access the existing RDS instance
    stack = velvet.cloudformation.get_stack(env.stack_id)
    if not stack:
        print red("*** Stack %(stack_id)s not found" % { 'stack_id' : env.stack_id })
        result = OpsWorksResult()
        result.succeeded = False
        result.failed = not result.succeeded
        return result

    authorized = _authorize_rds_security_groups(stack, config)

    result = OpsWorksResult()
    result.succeeded = authorized
    result.failed = not result.succeeded
    return result


def cleanup_security_groups():
    """
    Cleanup security groups set up by the provision scripts
    """

    config = velvet.config.environment_config
    if 'security_groups' not in config:
        print yellow('*** No security groups configuration found')
        result = OpsWorksResult()
        result.succeeded = True
        result.failed = not result.succeeded
        return result

    # Deny application from accessing the existing RDS instance
    stack = velvet.cloudformation.get_stack(env.stack_id)
    if not stack:
        print red("*** Stack %(stack_id)s not found" % { 'stack_id' : env.stack_id })
        result = OpsWorksResult()
        result.succeeded = False
        result.failed = not result.succeeded
        return result

    revoked = _revoke_rds_security_groups(stack, config)

    result = OpsWorksResult()
    result.succeeded = revoked
    result.failed = not result.succeeded
    return result


def _find_opsworks_stack():

    if not 'stacks' in env:
        raise Exception("OpsWorks deployment requires stack configuration option to be defined")

    if not 'opsworks' in env:
        raise Exception("OpsWorks configuration missing")

    opsworks = env['opsworks']
    if opsworks is False:
        raise Exception("OpsWorks disabled")

    if 'stack' not in opsworks:
        raise Exception("OpsWorks stack output key missing")

    if 'layer' not in opsworks:
        raise Exception("OpsWorks layer output key missing")

    if 'app' not in opsworks:
        raise Exception("OpsWorks app output key missing")

    for item in env['stacks']:
        if 'role' in item and item['role'] == 'opsworks':
            cf_stack = velvet.cloudformation.stack.get_stack(item['name'])
            if cf_stack:
                outputs = velvet.cloudformation.stack.get_stack_outputs(cf_stack)
                return {
                    'cloudformation_id' : cf_stack.stack_id,
                    'stack_id' : outputs[opsworks['stack']],
                    'layer_id' : outputs[opsworks['layer']],
                    'app_id' : outputs[opsworks['app']],
                }

    return None


def app_deploy(comment=None):

    config = _find_opsworks_stack()

    print "--> Deploy OpsWorks application"

    print "CloudFormation Stack: %(cloudformation_id)s" % config

    deploy = OpsWorksDeployment()

    # find stack matching the requested environment
    stack = deploy.get_stack(config['stack_id'])
    print "OpsWorks Stack: %(Name)s" % stack

    # find application server layer
    layer = deploy.get_layer(config['layer_id'])
    print "OpsWorks Layer: %(Name)s" % layer

    # find the application
    app = deploy.get_app(config['app_id'])
    print "OpsWorks Application: %(Name)s" % app

    instance_ids = []
    instances = deploy.get_layer_instances(layer['LayerId'])
    for instance in instances['Instances']:
        if instance['Status'] != "online":
            continue
        instance_ids.append(instance['InstanceId'])
        if 'ElasticIp' in instance:
            print "Instance: %(Hostname)s | %(InstanceType)s | %(ElasticIp)s | %(Status)s" % instance    
        else:
            print "Instance: %(Hostname)s | %(InstanceType)s | %(PublicIp)s | %(Status)s" % instance


    if len(instance_ids) == 0:
        raise Exception('No instances online')

    deployment = deploy.deploy_app(stack['StackId'], app['AppId'],
                                   instance_ids=instance_ids, comment=comment)
    print "--> Deployment: %(DeploymentId)s" % deployment

    result = OpsWorksResult()
    result.failed = False
    result.succeeded = not result.failed
    result.deployment = deployment
    return result


def cookbooks_deploy(comment=None):

    config = _find_opsworks_stack()

    print "--> Deploy OpsWorks cookbooks"

    print "CloudFormation Stack: %(cloudformation_id)s" % config

    deploy = OpsWorksDeployment()

    # find stack matching the requested environment
    stack = deploy.get_stack(config['stack_id'])
    print "OpsWorks Stack: %(Name)s" % stack

    # find application server layer
    layer = deploy.get_layer(config['layer_id'])
    print "OpsWorks Layer: %(Name)s" % layer

    # find the application
    app = deploy.get_app(config['app_id'])
    print "OpsWorks Application: %(Name)s" % app

    instance_ids = []
    instances = deploy.get_layer_instances(layer['LayerId'])
    for instance in instances['Instances']:
        if instance['Status'] != "online":
            continue
        instance_ids.append(instance['InstanceId'])
        if 'ElasticIp' in instance:
            print "Instance: %(Hostname)s | %(InstanceType)s | %(ElasticIp)s | %(Status)s" % instance    
        else:
            print "Instance: %(Hostname)s | %(InstanceType)s | %(PublicIp)s | %(Status)s" % instance


    if len(instance_ids) == 0:
        raise Exception('No instances online')

    deployment = deploy.update_cookbooks(stack['StackId'], app['AppId'],
                                         instance_ids=instance_ids, comment=comment)
    print "--> Deployment: %(DeploymentId)s" % deployment

    result = OpsWorksResult()
    result.failed = False
    result.succeeded = not result.failed
    result.deployment = deployment
    return result


def app_deploy_ready():

    config = _find_opsworks_stack()

    deploy = OpsWorksDeployment()

    # find stack matching the requested environment
    stack = deploy.get_stack(config['stack_id'])
    print "OpsWorks Stack: %(Name)s" % stack

    # find the application
    app = deploy.get_app(config['app_id'])
    print "OpsWorks Application: %(Name)s" % app

    print "--> Checking for incomplete application deployments..."
    deployments = deploy.get_app_deployments(config['app_id'])

    failed = False

    if len(deployments) > 0:
        running = True
        while running:
            incomplete_deployments = deploy.get_incomplete_deployments(deployments)

            # stop if we have completed all deployments
            if len(incomplete_deployments) == 0:
                running = False
                break

            running = True
            for deployment in incomplete_deployments:
                print yellow("* %(CreatedAt)s | %(CommandName)s | %(Status)s | %(DeploymentId)s" % {
                    'DeploymentId' : deployment['DeploymentId'],
                    'CreatedAt' : deployment['CreatedAt'],
                    'Status' : deployment['Status'],
                    'CommandName' : deployment['Command']['Name'],
                })

            print "--> Waiting for application deployments to complete..."
            sleep(5) # delays for 5 seconds

        complete_deployments = deploy.get_deployments(deployments)
        for deployment in complete_deployments:
            if deployment['Status'] == "failed":
                print red("* %(CreatedAt)s | %(CommandName)s | %(Status)s | %(DeploymentId)s" % {
                    'DeploymentId' : deployment['DeploymentId'],
                    'CreatedAt' : deployment['CreatedAt'],
                    'Status' : deployment['Status'],
                    'CommandName' : deployment['Command']['Name'],
                })
                failed = True

    result = OpsWorksResult()
    result.failed = False

    if failed:
        result.failed = True
        print red("--> Failed deployments found")
    else:
        print green("--> All application deployments complete")

    result.succeeded = not result.failed
    return result