import re
import urlparse
import datetime
from django.core import urlresolvers
from django.template.defaultfilters import slugify, truncatewords

from .base import db, feeds_db, Document
from .metadata import Metadata


class FeedEntry(Document):
    collection = feeds_db.entries

    def __init__(self, *args, **kw):
        super(FeedEntry, self).__init__(*args, **kw)
        self._process()

    def _process(self, billy_db=db):
        '''Mutate the feed entry with hyperlinked entities. Add tagging
        data and other template context values, including source.
        '''
        entity_types = {'L': 'legislator',
                        'C': 'committee',
                        'B': 'bill'}
        entry = self

        summary = truncatewords(entry['summary'], 50)
        entity_strings = entry['entity_strings']
        entity_ids = entry['entity_ids']
        state = entry['state']

        _entity_strings = []
        _entity_ids = []
        _entity_urls = []
        _done = []
        if entity_strings:
            data = zip(entity_strings, entity_ids)
            data = sorted(data, key=lambda t: len(t[0]), reverse=True)
            hyperlinked_spans = []
            for entity_string, _id in data:
                if entity_string in _done:
                    continue
                else:
                    _done.append(entity_string)
                    _entity_strings.append(entity_string)
                    _entity_ids.append(_id)
                entity_type = entity_types[_id[2]]
                if entity_type == 'legislator':
                    url = urlresolvers.reverse(
                        entity_type, args=[state, _id, slugify(entity_string)])
                else:
                    url = urlresolvers.reverse(entity_type, args=[state, _id])
                _entity_urls.append(url)

                # This is tricky. Need to hyperlink the entity without mangling
                # other previously hyperlinked strings, like Fiona Ma and
                # Mark Leno.
                matches = re.finditer(entity_string, summary)
                replacer = lambda m: '<a href="%s">%s</a>' % (url, entity_string)
                for match in matches:

                    # Only hyperlink if no previous hyperlink has been added
                    # in the same span.
                    if any((start <= n < stop) for n in match.span()
                           for (start, stop) in hyperlinked_spans):
                        continue

                    summary = re.sub(entity_string, replacer, summary)
                    hyperlinked_spans.append(match.span())

            # For entity_strings, us modelinstance.display_name strings.
            _entity_display_names = []
            for _id in _entity_ids:
                collection_name = entity_types[_id[2]] + 's'
                collection = getattr(billy_db, collection_name)
                instance = collection.find_one(_id)
                string = instance.display_name()
                _entity_display_names.append(string)

            entity_data = zip(_entity_strings, _entity_display_names,
                              _entity_ids, _entity_urls)

            entry['summary'] = summary
            entry['entity_data'] = entity_data

        entry['id'] = entry['_id']
        urldata = urlparse.urlparse(entry['link'])
        entry['source'] = urldata.scheme + urldata.netloc
        entry['host'] = urldata.netloc

        # Prevent obfuscation of `published` method in template rendering.
        del entry['published']

    def published(self):
        return datetime.datetime.fromtimestamp(self['published_parsed'])

    @property
    def metadata(self):
        return Metadata.get_object(self['state'])
