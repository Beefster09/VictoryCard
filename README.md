# PyCard
Un-opinionated card game prototyping engine

Generate printable cards for prototyping using yaml, html, css.

* Card data stored in yaml
* Html jinja2 templating
* CSS for styling

_Only tested in Python 3.7_

###  Quick Start

```
git clone https://github.com/Beefster09/pycard.git
cd pycard
pip install -r requirements.txt
python pycard.py examples/cards.yaml
```

Example output

```
$ python pycard.py examples
[I 171010 19:30:34 server:283] Serving on http://127.0.0.1:8800
2017-10-10 19:30:34 - Serving on http://127.0.0.1:8800
[I 171010 19:30:34 handlers:60] Start watching changes
2017-10-10 19:30:34 - Start watching changes
[I 171010 19:30:34 handlers:62] Start detecting changes
2017-10-10 19:30:34 - Start detecting changes
2017-10-10 19:30:34 - Created file: examples/index.html
2017-10-10 19:30:34 - Modified directory: examples
```

Navigate to `localhost:8800` to see your cards. This page will automatically refresh anytime changes are made.

You can also run `python pycard.py --help` for a list of options.

See `examples` directory to setup your files

### Explanation

#### Files Explained

These files should be in the directory specified by `-p` or `--path` option

```diff
- Important
index.html file is created/overwritten in the assets path!
```

Note: You can change the prefix with the `-x` or `--prefix` commandline option. Default is `_card`.

* YAML file entry point (`cards.yaml` in the example) - **[Required]** is the card data. The top level contains 3 sections:
    * `general` for general settings about the cards themselves
        * `template`: a path to the deck template if you would like to override the default
        * `stylesheet`: the stylesheet used for the whole deck. Defaults to the same name as the yaml, but with a `css` extension.
        * `header`: a path to an optional header that gets inserted in the `<head>` of the deck template.
        Defaults to the same as the yaml, but with an `html.header` extension
        * `output`: the path to output the deck to. Defaults to the same as the yaml, but with an `html` extension
        * `markdown`: allows customizing markdown
            * `default_mode`: (`paragraph`, `inline`, or `auto`. Default `auto`) specifies whether the regular `markdown` filter strips out p tags or not
    * `defaults` allows you to set some defaults for each card
    * `cards` - **[Required]** A yaml list of each card and its attributes. Each field is passed to the jinja2 template and is
    pulled from your defaults section if missing. Some additional fields:
        * `template`: the card template to use for this specific card. Typically you will only want to set this in the `defaults` section.
        By default, the default template is the same as the yaml, but with a `html.jinja2` extension.
        Also note that this template *must* have an `html.jinja2` extension, as it will be added to the field if not present.
        See [Jinja Documentation](http://jinja.pocoo.org/docs/2.9/templates/) for details on how to create templates for each card.
        * `copies`: indicates how many copies of that card will be rendered. Set to 0 to exclude the card from rendering.
        Defaults to 1 unless otherwise specified in the `defaults` section

Jinja2 card templates now support markdown as a filter:

* `md_paragraph`: Resulting text is wrapped in `<p>` tags
* `md_inline`: Resulting text is not wrapped in `<p>` tags (good for inline values)
* `md_auto`: Resulting text is wrapped in `<p>` tags only if the input string includes newlines
* `markdown` is an alias for `md_auto` by default.

### Credits

Inspired by https://github.com/vaemendis/hccd

Forked from https://github.com/ghostsquad/pycard
