from peewee import BooleanField, CharField, CompositeKey, DateTimeField, IntegerField, Model, \
    MySQLDatabase, ForeignKeyField

from tools.db_config import MYSQL_DB_HOST, MYSQL_DB_NAME, MYSQL_DB_PASSWORD, MYSQL_DB_PORT, \
    MYSQL_DB_USER

dbhandle = MySQLDatabase(
    MYSQL_DB_NAME, user=MYSQL_DB_USER,
    password=MYSQL_DB_PASSWORD,
    host=MYSQL_DB_HOST,
    port=MYSQL_DB_PORT
)


class BaseModel(Model):
    class Meta:
        database = dbhandle


class Report(BaseModel):
    my_id = IntegerField()
    node_id = IntegerField()
    is_alive = BooleanField()
    latency = IntegerField()
    stamp = DateTimeField()


class BountyReceipt(BaseModel):
    tx_hash = CharField()
    eth_balance_before = CharField()
    skl_balance_before = CharField()
    eth_balance = CharField()
    skl_balance = CharField()
    gas_used = IntegerField()

    class Meta:
        db_table = 'bounty_receipt'
        primary_key = CompositeKey('tx_hash')


class BountyEvent(BaseModel):
    my_id = IntegerField()
    tx_dt = DateTimeField()
    bounty = CharField()
    downtime = IntegerField()
    latency = IntegerField()
    gas = IntegerField()
    stamp = DateTimeField()
    tx_hash = CharField()
    bounty_receipt = ForeignKeyField(BountyReceipt, to_field='tx_hash', db_column='tx_hash')

    class Meta:
        db_table = 'bounty_event'
