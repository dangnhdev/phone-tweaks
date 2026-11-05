import re, sys, collections
txt = open(sys.argv[1], errors="replace").read()
sec = None
last = collections.defaultdict(str); tot = collections.Counter(); launches = collections.Counter()
for line in txt.splitlines():
    m = re.match(r"\s*In-memory (\w+) stats", line)
    if m: sec = m.group(1); continue
    m = re.match(r'\s*package=(\S+) totalTimeUsed="([^"]*)" lastTimeUsed="([^"]*)".*?(?:appLaunchCount=(\d+))?', line)
    if not m: continue
    pkg, t, l, lc = m.groups()
    if l and l > last[pkg]: last[pkg] = l
    if sec == "yearly":
        h = re.match(r"(?:(\d+)d )?(?:(\d+)h )?(?:(\d+)m )?(?:(\d+)s )?", t + " ")
        d, hh, mm, ss = [int(x or 0) for x in h.groups()]
        tot[pkg] += d*86400 + hh*3600 + mm*60 + ss
        launches[pkg] += int(lc or 0)
print(f"{'package':52} {'năm, giờ':>7} {'lần mở':>8}  lần cuối")
for pkg, s in tot.most_common(70):
    print(f"{pkg:52} {s/3600:7.1f} {launches[pkg]:8}  {last[pkg][:16]}")
print("\nPackages có hoạt động:", len([p for p in last if last[p] and not last[p].startswith('1970')]))
