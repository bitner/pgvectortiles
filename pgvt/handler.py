import os
import psycopg2
from psycopg2 import sql
from lambda_proxy.proxy import API
from pathlib import Path
import boto3
import io
import sys

s3 = boto3.client('s3')

APP = API(app_name='pgvt')

@APP.route('/', methods=['GET'], cors=True)
def index():
    body=Path('pgvt/index.html').read_text()
    return ('OK', 'text/html', body)

@APP.route('/<table>/', methods=['GET'], cors=True)
@APP.pass_event
def ol(event, table):
    server=event['headers'].get('Host', '')
    body=Path('pgvt/ol.html').read_text().replace('<server>',server).replace('<table>',table)
    return ('OK', 'text/html', body)

@APP.route('/simple.json', methods=['GET'], cors=True)
@APP.pass_event
def simplejs(event):
    server=event['headers'].get('Host', '')
    body=Path('pgvt/simple.json').read_text().replace('<server>',server)
    return ('OK', 'application/json', body)


@APP.route('/<table>/<z>/<x>/<y>.pbf', methods=['GET'], cors=True, binary_b64encode=True)
def pgvt(table, z, x, y):
    #check if cache exists
    '''key = "cache/{}/{}/{}/{}.pbf".format(table, z, x, y)
    try:
        obj=s3.getObject('mapproxy-lambda-demo', key)
        print('returning from cache', key)
        return ('OK', 'application/octet-stream', obj['Body'].read())
    except:
        print ('not in cache')'''

    print('connecting to ', os.environ['PGHOST'])
    conn = psycopg2.connect(
        host=os.environ['PGHOST'],
        dbname=os.environ['PGDATABASE'],
        user=os.environ['PGUSER'],
        password=os.environ['PGPASSWORD']
    )
    print('connected')
    
    print(table, z, x, y)
    # Get column list from table
    q='''
    select 
    array_agg(c.column_name::text)
    from information_schema.columns as c 
    WHERE table_name=%s 
    and c.column_name not in ('geom');
    '''
    '''with conn:
        with conn.cursor() as c:
            c.execute(q,(table,))
            if c.rowcount != 1:
                return ('NOK', 'plain/txt', 'Table f{table} does not exist')
            columns = c.fetchone()[0]
    columns_sql = list(map(lambda x:sql.Identifier(x).as_string(conn), columns))
    columns_str = ', '.join(columns_sql)
    print(columns_str)
    table_str = sql.Identifier(table).as_string(conn)
    print(table_str)'''
    table_str='major_roads'
    columns_str='gid'

    q='''
    SELECT ST_AsMVT(q, %(table)s, 4096, 'mvtg') FROM (
        SELECT {},
        ST_ASMVTGeom(
            st_transform(geom, 3857),
            TileBBox(%(z)s, %(x)s, %(y)s),
            4096,
            256,
            true
        ) as mvtg
        FROM {}
        WHERE st_transform(geom, 3857) && TileBBox(%(z)s, %(x)s, %(y)s)
        AND ST_Intersects(st_transform(geom, 3857), TileBBox(%(z)s, %(x)s, %(y)s))
    ) q;
    '''
    baseq = q.format(columns_str, table_str)
    print(baseq)
    with conn:
        with conn.cursor() as c:
            
            c.execute(
                baseq,
                {'z':z,'x':x,'y':y, 'table': table}
            )
            print (c.query)
            tile = c.fetchone()[0]
            '''b = io.BytesIO(tile)
            
            print('adding to cache', key)
            if sys.getsizeof(b)>0:
                s3.put_object(Body=b, Bucket='mapproxy-lambda-demo', Key=key)
                print('cache added', key)
            else:
                print('bytesio object 0', key)'''
    conn.close()
    return ('OK', 'application/octet-stream', tile)