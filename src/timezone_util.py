"""
时区工具
"""
import time as _time


try:
    import zoneinfo
    TZ_ASIA_SHANGHAI = zoneinfo.ZoneInfo("Asia/Shanghai")
except Exception:
    import datetime as _dt
    TZ_ASIA_SHANGHAI = _dt.timezone(_dt.timedelta(hours=8))


def log_record_time(t=None):
    """日志记录器使用的本地时间转换函数"""
    return _time.localtime(t).__class__(_time.localtime(t))
