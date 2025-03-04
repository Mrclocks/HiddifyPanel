import glob
import re
import json
import subprocess

from datetime import datetime
from typing import Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from flask import current_app, g
from flask_babel import lazy_gettext as _
from flask_babel import gettext as __
from datetime import timedelta

from hiddifypanel.cache import cache
from hiddifypanel.models import *
from hiddifypanel.database import db
from hiddifypanel.hutils.utils import *
from hiddifypanel.Events import domain_changed
from hiddifypanel import hutils
from hiddifypanel.panel.run_commander import commander, Command
import subprocess
to_gig_d = 1000 * 1000 * 1000


# def add_temporary_access():
#     random_port = random.randint(30000, 50000)
#     # exec_command(
#     #     f'sudo /opt/hiddify-manager/hiddify-panel/temporary_access.sh {random_port} &')

#     # run temporary_access.sh
#     commander(Command.temporary_access, port=random_port)
#     temp_admin_link = f"http://{hutils.network.get_ip_str(4)}:{random_port}{get_admin_path()}"
#     g.temp_admin_link = temp_admin_link


# with user panel url format we don't really need this function
def add_short_link(link: str, period_min: int = 5) -> Tuple[str, int]:
    short_code, expire_date = add_short_link_imp(link, period_min)
    return short_code, (expire_date - datetime.now()).seconds


@cache.cache(ttl=300)
# TODO: Change ttl dynamically
def add_short_link_imp(link: str, period_min: int = 5) -> Tuple[str, datetime]:
    # pattern = "\^/([^/]+)(/)?\?\$\ {return 302 " + re.escape(link) + ";}"

    pattern = r"([^/]+)\("

    with open(current_app.config['HIDDIFY_CONFIG_PATH'] + "/nginx/parts/short-link.conf", 'r') as f:
        for line in f:
            if link in line:
                return re.search(pattern, line).group(1), datetime.now() + timedelta(minutes=period_min)

    short_code = hutils.random.get_random_string(6, 10).lower()
    # exec_command(
    #     f'sudo /opt/hiddify-manager/nginx/add2shortlink.sh {link} {short_code} {period_min} &')

    commander(Command.temporary_short_link, url=link, slug=short_code, period=period_min)

    return short_code, datetime.now() + timedelta(minutes=period_min)


def exec_command(cmd, cwd=None):
    try:
        subprocess.Popen(cmd.split(" "))  # run in background
    except Exception as e:
        print(e)


@cache.cache(ttl=300)
def get_available_proxies(child_id):
    proxies = Proxy.query.filter(Proxy.child_id == child_id).all()
    proxies = [c for c in proxies if 'restls' not in c.transport]
    # if not hconfig(ConfigEnum.tuic_enable, child_id):
    #     proxies = [c for c in proxies if c.proto != ProxyProto.tuic]
    # if not hconfig(ConfigEnum.hysteria_enable, child_id):
    #     proxies = [c for c in proxies if c.proto != ProxyProto.hysteria2]
    if not hconfig(ConfigEnum.shadowsocks2022_enable, child_id):
        proxies = [c for c in proxies if 'shadowsocks' != c.transport]

    if not hconfig(ConfigEnum.ssfaketls_enable, child_id):
        proxies = [c for c in proxies if 'faketls' != c.transport]
    if not hconfig(ConfigEnum.v2ray_enable, child_id):
        proxies = [c for c in proxies if 'v2ray' != c.proto]
    if not hconfig(ConfigEnum.shadowtls_enable, child_id):
        proxies = [c for c in proxies if c.transport != 'shadowtls']
    if not hconfig(ConfigEnum.ssr_enable, child_id):
        proxies = [c for c in proxies if 'ssr' != c.proto]
    if not hconfig(ConfigEnum.vmess_enable, child_id):
        proxies = [c for c in proxies if 'vmess' not in c.proto]
    if not hconfig(ConfigEnum.httpupgrade_enable, child_id):
        proxies = [c for c in proxies if ProxyTransport.httpupgrade not in c.transport]
    if not hconfig(ConfigEnum.ws_enable, child_id):
        proxies = [c for c in proxies if ProxyTransport.WS not in c.transport]

    if not hconfig(ConfigEnum.grpc_enable, child_id):
        proxies = [c for c in proxies if ProxyTransport.grpc not in c.transport]
    if not hconfig(ConfigEnum.kcp_enable, child_id):
        proxies = [c for c in proxies if 'kcp' not in c.l3]

    if not hconfig(ConfigEnum.http_proxy_enable, child_id):
        proxies = [c for c in proxies if 'http' != c.l3]

    if not Domain.query.filter(Domain.mode.in_([DomainType.cdn, DomainType.auto_cdn_ip])).first():
        proxies = [c for c in proxies if c.cdn != "CDN"]

    if not Domain.query.filter(Domain.mode.in_([DomainType.relay])).first():
        proxies = [c for c in proxies if c.cdn != ProxyCDN.relay]

    if not Domain.query.filter(Domain.mode.in_([DomainType.cdn, DomainType.auto_cdn_ip]), Domain.servernames != "", Domain.servernames != Domain.domain).first():
        proxies = [c for c in proxies if 'Fake' not in c.cdn]
    proxies = [c for c in proxies if not ('vless' == c.proto and ProxyTransport.tcp == c.transport and c.cdn == ProxyCDN.direct)]
    return proxies


