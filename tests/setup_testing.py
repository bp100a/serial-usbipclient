"""setup for running tests"""
import json
from tests.common_test_base import CommonTestBase


class TestGeneratePortAssignments(CommonTestBase):
    """generate the port assignments"""

    def test_generate_test_port_assignments(self):
        """test the port assignments"""
        # perform a test runner collection on the root dir
        self.skip_on_ci(reason='run locally to generate data')

        import os  # pylint: disable=import-outside-toplevel
        from subprocess import Popen, PIPE  # pylint: disable=import-outside-toplevel
        pytest_output: list[str] = []
        base_dir: str = os.path.join(os.path.dirname(__file__), '..')
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
                unambiguous_names.append(unambiguous_name)
            elif 'Dir' in line:
                dirname = line.strip('<>').replace('Dir', '').strip(' ')

        file_path: str = os.path.join(base_dir, 'tests', 'list_of_tests.json')
        with open(file_path, mode='w+', encoding='utf-8') as json_file:
            json_file.write(json.dumps(unambiguous_names))
