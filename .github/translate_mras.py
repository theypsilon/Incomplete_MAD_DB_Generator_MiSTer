#!/usr/bin/env python3
# Copyright (c) 2021 José Manuel Barroso Galindo <theypsilon@gmail.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import subprocess
from pathlib import Path
import configparser
from inspect import currentframe, getframeinfo
import itertools
import os
import io
import hashlib
import distutils.util
from datetime import datetime
import difflib
import shutil
import time
import json
import xml.etree.cElementTree as ET
import urllib.request
from xml.dom import minidom

def main():

    print('START!')

    run_succesfully('git clone https://github.com/theypsilon/BetaDistrib.git')
    run_succesfully('git clone https://github.com/jotego/jtbin.git')
    run_succesfully('git clone https://github.com/MrX-8B/MiSTer-Arcade-PenguinKunWars.git')
    run_succesfully('git clone https://github.com/MrX-8B/MiSTer-Arcade-Gyruss.git')

    mister_devel_mras = list(MraFinder('BetaDistrib/_Arcade').find_all_mras())
    jtbin_mras = list(MraFinder('jtbin/mra').find_all_mras())
    penguinkunwars_mras = list(MraFinder('MiSTer-Arcade-PenguinKunWars/releases').find_all_mras())
    gyruss_mras = list(MraFinder('MiSTer-Arcade-Gyruss/releases').find_all_mras())

    run_succesfully('git clone https://github.com/theypsilon/MAD_Database_MiSTer.git')

    run_succesfully('rm -rf MAD_Database_MiSTer/mad || true')
    run_succesfully('mkdir -p MAD_Database_MiSTer/mad')
    mra_reader = MraReader('MAD_Database_MiSTer/mad')
    for mra in (mister_devel_mras + jtbin_mras + penguinkunwars_mras + gyruss_mras):
        print(str(mra))
        mra_reader.translate_mra(mra)

    run_succesfully("""
        cd MAD_Database_MiSTer
        git add mad
        git commit -m "%s"
        git push "https://theypsilon:%s@github.com/theypsilon/MAD_Database_MiSTer.git" main
    """ % (datetime.now().strftime("%Y/%m/%d %H:%M:%S"), os.getenv('REPOSITORY_DISPATCH_THEYPSILON', 'ooops')))

    print('Done.')

def translate_mame_rotation(rot):
    if rot == 'rot0':
        return 0
    elif  rot == 'rot90':
        return 90
    elif  rot == 'rot180':
        return 180
    elif  rot == 'rot270':
        return 270
    else:
        return None

def translate_mad_rotation(rot):
    if rot == 'horizontal':
        return 0
    elif  rot == 'vertical (cw)':
        return 90
    elif  rot == 'horizontal (180)':
        return 180
    elif  rot == 'vertical (ccw)':
        return 270
    else:
        return None

class MraFinder:
    def __init__(self, dir):
        self._dir = dir

    def find_all_mras(self):
        return sorted(self._scan(self._dir), key=lambda mad: mad.name.lower())

    def _scan(self, directory):
        for entry in os.scandir(directory):
            if entry.is_dir(follow_symlinks=False):
                yield from self._scan(entry.path)
            elif entry.name.lower().endswith(".mra"):
                yield Path(entry.path)

def read_mra_fields(mra_path, tags):
    fields = { i : '' for i in tags }

    try:
        context = ET.iterparse(str(mra_path), events=("start",))
        for event, elem in context:
            elem_tag = elem.tag.lower()
            if elem_tag in tags:
                tags.remove(elem_tag)
                elem_value = elem.text
                if isinstance(elem_value, str):
                    fields[elem_tag] = elem_value
                if len(tags) == 0:
                    break
    except Exception as e:
        print("Line %s || %s (%s)" % (lineno(), e, mra_path))

    return fields

def lineno():
    return getframeinfo(currentframe().f_back).lineno

def is_path_alternative(mra_path):
    return any(p.name.lower() == '_alternatives' for p in mra_path.parents)

