from contextlib import contextmanager
import logging
import os
import signal
import subprocess
import time
import threading

import tempfile_wrapper

def _create_log_file(log_file_name, line_buffered=False):
    if not log_file_name:
        return open('/dev/null', 'w')
    logging_dir, log_file_name = os.path.split(log_file_name)
    return tempfile_wrapper.get_temp_file(desired_name=log_file_name, 
                                          bufsize=1 if line_buffered else -1,
                                          in_dir=logging_dir, 
                                          delete=False)

def kill_processes(process_command_substrings):
    if isinstance(process_command_substrings, basestring):
        process_command_substrings = (process_command_substrings,)
    keys = None
    killed = []
    for line in subprocess.check_output('ps aux', shell=True).split('\n'):
        if not line.strip():
            continue
        if not keys:
            keys = line.split()
        else:
            values = line.split()
            process = dict(zip(keys, values))
            process[keys[-1]] += u' ' + u' '.join(values[len(keys):])
            if any( s in process['COMMAND'] for s in process_command_substrings ):
                killed.append(process)
                logging.debug('Executing "kill -9 %s"', process['PID'])
                subprocess.call('kill -9 ' + process['PID'], shell=True)
    return killed

class ServiceProcess(object):
    def __init__(self, command, name, log, teardown_command=None):
        self.log = _create_log_file(log) if isinstance(log, basestring) else log
        self.name = name
        self.process = subprocess.Popen(command, stdout=self.log, stderr=self.log, shell=True, preexec_fn=os.setsid)
        self.teardown_command = teardown_command
        self.assert_is_running()

    def is_alive(self):
        return self.process.poll() is None
    
    def in_os_process_list(self):
        # assumes that OS does not reuse process id immediately
        with open('/dev/null', 'w') as output:
            return 0 == subprocess.call('ps %d' % (self.process.pid), 
                                        stdout=output, 
                                        stderr=output, 
                                        shell=True)
        
    def failed(self):
        return self.process.poll() is not None and self.process.poll() != 0

    def return_code(self):
        return self.process.poll()

    def assert_is_running(self):
        # TODO: could be a more elaborate check
        for i in xrange(2):
            time.sleep(2*(i+1))
            if self.failed():
                break
            if self.is_alive():
                return
        msg = '%s is not running' % (self.name,)
        logging.error(msg)
        raise RuntimeError, msg

    def wait(self):
        self.process.wait()

    def teardown(self):
        if self.is_alive():
            if self.teardown_command:
                _run(self.teardown_command, 
                     'Teardown command of "%s"' % self.name,
                     self.log, False)
            wait_thread = threading.Thread(target=self.wait)
            wait_thread.daemon = True
            wait_thread.start()
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except OSError:
                pass 
            wait_thread.join(30)
            if self.is_alive():
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except OSError:
                    pass
            wait_thread.join(5)
            if self.is_alive() or self.in_os_process_list():
                msg = 'Could not terminate %s. Exiting.' % (self.name,)
                logging.error(msg)
                raise RuntimeError, msg
            
        
def _run(command, name, log, check_status_code):
    return_code = subprocess.call(command, stdout=log, stderr=log, shell=True)
    if check_status_code and return_code != 0:
        msg = '%s failed with return code %d. See %s for details. Exiting.' % (name, 
                                                                               return_code, 
                                                                               log.name)
        logging.error(msg)
        raise RuntimeError, msg

def _run_with_timeout(command, name, log, check_status_code, inactivity_timeout):
    process = ServiceProcess(command, name, log)
    try:
        while True:
            if not process.is_alive():
                break
            time.sleep(inactivity_timeout/10)
            log_inactivity_time = time.time() - os.path.getmtime(log.name)
            if log_inactivity_time > inactivity_timeout:
                logging.error('%s timed out (no activity for %.2f seconds', name, log_inactivity_time)
                process.teardown()
                break
        if check_status_code and process.failed():
            msg = '%s failed with return code %d. See %s for details. Exiting.' % (name, 
                                                                                   process.return_code(), 
                                                                                   log.name)
            logging.error(msg)
            raise RuntimeError, msg
    except BaseException:
        if process.is_alive():
            process.teardown()
        raise
    
def _private_run(command, name, log_file_name, check_status_code, inactivity_timeout):
    logging.debug('Running %s', name)
    with _create_log_file(log_file_name, inactivity_timeout) as log:
        if inactivity_timeout:
            _run_with_timeout(command, name, log, check_status_code, inactivity_timeout)
        else:
            _run(command, name, log, check_status_code)

def run_successfully(command, name, log_file_name, inactivity_timeout=None):
    _private_run(command, name, log_file_name, True, inactivity_timeout)

def run(command, name, log_file_name, inactivity_timeout=None):
    _private_run(command, name, log_file_name, False, inactivity_timeout)

@contextmanager
def using_services(log_dir, *services):
    processes = []
    try:
        for command, name, logname, teardown_command in services:
            log_file_name = os.path.join(log_dir, logname)
            logging.debug('Starting %s in background', name)
            processes.append(ServiceProcess(command, 
                                            name, 
                                            _create_log_file(log_file_name), 
                                            teardown_command))
    except BaseException:
        for p in reversed(processes):
            try:
                p.teardown()
            except Exception:#pylint: disable=W0703
                logging.exception('Exception during emergency teardown of %s', p.name)
        raise
    try:
        yield None
    finally:
        for p in reversed(processes):
            exceptions = []
            try:
                p.teardown()
            except BaseException, ex:#pylint: disable=W0703
                exceptions.append(ex)
                logging.exception('Exception during teardown of %s. Exiting.', p.name)
            if exceptions:
                raise RuntimeError

