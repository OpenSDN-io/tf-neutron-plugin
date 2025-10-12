# -*- mode: python; -*-

env = DefaultEnvironment()

base_path = '#openstack/neutron_plugin/'

sdist_gen = env.Command(
    '/pip/neutron_plugin_contrail-0.1.dev0-py3-none-any.whl', 'setup.py',
    'cd ' + Dir(base_path).path + ' && ' + 'python3 setup.py bdist_wheel --dist-dir /pip')
env.Alias('install', sdist_gen)

deps = [
    '/pip/contrail_api_client-0.1.dev0-py3-none-any.whl',
]
env.SetupPyTestSuiteWithDeps(sdist_gen, sdist_depends=deps, top_dir=Dir(base_path).abspath)
