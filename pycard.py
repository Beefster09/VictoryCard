import argparse
import functools
import logging
import os
import re
import time
from datetime import datetime

import jinja2
import livereload
import markdown
import yaml
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor
from markdown.util import etree

log = logging.getLogger('pycard')


VERSION = '0.3.1'

FULL_DECK_TEMPLATE = os.path.join(os.path.dirname(__file__), 'cards.html.jinja2')


def find_icon(name, parent_dir='.', root='.'):
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


class IconInsertionProcessor(InlineProcessor):
    def __init__(self, pattern, sub_missing=True, *, icon_root='.', fs_root='.', **kwargs):
        self.icon_root = icon_root
        self.fs_root = fs_root
        self.sub_missing = sub_missing
        super().__init__(pattern, **kwargs)

    def handleMatch(self, m, data):
        icon_name = m.group(1)
        icon_path = find_icon(icon_name)
        if not icon_path:
            if not self.sub_missing:
                return None, None, None # no substitution
            log.warning(f"No icons found for {icon_name!r}. Using placeholder")
            el = etree.Element('del')
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
            100
        )
        md.inlinePatterns.register(  # {#id.class1.class2}
            SpanInsertionProcessor(
                r'{(?:#(?P<id>[-\w]+))?(?P<classes>(\.[-\w]+)*)}\[(?P<text>[^\[\]]*)\]'
            ),
            'span_insertion',
            100
        )


P_TAG = re.compile(r'</?p>')


def render_from_yaml(yaml_path):
    base, ext = os.path.splitext(os.path.basename(yaml_path))
    source_dir = os.path.abspath(os.path.dirname(yaml_path))
    now = datetime.now()

    jinja_loader = jinja2.FileSystemLoader(source_dir)
    jinja_env = jinja2.Environment(loader=jinja_loader)

    with open(yaml_path) as yf:
        deck_info = yaml.safe_load(yf)

    general = {
        'template': FULL_DECK_TEMPLATE,
        'stylesheet': base + '.css',
        'header': base + '.html.header',
        'output': base + '.html',
        'icon_path': '.',
        'markdown': {},
        **deck_info.get('general', {})
    }

    jinja_env.filters['icon'] = functools.partial(find_icon, parent_dir=general['icon_path'], root=source_dir)

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

    jinja_env.filters['md_paragraph'] = md_paragraph = functools.partial(
        markdown.markdown,
        extensions=md_extensions,
        extension_configs=md_ext_conf,
    )
    jinja_env.filters['md_inline'] = md_inline = lambda text: P_TAG.sub('', md_paragraph(text))
    jinja_env.filters['md_auto'] = lambda text: md_paragraph(text) if '\n' in text else md_inline(text)
    jinja_env.filters['markdown'] = jinja_env.filters[f"md_{general['markdown'].get('default_mode', 'auto')}"]


    defaults = {
        'template': base + '.html.jinja2',
        'copies': 1,
        **deck_info.get('default', {})
    }

    template_cache = {}
    def get_template(name):
        nonlocal template_cache
        if not name.endswith('.html.jinja2'):
            name += '.html.jinja2'
        if name in template_cache:
            return template_cache[name]
        else:
            template = jinja_env.get_template(name)
            template_cache[name] = template
            return template

    rendered_cards = []
    for card in deck_info['cards']:
        try:
            copies = int(card.pop('copies', defaults['copies']) or 1)
        except ValueError as err:
            log.warning("Invalid value for 'copies': {}".format(err.args[0]))
            copies = 1

        if copies <= 0:
            continue

        template = get_template(card.pop('template', defaults['template']))
        rendered = template.render(
            {**defaults, **card},
            __card_data=card,
            __time=now
        )
        rendered_cards += [rendered] * copies

    log.info("%d total cards", len(rendered_cards))

    header_path = os.path.join(source_dir, general['header'])
    if os.path.exists(header_path):
        with open(header_path) as f:
            custom_header = f.read()
    else:
        custom_header = None

    with open(general['template']) as tf:
        global_template = jinja2.Template(tf.read())

    abs_output_path = os.path.join(source_dir, general['output'])
    with open(abs_output_path, "w") as of:
        of.write(
            global_template.render(
                rendered_cards=rendered_cards,
                stylesheet=general['stylesheet'],
                custom_header=custom_header,
                absolute_to_relative=os.path.relpath(os.path.dirname(abs_output_path)),
            )
        )
    return source_dir, general['output']


def parse_args():
    parser = argparse.ArgumentParser(
        description="HTML + CSS card template renderer"
    )

    parser.add_argument(
        'path',
        type=os.path.abspath,
        metavar='PATH',
        help="path to assets"
    )

    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8800,
        metavar='PORT',
        help="port to use for live reloaded page",
    )

    parser.add_argument(
        '--host',
        help="host address to bind to",
        default='0.0.0.0',
        metavar='ADDRESS'
    )

    parser.add_argument(
        '-1', '--no-server',
        dest='run_server',
        action='store_false',
        help="Do not start up a server that watches the directory"
    )

    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    args = parse_args()

    source, output = render_from_yaml(args.path)

    if args.run_server:
        server = livereload.Server()
        server.watch(
            f'{source}/*',
            lambda: render_from_yaml(args.path),
            ignore=lambda path: path.endswith('.html')
        )
        server.serve(root=source, port=args.port, host=args.host)


if __name__ == "__main__":
    main()
