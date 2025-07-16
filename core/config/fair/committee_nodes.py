import bisect
import time


class CommitteeNodesConfigError(Exception):
    pass


class NoActiveGroupError(CommitteeNodesConfigError):
    pass


class NoFutureGroupError(CommitteeNodesConfigError):
    pass


def pick_active_group_from_committee_nodes(committee_nodes_in_scope: dict, current_ts: int) -> list:
    timestamps = sorted(map(lambda str_ts_repr: int(str_ts_repr), committee_nodes_in_scope))
    ts_index = bisect.bisect_right(timestamps, current_ts)
    ts = timestamps[ts_index - 1]
    if ts > current_ts:
        raise NoActiveGroupError('No active group found in committee nodes')
    return committee_nodes_in_scope[str(ts)]['group']


def pick_future_group_from_committee_nodes(committee_nodes_in_scope: dict) -> list:
    timestamps = sorted(
        map(lambda str_ts_repr: int(str_ts_repr), committee_nodes_in_scope.values())
    )
    current_ts = time.time()
    ts_index = bisect.bisect_left(timestamps, current_ts)
    ts = timestamps[ts_index - 1]
    if ts < current_ts:
        raise NoFutureGroupError('All groups are activated')
    return committee_nodes_in_scope[str(ts)]['group']