def quick_apply_users():
    if hconfig(ConfigEnum.is_parent):
        return
    # from hiddifypanel.panel import usage
    # usage.update_local_usage()
    # return
    # for user in User.query.all():
    #     if user.is_active:
    #         xray_api.add_client(user.uuid)
    #     else:
    #         xray_api.remove_client(user.uuid)

    # exec_command("sudo /opt/hiddify-manager/install.sh apply_users --no-gui")

    # run install.sh apply_users
    commander(Command.apply_users)

    # time.sleep(1)
    return {"status": 'success'}


# Importing socket library

# Function to display hostname and
# IP address


def get_html_user_link(model: BaseAccount, domain: Domain):
    is_cdn = domain.mode == DomainType.cdn if isinstance(domain, Domain) else False
    res = ""
    d = domain.domain
    if "*" in d:
        d = d.replace("*", hutils.random.get_random_string(5, 15))

    link = f'{get_account_panel_link(model, d)}#{hutils.encode.unicode_slug(model.name)}'

    text = domain.alias or domain.domain
    color_cls = 'info'

    if isinstance(domain, Domain) and not domain.sub_link_only and domain.mode in [DomainType.cdn, DomainType.auto_cdn_ip]:
        auto_cdn = (domain.mode == DomainType.auto_cdn_ip) or (domain.cdn_ip and "MTN" in domain.cdn_ip)
        color_cls = "success" if auto_cdn else 'warning'
        text = f'<span class="badge badge-secondary" >{"Auto" if auto_cdn else "CDN"}</span> ' + text

    res += f"<a target='_blank' data-copy='{link}' href='{link}' class='btn btn-xs btn-{color_cls} ltr share-link' ><i class='fa-solid fa-arrow-up-right-from-square d-none'></i> {text}</a>"

    return res


def reinstall_action(complete_install=False, domain_changed=False, do_update=False):
    from hiddifypanel.panel.admin.Actions import Actions
    action = Actions()
    if do_update:
        return action.update()
    return action.reinstall(complete_install=complete_install, domain_changed=domain_changed)


def check_need_reset(old_configs, do=False):
    restart_mode = ApplyMode.nothing
    for c in old_configs:
        # c=ConfigEnum(c)
        if old_configs[c] != hconfig(c) and c.apply_mode != ApplyMode.nothing:
            if restart_mode != ApplyMode.restart:
                restart_mode = c.apply_mode
    if old_configs[ConfigEnum.proxy_path_admin] != hconfig(ConfigEnum.proxy_path_admin):
        g.new_proxy_path = hconfig(ConfigEnum.proxy_path_admin)
        g.force_proxy_path = g.proxy_path
    # do_full_install=old_config[ConfigEnum.telegram_lib]!=hconfig(ConfigEnum.telegram_lib)
    if old_configs[ConfigEnum.package_mode] != hconfig(ConfigEnum.package_mode):
        return reinstall_action(do_update=True)
    if not (do and restart_mode == ApplyMode.restart):
        return hutils.flask.flash_config_success(restart_mode=restart_mode, domain_changed=False)

    return reinstall_action(complete_install=True, domain_changed=False)


