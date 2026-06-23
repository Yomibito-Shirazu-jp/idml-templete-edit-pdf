"""
patch_csv.py — v4→v5 の変更テキストを CSV に適用する

使い方:
  1. PATCHES リストに (旧テキスト, 新テキスト) を列挙する
     または --auto モードで v4_md / v5_md を指定して自動 diff

  2. python patch_csv.py
     → 変更された CSV 行を上書き保存 + patch_report.txt を出力

マッチング方式:
  - 完全一致を優先
  - 見つからなければ difflib.SequenceMatcher で最近傍 (ratio > 0.7) を使用
  - 複数候補がある場合は最もスコアが高い1行のみ更新

触ってよい列: text のみ
"""
import csv, difflib, os, sys

BASE   = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
CSV_   = os.path.join(BASE, 'idml_variable_map.csv')
REPORT = os.path.join(BASE, 'patch_report.txt')

# ─────────────────────────────────────────────────
# ここに変更を記述する
# ("旧テキスト（v4）", "新テキスト（v5）")
# ─────────────────────────────────────────────────
PATCHES = [
    # 例:
    # ("誤字のある旧テキスト", "修正済み新テキスト"),
    # ("もう一箇所の誤字", "修正済み"),
]
# ─────────────────────────────────────────────────


MATCH_THRESHOLD = 0.75  # 類似度閾値


def find_best_match(rows, old_text, is_footnote=None):
    """CSVから最も old_text に近い行インデックスを返す"""
    best_idx = None
    best_ratio = 0.0

    for i, row in enumerate(rows):
        if is_footnote is not None and row['is_footnote'] != str(is_footnote):
            continue
        ratio = difflib.SequenceMatcher(None, old_text, row['text']).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_ratio >= MATCH_THRESHOLD:
        return best_idx, best_ratio
    return None, best_ratio


def apply_patches_from_list(rows, patches):
    report = []
    changed = 0

    for old_text, new_text in patches:
        # 完全一致検索
        exact = [i for i, r in enumerate(rows) if r['text'] == old_text]
        if len(exact) == 1:
            i = exact[0]
            rows[i]['text'] = new_text
            report.append(f"EXACT var={rows[i]['var_id']} story={rows[i]['tag_name']}")
            report.append(f"  - {old_text[:80]}")
            report.append(f"  + {new_text[:80]}")
            report.append('')
            changed += 1
        elif len(exact) > 1:
            # 重複あり：最初の1件だけ更新して警告
            i = exact[0]
            rows[i]['text'] = new_text
            report.append(f"WARN: {len(exact)} exact matches, used first var={rows[i]['var_id']}")
            report.append(f"  - {old_text[:80]}")
            report.append(f"  + {new_text[:80]}")
            report.append('')
            changed += 1
        else:
            # 類似検索
            idx, ratio = find_best_match(rows, old_text)
            if idx is not None:
                rows[idx]['text'] = new_text
                report.append(f"FUZZY ratio={ratio:.3f} var={rows[idx]['var_id']} story={rows[idx]['tag_name']}")
                report.append(f"  original: {rows[idx]['text'][:80]}")
                report.append(f"  - {old_text[:80]}")
                report.append(f"  + {new_text[:80]}")
                report.append('')
                changed += 1
            else:
                report.append(f"MISS (ratio={ratio:.3f}): no match found for:")
                report.append(f"  {old_text[:80]}")
                report.append('')

    return changed, report


def auto_diff_patches(v4_md_path, v5_md_path):
    """v4/v5 MD ファイルを比較して変更行を自動抽出"""
    def load_lines(path):
        with open(path, encoding='utf-8') as f:
            text = f.read()
        # frontmatter スキップ
        if text.startswith('---'):
            end = text.index('---', 3) + 3
            text = text[end:]
        # 空行で分割した段落リスト
        import re
        return [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

    v4_paras = load_lines(v4_md_path)
    v5_paras = load_lines(v5_md_path)

    patches = []
    matcher = difflib.SequenceMatcher(None, v4_paras, v5_paras)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            # 1:1 置換のみ対応（段落数が変わる場合はスキップ）
            if (i2 - i1) == (j2 - j1):
                for k in range(i2 - i1):
                    old = v4_paras[i1 + k]
                    new = v5_paras[j1 + k]
                    if old != new:
                        patches.append((old, new))
    return patches


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--v4', help='v4 combined_body_only.md のパス')
    parser.add_argument('--v5', help='v5 combined_body_only.md のパス')
    args = parser.parse_args()

    rows = []
    with open(CSV_, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(dict(row))

    if args.v4 and args.v5:
        patches = auto_diff_patches(args.v4, args.v5)
        print(f"auto diff: {len(patches)} changes detected")
    else:
        patches = PATCHES
        print(f"manual patches: {len(patches)} entries")

    if not patches:
        print("パッチなし。PATCHES リストに変更を記述してください。")
        return

    changed, report = apply_patches_from_list(rows, patches)

    # CSV 書き戻し
    with open(CSV_, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # レポート
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write(f"=== patch_csv レポート ===\n変更行数: {changed}\n\n")
        f.write('\n'.join(report))

    print(f"{changed} 行更新完了 → {REPORT}")


if __name__ == '__main__':
    main()
