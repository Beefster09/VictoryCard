import functools
import logging
import os
import re

import jinja2
import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor, SimpleTagInlineProcessor
from markdown.util import etree

from core.util import find_working_ext

log = logging.getLogger(__name__)

def find_icon(name, parent_dir='.', root='.'):
    try:
        icon = find_working_ext(
            os.path.join(root, parent_dir, name),
            '.svg', '.png', '.gif', '.bmp', '.webp', '.jpeg', '.jpg'
        )
        if icon:
            # Extension given explicitly; assume it exists
            return '/' + os.path.relpath(icon, root).replace('\\', '/')
        else:
            return None
    except TypeError as e:
        log.warning(f"Icon Finder: {e}")


class IconInsertionProcessor(InlineProcessor):
    def __init__(self, pattern, sub_missing=True, *, icon_root='.', fs_root='.', **kwargs):
        self.icon_root = icon_root
        self.fs_root = fs_root
        self.sub_missing = sub_missing
        super().__init__(pattern, **kwargs)

    def handleMatch(self, m, data):
        icon_name = m.group(1)
        icon_path = find_icon(icon_name, self.icon_root, self.fs_root)
        if not icon_path:
            if not self.sub_missing:
                return None, None, None # no substitution
            log.warning(f"No icons found for {icon_name!r}. Using placeholder")
            el = etree.Element('s')
            el.attrib['class'] = '__icon'
            el.text = icon_name
            return el, m.start(0), m.end(0)
        el = etree.Element('img')
        el.attrib['src'] = icon_path
        el.attrib['class'] = '__icon'
        return el, m.start(0), m.end(0)


class SpanInsertionProcessor(InlineProcessor):
    def handleMatch(self, m, data):
        id = m.group('id')
        classes = m.group('classes')
        el = etree.Element('span')
        if id:
            el.attrib['id'] = id
        el.attrib['class'] = classes.replace('.', ' ').strip()
        el.text = m.group('text')
        return el, m.start(0), m.end(0)


class ClassSpanProcessor(InlineProcessor):
    def __init__(self, pattern, css_class, tag='span'):
        InlineProcessor.__init__(self, pattern)
        self.css_class = css_class
        self.tag = tag

    def handleMatch(self, m, data):
        el = etree.Element(self.tag)
        el.attrib['class'] = self.css_class
        el.text = m.group(2)
        return el, m.start(0), m.end(0)


class MarkdownExtensions(Extension):
    def __init__(self, **kwargs):
        self.config = {
            "icon_root"  : ['.', "The root to use for the icon, relative to the cards.yaml"],
            "fs_root"  : ['.', "The filesystem root of the deck data"],
        }
        super().__init__(**kwargs)

    def extendMarkdown(self, md):
        md.inlinePatterns.register(  # [icon:asdf] style icons (also accepts [i:asdf])
            IconInsertionProcessor(
                r'\[(?:icon|i):([-\w]+)\]',
                **self.getConfigs()
            ),
            'bracket_icon',
            35
        )
        md.inlinePatterns.register(  # &entity; style icons
            IconInsertionProcessor(
                r'&([-\w]+);',
                False,
                **self.getConfigs()
            ),
            'entity_icon',
            100  # This doesn't work with a lower priority for some reason
        )
        md.inlinePatterns.register(  # {#id.class1.class2}[span text]
            SpanInsertionProcessor(
                r'{(?:#(?P<id>[-\w]+))?(?P<classes>(\.[-\w]+)*)}\[(?P<text>[^\[\]]*)\]'
            ),
            'span_insertion',
            35
        )
        md.inlinePatterns.register(
            SimpleTagInlineProcessor(r'(~~)(\S|\S.*\S)\1', 'del'),
            'dtilde_del',
            5
        )
        md.inlinePatterns.register(
            ClassSpanProcessor(r'(\(\()(.*?)(\)\))', 'nowrap'),
            'span_nowrap',
            50
        )


def read_safe(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        log.exception("Could not read %r", path)
    except TypeError as err:
        log.error("%s", err)
    return None

P_TAG = re.compile(r'</?p>')

def get_jinja2_env(root, *, md_config, icon_path):
    # Configure markdown
    md_extensions = md_config.get('extensions', ['smarty'])
    md_ext_conf = md_config.get('extension_configs', {})
    md_extensions.append(
        MarkdownExtensions(
            icon_root=icon_path,
            fs_root=root,
            **md_ext_conf.get('victorycard', {})
        )
    )

    # Configure Jinja2
    loader = jinja2.FileSystemLoader(root)
    env = jinja2.Environment(loader=loader)

    env.filters['icon'] = functools.partial(find_icon, parent_dir=icon_path, root=root)
    env.filters['embed'] = read_safe

    env.filters['md_paragraph'] = md_paragraph = functools.partial(
        markdown.markdown,
        extensions=md_extensions,
        extension_configs=md_ext_conf,
    )
    env.filters['md_inline'] = md_inline = lambda text: P_TAG.sub('', md_paragraph(text))
    env.filters['md_auto'] = lambda text: md_paragraph(text) if '\n' in text else md_inline(text)
    env.filters['markdown'] = env.filters[f"md_{md_config.get('default_mode', 'auto')}"]

    return env
