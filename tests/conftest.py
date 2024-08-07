"""setup for running tests"""
import sys
import json
import os
from subprocess import Popen, PIPE


def pytest_sessionstart(session):
    """perform setup before any tests are run"""
    print(f"Generating list of all tests to run for unique port assignment")
    pytest_output: list[str] = []
    base_dir: str = os.path.join(os.path.dirname(__file__), '..')
    if 'collect-only' in "".join(sys.argv):  # avoid recursion
        return

    with Popen(['pytest',
                '--collect-only',  # shorter traceback format
                base_dir], stdout=PIPE, bufsize=1,
               universal_newlines=True) as pytest_process:
        for line in pytest_process.stdout:
            pytest_output.append(line.strip(' \n'))

    package: str = ''
    test_case: str = ''
    module: str = ''
    unambiguous_names: list[str] = []
    dirname: str = ''
    for line in pytest_output:
        if 'Module' in line:
            module = line.strip('<>').replace('Module', '').strip(' ')
        elif 'UnitTestCase' in line:
            test_case = line.strip('<>').replace('UnitTestCase', '').strip(' ')
        elif 'Package' in line:
            package = line.strip('<>').replace('Package', '').strip(' ')
        elif 'TestCaseFunction' in line:
            test_function: str = line.strip('<>').replace('TestCaseFunction', '').strip(' ')
            unambiguous_name: str = f"{package}.{dirname}.{module}.{test_case}.{test_function}"
            unambiguous_names.append(unambiguous_name.lower())
        elif 'Dir' in line:
            dirname = line.strip('<>').replace('Dir', '').strip(' ')

    file_path: str = os.path.join(base_dir, 'tests', 'list_of_tests.json')
    with open(file_path, mode='w+', encoding='utf-8') as json_file:
        json_file.write(json.dumps(unambiguous_names))
