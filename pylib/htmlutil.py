from bs4 import BeautifulSoup, Comment


def cleanup_html(html_code, tokenizer, max_attr_length=32, target_length=512, n_list_options=5):
    def remove_trivial_attributes(soup):
        for tag in soup.find_all():
            tag.attrs.pop('style', None)
            tag.attrs.pop('class', None)

    def remove_trivial_elements(soup):
        for tag in soup.select('script, meta, style, svg, img, iframe, media, br'):
            tag.extract()

    def remove_long_attributes(soup):
        for tag in soup.find_all():
            for k in list(tag.attrs.keys()):
                if len(tag.attrs[k]) > max_attr_length:
                    tag.attrs.pop(k, None)

    def remove_empty_tags(soup):
        for tag in soup.find_all():
            if len(tag.get_text(strip=True)) == 0:
                tag.extract()

    def keep_minimal_attributes(soup):
        for tag in soup.find_all():
            for k in list(tag.attrs.keys()):
                if k not in {'id', 'name', 'type', 'value', 'for'}:
                    tag.attrs.pop(k, None)

    def remove_comments(soup):
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

    def cleanup_list_options(soup, n_options=n_list_options):
        for tag in soup.find_all(['select', 'ol', 'ul']):
            options = tag.find_all(['option', 'li'], recursive=True)

            if len(options) > n_options:
                for o in options[n_options:]:
                    o.extract()

                options[n_options - 1].string = '...'

    soup = BeautifulSoup(html_code, 'html.parser')

    cleanup_functions = [
        remove_trivial_elements,
        remove_long_attributes,
        remove_empty_tags,
        remove_trivial_attributes,
        keep_minimal_attributes,
        remove_comments,
        cleanup_list_options,
    ]

    for func in cleanup_functions:
        cleaned_code = str(soup.prettify())
        n_tokens = len(tokenizer.encode(cleaned_code))

        if n_tokens <= target_length:
            break

        func(soup)
    else:
        cleaned_code = str(soup.prettify())
        n_tokens = len(tokenizer.encode(cleaned_code))

    return cleaned_code, n_tokens
