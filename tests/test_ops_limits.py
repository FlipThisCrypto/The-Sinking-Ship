# SPDX-License-Identifier: MIT
from fulfillment.ops_limits import MAX_RECONCILE_HOSTS, RECOMMENDED_BACKUP_INTERVAL_MIN
def test_ops_limits():
    assert MAX_RECONCILE_HOSTS == 1
    assert RECOMMENDED_BACKUP_INTERVAL_MIN >= 5
