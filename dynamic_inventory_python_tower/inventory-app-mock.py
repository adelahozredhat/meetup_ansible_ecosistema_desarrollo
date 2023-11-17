#!/usr/bin/env python

# Copyright 2017 Reuben Stump, Alex Mittell
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied. See the License for the specific language governing
# permissions and limitations under the License.


import os
import sys
import requests
import base64
import json
import re
from six.moves import configparser
import time
import warnings
import re



class ErrorParameters(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class Inventory(object):
    def __init__(
            self,
            hostname,
            service,
            username,
            password,
            tower_env,
            team=None,
            environment=None,
            proxy=None):
        self.hostname = hostname

        self.service = service

        # requests session
        self.session = requests.Session()

        self.auth = requests.auth.HTTPBasicAuth(username, password)
        # request headers
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }


        if proxy is None:
            proxy = []

        # table
        self.team = team

        # extra fields (table columns)
        self.environment = environment

        if self.environment is not None:
            self.environment = self.environment.lower()
 

        # tower_env
        self.tower_env = tower_env
  

        # proxy settings
        self.proxy = proxy

        warnings.filterwarnings("ignore")
        return

    def _put_cache(self, name, value):
        cache_dir = os.environ.get('SN_CACHE_DIR')
        if not cache_dir and config.has_option('defaults', 'cache_dir'):
            cache_dir = os.path.expanduser(config.get('defaults', 'cache_dir'))
        if cache_dir:
            cache_dir = os.path.join(os.path.dirname(__file__), cache_dir)
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            cache_file = os.path.join(cache_dir, name)
            with open(cache_file, 'w') as cache:
                json.dump(value, cache, indent=0, separators=(',', ': '), sort_keys=True)

    def _get_cache(self, name, default=None):
        cache_dir = os.environ.get('SN_CACHE_DIR')
        if not cache_dir and config.has_option('defaults', 'cache_dir'):
            cache_dir = os.path.expanduser(config.get('defaults', 'cache_dir'))
        if cache_dir:
            cache_dir = os.path.join(os.path.dirname(__file__), cache_dir)
            cache_file = os.path.join(cache_dir, name)
            if os.path.exists(cache_file):
                cache_max_age = os.environ.get('SN_CACHE_MAX_AGE')
                if not cache_max_age:
                    if config.has_option('defaults', 'cache_max_age'):
                        cache_max_age = config.getint('defaults',
                                                      'cache_max_age')
                    else:
                        cache_max_age = 0
                cache_stat = os.stat(cache_file)
                if (cache_stat.st_mtime + int(cache_max_age)) >= time.time():
                    with open(cache_file) as cache:
                        return json.load(cache)
        return default

    def _invoke(self, verb, path, data):

        cache_name = '__snow_inventory__'
        inventory = self._get_cache(cache_name, None)
        if inventory is not None:
            return inventory

        # build url
        url = "https://%s/%s" % (self.hostname, path)
        results = []
        response = self.session.get(
            url, auth=self.auth, headers=self.headers, proxies={
                'http': self.proxy, 'https': self.proxy}, verify=False)

        data = None
        if response.status_code != 200 and (response.status_code != 422 and not response.text["message"].__eq__('Inventory not generated')):
            raise ErrorParameters("http error (%s): %s" % (response.status_code,
                                                           response.text))
        else:
            if response.status_code == 200:
                status = response.json()['status']
                if status == 'failed':
                    message = response.json()['message']
                    raise ErrorParameters("http error : %s" % (message))

                self._put_cache(cache_name, data)
                data = response.json()['data']
        return data

    def _invoke_mock(self, verb, path, data):
        return json.load(open('mockup_app_inv_v2.json'))

    def add_group(self,data, group, pre_name, fathername):
        environments_pro_inv = ['tst', 'pre', 'pro', 'cnt']
        if self.tower_env == 'pre':
            for record in group:
                if record != 'default':
                    if record != 'hosts' and re.match(r"^(custom_)[\w]+", record) is None and record not in environments_pro_inv:
                        name = record
                        if pre_name != '':
                            name = pre_name + "_" + record
                        if "children" not in data[fathername]:
                            data[fathername]['children'] = []
                        data[fathername]['children'].append(name)
                        data[name] = {}                        
                        self.add_group(data, group[record], name, name)
                    else:       
                        #check_fathername = re.match(r"[\w]+(_)[\w]+(_lab_)[\w]+", fathername)
                        data[fathername]['hosts'] = []
                        if record == 'hosts':
                            data[fathername]['hosts'] = self.add_host(data, group[record])
                       

        if self.tower_env == 'pro':
            for record in group:         
                if record != 'default' and re.match(r"^(lab_)[\w]+", record) is None:
                    if record != 'hosts':
                        name = record
                        if pre_name != '':
                            name = pre_name + "_" + record
                        if "children" not in data[fathername]:
                            data[fathername]['children'] = []
                        data[fathername]['children'].append(name)
                        data[name] = {}
                        self.add_group(data, group[record], name, name)
                    else:               
                        data[fathername]['hosts'] = []
                        data[fathername]['hosts'] = self.add_host(data, group[record])

        return data


    def add_host(self, data, hosts):
        data_list = []
        for record in hosts:
            data_list.append(record)
        return data_list

    def generate(self):

        path = self.service

        if self.team is not None:
            path = path + '?ttss=' + self.team

        if self.environment is not None:
            if self.team is not None:
                path = path + '&environment=' + self.environment
            else:
                path = path + '?environment=' + self.environment

        content = self._invoke_mock('GET', path, None)

        # pre_name = ''


        # data = {'_meta':{'hostvars':{}}}
        # if content is not None:
        #     data['all'] = {}
        #     for record in content['all']['groups']:
        #         if self.team is None:
        #             pre_name = (record).replace("-","_")
        #         self.add_group(data, content['all']['groups'][record], pre_name, 'all')
        #     data['_meta']['hostvars'] = content['all']['_meta']['hostvars']
        #     data['all']['vars'] = content['all']['vars']

        # return data
        return content

    def json(self):
        return json.dumps(self.inventory)


