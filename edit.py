# -*- coding: utf-8 -*-
import argparse
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime

import dateutil.parser

os.environ['PYWIKIBOT_DIR'] = os.path.dirname(os.path.realpath(__file__))
import pywikibot

from config import config_page_name  # pylint: disable=E0611,W0614

os.environ['TZ'] = 'UTC'


class TitleblacklistExpiry:
    RANDOM_SEP = str(uuid.uuid1())

    def __init__(self, config_page_name, args):
        self.args = args

        self.site = pywikibot.Site()
        self.site.login()

        self.logger = logging.getLogger('titleblacklist_expiry')
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        self.logger.addHandler(stdout_handler)

        config_page = pywikibot.Page(self.site, config_page_name)
        self.cfg = json.loads(config_page.text)
        self.logger.debug('config: %s', json.dumps(self.cfg, indent=4, ensure_ascii=False))

    def check_expiry(self, line):
        # comment
        if re.search(r'^\s*#', line):
            return line
        line_no_comment = re.sub(r'^\s*([^#]*).*?$', r'\1', line).strip()

        # match expiry
        m = re.search(r'(?:<|<.*?\|)\s*expiry\s*=\s*([^|]*?)(?:\|[^|]*?)*?>', line_no_comment)
        if not m:
            return line

        try:
            expiry = dateutil.parser.parse(m.group(1))
        except Exception:
            self.logger.error('bad expiry: %s', m.group(1))
            line = re.sub(r'<\s*expiry\s*=\s*[^|]*?(?:\|(.*?))?>', r'<\1>', line)
            line = re.sub(r'(<.*?)\|\s*expiry\s*=\s*[^|]*?(\|.*)?>', r'\1\2>', line)
            return line

        # not expiry
        if expiry > datetime.utcnow():
            return line

        # check comment flag
        if re.search(r'(?:<|<.*?\|)\s*expirycomment\s*(?:\|[^|]*?)*?>', line_no_comment):
            return '# ' + line.strip()

        return None

    def main(self):
        self.logger.info('start')
        if not self.cfg['enable']:
            self.logger.warning('disabled')
            return

        page = pywikibot.Page(self.site, self.cfg['page'])
        lines = page.text.splitlines()
        new_text = ''
        for line in lines:
            new_line = self.check_expiry(line)
            if new_line is not None:
                new_text += new_line + '\n'
        new_text = new_text.rstrip()

        if page.text == new_text:
            self.logger.info('no changes')
            return

        summary = self.cfg['summary']
        if self.args.confirm or self.args.loglevel <= logging.DEBUG:
            pywikibot.showDiff(page.text, new_text)
            self.logger.info('summary: %s', summary)

        save = True
        if self.args.confirm:
            save = pywikibot.input_yn('Save changes for main page?', 'Y')
        if save:
            self.logger.debug('save changes')
            page.text = new_text
            page.save(summary=summary, minor=False)
        else:
            self.logger.debug('skip save')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--confirm', action='store_true')
    parser.add_argument('-d', '--debug', action='store_const', dest='loglevel', const=logging.DEBUG, default=logging.INFO)
    args = parser.parse_args()

    titleblacklist_expiry = TitleblacklistExpiry(config_page_name, args)
    titleblacklist_expiry.logger.setLevel(args.loglevel)
    titleblacklist_expiry.logger.debug('args: %s', args)
    titleblacklist_expiry.main()
