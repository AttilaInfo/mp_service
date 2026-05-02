# gunicorn.conf.py — zero-downtime деплой

bind            = '0.0.0.0:8080'
workers         = 2
timeout         = 120
graceful_timeout = 30   # ждём 30 сек пока текущие запросы завершатся
keepalive       = 5

# Логи в stdout — Railway их подхватывает
accesslog  = '-'
errorlog   = '-'
loglevel   = 'info'
