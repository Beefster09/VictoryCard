import functools
import inspect
import os.path

def get_first(mapping, *attrs, default=None):
    for key in attrs:
        if key in mapping:
            return mapping[key]
    else:
        return default


class TransactionDelegate:
    __slots__ = '_delegate_', '_overrides_'

    def __init__(self, delegate):
        self._delegate_ = delegate
        self._overrides_ = {}

    def __getattr__(self, attr):
        if attr in self._overrides_:
            return self._overrides_[attr]
        else:
            value = getattr(self._delegate_, attr)
            if inspect.ismethod(value):
                # Avoid leaking the underlying self from the bound method
                # Properties will, unfortunately, leak and there is nothing I can do about it.
                return functools.partial(getattr(type(self._delegate_), attr), self)
            else:
                return value

    def __setattr__(self, attr, value):
        if attr in TransactionDelegate.__slots__:
            super().__setattr__(attr, value)
        else:
            self._overrides_[attr] = value

    def commit(self):
        for attr, value in self._overrides_.items():
            setattr(self._delegate_, attr, value)


def transactional(method):
    @functools.wraps(method)
    def _method(self):
        transaction = TransactionDelegate(self)
        try:
            result = method(transaction)
        except:
            raise
        else:
            transaction.commit()
            return result

    return _method


def find_working_ext(base, *extensions):
    if os.path.splitext(base)[1]:
        # Extension given explicitly; assume it exists
        return base
    for ext in extensions:
        candidate = base + ext
        if os.path.isfile(candidate):
            return candidate
    else:
        return None
