__author__ = 'marko.kirves'

import velvet.jenkins as jenkins

def write_build_changes(url=None, job_name=None, build_number=None):
    """
    Write BUILD_CHANGES.properties file for Jenkins
    :type url: str
    """
    build_changes = jenkins.export_build_changes(url, job_name, build_number)
    formatted = "BUILD_CHANGES = {}".format("\\\n".join(build_changes))
    with open('BUILD_CHANGES.properties', 'wb') as f:
        f.write(formatted)
