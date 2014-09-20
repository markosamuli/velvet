Velvet
======

AWS API and Fabric tasks for deploying applications into EC2 instances

Installation and usage
----------------------

You need pip, build-essential and python-dev installed to run this:

Ubuntu
::

    sudo apt-get install python-pip build-essential python-dev 


Install package:
::

    pip install .


Setup Velvet for a new project
------------------------------

Create `requirements.txt` file in the project root. This will install the package from Github.
::

    git+ssh://git@github.com:markosamuli/velvet.git@v0.5.6

Create Python virtualenv for the project.
::

    mkvirtualenv PROJECT_NAME

Install packages.
::

    pip install -r requirements.txt

Create acceess key:
::

    aws iam create-access-key --user-name USERNAME > ~/.aws/PROJECT_NAME.json

Configure Velvet and import your AWS access key JSON file.
::

    velvet-config --import-access-key ~/.aws/PROJECT_NAME.json

    --aws-config

Configure Velvet and import your AWS credentials.
::

    velvet-config --import-credentials credentials.csv

Create `config/velvet.yml` file.

OpsWorks project Velvet configuration
-------------------------------------

Example `config/velvet.yml` file for a project deployed to OpsWorks.
::

    # deployment configuration file version (minimum supported Velvet version number)
    version: 0.4

    # defaults for all environments
    defaults:

        # application name
        app_name: application

        # deployment package file name without extension
        deploy_package: application

        # S3 bucket for application deployment
        deploy_bucket: application-deploy

        # path to CloudFormation template files
        cloudformation_path: cloudformation

        # build directories
        build_root: application
        build_grunt: application
        build_exclude:
            - vendor
            - node_modules

        cookbooks_root: cookbooks
        cookbooks_package: application_cookbooks

        # root directory inside the application for assets
        assets_root: public_html/assets

        # use compressed assets if avaiblable when publishing to S3
        # assets are compressed with Grunt in the application build process
        gzip_enabled: true

        # assets to be published to S3
        assets:
            - css/**/*.css
            - fonts/**/*
            - js/**/*
            - img/**/*
            - video/**/*

        opsworks:
            stack: StackId
            layer: WebLayerId
            app: WebAppId

    # define available environments
    environments:

        dev:

            stacks:

                -   # CloudFormation / OpsWorks stack
                    name: dev-opsworks
                    role: opsworks
                    template: opsworks

            # disable automatic CloudFormation rollback on failure
            disable_rollback: true

            assets_bucket: application-assets-dev


Create CloudFormation templates
-------------------------------

Create cfn-pyplates templates in `cloudformation` directory and create mappings YAML files for each environment.
::

    cloudformation
        mappings
            dev.yaml
        mysql.py
        opsworks.py
        vpc.py

Run velvet-cloudformation to generate the templates.
::

    velvet-cloudformation dev opsworks

Create Fabric files
-------------------

Fabric main file `fabric.py` is used for environment configuration and loading actual task packages.

::

    # fabric.py (generic AWS setup)
    from fabric.api import env, task

    import velvet.config
    import velvet.aws.config

    ## 
    # import application specific tasks
    ##

    # build tasks
    import build

    # deployment tasks
    import deploy

    # infrastructure provisioning tasks
    import provision

    ##
    # define environments
    ##

    @task
    def environment(name):

        # Load AWS configuration
        velvet.aws.config.load()

        # Load environment configuration
        velvet.config.environment(name)

