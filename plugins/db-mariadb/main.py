from genesis.api import *
from genesis.ui import *
from genesis.com import Plugin, Interface, implements
from genesis import apis
from genesis.utils import *
from genesis.plugins.databases.utils import *

import re
import MySQLdb
import _mysql_exceptions


class MariaDB(Plugin):
    implements(apis.databases.IDatabase)
    db = None

    def connect(self, store, user='root', passwd='', db=None):
        if db:
            self.db = MySQLdb.connect('localhost', user, passwd, db)
            store[self.plugin_info.name] = self.db
        else:
            try:
                self.db = MySQLdb.connect('localhost', user, passwd)
            except _mysql_exceptions.OperationalError:
                raise DBAuthFail(self.plugin_info.name)
            store[self.plugin_info.name] = self.db

    def checkpwstat(self):
        try:
            MySQLdb.connect('localhost', 'root', '')
            return False
        except:
            return True

    def chpwstat(self, newpasswd, conn=None):
        if not self.db and conn:
            self.db = conn
        self.db.query('USE mysql')
        self.db.query('UPDATE user SET password=PASSWORD("'+newpasswd+'") WHERE User=\'root\'')
        self.db.query('FLUSH PRIVILEGES')

    def validate(self, name='', user='', passwd='', conn=None):
        if not self.db and conn:
            self.db = conn
        if name and re.search('\.|-|`|\\\\|\/|^test$|[ ]', name):
            raise Exception('Database name must not contain spaces, dots, dashes or other special characters')
        elif name and len(name) > 16:
            raise Exception('Database name must be shorter than 16 characters')
        if user and re.search('\.|-|`|\\\\|\/|^test$|[ ]', user):
            raise Exception('Database username must not contain spaces, dots, dashes or other special characters')
        elif user and len(user) > 16:
            raise Exception('Database username must be shorter than 16 characters')
        if passwd and len(passwd) < 8:
            raise Exception('Database password must be longer than 8 characters')
        if name:
            for x in self.get_dbs(self.db):
                if x['name'] == name:
                    raise Exception('You already have a database named %s - please remove that one or choose a new name!' % name)
        if user:
            for x in self.get_users(self.db):
                if x['name'] == user:
                    raise Exception('You already have a database user named %s - please remove that one or choose a new name!' % user)
        return True

    def add(self, dbname, conn=None):
        if not self.db and conn:
            self.db = conn
        self.validate(name=dbname, user=dbname)
        self.db.query('CREATE DATABASE %s' % dbname)

    def remove(self, dbname, conn=None):
        if not self.db and conn:
            self.db = conn
        if self.db:
            self.db.query('DROP DATABASE %s' % dbname)
        else:
            raise DBConnFail(self.plugin_info.name)

    def usermod(self, user, action, passwd, conn=None):
        if not self.db and conn:
            self.db = conn
        if action == 'add' and self.db:
            self.validate(user=user, passwd=passwd)
            self.db.query('CREATE USER \'%s\'@\'localhost\' IDENTIFIED BY \'%s\''
                % (user,passwd))
        elif action == 'del' and self.db:
            self.db.query('DROP USER \'%s\'@\'localhost\'' % user)
        else:
            raise Exception('Unknown input or database connection failure')

    def chperm(self, dbname, user, action, conn=None):
        if not self.db and conn:
            self.db = conn
        if action == 'check' and self.db:
            self.db.query('SHOW GRANTS FOR \'%s\'@\'localhost\''
                % user)
            r = self.db.store_result()
            out = r.fetch_row(0)
            parse = []
            status = ''
            for line in out:
                if line[0].startswith('Grants for'):
                    continue
                elif line[0] is '' or line[0] is ' ':
                    continue
                else:
                    parse.append(line[0].split(' IDENT')[0])
            for line in parse:
                status += line + '\n'
            return status
        elif action == 'grant' and self.db:
            self.db.query('GRANT ALL ON %s.* TO \'%s\'@\'localhost\'' 
                % (dbname, user))
        elif action == 'revoke' and self.db:
            self.db.query('REVOKE ALL ON %s.* FROM \'%s\'@\'localhost\'' 
                % (dbname, user))
        else:
            raise Exception('Unknown input or database connection failure')

    def execute(self, dbname, cmd, conn=None, commit=False, strf=True):
        if not self.db and conn:
            self.db = conn
        if self.db:
            self.db.query('USE %s' % dbname)
            cur = self.db.cursor()
            parse, s = [], ""
            for l in cmd.split('\n'):
                if not l.split() or re.match('--', l):
                    continue
                elif not re.search('[^-;]+;', l):
                    s = s + l
                elif re.search('^\s*USE', l):
                    raise Exception('Cannot switch databases during execution')
                else:
                    s = s + l
                    cur.execute(s)
                    for x in cur.fetchall():
                        parse.append(x)
                    s = ""
            if commit:
                self.db.commit()
            if strf:
                status = ""
                for line in parse:
                    line = [str(x) for x in line]
                    status += ', '.join(line)+'\n'
                return status
            else:
                return parse
        else:
            raise DBConnFail(self.plugin_info.name)

    def get_dbs(self, conn=None):
        dblist = []
        excludes = ['Database', 'information_schema', 
            'mysql', 'performance_schema']
        if not self.db and conn:
            self.db = conn
        if self.db:
            self.db.query('SHOW DATABASES')
            r = self.db.store_result()
            dbs = r.fetch_row(0)
        else:
            raise DBConnFail(self.plugin_info.name)
        for db in dbs:
            if not db[0] in excludes and db[0].split():
                dblist.append({
                    'name': db[0],
                    'type': 'MariaDB',
                    'class': self.__class__
                })
        return dblist

    def get_users(self, conn=None):
        userlist = []
        excludes = ['root', ' ', '']
        if not self.db and conn:
            self.db = conn
        if self.db:
            self.db.query('SELECT user FROM mysql.user')
            r = self.db.store_result()
            output = r.fetch_row(0)
        else:
            raise DBConnFail(self.plugin_info.name)
        for usr in output:
            if not usr[0] in userlist and not usr[0] in excludes:
                userlist.append({
                    'name': usr[0],
                    'type': 'MariaDB',
                    'class': self.__class__
                })
        return userlist

    def get_size(self, dbname, conn=None):
        s = self.execute(dbname, "SELECT sum(data_length+index_length) FROM information_schema.TABLES WHERE table_schema LIKE '%s';" % dbname, conn, strf=False)
        return str_fsize(int(s[0][0]) if s[0][0] else 0)

    def dump(self, dbname, conn=None):
        if not self.db and conn:
            self.db = conn
        self.db.query("USE %s" % dbname)
        cur = self.db.cursor()
        tables, data = [], ""
        cur.execute("SHOW TABLES")
        for table in cur.fetchall():
            tables.append(table[0])
        for table in tables:
            data += "DROP TABLE IF EXISTS `"+str(table)+"`;"
            cur.execute("SHOW CREATE TABLE `"+str(table)+"`;")
            data += "\n"+str(cur.fetchone()[1])+";\n\n"
            cur.execute("SELECT * FROM `"+str(table)+"`;")
            rows = cur.fetchall()
            if rows:
                data += "INSERT INTO `"+str(table)+"` VALUES ("
                s = True
            for row in rows:
                f = True
                if not s:
                    data += '), ('
                for field in row:
                    if not f:
                        data += ', '
                    if type(field) in [int, long]:
                        data += str(field)
                    elif type(field) == str:
                        data += '"'+str(self.db.escape_string(field))+'"'
                    else:
                        data += '"'+str(field)+'"'
                    f = False
                s = False
            if rows:
                data += ");\n"
            data += "\n\n"
        return data
