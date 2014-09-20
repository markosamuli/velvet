__author__ = 'marko.kirves'

import jenkinsapi
from jenkinsapi.jenkins import Jenkins

import re
import os

VALID_BUILD_NUMBER = re.compile("^[0-9]+$")

def get_build_number():
    build_number = os.getenv('BUILD_NUMBER')

    if build_number is None:
        raise Exception("BUILD_NUMBER not defined")

    if not VALID_BUILD_NUMBER.match(build_number):
        raise Exception("BUILD_NUMBER is not valid")

    return int(build_number)


def get_job_name():
    job_name = os.getenv('JOB_NAME')

    if job_name is None:
        raise Exception("JOB_NAME not defined")

    return job_name


def get_jenkins_url():
    url = os.getenv('JENKINS_URL')

    if url is None:
        raise Exception("JENKINS_URL not defined")

    return url


def export_build_changes(url=None, job_name=None, build_number=None):

    if job_name is None:
        job_name = get_job_name()

    if build_number is None:
        build_number = get_build_number()

    J = connect(url)
    if job_name in J:
        build = J[job_name].get_build(build_number)
        changes = get_changes(build)
        return format_changes(changes)


def get_changes(build):
    """
    :type build: jenkinsapi.build.Build
    :return: list
    """

    assert type(build) == jenkinsapi.build.Build

    changes = []
    for change in build._data['changeSet']['items']:
        changes.append({
            'commitId' : change['commitId'][0:7],
            'author' : change['author']['fullName'],
            'date' : change['date'],
            'msg' : change['msg'],
        })
    return changes


def format_changes(changes):
    """
    :type changes: list
    """

    def _format_change(change):
        """
        :type change: dict
        """
        return "* %(commitId)s - %(msg)s (%(date)s) <%(author)s>" % change

    return [_format_change(change) for change in changes]


def connect(url=None):
    """
    :type url: str
    :rtype: jenkinsapi.jenkins.Jenkins
    """
    if url is None:
        url = get_jenkins_url()
    return Jenkins(url)