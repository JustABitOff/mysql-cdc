import json
from os import getenv

import boto3
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)
from celery import Celery

app = Celery('tasks', broker='pyamqp://guest@localhost//')


@app.task(name='put_record_to_kinesis')
def put_record_to_kinesis(
    event, 
    kinesis_partition_key,
    server_id,
    log_file,
    log_pos
):
    kinesis = boto3.client(
        'kinesis',
        region_name='us-east-2',
        aws_access_key_id=getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=getenv('AWS_SECRET_ACCESS_KEY')
    )
    dynamo_table = boto3.resource(
        'dynamodb',
        region_name='us-east-2',
        aws_access_key_id=getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=getenv('AWS_SECRET_ACCESS_KEY')
    ).Table('cdc_stream_state')

    kinesis_output = kinesis.put_record(
        StreamName='mysql_cdc_stream',
        Data=json.dumps(event),
        PartitionKey=kinesis_partition_key
    )
    print('>>> kinesis output: ', kinesis_output)
    
    dynamo_table.update_item(
        Key={
            'server_id': server_id
        },
        UpdateExpression="set log_file=:f, log_file_sequence=:s, log_pos=:p",
        ExpressionAttributeValues={
            ":f": log_file,
            ":s": int(log_file.split('.')[-1]),
            ":p": log_pos
        },
    )


def main():
    MYSQL_SETTINGS = {
      'host': 'localhost',
      'port': 3306,
      'user': 'root',
      'passwd': 'password'
    }
    dynamo_table = boto3.resource(
        'dynamodb',
        region_name='us-east-2',
        aws_access_key_id=getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=getenv('AWS_SECRET_ACCESS_KEY')
    ).Table('cdc_stream_state')
    server_id = 1012598212
    log_state = dynamo_table.get_item(Key={'server_id': server_id}, ConsistentRead=True).get('Item')
    log_file = log_state.get('log_file') if log_state else None
    log_pos = int(log_state.get('log_pos')) if log_state else None

    print('>>> listener start streaming')
    stream = BinLogStreamReader(
        connection_settings=MYSQL_SETTINGS,
        server_id=server_id,
        blocking=True,
        resume_stream=True,
        only_events=[DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent],
        log_file=log_file,
        log_pos=log_pos,
    )
    for binlogevent in stream:
        print(f'>>> events for log file {stream.log_file} at position {binlogevent.packet.log_pos}:')
        for row in binlogevent.rows:
            if isinstance(binlogevent, WriteRowsEvent):
                event = {
                    'event_type': 'insert',
                    'timestamp': binlogevent.timestamp,
                    'schema': binlogevent.schema,
                    'table': binlogevent.table,
                    'log_position': binlogevent.packet.log_pos,
                    'row': row.get('values', None),
                }
            elif isinstance(binlogevent, UpdateRowsEvent):
                event = {
                    'event_type': 'update',
                    'timestamp': binlogevent.timestamp,
                    'schema': binlogevent.schema,
                    'table': binlogevent.table,
                    'log_position': binlogevent.packet.log_pos,
                    'row': row.get('after_values', None),
                }
            elif isinstance(binlogevent, DeleteRowsEvent):
                event = {
                    'event_type': 'delete',
                    'timestamp': binlogevent.timestamp,
                    'schema': binlogevent.schema,
                    'table': binlogevent.table,
                    'log_position': binlogevent.packet.log_pos,
                    'row': row.get('values', None),
                }
            else:
                pass

            print('>>> event:', event)
            put_record_to_kinesis.delay(
                event,
                f'{binlogevent.schema}.{binlogevent.table}',
                server_id,
                stream.log_file,
                binlogevent.packet.log_pos
            )

    stream.close()


if __name__ == '__main__':
    main()