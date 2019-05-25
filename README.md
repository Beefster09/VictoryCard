# PyCard
Flexible card game prototyping engine

Generate printable cards for prototyping using yaml, html, css.

* Card data stored in yaml
* Html jinja2 templating
* CSS for styling

_Only tested in Python 3.7_

##  Quick Start

```
git clone https://github.com/Beefster09/pycard.git
cd pycard
pip install -r requirements.txt
python pycard.py examples/cards.yaml
```

Example output

```
$ python pycard.py examples/cards.yaml
2019-05-24 20:34:46 - Invalid value for 'copies': invalid literal for int() with base 10: 'Invalid (assumes 1)'
2019-05-24 20:34:46 - No icons found for 'bad-icon'. Using placeholder
2019-05-24 20:34:46 - 22 total cards
[I 190524 20:34:46 server:296] Serving on http://0.0.0.0:8800
2019-05-24 20:34:46 - Serving on http://0.0.0.0:8800
[I 190524 20:34:46 handlers:62] Start watching changes
2019-05-24 20:34:46 - Start watching changes
[I 190524 20:34:46 handlers:64] Start detecting changes
2019-05-24 20:34:46 - Start detecting changes
[I 190524 20:34:54 web:2246] 101 GET /livereload (127.0.0.1) 0.00ms
2019-05-24 20:34:54 - 101 GET /livereload (127.0.0.1) 0.00ms
[I 190524 20:34:55 handlers:135] Browser Connected: http://localhost:8800/cards.html
2019-05-24 20:34:55 - Browser Connected: http://localhost:8800/cards.html
```

Navigate to `localhost:8800` to see your cards. This page will automatically refresh anytime changes are made.

You can also run `python pycard.py --help` for a list of options.

## Explanation

### YAML deck data file

PyCard uses YAML to define card data. The top level contains 3 sections:

* `general` for general settings about the cards themselves
    * `deck_template`: a path to the deck template if you would like to override the default
    * `stylesheet`: the stylesheet used for the whole deck. Defaults to the same name as the yaml, but with a `css` extension.
    * `header`: a path to an optional header that gets inserted in the `<head>` of the deck template.
    Defaults to the same as the yaml, but with an `html.header` extension
    * `output`: the path to output the deck to. Defaults to the same as the yaml, but with an `html` extension
    * `icon_path`: a path (relative to the YAML file) of where icons are kept.
    * `markdown`: allows customizing markdown features
        * `default_mode`: (`paragraph`, `inline`, or `auto`. Default `auto`) specifies whether the regular `markdown` filter strips out p tags or not
        * `extensions`: A list of extensions to enable. `smarty` is enabled by default in order to get smart quotes, dashes, and ellipses.
        * `extension_configs`: A dictionary defining configurations for those extensions
* `defaults` allows you to set some defaults for each card
* `cards` - **[Required]** A yaml list of each card and its attributes. Each field is passed to the jinja2 template and is
pulled from your defaults section if missing. Some additional fields:
    * `template`: the card template to use for this specific card. Typically you will only want to set this in the `defaults` section.
    By default, the default template is the same as the yaml, but with a `html.jinja2` extension.
    Also note that this template *must* have an `html.jinja2` extension, as it will be added to the field if not present.
    See [Jinja Documentation](http://jinja.pocoo.org/docs/2.9/templates/) for details on how to create templates for each card.
    * `copies`: indicates how many copies of that card will be rendered. Set to 0 to exclude the card from rendering.
    Defaults to 1 unless otherwise specified in the `defaults` section

### Jinja2 Extensions

PyCard adds a few extensions to Jinja2:

* Markdown filter. This enables data from your yaml file to be processed by markdown first. There are a few variants:
    * `md_paragraph`: Resulting text is wrapped in `<p>` tags.
    This is good for raw multiline strings (`|` prefix) and when you might want multi-paragraph text.
    * `md_inline`: Resulting text is stripped of all paragraph tags.
    This is good for flow-style strings (single-line, quotes, or no start tokens)
    * `md_auto`: Resulting text is wrapped in `<p>` tags only if the input string includes newlines
    * `markdown` is an alias for `md_auto` by default.
* Icon search (`icon`). This will search your `icon_path` for suitable icons.

### Markdown Exensions

PyCard adds a few extensions to Markdown:

* Inline icons, either with a `[icon:whatever]` or `&whatever;` syntax. The latter will not be replaced by placeholder text.
* `~~` strikethrough
* Concise spans for things such as game keywords that you may want to style differently. (`{#id.class1.class2}[text]`)

## Credits

Inspired by https://github.com/vaemendis/hccd

Forked from https://github.com/ghostsquad/pycard (I have no intention of making a pull request)
