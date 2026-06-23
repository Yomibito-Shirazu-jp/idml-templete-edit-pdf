"""
make_variable_template.py

本文PMI_v3.idml から:
  1. pmi_template_variables.idml  (Content を {{C_XXXXXX}} に置換)
  2. idml_variable_map.csv        (var_id → story/style/text のマップ)

を生成する。

粒度: 1 Content要素 = 1変数 (脚注も同様)
"""
import zipfile, shutil, os, csv, re
from lxml import etree

SRC  = r'E:\ideml\本文PMI_v3.idml'
OUT  = r'E:\pmi_typesetting\templates\pmi_template_variables.idml'
CSV_ = r'E:\pmi_typesetting\idml_variable_map.csv'
WORK = r'C:\tmp\var_template_work'

STORY_TAGS = [
    ('story_00_prologue_ch01_rt01', 'u987'),
    ('story_02_ch02_rt02',          'u10a9'),
    ('story_03_ch03_rt03',          'u12fa'),
    ('story_04_ch04_rt04',          'u154b'),
    ('story_05_ch05_rt05',          'u194b'),
    ('story_06_ch06_rt06',          'u1e63'),
    ('story_07_epilogue_message',   'u2292'),
]


_GLOBAL_COUNTER = [0]  # モジュール共有カウンター


def extract_and_variablize(story_xml_bytes):
    """
    Story XMLの全Content要素にvar_idを付与し、テキストを{{C_XXXXXX}}に置換。
    Returns: (new_xml_bytes, rows)
    """
    root = etree.fromstring(story_xml_bytes)
    rows = []

    def next_id():
        _GLOBAL_COUNTER[0] += 1
        return f'C_{_GLOBAL_COUNTER[0]:06d}'

    for psr_idx, psr in enumerate(root.iter('ParagraphStyleRange')):
        style = psr.get('AppliedParagraphStyle', '').replace('ParagraphStyle/', '')

        # このPSR内の全CharacterStyleRange（脚注の中も含む）
        for csr in psr.iter('CharacterStyleRange'):
            # このCSRが脚注の中かどうか判定
            is_fn = csr.getparent() is not None and csr.getparent().tag == 'Footnote'
            # 脚注の中のPSRを判定
            parent = csr
            while parent is not None:
                if parent.tag == 'Footnote':
                    is_fn = True
                    break
                parent = parent.getparent()

            for content in csr.findall('Content'):
                orig = content.text or ''
                # 空、または既に他のPSRイテレーションで variablize済みならスキップ
                if not orig or orig.startswith('{{C_'):
                    continue
                vid = next_id()
                rows.append({
                    'var_id': vid,
                    'psr_idx': psr_idx,
                    'psr_style': style,
                    'is_footnote': is_fn,
                    'text': orig,
                })
                content.text = '{{' + vid + '}}'

    new_bytes = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
    return new_bytes, rows


def main():
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)

    z = zipfile.ZipFile(SRC)
    z.extractall(WORK)
    z.close()

    all_rows = []
    for tag_name, story_id in STORY_TAGS:
        path = os.path.join(WORK, 'Stories', f'Story_{story_id}.xml')
        with open(path, 'rb') as f:
            story_bytes = f.read()

        new_bytes, rows = extract_and_variablize(story_bytes)

        # story_id と tag_name を各行に付与
        for r in rows:
            r['story_id'] = story_id
            r['tag_name'] = tag_name
        all_rows.extend(rows)

        with open(path, 'wb') as f:
            f.write(new_bytes)

        print(f"  {story_id}: {len(rows)} variables")

    # CSV 書き出し
    fieldnames = ['var_id', 'tag_name', 'story_id', 'psr_idx', 'psr_style', 'is_footnote', 'text', 'permission']
    with open(CSV_, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            r['permission'] = 'TEXT_ONLY_REPLACE'
            w.writerow(r)

    print(f"\nCSV: {CSV_}  ({len(all_rows)} rows)")

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
    print(f"wrote {OUT}  ({sz:,} bytes)")
    shutil.rmtree(WORK)
    print("done")


if __name__ == '__main__':
    main()
