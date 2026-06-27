# Copyright 2026 Juniper Networks.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import unittest

from neutron_plugin_contrail.plugins.opencontrail import contrail_plugin


class FakeContext(object):
    def __init__(self, request_id):
        self.request_id = request_id


class GetNetworkMemoTestCase(unittest.TestCase):
    """Request-scoped get_network cache (see contrail_plugin._NET_MEMO)."""

    def setUp(self):
        contrail_plugin._NET_MEMO.clear()
        self.addCleanup(contrail_plugin._NET_MEMO.clear)
        # Skip __init__ (registers config/api servers); we only exercise
        # get_network, which needs _get_network, _prune and the base method.
        self.plugin = contrail_plugin.NeutronPluginContrailCoreV2.__new__(
            contrail_plugin.NeutronPluginContrailCoreV2)
        self.fetched = []

        def fake_get_network(context, network_id, fields=None):
            self.fetched.append(network_id)
            return {'id': network_id,
                    'tenant_id': 't-%s' % network_id,
                    'shared': False,
                    'name': 'net-%s' % network_id}

        self.plugin._get_network = fake_get_network

    def test_same_request_same_net_fetched_once(self):
        ctx = FakeContext('req-1')
        self.plugin.get_network(ctx, 'n1', ['tenant_id'])
        self.plugin.get_network(ctx, 'n1', ['shared'])
        # One backend fetch; the full dict served both field subsets.
        self.assertEqual(['n1'], self.fetched)

    def test_field_projection(self):
        ctx = FakeContext('req-1')
        self.assertEqual(
            {'tenant_id': 't-n1'},
            self.plugin.get_network(ctx, 'n1', ['tenant_id']))

    def test_per_request_isolation(self):
        self.plugin.get_network(FakeContext('req-1'), 'n1')
        self.plugin.get_network(FakeContext('req-2'), 'n1')
        self.assertEqual(['n1', 'n1'], self.fetched)

    def test_no_request_id_bypasses_cache(self):
        ctx = FakeContext(None)
        self.plugin.get_network(ctx, 'n1')
        self.plugin.get_network(ctx, 'n1')
        self.assertEqual(['n1', 'n1'], self.fetched)

    def test_cached_dict_not_mutated_by_pruning(self):
        ctx = FakeContext('req-1')
        self.plugin.get_network(ctx, 'n1', ['tenant_id'])
        cached = contrail_plugin._NET_MEMO['req-1']['n1']
        self.assertEqual({'id', 'tenant_id', 'shared', 'name'}, set(cached))

    def test_lru_evicts_oldest_request(self):
        for i in range(contrail_plugin._NET_MEMO_MAX + 10):
            self.plugin.get_network(FakeContext('req-%d' % i), 'n1')
        self.assertLessEqual(len(contrail_plugin._NET_MEMO),
                             contrail_plugin._NET_MEMO_MAX)


if __name__ == '__main__':
    unittest.main()
