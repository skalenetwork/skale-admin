from core.schains.config.previous_keys import (
    compose_previous_keys_info, previous_keys_info_to_dicts, PreviousKeyInfo
)

from tests.rotation_test.utils import rotated_nodes, wait_for_contract_exiting, run_dkg_all  # noqa


PREVIOUS_PUBLIC_KEYS_MOCK = [((1213654839325820620408896725120102048693147754091411689779570169825703344853, 15248164698915670635654525181019621301549603087998338702315270709408053942808), (543021366887249830308126035948433395973058737876795072972312032601626014416, 12665655462422434603013841434494093958135095755975249241376632243235810937279))]  # noqa


def test_previous_public_keys(skale, skale_ima, rotated_nodes, dutils, meta_file):  # noqa
    nodes, schain_name = rotated_nodes

    exited_node, _ = nodes[0], nodes[2]
    exited_node.exit({})

    wait_for_contract_exiting(skale, exited_node.config.id)

    new_nodes = [nodes[1], nodes[2]]
    skale_instances = [new_nodes[0].skale, new_nodes[1].skale]
    nodes_data = [{'node_id': new_nodes[0].config.id}, {'node_id': new_nodes[1].config.id}]
    run_dkg_all(skale, skale_instances, schain_name, nodes_data)

    group_id = skale.schains.name_to_group_id(schain_name)
    previous_public_keys = skale.key_storage.get_all_previous_public_keys(group_id)

    assert len(previous_public_keys) == 1
    assert isinstance(previous_public_keys[0], tuple)
    assert len(previous_public_keys[0]) == 2
    assert len(previous_public_keys[0][0]) == 2

    rotation_data = skale.node_rotation.get_rotation(schain_name)
    previous_keys_info = compose_previous_keys_info(skale, [rotation_data], previous_public_keys)
    previous_keys_info_dicts = previous_keys_info_to_dicts(previous_keys_info)

    assert isinstance(previous_keys_info, list)
    assert isinstance(previous_keys_info_dicts, list)

    assert isinstance(previous_keys_info[0], PreviousKeyInfo)
    assert isinstance(previous_keys_info_dicts[0], dict)
