import json, re, sys
txt = open(sys.argv[1]).read()
def arr(name):
    m = re.search(r'^' + re.escape(name) + r': (\[.*\])$', txt, re.M)
    return json.loads(m.group(1)) if m else []
names, app, data, cache = arr("Package Names"), arr("App Sizes"), arr("App Data Sizes"), arr("Cache Sizes")
rows = [(n, a/1e6, d/1e6, c/1e6) for n, a, d, c in zip(names, app, data, cache)]
rows.sort(key=lambda r: -(r[1]+r[2]+r[3]))
print(f"{'package':52} {'apk MB':>8} {'data MB':>8} {'cache MB':>9} {'tổng':>8}")
for n, a, d, c in rows[:35]:
    print(f"{n:52} {a:8.0f} {d:8.0f} {c:9.0f} {a+d+c:8.0f}")
print(f"\nTổng số package: {len(rows)}; apk {sum(r[1] for r in rows)/1e3:.1f} GB, data {sum(r[2] for r in rows)/1e3:.1f} GB, cache {sum(r[3] for r in rows)/1e3:.2f} GB")
print("\nCache lớn nhất:")
for n, a, d, c in sorted(rows, key=lambda r: -r[3])[:12]:
    print(f"  {n:52} {c:8.0f} MB")