def get_child(unique_id):
    child_id = Child.current.id
    if unique_id is None or unique_id in ["self", "default", str(hconfig(ConfigEnum.unique_id))]:
        child_id = 0
    else:
        child = Child.query.filter(Child.unique_id == str(unique_id)).first()
        if not child:
            child = Child(unique_id=str(unique_id))
            db.session.add(child)
            db.session.commit()
            child = Child.query.filter(Child.unique_id == str(unique_id)).first()
        child_id = child.id
    return child_id


def dump_db_to_dict():
    return {"childs": [u.to_dict() for u in Child.query.all()],
            "users": [u.to_dict() for u in User.query.all()],
            "domains": [u.to_dict() for u in Domain.query.all()],
            "proxies": [u.to_dict() for u in Proxy.query.all()],
            "parent_domains": [] if not hconfig(ConfigEnum.license) else [u.to_dict() for u in ParentDomain.query.all()],
            'admin_users': [d.to_dict() for d in AdminUser.query.all()],
            "hconfigs": [*[u.to_dict() for u in BoolConfig.query.all()],
                         *[u.to_dict() for u in StrConfig.query.all()]]
            }


def get_ids_without_parent(input_dict):
    selector = "uuid"
    # Get all parent_uuids in a set for faster lookup
    parent_uuids = {item.get(f'parent_admin_uuid') for item in input_dict.values()
                    if item.get(f'parent_admin_uuid') is not None
                    and item.get(f'parent_admin_uuid') != item.get('uuid')}
    print("PARENTS", parent_uuids)
    uuids = {v['uuid']: v for v in input_dict.values()}
    # Find all uuids that do not have a parent_uuid in the dict
    uuids_without_parent = [key for key, item in input_dict.items()
                            if item.get(f'parent_admin_uuid') is None
                            or item.get(f'parent_admin_uuid') == item.get('uuid')
                            or item[f'parent_admin_uuid'] not in uuids]
    print("abondon uuids", uuids_without_parent)
    return uuids_without_parent


def set_db_from_json(json_data, override_child_unique_id=True, set_users=True, set_domains=True, set_proxies=True, set_settings=True, remove_domains=False, remove_users=False,
                     override_unique_id=True, set_admins=True, override_root_admin=False, replace_owner_admin=False, fix_admin_hierarchy=True, set_child=True):
    new_rows = []

    # override root child unique id
    if override_child_unique_id:
        backup_child_unique_id = get_backup_child_unique_id(json_data)
        replace_backup_child_unique_id(json_data, backup_child_unique_id, Child.current.unique_id)

    # restore childs
    if set_child and 'childs' in json_data:
        Child.bulk_register(json_data['childs'], commit=True)

    uuids_without_parent = get_ids_without_parent({u['uuid']: u for u in json_data['admin_users']})
    print('uuids_without_parent===============', uuids_without_parent)
    if replace_owner_admin and len(uuids_without_parent):
        new_owner_uuid = uuids_without_parent[0]
        old_owner = AdminUser.query.filter(AdminUser.id == 1).first()
        old_uuid_admin = AdminUser.query.filter(AdminUser.uuid == new_owner_uuid).first()
        if old_owner and not old_uuid_admin:
            old_owner.uuid = new_owner_uuid
            db.session.commit()

    all_admins = {u.uuid: u for u in AdminUser.query.all()}
    uuids_without_parent = [uuid for uuid in uuids_without_parent if uuid not in all_admins]
    print('uuids_not admin exist===============', uuids_without_parent)

    if "admin_users" in json_data:
        for u in json_data['admin_users']:
            if override_root_admin and u['uuid'] in uuids_without_parent:
                u['uuid'] = AdminUser.current_admin_or_owner().uuid
            if u['parent_admin_uuid'] in uuids_without_parent:
                u['parent_admin_uuid'] = AdminUser.current_admin_or_owner().uuid
        # fix admins hierarchy
        if fix_admin_hierarchy and len(json_data['admin_users']) > 2:
            hierarchy_is_ok = False
            for u in json_data['admin_users']:
                if u['uuid'] == AdminUser.current_admin_or_owner().uuid:
                    continue
                if u['parent_admin_uuid'] == AdminUser.current_admin_or_owner().uuid:
                    hierarchy_is_ok = True
                    break
            if not hierarchy_is_ok:
                json_data['admin_users'][1]['parent_admin_uuid'] = AdminUser.current_admin_or_owner().uuid

    if "users" in json_data and override_root_admin:
        for u in json_data['users']:
            if u['added_by_uuid'] in uuids_without_parent:
                u['added_by_uuid'] = AdminUser.current_admin_or_owner().uuid

    if set_admins and 'admin_users' in json_data:
        AdminUser.bulk_register(json_data['admin_users'], commit=False)
    if set_users and 'users' in json_data:
        User.bulk_register(json_data['users'], commit=False, remove=remove_users)
    if set_domains and 'domains' in json_data:
        bulk_register_domains(json_data['domains'], commit=False, remove=remove_domains, override_child_unique_id=override_child_unique_id)
    # if set_domains and 'parent_domains' in json_data:
    #     ParentDomain.bulk_register(json_data['parent_domains'], commit=False, remove=remove_domains)
    if set_settings and 'hconfigs' in json_data:
        bulk_register_configs(json_data["hconfigs"], commit=True, override_child_unique_id=override_child_unique_id, override_unique_id=override_unique_id)
        if 'proxies' in json_data:
            Proxy.bulk_register(json_data['proxies'], commit=False, override_child_unique_id=override_child_unique_id)

    ids_without_parent = get_ids_without_parent({u.id: u.to_dict() for u in AdminUser.query.all()})
    owner = AdminUser.get_super_admin()
    ids_without_parent = [id for id in ids_without_parent if id != owner.id]

    for u in AdminUser.query.all():
        if u.parent_admin_id in ids_without_parent:
            u.parent_admin_id = owner.id
    # for u in User.query.all():
    #     if u.added_by in uuids_without_parent:
    #         u.added_by = g.account.id

    db.session.commit()


