"""
inject_xml_to_idml.py — xml/*.xml を pmi_template.idml の Stories に注入して output/pmi_generated.idml を生成

動作:
1. templates/pmi_template.idml を展開（Spreads/MasterSpreads/Resources は一切変更しない）
2. xml/*.xml の各ファイルについて、対応する Stories/Story_XXXX.xml を差し替える
3. IDML再パッケージング → output/pmi_generated.idml
"""
import zipfile, shutil, os, glob, re
from lxml import etree

BASE  = os.path.dirname(__file__) + '/..'
TMPL  = os.path.normpath(f'{BASE}/templates/pmi_template.idml')
XML_D = os.path.normpath(f'{BASE}/xml')
OUT   = os.path.normpath(f'{BASE}/output/pmi_generated.idml')
WORK  = os.path.normpath(f'{BASE}/output/_work')

# tag_name → story_id のマッピング
TAG_TO_STORY = {
    'story_00_prologue_ch01_rt01': 'u987',
    'story_02_ch02_rt02':          'u10a9',
    'story_03_ch03_rt03':          'u12fa',
    'story_04_ch04_rt04':          'u154b',
    'story_05_ch05_rt05':          'u194b',
    'story_06_ch06_rt06':          'u1e63',
    'story_07_epilogue_message':   'u2292',
}


def build_story_xml(xml_content, template_story_xml):
    """
    xml/*.xml (md_to_xml.py 生成) と テンプレートStory XMLを組み合わせる。
    テンプレートのStory要素の属性（Self, TextFile等）は維持しつつ、
    XMLElement の中身（ParagraphStyleRange群）を注入したものに差し替える。
    """
    # 注入元: XMLElement内のコンテンツを取得
    src_root = etree.fromstring(xml_content.encode('utf-8'))
    # <XMLElement Self="..."> の直下の ParagraphStyleRange群
    src_xe = src_root.find('.//XMLElement')
    if src_xe is None:
        raise ValueError("注入元XMLにXMLElementが見つかりません")
    new_children = list(src_xe)

    # テンプレート: 既存 XMLElement を探して子を差し替え
    tmpl_root = etree.fromstring(template_story_xml.encode('utf-8'))
    tmpl_story = tmpl_root[0]  # <Story Self="...">

    # XMLElement ラッパーを探す
    xe = None
    for child in tmpl_story:
        if child.tag == 'XMLElement':
            xe = child
            break

    if xe is None:
        # XMLElement がない場合（テンプレートが古い）→ 直接 Story に追加
        for child in list(tmpl_story):
            tmpl_story.remove(child)
        wrapper = etree.SubElement(tmpl_story, 'XMLElement',
                                    Self='xe_injected',
                                    MarkupTag=f'XMLTag/{src_xe.get("MarkupTag","").replace("XMLTag/","")}')
        for child in new_children:
            wrapper.append(child)
    else:
        # XMLElement の子をすべて差し替え
        for child in list(xe):
            xe.remove(child)
        for child in new_children:
            xe.append(child)

    return etree.tostring(tmpl_root, xml_declaration=True, encoding='UTF-8', standalone=True).decode('utf-8')


def main():
    # ワーク展開
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)

    z = zipfile.ZipFile(TMPL)
    z.extractall(WORK)
    z.close()
    print(f"template extracted to {WORK}")

    # xml/*.xml を Story に注入
    xml_files = sorted(glob.glob(os.path.join(XML_D, '*.xml')))
    if not xml_files:
        print("xml/ にファイルがありません。md_to_xml.py を先に実行してください。")
        return

    injected = []
    for xml_path in xml_files:
        tag_name = os.path.splitext(os.path.basename(xml_path))[0]
        story_id = TAG_TO_STORY.get(tag_name)
        if story_id is None:
            print(f"  SKIP {tag_name} (TAG_TO_STORY に登録なし)")
            continue

        story_path = os.path.join(WORK, 'Stories', f'Story_{story_id}.xml')
        if not os.path.exists(story_path):
            print(f"  SKIP {tag_name} (Story_{story_id}.xml が見つからない)")
            continue

        with open(xml_path, encoding='utf-8') as f:
            xml_content = f.read()
        with open(story_path, encoding='utf-8') as f:
            tmpl_story = f.read()

        try:
            new_story = build_story_xml(xml_content, tmpl_story)
            with open(story_path, 'w', encoding='utf-8') as f:
                f.write(new_story)
            injected.append(tag_name)
            print(f"  injected: {tag_name} → Story_{story_id}.xml")
        except Exception as e:
            print(f"  ERROR {tag_name}: {e}")

    if not injected:
        print("注入できたStoryがありません")
        shutil.rmtree(WORK)
        return

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
    print(f"\nwrote {OUT}  ({sz:,} bytes)")
    print(f"zip integrity: {'OK' if bad is None else bad}")
    print(f"注入したStory: {len(injected)}/{len(TAG_TO_STORY)}")


if __name__ == '__main__':
    main()
