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


def dict_merge(base, overrides, ignore_keys=()):
    result = {}
    for key in {*base, *overrides} - {key.split('.', 1)[0] for key in ignore_keys}:
        if key not in overrides:
            result[key] = base[key]
            continue
        elif key not in base:
            result[key] = overrides[key]
            continue

        b_val = base[key]
        o_val = overrides[key]
        if isinstance(o_val, type(b_val)):
            if isinstance(b_val, dict):
                result[key] = dict_merge(
                    b_val, o_val,
                    {
                        key.split('.', 1)[1]
                        for key in ignore_keys
                        if '.' in key
                    }
                )
            elif isinstance(b_val, list):
                result[key] = [*b_val, *o_val]
            else:
                result[key] = o_val
        else:
            result[key] = o_val
    return result
