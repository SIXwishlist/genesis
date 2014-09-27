from genesis.com import *
from genesis.api import *
from genesis.ui import *
from genesis import apis
from genesis.utils import SystemTime
from genesis.plugins.network.backend import IHostnameManager

from backend import CertControl

import os
import re


class CertificatesPlugin(CategoryPlugin, URLHandler):
    text = 'Certificates'
    iconfont = 'gen-certificate'
    folder = 'tools'

    def on_init(self):
        self.certs = sorted(self._cc.get_certs(),
            key=lambda x: x.name)
        self.cas = sorted(self._cc.get_cas(),
            key=lambda x: x['name'])
        self._hostname = self.app.get_backend(IHostnameManager).gethostname().lower()

    def on_session_start(self):
        self._cc = CertControl(self.app)
        self._cfg = self.app.get_config(self._cc)
        self._gen = None
        self._tab = 0
        self._wal = []
        self._pal = []
        self._hostname = ''
        self._upload = None

    def get_ui(self):
        ui = self.app.inflate('certificates:main')
        ui.find('tabs').set('active', self._tab)

        ui.find('kl'+self._cfg.keylength).set('selected', True)
        ui.find('kt'+self._cfg.keytype.lower()).set('selected', True)
        ui.find('ciphers').set('value', self._cfg.ciphers)

        for s in self.certs:
            ui.find('certlist').append(
                UI.TblBtn(
                    id='info/'+str(self.certs.index(s)),
                    icon='gen-certificate',
                    name=s.name,
                    subtext="%s-bit %s" % (s.keylength, s.keytype)
                    )
                )
        ui.find('certlist').append(
            UI.TblBtn(
                id='gen',
                icon='gen-plus-circle',
                name='Generate certificate'
                )
            )
        ui.find('certlist').append(
            UI.TblBtn(
                id='upl',
                icon='gen-file-upload',
                name='Upload certificate'
                )
            )

        lst = ui.find('certauth')
        if not self.cas:
            lst.append(UI.Btn(text="Generate New", id="cagen"))
        for s in self.cas:
            exp = SystemTime.convert(s['expiry'], '%Y%m%d%H%M%SZ', self.app.gconfig.get('genesis', 'dformat', '%d %b %Y'))
            lst.append(UI.FormLine(
                UI.HContainer(
                    UI.Label(text='Expires '+exp),
                    UI.TipIcon(iconfont='gen-download', text='Download',
                        id='cadl',
                        onclick='window.open("/certificates/dl", "_blank")'),
                    UI.TipIcon(iconfont='gen-close', text='Delete',
                        id='cadel/' + str(self.cas.index(s))),
                    ), text=s['name'], horizontal=True
               ))

        if self._gen:
            ui.find('certcn').set('value', self._hostname)
            self._wal, self._pal = self._cc.get_ssl_capable()
            alist, wlist, plist = [], [], []
            for cert in self.certs:
                for i in cert.assign:
                    alist.append(i)
            if not {'type': 'genesis'} in alist:
                ui.find('certassign').append(
                    UI.FormLine(
                        UI.Checkbox(text='Genesis SSL', name='genesis', value='genesis', checked=False),
                    checkbox=True)
                )
            for x in self._wal:
                if not {'type': 'website', 'name': x.name} in alist:
                    ui.find('certassign').append(
                        UI.FormLine(
                            UI.Checkbox(text=x.name, name='wassign[]', value=x.name, checked=False),
                        checkbox=True)
                    )
                    wlist.append(x)
            self._wal = wlist
            for x in self._pal:
                if not {'type': 'plugin', 'name': x.text} in alist:
                    ui.find('certassign').append(
                        UI.FormLine(
                            UI.Checkbox(text=x.text, name='passign[]', value=x.text, checked=False),
                        checkbox=True)
                    )
                    plist.append(x)
            self._pal = plist
        else:
            ui.remove('dlgGen')

        if self._cinfo:
            self._wal, self._pal = self._cc.get_ssl_capable()
            ui.find('certname').set('text', self._cinfo.name)
            ui.find('domain').set('text', self._cinfo.domain)
            ui.find('ikeytype').set('text', '%s-bit %s' % (self._cinfo.keylength, self._cinfo.keytype))
            exp = SystemTime.convert(self._cinfo.expiry, '%Y%m%d%H%M%SZ', self.app.gconfig.get('genesis', 'dformat', '%d %b %Y'))
            ui.find('expires').set('text', exp)
            ui.find('sha1').set('text', self._cinfo.sha1)
            ui.find('md5').set('text', self._cinfo.md5)

            alist = []
            for cert in self.certs:
                if cert != self._cinfo:
                    for i in cert.assign:
                        alist.append(i)

            if not 'genesis' in [x['type'] for x in alist]:
                if 'genesis' in [x['type'] for x in self._cinfo.assign]:
                    ic, ict, show = 'gen-checkmark-circle', 'Assigned', 'd'
                else:
                    ic, ict, show = None, None, 'e'
                ui.find('certassign').append(
                    UI.DTR(
                        UI.IconFont(iconfont=ic, text=ict),
                        UI.IconFont(iconfont='gen-arkos-round'),
                        UI.Label(text='Genesis'),
                        UI.HContainer(
                            (UI.TipIcon(iconfont='gen-checkmark-circle',
                                text='Assign', id='ac/'+self._cinfo.name+'/g') if show == 'e' else None),
                            (UI.TipIcon(iconfont='gen-close',
                                text='Unassign', id='uc/'+self._cinfo.name+'/g',
                                warning=('Are you sure you wish to unassign this certificate? '
                                    'SSL on this service will be disabled, and you will need to '
                                    'reload Genesis for changes to take place.')) if show == 'd' else None),
                        ),
                    )
                )
            for x in self._wal:
                if not x.name in [y['name'] for y in alist if y['type'] == 'website']:
                    if x.name in [y['name'] for y in self._cinfo.assign if y['type'] == 'website']:
                        ic, ict, show = 'gen-checkmark-circle', 'Assigned', 'd'
                    else:
                        ic, ict, show = None, None, 'e'
                    ui.find('certassign').append(
                        UI.DTR(
                            UI.IconFont(iconfont=ic, text=ict),
                            UI.IconFont(iconfont='gen-earth'),
                            UI.Label(text=x.name),
                            UI.HContainer(
                                (UI.TipIcon(iconfont='gen-checkmark-circle',
                                    text='Assign', id='ac/'+self._cinfo.name+'/w/'+str(self._wal.index(x))) if show == 'e' else None),
                                (UI.TipIcon(iconfont='gen-close',
                                    text='Unassign', id='uc/'+self._cinfo.name+'/w/'+str(self._wal.index(x)),
                                    warning=('Are you sure you wish to unassign this certificate? '
                                        'SSL on this service will be disabled.')) if show == 'd' else None),
                            ),
                        )
                    )
            for x in self._pal:
                if not x.pid in [y['id'] for y in alist if y['type'] == 'plugin']:
                    if x.pid in [y['id'] for y in self._cinfo.assign if y['type'] == 'plugin']:
                        ic, ict, show = 'gen-checkmark-circle', 'Assigned', 'd'
                    else:
                        ic, ict, show = None, None, 'e'
                    ui.find('certassign').append(
                        UI.DTR(
                            UI.IconFont(iconfont=ic, text=ict),
                            UI.IconFont(iconfont=x.iconfont),
                            UI.Label(text=x.text),
                            UI.HContainer(
                                (UI.TipIcon(iconfont='gen-checkmark-circle',
                                    text='Assign', id='ac/'+self._cinfo.name+'/p/'+str(self._pal.index(x))) if show == 'e' else None),
                                (UI.TipIcon(iconfont='gen-close',
                                    text='Unassign', id='uc/'+self._cinfo.name+'/p/'+str(self._pal.index(x)),
                                    warning=('Are you sure you wish to unassign this certificate? '
                                        'SSL on this service will be disabled.')) if show == 'd' else None),
                            ),
                        )
                    )
        else:
            ui.remove('dlgInfo')

        if self._upload:
            ui.append('main', UI.DialogBox(
                UI.FormLine(UI.TextInput(name='certname'), text='Name'),
                UI.FormLine(UI.FileInput(id='certfile'), text='Certificate file'),
                UI.FormLine(UI.FileInput(id='keyfile'), text='Certificate keyfile'),
                UI.FormLine(UI.FileInput(id='chainfile'), text='Certificate chainfile', 
                    help='This is optional, only put it if you know you need one.'),
                id='dlgUpload', mp=True))

        return ui

    @url('^/certificates/dl$')
    def download(self, req, start_response):
        params = req['PATH_INFO'].split('/')[3:] + ['']
        filename = CertControl(self.app).get_cas()[0]['name']+'.pem'
        path = os.path.join('/etc/ssl/certs/genesis/ca', filename)
        f = open(path, 'rb')
        size = os.path.getsize(path)
        start_response('200 OK', [
            ('Content-length', str(size)),
            ('Content-Disposition', 'attachment; filename=%s' % filename)
        ])
        return f.read()

    @event('button/click')
    def on_click(self, event, params, vars = None):
        if params[0] == 'info':
            self._tab = 0
            self._cinfo = self.certs[int(params[1])]
        elif params[0] == 'gen':
            self._tab = 0
            self._gen = True
        elif params[0] == 'del':
            self._tab = 0
            self._cc.remove(self._cinfo)
            self._cinfo = None
            self.put_message('success', 'Certificate successfully deleted')
        elif params[0] == 'ac' and params[2] == 'p':
            self._tab = 0
            self._cc.assign(self._cinfo.name, 
                [('plugin', self._pal[int(params[3])])])
            self.put_message('success', '%s added to %s plugin' % (self._cinfo.name, self._pal[int(params[3])].text))
            self._cinfo = None
        elif params[0] == 'ac' and params[2] == 'w':
            self._tab = 0
            self._cc.assign(self._cinfo.name,
                [('website', self._wal[int(params[3])])])
            self.put_message('success', '%s added to %s website' % (self._cinfo.name, self._wal[int(params[3])].name))
            self._cinfo = None
        elif params[0] == 'ac' and params[2] == 'g':
            self._tab = 0
            self._cc.assign(self._cinfo.name, [[('genesis')]])
            self.put_message('success', '%s serving as Genesis certificate. Restart Genesis for changes to take effect' % self._cinfo.name)
            self._cinfo = None
        elif params[0] == 'uc' and params[2] == 'p':
            self._tab = 0
            self._cc.unassign(('plugin', self._pal[int(params[3])]))
            self.put_message('success', '%s removed from %s plugin, and SSL disabled.' % (self._cinfo.name, self._pal[int(params[3])].text))
            self._cinfo = None
        elif params[0] == 'uc' and params[2] == 'w':
            self._tab = 0
            self._cc.unassign(('website', self._wal[int(params[3])]))
            self.put_message('success', '%s removed from %s website, and SSL disabled.' % (self._cinfo.name, self._wal[int(params[3])].name))
            self._cinfo = None
        elif params[0] == 'uc' and params[2] == 'g':
            self._tab = 0
            self._cc.unassign(('genesis'))
            self.put_message('success', 'Certificate removed and SSL disabled for Genesis. Reload Genesis for changes to take effect')
            self._cinfo = None
        elif params[0] == 'upl':
            self._tab = 0
            self._upload = True
        elif params[0] == 'cagen':
            self._tab = 1
            self._cc.create_authority(self._hostname)
        elif params[0] == 'cadel':
            self._tab = 1
            self._cc.delete_authority(self.cas[int(params[1])])

    @event('form/submit')
    @event('dialog/submit')
    def on_submit(self, event, params, vars = None):
        if params[0] == 'dlgAdd':
            self._tab = 0
            if vars.getvalue('action', '') == 'OK':
                pass
        elif params[0] == 'dlgGen':
            self._tab = 0
            if vars.getvalue('action', '') == 'OK':
                name = vars.getvalue('certname', '')
                if name == '':
                    self.put_message('err', 'Certificate name is mandatory')
                elif re.search('\.|-|`|\\\\|\/|[ ]', name):
                    self.put_message('err', 'Certificate name must not contain spaces, dots, dashes or special characters')
                elif name in [x.name for x in self.certs]:
                    self.put_message('err', 'You already have a certificate with that name.')
                elif len(vars.getvalue('certcountry', '')) != 2:
                    self.put_message('err', 'The country field must be a two-letter abbreviation')
                else:
                    lst = []
                    if vars.getvalue('genesis', '') == '1':
                        lst.append([('genesis')])
                    for i in range(0, len(self._wal)):
                        try:
                            if vars.getvalue('wassign[]')[i] == '1':
                                lst.append(('website', self._wal[i]))
                        except TypeError:
                            pass
                    for i in range(0, len(self._pal)):
                        try:
                            if vars.getvalue('passign[]')[i] == '1':
                                lst.append(('plugin', self._pal[i]))
                        except TypeError:
                            pass
                    self.statusmsg('Generating a certificate and key...')
                    try:
                        self._cc.gencert(name, vars, self._cfg.keytype,
                            self._cfg.keylength, self._hostname)
                        self.statusmsg('Assigning new certificate...')
                        self._cc.assign(name, lst)
                        self.put_message('success', 'Certificate successfully generated')
                    except Exception, e:
                        self.put_message('err', str(e))
                        self.app.log.error(str(e))
            self._wal = []
            self._pal = []
            self._gen = False
        elif params[0] == 'dlgInfo':
            self._tab = 0
            self._cinfo = None
            self._wal = []
            self._pal = []
        elif params[0] == 'dlgUpload':
            self._tab = 0
            if vars.getvalue('action', '') == 'OK':
                if not vars.has_key('certfile') and not vars.has_key('keyfile'):
                    self.put_message('err', 'Please select at least a certificate and private key')
                elif not vars.has_key('certfile'):
                    self.put_message('err', 'Please select a certificate file')
                elif not vars.has_key('keyfile'):
                    self.put_message('err', 'Please select a key file')
                elif not vars.getvalue('certname', ''):
                    self.put_message('err', 'Must choose a certificate name')
                elif vars.getvalue('certname', '') in [x.name for x in self.certs]:
                    self.put_message('err', 'You already have a certificate with that name.')
                elif re.search('\.|-|`|\\\\|\/|[ ]', vars.getvalue('certname')):
                    self.put_message('err', 'Certificate name must not contain spaces, dots, dashes or special characters')
                else:
                    try:
                        self._cc.add_ext_cert(vars.getvalue('certname'), 
                            vars['certfile'].value, vars['keyfile'].value,
                            vars['chainfile'].value if vars.has_key('chainfile') else None)
                        self.put_message('success', 'Certificate %s installed' % vars.getvalue('certname'))
                    except Exception, e:
                        self.put_message('err', 'Couldn\'t add certificate: %s' % str(e[0]))
                        self.app.log.error('Couldn\'t add certificate: %s - Error: %s' % (str(e[0]), str(e[1])))
            self._upload = None
        elif params[0] == 'frmCertSettings':
            self._tab = 1
            if vars.getvalue('action', '') == 'OK':
                self._cfg.keylength = vars.getvalue('keylength', '2048')
                self._cfg.keytype = vars.getvalue('keytype', 'RSA')
                self._cfg.ciphers = vars.getvalue('ciphers', '')
                self._cfg.save()
                self.put_message('success', 'Settings saved successfully')
