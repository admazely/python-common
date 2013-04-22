import os
import tempfile

def _try_create_desired_file(mode, bufsize, dir_path, desired_name, delete):
    # try to match desired_name directly 
    # most of this code is adapted from the tempfile source
    # pylint: disable=W0212
    if 'b' in mode:
        flags = tempfile._bin_openflags
    else:
        flags = tempfile._text_openflags
    fd = os.open(os.path.join(dir_path, desired_name), flags, 0600)
    tempfile._set_cloexec(fd)
    file_name = os.path.abspath(os.path.join(dir_path, desired_name))
    file_handle = os.fdopen(fd, mode, bufsize)
    return tempfile._TemporaryFileWrapper(file_handle, file_name, delete)

def get_temp_file(mode='w+b', bufsize=-1, desired_name='', in_dir='', delete=None):
    # normalize dir part
    if delete is None:
        delete = os.path.samefile(in_dir, tempfile.gettempdir())
    if os.path.dirname(desired_name):
        in_dir = os.path.join(in_dir, os.path.dirname(desired_name))
        desired_name = os.path.basename(desired_name)
    if not os.path.exists(in_dir):
        get_temp_folder(in_dir)
    try:
        result = _try_create_desired_file(mode, bufsize, in_dir, desired_name, delete)
    except OSError, e:
        if e.errno != tempfile._errno.EEXIST: # pylint: disable=W0212
            raise
        prefix, _, suffix = desired_name.partition('.') 
        result = tempfile.NamedTemporaryFile(mode=mode, 
                                             bufsize=bufsize,
                                             suffix='.' + suffix, 
                                             prefix=prefix, 
                                             dir=in_dir, 
                                             delete=delete)
    return result

def _try_create_desired_folder(dir_path, desired_name):
    # much simpler than in the case of files, as tempfile doesn't wrap folders
    # pylint: disable=W0212
    full_path = os.path.join(dir_path, desired_name)
    os.mkdir(full_path)
    return full_path

def get_temp_folder(desired_name='', in_dir=''):
    def ensure_named_folder_exist(base, f):
        try:
            return _try_create_desired_folder(base, f)
        except OSError, e:
            if e.errno != tempfile._errno.EEXIST:# pylint: disable=W0212
                raise
            return None
    # normalize dir part
    if os.path.dirname(desired_name):
        in_dir = os.path.join(in_dir, os.path.dirname(desired_name))
        desired_name = os.path.basename(desired_name)
    base_folder = in_dir
    dirs_to_create = []
    while not os.path.exists(base_folder):
        base_folder, segment = os.path.split(base_folder)
        dirs_to_create.append(segment)
    for folder in reversed(dirs_to_create):
        ensure_named_folder_exist(base_folder, folder)
        base_folder = os.path.join(base_folder, folder)
    result = ensure_named_folder_exist(base_folder, desired_name) or \
             tempfile.mkdtemp(prefix=desired_name, dir=base_folder)
    return result

