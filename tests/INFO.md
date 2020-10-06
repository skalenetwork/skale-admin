# General information about skale-admin tests

Tests divied to three parts:
- General tests
- Node rotation tests
- Firewall tests

## General tests
Covers basic functionality of common parts:
- Config creation 
- Docker workflow
- Api endpints
- SChains database
- SChains checks
- Basic dkg testing
- Telegram notifications

Requires:
- *Ganache* with deployed *skale-manager* contracts
- *Sgx simulator*
- *Redis* container (for telegram notifcations tests)

## Rotation tests
Covers basic node roation logic.
Requires:
- *Ganache* with deployed *skale-manager* contracts
- *Sgx simulator*

## Firewall tests
Covers firewall logic (tests are running in docker container to avoid changes of iptables rules on local machine)


## Conftest fixtures
tests/conftest.py modules contains set of fixtures that can be used to emulate test environment. 

0. **_schain_name** - Generates random schain name (because all schain's names (including deleted) is unique in skale-manager.
Should not be used directly.
1. **schain_config** - creates config and secret key file in schain config directory for schain with name **_schain_name**. Removes all files during teardown. 
2. **db** - creates sqlite db with SChainRecord table. Removes db file during teardown. 
3. **schain_db** - *db* with inserted **_schain_name** data. 
4. **schain_on_contracts** - creates two nodes and **_schain_name**. Removes schain and nodes during teardown. 

### Note
If you need more then one schain to emulate environment you can use the same approach to setup and cleanup schains data. 
***Please avoid leaving*** any artifacts after test is completed (including the case when it's failed).


## Skaled test environment
It's important to note that during tests skaled runs in slightly different environement.
1. ssl is disabled so https and wss endpints is not working.
2. Datadir uses default driver instead of docker-lvmpy.
3. All other volume attached using :Z mode because of permission issues. 
4. Ulimit check is disabled because of permission issues. 



