#!/usr/bin/env python3
# Copyright (C) 2017 Qrama
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from base64 import b64encode
import os
from subprocess import check_call, run, CalledProcessError
from charms.reactive import set_flag, clear_flag, when_not, when, when_any
from charms.reactive.relations import endpoint_from_flag
from charms.reactive.helpers import data_changed
from charmhelpers.core import templating
from charmhelpers.core.host import service_start, service_stop, service_running
from charmhelpers.core.hookenv import status_set, log, config, open_port, close_port, charm_dir, service_name, unit_private_ip
from charmhelpers.fetch.archiveurl import ArchiveUrlFetchHandler
from charms.reactive.flags import get_flags

KEYCLOAK_VERSION = '3.4.3.Final'
KEYCLOAK_DOWNLOAD = 'https://downloads.jboss.org/keycloak/{}/keycloak-{}.tar.gz'.format(KEYCLOAK_VERSION, KEYCLOAK_VERSION)
KEYCLOAK_BASE_DIR = '/opt'
KEYCLOAK_HOME = '{}/keycloak-{}'.format(KEYCLOAK_BASE_DIR, KEYCLOAK_VERSION)

@when('apt.installed.openjdk-8-jdk')
@when_not('keycloak.installed')
def install_keycloak():
    status_set('maintenance', 'Downloading and installing Keycloack distribution ({})'.format(KEYCLOAK_VERSION))
    handler = ArchiveUrlFetchHandler()
    os.makedirs(KEYCLOAK_BASE_DIR, exist_ok=True)
    handler.install(KEYCLOAK_DOWNLOAD, KEYCLOAK_BASE_DIR)
    log('Keycloak binary downloaded and extracted in {}'.format(KEYCLOAK_HOME))

    module_dir = '{}/modules/system/layers/keycloak/org/postgresql/main'.format(KEYCLOAK_HOME)
    os.makedirs(module_dir, exist_ok=True)
    os.symlink('{}/files/module.xml'.format(charm_dir()), '{}/module.xml'.format(module_dir))
    os.symlink('{}/files/postgresql-42.2.1.jar'.format(charm_dir()), '{}/postgresql-42.2.1.jar'.format(module_dir))
    log('PostgreSQL module copied.')

    standalone_context = {
        'name': service_name(),
        'script': '{}/bin/standalone.sh'.format(KEYCLOAK_HOME)
    }
    templating.render(source='keycloak.service.jinja2',
                      target='/etc/systemd/system/keycloak.service',
                      context=standalone_context)
    check_call(['systemctl', 'enable', 'keycloak.service'])
    log('Keycloak service enabled.')

    set_flag('keycloak.installed')

@when('keycloak.installed')
@when_not('db.connected')
def no_database():
    if service_running('keycloak'):
        log('keycloak service is running, will stop service first.')
        service_stop('keycloak')
    close_port('8080')
    log('Resetting all flags, except keycloak.installed')
    clear_flag('keycloak.running')
    clear_flag('keycloak.configured')
    clear_flag('keycloak.dbconnected')
    status_set('blocked', 'Please connect a PostgreSQL database.')

@when('db.connected')
@when_not('keycloak.dbconnected')
def set_db(pgsql):
    status_set('maintenance', 'Setting up database on the external PostgreSQL server.')
    db_name = 'keycloak_{}'.format(service_name())
    pgsql.set_database(db_name)
    log('Database {} is requested on PostgreSQL'.format(db_name))
    set_flag('keycloak.dbconnected')

@when('db.master.available', 'keycloak.installed', 'keycloak.dbconnected')
@when_not('keycloak.configured')
def configure_db(pgsql):
    postgresql_uri = 'jdbc:postgresql://{}:{}/{}'.format(pgsql.master.host, pgsql.master.port, pgsql.master.dbname)
    standalone_context = {
        'private_ip': unit_private_ip(),
        'postgresql_uri': postgresql_uri,
        'postgresql_username': pgsql.master.user,
        'postgresql_password': pgsql.master.password
    }
    templating.render(source='standalone.xml.jinja2',
                      target='{}/standalone/configuration/standalone.xml'.format(KEYCLOAK_HOME),
                      context=standalone_context)
    status_set('maintenance', 'Database ready: {}'.format(postgresql_uri))
    log('Keycloak configuration adjusted.')
    set_flag('keycloak.configured')


@when('keycloak.installed', 'keycloak.dbconnected', 'keycloak.configured')
@when_not('keycloak.running')
def start_keycloak():
    admin_user = 'admin'
    admin_password = b64encode(os.urandom(18)).decode('utf-8')

    check_call(['{}/bin/add-user-keycloak.sh'.format(KEYCLOAK_HOME), '-u', admin_user, '-p', admin_password])
    log('Added Keycloak admin user: {}'.format(admin_user))

    service_start('keycloak')
    open_port('8080')
    log('Keycloak service started.')

    set_flag('keycloak.running')
    status_set('active', 'Keycloak is running [admin user: {}:{}]'.format(admin_user, admin_password))
