# Overview

This charm installs and configures RedHat's [Keycloak](http://www.keycloak.org). 
Keycloak is an open source identity and access management system. More info about
Keycloak can be found [here](http://www.keycloak.org/about.html).

The charm expects a relation to a PostgreSQL Database Server.


# Usage

Deploy Keycloak with the following command:

`juju deploy cs:keycloak <name>`

Add a relation to your PostgreSQL Database Server.

`juju add-relation <name> postgresql:db`

This will create a database with the name `keycloak_<name>`. When Keycloak is active
you can browse the management console on `http://ip-address:8080/auth/admin/master/console`.
Login as user `admin` and use the randomly generated  password, which can be found 
in the status message of the application.

# Known Limitations and Issues

Clustering is not supported yet, so this version of the charm should not be scaled.

## Authors

This software was created at [Tengu](https://www.tengu.io) (powered by Qrama).

 - Gregory Van Seghbroeck <gregory.vanseghbroeck@tengu.io>
