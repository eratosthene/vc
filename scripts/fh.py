#!/usr/bin/env python

from bs4 import BeautifulSoup
import argparse
from pathlib import Path
import re

def strip_css(tag):
    retval = False
    if tag.name == 'link' and tag.has_attr('href'):
        if not re.search(r'(?:bootstrap.min.css|printview.css)', str(tag['href'])):
            retval = True
    return retval

parser = argparse.ArgumentParser(description='Filter static html site')
parser.add_argument('-f', '--folder', help='Folder containing files to filter')

args = parser.parse_args()

rootdir = Path(args.folder)
filelist = [f for f in rootdir.glob('**/*.html') if f.is_file()]

for filepath in filelist:
    print('Reading from ' + str(filepath))
    soup = BeautifulSoup(filepath.read_text(), 'lxml')
    for l in soup.find_all(strip_css):
        print("Stripping " + str(l))
        l.decompose()
    for s in soup.find_all('script'):
        print("Stripping " + str(s))
        s.decompose()
    with filepath.open("w", encoding="utf-8") as f:
        f.write(soup.prettify())


