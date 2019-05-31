import argparse
import functools
import inspect
import logging
import os
import re
import time
from datetime import datetime

import jinja2
import markdown
import yaml

from core.extensions import get_jinja2_env

log = logging.getLogger(__name__)


FULL_DECK_TEMPLATE = os.path.join(os.path.dirname(__file__), 'deck_template.html.jinja2')


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
                return functools.partial(getattr(type(self._delegate_), attr), self._delegate_)
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


class SourceFile:
    def __init__(self, path):
        self.path = path
        self._mtime = os.stat(path).st_mtime
        self.base, self.ext = os.path.splitext(os.path.basename(path))
        self.dir = os.path.abspath(os.path.dirname(path))

    @property
    def dirty(self):
        return os.stat(self.path).st_mtime > self._mtime

    def refresh(self):
        mtime = os.stat(self.path).st_mtime
        is_dirty = mtime > self._mtime
        self._mtime = mtime
        return is_dirty


class Deck:
    def __init__(self, source):
        self.source = SourceFile(source)

        self._interpret_source()

    @transactional
    def _interpret_source(self):
        self.sub_sources = {}

        source = self.source.path

        with open(source) as yf:
            deck_info = yaml.safe_load(yf)

        general = deck_info.get('general', {})
        base = general.get('name', self.source.base)
        self._sub_source(
            general,
            'stylesheet', 'styles', 'css', 'style',
            default=(base + '.css')
        )
        self._sub_source(
            general,
            'header',
            default=(base + '.html.header')
        )
        self._sub_source(
            general,
            'template',
            default=(base + '.html.header'),
            required=True,
        )
        for (attr, *aliases), default in [
            (['output', 'destination', 'dest'], base + '.html'),
            (['icon_path', 'icon_dir', 'icon_root'], '.'),
            (['card_spacing', 'spacing'], '2pt'),
        ]:
            setattr(self, attr, get_first(general, attr, *aliases, default=default))

        defaults = {
            'copies': 1,
            **deck_info.get('default', {})
        }

        cards = deck_info['cards']
        if isinstance(cards, dict):
            self.cards = [
                {**defaults, **card, '_id': key}
                for key, card in cards.items()
            ]
        else:
            self.cards = [
                {**defaults, **card, '_id': f"card{index}"}
                for index, card in enumerate(cards, 1)
            ]
        self.card_index = {
            card['_id']: card
            for card in self.cards
        }

    def _sub_source(self, config, attribute, *aliases, default=None, required=False):
        value = get_first(config, attribute, *aliases)
        if value:
            try:
                self.sub_sources[attribute] = SourceFile(value)
            except OSError:
                if required:
                    raise