class MraReader:
    def __init__(self, targetdir):
        self._targetdir = targetdir

    def translate_mra(self, mra):
        fields = read_mra_fields(mra, [
            'name',
            'setname',
            'rotation',
            'flip',
            'resolution',
            'cocktail',
            'region',
            'year',
            'category',
            'manufacturer',
            'homebrew',
            'bootleg',
            'enhancements',
            'translations',
            'joystick',
            'hacks',
            'best_of',
            'platform',
            'series',
            'num_buttons',
            'num_controllers',
            'num_monitors',
            'move_inputs',
            'special_controls',
        ])

        mra_str = str(mra)

        if fields['homebrew'] == '' and ('hbmame' in mra_str.lower() or '[hb]' in mra_str.lower()):
            fields['homebrew'] = 'yes'

        if fields['bootleg'] == '' and ('bootleg' in mra_str.lower() or '[bl]' in mra_str.lower()):
            fields['bootleg'] = 'yes'

        fields['alternative'] = "yes" if is_path_alternative(mra) else "no"

        fields['move_inputs'] = 'joystick %s' % fields['joystick'] if fields['joystick'] != '' else ''

        doc = ET.Element("misterarcadedescription")

        set_if_not_empty(doc, fields, 'setname')
        set_if_not_empty(doc, fields, 'alternative')
        set_if_not_empty(doc, fields, 'name')
        set_if_not_empty(doc, fields, 'flip')
        set_if_not_empty(doc, fields, 'resolution')
        set_if_not_empty(doc, fields, 'cocktail')
        set_if_not_empty(doc, fields, 'region')
        set_if_not_empty(doc, fields, 'year')
        set_if_not_empty(doc, fields, 'category')
        set_if_not_empty(doc, fields, 'manufacturer')
        set_if_not_empty(doc, fields, 'homebrew')
        set_if_not_empty(doc, fields, 'bootleg')
        set_if_not_empty(doc, fields, 'enhancements')
        set_if_not_empty(doc, fields, 'translations')
        set_if_not_empty(doc, fields, 'hacks')
        set_if_not_empty(doc, fields, 'best_of')
        set_if_not_empty(doc, fields, 'platform')
        set_if_not_empty(doc, fields, 'series')
        set_if_not_empty(doc, fields, 'num_buttons')
        set_if_not_empty(doc, fields, 'num_controllers')
        set_if_not_empty(doc, fields, 'num_monitors')
        set_if_not_empty(doc, fields, 'move_inputs')
        set_if_not_empty(doc, fields, 'special_controls')

        parts = mra_str.split('/')
        base = parts[0] + '/' + parts[1] + '/'
        target_path = self._targetdir + "/" + mra_str.replace(base, '').replace('.mra', '.mad')
        os.makedirs(str(Path(target_path).parent), exist_ok=True)

        xmlstr = minidom.parseString(ET.tostring(doc)).toprettyxml(indent="   ")
        with open(target_path, "w") as f:
            f.write(xmlstr)

def create_orphan_branch(branch):
    run_succesfully('git checkout -qf --orphan %s' % branch)
    run_succesfully('git rm -rf .')

def force_push_file(file_name, branch):
    run_succesfully('git add %s' % file_name)
    run_succesfully('git commit -m "BOT: Releasing new MAD database." > /dev/null 2>&1 || true')
    run_succesfully('git fetch origin %s > /dev/null 2>&1 || true' % branch)
    if not run_conditional('git diff --exit-code %s origin/%s' % (branch, branch)):
        print("There are changes to push.")
        print()

        run_succesfully('git push --force origin %s' % branch)
        print()
        print("New %s ready to be used." % file_name)
    else:
        print("Nothing to be updated.")

def set_if_not_empty(doc, fields, key):
    if fields[key] != '':
        ET.SubElement(doc, key).text = fields[key]

def save_data_to_compressed_json(db, json_name, zip_name):

    with open(json_name, 'w') as f:
        json.dump(db, f, sort_keys=True)

    run_succesfully('touch -a -m -t 202108231405 %s' % json_name)
    run_succesfully('zip -rq -D -X -9 -A --compression-method deflate %s %s' % (zip_name, json_name))

def hash(file):
    with open(file, "rb") as f:
        file_hash = hashlib.md5()
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
        return file_hash.hexdigest()

def run_conditional(command):
    result = subprocess.run(command, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE)

    stdout = result.stdout.decode()
    if stdout.strip():
        print(stdout)
        
    return result.returncode == 0

def run_succesfully(command):
    result = subprocess.run(command, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    stdout = result.stdout.decode()
    stderr = result.stderr.decode()
    if stdout.strip():
        print(stdout)
    
    if stderr.strip():
        print(stderr)

    if result.returncode != 0:
        raise Exception("subprocess.run Return Code was '%d'" % result.returncode)

if __name__ == '__main__':
    main()
