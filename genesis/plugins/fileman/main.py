# coding: utf-8
from genesis.ui import *
from genesis.api import *
from genesis.plugins.core.api import *
from genesis.plugins.notepad.main import NotepadPlugin
from genesis.utils import *
import os
from base64 import b64encode, b64decode
from stat import ST_UID, ST_GID, ST_MODE, ST_SIZE
import grp, pwd
import shutil
from acl import *
import utils


class FMPlugin(CategoryPlugin, URLHandler):
    text = 'File Manager'
    iconfont = 'gen-files'
    folder = 'bottom'

    def on_init(self):
        self._has_acls = shell_status('which getfacl')==0

    def on_session_start(self):
        self._config = self.app.get_config(self)
        self._root = self._config.dir
        self._tabs = []
        self._tab = 0
        self._clipboard = []
        self._cbs = None
        self._renaming = []
        self._clipdlg = None
        self._newfolder = None
        self._newfile = None
        self._upload = None
        self._archupl = []
        self._showhidden = self._config.showhidden
        self.add_tab()

    def get_ui(self):
        ui = self.app.inflate('fileman:main')
        tc = UI.TabControl(active=self._tab)

        idx = 0
        for tab in self._tabs:
            tc.add(tab, content=self.get_tab(tab, tidx=idx), id=str(idx))
            idx += 1
        tc.add('+', None)

        self._clipboard = sorted(self._clipboard)
        if self._clipboard:
            ui.find('clip').set('badge', len(self._clipboard))
        idx = 0
        for f in self._clipboard:
            ui.append('clipboard', UI.DTR(
                UI.IconFont(iconfont='gen-'+
                    ('folder' if os.path.isdir(f) else 'file')),
                UI.Label(text=f),
                UI.TipIcon(
                    iconfont='gen-cancel-circle',
                    text='Remove from clipboard',
                    id='rmClipboard/%i'%idx
                ),
            ))
            idx += 1

        ui.append('main', tc)

        if self._renaming:
            ui.append('main', UI.InputBox(
                text='New name',
                value=os.path.split(self._renaming[0])[1],
                id='dlgRename'
            ))

        if self._editing_acl is not None:
            dlg = self.app.inflate('fileman:acl')
            ui.append('main', dlg)
            ui.find('dlgAcl').set('title', 'Permissions for %s' % self._editing_acl)
            acls = get_acls(self._editing_acl)
            idx = 0
            mode = self.mode_string(os.stat(self._editing_acl)[ST_MODE])
            dlg.append('plist', UI.DTR(
                UI.Label(size=1, text='User'),
                UI.Checkbox(name='user-read', checked=mode[0]=='r'),
                UI.Checkbox(name='user-write', checked=mode[1]=='w'),
                UI.Checkbox(name='user-exec', checked=mode[2]=='x'),
            ))
            dlg.append('plist', UI.DTR(
                UI.Label(size=1, text='Group'),
                UI.Checkbox(name='group-read', checked=mode[3]=='r'),
                UI.Checkbox(name='group-write', checked=mode[4]=='w'),
                UI.Checkbox(name='group-exec', checked=mode[5]=='x'),
            ))
            dlg.append('plist', UI.DTR(
                UI.Label(size=1, text='Other'),
                UI.Checkbox(name='other-read', checked=mode[6]=='r'),
                UI.Checkbox(name='other-write', checked=mode[7]=='w'),
                UI.Checkbox(name='other-exec', checked=mode[8]=='x'),
            ))
            if os.path.isdir(self._editing_acl):
                dlg.append('recur', UI.Formline(UI.Checkbox(name='recursive', text='Set permissions recursively?', checked=True), checkbox="true"))
            for acl in acls:
                dlg.append('alist', UI.DTR(
                    UI.Editable(id='edAclSubject/%i'%idx, value=acl[0]),
                    UI.Editable(id='edAclPerm/%i'%idx, value=acl[1]),
                    UI.TipIcon(
                        iconfont='gen-cancel-circle',
                        text='Delete',
                        id='delAcl/%i'%idx
                    )
                ))
                idx += 1

        if self._upload:
            ui.append('main', UI.UploadBox(id='dlgUpload', 
                text="Select file(s) to upload",
                location=self._tabs[self._tab]))

        if self._archupl:
            ui.append('main', UI.DialogBox(
                UI.Label(text='The file you just uploaded, %s, appears to be a compressed archive. '
                    'Do you want to extract its contents to %s?' % (self._archupl[0][1], self._archupl[0][0]),
                    lbreak=True, bold=True),
                id='dlgArchUpl', yesno=True))

        if self._newfile:
            ui.append('main', UI.InputBox(
                text='Enter path for file',
                value='',
                id='dlgNewFile'
            ))

        if self._newfolder:
            ui.append('main', UI.InputBox(
                text='Enter path for folder',
                value='',
                id='dlgNewFolder'
            ))

        if not self._clipdlg:
            ui.remove('dlgClip')

        return ui

    def get_tab(self, tab, tidx):
        ui = self.app.inflate('fileman:tab')

        ui.find('paste').set('id', 'paste/%i'%tidx)
        ui.find('newfile').set('id', 'newfile/%i'%tidx)
        ui.find('newfld').set('id', 'newfld/%i'%tidx)
        ui.find('close').set('id', 'close/%i'%tidx)
        for x in sorted(apis.poicontrol(self.app).get_pois(), key=lambda x: x.name):
            ui.find('gomenu').append(
                UI.DButtonItem(
                    text=x.name, 
                    iconfont=x.icon, 
                    id='goto/%i/%s'%(tidx, self.enc_file(x.path))
                )
            )
        if self._showhidden:
            ui.find('hidden').set('text', 'Hide hidden')
            ui.find('hidden').set('iconfont', 'gen-eye-blocked')

        # Generate breadcrumbs
        path = tab
        parts = path.split('/')
        while '' in parts:
            parts.remove('')
        parts.insert(0, '/')

        idx = 0
        for part in parts:
            ui.append('path', UI.Btn(
                text=part,
                id='goto/%i/%s' % (
                    tidx,
                    self.enc_file('/'.join(parts[:idx+1])),
                )
            ))
            idx += 1

        # File listing
        try:
            templist = os.listdir(path)
        except:
            templist = []
        lst = []

        for x in sorted(templist):
            if self._showhidden and os.path.isdir(os.path.join(path, x)):
                lst.append(x)
            elif not self._showhidden and not x.startswith('.') \
            and os.path.isdir(os.path.join(path, x)):
                lst.append(x)
        for x in sorted(templist):
            if self._showhidden and not os.path.isdir(os.path.join(path, x)):
                lst.append(x)
            elif not self._showhidden and not x.startswith('.') \
            and not os.path.isdir(os.path.join(path, x)):
                lst.append(x)

        for f in lst:
            np = os.path.join(path, f)
            isdir = os.path.isdir(np)
            islink = os.path.islink(np)
            ismount = os.path.ismount(np)

            iconfont = 'gen-file'
            if isdir: iconfont = 'gen-folder'
            if islink: iconfont ='gen-link'
            if ismount: iconfont = 'gen-storage'

            try:
                stat = os.stat(np)
                mode = stat[ST_MODE]
                size = stat[ST_SIZE]
            except:
                continue

            try:
                user = pwd.getpwuid(stat[ST_UID])[0]
            except:
                user = str(stat[ST_UID])
            try:
                group = grp.getgrgid(stat[ST_GID])[0]
            except:
                group = str(stat[ST_GID])

            name = f
            if islink:
                name += ' → ' + os.path.realpath(np)

            if not isdir and not path.startswith('/dev'):
                tc = ''.join(map(chr, [7,8,9,10,12,13,27] + range(0x20, 0x100)))
                ibs = lambda b: bool(b.translate(None, tc))
                if ibs(open(np).read(1024)):
                    item = UI.Label(text=name)
                else:
                    item = UI.Tooltip(UI.LinkLabelRedirect(text=name, 
                        id='open/%i/%s' % (
                        tidx,
                        self.enc_file(np)
                    ), redirect="notepadplugin"
                    ), text="Open in Notepad")
            else:
                item = UI.LinkLabel(text=name, id='goto/%i/%s' % (
                    tidx,
                    self.enc_file(np)
                ))
            row = UI.DTR(
                UI.Checkbox(name='%i/%s' % (
                    tidx,
                    self.enc_file(np)
                )),
                UI.IconFont(iconfont=iconfont),
                UI.HContainer(
                    item,
                    UI.LinkLabel(
                        text='↗',
                        id='gototab/%i/%s' % (
                            tidx,
                            self.enc_file(np)
                    )) if isdir else None,
                ),
                UI.Label(text=str_fsize(size)),
                UI.Label(text='%s:%s'%(user,group), monospace=True),
                UI.Label(text=self.mode_string(mode), monospace=True),
                UI.HContainer(
                    UI.TipIcon(
                        iconfont='gen-download',
                        text='Download',
                        onclick='window.open("/fm/s/%i/%s", "_blank")'%(
                            tidx,
                            self.enc_file(f)
                        ),
                    ),
                    UI.TipIcon(
                        iconfont='gen-lock',
                        text='Permissions',
                        id='acls/%i/%s'%(
                            tidx,
                            self.enc_file(np)
                        ),
                    ) if self._has_acls else None,
                    UI.TipIcon(
                        iconfont='gen-cancel-circle',
                        text='Delete',
                        warning='Delete %s'%np,
                        id='delete/%i/%s'%(
                            tidx,
                            self.enc_file(np)
                            ),
                        ),
                    )
                )

            ui.append('list', row)
        return ui

    def enc_file(self, path):
        path = path.replace('//','/')
        return b64encode(path, altchars='+-').replace('=', '*')

    def dec_file(self, b64):
        return b64decode(b64.replace('*', '='), altchars='+-')

    def add_tab(self, path=''):
        self._tabs.append(path if path else self._root)
        self._tab = len(self._tabs) - 1

    def mode_string(self, mode):
        return ('r' if mode & 256 else '-') + \
           ('w' if mode & 128 else '-') + \
           ('x' if mode & 64 else '-') + \
           ('r' if mode & 32 else '-') + \
           ('w' if mode & 16 else '-') + \
           ('x' if mode & 8 else '-') + \
           ('r' if mode & 4 else '-') + \
           ('w' if mode & 2 else '-') + \
           ('x' if mode & 1 else '-')

    @url('^/fm/s/.*$')
    def download(self, req, start_response):
        params = req['PATH_INFO'].split('/')[3:] + ['']
        filename = self.dec_file(params[1])
        path = os.path.join(self._tabs[int(params[0])], filename)
        if os.path.isdir(path):
            t = utils.compress([path])
            size = os.path.getsize(t)
            f = open(t, 'rb')
            start_response('200 OK', [
                ('Content-length', str(size)),
                ('Content-type', 'application/gzip'),
                ('Content-Disposition', 'attachment; filename=%s' % filename+'.tar.gz')
            ])
        else:
            f = open(path, 'rb')
            size = os.path.getsize(path)
            start_response('200 OK', [
                ('Content-length', str(size)),
                ('Content-Disposition', 'attachment; filename=%s' % filename)
            ])
        return f.read()

    @event('tab/click')
    def on_tab_click(self, event, params, vars=None):
        self.add_tab()

    @event('button/click')
    @event('linklabel/click')
    def on_btn_click(self, event, params, vars=None):
        if params[0] == 'hidden':
            self._showhidden = not self._showhidden
            if self.app.auth.user and self.app.auth.user != 'anonymous':
                self._config.showhidden = self._showhidden
                self._config.save()
        if params[0] == 'breadcrumb':
            self._tabs[int(params[1])] = self.dec_file(params[2])
        if params[0] == 'goto':
            self._tab = int(params[1])
            self._tabs[self._tab] = self.dec_file(params[2])
        if params[0] == 'gototab':
            self._tab = len(self._tabs)
            self._tabs.append(self.dec_file(params[2]))
        if params[0] == 'open':
            NotepadPlugin(self.app).open(
                os.path.join(self._tabs[int(params[1])],
                    self.dec_file(params[2])))
        if params[0] == 'rmClipboard':
            self._clipboard.remove(self._clipboard[int(params[1])])
        if params[0] == 'close' and len(self._tabs)>1:
            self._tabs.remove(self._tabs[int(params[1])])
            self._tab = 0
        elif params[0] == 'close':
            self._tabs = []
            self.add_tab()
            self._tab = 0
        if params[0] == 'closeall':
            self._tabs = []
            self.add_tab()
            self._tab = 0
        if params[0] == 'paste':
            self._tab = int(params[1])
            path = self._tabs[int(params[1])]
            self.work(self._cbs, self._clipboard, path)
        if params[0] == 'upload':
            self._upload = True
        if params[0] == 'newfile':
            self._tab = int(params[1])
            self._newfile = self._tabs[int(params[1])]
        if params[0] == 'newfld':
            self._tab = int(params[1])
            self._newfolder = self._tabs[int(params[1])]
        if params[0] == 'delete':
            self._tab = int(params[1])
            f = self.dec_file(params[2])
            try:
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.unlink(f)
                self.put_message('success', 'Deleted %s'%f)
            except Exception, e:
                self.put_message('err', str(e))
        if params[0] == 'download':
            pass
        if params[0] == 'acls':
            self._tab = int(params[1])
            self._editing_acl = self.dec_file(params[2])
        if params[0] == 'delAcl':
            idx = int(params[1])
            del_acl(self._editing_acl, get_acls(self._editing_acl)[idx][0])
        if params[0] == 'clip':
            self._clipdlg = True
        if params[0] == 'clrclip':
            self._clipboard = []
            self._clipdlg = None

    @event('form/submit')
    @event('dialog/submit')
    def on_submit(self, event, params, vars=None):
        if params[0] == 'files':
            act = vars.getvalue('action', '')
            tab = self._tab
            lst = []
            for x in vars:
                if '/' in x and vars.getvalue(x, None) == '1':
                    tab, f = x.split('/')
                    f = self.dec_file(f)
                    lst.append(f)
            if len(lst) > 0:
                if act == 'copy':
                    self._clipboard = lst
                    self._cbs = 'copy'
                if act == 'cut':
                    self._clipboard = lst
                    self._cbs = 'cut'
                if act == 'rename':
                    self._renaming = lst
                if act == 'delete':
                    suc, err = [], []
                    for x in lst:
                        try:
                            if os.path.isdir(x):
                                shutil.rmtree(x)
                            else:
                                os.unlink(x)
                            suc.append(x)
                        except Exception, e:
                            self.app.log.error('Failed to delete %s: %s'%(x,str(e)))
                            err.append(x)
                    if suc:
                        self.put_message('success', 'Deleted %s'%(', '.join(suc)))
                    if err:
                        self.put_message('err', 'Deleting of %s failed'%(', '.join(suc)))
            self._tab = tab
        if params[0] == 'dlgRename':
            if vars.getvalue('action', None) == 'OK':
                os.rename(self._renaming[0],
                    os.path.join(
                        os.path.split(self._renaming[0])[0],
                        vars.getvalue('value', None)
                    ))
            self._renaming.remove(self._renaming[0])
        if params[0] == 'dlgAcl':
            if vars.getvalue('action', '') == 'OK':
                user = (int(vars.getvalue('user-read', '1'))*4) + (int(vars.getvalue('user-write', '1'))*2) + (int(vars.getvalue('user-exec', '0')))
                group = (int(vars.getvalue('group-read', '1'))*4) + (int(vars.getvalue('group-write', '0'))*2) + (int(vars.getvalue('group-exec', '0')))
                other = (int(vars.getvalue('other-read', '1'))*4) + (int(vars.getvalue('other-write', '0'))*2) + (int(vars.getvalue('other-exec', '0')))
                bm = int(str((user*100)+(group*10)+other), 8)
                os.chmod(self._editing_acl, bm)
                if vars.getvalue('recursive', '0') == '1':
                    for r, d, f in os.walk(self._editing_acl):
                        for x in d:
                            os.chmod(os.path.join(r, x), bm)
                        for x in f:
                            os.chmod(os.path.join(r, x), bm)
            self._editing_acl = None
        if params[0] == 'dlgUpload':
            if vars.getvalue('action', '') == 'OK' and vars.has_key('file'):
                files = []
                if type(vars['file']) == list:
                    names = []
                    for x in vars['file']:
                        open(os.path.join(self._tabs[self._tab], x.filename), 'w').write(x.value)
                        names.append(x.filename)
                        files.append((self._tabs[self._tab], x.filename))
                    self.put_message('success', 'Uploaded the following files to %s: %s'
                        % (self._tabs[self._tab], ', '.join(names)))
                else:
                    f = vars['file']
                    open(os.path.join(self._tabs[self._tab], f.filename), 'w').write(f.value)
                    self.put_message('success', 'Uploaded %s to %s'
                        % (f.filename, self._tabs[self._tab]))
                    files.append((self._tabs[self._tab], f.filename))
                for x in files:
                    archives = ['.tar.gz', '.tgz', '.gz', '.tar.bz2', '.tbz2', '.bz2', '.zip']
                    if self.app.auth.user != 'anonymous':
                        uid, gid = pwd.getpwnam(self.app.auth.user).pw_uid, pwd.getpwnam(self.app.auth.user).pw_gid
                        os.chown(os.path.join(x[0], x[1]), uid, gid)
                    for y in archives:
                        if x[1].endswith(y):
                            self._archupl.append((x[0], x[1], y))
                            break
            self._upload = None
        if params[0] == 'dlgArchUpl':
            f = self._archupl[0]
            if vars.getvalue('action', '') == 'OK':
                try:
                    utils.extract(os.path.join(f[0], f[1]), f[0], False)
                except Exception, e:
                    self.put_message('err', 'Failed to extract %s: %s' % (f[1], str(e)))
            self._archupl.remove(f)
        if params[0] == 'dlgNewFile':
            if vars.getvalue('action', '') == 'OK' and vars.getvalue('value', ''):
                filename = vars.getvalue('value', '')
                if filename[0] != '/':
                    filename = os.path.join(self._newfile, filename)
                if os.path.exists(filename):
                    self.put_message('err', 'That file already exists!')
                else:
                    try:
                        open(filename, 'w')
                        self.put_message('success', 'File created: %s' % filename)
                    except Exception, e:
                        self.put_message('err', 'File creation failed: %s' % str(e))
            self._newfile = None
        if params[0] == 'dlgNewFolder':
            if vars.getvalue('action', '') == 'OK' and vars.getvalue('value', ''):
                fld = vars.getvalue('value', '')
                if fld[0] != '/':
                    fld = os.path.join(self._newfolder, fld)
                try:
                    os.makedirs(fld)
                    self.put_message('success', 'Folder(s) created: %s' % fld)
                except Exception, e:
                    self.put_message('err', 'Folder creation failed: %s' % str(e))
            self._newfolder = None
        if params[0] == 'frmAddAcl':
            if vars.getvalue('action', None) == 'OK':
                set_acl(self._editing_acl,
                    vars.getvalue('subject', None),
                    vars.getvalue('perm', None),
                    )
        if params[0] == 'edAclPerm':
            idx = int(params[1])
            set_acl(self._editing_acl, get_acls(self._editing_acl)[idx][0], vars.getvalue('value', None))
        if params[0] == 'edAclSubject':
            idx = int(params[1])
            perm = get_acls(self._editing_acl)[idx][1]
            del_acl(self._editing_acl, get_acls(self._editing_acl)[idx][0])
            set_acl(self._editing_acl, vars.getvalue('value', None), perm)
        if params[0] == 'dlgClip':
            self._clipdlg = None

    def work(self, action, files, target):
        w = FMWorker(self, action, files, target)
        self.app.session['fm_worker'] = w
        w.start()


