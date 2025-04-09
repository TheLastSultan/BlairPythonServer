"""
This script takes in a `docker-compose.yml` & outputs an elastic-beanstalk 
friendly version of that compose.

This script writes iff there is a change in content.
"""
import os
import argparse
import yaml
import json
from copy import deepcopy


def _process(old_compose: dict) -> dict:
    """
    Makes necessary modifications to old docker-compose into an 
    EB-friendly version
    """
    new_compose = deepcopy(old_compose)
    for service_name in list(new_compose['services'].keys()):
        service = new_compose['services'][service_name]
        if 'build' in service:
            del service['build']
        if 'restart' in service:
            del service['restart']
    return new_compose


def _has_changes(new_compose: dict, abs_output: str):
    if os.path.exists(abs_output):
        with open(abs_output, 'r') as file:
            old_compose = yaml.safe_load(file)
        
        if json.dumps(old_compose, sort_keys=True) == json.dumps(new_compose, sort_keys=True):
            return False
    return True


def recompose(input: str, output: str):
    abs_input = os.path.abspath(input)
    abs_output = os.path.abspath(output)
    with open(abs_input, 'r') as file:
        input_compose = yaml.safe_load(file)
    
    new_compose = _process(input_compose)

    if _has_changes(new_compose, abs_output):
        with open(abs_output, 'w') as file:
            yaml.dump(new_compose, file, sort_keys=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", help="Service Docker-compose file.", required=True)
    parser.add_argument("-o", "--output", help="Where to write the Elastic-Beanstalk Docker-compose file.", required=True)
    recompose(**vars(parser.parse_args()))
