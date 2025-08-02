# Gunicorn configuration file
import multiprocessing

# Server socket
bind = '0.0.0.0:8000'

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
max_requests = 2000
max_requests_jitter = 50

# Timeouts
timeout = 90
keepalive = 5

# Logging
loglevel = 'info'
accesslog = '-'  # Log to stdout
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)s'

errorlog = '-'
capture_output = True

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Debugging
reload = False

# Process naming
proc_name = 'todo_react_py'
