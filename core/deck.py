import argparse
import functools
import logging
import os
import re
import time
from datetime import datetime

import jinja2
import markdown
import yaml

from core.extensions import get_jinja2_env
from core.util import dict_merge, find_working_ext, get_first, transactional

log = logging.getLogger(__name__)


FULL_DECK_TEMPLATE = os.path.join(os.path.dirname(__file__), 'deck_template.html.jinja2')


class DeckError(Exception):
    pass

class CyclicDependency(DeckError):
    pass

class MissingDependency(DeckError):
    pass


class _SourceFile:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.dir, self.name = os.path.split(self.path)
        self.base, self.ext = os.path.splitext(self.name)
        self._mtime = os.path.getmtime(self.path)

    @property
    def dirty(self):
        return os.path.getmtime(self.path) > self._mtime

    def refresh(self):
        mtime = os.path.getmtime(self.path)
        is_dirty = mtime > self._mtime
        self._mtime = mtime
        return is_dirty


def sanitize_copies(copies, default=1):
    try:
        return max(int(copies if copies is not None else default), 0)
    except ValueError as err:
        log.warning(f"Invalid value for 'copies': {err.args[0]}")
        return default


class _Card(dict):
    def __init__(self, id, defaults={}, data={}):
        self.id = id
        self.copies = sanitize_copies(data.pop('copies', None), defaults.get('copies'))
        super().__init__({**defaults, **data})

    @property
    def skip(self):
        return self.copies <= 0


def _parse_definitions(path, *child_paths):
    with open(path) as yf:
        definitions = yaml.safe_load(yf)
    if not isinstance(definitions, dict):
        raise DeckError(f"Invalid Deck Definition: {path!r} (file must be a YAML dictionary)")
    if 'extends' in definitions:
        parent_path = os.path.join(os.path.dirname(path), definitions['extends'])
        if os.path.samefile(parent_path, path):
            raise CyclicDependency(
                f"{path!r} wants to extend {parent_path!r}, but they are the same file"
            )
        for child_path in child_paths:
            if os.path.samefile(parent_path, child_path):
                raise CyclicDependency(
                    f"{path!r} wants to extend {parent_path!r},"
                    f" but {parent_path!r} already directly or indirectly extends {path!r}"
                )
        try:
            parent_defs, parent_deps = _parse_definitions(parent_path, path, *child_paths)
        except FileNotFoundError:
            raise MissingDependency(parent_path)
        else:
            return (
                dict_merge(parent_defs, definitions, ignore_keys={'extends'}),
                [parent_path, *parent_deps]
            )
    else:
        return definitions, []


class Deck:
    def __init__(self, source):
        self.source = _SourceFile(source)

        self._interpret_source()

    @transactional
    def _interpret_source(self):
        self.sub_sources = {}

        deck_info, deps = _parse_definitions(self.source.path)
        self.hierarchy = [_SourceFile(path) for path in deps]

        self.title = deck_info.get('title')

        general = deck_info.get('general', {})

        output_basename = get_first(
            general,
            'output', 'destination', 'dest',
            default=(self.source.base + '.html')
        )
        self.output = os.path.join(self.source.dir, output_basename)

        for (attr, *aliases), default in [
            (['icon_path', 'icon_dir', 'icon_root'], '.'),
            (['card_spacing', 'spacing'], '2pt'),
            (['embed_styles', 'embed_css'], True),
            (['markdown', 'md_config', 'md', 'md_conf', 'markdown_config'], {}),
        ]:
            setattr(self, attr, get_first(general, attr, *aliases, default=default))

        self._sub_source(  # TODO: support for LESS, Stylus, SCSS, etc...
            general,
            'stylesheet', 'styles', 'css', 'style',
            default=(self.source.base + '.css'),
        )
        self._sub_source(
            general,
            'header',
            default=(self.source.base + '.html.header')
        )
        self._sub_source(
            general,
            'template',
            default=self.source.base,
            required=True,
            extensions=['.html.jinja2', '.jinja2', '.hj2', '.vct']
        )

        defaults = deck_info.get('default', {})
        defaults['copies'] = sanitize_copies(defaults.get('copies'), 1)

        cards = deck_info['cards']
        if isinstance(cards, dict):
            self.cards = [
                _Card(key, defaults, card)
                for key, card in cards.items()
            ]
        else:
            self.cards = [
                _Card(f"card{index}", defaults, card)
                for index, card in enumerate(cards, 1)
            ]
        self.card_index = {
            card.id: card
            for card in self.cards
        }

    def _sub_source(self,
                    config, attribute, *aliases,
                    default=None,
                    required=False,
                    extensions=None):
        value = get_first(config, attribute, *aliases) or default
        base = os.path.join(self.source.dir, value)
        if extensions:
            path = find_working_ext(base, *extensions)
            if path is None:
                if required:
                    raise MissingDependency(
                        f"Cannot find a suitable file for {value!r} "
                        f"({attribute}, in {self.source.name!r})"
                    )
                return
        else:
            path = base
        try:
            self.sub_sources[attribute] = _SourceFile(path)
        except OSError:
            if required:
                raise MissingDependency(
                    f"{attribute} deck source {value!r} is missing for {self.source.name!r}"
                )

    @property
    def header(self):
        return self.sub_sources.get('header')

    @property
    def stylesheet(self):
        return self.sub_sources.get('stylesheet')

    @property
    def template(self):
        return self.sub_sources['template']

    def render(self):
        env = get_jinja2_env(
            root=self.source.dir,
            md_config=self.markdown,
            icon_path=self.icon_path
        )
        now = datetime.now()
        template = env.get_template(os.path.relpath(self.template.path, self.source.dir))

        rendered_cards = []
        for card in self.cards:
            if card.skip:
                continue

            rendered = template.render(
                card,
                __card_data=card,
                __time=now
            )
            rendered_cards += [rendered] * card.copies

        log.info("Rendered %d total cards", len(rendered_cards))

        if self.header:
            with open(self.header.path) as f:
                custom_header = f.read()
        else:
            custom_header = None

        with open(FULL_DECK_TEMPLATE) as tf:
            global_template = env.from_string(tf.read())

        with open(self.output, "w") as of:
            of.write(
                global_template.render(
                    rendered_cards=rendered_cards,
                    stylesheet=self.stylesheet.path,
                    custom_header=custom_header,
                    absolute_to_relative=os.path.relpath(
                        os.path.dirname(self.output),
                        self.source.dir
                    ),
                    card_spacing=self.card_spacing,
                    embed_styles=self.embed_styles,
                    deck_title=self.title,
                )
            )

    def sync(self):
        if self.source.refresh() or any(dep.refresh() for dep in self.hierarchy):
            self._interpret_source()
            self.render()
        else:
            dirty = False
            for dep in self.sub_sources.values():
                dirty |= dep.refresh()
            if dirty:
                self.render()

    def is_dependency(self, path):
        return (
            path.endswith(self.source.name)
            or any(path.endswith(dep.name) for dep in self.hierarchy)
            or any(path.endswith(dep.name) for dep in self.sub_sources.values())
        )