class FMWorker(BackgroundWorker):
    def __init__(self, *args):
        self.action = ''
        BackgroundWorker.__init__(self, *args)

    def run(self, cat, action, files, target):
        self.action = action
        try:
            for f in files:
                np = os.path.join(target, os.path.split(f)[1])
                if action == 'copy':
                    if (not os.path.isdir(f)) or os.path.islink(f):
                        shutil.copy2(f, np)
                    else:
                        shutil.copytree(f, np, symlinks=True)
                if action == 'cut':
                    os.rename(f, np)
        except Exception, e:
            cat.put_message('err', str(e))

    def get_status(self):
        return self.action


class FMProgress(Plugin):
    implements(IProgressBoxProvider)
    title = 'File manager'
    iconfont = 'gen-files'
    can_abort = True

    def get_worker(self):
        try:
            return self.app.session['fm_worker']
        except:
            return None

    def has_progress(self):
        if self.get_worker() is None:
            return False
        return self.get_worker().alive

    def get_progress(self):
        return self.get_worker().get_status()

    def abort(self):
        if self.has_progress():
            self.get_worker().kill()


class FileManListener(Plugin):
    implements(apis.orders.IListener)
    id = 'fileman'
    cat = 'fmplugin'

    def order(self, op, path):
        if op == 'open':
            FMPlugin(self.app).add_tab(path)