def get_domain_btn_link(domain):
    text = domain.alias or domain.domain
    color_cls = "info"
    if domain.mode in [DomainType.cdn, DomainType.auto_cdn_ip]:
        auto_cdn = (domain.mode == DomainType.auto_cdn_ip) or (domain.cdn_ip and "MTN" in domain.cdn_ip)
        color_cls = "success" if auto_cdn else 'warning'
        text = f'<span class="badge badge-secondary" >{"Auto" if auto_cdn else "CDN"}</span> ' + text
    res = f"<a target='_blank' href='#' class='btn btn-xs btn-{color_cls} ltr' ><i class='fa-solid fa-arrow-up-right-from-square d-none'></i> {text}</a>"
    return res


def debug_flash_if_not_in_the_same_asn(domain):
    from hiddifypanel.hutils.network.auto_ip_selector import IPASN
    ipv4 = hutils.network.get_ip_str(4)
    dip = hutils.network.get_domain_ip(domain)
    try:
        if IPASN:
            asn_ipv4 = IPASN.get(ipv4)
            asn_dip = IPASN.get(dip)
            # country_ipv4= ipcountry.get(ipv4)
            # country_dip= ipcountry.get(dip)
            if asn_ipv4.get('autonomous_system_organization') != asn_dip.get('autonomous_system_organization'):
                hutils.flask.flash(_("selected domain for REALITY is not in the same ASN. To better use of the protocol, it is better to find a domain in the same ASN.") +
                                   f"<br> Server ASN={asn_ipv4.get('autonomous_system_organization','unknown')}<br>{domain}_ASN={asn_dip.get('autonomous_system_organization','unknown')}", "warning")
    except BaseException:
        pass


def generate_x25519_keys():
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    import base64
    pub_str = base64.urlsafe_b64encode(pub_bytes).decode()[:-1]
    priv_str = base64.urlsafe_b64encode(priv_bytes).decode()[:-1]

    return {'private_key': priv_str, 'public_key': pub_str}


def get_hostkeys(dojson=False):
    key_files = glob.glob(current_app.config['HIDDIFY_CONFIG_PATH'] + "/other/ssh/host_key/*_key.pub")
    host_keys = []
    for file_name in key_files:
        with open(file_name, "r") as f:
            host_key = f.read().strip()
            host_key = host_key.split()
            if len(host_key) > 2:
                host_key = host_key[:2]  # strip the hostname part
            host_key = " ".join(host_key)
            host_keys.append(host_key)
    if dojson:
        return json.dumps(host_keys)
    return host_keys


def get_ssh_client_version(user):
    return 'SSH-2.0-OpenSSH_7.4p1'


