import re, sys
txt = open(sys.argv[1], errors="replace").read()
start = txt.find("\nPackages:\n")
end = txt.find("\nShared users:", start) if txt.find("\nShared users:", start) > 0 else len(txt)
body = txt[start:end]
blocks = re.split(r"\n  Package \[", body)[1:]
rows = []
for b in blocks:
    name = b.split("]", 1)[0]
    g = lambda k: (re.search(r"^\s*" + k + r"=(\S+)", b, re.M) or [None, ""])[1]
    flags = (re.search(r"^\s*flags=\[([^\]]*)\]", b, re.M) or [None, ""])[1]
    pflags = (re.search(r"^\s*privateFlags=\[([^\]]*)\]", b, re.M) or [None, ""])[1]
    u0 = re.search(r"^\s*User 0:(.*)$", b, re.M)
    u0 = u0.group(1) if u0 else ""
    ug = lambda k: (re.search(k + r"=(\S+)", u0) or [None, ""])[1]
    fit = ug("firstInstallTime") or g("firstInstallTime")
    rows.append(dict(pkg=name, system="SYS" if " SYSTEM " in f" {flags} " else "3rd",
        code=g("codePath"), ver=g("versionName"), inst=g("installerPackageName") or "-",
        first=fit, upd=g("lastUpdateTime"), enabled=ug("enabled"), installed=ug("installed"),
        stopped=ug("stopped"), pflags=pflags))
import csv
w = csv.DictWriter(open(sys.argv[2], "w"), fieldnames=['pkg', 'system', 'code', 'ver', 'inst', 'first', 'upd', 'enabled', 'installed', 'stopped', 'pflags'], delimiter="\t")
w.writeheader(); [w.writerow(r) for r in rows]
print(f"Tổng packages trong dumpsys: {len(rows)}")
def show(title, rs):
    print(f"\n=== {title} ({len(rs)}) ===")
    print(f"{'package':48} {'ver':16} {'installer':30} {'first':10} {'upd':10} {'en':2} {'inst':5} {'code'}")
    for r in sorted(rs, key=lambda r: r['first']):
        code = r['code'].replace('/data/app/~~','/data/app/…')[:40]
        print(f"{r['pkg'][:48]:48} {r['ver'][:16]:16} {r['inst'][:30]:30} {r['first'][:10]:10} {r['upd'][:10]:10} {r['enabled']:2} {r['installed']:5} {code}")
show("Ứng dụng bên thứ ba (3rd)", [r for r in rows if r['system']=="3rd"])
show("Không cài cho user 0 (installed=false)", [r for r in rows if r['installed']=="false"])
show("Đã tắt (enabled=2/3/4)", [r for r in rows if r['enabled'] in ("2","3","4")])
show("System packages cập nhật trong /data/app", [r for r in rows if r['system']=="SYS" and r['code'].startswith("/data/app")])
