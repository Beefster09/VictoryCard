import functools
import logging
import re

import jinja2
import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor, SimpleTagInlineProcessor
from markdown.util import etree

log = logging.getLogger(__name__)

def find_icon(name, parent_dir='.', root='.'):
    try:
        if os.path.splitext(name)[1]:
            # Extension given explicitly; assume it exists
            return '/' + os.path.relpath(os.path.join(root, parent_dir, name), root).replace('\\', '/')
        else:
            # Try to find a working image with that base name
            for ext in ['.svg', '.webp', '.png', '.gif', '.bmp', '.jpeg', '.jpg']:
                candidate = os.path.join(root, parent_dir, name + ext)
                if os.path.isfile(candidate):
                    return '/' + os.path.relpath(candidate, root).replace('\\', '/')
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


class PyCardExtension(Extension):
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


def get_jinja2_env():
    # Configure markdown
    md_extensions = general['markdown'].get('extensions', ['smarty'])
    md_ext_conf = general['markdown'].get('extension_configs', {})
    md_extensions.append(
        PyCardExtension(
            icon_root=general['icon_path'],
            fs_root=source_dir,
            **md_ext_conf.get('pycard', {})
        )
    )

    # Configure Jinja2
    loader = jinja2.FileSystemLoader(source_dir)
    env = jinja2.Environment(loader=loader)

    env.filters['icon'] = functools.partial(find_icon, parent_dir=general['icon_path'], root=source_dir)

    env.filters['md_paragraph'] = md_paragraph = functools.partial(
        markdown.markdown,
        extensions=md_extensions,
        extension_configs=md_ext_conf,
    )
    env.filters['md_inline'] = md_inline = lambda text: P_TAG.sub('', md_paragraph(text))
    env.filters['md_auto'] = lambda text: md_paragraph(text) if '\n' in text else md_inline(text)
    env.filters['markdown'] = env.filters[f"md_{general['markdown'].get('default_mode', 'auto')}"]

    return env
