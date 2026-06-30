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

from neutron_plugin_contrail.plugins.opencontrail.quota import driver as drv
from neutron_plugin_contrail.plugins.opencontrail.quota.driver import \
    QuotaDriver

TENANT = '11111111-2222-3333-4444-555555555555'


class _NoRead(object):
    """Connection whose per-object reads must never run (proves N+1 gone)."""

    def virtual_network_read(self, *a, **k):
        raise AssertionError('virtual_network_read called: N+1 not removed')

    def security_group_read(self, *a, **k):
        raise AssertionError('security_group_read called: N+1 not removed')


class _Ipam(object):
    def __init__(self, n):
        self._n = n

    def get_ipam_subnets(self):
        return list(range(self._n))


class _VN(object):
    def __init__(self, subnets):
        self._refs = [{'attr': _Ipam(subnets)}] if subnets else []

    def get_network_ipam_refs(self):
        return self._refs or None


class _Entries(object):
    def __init__(self, n):
        self._n = n

    def get_policy_rule(self):
        return list(range(self._n))


class _SG(object):
    def __init__(self, rules):
        self._entries = _Entries(rules) if rules is not None else None

    def get_security_group_entries(self):
        return self._entries


class _ListConn(_NoRead):
    """Returns detail=True object lists; counts list calls."""

    def __init__(self, vns=None, sgs=None):
        self._vns = vns or []
        self._sgs = sgs or []
        self.list_calls = 0

    def virtual_networks_list(self, parent_id=None, detail=False):
        assert detail is True
        self.list_calls += 1
        return self._vns

    def security_groups_list(self, parent_id=None, detail=False):
        assert detail is True
        self.list_calls += 1
        return self._sgs


class QuotaConnCacheTest(unittest.TestCase):
    """_get_vnc_conn reuses one VncApi instead of re-authenticating."""

    def setUp(self):
        QuotaDriver._vnc_conn = None
        self.addCleanup(setattr, QuotaDriver, '_vnc_conn', None)
        self._orig = drv.utils.get_vnc_api_instance
        self.addCleanup(
            setattr, drv.utils, 'get_vnc_api_instance', self._orig)
        self.built = []

        def fake():
            obj = object()
            self.built.append(obj)
            return obj

        drv.utils.get_vnc_api_instance = fake

    def test_connection_built_once_and_reused(self):
        a = QuotaDriver._get_vnc_conn()
        b = QuotaDriver._get_vnc_conn()
        c = QuotaDriver._get_vnc_conn()
        self.assertIs(a, b)
        self.assertIs(b, c)
        self.assertEqual(1, len(self.built))


class _Project(object):
    def get_quota(self):
        return None


class _DefProjConn(object):
    """Resolves the default-project fq_name and reads quota by id."""

    def __init__(self):
        self.fqname_calls = 0
        self.read_ids = []

    def fq_name_to_id(self, res_type, fq_name):
        self.fqname_calls += 1
        return 'def-proj-uuid'

    def project_read(self, id=None, fq_name=None):
        assert id is not None, 'should read by cached id, not fq_name'
        self.read_ids.append(id)
        return _Project()


class QuotaDefaultProjectCacheTest(unittest.TestCase):
    """default-project fq_name resolves once; quota value read every call."""

    def setUp(self):
        QuotaDriver._vnc_conn = None
        QuotaDriver._default_project_id = None
        self.addCleanup(setattr, QuotaDriver, '_vnc_conn', None)
        self.addCleanup(setattr, QuotaDriver, '_default_project_id', None)

    def test_default_project_resolved_once_value_read_each_call(self):
        conn = _DefProjConn()
        QuotaDriver._vnc_conn = conn
        for _ in range(3):
            QuotaDriver.get_default_quotas(None, ['network'])
        self.assertEqual(1, conn.fqname_calls)
        self.assertEqual(['def-proj-uuid'] * 3, conn.read_ids)


class QuotaUsedNoPerObjectReadTest(unittest.TestCase):
    """_get_used_quota counts via one detail list, no per-object reads."""

    def setUp(self):
        QuotaDriver._vnc_conn = None
        self.addCleanup(setattr, QuotaDriver, '_vnc_conn', None)

    def test_subnet_used_without_per_vn_read(self):
        conn = _ListConn(vns=[_VN(2), _VN(3), _VN(0)])
        QuotaDriver._vnc_conn = conn  # bypass real auth
        self.assertEqual(5, QuotaDriver._get_used_quota('subnet', TENANT))
        self.assertEqual(1, conn.list_calls)

    def test_sgr_used_without_per_sg_read(self):
        # _SG(None) has no entries -> guarded (old code would crash here).
        conn = _ListConn(sgs=[_SG(4), _SG(0), _SG(None)])
        QuotaDriver._vnc_conn = conn
        self.assertEqual(
            4, QuotaDriver._get_used_quota('security_group_rule', TENANT))
        self.assertEqual(1, conn.list_calls)


if __name__ == '__main__':
    unittest.main()
