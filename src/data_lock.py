"""Cooperative local process locks; files stay in place, OS locks release on exit."""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path


class DataBusyError(OSError):
    pass


def marker_paths(database, scans):
    return [Path(str(p) + '.restore-in-progress') for p in (database, scans)]


def check_recovery(database, scans):
    if any(p.exists() for p in marker_paths(database, scans)):
        raise DataBusyError('An interrupted restore needs recovery; see the local backup guide')


@contextmanager
def data_lock(database, scans, purpose='writer'):
    """Lock both resources, so sharing either path cannot bypass coordination."""
    with ExitStack() as stack:
        for resource in sorted({Path(database).resolve(), Path(scans).resolve()}, key=str):
            path = Path(str(resource) + '.storeroom-' + purpose + '.lock')
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = stack.enter_context(path.open('a+b'))
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise DataBusyError('StoreRoom data is busy; wait for backup or stop the app before restore') from error
            # Closing the descriptor releases the lock, including on errors.
        check_recovery(database, scans)
        yield