def main(args):
    global config
    config = configparser.ConfigParser()

    if os.environ.get('INI', ''):
        config_files = [os.environ['INI']]
    else:
        config_files = [
            os.path.abspath(sys.argv[0]).rstrip('.py') + '.ini', 'inventory-app-mock.ini'
        ]

    for config_file in config_files:
        if os.path.exists(config_file):
            config.read(config_file)
            break

    # Read authentication information from environment variables (if set),
    # otherwise from INI file.
    instance = os.environ.get('SN_INSTANCE')
    if not instance and config.has_option('auth', 'instance'):
        instance = config.get('auth', 'instance')

    service = os.environ.get('SN_SERVICE')
    if not service and config.has_option('auth', 'service'):
        service = config.get('auth', 'service')

    username = os.environ.get('SN_USERNAME')
    if not username and config.has_option('auth', 'user'):
        username = config.get('auth', 'user')
        #username = api_user

    password = os.environ.get('SN_PASSWORD')
    if not password and config.has_option('auth', 'password'):
        password = config.get('auth', 'password')
        #password = api_password

    # SN_TEAM
    team = os.environ.get('SN_APP')
    if not team and config.has_option('config', 'team'):
        team = config.get('config', 'team')

    # SN_ENVIRONMENT
    environment = os.environ.get('SN_ENVIRONMENT')
    if not environment and config.has_option('config', 'environment'):
        environment = config.get('config', 'environment')
    
    # SN_TOWER_ENV
    tower_env = os.environ.get('SN_TOWER_ENV')
    if not tower_env and config.has_option('config', 'tower_env'):
        tower_env = config.get('config', 'tower_env')

    # SN_PROXY
    proxy = os.environ.get('SN_PROXY')
    if not proxy and config.has_option('config', 'proxy'):
        proxy = config.get('config', 'proxy')

    inventory = Inventory(
        hostname=instance,
        service=service,
        username=username,
        password=password,
        team=team,
        tower_env=tower_env,
        environment=environment,
        proxy=proxy)

    inventory.generate()

    print(json.dumps(inventory.generate()))


if __name__ == "__main__":
    main(sys.argv)