def get_ed25519_private_public_pair():
    from cryptography.hazmat.primitives.asymmetric import ed25519
    from cryptography.hazmat.primitives import serialization
    privkey = ed25519.Ed25519PrivateKey.generate()
    pubkey = privkey.public_key()
    priv_bytes = privkey.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = pubkey.public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    return priv_bytes.decode(), pub_bytes.decode()


def get_wg_private_public_psk_pair():
    try:
        private_key = subprocess.run(["wg", "genkey"], capture_output=True, text=True, check=True).stdout.strip()
        public_key = subprocess.run(["wg", "pubkey"], input=private_key, capture_output=True, text=True, check=True).stdout.strip()
        psk = subprocess.run(["wg", "genpsk"], capture_output=True, text=True, check=True).stdout.strip()
        return private_key, public_key, psk
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return None, None, None


def get_account_panel_link(account: BaseAccount, host: str, is_https: bool = True, prefere_path_only: bool = False, child_id=None):
    if child_id is None:
        child_id = Child.current.id
    is_admin = isinstance(account, AdminUser)
    basic_auth = False  # is_admin #because safri does not support it.

    link = ""
    if basic_auth or not prefere_path_only:
        link = "https://" if is_https else "http://"
        if basic_auth:
            link += f'{account.uuid}@'
        link += str(host)
    proxy_path = hconfig(ConfigEnum.proxy_path_admin if is_admin else ConfigEnum.proxy_path_client, child_id)
    link += f'/{proxy_path}/'
    if child_id != 0:
        child = Child.by_id(child_id)
        link += f"{child.id}/"
    if basic_auth:
        link += "l"
    else:
        link += f'{account.uuid}/'
    return link


def is_telegram_proxy_enable() -> bool:
    ok_domains = True if Domain.query.filter(Domain.mode.in_([DomainType.direct, DomainType.relay, DomainType.old_xtls_direct])).first() else False
    return hconfig(ConfigEnum.telegram_enable) and ok_domains


def clone_model(model):
    """Clone an arbitrary sqlalchemy model object without its primary key values."""
    # Ensure the model’s data is loaded before copying.
    # model.id
    new_model = model.__class__()
    table = model.__table__
    for k in table.columns.keys():
        if k == "id":
            continue
        # if k in table.primary_key:
        #     continue
        setattr(new_model, f'{k}', getattr(model, k))

    # data.pop('id')
    return new_model


def replace_backup_child_unique_id(backupdata: dict, old_child_unique_id: str, new_child_unique_id: str):
    for k, v in backupdata.copy().items():
        if k == 'admin_users' or k == 'users':
            continue
        if k == 'childs':
            if len(v) < 1:
                continue

            if v[0]['unique_id'] == old_child_unique_id or v[0]['unique_id'] == 'self' or v[0]['unique_id'] == 'default':
                v[0]['unique_id'] = new_child_unique_id
        else:
            for item in v:
                if item['child_unique_id'] == old_child_unique_id or item['child_unique_id'] == 'self' or item['child_unique_id'] == 'default':
                    item['child_unique_id'] = new_child_unique_id


def get_backup_child_unique_id(backupdata: dict) -> str:
    if len(backupdata.get('childs', [])) == 0:
        return "self"
    return backupdata['childs'][0]['unique_id']

    # for k, v in backupdata.items():
    #     if k == 'admin_users' or k == 'users':
    #         continue
    #     if k == 'childs':
    #         if len(v) < 1:
    #             continue
    #         return v[0]['unique_id']
    #     else:
    #         for item in v:
    #             return item['child_unique_id']
    # return 'self'


def is_hiddify_next_version(major_v: int = 0, minor_v: int = 0, patch_v: int = 0) -> bool:
    '''If the user agent version be equals or higher than parameters returns True'''
    if not g.user_agent.get('hiddify_version'):
        return False
    raw_v = g.user_agent['hiddify_version']
    raw_v_len = len(raw_v)
    u_major_v = raw_v[0] if raw_v_len > 0 else 0
    u_minor_v = raw_v[1] if raw_v_len > 1 else 0
    u_patch_v = raw_v[2] if raw_v_len > 2 else 0

    if u_major_v >= major_v and u_minor_v >= minor_v and u_patch_v >= patch_v:
        return True
    return False
