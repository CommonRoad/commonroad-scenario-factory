def pytest_addoption(parser):
    parser.addoption('--random_test', action='store_true', help='Enable the random testing.')