from logging import getLogger

from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)
import redis
from celery import Celery

logger = getLogger('stream')

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

app = Celery('tasks', broker='pyamqp://guest:guest@127.0.0.1:5672//')


@app.task(name='put_record')
def put_record(
    event, 
    server_id,
    log_file,
    log_pos
):
    logger.info(f'>>> event inside the worker: {event}')

    redis_key = f"cdc:{server_id}"
    redis_client.hmset(redis_key, {
        'log_file': log_file,
        'log_pos': log_pos
    })


def main():
    MYSQL_SETTINGS = {
      'host': 'localhost',
      'port': 3306,
      'user': 'root',
      'passwd': 'password'
    }

    server_id = 1
    redis_key = f"cdc:{server_id}"
    logger.info(f">>> Starting service")
    state = redis_client.hgetall(redis_key)
    log_file = state.get('log_file', None)
    log_pos = int(state['log_pos']) if 'log_pos' in state else None

    logger.info(f">>> Starting binlog stream with log_file={log_file}, log_pos={log_pos}")

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

        logger.info(f'>>> events for log file {stream.log_file} at position {binlogevent.packet.log_pos}:')
        
        for row in binlogevent.rows:
            if isinstance(binlogevent, WriteRowsEvent):
                event_type = 'insert'
                row_data = row.get('values', None)
            elif isinstance(binlogevent, UpdateRowsEvent):
                event_type = 'update'
                row_data = row.get('after_values', None)
            elif isinstance(binlogevent, DeleteRowsEvent):
                event_type = 'delete'
                row_data = row.get('values', None)
            else:
                continue

            event = {
                'event_type': event_type,
                'timestamp': binlogevent.timestamp,
                'schema': binlogevent.schema,
                'table': binlogevent.table,
                'log_position': binlogevent.packet.log_pos,
                'row': row_data,
            }
            print(event)

            put_record.delay(
                event,
                server_id,
                stream.log_file,
                binlogevent.packet.log_pos
            )

    stream.close()


if __name__ == '__main__':
    main()