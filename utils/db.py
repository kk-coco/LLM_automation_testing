import pymysql
from dbutils.pooled_db import PooledDB
from flask import current_app

from utils.logging import Logger

db_pool = None
log = Logger()

def init_db_pool(config):
    global db_pool
    db_pool = PooledDB(
        creator=pymysql,
        maxconnections=10,
        mincached=2,
        maxcached=5,
        maxshared=3,
        blocking=True,
        host=config['MYSQL_HOST'],
        port=config['MYSQL_PORT'],
        user=config['MYSQL_USER'],
        password=config['MYSQL_PASSWORD'],
        database=config['MYSQL_DB'],
        charset=config['MYSQL_CHARSET'],
        cursorclass=pymysql.cursors.DictCursor,
    )

def get_conn():
    if not db_pool:
        log.error("DB pool not initialized")
    return db_pool.connection()

def fetch_all(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchall()
        conn.commit()
        return result
    except Exception as e:
        current_app.logger.error(f"[fetch_all] SQL Error: {e}")
        return []
    finally:
        conn.close()

def fetch_one(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchone()
        conn.commit()
        return result
    except Exception as e:
        current_app.logger.error(f"[fetch_one] SQL Error: {e}")
        return None
    finally:
        conn.close()

def execute(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"[execute] SQL Error: {e}")
        return False
    finally:
        conn.close()
