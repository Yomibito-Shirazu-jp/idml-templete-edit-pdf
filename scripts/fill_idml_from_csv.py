"""
fill_idml_from_csv.py

idml_variable_map.csv の text 列を pmi_template_variables.idml の
{{C_XXXXXX}} プレースホルダーに流し込んで output/pmi_filled.idml を生成。

作業者AI(または人間)は text 列だけ編集してよい。
var_id / story_id / psr_style / is_footnote / permission 列は変更禁止。
"""
import zipfile, shutil, os, csv, re

BASE  = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
TMPL  = os.path.join(BASE, 'templates', 'pmi_template_variables.idml')
CSV_  = os.path.join(BASE, 'idml_variable_map.csv')
OUT   = os.path.join(BASE, 'output', 'pmi_filled.idml')
WORK  = os.path.join(BASE, 'output', '_fill_work')

STORY_IDS = ['u987', 'u10a9', 'u12fa', 'u154b', 'u194b', 'u1e63', 'u2292']

VAR_PATTERN = re.compile(r'\{\{(C_\d{6})\}\}')


def xml_escape(s):
    return (s.replace('&', '&amp;')
              .replace('<', '&lt;')
              .replace('>', '&gt;')
              .replace('"', '&quot;'))


def main():
    # CSV ロード
    var_map = {}
    with open(CSV_, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            var_map[row['var_id']] = row['text']

    print(f"loaded {len(var_map)} variables from CSV")

    # テンプレート展開
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)

    z = zipfile.ZipFile(TMPL)
    z.extractall(WORK)
    z.close()

    filled = 0
    missing = []

    for sid in STORY_IDS:
        path = os.path.join(WORK, 'Stories', f'Story_{sid}.xml')
        with open(path, encoding='utf-8') as f:
            content = f.read()

        def replace_var(m):
            nonlocal filled
            vid = m.group(1)
            if vid in var_map:
                filled += 1
                return xml_escape(var_map[vid])
            else:
                missing.append(vid)
                return m.group(0)  # keep placeholder if not in CSV

        new_content = VAR_PATTERN.sub(replace_var, content)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    print(f"filled: {filled}, missing: {len(missing)}")
    if missing[:5]:
        print(f"  missing vars (first 5): {missing[:5]}")

    # 残存プレースホルダー確認
    leftover = []
    for sid in STORY_IDS:
        path = os.path.join(WORK, 'Stories', f'Story_{sid}.xml')
        with open(path, encoding='utf-8') as f:
            txt = f.read()
        found = VAR_PATTERN.findall(txt)
        leftover.extend(found)
    if leftover:
        print(f"WARNING: {len(leftover)} unfilled placeholders remain")

    # パッケージング
    if os.path.exists(OUT):
        os.remove(OUT)

    all_files = []
    for root_dir, dirs, files in os.walk(WORK):
        for fname in files:
            full = os.path.join(root_dir, fname)
            rel = os.path.relpath(full, WORK).replace(os.sep, '/')
            all_files.append((rel, full))
    all_files.sort(key=lambda x: (x[0] != 'mimetype', x[0]))

    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zout:
        zout.write(all_files[0][1], 'mimetype', compress_type=zipfile.ZIP_STORED)
        for rel, full in all_files[1:]:
            zout.write(full, rel)

    sz = os.path.getsize(OUT)
    zcheck = zipfile.ZipFile(OUT)
    bad = zcheck.testzip()
    zcheck.close()

    shutil.rmtree(WORK)
    print(f"wrote {OUT}  ({sz:,} bytes)  zip: {'OK' if bad is None else bad}")


if __name__ == '__main__':
    main()
