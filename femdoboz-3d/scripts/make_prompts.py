"""Expand higgsfield/prompts.json into copy-paste prompts (higgsfield/PROMPTOK.md)."""
import json, os

here = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(here)
cfg = json.load(open(os.path.join(root, 'higgsfield', 'prompts.json'), encoding='utf-8'))
order = ['amphead', 'leather', 'steel']
out = ['# Higgsfield promptok – Hybrid Matrix', '',
       'Másold be a promptot, töltsd fel a megadott képe(ke)t, és állítsd be a modellt.',
       'Ajánlott: **Kling 3.0**, mód: `pro`, hang: `off` (a zenét a vágásnál teszed alá).',
       'Ha 1080p kell: **Seedance 2.5**, felbontás: `1080p`.', '']
for v in order:
    var = cfg['variants'][v]
    out += [f"## {var['label_hu']} (`{v}`)", '']
    for s in cfg['shots']:
        if s['id'] == 'F_lineup':
            continue
        p = s['prompt'].format(product_anchor=cfg['product_anchor'], material=var['material'],
                               macro_focus=var['macro_focus'], consistency_suffix=cfg['consistency_suffix'])
        start = s['start_image'].format(variant=v)
        end = s['end_image'].format(variant=v) if s['end_image'] else None
        out += [f"### {s['id']} · {s['duration_s']} mp · {s['aspect_ratio']}", '',
                f"- Start frame: `{start}`", f"- End frame: `{end}`" if end else '- End frame: nincs', '',
                '```', p, '```', '']
s = next(x for x in cfg['shots'] if x['id'] == 'F_lineup')
out += ['## Mindhárom verzió együtt', '', f"### F_lineup · {s['duration_s']} mp · {s['aspect_ratio']}", '',
        f"- Start frame: `{s['start_image']}`", '- End frame: nincs', '', '```',
        s['prompt'].format(consistency_suffix=cfg['consistency_suffix']), '```', '']
open(os.path.join(root, 'higgsfield', 'PROMPTOK.md'), 'w', encoding='utf-8').write('\n'.join(out))
print('ok')
